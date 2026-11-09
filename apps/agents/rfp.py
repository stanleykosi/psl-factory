from django.core.exceptions import ValidationError,PermissionDenied
from django.db import transaction
from apps.core.services import lock_case,event
from apps.identity.services import require
from apps.pmo.rfp import root,source_snapshot,reviewed
from apps.pmo.commercial import valid_approvals
from adapters.rfp import LocalRFPAdapter
from .models import AgentRun

def intake_revision_findings(actor, rfp):
    """Proposed assistance only: compare typed references, never interpret source prose.

    No new business gate or contact is created. Retained source bodies, dates and
    identifiers are deliberately absent from the persisted question, so a later
    permission change cannot expose old content through an investigation history.
    """
    current = rfp.current_intake
    previous = rfp.intakes.filter(number__lt=current.number).order_by('-number').first()
    if previous is None:
        return []
    from apps.core.evidence_access import public_evidence
    from apps.core.models import Evidence
    try:
        require(actor, rfp.case, 'case.read')
        require(actor, rfp.case, 'rfp.read')
        for intake in (previous, current):
            require(intake.actor, rfp.case, 'rfp.intake')
            sources = [(intake.evidence_id, 'rfp_intake')]
            if intake.deadline_evidence_id:
                sources.append((intake.deadline_evidence_id, 'rfp_deadline'))
            for source_id, kind in sources:
                source = public_evidence(Evidence.objects.filter(case=rfp.case, pk=source_id, kind=kind)).first()
                if source is None:
                    raise PermissionDenied('Source unavailable')
                require(source.created_by, rfp.case, 'evidence.add')
    except PermissionDenied:
        return ['Retained intake comparison is unavailable under current source access; ask the source owner for a permitted clarification.']
    source_changed = previous.evidence_id != current.evidence_id
    deadline_changed = (previous.deadline_status, previous.deadline_at, previous.deadline_evidence_id) != (
        current.deadline_status, current.deadline_at, current.deadline_evidence_id)
    if source_changed:
        return ['The intake requirements source reference was revised. Ask the source owner which requirements changed and to clarify the recorded deadline; source text has not been interpreted.']
    if deadline_changed:
        return ['The recorded deadline status, time or source reference changed. Ask the source owner to clarify the deadline and whether requirements also changed; no requirements change is inferred.']
    return []


@transaction.atomic
def investigate_rfp(actor,case_id,expected):
    case=lock_case(actor,case_id,'agent.rfp',expected);require(actor,case,'rfp.read');r=root(case);result=LocalRFPAdapter().read(r);findings=intake_revision_findings(actor,r)
    try:source_snapshot(r)
    except (ValidationError,PermissionDenied) as exc:findings.append(str(exc))
    from apps.pmo.models import RFPDisposition
    disposition=RFPDisposition.objects.filter(rfp=r).first()
    v=r.current_response
    if v and not disposition:
        for check in [lambda:reviewed(v),lambda:valid_approvals(v.commercial,['PM','Head of PMO','CEO'])]:
            try:check()
            except (ValidationError,PermissionDenied) as exc:findings.append(str(exc))
        findings.extend('Requirement '+row['key']+' needs explicit follow-up: '+row['disposition'] for row in v.matrix if row['disposition']!='addressed')
        if not v.submissions.exists():findings.append('No actual controlled submission receipt recorded')
        if not v.submissions.filter(outcomes__isnull=False).exists():findings.append('Outcome remains unknown until relationship-owner evidence is captured')
    elif not v:findings.append('Assigned PM should prepare a cited technical/commercial response from all four inputs')
    result.update(findings=findings,approval_granted=False,submission_dispatched=False,capability='A01/A02/A04/A07 cited RFP intake, coverage and next-work investigation',
        next_work='Resolve cited input and coverage gaps; obtain separate response reviews, ordered costing decisions and outward document review. Record actual delivery and outcome; a win starts Route A with fresh SOW controls.')
    if disposition:
        result.update(recorded_disposition={'id':disposition.pk,'kind':disposition.kind},next_work=
            'Preserve the RFP submission and outcome. Continue Route A with a fresh project SOW and its own commercial approvals/signature.' if disposition.kind=='route_a' else
            'Preserve the loss archive, response and cited lessons. Remote archive export and retention execution remain separate work.')
    # Datetimes in adapter output are serialized as ISO evidence, never executable tool instructions.
    for s in result['submissions']:s['submitted_at']=s['submitted_at'].isoformat()
    run=AgentRun.objects.create(case=case,actor=actor,evidence=r.current_intake.evidence,provider='deterministic-rfp-investigation-v1',process_id='P47',result=result)
    event(actor,case,'agent.rfp_investigation',run=run.pk);return run

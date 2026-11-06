from django.core.exceptions import ValidationError,PermissionDenied
from django.db import transaction
from apps.core.services import lock_case,event
from apps.identity.services import require
from apps.pmo.rfp import root,source_snapshot,reviewed
from apps.pmo.commercial import valid_approvals
from adapters.rfp import LocalRFPAdapter
from .models import AgentRun

@transaction.atomic
def investigate_rfp(actor,case_id,expected):
    case=lock_case(actor,case_id,'agent.rfp',expected);require(actor,case,'rfp.read');r=root(case);result=LocalRFPAdapter().read(r);findings=[]
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

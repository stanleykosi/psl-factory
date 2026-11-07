from django.core.exceptions import ValidationError, PermissionDenied
from django.db import transaction
from apps.core.services import lock_case, event, bump
from apps.documents.controlled import baseline_manifest, create_version
from apps.documents.models import Template, PublicationReceipt
from apps.policy.services import decision_authority, active_component, reference_values
from .models import (Baseline, CommercialCase, CommercialRevision, CommercialDecision,
    CommercialDocumentBinding, ClientResponse, BaselineAdoption)
from .services import subject

SOURCE_KINDS = ['requirements', 'engineering_estimate', 'security_estimate', 'plan', 'costing', 'sow']
ROLES = ['PM', 'Head of PMO', 'CEO', 'PMO Lead']


def note_required(note):
    if not isinstance(note, str) or not note.strip() or len(note) > 4000:
        raise ValidationError('An evidenced rationale of at most 4000 characters is required')


def current_revision(case, pk):
    revision = CommercialRevision.objects.select_related('dossier__case').filter(pk=pk, dossier__case=case).first()
    if not revision or revision.dossier.current_id != revision.pk:
        raise ValidationError('Select this case current commercial revision')
    if revision.base_manifest != baseline_manifest(case):
        raise ValidationError('Active baseline changed; prepare a new proposal')
    return revision


def latest_decisions(revision):
    result = {}
    for decision in revision.decisions.order_by('pk'):
        result[decision.role] = decision
    return result


def check_decision(decision):
    case = decision.revision.dossier.case
    from apps.identity.services import require
    require(decision.actor, case, 'commercial.decide')
    current = decision_authority(decision.actor, case, decision.role, decision.verdict, decision.delegated)
    # Inherited decisions retain both the current authority and the configured reuse lineage.
    actual = {k: v for k, v in decision.authority.items() if k != 'D05.revision_invalidation_rules'}
    if current != actual:
        raise ValidationError('Decision authority changed; record a current decision')
    if decision.inherited_id:
        rule = active_component('D05.revision_invalidation_rules', case)
        if decision.authority.get(rule.component) != rule.pk:
            raise ValidationError('Decision reuse policy changed; obtain a new direct decision')


def valid_approvals(revision, roles=ROLES, *, check_authority=True):
    from .costing import verify_costing
    verify_costing(subject(revision.dossier.case,revision.sources['costing'],'costing'),revision.sources['plan'])
    decisions = latest_decisions(revision)
    for role in roles:
        d = decisions.get(role)
        if not d or d.verdict != 'approve':
            raise ValidationError('Current commercial approvals missing: ' + role)
        if check_authority:check_decision(d)
    return [decisions[role].pk for role in roles]


def terminal(revision):
    return revision.decisions.filter(verdict__in=['return', 'reject', 'withdraw']).exists()


@transaction.atomic
def propose(actor, case_id, sources, context_id, reason, expected, reuse=False, _rfp=False):
    case = lock_case(actor, case_id, 'commercial.prepare', expected)
    if case.kind != 'project' or not isinstance(sources, dict) or set(sources) != set(SOURCE_KINDS):
        raise ValidationError('A project and all six versioned commercial sources are required')
    from .models import RFPCase,RFPDisposition,RFPResponse
    rfp=RFPCase.objects.filter(case=case).first()
    if rfp and not _rfp and not RFPDisposition.objects.filter(rfp=rfp,kind='route_a').exists():
        raise ValidationError('Prepare this pre-engagement proposal through the RFP response workflow')
    if _rfp and not rfp:raise ValidationError('RFP workspace required')
    if _rfp:
        from .rfp import ensure_open
        ensure_open(rfp)
    from .costing import verify_costing
    verify_costing(subject(case,sources['costing'],'costing'),sources['plan'])
    note_required(reason)
    source_ids = {kind: subject(case, pk, kind).pk for kind, pk in sources.items()}
    if rfp and not _rfp and any(x.commercial.sources['sow']==source_ids['sow'] for x in rfp.responses.select_related('commercial')):
        raise ValidationError('Prepare a fresh project SOW; the bid response is not a project contract')
    context = subject(case, context_id)
    if context.kind not in ['client_feedback', 'change_request', 'requirements', 'rfp_response']:
        raise ValidationError('Link requirements, captured client feedback or a change request')
    if context.kind=='rfp_response' and not _rfp:raise ValidationError('Use RFP response preparation')
    dossier, _ = CommercialCase.objects.get_or_create(case=case)
    previous = dossier.current
    base = baseline_manifest(case)
    if not previous and base and source_ids['plan'] != base['plan_id'] and source_ids['costing'] == base['costing_id']:
        raise ValidationError('A changed plan requires a new costing version')
    if previous and source_ids == previous.sources:
        raise ValidationError('A revised proposal must change an exact evidence version')
    if previous and source_ids['plan'] != previous.sources['plan'] and source_ids['costing'] == previous.sources['costing']:
        raise ValidationError('A changed plan requires a new costing version')
    revision = CommercialRevision.objects.create(dossier=dossier, number=dossier.revisions.count()+1,
        sources=source_ids, base_manifest=baseline_manifest(case), reason=reason, context=context,
        previous=previous, actor=actor)
    dossier.current = revision
    dossier.save(update_fields=['current'])
    if reuse:
        if previous and RFPResponse.objects.filter(commercial=previous).exists():raise ValidationError('RFP approvals cannot be inherited into a project SOW')
        if not previous:
            raise ValidationError('No prior proposal decisions to reuse')
        config = active_component('D05.revision_invalidation_rules', case)
        rules = reference_values(config)[0]
        allowed = rules['unchanged_subject_reuse_roles']
        unchanged = source_ids['costing'] == previous.sources['costing'] and source_ids['plan'] == previous.sources['plan']
        for role, decision in latest_decisions(previous).items():
            same_subject = source_ids['sow'] == previous.sources['sow'] if role == 'PMO Lead' else unchanged
            if role in allowed and same_subject and decision.verdict == 'approve' and not terminal(previous):
                check_decision(decision)
                authority = dict(decision.authority, **{config.component: config.pk})
                CommercialDecision.objects.create(revision=revision, role=role, verdict='approve', note='Explicit configured reuse from decision '+str(decision.pk),
                    actor=decision.actor, authority=authority, delegated=decision.delegated, inherited=decision)
    event(actor, case, 'commercial.proposed', revision=revision.pk, sources=source_ids, previous=previous.pk if previous else None)
    bump(case)
    return revision


@transaction.atomic
def decide_proposal(actor, case_id, revision_id, role, verdict, note, expected, delegated=False):
    case = lock_case(actor, case_id, 'commercial.decide', expected)
    revision = current_revision(case, revision_id)
    from .costing import verify_costing
    if verdict=='approve':verify_costing(subject(case,revision.sources['costing'],'costing'),revision.sources['plan'])
    from .models import RFPResponse
    rfp=RFPResponse.objects.filter(commercial=revision).first()
    from .models import RFPCase,RFPDisposition
    workspace=RFPCase.objects.filter(case=case).first()
    if workspace and not rfp and not RFPDisposition.objects.filter(rfp=workspace,kind='route_a').exists():
        raise ValidationError('Prepare a bound RFP response before commercial decisions')
    if rfp:
        from .rfp import reviewed
        reviewed(rfp)
        if role=='PMO Lead':raise ValidationError('Use the separate RFP response and outward quality reviews')
    note_required(note)
    if role not in ROLES or verdict not in ['approve', 'return', 'reject', 'withdraw']:
        raise ValidationError('Unsupported commercial role or action')
    if terminal(revision) or BaselineAdoption.objects.filter(revision=revision).exists():
        raise ValidationError('A closed proposal requires a new revision')
    if verdict == 'withdraw' and role != 'PM':
        raise ValidationError('Withdrawal is a configured PM action')
    authority = decision_authority(actor, case, role, verdict, delegated)
    if verdict == 'approve':
        # Document quality review is separate; only the costing chain has this order.
        if role != 'PMO Lead':
            valid_approvals(revision, ROLES[:ROLES.index(role)])
        last = latest_decisions(revision).get(role)
        if last and last.verdict == verdict and last.authority == authority:
            raise ValidationError('This exact approval is already current')
    result = CommercialDecision.objects.create(revision=revision, role=role, verdict=verdict, note=note,
        actor=actor, authority=authority, delegated=delegated)
    event(actor, case, 'commercial.decision', revision=revision.pk, decision=result.pk, verdict=verdict, role=role)
    bump(case)
    return result


@transaction.atomic
def draft_submission(actor, case_id, revision_id, template_id, expected, *, template_scope_id=None):
    case = lock_case(actor, case_id, 'commercial.submit', expected)
    require_project_conversion(case)
    revision = current_revision(case, revision_id)
    from .costing import verify_costing
    verify_costing(subject(case,revision.sources['costing'],'costing'),revision.sources['plan'])
    from .models import RFPResponse
    if RFPResponse.objects.filter(commercial=revision).exists():raise ValidationError('An RFP response cannot be adopted or submitted as a project SOW')
    if terminal(revision):
        raise ValidationError('Returned, rejected or withdrawn proposals need revision')
    decisions = valid_approvals(revision)
    template = Template.objects.filter(case=case, pk=template_id, definition__document_type='sow').first()
    if not template:
        raise ValidationError('Select this case controlled SOW template')
    from adapters.commercial import LocalCommercialAdapter
    fields = LocalCommercialAdapter().submission_fields(case, revision)
    version = create_version(actor, case.pk, template.pk, 'Commercial proposal '+str(revision.number), 'client', fields, case.revision, template_scope_id=template_scope_id)
    CommercialDocumentBinding.objects.create(version=version, revision=revision, decision_ids=decisions)
    return version


def binding_findings(binding):
    try:
        revision = current_revision(binding.revision.dossier.case, binding.revision_id)
        if terminal(revision) or binding.decision_ids != valid_approvals(revision):
            return ['Commercial proposal decisions changed; draft and review a new outward version']
    except (ValidationError, PermissionDenied) as exc:
        return ['Commercial proposal is no longer publishable: '+str(exc)]
    return []


@transaction.atomic
def capture_response(actor, case_id, revision_id, receipt_id, kind, evidence_id, note, expected):
    case = lock_case(actor, case_id, 'commercial.response', expected)
    revision = CommercialRevision.objects.filter(pk=revision_id, dossier__case=case).first()
    if not revision:
        raise ValidationError('Proposal must belong to this case')
    note_required(note)
    if kind not in ['feedback', 'signed', 'declined']:
        raise ValidationError('Choose feedback, signed or declined')
    receipt = PublicationReceipt.objects.filter(pk=receipt_id, publication__version__commercialdocumentbinding__revision=revision,
        publication__version__audience='client').first()
    if not receipt:
        raise ValidationError('Response must identify the exact delivered client proposal receipt')
    evidence = subject(case, evidence_id, 'signature' if kind == 'signed' else 'client_feedback')
    if ClientResponse.objects.filter(revision=revision, receipt=receipt, kind=kind, evidence=evidence).exists():
        raise ValidationError('Response evidence already captured')
    response = ClientResponse.objects.create(revision=revision, receipt=receipt, kind=kind, evidence=evidence, note=note, actor=actor)
    event(actor, case, 'commercial.client_response', revision=revision.pk, response=response.pk, kind=kind)
    bump(case)
    return response


@transaction.atomic
def adopt_signed(actor, case_id, revision_id, response_id, expected):
    case = lock_case(actor, case_id, 'baseline.sign', expected)
    require_project_conversion(case)
    revision = current_revision(case, revision_id)
    from .costing import verify_costing
    verify_costing(subject(case,revision.sources['costing'],'costing'),revision.sources['plan'])
    from .models import RFPResponse
    if RFPResponse.objects.filter(commercial=revision).exists():raise ValidationError('An RFP response cannot be adopted or submitted as a project SOW')
    if terminal(revision):
        raise ValidationError('Closed proposal cannot be signed')
    valid_approvals(revision)
    response = ClientResponse.objects.filter(pk=response_id, revision=revision, kind='signed').first()
    if not response or revision.responses.order_by('-pk').first().pk != response.pk:
        raise ValidationError('Current response must attest the exact delivered signed version')
    binding = CommercialDocumentBinding.objects.get(version=response.receipt.publication.version)
    if binding_findings(binding):
        raise ValidationError(binding_findings(binding))
    if BaselineAdoption.objects.filter(response__evidence=response.evidence).exists() or Baseline.objects.filter(signed=response.evidence).exists():
        raise ValidationError('Signature evidence cannot be reused for another baseline')
    from .signatures import current_packet, record_use
    signature_packet = current_packet(case, response.evidence_id, revision)
    before = baseline_manifest(case)
    if before.get('signed_id'):
        # A signed scope change also needs the independently controlled change authorization.
        from .changes import require_change_for_adoption
        require_change_for_adoption(case, revision)
    after = {key+'_id': revision.sources[key] for key in ['plan', 'costing', 'sow']}
    after['signed_id'] = response.evidence_id
    adoption = BaselineAdoption.objects.create(revision=revision, response=response, before=before, after=after, actor=actor)
    record_use(actor, signature_packet, adoption)
    Baseline.objects.update_or_create(case=case, defaults=after)
    from adapters.signed_baselines import InternalSignedBaselineAdapter
    receipt = InternalSignedBaselineAdapter().deliver(adoption)
    event(actor, case, 'commercial.baseline_adopted', adoption=adoption.pk, before=before, after=after)
    event(actor, case, 'finance.signed_baseline_received', receipt=receipt.pk, operation_key=receipt.operation_key)
    bump(case)
    return adoption


def require_project_conversion(case):
    from .models import RFPCase,RFPDisposition
    r=RFPCase.objects.filter(case=case).first()
    if r and not RFPDisposition.objects.filter(rfp=r,kind='route_a').exists():
        raise ValidationError('RFP workspace needs an evidenced won Route A conversion before project SOW work')

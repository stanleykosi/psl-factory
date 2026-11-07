"""Owner-backed internal applicability. An exemption never writes a signature."""
from django.core.exceptions import ValidationError
from django.db import transaction
from apps.core.services import lock_case, event, bump
from apps.identity.services import require
from apps.policy.services import active_component, reference_values, role_policy, PolicyHold, Resolution
from apps.policy.signature_validators import COMPONENT
from .models import Baseline, BaselineSignatureExemption, BaselineAdoption, ClientResponse, CommercialSignatureUse
from .services import subject, baseline_approval_refs
from .signatures import pin, assert_current_signed_baseline


def no_external_client_facts(case):
    from apps.documents.models import PublicationReceipt
    if (ClientResponse.objects.filter(revision__dossier__case=case).exists()
            or BaselineAdoption.objects.filter(revision__dossier__case=case).exists()
            or PublicationReceipt.objects.filter(publication__version__document__case=case, publication__version__audience='client').exists()):
        raise ValidationError('Existing client delivery, response or adoption facts contradict internal-only project classification')


def no_client_facts(case):
    from apps.core.models import Audit
    no_external_client_facts(case)
    if (Audit.objects.filter(case=case, action='baseline.signed').exists()
            or CommercialSignatureUse.objects.filter(packet__case=case).exists()):
        raise ValidationError('Existing signed facts contradict an unsigned exemption; preserve the actual signature history')


def owner_requirement(case):
    policy = active_component(COMPONENT, case)
    rules = reference_values(policy)[0]
    if rules['applicability'] == 'unresolved' or rules['signature_requirement'] == 'unresolved':
        raise PolicyHold([Resolution('MISSING', COMPONENT, policy, 'Owner project classification or signature applicability remains unresolved; preparation is still available')])
    if rules['applicability'] == 'internal_project':
        no_external_client_facts(case)
        subject(case, rules['scope_evidence_id'], 'internal_project_scope')
    return policy, rules


def latest(case):
    return BaselineSignatureExemption.objects.filter(case=case).order_by('-pk').first()


def source_pins(case, baseline, prd_id, previous=None):
    prd = subject(case, prd_id, 'prd')
    result = {key: pin(getattr(baseline, key)) for key in ['plan', 'costing', 'sow']}
    result['prd'] = pin(prd)
    if previous and previous.sources == result:
        return result
    if case.evidence.filter(kind='prd').order_by('-version').values_list('pk', flat=True).first() != prd.pk:
        raise ValidationError('Select the current PRD for a new internal baseline; unchanged existing proof can retain its exact adopted document')
    return result


def validate_exemption(row):
    case = row.case
    require(row.actor, case, 'baseline.sign')
    if role_policy(row.actor, case, 'PM').pk != row.authority_id:
        raise ValidationError('Internal baseline recorder authority changed; a current human exemption record is required')
    policy, rules = owner_requirement(case)
    if policy.pk != row.policy_id or rules['applicability'] != 'internal_project' or rules['signature_requirement'] != 'not_applicable':
        raise ValidationError('Current explicit owner-backed internal not-applicable decision required')
    if rules['scope_evidence_id'] != row.scope_evidence_id:
        raise ValidationError('Owner internal-scope evidence changed')
    no_client_facts(case)
    baseline = Baseline.objects.filter(case=case, signed__isnull=True).first()
    if not baseline or any(row.sources[key]['id'] != getattr(baseline, key + '_id') for key in ['plan', 'costing', 'sow']):
        raise ValidationError('Current exact unsigned internal baseline required; no signed fact is replaced')
    for kind, value in row.sources.items():
        if pin(subject(case, value['id'], kind)) != value:
            raise ValidationError('Internal baseline source evidence changed or was withdrawn')
    return row


def assert_current_baseline_assurance(case):
    baseline = Baseline.objects.filter(case=case).first()
    if not baseline:
        raise ValidationError('Prepared native baseline required')
    if baseline.signed_id:
        return {'kind': 'dual_document_signatures', 'id': assert_current_signed_baseline(case).pk}
    policy, rules = owner_requirement(case)
    if rules['signature_requirement'] != 'not_applicable' or rules['applicability'] != 'internal_project':
        raise ValidationError('Actual required document signatures remain missing; unsigned facts are not signatures')
    row = latest(case)
    if not row:
        raise ValidationError('Record the explicit owner-backed internal signature exemption against this prepared baseline')
    validate_exemption(row)
    return {'kind': 'internal_signature_exemption', 'id': row.pk}


@transaction.atomic
def record_exemption(actor, case_id, prd_id, note, operation_key, expected, predecessor_id=None):
    case = lock_case(actor, case_id, 'baseline.sign', expected)
    authority = role_policy(actor, case, 'PM')
    policy, rules = owner_requirement(case)
    if rules['applicability'] != 'internal_project' or rules['signature_requirement'] != 'not_applicable':
        raise ValidationError('Only an explicit owner-backed proven internal not-applicable decision permits exemption')
    no_client_facts(case)
    baseline = Baseline.objects.filter(case=case, signed__isnull=True).first()
    if not baseline:
        raise ValidationError('Prepare the unsigned native baseline; an exemption never rewrites signed facts')
    from .commercial import note_required
    note_required(note)
    if not isinstance(operation_key, str) or not operation_key.strip() or len(operation_key) > 100:
        raise ValidationError('A stable exemption capture key of at most 100 characters is required')
    previous = latest(case)
    pinned = source_pins(case, baseline, prd_id, previous)
    approvals = previous.approval_refs if previous and previous.sources == pinned else baseline_approval_refs(case, baseline)
    repeated = BaselineSignatureExemption.objects.filter(case=case, operation_key=operation_key).first()
    identity = (pinned, approvals, rules['scope_evidence_id'], policy.pk, authority.pk, actor.pk, note)
    if repeated:
        if repeated != previous or (repeated.sources, repeated.approval_refs, repeated.scope_evidence_id, repeated.policy_id,
                repeated.authority_id, repeated.actor_id, repeated.note) != identity:
            raise ValidationError('Exemption capture key already identifies other or historical facts')
        validate_exemption(repeated)
        return repeated
    if (previous.pk if previous else None) != predecessor_id:
        raise ValidationError('Refresh and identify the current internal exemption predecessor')
    row = BaselineSignatureExemption.objects.create(case=case, sources=pinned, approval_refs=approvals,
        scope_evidence_id=rules['scope_evidence_id'], policy=policy, authority=authority, actor=actor,
        predecessor=previous, note=note, operation_key=operation_key)
    event(actor, case, 'pmo.internal_signature_exemption_recorded', exemption=row.pk, predecessor=predecessor_id,
          policy=policy.pk, signature_created=False, finance_intake_created=False)
    bump(case)
    return row

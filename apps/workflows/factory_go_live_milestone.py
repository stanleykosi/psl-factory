"""Connect verified go-live to an optional, human-recorded PMO milestone."""
from hashlib import sha256

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Exists, OuterRef, Q
from django.utils import timezone

from apps.core.evidence_access import public_evidence
from apps.core.models import Audit, Evidence
from apps.core.services import event, lock_case
from apps.identity.factory_access import department_memberships, role_managed
from apps.identity.models import Grant
from apps.identity.services import require, subject_actions
from apps.identity.team_models import StaffMembership
from apps.pmo import delivery
from apps.pmo.models import DeliveryRecord, Milestone
from apps.pmo.services import complete_milestone
from apps.pmo.signature_exemptions import assert_current_baseline_assurance
from apps.policy.go_live_milestone_validators import COMPONENT, baseline_signature, current_sources, validate_mapping
from apps.policy.operator_drafts import draft_operator_policy
from apps.policy.services import active_component, decision_authority, reference_values
from . import factory, factory_go_live as go_live
from .models import FactoryWork


RECORDED = 'factory.go_live_milestone_completed'
CONFIRMED = 'factory.go_live_milestone_confirmed'


def current_mapping(case, dossier):
    try:
        configuration = active_component(COMPONENT, case)
    except ValidationError:
        raise ValidationError('An approved milestone mapping must be current for this project and delivery.') from None
    value = reference_values(configuration)[0]
    if value['dossier_id'] != dossier.pk:
        raise ValidationError('The approved milestone mapping belongs to another delivery dossier.')
    return configuration, value


def _authority(actor, case, *, direct=False, locked=False):
    factory.access(actor, case, 'factory.read', go_live.DEFINITION)
    leads = department_memberships(actor, 'pmo-lead').filter(mode='lead', case__tenant=case.tenant,
                                                           case__synthetic=case.synthetic)
    if locked:
        leads = leads.select_for_update(of=('self',))
    membership = leads.order_by('pk').first()
    if membership:
        return {'role': 'PMO Lead', 'membership_id': membership.pk}
    if direct or not case.synthetic or role_managed(actor):
        raise PermissionDenied('The current PMO Lead must confirm this milestone.')
    require(actor, case, 'delivery.manage')
    require(actor, case, 'milestone.complete')
    return decision_authority(actor, case, 'PM')


def _recorded(case, dossier):
    return Audit.objects.filter(case=case, action=RECORDED, data__dossier=dossier.pk).first()


def authorize_dispatch(job, case, *, locked=False):
    recorded = Audit.objects.filter(case=case, actor=job.actor, action=RECORDED,
                                    data__milestone=job.milestone_id, data__has_key='confirmation').first()
    if recorded is None:
        require(job.actor, case, 'milestone.complete')
        return
    confirmation = Audit.objects.filter(case=case, actor=job.actor, action=CONFIRMED,
                                        pk=recorded.data['confirmation']).first()
    if (confirmation is None or confirmation.data['evidence'] != job.milestone.evidence_id
            or confirmation.data['milestone_name'] != job.milestone.name):
        raise PermissionDenied('The original PMO Lead confirmation does not match this milestone.')
    _authority(job.actor, case, direct=True, locked=locked)


def _completion_sources(case, dossier):
    release = delivery.latest(dossier, 'release_outcome', required=False)
    already_used = Milestone.objects.filter(case=case).values('evidence_id')
    leads = StaffMembership.objects.filter(user_id=OuterRef('created_by_id'), user__is_active=True,
        active=True, role='pmo-lead', mode='lead', case__kind='project', case__tenant=case.tenant,
        case__synthetic=case.synthetic)
    return public_evidence(Evidence.objects.filter(case=case, kind='completion')).filter(
        Q(pk__in=current_sources(case, 'completion').values('pk')) | Q(Exists(leads))
    ).exclude(
        pk=release.evidence_id if release else None,
    ).exclude(pk__in=already_used)


def _current_work(work):
    return work.status == 'verified' and not work.cancel_requested and not (
        work.lease_until and work.lease_until > timezone.now()
    )


def panel(actor, work, state):
    case, dossier = work.case, state['dossier']
    result = {}
    try:
        require(actor, case, 'policy.read')
        require(actor, case, 'policy.configure')
        delivery.ensure_open(dossier)
        baseline_signature(case, dossier)
        result['settings'] = list(current_sources(case, 'policy_decision').order_by('-pk').values('pk', 'version')[:100])
    except (ValidationError, PermissionDenied):
        pass
    recorded = _recorded(case, dossier)
    if recorded:
        milestone = Milestone.objects.filter(case=case, pk=recorded.data['milestone']).first()
        if milestone:
            result['recorded'] = milestone
            result['confirmation'] = case.audit.filter(pk=recorded.data.get('confirmation'), action=CONFIRMED).first()
        return result
    try:
        authority = _authority(actor, case)
    except (ValidationError, PermissionDenied):
        return result
    sign_off = state['sign_off']
    if not _current_work(work) or not sign_off or any(not item.get('evidence_id') for item in sign_off['signatures']):
        return result
    try:
        delivery.ensure_open(dossier)
        assert_current_baseline_assurance(case)
    except (ValidationError, PermissionDenied):
        return result
    proof = list(_completion_sources(case, dossier).order_by('-pk').values('pk', 'version', 'created_at')[:100])
    if authority.get('membership_id'):
        if state['verified_acceptance_id'] and proof:
            result['direct_confirmation'] = {'acceptance': state['verified_acceptance_id'], 'sources': proof}
        return result
    try:
        configuration, mapping = current_mapping(case, dossier)
        if Milestone.objects.filter(case=case, name=mapping['milestone_name']).exists():
            return result
    except (ValidationError, PermissionDenied):
        return result
    result['completion'] = {
        'configuration': configuration.pk,
        'name': mapping['milestone_name'],
        'acceptance': state['verified_acceptance_id'],
        'sources': proof,
    }
    return result


def _locked_work(actor, work_id, expected, case_expected, action):
    if any(type(ref) is not int or ref < 1 or ref > 9223372036854775807 for ref in (work_id, expected, case_expected)):
        raise ValidationError('Refresh and use the current go-live record.')
    work = FactoryWork.objects.select_for_update(of=('self',)).select_related('case', 'actor', 'source_head').get(
        pk=work_id, definition=go_live.DEFINITION,
    )
    factory.access(actor, work.case, 'factory.read', go_live.DEFINITION)
    work.case = lock_case(actor, work.case_id, action, case_expected)
    list(Grant.objects.select_for_update().filter(case=work.case).order_by('pk').values_list('pk', flat=True))
    if work.revision != expected:
        raise ValidationError('Go-live work changed. Refresh it before continuing.')
    return work


@transaction.atomic
def draft_mapping(actor, work_id, expected, case_expected, name, decision_id):
    work = _locked_work(actor, work_id, expected, case_expected, 'policy.configure')
    require(actor, work.case, 'policy.read')
    dossier, _, _ = go_live.source(work, actor, current=False)
    delivery.ensure_open(dossier)
    value = {
        'dossier_id': dossier.pk,
        'baseline_signature_id': baseline_signature(work.case, dossier),
        'milestone_name': name,
    }
    if type(decision_id) is not int or not 0 < decision_id <= 9223372036854775807:
        raise ValidationError('Choose current owner-decision evidence from this project.')
    validate_mapping(value, work.case, decision_id)
    return draft_operator_policy(actor, work.case_id, COMPONENT, value, decision_id, timezone.now())


@transaction.atomic
def record(actor, work_id, expected, case_expected, configuration_id, acceptance_id, evidence_id):
    if any(type(ref) is not int or ref < 1 or ref > 9223372036854775807
           for ref in (configuration_id, acceptance_id, evidence_id)):
        raise ValidationError('Select the exact approved milestone and its completion evidence.')
    work = _locked_work(actor, work_id, expected, case_expected, 'delivery.read')
    authority = _authority(actor, work.case, locked=True)
    if authority.get('membership_id'):
        raise ValidationError('Use the PMO Lead confirmation with the exact go-live and completion evidence.')
    dossier = delivery.dossier_for(work.case, work.request['dossier'])
    configuration, mapping = current_mapping(work.case, dossier)
    if configuration.pk != configuration_id:
        raise ValidationError('The approved milestone mapping changed. Refresh it before recording the milestone.')
    return _complete(actor, work, dossier, authority, mapping['milestone_name'], acceptance_id, evidence_id,
                     case_expected, configuration=configuration, signature=mapping['baseline_signature_id'])


@transaction.atomic
def confirm_and_complete(actor, work_id, expected, case_expected, name, acceptance_id, evidence_id, note):
    if any(type(ref) is not int or not 1 <= ref <= 9223372036854775807 for ref in (acceptance_id, evidence_id)):
        raise ValidationError('Select the exact go-live sign-off and separate completion evidence.')
    if not isinstance(name, str) or not name.strip() or len(name.strip()) > 200 or not name.strip().isprintable():
        raise ValidationError('Enter the exact milestone name awaiting PMO Lead confirmation.')
    if not isinstance(note, str) or len(note) > 4000:
        raise ValidationError('The optional confirmation note must be 4,000 characters or fewer.')
    work = _locked_work(actor, work_id, expected, case_expected, 'delivery.read')
    authority = _authority(actor, work.case, direct=True, locked=True)
    dossier = delivery.dossier_for(work.case, work.request['dossier'])
    signature = baseline_signature(work.case, dossier)
    return _complete(actor, work, dossier, authority, name.strip(), acceptance_id, evidence_id, case_expected,
                     signature=signature, note=note.strip())


def _complete(actor, work, dossier, authority, name, acceptance_id, evidence_id, case_expected, *,
              signature, configuration=None, note=None):
    case = work.case
    if not _current_work(work):
        raise ValidationError('The current go-live acceptance must be verified before recording a milestone.')
    if _recorded(case, dossier):
        raise ValidationError('A milestone has already been recorded from this go-live dossier.')
    delivery.ensure_open(dossier)
    proof = go_live.verify(work, actor)
    if proof['acceptance'] != acceptance_id:
        raise ValidationError('Go-live acceptance changed. Refresh the exact sign-off before continuing.')
    signature_ids = [proof['pm_signature'], proof['client_signature']]
    if public_evidence(Evidence.objects.filter(case=case, pk__in=signature_ids, kind='signature')).count() != 2:
        raise ValidationError('The exact go-live signature evidence is unavailable with current access.')
    receipt_id, attestation_evidence = DeliveryRecord.objects.filter(
        dossier=dossier, pk=acceptance_id,
    ).values_list('data__receipt_id', 'evidence_id').get()
    evidence = _completion_sources(case, dossier).exclude(pk=attestation_evidence).filter(pk=evidence_id).first()
    if not evidence or sha256(evidence.body.encode()).hexdigest() != evidence.sha256:
        raise ValidationError('Choose separate current project completion evidence, recorded by its authorised owner.')
    confirmation = None
    if authority.get('membership_id'):
        confirmation = event(actor, case, CONFIRMED, work=work.pk, dossier=dossier.pk, head=proof['head'],
                             milestone_name=name, acceptance=acceptance_id, baseline_signature=signature,
                             evidence=evidence.pk, authority=authority, note=note)
    with subject_actions(actor, case, {'milestone.complete'} if confirmation else set()):
        milestone = complete_milestone(actor, case.pk, name, evidence.pk, case_expected)
    event(
        actor, case, RECORDED, work=work.pk, head=proof['head'], dossier=dossier.pk,
        configuration=configuration.pk if configuration else None,
        configuration_revision=configuration.revision if configuration else None,
        baseline_signature=signature, acceptance=acceptance_id,
        report_version=proof['document_version'], receipt=receipt_id, milestone=milestone.pk,
        evidence=evidence.pk, evidence_sha256=evidence.sha256, authority=authority,
        **({'confirmation': confirmation.pk} if confirmation else {}),
    )
    return milestone

"""Connect verified go-live to an optional, human-recorded PMO milestone."""
from hashlib import sha256

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from apps.core.evidence_access import public_evidence
from apps.core.models import Audit, Evidence
from apps.core.services import event, lock_case
from apps.identity.models import Grant
from apps.identity.services import require
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


def current_mapping(case, dossier):
    try:
        configuration = active_component(COMPONENT, case)
    except ValidationError:
        raise ValidationError('An approved milestone mapping must be current for this project and delivery.') from None
    value = reference_values(configuration)[0]
    if value['dossier_id'] != dossier.pk:
        raise ValidationError('The approved milestone mapping belongs to another delivery dossier.')
    return configuration, value


def _authority(actor, case):
    factory.access(actor, case, 'factory.read', go_live.DEFINITION)
    require(actor, case, 'milestone.complete')
    return decision_authority(actor, case, 'PM')


def _recorded(case, dossier):
    return Audit.objects.filter(case=case, action=RECORDED, data__dossier=dossier.pk).first()


def _completion_sources(case, dossier):
    release = delivery.latest(dossier, 'release_outcome', required=False)
    already_used = Milestone.objects.filter(case=case).values('evidence_id')
    return current_sources(case, 'completion').exclude(
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
    try:
        _authority(actor, case)
    except (ValidationError, PermissionDenied):
        return result
    recorded = _recorded(case, dossier)
    if recorded:
        milestone = Milestone.objects.filter(case=case, pk=recorded.data['milestone']).first()
        if milestone:
            result['recorded'] = milestone
        return result
    sign_off = state['sign_off']
    if not _current_work(work) or not sign_off or any(not item.get('evidence_id') for item in sign_off['signatures']):
        return result
    try:
        delivery.ensure_open(dossier)
        configuration, mapping = current_mapping(case, dossier)
        assert_current_baseline_assurance(case)
        if Milestone.objects.filter(case=case, name=mapping['milestone_name']).exists():
            return result
    except (ValidationError, PermissionDenied):
        return result
    result['completion'] = {
        'configuration': configuration.pk,
        'name': mapping['milestone_name'],
        'acceptance': state['verified_acceptance_id'],
        'sources': list(_completion_sources(case, dossier).order_by('-pk').values('pk', 'version', 'created_at')[:100]),
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
    work = _locked_work(actor, work_id, expected, case_expected, 'milestone.complete')
    case = work.case
    authority = _authority(actor, case)
    if not _current_work(work):
        raise ValidationError('The current go-live acceptance must be verified before recording a milestone.')
    dossier = delivery.dossier_for(case, work.request['dossier'])
    if _recorded(case, dossier):
        raise ValidationError('A milestone has already been recorded from this go-live dossier.')
    delivery.ensure_open(dossier)
    configuration, mapping = current_mapping(case, dossier)
    if configuration.pk != configuration_id:
        raise ValidationError('The approved milestone mapping changed. Refresh it before recording the milestone.')
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
    milestone = complete_milestone(actor, case.pk, mapping['milestone_name'], evidence.pk, case_expected)
    event(
        actor, case, RECORDED, work=work.pk, head=proof['head'], dossier=dossier.pk,
        configuration=configuration.pk, configuration_revision=configuration.revision,
        baseline_signature=mapping['baseline_signature_id'], acceptance=acceptance_id,
        report_version=proof['document_version'], receipt=receipt_id, milestone=milestone.pk,
        evidence=evidence.pk, evidence_sha256=evidence.sha256, authority=authority,
    )
    return milestone

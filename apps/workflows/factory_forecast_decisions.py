"""Scoped decision readback from the artifacts prepared by one forecast work item."""

from functools import lru_cache

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models.fields.json import KeyTextTransform

from apps.core.models import Audit, Case, Evidence
from apps.documents.contracts import digest
from apps.documents.models import ControlledReview
from apps.finance import forecast, group_forecast
from apps.finance.models import ForecastBinding, ForecastReview
from apps.identity.models import Grant
from apps.identity.services import require
from apps.policy.services import active_component, decision_authority, reference_values

from . import factory_forecast as flow
from .factory import access
from .models import FactoryAttempt, FactoryWork


ARTIFACT_LIMIT = 8
HISTORY_LIMIT = 12
DECISIONS = {'approve': 'Approved', 'return': 'Returned for correction', 'reject': 'Rejected'}
CURRENT_STAGES = {'group_review', 'publication', 'complete'}
PREPARER_ACTIONS = ('factory.manage', 'finance.publish', 'document.draft')
SOURCE_ACTIONS = {'factory.forecast_intake': 'factory.start', 'factory.forecast_source': 'factory.manage'}


@transaction.atomic
def management_readback(actor, work, forecast_row):
    """Read the latest native decision for the exact current management calculation."""
    run = forecast_row['run']
    if (forecast_row['selection']['audience'] != 'management' or not forecast_row['intake_current']
            or forecast_row['status']['stage'] not in ('review', 'publication', 'complete') or run is None):
        return None

    case = Case.objects.select_for_update().get(pk=work.case_id)
    access(actor, case, 'factory.read', flow.DEFINITION)
    current_head = FactoryWork.objects.filter(case=case, pk=work.pk).values_list('source_head_id', flat=True).get()
    if current_head != work.source_head_id or flow.observed(work, 'forecast_run') != run.pk:
        return None

    correction_actions = {'factory.manage', 'evidence.add'}
    can_correct = (work.source_head.created_by_id == actor.pk and correction_actions == set(
        Grant.objects.filter(case=case, user=actor, active=True, action__in=correction_actions)
        .values_list('action', flat=True)))
    if not can_correct:
        require(actor, case, 'finance.forecast.review')

    review = (ForecastReview.objects.filter(run_id=run.pk, run__case=case).select_related('actor')
              .only('verdict', 'role', 'authority', 'created_at', 'evidence_id', 'actor__is_active')
              .annotate(reviewed_run_hash=KeyTextTransform('run_hash', 'snapshot')).order_by('-pk').first())
    if (not review or review.verdict not in DECISIONS or review.reviewed_run_hash != run.sha256
            or not Evidence.objects.filter(pk=review.evidence_id, case=case, kind='forecast_review').exists()):
        return None

    purpose = 'forecast_rollover' if run.scenario.parent_id else 'forecast'
    if not can_correct:
        forecast.review_authority(actor, case, purpose, review.role, review.verdict, run.actor_id)
    for action in ('case.read', 'finance.read', 'finance.forecast.review'):
        require(review.actor, case, action)
    authority = forecast.review_authority(review.actor, case, purpose, review.role, review.verdict, run.actor_id)
    if not forecast.review_authority_matches(authority, review.authority):
        return None

    scenario, selection = flow.source(work, actor)
    if selection['audience'] != 'management' or scenario.pk != run.scenario_id:
        return None
    forecast.ensure_current(run)
    reason = ForecastReview.objects.values_list('reason', flat=True).get(pk=review.pk)
    return {'id': review.pk, 'run': run.pk, 'code': review.verdict, 'verdict': DECISIONS[review.verdict],
            'recorded_at': review.created_at, 'reason': reason}


def current_source(case, intake, binding):
    origin = Audit.objects.filter(case=case, actor_id=intake.created_by_id, action__in=SOURCE_ACTIONS,
                                  data={'evidence_id': intake.pk, 'sha256': intake.sha256}).first()
    review = ForecastReview.objects.filter(pk=binding.snapshot['output_review'], run_id=binding.run_id,
        verdict='approve').select_related('actor').only('role', 'authority', 'snapshot', 'actor__is_active').first()
    if not origin or not review or review.authority != binding.snapshot['forecast_authority']:
        raise ValidationError('The original forecast inputs and review must match.')
    for action in ('case.read', 'finance.read', 'evidence.add', SOURCE_ACTIONS[origin.action]):
        require(intake.created_by, case, action)
    require(binding.run.actor, case, 'finance.forecast.calculate')
    require(binding.run.scenario.actor, case, 'finance.forecast.capture')
    require(binding.version.created_by, case, 'document.draft')
    require(review.actor, case, 'finance.forecast.review')
    purpose = 'forecast_rollover' if binding.run.scenario.parent_id else 'forecast'
    authority = forecast.review_authority(review.actor, case, purpose, review.role, 'approve', binding.run.actor_id)
    if not forecast.review_authority_matches(authority, review.authority) or review.snapshot.get('run_hash') != binding.run.sha256:
        raise ValidationError('The original forecast approval no longer has its recorded authority.')


@transaction.atomic
def readback(actor, work, forecast_row):
    """Read bounded metadata first. Load a reason only after all relevant checks."""
    case = Case.objects.select_for_update().get(pk=work.case_id)
    access(actor, case, 'factory.read', flow.DEFINITION)
    require(actor, case, 'finance.read')
    actions = set(Grant.objects.filter(case=case, user=actor, active=True).values_list('action', flat=True))
    can_prepare = set(PREPARER_ACTIONS) <= actions
    if 'document.review_controlled' not in actions and not can_prepare:
        return None
    config = active_component('D10.audience_projection_rules', case)
    policy = reference_values(config)[0].get('group')
    if policy is None:
        return None
    pins = FactoryAttempt.objects.filter(activity__work=work, activity__kind='ACT09', phase='observed',
        result__has_key='document_version').order_by('-pk').values_list(
        'result__document_version', 'result__head', 'result__forecast_run')[:ARTIFACT_LIMIT]
    pins = {version: (head, run) for version, head, run in pins if all(type(pk) is int for pk in (version, head, run))}
    bindings = {binding.version_id: binding for binding in ForecastBinding.objects.filter(
        version_id__in=pins, run__case=case, run__scenario__reference=work.request['scenario_reference'],
        version__document__case=case, version__audience='group',
        version__template__definition__document_type='finance_group_report').select_related(
        'version__created_by', 'version__document', 'run__actor', 'run__scenario__actor').only(
        'snapshot', 'version__payload_sha256', 'version__created_by__is_active', 'version__document__current_id',
        'run__sha256', 'run__actor__is_active', 'run__scenario__parent_id', 'run__scenario__actor__is_active')
        if binding.run_id == pins[binding.version_id][1]}
    intakes = Evidence.objects.filter(case=case, kind=flow.KIND,
        pk__in=[head for head, _ in pins.values()]).select_related('created_by').only('sha256', 'created_by__is_active').in_bulk()

    @lru_cache(maxsize=None)
    def checked_source(version):
        binding = bindings[version]
        intake = intakes.get(pins[version][0])
        if not intake:
            raise ValidationError('The original forecast intake is unavailable.')
        current_source(case, intake, binding)
        return binding

    @lru_cache(maxsize=None)
    def reviewer_role(user_id, role, verdict='approve'):
        if role not in policy['reviewer_roles']:
            raise PermissionDenied
        person = get_user_model().objects.only('id', 'is_active').get(pk=user_id)
        require(person, case, 'document.review_controlled')
        require(person, case, 'finance.read')
        return decision_authority(person, case, role, verdict)

    def authorized(review):
        context = review.authority
        role = context.get('role')
        binding = bindings[review.version_id]
        original = binding.snapshot['projection']
        if (review.verdict not in DECISIONS or context.get('group') != group_forecast.IMPLEMENTATION
                or review.delegated or role not in original['reviewer_roles']
                or review.payload_sha256 != binding.version.payload_sha256
                or context.get('binding_hash') != digest(binding.snapshot)
                or context.get('recipients') != sorted(original['recipient_ids'])):
            return False
        try:
            if not (can_prepare and actor.pk == binding.version.created_by_id):
                reviewer_role(actor.pk, role)
            if reviewer_role(review.actor_id, role, review.verdict) != context.get('authority'):
                return False
            checked_source(review.version_id)
        except (PermissionDenied, ValidationError):
            return False
        return True

    visible = ControlledReview.objects.filter(version_id__in=bindings).defer('note').order_by('-pk')
    active = forecast_row['document']
    current_id = active.version_id if active else None
    current = visible.filter(version_id=current_id).first() if current_id in bindings else None
    earlier = list(visible.exclude(pk=current.pk if current else None)[:HISTORY_LIMIT])
    decisions = [review for review in ([current] if current else []) + earlier if authorized(review)]
    notes = dict(ControlledReview.objects.filter(pk__in=[review.pk for review in decisions]).values_list('pk', 'note'))
    result = {'current': None, 'history': []}
    current_head = FactoryWork.objects.filter(case=case, pk=work.pk).values_list('source_head_id', flat=True).get()
    for review in decisions:
        binding = bindings[review.version_id]
        row = {'version': review.version_id, 'verdict': DECISIONS[review.verdict], 'note': notes[review.pk],
               'recorded_at': review.created_at}
        if (review == current and forecast_row['intake_current'] and forecast_row['status']['stage'] in CURRENT_STAGES
                and pins[review.version_id][0] == current_head
                and binding.version.document.current_id == review.version_id
                and binding.snapshot['projection_config'] == config.pk):
            result['current'] = row
        else:
            result['history'].append(row)
    return result

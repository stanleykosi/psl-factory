"""A change can annotate one signed billing stage without changing its terms."""
from collections import defaultdict

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import F, OuterRef, Subquery

from apps.core.evidence_access import public_evidence
from apps.core.read_budget import ReadLimit, limit_queries
from apps.core.services import bump, event, lock_case
from apps.finance.models import BillingCoverage
from apps.finance.project_money import expected_milestone, terms
from apps.identity.services import active_case_grants

from .change_execution import validate_authorization
from .change_impacts import deviation_hold
from .models import ChangeExecutionEvent, ChangeMilestoneLink


READ_ACTIONS = frozenset({'case.read', 'change.read', 'finance.read'})
MANAGE_ACTIONS = READ_ACTIONS | {'change.manage'}
MAX_ROWS = 12


def require_access(actor, case, required):
    actions = {action for _, action in active_case_grants(actor, [case.pk], actions=required)}
    if case.kind != 'project' or not required.issubset(actions):
        raise PermissionDenied('This action requires access to the project, its changes and its signed terms.')


def current_plans(case):
    latest = ChangeExecutionEvent.objects.filter(
        authorization__version_id=OuterRef('authorization__version_id'), kind='plan_updated',
    ).order_by('-pk').values('pk')[:1]
    return ChangeExecutionEvent.objects.filter(
        authorization__version__change__case=case,
        authorization__version_id=F('authorization__version__change__current_id'),
        pk=Subquery(latest), kind='plan_updated',
    ).select_related('authorization__version__change').defer(
        'note', 'authorization__version__description', 'authorization__version__reason',
    )


def plan_proof(case, plan):
    validate_authorization(case, plan.authorization)
    deviation_hold(plan.authorization)
    source_id = plan.impact_details.get('source_plan_id', plan.evidence_id)
    if type(source_id) is not int:
        raise ValidationError('The original project plan source is unavailable.')
    sources = public_evidence(case.evidence.filter(pk__in=[source_id, plan.evidence_id], kind='plan'))
    if set(sources.values_list('pk', flat=True)) != {source_id, plan.evidence_id}:
        raise ValidationError('The original project plan source is unavailable.')
    return source_id


def stage_choices(case, records, coverage):
    if not coverage:
        return []
    return [(stage, expected_milestone(case, coverage, stage) or label)
            for stage, label in ChangeMilestoneLink.Stage.choices if stage in records]


def options(case):
    with limit_queries(350):
        records, baseline, coverage_id, configuration = terms(case)
        coverage = BillingCoverage.objects.filter(pk=coverage_id, case=case).first() if baseline and configuration else None
        stages = stage_choices(case, records, coverage)
        if not stages:
            return [], [], False
        plans = list(current_plans(case).filter(authorization__version__changemilestonelink__isnull=True)
                     .order_by('-pk')[:MAX_ROWS + 1])
        choices = []
        for plan in plans[:MAX_ROWS]:
            try:
                plan_proof(case, plan)
            except (ValidationError, PermissionDenied):
                continue
            version = plan.authorization.version
            choices.append((plan.pk, f'{version.change.reference} · version {version.number}'))
        return stages, choices, len(plans) > MAX_ROWS


@transaction.atomic
def record(actor, case_id, *, stage, plan_id, scope_note, expected):
    case = lock_case(actor, case_id, 'change.manage', expected)
    require_access(actor, case, READ_ACTIONS)
    note = scope_note.strip()
    if not note or len(note) > 240:
        raise ValidationError('Describe the change’s scope on the selected milestone in up to 240 characters.')
    records, baseline, coverage_id, configuration = terms(case)
    if (stage not in ChangeMilestoneLink.Stage.values or stage not in records or not baseline or not configuration
            or not BillingCoverage.objects.filter(case=case, pk=coverage_id).exists()):
        raise ValidationError('Select a milestone with current reviewed signed terms.')
    plan = current_plans(case).filter(pk=plan_id).first()
    if plan is None:
        raise ValidationError('Select the latest plan for a current change.')
    version_id = plan.authorization.version_id
    values = dict(case_id=case.pk, stage=stage, plan_event_id=plan.pk, original_plan_id=plan_proof(case, plan),
                  signed_id=baseline.signed_id, coverage_id=coverage_id, terms_id=configuration.pk, scope_note=note)
    prior = ChangeMilestoneLink.objects.filter(version_id=version_id).first()
    if prior is not None:
        if all(getattr(prior, field) == value for field, value in values.items()):
            return prior
        raise ValidationError('This change version already has a milestone link. Use a newly reviewed change version for a different link.')
    link = ChangeMilestoneLink.objects.create(version_id=version_id, actor=actor, **values)
    event(actor, case, 'change.milestone_linked', link=link.pk, version=version_id, stage=stage)
    bump(case)
    return link


def decorate(case, result, baseline, coverage, configuration):
    """Add bounded, exact-current scope readback to otherwise independent signed figures."""
    if not (baseline and coverage and configuration):
        return
    by_stage = defaultdict(list)
    try:
        with limit_queries(350):
            plans = current_plans(case)
            links = list(ChangeMilestoneLink.objects.filter(
                case=case, signed_id=baseline.signed_id, coverage=coverage, terms=configuration,
            ).order_by('-pk')[:MAX_ROWS + 1])
            by_plan = {plan.pk: plan for plan in plans.filter(pk__in=[link.plan_event_id for link in links[:MAX_ROWS]])}
            for link in links[:MAX_ROWS]:
                plan = by_plan.get(link.plan_event_id)
                if plan is None:
                    continue
                try:
                    proof = plan_proof(case, plan)
                except (ValidationError, PermissionDenied):
                    continue
                if proof == link.original_plan_id:
                    version = plan.authorization.version
                    by_stage[link.stage].append({'reference': version.change.reference, 'number': version.number,
                                                 'note': link.scope_note, 'plan_id': proof, 'link_id': link.pk,
                                                 'version_id': version.pk})
    except ReadLimit:
        result['change_links_limited'] = True
        return
    result['change_links_limited'] = len(links) > MAX_ROWS
    for row in result['rows']:
        row['change_links'] = by_stage[row['key']]

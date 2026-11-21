"""Case-scoped comparison and exact human reconciliation notes for a forecast month."""
from collections import defaultdict

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Exists, OuterRef, Q, Sum

from apps.core.services import bump, event, lock_case
from apps.identity.models import Grant
from apps.identity.services import require
from . import forecast
from .analysis import note
from .models import ForecastActual, ForecastActualVerification, ForecastMatch, ForecastScenario
from .rules import decimal


NOTE = 'forecast.actual_left_unmatched'
NOTE_SCHEMA = 'forecast-unmatched/v1'
HISTORY_LIMIT = 50


def items_for(scenario, month):
    if month not in scenario.payload['months']:
        raise ValidationError('Select a month from this exact forecast.')
    return {item['key']: item for item in scenario.payload['items']
            if item['expected_on'] and item['expected_on'][:7] == month}


def source_scope(case, scenario, month):
    scope = scenario.payload
    return ForecastActual.objects.filter(
        case=case, payload__entity=scope['entity'], payload__currency=scope['currency'],
        payload__basis=scope['basis'], payload__account__in=scope['coverage']['accounts'],
        payload__occurred_on__startswith=f'{month}-', payload__occurred_on__gte=scope['as_of'],
    )


def actuals_for(case, scenario, month):
    return source_scope(case, scenario, month).filter(
        ~Exists(ForecastActual.objects.filter(supersedes_id=OuterRef('pk')))).exclude(lot__cashreversal__isnull=False)


@transaction.atomic
def leave_unmatched(actor, case_id, scenario_id, month, item_key, actual_id, reason, expected):
    case = lock_case(actor, case_id, 'finance.forecast.match', expected)
    list(Grant.objects.select_for_update().filter(case=case, user=actor).order_by('pk').values_list('pk', flat=True))
    require(actor, case, 'finance.forecast.match')
    require(actor, case, 'case.read')
    require(actor, case, 'finance.read')
    scenario = forecast.exact(case, ForecastScenario, scenario_id)
    item = items_for(scenario, month).get(item_key)
    note(reason)
    actual = (actuals_for(case, scenario, month).filter(pk=actual_id, evidence__case=case, evidence__kind='forecast_actual')
              .select_related('evidence').defer('evidence__body').first())
    if item is None or actual is None or actual.payload['direction'] != forecast.direction(item):
        raise ValidationError('Select an exact forecast item and current actual with matching direction and scope.')

    remaining = forecast.residual(scenario, item)
    amount = actual.payload['amount']
    if remaining is not None and remaining <= 0:
        raise ValidationError('This forecast item has no remaining amount to reconcile.')
    if amount is not None:
        used = forecast.amount_sum(forecast.active_matches().filter(actual=actual).values_list('amount', flat=True))
        if decimal(amount) <= used:
            raise ValidationError('This actual has no remaining amount to reconcile.')

    binding = {'schema': NOTE_SCHEMA, 'scenario': scenario.pk, 'month': month, 'item': item_key,
               'actual': actual.pk, 'transaction': actual.transaction, 'actual_evidence': actual.evidence_id,
               'actual_evidence_sha256': actual.evidence.sha256}
    prior = case.audit.filter(action=NOTE, data__contains=binding).order_by('-pk').first()
    if prior and prior.actor_id == actor.pk and prior.data['reason'] == reason.strip():
        return prior
    entry = event(actor, case, NOTE, **binding, reason=reason.strip())
    bump(case)
    return entry


def monthly(actor, case, scenario, month):
    require(actor, case, 'case.read')
    require(actor, case, 'finance.read')
    if scenario.case_id != case.pk:
        raise ValidationError('Select the exact forecast on this workspace.')
    items = items_for(scenario, month)
    root_id = scenario.root_id or scenario.pk
    actuals_query = actuals_for(case, scenario, month)
    actuals = list(actuals_query.annotate(
        independently_verified=Exists(ForecastActualVerification.objects.filter(actual_id=OuterRef('pk'))),
    ).order_by('-pk')[:HISTORY_LIMIT + 1])
    links = forecast.active_matches().filter(case=case, root_id=root_id, item_key__in=items,
        actual_id__in=actuals_query.values('pk')).filter(
            Q(actual__lot_id__isnull=False) | Q(actual__forecastactualverification__isnull=False))
    totals = dict(links.values('item_key').annotate(total=Sum('amount')).values_list('item_key', 'total'))

    # Keep superseded observations in the history. Only current verified sources contribute to monthly amounts.
    history = list(ForecastMatch.objects.filter(case=case, root_id=root_id, item_key__in=items,
        actual_id__in=source_scope(case, scenario, month).values('pk')).select_related('actual', 'reversal').order_by('-pk')[:HISTORY_LIMIT + 1])
    notes = list(case.audit.filter(action=NOTE, data__schema=NOTE_SCHEMA, data__scenario=scenario.pk,
        data__month=month, data__item__in=items).select_related('actor').order_by('-pk')[:HISTORY_LIMIT + 1])
    by_item = defaultdict(list)
    for entry in notes[:HISTORY_LIMIT]:
        by_item[entry.data['item']].append(entry)
    rows = []
    for key, item in items.items():
        matched = totals.get(key)
        expected = item['amount']
        status = 'Awaiting match'
        if matched is not None:
            status = 'Part matched' if expected is None or matched < decimal(expected) else 'Matched'
        rows.append({'item': item, 'actual': matched, 'status': status, 'notes': by_item[key]})
    return {'rows': rows, 'actuals': actuals[:HISTORY_LIMIT], 'history': history[:HISTORY_LIMIT],
            'more_actuals': len(actuals) > HISTORY_LIMIT, 'more_history': len(history) > HISTORY_LIMIT,
            'more_notes': len(notes) > HISTORY_LIMIT}

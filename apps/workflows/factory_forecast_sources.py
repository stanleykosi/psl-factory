"""Exact forecast selection boundary; native Finance remains the calculation owner.

Selections are not calculation pins: every native case actual remains in the
native manifest even when it was not selected as a scenario assumption.
"""
from copy import deepcopy
from datetime import date
from django.core.exceptions import ValidationError, PermissionDenied
from django.db import transaction
from apps.core.models import Evidence
from apps.core.services import lock_case, event
from apps.identity.services import require
from apps.finance import forecast
from apps.finance.models import ForecastScenario, ForecastRun
from apps.documents.models import Template
from apps.documents.contracts import digest

PROTOCOL = 'factory-forecast-selection/v1'
FIELDS = {'protocol', 'scenario_id', 'as_of', 'months', 'source_ids', 'template_id', 'audience'}


def selection(actor, case, value, *, current=True):
    """Validate an explicit selection, without inventing or silently refreshing it."""
    require(actor, case, 'case.read')
    require(actor, case, 'finance.read')
    if not isinstance(value, dict) or set(value) != FIELDS or value['protocol'] != PROTOCOL:
        raise ValidationError('Exact typed forecast scenario, horizon and source inventory required')
    if type(value['scenario_id']) is not int or value['scenario_id'] < 1:
        raise ValidationError('Select an exact native scenario')
    scenario = ForecastScenario.objects.select_related('case', 'evidence', 'actor').filter(case=case, pk=value['scenario_id']).first()
    if scenario is None:
        raise ValidationError('Select this case native forecast scenario')
    payload = scenario.payload
    if value['as_of'] != payload['as_of'] or value['months'] != payload['months']:
        raise ValidationError('Explicit as-of and ordered horizon must equal the selected scenario')
    ids = value['source_ids']
    expected = {scenario.evidence_id} | {x['evidence_id'] for x in payload['openings'] + payload['items']}
    if not isinstance(ids, list) or any(type(x) is not int or x < 1 for x in ids) or len(ids) != len(set(ids)) or set(ids) != expected:
        raise ValidationError('Select the complete exact scenario, opening and assumption source inventory')
    rows = list(Evidence.objects.filter(case=case, pk__in=ids).order_by('pk'))
    if len(rows) != len(expected):
        raise ValidationError('Every forecast source must belong to this case')
    if value['template_id'] is not None and (type(value['template_id']) is not int or not Template.objects.filter(case=case, pk=value['template_id'], definition__document_type='finance_report').exists()):
        raise ValidationError('Select this case aggregate Finance template')
    if value['audience'] not in ['internal', 'management']:
        raise ValidationError('Choose an exact aggregate forecast audience')
    if current:
        require(scenario.actor, case, 'finance.forecast.capture')
        if ForecastScenario.objects.filter(case=case, reference=scenario.reference, number__gt=scenario.number).exists():
            raise ValidationError('Scenario revised; explicitly select its new source inventory and horizon')
    return scenario, rows


def selected_run(actor, case, value, run_id, *, current=True):
    scenario, rows = selection(actor, case, value, current=current)
    if type(run_id) is not int:
        raise ValidationError('Select an exact calculation pin')
    run = ForecastRun.objects.select_related('case', 'scenario').filter(case=case, scenario=scenario, pk=run_id).first()
    if run is None:
        raise ValidationError('Calculation pin must belong to the exact selected scenario')
    if current:
        forecast.ensure_current(run)
    return run


@transaction.atomic
def prepare(actor, case_id, value, expected):
    case = lock_case(actor, case_id, 'finance.forecast.calculate', expected)
    scenario, rows = selection(actor, case, value)
    run = forecast.prepare(actor, case.pk, scenario.pk, case.revision)
    event(actor, case, 'factory.forecast_calculation', selection_hash=digest(value), scenario=scenario.pk, run=run.pk)
    return run


def investigation(actor, case, value, run_id=None):
    """Pure scoped diagnostic. No approval, actual verification or matching tools."""
    scenario, rows = selection(actor, case, value)
    findings = []
    run = None
    current = False
    if run_id is not None:
        run = selected_run(actor, case, value, run_id, current=False)
        findings.extend(run.result['findings'])
        try:
            forecast.ensure_current(run)
            current = True
        except (ValidationError, PermissionDenied) as exc:
            findings.append('; '.join(exc.messages) if isinstance(exc, ValidationError) else str(exc))
    else:
        findings.append('Calculate the exact selected scenario using the configured native forecast method')
    p = scenario.payload
    repeated = bool(scenario.parent_id and scenario.parent.scenario.parent_id and any(x['disposition']=='carry' for x in p['rollover']))
    if repeated:
        findings.append('Repeated carry retains original age; Finance should reassess continuing validity. Fresh opening evidence is not renewed evidence of receipt certainty.')
    aging = [{'item':i['key'], 'original_due':i['original_due'], 'expected_on':i['expected_on'],
              'days_past_original_due':max(0,(date.fromisoformat(p['as_of'])-date.fromisoformat(i['original_due'])).days) if i['original_due'] else None}
             for i in p['items']]
    result = {
        'protocol': 'factory-forecast-investigation/v1',
        'selection': deepcopy(value),
        'selection_hash': digest(value),
        'calculation_pin': {'run_id': run.pk, 'sha256': run.sha256, 'current': current} if run else None,
        'calculation_inventory': deepcopy(run.manifest) if run else None,
        'rollover': {'parent_run':scenario.parent_id, 'root_scenario':scenario.root_id, 'dispositions':deepcopy(p['rollover']), 'repeated_carry':repeated},
        'aging': aging,
        'coverage': deepcopy(p['coverage']),
        'openings': deepcopy(p['openings']),
        'assumptions': deepcopy(p['items']),
        'findings': findings,
        'citations': [{'id': e.pk, 'sha256': e.sha256, 'kind': e.kind} for e in rows],
        'human_waits': ['Finance verifies actuals and explicitly matches or reverses links.',
                        'A configured human reviews the exact current forecast.',
                        'Management records owned priorities through native decisions.'],
        'approval_granted': False, 'cash_mutated': False, 'execution_authorized': False,
        'tools': ['forecast_selected_sources_read', 'forecast_calculation_compare'],
        'scope': 'Selected scenario sources; calculation manifest retains native case-wide actual inventories. Not complete business coverage or payment authority.',
    }
    return result

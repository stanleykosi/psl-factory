"""Prepare one isolated forecast month with an independently reviewable part-payment."""
from decimal import Decimal
import json
import os
from uuid import NAMESPACE_URL, uuid5

from django.contrib.auth import get_user_model
from django.db import connection, transaction
from django.urls import reverse

from apps.core.models import Audit, Case
from apps.core.services import add_evidence, event
from apps.finance import forecast, forecast_actuals
from apps.finance.models import ForecastActual, ForecastActualVerification, ForecastMatch, ForecastScenario
from apps.identity.models import Grant
from apps.policy.services import active_component, register_reference
from tests import forecast_helpers as helpers
from tests.billing_helpers import policy
from tests.helpers import activate, rev
from tests.railway_batch_walkthrough_seed import PREVIEW_PROJECT


GUARD = 'PSL_FORECAST_ACTUALS_WALKTHROUGH_FIXTURE'
TENANT = 'design-forecast-actuals-walkthrough'
CASE = uuid5(NAMESPACE_URL, TENANT)
TITLE = 'SAMPLE forecast against actuals'
OWNER = 'sample-forecast-actuals-source-holder'
REFERENCE = 'SAMPLE-MONTHLY-FORECAST-ACTUALS'
MARKER = 'sample.forecast_actuals_walkthrough_prepared'
TRIAL_ACTIONS = {'case.read', 'finance.read', 'finance.forecast.actual_verify', 'finance.forecast.match'}
OWNER_ACTIONS = {'case.read', 'finance.read', 'evidence.add', 'policy.read', 'policy.configure', 'policy.activate',
                 'finance.forecast.capture', 'finance.forecast.actual', 'finance.forecast.calculate', 'finance.forecast.review'}
NOTE = 'Keep this synthetic part-payment unmatched until the independent statement is checked.'
REVERSAL = 'Reverse the synthetic forecast association while retaining the verified receipt.'


def configure(case, holder, trial):
    for actor, actions in ((holder, OWNER_ACTIONS), (trial, TRIAL_ACTIONS)):
        Grant.objects.bulk_create([Grant(case=case, user=actor, action=action) for action in actions])
    rules = helpers.configure(holder, case)
    owner = add_evidence(holder, case.pk, 'policy_decision', 'Synthetic Forecast source-holder and reviewer.', 'sample-scope')
    assignment = active_component('D05.role_principal_assignments', case)
    nominated = register_reference(holder, case.pk, 'sample-actuals:trial-reviewer', 'schema:psl/role-assignment/v1',
                                   {'role': 'Finance', 'user_id': trial.pk}, owner.pk)
    activate(holder, case, 'D05.role_principal_assignments', [*assignment.envelope['value'], nominated.ref], owner)
    policy(holder, case, forecast.METHOD, {**rules, 'distinct_actual_reporter': True})


def populate(case, holder, trial):
    configure(case, holder, trial)
    value = helpers.payload(holder, case)
    item = value['items'][0]
    value['items'] = [
        {**item, 'key': 'full-receipt', 'source_ref': 'SAMPLE-full-receipt', 'amount': '10'},
        {**item, 'key': 'part-receipt', 'source_ref': 'SAMPLE-part-receipt', 'amount': '50'},
        {**item, 'key': 'unknown-payroll', 'source_ref': 'SAMPLE-payroll', 'amount': None, 'kind': 'outflow'},
    ]
    scenario = helpers.scenario(holder, case, value, REFERENCE)
    run = forecast.prepare(holder, case.pk, scenario.pk, rev(case))
    helpers.review(holder, case, run)
    def actual(transaction_ref, amount, direction='inflow'):
        document = {'entity': value['entity'], 'account': value['coverage']['accounts'][0],
                    'currency': value['currency'], 'basis': value['basis'], 'source': 'sample-statement',
                    'transaction': transaction_ref, 'direction': direction, 'amount': amount, 'occurred_on': value['as_of']}
        supplied = add_evidence(holder, case.pk, 'forecast_actual', json.dumps(document), 'sample-actual-source')
        return forecast.capture_actual(holder, case.pk, supplied.pk, rev(case))

    full = actual('SAMPLE-PREVIOUS-COMPLETE', '10')
    part = actual('SAMPLE-CURRENT-PART', '15')
    unknown = actual('SAMPLE-PAYROLL-UNKNOWN', None, 'outflow')
    confirmed = {}
    for actual in (full, part):
        confirmed[actual.pk] = add_evidence(holder, case.pk, 'forecast_actual_verification', json.dumps(actual.payload),
                                            f'sample-independent-source-{actual.transaction}')
    forecast.verify_actual(trial, case.pk, full.pk, 'Finance', confirmed[full.pk].pk, rev(case))
    proof = add_evidence(holder, case.pk, 'forecast_match', 'Review the exact sample monthly receipt and forecast item.',
                         'sample-monthly-reconciliation-note')
    earlier = forecast.match(trial, case.pk, scenario.pk, 'full-receipt', full.pk, '10', 'sample-forecast-actual-prior',
                             proof.pk, rev(case))
    return event(holder, case, MARKER, trial=trial.pk, scenario=scenario.pk, month=value['months'][0], run=run.pk,
                 full=full.pk, part=part.pk, unknown=unknown.pk, prior_match=earlier.pk,
                 part_verification=confirmed[part.pk].pk, match_proof=proof.pk, item='part-receipt')


@transaction.atomic
def prepare():
    if os.getenv(GUARD) != '1':
        raise RuntimeError('Use the explicit forecast actuals acceptance guard.')
    trial = get_user_model().objects.get(username='psl-agent-trial', is_active=True, is_staff=False, is_superuser=False)
    attrs = {'tenant': TENANT, 'title': TITLE, 'kind': 'project', 'synthetic': True}
    if Case.objects.filter(tenant=TENANT).exclude(pk=CASE).exists():
        raise RuntimeError('The exact forecast actuals workspace is required.')
    case, created = Case.objects.get_or_create(pk=CASE, defaults=attrs)
    case = Case.objects.select_for_update().get(pk=case.pk)
    if any(getattr(case, key) != value for key, value in attrs.items()):
        raise RuntimeError('Preserve the named synthetic forecast actuals workspace.')
    if created:
        holder = get_user_model().objects.create_user(username=OWNER)
        marker = populate(case, holder, trial)
    else:
        marker = Audit.objects.select_related('actor').get(case=case, action=MARKER, actor__username=OWNER)
    holder, data = marker.actor, marker.data
    if (trial.pk != data['trial'] or not holder.is_active or holder.has_usable_password() or holder.is_staff
            or holder.is_superuser or Grant.objects.filter(user=holder).exclude(case=case).exists()
            or set(Grant.objects.filter(case=case, user=trial, active=True).values_list('action', flat=True)) != TRIAL_ACTIONS):
        raise RuntimeError('Preserve the synthetic non-signing holder and exact Trial permissions.')
    selected = ForecastScenario.objects.get(case=case, pk=data['scenario'], actor=holder, reference=REFERENCE)
    if (not forecast.method(case)[1]['distinct_actual_reporter']
            or set(ForecastActual.objects.filter(case=case, actor=holder).values_list('pk', flat=True)) !=
                {data['full'], data['part'], data['unknown']}
            or not ForecastMatch.objects.filter(case=case, pk=data['prior_match'], actual_id=data['full'],
                                                  item_key='full-receipt', amount=Decimal('10'), actor=trial).exists()
            or not ForecastActualVerification.objects.filter(actual__case=case, actual_id=data['full'], actor=trial).exists()
            or selected.payload['months'][0] != data['month']):
        raise RuntimeError('Preserve the exact known full, part and Unknown sample facts.')
    path = reverse('finance_forecast_actuals', args=[case.pk, selected.pk])
    return {**data, 'case': str(case.pk), 'path': f'{path}?month={data["month"]}', 'preserved': not created,
            'match_amount': '15', 'note': NOTE, 'reversal': REVERSAL,
            'part_already_verified': ForecastActualVerification.objects.filter(actual_id=data['part']).exists(),
            'part_note_recorded': case.audit.filter(action=forecast_actuals.NOTE, data__actual=data['part']).exists()}


def run():
    if (os.getenv('RAILWAY_PROJECT_ID'), os.getenv('RAILWAY_ENVIRONMENT_NAME'), os.getenv('RAILWAY_SERVICE_ID'),
            os.getenv(GUARD)) != (PREVIEW_PROJECT, 'design-acceptance', '00c14ca1-5361-4bee-97a5-2ec7aba6ef18', '1'):
        raise RuntimeError('Use only the isolated Railway acceptance checks service.')
    database = os.getenv('PGDATABASE', '')
    if not database or database.lower().startswith('test_') or connection.vendor != 'postgresql':
        raise RuntimeError('Select the existing PostgreSQL preview database.')
    with connection.cursor() as cursor:
        cursor.execute('SELECT current_database()')
        if cursor.fetchone()[0] != database:
            raise RuntimeError('The configured preview database must match the connection.')
    print(GUARD + '=' + json.dumps(prepare()), flush=True)

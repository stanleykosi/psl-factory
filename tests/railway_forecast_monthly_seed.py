"""Prepare one synthetic management calculation for its independent Finance reviewer."""

import json
import os
from datetime import datetime, time, timedelta
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from django.contrib.auth import get_user_model
from django.db import connection, transaction
from django.urls import reverse
from django.utils import timezone

from adapters.forecast import OPENING_CONTRACT
from apps.core.models import Audit, Case
from apps.core.services import event
from apps.documents.models import Publication
from apps.identity.models import Grant
from apps.identity.services import require
from apps.policy.operator_drafts import draft_operator_policy
from apps.policy.services import active_component, reference_values, register_reference, transition
from apps.workflows import factory, factory_forecast as flow
from apps.workflows.factory_forecast_sources import PROTOCOL
from apps.workflows.models import FactoryWork
from tests import forecast_helpers
from tests.billing_helpers import evidence, policy
from tests.helpers import activate, rev
from tests.railway_batch_walkthrough_seed import PREVIEW_PROJECT
from tests.railway_finance_schedule_seed import fixture_reviewer


TENANT = 'design-management-forecast-opening-review'
TITLE = 'SAMPLE management forecast with an unreconciled opening'
KEY = 'sample-management-forecast-unreconciled-opening'
CASE_ID = uuid5(NAMESPACE_URL, TENANT)
GUARD = 'PSL_FORECAST_MONTHLY_REVIEW_FIXTURE'
MARKER = 'sample.forecast_monthly_review_prepared'
PREPARER = 'sample-management-forecast-preparer'
REVIEWER_ACTIONS = ('case.read', 'factory.read', 'finance.read', 'finance.forecast.review')
PREPARER_ACTIONS = ('case.read', 'factory.read', 'factory.start', 'factory.execute', 'finance.read',
                    'finance.forecast.capture', 'finance.forecast.calculate', 'finance.publish',
                    'document.draft', 'document.publish', 'evidence.add', 'policy.read',
                    'policy.configure', 'policy.activate')


def opening_selection(preparer, case):
    today = timezone.localdate()
    previous = today - timedelta(days=1)
    instant = datetime.combine(today, time.min, timezone.get_current_timezone()).isoformat()
    value = forecast_helpers.payload(preparer, case, today=today)
    value['coverage']['inflows'] = 'partial'
    # The existing embedded F38-N01 evidence format binds the close and its boundary in one exact source.
    opening = {'contract': OPENING_CONTRACT, 'entity': value['entity'], 'currency': value['currency'],
        'basis': value['basis'], 'account': value['coverage']['accounts'][0], 'amount': '100',
        'observed_on': previous.isoformat(), 'cutoff': 'end_of_day', 'source': 'sample-supplied-close',
        'source_version': f'sample-supplied-close-{previous.isoformat()}-v1', 'boundary_at': instant,
        'boundary': {'as_of': value['as_of'], 'opening_at': instant, 'status': 'unreconciled'}}
    source = evidence(preparer, case, 'forecast_opening', json.dumps(opening, sort_keys=True))
    value['openings'] = [{**opening, 'evidence_id': source.pk}]
    scenario = forecast_helpers.scenario(preparer, case, value, reference='SAMPLE-MANAGEMENT-UNKNOWN')
    selection = {'protocol': PROTOCOL, 'scenario_id': scenario.pk, 'as_of': value['as_of'], 'months': value['months'],
                 'source_ids': sorted({scenario.evidence_id, source.pk, *(item['evidence_id'] for item in value['items'])}),
                 'template_id': None, 'audience': 'management'}
    return selection, source.pk


def seed(case, reviewer):
    maker = get_user_model().objects.create_user(PREPARER)
    Grant.objects.bulk_create([Grant(case=case, user=actor, action=action)
        for actor, actions in ((maker, PREPARER_ACTIONS), (reviewer, REVIEWER_ACTIONS)) for action in actions])
    decision = evidence(maker, case, 'policy_decision', 'Synthetic independent Finance review for one calculation.')
    nominations = [register_reference(maker, case.pk, f'sample-forecast-role-{actor.pk}', 'schema:psl/role-assignment/v1',
                   {'role': 'Finance', 'user_id': actor.pk}, decision.pk).ref for actor in (maker, reviewer)]
    activate(maker, case, 'D05.role_principal_assignments', nominations, decision)
    forecast_helpers.configure(maker, case)
    matrix = reference_values(active_component('D05.decision_action_matrix', case))[0]
    policy(maker, case, 'D05.decision_action_matrix', dict(matrix, finance=[
        dict(rule, allow_preparer_review=False) for rule in matrix['finance']]))
    settings_path = Path(__file__).resolve().parent.parent / 'fixtures/factory-forecast.json'
    profile = json.loads(settings_path.read_text(encoding='utf-8'))
    profile.pop('classification')
    profile.update(preparer_id=maker.pk, executor_id=maker.pk)
    configuration = draft_operator_policy(maker, case.pk, 'OPS.factory_forecast_execution', profile, decision.pk, timezone.now())
    transition(maker, configuration.pk, 'validated')
    transition(maker, configuration.pk, 'active')
    selection, opening = opening_selection(maker, case)
    review_evidence = evidence(maker, case, 'forecast_review', 'Synthetic evidence for the independent calculation review.')
    work = flow.start(maker, case.pk, KEY, selection, TITLE, rev(case))
    factory.run_until_wait(work.pk)
    work.refresh_from_db()
    calculation = flow.calculation(work, reviewer)
    if calculation is None or flow.report(work, reviewer)['stage'] != 'review':
        raise RuntimeError('The exact prepared management calculation must await a separate Finance review.')
    first = calculation.result['periods'][0]
    if ((first['opening'], first['outflow'], first['closing']) != (None, '0', None)
            or calculation.result['coverage']['inflows'] != 'partial'
            or calculation.result['coverage']['outflows'] != 'complete'
            or calculation.result['opening_provenance'][0]['eligible']
            or calculation.forecastreview_set.exists() or Publication.objects.filter(factory_work=work).exists()):
        raise RuntimeError('The fresh fixture must retain unknown amounts, a genuine zero and no decision or release.')
    return event(maker, case, MARKER, reviewer=reviewer.pk, work=work.pk, run=calculation.pk, source=work.source_head_id,
                 source_sha256=work.source_head.sha256, opening=opening, review_evidence=review_evidence.pk,
                 scenario=selection['scenario_id'], source_ids=selection['source_ids'], months=selection['months'])


@transaction.atomic
def prepare():
    if os.getenv(GUARD) != '1':
        raise RuntimeError('Explicit synthetic management forecast fixture permission is required.')
    reviewer = fixture_reviewer()
    case, created = Case.objects.get_or_create(pk=CASE_ID,
        defaults={'tenant': TENANT, 'title': TITLE, 'kind': 'project', 'synthetic': True})
    if (case.tenant, case.title, case.kind, case.synthetic) != (TENANT, TITLE, 'project', True):
        raise RuntimeError('The existing case must match this isolated synthetic forecast identity.')
    marker = seed(case, reviewer) if created else Audit.objects.get(case=case, actor__username=PREPARER, action=MARKER)
    pinned = marker.data
    work = FactoryWork.objects.get(pk=pinned['work'], case=case, actor=marker.actor, definition=flow.DEFINITION,
                                  key=KEY)
    if (reviewer.pk != pinned['reviewer'] or reviewer.pk == marker.actor_id
            or (work.source_head_id, work.source_head.sha256) != (pinned['source'], pinned['source_sha256'])):
        raise RuntimeError('Preserve different reviewers or corrected source versions without replay.')
    factory.access(reviewer, case, 'factory.read', flow.DEFINITION)
    require(reviewer, case, 'finance.forecast.review')
    return {**pinned, 'case': str(case.pk), 'preserved': not created,
            'decision_path': reverse('factory_invoice_decision', args=[work.pk]),
            'source_path': reverse('finance_forecast', args=[case.pk])}


def run():
    if (os.getenv('RAILWAY_PROJECT_ID'), os.getenv('RAILWAY_ENVIRONMENT_NAME'),
            os.getenv('RAILWAY_SERVICE_ID'), os.getenv(GUARD)) != (
            PREVIEW_PROJECT, 'design-acceptance', '00c14ca1-5361-4bee-97a5-2ec7aba6ef18', '1'):
        raise RuntimeError('Use the isolated Railway fixture checks service.')
    database = os.getenv('PGDATABASE', '')
    if not database or database.lower().startswith('test_') or connection.vendor != 'postgresql':
        raise RuntimeError('Select the existing PostgreSQL preview database.')
    with connection.cursor() as cursor:
        cursor.execute('SELECT current_database()')
        if cursor.fetchone()[0] != database:
            raise RuntimeError('The original preview database must match the configured database.')
    print('PSL_FORECAST_MONTHLY_REVIEW_FIXTURE=' + json.dumps(prepare()), flush=True)

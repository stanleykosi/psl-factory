"""Prepare isolated source records for a grouped browser walkthrough."""
import json
import os
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from apps.core.models import Case
from apps.documents import controlled, delivery as publication_worker
from apps.documents.models import PublicationReceipt
from apps.identity.actions import ACTIONS
from apps.identity.models import Grant
from apps.policy.operator_drafts import draft_operator_policy
from apps.policy.services import transition
from apps.workflows import factory_change, factory_progress
from apps.workflows.models import FactoryProgress, FactoryWork
from tests import test_commercial_changes, test_delivery, test_factory_hypercare, test_project_archive_files, test_standard_changes
from tests.helpers import rev
from tests.signature_helpers import reaffirm_for


PREVIEW_PROJECT = 'f957481b-c6f7-43af-bc66-449a330a9d53'
TENANT = 'design-composed-delivery-walkthrough'
PREPARATION = {
    'stability': ('delivery-hypercare/v1', 'SAMPLE release stability walkthrough'),
    'archive': ('delivery-archive/v1', 'SAMPLE file archive walkthrough'),
    'standard': ('pmo-change/v1', 'SAMPLE standard change walkthrough'),
    'emergency': ('pmo-emergency/v1', 'SAMPLE emergency walkthrough'),
    'escalation': ('pmo-escalation/v1', 'SAMPLE escalation walkthrough'),
    'leadership': ('pmo-leadership-report/v1', 'SAMPLE leadership report walkthrough'),
    'tuesday': ('pmo-leadership-report/v1', 'SAMPLE Tuesday report walkthrough'),
    'accounts': ('finance-accounts/v1', 'SAMPLE accounts close walkthrough'),
    'assets': ('finance-ppe/v1', 'SAMPLE fixed asset walkthrough'),
    'schedules': ('finance-schedules/v1', 'SAMPLE schedules walkthrough'),
    'forecast': ('finance-forecast/v1', 'SAMPLE cash forecast walkthrough'),
}


def scoped_publish(entry, version):
    if version.audience == 'client':
        controlled.request_review(entry.actor, entry.case.pk, version.pk, rev(entry.case))
        controlled.review_version(entry.actor, entry.case.pk, version.pk, 'approve',
                                  'Sample setup review of the exact delivered document.', rev(entry.case))
    publication = controlled.reserve_publication(entry.actor, entry.case.pk, version.pk, rev(entry.case))
    publication_worker.run_publication_once(job_id=publication.job.pk)
    return PublicationReceipt.objects.get(publication=publication)


def pause_existing_background(actor, work):
    work.refresh_from_db()
    if FactoryProgress.objects.filter(work=work, status__in=factory_progress.ACTIVE).exists():
        factory_progress.set_progress(actor, work.pk, work.revision, False)


def prepare_stability(actor, case):
    with (patch.object(test_delivery, 'setup_case', return_value=(actor, case)),
          patch.object(test_delivery.DeliveryFixture, 'publish', scoped_publish)):
        entry = test_factory_hypercare.setup()
        entry.accepted()
        entry.criteria()
        entry.observations()
    return entry.work


def prepare_archive(actor, case):
    with (patch.object(test_delivery, 'setup_case', return_value=(actor, case)),
          patch.object(test_delivery.DeliveryFixture, 'publish', scoped_publish)):
        entry = test_project_archive_files.configured()
    return entry.work


def prepare_standard(actor, case):
    with patch.object(test_standard_changes, 'fixture', side_effect=lambda *, existing:
                      test_commercial_changes.fixture(existing=existing, context=(actor, case))):
        entry = test_standard_changes.StandardChangeTests()
        entry.setUp()
    reaffirm_for(actor, case)
    entry.bound()
    template = entry.change_template()
    profile = json.loads(Path('fixtures/factory-change.json').read_text())
    profile.pop('classification')
    profile.update(preparer_id=actor.pk, executor_id=actor.pk)
    config = draft_operator_policy(actor, case.pk, 'OPS.factory_change_execution', profile,
                                   entry.e['policy_decision'].pk, timezone.now())
    transition(actor, config.pk, 'validated')
    transition(actor, config.pk, 'active')
    work = factory_change.start(actor, case.pk, 'SAMPLE-BATCH-STANDARD', entry.cv.pk,
                                {'template_id': template.pk, 'authorization_id': None},
                                'SAMPLE standard change with recorded procedure', rev(case))
    return work


def prepare_emergency(actor, case):
    from tests import test_emergencies, test_factory_emergency

    with patch.object(test_emergencies, 'fixture', side_effect=lambda *, existing:
                      test_commercial_changes.fixture(existing=existing, context=(actor, case))):
        entry = test_factory_emergency.FactoryEmergencyTests()
        entry.setUp()
    entry.policies()
    entry.clocks()
    return entry.start_work()


def prepare_escalation(actor, case):
    from tests import document_helpers, test_factory_escalation

    with patch.object(document_helpers, 'setup_case', return_value=(actor, case)):
        entry = test_factory_escalation.FactoryEscalationTests()
        entry.setUp()
    return entry.start()


def prepare_leadership(actor, case, *, tuesday=False):
    from tests import document_helpers, test_factory_leadership

    with patch.object(document_helpers, 'setup_case', return_value=(actor, case)):
        entry = test_factory_leadership.FactoryLeadershipTests()
        entry.setUp()
    if tuesday:
        entry.tuesday()
    return entry.start_work()


def prepare_accounts(actor, case):
    from tests import factory_accounting_helpers, finance_analysis_helpers as source

    with patch.object(source, 'setup_case', return_value=(actor, case)):
        _, _, evidence, _, _, ledger, template, _ = source.fixture()
    return factory_accounting_helpers.configured(actor, case, evidence, ledger, template, source.METRICS)['work']


def prepare_assets(actor, case):
    from tests import finance_analysis_helpers, test_factory_ppe

    with patch.object(finance_analysis_helpers, 'setup_case', return_value=(actor, case)):
        entry = test_factory_ppe.FactoryPPETests()
        entry.setUp()
    return entry.start()


def prepare_schedules(actor, case):
    from tests import finance_analysis_helpers, test_factory_schedules

    with patch.object(finance_analysis_helpers, 'setup_case', return_value=(actor, case)):
        entry = test_factory_schedules.FactorySchedulesTests()
        entry.setUp()
    return entry.start()


def prepare_forecast(actor, case):
    from tests import forecast_helpers, test_factory_forecast

    with patch.object(forecast_helpers, 'setup_case', return_value=(actor, case)):
        entry = test_factory_forecast.ForecastFactoryTests()
        entry.setUp()
    return entry.start()


@transaction.atomic
def prepare_project(actor, key):
    definition, title = PREPARATION[key]
    case, created = Case.objects.get_or_create(tenant=TENANT, title=title, kind='project', synthetic=True)
    if created:
        Grant.objects.bulk_create([Grant(user=actor, case=case, action=action) for action in dict.fromkeys(ACTIONS)])
        prepare = {'stability': prepare_stability, 'archive': prepare_archive, 'standard': prepare_standard,
                   'emergency': prepare_emergency, 'escalation': prepare_escalation,
                   'leadership': prepare_leadership, 'tuesday': prepare_leadership,
                   'accounts': prepare_accounts, 'assets': prepare_assets,
                   'schedules': prepare_schedules, 'forecast': prepare_forecast}[key]
        users = get_user_model().objects
        create_user = users.create_user
        with patch.object(users, 'create_user', side_effect=lambda username, **values:
                          create_user(username=f'batch-{key}-{username}', **values)):
            work = prepare(actor, case, tuesday=True) if key == 'tuesday' else prepare(actor, case)
        pause_existing_background(actor, work)
    else:
        work = FactoryWork.objects.get(case=case, actor=actor, definition=definition)
    return {'case': str(case.pk), 'work': work.pk, 'path': reverse('factory_detail', args=[work.pk]),
            'existing_work_preserved': not created}


def run():
    if (os.getenv('RAILWAY_ENVIRONMENT_NAME'), os.getenv('RAILWAY_PROJECT_ID'),
            os.getenv('PSL_COMPOSED_WALKTHROUGH')) != ('design-acceptance', PREVIEW_PROJECT, '1'):
        raise RuntimeError('Exact Railway acceptance environment and explicit fixture guard required')
    actor = get_user_model().objects.get(username='psl-agent-trial', is_active=True, is_staff=False, is_superuser=False)
    from tests.railway_commercial_client_seed import prepare_rework

    sessions = {key: lambda key=key: prepare_project(actor, key) for key in PREPARATION}
    sessions['rework'] = prepare_rework
    failed = False
    for key, prepare in sessions.items():
        try:
            result = prepare()
        except Exception as exc:
            failed = True
            print(f'PSL_BATCH_FIXTURE_ERROR={key}: {type(exc).__name__}: {str(exc)[:240]}', flush=True)
        else:
            if key == 'rework':
                result['path'] = reverse('commercial_client_response', args=[result['case']])
            print('PSL_BATCH_FIXTURE=' + json.dumps({'journey': key, **result}), flush=True)
    if failed:
        raise RuntimeError('A sample preparation failed. Successful cases remain available.')

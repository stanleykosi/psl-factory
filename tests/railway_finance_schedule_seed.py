"""Add synthetic F12 and F13 samples for an independently reviewed browser batch."""

import json
import os
from functools import partial
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import transaction
from django.urls import reverse

from apps.core.models import Case
from apps.identity.actions import ACTIONS
from apps.identity.models import Grant
from apps.workflows import factory, factory_progress, factory_schedules
from apps.workflows.models import FactoryWork
from tests import finance_analysis_helpers, schedule_helpers, test_factory_schedules
from tests.helpers import rev
from tests.railway_batch_walkthrough_seed import PREVIEW_PROJECT


TENANT = 'design-schedule-review-walkthrough'
TITLES = {
    'income': 'SAMPLE income review, corrected detail and adjustment',
    'inventory': 'SAMPLE selected statutory schedule inventory review',
}


@transaction.atomic
def prepare(reviewer, kind):
    case, created = Case.objects.get_or_create(tenant=TENANT, title=TITLES[kind], kind='project', synthetic=True)
    username = f'batch-schedule-{kind}-source-owner'
    if not created:
        work = FactoryWork.objects.get(case=case, definition=factory_schedules.DEFINITION, actor__username=username)
        return browser_record(work, preserved=True)

    maker = get_user_model().objects.create_user(username)
    Grant.objects.bulk_create([Grant(user=maker, case=case, action=action) for action in dict.fromkeys(ACTIONS)])
    with (
        patch.object(finance_analysis_helpers, 'setup_case', return_value=(maker, case)),
        patch.object(test_factory_schedules, 'fixture', side_effect=partial(
            schedule_helpers.fixture, reviewer=reviewer, recipient_username=f'batch-schedule-{kind}-inbox',
        )),
    ):
        sample = test_factory_schedules.FactorySchedulesTests()
        sample.setUp()

    context = sample.f
    if kind == 'income':
        addition = schedule_helpers.row(context, 'reviewed-training', '20', 'additive',
                                        lines=[{'account': 'sales', 'amount': '20'}])
        initial = dict(sample.payload, rows=[
            schedule_helpers.row(context, 'software-licences', '-750'),
            schedule_helpers.row(context, 'maintenance', '-250'),
            addition,
        ])
        replacement = dict(initial, rows=[
            schedule_helpers.row(context, 'software-licences', '-700'),
            schedule_helpers.row(context, 'maintenance', '-300'),
            dict(addition, amount='25', adjustment_lines=[{'account': 'sales', 'amount': '25'}]),
        ])
        source = schedule_helpers.evidence(context, 'income_detail', json.dumps(initial))
        successor = schedule_helpers.evidence(context, 'income_detail', json.dumps(replacement))
        parent = context['parent'].pk
    else:
        source = schedule_helpers.evidence(context, 'schedule_inventory', json.dumps(context['values']['inventory']))
        successor = None
        parent = None

    work = factory_schedules.start(maker, case.pk, f'BATCH-SCHEDULE-{kind.upper()}', kind, parent, source.pk, None,
                                  f'sample-{kind}-review', rev(case))
    factory.run_until_wait(work.pk)
    work.refresh_from_db()
    result = factory_schedules.schedule(work)
    if not result or result.result['status'] != 'ready' or result.reviews.exists():
        raise RuntimeError('Fixture must stop at the exact native independent decision')
    if factory_schedules.projection(reviewer, work)['pending_reviews'] != [result.pk]:
        raise RuntimeError('Expected independently reviewable sample schedule')
    factory_progress.set_progress(maker, work.pk, work.revision, True)
    return {
        **browser_record(work, preserved=False),
        'original_source': source.pk,
        'replacement_source': successor.pk if successor else None,
        'review_evidence': context['e']['finance_review'].pk,
        'adjustment_evidence': context['e']['finance_adjustment'].pk,
        'mapping': parent,
        'prepared_schedule': result.pk,
    }


def browser_record(work, *, preserved):
    return {
        'journey': f'schedule_close_{work.request["kind"]}',
        'case': str(work.case_id),
        'work': work.pk,
        'decision_path': reverse('factory_invoice_decision', args=[work.pk]),
        'recovery_path': reverse('factory_invoice_recovery', args=[work.pk]),
        'existing_work_preserved': preserved,
    }


def run():
    if (os.getenv('RAILWAY_ENVIRONMENT_NAME'), os.getenv('RAILWAY_PROJECT_ID'),
            os.getenv('PSL_COMPOSED_WALKTHROUGH')) != ('design-acceptance', PREVIEW_PROJECT, '1'):
        raise RuntimeError('Exact Railway acceptance environment and explicit fixture guard required')
    reviewer = get_user_model().objects.get(username='psl-agent-trial', is_active=True, is_staff=False, is_superuser=False)
    for kind in TITLES:
        print('PSL_FINANCE_SCHEDULE_FIXTURE=' + json.dumps(prepare(reviewer, kind)), flush=True)

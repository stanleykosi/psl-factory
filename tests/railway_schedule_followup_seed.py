"""Guarded, independent browser cases for Finance follow-up after schedule review."""

import json
from functools import partial
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import transaction
from django.urls import reverse

from apps.core.models import Case
from apps.finance.models import ScheduleAdjustment
from apps.identity.actions import ACTIONS
from apps.identity.models import Grant
from apps.workflows import factory, factory_schedules as schedules
from apps.workflows.models import FactoryWork
from tests import finance_analysis_helpers, schedule_helpers, test_factory_schedules
from tests.helpers import rev
from tests.railway_finance_schedule_seed import fixture_reviewer


TENANT = 'design-schedule-finance-followup-walkthrough'
STATIONS = {
    'receiving-adjustment': 'SAMPLE exported income adjustment awaiting Finance review',
    'restore-approval': 'SAMPLE independent income schedule approval restoration',
}


@transaction.atomic
def prepare(station):
    reviewer = fixture_reviewer()
    case, created = Case.objects.get_or_create(tenant=TENANT, title=STATIONS[station], kind='project', synthetic=True)
    username = f'batch-schedule-{station}-owner'
    if not created:
        work = FactoryWork.objects.get(case=case, definition=schedules.DEFINITION, actor__username=username)
        return browser_record(station, work, preserved=True)

    maker = get_user_model().objects.create_user(username)
    Grant.objects.bulk_create([Grant(user=maker, case=case, action=action) for action in dict.fromkeys(ACTIONS)])
    with (
        patch.object(finance_analysis_helpers, 'setup_case', return_value=(maker, case)),
        patch.object(test_factory_schedules, 'fixture', side_effect=partial(
            schedule_helpers.fixture, reviewer=reviewer, recipient_username=f'batch-schedule-{station}-reader',
        )),
    ):
        sample = test_factory_schedules.FactorySchedulesTests()
        sample.setUp()

    data = sample.f
    addition = schedule_helpers.row(data, 'approved-training-cost', '20', 'additive',
                                    lines=[{'account': 'sales', 'amount': '20'}])
    supplied = schedule_helpers.evidence(data, 'income_detail', json.dumps(
        dict(sample.payload, rows=[*sample.payload['rows'], addition]),
    ))
    work = schedules.start(maker, case.pk, f'FOLLOWUP-SCHEDULE-{station.upper()}', 'income', data['parent'].pk,
                           supplied.pk, None, f'sample-schedule-{station}', rev(case))
    factory.run_until_wait(work.pk)
    work.refresh_from_db()
    prepared = schedules.schedule(work)
    schedules.review(reviewer, work.pk, work.revision, rev(case), prepared.pk, 'approve',
                     data['e']['finance_review'].pk, 'Synthetic precondition for the separate follow-up walkthrough.')
    factory.run_until_wait(work.pk)
    work.refresh_from_db()
    if work.status != 'verified':
        raise RuntimeError('The selected original schedule must reach verification before preparing follow-up.')

    if station == 'receiving-adjustment':
        schedules.export(maker, work.pk, work.revision, rev(case), prepared.pk, 'additive',
                         data['e']['finance_adjustment'].pk)
    return browser_record(station, work, preserved=False)


def browser_record(station, work, *, preserved):
    schedule = schedules.schedule(work)
    linked_adjustment = ScheduleAdjustment.objects.filter(work=schedule).values_list('adjustment_id', flat=True).first()
    return {'station': station, 'case': str(work.case_id), 'work': work.pk, 'schedule': schedule.pk,
            'finance_source': schedule.parent.source_id, 'adjustment': linked_adjustment,
            'review_evidence': work.case.evidence.get(kind='finance_review').pk,
            'decision_path': reverse('factory_invoice_decision', args=[work.pk]),
            'recovery_path': reverse('factory_invoice_recovery', args=[work.pk]),
            'analysis_path': reverse('finance_analysis', args=[work.case_id]),
            'report_path': reverse('schedule_report', args=[work.case_id, schedule.pk]),
            'existing_work_preserved': preserved}


def run():
    for station in STATIONS:
        print('PSL_FINANCE_SCHEDULE_FOLLOWUP_FIXTURE=' + json.dumps(prepare(station)), flush=True)

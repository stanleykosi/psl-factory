"""Prepare one received synthetic staff-cost report with no Assistant questions."""

import json
import os
from urllib.parse import urlencode
from uuid import NAMESPACE_URL, uuid5

from django.contrib.auth import get_user_model
from django.db import connection, transaction
from django.urls import reverse

from apps.agents.assistant_models import AssistantConversation
from apps.agents.payroll import received_report_context
from apps.core.models import Audit, Case
from apps.core.services import event
from apps.finance import payroll
from apps.finance.payroll_models import PayrollReportReceipt
from apps.finance.payroll_question_models import PayrollReportQuestion
from apps.identity.actions import ACTIONS
from apps.identity.models import Grant
from apps.policy.payroll_validators import QUESTION_ROUTE
from tests import payroll_helpers
from tests.helpers import rev
from tests.railway_batch_walkthrough_seed import PREVIEW_PROJECT
from tests.railway_finance_schedule_seed import fixture_reviewer


TENANT = 'design-zainab-received-payroll-report'
TITLE = 'SAMPLE received staff-cost report for Zainab'
CASE_ID = uuid5(NAMESPACE_URL, TENANT)
GUARD = 'PSL_ZAINAB_PAYROLL_REPORT_FIXTURE'
MARKER = 'sample.zainab_received_payroll_report'
OWNER = 'sample-zainab-report-hr-holder'
RECIPIENT_ACTIONS = ('case.read', 'payroll.read', 'payroll.report.read', 'payroll.report.receive', 'agent.extract')


def seed(case, recipient):
    users = get_user_model().objects
    owner = users.create_user(OWNER)
    Grant.objects.bulk_create([Grant(case=case, user=owner, action=action) for action in dict.fromkeys(ACTIONS)])

    def principal(role):
        if role == 'manager':
            return recipient
        return users.create_user(f'sample-zainab-report-{role}')

    fixture = payroll_helpers.fixture(employee_ids=['PRIVATE-ZAINAB-SAMPLE-001', 'PRIVATE-ZAINAB-SAMPLE-002'],
                                      context=(owner, case), principal=principal)
    Grant.objects.create(case=case, user=recipient, action='agent.extract')
    _, _, _, report = payroll_helpers.pipeline(fixture, 'sample-zainab-received-report')
    payroll_helpers.policy(fixture, QUESTION_ROUTE, {'owner_id': owner.pk, 'action': 'answer_aggregate_question',
        'disclosure': 'report_identity_and_topic_only', 'reply': 'closed_codes_only'})
    receipt = payroll.receive_report(recipient, case.pk, report.pk, rev(case))
    if (report.payload['disclosure'] != 'aggregate_only' or report.actor_id == recipient.pk
            or AssistantConversation.objects.filter(case=case).exists()
            or PayrollReportQuestion.objects.filter(case=case).exists()):
        raise RuntimeError('The fixture must stop at the original aggregate receipt before any question.')
    return event(owner, case, MARKER, recipient=recipient.pk, report=report.pk, receipt=receipt.pk,
                 publisher=report.actor_id, version=report.version, currency=report.payload['currency'],
                 period=report.payload['period'], total=report.payload['eligible_total'])


@transaction.atomic
def prepare():
    if os.getenv(GUARD) != '1':
        raise RuntimeError('Explicit synthetic received-report fixture permission is required.')
    recipient = fixture_reviewer()
    case, created = Case.objects.get_or_create(pk=CASE_ID,
        defaults={'tenant': TENANT, 'title': TITLE, 'kind': 'project', 'synthetic': True})
    if (case.tenant, case.title, case.kind, case.synthetic) != (TENANT, TITLE, 'project', True):
        raise RuntimeError('Preserve any existing case outside the exact synthetic payroll-report identity.')
    marker = seed(case, recipient) if created else Audit.objects.get(case=case, actor__username=OWNER, action=MARKER)
    pinned = marker.data
    access = set(Grant.objects.filter(case=case, user=recipient, active=True).values_list('action', flat=True))
    if recipient.pk != pinned['recipient'] or access != set(RECIPIENT_ACTIONS):
        raise RuntimeError('Preserve the fixture unless the original aggregate-only reader still matches.')
    receipt = PayrollReportReceipt.objects.select_related('publication').get(
        pk=pinned['receipt'], publication_id=pinned['report'], publication__request__case=case, actor=recipient)
    context = received_report_context(recipient, case)
    if (not context or (context['publication_id'], context['report_version']) != (pinned['report'], pinned['version'])
            or receipt.publication.actor_id != pinned['publisher']):
        raise RuntimeError('Use only the current original reviewed publication and the exact recipient receipt.')
    report_path = reverse('payroll_inspect', args=[case.pk, 'report', pinned['report']])
    return {**pinned, 'case': str(case.pk), 'preserved': not created, 'report_path': report_path,
            'assistant_path': reverse('assistant_start', args=['zainab']) + '?' + urlencode({'workspace': case.pk}),
            'question_path': reverse('payroll_questions', args=[case.pk]) + '?' + urlencode({'report': pinned['report']})}


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
    print('PSL_ZAINAB_PAYROLL_REPORT_FIXTURE=' + json.dumps(prepare()), flush=True)

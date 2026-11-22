"""Prepare an isolated held payroll combination for a separate human review."""

from copy import deepcopy
import json
import os
from pathlib import Path
from unittest.mock import patch
from uuid import NAMESPACE_URL, uuid5

from django.contrib.auth import get_user_model
from django.db import connection, transaction
from django.db.migrations.recorder import MigrationRecorder
from django.urls import reverse
from django.utils import timezone

from apps.core.models import Audit, Case
from apps.core.services import event
from apps.finance import payroll
from apps.finance.hrfinance_models import HRHandoffRecord
from apps.finance.payroll_models import PayrollPublication, PayrollReportReceipt, PayrollReview, PayrollRun
from apps.identity.models import Grant
from apps.identity.services import require
from apps.policy.operator_drafts import draft_operator_policy
from apps.policy.payroll_validators import ACCESS, MERGE
from apps.policy.services import transition
from apps.workflows import factory_payroll as flow
from apps.workflows.models import FactoryProgress, FactoryWork
from tests import payroll_helpers
from tests.helpers import rev
from tests.railway_admitted_schedule_seed import admitted_user
from tests.railway_batch_walkthrough_seed import PREVIEW_PROJECT
from tests.railway_finance_schedule_seed import fixture_reviewer


GUARD = 'PSL_ADMITTED_PAYROLL_DRAFT_WALKTHROUGH'
TENANT = 'design-admitted-payroll-combination-review'
MARKER = 'sample.payroll_draft_combination_prepared'
MAKER_ACTIONS = ('case.read', 'evidence.add', 'factory.read', 'factory.start', 'factory.execute', 'agent.payroll',
                 'payroll.read', 'payroll.private.read', 'payroll.request', 'payroll.combine', 'payroll.match',
                 'hrfinance.read', 'hrfinance.need', 'hrfinance.contract', 'hrfinance.snapshot.read', 'hrfinance.receive')
REVIEWER_ACTIONS = ('case.read', 'factory.read', 'payroll.read', 'payroll.private.read', 'payroll.review',
                    'hrfinance.read', 'hrfinance.snapshot.read', 'hrfinance.receive')
SOURCE_ACTIONS = ('case.read', 'evidence.add', 'policy.configure', 'policy.activate', 'policy.read',
                  'payroll.read', 'payroll.capture', 'hrfinance.read', 'hrfinance.authorize', 'hrfinance.capture')


def seed(case, owner, maker, reviewer, suffix):
    recipient = get_user_model().objects.create_user(f'sample-payroll-draft-aggregate-reader-{suffix}')
    principals = {'preparer': maker, 'reviewer': reviewer, 'manager': recipient}
    Grant.objects.bulk_create([Grant(case=case, user=owner, action=action) for action in SOURCE_ACTIONS])
    with patch.object(payroll_helpers, 'ACTIONS', tuple(dict.fromkeys((*MAKER_ACTIONS, *REVIEWER_ACTIONS)))):
        sample = payroll_helpers.fixture(context=(owner, case), principal=principals.__getitem__,
                                         preparer_receipt=False)
    for person, permitted in ((maker, MAKER_ACTIONS), (reviewer, REVIEWER_ACTIONS)):
        Grant.objects.filter(case=case, user=person).exclude(action__in=permitted).update(active=False)

    access = deepcopy(sample['config']['access'])
    merge = deepcopy(sample['config']['merge'])
    access.update(format='psl.payroll-access/v2', row_handling='hold_conflicting_rows', currency_mode='row_currency')
    merge.update(format='psl.payroll-merge/v2', duplicate_within_source='hold_conflicting_rows')
    payroll_helpers.policy(sample, ACCESS, access)
    payroll_helpers.policy(sample, MERGE, merge)
    context = sample['request'].metadata
    first = [{**row, 'currency': context['currency']} for row in sample['config']['exports'][0]['rows']]
    second = [{**sample['config']['exports'][1]['rows'][0], 'currency': context['currency']},
              {'row_ref': 'B2', 'employee_id': 'E002', 'component': 'BASIC', 'amount': '200', 'currency': context['currency']},
              {'row_ref': 'B3', 'employee_id': 'E004', 'component': 'BASIC', 'amount': '50', 'currency': None}]
    selected = [payroll_helpers.capture(sample, 0, 'sample-held-source-a', rows=first, source_version='SAMPLE-V2-A'),
                payroll_helpers.capture(sample, 1, 'sample-held-source-b', rows=second, control_total='400',
                                        source_version='SAMPLE-V2-B')]
    snapshot = sample['hr']
    profile = json.loads(Path('fixtures/factory-payroll.json').read_text())
    profile.pop('classification')
    config = draft_operator_policy(owner, case.pk, 'OPS.factory_payroll_execution', profile,
                                   sample['e']['policy_decision'].pk, timezone.now())
    transition(owner, config.pk, 'validated')
    transition(owner, config.pk, 'active')
    work = flow.start(maker, case.pk, 'SAMPLE-HELD-PAYROLL-COMBINATION', sample['request'].pk,
                     {'input_ids': [row.pk for row in selected], 'hr_snapshot_id': snapshot.pk},
                     'SAMPLE review the held payroll combination', rev(case))
    combined = flow.human_action(maker, work.pk, work.revision, rev(case), 'working', {'stage': 'combine'})
    payroll.authority(reviewer, sample['request'], 'combine', maker.pk)
    _, eligible = payroll.draft_matching.scope(reviewer, combined)
    summary = payroll.draft_matching.summary(combined, eligible)
    if (summary != {'eligible_rows': 1, 'held_rows': 2, 'known_amount': '100', 'currency': context['currency']}
            or [row['source_amount'] for row in selected[1].payload['rows']] != ['150', '200', '50']
            or PayrollReview.objects.filter(request__case=case).exists()
            or PayrollRun.objects.filter(request__case=case).exclude(kind='combine').exists()
            or PayrollPublication.objects.filter(request__case=case).exists()
            or PayrollReportReceipt.objects.filter(publication__request__case=case).exists()
            or FactoryProgress.objects.filter(work=work).exists()
            or HRHandoffRecord.objects.filter(kind='receipt', snapshot=snapshot, actor=maker).exists()):
        raise RuntimeError('Preserve the exact held sources and leave decisions, matching and receipts for the walkthrough.')
    return {'work': work.pk, 'request': sample['request'].pk, 'combined': combined.pk,
            'inputs': [row.pk for row in selected], 'snapshot': snapshot.pk,
            'review_proof': sample['e']['payroll_review'].pk, 'hr_receipt_proof': sample['e']['hr_disclosure_decision'].pk,
            **summary}


@transaction.atomic
def prepare(invitation_id, user_id):
    if os.getenv(GUARD) != '1':
        raise RuntimeError('Explicit opt-in for the isolated synthetic payroll sample is required.')
    reviewer = fixture_reviewer()
    admission, maker = admitted_user(invitation_id, user_id, reviewer)
    require(maker, admission.invitation.case, 'case.read')
    attributes = {'tenant': TENANT, 'title': f'SAMPLE held payroll combination {invitation_id}',
                  'kind': 'project', 'synthetic': True}
    case, created = Case.objects.get_or_create(pk=uuid5(NAMESPACE_URL, f'{TENANT}:{invitation_id}'), defaults=attributes)
    if any(getattr(case, key) != value for key, value in attributes.items()) or case.pk == admission.invitation.case_id:
        raise RuntimeError('Use the separate exact synthetic workspace only.')
    identity = {'invitation': invitation_id, 'admission': admission.pk, 'maker': maker.pk, 'reviewer': reviewer.pk}
    username = f'sample-payroll-draft-source-holder-{invitation_id}'
    if created:
        owner = get_user_model().objects.create_user(username)
        marker = event(owner, case, MARKER, **identity, **seed(case, owner, maker, reviewer, invitation_id))
    else:
        marker = Audit.objects.get(case=case, actor__username=username, action=MARKER)
    if any(marker.data.get(key) != value for key, value in identity.items()):
        raise RuntimeError('Preserve the existing specimen and the original admitted users.')
    for person, expected in ((maker, MAKER_ACTIONS), (reviewer, REVIEWER_ACTIONS)):
        if set(Grant.objects.filter(case=case, user=person, active=True).values_list('action', flat=True)) != set(expected):
            raise RuntimeError('The original isolated reviewer or matcher authority changed. Preserve it for review.')
    work_id = marker.data['work']
    FactoryWork.objects.get(case=case, actor=maker, pk=work_id, definition=flow.DEFINITION)
    return {**marker.data, 'case': str(case.pk), 'preserved': not created,
            'decision_path': reverse('factory_invoice_decision', args=[work_id]),
            'recovery_path': reverse('factory_invoice_recovery', args=[work_id])}


def run(invitation_id, user_id):
    if (os.getenv('RAILWAY_PROJECT_ID'), os.getenv('RAILWAY_ENVIRONMENT_NAME'), os.getenv('RAILWAY_SERVICE_ID'),
            os.getenv(GUARD)) != (PREVIEW_PROJECT, 'design-acceptance', '00c14ca1-5361-4bee-97a5-2ec7aba6ef18', '1'):
        raise RuntimeError('Use only the isolated Railway acceptance checks service.')
    database = os.getenv('PGDATABASE', '')
    if not database or database.lower().startswith('test_') or connection.vendor != 'postgresql':
        raise RuntimeError('Select the existing PostgreSQL preview database.')
    with connection.cursor() as cursor:
        cursor.execute('SELECT current_database()')
        if cursor.fetchone()[0] != database:
            raise RuntimeError('The configured preview database must match the current connection.')
    if not MigrationRecorder(connection).migration_qs.filter(app='finance', name='0084_payroll_draft_match_guard').exists():
        raise RuntimeError('Apply the verified draft-only match guard before preparing this browser specimen.')
    print('PSL_ADMITTED_PAYROLL_DRAFT_FIXTURE=' + json.dumps(prepare(invitation_id, user_id)), flush=True)

"""Prepare one approved synthetic payroll draft for a recipient-only Trial journey."""
import json
import os
from pathlib import Path
from unittest.mock import patch
from uuid import NAMESPACE_URL, uuid5

from django.contrib.auth import get_user_model
from django.db import connection, transaction
from django.urls import reverse
from django.utils import timezone

from apps.core.models import Audit, Case
from apps.core.services import event
from apps.finance import payroll
from apps.finance.models import PayrollPublication, PayrollReportReceipt
from apps.identity.models import Grant
from apps.identity.services import require
from apps.policy.operator_drafts import draft_operator_policy
from apps.policy.services import transition
from apps.workflows import factory_payroll as flow
from apps.workflows.models import FactoryWork
from tests import payroll_helpers
from tests.helpers import rev
from tests.railway_admitted_payroll_draft_seed import MAKER_ACTIONS, REVIEWER_ACTIONS, SOURCE_ACTIONS
from tests.railway_admitted_schedule_seed import admitted_user
from tests.railway_batch_walkthrough_seed import PREVIEW_PROJECT
from tests.railway_finance_schedule_seed import fixture_reviewer


GUARD = 'PSL_PAYROLL_FOLLOWUP_DRAFT_FIXTURE'
TENANT = 'design-payroll-followup-draft'
MARKER = 'sample.payroll_followup_draft_prepared'
TRIAL_ACTIONS = {'case.read', 'factory.read', 'payroll.read', 'payroll.report.read', 'payroll.report.receive'}
PREPARER_ACTIONS = set(MAKER_ACTIONS) | {'factory.manage', 'payroll.aggregate', 'payroll.publish'}
REASON = 'Fictional provider correction requires a clearly marked replacement of the original report.'


def populate(case, holder, maker, trial, suffix):
    reviewer = get_user_model().objects.create_user(username=f'sample-payroll-followup-reviewer-{suffix}')
    roles = {'preparer': maker, 'reviewer': reviewer, 'manager': trial}
    Grant.objects.bulk_create([Grant(case=case, user=holder, action=action) for action in SOURCE_ACTIONS])
    with patch.object(payroll_helpers, 'ACTIONS', tuple(sorted(PREPARER_ACTIONS | set(REVIEWER_ACTIONS)))):
        sample = payroll_helpers.fixture(context=(holder, case), principal=roles.__getitem__)
    for person, allowed in ((maker, PREPARER_ACTIONS), (reviewer, REVIEWER_ACTIONS)):
        Grant.objects.filter(case=case, user=person).exclude(action__in=allowed).update(active=False)
    Grant.objects.create(case=case, user=trial, action='factory.read')
    profile = json.loads(Path('fixtures/factory-payroll.json').read_text(encoding='utf-8'))
    profile.pop('classification')
    config = draft_operator_policy(holder, case.pk, 'OPS.factory_payroll_execution', profile,
                                   sample['e']['policy_decision'].pk, timezone.now())
    transition(holder, config.pk, 'validated')
    transition(holder, config.pk, 'active')

    request, snapshot = sample['request'], sample['hr']
    inputs = [source.pk for source in sample['inputs']]
    work = flow.start(maker, case.pk, 'SAMPLE-PAYROLL-CORRECTED-REPORT', request.pk,
                      {'input_ids': inputs, 'hr_snapshot_id': snapshot.pk},
                      'SAMPLE payroll withdrawal and replacement', rev(case))
    for source in sample['inputs']:
        payroll_helpers.approve(sample, source)
    combined = payroll.combine(maker, case.pk, request.pk, inputs, flow.key(work, 'combine'), rev(case))
    payroll_helpers.approve(sample, combined)
    matching = payroll.match(maker, case.pk, combined.pk, snapshot.pk, flow.key(work, 'match'), rev(case))
    payroll_helpers.approve(sample, matching)
    aggregate = payroll.aggregate(maker, case.pk, matching.pk, flow.key(work, 'aggregate'), rev(case))
    approval = payroll_helpers.approve(sample, aggregate)
    if (flow.report(work, maker)['stage'] != 'publish' or PayrollPublication.objects.filter(request=request).exists()
            or PayrollReportReceipt.objects.filter(publication__request=request).exists() or flow.withdrawal(work)):
        raise RuntimeError('Leave the reviewed synthetic report unpublished and the withdrawal for a fresh action.')
    return {'work': work.pk, 'request': request.pk, 'inputs': inputs, 'snapshot': snapshot.pk,
            'aggregate': aggregate.pk, 'approval': approval.pk, 'reviewer': reviewer.pk,
            'review_proof': sample['e']['payroll_review'].pk}


@transaction.atomic
def prepare(invitation_id, user_id):
    if os.getenv(GUARD) != '1':
        raise RuntimeError('Use the explicit isolated payroll follow-up draft guard.')
    receiver = fixture_reviewer()
    admission, maker = admitted_user(invitation_id, user_id, receiver)
    require(maker, admission.invitation.case, 'case.read')
    case_id = uuid5(NAMESPACE_URL, f'{TENANT}:{admission.pk}:{maker.pk}')
    attrs = {'tenant': TENANT, 'title': f'SAMPLE payroll follow-up draft {admission.pk}', 'kind': 'project', 'synthetic': True}
    case, created = Case.objects.get_or_create(pk=case_id, defaults=attrs)
    case = Case.objects.select_for_update().get(pk=case.pk)
    if any(getattr(case, key) != value for key, value in attrs.items()) or case.pk == admission.invitation.case_id:
        raise RuntimeError('Use only the distinct named synthetic draft workspace.')
    name = f'sample-payroll-followup-holder-{admission.pk}'
    identity = {'invitation': invitation_id, 'admission': admission.pk, 'maker': maker.pk, 'receiver': receiver.pk}
    if created:
        holder = get_user_model().objects.create_user(username=name)
        marker = event(holder, case, MARKER, **identity, **populate(case, holder, maker, receiver, admission.pk))
    else:
        marker = Audit.objects.select_related('actor').get(case=case, action=MARKER, actor__username=name)
    data, holder = marker.data, marker.actor
    if (any(data.get(key) != value for key, value in identity.items()) or not holder.is_active or holder.is_staff
            or holder.is_superuser or holder.has_usable_password() or Grant.objects.filter(user=holder).exclude(case=case).exists()):
        raise RuntimeError('Preserve the distinct admitted people and own source holder.')
    for actor, actions in ((maker, PREPARER_ACTIONS), (receiver, TRIAL_ACTIONS)):
        if set(Grant.objects.filter(case=case, user=actor, active=True).values_list('action', flat=True)) != actions:
            raise RuntimeError('Preserve exact case-local publisher and aggregate-only receiver actions.')
    work = FactoryWork.objects.get(pk=data['work'], case=case, definition=flow.DEFINITION, actor=maker)
    if receiver.pk in payroll.access(payroll.exact(case, payroll.PayrollRequest, data['request']))[1]['reader_ids']:
        raise RuntimeError('The receiver must have no restricted payroll source access.')
    if not flow.publication_history(work).filter(run_id=data['aggregate']).exists():
        report = flow.run(work, 'aggregate')
        if not report or report.pk != data['aggregate'] or payroll.current_review(report).pk != data['approval']:
            raise RuntimeError('The approved draft changed. Preserve it for review.')
    publication = flow.publication(work)
    return {**data, 'case': str(case.pk), 'preserved': not created, 'publication': publication.pk if publication else None,
            'reason': REASON, 'publish_path': reverse('factory_work_response', args=[work.pk]),
            'recovery_path': reverse('factory_invoice_recovery', args=[work.pk])}


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
            raise RuntimeError('The configured preview database must match the connection.')
    print(GUARD + '=' + json.dumps(prepare(invitation_id, user_id)), flush=True)

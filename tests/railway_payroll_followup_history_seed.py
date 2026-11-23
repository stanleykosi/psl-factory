"""Model a past internal synthetic withdrawal and leave the replacement for the browser."""
import json
import os
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from django.contrib.auth import get_user_model
from django.db import connection, transaction
from django.urls import reverse
from django.utils import timezone

from apps.core.models import Audit, Case
from apps.core.services import event
from apps.finance import payroll
from apps.finance.payroll_models import PayrollPublication, PayrollReportReceipt, PayrollReview
from apps.identity.models import Grant
from apps.identity.services import require
from apps.workflows import factory_payroll as flow
from apps.workflows.models import FactoryWork
from tests import railway_payroll_followup_draft_seed as draft
from tests.helpers import rev
from tests.railway_admitted_schedule_seed import admitted_user
from tests.railway_batch_walkthrough_seed import PREVIEW_PROJECT
from tests.railway_finance_schedule_seed import fixture_reviewer


GUARD = 'PSL_PAYROLL_FOLLOWUP_HISTORY_FIXTURE'
TENANT = 'design-payroll-withdrawal-recipient-history'
MARKER = 'sample.payroll_followup_history_prepared'
REASON = 'Synthetic prior withdrawal: the original provider supplied a different confirmed total.'


def populate(case, holder, maker, recipient, suffix):
    data = draft.populate(case, holder, maker, recipient, f'history-{suffix}')
    reviewer = get_user_model().objects.get(pk=data['reviewer'], is_active=True, is_staff=False, is_superuser=False)
    work = FactoryWork.objects.get(pk=data['work'], case=case, actor=maker)
    request = payroll.exact(case, payroll.PayrollRequest, data['request'])
    # These effects are fictional internal baseline facts, created only in this new isolated case.
    original = flow.human_action(maker, work.pk, work.revision, rev(case), 'publish', {})
    original_receipt = flow.human_action(recipient, work.pk, work.revision, rev(case), 'receive',
                                         {'publication_id': original.pk})
    stopped = flow.cancel(maker, work.pk, work.revision)
    withdrawn = flow.withdraw_publication(reviewer, work.pk, stopped.revision, rev(case), original.pk,
                                          data['review_proof'], REASON)
    if (original.version != 1 or original_receipt.actor_id != recipient.pk
            or withdrawn.actor_id != reviewer.pk or stopped.status != 'followup_needed'):
        raise RuntimeError('The fixture requires one distinct synthetic internal receipt and authorised withdrawal.')

    export = json.loads(Path('fixtures/payroll.json').read_text(encoding='utf-8'))['exports'][0]
    if export['provider'] != 'PAY-A' or len(export['rows']) != 1:
        raise RuntimeError('The exact synthetic provider fixture is required.')
    export.update(source_version='SAMPLE-PAY-A-HISTORY-v2', extracted_at=timezone.now().isoformat(), control_total='110')
    export['rows'][0]['amount'] = '110'
    corrected = payroll.capture(holder, case.pk, request.pk, 'PAY-A', 'sample-historical-payroll-replacement',
                                json.dumps(export, sort_keys=True), rev(case))
    current_inputs = [corrected.pk, data['inputs'][1]]
    work.refresh_from_db()
    work = flow.prepare_successor(maker, work.pk, work.revision, rev(case), original.pk, request.pk,
                                  {'input_ids': current_inputs, 'hr_snapshot_id': data['snapshot']}, REASON)

    def approve(kind, source):
        return payroll.review(reviewer, case.pk, kind, source.pk, 'approve', f'sample-history-review-{kind}-{source.pk}',
                              data['review_proof'], rev(case))

    approve('input', corrected)
    combined = payroll.combine(maker, case.pk, request.pk, current_inputs, flow.key(work, 'combine'), rev(case))
    approve('run', combined)
    matched = payroll.match(maker, case.pk, combined.pk, data['snapshot'], flow.key(work, 'match'), rev(case))
    approve('run', matched)
    aggregate = payroll.aggregate(maker, case.pk, matched.pk, flow.key(work, 'aggregate'), rev(case))
    approval = approve('run', aggregate)
    if (flow.report(work, maker)['stage'] != 'publish' or flow.publication(work) is not None
            or flow.publication_history(work).count() != 1 or original.payload['eligible_total'] != '250.00'
            or aggregate.result['eligible_total'] != '260.00'):
        raise RuntimeError('Keep the original effect and leave only the reviewed replacement ready for publication.')
    return {**data, 'original_publication': original.pk, 'original_receipt': original_receipt.pk,
            'withdrawal_decision': withdrawn.pk, 'withdrawal': flow.withdrawal(work, original.pk).pk,
            'corrected_input': corrected.pk, 'current_inputs': current_inputs,
            'successor_aggregate': aggregate.pk, 'successor_review': approval.pk}


@transaction.atomic
def prepare(invitation_id, user_id):
    if os.getenv(GUARD) != '1':
        raise RuntimeError('Explicit synthetic historical payroll preparation is required.')
    recipient = fixture_reviewer()
    admission, maker = admitted_user(invitation_id, user_id, recipient)
    require(maker, admission.invitation.case, 'case.read')
    cid = uuid5(NAMESPACE_URL, f'{TENANT}:{admission.pk}:{maker.pk}')
    attrs = {'tenant': TENANT, 'title': f'SAMPLE payroll withdrawal history {admission.pk}', 'kind': 'project', 'synthetic': True}
    case, created = Case.objects.get_or_create(pk=cid, defaults=attrs)
    case = Case.objects.select_for_update().get(pk=case.pk)
    if any(getattr(case, key) != value for key, value in attrs.items()) or case.pk == admission.invitation.case_id:
        raise RuntimeError('Use only the separately named synthetic history workspace.')
    name = f'sample-payroll-history-holder-{admission.pk}'
    identity = {'invitation': invitation_id, 'admission': admission.pk, 'maker': maker.pk, 'recipient': recipient.pk}
    if created:
        holder = get_user_model().objects.create_user(username=name)
        marker = event(holder, case, MARKER, **identity, **populate(case, holder, maker, recipient, admission.pk))
    else:
        marker = Audit.objects.select_related('actor').get(case=case, action=MARKER, actor__username=name)
    data, holder = marker.data, marker.actor
    if (any(data.get(key) != value for key, value in identity.items()) or not holder.is_active or holder.is_staff
            or holder.is_superuser or holder.has_usable_password() or Grant.objects.filter(user=holder).exclude(case=case).exists()):
        raise RuntimeError('Preserve the apart synthetic holder and exact admitted accounts.')
    for actor, allowed in ((maker, draft.PREPARER_ACTIONS), (recipient, draft.TRIAL_ACTIONS)):
        if set(Grant.objects.filter(case=case, user=actor, active=True).values_list('action', flat=True)) != allowed:
            raise RuntimeError('Preserve the exact scoped preparer and aggregate-only recipient.')
    work = FactoryWork.objects.get(pk=data['work'], case=case, definition=flow.DEFINITION, actor=maker)
    original = PayrollPublication.objects.defer('payload').get(pk=data['original_publication'], request__case=case,
                                                               run_id=data['aggregate'], version=1, actor=maker)
    PayrollReportReceipt.objects.get(pk=data['original_receipt'], publication=original, actor=recipient)
    withdrawal = flow.withdrawal(work, original.pk)
    if not withdrawal or withdrawal.pk != data['withdrawal'] or withdrawal.data['decision'] != data['withdrawal_decision']:
        raise RuntimeError('Preserve the exact original internal withdrawal.')
    PayrollReview.objects.get(pk=data['withdrawal_decision'], run=original.run, actor_id=data['reviewer'], verdict='revoke')
    successor = flow.run(work, 'aggregate')
    if not successor or successor.pk != data['successor_aggregate'] or payroll.current_review(successor).pk != data['successor_review']:
        raise RuntimeError('Preserve the exact reviewed successor prepared in this sample.')
    current = flow.publication(work)
    if current and (current.actor_id != maker.pk or current.run_id != successor.pk or current.version != 2):
        raise RuntimeError('Only the exact reviewed successor may be released on this specimen.')
    return {**data, 'case': str(case.pk), 'preserved': not created, 'successor_publication': current.pk if current else None,
            'prepared_history_is_synthetic': True, 'publish_path': reverse('factory_work_response', args=[work.pk]),
            'recipient_path': reverse('factory_invoice_recovery', args=[work.pk])}


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

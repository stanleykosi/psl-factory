"""Prepare the exact independent Return step for a separate payroll combination."""
import json
import os
from uuid import NAMESPACE_URL, uuid5

from django.contrib.auth import get_user_model
from django.db import connection, transaction
from django.urls import reverse

from apps.core.models import Audit, Case
from apps.core.services import event
from apps.finance import payroll
from apps.finance.models import PayrollPublication, PayrollReview, PayrollRun
from apps.identity.models import Grant
from apps.identity.services import require
from apps.workflows import factory_payroll as flow
from apps.workflows.models import FactoryWork
from tests import railway_payroll_review_walkthrough_seed as review_sample
from tests.helpers import rev
from tests.railway_admitted_schedule_seed import admitted_user
from tests.railway_batch_walkthrough_seed import PREVIEW_PROJECT
from tests.railway_finance_schedule_seed import fixture_reviewer


GUARD = 'PSL_PAYROLL_COMBINE_RETURN_FIXTURE'
TENANT = 'design-payroll-combine-return-rebuild'
MARKER = 'sample.payroll_combine_return_prepared'
RETURN_NOTE = 'Please rebuild the fictional combined payroll and confirm its exact provider coverage.'
REBUILD_REASON = 'Rebuild the exact two accepted sources after the independent combined payroll return.'


def populate(case, holder, maker, reviewer, suffix):
    data = review_sample.seed(case, holder, maker, reviewer, f'combine-return-{suffix}')
    work = FactoryWork.objects.get(pk=data['work'], case=case, actor=maker)
    inputs = [data['other_input'], data['original_input']]
    for source in inputs:
        payroll.review(reviewer, case.pk, 'input', source, 'approve', f'sample-prepare-{source}',
                       data['review_proof'], rev(case))
    combined = payroll.combine(maker, case.pk, data['request'], inputs, flow.key(work, 'combine'), rev(case))
    if (combined.metadata['status'] != 'complete' or flow.report(work, reviewer)['stage'] != 'combine_review'
            or combined.reviews.exists() or PayrollRun.objects.filter(request__case=case).exclude(pk=combined.pk).exists()
            or PayrollPublication.objects.filter(request__case=case).exists()):
        raise RuntimeError('Leave the first combination unreviewed and all matching and publication untouched.')
    return {**data, 'combined': combined.pk, 'inputs': inputs, 'original_head': work.source_head_id}


@transaction.atomic
def prepare(invitation_id, user_id):
    if os.getenv(GUARD) != '1':
        raise RuntimeError('Use the explicit isolated payroll combination guard.')
    reviewer = fixture_reviewer()
    admission, maker = admitted_user(invitation_id, user_id, reviewer)
    require(maker, admission.invitation.case, 'case.read')
    cid = uuid5(NAMESPACE_URL, f'{TENANT}:{admission.pk}:{maker.pk}')
    attrs = {'tenant': TENANT, 'title': f'SAMPLE combined payroll return {admission.pk}', 'kind': 'project', 'synthetic': True}
    case, created = Case.objects.get_or_create(pk=cid, defaults=attrs)
    case = Case.objects.select_for_update().get(pk=case.pk)
    if any(getattr(case, key) != value for key, value in attrs.items()) or case.pk == admission.invitation.case_id:
        raise RuntimeError('Use only the separate named synthetic combination case.')
    username = f'sample-payroll-combine-holder-{admission.pk}'
    identity = {'admission': admission.pk, 'invitation': invitation_id, 'maker': maker.pk, 'reviewer': reviewer.pk}
    if created:
        holder = get_user_model().objects.create_user(username=username)
        marker = event(holder, case, MARKER, **identity, **populate(case, holder, maker, reviewer, admission.pk))
    else:
        marker = Audit.objects.select_related('actor').get(case=case, action=MARKER, actor__username=username)
    data, holder = marker.data, marker.actor
    if (any(data.get(key) != value for key, value in identity.items()) or not holder.is_active or holder.is_staff
            or holder.is_superuser or holder.has_usable_password() or Grant.objects.filter(user=holder).exclude(case=case).exists()):
        raise RuntimeError('Preserve the admitted preparer, independent Trial reviewer and non-interactive source holder.')
    for actor, actions in ((maker, review_sample.MAKER_GRANTS), (reviewer, review_sample.REVIEWER_GRANTS)):
        if set(Grant.objects.filter(case=case, user=actor, active=True).values_list('action', flat=True)) != actions:
            raise RuntimeError('Preserve exact case-local preparer and reviewer responsibilities.')
    work = FactoryWork.objects.get(pk=data['work'], case=case, actor=maker, definition=flow.DEFINITION)
    combined = PayrollRun.objects.get(pk=data['combined'], request_id=data['request'], request__case=case, actor=maker, kind='combine')
    current = flow.run(work, 'combine')
    prior_return = PayrollReview.objects.filter(run=combined, actor=reviewer, verdict='return').first()
    if (combined.metadata['input_ids'] != data['inputs'] or PayrollPublication.objects.filter(request__case=case).exists()
            or work.source_head_id != data['original_head'] and prior_return is None):
        raise RuntimeError('Preserve the original exact combination and its justified same-source rebuild.')
    return {**data, 'case': str(case.pk), 'preserved': not created, 'returned': prior_return.pk if prior_return else None,
            'current_combine': current.pk if current else None, 'return_note': RETURN_NOTE, 'rebuild_reason': REBUILD_REASON,
            'decision_path': reverse('factory_invoice_decision', args=[work.pk]),
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

"""Guarded preview invoice stop with one issued original and one unsent draft."""
import json
import os
from unittest.mock import patch
from uuid import NAMESPACE_URL, uuid5

from django.contrib.auth import get_user_model
from django.db import connection, transaction
from django.urls import reverse

from apps.core.models import Audit, Case
from apps.core.services import event
from apps.finance import invoice_delivery, invoices
from apps.finance.models import Invoice, InvoiceDelivery, InvoiceIssue, InvoiceJob, InvoiceReview
from apps.identity.actions import ACTIONS
from apps.identity.models import Grant
from apps.workflows import factory
from apps.workflows.factory_invoice_cancellation import eligible, existing_issue, readback
from apps.workflows.models import FactoryProgress, FactoryWork, HumanTask
from tests import usage_intake_helpers
from tests.helpers import rev
from tests.obligation_helpers import identified
from tests.railway_batch_walkthrough_seed import PREVIEW_PROJECT
from tests.test_factory_invoice_intake import prepared, start


TENANT = 'design-invoice-draft-stop'
CASE_ID = uuid5(NAMESPACE_URL, TENANT)
TITLE = 'SAMPLE duplicate invoice draft to stop'
MARKER = 'sample.invoice_draft_stop_prepared'
TRIAL = 'psl-agent-trial'
PREPARER = 'sample-duplicate-invoice-preparer'
DUPLICATE = 'SAMPLE-DUPLICATE-INVOICE'
ORIGINAL = 'SAMPLE-ISSUED-INVOICE'
REASON = 'This duplicate was never sent. The billing obligation is already recorded on the existing invoice.'
TRIAL_ACTIONS = {'case.read', 'factory.read', 'factory.manage', 'finance.read'}


def create_station(case, trial):
    owner = get_user_model().objects.create_user(PREPARER)
    Grant.objects.bulk_create([
        *[Grant(user=owner, case=case, action=action) for action in dict.fromkeys(ACTIONS)],
        *[Grant(user=trial, case=case, action=action) for action in sorted(TRIAL_ACTIONS)],
    ])
    with patch.object(usage_intake_helpers, 'setup_case', return_value=(owner, case)):
        data = prepared(PREPARER)
    work = start(data, reference=DUPLICATE)
    factory.run_until_wait(work.pk)
    work.refresh_from_db()
    task = HumanTask.objects.get(case=case, kind='factory_review', status='open', context__work=work.pk)
    if not eligible(trial, work) or task.claimed_by_id is not None or task.context['packet']['invoice'] != work.invoice_id:
        raise RuntimeError('Use an exact unapproved synthetic duplicate before its first invoice operation.')

    invoice = invoices.draft(owner, case.pk, data['prep'].pk, ORIGINAL, work.invoice.due_date, rev(case))
    identified(owner, case, invoice)
    review = invoices.review(owner, case.pk, invoice.pk, 'Finance', 'approve', data['proof'].pk,
                             'Synthetic internal invoice reviewed separately from the duplicate.', rev(case))
    job = invoices.reserve(owner, case.pk, invoice.pk, 'issue', 'Finance', rev(case))
    if not invoice_delivery.run_once(case_id=case.pk, job_id=job.pk):
        raise RuntimeError('The original synthetic internal issue did not settle.')
    issue = InvoiceIssue.objects.get(invoice=invoice, job=job)
    return event(owner, case, MARKER, trial=trial.pk, work=work.pk, draft=work.invoice_id,
                 draft_sha256=work.invoice.sha256, task=task.pk, invoice=invoice.pk, issue=issue.pk,
                 job=job.pk, review=review.pk)


@transaction.atomic
def prepare():
    trial = get_user_model().objects.get(username=TRIAL, is_active=True, is_staff=False, is_superuser=False)
    if Case.objects.filter(tenant=TENANT).exclude(pk=CASE_ID).exists():
        raise RuntimeError('Use only the exact duplicate invoice sample workspace.')
    case, created = Case.objects.get_or_create(pk=CASE_ID, defaults={
        'tenant': TENANT, 'title': TITLE, 'kind': 'project', 'synthetic': True,
    })
    case = Case.objects.select_for_update().get(pk=case.pk)
    if (case.tenant, case.title, case.kind, case.synthetic) != (TENANT, TITLE, 'project', True):
        raise RuntimeError('The duplicate invoice sample workspace must be synthetic and unchanged.')
    marker = create_station(case, trial) if created else Audit.objects.select_related('actor').get(case=case, action=MARKER)
    data, owner = marker.data, marker.actor
    if (data['trial'] != trial.pk or owner.username != PREPARER or owner.has_usable_password()
            or not owner.is_active or owner.is_staff or owner.is_superuser
            or Grant.objects.filter(user=owner).exclude(case=case).exists()
            or set(Grant.objects.filter(case=case, user=trial, active=True).values_list('action', flat=True)) != TRIAL_ACTIONS):
        raise RuntimeError('Preserve the original case-local preparer and Trial authorities.')
    work = FactoryWork.objects.select_related('invoice').get(
        pk=data['work'], case=case, definition='pmo-finance/v1', actor=owner,
        invoice_id=data['draft'], invoice__reference=DUPLICATE, invoice__sha256=data['draft_sha256'],
    )
    task = HumanTask.objects.get(pk=data['task'], case=case, kind='factory_review', context__work=work.pk)
    issue = existing_issue(trial, work, data['invoice'])
    if (not issue or (issue.pk, issue.job_id, issue.invoice.reference) != (data['issue'], data['job'], ORIGINAL)
            or work.invoice.preparation_id != issue.invoice.preparation_id
            or Invoice.objects.filter(case=case).count() != 2
            or InvoiceReview.objects.filter(invoice__case=case).exclude(pk=data['review'], invoice=issue.invoice).exists()
            or InvoiceJob.objects.filter(invoice__case=case).exclude(pk=issue.job_id).exists()
            or InvoiceDelivery.objects.filter(invoice__case=case).exists() or FactoryProgress.objects.filter(work=work).exists()):
        raise RuntimeError('Preserve the separate original internal issue and unsent duplicate.')
    stopped = readback(trial, work)
    if stopped:
        if stopped['actor'].pk != trial.pk or task.status != 'returned':
            raise RuntimeError('Only Trial can stop the exact duplicate in this walkthrough.')
    elif task.status != 'open' or task.claimed_by_id or not eligible(trial, work):
        raise RuntimeError('Use the exact review wait before stopping the duplicate.')
    return {**data, 'case': str(case.pk), 'reason': REASON, 'reference': ORIGINAL,
            'recovery': reverse('factory_invoice_recovery', args=[work.pk]),
            'work_path': reverse('factory_detail', args=[work.pk]), 'stopped': bool(stopped), 'preserved': not created}


def run():
    if (os.getenv('RAILWAY_PROJECT_ID'), os.getenv('RAILWAY_ENVIRONMENT_NAME'),
            os.getenv('PSL_INVOICE_DRAFT_STOP_FIXTURE')) != (PREVIEW_PROJECT, 'design-acceptance', '1'):
        raise RuntimeError('Use the explicit duplicate invoice guard in the exact Railway acceptance project.')
    database = os.getenv('PGDATABASE', '')
    if connection.vendor != 'postgresql' or not database or database.startswith('test_') or database != connection.settings_dict['NAME']:
        raise RuntimeError('Set the explicit acceptance preview PostgreSQL database.')
    print('PSL_INVOICE_DRAFT_STOP_FIXTURE=' + json.dumps(prepare()), flush=True)

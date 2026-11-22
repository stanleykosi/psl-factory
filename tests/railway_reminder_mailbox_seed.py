"""Provision only named synthetic fixtures for the Railway browser walkthrough."""
from datetime import timedelta
from io import BytesIO
import json
import os
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import transaction
from django.utils import timezone
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from apps.agents.models import CaseUpload
from apps.agents.upload_views import upload_file
from apps.core.models import Case
from apps.core.services import add_evidence
from apps.finance import reminders
from apps.finance.models import InvoiceIssue
from apps.identity.actions import ACTIONS
from apps.identity.models import Grant
from apps.policy.operator_drafts import draft_operator_policy
from apps.policy.reminder_validators import COMPONENT
from apps.policy.services import resolve, transition
from apps.workflows.models import FactoryWork
from tests import document_helpers
from tests.test_factory_reporting import FactoryReportingTests

if os.environ.get('RAILWAY_ENVIRONMENT_NAME') != 'design-acceptance':
    raise SystemExit('Exact isolated acceptance environment required')
users = get_user_model()
actor = users.objects.get(username='psl-agent-trial', is_active=True, is_staff=False, is_superuser=False)


def sample_invoice():
    writer, output = PdfWriter(), BytesIO()
    page = writer.add_blank_page(width=500, height=230)
    name = NameObject
    page[name('/Resources')] = DictionaryObject({name('/Font'): DictionaryObject({
        name('/F1'): DictionaryObject({name('/Type'):name('/Font'),name('/Subtype'):name('/Type1'),name('/BaseFont'):name('/Helvetica')})
    })})
    stream = DecodedStreamObject()
    stream.set_data(b'BT /F1 16 Tf 48 180 Td (Synthetic invoice BROWSER-INVOICE-001) Tj 0 -30 Td (Issued total: NGN 32.25) Tj ET')
    page[name('/Contents')] = stream
    writer.write(output)
    return SimpleUploadedFile('BROWSER-INVOICE-001.pdf', output.getvalue(), content_type='application/pdf')


@transaction.atomic
def mailbox():
    case = Case.objects.get(tenant='design-browser-acceptance', title='Browser acceptance client billing and receipts', synthetic=True)
    issue = InvoiceIssue.objects.get(invoice__case=case, invoice__reference='BROWSER-INVOICE-001', invoice__amount='32.25')
    contact = reminders.contact(issue)
    if not contact or contact.email != 'browser-billing@example.invalid':
        raise RuntimeError('Exact synthetic contact needed')
    result = resolve(COMPONENT, case)
    if result.status != 'ACTIVE' or reminders._settings(case)[1]['mode'] != 'synthetic_mailbox':
        proof = add_evidence(actor, case.pk, 'policy_decision', 'Synthetic mailbox fixture. No external mail is sent.', 'synthetic:mailbox')
        cfg = draft_operator_policy(actor, case.pk, COMPONENT, {
            'contact_revision_ids':[contact.pk], 'sender_ids':[actor.pk], 'receipt_recorder_ids':[actor.pk],
            'mode':'synthetic_mailbox', 'days_after_due':0, 'minimum_days_between':0,
            'schedule_days_ahead':2, 'attachment_required':True,
        }, proof.pk, timezone.now()-timedelta(seconds=1))
        transition(actor,cfg.pk,'validated')
        transition(actor,cfg.pk,'active')
    sample = CaseUpload.objects.filter(case=case, actor=actor, name='BROWSER-INVOICE-001.pdf').first()
    if sample is None:
        sample = upload_file(actor, case, sample_invoice())
    return {'case':str(case.pk), 'issue':issue.pk, 'upload':sample.pk}


def weekly(kind):
    case, created = Case.objects.get_or_create(tenant='design-browser-recovery', kind='project', synthetic=True,
                                               title=f'Browser weekly report {kind}')
    if not created:
        existing = FactoryWork.objects.filter(case=case).first()
        if existing:
            return {'case':str(case.pk),'work':existing.pk}
        if case.evidence.exists() or Grant.objects.filter(case=case).exists():
            raise RuntimeError('Inspect existing setup before reusing this fixture')
    original = users.objects.create_user
    with transaction.atomic():
        Grant.objects.bulk_create([Grant(case=case,user=actor,action=action) for action in dict.fromkeys(ACTIONS)])
        entry = FactoryReportingTests()
        with (
            patch.object(document_helpers,'setup_case',return_value=(actor,case)),
            patch.object(users.objects,'create_user',side_effect=lambda username: original(f'browser-weekly-{kind}-{username}')),
        ):
            entry.setUp()
    if kind == 'recovery':
        _, receipt = entry.uncertain_publication()
        return {'case':str(case.pk),'work':entry.work.pk,'receipt':receipt.pk}
    entry.start_work()
    entry.advance()
    return {'case':str(case.pk),'work':entry.work.pk}


for key, seed in [('mailbox',mailbox),('weekly-review',lambda: weekly('review')),('weekly-recovery',lambda: weekly('recovery'))]:
    try:
        print('PSL_MAILBOX_FIXTURE='+json.dumps({'key':key,**seed()}),flush=True)
    except Exception as exc:
        print('PSL_MAILBOX_FIXTURE_ERROR='+json.dumps({'key':key,'type':type(exc).__name__,'reason':str(exc)[:200]}),flush=True)

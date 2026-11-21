"""A separate synthetic issued invoice and existing allocation for a bank payment walkthrough."""
import json
import os
from datetime import timedelta
from decimal import Decimal
from io import BytesIO
from unittest.mock import patch
from uuid import NAMESPACE_URL, uuid5

from django.contrib.auth import get_user_model
from django.db import connection, transaction
from django.urls import reverse
from django.utils import timezone
from reportlab.pdfgen.canvas import Canvas

from apps.core.models import Audit, Case
from apps.core.services import add_evidence, event
from apps.finance import cash, invoice_delivery, invoices
from apps.finance.bank_receipt_capture import ALLOCATION_POLICY, SOURCE_POLICY, VERIFIER_POLICY
from apps.finance.models import CashReceipt, CashVerification, InvoiceIssue, InvoiceJob, InvoiceDelivery
from apps.identity.actions import ACTIONS
from apps.identity.models import Grant
from apps.policy.services import active_component, reference_values, register_reference
from tests import settlement_helpers as settlement
from tests.billing_helpers import policy
from tests.helpers import activate, rev
from tests.obligation_helpers import identified
from tests.railway_batch_walkthrough_seed import PREVIEW_PROJECT


GUARD = 'PSL_BANK_RECEIPT_WALKTHROUGH_FIXTURE'
TENANT = 'design-bank-receipt-walkthrough'
CASE_ID = uuid5(NAMESPACE_URL, TENANT)
TITLE = 'SAMPLE bank payment and partial allocation'
OWNER = 'sample-bank-receipt-internal-issuer'
TRIAL = 'psl-agent-trial'
MARKER = 'sample.bank_receipt_walkthrough_prepared'
INVOICE = 'SAMPLE-RECEIVED-PAYMENT-INVOICE'
BANK = 'synthetic-bank'
PRIOR_TRANSFER = 'SAMPLE-PREVIOUS-BANK-TRANSFER'
TRANSFER = 'SAMPLE-NEW-BANK-TRANSFER'
LOCATORS = {'report': 'sample-bank-statement-page-12', 'verification': 'sample-bank-confirmation-9042'}
FILENAMES = {'report': 'SAMPLE-BANK-STATEMENT-PAGE-12.pdf', 'verification': 'SAMPLE-BANK-CONFIRMATION-9042.pdf'}
FACE = Decimal('32.25')
PRIOR = Decimal('5.00')
PAYMENT = Decimal('12.50')
REMAINING = FACE - PRIOR - PAYMENT
REASON = 'Apply this separately verified synthetic transfer to the exact sample invoice.'
TRIAL_ACTIONS = {
    'case.read', 'finance.read', 'evidence.add', 'finance.cash.record', 'finance.cash.verify',
    'finance.cash.assign', 'finance.cash.allocate', 'finance.short_payment.read',
}


def pdf_bytes(facts, kind):
    """Fictional supplied proof with the exact same bank facts and separate statement provenance."""
    label = {'report': 'Bank statement extract', 'verification': 'Separate bank confirmation'}[kind]
    target = BytesIO()
    document = Canvas(target, pagesize=(595, 380), invariant=True)
    document.setTitle(f'Synthetic {label}')
    document.setFont('Helvetica-Bold', 20)
    document.drawString(42, 326, label)
    document.setFont('Helvetica', 11)
    lines = [
        'Synthetic test data. No actual bank transaction.',
        f"Statement reference  {LOCATORS[kind]}",
        f"Bank source  {facts['source']}",
        f"Bank transaction reference  {facts['transaction_ref']}",
        f"Received from  {facts['customer']}",
        f"Amount received  {facts['currency']} {Decimal(facts['amount']):.2f}",
        f"Date and time in the bank  {facts['received_at']}",
        'Amount basis  Gross including tax',
    ]
    for number, line in enumerate(lines):
        document.drawString(42, 286 - number * 25, line)
    document.showPage()
    document.save()
    return target.getvalue()


def setup(case, owner, trial):
    for actor, actions in ((owner, set(ACTIONS)), (trial, TRIAL_ACTIONS)):
        Grant.objects.bulk_create(Grant(case=case, user=actor, action=action) for action in sorted(actions))
    with patch.object(settlement, 'setup_case', return_value=(owner, case)):
        _, _, coverage, preparation, proof = settlement.fixture()
    rule_evidence = add_evidence(owner, case.pk, 'policy_decision',
        'Synthetic walkthrough authority for this invoice and test bank only.', 'synthetic:bank-receipt-walkthrough')
    role = register_reference(owner, case.pk, 'sample-bank-trial-finance', 'schema:psl/role-assignment/v1',
                              {'role': 'Finance', 'user_id': trial.pk}, rule_evidence.pk)
    activate(owner, case, 'D05.role_principal_assignments', ['settlement-finance', role.ref], rule_evidence)
    current_source = reference_values(active_component(SOURCE_POLICY, case))[0]
    source_policy = policy(owner, case, SOURCE_POLICY, {**current_source, 'require_independent_evidence': True})

    invoice = settlement.draft(owner, case, preparation, INVOICE)
    identified(owner, case, invoice)
    settlement.approve(owner, case, invoice, proof)
    job = invoices.reserve(owner, case.pk, invoice.pk, 'issue', 'Finance', rev(case))
    if not invoice_delivery.run_once(case_id=case.pk, job_id=job.pk):
        raise RuntimeError('The exact internal synthetic invoice must be confirmed before recording cash.')
    issue = InvoiceIssue.objects.get(invoice=invoice, job=job)
    at = timezone.localtime(timezone.now() - timedelta(hours=4)).replace(second=0, microsecond=0)
    facts = {'source': BANK, 'customer': coverage.customer, 'transaction_ref': TRANSFER,
             'amount': str(PAYMENT.normalize()), 'currency': 'NGN',
             'amount_basis': invoice.amount_basis, 'received_at': at.isoformat()}
    prior = {**facts, 'transaction_ref': PRIOR_TRANSFER, 'amount': str(PRIOR),
             'received_at': (at - timedelta(days=1)).isoformat()}
    prior_report = add_evidence(owner, case.pk, 'cash_report', json.dumps(prior), 'synthetic:earlier-report')
    receipt = cash.report(owner, case.pk, prior_report.pk, rev(case))
    prior_check = add_evidence(owner, case.pk, 'cash_verification', json.dumps(prior), 'synthetic:earlier-bank-confirmation')
    lot = cash.verify(owner, case.pk, receipt.pk, 'Finance', prior_check.pk, rev(case))
    assignment = settlement.assign(owner, case, receipt, coverage, proof)
    allocation = settlement.allocate(owner, case, lot, issue, str(PRIOR), proof, key='sample-earlier-allocation')
    if invoice.amount != FACE or cash.open_amount(issue) != FACE - PRIOR:
        raise RuntimeError('Preserve the exact synthetic invoice and prior allocation totals.')
    return event(owner, case, MARKER, trial=trial.pk, issue=issue.pk, job=job.pk, invoice=invoice.pk,
                 prior_receipt=receipt.pk, prior_lot=lot.pk, prior_allocation=allocation.pk,
                 prior_assignment=assignment.pk, source_policy=source_policy.pk, facts=facts)


@transaction.atomic
def prepare():
    if os.getenv(GUARD) != '1':
        raise RuntimeError('Use the explicit isolated bank payment walkthrough guard.')
    trial = get_user_model().objects.get(username=TRIAL, is_active=True, is_staff=False, is_superuser=False)
    attrs = {'tenant': TENANT, 'title': TITLE, 'kind': 'project', 'synthetic': True}
    if Case.objects.filter(tenant=TENANT).exclude(pk=CASE_ID).exists():
        raise RuntimeError('Preserve the single exact synthetic bank payment workspace.')
    case, created = Case.objects.get_or_create(pk=CASE_ID, defaults=attrs)
    case = Case.objects.select_for_update().get(pk=case.pk)
    if any(getattr(case, key) != value for key, value in attrs.items()):
        raise RuntimeError('The bank payment walkthrough requires its named synthetic workspace.')
    if created:
        owner = get_user_model().objects.create_user(username=OWNER)
        marker = setup(case, owner, trial)
    else:
        marker = Audit.objects.select_related('actor').get(case=case, action=MARKER, actor__username=OWNER)
    data, owner = marker.data, marker.actor
    if (data['trial'] != trial.pk or not owner.is_active or owner.has_usable_password()
            or owner.is_staff or owner.is_superuser or Grant.objects.filter(user=owner).exclude(case=case).exists()
            or set(Grant.objects.filter(case=case, user=trial, active=True).values_list('action', flat=True)) != TRIAL_ACTIONS):
        raise RuntimeError('Preserve the exact separate issuer and case-local Trial authorities.')
    source = active_component(SOURCE_POLICY, case)
    allowance = reference_values(active_component(VERIFIER_POLICY, case))[0]
    matching = reference_values(active_component(ALLOCATION_POLICY, case))[0]
    if (source.pk != data['source_policy'] or not reference_values(source)[0]['require_independent_evidence']
            or not allowance['allow_reporter_verify'] or not matching['allow_verifier_allocation']):
        raise RuntimeError('Preserve the sample’s reviewed separate evidence and human role rules.')
    for component, action in ((VERIFIER_POLICY, 'finance.cash.verify'), (ALLOCATION_POLICY, 'finance.cash.allocate'),
                              (ALLOCATION_POLICY, 'finance.cash.assign')):
        cash.authority_facts(trial, case, component, 'Finance', action)
    issue = InvoiceIssue.objects.get(
        pk=data['issue'], invoice_id=data['invoice'], invoice__case=case, invoice__reference=INVOICE, invoice__actor=owner,
        invoice__amount=FACE, invoice__currency='NGN', job_id=data['job'], job__kind='issue', job__status='confirmed',
    )
    previous = cash.allocations(issue=issue).get(pk=data['prior_allocation'], lot_id=data['prior_lot'],
        lot__receipt_id=data['prior_receipt'], lot__amount=PRIOR, lot__actor=owner, amount=PRIOR, actor=owner)
    if cash.assigned(previous.lot.receipt).pk != data['prior_assignment']:
        raise RuntimeError('Preserve the earlier verified payment and contract assignment.')
    supplied = CashReceipt.objects.filter(case=case, transaction_ref=TRANSFER).first()
    if supplied and CashVerification.objects.filter(receipt=supplied).exclude(actor=trial, amount=PAYMENT).exists():
        raise RuntimeError('Preserve the exact Trial verification of the separately supplied bank payment.')
    new_allocations = cash.allocations(issue=issue).exclude(pk=previous.pk)
    if (InvoiceJob.objects.filter(invoice__case=case).exclude(pk=issue.job_id).exists()
            or InvoiceDelivery.objects.filter(invoice__case=case).exists()
            or CashReceipt.objects.filter(case=case).exclude(transaction_ref__in=[TRANSFER, PRIOR_TRANSFER]).exists()
            or supplied and (supplied.actor_id != trial.pk or supplied.payload != data['facts'])
            or new_allocations.exclude(lot__receipt=supplied, actor=trial, amount=PAYMENT).exists()):
        raise RuntimeError('The fixture may only record and apply the one exact separate synthetic bank payment.')
    new = new_allocations.first()
    if new and (new_allocations.count() != 1 or cash.open_amount(issue) != REMAINING):
        raise RuntimeError('The exact prior and new allocations must preserve the expected remaining balance.')
    return {**data, 'case': str(case.pk), 'preserved': not created,
            'reference': INVOICE, 'reported': supplied.pk if supplied else None, 'applied': new.pk if new else None,
            'record_path': reverse('finance_record_payment', args=[case.pk, issue.pk]),
            'locators': LOCATORS, 'filenames': FILENAMES,
            'received_local': data['facts']['received_at'][:16], 'allocation_amount': str(PAYMENT), 'reason': REASON,
            'balance': str(cash.open_amount(issue)), 'expected_remaining': str(REMAINING)}


def run():
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
    print(GUARD + '=' + json.dumps(prepare()), flush=True)

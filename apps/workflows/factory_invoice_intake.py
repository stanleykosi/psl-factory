"""Explicit native preparation continuation in the existing invoice factory envelope.

This route never selects a preparation, recalculates a correction, or supplies PMO
completion. Finance retains all calculation, review, issue and receipt authority.
"""
from datetime import date
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from apps.core.services import lock_case, event
from apps.identity.services import require
from apps.finance import billing, invoices
from apps.finance.models import BillingPreparation, Invoice, InvoiceIssue, InvoiceJob
from apps.finance.fixed_charge import preparation_access
from .models import FactoryWork

MODE = 'existing-preparation/v1'


def bound(work):
    return work.definition == 'pmo-finance/v1' and work.request.get('mode') == MODE


def pins(prep):
    continuation=None
    if prep.kind=='fixed_contract':
        from apps.finance.preparation_continuation import latest
        current=latest(prep.fixed_charge.request)
        continuation=current.pk if current else None
    return {'id': prep.pk, 'operation_key': prep.operation_key, 'kind': prep.kind,
            'actor': prep.actor_id, 'snapshot': prep.snapshot, 'result': prep.result, 'continuation':continuation}


def selection(work):
    successor = work.preparation_bindings.order_by('-sequence').first()
    return successor.payload if successor else work.request


def check(work, actor):
    prep = work.preparation
    if not prep or pins(prep) != selection(work)['preparation'] or invoices.obligation(prep) != work.business_key:
        raise ValidationError('Exact intake preparation lineage changed; source-owned correction required')
    preparation_access(actor, prep)
    billing.ensure_current(prep)
    return prep


@transaction.atomic
def start(actor, case_id, key, preparation_id, reference, due_date, expected, invoice_id=None):
    from .factory import access
    case = lock_case(actor, case_id, 'factory.start', expected)
    access(actor, case, 'factory.start')
    if not isinstance(key, str) or not 1 <= len(key) <= 100 or not key.isascii():
        raise ValidationError('Bounded work identity required')
    from adapters.billing_usage import KEY
    if not isinstance(reference, str) or not KEY.fullmatch(reference):
        raise ValidationError('Bounded invoice reference required')
    if due_date is not None and type(due_date) is not date:
        raise ValidationError('Explicit invoice due date required')
    prep = BillingPreparation.objects.filter(case=case, pk=preparation_id).select_related('coverage', 'usage', 'fixed_charge').first()
    if not prep or not (prep.kind == 'fixed_contract' or prep.kind == 'usage' and prep.usage_id and prep.usage.collective_acceptance_id):
        raise ValidationError('Choose an exact native collective-usage or fixed-contract preparation')
    preparation_access(actor, prep)
    business_key = invoices.obligation(prep)
    payload = {'mode': MODE, 'coverage': prep.coverage_id, 'preparation': pins(prep),
               'reference': reference, 'due_date': due_date.isoformat() if due_date else None, 'existing_invoice': invoice_id}
    sha = billing.digest(payload)
    old = FactoryWork.objects.filter(case=case).filter(Q(key=key) | Q(definition='pmo-finance/v1', business_key=business_key)).first()
    if old:
        if old.request_hash != sha:
            raise ValidationError('IDEMPOTENCY_CONFLICT: this obligation already has factory work; preserve its history and use explicit native correction/recovery')
        # Current read/start permission permits discovery, not ownership reassignment.
        return old
    billing.ensure_current(prep)
    invoice = None
    candidates = Invoice.objects.filter(case=case, obligation_key=business_key)
    if invoice_id is not None:
        invoice = candidates.filter(pk=invoice_id, preparation=prep, reference=reference, due_date=due_date).first()
        if not invoice: raise ValidationError('Exact same-preparation invoice, reference and due terms required')
        if candidates.filter(pk__gt=invoice.pk).exists(): raise ValidationError('A newer native invoice exists; select its exact preparation and identity')
        invoices.current(invoice)
    elif candidates.exists():
        raise ValidationError('An invoice already exists for this obligation; explicitly select it instead of creating another draft')
    if InvoiceIssue.objects.filter(obligation_key=business_key).exclude(invoice=invoice).exists():
        raise ValidationError('Another issued invoice owns this obligation; use its native correction workflow')
    if InvoiceJob.objects.filter(invoice__obligation_key=business_key, status__in=['pending','leased','unknown','held']).exists():
        raise ValidationError('Reconcile existing native invoice work before attaching its preparation to the factory')
    work = FactoryWork.objects.create(case=case, actor=actor, key=key, business_key=business_key,
        request=payload, request_hash=sha, preparation=prep, invoice=invoice)
    event(actor, case, 'factory.started', work=work.pk, definition=work.definition,
          preparation=prep.pk, original_preparer=prep.actor_id, existing_invoice=invoice_id)
    return work


def draft(work):
    prep = check(work, work.execution_actor)
    require(work.execution_actor, work.case, 'finance.invoice.draft')
    if work.invoice_id:
        invoices.current(work.invoice)
        return {'preparation': prep.pk, 'invoice': work.invoice_id, 'reused': True}
    prior_ids=[b.payload.get('previous_invoice') for b in work.preparation_bindings.all()]
    if Invoice.objects.filter(case=work.case, obligation_key=work.business_key).exclude(pk__in=[i for i in prior_ids if i]).exists():
        raise ValidationError('Native invoice appeared after intake; explicit reconciliation required, not another draft')
    chosen = selection(work)
    due = date.fromisoformat(chosen['due_date']) if chosen['due_date'] else None
    work.invoice = invoices.draft(work.execution_actor, work.case_id, prep.pk, chosen['reference'], due, work.case.revision)
    return {'preparation': prep.pk, 'invoice': work.invoice.pk, 'amount': work.invoice.payload['amount']}


@transaction.atomic
def replace(actor, work_id, preparation_id, reference, due_date, expected, reason):
    """Explicit corrected source, same obligation, before any unresolved/issued effect."""
    from .factory import access
    from .factory_execution import require_control
    from .models import FactoryInvoicePreparationBinding
    from django.utils import timezone
    work = FactoryWork.objects.select_for_update().get(pk=work_id)
    access(actor, work.case, 'factory.manage'); require_control(actor, work)
    lock_case(actor, work.case_id, 'factory.manage')
    if not bound(work) or work.revision != expected:
        raise ValidationError('Exact explicit preparation work and current revision required')
    if work.cancel_requested or work.status in ['verified', 'cancelled', 'followup_needed']:
        raise ValidationError('Stopped work cannot replace its preparation')
    if work.lease_until and work.lease_until > timezone.now():
        raise ValidationError('Current worker still owns this work')
    if InvoiceIssue.objects.filter(obligation_key=work.business_key).exists() or InvoiceJob.objects.filter(
            invoice__obligation_key=work.business_key, status__in=['pending','leased','unknown','held']).exists():
        raise ValidationError('Reconcile native effects; issued obligations require their native correction workflow')
    if not isinstance(reason,str) or not reason.strip() or len(reason)>2000:
        raise ValidationError('Explain the explicit source correction')
    from adapters.billing_usage import KEY
    if not isinstance(reference,str) or not KEY.fullmatch(reference) or due_date is not None and type(due_date) is not date:
        raise ValidationError('Exact reference and due date required')
    prep = BillingPreparation.objects.filter(case=work.case,pk=preparation_id).first()
    if not prep or invoices.obligation(prep) != work.business_key or pins(prep)==selection(work)['preparation']:
        raise ValidationError('Select an exact different preparation for this same obligation')
    preparation_access(actor,prep);billing.ensure_current(prep)
    if prep.kind != work.preparation.kind:
        raise ValidationError('Preparation kind cannot change')
    if prep.kind=='usage':
        # Native SQL supplies the accepted correction ancestry, not timestamp order.
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute('SELECT psl_usage_ancestor(%s,%s)', [work.preparation.usage.collective_acceptance.source_id,prep.usage.collective_acceptance.source_id])
            if cursor.fetchone()[0] is not True:raise ValidationError('Accepted collective usage successor ancestry required')
    elif prep.fixed_charge.request_id != work.preparation.fixed_charge.request_id:
        raise ValidationError('Exact fixed-contract preparation request ancestry required')
    same_preparation=prep.pk==work.preparation_id
    if same_preparation and (reference!=selection(work)['reference'] or (due_date.isoformat() if due_date else None)!=selection(work)['due_date']):
        raise ValidationError('Continuation-only selection retains original invoice reference and due terms')
    if not same_preparation and Invoice.objects.filter(case=work.case,preparation=prep).exists():
        raise ValidationError('A native successor invoice exists; explicit operator reconciliation required')
    previous=work.preparation_bindings.order_by('-sequence').first()
    payload=dict(mode=MODE,coverage=prep.coverage_id,preparation=pins(prep),reference=reference,
                 due_date=due_date.isoformat() if due_date else None,existing_invoice=selection(work).get('existing_invoice') if same_preparation else None,
                 previous_invoice=work.invoice_id)
    binding=FactoryInvoicePreparationBinding.objects.create(work=work,previous=previous,preparation=prep,
        sequence=previous.sequence+1 if previous else 1,actor=actor,payload=payload,reason=reason.strip())
    work.preparation=prep
    if not same_preparation:work.invoice=None
    work.status='ready';work.finding='';work.revision+=1;work.fence+=1
    work.lease_until=None;work.save()
    event(actor,work.case,'factory.invoice_preparation_replaced',work=work.pk,binding=binding.pk,
          original_preparation=work.request['preparation']['id'],preparation=prep.pk,budget_used=work.budget_used)
    return binding

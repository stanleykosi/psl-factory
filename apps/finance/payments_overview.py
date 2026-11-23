"""Current authorized payment records with explicit gaps in the bank evidence."""
from decimal import Decimal, localcontext
from urllib.parse import urlencode

from django.contrib.auth.decorators import login_required
from django.core import signing
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Exists, OuterRef, Q
from django.http import Http404
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_safe

from apps.core.read_budget import ReadBudget, ReadLimit, limit_queries
from apps.core.workbench import granted
from apps.identity.services import active_case_grants
from apps.policy.services import reference_values, resolve

from .fixed_charge import preparation_access
from .models import BillingPreparation, Invoice, InvoiceIssue, InvoiceJob, PaymentReminderDraft
from .project_money import balance


STATES = (
    ('', 'Any state'), ('issued', 'Issued invoices'), ('part-paid', 'Part paid'), ('overdue', 'Overdue'),
    ('paid', 'Paid'), ('unknown', 'Awaiting verification'),
)
LABELS = {'issued': 'Issued', 'part-paid': 'Part paid', 'overdue': 'Overdue', 'paid': 'Paid',
          'voided': 'Voided', 'unknown': 'Awaiting verification'}
ROW_LIMIT = 25
SCAN_LIMIT = 75
CURSOR_SALT = 'psl.finance.payments/v1'


def invoice_rows(cases, search, before):
    known_issue = InvoiceIssue.objects.filter(obligation_key=OuterRef('obligation_key'))
    uncertain_issue = InvoiceJob.objects.filter(invoice_id=OuterRef('pk'), kind='issue', status__in=['leased', 'unknown'])
    uncertain_correction = InvoiceJob.objects.filter(invoice_id=OuterRef('pk'), kind='adjust',
                                                      status__in=['leased', 'unknown'])
    rows = Invoice.objects.filter(case__in=cases).alias(known_issue=Exists(known_issue)).annotate(
        issue_unverified=Exists(uncertain_issue), correction_unverified=Exists(uncertain_correction),
    ).filter(Q(invoiceissue__isnull=False) | Q(known_issue=False, issue_unverified=True)).select_related(
        'case', 'invoiceissue', 'preparation__coverage',
    ).only('id', 'reference', 'due_date', 'amount', 'currency', 'amount_basis', 'case__title', 'case__kind',
           'case__tenant', 'case__synthetic', 'case__revision', 'invoiceissue__id', 'preparation__coverage__customer',
           'preparation__coverage__contract')
    if search:
        rows = rows.filter(Q(reference__icontains=search) | Q(case__title__icontains=search)
                           | Q(preparation__coverage__customer__icontains=search)
                           | Q(preparation__coverage__contract__icontains=search))
    if before is not None:
        rows = rows.filter(pk__lt=before)
    return rows.order_by('-pk')


def case_scope(actor, case, budget):
    """Use the same protected-charge boundary as the linked settlement and reminder screens."""
    fixed = budget.take(BillingPreparation.objects.filter(case=case, kind='fixed_contract').only(
        'id', 'case_id', 'kind', 'fixed_charge_id').order_by('pk'), 50)
    for preparation in fixed:
        preparation_access(actor, preparation)
    actions = {action for _, action in active_case_grants(actor, [case.pk], actions={
        'case.read', 'finance.read', 'finance.reminder.read', 'finance.cash.record', 'evidence.add',
        'finance.cash.verify','finance.cash.allocate',
    })}
    if not {'case.read', 'finance.read'}.issubset(actions):
        raise PermissionDenied
    method = resolve('D14.allocation_rule_ref', case, budget=budget)
    ageing = method.status == 'ACTIVE' and reference_values(method.configuration, budget=budget)[0]['overdue_definition'] == 'due_date_before_as_of'
    settlement = reverse('finance_settlement', args=[case.pk])
    return {'reminders': 'finance.reminder.read' in actions, 'ageing': ageing, 'settlement': settlement,
            'record_payment': {'finance.cash.record','evidence.add'}<=actions,
            'review_payment': bool({'finance.cash.verify','finance.cash.allocate'}.intersection(actions))}


def observation(invoice, scope, as_of, budget):
    issue = getattr(invoice, 'invoiceissue', None)
    coverage = invoice.preparation.coverage
    row = {'invoice_id': invoice.pk, 'issue_id': issue.pk if issue else None, 'case_id': invoice.case_id,
           'reference': invoice.reference, 'workspace': invoice.case.title, 'customer': coverage.customer,
           'contract': coverage.contract, 'currency': invoice.currency, 'basis': invoice.amount_basis,
           'records': scope['settlement'] + f'#invoice-{invoice.pk}', 'record_payment': None,
           'age_days': None, 'paid': None, 'owed': None, 'face': None}
    if not issue:
        return {**row, 'key': 'unknown', 'reason': 'The invoice issue is still being verified.'}
    if scope['record_payment']:
        row['record_payment']=reverse('finance_record_payment',args=[invoice.case_id,issue.pk])
    elif scope['review_payment']:
        row['review_payment']=reverse('finance_record_payment',args=[invoice.case_id,issue.pk])
    try:
        paid, owed, applied_changes, _ = balance(invoice, budget, include_sources=False)
    except ReadLimit:
        return {**row, 'key': 'unknown', 'issued': True, 'reason': 'Open the invoice records to check this balance.'}
    voided = any(change.correction.kind == 'void' for change in applied_changes)
    face = paid + owed if owed is not None else None
    age_days = None
    if invoice.correction_unverified or owed is None:
        reason = 'A correction is still being verified.' if invoice.correction_unverified else 'The recorded allocations need reconciliation.'
        return {**row, 'key': 'unknown', 'issued': True, 'reason': reason, 'paid': paid}
    if scope['ageing'] and invoice.due_date is not None:
        age_days = max((as_of - invoice.due_date).days, 0) if owed > 0 else 0
    key = 'voided' if voided else 'paid' if owed == 0 else 'part-paid' if paid > 0 else 'overdue' if age_days else 'issued'
    reminder = reverse('design_payment_reminder', args=[invoice.case_id, issue.pk]) if scope['reminders'] and owed > 0 else None
    draft = PaymentReminderDraft.objects.filter(issue=issue).order_by('-number').values_list(
        'set_aside__pk', 'dispatch__receipt__pk').first() if reminder else None
    has_draft = draft == (None, None)
    return {**row, 'key': key, 'issued': True, 'age_days': age_days, 'paid': paid, 'owed': owed,
            'face': face, 'reminder': reminder, 'has_draft': has_draft}


def matches(row, state):
    if state == 'issued':
        return row.get('issued', False)
    if state == 'overdue':
        return bool(row.get('age_days'))
    return not state or row['key'] == state


def recorded_totals(rows):
    groups = {}
    for row in rows:
        key = row['currency'], row['basis']
        group = groups.setdefault(key, {'currency': key[0], 'basis': key[1], 'owed': Decimal(0), 'overdue': Decimal(0),
                                        'known_owed': Decimal(0), 'unknown_owed_count': 0})
        if row['owed'] is None:
            group['unknown_owed_count'] += 1
            group['owed'] = None
        else:
            group['known_owed'] += row['owed']
            if group['owed'] is not None:
                group['owed'] += row['owed']
        if row['age_days'] is None or row['owed'] is None:
            group['overdue'] = None
        elif group['overdue'] is not None and row['age_days']:
            group['overdue'] += row['owed']
    return groups.values()


def page(actor, cases, search, state, before, as_of):
    budget = ReadBudget()
    rows, scopes = [], {}
    seen = None
    try:
        with limit_queries(500):
            candidates = list(invoice_rows(cases, search, before)[:SCAN_LIMIT + 1])
            more = False
            with localcontext() as context:
                context.prec = 512
                for invoice in candidates[:SCAN_LIMIT]:
                    if invoice.case_id not in scopes:
                        try:
                            scopes[invoice.case_id] = case_scope(actor, invoice.case, budget)
                        except (PermissionDenied, ValidationError, ReadLimit):
                            scopes[invoice.case_id] = None
                    scope = scopes[invoice.case_id]
                    if not scope:
                        continue
                    row = observation(invoice, scope, as_of, budget)
                    if matches(row, state):
                        if len(rows) == ROW_LIMIT:
                            more = True
                            break
                        row['state'] = LABELS[row['key']]
                        rows.append(row)
                    seen = invoice.pk
                more = more or len(candidates) > SCAN_LIMIT
                return rows, list(recorded_totals(rows)), seen if more else None, more and seen is None
    except ReadLimit:
        return rows, [], seen, True


def read_page(actor, search, state, token):
    cases = granted(actor, ['finance.read'])
    if not cases.exists():
        raise PermissionDenied
    filters = {'q': search, 'state': state}
    before = None
    if token:
        try:
            cursor = signing.loads(token, salt=CURSOR_SALT, max_age=3600)
            before = cursor['before']
            if (cursor['actor'] != actor.pk or cursor['filters'] != filters or type(before) is not int
                    or not 0 < before <= 9223372036854775807):
                raise ValueError
        except (signing.BadSignature, KeyError, ValueError, TypeError) as error:
            raise Http404('Choose an available payments page.') from error
    as_of = timezone.localdate()
    rows, totals, ending, limited = page(actor, cases, search, state, before, as_of)
    key = (signing.dumps({'actor': actor.pk, 'filters': filters, 'before': ending}, salt=CURSOR_SALT)
           if ending is not None else None)
    return rows, totals, key, limited, as_of


@login_required
@require_safe
@never_cache
def show(request):
    search = request.GET.get('q', '').strip()[:100]
    submitted_state = request.GET.get('state', '')
    state = submitted_state if submitted_state in dict(STATES) else ''
    rows, totals, key, limited, as_of = read_page(request.user, search, state, request.GET.get('page'))
    next_url = '?' + urlencode({'q': search, 'state': state, 'page': key}) if key else None
    return render(request, 'design/payments_overview.html', {
        'rows': rows, 'totals': totals, 'next_url': next_url, 'limited': limited,
        'as_of': as_of, 'search': search, 'states': STATES, 'state': state,
    })

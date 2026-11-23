"""Review close inputs and recorded receivables at each permitted workspace."""
from calendar import monthrange
from datetime import date, datetime, time
from decimal import Decimal, localcontext

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import F, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST, require_safe

from apps.core.read_budget import ReadBudget, ReadLimit, limit_queries
from apps.core.presentation import workspace_name
from apps.core.services import lock_case
from apps.core.workbench import granted
from apps.identity.services import active_case_grants, require
from apps.workflows.factory_definitions import DEFINITIONS
from apps.workflows.models import FactoryWork

from .cash import lot_payload
from .fixed_charge import case_access, preparation_access
from .models import BillingPreparation, CashVerification, FinancePeriod, ReceivableSnapshot
from .performance import period_acceptance
from .statement_ppe import recipient_access
from . import receivables


CLOSE_STATIONS = (
    ('finance_performance', 'Monthly figures and restatements', ()),
    ('finance_analysis', 'Accounting preparation and financial reports', ()),
    ('finance_corrections', 'Invoice and cash corrections', ()),
    ('finance_forecast', 'Cash forecasts and actuals', ()),
    ('finance_schedules', 'Income adjustments and schedules', ('schedules.read',)),
    ('ppe', 'Assets and depreciation', ('ppe.read',)),
    ('recognition', 'Project revenue recognition', ('recognition.read',)),
    ('ledger', 'Transaction evidence', ('ledger.read', 'ledger.private.read')),
    ('payroll', 'Restricted payroll and staff costs', ('payroll.read',)),
    ('bu', 'Business unit attribution', ('bu.read',)),
)
FINANCE_WORK = {
    'finance-accounts/v1': 'Management accounts',
    'finance-schedules/v1': 'Income detail and schedules',
    'finance-ppe/v1': 'Fixed asset schedule',
    'finance-forecast/v1': 'Cash forecast',
    'finance-bu/v1': 'Business-unit totals',
    'finance-payroll/v1': 'Payroll',
    'finance-ledger/v1': 'Transaction evidence',
    'pmo-finance/v1': 'Invoices and delivery',
}
WORK_LIMIT = 25
WORK_CHECK_LIMIT = 50
WORK_STATES = {
    'verified': ('done', 'Verified'),
    'cancelled': ('stopped', 'Cancelled'),
    'blocked': ('waiting', 'Action needed'),
    'owner_needed': ('waiting', 'Owner needed'),
    'configuration_needed': ('waiting', 'Rules needed'),
    'waiting_effect': ('waiting', 'Receipt needs reconciliation'),
    'followup_needed': ('waiting', 'Finance follow-up needed'),
    'waiting': ('waiting', 'Waiting'),
    'ready': ('waiting', 'Ready to continue'),
}


class MonthForm(forms.Form):
    month = forms.RegexField(r'\A[1-9][0-9]{3}-(?:0[1-9]|1[0-2])\Z', label='Reporting month', max_length=7,
                             widget=forms.DateInput(attrs={'type': 'month'}))


def selection(request):
    today = timezone.localdate()
    form = MonthForm({'month': request.GET.get('month')} if 'month' in request.GET else None,
                     initial={'month': today.strftime('%Y-%m')})
    month = form.initial['month']
    if form.is_bound:
        month = form.cleaned_data['month'] if form.is_valid() else None
    return form, month


def reviewed_periods(actor, case, month):
    periods = []
    current = FinancePeriod.objects.filter(case=case, manifest__period=month, replacement__isnull=True).select_related(
        'case', 'actor', 'run__actor', 'run__source', 'restatement',
    ).order_by('-pk')[:12]
    for period in current:
        try:
            recipient_access(period.run, [actor.pk])
        except (PermissionDenied, ValidationError):
            continue
        values = []
        try:
            period_acceptance(period)
        except (PermissionDenied, ValidationError):
            status = 'Needs a fresh review'
        else:
            status = 'Reviewed figures'
            company = period.manifest['result']['company']
            contracts = period.manifest['metric_contracts']
            values = [{'label': contracts.get(key, {}).get('label') or key, 'value': row['value'], 'unit': row['unit']}
                      for key, row in company.items()]
        periods.append({'entity': period.manifest['entity'], 'currency': period.manifest['currency'],
                        'at': period.created_at, 'status': status, 'values': values})
    return periods


def show(request, case, tabs):
    require(request.user, case, 'finance.read')
    form, month = selection(request)
    close = workspace_close(request.user, case, month) if month else None
    overview = month_overview(request.user, [close], month) if close else None
    return render(request, 'design/month_end.html', {
        'case': case, 'tab': 'month-end', 'tabs': tabs, 'periods': close['periods'] if close else [],
        'close': close,
        'form': form, 'month': month, 'overview': overview,
    })


def cash_received_snapshot(actor, case, month):
    require(actor, case, 'finance.read')
    budget = ReadBudget()
    with limit_queries(100):
        budget.take(BillingPreparation.objects.filter(case=case, kind='fixed_contract').only('pk'), 50)
        case_access(actor, case)
        verified = CashVerification.objects.filter(receipt__case=case, cashreversal__isnull=True).select_related(
            'receipt', 'successor', 'reported_amount')
        lots = budget.take(verified.only('amount', 'created_at', 'receipt__payload', 'successor__payload',
                                         'reported_amount__payload').order_by('pk'), 300)
    groups = {}
    last_received_at, last_verified_at = None, None
    with localcontext() as context:
        context.prec = 512
        for lot in lots:
            fact = lot_payload(lot)
            received = parse_datetime(fact['received_at'])
            if received and timezone.is_aware(received) and timezone.localtime(received).strftime('%Y-%m') == month:
                key = (fact['currency'], fact['amount_basis'])
                groups[key] = groups.get(key, Decimal(0)) + lot.amount
                last_received_at = max(last_received_at, received) if last_received_at else received
                last_verified_at = max(last_verified_at, lot.created_at) if last_verified_at else lot.created_at
    return [(currency, basis, groups[currency, basis]) for currency, basis in sorted(groups)], last_received_at, last_verified_at


def cash_received(actor, case, month):
    return cash_received_snapshot(actor, case, month)[0]


def receivable_cutoff(month, today):
    start = date.fromisoformat(month + '-01')
    if start > today:
        return None
    last = start.replace(day=monthrange(start.year, start.month)[1])
    return min(last, today)


def captured_receivables(actor, case, cutoff):
    """Use an actual capture on the requested date, with a separately labelled earlier fallback."""
    require(actor, case, 'finance.read')
    budget = ReadBudget()
    with limit_queries(120):
        budget.take(BillingPreparation.objects.filter(case=case, kind='fixed_contract').only('pk'), 50)
        case_access(actor, case)
        if cutoff is None:
            return {'status': 'Future month'}
        start = cutoff.replace(day=1)
        row = ReceivableSnapshot.objects.filter(case=case, as_of__range=(start, cutoff)).defer(
            'manifest', 'result').order_by('-as_of', '-pk').first()
        if not row:
            return {'status': 'No receivables capture in this month', 'cutoff': cutoff}
        manifest = budget.load(row, 'manifest')
        result = budget.load(row, 'result')
        if manifest.get('as_of') != row.as_of.isoformat() or receivables.digest({'manifest': manifest, 'result': result}) != row.sha256:
            raise ValidationError('The recorded snapshot could not be verified.')
    scope = ('customer', 'contract', 'currency', 'amount_basis', 'receivable', 'unallocated_cash', 'overdue')
    groups = [{field: group.get(field) for field in scope} for group in result['groups'][:12]]
    categories = {
        'Reported cash awaiting verification': 'reported_unverified',
        'Verified cash awaiting matching': 'unmatched_cash',
        'Draft invoices awaiting issuance': 'unbilled_drafts',
        'Uncertain invoice issuance': 'uncertain_issuance',
        'Pending invoice corrections': 'pending_corrections',
        'Uncertain correction deliveries': 'uncertain_corrections',
        'Pending replacement cash records': 'pending_cash_successors',
        'Reconciliation findings': 'findings',
    }
    exceptions = []
    for label, key in categories.items():
        rows = result.get(key)
        if rows is None:
            continue
        count = sum(not entry.get('reversed') for entry in rows) if key == 'unmatched_cash' else len(rows)
        if count:
            exceptions.append((label, count))
    return {'status': 'Captured on the selected date' if row.as_of == cutoff else 'Earlier capture in this month',
            'cutoff': cutoff, 'date': row.as_of, 'recorded': row.created_at, 'pk': row.pk,
            'groups': groups, 'total_groups': len(result['groups']), 'exceptions': exceptions}


def workspace_close(actor, case, month):
    today = timezone.localdate()
    cutoff = receivable_cutoff(month, today)
    grants = {action for _, action in active_case_grants(actor, [case.pk], actions={
        'finance.receivables', *(action for _, _, actions in CLOSE_STATIONS for action in actions),
    })}
    sections = {'case': case, 'periods': reviewed_periods(actor, case, month), 'cash': [],
                'stations': [(reverse(route, args=[case.pk]), label) for route, label, actions in CLOSE_STATIONS
                             if grants.issuperset(actions)]}
    try:
        sections['cash'] = cash_received(actor, case, month)
    except (PermissionDenied, ValidationError, ReadLimit):
        sections['cash_unavailable'] = True
    try:
        sections['receivables'] = captured_receivables(actor, case, cutoff)
    except (PermissionDenied, ValidationError, ReadLimit):
        sections['receivables'] = {'status': 'Receivables coverage is unavailable in this view'}
    else:
        sections['can_capture'] = cutoff == today and 'finance.receivables' in grants
    return sections


def authorized_work_read(actor, item, actions):
    if item.preparation_kind == 'fixed_contract':
        preparation_access(actor, item.preparation)
    if item.definition == 'finance-ledger/v1':
        from apps.workflows.factory_ledger import source
        source(item, actor, False)
    elif item.definition == 'finance-schedules/v1':
        from apps.workflows.factory_schedules import source
        source(item, actor, False)
    elif item.definition == 'finance-ppe/v1':
        from apps.workflows.factory_ppe import source
        source(item, actor, False)
    elif item.definition == 'finance-forecast/v1':
        from apps.workflows.factory_forecast import source
        source(item, actor, False)
    elif item.definition in ('finance-bu/v1', 'finance-payroll/v1'):
        from apps.workflows import factory_bu, factory_payroll

        if item.definition == 'finance-bu/v1':
            service, private, receipt_reader = factory_bu, 'bu.private.read', factory_bu.native.read_report
        else:
            service, private, receipt_reader = factory_payroll, 'payroll.private.read', factory_payroll.native.read_publication
        if private in actions:
            try:
                service.source(item, actor, False)
                return
            except (PermissionDenied, ValidationError):
                pass
        publication = service.publication(item)
        if publication is None:
            raise PermissionDenied('Current source or aggregate access required')
        receipt_reader(actor, publication.pk)


def work_in_month(actor, entries, start, as_of):
    ids = {entry['case'].pk for entry in entries}
    grants = {case_id: set() for case_id in ids}
    for case_id, action in active_case_grants(actor, ids):
        grants[case_id].add(action)
    common = {'case.read', 'factory.read', 'finance.read'}
    scope = Q(pk__in=[])
    for definition in FINANCE_WORK:
        actions = common | {DEFINITIONS[definition]['read']}
        if definition == 'finance-ledger/v1':
            actions.add('ledger.private.read')
        permitted = granted(actor, sorted(actions)).filter(pk__in=ids)
        scope |= Q(definition=definition, case_id__in=permitted.values('pk'))

    last = start.replace(day=monthrange(start.year, start.month)[1])
    window = (timezone.make_aware(datetime.combine(start, time.min)),
              timezone.make_aware(datetime.combine(last, time.max)))
    candidates = FactoryWork.objects.filter(scope, updated_at__range=window).select_related('case').only(
        'case__title', 'case__kind', 'case__synthetic', 'definition', 'status', 'updated_at',
        'cancel_requested', 'lease_until', 'preparation_id', 'source_head_id',
    ).annotate(preparation_kind=F('preparation__kind')).order_by('-updated_at', '-pk')[:WORK_CHECK_LIMIT]
    rows = []
    try:
        with limit_queries(180):
            for item in candidates:
                try:
                    authorized_work_read(actor, item, grants[item.case_id])
                except (PermissionDenied, ValidationError):
                    continue
                state, label = WORK_STATES.get(item.status, ('waiting', 'Check current work'))
                if state == 'waiting':
                    if item.cancel_requested:
                        label = 'Cancellation requested'
                    elif item.lease_until and item.lease_until > as_of:
                        state, label = 'in_progress', 'Processing'
                rows.append({'title': FINANCE_WORK[item.definition], 'workspace_id': str(item.case_id),
                             'workspace': workspace_name(item.case),
                             'state': state, 'label': label, 'at': item.updated_at,
                             'url': reverse('factory_detail', args=[item.pk])})
                if len(rows) == WORK_LIMIT:
                    break
    except ReadLimit:
        pass
    return rows


def cash_in_month(entries):
    # The visible workspace page can contain several organizations. Separate
    # their receipts as well as currencies and amount bases.
    by_workspace = len({entry['case'].tenant for entry in entries}) > 1
    totals = {}
    with localcontext() as context:
        context.prec = 512
        for entry in entries:
            case = entry['case']
            workspace = (str(case.pk), workspace_name(case)) if by_workspace else (None, None)
            for currency, basis, amount in entry['cash']:
                key = (workspace, case.synthetic, currency, basis)
                totals[key] = totals.get(key, Decimal(0)) + amount
    groups = [{'workspace_id': case_id, 'workspace': name, 'sample': sample,
               'currency': currency, 'basis': basis, 'amount': amount}
              for ((case_id, name), sample, currency, basis), amount in totals.items()]
    return {'groups': groups[:12], 'more_groups': len(groups) > 12}


def month_overview(actor, entries, month):
    as_of = timezone.now()
    start = date.fromisoformat(month + '-01')
    work = work_in_month(actor, entries, start, as_of)
    return {'as_of': as_of, 'month_start': start, 'work': work, 'work_limit': WORK_LIMIT, 'workspaces': len(entries),
            'counts': {state: sum(row['state'] == state for row in work)
                       for state in ('done', 'waiting', 'in_progress', 'stopped')}, 'cash': cash_in_month(entries)}


@login_required
@require_POST
def capture(request, case_id):
    case = get_object_or_404(granted(request.user, ['finance.read']), pk=case_id)
    form = MonthForm(request.POST)
    today = timezone.localdate()
    destination = (reverse('design_project_tab', args=[case.pk, 'month-end'])
                   if request.POST.get('return_to') == 'workspace' else reverse('design_company_month_end'))
    if not form.is_valid() or form.cleaned_data['month'] != today.strftime('%Y-%m'):
        messages.error(request, 'Choose the current month to capture today’s receivables.')
        return redirect(destination)
    try:
        capture_today(request.user, case.pk, form.cleaned_data['month'], int(request.POST.get('revision', '')))
    except (ValidationError, ValueError) as exc:
        messages.error(request, exc.messages[0] if isinstance(exc, ValidationError) else 'Reload the close view before capturing.')
    else:
        messages.success(request, 'Today’s receivables were captured.')
    return redirect(destination + '?month=' + today.strftime('%Y-%m'))


@transaction.atomic
def capture_today(actor, case_id, month, revision):
    today = timezone.localdate()
    if month != today.strftime('%Y-%m'):
        raise ValidationError('Choose the current month to capture today’s receivables.')
    case = lock_case(actor, case_id, 'finance.receivables', revision)
    case_access(actor, case)
    return receivables.snapshot(actor, case.pk, today, case.revision)


@login_required
@require_safe
@never_cache
def company(request):
    form, month = selection(request)
    cases = granted(request.user, ['finance.read']).order_by('title', 'pk')
    page = Paginator(cases, 12).get_page(request.GET.get('page'))
    report = []
    coverage = None
    overview = None
    if month:
        report = [workspace_close(request.user, case, month) for case in page]
        coverage = {
            'workspaces': len(report),
            'reviewed': sum(any(period['status'] == 'Reviewed figures' for period in entry['periods']) for entry in report),
            'captured': sum(entry['receivables'].get('date') is not None and
                            entry['receivables']['date'] == entry['receivables']['cutoff'] for entry in report),
            'cash': sum(bool(entry['cash']) for entry in report),
        }
        if report:
            overview = month_overview(request.user, report, month)
    return render(request, 'design/company_month_end.html', {'form': form, 'month': month, 'page': page, 'report': report,
                                                             'coverage': coverage, 'overview': overview})

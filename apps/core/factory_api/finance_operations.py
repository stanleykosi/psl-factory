"""Payment coverage and close capture through their native Finance readers."""
from decimal import Decimal, localcontext

from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404
from django.utils import timezone

from apps.core.workbench import granted
from apps.core.models import Case
from apps.core.read_budget import ReadLimit
from apps.finance import month_end, payments_overview

from .http import BOOLEAN, DATETIME, ID, REVISION, TEXT, UUID, Problem, array, choice, endpoint, nullable, obj
from .work import PAGE, page_number
from .workspaces import CLOSE, DATES, MONEY, MONTH, close_payload


CURSOR = {**TEXT, 'maxLength': 1024}
COUNT = {'type': 'integer', 'minimum': 0}
PAYMENTS_STATE = choice(*(value for value, label in payments_overview.STATES if value))
PAYMENT = obj({
    'invoice_id': ID, 'issue_id': nullable(ID), 'case_id': UUID, 'reference': TEXT, 'workspace': TEXT,
    'customer': {'type': 'string'}, 'contract': {'type': 'string'}, 'currency': TEXT, 'basis': TEXT,
    'status': choice(*payments_overview.LABELS), 'label': TEXT, 'records_url': TEXT,
    'record_payment_url': nullable(TEXT), 'review_payment_url': nullable(TEXT), 'reminder_url': nullable(TEXT),
    'age_days': nullable(COUNT), 'paid': MONEY, 'owed': MONEY, 'face': MONEY, 'reason': nullable(TEXT),
    'has_reminder_draft': BOOLEAN,
})
TOTAL = obj({'currency': TEXT, 'basis': TEXT, 'owed': MONEY, 'overdue': MONEY,
             'known_owed': MONEY, 'unknown_owed_count': COUNT})
CASH_COVERAGE = obj({'month': MONTH, 'scope': choice('workspaces_in_results'), 'workspaces_read': COUNT,
    'workspaces_unknown': COUNT, 'last_received_at': nullable(DATETIME), 'last_verified_at': nullable(DATETIME),
    'totals': array(obj({'currency': TEXT, 'basis': TEXT, 'amount': TEXT}))})


def amount(number):
    return str(number) if number is not None else None


def receipt_coverage(actor, rows, as_of):
    workspace_ids = {row['case_id'] for row in rows}
    month = as_of.strftime('%Y-%m')
    totals = {}
    read = 0
    received_at, verified_at = None, None
    with localcontext() as precision:
        precision.prec = 512
        for case in Case.objects.filter(pk__in=workspace_ids):
            try:
                groups, received, verified = month_end.cash_received_snapshot(actor, case, month)
            except (PermissionDenied, ValidationError, ReadLimit):
                continue
            read += 1
            if received:
                received_at = max(received_at, received) if received_at else received
            if verified:
                verified_at = max(verified_at, verified) if verified_at else verified
            for currency, basis, value in groups:
                key = (currency, basis)
                totals[key] = totals.get(key, Decimal(0)) + value
    return {'month': month, 'scope': 'workspaces_in_results', 'workspaces_read': read,
            'workspaces_unknown': len(workspace_ids) - read, 'last_received_at': received_at, 'last_verified_at': verified_at,
            'totals': [{'currency': key[0], 'basis': key[1], 'amount': amount(value)}
                       for key, value in sorted(totals.items())]}


@endpoint(response=obj({'as_of': DATES, 'items': array(PAYMENT, limit=25), 'totals': array(TOTAL, limit=25),
                        'received_this_month': CASH_COVERAGE,
                        'cursor': nullable(CURSOR), 'limited': BOOLEAN}),
          query={'q': {'type': 'string', 'maxLength': 100}, 'state': PAYMENTS_STATE, 'cursor': CURSOR},
          summary='Read the scoped payments queue and explicitly bounded totals')
def payments(http):
    search = http.GET.get('q', '').strip()
    state = http.GET.get('state', '')
    cursor = http.GET.get('cursor')
    if len(search) > 100 or state not in dict(payments_overview.STATES) or (cursor and len(cursor) > 1024):
        raise Problem(422, 'invalid_filter', 'Choose a shorter search and an available payment filter.')
    rows, totals, key, limited, as_of = payments_overview.read_page(http.user, search, state, cursor)
    items = [{
        **{name: row[name] for name in ('invoice_id', 'issue_id', 'case_id', 'reference', 'workspace',
                                        'customer', 'contract', 'currency', 'basis', 'age_days')},
        'status': row['key'], 'label': row['state'], 'records_url': row['records'],
        'record_payment_url': row['record_payment'], 'review_payment_url': row.get('review_payment'),
        'reminder_url': row.get('reminder'), 'reason': row.get('reason'),
        'has_reminder_draft': row.get('has_draft', False),
        **{name: amount(row[name]) for name in ('paid', 'owed', 'face')},
    } for row in rows]
    return {'as_of': as_of, 'items': items, 'limited': limited, 'cursor': key,
            'received_this_month': receipt_coverage(http.user, rows, as_of),
            'totals': [{**total, 'owed': amount(total['owed']), 'overdue': amount(total['overdue']),
                        'known_owed': amount(total['known_owed'])} for total in totals]}


MONTH_WORK = obj({'title': TEXT, 'workspace_id': UUID, 'workspace': TEXT,
                  'state': choice('done', 'waiting', 'in_progress', 'stopped'), 'label': TEXT,
                  'at': DATETIME, 'url': TEXT})
CASH_GROUP = obj({'workspace_id': nullable(UUID), 'workspace': nullable(TEXT), 'currency': TEXT,
                  'basis': TEXT, 'amount': TEXT})


@endpoint(response=obj({'month': MONTH, 'as_of': DATETIME, 'workspaces': array(CLOSE, limit=12),
                        'page': PAGE, 'next_page': nullable(PAGE), 'work': array(MONTH_WORK),
                        'cash': array(CASH_GROUP, limit=12), 'more_cash_groups': BOOLEAN,
                        'counts': obj({state: COUNT for state in ('done', 'waiting', 'in_progress', 'stopped')})}),
          query={'month': MONTH, 'page': PAGE}, summary='Read the bounded company close and source-authorised work')
def company_close(http):
    _, month = month_end.selection(http)
    if not month:
        raise Problem(422, 'invalid_filter', 'Choose a reporting month.')
    actor = http.user
    cases = granted(actor, ['finance.read']).order_by('title', 'pk')
    page = Paginator(cases, 12).get_page(page_number(http))
    entries = [month_end.workspace_close(actor, case, month) for case in page]
    value = month_end.month_overview(actor, entries, month)
    return {'month': month, 'as_of': value['as_of'], 'page': page.number,
            'next_page': page.next_page_number() if page.has_next() and page.number < PAGE['maximum'] else None,
            'workspaces': [close_payload(month, row, value['as_of']) for row in entries],
            'work': value['work'], 'counts': value['counts'],
            'cash': [{**row, 'workspace': row['workspace'] or None, 'amount': amount(row['amount'])}
                     for row in value['cash']['groups']], 'more_cash_groups': value['cash']['more_groups']}


@endpoint(method='POST', request=obj({'month': MONTH, 'revision': REVISION}),
          response=obj({'id': ID, 'as_of': DATES, 'sha256': TEXT, 'revision': REVISION}), status=201,
          summary='Capture current-day receivables from exact authorised Finance sources')
def capture_close(http, case_id, *, body):
    case = get_object_or_404(granted(http.user, ['finance.read']), pk=case_id)
    snapshot = month_end.capture_today(http.user, case.pk, body['month'], body['revision'])
    case.refresh_from_db(fields=['revision'])
    return {'id': snapshot.pk, 'as_of': snapshot.as_of, 'sha256': snapshot.sha256, 'revision': case.revision}

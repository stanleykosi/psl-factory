from time import monotonic

from django.core.exceptions import PermissionDenied, ValidationError
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils import timezone

from apps.core.design_views import discoverable_work
from apps.core.read_budget import ReadLimit, limit_queries
from apps.workflows import (
    factory, factory_accounting, factory_change, factory_commercial, factory_emergency, factory_escalation,
    factory_forecast, factory_go_live, factory_handover, factory_leadership, factory_minutes, factory_planning,
    factory_progress, factory_reporting, factory_rfp, factory_views,
)
from apps.workflows.factory_definitions import DEFINITIONS
from apps.workflows.models import FactoryAttempt, HumanTask
from apps.workflows.screen_focus import SCREENS

from .http import BOOLEAN, DATETIME, ID, REVISION, TEXT, UUID, Problem, array, choice, endpoint, nullable, obj


FINANCE_INVOICE = 'pmo-finance/v1'
ACCOUNTING = 'finance-accounts/v1'
RESTRICTED_LINES = {'finance-payroll/v1': 'payroll', 'finance-bu/v1': 'bu'}
STATES = {
    'ready': 'ready', 'waiting': 'waiting', 'blocked': 'action_needed', 'owner_needed': 'owner_needed',
    'configuration_needed': 'setup_needed', 'verified': 'verified', 'cancelled': 'cancelled',
    'waiting_effect': 'awaiting_reconciliation', 'followup_needed': 'followup_needed',
}
STATE = choice(*STATES.values(), 'processing', 'effect_uncertain')
ITEM = obj({
    'id': ID, 'case_id': UUID, 'title': TEXT, 'line': TEXT, 'state': STATE,
    'status_label': TEXT, 'sample': BOOLEAN, 'updated_at': DATETIME, 'django_url': TEXT,
})
FOCUS = obj({'key': choice('decision', 'response', 'recovery'), 'django_url': TEXT})
TASK = obj({
    'id': ID, 'kind': TEXT, 'role': TEXT, 'status': TEXT, 'revision': REVISION,
    'claimed_by_you': BOOLEAN, 'can_claim': BOOLEAN, 'can_decide': BOOLEAN,
    'verdicts': array(choice('approve', 'return', 'reject')),
})
DETAIL = obj({
    **ITEM['properties'], 'revision': nullable(REVISION), 'case_revision': nullable(REVISION), 'next_step': TEXT,
    'blocker': {'type': 'string'}, 'tasks': array(TASK), 'screens': array(FOCUS),
    'actions': array(choice('background', 'reconcile', 'release_invoice')),
    'progress': nullable(obj({'status': TEXT, 'updated_at': DATETIME})),
    'aggregate': nullable(obj({'report_id': ID, 'values': {'type': 'object', 'additionalProperties': {'type': ['string', 'number']}},
                               'currency': TEXT, 'period': TEXT, 'receipt_id': nullable(ID)})),
})
QUEUE = obj({
    'items': array(ITEM, limit=8), 'page': ID, 'next_page': nullable(ID), 'as_of': DATETIME,
    'limited': BOOLEAN, 'lines': array(obj({'key': TEXT, 'title': TEXT})),
})
WORK_RESULT = obj({'work_id': ID, 'state': STATE, 'revision': REVISION})
PAGE = {'type': 'integer', 'minimum': 1, 'maximum': 10000}


def state(work, row=None):
    if row and row['state'] in {'Effect uncertain', 'Document delivery uncertain', 'Delivery uncertain'}:
        return 'effect_uncertain'
    if work.lease_until and work.lease_until > timezone.now() and work.status not in factory.TERMINAL:
        return 'processing'
    return STATES.get(work.status, 'action_needed')


def summary(row):
    work = row['work']
    return {
        'id': work.pk, 'case_id': work.case_id, 'title': row.get('title') or DEFINITIONS[work.definition]['title'],
        'line': work.definition, 'state': state(work, row), 'status_label': row['state'],
        'sample': work.case.synthetic, 'updated_at': work.updated_at,
        'django_url': reverse('factory_detail', args=[work.pk]),
    }


def page_number(request):
    value = request.GET.get('page', '1')
    if not value.isascii() or not value.isdecimal() or len(value) > 5 or not 1 <= int(value) <= PAGE['maximum']:
        raise Problem(422, 'invalid_filter', 'Choose a page from 1 to 10000.')
    return int(value)


@endpoint(response=QUEUE, summary='Read the scoped factory queue',
          query={'queue': choice(*factory_views.QUEUES), 'line': choice(*DEFINITIONS),
                 'q': {'type': 'string', 'maxLength': 120}, 'page': PAGE, 'project': UUID})
def queue(request):
    scope = discoverable_work(request.user)
    project = request.GET.get('project')
    if project:
        from uuid import UUID as parse_uuid

        try:
            scope = scope.filter(case_id=parse_uuid(project))
        except ValueError:
            raise Problem(422, 'invalid_filter', 'Choose a valid project identifier.') from None
    values = request.GET.copy()
    values['page'] = str(page_number(request))
    if (values.get('queue', 'needs_me') not in factory_views.QUEUES or
            values.get('line', '') not in ('', *DEFINITIONS) or len(values.get('q', '')) > 120):
        raise Problem(422, 'invalid_filter', 'Check the work queue filters.')
    context = factory_views.queue_context(request.user, values, scope=scope)
    page = context['candidates']
    return {'items': [summary(row) for row in context['rows']], 'page': page.number,
            'next_page': page.next_page_number() if page.has_next() and page.number < PAGE['maximum'] else None,
            'limited': context['limited'], 'as_of': context['as_of'],
            'lines': [{'key': key, 'title': title} for key, title in context['line_choices']]}


def bound_work(actor, work_id):
    return get_object_or_404(factory_views.visible(actor, work_id=work_id))


def observed_work(actor, work_id):
    work = bound_work(actor, work_id)
    try:
        with limit_queries(1400, deadline=monotonic() + 8):
            row = factory_views.presentation(actor, work, include_progress=True)
    except ReadLimit:
        raise Problem(503, 'read_limited', 'The work details exceeded the current read limit. Try again.') from None
    protected = row.get(RESTRICTED_LINES.get(work.definition), {})
    if protected.get('restricted'):
        raise Http404
    return work, row, protected


def task_data(task, actor):
    return {
        'id': task.pk, 'kind': task.kind, 'role': task.required_role, 'status': task.status,
        'revision': task.revision, 'claimed_by_you': task.claimed_by_id == actor.pk,
        'can_claim': bool(getattr(task, 'can_claim', False)), 'can_decide': bool(getattr(task, 'can_decide', False)),
        'verdicts': list(getattr(task, 'allowed_verdicts', getattr(task, 'verdicts', ()))),
    }


# These paths have a matching native recovery handler for an exact existing effect.
RECONCILE_LINES = {
    FINANCE_INVOICE: factory.reconcile,
    'finance-accounts/v1': factory_accounting.reconcile,
    'finance-forecast/v1': factory_forecast.reconcile,
    'rfp-response/v1': factory_rfp.reconcile,
    'pmo-minutes/v1': factory_minutes.reconcile,
    'pmo-weekly-report/v1': factory_reporting.reconcile,
    'pmo-leadership-report/v1': factory_leadership.reconcile,
    'pmo-escalation/v1': factory_escalation.reconcile,
    'pmo-emergency/v1': factory_emergency.reconcile,
    'pmo-change/v1': factory_change.reconcile,
    'delivery-go-live/v1': factory_go_live.reconcile,
    'delivery-handover/v1': factory_handover.reconcile,
    'commercial/v1': factory_commercial.reconcile,
    'planning/v1': factory_planning.reconcile,
}
FOCUS_ROUTES = {
    'decision': 'factory_invoice_decision', 'recovery': 'factory_invoice_recovery',
    'response': 'factory_work_response',
}


@endpoint(response=DETAIL, summary='Read the current work, independent tasks and permitted actions')
def detail(request, work_id):
    work, row, protected = observed_work(request.user, work_id)
    recipient = protected.get('recipient_only', False)
    aggregate = None
    if recipient and 'totals' in protected:
        receipt = protected.get('receipt')
        aggregate = {'report_id': protected['publication'], 'values': protected['totals'],
                     'currency': protected['currency'], 'period': protected['period'],
                     'receipt_id': receipt.pk if receipt else None}
    if recipient:
        # Recipient authorization is for the publication, not the preparer's queue or work facts.
        return {
            **summary(row), 'title': 'Received aggregate report', 'revision': None, 'case_revision': None,
            'state': 'waiting' if not aggregate or not aggregate['receipt_id'] else 'verified',
            'next_step': row['next_action'], 'blocker': '',
            'tasks': [], 'screens': [], 'actions': [], 'progress': None, 'aggregate': aggregate,
        }
    tasks = [task_data(task, request.user) for task in row['tasks']] if work.definition in {FINANCE_INVOICE, ACCOUNTING} else []
    actions = []
    from apps.workflows.factory_execution import can_control

    if can_control(request.user, work) and work.status not in factory.TERMINAL and not work.cancel_requested:
        actions.append('background')
    if work.definition in RECONCILE_LINES and row.get('can_reconcile'):
        actions.append('reconcile')
    progress = getattr(work, 'background_progress', None)
    if (work.definition == FINANCE_INVOICE and row.get('can_advance') and not row['jobs']
            and (not progress or progress.status not in factory_progress.ACTIVE)):
        try:
            if factory_progress.invoice_release_ready(work):
                actions.append('release_invoice')
        except (ValidationError, PermissionDenied):
            pass
    return {
        **summary(row), 'revision': work.revision, 'case_revision': work.case.revision,
        'next_step': row.get('next_action') or 'Review the current work.', 'blocker': row.get('blocker') or '',
        'tasks': tasks, 'actions': actions, 'aggregate': aggregate,
        'screens': [{'key': key, 'django_url': reverse(FOCUS_ROUTES[key], args=[work.pk])}
                    for key in SCREENS.get(work.definition, {})],
        'progress': {'status': progress.status, 'updated_at': progress.updated_at} if progress else None,
    }


ATTEMPT = obj({'at': DATETIME, 'station': TEXT, 'status': TEXT})


@endpoint(response=obj({'items': array(ATTEMPT, limit=30), 'as_of': DATETIME}),
          query={'kind': choice('worker', 'decision', 'evidence')}, summary='Read recent work, decision or evidence history')
def history(request, work_id):
    work, _, protected = observed_work(request.user, work_id)
    kind = request.GET.get('kind', 'worker')
    if kind not in ('worker', 'decision', 'evidence'):
        raise Problem(422, 'invalid_filter', 'Choose a listed history filter.')
    items = []
    if not protected.get('recipient_only'):
        from apps.core.templatetags.studio_ui import readable
        from apps.workflows.models import TaskEvent

        if kind == 'worker':
            attempts = (FactoryAttempt.objects.filter(activity__work=work)
                        .order_by('-pk').values_list('created_at', 'activity__kind', 'phase')[:30])
            items = [{'at': at, 'station': readable(station), 'status': phase} for at, station, phase in attempts]
        else:
            events = TaskEvent.objects.filter(task__case=work.case, task__context__work=work.pk,
                                              task__factory_key__startswith=f'factory:{work.pk}:')
            if kind == 'decision':
                events = events.filter(data__verdict__in=['approve', 'return', 'reject'])
            else:
                events = events.filter(action__in=['factory.information_verified', 'factory.packet_superseded'])
            items = [{'at': event.created_at, 'station': readable(event.task.kind),
                      'status': event.data['verdict'] if kind == 'decision' else readable(event.action.split('.')[-1])}
                     for event in events.select_related('task').order_by('-pk')[:30]]
    return {'items': items, 'as_of': timezone.now()}


def result(work):
    return {'work_id': work.pk, 'state': state(work), 'revision': work.revision}


@endpoint(method='POST', request=obj({'expected_revision': REVISION, 'enabled': BOOLEAN}),
          response=WORK_RESULT, status=202, summary='Continue or pause an existing background request')
def background(request, work_id, *, body):
    work, _, protected = observed_work(request.user, work_id)
    if protected.get('recipient_only'):
        raise Http404
    if work.revision != body['expected_revision']:
        raise ValidationError('STALE_VERSION: Open the current work item.')
    factory_progress.set_progress(request.user, work.pk, body['expected_revision'], body['enabled'])
    work.refresh_from_db(fields=['status', 'revision', 'lease_until'])
    return result(work)


@endpoint(method='POST', request=obj({'expected_revision': REVISION, 'action': choice('reconcile', 'release_invoice')}),
          response=WORK_RESULT, status=202, summary='Check an original effect or explicitly request invoice release')
def action(request, work_id, *, body):
    work = bound_work(request.user, work_id)
    if body['action'] == 'release_invoice':
        operation = factory_progress.queue_invoice_release if work.definition == FINANCE_INVOICE else None
    else:
        operation = RECONCILE_LINES.get(work.definition)
    if operation is None:
        raise Http404
    if work.revision != body['expected_revision']:
        raise ValidationError('STALE_VERSION: Open the current work item.')
    operation(request.user, work.pk, body['expected_revision'])
    work.refresh_from_db(fields=['status', 'revision', 'lease_until'])
    return result(work)


def review_task(actor, task_id):
    # Both the task and the work binding are required. Arbitrary task types have separate interfaces.
    kinds = {'factory_review': FINANCE_INVOICE, 'factory_accounting_review': ACCOUNTING}
    task = get_object_or_404(HumanTask, pk=task_id, kind__in=kinds)
    work_id = task.context.get('work')
    if type(work_id) is not int or not task.factory_key or not task.factory_key.startswith(f'factory:{work_id}:'):
        raise Http404
    work = bound_work(actor, work_id)
    if work.definition != kinds[task.kind] or work.case_id != task.case_id:
        raise Http404
    return work, task


PACKET = obj({
    'invoice_id': ID, 'version': REVISION, 'sha256': TEXT, 'amount': TEXT, 'currency': TEXT,
    'recipient': nullable(TEXT), 'preparation_id': ID,
    'sources': array(obj({'id': ID, 'version': REVISION, 'kind': TEXT, 'sha256': TEXT})),
})


@endpoint(response=obj({'task': TASK, 'work_id': ID, 'label': TEXT, 'invoice_packet': nullable(PACKET),
                        'review_evidence': array(obj({'id': ID, 'version': ID, 'source': TEXT, 'sha256': TEXT}))}),
          summary='Read the exact current Finance task and permitted invoice packet')
def task(request, task_id):
    work, _ = review_task(request.user, task_id)
    work, row, _ = observed_work(request.user, work.pk)
    selected = next((item for item in row['tasks'] if item.pk == task_id), None)
    if selected is None:
        raise Http404
    fields = None
    if work.definition == FINANCE_INVOICE:
        from apps.workflows.factory_invoice_review import context

        context(request.user, row)
        packet = selected.display_packet
        if packet and work.invoice_id and 'preparation' in packet:
            fields = {'invoice_id': packet['invoice'], 'version': packet['version'], 'sha256': packet['payload_hash'],
                      'amount': packet['amount'], 'currency': packet['currency'], 'preparation_id': packet['preparation'],
                      'recipient': getattr(selected, 'recipient_name', None),
                      'sources': [{'id': item.pk, 'version': item.version, 'kind': item.kind, 'sha256': item.sha256}
                                  for item in selected.source_records]}
    from apps.core.evidence_access import public_evidence
    from apps.core.models import Evidence

    info = task_data(selected, request.user)
    proofs = []
    if info['can_decide'] and fields:
        proofs = list(public_evidence(Evidence.objects.filter(case=work.case, kind='invoice_review'))
                      .order_by('-pk').values('id', 'version', 'source', 'sha256'))
    return {'task': info, 'work_id': work.pk, 'review_evidence': proofs,
            'label': getattr(selected, 'label', 'Finance review'), 'invoice_packet': fields}


@endpoint(method='POST', request=obj({'expected_revision': REVISION}),
          response=obj({'task_id': ID, 'revision': REVISION, 'claimed_by': TEXT}),
          summary='Claim an exact current invoice or accounting review')
def claim(request, task_id, *, body):
    work, task = review_task(request.user, task_id)
    service = factory_accounting if work.definition == ACCOUNTING else factory
    acquire = service.claim if work.definition == ACCOUNTING else service.claim_task
    claimed = acquire(request.user, task.pk, body['expected_revision'])
    return {'task_id': claimed.pk, 'revision': claimed.revision,
            'claimed_by': request.user.get_full_name() or request.user.get_username()}


@endpoint(method='POST', request=obj({
    'expected_revision': REVISION, 'verdict': choice('approve', 'return', 'reject'), 'evidence_id': ID,
    'note': {'type': 'string', 'maxLength': 2000},
}), response=obj({'task_id': ID, 'review_id': ID, 'verdict': TEXT, 'work_state': STATE}),
    summary='Record a decision on the currently claimed Finance subject')
def decision(request, task_id, *, body):
    work, task = review_task(request.user, task_id)
    service = factory_accounting if work.definition == ACCOUNTING else factory
    review = service.decide(request.user, task.pk, body['expected_revision'], body['verdict'],
                            body['evidence_id'], body['note'])
    work.refresh_from_db(fields=['status', 'revision', 'lease_until'])
    return {'task_id': task.pk, 'review_id': review.pk, 'verdict': review.verdict, 'work_state': state(work)}

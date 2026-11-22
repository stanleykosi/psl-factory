from time import monotonic

from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils import timezone

from apps.core.design_views import discoverable_work
from apps.core.presentation import workspace_name
from apps.core.workbench import granted
from apps.identity.services import active_case_grants
from apps.core.read_budget import ReadLimit, limit_queries
from apps.workflows import (
    factory, factory_accounting, factory_change, factory_commercial, factory_emergency, factory_escalation,
    factory_forecast, factory_go_live, factory_handover, factory_leadership, factory_minutes, factory_planning,
    factory_progress, factory_reporting, factory_rfp, factory_views,
)
from apps.workflows.factory_definitions import DEFINITIONS
from apps.workflows.models import FactoryAttempt, HumanTask
from apps.workflows.native_station_contracts import DEFINITION as DEPARTMENT_HANDOFF
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
    'status_label': TEXT, 'owner': nullable(TEXT), 'sample': BOOLEAN, 'updated_at': DATETIME, 'django_url': TEXT, 'api_url': TEXT,
})
FOCUS = obj({'key': choice('decision', 'response', 'recovery'), 'django_url': TEXT})
TASK = obj({
    'id': ID, 'kind': TEXT, 'role': TEXT, 'status': TEXT, 'revision': REVISION,
    'claimed_by_you': BOOLEAN, 'can_claim': BOOLEAN, 'can_decide': BOOLEAN,
    'verdicts': array(choice('approve', 'return', 'reject')), 'url': TEXT,
})
DETAIL = obj({
    **ITEM['properties'], 'revision': nullable(REVISION), 'case_revision': nullable(REVISION), 'next_step': TEXT,
    'blocker': {'type': 'string'}, 'tasks': array(TASK), 'screens': array(FOCUS),
    'actions': array(choice('background', 'reconcile', 'release_invoice')),
    'progress': nullable(obj({'status': TEXT, 'updated_at': DATETIME})),
    'aggregate': nullable(obj({'report_id': ID, 'values': {'type': 'object', 'additionalProperties': {'type': ['string', 'number']}},
                               'currency': TEXT, 'period': TEXT, 'receipt_id': nullable(ID)})),
    'department_handoff_url': TEXT, 'panels': array(obj({'key': TEXT, 'url': TEXT})),
    'output_url': nullable(TEXT), 'information': array(obj({'task_id': ID, 'url': TEXT})),
    'available_control': array(choice('resume', 'cancel', 'adopt_profile')),
    'profile_adoption': obj({'configuration_id': ID, 'version': REVISION}),
}, optional=('department_handoff_url', 'profile_adoption'))
QUEUE = obj({
    'items': array(ITEM, limit=8), 'page': ID, 'next_page': nullable(ID), 'as_of': DATETIME,
    'limited': BOOLEAN, 'lines': array(obj({'key': TEXT, 'title': TEXT})),
    'evaluated': {'type': 'integer', 'minimum': 0}, 'deferred': array(obj({'id': ID, 'url': TEXT}), limit=8),
    'payroll_questions': array(obj({'case_id': UUID, 'id': ID, 'state': TEXT, 'url': TEXT}), limit=8),
})
WORK_RESULT = obj({'work_id': ID, 'state': STATE, 'revision': REVISION})
PAGE = {'type': 'integer', 'minimum': 1, 'maximum': 10000}


def state(work, row=None):
    if row and row['state'].casefold().endswith('uncertain'):
        return 'effect_uncertain'
    if work.lease_until and work.lease_until > timezone.now() and work.status not in factory.TERMINAL:
        return 'processing'
    return STATES.get(work.status, 'action_needed')


def summary(row):
    work = row['work']
    return {
        'id': work.pk, 'case_id': work.case_id, 'title': row.get('title') or DEFINITIONS[work.definition]['title'],
        'line': work.definition, 'state': state(work, row), 'status_label': row['state'], 'owner': row.get('owner') or None,
        'sample': work.case.synthetic, 'updated_at': work.updated_at,
        'django_url': reverse('factory_detail', args=[work.pk]), 'api_url': f'/api/v1/work/{work.pk}',
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
    questions = context['payroll_questions']
    return {'items': [summary(row) for row in context['rows']], 'page': page.number,
            'next_page': page.next_page_number() if page.has_next() and page.number < PAGE['maximum'] else None,
            'limited': context['limited'] or questions['held'], 'as_of': context['as_of'], 'evaluated': context['evaluated'],
            'deferred': [{'id': work.pk, 'url': f'/api/v1/work/{work.pk}'} for work in context['deferred']],
            'payroll_questions': [
                {'case_id': row['case'].pk, 'id': row['id'], 'state': row['state'],
                 'url': f"/api/v1/projects/{row['case'].pk}/payroll/questions/{row['id']}"}
                for row in questions['rows'] if not project or str(row['case'].pk) == project],
            'lines': [{'key': key, 'title': title} for key, title in context['line_choices']]}


FINANCE_QUEUES = {
    'accounting-intake': ('case.read', 'finance.read'),
    'asset-registers': ('case.read', 'finance.read', 'ppe.read'),
    'incumbent-resolutions': ('case.read', 'finance.read', 'ledger.read', 'ledger.private.read'),
    'business-unit-intake': ('case.read', 'bu.read', 'bu.private.read'),
    'payroll/requests': ('case.read', 'payroll.read', 'payroll.private.read'),
}


@endpoint(response=obj({'items': array(obj({'case_id': UUID, 'title': TEXT, 'sources': array(
    obj({'key': choice(*FINANCE_QUEUES), 'url': TEXT}), limit=5)}), limit=25), 'next_page': nullable(PAGE)}),
    query={'page': PAGE}, summary='List authorised Finance source queues by workspace')
def finance_sources(request):
    actor = request.user
    choices = [granted(actor, actions, include_roles=False) for actions in FINANCE_QUEUES.values()]
    cases = choices[0].union(*choices[1:]).order_by('title', 'pk')
    page = Paginator(cases, 25).get_page(page_number(request))
    scoped = {}
    for case_id, action in active_case_grants(actor, [case.pk for case in page]):
        scoped.setdefault(case_id, set()).add(action)
    return {'items': [{'case_id': case.pk, 'title': workspace_name(case), 'sources': [
        {'key': key, 'url': f'/api/v1/projects/{case.pk}/{key}'} for key, actions in FINANCE_QUEUES.items()
        if set(actions) <= scoped.get(case.pk, set())]} for case in page],
        'next_page': page.next_page_number() if page.has_next() and page.number < PAGE['maximum'] else None}


def bound_work(actor, work_id):
    return get_object_or_404(factory_views.visible(actor, work_id=work_id))


def observed_work(actor, work_id):
    work = bound_work(actor, work_id)
    if work.definition == DEPARTMENT_HANDOFF:
        # visible() rechecks this exact source, actor and current native receipt.
        # The worker's execution permissions belong to the department service.
        from .handoffs import item
        from apps.core.templatetags.studio_ui import readable

        return work, {'work': work, 'title': item(work)['title'], 'state': readable(work.status)}, {'handoff': True}
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
        'url': f'/api/v1/tasks/{task.pk}',
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
STATION_PANELS = {
    'engagement/v1': ('engagement',),
    'planning/v1': ('planning-owner-requests', 'planning-exit'),
    'delivery-release/v1': ('release-register',),
    'delivery-handover/v1': ('support-receipt', 'support-replies'),
    'delivery-go-live/v1': ('go-live-signoff', 'go-live-replies', 'go-live-milestone'),
    'delivery-hypercare/v1': ('stability', 'stability/events'),
    'delivery-archive/v1': ('archive-files',),
    'pmo-weekly-report/v1': ('weekly-report',),
    'pmo-leadership-report/v1': ('leadership-report',),
    'pmo-minutes/v1': ('minutes',),
    'pmo-escalation/v1': ('escalation',),
    'pmo-emergency/v1': ('emergency',),
    'pmo-change/v1': ('change',),
    'pmo-issues/v1': ('issue-followup',),
    'finance-schedules/v1': ('finance-schedule',),
    'finance-ppe/v1': ('assets',),
    'finance-forecast/v1': ('forecast', 'forecast/disclosure', 'forecast/lifecycle'),
    'finance-payroll/v1': ('payroll-operations', 'payroll-recovery'),
    'finance-bu/v1': ('business-units',),
    'finance-ledger/v1': ('incumbent-reference',),
    FINANCE_INVOICE: ('invoice-milestone-proof', 'invoice-draft-stop'),
    ACCOUNTING: ('accounting',),
    'rfp-response/v1': ('bid-answers', 'bid-pricing', 'bid-submission', 'bid-outcomes', 'security-estimate'),
}
OUTPUT_PANEL = {
    'delivery-go-live/v1': 'go-live-milestone',
    'rfp-response/v1': 'bid-submission',
    'finance-forecast/v1': 'forecast',
    'finance-payroll/v1': 'payroll-operations',
}


def panels_for(work, row):
    root = f'/api/v1/work/{work.pk}'
    case = f'/api/v1/projects/{work.case_id}'
    panels = [{'key': key, 'url': f'{root}/{key}'} for key in STATION_PANELS.get(work.definition, ())]
    output_key = OUTPUT_PANEL.get(work.definition)
    output = f'{root}/{output_key}' if output_key else panels[0]['url'] if panels else None
    if work.definition == 'commercial/v1':
        panels.append({'key': 'commercial-response', 'url': f'{case}/commercial-response'})
        output = panels[-1]['url']
    if work.definition == 'delivery-closure/v1' and type(work.request.get('dossier')) is int:
        output = f"{case}/delivery/{work.request['dossier']}/closure-checklist"
        panels.append({'key': 'closure-checklist', 'url': output})
    if work.definition == 'delivery-release/v1' and type(work.request.get('dossier')) is int:
        testing = f"{case}/delivery/{work.request['dossier']}/client-testing"
        panels += [{'key': 'client-testing', 'url': testing}, {'key': 'client-testing-pack', 'url': f'{testing}/pack'}]
    if work.definition == FINANCE_INVOICE and work.invoice_id:
        output = f'{case}/billing-invoices/{work.invoice_id}'
        panels.append({'key': 'invoice', 'url': output})
    return panels, output if work.status == 'verified' and not row.get('readiness_changed') else None


@endpoint(response=DETAIL, summary='Read the current work, independent tasks and permitted actions')
def detail(request, work_id):
    work, row, protected = observed_work(request.user, work_id)
    if protected.get('handoff'):
        url = request.path.rstrip('/') + '/department-handoff'
        return {
            **summary(row), 'revision': None, 'case_revision': None,
            'next_step': 'Open the department handoff to check its evidence and available decisions.',
            'department_handoff_url': url, 'panels': [{'key': 'department-handoff', 'url': url}],
            'output_url': url if work.status == 'verified' else None, 'information': [], 'available_control': [],
            'blocker': '', 'tasks': [], 'screens': [], 'actions': [], 'progress': None, 'aggregate': None,
        }
    recipient = protected.get('recipient_only', False)
    aggregate = None
    if recipient and 'totals' in protected:
        receipt = protected.get('receipt')
        aggregate = {'report_id': protected['publication'], 'values': protected['totals'],
                     'currency': protected['currency'], 'period': protected['period'],
                     'receipt_id': receipt.pk if receipt else None}
    if recipient:
        # Recipient authorization is for the publication, not the preparer's queue or work facts.
        url = (f"/api/v1/projects/{work.case_id}/payroll/reports/{aggregate['report_id']}"
               if aggregate and work.definition == 'finance-payroll/v1' else None)
        return {
            **summary(row), 'title': 'Received aggregate report', 'revision': None, 'case_revision': None,
            'state': 'waiting' if not aggregate or not aggregate['receipt_id'] else 'verified',
            'next_step': row['next_action'], 'blocker': '',
            'tasks': [], 'screens': [], 'actions': [], 'progress': None, 'aggregate': aggregate,
            'panels': [{'key': 'aggregate', 'url': url}] if url else [], 'output_url': url, 'information': [], 'available_control': [],
        }
    tasks = [task_data(task, request.user) for task in row['tasks'] if task.kind in (
        'factory_review', 'factory_accounting_review')] if work.definition in {FINANCE_INVOICE, ACCOUNTING} else []
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
    panels, output = panels_for(work, row)
    control = []
    if row.get('can_cancel'):
        control.append('cancel')
    if row.get('can_manage') and work.status not in factory.TERMINAL and not work.cancel_requested:
        control.append('resume')
    if row.get('adoption'):
        control.append('adopt_profile')
    adoption = row.get('adoption')
    return {
        **summary(row), 'revision': work.revision, 'case_revision': work.case.revision,
        'next_step': row.get('next_action') or 'Review the current work.', 'blocker': row.get('blocker') or '',
        'tasks': tasks, 'actions': actions, 'aggregate': aggregate, 'panels': panels, 'output_url': output,
        'available_control': control,
        **({'profile_adoption': {'configuration_id': adoption['id'], 'version': adoption['revision']}} if adoption else {}),
        'information': [{'task_id': task.pk, 'url': f'/api/v1/work/{work.pk}/information/{task.pk}'}
                        for task in row.get('tasks', []) if work.definition == FINANCE_INVOICE
                        and task.kind in ('factory_information', 'factory_governance')],
        'screens': [{'key': key, 'django_url': reverse(FOCUS_ROUTES[key], args=[work.pk])}
                    for key in SCREENS.get(work.definition, {})],
        'progress': {'status': progress.status, 'updated_at': progress.updated_at} if progress else None,
    }


ATTEMPT = obj({'at': DATETIME, 'station': TEXT, 'status': TEXT, 'task_id': ID, 'actor': TEXT, 'reason': {'type': 'string'},
    'evidence_id': nullable(ID)}, optional=('task_id', 'actor', 'reason', 'evidence_id'))


@endpoint(response=obj({'items': array(ATTEMPT, limit=30), 'as_of': DATETIME}),
          query={'kind': choice('worker', 'decision', 'evidence')}, summary='Read recent work, decision or evidence history')
def history(request, work_id):
    work, _, protected = observed_work(request.user, work_id)
    kind = request.GET.get('kind', 'worker')
    if kind not in ('worker', 'decision', 'evidence'):
        raise Problem(422, 'invalid_filter', 'Choose a listed history filter.')
    items = []
    if not (protected.get('recipient_only') or protected.get('handoff')):
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
                events = events.filter(action__in=['factory.information_received', 'factory.information_verified', 'factory.packet_superseded'])
            events = list(events.select_related('task', 'actor').order_by('-pk')[:30])
            exact_reviews, proof_candidates = {}, set()
            from apps.core.evidence_access import public_evidence

            if kind == 'decision' and work.definition == FINANCE_INVOICE and work.invoice_id:
                from apps.finance.models import InvoiceReview

                ids = [event.data['native_review'] for event in events if type(event.data.get('native_review')) is int]
                exact_reviews = InvoiceReview.objects.filter(invoice_id=work.invoice_id).in_bulk(ids)
                proof_candidates.update(row.evidence_id for row in exact_reviews.values())
            elif kind == 'evidence':
                proof_candidates.update(event.data['evidence'] for event in events if type(event.data.get('evidence')) is int)
            proofs = set(public_evidence(work.case.evidence.filter(pk__in=proof_candidates)).values_list('pk', flat=True))
            for event in events:
                entry = {'at': event.created_at, 'station': readable(event.task.kind), 'task_id': event.task_id,
                         'status': event.data['verdict'] if kind == 'decision' else readable(event.action.split('.')[-1]),
                         'actor': event.actor.get_full_name() or event.actor.get_username()}
                review = exact_reviews.get(event.data.get('native_review'))
                if review and review.actor_id == event.actor_id and review.verdict == event.data['verdict'] and review.evidence_id in proofs:
                    entry.update(reason=review.note, evidence_id=review.evidence_id)
                if kind == 'evidence' and type(event.data.get('evidence')) is int and event.data['evidence'] in proofs:
                    entry['evidence_id'] = event.data['evidence']
                items.append(entry)
    return {'items': items, 'as_of': timezone.now()}


def result(work):
    return {'work_id': work.pk, 'state': state(work), 'revision': work.revision}


@endpoint(method='POST', request=obj({'expected_revision': REVISION, 'enabled': BOOLEAN}),
          response=WORK_RESULT, status=202, summary='Continue or pause an existing background request')
def background(request, work_id, *, body):
    work, _, protected = observed_work(request.user, work_id)
    if protected.get('recipient_only') or protected.get('handoff'):
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
    if work.definition == DEPARTMENT_HANDOFF:
        raise Http404
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


CONTROL = {'oneOf': [
    obj({'expected_revision': REVISION, 'action': choice('cancel', 'resume')}),
    obj({'expected_revision': REVISION, 'action': {'const': 'adopt_profile'}, 'configuration_id': ID,
         'reason': {**TEXT, 'maxLength': 2000}}),
]}


@endpoint(method='POST', request=CONTROL, response=WORK_RESULT,
          summary='Record an authorised stop, resume or exact reviewed execution profile adoption')
def control(request, work_id, *, body):
    work = bound_work(request.user, work_id)
    if work.definition == DEPARTMENT_HANDOFF:
        raise Http404
    action = body['action']
    if action == 'adopt_profile':
        work = factory.adopt_profile(request.user, work.pk, body['expected_revision'], body['configuration_id'], body['reason'])
    else:
        work = factory.manage(request.user, work.pk, body['expected_revision'], action)
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

from datetime import date
from time import monotonic

from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db.models import Exists, OuterRef, Q, Subquery
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.urls import Resolver404, resolve, reverse
from django.utils import timezone

from apps.agents.assistant_models import AssistantTurn
from apps.core.design_views import discoverable_work
from apps.core.presentation import workspace_name
from apps.core.workbench import granted
from apps.identity.services import active_case_grants
from apps.core.read_budget import ReadLimit, limit_queries
from apps.core.read_observation import observation_scope, read_observation
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
STATION_NAMES = {'intake': 'Intake', 'execution': 'Agent and team work', 'decision': 'Human decision',
                 'delivery': 'Delivery and receipt', 'verified': 'Verified result'}
QUEUE_STATION = obj({'key': choice(*STATION_NAMES), 'index': ID, 'count': ID, 'name': TEXT})
ITEM = obj({
    'id': ID, 'case_id': UUID, 'title': TEXT, 'line': TEXT, 'state': STATE,
    'status_label': TEXT, 'owner': nullable(TEXT), 'sample': BOOLEAN, 'updated_at': DATETIME, 'django_url': TEXT, 'api_url': TEXT,
    'reference': nullable(TEXT), 'started_at': DATETIME, 'verified_at': nullable(DATETIME),
    'queue_output_url': nullable(TEXT), 'exception_code': nullable(TEXT), 'exception_next_step': nullable(TEXT),
    'exception_started_at': nullable(DATETIME), 'action_kind': nullable(choice('decide', 'do', 'fix', 'started')),
    'station': nullable(QUEUE_STATION), 'agent': nullable(TEXT),
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
    'department_handoff_url': TEXT, 'panels': array(obj({'key': TEXT, 'url': TEXT, 'contract_path': nullable(TEXT)})),
    'output_url': nullable(TEXT), 'information': array(obj({'task_id': ID, 'url': TEXT})),
    'available_control': array(choice('resume', 'cancel', 'adopt_profile')),
    'profile_adoption': obj({'configuration_id': ID, 'version': REVISION}),
    'current_activity': obj({'label': TEXT, 'watching': BOOLEAN}),
    'tracking_url': nullable(TEXT), 'proofs_url': nullable(TEXT),
}, optional=('department_handoff_url', 'profile_adoption', 'current_activity'))
COUNT = {'type': 'integer', 'minimum': 0}
PAGE_SIZE = {'type': 'integer', 'enum': [8, 10, 15, 20, 50]}
QUEUE = obj({
    'items': array(ITEM, limit=50), 'page': ID, 'next_page': nullable(ID), 'as_of': DATETIME,
    'page_size': PAGE_SIZE, 'total': nullable(COUNT),
    'limited': BOOLEAN, 'total_coverage': choice('complete', 'incomplete'),
    'lines': array(obj({'key': TEXT, 'title': TEXT})),
    'evaluated': COUNT, 'deferred': array(obj({'id': ID, 'url': TEXT}), limit=50),
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


def verification_events():
    return FactoryAttempt.objects.filter(activity__kind='ACT13', phase='observed', result__verified=True).order_by('-pk')


def queue_observations(scope, actor):
    attempts = FactoryAttempt.objects.filter(activity__work_id=OuterRef('pk'))
    assistant = AssistantTurn.objects.filter(started_work_id=OuterRef('pk'), conversation__actor=actor).order_by('pk')
    return scope.annotate(last_verification_at=Subquery(verification_events().filter(
        activity__work_id=OuterRef('pk')).values('created_at')[:1]), has_attempt=Exists(attempts),
        assistant_agent=Subquery(assistant.values('conversation__persona')[:1]))


def queue_station(work, row):
    if work.status == 'verified' and not row.get('readiness_changed'):
        return 'verified'
    if work.status == 'waiting_effect':
        return 'delivery'
    if factory_views.decision_inbox_row(row):
        return 'decision'
    return 'execution' if work.has_attempt or work.status not in ('ready', 'configuration_needed') else 'intake'


def summary(row):
    work = row['work']
    reference = work.request.get('reference') if work.definition not in RESTRICTED_LINES else None
    return {
        'id': work.pk, 'case_id': work.case_id, 'title': row.get('title') or DEFINITIONS[work.definition]['title'],
        'line': work.definition, 'state': state(work, row), 'status_label': row['state'], 'owner': row.get('owner') or None,
        'reference': reference if isinstance(reference, str) and reference else None,
        'sample': work.case.synthetic, 'updated_at': work.updated_at, 'started_at': work.created_at,
        'verified_at': getattr(work, 'last_verification_at', None)
            if work.status == 'verified' and not row.get('readiness_changed') else None,
        'queue_output_url': None, 'exception_code': None, 'exception_next_step': None,
        'exception_started_at': None, 'action_kind': None, 'station': None, 'agent': None,
        'django_url': reverse('factory_detail', args=[work.pk]), 'api_url': f'/api/v1/work/{work.pk}',
    }


def queue_summary(row, queue_key):
    item = summary(row)
    work = row['work']
    if work.definition in RESTRICTED_LINES or work.definition == DEPARTMENT_HANDOFF:
        return item
    station = queue_station(work, row)
    item['station'] = {'key': station, 'index': list(STATION_NAMES).index(station) + 1,
                       'count': len(STATION_NAMES), 'name': STATION_NAMES[station]}
    item['agent'] = work.assistant_agent
    item['action_kind'] = 'fix' if factory_views.exception_inbox_row(row, work.status) else (
        'decide' if station == 'decision' else 'do' if row.get('needs_me') else 'started')
    if queue_key == 'verified':
        item['queue_output_url'] = panels_for(work, row)[1]
    if queue_key == 'exceptions':
        holds = ('readiness_changed', 'correction_required', 'review_needs_update', 'coordination_needed',
                 'execution_owner_needed', 'source_instruction_needed', 'source_followup_needed',
                 'operation_followup_needed', 'outcome_selection_needed', 'held_publication_needs_operator', 'adoption')
        item['exception_code'] = next((hold for hold in holds if row.get(hold)), item['state'])
        item['exception_next_step'] = row.get('next_action') or None
        if item['exception_code'] == STATES.get(work.status) and work.status in (
            'blocked', 'owner_needed', 'configuration_needed', 'waiting_effect', 'followup_needed',
        ):
            item['exception_started_at'] = work.status_changed_at
    return item


def page_number(request):
    value = request.GET.get('page', '1')
    if not value.isascii() or not value.isdecimal() or len(value) > 5 or not 1 <= int(value) <= PAGE['maximum']:
        raise Problem(422, 'invalid_filter', 'Choose a page from 1 to 10000.')
    return int(value)


@endpoint(response=QUEUE, summary='Read the scoped factory queue',
          query={'queue': choice(*factory_views.QUEUES), 'line': choice(*DEFINITIONS),
                 'q': {'type': 'string', 'maxLength': 120}, 'page': PAGE, 'project': UUID, 'limit': PAGE_SIZE,
                 'state': STATE, 'verified_month': {'type': 'string', 'pattern': r'^\d{4}-(0[1-9]|1[0-2])$'}})
def queue(request):
    scope = queue_observations(discoverable_work(request.user), request.user)
    project = request.GET.get('project')
    if project:
        from uuid import UUID as parse_uuid

        try:
            scope = scope.filter(case_id=parse_uuid(project))
        except ValueError:
            raise Problem(422, 'invalid_filter', 'Choose a valid project identifier.') from None
    values = request.GET.copy()
    values['page'] = str(page_number(request))
    verified_month = values.get('verified_month')
    if verified_month:
        try:
            month = date.fromisoformat(f'{verified_month}-01')
        except ValueError:
            raise Problem(422, 'invalid_filter', 'Choose a month in YYYY-MM format.') from None
        if values.get('queue') != 'verified':
            raise Problem(422, 'invalid_filter', 'Choose the verified queue to filter by verification month.')
        scope = scope.filter(last_verification_at__year=month.year, last_verification_at__month=month.month)
    size = request.GET.get('limit', '8')
    if size not in {str(value) for value in PAGE_SIZE['enum']}:
        raise Problem(422, 'invalid_filter', 'Choose 8, 10, 15, 20 or 50 rows per page.')
    selected_state = request.GET.get('state')
    if selected_state is not None and selected_state not in STATE['enum']:
        raise Problem(422, 'invalid_filter', 'Choose one of the available work states.')
    if (values.get('queue', 'needs_me') not in factory_views.QUEUES or
            values.get('line', '') not in ('', *DEFINITIONS) or len(values.get('q', '')) > 120):
        raise Problem(422, 'invalid_filter', 'Check the work queue filters.')
    def include_row(work, row):
        return selected_state is None or state(work, row) == selected_state

    context = factory_views.queue_context(request.user, values, scope=scope, page_size=int(size),
                                          empty_page_lookahead=2, include_row=include_row)
    page = context['candidates']
    questions = context['payroll_questions']
    total = None
    if not context['limited']:
        if page.paginator.num_pages == 1:
            total = len(context['rows'])
        elif selected_state is None and values.get('queue') in ('mine', 'active'):
            total = page.paginator.count
    return {'items': [queue_summary(row, context['queue']) for row in context['rows']], 'page': page.number, 'page_size': int(size),
            'total': total, 'total_coverage': 'complete' if total is not None else 'incomplete',
            'next_page': page.next_page_number() if page.has_next() and page.number < PAGE['maximum'] else None,
            'limited': context['limited'] or questions['held'], 'as_of': context['as_of'], 'evaluated': context['evaluated'],
            'deferred': [{'id': work.pk, 'url': f'/api/v1/work/{work.pk}'} for work in context['deferred']],
            'payroll_questions': [
                {'case_id': row['case'].pk, 'id': row['id'], 'state': row['state'],
                 'url': f"/api/v1/projects/{row['case'].pk}/payroll/questions/{row['id']}"}
                for row in questions['rows'] if not project or str(row['case'].pk) == project],
            'lines': [{'key': key, 'title': title} for key, title in context['line_choices']]}


@endpoint(response=obj({'as_of': DATETIME, 'evaluated': COUNT, 'limited': BOOLEAN, 'verified_month': TEXT,
    'queues': array(obj({'key': choice(*factory_views.QUEUES), 'observed': COUNT, 'total': nullable(COUNT)})),
    'lines': array(obj({'key': choice(*DEFINITIONS), 'needs_person': COUNT, 'held': COUNT,
                       'open': COUNT, 'stopped': COUNT, 'verified': COUNT, 'verified_this_month': COUNT,
                       'stations': array(obj({'key': choice(*STATION_NAMES), 'count': COUNT, 'needs_person': COUNT}))}))}),
    query={'project': UUID, 'line': choice(*DEFINITIONS), 'q': {'type': 'string', 'maxLength': 120},
           'verified_month': {'type': 'string', 'pattern': r'^\d{4}-(0[1-9]|1[0-2])$'}},
    summary='Count authorised work with explicit coverage for the queue and line summaries')
def counts(request):
    actor = request.user
    line, project = request.GET.get('line'), request.GET.get('project')
    search = request.GET.get('q', '').strip()
    month = request.GET.get('verified_month') or timezone.localdate().strftime('%Y-%m')
    try:
        month_start = date.fromisoformat(f'{month}-01')
    except ValueError:
        raise Problem(422, 'invalid_filter', 'Choose a month in YYYY-MM format.') from None
    if (line and line not in DEFINITIONS) or len(search) > 120:
        raise Problem(422, 'invalid_filter', 'Check the work filters.')
    try:
        scope = discoverable_work(actor, case_id=project)
        if line:
            scope = scope.filter(definition=line)
        if search:
            scope = scope.filter(Q(request__reference__icontains=search) | Q(case__title__icontains=search) | Q(key__icontains=search))
        candidates = list(queue_observations(scope, actor).order_by('-updated_at', '-pk')[:51])
    except ValidationError:
        raise Problem(422, 'invalid_filter', 'Choose a valid project identifier.') from None
    observed = dict.fromkeys(factory_views.QUEUES, 0)
    lines = {}
    evaluated = 0
    as_of = timezone.now()
    deadline = monotonic() + 8
    for item in candidates[:50]:
        try:
            with observation_scope(), limit_queries(1400, deadline=deadline):
                row = factory_views.presentation(actor, item)
        except ReadLimit:
            continue
        evaluated += 1
        active = item.status not in ('verified', 'cancelled')
        memberships = {
            'needs_me': item.status != 'cancelled' and (item.status != 'verified' or item.definition != FINANCE_INVOICE)
                        and row['needs_me'],
            'waiting': item.status in ('waiting', 'waiting_effect') and not row['needs_me'],
            'mine': item.actor_id == actor.pk, 'active': active,
            'decisions': active and factory_views.decision_inbox_row(row),
            'exceptions': factory_views.exception_inbox_row(row, item.status),
            'unassigned': active and row['owner'] == 'Unassigned',
            'verified': item.status == 'verified' and not row.get('readiness_changed'),
        }
        for key, included in memberships.items():
            observed[key] += bool(included)
        line_counts = lines.setdefault(item.definition, {'needs_person': 0, 'held': 0, 'open': 0, 'stopped': 0,
            'verified': 0, 'verified_this_month': 0, 'stations': {key: {'count': 0, 'needs_person': 0} for key in STATION_NAMES}})
        line_counts['needs_person'] += bool(memberships['decisions'])
        line_counts['held'] += bool(memberships['exceptions'])
        line_counts['open'] += bool(memberships['active'])
        line_counts['verified'] += bool(memberships['verified'])
        line_counts['stopped'] += item.status in ('cancelled', 'followup_needed')
        line_counts['verified_this_month'] += bool(memberships['verified'] and item.last_verification_at and
            timezone.localdate(item.last_verification_at).replace(day=1) == month_start)
        station = line_counts['stations'][queue_station(item, row)]
        station['count'] += 1
        station['needs_person'] += bool(memberships['decisions'])
    limited = evaluated < len(candidates)
    return {'as_of': as_of, 'evaluated': evaluated, 'limited': limited, 'verified_month': month,
            'queues': [{'key': key, 'observed': count, 'total': None if limited else count}
                       for key, count in observed.items()],
            'lines': [{'key': key, **values, 'stations': [{'key': station, **counts}
                for station, counts in values['stations'].items()]} for key, values in sorted(lines.items())]}


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
    verification = verification_events().filter(activity__work_id=OuterRef('pk'))
    return get_object_or_404(factory_views.visible(actor, work_id=work_id).annotate(
        last_verification_at=Subquery(verification.values('created_at')[:1])))


@read_observation
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
            if work.definition == 'finance-bu/v1' and not (row['bu'].get('restricted') or row['bu'].get('recipient_only')):
                from apps.workflows.factory_bu_views import investigation_progress

                row['bu']['progress'] = investigation_progress(actor, work, state=row.get('bu_observation'))
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
    'planning/v1': ('planning-owner-requests',),
    'delivery-release/v1': ('release-register', 'planning-exit'),
    'delivery-handover/v1': ('support-receipt', 'support-replies', 'support-publication'),
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
    FINANCE_INVOICE: ('invoice-milestone-proof', 'invoice-draft-stop', 'invoice-preparation'),
    ACCOUNTING: ('accounting',),
    'rfp-response/v1': ('bid-answers', 'bid-pricing', 'bid-submission', 'bid-outcomes', 'security-estimate'),
}
OUTPUT_PANEL = {
    'delivery-go-live/v1': 'go-live-milestone',
    'rfp-response/v1': 'bid-submission',
    'finance-forecast/v1': 'forecast',
    'finance-payroll/v1': 'payroll-operations',
}


def panel_link(key, url):
    from .urls import PATH_PARAMETER

    try:
        match = resolve(url)
    except Resolver404:
        return {'key': key, 'url': url, 'contract_path': None}
    handlers = getattr(match.func, 'api_handlers', {})
    contract_path = '/' + PATH_PARAMETER.sub(r'{\2}', match.route) if 'GET' in handlers else None
    return {'key': key, 'url': url, 'contract_path': contract_path}


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
    return [panel_link(panel['key'], panel['url']) for panel in panels], (
        output if work.status == 'verified' and not row.get('readiness_changed') else None)


@endpoint(response=DETAIL, summary='Read the current work, independent tasks and permitted actions')
def detail(request, work_id):
    work, row, protected = observed_work(request.user, work_id)
    if protected.get('handoff'):
        url = request.path.rstrip('/') + '/department-handoff'
        return {
            **summary(row), 'revision': None, 'case_revision': None,
            'next_step': 'Open the department handoff to check its evidence and available decisions.',
            'department_handoff_url': url, 'panels': [panel_link('department-handoff', url)], 'tracking_url': None,
            'proofs_url': None,
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
            'reference': None, 'tracking_url': None, 'proofs_url': None,
            'state': 'waiting' if not aggregate or not aggregate['receipt_id'] else 'verified',
            'next_step': row['next_action'], 'blocker': '',
            'tasks': [], 'screens': [], 'actions': [], 'progress': None, 'aggregate': aggregate,
            'panels': [panel_link('aggregate', url)] if url else [], 'output_url': url, 'information': [], 'available_control': [],
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
    activity = next((row[key]['progress'] for key in (
        'accounting', 'bu', 'escalation', 'forecast', 'ledger', 'ppe', 'reporting', 'schedules',
    ) if row.get(key) and row[key].get('progress')), None)
    return {
        **summary(row), 'revision': work.revision, 'case_revision': work.case.revision,
        'tracking_url': f'/api/v1/work/{work.pk}/tracking',
        'proofs_url': f'/api/v1/work/{work.pk}/proofs',
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
        **({'current_activity': activity} if activity else {}),
    }


ATTEMPT = obj({'at': DATETIME, 'station': TEXT, 'status': TEXT, 'task_id': ID, 'actor': TEXT, 'reason': {'type': 'string'},
    'actor_kind': choice('person', 'worker'), 'entry_id': ID, 'evidence_id': nullable(ID)},
    optional=('task_id', 'actor', 'reason', 'evidence_id'))


@endpoint(response=obj({'items': array(ATTEMPT, limit=30), 'as_of': DATETIME, 'next_before': nullable(ID)}),
          query={'kind': choice('worker', 'decision', 'evidence'), 'before': ID},
          summary='Read work, decision or evidence history with a stable older-record cursor')
def history(request, work_id):
    from .intake_sources import positive_id

    work, _, protected = observed_work(request.user, work_id)
    kind = request.GET.get('kind', 'worker')
    before = positive_id(request, 'before')
    if kind not in ('worker', 'decision', 'evidence'):
        raise Problem(422, 'invalid_filter', 'Choose a listed history filter.')
    items = []
    next_before = None
    if not (protected.get('recipient_only') or protected.get('handoff')):
        from apps.core.templatetags.studio_ui import readable
        from apps.workflows.models import TaskEvent

        if kind == 'worker':
            attempts = FactoryAttempt.objects.filter(activity__work=work)
            if before:
                attempts = attempts.filter(pk__lt=before)
            rows = list(attempts.order_by('-pk').values_list('pk', 'created_at', 'activity__kind', 'phase')[:31])
            items = [{'entry_id': pk, 'at': at, 'station': readable(station), 'status': phase, 'actor_kind': 'worker'}
                     for pk, at, station, phase in rows[:30]]
            next_before = rows[29][0] if len(rows) > 30 else None
        else:
            events = TaskEvent.objects.filter(task__case=work.case, task__context__work=work.pk,
                                              task__factory_key__startswith=f'factory:{work.pk}:')
            if kind == 'decision':
                events = events.filter(data__verdict__in=['approve', 'return', 'reject'])
            else:
                events = events.filter(action__in=['factory.information_received', 'factory.information_verified', 'factory.packet_superseded'])
            if before:
                events = events.filter(pk__lt=before)
            batch = list(events.select_related('task', 'actor').order_by('-pk')[:31])
            next_before = batch[29].pk if len(batch) > 30 else None
            events = batch[:30]
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
                entry = {'entry_id': event.pk, 'actor_kind': 'person', 'at': event.created_at,
                         'station': readable(event.task.kind), 'task_id': event.task_id,
                         'status': event.data['verdict'] if kind == 'decision' else readable(event.action.split('.')[-1]),
                         'actor': event.actor.get_full_name() or event.actor.get_username()}
                review = exact_reviews.get(event.data.get('native_review'))
                if review and review.actor_id == event.actor_id and review.verdict == event.data['verdict'] and review.evidence_id in proofs:
                    entry.update(reason=review.note, evidence_id=review.evidence_id)
                if kind == 'evidence' and type(event.data.get('evidence')) is int and event.data['evidence'] in proofs:
                    entry['evidence_id'] = event.data['evidence']
                items.append(entry)
    return {'items': items, 'as_of': timezone.now(), 'next_before': next_before}


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
    'recipient': nullable(TEXT), 'preparation_id': ID, 'basis': TEXT, 'prepared_by': TEXT,
    'prepared_at': DATETIME,
    'sources': array(obj({'id': ID, 'version': REVISION, 'kind': TEXT, 'sha256': TEXT})),
})


@endpoint(response=obj({'task': TASK, 'work_id': ID, 'label': TEXT, 'invoice_packet': nullable(PACKET),
    'decision_hold_code': nullable(choice('task_closed', 'claimed_by_other', 'review_needs_update', 'not_assigned',
                                           'decision_unavailable')),
    'review_stations_url': nullable(TEXT),
    'changes_from_previous': nullable(obj({'invoice_id': ID, 'version': REVISION, 'changes': array(obj({
        'field': choice('reference', 'amount', 'currency', 'amount_basis', 'due_date'),
        'before': nullable(TEXT), 'after': nullable(TEXT),
    }))})),
    'review_evidence': array(obj({'id': ID, 'version': ID, 'source': TEXT, 'sha256': TEXT})),
    'recipient_change': obj({'earlier': nullable(TEXT), 'current': nullable(TEXT)})}, optional=('recipient_change',)),
          summary='Read the exact current Finance task and permitted invoice packet')
def task(request, task_id):
    work, _ = review_task(request.user, task_id)
    work, row, _ = observed_work(request.user, work.pk)
    selected = next((item for item in row['tasks'] if item.pk == task_id), None)
    if selected is None:
        raise Http404
    fields = None
    changes = None
    recipient_change = None
    if work.definition == FINANCE_INVOICE:
        from apps.workflows.factory_invoice_review import context

        invoice_context = context(request.user, row)
        if selected.can_read_invoice_destination and invoice_context:
            recipient_change = invoice_context['recipient_change']
        packet = selected.display_packet
        if packet and work.invoice_id and 'preparation' in packet:
            from apps.finance.fixed_charge import preparation_access
            from apps.finance.models import Invoice

            exact = Invoice.objects.filter(case_id=work.case_id, pk=packet['invoice'],
                preparation_id=packet['preparation']).select_related('preparation', 'actor').first()
            if exact is not None:
                try:
                    preparation_access(request.user, exact.preparation)
                except (ValidationError, PermissionDenied):
                    exact = None
        else:
            exact = None
        if exact:
            fields = {'invoice_id': packet['invoice'], 'version': packet['version'], 'sha256': packet['payload_hash'],
                      'amount': packet['amount'], 'currency': packet['currency'], 'preparation_id': packet['preparation'],
                      'recipient': getattr(selected, 'recipient_name', None),
                      'basis': exact.amount_basis,
                      'prepared_by': exact.actor.get_full_name() or exact.actor.get_username(),
                      'prepared_at': exact.created_at,
                      'sources': [{'id': item.pk, 'version': item.version, 'kind': item.kind, 'sha256': item.sha256}
                                  for item in selected.source_records]}
            previous = Invoice.objects.filter(case_id=work.case_id, obligation_key=exact.obligation_key,
                pk__lt=exact.pk).select_related('preparation').order_by('-pk').first()
            if previous:
                try:
                    preparation_access(request.user, previous.preparation)
                except (PermissionDenied, ValidationError):
                    pass
                else:
                    comparison = []
                    for field in ('reference', 'amount', 'currency', 'amount_basis', 'due_date'):
                        old, new = getattr(previous, field), getattr(exact, field)
                        if old != new:
                            comparison.append({'field': field, 'before': str(old) if old is not None else None,
                                               'after': str(new) if new is not None else None})
                    changes = {'invoice_id': previous.pk, 'version': previous.version, 'changes': comparison}
    from apps.core.evidence_access import public_evidence
    from apps.core.models import Evidence

    info = task_data(selected, request.user)
    proofs = []
    if info['can_decide'] and fields:
        proofs = list(public_evidence(Evidence.objects.filter(case=work.case, kind='invoice_review'))
                      .order_by('-pk').values('id', 'version', 'source', 'sha256'))
    hold = None
    if not (info['can_decide'] or info['can_claim']):
        if selected.status != 'open':
            hold = 'task_closed'
        elif selected.claimed_by_id and selected.claimed_by_id != request.user.pk:
            hold = 'claimed_by_other'
        elif row.get('review_needs_update'):
            hold = 'review_needs_update'
        elif row.get('routing', {}).get('eligible_principals') and request.user.pk not in row['routing']['eligible_principals']:
            hold = 'not_assigned'
        else:
            hold = 'decision_unavailable'
    return {'task': info, 'work_id': work.pk, 'review_evidence': proofs, 'decision_hold_code': hold,
            'review_stations_url': f'/api/v1/work/{work.pk}/accounting' if work.definition == ACCOUNTING else None,
            'changes_from_previous': changes,
            'label': getattr(selected, 'label', 'Finance review'), 'invoice_packet': fields,
            **({'recipient_change': recipient_change} if recipient_change is not None else {})}


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

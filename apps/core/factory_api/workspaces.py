from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import Http404
from django.middleware.csrf import get_token
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from apps.agents.assistant import PERSONAS, cases_for
from apps.core import client_contacts, project_journey, workbench
from apps.core.design_views import discoverable_work
from apps.core.models import ClientContactRevision
from apps.core.presentation import workspace_name
from apps.identity.factory_access import project_actions, project_cases
from apps.finance import hr_workspace, month_end, project_money
from apps.identity.services import active_case_grants
from apps.policy.role_assignments import invoice_delegation_source
from apps.workflows.factory_definitions import DEFINITIONS
from apps.workflows.factory_views import intake_options

from .http import BOOLEAN, DATETIME, ID, REVISION, TEXT, UUID, Problem, array, choice, endpoint, nullable, obj
from .work import PAGE, page_number
from .role_work import POSITION


LINK = obj({'key': TEXT, 'title': TEXT, 'django_url': TEXT})
DESTINATION = obj({**LINK['properties'], 'url': TEXT, 'available': BOOLEAN})
DATES = {'type': 'string', 'format': 'date'}
MONEY = nullable({'type': 'string'})
WORKSPACE = obj({'case_id': UUID, 'title': TEXT, 'revision': REVISION, 'sample': BOOLEAN})
PROJECT_ROW = obj({
    **WORKSPACE['properties'], 'manager': nullable(TEXT), 'lifecycle': nullable(TEXT), 'phase': nullable(TEXT),
    'reviews': nullable({'type': 'integer', 'minimum': 0}), 'exceptions': nullable({'type': 'integer', 'minimum': 0}),
    'next_milestone': nullable(obj({'name': TEXT, 'due': nullable(DATES)})),
    'django_url': TEXT,
})


def workspace(case):
    return {'case_id': case.pk, 'title': workspace_name(case), 'revision': case.revision, 'sample': case.synthetic}


def project_for(actor, case_id):
    return get_object_or_404(project_cases(actor), pk=case_id, kind='project')


@endpoint(response=obj({
    'name': TEXT, 'work_desk_url': TEXT, 'destinations': array(DESTINATION), 'startable_lines': array(TEXT),
    'csrf_token': TEXT, 'assistant_agents': array(choice(*PERSONAS)), 'positions': array(POSITION, limit=50),
}), summary='Bootstrap the same-origin Django session')
def me(request):
    from django.conf import settings
    from apps.core import client_directory
    from apps.identity.role_work import workspace_positions

    actor = request.user
    positions = workspace_positions(actor)
    personas = [name for name in PERSONAS if cases_for(actor, name).exists()]
    destinations = (
        ('my_work', 'My work', 'home', '/my-work', True),
        ('projects', 'Projects', 'workspace_overview', '/projects', project_cases(actor).exists()),
        ('overview', 'Overview', 'design_overview', '/overview', True),
        ('setup', 'Setup', 'design_setup', '/setup',
         any(position['role'] == 'admin' for position in positions) or workbench.granted(actor, ['policy.read']).exists()),
        ('clients', 'Clients', 'design_clients', '/clients',
         client_directory.active_links(client_directory.visible_links(actor)).exists()),
        ('assistant', 'Assistant', 'design_agents', '/assistant', True),
    )
    return {
        'name': actor.get_full_name() or actor.get_username(),
        'work_desk_url': reverse('connected_factory_work') if settings.PSL_DJANGO_UI else '/my-work',
        'destinations': [{'key': key, 'title': label, 'url': url, 'available': available,
                          'django_url': reverse(route) + ('?kind=project' if key == 'projects' else '')
                          if settings.PSL_DJANGO_UI else url}
                         for key, label, route, url, available in destinations],
        'startable_lines': [line['definition'] for line in intake_options(actor)],
        'csrf_token': get_token(request), 'assistant_agents': personas, 'positions': positions,
    }


@endpoint(response=obj({'items': array(PROJECT_ROW), 'next_cursor': nullable(TEXT), 'as_of': DATETIME,
                        'totals': obj(dict.fromkeys(('all', 'active', 'closed'), {'type': 'integer', 'minimum': 0}))}),
          query={'q': {'type': 'string', 'maxLength': 120}, 'status': choice('all', 'active', 'closed'),
                 'cursor': {**TEXT, 'maxLength': 4096}},
          summary='List authorised projects with current bounded summaries')
def projects(request):
    status = request.GET.get('status', 'all')
    if status not in {'all', 'active', 'closed'}:
        raise Problem(422, 'invalid_filter', 'Choose a valid project status.')
    value = workbench.discover(request.user, kind='project', q=request.GET.get('q', ''),
                               cursor=request.GET.get('cursor'), lifecycle='' if status == 'all' else status, include_counts=True)
    return {'items': [
        {**workspace(row['case']), 'manager': row['manager'], 'lifecycle': row['lifecycle'],
         'phase': row['phase'], 'reviews': row['reviews'], 'exceptions': row['exceptions'],
         'next_milestone': row['milestone'],
         'django_url': reverse('design_project', args=[row['case'].pk])} for row in value['project_rows']
    ], 'next_cursor': value['next_cursor'], 'as_of': timezone.now(), 'totals': value['totals']}


JOURNEY_ROW = obj({'id': ID, 'line': TEXT, 'reference': nullable({'type': 'string'}), 'state': TEXT,
                   'started': DATETIME, 'updated': DATETIME, 'django_url': TEXT})


COUNTS = {'type': 'integer', 'minimum': 0}
TAB_LINK = obj({**LINK['properties'], 'api_url': TEXT})
JOURNEY_FACTS = obj({'total': COUNTS, 'waiting': COUNTS, 'stopped': COUNTS,
    'finance': nullable(obj({'stages': nullable(COUNTS), 'delivered': nullable(COUNTS),
        'next': nullable(TEXT), 'limited': BOOLEAN})),
    'engagement': nullable(obj({'route': TEXT, 'reference': TEXT, 'manager': nullable(TEXT)}))})


@endpoint(response=obj({
    **WORKSPACE['properties'], 'tabs': array(TAB_LINK),
    'items': array(obj(JOURNEY_ROW['properties'] | {'api_url': TEXT})), 'page': ID,
    'next_page': nullable(ID), 'as_of': DATETIME, 'facts': JOURNEY_FACTS,
    'assistant': array(obj({'agent': choice(*PERSONAS), 'scope': {'const': 'project'}, 'api_url': TEXT})),
}), query={'page': PAGE}, summary='Read project journey facts, typed work links and exact Assistant launch choices')
def project(request, case_id):
    case = get_object_or_404(project_cases(request.user), pk=case_id)
    grants = project_actions(request.user, case)
    journey = project_journey.work_timeline(discoverable_work(request.user, case_id=case_id), page_number(request))
    page = journey['page']
    prefix = f'/api/v1/projects/{case.pk}'
    finance = project_journey.finance_facts(request.user, case) if 'finance.read' in grants else None
    engagement = project_journey.engagement_facts(request.user, case) if 'engagement.read' in grants else None
    return {**workspace(case), 'tabs': [
        {'key': tab['key'], 'title': tab['title'], 'django_url': tab['url'],
         'api_url': prefix if tab['key'] == 'journey' else f"{prefix}/{tab['key']}"} for tab in project_journey.tabs(case, grants)
    ], 'items': [{**row, 'django_url': reverse('factory_detail', args=[row['id']]), 'api_url': f"/api/v1/work/{row['id']}"}
                  for row in journey['items']], 'page': page.number,
        'next_page': page.next_page_number() if page.has_next() else None, 'as_of': journey['as_of'],
        'facts': {**{key: journey[key] for key in ('total', 'waiting', 'stopped')},
                  'finance': {**{key: finance.get(key) for key in ('stages', 'delivered', 'next')},
                              'limited': finance.get('limited', False)} if finance is not None else None,
                  'engagement': {**engagement, 'manager': engagement.get('manager')} if engagement else None},
        'assistant': [{'agent': key, 'scope': 'project', 'api_url': '/api/v1/assistant/conversations'}
                      for key in PERSONAS if cases_for(request.user, key).filter(pk=case.pk).exists()]}


SECTION_ITEM = obj({
    'title': TEXT, 'state': TEXT, 'state_code': TEXT, 'detail': nullable(TEXT), 'at': nullable(DATETIME), 'due': nullable(DATETIME),
    'severity': nullable(TEXT), 'owner': nullable(TEXT), 'django_url': TEXT, 'record_id': ID, 'api_url': nullable(TEXT),
    'reference': nullable(TEXT), 'age_days': nullable(COUNTS),
    'origin_meeting': nullable(obj({'id': ID, 'reference': TEXT, 'at': DATETIME})),
})
SECTION = obj({'key': TEXT, 'title': TEXT, 'items': array(SECTION_ITEM, limit=25), 'page': ID, 'has_more': BOOLEAN, 'django_url': TEXT,
               'api_url': nullable(TEXT), 'total': COUNTS,
               'counts': nullable(obj({'overdue': COUNTS, 'unassigned': COUNTS, 'total': COUNTS}))})
PROJECT_TABS = ('milestones', 'documents', 'registers', 'actions')


@endpoint(response=obj({'case_id': UUID, 'destinations': array(obj({
    **LINK['properties'], 'description': TEXT,
}))}), summary='Read the permitted HR handoff and follow-up destinations')
def hr(request, case_id):
    case = project_for(request.user, case_id)
    from apps.identity.services import require
    require(request.user, case, 'hrfinance.read')
    return {'case_id': case.pk, 'destinations': hr_workspace.destinations(request.user, case)}


@endpoint(response=obj({'case_id': UUID, 'tab': TEXT, 'sections': array(SECTION), 'as_of': DATETIME}),
          query={'q': {'type': 'string', 'maxLength': 120}, 'page': PAGE, 'state': TEXT, 'owner': TEXT, 'severity': TEXT},
          path_parameters={'tab': choice(*PROJECT_TABS)},
          summary='Read permitted project milestones, evidence, registers or actions')
def project_tab(request, case_id, tab):
    if tab not in PROJECT_TABS:
        raise Http404
    case = get_object_or_404(project_cases(request.user), pk=case_id)
    grants = project_actions(request.user, case)
    form = project_journey.filters(case, tab, grants, request.GET)
    query = request.GET.get('q', '').strip()
    if not form.is_valid() or len(query) > 120:
        raise Problem(422, 'invalid_filter', 'Check the project tab filters.')
    page = page_number(request)
    from django.http import QueryDict

    pages = QueryDict(mutable=True)
    for route in ('case', 'documents', 'meetings', 'issues', 'escalations', 'changes', 'emergencies', 'rfp'):
        pages[f'{route}-page'] = page
    sections = project_journey.sections(request.user, case, tab, grants, query, pages, form.cleaned_data)
    prefix = f'/api/v1/projects/{case.pk}'
    collection = {'issues-page': 'issues', 'escalations-page': 'escalation-register', 'changes-page': 'ordinary-changes',
                  'emergencies-page': 'emergency-intake', 'rfp-page': 'received-bids', 'case-page': 'milestones/completions',
                  'meetings-page': 'meetings', 'documents-page': 'templates'}

    def item_url(section, item):
        pk = item['record_id']
        if item.get('assignment_id'):
            return f"/api/v1/role-work/{item['assignment_id']}"
        return {'issues-page': f'{prefix}/issues/{pk}', 'case-page': f'{prefix}/milestones/{pk}',
                'meetings-page': f'{prefix}/actions/{pk}',
                'escalations-page': f'{prefix}/escalation-register/{pk}',
                'rfp-page': f"/api/v1/received-bids/{case.pk}/receipts/{item.get('receipt_id')}",
                'changes-page': f"{prefix}/change-versions/{item.get('version_id')}",
                'emergencies-page': f"{prefix}/emergency-intake/{item.get('version_id')}"}.get(section['page_key'])

    return {'case_id': case.pk, 'tab': tab, 'sections': [
        {'key': section['page_key'].removesuffix('-page'), 'title': section['title'],
         'django_url': section['url'], 'page': section['page'].number, 'total': section['page'].paginator.count,
         'counts': section.get('counts'),
         'api_url': ('/api/v1/received-bids' if section['page_key'] == 'rfp-page'
                     else f"{prefix}/{collection[section['page_key']]}"),
         'has_more': section['page'].has_next(), 'items': [
             {'title': item['title'], 'state': item['state'], 'state_code': item['state_code'], 'detail': item.get('detail') or None,
              'at': item.get('at'), 'due': item.get('due'), 'severity': item.get('severity') or None,
              'reference': item.get('reference'), 'age_days': item.get('age_days'), 'origin_meeting': item.get('origin_meeting'),
              'owner': item.get('owner') or None, 'django_url': item.get('url', section['url']),
              'record_id': item['record_id'], 'api_url': item_url(section, item)}
             for item in section['items']
         ]} for section in sections
    ], 'as_of': timezone.now()}


INVOICE = obj({'id': ID, 'reference': TEXT, 'version': REVISION, 'currency': TEXT,
               'paid': MONEY, 'owed': MONEY, 'status': TEXT, 'at': DATETIME, 'api_url': TEXT})
MONEY_SOURCE = obj({'label': TEXT, 'django_url': TEXT, 'at': nullable(DATETIME), 'kind': nullable(TEXT),
                   'record_id': nullable(ID), 'reference': nullable(TEXT), 'api_url': nullable(TEXT)})
STAGE_CHANGE = obj({'link_id': ID, 'version_id': ID, 'reference': TEXT, 'number': REVISION, 'note': TEXT,
                    'plan_id': ID, 'additional_amount': {'type': 'null'}, 'api_url': TEXT})
FIGURE = obj({
    'key': TEXT, 'label': TEXT, 'amount': MONEY, 'currency': TEXT, 'due_date': nullable(DATES),
    'milestone_id': nullable(ID), 'stage_position': nullable(ID),
    'completed_at': nullable(DATETIME), 'contract_stage': BOOLEAN, 'missing_reason': nullable(TEXT),
    'invoices': array(INVOICE), 'sources': array(MONEY_SOURCE), 'changes': array(STAGE_CHANGE, limit=12),
})


def money_source(case, source):
    prefix = f'/api/v1/projects/{case.pk}'
    kind, pk = source.get('record_kind'), source.get('record_id')
    api = {'invoice': f'{prefix}/billing-invoices/{pk}', 'agreement': f'{prefix}/commercial-response',
           'correction': f'{prefix}/financial-corrections/invoice/{pk}', 'cash-lot': f'{prefix}/cash-lots/{pk}',
           'reviewed-terms': f'/api/v1/setup/{case.pk}/policy-configurations?component=D12.stage_terms',
           'milestone': f'{prefix}/milestones/{pk}', 'preparation': f'{prefix}/intake-sources?line=pmo-finance%2Fv1'}
    return {'label': source['label'], 'django_url': source['url'], 'at': source.get('at'),
            'kind': kind, 'record_id': pk, 'reference': source.get('reference'), 'api_url': api.get(kind)}


@endpoint(response=obj({'items': array(FIGURE), 'limited': BOOLEAN, 'as_of': DATETIME, 'finance_url': TEXT}),
          query={'figure': {**TEXT, 'maxLength': 80}}, summary='Read contract and invoice figures with native provenance')
def money(request, case_id):
    case = get_object_or_404(workbench.granted(request.user, ['finance.read']), pk=case_id, kind='project')
    key = request.GET.get('figure', '')
    if len(key) > 80:
        raise Problem(422, 'invalid_filter', 'Choose an available figure.')
    from apps.pmo.change_stage_links import READ_ACTIONS

    grants = {action for _, action in active_case_grants(request.user, [case.pk], actions=READ_ACTIONS)}
    value = project_money.projection(request.user, case, key, include_change_links=READ_ACTIONS <= grants)
    rows = [value['selected']] if key and value.get('selected') else value['rows']
    positions = {stage: i for i, stage in enumerate(project_money.STAGES, start=1)}
    return {'items': [
        {'key': row['key'], 'label': row['label'], 'amount': str(row['amount']) if row['amount'] is not None else None,
         'currency': row['currency'], 'due_date': row['due_date'], 'contract_stage': row['contract_stage'],
         'milestone_id': row['completion'].pk if row['completion'] else None,
         'stage_position': positions.get(row['key']) if row['contract_stage'] else None,
         'completed_at': row['completion'].completed_at if row['completion'] else None,
         'missing_reason': row['missing_reason'], 'invoices': [
             {**{field: invoice[field] for field in ('reference', 'version', 'currency', 'at', 'status')},
              'id': invoice['invoice'].pk, 'paid': str(invoice['paid']) if invoice['paid'] is not None else None,
              'api_url': f"/api/v1/projects/{case.pk}/billing-invoices/{invoice['invoice'].pk}",
              'owed': str(invoice['owed']) if invoice['owed'] is not None else None}
             for invoice in row['invoices']
         ], 'sources': [money_source(case, source) for source in row['sources']],
         'changes': [{**change, 'additional_amount': None, 'api_url': f"/api/v1/projects/{case.pk}/change-versions/{change['version_id']}"}
                     for change in row.get('change_links', [])]}
        for row in rows
    ], 'limited': value.get('limited', False) or value.get('change_links_limited', False), 'as_of': timezone.now(),
        'finance_url': reverse('finance_settlement', args=[case.pk])}


@endpoint(response=obj({'id': ID, 'reference': TEXT, 'version': REVISION, 'issued_at': nullable(DATETIME),
    'delivered_at': nullable(DATETIME), 'currency': TEXT, 'amount': TEXT, 'paid': MONEY, 'owed': MONEY,
    'preparation_id': ID, 'issue_id': nullable(ID), 'delivery_id': nullable(ID),
    'payments_url': nullable(TEXT), 'corrections_url': TEXT}),
    summary='Read the exact permitted invoice, issued and delivered records, and current amounts')
def billing_invoice(request, case_id, invoice_id):
    from apps.core.read_budget import ReadBudget, limit_queries
    from apps.finance.fixed_charge import preparation_access
    from apps.finance.models import Invoice

    actor = request.user
    case = get_object_or_404(workbench.granted(actor, ['finance.read']), pk=case_id, kind='project')
    row = get_object_or_404(Invoice.objects.select_related(
        'preparation__coverage', 'preparation__handoff__milestone', 'invoiceissue', 'invoicedelivery'), case=case, pk=invoice_id)
    with limit_queries(350):
        preparation_access(actor, row.preparation)
        paid, owed, _, _ = project_money.balance(row, ReadBudget())
    issue = getattr(row, 'invoiceissue', None)
    delivery = getattr(row, 'invoicedelivery', None)
    root = f'/api/v1/projects/{case.pk}'
    return {'id': row.pk, 'reference': row.reference, 'version': row.version, 'currency': row.currency,
            'issued_at': issue.created_at if issue else None, 'delivered_at': delivery.created_at if delivery else None,
            'amount': str(row.amount), 'paid': str(paid) if paid is not None else None,
            'owed': str(owed) if owed is not None else None, 'preparation_id': row.preparation_id,
            'issue_id': issue.pk if issue else None, 'delivery_id': delivery.pk if delivery else None,
            'payments_url': f'{root}/invoices/{issue.pk}/payments' if issue else None,
            'corrections_url': f'{root}/financial-corrections'}


@endpoint(response=obj({
    'as_of': DATETIME, 'lines': array(obj({'key': TEXT, 'title': TEXT, 'total': {'type': 'integer', 'minimum': 0}})),
}), summary='Read recorded work counts by authorised factory line')
def overview(request):
    work = discoverable_work(request.user).exclude(status__in=['verified', 'cancelled'])
    from django.db.models import Count

    counts = work.order_by().values('definition').annotate(total=Count('pk'))
    return {'as_of': timezone.now(), 'lines': sorted(
        ({'key': row['definition'], 'title': DEFINITIONS[row['definition']]['title'], 'total': row['total']}
         for row in counts), key=lambda line: line['title'])}


CONTACT = obj({
    'contact_id': ID, 'version': REVISION, 'purpose': choice('project', 'billing'),
    'customer': {'type': 'string'}, 'client_name': TEXT, 'name': TEXT, 'email': {'type': 'string'},
    'role': {'type': 'string'},
})


def contact(record):
    return {'contact_id': record.pk, 'version': record.number, **{
        key: getattr(record, key) for key in ('purpose', 'customer', 'client_name', 'name', 'email', 'role')
    }}


@endpoint(response=obj({**WORKSPACE['properties'], 'contacts': array(CONTACT), 'django_url': TEXT}),
          summary='Read authorised current client contacts for a workspace')
def client(request, case_id):
    case = project_for(request.user, case_id)
    contacts, permitted = [], False
    for purpose in client_contacts.READ:
        try:
            client_contacts.authorize(request.user, case, purpose)
        except (PermissionDenied, ValidationError):
            continue
        permitted = True
        rows = (ClientContactRevision.objects.filter(case=case, purpose=purpose)
                .order_by('customer', '-number').distinct('customer')[:100])
        contacts.extend(map(contact, rows))
    if not permitted:
        raise Http404
    return {**workspace(case), 'contacts': contacts, 'django_url': reverse('design_client_project', args=[case.pk])}


@endpoint(method='POST', request=obj({
    'purpose': choice('project', 'billing'), 'customer': {'type': 'string', 'maxLength': 160},
    'client_name': {**TEXT, 'maxLength': 160}, 'name': {**TEXT, 'maxLength': 160},
    'email': {'type': 'string', 'maxLength': 254}, 'role': {'type': 'string', 'maxLength': 100},
    'evidence_id': ID, 'expected_revision': REVISION,
}), response=CONTACT, summary='Record a versioned client contact with the exact source')
def save_contact(request, case_id, *, body):
    case = project_for(request.user, case_id)
    purpose = body['purpose']
    client_contacts.authorize(request.user, case, purpose)
    values = {key: body[key] for key in ('customer', 'client_name', 'name', 'email', 'role')}
    form = client_contacts.ContactForm(case, purpose, {
        **values, 'evidence': body['evidence_id'], 'revision': body['expected_revision'],
    })
    if not form.is_valid():
        raise Problem(422, 'invalid_input', 'Review the contact fields and selected proof.',
                      fields=[{'name': key, 'message': errors[0]} for key, errors in form.errors.items()])
    return contact(client_contacts.save(request.user, case, purpose, form.cleaned_data))


MONTH = {'type': 'string', 'pattern': '^[1-9][0-9]{3}-(0[1-9]|1[0-2])$'}


CLOSE = obj({
    'month': MONTH, 'as_of': DATETIME, 'workspace': WORKSPACE, 'stations': array(LINK),
    'cash': array(obj({'currency': TEXT, 'basis': TEXT, 'amount': TEXT})), 'cash_unavailable': BOOLEAN,
    'periods': array(obj({'entity': TEXT, 'currency': TEXT, 'at': DATETIME, 'status': TEXT,
                          'values': array(obj({'label': TEXT, 'value': MONEY, 'unit': TEXT}))})),
    'receivables': obj({'status': TEXT, 'cutoff': nullable(DATES), 'captured_date': nullable(DATES),
                        'snapshot_id': nullable(ID)}), 'can_capture': BOOLEAN,
})


@endpoint(response=CLOSE, query={'month': MONTH}, summary='Read the reviewed month-end facts and capture dates for a workspace')
def close(request, case_id):
    from apps.identity.services import require

    case = project_for(request.user, case_id)
    require(request.user, case, 'finance.read')
    _, month = month_end.selection(request)
    if month is None:
        raise Problem(422, 'invalid_filter', 'Choose a reporting month.')
    return close_payload(month, month_end.workspace_close(request.user, case, month), timezone.now())


def close_payload(month, data, as_of):
    receivables = data['receivables']
    return {'month': month, 'as_of': as_of, 'workspace': workspace(data['case']),
            'stations': [{'key': str(index), 'title': label, 'django_url': url}
                         for index, (url, label) in enumerate(data['stations'], start=1)],
            'cash': [{'currency': currency, 'basis': basis, 'amount': str(amount)}
                     for currency, basis, amount in data['cash']], 'cash_unavailable': data.get('cash_unavailable', False),
            'periods': [{**row, 'values': [
                {**figure, 'value': str(figure['value']) if figure['value'] is not None else None}
                for figure in row['values']
            ]} for row in data['periods']],
            'receivables': {'status': receivables['status'], 'cutoff': receivables.get('cutoff'),
                            'captured_date': receivables.get('date'), 'snapshot_id': receivables.get('pk')},
            'can_capture': data.get('can_capture', False)}


@endpoint(response=obj({'items': array(obj({
    'role': TEXT, 'principal_id': ID, 'delegate_id': ID, 'valid_from': DATETIME, 'valid_until': DATETIME,
    'principal': nullable(TEXT), 'delegate': nullable(TEXT), 'reason': nullable(TEXT),
    'status': choice('scheduled', 'current_window', 'expired'),
})), 'as_of': DATETIME, 'django_url': TEXT, 'configuration_id': nullable(ID)}),
    summary='Read the currently accessible delegation assignments')
def delegations(request, case_id):
    from apps.policy.delegation_views import SUBMISSION_ACTION

    case = project_for(request.user, case_id)
    configuration, rows = invoice_delegation_source(request.user, case)
    ids = {row[key] for row in rows for key in ('principal_id', 'delegate_id')}
    people = get_user_model().objects.filter(pk__in=ids, grant__case=case, grant__active=True,
                                             grant__action='case.read').in_bulk()
    now = timezone.now()
    items = []
    for row in rows:
        start, end = parse_datetime(row['valid_from']), parse_datetime(row['valid_until'])
        reason = configuration.case.audit.filter(action=SUBMISSION_ACTION, data__configuration=configuration.pk,
            data__intent__contains={
            key: row[key] for key in ('role', 'principal_id', 'delegate_id', 'valid_from', 'valid_until')
        }, data__intent__reason__isnull=False).order_by('-pk').values_list('data__intent__reason', flat=True).first()
        names = {key: people.get(row[f'{key}_id']) for key in ('principal', 'delegate')}
        items.append({**{key: row[key] for key in ('role', 'principal_id', 'delegate_id', 'valid_from', 'valid_until')},
                      **{key: user.get_full_name() or user.get_username() if user else None for key, user in names.items()},
                      'reason': reason,
                      'status': 'expired' if now >= end else 'scheduled' if now < start else 'current_window'})
    return {'items': items, 'as_of': now, 'configuration_id': configuration.pk if configuration else None,
            'django_url': reverse('design_delegation', args=[case.pk])}

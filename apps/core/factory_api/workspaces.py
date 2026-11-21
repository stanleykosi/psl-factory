from django.core.exceptions import PermissionDenied, ValidationError
from django.http import Http404
from django.middleware.csrf import get_token
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils import timezone

from apps.agents.assistant import PERSONAS, cases_for
from apps.core import client_contacts, project_journey, workbench
from apps.core.design_views import discoverable_work
from apps.core.models import ClientContactRevision
from apps.core.presentation import workspace_name
from apps.identity.factory_access import project_actions, project_cases
from apps.finance import hr_workspace, month_end, project_money
from apps.identity.services import active_case_grants, visible_cases
from apps.policy.delegation_views import assignments
from apps.workflows.factory_definitions import DEFINITIONS
from apps.workflows.factory_views import intake_options

from .http import BOOLEAN, DATETIME, ID, REVISION, TEXT, UUID, Problem, array, choice, endpoint, nullable, obj
from .work import PAGE, page_number


LINK = obj({'key': TEXT, 'title': TEXT, 'django_url': TEXT})
DATES = {'type': 'string', 'format': 'date'}
MONEY = nullable({'type': 'string'})
WORKSPACE = obj({'case_id': UUID, 'title': TEXT, 'revision': REVISION, 'sample': BOOLEAN})
PROJECT_ROW = obj({
    **WORKSPACE['properties'], 'manager': nullable(TEXT), 'lifecycle': nullable(TEXT), 'phase': nullable(TEXT),
    'reviews': nullable({'type': 'integer', 'minimum': 0}), 'exceptions': nullable({'type': 'integer', 'minimum': 0}),
    'django_url': TEXT,
})


def workspace(case):
    return {'case_id': case.pk, 'title': workspace_name(case), 'revision': case.revision, 'sample': case.synthetic}


def project_for(actor, case_id):
    return get_object_or_404(visible_cases(actor), pk=case_id, kind='project')


@endpoint(response=obj({
    'name': TEXT, 'destinations': array(LINK), 'startable_lines': array(TEXT),
    'csrf_token': TEXT, 'assistant_agents': array(choice(*PERSONAS)),
}), summary='Bootstrap the same-origin Django session')
def me(request):
    from apps.identity.primary_roles import administered_projects
    from apps.identity.teams import memberships

    actor = request.user
    destinations = [('my_work', 'My work', 'home'), ('projects', 'Projects', 'workspace_overview'),
                    ('overview', 'Overview', 'design_overview'), ('setup', 'Setup', 'design_setup'),
                    ('clients', 'Clients', 'design_clients'), ('assistant', 'Assistant', 'design_agents')]
    personas = [name for name in PERSONAS if cases_for(actor, name).exists()]
    if memberships(actor).exists() or administered_projects(actor).exists():
        role_dashboard = ('role_dashboard', 'Role assignments', 'role_dashboard')
        destinations.insert(0, role_dashboard)
    return {
        'name': actor.get_full_name() or actor.get_username(),
        'destinations': [{'key': key, 'title': label,
                          'django_url': reverse(route) + ('?kind=project' if key == 'projects' else '')}
                         for key, label, route in destinations],
        'startable_lines': [line['definition'] for line in intake_options(actor)],
        'csrf_token': get_token(request), 'assistant_agents': personas,
    }


@endpoint(response=obj({'items': array(PROJECT_ROW), 'next_cursor': nullable(TEXT), 'as_of': DATETIME}),
          query={'q': {'type': 'string', 'maxLength': 120}, 'status': choice('all', 'active', 'closed'),
                 'cursor': {**TEXT, 'maxLength': 4096}},
          summary='List authorised projects with current bounded summaries')
def projects(request):
    status = request.GET.get('status', 'all')
    if status not in {'all', 'active', 'closed'}:
        raise Problem(422, 'invalid_filter', 'Choose a valid project status.')
    value = workbench.discover(request.user, kind='project', q=request.GET.get('q', ''),
                               cursor=request.GET.get('cursor'), lifecycle='' if status == 'all' else status)
    return {'items': [
        {**workspace(row['case']), 'manager': row['manager'], 'lifecycle': row['lifecycle'],
         'phase': row['phase'], 'reviews': row['reviews'], 'exceptions': row['exceptions'],
         'django_url': reverse('design_project', args=[row['case'].pk])} for row in value['project_rows']
    ], 'next_cursor': value['next_cursor'], 'as_of': timezone.now()}


JOURNEY_ROW = obj({'id': ID, 'line': TEXT, 'reference': nullable({'type': 'string'}), 'state': TEXT,
                   'started': DATETIME, 'updated': DATETIME, 'django_url': TEXT})


@endpoint(response=obj({
    **WORKSPACE['properties'], 'tabs': array(LINK), 'items': array(JOURNEY_ROW), 'page': ID,
    'next_page': nullable(ID), 'as_of': DATETIME,
}), query={'page': PAGE}, summary='Read the project journey and its available tabs')
def project(request, case_id):
    case = get_object_or_404(project_cases(request.user), pk=case_id)
    grants = project_actions(request.user, case)
    journey = project_journey.work_timeline(discoverable_work(request.user, case_id=case_id), page_number(request))
    page = journey['page']
    return {**workspace(case), 'tabs': [
        {'key': tab['key'], 'title': tab['title'], 'django_url': tab['url']} for tab in project_journey.tabs(case, grants)
    ], 'items': [{**row, 'django_url': reverse('factory_detail', args=[row['id']])} for row in journey['items']],
        'page': page.number, 'next_page': page.next_page_number() if page.has_next() else None, 'as_of': journey['as_of']}


SECTION_ITEM = obj({
    'title': TEXT, 'state': TEXT, 'detail': nullable(TEXT), 'at': nullable(DATETIME), 'due': nullable(DATETIME),
    'severity': nullable(TEXT), 'owner': nullable(TEXT), 'django_url': TEXT,
})
SECTION = obj({'title': TEXT, 'items': array(SECTION_ITEM, limit=25), 'page': ID, 'has_more': BOOLEAN, 'django_url': TEXT})


@endpoint(response=obj({'case_id': UUID, 'destinations': array(obj({
    **LINK['properties'], 'description': TEXT,
}))}), summary='Read the permitted HR handoff and follow-up destinations')
def hr(request, case_id):
    case = project_for(request.user, case_id)
    return {'case_id': case.pk, 'destinations': hr_workspace.destinations(request.user, case)}


@endpoint(response=obj({'case_id': UUID, 'tab': TEXT, 'sections': array(SECTION), 'as_of': DATETIME}),
          query={'q': {'type': 'string', 'maxLength': 120}, 'page': PAGE, 'state': TEXT, 'owner': TEXT, 'severity': TEXT},
          summary='Read permitted project milestones, evidence, registers or actions')
def project_tab(request, case_id, tab):
    if tab not in {'milestones', 'documents', 'registers', 'actions'}:
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
    return {'case_id': case.pk, 'tab': tab, 'sections': [
        {'title': section['title'], 'django_url': section['url'], 'page': section['page'].number,
         'has_more': section['page'].has_next(), 'items': [
             {'title': item['title'], 'state': item['state'], 'detail': item.get('detail') or None,
              'at': item.get('at'), 'due': item.get('due'), 'severity': item.get('severity') or None,
              'owner': item.get('owner') or None, 'django_url': item.get('url', section['url'])}
             for item in section['items']
         ]} for section in sections
    ], 'as_of': timezone.now()}


INVOICE = obj({'id': ID, 'reference': TEXT, 'version': REVISION, 'currency': TEXT,
               'paid': MONEY, 'owed': MONEY, 'status': TEXT, 'at': DATETIME})
FIGURE = obj({
    'key': TEXT, 'label': TEXT, 'amount': MONEY, 'currency': TEXT, 'due_date': nullable(DATES),
    'completed_at': nullable(DATETIME), 'contract_stage': BOOLEAN, 'missing_reason': nullable(TEXT),
    'invoices': array(INVOICE), 'sources': array(obj({'label': TEXT, 'django_url': TEXT, 'at': nullable(DATETIME)})),
})


@endpoint(response=obj({'items': array(FIGURE), 'limited': BOOLEAN, 'as_of': DATETIME, 'finance_url': TEXT}),
          query={'figure': {**TEXT, 'maxLength': 80}}, summary='Read contract and invoice figures with native provenance')
def money(request, case_id):
    case = get_object_or_404(workbench.granted(request.user, ['finance.read']), pk=case_id, kind='project')
    key = request.GET.get('figure', '')
    if len(key) > 80:
        raise Problem(422, 'invalid_filter', 'Choose an available figure.')
    value = project_money.projection(request.user, case, key)
    rows = [value['selected']] if key and value.get('selected') else value['rows']
    return {'items': [
        {'key': row['key'], 'label': row['label'], 'amount': str(row['amount']) if row['amount'] is not None else None,
         'currency': row['currency'], 'due_date': row['due_date'], 'contract_stage': row['contract_stage'],
         'completed_at': row['completion'].completed_at if row['completion'] else None,
         'missing_reason': row['missing_reason'], 'invoices': [
             {**{field: invoice[field] for field in ('reference', 'version', 'currency', 'at', 'status')},
              'id': invoice['invoice'].pk, 'paid': str(invoice['paid']) if invoice['paid'] is not None else None,
              'owed': str(invoice['owed']) if invoice['owed'] is not None else None}
             for invoice in row['invoices']
         ], 'sources': [{'label': source['label'], 'django_url': source['url'], 'at': source.get('at')}
                        for source in row['sources']]}
        for row in rows
    ], 'limited': value.get('limited', False), 'as_of': timezone.now(),
        'finance_url': reverse('finance_settlement', args=[case.pk])}


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


@endpoint(response=obj({
    'month': MONTH, 'as_of': DATETIME, 'workspace': WORKSPACE, 'stations': array(LINK),
    'cash': array(obj({'currency': TEXT, 'basis': TEXT, 'amount': TEXT})), 'cash_unavailable': BOOLEAN,
    'periods': array(obj({'entity': TEXT, 'currency': TEXT, 'at': DATETIME, 'status': TEXT,
                          'values': array(obj({'label': TEXT, 'value': MONEY, 'unit': TEXT}))})),
    'receivables': obj({'status': TEXT, 'cutoff': nullable(DATES), 'captured_date': nullable(DATES),
                        'snapshot_id': nullable(ID)}),
}), query={'month': MONTH}, summary='Read the reviewed month-end facts and capture dates for a workspace')
def close(request, case_id):
    from apps.identity.services import require

    case = project_for(request.user, case_id)
    require(request.user, case, 'finance.read')
    _, month = month_end.selection(request)
    if month is None:
        raise Problem(422, 'invalid_filter', 'Choose a reporting month.')
    data = month_end.workspace_close(request.user, case, month)
    receivables = data['receivables']
    return {'month': month, 'as_of': timezone.now(), 'workspace': workspace(case),
            'stations': [{'key': str(index), 'title': label, 'django_url': url}
                         for index, (url, label) in enumerate(data['stations'], start=1)],
            'cash': [{'currency': currency, 'basis': basis, 'amount': str(amount)}
                     for currency, basis, amount in data['cash']], 'cash_unavailable': data.get('cash_unavailable', False),
            'periods': [{**row, 'values': [
                {**figure, 'value': str(figure['value']) if figure['value'] is not None else None}
                for figure in row['values']
            ]} for row in data['periods']],
            'receivables': {'status': receivables['status'], 'cutoff': receivables.get('cutoff'),
                            'captured_date': receivables.get('date'), 'snapshot_id': receivables.get('pk')}}


@endpoint(response=obj({'items': array(obj({
    'role': TEXT, 'principal_id': ID, 'delegate_id': ID, 'valid_from': DATETIME, 'valid_until': DATETIME,
})), 'as_of': DATETIME, 'django_url': TEXT}), summary='Read the currently accessible delegation assignments')
def delegations(request, case_id):
    case = project_for(request.user, case_id)
    rows = assignments(request.user, case)
    return {'items': [{key: row[key] for key in ('role', 'principal_id', 'delegate_id', 'valid_from', 'valid_until')}
                      for row in rows], 'as_of': timezone.now(),
            'django_url': reverse('design_delegation', args=[case.pk])}

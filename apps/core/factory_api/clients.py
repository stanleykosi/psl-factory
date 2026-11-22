"""The authorised client directory and contact version history."""
from django.core.paginator import Paginator
from django.http import Http404

from apps.core import client_contacts, client_directory
from apps.core.models import ClientContactRevision
from apps.identity.services import require

from .http import ID, REVISION, TEXT, UUID, Problem, array, choice, endpoint, nullable, obj
from .workspaces import CONTACT, contact, project_for


GROUP = {'type': 'string', 'pattern': '^[a-f0-9]{64}$'}
STATUS = choice('recorded', 'needed', 'unknown')
PROJECT = obj({'case_id': UUID, 'title': TEXT, 'client': nullable(TEXT), 'billing': STATUS})
FILTERS = {'q': {'type': 'string', 'maxLength': 100}, 'billing': STATUS, 'page': ID, 'clients_page': ID}


def next_page(page):
    return page.next_page_number() if page and page.has_next() else None


def project_row(case, label, billing):
    return {'case_id': case.pk, 'title': case.title, 'client': label or None, 'billing': billing}


@endpoint(response=obj({
    'projects': array(PROJECT, limit=25), 'next_page': nullable(ID),
    'groups': array(obj({'key': GROUP, 'label': TEXT, 'project_count': ID,
                         'contacts_needed': {'type': 'integer', 'minimum': 0}}), limit=25),
    'next_group_page': nullable(ID),
}), query=FILTERS, summary='Read client groups and ungrouped projects within your authorised scope')
def directory(http):
    search = http.GET.get('q', '').strip()
    billing = http.GET.get('billing', '')
    if len(search) > 100 or billing not in dict(client_directory.BILLING_FILTERS):
        raise Problem(422, 'invalid_filter', 'Choose a shorter search and a listed billing filter.')
    actor = http.user
    links = client_directory.active_links(client_directory.visible_links(actor))
    projects = client_directory.page(actor, search, billing, http.GET.get('page'), links)
    groups = client_directory.grouped_page(links, search, billing, http.GET.get('clients_page'))
    return {'projects': [project_row(case, case.client_name, case.billing_status) for case in projects],
            'next_page': next_page(projects),
            'groups': [{'key': row['group_key'], 'label': row['label'], 'project_count': row['project_count'],
                        'contacts_needed': row['contacts_needed']} for row in groups],
            'next_group_page': next_page(groups)}


@endpoint(response=obj({'key': GROUP, 'label': TEXT, 'projects': array(PROJECT, limit=25), 'next_page': nullable(ID)}),
          query={'page': ID}, path_parameters={'group': GROUP}, summary='Read visible projects for an exact client group')
def group(http, group):
    if len(group) != 64 or any(char not in '0123456789abcdef' for char in group):
        raise Http404
    links = client_directory.active_links(client_directory.visible_links(http.user))
    label, members = client_directory.group_members(links, group, http.GET.get('page'))
    if not label:
        raise Http404
    return {'key': group, 'label': label,
            'projects': [project_row(link.case, label, link.billing_status) for link in members],
            'next_page': next_page(members)}


@endpoint(response=obj({'revision': REVISION, 'items': array(CONTACT, limit=25), 'next_page': nullable(ID)}),
          query={'purpose': choice('project', 'billing'), 'customer': {'type': 'string', 'maxLength': 160}, 'page': ID},
          required_query=('purpose',), summary='Read version history for a project or an exact billing customer')
def contact_history(http, case_id):
    purpose = http.GET.get('purpose')
    customer = http.GET.get('customer', '')
    if purpose not in client_contacts.READ or len(customer) > 160 or bool(customer) != (purpose == 'billing'):
        raise Problem(422, 'invalid_filter', 'Choose the contact purpose and the exact billing customer where applicable.')
    case = project_for(http.user, case_id)
    client_contacts.authorize(http.user, case, purpose)
    records = ClientContactRevision.objects.filter(case=case, purpose=purpose, customer=customer).order_by('-number')
    page = Paginator(records, 25).get_page(http.GET.get('page'))
    return {'revision': case.revision, 'items': [contact(record) for record in page], 'next_page': next_page(page)}


@endpoint(response=obj({
    'revision': REVISION, 'customers': array(TEXT, limit=100),
    'proofs': array(obj({'id': ID, 'kind': TEXT, 'version': REVISION}), limit=25),
}), query={'purpose': choice('project', 'billing')}, required_query=('purpose',),
          summary='Read current selectable proof and customer fields for a client contact')
def contact_options(http, case_id):
    purpose = http.GET.get('purpose')
    if purpose not in client_contacts.READ:
        raise Problem(422, 'invalid_filter', 'Choose the contact purpose.')
    case = project_for(http.user, case_id)
    client_contacts.authorize(http.user, case, purpose)
    require(http.user, case, client_contacts.WRITE[purpose])
    form = client_contacts.ContactForm(case, purpose)
    return {'revision': case.revision, 'customers': [key for key, _ in form.fields['customer'].choices],
            'proofs': [{'id': row.pk, 'kind': row.kind, 'version': row.version}
                       for row in form.fields['evidence'].queryset]}

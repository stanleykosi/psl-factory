"""Versioned client identities and separately reviewed organisation linkage."""
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404

from apps.core import client_billing_identity as identity, client_contacts, client_project_people as people
from apps.core import client_workspace_links as links
from apps.core.client_workspace_link_views import ProposalForm
from apps.core.evidence_access import CLIENT_WORKSPACE_LINK_PROOF
from apps.identity.services import active_case_grants, require

from .http import BOOLEAN, ID, REVISION, TEXT, UUID, Problem, array, choice, endpoint, nullable, obj
from .work import PAGE, page_number
from .workspaces import project_for


NAME = {**TEXT, 'maxLength': 160}
OPTION = obj({'id': ID, 'label': TEXT})
EMAIL = {'type': 'string', 'maxLength': 254}
PERSON = obj({'id': ID, 'key': UUID, 'version': REVISION, 'name': NAME, 'role': TEXT, 'email': EMAIL,
              'evidence_id': ID, 'previous_id': nullable(ID)})
IDENTITY = obj({'id': ID, 'customer': TEXT, 'coverage_id': ID, 'version': REVISION, 'evidence_id': ID,
                'legal_name': nullable(NAME), 'billing_address': nullable(TEXT), 'tax_reference': nullable(TEXT)})
LINK = obj({'id': ID, 'version': REVISION, 'coverage_id': nullable(ID), 'label': nullable(NAME),
            'group_key': nullable(TEXT), 'evidence_id': ID})


def form_fields(form):
    if not form.is_valid():
        raise Problem(422, 'invalid_input', 'Check the selected fields and evidence.',
                      fields=[{'name': key, 'message': messages[0]} for key, messages in form.errors.items()])
    return form.cleaned_data


def authorise(http, case_id, purpose, *, write=False):
    case = project_for(http.user, case_id)
    client_contacts.authorize(http.user, case, purpose)
    if write:
        require(http.user, case, client_contacts.WRITE[purpose])
    return case


def person_record(row):
    return {'id': row.pk, 'key': row.person_key, 'version': row.number, 'name': row.name, 'role': row.role,
            'email': row.email, 'evidence_id': row.evidence_id, 'previous_id': row.previous_id}


def form_options(field):
    return [{'id': row.pk, 'label': field.label_from_instance(row)} for row in field.queryset]


@endpoint(response=obj({'revision': REVISION, 'items': array(PERSON, limit=25), 'proofs': array(OPTION, limit=30),
                        'can_save': BOOLEAN, 'next_page': nullable(PAGE)}), query={'page': PAGE},
          summary='Read the current named project contacts and selectable exact source proof')
def named_people(http, case_id):
    case = authorise(http, case_id, 'project')
    can_save = (case.pk, 'engagement.capture') in active_case_grants(http.user, [case.pk])
    panel = people.panel(case, can_edit=can_save, number=page_number(http))
    page = panel['page']
    return {'revision': case.revision, 'items': [person_record(row) for row in panel['entries']],
            'can_save': can_save, 'proofs': form_options(panel['form'].fields['evidence']) if can_save else [],
            'next_page': page.next_page_number() if page.has_next() and page.number < PAGE['maximum'] else None}


@endpoint(method='POST', request=obj({'revision': REVISION, 'previous_id': nullable(ID), 'name': NAME,
                                     'role': {**TEXT, 'maxLength': 100}, 'email': EMAIL, 'evidence_id': ID},
                                     optional=('previous_id', 'email')),
          response=obj({'revision': REVISION, 'person': PERSON}), status=201,
          summary='Record a named project contact or append an exact successor')
def save_person(http, case_id, *, body):
    case = authorise(http, case_id, 'project', write=True)
    if body['revision'] != case.revision:
        raise Problem(409, 'stale_version', 'Reload the current client contacts before saving.')
    prior = body.get('previous_id')
    row = get_object_or_404(people.current(case), pk=prior) if prior else None
    form = people.PersonForm(case, [row] if row else [], {
        'revision': body['revision'], 'entry': prior, 'name': body['name'], 'role': body['role'],
        'email': body.get('email', ''), 'evidence': str(body['evidence_id']),
    }, row)
    saved = people.save(http.user, case, form_fields(form))
    case.refresh_from_db(fields=['revision'])
    return {'revision': case.revision, 'person': person_record(saved)}


def identity_record(row):
    return {'id': row.pk, 'customer': row.customer_ref, 'coverage_id': row.coverage_id, 'version': row.number,
            'evidence_id': row.evidence_id, **{key: getattr(row, key) for key in identity.FIELDS}}


@endpoint(response=obj({'revision': REVISION, 'can_save': BOOLEAN, 'items': array(obj({
    'customer': TEXT, 'identity': nullable(IDENTITY),
}), limit=100), 'history': array(IDENTITY, limit=30), 'coverage': array(OPTION, limit=100),
    'proofs': array(OPTION, limit=130)}),
          summary='Read exact customer legal billing details, history and current proof choices')
def billing_identities(http, case_id):
    case = authorise(http, case_id, 'billing')
    can_save = (case.pk, 'finance.billing.register') in active_case_grants(http.user, [case.pk])
    panel = identity.panel(case, can_edit=can_save)
    form = panel['form']
    return {'revision': case.revision, 'can_save': can_save and form is not None,
            'items': [{'customer': row['customer'], 'identity': identity_record(row['identity']) if row['identity'] else None}
                      for row in panel['rows']],
            'history': [identity_record(row) for row in panel['earlier']],
            'coverage': form_options(form.fields['coverage']) if form else [],
            'proofs': form_options(form.fields['evidence']) if form else []}


@endpoint(method='POST', request=obj({
    'revision': REVISION, 'coverage_id': ID, 'evidence_id': ID, 'legal_name': {'type': 'string', 'maxLength': 160},
    'billing_address': {'type': 'string', 'maxLength': 600}, 'tax_reference': {'type': 'string', 'maxLength': 100},
}), response=obj({'revision': REVISION, 'identity': IDENTITY}), status=201,
          summary='Record a legal billing identity for the exact current coverage and evidence')
def save_identity(http, case_id, *, body):
    case = authorise(http, case_id, 'billing', write=True)
    form = identity.BillingIdentityForm(case, {'revision': body['revision'], 'coverage': body['coverage_id'],
        'evidence': body['evidence_id'], **{key: body[key] for key in identity.FIELDS}})
    saved = identity.save(http.user, case, form_fields(form))
    case.refresh_from_db(fields=['revision'])
    return {'revision': case.revision, 'identity': identity_record(saved)}


def linked_record(record):
    return {'id': record.pk, 'version': record.number, 'coverage_id': record.coverage_id,
            'label': record.client_label or None, 'group_key': record.group_key or None,
            'evidence_id': record.evidence_id}


@endpoint(response=obj({'revision': REVISION, 'can_propose': BOOLEAN, 'current': nullable(LINK),
    'history': array(LINK, limit=9), 'coverage': array(OPTION, limit=100), 'proposals': array(obj({
        'id': ID, 'action': choice('link', 'unlink'), 'label': nullable(NAME), 'coverage_id': nullable(ID),
        'issuer': nullable(TEXT), 'reference': nullable(TEXT), 'can_confirm': BOOLEAN,
    }), limit=20)}), summary='Read the workspace’s reviewed organisation link and exact pending proposals')
def workspace_links(http, case_id):
    actor = http.user
    case = project_for(actor, case_id)
    links.authorise(actor, case)
    grants = {action for _, action in active_case_grants(actor, [case.pk])}
    can_propose = {'finance.billing.register', 'evidence.add'}.issubset(grants)
    history = list(case.clientworkspacelink_set.order_by('-number')[:10])
    current = history[0] if history else None
    candidates = case.evidence.filter(kind=CLIENT_WORKSPACE_LINK_PROOF, clientworkspacelink__isnull=True).order_by('-pk')[:20]
    proposals = []
    for evidence in candidates:
        try:
            value = links.facts_from(evidence)
            coverage, _, name = links.validate(case, value)
        except ValidationError:
            continue
        if value['previous'] == (current.pk if current else None):
            proposals.append({'id': evidence.pk, 'action': value['action'], 'label': name or None,
                'coverage_id': coverage.pk if coverage else None, 'issuer': value.get('issuer'),
                'reference': value.get('reference'),
                'can_confirm': 'policy.activate' in grants and evidence.created_by_id != actor.pk})
    return {'revision': case.revision, 'can_propose': can_propose, 'current': linked_record(current) if current else None,
            'history': [linked_record(row) for row in history[1:]], 'proposals': proposals,
            'coverage': form_options(ProposalForm(case).fields['coverage']) if can_propose else []}


LINK_PROPOSAL = {'oneOf': [
    obj({'action': {'const': 'link'}, 'revision': REVISION, 'coverage_id': ID, 'issuer': {**TEXT, 'maxLength': 100},
         'reference': {**TEXT, 'maxLength': 100}, 'name': NAME, 'source': {**TEXT, 'maxLength': 500}}),
    obj({'action': {'const': 'unlink'}, 'revision': REVISION, 'source': {**TEXT, 'maxLength': 500}}),
]}


@endpoint(method='POST', request=LINK_PROPOSAL, response=obj({'revision': REVISION, 'proposal_id': ID}),
          status=201, summary='Propose an organisation link or removal for a separate reviewer')
def propose_link(http, case_id, *, body):
    actor = http.user
    case = project_for(actor, case_id)
    links.authorise(actor, case, 'finance.billing.register')
    proposal = links.propose(actor, case, body['revision'], **{key: value for key, value in body.items() if key != 'revision'})
    case.refresh_from_db(fields=['revision'])
    return {'revision': case.revision, 'proposal_id': proposal.pk}


@endpoint(method='POST', request=obj({'revision': REVISION}), response=obj({'revision': REVISION, 'link': LINK}),
          status=201, summary='Independently confirm one exact organisation link proposal')
def confirm_link(http, case_id, evidence_id, *, body):
    actor = http.user
    case = project_for(actor, case_id)
    links.authorise(actor, case, 'policy.activate')
    record = links.confirm(actor, case, body['revision'], evidence_id)
    case.refresh_from_db(fields=['revision'])
    return {'revision': case.revision, 'link': linked_record(record)}

"""Versioned Setup and delegation through authorised native policy services."""
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404
from django.utils import timezone

from apps.core import setup_rules
from apps.core.workbench import granted
from apps.core.presentation import workspace_name
from apps.identity.services import active_case_grants, require
from apps.policy import delegation_views
from apps.policy.role_assignments import eligibility, invoice_delegation_source

from .http import BOOLEAN, DATETIME, ID, REVISION, TEXT, UUID, Problem, array, endpoint, nullable, obj
from .work import PAGE, page_number


@endpoint(response=obj({'organisations': array(TEXT), 'workspaces': array(obj({
    'case_id': UUID, 'organisation': TEXT, 'name': TEXT, 'revision': REVISION,
    'can_configure': BOOLEAN, 'rules_url': TEXT, 'policy_scopes_url': TEXT,
}), limit=25), 'next_page': nullable(PAGE)}), query={'page': PAGE},
          summary='Discover the organisations and workspace policy settings available in Setup')
def scope_options(request):
    from apps.identity.intake import options

    actor = request.user
    organisations = {authority.tenant for authority in options(actor, 'manage_access')}
    readable = granted(actor, ['policy.read'])
    page = Paginator(readable.order_by('title', 'pk'), 25).get_page(page_number(request))
    cases = list(page)
    configured = set(granted(actor, ['policy.read', 'policy.configure']).filter(
        pk__in=[case.pk for case in cases]).values_list('pk', flat=True))
    return {'organisations': sorted(organisations), 'workspaces': [
        {'case_id': case.pk, 'organisation': case.tenant, 'name': workspace_name(case), 'revision': case.revision,
         'can_configure': case.pk in configured, 'rules_url': f'/api/v1/setup/{case.pk}/rules',
         'policy_scopes_url': f'/api/v1/setup/{case.pk}/policy-scopes'} for case in cases],
        'next_page': page.next_page_number() if page.has_next() and page.number < PAGE['maximum'] else None}


@endpoint(response=obj({
    'revision': REVISION, 'as_of': DATETIME, 'items': array(obj({
        'label': TEXT, 'area': TEXT, 'status': TEXT, 'version': nullable(REVISION), 'value': nullable(TEXT),
        'details': array(TEXT), 'roles': array(TEXT), 'url': nullable(TEXT),
    })),
}), summary='Read versioned rule summaries with original-owner access checks')
def rules(http, case_id):
    case = get_object_or_404(granted(http.user, ['policy.read']), pk=case_id)
    permissions = {action for _, action in active_case_grants(http.user, [case.pk])}
    at = timezone.now()
    return {'revision': case.revision, 'as_of': at, 'items': setup_rules.rows(http.user, case, permissions, at)}


@endpoint(response=obj({
    'revision': REVISION, 'source_configuration': nullable(ID),
    'roles': array(TEXT), 'people': array(obj({'id': ID, 'label': TEXT}), limit=100),
    'proofs': array(obj({'id': ID, 'version': ID}), limit=25), 'limited': BOOLEAN,
}), query={'role': TEXT}, summary='Read delegated-decision roles and eligible people and proof')
def delegation_options(http, case_id):
    actor = http.user
    case = get_object_or_404(granted(actor, ['policy.read', 'policy.configure']), pk=case_id)
    source, _ = invoice_delegation_source(actor, case)
    members = delegation_views.assignments(actor, case)
    roles = sorted({item['role'] for item in members})
    role = http.GET.get('role')
    people, proofs = [], []
    limited = False
    if role:
        if role not in roles:
            raise Problem(422, 'invalid_filter', 'Choose a currently assigned role.')
        form = delegation_views.DelegationDraftForm(case, source, members, role)
        eligible_ids = {item['user_id'] for item in members if item['role'] == role}
        people = [
            {'id': person.pk, 'label': person.get_full_name() or person.get_username()}
            for person in form.fields['principal'].queryset.filter(pk__in=eligible_ids).only('first_name', 'last_name', 'username', 'is_active')[:101]
            if eligibility(case, members, person.pk, active=person.is_active)['eligible_role_bundle']
        ]
        proofs = [{'id': row.pk, 'version': row.version} for row in form.fields['evidence'].queryset.only('version')[:25]]
        limited = len(people) > 100
    return {'revision': case.revision, 'source_configuration': source.pk if source else None,
            'roles': roles, 'people': people[:100], 'proofs': proofs, 'limited': limited}


@endpoint(method='POST', request=obj({
    'revision': REVISION, 'source_configuration': nullable(ID), 'submission_key': UUID, 'role': TEXT,
    'principal': ID, 'delegate': ID, 'starts': DATETIME, 'ends': DATETIME, 'effective': DATETIME, 'evidence': ID,
    }), response=obj({'configuration_id': ID, 'version': REVISION, 'revision': REVISION}),
          status=201, summary='Save a delegation proposal as a new policy draft')
def draft_delegation(http, case_id, *, body):
    actor = http.user
    case = get_object_or_404(granted(actor, ['policy.read']), pk=case_id)
    require(actor, case, 'policy.configure')
    source, _ = invoice_delegation_source(actor, case)
    members = delegation_views.assignments(actor, case)
    if body['role'] not in {item['role'] for item in members}:
        raise Problem(422, 'invalid_input', 'Choose a currently assigned role.')
    form = delegation_views.DelegationDraftForm(case, source, members, body['role'], body)
    if not form.is_valid():
        raise Problem(422, 'invalid_input', 'Check the delegation fields.',
                      fields=[{'name': key, 'message': messages[0]} for key, messages in form.errors.items()])
    try:
        draft = delegation_views.save(actor, case.pk, form.cleaned_data)
    except ValidationError as exc:
        if exc.messages[0].startswith(('The workspace changed.', 'Delegations changed.', 'This submission already')):
            raise Problem(409, 'conflict', exc.messages[0]) from exc
        raise
    case.refresh_from_db(fields=['revision'])
    return {'configuration_id': draft.pk, 'version': draft.revision, 'revision': case.revision}

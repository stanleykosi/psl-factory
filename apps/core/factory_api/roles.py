from django.shortcuts import get_object_or_404
from django.urls import reverse

from apps.identity import primary_roles as domain
from apps.identity.services import visible_cases

from .http import BOOLEAN, ID, TEXT, UUID, array, choice, endpoint, nullable, obj


ROLE_KEY = {'type': 'string', 'maxLength': 50, 'pattern': '^[a-z0-9]+(?:-[a-z0-9]+)*$'}
REASON = {**TEXT, 'maxLength': 1000}
FUNCTION = choice(*domain.FUNCTIONS)
CURRENT = obj({'key': ROLE_KEY, 'name': TEXT, 'state': choice('active', 'review_needed'),
               'mode': choice('member', 'lead', 'standalone'), 'team': nullable(TEXT)}, optional=('mode', 'team'))
ROLE = obj({
    'key': ROLE_KEY, 'name': TEXT, 'description': {'type': 'string'},
    'functions': array(FUNCTION), 'definition_id': nullable(ID),
})
PREVIEW = obj({
    'selected': nullable(ROLE), 'added': array(TEXT), 'removed': array(TEXT),
    'fingerprint': {'type': 'string', 'pattern': '^[a-f0-9]{64}$'}, 'changed': BOOLEAN,
})


def workspace(actor, case_id):
    return get_object_or_404(visible_cases(actor), pk=case_id, kind='project')


@endpoint(response=obj({'roles': array(ROLE, limit=len(domain.BUILT_INS))}), summary='Read the built-in primary roles')
def built_ins(request):
    return {'roles': domain.built_ins()}


@endpoint(response=obj({
    'case_id': UUID, 'roles': array(ROLE, limit=domain.MAX_CUSTOM_ROLES + len(domain.BUILT_INS)), 'can_create': BOOLEAN,
    'functions': array(obj({'key': FUNCTION, 'name': TEXT})), 'django_url': TEXT,
}), summary='Read available workspace roles and administrator options')
def catalogue(request, case_id):
    case = workspace(request.user, case_id)
    can_create = domain.is_admin(request.user, case)
    functions = []
    if can_create:
        configuration = domain.administrator(request.user, case)
        allowed = set(configuration.value['allowed_actions'])
        functions = [{'key': key, 'name': name} for key, (name, actions) in domain.FUNCTIONS.items()
                     if actions <= allowed]
    return {'case_id': case.pk, 'roles': domain.catalogue(case), 'can_create': can_create,
            'functions': functions, 'django_url': reverse('staff_primary_roles', args=[case.pk])}


@endpoint(method='POST', request=obj({
    'name': {**TEXT, 'maxLength': 80},
    'functions': {**array(FUNCTION, limit=len(domain.FUNCTIONS)), 'minItems': 1, 'uniqueItems': True},
    'reason': REASON,
}), response=ROLE, status=201, summary='Create a workspace role under current Admin delegation')
def create(request, case_id, *, body):
    case = workspace(request.user, case_id)
    role = domain.create_definition(request.user, case.pk, **body)
    return {'key': role.key, 'name': role.name, 'description': '', 'functions': role.functions,
            'definition_id': role.pk}


@endpoint(response=obj({'case_id': UUID, 'role': nullable(CURRENT)}), summary='Read your own current workspace role')
def own(request, case_id):
    from apps.identity.teams import memberships, scope_label

    scope = memberships(request.user).filter(case_id=case_id).select_related('team').first()
    if scope:
        return {'case_id': case_id, 'role': {**domain.description(scope.role, scope_label(scope.role, scope.mode)),
                'mode': scope.mode, 'team': scope.team.name if scope.team else None}}
    case = workspace(request.user, case_id)
    return {'case_id': case.pk, 'role': domain.own_role(request.user, case)}


@endpoint(response=obj({
    'case_id': UUID, 'person_id': ID, 'person': TEXT, 'current': nullable(CURRENT),
    'roles': array(ROLE), 'preview': nullable(PREVIEW), 'django_url': TEXT,
}), query={'role': {'type': 'string', 'maxLength': 50, 'description': 'Leave the value empty to preview removal.'}},
    summary='Preview an exact primary role change for a person in this workspace')
def review(request, case_id, person_id):
    case = workspace(request.user, case_id)
    prepared = domain.review(request.user, case, person_id)
    person = prepared['person']
    preview = domain.proposal(prepared, request.GET['role'] or None) if 'role' in request.GET else None
    return {'case_id': case.pk, 'person_id': person.pk, 'person': person.get_full_name() or person.get_username(),
            'current': prepared['current'], 'roles': prepared['roles'], 'preview': preview,
            'django_url': reverse('staff_primary_role', args=[case.pk, person.pk])}


@endpoint(method='POST', request=obj({
    'role_key': nullable(ROLE_KEY), 'fingerprint': PREVIEW['properties']['fingerprint'], 'reason': REASON,
    'operation': UUID, 'confirmed': {'const': True},
}), response=obj({'change_id': ID, 'role_key': nullable(ROLE_KEY), 'added': array(TEXT), 'removed': array(TEXT)}),
    summary='Confirm a reviewed primary role assignment or removal')
def apply(request, case_id, person_id, *, body):
    case = workspace(request.user, case_id)
    row = domain.apply(request.user, case.pk, person_id, body['role_key'], body['fingerprint'],
                       body['reason'], body['operation'])
    return {'change_id': row.pk, 'role_key': row.role_key or None, 'added': row.added, 'removed': row.removed}

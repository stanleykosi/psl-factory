"""Staff admission, account review and technical delegation."""

from uuid import UUID as parse_uuid

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.db.models import Exists, OuterRef
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.debug import sensitive_variables

from apps.agents.staff_accounts import investigate_restoration
from apps.core.views import accessible_case
from apps.identity import primary_roles, staff, staff_accounts, staff_profiles, staff_reactivation, teams
from apps.identity.intake_models import TenantAuthority
from apps.identity.models import Grant
from apps.identity.staff_account_views import DepartureForm, roster_projection
from apps.identity.staff_models import StaffInvitation
from apps.identity.staff_profile_views import person_projection
from apps.identity.staff_views import DepartureForm as WorkspaceDepartureForm
from apps.identity.team_models import StaffTeam

from .http import BOOLEAN, DATETIME, ID, REVISION, TEXT, UUID, Problem, array, choice, endpoint, nullable, obj
from .intake_sources import positive_id
from .work import PAGE, page_number


NAMED = obj({'id': ID, 'name': TEXT})
PERSON = obj({'id': ID, 'name': TEXT, 'username': TEXT, 'email': {'type': 'string'}, 'active': BOOLEAN})
INVITATION = obj({'id': ID, 'case_id': UUID, 'name': TEXT, 'username': TEXT, 'email': {'type': 'string'},
                  'access': TEXT, 'expires_at': DATETIME, 'status': choice('pending', 'expired', 'accepted', 'superseded')})
ROSTER_PERSON = obj({**PERSON['properties'], 'workspace_count': {'type': 'integer', 'minimum': 0},
                     'access': TEXT, 'departure_available': BOOLEAN, 'reactivation_available': BOOLEAN})
REASON = {**TEXT, 'maxLength': 1000}
PIN = {'type': 'string', 'pattern': '^[a-f0-9]{64}$'}
ROLE = choice(*(row['key'] for row in primary_roles.built_ins()))
PROFILE_KEY = {'type': 'string', 'pattern': '^[A-Za-z0-9_-]{1,50}$'}
PROFILE = obj({'key': PROFILE_KEY, 'label': {**TEXT, 'maxLength': 80}, 'actions': array(TEXT, limit=250)})
REVIEW = {'fingerprint': PIN, 'operation': UUID, 'reason': REASON, 'confirmed': {'const': True}}


def person_payload(user):
    return {'id': user.pk, 'name': user.get_full_name() or user.username, 'username': user.username,
            'email': user.email, 'active': user.is_active}


def invitation_payload(row):
    return {'id': row.pk, 'case_id': row.case_id, 'name': row.name, 'username': row.username, 'email': row.email,
            'access': teams.describe_pin(row.role_scope) if row.role_scope else row.profile_label or 'Individual workspace access',
            'expires_at': row.expires_at, 'status': 'accepted' if hasattr(row, 'admission') else
            'superseded' if getattr(row, 'superseded', False) else 'expired' if row.expires_at <= timezone.now() else 'pending'}


def next_page(page):
    return page.next_page_number() if page.has_next() and page.number < PAGE['maximum'] else None


@endpoint(response=obj({'people': array(ROSTER_PERSON, limit=25), 'invitations': array(INVITATION, limit=25),
    'next_page': nullable(PAGE), 'next_invitations_page': nullable(PAGE), 'observed_at': DATETIME, 'available': BOOLEAN}),
    query={'page': PAGE, 'invitations_page': PAGE, 'q': {'type': 'string', 'maxLength': 120},
           'status': choice('all', 'active', 'inactive')}, summary='Read staff and pending invitations in workspaces you administer')
def roster(request):
    status, search = request.GET.get('status', 'all'), request.GET.get('q', '').strip()
    invitation_page = positive_id(request, 'invitations_page') or 1
    if status not in {'all', 'active', 'inactive'} or len(search) > 120 or invitation_page > PAGE['maximum']:
        raise Problem(422, 'invalid_filter', 'Choose a supported roster filter and page.')
    data = roster_projection(request.user, search, status, page_number(request), invitation_page)
    return {'people': [{**person_payload(user), 'access': user.first_profile_label,
                        'workspace_count': user.managed_workspace_count, 'departure_available': user.departure_available,
                        'reactivation_available': user.reactivation_available} for user in data['people']],
            'invitations': [invitation_payload(row) for row in data['invitations']], 'next_page': next_page(data['people']),
            'next_invitations_page': next_page(data['invitations']),
            'observed_at': data['observed_at'], 'available': data['available']}


@endpoint(response=obj({'person': PERSON, 'workspaces': array(obj({'case_id': UUID, 'name': TEXT, 'access': TEXT,
    'primary_role': nullable(TEXT), 'can_edit_profile': BOOLEAN, 'can_assign_primary_role': BOOLEAN}), limit=20),
    'next_page': nullable(PAGE)}), query={'page': PAGE}, summary='Read the staff account’s scoped workspace access')
def person(request, person_id):
    data = person_projection(request.user, person_id, page_number(request))
    page = data['workspaces']
    return {'person': person_payload(data['person']), 'next_page': next_page(page), 'workspaces': [
        {'case_id': case.pk, 'name': case.title, 'access': case.account_access_label, 'primary_role': case.primary_role,
         'can_edit_profile': case.can_edit_profile, 'can_assign_primary_role': case.can_assign_primary_role} for case in page]}


@endpoint(response=obj({'revision': REVISION, 'authority_id': ID, 'membership_id': nullable(ID),
    'lead_role': nullable(ROLE), 'teams': array(NAMED, limit=100),
    'invitations': array(INVITATION, limit=40)}), query={'team_id': ID},
    summary='Read current invitation authority and recent invitations for the selected team or workspace')
def invitations(request, case_id):
    actor = request.user
    team_id = positive_id(request, 'team_id')
    if team_id is None:
        case = accessible_case(actor, case_id)
        authority, _ = teams.invitation_authority(actor, case, 'lead')
        lead = None
    else:
        lead = get_object_or_404(teams.memberships(actor).select_related('case', 'team'),
                                 case_id=case_id, team_id=team_id, mode='lead')
        case = lead.case
        authority, _ = teams.invitation_authority(actor, case, 'member', team_id=team_id, membership_id=lead.pk)
    rows = StaffInvitation.objects.filter(case=case)
    if lead:
        rows = rows.filter(role_scope__team_id=team_id, role_scope__mode='member')
    latest = StaffInvitation.objects.filter(case=case, username=OuterRef('username'), number__gt=OuterRef('number'))
    rows = rows.annotate(superseded=Exists(latest)).select_related('admission').order_by('-pk')[:40]
    team_rows = [lead.team] if lead else StaffTeam.objects.filter(case=case).order_by('name', 'pk')[:100]
    return {'revision': case.revision, 'authority_id': authority.pk, 'membership_id': lead.pk if lead else None,
            'lead_role': lead.role if lead else None,
            'teams': [{'id': row.pk, 'name': row.name} for row in team_rows],
            'invitations': [invitation_payload(row) for row in rows]}


@endpoint(method='POST', request=obj({'revision': REVISION, 'name': {**TEXT, 'maxLength': 150},
    'username': {**TEXT, 'maxLength': 150}, 'email': {**TEXT, 'maxLength': 254, 'format': 'email'},
    'authority_id': ID, 'membership_id': nullable(ID),
    'role': ROLE, 'mode': choice('lead', 'member', 'standalone'), 'team_id': nullable(ID), 'preceding_id': nullable(ID)}),
    response=obj({'invitation': INVITATION, 'join_url': TEXT, 'revision': REVISION}), status=201,
    summary='Create or renew a role-scoped invitation under the current administrator or team lead')
@sensitive_variables('token')
def invite(request, case_id, *, body):
    actor = request.user
    if body['mode'] == 'member':
        lead = get_object_or_404(teams.memberships(actor).select_related('case'),
                                 case_id=case_id, team_id=body['team_id'], mode='lead')
        case = lead.case
    else:
        case = accessible_case(actor, case_id)
    row, token = staff.invite_person(actor, case.pk, body['username'], body['name'], body['email'], body['revision'],
        role=body['role'], mode=body['mode'], team_id=body['team_id'], preceding=body['preceding_id'],
        expected_authority=body['authority_id'], expected_membership=body['membership_id'])
    case.refresh_from_db(fields=['revision'])
    return {'invitation': invitation_payload(row), 'revision': case.revision,
            'join_url': request.build_absolute_uri(reverse('staff_accept_invite')) + '#' + token}


@endpoint(response=obj({'person': PERSON, 'fingerprint': PIN, 'profile': TEXT, 'profiles': array(PROFILE, limit=30),
    'current_actions': array(TEXT, limit=250)}), summary='Read the exact technical access-profile review and active grants')
def profile(request, case_id, person_id):
    case = accessible_case(request.user, case_id)
    current = staff_profiles.review(request.user, case, person_id)
    return {'person': person_payload(current['person']), 'fingerprint': current['fingerprint'],
            'profile': staff_profiles.labels([case.pk], person_id)[case.pk], 'profiles': current['profiles'],
            'current_actions': [grant['action'] for grant in current['manifest']['grants']]}


@endpoint(method='POST', request=obj({**REVIEW, 'profile': PROFILE_KEY}), response=obj({'person_id': ID}),
          summary='Confirm the exact reviewed technical access profile')
def apply_profile(request, case_id, person_id, *, body):
    case = accessible_case(request.user, case_id)
    staff_profiles.apply(request.user, case.pk, person_id, body['profile'], body['fingerprint'], body['reason'],
                         parse_uuid(body['operation']))
    return {'person_id': person_id}


DEPARTURE_SCOPE = obj({'case_id': UUID, 'name': TEXT, 'handover_pending': BOOLEAN, 'proofs': array(NAMED, limit=50),
    'actions': array(obj({'id': ID, 'description': TEXT, 'successors': array(NAMED, limit=100),
                          'may_be_unassigned': BOOLEAN}), limit=100)})


def scoped_person(actor, case, person_id):
    config, _ = staff.authority(actor, case, 'allow_deactivation')
    return get_object_or_404(Grant.objects.filter(case=case, user_id=person_id, active=True,
        action__in=config.value['allowed_actions']).select_related('user').order_by('pk')[:1]).user


@endpoint(response=obj({'revision': REVISION, 'person': PERSON, 'workspace': DEPARTURE_SCOPE}),
          summary='Review removal from this one workspace, including every open action handover')
def workspace_departure(request, case_id, person_id):
    actor = request.user
    case = accessible_case(actor, case_id)
    user = scoped_person(actor, case, person_id)
    items = list(staff.open_actions(case, person_id)[:101])
    if len(items) > 100:
        raise Problem(422, 'handover_required', 'Review the complete action inventory before removing access.')
    form = WorkspaceDepartureForm(case, items, actor=actor)
    return {'revision': case.revision, 'person': person_payload(user), 'workspace': {'case_id': case.pk, 'name': case.title,
            'handover_pending': bool(staff.work_handover_findings(case, user)),
            'proofs': [{'id': value, 'name': label} for value, label in form.fields['evidence'].choices] if items else [],
            'actions': [{'id': item.pk, 'description': item.current.description, 'may_be_unassigned': False,
                         'successors': [{'id': value, 'name': label} for value, label in
                                        form.fields[f'reassign_{item.pk}'].choices]} for item in items]}}


@endpoint(method='POST', request=obj({'revision': REVISION, 'reason': REASON, 'evidence_id': nullable(ID),
    'actions': array(obj({'action_id': ID, 'successor_id': ID}), limit=100)}), response=obj({'person_id': ID}),
    summary='Remove one workspace grant after reassigning each open action to a current successor')
def remove_workspace_access(request, case_id, person_id, *, body):
    actor = request.user
    case = accessible_case(actor, case_id)
    scoped_person(actor, case, person_id)
    replacements = {row['action_id']: row['successor_id'] for row in body['actions']}
    if len(replacements) != len(body['actions']):
        raise Problem(422, 'invalid_input', 'Choose one new owner for each open action.')
    staff.deactivate(actor, case.pk, person_id, replacements, body['evidence_id'], body['reason'], body['revision'])
    return {'person_id': person_id}


@endpoint(response=obj({'person': PERSON, 'fingerprint': PIN, 'blocked': array(TEXT),
                        'workspaces': array(DEPARTURE_SCOPE, limit=100)}),
          summary='Review the entire account scope and all affected action handovers before deactivation')
def departure(request, person_id):
    prepared = staff_accounts.prepare(request.user, person_id)
    form = DepartureForm(prepared)
    workspaces = []
    for scope, group in zip(prepared['scopes'], form.groups, strict=True):
        actions = [{'id': row['item'].pk, 'description': row['item'].current.description,
                    'successors': [{'id': value, 'name': label} for value, label in row['field'].field.choices if value],
                    'may_be_unassigned': not row['field'].field.required} for row in group['rows']]
        proof = group['evidence']
        workspaces.append({'case_id': scope['case'].pk, 'name': scope['case'].title,
            'handover_pending': scope['handover_pending'], 'actions': actions,
            'proofs': [{'id': value, 'name': label} for value, label in proof.field.choices] if proof else []})
    return {'person': person_payload(prepared['person']), 'fingerprint': prepared['fingerprint'],
            'blocked': prepared['blocked'], 'workspaces': workspaces}


@endpoint(method='POST', request=obj({**REVIEW,
    'actions': array(obj({'action_id': ID, 'successor_id': nullable(ID)}), limit=10000),
    'evidence': array(obj({'case_id': UUID, 'evidence_id': ID}), limit=100)}),
    response=obj({'person_id': ID, 'active': BOOLEAN}), summary='Deactivate the exact reviewed account after required handovers')
def deactivate(request, person_id, *, body):
    replacements = {row['action_id']: row['successor_id'] for row in body['actions']}
    evidence = {str(parse_uuid(row['case_id'])): row['evidence_id'] for row in body['evidence']}
    if len(replacements) != len(body['actions']) or len(evidence) != len(body['evidence']):
        raise Problem(422, 'invalid_input', 'Supply one action handover and evidence entry per reference.')
    staff_accounts.deactivate(request.user, person_id, body['fingerprint'], replacements, evidence, body['reason'],
                              parse_uuid(body['operation']))
    return {'person_id': person_id, 'active': False}


@endpoint(response=obj({'person': PERSON, 'fingerprint': PIN, 'blocked': array(TEXT), 'guidance': TEXT,
    'workspaces': array(obj({'case_id': UUID, 'name': TEXT, 'role_source': nullable(ID)}), limit=100)}),
    summary='Review account restoration and required fresh workspace access')
def restoration(request, person_id):
    prepared = investigate_restoration(request.user, person_id)
    return {'person': person_payload(prepared['person']), 'fingerprint': prepared['fingerprint'],
            'blocked': prepared['blocked'], 'guidance': prepared['assistance']['next_action'],
            'workspaces': [{'case_id': row['case'].pk, 'name': row['case'].title, 'role_source': row['role_source']}
                           for row in prepared['scopes']]}


@endpoint(method='POST', request=obj(REVIEW), response=obj({'person_id': ID, 'active': BOOLEAN}),
          summary='Restore sign-in under the reviewed human authority and keep prior grants revoked')
def restore(request, person_id, *, body):
    staff_reactivation.restore(request.user, person_id, body['fingerprint'], body['reason'], parse_uuid(body['operation']))
    return {'person_id': person_id, 'active': True}


CONTROLS = obj({key: nullable(BOOLEAN) for key in staff_accounts.CONTROL_KEYS})
PROFILES = nullable(array(PROFILE, limit=30))
DELEGATION = obj({'id': ID, 'tenant': TEXT, 'person': PERSON, 'version': REVISION, 'enabled': BOOLEAN,
                  'expires_at': DATETIME, 'controls': CONTROLS, 'profiles': PROFILES, 'allowed_actions': array(TEXT)})


def technical_authority(actor, authority_id):
    if not get_user_model().objects.filter(pk=actor.pk, is_active=True, is_superuser=True).exists():
        raise PermissionDenied
    return get_object_or_404(TenantAuthority.objects.select_related('user'), pk=authority_id)


def technical_payload(record):
    lifecycle = record.value.get('staff_lifecycle', {}) or {}
    return {'id': record.pk, 'tenant': record.tenant, 'person': person_payload(record.user), 'version': record.version,
            'enabled': record.enabled, 'expires_at': record.expires_at,
            'controls': {key: lifecycle.get(key) for key in staff_accounts.CONTROL_KEYS},
            'profiles': lifecycle.get('profiles'), 'allowed_actions': record.value['allowed_actions']}


@endpoint(response=DELEGATION, summary='Read the exact technical delegation and its staff lifecycle controls')
def delegation(request, authority_id):
    return technical_payload(technical_authority(request.user, authority_id))


@endpoint(method='POST', request={'oneOf': [obj({'action': {'const': 'controls'}, 'controls': CONTROLS, 'reason': REASON}),
              obj({'action': {'const': 'profiles'}, 'profiles': PROFILES, 'reason': REASON})]},
    response=DELEGATION, status=201, summary='Review and record a successor technical delegation version')
def update_delegation(request, authority_id, *, body):
    actor = request.user
    previous = technical_authority(actor, authority_id)
    if body['action'] == 'controls':
        saved = staff_accounts.configure_controls(actor, previous.pk, body['controls'], body['reason'])
    else:
        saved = staff_profiles.configure(actor, previous.pk, body['profiles'], body['reason'])
    return technical_payload(saved)

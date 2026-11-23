"""Same-origin login, staff onboarding and one-use account recovery."""

from urllib.parse import urlsplit

from django.contrib.auth import login as django_login, logout as django_logout, update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from django.core.exceptions import PermissionDenied, ValidationError
from django.middleware.csrf import get_token
from django.views.decorators.debug import sensitive_variables

from apps.core import account_delivery, recovery_views
from apps.core.design_views import FactorySignInForm
from apps.core.workbench import visible_cases
from apps.identity import staff, teams
from apps.identity.intake import options as authority_options

from .http import BOOLEAN, DATETIME, TEXT, Problem, array, endpoint, obj
from .notifications import STATUS, preference_data


PASSWORD = {**TEXT, 'maxLength': 128, 'format': 'password'}
LOGIN_PASSWORD = {**TEXT, 'maxLength': 4096, 'format': 'password'}
EMAIL = {**TEXT, 'maxLength': 254, 'format': 'email'}
CODE = {'type': 'string', 'minLength': 43, 'maxLength': 43, 'pattern': '^[A-Za-z0-9_-]+$'}
SESSION = obj({'csrf_token': TEXT, 'signed_in': BOOLEAN, 'next_url': TEXT})
CONFIRM = obj({'complete': BOOLEAN})
PASSWORD_PAIR = {'new_password1': PASSWORD, 'new_password2': PASSWORD}
FRONTEND_PAGES = frozenset(('my-work', 'projects', 'overview', 'assistant', 'setup', 'clients', 'work',
                            'exceptions', 'finance', 'notifications', 'settings'))
FRONTEND_SIGN_IN = '/sign-in'
FRONTEND_HOME = '/my-work'


def frontend_next(value):
    if (not value or not value.startswith('/') or value.startswith('//') or '\\' in value
            or any(ord(char) < 32 or ord(char) == 127 for char in value)):
        return None
    path = urlsplit(value).path
    segments = path.split('/')
    if path == '/' or (segments[1] in FRONTEND_PAGES and not any(
            segment in ('.', '..') or '%' in segment for segment in segments)):
        return value
    return None


def session_data(request, next_url=None):
    signed_in = bool(request.user.is_authenticated and request.user.is_active)
    return {'csrf_token': get_token(request), 'signed_in': signed_in,
            'next_url': next_url or (FRONTEND_HOME if signed_in else FRONTEND_SIGN_IN)}


def form_problem(form, message):
    return Problem(422, 'invalid_input', message,
                   fields=[{'name': key, 'message': errors[0]} for key, errors in form.errors.items()])


@endpoint(response=SESSION, authenticated=False, summary='Get a same-origin CSRF token and account entry state')
def session(request):
    return session_data(request)


@endpoint(method='POST', request=obj({'username': {**TEXT, 'maxLength': 254}, 'password': LOGIN_PASSWORD,
    'remember': BOOLEAN, 'next_url': {**TEXT, 'maxLength': 2048}}, optional=('remember', 'next_url')),
    response=SESSION, authenticated=False, summary='Sign in with the Django session and rotate the CSRF token')
@sensitive_variables('body', 'form')
def sign_in(request, *, body):
    form = FactorySignInForm(request, {key: body[key] for key in ('username', 'password', 'remember') if key in body})
    if not form.is_valid():
        raise Problem(422, 'sign_in_failed', 'Check the sign-in details.')
    django_login(request, form.get_user())
    request.session.set_expiry(None if form.cleaned_data['remember'] else 0)
    return session_data(request, frontend_next(body.get('next_url')))


@endpoint(method='POST', request=obj({}), response=SESSION, authenticated=False, summary='End the current session')
def sign_out(request, *, body):
    django_logout(request)
    return session_data(request)


@endpoint(response=obj({'admitted': BOOLEAN, 'can_create_workspace': BOOLEAN, 'next_url': TEXT}),
          summary='Read the current onboarding state and workspace entry point')
def onboarding(request):
    actor = request.user
    admitted = teams.memberships(actor).exists() or visible_cases(actor).exists()
    return {'admitted': admitted, 'can_create_workspace': bool(authority_options(actor, 'create_cases')),
            'next_url': FRONTEND_HOME if admitted else FRONTEND_SIGN_IN}


@endpoint(response=obj({'name': TEXT, 'username': TEXT, 'email': {'type': 'string'}, 'alerts': STATUS}),
          summary='Read your own account settings and verified alert channel availability')
def account(request):
    actor = request.user
    return {'name': actor.get_full_name() or actor.username, 'username': actor.username, 'email': actor.email,
            'alerts': preference_data(actor)}


@endpoint(method='POST', request=obj({'old_password': LOGIN_PASSWORD, **PASSWORD_PAIR}), response=SESSION,
          summary='Change your password using the current Django session')
@sensitive_variables('body', 'form')
def password(request, *, body):
    form = PasswordChangeForm(request.user, body)
    if not form.is_valid():
        raise form_problem(form, 'Check the password fields.')
    user = form.save()
    update_session_auth_hash(request, user)
    return session_data(request)


@endpoint(method='POST', request=obj({'email': EMAIL}), response=obj({'requested': BOOLEAN}), status=202,
          authenticated=False, summary='Request password recovery with the same response for all valid addresses')
def request_recovery(request, *, body):
    account_delivery.queue_recovery(body['email'])
    return {'requested': True}


@endpoint(method='POST', request=obj({'token': {**TEXT, 'maxLength': 128}}), response=obj({'ready': BOOLEAN}),
          authenticated=False, summary='Bind a verified recovery link to this session')
@sensitive_variables('body')
def redeem(request, *, body):
    return {'ready': recovery_views.bind_recovery_session(request, body['token'])}


@endpoint(response=obj({'ready': BOOLEAN}), authenticated=False,
          summary='Check whether this session has a current password recovery request')
def recovery_status(request):
    return {'ready': recovery_views.recovery_session(request) is not None}


@endpoint(method='POST', request=obj(PASSWORD_PAIR), response=CONFIRM, authenticated=False,
          summary='Set a new password and consume the exact recovery request')
@sensitive_variables('body', 'form')
def reset_password(request, *, body):
    record = recovery_views.recovery_session(request)
    if record is None:
        raise Problem(422, 'recovery_unavailable', 'This recovery session is unavailable.')
    form, changed = recovery_views.change_recovered_password(request, record, body)
    if not changed:
        if form is not None:
            raise form_problem(form, 'Check the new password fields.')
        raise Problem(422, 'recovery_unavailable', 'This recovery session is unavailable.')
    return {'complete': True}


@endpoint(method='POST', request=obj({'token': CODE}), response=obj({'name': TEXT, 'email': EMAIL,
    'expires_at': DATETIME, 'workspaces': array(obj({'name': TEXT, 'access': TEXT}))}), authenticated=False,
    summary='Preview the exact role and workspace access offered by a current invitation')
@sensitive_variables('body')
def preview_invitation(request, *, body):
    try:
        row = staff.pending(body['token'], role_required=True)
        extra = staff.additional_access(row, row.authority)
    except (PermissionDenied, ValidationError) as exc:
        raise Problem(422, 'invitation_unavailable', 'This invitation is unavailable.') from exc
    workspaces = [{'name': row.case.title, 'access': teams.describe_pin(row.role_scope)}]
    workspaces.extend({'name': case.title, 'access': profile['label']} for case, profile in extra)
    return {'name': row.name, 'email': row.email, 'expires_at': row.expires_at, 'workspaces': workspaces}


@endpoint(method='POST', request=obj({'token': CODE, 'password': PASSWORD, 'confirm': PASSWORD, 'review_alerts': BOOLEAN},
    optional=('review_alerts',)), response=obj({'complete': BOOLEAN, 'next_url': TEXT}), status=201, authenticated=False,
    summary='Set up a staff account under the inviter’s current reviewed authority')
@sensitive_variables('body')
def accept_invitation(request, *, body):
    if body['password'] != body['confirm']:
        raise Problem(422, 'invalid_input', 'The passwords differ.')
    try:
        staff.accept(body['token'], body['password'], role_required=True)
    except PermissionDenied as exc:
        raise Problem(422, 'invitation_unavailable', 'This invitation is unavailable.') from exc
    next_url = FRONTEND_SIGN_IN + ('?next=%2Fsettings%2Falerts' if body.get('review_alerts') else '')
    return {'complete': True, 'next_url': next_url}

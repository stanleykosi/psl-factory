"""Reviewed synthetic admissions for authenticated workflow access checks."""
from datetime import timedelta
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.test import Client, override_settings
from django.utils import timezone

from apps.identity import intake, staff, teams
from apps.identity.models import Grant
from .helpers import rev


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
def role_accounts(case):
    if not case.synthetic or case.kind != 'project':
        raise ValueError('Role acceptance requires a synthetic project.')
    users = get_user_model().objects
    suffix = uuid4().hex[:10]
    bootstrap = users.create_superuser('roles-root-' + suffix)
    administrator = users.create_user('roles-issuer-' + suffix)
    Grant.objects.create(user=administrator, case=case, action='case.read')
    intake.provision(bootstrap, administrator, case.tenant, {
        'format': 'psl.tenant-access/v3', 'create_cases': False, 'manage_access': True,
        'kinds': ['project'], 'allowed_actions': ['case.read'], 'initial_actions': ['case.read'],
        'classification': 'synthetic', 'staff_lifecycle': {
            'invite_minutes': 30, 'allow_invite': True, 'allow_deactivation': True,
            'allow_profile_edit': True, 'allow_roster': True,
        },
    }, timezone.now() + timedelta(hours=4), True, 'Synthetic role access checks.')

    def admit(key, issuer, role, mode, team=None):
        name = key + '-' + suffix
        _, token = staff.invite_person(issuer, case.pk, name, name, name + '@example.test', rev(case),
                                      role=role, mode=mode, team_id=team.pk if team else None)
        return staff.accept(token, 'Synthetic test roles only! 126')

    actors = {}
    for role, key in [('pmo-lead', 'pmo'), ('finance-lead', 'finance'), ('hr', 'hr'), ('admin', 'admin')]:
        team = teams.create_team(administrator, case.pk, role, 'Access check ' + suffix)
        leader = admit(key + '-head', administrator, role, 'lead', team)
        if key in ('pmo', 'finance'):
            actors[key + '_head'] = leader
            actors[key + '_member'] = admit(key + '-member', leader, role, 'member', team)
        else:
            actors[key] = leader
    for role in ('ceo', 'cto'):
        actors[role] = admit(role, administrator, role, 'standalone')
    return actors


def role_clients(case):
    clients = {}
    for key, user in role_accounts(case).items():
        clients[key] = Client()
        clients[key].force_login(user)
    return clients

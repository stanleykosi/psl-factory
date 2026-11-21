"""Workspace membership and invitation pins for the six base roles."""
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import F, Q, Subquery

from apps.core.models import Case
from apps.core.services import bump, event

from . import intake, primary_roles
from .team_models import STANDALONE_ROLES, TEAM_ROLES, StaffMembership, StaffTeam


FOCUS = {
    'pmo-lead': ('Project management', 'Planning, delivery, milestones and reporting'),
    'finance-lead': ('Finance', 'Billing, payments, forecasts and close'),
    'hr': ('Human resources', 'HR handoffs, staff matching and staff-cost follow-up'),
    'admin': ('Administration', 'Staff invitations, access reviews and account follow-up'),
    'cto': ('Technology', 'Technical readiness, releases and incidents'),
    'ceo': ('Leadership', 'Leadership reports, decisions and verified outcomes'),
}
MODE_LABELS = {'member': 'Team member', 'lead': 'Team lead', 'standalone': 'Standalone role'}


def memberships(actor):
    return StaffMembership.objects.filter(user=actor, active=True, user__is_active=True)


def scope_label(role, mode):
    return FOCUS[role][0] if mode == 'member' else primary_roles.BUILT_INS[role][0]


def manageable(actor, case, actions=()):
    cfg = primary_roles.administrator(actor, case)
    if set(actions) - set(cfg.value['allowed_actions']):
        raise PermissionDenied('Your current delegation does not cover this assignment.')
    return cfg


def describe_pin(pin):
    text = [scope_label(pin['role'], pin['mode']), MODE_LABELS[pin['mode']]]
    if pin['team_name']:
        text.append(pin['team_name'])
    return ' · '.join(text)


def invitation_scope(actor, case, role, mode, team_id):
    cfg = manageable(actor, case, ['case.read'])
    if not cfg.value.get('staff_lifecycle', {}).get('allow_invite'):
        raise PermissionDenied('A current staff invitation delegation is required.')
    if role in STANDALONE_ROLES and mode == 'standalone' and team_id is None:
        return {'format': 'psl.staff-role-scope/v1', 'role': role, 'mode': mode, 'team_id': None, 'team_name': ''}
    if role not in TEAM_ROLES or mode not in ('member', 'lead') or type(team_id) is not int:
        raise ValidationError('Choose a base role and the appropriate team or standalone scope.')
    team = StaffTeam.objects.filter(case=case, role=role, pk=team_id).first()
    if not team:
        raise ValidationError('Choose a current team for this role in the invited workspace.')
    return {'format': 'psl.staff-role-scope/v1', 'role': role, 'mode': mode, 'team_id': team.pk, 'team_name': team.name}


@transaction.atomic
def create_team(actor, case_id, role, name):
    case = Case.objects.select_for_update().get(pk=case_id)
    intake.lock_users([actor.pk])
    manageable(actor, case)
    intake.text(name, 80)
    if role not in TEAM_ROLES:
        raise ValidationError('Choose a role that has a team.')
    if StaffTeam.objects.filter(case=case, role=role, name__iexact=name).exists():
        raise ValidationError('A team already uses this name in this role.')
    row = StaffTeam.objects.create(case=case, role=role, name=name, actor=actor)
    event(actor, case, 'staff.team_created', team=row.pk, role=role)
    bump(case)
    return row


def verify_invitation(row):
    pin = row.role_scope
    if (not isinstance(pin, dict) or row.actions or row.profile_key or row.workspace_profiles or
            pin != invitation_scope(row.actor, row.case, pin.get('role'), pin.get('mode'), pin.get('team_id'))):
        raise ValidationError('The approved role or scope changed. Ask for a new invitation.')


def admit(row, user):
    verify_invitation(row)
    pin = row.role_scope
    membership = StaffMembership.objects.create(case=row.case, user=user, role=pin['role'], mode=pin['mode'],
                                                team_id=pin['team_id'], invitation=row)
    event(row.actor, row.case, 'staff.membership_admitted', member=membership.pk, person=user.pk, team=membership.team_id)
    return membership


@transaction.atomic
def revoke(actor, case_id, member_id, reason):
    case = Case.objects.select_for_update().get(pk=case_id)
    member = StaffMembership.objects.select_for_update().get(case=case, pk=member_id, active=True)
    intake.lock_users([actor.pk, member.user_id])
    manageable(actor, case)
    intake.text(reason, 1000)
    member.active = False
    member.save(update_fields=['active'])
    event(actor, case, 'staff.membership_revoked', member=member.pk, person=member.user_id, reason=reason)
    bump(case)


def visible_assignments(actor):
    from .team_models import StaffAssignment

    own = memberships(actor)
    teams = own.filter(mode='lead').values('team_id')
    return StaffAssignment.objects.filter(membership__active=True, membership__user__is_active=True).filter(
        Q(membership_id__in=Subquery(own.values('pk'))) |
        Q(membership__team_id__in=Subquery(teams))
    ).filter(Q(action__isnull=True) | Q(action__current__owner_id=F('membership__user_id')))

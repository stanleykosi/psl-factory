"""Workspace navigation and operational access derived from current staff roles."""
from django.db.models import Exists, OuterRef, Q, Subquery

from apps.core.models import Case

from .team_models import StaffMembership


# Preparation and source discovery. Decisions, publishing, private source
# access and external effects continue to require their native authority.
LEAD_ACTIONS = {
    'pmo-lead': frozenset({
        'case.read', 'factory.read', 'factory.start', 'agent.extract', 'evidence.add',
        'engagement.read', 'engagement.capture', 'planning.read', 'delivery.read',
        'meeting.read', 'issue.read', 'change.read', 'report.read', 'emergency.read', 'rfp.read',
    }),
    'finance-lead': frozenset({
        'case.read', 'factory.read', 'factory.start', 'agent.extract', 'evidence.add',
        'finance.read', 'finance.calculate', 'finance.import', 'finance.validate', 'finance.source',
        'schedules.read', 'ppe.read',
    }),
    'hr': frozenset({'case.read', 'agent.extract', 'evidence.add', 'hrfinance.read'}),
}


def leads(actor):
    return StaffMembership.objects.filter(user=actor, user__is_active=True, active=True,
                                          mode='lead', role__in=LEAD_ACTIONS, case__kind='project')


def authorized_leads(actor, actions):
    actions = frozenset(actions)
    roles = [name for name, allowed in LEAD_ACTIONS.items() if actions <= allowed]
    return leads(actor).filter(role__in=roles)


def role_cases(actor, actions):
    return Case.objects.filter(pk__in=authorized_leads(actor, actions).values('case_id')).distinct()


def project_cases(actor):
    from .services import visible_cases

    return (visible_cases(actor) | role_cases(actor, ['case.read'])).filter(kind='project')


def project_actions(actor, case):
    from .services import active_case_grants

    actions = {action for _, action in active_case_grants(actor, [case.pk])}
    for role in leads(actor).filter(case=case).values_list('role', flat=True):
        actions.update(LEAD_ACTIONS[role])
    return actions


def team_work_scope(actor, definition, actions):
    own_team = authorized_leads(actor, actions)
    creator_team = StaffMembership.objects.filter(
        case_id=OuterRef('case_id'), user_id=OuterRef('actor_id'), active=True, user__is_active=True,
        team_id__in=Subquery(own_team.filter(case_id=OuterRef('case_id')).values('team_id')),
    )
    return Q(definition=definition) & Q(Exists(creator_team))

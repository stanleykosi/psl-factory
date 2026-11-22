"""Workspace navigation and operational access derived from current staff roles."""
from django.db.models import Exists, OuterRef, Q

from apps.core.models import Case

from .team_models import StaffMembership


# Preparation and source discovery. Decisions, publishing, private source
# access and external effects continue to require their native authority.
LEAD_ACTIONS = {
    'pmo-lead': frozenset({
        'case.read', 'factory.read', 'factory.start', 'agent.extract', 'evidence.add',
        'engagement.read', 'engagement.capture', 'planning.read', 'delivery.read',
        'issue.read', 'change.read', 'report.read', 'emergency.read', 'rfp.read',
    }),
    'finance-lead': frozenset({
        'case.read', 'factory.read', 'factory.start', 'agent.extract', 'evidence.add',
        'finance.read', 'finance.calculate', 'finance.import', 'finance.validate', 'finance.source',
        'schedules.read', 'ppe.read',
    }),
    'hr': frozenset({'case.read', 'agent.extract', 'evidence.add', 'hrfinance.read'}),
}

PERSONA_ROLES = {'tola': 'pmo-lead', 'chidi': 'finance-lead', 'zainab': 'hr'}
DEPARTMENT_READS = {
    'pmo-lead': frozenset({'case.read', 'factory.read', 'engagement.read', 'planning.read', 'costing.read',
                           'commercial.read', 'delivery.read', 'meeting.read', 'issue.read', 'change.read',
                           'report.read', 'emergency.read', 'rfp.read', 'costing.source.read', 'commercial.proof.read',
                           'client_uat.proof.read', 'delivery.progress.read', 'issue.message.read', 'rfp.estimate.read',
                           'issue.reference.change.read', 'issue.reference.incident.read', 'issue.reference.risk.read'}),
    'finance-lead': frozenset({'case.read', 'factory.read', 'finance.read', 'schedules.read', 'ppe.read',
                               'ledger.read', 'ledger.private.read', 'bu.read', 'bu.report.read', 'payroll.read',
                               'finance.handoff.read', 'finance.receipt_followup.read', 'finance.reminder.read',
                               'finance.short_payment.read', 'payment.read', 'recognition.read', 'coverage.read'}),
    'hr': frozenset({'case.read', 'hrfinance.read', 'hrfinance.snapshot.read'}),
}


def department_memberships(actor, role):
    return StaffMembership.objects.filter(user=actor, user__is_active=True, active=True, role=role,
                                          case__kind='project')


def department_cases(actor, role, *, heads_only=False):
    memberships = department_memberships(actor, role)
    heads = memberships.filter(mode='lead', case__tenant=OuterRef('tenant'), case__synthetic=OuterRef('synthetic'))
    scope = Q(Exists(heads)) if role in ('pmo-lead', 'finance-lead') else Q(pk__in=[])
    if not heads_only:
        scope |= Q(pk__in=memberships.values('case_id'))
    return Case.objects.filter(scope, kind='project')


def role_managed(actor):
    # Keep a revoked account from falling back to an earlier assistant grant.
    return StaffMembership.objects.filter(user=actor).exists()


def leads(actor):
    return StaffMembership.objects.filter(user=actor, user__is_active=True, active=True,
                                          mode='lead', role__in=LEAD_ACTIONS, case__kind='project')


def authorized_leads(actor, actions):
    actions = frozenset(actions)
    # A head can combine preparation rights with the department reads they
    # already hold in their assigned workspace. No extra action is granted.
    roles = [name for name, allowed in LEAD_ACTIONS.items() if actions <= (allowed | DEPARTMENT_READS.get(name, frozenset()))]
    return leads(actor).filter(role__in=roles)


def role_cases(actor, actions):
    query = Q(pk__in=authorized_leads(actor, actions).values('case_id'))
    for role, allowed in DEPARTMENT_READS.items():
        if actions and set(actions) <= allowed:
            query |= Q(pk__in=department_cases(actor, role).values('pk'))
    return Case.objects.filter(query).distinct()


def project_cases(actor):
    from .services import visible_cases

    return (visible_cases(actor) | role_cases(actor, ['case.read'])).filter(kind='project')


def project_actions(actor, case):
    from .services import active_case_grants, legacy_projects

    actions = {action for _, action in active_case_grants(actor, [case.pk])}
    if actions and not legacy_projects(actor, Case.objects.filter(pk=case.pk)).exists():
        actions.clear()
    for role, allowed in DEPARTMENT_READS.items():
        if department_cases(actor, role).filter(pk=case.pk).exists():
            actions.update(allowed)
    for role in leads(actor).filter(case=case).values_list('role', flat=True):
        actions.update(LEAD_ACTIONS[role])
        if role == 'pmo-lead':
            actions.add('team.actions.read')
    return actions

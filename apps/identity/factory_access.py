"""Workspace navigation and operational access derived from current staff roles."""
from django.db.models import Exists, OuterRef, Q

from apps.core.models import Case

from .team_models import StaffMembership


DEPARTMENT_LEADS = ('pmo-lead', 'finance-lead')

# Preparation and source discovery. Decisions, publishing, private source
# access and external effects continue to require their native authority.
LEAD_ACTIONS = {
    'pmo-lead': frozenset({
        'case.read', 'factory.read', 'factory.start', 'agent.extract', 'evidence.add',
        'engagement.read', 'engagement.capture', 'planning.read', 'delivery.read', 'delivery.planning_decide',
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
    scope = organisation_scope(memberships.filter(mode='lead')) if role in DEPARTMENT_LEADS else Q(pk__in=[])
    if not heads_only:
        scope |= Q(pk__in=memberships.values('case_id'))
    return Case.objects.filter(scope, kind='project')


def organisation_scope(memberships):
    return Q(Exists(memberships.filter(case__tenant=OuterRef('tenant'), case__synthetic=OuterRef('synthetic'))))


def management_cases(actor):
    """Workspace entry for current PSL department leads and executives."""
    current = StaffMembership.objects.filter(user=actor, user__is_active=True, active=True, case__kind='project')
    positions = current.filter(Q(role__in=DEPARTMENT_LEADS, mode='lead') |
                               Q(role__in=('ceo', 'cto'), mode='standalone'))
    return Case.objects.filter(organisation_scope(positions), kind='project').distinct()


def role_managed(actor):
    # Keep a revoked account from falling back to an earlier assistant grant.
    return StaffMembership.objects.filter(user=actor).exists()


def leads(actor):
    return StaffMembership.objects.filter(user=actor, user__is_active=True, active=True,
                                          mode='lead', role__in=LEAD_ACTIONS, case__kind='project')


def authorized_leads(actor, actions):
    actions = frozenset(actions)
    # Match the complete combination to one current role before expanding its
    # workspace scope.
    roles = [name for name, allowed in LEAD_ACTIONS.items() if actions <= (allowed | DEPARTMENT_READS.get(name, frozenset()))]
    return leads(actor).filter(role__in=roles)


def role_cases(actor, actions):
    eligible = authorized_leads(actor, actions)
    query = Q(pk__in=eligible.values('case_id')) | (
        Q(kind='project') & organisation_scope(eligible.filter(role__in=DEPARTMENT_LEADS)))
    for role, allowed in DEPARTMENT_READS.items():
        if actions and set(actions) <= allowed:
            query |= Q(pk__in=department_cases(actor, role).values('pk'))
    return Case.objects.filter(query).distinct()


def project_cases(actor):
    from .services import visible_cases

    return (visible_cases(actor) | role_cases(actor, ['case.read']) | management_cases(actor)).filter(kind='project')


def project_actions(actor, case):
    from .services import active_case_grants, legacy_projects

    actions = {action for _, action in active_case_grants(actor, [case.pk])}
    if actions and not legacy_projects(actor, Case.objects.filter(pk=case.pk)).exists():
        actions.clear()
    for role, allowed in DEPARTMENT_READS.items():
        if department_cases(actor, role).filter(pk=case.pk).exists():
            actions.update(allowed)
    lead_scope = Q(case=case) | Q(role__in=DEPARTMENT_LEADS, case__tenant=case.tenant,
                                 case__synthetic=case.synthetic, case__kind=case.kind)
    for role in leads(actor).filter(lead_scope).values_list('role', flat=True).distinct():
        actions.update(LEAD_ACTIONS[role])
    if leads(actor).filter(case=case, role='pmo-lead').exists():
        actions.add('team.actions.read')
    return actions

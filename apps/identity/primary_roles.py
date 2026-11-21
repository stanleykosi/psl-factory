"""Primary workspace roles use native grants and leave approval authority to domain rules."""
import re
from uuid import UUID

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Q
from django.http import Http404
from django.utils.text import slugify

from apps.core.models import Case
from apps.core.services import bump, event
from apps.documents.contracts import digest

from . import intake, staff, staff_accounts
from .intake_models import AccessChange
from .models import Grant
from .services import require, visible_cases
from .staff_models import StaffPrimaryRoleChange, StaffRoleDefinition


FUNCTIONS = {
    'workspace': ('Workspace and work queue', frozenset({'factory.read'})),
    'planning': ('Engagement and planning', frozenset({'engagement.read', 'planning.read'})),
    'delivery': ('Delivery and release records', frozenset({'delivery.read'})),
    'changes': ('Issues, changes and incidents', frozenset({'issue.read', 'change.read', 'emergency.read'})),
    'reporting': ('Project reports', frozenset({'report.read'})),
    'meetings': ('Minutes and actions', frozenset({'meeting.read'})),
    'finance': ('Invoices, payments and Finance close', frozenset({'finance.read', 'payment.read'})),
    'finance_schedules': ('Financial schedules and fixed assets', frozenset({'schedules.read', 'ppe.read'})),
    'hr_handoff': ('HR handoffs and staff-cost follow-up', frozenset({'hrfinance.read'})),
    'executive': ('Approved project summaries', frozenset({'project.view'})),
}
BUILT_INS = {
    'pmo-lead': ('PMO Lead', 'Oversee planning, delivery, reporting and escalations.',
                 ('workspace', 'planning', 'delivery', 'changes', 'reporting', 'meetings')),
    'finance-lead': ('Finance Lead', 'Oversee invoices, payments and the Finance close.',
                     ('workspace', 'finance', 'finance_schedules')),
    'ceo': ('CEO', 'See approved summaries and leadership reports in assigned workspaces.',
            ('executive', 'reporting')),
    'cto': ('CTO', 'Oversee technical readiness, releases, changes and incidents.',
            ('workspace', 'delivery', 'changes')),
    'hr': ('HR', 'Follow up on HR disclosures, staff matching and staff-cost questions.',
           ('hr_handoff',)),
    'admin': ('Admin', 'Manage staff access and roles within a current delegated workspace.',
              ()),
}
CATALOGUE_VERSION = 2
MAX_CUSTOM_ROLES = 50
CUSTOM_ALIAS = re.compile(r'custom-role-[0-9]+(?:-[0-9]+)?')
ACTION_LABELS = {
    'factory.read': 'View work and queues', 'engagement.read': 'View engagement records',
    'planning.read': 'View project plans', 'delivery.read': 'View delivery and release records',
    'issue.read': 'View issues and escalations', 'change.read': 'View change records',
    'emergency.read': 'View Emergency records', 'report.read': 'View project reports',
    'meeting.read': 'View meeting minutes and actions', 'finance.read': 'View invoices and Finance close',
    'payment.read': 'View payment assessments', 'schedules.read': 'View financial schedules',
    'ppe.read': 'View fixed assets', 'project.view': 'View approved project summaries',
    'hrfinance.read': 'View HR handoffs and staff-cost follow-up',
}


def built_ins():
    return [{'key': key, 'name': name, 'description': description, 'functions': list(functions),
             'definition_id': None}
            for key, (name, description, functions) in BUILT_INS.items()]


def catalogue(case):
    definitions = list(StaffRoleDefinition.objects.filter(case=case).order_by('name', 'pk'))
    reserved = set(BUILT_INS) | {role.key for role in definitions}
    entries = built_ins()
    for role in definitions:
        key = role.key
        if key in BUILT_INS:
            # A built-in may be added after an Admin created a role with the same key.
            base = key = f'custom-role-{role.pk}'
            suffix = 1
            while key in reserved:
                key = f'{base}-{suffix}'
                suffix += 1
            reserved.add(key)
        details = 'Previously added for this workspace.' if key != role.key else ''
        entries.append({'key': key, 'name': role.name, 'description': details, 'functions': role.functions,
                        'definition_id': role.pk})
    return entries


def administrator(actor, case):
    if case.kind != 'project':
        raise PermissionDenied('Primary roles apply to managed project workspaces.')
    configuration, _ = staff.authority(actor, case, 'allow_profile_edit')
    return configuration


def is_admin(actor, case):
    try:
        administrator(actor, case)
    except PermissionDenied:
        return False
    return True


def administered_projects(actor):
    scope = Q(pk__in=[])
    for delegation in intake.options(actor, 'manage_access'):
        if ('project' in delegation.value['kinds']
                and delegation.value.get('staff_lifecycle', {}).get('allow_profile_edit') is True):
            scope |= Q(tenant=delegation.tenant, synthetic=delegation.value['classification']=='synthetic')
    return visible_cases(actor).filter(scope,kind='project')


def actions(functions):
    return set().union(*(FUNCTIONS[key][1] for key in functions))


@transaction.atomic
def create_definition(actor, case_id, name, functions, reason):
    from apps.core.read_observation import assert_command_allowed

    assert_command_allowed()
    case = Case.objects.select_for_update().get(pk=case_id)
    intake.lock_users([actor.pk])
    configuration = administrator(actor, case)
    intake.text(name, 80)
    intake.text(reason, 1000)
    key = '-'.join(part for part in slugify(name).replace('_', '-').split('-') if part)
    if not key or len(key) > 50 or key in BUILT_INS or CUSTOM_ALIAS.fullmatch(key):
        raise ValidationError('Choose a unique role name distinct from the built-in roles.')
    if (not isinstance(functions, list) or not functions or len(functions) > len(FUNCTIONS)
            or any(not isinstance(item, str) or item not in FUNCTIONS for item in functions)
            or len(set(functions)) != len(functions)):
        raise ValidationError('Select distinct workspace functions from the available list.')
    if actions(functions) - set(configuration.value['allowed_actions']):
        raise PermissionDenied('The selected functions exceed your current delegation.')
    rows = StaffRoleDefinition.objects.filter(case=case)
    if rows.filter(key=key).exists():
        raise ValidationError('CONFLICT: A role already uses this name.')
    if rows.count() >= MAX_CUSTOM_ROLES:
        raise ValidationError('This workspace reached its role catalogue limit.')
    role = rows.create(actor=actor, authority=configuration, case=case, key=key, name=name,
                       functions=sorted(functions), reason=reason)
    event(actor, case, 'staff.role_defined', definition=role.pk, role=key)
    bump(case)
    return role


def role_head(case, person):
    return StaffPrimaryRoleChange.objects.filter(case=case, user=person).order_by('-pk').first()


def person_for(case, person_id):
    person = get_user_model().objects.filter(pk=person_id, is_active=True, grant__case=case,
        grant__action='case.read', grant__active=True).first()
    if person is None:
        raise Http404
    return person


def description(key, name, state='active'):
    return {'key': key, 'name': name, 'state': state}


def current_role(previous, roles, active):
    if not previous or not previous.role_key:
        return None
    if previous.definition_id is not None:
        role = next((item for item in roles if item['definition_id'] == previous.definition_id), None)
    else:
        role = next((item for item in roles if item['definition_id'] is None and item['key'] == previous.role_key), None)
    complete = role is not None and actions(role['functions']) <= active
    return description(role['key'] if role else previous.role_key, previous.role_name,
                       'active' if complete else 'review_needed')


def review(actor, case, person_id):
    config = administrator(actor, case)
    person = person_for(case, person_id)
    if (person.pk == actor.pk or person.is_staff or person.is_superuser or
            staff_accounts._technical_authority(person)):
        raise PermissionDenied('This account requires its separately delegated administration controls.')
    previous = role_head(case, person)
    active = set(Grant.objects.filter(case=case, user=person, active=True).values_list('action', flat=True))
    heads = dict(AccessChange.objects.filter(case=case, subject=person).order_by('action', '-pk')
                 .distinct('action').values_list('action', 'pk'))
    managed = {key: value for key, value in (previous.managed_access if previous else {}).items()
               if key in active and heads.get(key) == value}
    roles = [item for item in catalogue(case) if item['key'] != 'admin']
    current = current_role(previous, roles, active)
    return {'case': case, 'person': person, 'authority': config, 'previous': previous, 'active': active,
            'heads': heads, 'managed': managed, 'roles': roles, 'current': current}


def proposal(reviewed, key):
    selected = next((item for item in reviewed['roles'] if item['key'] == key), None)
    if key and selected is None:
        raise ValidationError('Choose a role in this workspace’s catalogue.')
    targets = actions(selected['functions']) if selected else set()
    added = sorted(targets - reviewed['active'])
    removed = sorted(set(reviewed['managed']) - targets)
    allowed = set(reviewed['authority'].value['allowed_actions'])
    if set(added + removed) - allowed or targets - allowed:
        raise PermissionDenied('The selected role change exceeds your current delegation.')
    previous = reviewed['previous']
    previous_key = reviewed['current']['key'] if reviewed['current'] else None
    token = digest({
        'case': str(reviewed['case'].pk), 'revision': reviewed['case'].revision,
        'person': reviewed['person'].pk, 'authority': reviewed['authority'].pk,
        'previous': previous.pk if previous else None, 'catalogue': CATALOGUE_VERSION, 'selection': selected,
        'active': sorted(reviewed['active']), 'heads': reviewed['heads'],
    })
    return {'selected': selected, 'added': added, 'removed': removed, 'fingerprint': token,
            'changed': bool(added or removed or key != previous_key)}


@transaction.atomic
def apply(actor, case_id, person_id, key, fingerprint, reason, operation):
    from apps.core.read_observation import assert_command_allowed

    assert_command_allowed()
    intake.text(reason, 1000)
    try:
        operation = UUID(str(operation))
    except (TypeError, ValueError):
        raise ValidationError('Use the displayed change request.') from None
    case = Case.objects.select_for_update().get(pk=case_id)
    intake.lock_users([actor.pk, person_id])
    reviewed = review(actor, case, person_id)
    intent = digest({'role': key, 'preview': fingerprint, 'reason': reason})
    previous_request = StaffPrimaryRoleChange.objects.filter(operation=operation).first()
    if previous_request:
        actual = (previous_request.actor_id, previous_request.case_id, previous_request.user_id,
                  previous_request.intent_sha256, previous_request.authority_id)
        if actual != (actor.pk, case.pk, person_id, intent, reviewed['authority'].pk):
            raise ValidationError('IDEMPOTENCY_CONFLICT: This request already recorded a different role change.')
        return previous_request
    change = proposal(reviewed, key)
    if fingerprint != change['fingerprint']:
        raise ValidationError('STALE_VERSION: Access changed. Review the role again.')
    if not change['changed']:
        raise ValidationError('Choose a change to this person’s current role.')
    if change['removed']:
        staff.require_work_handover(case, reviewed['person'])
    owned = reviewed['managed'].copy()
    for action in change['removed']:
        intake.change_access(actor, case.pk, person_id, action, False, reason)
        owned.pop(action)
    for action in change['added']:
        access = intake.change_access(actor, case.pk, person_id, action, True, reason)
        owned[action] = access.pk
    selected = change['selected']
    row = StaffPrimaryRoleChange.objects.create(case=case, user=reviewed['person'], actor=actor,
        authority=reviewed['authority'], role_key=key or '', role_name=selected['name'] if selected else '',
        definition_id=selected['definition_id'] if selected else None, managed_access=owned,
        added=change['added'], removed=change['removed'], operation=operation, intent_sha256=intent, reason=reason)
    event(actor, case, 'staff.primary_role_changed', change=row.pk, person=person_id, role=key)
    bump(case)
    return row


def own_role(actor, case):
    require(actor, case, 'case.read')
    if is_admin(actor, case):
        return description('admin', BUILT_INS['admin'][0])
    previous = role_head(case, actor)
    if not previous or not previous.role_key:
        return None
    current = set(Grant.objects.filter(case=case, user=actor, active=True).values_list('action', flat=True))
    return current_role(previous, catalogue(case), current)

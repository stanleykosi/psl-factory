"""Read-only setup summary over the named Finance workflow contracts."""

from typing import NamedTuple

from django.core.exceptions import ImproperlyConfigured, PermissionDenied
from django.urls import reverse

from apps.policy.factory_accounting_validators import COMPONENT as ACCOUNTING_PROFILE
from apps.policy.factory_forecast_validators import COMPONENT as FORECAST_PROFILE
from apps.policy.registry import components
from apps.policy.role_assignments import COMPONENT as ROLES, authorize_header
from apps.policy.services import Resolution, reference_values, resolve


GROUP_DISCLOSURE = 'D10.audience_projection_rules'


class FinanceRule(NamedTuple):
    label: str
    components: tuple[str, ...]
    fields: tuple[str, ...] = ()
    assignment: bool = False


FINANCE_RULE_GROUPS = (
    ('Management accounts', ('finance.read',), 'finance_analysis', (
        FinanceRule('Statement contract', ('D06.statement_contract',)),
        FinanceRule('Business-unit metrics', (ACCOUNTING_PROFILE,), ('bu_metrics',)),
        FinanceRule('Report template and audience', (ACCOUNTING_PROFILE,), ('template_id', 'audience')),
        FinanceRule('Finance executor who publishes', (ACCOUNTING_PROFILE,), ('executor_id',), assignment=True),
    )),
    ('Income schedules', ('finance.read', 'schedules.read'), 'finance_schedules', (
        FinanceRule('Income detail rules', ('F12.detail_rules',)),
        FinanceRule('Inventory rules', ('F13.inventory_rules',)),
        FinanceRule('Who reviews schedules', ('SCHEDULES.review_authority',), assignment=True),
    )),
    ('Asset schedule', ('finance.read', 'ppe.read'), 'ppe', (
        FinanceRule('Register rules', ('F07.source_rules',)),
        FinanceRule('Calculation rules', ('F07.calculation_rules',)),
        FinanceRule('Who reviews assets', ('F07.review_authority',), assignment=True),
    )),
    ('Cash forecast', ('finance.read',), 'finance_forecast', (
        FinanceRule('Forecast preparer', (FORECAST_PROFILE,), ('preparer_id',), assignment=True),
        FinanceRule('Inclusion rule', ('D10.forecast_inclusion_rule_id',)),
        FinanceRule('Group reviewer', (GROUP_DISCLOSURE, ROLES), assignment=True),
    )),
    ('Business-unit totals', ('bu.read',), 'bu', (
        FinanceRule('Staff allocation rules', ('F21.allocation_rules',)),
        FinanceRule('Event source and attribution rules', ('F44.source_rules', 'F44.attribution_rules')),
        FinanceRule('Who reviews business-unit totals', ('BU.review_authority',), assignment=True),
        FinanceRule('Disclosure rules and recipients', ('BU.disclosure_rules',)),
    )),
    ('Ledger sources', ('finance.read', 'ledger.read'), 'ledger', (
        FinanceRule('Verification rules', ('F01.verification_rules',)),
        FinanceRule('Conflict rules', ('F01.conflict_rules',)),
        FinanceRule('Who reviews ledger sources', ('F01.review_authority',), assignment=True),
    )),
    ('Payroll', ('payroll.read', 'payroll.private.read'), 'payroll', (
        FinanceRule('Who may read inputs', ('F16.input_access_rules',), assignment=True),
        FinanceRule('Merge rules', ('F16.merge_rules',)),
        FinanceRule('Match rules', ('F17.match_rules',)),
        FinanceRule('Reporting rules', ('F18.reporting_rules',)),
        FinanceRule('Who reviews payroll', ('F18.review_authority',), assignment=True),
    )),
)


def rule_row(rule, results):
    row = {'label': rule.label}
    failed = [result.status for result in results if result.status != 'ACTIVE']
    if failed:
        status = 'UNAVAILABLE' if 'UNAVAILABLE' in failed else failed[0]
    else:
        status = 'ACTIVE'
        if rule.fields:
            values = reference_values(results[0].configuration)[0]
            if rule.fields == ('bu_metrics',) and values['allocation_mode'] == 'company_only':
                row['value'] = 'Company totals only'
            elif any(values[field] is None for field in rule.fields):
                status = 'MISSING'
        elif rule.components == (GROUP_DISCLOSURE, ROLES):
            projection = reference_values(results[0].configuration)[0].get('group')
            assignments = reference_values(results[1].configuration)
            if not projection or not any(assignment['role'] in projection['reviewer_roles'] for assignment in assignments):
                status = 'MISSING'
    row['status'] = 'UNASSIGNED' if status == 'MISSING' and rule.assignment else status
    if status == 'ACTIVE':
        row['revisions'] = [result.configuration.revision for result in results]
    return row


def groups(actor, case, permissions, at):
    registry = components()
    resolved = {}

    def lookup(component):
        if component not in registry:
            raise ImproperlyConfigured(f'Unregistered Finance setup component: {component}')
        if component not in resolved:
            try:
                authorize_header(actor, case, component)
            except PermissionDenied:
                resolved[component] = Resolution('UNAVAILABLE', component)
            else:
                resolved[component] = resolve(component, case, at=at)
        return resolved[component]

    overview = []
    profile_workflows = {'finance_analysis': 'finance-accounts/v1', 'finance_forecast': 'finance-forecast/v1'}
    for label, required, route, rules in FINANCE_RULE_GROUPS:
        if not permissions.issuperset(required):
            overview.append({'label': label, 'restricted': True})
            continue
        group = {'label': label, 'url': reverse(route, args=[case.pk]),
                 'rules': [rule_row(rule, [lookup(component) for component in rule.components]) for rule in rules]}
        if 'policy.configure' in permissions:
            if route in profile_workflows:
                setup = reverse('factory_configuration', args=[case.pk])
                group['configuration'] = setup + '?definition=' + profile_workflows[route]
                group['configuration_label'] = 'Review workflow setup'
            elif route == 'payroll':
                group['configuration'] = reverse('payroll_row_controls', args=[case.pk])
                group['configuration_label'] = 'Review payroll source controls'
        overview.append(group)
    return overview

"""Current, authorized business rule summaries for workspace Setup."""
from typing import NamedTuple

from django.core.exceptions import ObjectDoesNotExist, PermissionDenied, ValidationError
from django.urls import reverse

from apps.finance.project_money import STAGES
from apps.identity.services import active_case_grants
from apps.pmo.costing_models import CostingRule
from apps.pmo.models import Baseline
from apps.policy.bid_adjustment_validators import COMPONENT as BID_ADJUSTMENTS
from apps.policy.costing_validators import COMPONENT as COSTING
from apps.policy.models import ScopeApplication, ScopeVersion
from apps.policy.role_assignments import COMPONENT as ASSIGNMENTS, authorize_header
from apps.policy.services import reference_values, resolve
from apps.policy.short_payment_validators import COMPONENT as SHORT_PAYMENT, TREATMENTS

from .evidence_access import public_evidence
from .read_budget import ReadBudget, ReadLimit, limit_queries


BOARD_QUERY_LIMIT = 240
COMPONENT_QUERY_LIMIT = 68
MATRIX = 'D05.decision_action_matrix'
HYPERCARE = 'D11.hypercare_criteria_ref'
ARCHIVE = 'D11.template_storage_retention_rules'
AGREEMENT = 'D12.contract_version_ref'
PAYMENT_TERMS = 'D12.stage_terms'
RFP_READ = ('rfp.read',)
DOCUMENT_READ = ('document.read',)
COST_READ = ('costing.read', 'costing.source.read')
FINANCE_READ = ('finance.read',)
SHORT_PAYMENT_READ = (*FINANCE_READ, 'finance.short_payment.read')
DELIVERY_READ = ('delivery.read',)


class ObservedRule(NamedTuple):
    status: str
    revision: int | None
    values: tuple


def _can_read_origin(actor, case_id, permissions):
    needed = {'case.read', 'policy.read', *permissions}
    observed = active_case_grants(actor, [case_id], actions=needed)
    return all((case_id, action) in observed for action in needed)


def _lookup(actor, case, permissions, component, domains, at, budget):
    if not permissions.issuperset(domains):
        return ObservedRule('UNAVAILABLE', None, ())
    try:
        with limit_queries(COMPONENT_QUERY_LIMIT):
            header = authorize_header(actor, case, component)
            if header is None:
                return ObservedRule('MISSING', None, ())
            origin_id = ScopeApplication.objects.filter(configuration=header).values_list(
                'source__configuration__case_id', flat=True).first()
            if origin_id and not _can_read_origin(actor, origin_id, domains):
                return ObservedRule('UNAVAILABLE', None, ())
            if component == COSTING:
                candidate = reference_values(header, budget=budget)[0]
                studio_id = candidate.get('studio_source_id')
                if studio_id:
                    studio_owner = ScopeVersion.objects.filter(
                        pk=studio_id, kind='organization', ref=case.tenant,
                        configuration__component=component,
                        configuration__case__tenant=case.tenant,
                        configuration__case__synthetic=case.synthetic,
                    ).values_list('configuration__case_id', flat=True).first()
                    if not studio_owner or not _can_read_origin(actor, studio_owner, domains):
                        return ObservedRule('UNAVAILABLE', None, ())
            rule = resolve(component, case, at=at, budget=budget)
            if rule.status != 'ACTIVE':
                return ObservedRule(rule.status, None, ())
            if rule.configuration.pk != header.pk:
                return ObservedRule('UNKNOWN', None, ())
            return ObservedRule(rule.status, header.revision, tuple(reference_values(rule.configuration, budget=budget)))
    except PermissionDenied:
        return ObservedRule('UNAVAILABLE', None, ())
    except (ValidationError, ObjectDoesNotExist, ReadLimit):
        return ObservedRule('UNKNOWN', None, ())


def _row(label, area, observed, component, *, value=None, details=(), roles=(), route=None, case=None):
    present = bool(value or roles)
    status = 'MISSING' if observed.status == 'ACTIVE' and not present else observed.status
    return {
        'label': label, 'area': area, 'status': status, 'version': observed.revision if present else None,
        'component': component,
        'value': value, 'details': details, 'roles': tuple(roles),
        'url': reverse(route, args=[case.pk]) if route and status != 'UNAVAILABLE' else None,
    }


def _payment_terms(case, contract, terms):
    for item in (contract, terms):
        if item.status != 'ACTIVE':
            return item, ()
    binding = contract.values[0]
    try:
        signed = Baseline.objects.filter(
            case=case, signed_id=binding['signed_evidence_id'], signed__sha256=binding['signed_sha256'],
            signed__in=public_evidence(case.evidence.all()),
        ).exists()
    except ReadLimit:
        return ObservedRule('UNKNOWN', None, ()), ()
    if not signed:
        return ObservedRule('INVALID', None, ()), ()
    dates = {item['stage']: item['due_date'] for item in terms.values
             if item['coverage_id'] == binding['coverage_id'] and item['due_date']}
    return terms, tuple(f'{label}: {dates[stage]}' for stage, label in STAGES.items() if stage in dates)


def _cost_limits(case, costing, adjustments):
    for item in (adjustments, costing):
        if item.status != 'ACTIVE':
            return item, ()
    data = adjustments.values[0]
    if data['rule_id'] != costing.values[0]['rule_id']:
        return ObservedRule('INVALID', None, ()), ()
    try:
        currency = CostingRule.objects.filter(case=case, pk=data['rule_id']).values_list(
            'payload__currency', flat=True).first()
    except ReadLimit:
        return ObservedRule('UNKNOWN', None, ()), ()
    if not currency:
        return ObservedRule('INVALID', None, ()), ()
    targets = data['targets']
    limits = [f'{item["label"]}: {currency} {item["max_absolute_value"]}' for item in targets[:12]]
    if len(targets) > len(limits):
        limits.append(f'{len(targets) - len(limits)} more in rule settings')
    return adjustments, limits


def rows(actor, case, permissions, at):
    budget = ReadBudget()

    def read(component, domains):
        return _lookup(actor, case, permissions, component, domains, at, budget)

    with limit_queries(BOARD_QUERY_LIMIT):
        matrix = read(MATRIX, RFP_READ)
        bid_roles = matrix.values[0].get('rfp', {}) if matrix.values else {}
        assignments = read(ASSIGNMENTS, DOCUMENT_READ)
        # The standard client document review task names this role. Specialist
        # Finance and internal leadership flows have their own review rules.
        reviewers = ('PMO Lead',) if any(item['role'] == 'PMO Lead' for item in assignments.values) else ()
        calculation = read(COSTING, COST_READ)
        short_pay = read(SHORT_PAYMENT, SHORT_PAYMENT_READ)
        treatments = short_pay.values[0]['treatments'] if short_pay.values else ()
        hypercare = read(HYPERCARE, DELIVERY_READ)
        criteria = hypercare.values[0] if hypercare.values else {}
        archive = read(ARCHIVE, (*DELIVERY_READ, *DOCUMENT_READ))
        archive_value = f'Internal versioned archive for {archive.values[0]["retention_days"]} days' if archive.values else None
        payment_terms, due_dates = _payment_terms(case, read(AGREEMENT, FINANCE_READ), read(PAYMENT_TERMS, FINANCE_READ))
        adjustments, limits = _cost_limits(case, calculation, read(BID_ADJUSTMENTS, COST_READ))

    return [
        _row('Who may assign a bid to a project manager', 'Pre-sale', matrix, MATRIX, roles=bid_roles.get('assignment_roles', ()), route='rfp', case=case),
        _row('Who reviews client documents', 'All lines', assignments, ASSIGNMENTS, roles=reviewers, route='documents', case=case),
        _row('Costing rule', 'Pre-sale', calculation, COSTING, value='Reviewed calculation and independent examples' if calculation.values else None, route='costing', case=case),
        _row('Short payments (e.g. tax deducted)', 'Finance', short_pay, SHORT_PAYMENT, value='Finance review' if treatments else None,
             details=tuple(TREATMENTS[key] for key in treatments), route='finance_settlement', case=case),
        _row('Hypercare criteria', 'Delivery', hypercare, HYPERCARE,
             value=f'{criteria["minimum_hours"]} hours after release' if criteria else None,
             details=tuple(criteria.get('confirmation_owners', ())), route='delivery', case=case),
        _row('Archive storage and retention', 'Delivery', archive, ARCHIVE, value=archive_value, route='delivery', case=case),
        _row('Invoice payment terms default', 'Finance', payment_terms, PAYMENT_TERMS,
             value='From the signed agreement' if due_dates else None, details=due_dates, route='finance_billing', case=case),
        _row('Who may record a bid outcome', 'Pre-sale', matrix, MATRIX, roles=bid_roles.get('outcome_roles', ()), route='rfp', case=case),
        _row('Who may adjust a project’s costing', 'Pre-sale', adjustments, BID_ADJUSTMENTS,
             value='Assigned project manager' if limits else None, route='costing', case=case),
        _row('Costing adjustment limit', 'Pre-sale', adjustments, BID_ADJUSTMENTS, value='Maximum resulting value for each configured input' if limits else None,
             details=limits, route='costing', case=case),
    ]

"""Read-only F03 draft diagnostics. Never a FinanceRun or an approval input."""
from collections import Counter

from django.core.exceptions import ValidationError
from django.db import transaction
from jsonschema import Draft202012Validator, FormatChecker

from adapters.finance_analysis import LocalFinanceSourceAdapter
from apps.core.services import lock_case
from apps.identity.services import require
from apps.policy.models import Configuration, RegisteredReference
from apps.policy.registry import envelope_schema
from apps.policy.services import active_component, reference_values, validate_envelope
from .analysis import digest, source_for
from .mapping import effective

COMPONENT = 'D06.account_bu_maps'


def _draft_candidates(case, configuration_id):
    config = Configuration.objects.filter(case=case, pk=configuration_id, component=COMPONENT).first()
    state = config.states.order_by('-pk').first() if config else None
    if not state or state.state != 'draft':
        raise ValidationError('Select this case DRAFT mapping configuration; diagnostics never validate or activate it')
    envelope = config.envelope
    errors = list(Draft202012Validator(envelope_schema(), format_checker=FormatChecker()).iter_errors(envelope))
    if errors:
        raise ValidationError(['Invalid mapping draft envelope: ' + error.message for error in errors])
    if envelope['component_id'] != COMPONENT or envelope['lifecycle'] != 'draft':
        raise ValidationError('Draft mapping identity does not match its envelope')
    refs = envelope['value']
    if not isinstance(refs, list) or not 1 <= len(refs) <= 100 or len(set(refs)) != len(refs):
        raise ValidationError('Select 1–100 distinct typed mapping references')
    candidates = []
    for index, ref in enumerate(refs):
        # Full envelope and per-record checks are unchanged. Only cross-record
        # overlap is examined as a diagnostic, never accepted by the validator.
        validate_envelope(case, dict(envelope, value=[ref]))
        target = RegisteredReference.objects.get(case=case, ref=ref, version=1)
        candidates.append(dict(target.content, reference_id=target.pk, reference=ref,
            reference_version=target.version, reference_sha256=target.sha256,
            evidence_id=target.evidence_id, candidate_index=index))
    if len({item['key'] for item in candidates}) != len(candidates):
        raise ValidationError('Finance configuration keys must be unique')
    return config, candidates


@transaction.atomic
def preview_mapping_draft(actor, case_id, source_id, configuration_id, expected):
    """Return exact source/candidate evidence without any persistent effect.

    No adjustments, allocation, formula, review, publication, or receipt path
    consumes this result. Even a conflict-free draft remains non-authoritative.
    """
    case = lock_case(actor, case_id, 'finance.calculate', expected)
    require(actor, case, 'case.read')
    require(actor, case, 'finance.read')
    require(actor, case, 'policy.read')
    source = source_for(case, source_id)
    from .source_units import require_mapping
    require_mapping(source)
    config, candidates = _draft_candidates(case, configuration_id)
    schema = active_component('D06.source_schema_ref', case)
    convention_config = active_component('D06.unit_sign_currency_period', case)
    convention = reference_values(convention_config)[0]
    data = LocalFinanceSourceAdapter().read(source)
    applicable = effective(candidates, source.entity, convention['period'])
    counts = Counter(row['account'] for row in data['rows'])
    rows, exceptions = [], []
    for raw in data['rows']:
        matches = [candidate for candidate in applicable if candidate['account'] == raw['account']]
        status = 'unmapped' if not matches else 'ambiguous' if len(matches) > 1 else 'single_candidate'
        findings = [finding['message'] for finding in data['findings'] if finding['line'] == raw['line']]
        if raw['currency'] != convention['currency'] or raw['period'] != convention['period']:
            findings.append('Currency/period differs from the selected convention; no conversion')
        if counts[raw['account']] > 1:
            findings.append('Repeated source account retained as separate source rows')
        row = {'source_line': raw['line'], 'source_evidence': source.batch.evidence_id,
            'account': raw['account'], 'raw_amount': raw['amount'], 'currency': raw['currency'],
            'period': raw['period'], 'status': status, 'candidate_keys': [item['key'] for item in matches],
            'candidate_reference_ids': [item['reference_id'] for item in matches],
            'selected_mapping': None, 'findings': findings}
        rows.append(row)
        if status in ['unmapped', 'ambiguous']:
            exceptions.append({'code': 'UNMAPPED_ACCOUNT' if status == 'unmapped' else 'AMBIGUOUS_MAPPING',
                'source_line': raw['line'], 'source_evidence': source.batch.evidence_id,
                'account': raw['account'], 'candidate_reference_ids': row['candidate_reference_ids']})
    snapshot = {'source_id': source.pk, 'source_hash': source.batch.source_sha256,
        'source_context_evidence_id': source.evidence_id, 'configuration_id': config.pk,
        'configuration_revision': config.revision, 'configuration_hash': digest(config.envelope),
        'configuration_state': 'draft', 'schema_configuration_id': schema.pk,
        'convention_configuration_id': convention_config.pk}
    return {'implementation': 'finance-draft-mapping-diagnostics/v1', 'status': 'draft_only',
        'draft_only': True, 'authoritative': False, 'approval_granted': False,
        'ledger_posted': False, 'rules_changed': False, 'finance_run_created': False,
        'snapshot': snapshot, 'entity': source.entity, 'period': convention['period'],
        'currency': convention['currency'], 'rows': rows, 'exceptions': exceptions,
        'candidates': candidates, 'source_evidence_ids': sorted({source.evidence_id,
            source.batch.evidence_id} | {item['evidence_id'] for item in candidates}),
        'next_work': 'Finance must resolve the exact unmapped and conflicting draft entries, then validate, activate and review a new mapping through the existing controls. This diagnostic supplies no approved accounts or downstream output.'}

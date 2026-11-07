"""Draft-only generation, with durable claim-before-send and lookup-only recovery.

No lease expiry, absence observation or cancellation can authorize another generation.
Existing D03 confirmation is reused; this is not an extra invoice approval.
"""
import json
from django.core.exceptions import ValidationError, PermissionDenied
from django.db import connection, transaction
from django.db.models import Max
from django.utils import timezone
from apps.core.services import event, bump
from apps.documents.contracts import digest, validate
from apps.identity.services import require
from apps.identity.models import Grant
from apps.policy.services import active_component, reference_values
from apps.policy.d03_validators import STATEMENT
from adapters.forecast import obj, KEY
from adapters.hrfinance import timestamp
from adapters.draft_generation import configured_adapter, MockDraftGenerationAdapter
from . import billing_evidence as d
from .billing import ensure_current, exact
from .fixed_charge import preparation_access
from .invoices import obligation
from .models import BillingPreparation, DraftGeneration, DraftGenerationAttempt, DraftGenerationObservation, DraftGenerationCancellation

HASH = {'type': 'string', 'pattern': '^[a-f0-9]{64}$'}
CONTRACT = obj({'schema': {'const': 'draft-generation-contract/v1'}, 'action': {'const': 'draft_generation'},
    'implementation': {'const': 'mock_draft_generation_v1'}, 'draft_only': {'const': True},
    'flow_ref': KEY, 'flow_version': KEY, 'environment_ref': KEY,
    'output_contract': obj({'schema': {'const': 'draft-document/v1'}, 'document_ref': KEY,
                            'posted': {'const': False}, 'sent': {'const': False}})})
nullable = lambda schema: {'anyOf': [schema, {'type': 'null'}]}
OBSERVATION = obj({'schema': {'const': 'draft-generation-observation/v1'}, 'tenant': KEY,
    'case': {'type': 'string'}, 'operation_key': KEY, 'intent_sha256': HASH,
    'observed_at': {'type': 'string'}, 'outcome': {'enum': ['found', 'unknown', 'not_found']},
    **{key: nullable(KEY) for key in ['run_id', 'document_ref', 'document_version']},
    'document_sha256': nullable(HASH),
    **{key: nullable({'type': 'boolean'}) for key in ['generated', 'posted', 'sent']}})


def authority(actor, case):
    d.readable(actor, case)
    require(actor, case, 'finance.draft_generation.dispatch')
    require(actor, case, 'd03.source.read')
    return list(Grant.objects.filter(case=case, user=actor, active=True,
        action__in=['case.read', 'finance.read', 'd03.read', 'd03.source.read', 'finance.draft_generation.dispatch'])
        .order_by('action').values_list('action', 'pk'))


def contract(source):
    d.confirmed(source)
    if source.kind != 'flow_contract':
        raise ValidationError('Exact confirmed flow contract required')
    try:
        value = json.loads(source.payload['quote'])
    except (TypeError, ValueError):
        raise ValidationError('Confirmed source must contain the exact typed draft-only capability contract')
    validate(CONTRACT, value)
    if any(value[k] != source.payload[k] for k in ['flow_ref', 'flow_version', 'environment_ref']):
        raise ValidationError('Draft capability disagrees with confirmed source flow/environment/version')
    if source.payload['implementation'] != 'incumbent_reference_only':
        raise ValidationError('External draft generation must not impersonate the internal invoice adapter')
    return value


def pins(actor, preparation, source, batch_ref, operation_key):
    preparation_access(actor, preparation)
    ensure_current(preparation)
    capability = contract(source)
    statement = active_component(STATEMENT, preparation.case)
    # Existing D03 validator preserves exact reviewed wording and unresolved conflicts.
    statement_ref = reference_values(statement)[0]
    return {'schema': 'draft-generation-intent/v1', 'action': 'draft_generation',
        'tenant': preparation.case.tenant, 'case': str(preparation.case_id),
        'preparation': preparation.pk, 'preparation_key': preparation.operation_key,
        'batch_ref': batch_ref, 'batch_sha256': digest({'snapshot': preparation.snapshot, 'result': preparation.result}),
        'source': source.pk, 'source_sha256': source.sha256, 'source_review': d.confirmed(source).pk,
        'statement_policy': statement.pk, 'statement_reference': statement_ref,
        'actor': actor.pk, 'authority': [list(x) for x in authority(actor, preparation.case)],
        'operation_key': operation_key, **{k: v for k, v in capability.items() if k != 'schema'}}


@transaction.atomic
def reserve(actor, case_id, preparation_id, source_id, batch_ref, operation_key, expected=None):
    case = d.locked(actor, case_id, 'finance.draft_generation.dispatch', expected)
    validate(KEY, batch_ref); validate(KEY, operation_key)
    preparation = exact(case, BillingPreparation, preparation_id)
    source = d.exact_source(case, source_id)
    payload = pins(actor, preparation, source, batch_ref, operation_key)
    if not case.synthetic:
        raise ValidationError('Mock generation is restricted to explicit synthetic cases')
    d.advisory({'tenant': case.tenant, 'draft_generation': operation_key})
    old = DraftGeneration.objects.filter(tenant=case.tenant, operation_key=operation_key).first()
    if old:
        if old.payload != payload:
            raise ValidationError('Generation operation key conflicts with immutable intent')
        return old
    business_key = obligation(preparation)
    if DraftGeneration.objects.filter(tenant=case.tenant, business_key=business_key).exists():
        raise ValidationError('Business batch already has a generation intent; inspect original operation, never regenerate')
    row = DraftGeneration.objects.create(case=case, preparation=preparation, source=source, actor=actor,
        tenant=case.tenant, operation_key=operation_key, business_key=business_key, payload=payload, sha256=digest(payload))
    event(actor, case, 'draft_generation.reserved', generation=row.pk, posted=False, sent=False)
    bump(case)
    return row


def current(row):
    if DraftGenerationCancellation.objects.filter(generation=row).exists():
        raise ValidationError('Generation cancelled; original lookup remains available')
    if DraftGenerationObservation.objects.filter(attempt__generation=row, accepted=False).exists():
        raise ValidationError('Conflicting generation observation requires investigation')
    if row.payload != pins(row.actor, row.preparation, row.source, row.payload['batch_ref'], row.operation_key):
        raise ValidationError('Preparation, source, destination or authority changed; retain original intent for lookup')


@transaction.atomic
def claim(actor, case_id, generation_id):
    case = d.locked(actor, case_id, 'finance.draft_generation.lookup')
    row = exact(case, DraftGeneration, generation_id)
    original = row.attempts.filter(action='generate').first()
    if original:
        action = 'lookup'  # Revoked dispatch grants and stale sources do not block original lookup.
    else:
        if row.actor_id != actor.pk:
            raise PermissionDenied('Only the immutable intent actor may dispatch the initial generation')
        current(row)
        action = 'generate'
    sequence = (row.attempts.aggregate(n=Max('sequence'))['n'] or 0) + 1
    return DraftGenerationAttempt.objects.create(generation=row, action=action, sequence=sequence,
        intent_sha256=row.sha256, actor=actor)


@transaction.atomic
def observe(actor, case_id, attempt_id, fence, payload):
    case = d.locked(actor, case_id, 'finance.draft_generation.lookup')
    attempt = DraftGenerationAttempt.objects.select_related('generation').filter(pk=attempt_id, generation__case=case).first()
    if not attempt or str(attempt.fence) != str(fence):
        raise ValidationError('Exact original attempt fence required')
    validate(OBSERVATION, payload)
    row = attempt.generation
    sha = digest(payload)
    old = attempt.observations.filter(sha256=sha).first()
    if old:
        return old
    findings = []
    for key, value in {'tenant': row.tenant, 'case': str(row.case_id), 'operation_key': row.operation_key,
                       'intent_sha256': row.sha256}.items():
        if payload[key] != value:
            findings.append('Original operation identity mismatch')
    when = timestamp(payload['observed_at'])
    if when > timezone.now() or when < attempt.created_at:
        findings.append('Observation time outside original attempt')
    if payload['outcome'] == 'found':
        if any(payload[k] is None for k in ['run_id', 'document_ref', 'document_version', 'document_sha256']):
            findings.append('Missing exact generated document identity')
        if payload['document_ref'] != row.payload['output_contract']['document_ref']:
            findings.append('Destination/document output differs from immutable contract')
        if payload['generated'] is not True or payload['posted'] is not False or payload['sent'] is not False:
            findings.append('Result is not exclusively draft generation')
        identity = {'tenant': row.tenant, 'system': row.source.system,
                    'environment': row.payload['environment_ref'], 'document_ref': payload['document_ref'],
                    'document_version': payload['document_version']}
        d.advisory({'draft_output': identity})
        other = DraftGenerationObservation.objects.filter(accepted=True, payload__outcome='found',
            attempt__generation__tenant=row.tenant, attempt__generation__source__system=row.source.system,
            attempt__generation__payload__environment_ref=row.payload['environment_ref'],
            payload__document_ref=payload['document_ref'], payload__document_version=payload['document_version']).exclude(attempt__generation=row)
        if other.exists():
            findings.append('Generated document identity already belongs to another original operation')
        previous = DraftGenerationObservation.objects.filter(attempt__generation=row, accepted=True, payload__outcome='found').first()
        fact_keys = ['run_id', 'document_ref', 'document_version', 'document_sha256', 'generated', 'posted', 'sent']
        if previous and any(previous.payload[k] != payload[k] for k in fact_keys):
            findings.append('Conflicting original-operation result')
    elif any(payload[k] is not None for k in ['run_id', 'document_ref', 'document_version', 'document_sha256', 'generated', 'posted', 'sent']):
        findings.append('Unknown/not-found must not assert document facts')
    result = DraftGenerationObservation.objects.create(attempt=attempt, actor=actor, fence=attempt.fence, payload=payload, sha256=sha,
        accepted=not findings, finding='; '.join(sorted(set(findings)))[:240])
    event(actor, case, 'draft_generation.observed', observation=result.pk, accepted=result.accepted)
    bump(case)
    return result


def run_once(actor, case_id, generation_id, adapter=None):
    # A nested atomic block is a savepoint, not a durable claim before transport.
    if connection.in_atomic_block or not connection.get_autocommit():
        raise ValidationError('Draft generation requires an outer autocommit boundary')
    row = DraftGeneration.objects.select_related('case').get(pk=generation_id, case_id=case_id)
    d.readable(actor, row.case)
    require(actor, row.case, 'finance.draft_generation.lookup')
    adapter = adapter or configured_adapter(row.case)
    if not row.case.synthetic or type(adapter) is not MockDraftGenerationAdapter:
        raise ValidationError('Only the explicit synthetic transport is implemented')
    # The claim commits before the external call. A crash at any later instruction permits lookup only.
    attempt = claim(actor, case_id, generation_id)
    try:
        response = getattr(adapter, attempt.action)(attempt.generation.payload)
    except TimeoutError:
        return attempt
    return observe(actor, case_id, attempt.pk, attempt.fence, response)


@transaction.atomic
def cancel(actor, case_id, generation_id, reason):
    case = d.locked(actor, case_id, 'finance.draft_generation.cancel')
    row = exact(case, DraftGeneration, generation_id)
    if not isinstance(reason, str) or not 1 <= len(reason.strip()) <= 500:
        raise ValidationError('Bounded cancellation reason required')
    cancellation, created = DraftGenerationCancellation.objects.get_or_create(generation=row, defaults={'actor': actor, 'reason': reason})
    if created:
        event(actor, case, 'draft_generation.cancelled', generation=row.pk, remote_effect_cancelled=False)
        bump(case)
    return cancellation


def report(actor, case_id, generation_id):
    from apps.core.models import Case
    case = Case.objects.get(pk=case_id)
    d.readable(actor, case)
    row = exact(case, DraftGeneration, generation_id)
    preparation_access(actor, row.preparation)
    holds = []
    try:
        current(row)
    except (ValidationError, PermissionDenied) as exc:
        holds.append(str(exc))
    observations = list(DraftGenerationObservation.objects.filter(attempt__generation=row).order_by('pk'))
    found = [o for o in observations if o.accepted and o.payload['outcome'] == 'found']
    return {'generation': row.pk, 'batch_ref': row.payload['batch_ref'], 'operation_key': row.operation_key,
        'intent_sha256': row.sha256, 'generated': True if found else None, 'posted': False if found else None, 'sent': False if found else None,
        'result': found[0].payload if found else None, 'holds': holds,
        'attempts': list(row.attempts.values('id', 'action', 'sequence')),
        'observations': [{'id': o.pk, 'accepted': o.accepted, 'finding': o.finding, 'result': o.payload} for o in observations],
        'next_action': 'lookup_original_only' if row.attempts.exists() else 'held' if holds else 'draft_generation',
        'external_authenticity_verified': False, 'invoice_issue_created': False, 'invoice_delivery_created': False}

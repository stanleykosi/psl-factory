"""Shared scoped MCP broker. Agents and system callers have identical native gates."""
import hashlib
import hmac
import json
import os
from django.conf import settings
from django.core.exceptions import ValidationError, PermissionDenied
from django.db import transaction, connection
from django.db.models import Max
from django.utils import timezone
from apps.core.models import Evidence, Audit, Case
from apps.core.services import event, bump
from apps.documents.contracts import digest
from apps.finance import ledger
from adapters.quickbooks_mcp import Client, MCPError, VERSION, READ_TOOL, fingerprint, validate
from config.quickbooks_mcp_runtime import load

PREFIX = 'ledger.qbo.mcp.'
INTENT = 'integration_qbo_mcp_intent'
RESULT = 'integration_qbo_mcp_result'


def binding(contract):
    entry = next((v for v in load(settings.READINESS_SECRET_REFS).values() if v['contract_id'] == contract.pk), None)
    value = contract.payload
    if value['data_scope'] != 'scoped_qbo_invoice_identity_read_v1':
        raise ValidationError('Explicit reviewed MCP read data scope required')
    if not entry or not entry['enabled'] or value['kind'] != 'adapter' or value['family'] != 'ledgerdata' or value['contract_version'] != VERSION or value['model_id'] is not None or value['capabilities'] != ['health']:
        raise ValidationError('Enabled exact read-only MCP contract required')
    if any(value[key] != entry[key] for key in ['credential_ref','credential_revision','principal_ref']):
        raise ValidationError('MCP identity binding changed')
    # Endpoint selection is fixed in the adapter, never sourced from the contract.
    if value['target_key'] != 'endpoint:intuit-mcp':
        raise ValidationError('Exact hosted Intuit endpoint identity required')
    secret = os.getenv(settings.READINESS_SECRET_REFS[entry['credential_ref']]['env'])
    if not isinstance(secret, str) or not 0 < len(secret) <= 4096 or not all(32 < ord(c) < 127 for c in secret):
        raise ValidationError('MCP credential unavailable')
    pin = hmac.new(settings.SECRET_KEY.encode(), secret.encode(), hashlib.sha256).hexdigest()
    public = {'implementation':'hosted_mcp_read_v1','classification':'authenticated_remote_claim',
        'configuration':digest(entry),'credential_binding':pin,'credential_ref':entry['credential_ref'],
        'revision':entry['credential_revision'],'auth_mode':'bearer','protocol':VERSION}
    return public, {'entry':entry,'secret':secret}


def probe(job):
    if job.intent['kind'] != 'health':
        raise ValidationError('MCP has discovery only, no business receipt probe')
    public, private = binding(job.contract)
    if public != job.intent['binding']:
        raise ValidationError('MCP reserved binding changed')
    try:
        client = Client(private['secret'], private['entry']['app_name'])
        client.initialize()
        tools = client.discover()
    except MCPError:
        raise ConnectionError('MCP discovery unavailable or unknown') from None
    entry = private['entry']
    selected = [tool for tool in tools if tool['name'] == READ_TOOL]
    matched = (entry['reviewed_tool'] is not None and len(selected) == 1 and selected[0] == entry['reviewed_tool']
        and entry['output_schema'] is not None and entry['target_argument'] is not None and entry['result_identity_key'] is not None)
    return {'kind':'health','classification':public['classification'],'outcome':'passed' if matched else 'failed',
        'authenticated_transport':True,'identity_match':False,'company_identity_configured_not_verified':True,
        'protocol':VERSION,'tools':tools,'inventory_sha256':fingerprint(tools),
        'schema_match':matched,'business_dispatch_verified':False}


def append(actor, case, kind, payload):
    body = json.dumps(payload, sort_keys=True)
    version = (case.evidence.filter(kind=kind).aggregate(n=Max('version'))['n'] or 0) + 1
    row = Evidence.objects.create(case=case, kind=kind, version=version, source='native:qbo-mcp/v1',
        body=body, sha256=hashlib.sha256(body.encode()).hexdigest(), created_by=actor)
    event(actor, case, PREFIX+kind, evidence=row.pk, sha256=row.sha256)
    return row


def authentic(case, pk, kind):
    row = Evidence.objects.filter(case=case, pk=pk, kind=kind, source='native:qbo-mcp/v1').first()
    if not row or hashlib.sha256(row.body.encode()).hexdigest() != row.sha256 or not Audit.objects.filter(
        case=case, actor=row.created_by, action=PREFIX+kind, data__evidence=row.pk, data__sha256=row.sha256).exists():
        raise ValidationError('Authentic native MCP record required')
    return row, json.loads(row.body)


def context(actor, case_id, lineage_id, contract_id, expected=None, caller_mode='system', factory_work=None):
    from . import readiness
    from .readiness_models import IntegrationSelection
    case = ledger.locked(actor, case_id, 'ledger.verify', expected)
    if caller_mode not in ('system','agent'):
        raise ValidationError('Exact MCP caller mode required')
    if caller_mode == 'agent':
        from apps.identity.services import require
        require(actor, case, 'agent.ledger')
    lineage = ledger.exact(case, lineage_id)
    factory_head = None
    factory_profile = None
    factory_binding = None
    if factory_work is not None:
        from .models import FactoryWork
        from .factory import access, profile, TERMINAL
        from .factory_ledger import match
        work = FactoryWork.objects.select_for_update().get(pk=factory_work, case=case, definition='finance-ledger/v1')
        access(actor, case, 'factory.execute', work.definition)
        if caller_mode != 'agent' or work.execution_actor_id != actor.pk or work.cancel_requested or work.status in TERMINAL or work.status not in ['ready','waiting','waiting_effect']:
            raise ValidationError('Current scoped factory execution authority required')
        execution_policy, execution_value = profile(work)
        factory_profile = {'configuration':execution_policy.pk,'value_sha256':digest(execution_value)}
        factory_binding = work.execution_binding_id
        match(work, lineage, actor)
        factory_head = work.source_head_id
    policy, rules = ledger.context(lineage)
    if not ledger.is_head(lineage) or ledger.target_conflict(lineage):
        raise ValidationError('Current nonconflicting source target required')
    readiness.readable(actor, case, True)
    contract = readiness.contract_for(case, contract_id)
    readiness.contract_access(actor, contract)
    readiness.current_contract(contract)
    selection = IntegrationSelection.objects.filter(case=case, family='ledgerdata').order_by('-version').first()
    if not selection or selection.contract_id != contract.pk:
        raise ValidationError('Reviewed selected MCP contract required')
    gate = readiness.gate(case, 'ledgerdata')
    public, private = binding(contract)
    entry = private['entry']
    if not gate or lineage.payload['provider'] != 'quickbooks' or lineage.payload['realm'] != entry['realm'] or not lineage.payload['target_reference']:
        raise ValidationError('Exact reviewed company/source mapping required')
    if entry['reviewed_tool'] is None or entry['output_schema'] is None or not entry['target_argument'] or not entry['result_identity_key']:
        raise ValidationError('Actual reviewed MCP schema and identity projection required')
    arguments = dict(entry['fixed_arguments'], **{entry['target_argument']:lineage.payload['target_reference']})
    try:
        validate(entry['reviewed_tool']['inputSchema'], arguments)
    except MCPError:
        raise ValidationError('Configured exact source projection does not match MCP schema') from None
    pins = {'lineage':lineage.pk,'source':digest(lineage.payload),'policy':policy.pk,'contract':contract.pk,
        'binding':public,'review':gate,'arguments':arguments,'target':lineage.payload['target_reference'],
        'max_age_seconds':rules['max_age_seconds'],'realm':entry['realm'],
        'caller_mode':caller_mode,'factory_work':factory_work,'factory_head':factory_head,
        'factory_profile':factory_profile,'factory_execution_binding':factory_binding}
    return case, pins, private


@transaction.atomic
def reserve(actor, case_id, lineage_id, contract_id, expected=None, *, caller_mode='system', factory_work=None):
    case, pins, _ = context(actor, case_id, lineage_id, contract_id, expected, caller_mode, factory_work)
    if factory_work is not None and Audit.objects.filter(case=case, action=PREFIX+'reserved', data__factory_work=factory_work, data__factory_head=pins['factory_head']).exists():
        raise ValidationError('Original factory MCP intent already reserved; inspect it instead')
    row = append(actor, case, INTENT, pins)
    event(actor, case, PREFIX+'reserved', intent=row.pk, factory_work=factory_work, factory_head=pins['factory_head'])
    bump(case)
    return row


@transaction.atomic
def claim(actor, case_id, intent_id, expected=None):
    case = ledger.locked(actor, case_id, 'ledger.verify', expected)
    row, stored = authentic(case, intent_id, INTENT)
    if row.created_by_id != actor.pk or Audit.objects.filter(case=case, action=PREFIX+'started', data__intent=intent_id).exists():
        raise ValidationError('Original unattempted MCP intent required')
    _, pins, private = context(actor, case_id, stored['lineage'], stored['contract'], caller_mode=stored['caller_mode'], factory_work=stored['factory_work'])
    if pins != stored or not 0 <= (timezone.now()-row.created_at).total_seconds() <= pins['max_age_seconds']:
        raise ValidationError('MCP intent changed or expired')
    realm_key = digest({'realm':private['entry']['realm']})
    ledger.identity_lock(realm_key)
    last = Audit.objects.filter(action=PREFIX+'throttled', data__realm=realm_key).order_by('-created_at').first()
    if last and (timezone.now()-last.created_at).total_seconds() < 60:
        raise ValidationError('MCP throttled; wait at least 60 seconds')
    event(actor, case, PREFIX+'started', intent=intent_id)
    bump(case)
    return stored, private


@transaction.atomic
def finish(actor, case_id, intent_id, stored, result):
    ledger.scope_lock(case_id)
    case = Case.objects.select_for_update().get(pk=case_id)
    row, original = authentic(case, intent_id, INTENT)
    if original != stored or row.created_by_id != actor.pk or not Audit.objects.filter(case=case, actor=actor, action=PREFIX+'started', data__intent=intent_id).exists() or Audit.objects.filter(case=case, action=PREFIX+'completed', data__intent=intent_id).exists():
        raise ValidationError('Exact pending MCP attempt required')
    current = False
    try:
        _, pins, _ = context(actor, case_id, stored['lineage'], stored['contract'], caller_mode=stored['caller_mode'], factory_work=stored['factory_work'])
        current = pins == stored and 0 <= (timezone.now()-row.created_at).total_seconds() <= stored['max_age_seconds']
    except (ValidationError, PermissionDenied, RuntimeError):
        pass
    output = append(actor, case, RESULT, {'intent':intent_id,'result':result,
        'current_at_capture':current,'finance_verification':False,'untrusted_external_evidence':True})
    event(actor, case, PREFIX+'completed', intent=intent_id, evidence=output.pk)
    if result['status'] == 'throttled':
        event(actor, case, PREFIX+'throttled', realm=digest({'realm':stored['realm']}))
    bump(case)
    return output


def execute(actor, case_id, intent_id, expected=None):
    # A nested savepoint is not a durable once-only claim. Callers must not
    # roll back the claim after a remote read and accidentally enable replay.
    if connection.in_atomic_block or not connection.get_autocommit():
        raise ValidationError('Native MCP execution requires an outer autocommit boundary')
    stored, private = claim(actor, case_id, intent_id, expected)
    entry = private['entry']
    try:
        client = Client(private['secret'], entry['app_name'])
        client.initialize()
        result = client.call(entry['reviewed_tool'], stored['arguments'], entry['output_schema'])
        if result.get(entry['result_identity_key']) != stored['target']:
            raise MCPError('MCP returned another source identity')
        outcome = {'status':'observed','projection':result}
    except MCPError as exc:
        outcome = {'status':'throttled' if str(exc) == 'MCP throttled' else 'unknown','projection':None}
    return finish(actor, case_id, intent_id, stored, outcome)


def status(actor, case_id, intent_id):
    case = Case.objects.get(pk=case_id)
    ledger.readable(actor, case)
    row, stored = authentic(case, intent_id, INTENT)
    if stored['caller_mode'] == 'agent':
        from apps.identity.services import require
        require(actor, case, 'agent.ledger')
    completed = Audit.objects.filter(case=case, action=PREFIX+'completed', data__intent=row.pk).first()
    started = Audit.objects.filter(case=case, action=PREFIX+'started', data__intent=row.pk).exists()
    return {'intent':row.pk,'status':'completed' if completed else 'unknown_or_in_progress' if started else 'reserved',
        'result_evidence_id':completed.data['evidence'] if completed else None,
        'automatic_retry':False,'finance_verification':False}


@transaction.atomic
def factory_state(work, lineage, reader=None):
    """Metadata only; discovery, remote content and agent proposals grant nothing."""
    from .readiness_models import IntegrationSelection
    if lineage is None:
        return None
    selected = IntegrationSelection.objects.filter(case=work.case, family='ledgerdata').select_related('contract').order_by('-version').first()
    if not selected or selected.contract.payload['implementation'] != 'hosted_mcp_read_v1':
        return None
    actor = work.execution_actor
    try:
        _, pins, _ = context(actor, work.case_id, lineage.pk, selected.contract_id,
            caller_mode='agent', factory_work=work.pk)
    except (ValidationError, PermissionDenied, RuntimeError):
        return {'ready':False,'status':'configuration_or_current_authority_needed'}
    # An exact append-only reservation index prevents a bounded history scan
    # from accidentally hiding an older attempt and authorizing a replay.
    reservation = Audit.objects.filter(case=work.case, action=PREFIX+'reserved',
        data__factory_work=work.pk, data__factory_head=work.source_head_id).order_by('-pk').first()
    if reservation:
        row, value = authentic(work.case, reservation.data['intent'], INTENT)
        if value.get('factory_work') != work.pk or value.get('factory_head') != work.source_head_id:
            raise ValidationError('Factory MCP reservation binding differs')
        observed = status(actor, work.case_id, row.pk)
        return dict(observed, ready=False)
    return {'ready':True,'contract':selected.contract_id,'binding':pins['binding'],'status':'eligible_read_reservation'}


@transaction.atomic
def reconcile(actor, case_id, intent_id):
    case = ledger.locked(actor, case_id, 'ledger.verify')
    row, stored = authentic(case, intent_id, INTENT)
    if row.created_by_id != actor.pk:
        raise ValidationError('Original MCP principal required')
    _, pins, _ = context(actor, case_id, stored['lineage'], stored['contract'],
        caller_mode=stored['caller_mode'], factory_work=stored['factory_work'])
    if pins != stored:
        raise ValidationError('MCP result context changed; preserve historical evidence only')
    state = status(actor, case_id, intent_id)
    if state['status'] != 'completed':
        raise ValidationError('Original MCP read has no completed observation; never dispatch in reconciliation')
    evidence, payload = authentic(case, state['result_evidence_id'], RESULT)
    if payload['intent'] != intent_id:
        raise ValidationError('MCP result does not match original intent')
    return {'mcp_intent':intent_id,'mcp_result_evidence':evidence.pk,'mcp_outcome':payload['result']['status'],
        'current_at_capture':payload['current_at_capture'],'finance_verification':False,'posting_performed':False}

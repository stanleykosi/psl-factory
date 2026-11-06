from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
import hashlib
import json
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from jsonschema import Draft202012Validator, FormatChecker
from apps.core.models import Evidence
from apps.core.services import lock_case, event
from apps.identity.services import require
from .models import Configuration, PolicyState, RegisteredReference
from .registry import components, envelope_schema, dependencies


@dataclass(frozen=True)
class Resolution:
    status: str
    component: str
    configuration: object = None
    reason: str = ''


class PolicyHold(ValidationError):
    def __init__(self, results):
        self.results = results
        super().__init__([f'{r.component}: {r.status} {r.reason}' for r in results])


def validate_envelope(case, envelope, runtime=False):
    errors = sorted(Draft202012Validator(envelope_schema(), format_checker=FormatChecker()).iter_errors(envelope), key=lambda e: str(e.path))
    if errors:
        raise ValidationError([f'{list(e.path)}: {e.message}' for e in errors])
    component = components()[envelope['component_id']]
    if envelope['subject_scope'] != {'kind': 'project' if case.kind == 'project' else 'service', 'ref': str(case.pk)}:
        raise ValidationError('Executable local configurations require exact case scope; reusable sources must be explicitly applied, with no scope or stage fallback')
    if (envelope['fixture_scope'] == 'synthetic_test') != case.synthetic:
        raise ValidationError('Synthetic and operational scopes cannot mix')
    if envelope['implementation_id'] != 'psl.reference-validation' or envelope['implementation_version'] != '1':
        raise ValidationError('Implementation ID/version has no reviewed validator')
    if envelope['reviewed_implementation_ref'] != 'code:apps/policy/services.py#reference-validation-v1':
        raise ValidationError('Reviewed implementation reference does not match code registry')
    if envelope['schema_version'] != '1':
        raise ValidationError('Unsupported schema version')
    if envelope['component_schema_ref'] != component['schema_ref']:
        raise ValidationError('Incorrect component schema')
    start = datetime.fromisoformat(envelope['effective_from'])
    end = datetime.fromisoformat(envelope['effective_until']) if envelope.get('effective_until') else None
    if end and end <= start:
        raise ValidationError('Effective end must follow start')
    refs = envelope['evidence_refs'] + [envelope['human_decision_ref']]
    for ref in refs:
        if not ref.startswith('evidence:') or not ref.split(':')[-1].isdigit() or not Evidence.objects.filter(case=case, pk=ref.split(':')[-1]).exists():
            raise ValidationError('Evidence/decision references must identify evidence on this case')
    value = envelope['value']
    if envelope['component_id'] == 'D04.iana_timezone':
        try:
            ZoneInfo(value)
        except (ValueError, ZoneInfoNotFoundError):
            raise ValidationError('Unknown IANA timezone')
        return
    # Reference-backed values require a reviewed domain schema. Arbitrary text cannot execute rules.
    values = value if isinstance(value, list) else [value]
    resolved_contents=[]
    for item in values:
        if isinstance(item, dict):
            ref, version = item['artifact_ref'], item['artifact_version']
        else:
            ref, version = item, 1
        target = RegisteredReference.objects.filter(case=case, ref=ref, version=version).first()
        if not target:
            raise ValidationError('Registered domain reference is missing')
        resolved_contents.append(target.content)
        digest = hashlib.sha256(json.dumps(target.content, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        if target.sha256 != digest or (isinstance(item, dict) and (item['sha256'] != digest or item['schema_ref'] != target.schema_ref)):
            raise ValidationError('Referenced content hash/schema does not match')
        from .clock_validators import SUPPORTED as CLOCK_COMPONENTS, validate_reference as validate_clock_reference
        from .document_validators import SUPPORTED, validate_reference
        from .revision_validators import SUPPORTED as REVISION_COMPONENTS, validate_reference as validate_revision_reference
        from .change_validators import SUPPORTED as CHANGE_COMPONENTS, validate_reference as validate_change_reference
        from .emergency_validators import SUPPORTED as EMERGENCY_COMPONENTS, validate_reference as validate_emergency_reference
        from .delivery_validators import SUPPORTED as DELIVERY_COMPONENTS, validate_reference as validate_delivery_reference
        from .rfp_validators import SUPPORTED as RFP_COMPONENTS,validate_reference as validate_rfp_reference
        from .finance_validators import SUPPORTED as FINANCE_COMPONENTS,validate_reference as validate_finance_reference
        from .billing_validators import SUPPORTED as BILLING_COMPONENTS,validate_reference as validate_billing_reference
        from .settlement_validators import SUPPORTED as SETTLEMENT_COMPONENTS,validate_reference as validate_settlement_reference
        from .baas_validators import SUPPORTED as BAAS_COMPONENTS,validate_reference as validate_baas_reference
        from .partner_validators import handles,validate_reference as validate_partner
        from .payment_validators import SCHEMAS as PAYMENT_COMPONENTS,validate_reference as validate_payment
        from .validation_validators import SCHEMAS as VALIDATION_COMPONENTS,validate_reference as validate_discovery
        from .recognition_validators import SCHEMAS as RECOGNITION_COMPONENTS,validate_reference as validate_recognition
        from .hrfinance_validators import handles as hr_handles,validate_reference as validate_hr
        from .payroll_validators import SCHEMAS as PAYROLL_COMPONENTS,validate_reference as validate_payroll
        from .bu_validators import SCHEMAS as BU_COMPONENTS,validate_reference as validate_bu
        from .schedule_validators import SCHEMAS as SCHEDULE_COMPONENTS,validate_reference as validate_schedule
        from .ppe_validators import SCHEMAS as PPE_COMPONENTS,validate_reference as validate_ppe
        from .ledger_validators import SCHEMAS as LEDGER_COMPONENTS,validate_reference as validate_ledger
        from .support_validators import SCHEMAS as SUPPORT_COMPONENTS,validate_reference as validate_support
        from .approval_validators import SCHEMAS as APPROVAL_COMPONENTS,validate_reference as validate_approval
        from .migration_validators import SCHEMAS as MIGRATION_COMPONENTS,validate_reference as validate_migration
        from .d03_validators import SCHEMAS as D03_COMPONENTS,validate_reference as validate_d03
        from .costing_validators import SCHEMAS as COSTING_COMPONENTS,validate_reference as validate_costing
        from .operator_validators import SCHEMAS as OPERATOR_COMPONENTS,validate_reference as validate_operator
        from .readiness_validators import SCHEMAS as READINESS_COMPONENTS,validate_reference as validate_readiness
        from .agent_data_validators import SCHEMAS as DATA_COMPONENTS,validate_reference as validate_data
        from .support_agent_validators import SCHEMAS as SUPPORT_AGENT_COMPONENTS,validate_reference as validate_support_agent
        from .support_release_validators import SCHEMAS as RELEASE_COMPONENTS,validate_reference as validate_release
        from .support_channel_validators import SCHEMAS as CHANNEL_COMPONENTS,validate_reference as validate_channel
        if envelope['component_id'] in CHANNEL_COMPONENTS:
            validate_channel(envelope['component_id'],target,case,runtime=runtime)
        elif envelope['component_id'] in RELEASE_COMPONENTS:
            validate_release(envelope['component_id'],target,case,runtime=runtime)
        elif envelope['component_id'] in SUPPORT_AGENT_COMPONENTS:
            validate_support_agent(envelope['component_id'],target,case,runtime=runtime)
        elif envelope['component_id'] in DATA_COMPONENTS:
            validate_data(envelope['component_id'],target,case,runtime=runtime)
        elif envelope['component_id'] in READINESS_COMPONENTS:
            validate_readiness(envelope['component_id'],target,case,runtime=runtime)
        elif envelope['component_id'] in OPERATOR_COMPONENTS:
            validate_operator(envelope['component_id'],target,case,runtime=runtime)
        elif envelope['component_id'] in COSTING_COMPONENTS:
            validate_costing(envelope['component_id'],target,case,runtime=runtime)
        elif envelope['component_id'] in D03_COMPONENTS:
            validate_d03(envelope['component_id'],target,case,runtime=runtime)
        elif envelope['component_id'] in MIGRATION_COMPONENTS:
            validate_migration(envelope['component_id'],target,case,runtime=runtime)
        elif envelope['component_id'] in APPROVAL_COMPONENTS:
            validate_approval(envelope['component_id'],target,case,runtime=runtime)
        elif envelope['component_id'] in SUPPORT_COMPONENTS:
            validate_support(envelope['component_id'],target,case,runtime=runtime)
        elif envelope['component_id'] in LEDGER_COMPONENTS:
            validate_ledger(envelope['component_id'],target,case,runtime=runtime)
        elif envelope['component_id'] in PPE_COMPONENTS:
            validate_ppe(envelope['component_id'],target,case,runtime=runtime)
        elif envelope['component_id'] in SCHEDULE_COMPONENTS:
            validate_schedule(envelope['component_id'],target,case,runtime=runtime)
        elif envelope['component_id'] in BU_COMPONENTS:
            validate_bu(envelope['component_id'],target,case,runtime=runtime)
        elif envelope['component_id'] in PAYROLL_COMPONENTS:
            validate_payroll(envelope['component_id'],target,case,runtime=runtime)
        elif hr_handles(envelope['component_id'],target):
            validate_hr(envelope['component_id'],target,case,runtime=runtime)
        elif envelope['component_id'] in RECOGNITION_COMPONENTS:
            validate_recognition(envelope['component_id'],target,case,runtime=runtime)
        elif envelope['component_id'] in VALIDATION_COMPONENTS:
            validate_discovery(envelope['component_id'],target,case,runtime=runtime)
        elif envelope['component_id'] in PAYMENT_COMPONENTS:
            validate_payment(envelope['component_id'],target,case,runtime=runtime)
        elif handles(envelope['component_id'],target):
            validate_partner(envelope['component_id'],target,case,runtime=runtime)
        elif envelope['component_id'] in BAAS_COMPONENTS:
            validate_baas_reference(envelope['component_id'],target,case,runtime=runtime)
        elif envelope['component_id'] in SETTLEMENT_COMPONENTS:
            validate_settlement_reference(envelope['component_id'],target,case,runtime=runtime)
        elif envelope['component_id'] in BILLING_COMPONENTS:
            validate_billing_reference(envelope['component_id'],target,case,runtime=runtime)
        elif envelope['component_id'] in FINANCE_COMPONENTS or envelope['component_id']=='D06.unit_sign_currency_period' and target.schema_ref in ['schema:psl/source-conventions/v2','schema:psl/source-conventions/v3']:
            validate_finance_reference(envelope['component_id'],target,case,runtime=runtime)
        elif envelope['component_id'] in RFP_COMPONENTS:
            validate_rfp_reference(envelope['component_id'],target,case,runtime=runtime)
        elif envelope['component_id'] in DELIVERY_COMPONENTS:
            validate_delivery_reference(envelope['component_id'],target,case)
        elif envelope['component_id'] in EMERGENCY_COMPONENTS:
            validate_emergency_reference(envelope['component_id'],target,case)
        elif envelope['component_id'] in CHANGE_COMPONENTS:
            validate_change_reference(envelope['component_id'],target,case)
        elif envelope['component_id'] in REVISION_COMPONENTS:
            validate_revision_reference(envelope['component_id'],target,case)
        elif envelope['component_id'] in CLOCK_COMPONENTS:
            validate_clock_reference(envelope['component_id'],target,case)
        elif envelope['component_id'] in SUPPORTED:
            validate_reference(envelope['component_id'],target,case,runtime=runtime)
        elif envelope['component_id'] == 'D05.role_principal_assignments':
            from .role_assignments import validate_reference as validate_role_assignment
            validate_role_assignment(target,case)
        elif envelope['component_id'] == 'D06.source_schema_ref':
            if target.schema_ref != 'schema:psl/controlled-csv/v1' or target.content != {'columns': ['account', 'amount', 'currency', 'period']}:
                raise ValidationError('Expected the reviewed controlled CSV schema')
        elif envelope['component_id'] == 'D06.unit_sign_currency_period':
            from jsonschema import validate
            from jsonschema.exceptions import ValidationError as SchemaError
            schema = {'type':'object','properties':{'currency':{'type':'string','pattern':'^[A-Z]{3}$'}, 'unit':{'const':'major_currency'}, 'period':{'type':'string','pattern':r'^\d{4}-(0[1-9]|1[0-2])$'}, 'sign_convention':{'enum':['debit_positive','credit_positive']}},'required':['currency','unit','period','sign_convention'],'additionalProperties':False}
            if target.schema_ref != 'schema:psl/source-conventions/v1':
                raise ValidationError('Unsupported source convention schema')
            try:
                validate(target.content,schema)
            except SchemaError as exc:
                raise ValidationError(exc.message)
        else:
            raise ValidationError('Domain semantic validator is not implemented for this component yet; draft is retained')
    if envelope['component_id']=='D05.role_principal_assignments':
        from .role_assignments import validate_collection as validate_role_collection
        validate_role_collection(resolved_contents)
    from .d03_validators import validate_collection as validate_d03_collection
    validate_d03_collection(envelope['component_id'],resolved_contents)
    from .payment_validators import validate_collection as validate_payment_collection
    validate_payment_collection(envelope['component_id'],resolved_contents)
    from .partner_validators import validate_collection as validate_partner_collection
    validate_partner_collection(envelope['component_id'],resolved_contents)
    from .settlement_validators import SUPPORTED as SETTLEMENT_COMPONENTS,validate_collection as validate_settlement_collection
    if envelope['component_id'] in SETTLEMENT_COMPONENTS:validate_settlement_collection(envelope['component_id'],resolved_contents)
    from .billing_validators import SUPPORTED as BILLING_COMPONENTS,validate_collection as validate_billing_collection
    if envelope['component_id'] in BILLING_COMPONENTS:validate_billing_collection(envelope['component_id'],resolved_contents)
    from .finance_validators import SUPPORTED as FINANCE_COMPONENTS,validate_collection
    if envelope['component_id'] in FINANCE_COMPONENTS:validate_collection(envelope['component_id'],resolved_contents)
    if envelope['component_id'] in ['D01.change_type_catalogue','D11.adapter_configuration_refs']:
        if len(values)>100:
            raise ValidationError('Standard catalogue exceeds the 100-entry validation budget')
        keys=[RegisteredReference.objects.get(case=case,ref=ref,version=1).content['key'] for ref in values]
        if len(keys)!=len(set(keys)):
            raise ValidationError('Standard catalogue keys must be unique')


@transaction.atomic
def save_draft(actor, case_id, envelope):
    case = lock_case(actor, case_id, 'policy.configure')
    if not isinstance(envelope, dict):
        raise ValidationError('Configuration envelope must be a JSON object')
    component = envelope.get('component_id')
    if component not in components():
        raise ValidationError('Unknown component')
    revision = (Configuration.objects.filter(case=case, component=component).order_by('-revision').values_list('revision', flat=True).first() or 0) + 1
    envelope = dict(envelope, policy_revision=revision, lifecycle='draft')
    config = Configuration.objects.create(case=case, component=component, revision=revision, envelope=envelope, created_by=actor)
    PolicyState.objects.create(configuration=config, state='draft', actor=actor)
    event(actor, case, 'policy.drafted', configuration=config.pk, component=component, revision=revision)
    return config


@transaction.atomic
def transition(actor, config_id, state):
    config = Configuration.objects.get(pk=config_id)
    case = lock_case(actor, config.case_id, 'policy.activate' if state in ['active', 'revoked'] else 'policy.configure')
    from .models import ScopeVersion
    from .scopes import application_health
    if ScopeVersion.objects.filter(configuration=config).exists():
        raise ValidationError('Scoped source configuration is frozen; use its independent scope lifecycle')
    if state != 'revoked' and application_health(config) != 'ACTIVE':
        raise ValidationError('Scoped origin is unavailable; select and review a new source application')
    current = config.states.order_by('-pk').first().state
    if state not in {'validated', 'active', 'revoked'}:
        raise ValidationError('Unsupported lifecycle action')
    if state == 'validated' and current != 'draft' or state == 'active' and current != 'validated' or state == 'revoked' and current != 'active':
        raise ValidationError('Invalid policy lifecycle transition')
    if state != 'revoked':
        validate_envelope(case, config.envelope)
    if state == 'active':
        latest = Configuration.objects.filter(case=case, component=config.component).order_by('-revision').first()
        if latest.pk != config.pk:
            raise ValidationError('Stale policy draft')
        for other in Configuration.objects.filter(case=case, component=config.component).exclude(pk=config.pk):
            if other.states.order_by('-pk').first().state == 'active':
                PolicyState.objects.create(configuration=other, state='superseded', actor=actor)
    PolicyState.objects.create(configuration=config, state=state, actor=actor)
    event(actor, case, 'policy.' + state, configuration=config.pk)
    return config


def resolve(component, case, at=None, expected_revision=None):
    at = at or timezone.now()
    versions = Configuration.objects.filter(case=case, component=component).order_by('-revision')
    candidates = [c for c in versions if c.states.order_by('-pk').first().state in ['active', 'revoked', 'superseded']]
    if not candidates:
        return Resolution('MISSING', component, reason='No activated component version')
    config = candidates[0]
    state = config.states.order_by('-pk').first().state
    if state == 'revoked':
        return Resolution('REVOKED', component)
    from .scopes import application_health
    origin_status = application_health(config, at)
    if origin_status != 'ACTIVE':
        return Resolution(origin_status, component, reason='Explicit scoped source is unavailable; no fallback')
    if expected_revision is not None and config.revision != expected_revision:
        return Resolution('INVALID', component, reason='Stale policy revision')
    try:
        validate_envelope(case, config.envelope, runtime=True)
    except (ValidationError, ValueError, KeyError) as exc:
        return Resolution('INVALID', component, reason=str(exc))
    start = datetime.fromisoformat(config.envelope['effective_from'])
    end = datetime.fromisoformat(config.envelope['effective_until']) if config.envelope.get('effective_until') else None
    if at < start:
        return Resolution('MISSING', component, reason='Version is not yet effective')
    if end and at >= end:
        return Resolution('EXPIRED', component)
    return Resolution('ACTIVE', component, config)


def require_operation(operation, case):
    results = [resolve(c, case) for c in dependencies(operation)]
    missing = [r for r in results if r.status != 'ACTIVE']
    if missing:
        raise PolicyHold(missing)
    return results


def role_policy(actor, case, role):
    result = resolve('D05.role_principal_assignments', case)
    if result.status != 'ACTIVE':
        raise PolicyHold([result])
    from .role_assignments import assert_assigned
    assert_assigned(actor,case,reference_values(result.configuration),role)
    return result.configuration


@transaction.atomic
def register_reference(actor, case_id, ref, schema_ref, content, evidence_id):
    case = lock_case(actor,case_id,'policy.configure')
    evidence = Evidence.objects.filter(case=case,pk=evidence_id,kind='policy_decision').first()
    if not evidence or not ref.strip() or not schema_ref.startswith('schema:'):
        raise ValidationError('Reference needs a schema identifier and this case owner-decision evidence')
    try:
        encoded = json.dumps(content,sort_keys=True,separators=(',',':'),allow_nan=False)
    except (TypeError,ValueError):
        raise ValidationError('Policy reference content must be finite JSON values')
    if len(encoded) > 32000:
        raise ValidationError('Reference content budget exceeded')
    revision = (RegisteredReference.objects.filter(case=case,ref=ref).order_by('-version').values_list('version',flat=True).first() or 0) + 1
    reference = RegisteredReference.objects.create(case=case,ref=ref,schema_ref=schema_ref,version=revision,
        content=content,sha256=hashlib.sha256(encoded.encode()).hexdigest(),evidence=evidence)
    event(actor,case,'policy.reference_registered',reference=reference.pk,ref=ref,version=revision,sha256=reference.sha256)
    return reference


def active_component(component,case):
    result=resolve(component,case)
    if result.status!='ACTIVE':
        raise PolicyHold([result])
    return result.configuration


def reference_values(configuration):
    value=configuration.envelope['value']
    if isinstance(value,dict):
        return [RegisteredReference.objects.get(case=configuration.case,ref=value['artifact_ref'],version=value['artifact_version']).content]
    refs=[value] if isinstance(value,str) else value
    return [RegisteredReference.objects.get(case=configuration.case,ref=ref,version=1).content for ref in refs]


def decision_authority(actor,case,role,action='approve',delegated=False,delegation_context=None):
    from django.core.exceptions import PermissionDenied
    pinned={}
    if type(delegated) is not bool:raise ValidationError('Delegated authority mode must be boolean')
    if delegation_context is not None and not isinstance(delegation_context,dict):raise ValidationError('Typed delegation context required')
    if delegation_context is not None and not delegated:raise ValidationError('Scoped delegation requires explicit delegated mode')
    assignment=active_component('D05.role_principal_assignments',case)
    pinned[assignment.component]=assignment.pk
    if not delegated:
        role_policy(actor,case,role)
    else:
        delegation=active_component('D05.delegation_rules',case)
        now=timezone.now()
        matches=[r for r in reference_values(delegation) if r['delegate_id']==actor.pk and r['role']==role and
            datetime.fromisoformat(r['valid_from'])<=now<datetime.fromisoformat(r['valid_until'])]
        if delegation_context is None:matches=[r for r in matches if 'decision_scope' not in r]
        else:
            from .delegation_validators import invoice_scope_status
            if delegation_context.get('case_ref')!=str(case.pk):raise ValidationError('Delegation context must match the exact current case')
            scoped=[]
            for record in matches:
                status=invoice_scope_status(record,delegation_context)
                if status=='UNCONFIGURED':raise ValidationError('Invoice delegation scope needs configured actions, currency and amount limit')
                if status=='MATCH':scoped.append(record)
            matches=scoped
        assigned=reference_values(assignment)
        from django.contrib.auth import get_user_model
        from .delegation_validators import assert_delegate_eligible
        valid=False;qualification_errors=[];qualified=[]
        for record in matches:
            if not any(v['role']==role and v['user_id']==record['principal_id'] for v in assigned):continue
            principal=get_user_model().objects.filter(pk=record['principal_id'],is_active=True).first()
            if principal is None:continue
            try:
                role_policy(principal,case,role)
                assert_delegate_eligible(actor,case,record,assigned)
            except (ValidationError,PermissionDenied) as exc:
                qualification_errors.append(exc);continue
            valid=True;qualified.append(record)
            if delegation_context is None:break
        if not valid:
            if qualification_errors:raise qualification_errors[0]
            raise PermissionDenied('No current delegated authority for this person and role')
        pinned[delegation.component]=delegation.pk
        if delegation_context is not None:
            if len(qualified)!=1:raise ValidationError('Conflicting current invoice delegations require owner review')
            record=qualified[0]
            pinned['invoice_delegation']={'principal_id':record['principal_id'],'delegate_id':record['delegate_id'],
                'rule_sha256':hashlib.sha256(json.dumps(record,sort_keys=True,separators=(',',':')).encode()).hexdigest(),
                'scope_sha256':hashlib.sha256(json.dumps(record['decision_scope'],sort_keys=True,separators=(',',':')).encode()).hexdigest(),
                'scope_checks':{'project':'matched','decision':'matched','action':'matched','currency':'matched','amount':'within_configured_limit'}}
    if action!='approve':
        matrix=active_component('D05.decision_action_matrix',case)
        if not any(r['role']==role and action in r['actions'] for r in reference_values(matrix)[0].get('rules',[])):
            raise PermissionDenied('Decision action is not granted by configured authority')
        pinned[matrix.component]=matrix.pk
    return pinned

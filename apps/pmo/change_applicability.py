"""Exact owner applicability resolution. No category or baseline inference."""
from django.core.exceptions import ValidationError
from apps.policy.change_applicability_validators import COMPONENT, OWNER_QUESTION
from apps.policy.services import resolve, reference_values, PolicyHold, Resolution


def owner_requirement(auth):
    """Resolve only this change. A missing entry cannot authorize unsigned closure."""
    case = auth.version.change.case
    result = resolve(COMPONENT, case)
    if result.status != 'ACTIVE':
        raise PolicyHold([result])
    entries = reference_values(result.configuration)[0]['entries']
    entry = next((item for item in entries if item['authorization_id'] == auth.pk), None)
    if not entry or entry['requirement'] in [None, 'unresolved']:
        raise PolicyHold([Resolution('MISSING', COMPONENT, result.configuration, OWNER_QUESTION)])
    if entry['change_version_id'] != auth.version_id or auth.version.change.current_id != auth.version_id:
        raise ValidationError('Applicability does not cover the current exact change version')
    from apps.policy.change_applicability_validators import validate_owner
    validate_owner(case, entry)
    return result.configuration, entry


PROTOCOL = 'change-go-live-applicability-attestation/v1'


def validate_declaration(value):
    from django.utils import timezone
    from .go_live_attestations import exact, integer, identity, evidence_pin, instant
    from .change_signatures import PURPOSE
    exact(value, ['protocol', 'purpose', 'case_id', 'change', 'authorization', 'execution', 'report',
                  'signatures', 'attesting_actor_id', 'applicability'], 'change applicability attestation')
    if value['protocol'] != PROTOCOL or value['purpose'] != PURPOSE:
        raise ValidationError('Exact change-go-live applicability purpose required')
    integer(value['attesting_actor_id'])
    decision = value['applicability']
    exact(decision, ['policy_id', 'revision', 'entry'], 'applicability policy pin')
    integer(decision['policy_id']); integer(decision['revision'])
    from apps.documents.contracts import validate
    from apps.policy.change_applicability_validators import ENTRY
    validate(ENTRY, decision['entry'])
    requirement = decision['entry']['requirement']
    if requirement not in ['required', 'not_applicable']:
        raise ValidationError('Unresolved applicability cannot authorize unsigned closure')
    roles = ['PM', 'Client'] if requirement == 'required' else ['PM']
    exact(value['signatures'], roles, 'actual signatures for declared applicability')
    for signature in value['signatures'].values():
        exact(signature, ['evidence', 'source_system', 'source_reference', 'decision_id', 'decision_version',
                          'signer_reference', 'purpose', 'signed_at'], 'actual source signature')
        evidence_pin(signature['evidence'])
        for key in ['source_system', 'source_reference', 'decision_id', 'decision_version', 'signer_reference']:
            identity(signature[key])
        if signature['purpose'] != PURPOSE or instant(signature['signed_at']) > timezone.now():
            raise ValidationError('Actual aware change acceptance signature time and purpose required')
    if requirement == 'required' and value['signatures']['PM']['evidence']['id'] == value['signatures']['Client']['evidence']['id']:
        raise ValidationError('Distinct PM and Client signature evidence required')
    return value


def validate_record(row):
    from apps.identity.services import require
    from apps.policy.services import decision_authority
    from apps.documents.controlled import current_version
    from .change_execution import validate_authorization, execution_manifest, change_binding_findings
    from .change_signatures import subject_pins
    from .models import ChangeClosure, ChangeDocumentBinding, ChangeClosureApplicability
    from .commercial import note_required
    auth = row.authorization; case = auth.version.change.case
    validate_authorization(case, auth)
    require(row.actor, case, 'case.read'); require(row.actor, case, 'change.manage')
    if row.authority != decision_authority(row.actor, case, 'PM'):
        raise ValidationError('Current PM recorder authority required')
    note_required(row.note)
    if not isinstance(row.operation_key, str) or not row.operation_key.strip() or len(row.operation_key) > 100:
        raise ValidationError('Stable bounded applicability operation key required')
    policy, entry = owner_requirement(auth)
    if row.policy_id != policy.pk or row.requirement != entry['requirement']:
        raise ValidationError('Exact active owner applicability policy and requirement required')
    value = validate_declaration(row.declaration)
    if value['applicability'] != {'policy_id': policy.pk, 'revision': policy.revision, 'entry': entry}:
        raise ValidationError('Exact owner/source/policy-version decision snapshot required')
    if (row.requirement == 'not_applicable') != (row.client_signature_id is None):
        raise ValidationError('Not applicable is not a Client signature')
    receipt = row.receipt; version = receipt.publication.version
    current_version(case, version.pk)
    binding = ChangeDocumentBinding.objects.filter(version=version, authorization=auth, purpose='go_live').first()
    if not binding or change_binding_findings(binding) or row.execution_ids != execution_manifest(auth) or binding.execution_ids != row.execution_ids:
        raise ValidationError('Exact current authorized execution and report binding required')
    if version.audience != 'client' or receipt.payload != version.payload or receipt.payload_sha256 != version.payload_sha256:
        raise ValidationError('Actual exact client delivery receipt remains required; applicability grants no delivery waiver')
    if any(value[key] != pin for key, pin in subject_pins(auth, receipt).items()) or value['attesting_actor_id'] != row.actor_id:
        raise ValidationError('Exact change/execution/report/hash/receipt/recorder required')
    previous = auth.applicability_records.exclude(pk=row.pk).filter(pk__lt=row.pk).order_by('-pk').first() if row.pk else auth.applicability_records.order_by('-pk').first()
    if row.previous_id != (previous.pk if previous else None):
        raise ValidationError('Exact latest applicability predecessor required')
    legacy = auth.signature_bindings.order_by('-pk').first()
    if row.legacy_binding_id != (legacy.pk if legacy else None):
        raise ValidationError('Retain the exact latest original signed binding reference')
    closure = ChangeClosure.objects.filter(authorization=auth).first()
    if closure and (closure.receipt_id, closure.pm_signature_id, closure.execution_ids) != (row.receipt_id, row.pm_signature_id, row.execution_ids):
        raise ValidationError('Applicability successor cannot rewrite historical report/receipt/PM signature/execution')
    original = previous or legacy
    if original and original.declaration['signatures']['PM'] != value['signatures']['PM']:
        raise ValidationError('Preserve original actual PM signature facts')
    _signature_facts(row, value)
    return row


def _signature_facts(row, value):
    from .go_live_attestations import instant, pin, decision_key
    from .models import ChangeClosure, ChangeClosureSignatureBinding, ChangeClosureApplicability, GateRecord, DeliveryRecord, CommercialSignaturePacket
    auth = row.authorization; case = auth.version.change.case
    version = row.receipt.publication.version
    signatures = value['signatures']; ids = {row.pm_signature_id}
    if row.client_signature_id: ids.add(row.client_signature_id)
    keys = {decision_key(signature) for signature in signatures.values()}
    for role in signatures:
        evidence = row.pm_signature if role == 'PM' else row.client_signature
        signature = signatures[role]
        if evidence.case_id != case.pk or evidence.kind != 'signature' or signature['evidence'] != pin(evidence):
            raise ValidationError('Exact same-case actual role-specific signature evidence required')
        if instant(signature['signed_at']) <= version.created_at:
            raise ValidationError('Actual signature must follow report artifact creation')
        closure = ChangeClosure.objects.filter(authorization=auth).first()
        if closure and (role == 'PM' or evidence.pk == closure.client_signature_id) and instant(signature['signed_at']) > closure.created_at:
            raise ValidationError('Original historical signature must predate its unchanged closure')
    if GateRecord.objects.filter(evidence_id__in=ids, kind__in=['uat_product_manager','uat_product_owner','uat_client']).exists():
        raise ValidationError('UAT signatures cannot become change go-live acceptance')
    for old in ChangeClosure.objects.filter(authorization__version__change__case=case).exclude(authorization=auth):
        if ids & {old.pm_signature_id, old.client_signature_id}: raise ValidationError('Signature evidence already closes another change')
    for model in [ChangeClosureSignatureBinding, ChangeClosureApplicability]:
        for old in model.objects.filter(authorization__version__change__case=case).exclude(authorization=auth):
            if ids & {old.pm_signature_id, old.client_signature_id} or any(decision_key(s) in keys for s in old.declaration['signatures'].values()):
                raise ValidationError('Signature source decision already belongs to another change')
    for old in DeliveryRecord.objects.filter(dossier__case=case, kind__in=['go_live','go_live_reaffirmation']):
        if ids & {old.data.get('pm_signature_id'),old.data.get('client_signature_id')} or any(decision_key(s) in keys for s in old.data.get('attestation',{}).get('signatures',{}).values()):
            raise ValidationError('Project go-live signatures cannot be reused as change signatures')
    for old in CommercialSignaturePacket.objects.filter(case=case):
        if ids & {s.get('evidence_id') for s in old.signatures.values()}:
            raise ValidationError('SOW/PRD signatures cannot be reused as change signatures')


def capture(actor, auth, receipt, pm, client, execution_ids, note, declaration, operation_key, previous_id=None):
    from apps.policy.services import decision_authority
    from .models import ChangeClosureApplicability
    policy, entry = owner_requirement(auth)
    legacy = auth.signature_bindings.order_by('-pk').first()
    row = ChangeClosureApplicability(authorization=auth, receipt=receipt, pm_signature=pm, client_signature=client,
        execution_ids=execution_ids, note=note, declaration=declaration, actor=actor, policy=policy,
        requirement=entry['requirement'], authority=decision_authority(actor,auth.version.change.case,'PM'),
        operation_key=operation_key, previous_id=previous_id, legacy_binding=legacy)
    repeated = auth.applicability_records.filter(operation_key=operation_key).first()
    if repeated:
        fields = ['receipt_id','pm_signature_id','client_signature_id','execution_ids','note','declaration','actor_id',
                  'policy_id','requirement','authority','previous_id','legacy_binding_id']
        if repeated != auth.applicability_records.order_by('-pk').first() or any(getattr(repeated,k) != getattr(row,k) for k in fields):
            raise ValidationError('Operation key identifies different or historical applicability facts')
        return validate_record(repeated)
    validate_record(row); row.save(); return row


def current_closure(closure):
    from django.db import connection
    row = closure.authorization.applicability_records.order_by('-pk').first()
    if not row:
        raise ValidationError('Explicit applicability assurance record required')
    validate_record(row)
    with connection.cursor() as cursor:
        cursor.execute('SELECT psl_change_applicability_current(r) FROM pmo_changeclosureapplicability r WHERE id=%s',[row.pk])
        if cursor.fetchone() != (True,):
            raise ValidationError('Current native exact applicability proof required')
    return row


def declaration_draft(auth, receipt, actor):
    import json
    from .change_signatures import subject_pins, PURPOSE
    policy, entry = owner_requirement(auth)
    roles = ['PM','Client'] if entry['requirement'] == 'required' else ['PM']
    value = dict(subject_pins(auth, receipt), protocol=PROTOCOL, purpose=PURPOSE, attesting_actor_id=actor.pk,
        applicability={'policy_id':policy.pk,'revision':policy.revision,'entry':entry},
        signatures={role:{'evidence':{'id':None,'version':None,'sha256':None},
            **{key:None for key in ['source_system','source_reference','decision_id','decision_version','signer_reference','purpose','signed_at']}} for role in roles})
    return json.dumps(value, indent=2)


from django.db import transaction


@transaction.atomic
def record_successor(actor, case_id, closure_id, client_signature_id, declaration, note, operation_key, expected, previous_id=None):
    from apps.core.services import lock_case, event, bump
    from .models import ChangeClosure
    from .services import subject
    case = lock_case(actor, case_id, 'change.manage', expected)
    closure = ChangeClosure.objects.filter(pk=closure_id, authorization__version__change__case=case).first()
    if not closure:
        raise ValidationError('Select this case exact historical closure')
    client = subject(case, client_signature_id, 'signature') if client_signature_id else None
    repeated = closure.authorization.applicability_records.filter(operation_key=operation_key).first()
    row = capture(actor, closure.authorization, closure.receipt, closure.pm_signature, client,
        closure.execution_ids, note, declaration, operation_key, previous_id)
    if repeated and repeated.pk == row.pk:
        return row
    event(actor, case, 'change.applicability_recorded', record=row.pk, closure=closure.pk,
          requirement=row.requirement, client_signature_id=row.client_signature_id,
          client_signed=row.client_signature_id is not None, production_authorized=False)
    bump(case)
    return row


def presentation(auth, receipt, actor):
    from django.core.exceptions import PermissionDenied
    try:
        policy, entry = owner_requirement(auth)
        return {'status':entry['requirement'], 'policy_id':policy.pk,
                'declaration':declaration_draft(auth,receipt,actor) if receipt else '', 'finding':''}
    except (ValidationError, PermissionDenied) as exc:
        return {'status':'unresolved','policy_id':None,'declaration':'','finding':str(exc), 'question':OWNER_QUESTION}

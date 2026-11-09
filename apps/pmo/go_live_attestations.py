"""Declared, exact P33 signature linkage, not external signature authentication.

Source identities and actual signed-at values must be supplied by a human. This
module never creates a signature, selects a signer or infers a decision time.
"""
import re
from uuid import UUID
from django.core.exceptions import ValidationError
from django.utils import timezone
from .clocks import aware
from .models import DeliveryRecord, GateRecord

PROTOCOL = 'go-live-attestation/v1'
PURPOSE = 'go_live_business_acceptance'
ROLES = ('PM', 'Client')
IDENTITY = re.compile(r'[A-Za-z0-9][A-Za-z0-9._:/@+ -]{0,239}\Z')
HASH = re.compile(r'[0-9a-f]{64}\Z')
TIMESTAMP = re.compile(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})\Z')


def exact(value, keys, label):
    if not isinstance(value, dict) or set(value) != set(keys):
        raise ValidationError('Exact closed '+label+' fields required')


def integer(value):
    if type(value) is not int or not 1 <= value <= 9223372036854775807:
        raise ValidationError('Positive exact integer attestation pins required')


def identity(value):
    if not isinstance(value, str) or not IDENTITY.fullmatch(value) or value != value.strip():
        raise ValidationError('Bounded supplied source decision and signer identities required')


def evidence_pin(value):
    exact(value, ['id', 'version', 'sha256'], 'evidence pin')
    integer(value['id']); integer(value['version'])
    if not isinstance(value['sha256'], str) or not HASH.fullmatch(value['sha256']):
        raise ValidationError('Exact evidence SHA256 required')


def instant(value):
    if not isinstance(value, str) or not TIMESTAMP.fullmatch(value):
        raise ValidationError('Actual signed-at requires ISO timestamp with explicit timezone offset')
    return aware(value, 'Actual signed-at')


def validate_attestation(value, now=None):
    """Pure shape/purpose/time validation. No database lookup or invented facts."""
    exact(value, ['protocol', 'purpose', 'case_id', 'dossier_id', 'candidate', 'release', 'report', 'signatures', 'attesting_actor_id'], 'go-live attestation')
    if value['protocol'] != PROTOCOL or value['purpose'] != PURPOSE:
        raise ValidationError('Explicit go-live/business-acceptance purpose required; UAT is not go-live')
    if not isinstance(value['case_id'], str): raise ValidationError('Exact case UUID required')
    try:
        if str(UUID(value['case_id'])) != value['case_id']: raise ValueError
    except ValueError: raise ValidationError('Exact case UUID required')
    for key in ['dossier_id', 'attesting_actor_id']: integer(value[key])
    candidate = value['candidate']; exact(candidate, ['id', 'reference', 'requirements'], 'candidate')
    integer(candidate['id'])
    if not isinstance(candidate['reference'], str) or not 1 <= len(candidate['reference']) <= 160:
        raise ValidationError('Exact candidate reference required')
    evidence_pin(candidate['requirements'])
    release = value['release']; exact(release, ['id', 'external_ref', 'released_at'], 'release')
    integer(release['id'])
    if not isinstance(release['external_ref'], str) or not 1 <= len(release['external_ref']) <= 240:
        raise ValidationError('Exact actual release reference required')
    released = instant(release['released_at'])
    report = value['report']; exact(report, ['document_id', 'version_id', 'number', 'payload_sha256', 'receipt_id'], 'report')
    for key in ['document_id', 'version_id', 'number', 'receipt_id']: integer(report[key])
    if not isinstance(report['payload_sha256'], str) or not HASH.fullmatch(report['payload_sha256']):
        raise ValidationError('Exact report payload SHA256 required')
    exact(value['signatures'], ROLES, 'PM and Client signature roles')
    now = now or timezone.now()
    for signature in value['signatures'].values():
        exact(signature, ['evidence', 'source_system', 'source_reference', 'decision_id', 'decision_version', 'signer_reference', 'purpose', 'signed_at'], 'signature declaration')
        evidence_pin(signature['evidence'])
        for key in ['source_system', 'source_reference', 'decision_id', 'decision_version', 'signer_reference']: identity(signature[key])
        if signature['purpose'] != PURPOSE:
            raise ValidationError('Declared signature purpose must be go-live/business acceptance, not UAT')
        signed = instant(signature['signed_at'])
        if not released < signed <= now:
            raise ValidationError('Actual signed-at must be after actual release and not in the future')
    if value['signatures']['PM']['evidence']['id'] == value['signatures']['Client']['evidence']['id']:
        raise ValidationError('PM and Client require distinct exact signature evidence')
    return value


def pin(evidence):
    return {'id': evidence.pk, 'version': evidence.version, 'sha256': evidence.sha256}


def subject_pins(d, receipt, release):
    """Only existing subject facts, never signer/decision facts or a signed-at default."""
    v = receipt.publication.version
    return {'case_id': str(d.case_id), 'dossier_id': d.pk,
        'candidate': {'id': d.candidate_id, 'reference': d.candidate.reference, 'requirements': pin(d.candidate.requirements)},
        'release': {'id': release.pk, 'external_ref': release.data['external_ref'], 'released_at': release.data['released_at']},
        'report': {'document_id': v.document_id, 'version_id': v.pk, 'number': v.number,
                   'payload_sha256': v.payload_sha256, 'receipt_id': receipt.pk}}


def decision_key(signature):
    return tuple(signature[k] for k in ['source_system', 'source_reference', 'decision_id', 'decision_version'])


def validate_current_attestation(d, receipt, pm, client, binding, release, attestation, actor_id,
                                 previous=None, mode='fresh_signatures', current=None):
    """Shared relational validation for initial, successor and verified readback."""
    validate_attestation(attestation)
    expected = subject_pins(d, receipt, release)
    if any(attestation[key] != value for key, value in expected.items()) or attestation['attesting_actor_id'] != actor_id:
        raise ValidationError('Go-live attestation must bind this exact case/candidate/requirements/release/report/receipt and attesting PM')
    if receipt.payload_sha256 != receipt.publication.version.payload_sha256 or receipt.payload != receipt.publication.version.payload:
        raise ValidationError('Exact delivered payload required')
    for role, evidence in [('PM', pm), ('Client', client)]:
        if attestation['signatures'][role]['evidence'] != pin(evidence):
            raise ValidationError('Role-specific signature evidence version/hash differs')
    if GateRecord.objects.filter(kind__in=['uat_product_manager', 'uat_product_owner', 'uat_client'], evidence_id__in=[pm.pk, client.pk]).exists():
        raise ValidationError('Recorded UAT signature evidence cannot become post-release go-live acceptance')
    if mode not in ['fresh_signatures', 'metadata_binding']:
        raise ValidationError('Explicit fresh_signatures or metadata_binding mode required')
    if mode == 'metadata_binding':
        if not previous or any(previous.data.get(k) != value for k, value in
                [('receipt_id', receipt.pk), ('pm_signature_id', pm.pk), ('client_signature_id', client.pk)]) or previous.snapshot != binding.snapshot:
            raise ValidationError('Metadata binding requires exactly unchanged release/report/version/receipt/signature evidence')
        if any(instant(s['signed_at']) > previous.created_at for s in attestation['signatures'].values()):
            raise ValidationError('Metadata binding must retain actual decisions already made before the historical acceptance')
        old = previous.data.get('attestation')
        if isinstance(old,dict) and old.get('protocol')==PROTOCOL and (any(old.get(k) != attestation[k] for k in expected) or old.get('signatures') != attestation['signatures']):
            raise ValidationError('Metadata binding cannot alter original source decision facts or signed artifact')
    # Metadata repair can only repeat its own exact linear ancestry. Other accepted
    # uses, including reuploads of a declared source decision, remain disallowed.
    allowed = set()
    if mode == 'metadata_binding':
        ancestor = previous
        while ancestor and ancestor.kind in ['go_live', 'go_live_reaffirmation']:
            allowed.add(ancestor.pk); ancestor = ancestor.parent
    if current: allowed.add(current.pk)
    used = DeliveryRecord.objects.filter(kind__in=['go_live', 'go_live_reaffirmation'], dossier__case=d.case).exclude(pk__in=allowed)
    keys = {decision_key(s) for s in attestation['signatures'].values()}
    for row in used:
        if {pm.pk, client.pk} & {row.data.get('pm_signature_id'), row.data.get('client_signature_id')}:
            raise ValidationError('Go-live signature evidence cannot be reused')
        old_attestation=row.data.get('attestation')
        if isinstance(old_attestation,dict) and old_attestation.get('protocol')==PROTOCOL and any(decision_key(s) in keys for s in old_attestation.get('signatures', {}).values()):
            raise ValidationError('Declared source decision identity/version cannot be reused for a different acceptance')
    return attestation


def parse_attestation(text):
    """HTTP transports the supplied closed envelope; missing facts stay missing."""
    import json
    try:
        if not isinstance(text, str) or len(text) > 20000: raise ValueError
        value = json.loads(text)
    except (TypeError, ValueError):
        raise ValidationError('Supply the explicit go-live-attestation/v1 JSON declaration, including both actual signer decisions')
    return validate_attestation(value)


def declaration_draft(d, receipt, actor):
    """Render existing subject pins and visibly missing human facts, not sign-off."""
    import json
    from .delivery import latest
    release=latest(d,'release_outcome',False)
    if not release:return ''
    value=dict(subject_pins(d,receipt,release),protocol=PROTOCOL,purpose=PURPOSE,attesting_actor_id=actor.pk,
        signatures={role:{'evidence':{'id':None,'version':None,'sha256':None},
            **{key:None for key in ['source_system','source_reference','decision_id','decision_version','signer_reference','purpose','signed_at']}}
            for role in ROLES})
    return json.dumps(value,indent=2)

"""P60 exact signed change artifact facts. No signature creation/authentication."""
import json
from django.core.exceptions import ValidationError
from django.db import transaction, connection
from django.utils import timezone
from apps.core.services import lock_case, event, bump
from apps.identity.services import require
from apps.policy.services import decision_authority
from .go_live_attestations import exact, integer, identity, evidence_pin, instant, pin, decision_key
from .models import ChangeClosure, ChangeClosureSignatureBinding, GateRecord, DeliveryRecord

PROTOCOL='change-go-live-attestation/v1'
PURPOSE='change_go_live_acceptance'
ROLES=('PM','Client')


def subject_pins(auth, receipt):
    from .change_execution import execution_manifest
    v=receipt.publication.version
    return {'case_id':str(auth.version.change.case_id),
        'change':{'id':auth.version.change_id,'reference':auth.version.change.reference,
                  'version_id':auth.version_id,'number':auth.version.number,'evidence':pin(auth.version.evidence)},
        'authorization':{'id':auth.pk,'assessment_ids':auth.assessment_ids,'decision_ids':auth.decision_ids},
        'execution':[{'id':x.pk,'kind':x.kind,'evidence':pin(x.evidence)} for x in
                     auth.execution.filter(pk__in=execution_manifest(auth)).select_related('evidence').order_by('kind')],
        'report':{'document_id':v.document_id,'version_id':v.pk,'number':v.number,
                  'payload_sha256':v.payload_sha256,'receipt_id':receipt.pk}}


def validate_declaration(value):
    exact(value,['protocol','purpose','case_id','change','authorization','execution','report','signatures','attesting_actor_id'],'change go-live declaration')
    if value['protocol']!=PROTOCOL or value['purpose']!=PURPOSE:
        raise ValidationError('Actual change go-live signature purpose required; UAT is not change acceptance')
    integer(value['attesting_actor_id'])
    exact(value['signatures'],ROLES,'PM and Client signature roles')
    for s in value['signatures'].values():
        exact(s,['evidence','source_system','source_reference','decision_id','decision_version','signer_reference','purpose','signed_at'],'source signature declaration')
        evidence_pin(s['evidence'])
        for k in ['source_system','source_reference','decision_id','decision_version','signer_reference']:identity(s[k])
        if s['purpose']!=PURPOSE:raise ValidationError('Each signature must explicitly attest change go-live acceptance')
        if instant(s['signed_at'])>timezone.now():raise ValidationError('Actual signed-at cannot be in the future')
    if value['signatures']['PM']['evidence']['id']==value['signatures']['Client']['evidence']['id']:
        raise ValidationError('Distinct PM and Client signature evidence required')
    return value


def parse_declaration(text):
    try:
        if not isinstance(text,str) or len(text)>24000:raise ValueError
        value=json.loads(text)
    except (TypeError,ValueError):raise ValidationError('Supply the exact change-go-live-attestation/v1 declaration with actual source signature facts')
    from .change_applicability import PROTOCOL as APPLICABILITY_PROTOCOL, validate_declaration as validate_applicability
    if isinstance(value,dict) and value.get('protocol')==APPLICABILITY_PROTOCOL:
        return validate_applicability(value)
    return validate_declaration(value)


def validate_binding(row, *, current=False):
    from .change_execution import validate_authorization, execution_manifest, change_binding_findings
    from .models import ChangeDocumentBinding, CommercialSignaturePacket
    from apps.documents.controlled import current_version
    auth=row.authorization;case=auth.version.change.case
    validate_authorization(case,auth)
    require(row.actor,case,'change.manage')
    if decision_authority(row.actor,case,'PM')!=row.authority:raise ValidationError('Signature recorder authority changed; bind exact facts under current PM authority')
    if auth.applicability_records.exists():
        raise ValidationError('Use an applicability successor; preserve explicit owner decision history')
    receipt=row.receipt;version=receipt.publication.version
    current_version(case,version.pk)
    binding=ChangeDocumentBinding.objects.filter(version=version,authorization=auth,purpose='go_live').first()
    if not binding or change_binding_findings(binding) or row.execution_ids!=execution_manifest(auth) or binding.execution_ids!=row.execution_ids:
        raise ValidationError('Exact current authorized change execution and go-live document required')
    if version.audience!='client' or receipt.payload!=version.payload or receipt.payload_sha256!=version.payload_sha256:
        raise ValidationError('Exact delivered change go-live payload required')
    value=validate_declaration(row.declaration)
    if any(value[k]!=v for k,v in subject_pins(auth,receipt).items()) or value['attesting_actor_id']!=row.actor_id:
        raise ValidationError('Signature declaration must bind exact change/authorization/execution/report/receipt and recorder')
    previous=auth.signature_bindings.exclude(pk=row.pk).filter(pk__lt=row.pk).order_by('-pk').first() if row.pk else auth.signature_bindings.order_by('-pk').first()
    if row.previous_id!=(previous.pk if previous else None):raise ValidationError('Exact latest signature metadata predecessor required')
    closure=ChangeClosure.objects.filter(authorization=auth).first()
    if row.mode=='metadata_binding':
        if not closure or (closure.receipt_id,closure.pm_signature_id,closure.client_signature_id,closure.execution_ids)!=(row.receipt_id,row.pm_signature_id,row.client_signature_id,row.execution_ids):
            raise ValidationError('Metadata recovery requires the unchanged historical closure/artifact/receipt/signatures')
        if previous and {k:v for k,v in previous.declaration.items() if k!='attesting_actor_id'}!={k:v for k,v in value.items() if k!='attesting_actor_id'}:
            raise ValidationError('Metadata recovery cannot change original signature decisions or artifact')
    elif row.mode!='fresh_signatures' or previous or (closure and not current):
        raise ValidationError('Fresh signatures apply only to the initial exact change closure')
    signatures=value['signatures'];ids={row.pm_signature_id,row.client_signature_id}
    keys={decision_key(s) for s in signatures.values()}
    for role,evidence in [('PM',row.pm_signature),('Client',row.client_signature)]:
        s=signatures[role]
        if evidence.case_id!=case.pk or evidence.kind!='signature' or s['evidence']!=pin(evidence):raise ValidationError('Exact same-case role-specific signature evidence pin required')
        signed=instant(s['signed_at'])
        if signed<=version.created_at:raise ValidationError('Actual signature must follow creation of the signed report artifact')
        if row.mode=='metadata_binding' and signed>closure.created_at:raise ValidationError('Historical metadata must retain signatures made before original closure')
    if GateRecord.objects.filter(evidence_id__in=ids,kind__in=['uat_product_manager','uat_product_owner','uat_client']).exists():raise ValidationError('Recorded UAT signatures cannot become change go-live acceptance')
    for old in ChangeClosure.objects.filter(authorization__version__change__case=case).exclude(authorization=auth):
        if ids & {old.pm_signature_id,old.client_signature_id}:raise ValidationError('Signature evidence already closes another change')
    from .models import ChangeClosureApplicability
    for old in ChangeClosureApplicability.objects.filter(authorization__version__change__case=case).exclude(authorization=auth):
        if ids & {old.pm_signature_id,old.client_signature_id} or any(decision_key(s) in keys for s in old.declaration['signatures'].values()):raise ValidationError('Signature already belongs to another applicability change')
    for old in ChangeClosureSignatureBinding.objects.filter(authorization__version__change__case=case).exclude(authorization=auth):
        if ids & {old.pm_signature_id,old.client_signature_id} or any(decision_key(s) in keys for s in old.declaration['signatures'].values()):raise ValidationError('Signature source decision already belongs to another change')
    for old in DeliveryRecord.objects.filter(dossier__case=case,kind__in=['go_live','go_live_reaffirmation']):
        if ids & {old.data.get('pm_signature_id'),old.data.get('client_signature_id')} or any(decision_key(s) in keys for s in old.data.get('attestation',{}).get('signatures',{}).values()):raise ValidationError('Project go-live signatures cannot be reused as change signatures')
    for old in CommercialSignaturePacket.objects.filter(case=case):
        if ids & {s.get('evidence_id') for s in old.signatures.values()}:raise ValidationError('SOW/PRD signatures cannot be reused as change signatures')
    return row


def capture(actor,auth,receipt,pm,client,execution_ids,note,declaration,mode='fresh_signatures',previous_id=None):
    row=ChangeClosureSignatureBinding(authorization=auth,receipt=receipt,pm_signature=pm,client_signature=client,
        execution_ids=execution_ids,declaration=declaration,authority=decision_authority(actor,auth.version.change.case,'PM'),
        previous_id=previous_id,mode=mode,note=note,actor=actor)
    validate_binding(row);row.save();return row


def current_closure(closure):
    if closure.authorization.applicability_records.exists():
        from .change_applicability import current_closure as current_applicability
        return current_applicability(closure)
    row=closure.authorization.signature_bindings.order_by('-pk').first()
    if not row:raise ValidationError('Historical closure is legacy_unbound; retain history and explicitly bind actual signature metadata')
    if (row.receipt_id,row.pm_signature_id,row.client_signature_id,row.execution_ids)!=(closure.receipt_id,closure.pm_signature_id,closure.client_signature_id,closure.execution_ids):raise ValidationError('Signature binding differs from historical closure')
    validate_binding(row,current=True)
    with connection.cursor() as cursor:
        cursor.execute('SELECT psl_change_signature_current(r) FROM pmo_changeclosuresignaturebinding r WHERE id=%s',[row.pk])
        if cursor.fetchone()!=(True,):raise ValidationError('Current native change signature SQL proof required')
    return row


@transaction.atomic
def bind_historical(actor,case_id,closure_id,declaration,note,expected,previous_id=None):
    from .commercial import note_required
    case=lock_case(actor,case_id,'change.manage',expected);note_required(note)
    closure=ChangeClosure.objects.filter(pk=closure_id,authorization__version__change__case=case).first()
    if not closure:raise ValidationError('Select this case exact historical closure')
    row=capture(actor,closure.authorization,closure.receipt,closure.pm_signature,closure.client_signature,
                closure.execution_ids,note,declaration,'metadata_binding',previous_id)
    event(actor,case,'change.signature_metadata_bound',closure=closure.pk,binding=row.pk,previous=previous_id)
    bump(case);return row


def declaration_draft(auth,receipt,actor):
    """Existing subject pins only. Source decision/signature facts remain blank."""
    try:
        value=dict(subject_pins(auth,receipt),protocol=PROTOCOL,purpose=PURPOSE,attesting_actor_id=actor.pk,
            signatures={role:{'evidence':{'id':None,'version':None,'sha256':None},
                **{key:None for key in ['source_system','source_reference','decision_id','decision_version','signer_reference','purpose','signed_at']}} for role in ROLES})
        return json.dumps(value,indent=2)
    except ValidationError:return ''

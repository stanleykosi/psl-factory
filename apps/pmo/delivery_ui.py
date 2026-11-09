"""P22 references: Product/Design declares work; source owners decide elsewhere.

This typed internal correlation is not an authoritative external adapter or a
new approval workflow. Receipt versions never imply artifact versions.
"""
import hashlib
from django.core.exceptions import ValidationError
from django.utils import timezone
from apps.core.evidence_access import restricted
from apps.documents.contracts import validate
from apps.identity.services import require
from .clocks import aware
from .services import subject

KINDS = ('ui_target', 'ui_design', 'ui_client')
TEXT = {'type':'string', 'minLength':1, 'maxLength':240, 'pattern':r'\S'}
SHA = {'type':'string', 'pattern':'^[a-f0-9]{64}$'}
PIN = {'type':'object', 'properties':{
    'id':{'type':'integer','minimum':1}, 'version':{'type':'integer','minimum':1}, 'sha256':SHA},
    'required':['id','version','sha256'], 'additionalProperties':False}
IDENTITY = {'type':'object', 'properties':{
    'artifact_ref':TEXT, 'artifact_version':TEXT, 'artifact_sha256':SHA},
    'required':['artifact_ref','artifact_version','artifact_sha256'], 'additionalProperties':False}
TARGET = {'type':'object', 'properties':dict({k:{'anyOf':[v,{'type':'null'}]} for k,v in IDENTITY['properties'].items()},
    protocol={'const':'ui-target/v1'}, artifact_evidence={'anyOf':[PIN,{'type':'null'}]}),
    'required':['protocol','artifact_ref','artifact_version','artifact_sha256','artifact_evidence'],
    'additionalProperties':False}
APPROVAL = {'type':'object', 'properties':{
    'protocol':{'const':'ui-approval/v1'}, 'source_version':TEXT, 'signatory_ref':TEXT,
    'decided_at':{'type':'string','minLength':1,'maxLength':64,'pattern':r'T.*(Z|[+-][0-9]{2}(:?[0-9]{2})?(:[0-9]{2})?)$'}, 'approved_ui_target':IDENTITY},
    'required':['protocol','source_version','signatory_ref','decided_at','approved_ui_target'],
    'additionalProperties':False}


def identity(payload):
    return {k:payload[k] for k in IDENTITY['required']}


def validate_payload(kind, payload):
    if kind in ('ui_design','ui_client') and payload == {}:
        raise ValidationError('Legacy UI receipt has no approved artifact target; capture a typed owner source successor')
    validate(TARGET if kind == 'ui_target' else APPROVAL, payload)
    if kind != 'ui_target' and aware(payload['decided_at']) > timezone.now():
        raise ValidationError('UI source decision time must be an actual past instant')


def validate_capture(d, kind, external_ref, evidence, payload):
    """Exact same-case public pins and non-rebindable source identities."""
    validate_payload(kind, payload)
    if evidence.sha256 != hashlib.sha256(evidence.body.encode()).hexdigest():
        raise ValidationError('UI source evidence content hash is inconsistent')
    if restricted(evidence):
        raise ValidationError('UI references cannot expose restricted source evidence')
    if kind == 'ui_target':
        pin = payload['artifact_evidence']
        if pin is not None:
            artifact = subject(d.case, pin['id'])
            if restricted(artifact):
                raise ValidationError('UI references cannot expose restricted artifact evidence')
            if artifact.sha256 != hashlib.sha256(artifact.body.encode()).hexdigest():
                raise ValidationError('UI artifact evidence content hash is inconsistent')
            if pin != {'id':artifact.pk,'version':artifact.version,'sha256':artifact.sha256} or payload['artifact_sha256'] not in (None,artifact.sha256):
                raise ValidationError('UI target artifact hash and exact evidence pin must match captured artifact evidence')
        if all(payload[k] is not None for k in IDENTITY['required']):
            previous = d.sources.filter(kind=kind, payload__artifact_ref=payload['artifact_ref'],
                payload__artifact_version=payload['artifact_version'])
            if previous.exclude(payload__artifact_sha256=None).exclude(payload__artifact_sha256=payload['artifact_sha256']).exists():
                raise ValidationError('UI artifact reference/version already identifies different content; obtain an explicit owner successor version')
    else:
        previous = d.sources.filter(kind=kind, external_ref=external_ref, payload__source_version=payload['source_version'])
        if previous.exclude(payload=payload, evidence_id=evidence.pk).exists():
            raise ValidationError('UI source receipt version cannot be rebound; capture a new owner receipt version')


def validate_current(s, v=None):
    validate_capture(s.dossier, s.kind, s.external_ref, s.evidence, s.payload)
    require(s.actor, s.dossier.case, 'delivery.source')
    if s.kind=='ui_target' and any(s.payload[k] is None for k in [*IDENTITY['required'],'artifact_evidence']):
        raise ValidationError('Current declared UI target is incomplete; obtain Product/Design artifact version, hash and evidence')
    if v is not None:
        from apps.core.models import Case
        if not Case.objects.filter(pk=s.dossier.case_id,synthetic=True).exists():
            raise ValidationError('Operational UI source currentness needs an accepted authoritative adapter contract')
        from .delivery import source_result_schema
        validate(source_result_schema(s), v.result)


def current_target(d):
    # Never use an older verified target when the current declaration is held.
    from .delivery import verified_source
    head=d.sources.filter(kind='ui_target').order_by('-pk').first()
    if head is not None:validate_current(head)
    s, v = verified_source(d, 'ui_target')
    return s, v


def match_approval(d, approval):
    target, verification = current_target(d)
    validate_payload(approval.kind, approval.payload)
    if approval.payload['approved_ui_target'] != identity(target.payload):
        raise ValidationError('UI artifact target mismatch: '+approval.kind+' approves '+
            approval.payload['approved_ui_target']['artifact_version']+' but work targets '+
            target.payload['artifact_version']+'; obtain the owning team exact artifact receipt')
    return target, verification


def planning_binding(d, pins, client_required):
    from .delivery import verified_source
    target, verification = current_target(d)
    pins['ui_target'] = [target.pk, verification.pk]
    for kind in ['ui_design'] + (['ui_client'] if client_required else []):
        source = d.sources.filter(kind=kind).select_related('evidence').order_by('-pk').first()
        if source is not None:
            match_approval(d, source)
        s, v = verified_source(d, kind)
        pins[kind] = [s.pk, v.pk]
    return dict(identity(target.payload), artifact_evidence=target.payload['artifact_evidence'],
        source_id=target.pk, verification_id=verification.pk)

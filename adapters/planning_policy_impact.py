"""Bounded D11 readiness metadata, never source bodies or renewed readiness."""
import hashlib
import json
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models.functions import Length
from adapters.forecast import obj
from apps.documents.contracts import validate
from apps.core.models import Evidence, Audit
from apps.pmo import planning, approvals
from .planning_readiness_guard import readable as source_readable

KEY='pmo.planning_readiness'
COMPONENT='D11.planning_alignment'
MAX_CANDIDATES=100
MAX_BODY_BYTES=1048576
MAX_TOTAL_CHARACTERS=1048576
ID={'type':'integer','minimum':1}
HASH={'type':'string','pattern':'^[a-f0-9]{64}$'}
PIN=obj({'id':ID,'kind':{'type':'string'},'version':ID,'sha256':HASH})
OPTIONAL_PIN={'anyOf':[PIN,{'type':'null'}]}
CORRELATION_PIN=obj({'source':PIN,'target_prd_id':OPTIONAL_PIN,'target_scope_id':OPTIONAL_PIN,'evidence_id':OPTIONAL_PIN})
CORRELATION_PIN['properties']['resolution']=obj({'id':ID,'sha256':HASH})
CORRELATION=obj({'protocol':{'const':'planning-source-correlation/v1'},'complete':{'const':True},
    'findings':{'type':'array','maxItems':0},'source_pins':{'type':'object','maxProperties':100,'additionalProperties':CORRELATION_PIN},
    'resolution_ids':{'type':'array','maxItems':100,'items':ID},'approval_granted':{'const':False}})
SCHEMA=obj({'packet_id':ID,'packet_sha256':HASH,'comparison_required':{'type':'boolean'},'inputs':obj({
    'policy_id':ID,'alignment_links':obj({k:{'type':'array','minItems':2,'maxItems':2,'items':ID} for k in planning.PURPOSES}),
    'candidate_id':ID,'observations':obj({k:ID for k in planning.SUBJECTS}),
    'comparison_id':{'anyOf':[ID,{'type':'null'}]},'source_hashes':obj({k:HASH for k in planning.SOURCE_KINDS}),
    'source_correlation':CORRELATION,'native_verified':{'const':False}})})


def readable(actor,case):
    planning.readable(actor,case);approvals.readable(actor,case)


def parse(case,row):
    if row.case_id!=case.pk or row.kind!=planning.KINDS['ready'] or row.source!='psl:planning-v1':
        raise ValidationError('Exact native readiness evidence required')
    if len(row.body.encode())>MAX_BODY_BYTES or hashlib.sha256(row.body.encode()).hexdigest()!=row.sha256:
        raise ValidationError('Bounded immutable readiness content required')
    if not Audit.objects.filter(case=case,actor_id=row.created_by_id,action='planning.recorded',
            data={'kind':'ready','evidence_id':row.pk,'sha256':row.sha256}).exists():
        raise ValidationError('Native readiness provenance required')
    try:
        value=json.loads(row.body)
        validate(SCHEMA,value)
    except (ValueError,TypeError,ValidationError):
        raise ValidationError('Closed historical readiness metadata required') from None
    return value


def authorize_row(actor,case,row):
    readable(actor,case)
    value=parse(case,row)
    # Checks every current receipt source grant even if an earlier source is stale.
    packet=source_readable(actor,case,{'planning_packet_id':value['packet_id']})
    if packet.sha256!=value['packet_sha256']:
        raise ValidationError('Exact historical planning packet hash required')
    return value


def query(actor,config):
    if actor is None:raise PermissionDenied('Observer-scoped readiness selection required')
    readable(actor,config.case)
    if config.component!=COMPONENT:return Evidence.objects.none()
    candidates=Evidence.objects.filter(case=config.case,kind=planning.KINDS['ready'],source='psl:planning-v1').order_by('pk')
    sizes=list(candidates.annotate(body_length=Length('body')).values_list('pk','body_length')[:MAX_CANDIDATES+1])
    if len(sizes)>MAX_CANDIDATES or sum(size for _,size in sizes)>MAX_TOTAL_CHARACTERS or any(size>MAX_BODY_BYTES for _,size in sizes):
        raise ValidationError('Readiness history exceeds bounded metadata budget; no partial inventory returned')
    ids=[]
    for row in candidates.filter(pk__in=[pk for pk,_ in sizes]).iterator(chunk_size=20):
        value=authorize_row(actor,config.case,row)
        if value['inputs']['policy_id']==config.pk:ids.append(row.pk)
    return Evidence.objects.filter(case=config.case,pk__in=ids).order_by('pk')


def project(row):
    value=parse(row.case,row);current=True
    try:planning.current_readiness(row.case,row.pk)
    except (PermissionDenied,ValidationError):current=False
    head=planning.latest(row.case,'ready');packet_head=planning.latest(row.case,'packet')
    return {'id':row.pk,'kind':KEY,'metadata_only':True,'domain_route':'planning',
        'sha256':row.sha256,'packet':value['packet_id'],'packet_sha256':value['packet_sha256'],
        'readiness_head':head.pk if head else None,'packet_head':packet_head.pk if packet_head else None,
        'native_current':current,'state':'historical_readiness_requires_reassessment',
        'business_approval':False,'native_verified':False,'effects_performed':False}

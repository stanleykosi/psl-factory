"""Direct comparison policy pins; historical metadata never renews a contract."""
import hashlib
import json
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models.functions import Length
from adapters.forecast import obj
from apps.documents.contracts import validate
from apps.core.models import Evidence, Audit
from apps.identity.services import require
from apps.pmo import planning, approvals
from .planning_readiness_guard import readable as source_readable

KEY='pmo.planning_comparisons'
COMPONENT='D11.planning_alignment'
AUTHORITY='D05.role_principal_assignments'
MAX_CANDIDATES=100
MAX_BODY_BYTES=1048576
MAX_TOTAL_CHARACTERS=1048576
ID={'type':'integer','minimum':1}
HASH={'type':'string','pattern':'^[a-f0-9]{64}$'}
SCHEMA=obj({'packet_id':ID,'packet_sha256':HASH,'sow_id':ID,'signature_id':ID,
    'policy_id':ID,'verdict':{'enum':['no_difference','difference_unresolved']},
    'evidence_id':ID,'authority':obj({AUTHORITY:ID})})


def readable(actor,case):
    planning.readable(actor,case);approvals.readable(actor,case)
    require(actor,case,'commercial.read');require(actor,case,'document.read')


def parse(case,row):
    if row.case_id!=case.pk or row.kind!=planning.KINDS['comparison'] or row.source!='psl:planning-v1':
        raise ValidationError('Exact native comparison evidence required')
    if len(row.body.encode())>MAX_BODY_BYTES or hashlib.sha256(row.body.encode()).hexdigest()!=row.sha256:
        raise ValidationError('Bounded immutable comparison content required')
    if not Audit.objects.filter(case=case,actor_id=row.created_by_id,action='planning.recorded',
            data={'kind':'comparison','evidence_id':row.pk,'sha256':row.sha256}).exists():
        raise ValidationError('Native comparison provenance required')
    try:
        value=json.loads(row.body);validate(SCHEMA,value)
    except (ValueError,TypeError,ValidationError):
        raise ValidationError('Closed historical comparison metadata required') from None
    return value


def authorize_row(actor,case,row):
    readable(actor,case);value=parse(case,row)
    packet=source_readable(actor,case,{'planning_packet_id':value['packet_id']})
    if packet.sha256!=value['packet_sha256']:
        raise ValidationError('Exact historical comparison packet hash required')
    # Only already-public same-case signed artifacts are supported. Never treat
    # an arbitrary ID as authority to read a restricted artifact or its body.
    planning.proof(case,value['sow_id'],['sow'])
    planning.proof(case,value['signature_id'],['signature'])
    planning.proof(case,value['evidence_id'])
    return value


def query(actor,config):
    if actor is None:raise PermissionDenied('Observer-scoped comparison selection required')
    readable(actor,config.case)
    if config.component not in [COMPONENT,AUTHORITY]:return Evidence.objects.none()
    candidates=Evidence.objects.filter(case=config.case,kind=planning.KINDS['comparison'],source='psl:planning-v1').order_by('pk')
    sizes=list(candidates.annotate(body_length=Length('body')).values_list('pk','body_length')[:MAX_CANDIDATES+1])
    if len(sizes)>MAX_CANDIDATES or sum(size for _,size in sizes)>MAX_TOTAL_CHARACTERS or any(size>MAX_BODY_BYTES for _,size in sizes):
        raise ValidationError('Comparison history exceeds bounded metadata budget; no partial inventory returned')
    ids=[]
    for row in candidates.filter(pk__in=[pk for pk,_ in sizes]).iterator(chunk_size=20):
        value=authorize_row(actor,config.case,row)
        selected=value['policy_id'] if config.component==COMPONENT else value['authority'][AUTHORITY]
        if selected==config.pk:ids.append(row.pk)
    return Evidence.objects.filter(case=config.case,pk__in=ids).order_by('pk')


def project(row):
    value=parse(row.case,row);current=False
    try:
        packet,_=planning.packet(row.case,value['packet_id'])
        config,rules=planning.criteria(row.case)
        current=planning.comparison_context(row.case,packet,config,rules)==row.pk
    except (PermissionDenied,ValidationError):pass
    head=planning.latest(row.case,'comparison');packet_head=planning.latest(row.case,'packet')
    return {'id':row.pk,'kind':KEY,'metadata_only':True,'domain_route':'planning',
        'sha256':row.sha256,'packet':value['packet_id'],'packet_sha256':value['packet_sha256'],
        'comparison_head':head.pk if head else None,'packet_head':packet_head.pk if packet_head else None,
        'native_current':current,'state':'historical_comparison_requires_reassessment',
        'business_approval':False,'contract_renewed':False,'effects_performed':False}

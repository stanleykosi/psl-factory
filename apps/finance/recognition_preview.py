"""Private proposed input for unbound F33 observation, never an attestation."""
import hashlib
import json
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Max
from apps.core.models import Evidence, Audit
from apps.core.services import event, bump
from apps.identity.services import require
from . import recognition as native

KIND='agent_private_recognition_input'
SOURCE='psl:recognition-proposed-input/v1'
ACTION='agent.data.recognition_input'
FIELDS={'format','actor_id','packet_id','packet_sha256','operation_key','note','evidence_id','evidence_sha256','kind'}
HASH={'type':'string','pattern':'^[a-f0-9]{64}$'}
INPUT_SCHEMA={'type':'object','additionalProperties':False,'required':sorted(FIELDS),
    'properties':{'format':{'const':SOURCE},'kind':{'const':'attest'},
        'actor_id':native.ID,'packet_id':native.ID,'packet_sha256':HASH,
        'operation_key':native.KEY,'note':native.TEXT,'evidence_id':native.ID,'evidence_sha256':HASH}}


def readable(actor,case):
    require(actor,case,'case.read');require(actor,case,'recognition.read')


def envelope(actor,case,packet_id,operation_key,evidence_id,note):
    packet,e,_,_,_,_=native.guard_record(actor,case,packet_id,'attest',operation_key,evidence_id,note)
    return {'format':SOURCE,'kind':'attest','actor_id':actor.pk,'packet_id':packet.pk,
        'packet_sha256':packet.sha256,'operation_key':operation_key,'note':note,
        'evidence_id':e.pk,'evidence_sha256':e.sha256}


@transaction.atomic
def capture(actor,case_id,packet_id,operation_key,evidence_id,note,expected):
    case=native.locked(actor,case_id,'recognition.attest',expected)
    value=envelope(actor,case,packet_id,operation_key,evidence_id,note)
    body=json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False)
    # Restricted kind exists at INSERT, before any signal/observer can see it.
    version=(case.evidence.filter(kind=KIND).aggregate(v=Max('version'))['v'] or 0)+1
    row=Evidence.objects.create(case=case,kind=KIND,version=version,body=body,source=SOURCE,
        sha256=hashlib.sha256(body.encode()).hexdigest(),created_by=actor)
    event(actor,case,ACTION,evidence=row.pk,sha256=row.sha256)
    bump(case)
    return row


def get(observer,case,input_id,input_sha256):
    readable(observer,case) # No lookup or body parse before current domain grant.
    row=Evidence.objects.filter(case=case,pk=input_id,kind=KIND,source=SOURCE).first()
    if not row or row.sha256!=input_sha256 or hashlib.sha256(row.body.encode()).hexdigest()!=row.sha256:
        raise ValidationError('Exact private proposed input required')
    if not Audit.objects.filter(case=case,actor=row.created_by,action=ACTION,data__evidence=row.pk,data__sha256=row.sha256).exists():
        raise ValidationError('Native private capture provenance required')
    try:value=json.loads(row.body)
    except (ValueError,TypeError):raise ValidationError('Malformed private proposed input') from None
    if not isinstance(value,dict) or set(value)!=FIELDS or value['format']!=SOURCE or value['kind']!='attest' or value['actor_id']!=row.created_by_id:
        raise ValidationError('Malformed private proposed input')
    try:native.validate(INPUT_SCHEMA,value)
    except ValidationError:raise ValidationError('Malformed private proposed input') from None
    return row,value


def choices(observer,case):
    readable(observer,case)
    return Evidence.objects.filter(case=case,kind=KIND,source=SOURCE)


def guard(actor,case,recognition_input_id,recognition_input_sha256):
    row,value=get(actor,case,recognition_input_id,recognition_input_sha256)
    if value['actor_id']!=actor.pk:raise ValidationError('Exact proposed principal required')
    try:
        packet,e,intent,old,auth,_=native.guard_record(actor,case,value['packet_id'],'attest',value['operation_key'],value['evidence_id'],value['note'])
        if packet.sha256!=value['packet_sha256'] or e.sha256!=value['evidence_sha256']:
            raise ValidationError('Source identity changed')
    except ValidationError:
        # Native messages may carry private source details; never persist them in pilot findings.
        raise ValidationError('Private attestation input is not currently usable') from None
    return packet,{'input_id':row.pk,'input_sha256':row.sha256,'packet_id':packet.pk,
        'packet_sha256':packet.sha256,'authority':auth,'existing_record':old.pk if old else None,
        'scope':'unbound_proposed_attestation_observation','business_approval':False,
        'effects_scheduled':False,'separately_entered_intent_bound':False},old

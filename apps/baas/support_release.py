"""Exact draft -> projected packet -> human release. Internal storage is not customer response."""
from django.core.exceptions import ValidationError,PermissionDenied
from django.db import transaction
from django.utils import timezone
from apps.core.services import event,bump
from apps.identity.services import require
from apps.documents.contracts import digest,validate
from apps.policy.services import active_component,reference_values
from apps.policy.support_release_validators import COMPONENT,principal
from adapters.forecast import KEY
from . import support_agent as native,support
from .support_release_models import SupportResponsePacket as Packet,SupportResponseDecision as Decision,SupportResponseJob as Job,SupportResponseReceipt as Receipt

def rules(c):
 p=active_component(COMPONENT,c);return p,reference_values(p)[0]
def access(a,c,action='read'):
 native.source_access(a,c);require(a,c,'support.response.'+action)
def packet_for(c,pk):
 p=Packet.objects.select_related('draft__owner','case','actor').filter(case=c,pk=pk).first()
 if not p:raise ValidationError('Exact case response packet required')
 return p

def context(draft):
 report=native.report(draft.owner,draft.case_id,draft.pk)
 if not report['currently_approved']:raise ValidationError('Current exact human-approved draft required')
 policy,v=rules(draft.case)
 for key in ['recipient','releaser']:principal(draft.case,v,key)
 return {'policy':policy.pk,'draft':draft.pk,'draft_sha256':draft.sha256,'draft_review':report['review'],'lineage':draft.snapshot,'recipient':v['recipient_id'],'route':v['route'],'receipt_meaning':v['receipt_meaning'],'fields':v['fields'],'lease_seconds':v['lease_seconds']}

def projection(draft,fields):
 source=draft.source.projection.evidence
 import json
 selected=json.loads(source.body)['fields']
 result={}
 for field in fields:
  value=draft.body if field=='body' else selected.get(field)
  if not isinstance(value,str) or not value.strip():raise ValidationError('Selected response field unknown or outside approved source projection')
  result[field]=value
 return result

def current(p):
 pins=context(p.draft)
 if pins!=p.snapshot or projection(p.draft,pins['fields'])!=p.payload or digest(p.payload)!=p.sha256:raise ValidationError('Packet source/review/recipient/policy changed; prepare a new packet')
 return pins

@transaction.atomic
def prepare(a,case_id,draft_id,key,expected=None):
 c=native.locked(a,case_id,'support.response.prepare',expected);native.authority(a,c,'owner');validate(KEY,key)
 d=native.draft_for(c,draft_id);pins=context(d);payload=projection(d,pins['fields']);old=Packet.objects.filter(case=c,reference=key).first()
 if old:
  if old.draft_id!=d.pk or old.snapshot!=pins or old.payload!=payload or old.actor_id!=a.pk:raise ValidationError('Stable response intent changed')
  return old
 p=Packet.objects.create(case=c,reference=key,draft=d,actor=a,payload=payload,sha256=digest(payload),snapshot=pins)
 event(a,c,'agent.data.support_packet_prepared',packet=p.pk);bump(c);return p

def release_authority(a,p):
 c=p.case;access(a,c,'release');policy,v=rules(c)
 if a.pk!=v['releaser_id']:raise PermissionDenied('Configured human releaser required')
 principal(c,v,'releaser')
 preparers=[p.actor_id,p.draft.actor_id,p.draft.owner_id,p.draft.source.actor_id]
 auth=support.authority(a,c,'summary',preparers)
 if v['independent_release'] and a.pk in preparers:raise PermissionDenied('Independent human release required')
 return {'policy':policy.pk,'authority':auth,'packet_sha256':p.sha256}

def guard_decide(a,c,packet_id,verdict):
 p=packet_for(c,packet_id);auth=release_authority(a,p)
 if verdict not in ['release','withdraw']:raise ValidationError('Explicit human release/withdraw decision required')
 if verdict=='release':
  current(p)
  if Job.objects.filter(packet=p).exists():raise ValidationError('Already reserved intent; use recovery or a new reviewed packet')
 return p,auth

@transaction.atomic
def decide(a,case_id,pk,verdict,expected=None):
 c=native.locked(a,case_id,'support.response.release',expected)
 p,auth=guard_decide(a,c,pk,verdict)
 row=Decision.objects.create(packet=p,actor=a,verdict=verdict,snapshot=auth)
 if verdict=='release':Job.objects.create(packet=p,decision=row)
 event(a,c,'agent.data.support_response_decided',decision=row.pk);bump(c);return row

def releasable(j):
 p=j.packet;current(p);latest=Decision.objects.filter(packet=p).order_by('-pk').first();_,v=rules(p.case)
 if latest.pk!=j.decision_id or latest.verdict!='release':raise ValidationError('Release withdrawn')
 if latest.snapshot!=release_authority(latest.actor,p):raise ValidationError('Release authority changed')
 if (timezone.now()-latest.created_at).total_seconds()>v['release_ttl_seconds']:raise ValidationError('Release expired')
 return v

@transaction.atomic
def operate(a,case_id,pk,action,reason,expected=None):
 c=native.locked(a,case_id,'support.response.operate',expected);j=Job.objects.select_for_update().filter(packet__case=c,pk=pk).first()
 if not j or action not in ['retry','cancel'] or not isinstance(reason,str) or not reason.strip() or len(reason)>1000:raise ValidationError('Typed recovery and reason required')
 from adapters.support_response import InternalSupportResponseAdapter
 if InternalSupportResponseAdapter().lookup(j) or j.status in ['confirmed','cancelled'] or j.status=='leased' and j.lease_until>timezone.now():raise ValidationError('Committed/active intent cannot be changed')
 if action=='retry':
  from apps.workflows.readiness import gate
  gate(c,'supportresponse')
  v=releasable(j)
  if j.status!='held' or j.attempts>=v['max_attempts']:raise ValidationError('Only eligible held intent can retry within its original budget')
 j.status='pending' if action=='retry' else 'cancelled';j.error='Operator '+action;j.save(update_fields=['status','error'])
 event(a,c,'agent.data.support_response_operator',job=j.pk,operation=action,reason=reason);bump(c);return j

@transaction.atomic
def inspect(a,case_id,pk):
 c=native.locked(a,case_id,'support.response.read');p=packet_for(c,pk);access(a,c);j=Job.objects.filter(packet=p).first();r=Receipt.objects.filter(job=j).first() if j else None
 approved=False
 if j:
  try:releasable(j);approved=True
  except (ValidationError,PermissionDenied):pass
 return {'packet':p.pk,'draft':p.draft_id,'payload':p.payload,'sha256':p.sha256,'lineage':p.snapshot,'decisions':list(Decision.objects.filter(packet=p).order_by('pk').values('id','actor_id','verdict','created_at')),'job':j.pk if j else None,'status':j.status if j else 'unreleased','currently_releasable':approved,'receipt':r.pk if r else None,'receipt_classification':r.classification if r else None,'customer_delivery_verified':False,'response_clock_attested':False,'financial_effect':False}

@transaction.atomic
def receive(a,case_id,pk):
 c=native.locked(a,case_id,'support.response.receive');access(a,c,'receive');r=Receipt.objects.select_related('job__packet').filter(pk=pk,job__packet__case=c,recipient=a).first()
 if not r:raise ValidationError('Exact internal recipient receipt required')
 # Current destination authorisation is required even for historical inbox reads.
 _,v=rules(c)
 if principal(c,v,'recipient').pk!=a.pk:raise PermissionDenied('Current configured recipient required')
 from adapters.support_response import InternalSupportResponseAdapter
 InternalSupportResponseAdapter().lookup(r.job)
 return {'receipt':r.pk,'operation_key':r.operation_key,'payload':r.payload,'sha256':r.sha256,'classification':r.classification,'customer_delivery_verified':False,'response_clock_attested':False}

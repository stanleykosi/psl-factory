"""Supplied receipt identity -> authenticated read-only verification -> independent review -> human clock."""
import hashlib
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError,PermissionDenied
from django.db import transaction,connection
from django.utils import timezone
from apps.core.models import Evidence
from apps.core.services import event,bump
from apps.identity.services import require
from apps.documents.contracts import digest,validate
from apps.policy.models import PolicyState
from apps.policy.services import active_component,reference_values
from apps.policy.support_channel_validators import RECEIPTS,CLOCK,principal
from adapters.forecast import KEY
from adapters.support_channel import IDENTITY,RECEIPT,SupportChannelAdapter,binding
from . import support,support_agent as native,support_release as release
from .support_channel_models import SupportChannelClaim as Claim,SupportChannelCheck as Job,SupportChannelReceipt as Receipt,SupportChannelReview as Review,SupportClockAttestation as Attestation

def rules(c,component=RECEIPTS):
 p=active_component(component,c);return p,reference_values(p)[0]
def access(a,c,action='read'):
 native.source_access(a,c);require(a,c,'support.channel.'+action)
def locked(a,case_id,action,expected=None):
 c=native.locked(a,case_id,'support.channel.'+action,expected);access(a,c,action);return c

def authority(a,c,key,preparers=()):
 p,v=rules(c,CLOCK if key=='attestor' else RECEIPTS);person=principal(c,v,key)
 if a.pk!=person.pk:raise PermissionDenied('Exact configured channel principal required')
 if key=='reviewer' and a.pk in preparers:raise PermissionDenied('Independent channel evidence reviewer required')
 return {'policy':p.pk,'authority':support.authority(a,c,'summary' if key=='reviewer' else 'transition',preparers)}
def packet(c,pk):
 p=release.packet_for(c,pk);j=release.Job.objects.filter(packet=p).first()
 if not j or j.decision.verdict!='release' or 'body' not in p.payload:raise ValidationError('Exact human-released customer message body required; internal receipt alone is insufficient')
 if p.draft.source.intake.tenant!=c.tenant or p.draft.source.intake.payload['customer_ref']!=support.canonical(c)['customer_ref']:raise ValidationError('Native packet source identity/tenant mismatch')
 return p,j

def claim_for(c,pk):
 r=Claim.objects.select_related('case','packet__draft__source__intake','actor').filter(case=c,pk=pk).first()
 if not r:raise ValidationError('Exact case private channel claim required')
 return r

@transaction.atomic
def capture(a,case_id,packet_id,reference,external_ref,receipt_version,expected=None):
 c=locked(a,case_id,'capture',expected);support.authority(a,c,'triage');validate(KEY,reference);validate(KEY,external_ref);validate(KEY,receipt_version);p,j=packet(c,packet_id);_,v=rules(c);support.linked_current(c)
 key=digest({'tenant':c.tenant,'channel':v['channel_ref'],'account':v['account_ref'],'external_ref':external_ref})
 value={'protocol':v['protocol'],'receipt_key':key,'case_ref':str(c.pk),'tenant':c.tenant,'channel_ref':v['channel_ref'],'account_ref':v['account_ref'],'customer_ref':v['customer_ref'],'recipient_ref':v['recipient_ref'],'sender_ref':v['sender_ref'],'external_ref':external_ref,'receipt_version':receipt_version,'packet_sha256':p.sha256,'message_sha256':hashlib.sha256(p.payload['body'].encode('utf-8')).hexdigest()};validate(IDENTITY,value)
 # Stable external namespace is shared across cases; never reassign a receipt to another case.
 with connection.cursor() as cursor:cursor.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))',[key])
 old=Claim.objects.filter(tenant=c.tenant,channel=v['channel_ref'],account=v['account_ref'],external_ref=external_ref,predecessor__isnull=True).first()
 same=Claim.objects.filter(case=c,reference=reference).first()
 if old or same:
  old=old or same
  if old.case_id!=c.pk or old.reference!=reference or old.payload!=value or old.packet_id!=p.pk:raise ValidationError('Conflicting channel receipt identity; preserve original and investigate')
  return old
 row=Claim.objects.create(case=c,packet=p,tenant=c.tenant,channel=v['channel_ref'],account=v['account_ref'],external_ref=external_ref,reference=reference,payload=value,sha256=digest(value),actor=a);event(a,c,'agent.data.support_channel_claim',claim=row.pk);bump(c);return row

def intent(a,r):
 current_claim(r)
 access(a,r.case,'verify');auth=authority(a,r.case,'verifier');p,v=rules(r.case);b,_=binding(r.case,v);packet(r.case,r.packet_id)
 for field in ['channel_ref','account_ref','customer_ref','recipient_ref','sender_ref']:
  if r.payload[field]!=v[field]:raise ValidationError('Channel identity configuration changed')
 return {'policy':p.pk,'claim_sha256':r.sha256,'contract_evidence_sha256':Evidence.objects.get(pk=v['contract_evidence_id'],case=r.case).sha256,'authority':auth,'binding':b,'lease_seconds':v['lease_seconds'],'max_attempts':v['max_attempts']}

@transaction.atomic
def reserve(a,case_id,claim_id,key,expected=None):
 c=locked(a,case_id,'verify',expected);r=claim_for(c,claim_id);validate(KEY,key);pins=intent(a,r);old=Job.objects.filter(claim=r,intent_key=key).first()
 if old:
  if old.actor_id!=a.pk or old.intent!=pins:raise ValidationError('Receipt check intent changed')
  return old
 j=Job.objects.create(claim=r,actor=a,intent_key=key,operation_key=digest({'case':str(c.pk),'claim':r.pk,'key':key}),intent=pins);event(a,c,'agent.data.support_channel_check_reserved',job=j.pk);bump(c);return j

def validate_result(claim,result,v):
 validate(RECEIPT,result)
 if any(result[k]!=value for k,value in claim.payload.items()) or result['principal_ref']!=v['principal_ref'] or result['contract_version']!=v['contract_version']:raise ValidationError('Exact source/principal/contract/recipient/message receipt identity required')
 times={k:support.timestamp(result[k]) if result[k] is not None else None for k in ['sent_at','delivered_at']}
 if any(t and t>timezone.now() for t in times.values()) or times['delivered_at'] and (not times['sent_at'] or times['sent_at']>times['delivered_at']):raise ValidationError('Ordered nonfuture receipt times required')
 if result['status']=='delivered' and (not times['sent_at'] or not times['delivered_at']):raise ValidationError('Unknown delivery timestamps cannot prove delivery')
 return times

def delivered(r):
 _,v=rules(r.job.claim.case);times=validate_result(r.job.claim,r.payload,v)
 if r.payload['status']!='delivered' or not r.payload['human_response']:raise ValidationError('Only exact delivered human customer response qualifies')
 _,job=packet(r.job.claim.case,r.job.claim.packet_id)
 historical=reference_values(__import__('apps.policy.models',fromlist=['Configuration']).Configuration.objects.get(pk=job.packet.snapshot['policy']))[0]
 if times['sent_at']<job.decision.created_at or (times['sent_at']-job.decision.created_at).total_seconds()>historical['release_ttl_seconds'] or release.Decision.objects.filter(packet=job.packet,verdict='withdraw',created_at__lte=times['sent_at']).exists():raise ValidationError('Observed channel effect is outside recorded human release authority; preserve receipt and investigate')
 return times['delivered_at']

def accepted(r):
 current_claim(r.job.claim)
 c=r.job.claim.case;p,v=rules(c)
 if r.job.intent['policy']!=p.pk or Job.objects.filter(claim=r.job.claim).order_by('-pk').first().pk!=r.job_id or r.job.status!='confirmed':raise ValidationError('Latest successful channel verification under current policy required')
 # Credential bindings remain auditable after a committed check; no runtime secret is needed to read it.
 access(r.job.actor,c,'verify')
 if authority(r.job.actor,c,'verifier')!=r.job.intent['authority']:raise ValidationError('Channel verification authority changed')
 rr=Review.objects.select_related('actor').filter(receipt=r).order_by('-pk').first()
 preparers=[r.job.actor_id,r.job.claim.actor_id,r.job.claim.packet.actor_id]
 if not rr or rr.verdict!='confirm' or rr.authority!=authority(rr.actor,c,'reviewer',preparers):raise ValidationError('Current independent channel evidence review required')
 if (timezone.now()-rr.created_at).total_seconds()>v['review_ttl_seconds']:raise ValidationError('Channel review expired')
 delivered(r);return rr

@transaction.atomic
def review(a,case_id,receipt_id,verdict,expected=None):
 c=locked(a,case_id,'review',expected);r=Receipt.objects.select_related('job__claim__case','job__actor').filter(pk=receipt_id,job__claim__case=c).first()
 if not r or verdict not in ['confirm','return','withdraw']:raise ValidationError('Exact receipt and typed human review required')
 auth=authority(a,c,'reviewer',[r.job.actor_id,r.job.claim.actor_id,r.job.claim.packet.actor_id])
 if verdict=='confirm':
  current_claim(r.job.claim)
  delivered(r);p,_=rules(c)
  if r.job.intent['policy']!=p.pk or Job.objects.filter(claim=r.job.claim).order_by('-pk').first().pk!=r.job_id or r.job.status!='confirmed':raise ValidationError('Review exact latest completed verification')
 row=Review.objects.create(receipt=r,actor=a,verdict=verdict,authority=auth);event(a,c,'agent.data.support_channel_review',review=row.pk);bump(c);return row

def enrolled(c):return PolicyState.objects.filter(configuration__case=c,configuration__component=CLOCK,state='active').exists()
def clock_context(a,c,receipt_id):
 access(a,c,'attest');auth=authority(a,c,'attestor');r=Receipt.objects.select_related('job__claim__case').filter(pk=receipt_id,job__claim__case=c).first()
 if not r:raise ValidationError('Exact customer channel receipt required; internal storage receipt cannot attest a clock')
 rr=accepted(r);time=delivered(r);p,v=rules(c,CLOCK)
 if (timezone.now()-time).total_seconds()>v['max_receipt_age_seconds']:raise ValidationError('Clock evidence age exceeded')
 if Attestation.objects.filter(receipt__job__claim__packet_id=r.job.claim.packet_id).exists():raise ValidationError('Released customer message already has a human clock attestation')
 if time<min(support.timestamp(x.intake.payload['received_at']) for x in support.SupportLink.objects.filter(case=c).select_related('intake')):raise ValidationError('Customer response cannot precede case intake')
 return {'receipt':r.pk,'review':rr.pk,'receipt_sha256':r.sha256,'policy':p.pk,'authority':auth,'time':time.isoformat()}

@transaction.atomic
def attest(a,case_id,receipt_id,evidence_id,expected=None):
 c=locked(a,case_id,'attest',expected);pins=clock_context(a,c,receipt_id);head=support.head(c)
 return support.transition(a,c.pk,'respond',head.owner_id,evidence_id,pins['time'],None,'human',verified_receipt=receipt_id)

def record_clock(a,c,r,pins):
 row=Attestation.objects.create(case=c,receipt_id=pins['receipt'],event=r,actor=a,snapshot=pins);event(a,c,'agent.data.support_clock_attested',attestation=row.pk);return row

def metric_time(c,r):
 att=Attestation.objects.select_related('actor','receipt__job__claim__case').filter(case=c,event=r).first()
 if not att:return r.occurred_at if not enrolled(c) else None
 try:
  rr=accepted(att.receipt);p,_=rules(c,CLOCK)
  if rr.pk!=att.snapshot['review'] or p.pk!=att.snapshot['policy'] or authority(att.actor,c,'attestor')!=att.snapshot['authority']:return None
  return delivered(att.receipt)
 except (ValidationError,PermissionDenied):return None

@transaction.atomic
def inspect(a,case_id,claim_id):
 c=locked(a,case_id,'read');r=claim_for(c,claim_id);checks=[]
 for j in Job.objects.filter(claim=r).order_by('-pk')[:20]:
  receipt=Receipt.objects.filter(job=j).first();current=False
  if receipt:
   try:accepted(receipt);current=True
   except (ValidationError,PermissionDenied):pass
  checks.append({'job':j.pk,'status':j.status,'receipt':receipt.pk if receipt else None,'payload':receipt.payload if receipt else None,'classification':receipt.binding['classification'] if receipt else None,'contract_verified':receipt is not None,'review_history':list(Review.objects.filter(receipt=receipt).order_by('-pk').values('id','actor_id','verdict','created_at')[:20]) if receipt else [],'currently_reviewed_delivery':current,'live_customer_channel_evaluated':False,'live_gateway_receipt_reviewed':bool(current and receipt.binding['classification']=='authenticated_remote_claim'),'attestations':list(Attestation.objects.filter(receipt=receipt).values('id','event_id','created_at')) if receipt else []})
 return {'claim':r.pk,'packet':r.packet_id,'predecessor':r.predecessor_id,'successor':Claim.objects.filter(predecessor=r).values_list('pk',flat=True).first(),'supplied_identity':r.payload,'checks':checks,'no_dispatch':True,'financial_effect':False,'scope':'read-only configured gateway evidence; live vendor acceptance requires actual owner/source evidence'}

def current_claim(r):
 if Claim.objects.filter(predecessor=r).exists():raise ValidationError('Source receipt identity superseded; verify and review the explicit successor')

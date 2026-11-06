"""Human-reviewed metric successors. Never rewrite ordered events or historical projections."""
from django.db import transaction
from django.core.exceptions import ValidationError,PermissionDenied
from django.utils import timezone
from apps.core.services import event,bump
from apps.documents.contracts import validate
from apps.policy.support_channel_validators import CORRECTIONS,CLOCK,correction_principal
from adapters.forecast import KEY
from . import support_channel as d,support
from .support_channel_models import SupportClockCorrection as Correction,SupportClockCorrectionReview as Review

def private_evidence(c,pk,kind):
 e=d.Evidence.objects.filter(case=c,pk=pk,kind=kind).first()
 if not e:raise ValidationError('Exact case private correction/source evidence required')
 return e

def authority(a,c,purpose,preparers=()):
 p,v=d.rules(c,CORRECTIONS);person=correction_principal(c,v,purpose)
 if a.pk!=person.pk:raise PermissionDenied('Exact configured correction principal required')
 if purpose=='reviewer' and a.pk in preparers:raise PermissionDenied('Independent correction reviewer required')
 return {'policy':p.pk,'authority':support.authority(a,c,'summary' if purpose=='reviewer' else 'transition',preparers)}

@transaction.atomic
def successor(a,case_id,predecessor_id,reference,receipt_version,evidence_id,expected=None):
 c=d.locked(a,case_id,'successor',expected);_,v=d.rules(c,CORRECTIONS)
 if not v['allow_source_revision']:raise ValidationError('Source revision is not configured')
 auth=authority(a,c,'source_author')
 validate(KEY,reference);validate(KEY,receipt_version);old=d.claim_for(c,predecessor_id);e=private_evidence(c,evidence_id,'agent_private_channel_successor')
 existing=d.Claim.objects.filter(predecessor=old).first()
 if existing:
  if (existing.reference,existing.payload['receipt_version'],existing.evidence_id,existing.actor_id)!=(reference,receipt_version,e.pk,a.pk):raise ValidationError('Conflicting source successor; preserve original chain')
  return existing
 d.current_claim(old);d.packet(c,old.packet_id);support.linked_current(c)
 if d.Claim.objects.filter(case=c,reference=reference).exists():raise ValidationError('Distinct successor reference required')
 # A revision changes source version only. Corrected message/customer identity needs a new human release.
 if d.Claim.objects.filter(tenant=old.tenant,channel=old.channel,account=old.account,external_ref=old.external_ref,payload__receipt_version=receipt_version).exists():raise ValidationError('Distinct source revision required')
 row=d.Claim.objects.create(case=c,packet=old.packet,tenant=old.tenant,channel=old.channel,account=old.account,external_ref=old.external_ref,reference=reference,payload=dict(old.payload,receipt_version=receipt_version),sha256=d.digest(dict(old.payload,receipt_version=receipt_version)),actor=a,predecessor=old,evidence=e)
 event(a,c,'agent.data.support_channel_successor',claim=row.pk,predecessor=old.pk,authority=auth);bump(c);return row

def latest(c):return Correction.objects.filter(case=c).order_by('-version').first()

def basis(c,before_version=None):
 q=Correction.objects.filter(case=c,receipt__isnull=False)
 if before_version is not None:q=q.filter(version__lt=before_version)
 r=q.order_by('-version').first()
 if r:return r.receipt.job.claim.packet_id
 att=d.Attestation.objects.filter(case=c).order_by('event__version').first()
 return att.receipt.job.claim.packet_id if att else None

def pins(a,c,mode,receipt,before_version=None):
 auth=authority(a,c,'proposer');p,v=d.rules(c,CORRECTIONS)
 if mode not in v['allowed_modes']:raise ValidationError('Correction mode not configured')
 clock,clockv=d.rules(c,CLOCK);metric,_=support.config(c,'B14.metric_rules');support.linked_current(c);support.approved_flow(c)
 head=support.head(c)
 if not head:raise ValidationError('Started Support case required')
 if head.snapshot!={'flow_review':support.approved_flow(c).pk,**support.flow_snapshot(c)} or support.SupportMerge.objects.filter(source=c).exists():raise ValidationError('Current unmerged reviewed flow required')
 support.owner(c,head.owner_id)
 value={'policy':p.pk,'clock_policy':clock.pk,'metric_policy':metric.pk,'flow':support.flow_snapshot(c),'links':list(support.SupportLink.objects.filter(case=c).values_list('pk',flat=True)),'authority':auth,'receipt':None,'time':None}
 original=d.Attestation.objects.filter(case=c).order_by('event__version').first()
 value.update(projection_schema='psl.support-clock-correction/v1',original_attestation=original.pk if original else None,original_event=original.event_id if original else None)
 if mode=='withdraw':
  if receipt is not None:raise ValidationError('Withdrawal cannot install another receipt')
  return value
 if not receipt:raise ValidationError('Exact reviewed customer receipt required')
 rr=d.accepted(receipt);at=d.delivered(receipt)
 if (timezone.now()-at).total_seconds()>min(v['max_receipt_age_seconds'],clockv['max_receipt_age_seconds']):raise ValidationError('Correction receipt age exceeded')
 intake=min(support.timestamp(x.intake.payload['received_at']) for x in support.SupportLink.objects.filter(case=c).select_related('intake'))
 if at<intake:raise ValidationError('Clock cannot precede intake')
 prior=basis(c,before_version)
 if mode in ['replace','revalidate'] and (prior is None or receipt.job.claim.packet_id!=prior):raise ValidationError('Correction must retain original released-message lineage')
 if mode=='revalidate':
  q=Correction.objects.filter(case=c,receipt__isnull=False)
  if before_version is not None:q=q.filter(version__lt=before_version)
  previous=q.order_by('-version').first()
  original=d.Attestation.objects.filter(case=c).order_by('event__version').first()
  previous_time=previous.snapshot['time'] if previous else original.snapshot['time']
  if at!=support.timestamp(previous_time):raise ValidationError('Revalidation retains exact recorded clock time; changed time requires replacement')
 if mode=='late' and (prior is not None or at>=head.occurred_at):raise ValidationError('Late reconciliation requires unbound evidence preceding current history')
 value.update(receipt=receipt.pk,receipt_sha256=receipt.sha256,review=rr.pk,time=at.isoformat());return value

@transaction.atomic
def propose(a,case_id,mode,receipt_id,key,predecessor,evidence_id,reason,expected=None):
 c=d.locked(a,case_id,'correct',expected);validate(KEY,key)
 if not isinstance(reason,str) or not 1<=len(reason.strip())<=400:raise ValidationError('Bounded human correction reason required')
 e=private_evidence(c,evidence_id,'agent_private_clock_correction');r=d.Receipt.objects.filter(pk=receipt_id,job__claim__case=c).first() if receipt_id is not None else None
 if receipt_id is not None and not r:raise ValidationError('Exact case receipt required')
 old=Correction.objects.filter(case=c,operation_key=key).first()
 if old:
  authority(a,c,'proposer')
  if (old.actor_id,old.mode,old.receipt_id,old.predecessor_id,old.evidence_id,old.reason)!=(a.pk,mode,receipt_id,predecessor,e.pk,reason):raise ValidationError('Correction intent conflict')
  return old
 head=latest(c)
 if predecessor!=(head.pk if head else None):raise ValidationError('Explicit latest correction predecessor required')
 snapshot=pins(a,c,mode,r)
 row=Correction.objects.create(case=c,version=head.version+1 if head else 1,operation_key=key,predecessor=head,mode=mode,receipt=r,evidence=e,reason=reason,snapshot=snapshot,actor=a)
 event(a,c,'agent.data.support_clock_correction_proposed',correction=row.pk);bump(c);return row

def current(r):
 if latest(r.case).pk!=r.pk or pins(r.actor,r.case,r.mode,r.receipt,r.version)!=r.snapshot:raise ValidationError('Correction context changed; prepare an explicit successor')

@transaction.atomic
def review(a,case_id,pk,verdict,evidence_id,expected=None):
 c=d.locked(a,case_id,'correct_review',expected);r=Correction.objects.select_related('case','actor','receipt__job__claim__case').filter(case=c,pk=pk).first()
 if not r or verdict not in ['confirm','return','withdraw']:raise ValidationError('Exact correction and typed human verdict required')
 preparers=[r.actor_id,r.receipt.job.actor_id,r.receipt.job.claim.actor_id,r.receipt.job.claim.packet.actor_id] if r.receipt else [r.actor_id]
 auth=authority(a,c,'reviewer',preparers);e=private_evidence(c,evidence_id,'agent_private_clock_review')
 if verdict=='confirm':current(r)
 row=Review.objects.create(correction=r,actor=a,verdict=verdict,evidence=e,authority=auth);event(a,c,'agent.data.support_clock_correction_review',review=row.pk);bump(c);return row

def projection(c):
 r=latest(c)
 if not r:return None
 result={'correction':r.pk,'version':r.version,'review':None,'time':None,'finding':'clock_correction_not_current'}
 try:
  current(r);rr=Review.objects.filter(correction=r).select_related('actor').order_by('-pk').first()
  preparers=[r.actor_id,r.receipt.job.actor_id,r.receipt.job.claim.actor_id,r.receipt.job.claim.packet.actor_id] if r.receipt else [r.actor_id]
  _,v=d.rules(c,CORRECTIONS)
  if not rr or rr.verdict!='confirm' or authority(rr.actor,c,'reviewer',preparers)!=rr.authority or (timezone.now()-rr.created_at).total_seconds()>v['review_ttl_seconds']:return result
  result.update(review=rr.pk,time=r.snapshot['time'],finding='customer_clock_withdrawn' if r.mode=='withdraw' else None)
 except (ValidationError,PermissionDenied):pass
 return result

def history(a,c):
 d.access(a,c)
 stored=support.SupportCase.objects.filter(case=c).first()
 return {'current_projection':projection(c),'historical_first_response_at':stored.first_response_at if stored else None,'events_rewritten':False,'rows':[{'id':r.pk,'version':r.version,'predecessor':r.predecessor_id,'mode':r.mode,'receipt':r.receipt_id,'reason':r.reason,'snapshot':r.snapshot,'actor':r.actor_id,'reviews':list(Review.objects.filter(correction=r).order_by('-pk').values('id','actor_id','verdict','created_at'))} for r in Correction.objects.filter(case=c).order_by('-version')[:30]]}

def coverage_end(c,at):
 current=projection(c)
 return max(at,support.timestamp(current['time'])) if current and current['time'] and not current['finding'] else at

"""B14 native authority -> reviewed private extraction -> human-owned draft. No send."""
import json
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError,PermissionDenied
from django.db import transaction
from django.utils import timezone
from apps.core.models import Evidence
from apps.core.services import add_evidence,event,bump
from apps.identity.services import require
from apps.documents.contracts import digest,validate
from apps.policy.services import active_component,reference_values
from apps.policy.support_agent_validators import COMPONENT
from adapters.forecast import KEY
from adapters.support_projection import SupportProjectionAdapter
from apps.agents import boundary as gateway
from . import support
from .support_models import SupportIntake,SupportLink,SupportMerge
from .support_agent_models import SupportProjection,SupportAgentDraft as Draft,SupportAgentDraftReview as Review
KIND='agent_private_support'

def source_access(a,c):
 gateway.readable(a,c,True);support.readable(a,c);require(a,c,'support.private.read')
def rules(c):
 p=active_component(COMPONENT,c);return p,reference_values(p)[0]
def locked(a,case_id,action,expected=None):
 c=gateway.locked(a,case_id,action,expected);source_access(a,c)
 if c.kind!='support':raise ValidationError('Native support case required')
 return c
def authority(a,c,stem,preparers=()):
 source_access(a,c);p,v=rules(c);require(a,c,{'projector':'support.agent.project','owner':'support.agent.draft','reviewer':'support.agent.review'}[stem])
 if a.pk!=v[stem+'_id']:raise PermissionDenied('Exact configured native Support principal required')
 if stem=='owner':require(a,c,'support.own')
 auth=support.authority(a,c,{'projector':'triage','owner':'transition','reviewer':'summary'}[stem],preparers)
 return {'policy':p.pk,'native_authority':auth}
def source_snapshot(c,intake,a):
 p,v=rules(c);auth=authority(a,c,'projector');support.linked_current(c);flow=support.approved_flow(c);head=support.head(c)
 if not head or SupportMerge.objects.filter(source=c).exists():raise ValidationError('Current unmerged owned support flow required')
 flowpins=support.flow_snapshot(c)
 if head.snapshot!={'flow_review':flow.pk,**flowpins}:raise ValidationError('Case must explicitly adopt the current reviewed flow before projection or reuse')
 _,flowrules=support.config(c,'B14.flow_rules')
 if support.meaning(flowrules,head.state) in ['resolved','cancelled','merged']:raise ValidationError('A closed case cannot create or reuse an active response draft')
 if head.owner_id!=v['owner_id']:raise ValidationError('Configured draft owner must be the current support owner')
 if intake.case_id!=c.pk or intake.tenant!=c.tenant or intake.pk not in v['intake_ids'] or not SupportLink.objects.filter(case=c,intake=intake).exists():raise ValidationError('Exact currently linked authorised case/tenant intake required')
 return {'policy':p.pk,'source':intake.pk,'source_sha256':intake.sha256,'source_evidence_sha256':intake.evidence.sha256,'links':list(SupportLink.objects.filter(case=c).order_by('pk').values_list('pk',flat=True)),'head':head.pk,'flow_review':flow.pk,'flow':support.flow_snapshot(c),'intake_policy':support.config(c,'B14.intake_rules')[0].pk,'projector':auth,'owner':authority(get_user_model().objects.get(pk=v['owner_id']),c,'owner'),'fields':v['fields'],'purpose':v['purpose']}
def binding(p):
 r=SupportProjection.objects.select_related('intake__evidence','actor').filter(projection=p,case=p.case).first()
 if not r:raise ValidationError('Native support projection binding required; manually labelled evidence is insufficient')
 return r
def current(p):
 r=binding(p)
 if r.snapshot!=source_snapshot(p.case,r.intake,r.actor):raise ValidationError('Native source/owner/flow/policy changed; fresh projection required')
 expected=SupportProjectionAdapter().project(r.intake,r.snapshot['fields']);quotes=list(dict.fromkeys(expected['fields'].values()))
 if p.process_id!='B14' or p.purpose!=r.snapshot['purpose'] or p.payload['quotes']!=quotes or p.evidence.body!=json.dumps(expected,ensure_ascii=False,sort_keys=True):raise ValidationError('Native projection provenance mismatch')
 return r

@transaction.atomic
def project(a,case_id,intake_id,key,expected=None):
 c=locked(a,case_id,'support.agent.project',expected);require(a,c,'agent.data.project');validate(KEY,key)
 i=SupportIntake.objects.select_related('evidence').filter(case=c,pk=intake_id).first()
 if not i:raise ValidationError('Exact case supplied intake required')
 pins=source_snapshot(c,i,a);old=SupportProjection.objects.filter(case=c,intent_key=key).first()
 if old:
  if old.intake_id!=i.pk or old.actor_id!=a.pk or old.snapshot!=pins:raise ValidationError('Projection intent changed; new reviewed key required')
  return old
 value=SupportProjectionAdapter().project(i,pins['fields']);quotes=list(dict.fromkeys(value['fields'].values()))
 if len('\n'.join(quotes))>12000:raise ValidationError('Projection engineering budget exceeded')
 e=add_evidence(a,c.pk,KIND,json.dumps(value,ensure_ascii=False,sort_keys=True),'internal:support-intake-projection')
 payload={'quotes':quotes,'source_sha256':e.sha256,'source_version':e.version}
 p=gateway.Projection.objects.create(case=c,evidence=e,process_id='B14',purpose=pins['purpose'],version=1,payload=payload,sha256=digest(payload),actor=a)
 r=SupportProjection.objects.create(case=c,intent_key=key,projection=p,intake=i,policy_id=pins['policy'],snapshot=pins,actor=a);event(a,c,'agent.data.support_projected',binding=r.pk);bump(c);return r

def result_context(a,c,receipt):
 source_access(a,c);r=gateway.Receipt.objects.select_related('job__projection__case','job__projection__evidence').filter(job__projection__case=c,pk=receipt).first()
 if not r or r.job.projection.evidence.kind!=KIND:raise ValidationError('Exact native support extraction receipt required')
 source=current(r.job.projection);report=gateway.inspect(a,c.pk,r.pk)
 if not report['currently_accepted']:raise ValidationError('Current human-reviewed extraction required before reuse')
 rr=gateway.Review.objects.get(pk=report['review']);p,v=rules(c)
 return source,rr,{'source':source.pk,'result_review':rr.pk,'policy':p.pk,'owner':authority(a,c,'owner')}

@transaction.atomic
def reuse(a,case_id,receipt,key,expected=None):
 c=locked(a,case_id,'support.agent.draft',expected);validate(KEY,key);source,rr,pins=result_context(a,c,receipt)
 text='\n'.join(f['quote'] for f in rr.result['facts']);_,v=rules(c)
 if not text or len(text)>v['max_draft_chars']:raise ValidationError('Reviewed quotes must form a nonempty bounded draft')
 old=Draft.objects.filter(case=c,reference=key).order_by('-version').first()
 if old:
  if old.snapshot!=pins or old.result_review_id!=rr.pk:raise ValidationError('Draft intent changed; use a new reference')
  return old
 row=Draft.objects.create(case=c,reference=key,version=1,source=source,result_review=rr,owner=a,actor=a,body=text,sha256=digest({'text':text}),snapshot=pins);event(a,c,'agent.data.support_drafted',draft=row.pk);bump(c);return row
def draft_for(c,pk):
 r=Draft.objects.select_related('source__projection','result_review__receipt').filter(case=c,pk=pk).first()
 if not r:raise ValidationError('Exact private support draft required')
 return r
def current_draft(a,r):
 if Draft.objects.filter(case=r.case,reference=r.reference,version__gt=r.version).exists():raise ValidationError('Draft superseded')
 _,_,pins=result_context(a,r.case,r.result_review.receipt_id)
 if pins!=r.snapshot:raise ValidationError('Reviewed source/result/owner context changed')
 return pins
@transaction.atomic
def revise(a,case_id,pk,body,expected=None):
 c=locked(a,case_id,'support.agent.draft',expected);r=draft_for(c,pk);current_draft(a,r);_,v=rules(c)
 if a.pk!=r.owner_id:raise PermissionDenied('Current named human owner required')
 if not isinstance(body,str) or not body.strip() or len(body)>v['max_draft_chars']:raise ValidationError('Bounded human revision required')
 row=Draft.objects.create(case=c,reference=r.reference,version=r.version+1,parent=r,source=r.source,result_review=r.result_review,owner=a,actor=a,body=body,sha256=digest({'text':body}),snapshot=r.snapshot);event(a,c,'agent.data.support_draft_revised',draft=row.pk);bump(c);return row
@transaction.atomic
def review(a,case_id,pk,verdict,expected=None):
 c=locked(a,case_id,'support.agent.review',expected);r=draft_for(c,pk);auth=authority(a,c,'reviewer',[r.actor_id,r.owner_id,r.source.actor_id]);_,v=rules(c)
 if verdict not in ['approve','return','withdraw']:raise ValidationError('Typed draft review required')
 if v['independent_review'] and a.pk in [r.actor_id,r.owner_id,r.source.actor_id]:raise PermissionDenied('Independent draft reviewer required')
 if verdict=='approve':current_draft(r.owner,r)
 row=Review.objects.create(draft=r,actor=a,verdict=verdict,authority=auth);event(a,c,'agent.data.support_draft_reviewed',review=row.pk);bump(c);return row
@transaction.atomic
def report(a,case_id,pk):
 c=locked(a,case_id,'support.agent.read');r=draft_for(c,pk);rr=Review.objects.select_related('actor').filter(draft=r).order_by('-pk').first();accepted=False
 if rr and rr.verdict=='approve':
  try:
   current_draft(r.owner,r);_,v=rules(c);accepted=rr.authority==authority(rr.actor,c,'reviewer',[r.actor_id,r.owner_id,r.source.actor_id]) and (timezone.now()-rr.created_at).total_seconds()<=v['review_ttl_seconds']
  except (ValidationError,PermissionDenied):pass
 history=[{'id':x.pk,'verdict':x.verdict,'actor':x.actor_id,'recorded_at':x.created_at.isoformat()} for x in Review.objects.filter(draft=r).order_by('-pk')[:20]]
 return {'draft':r.pk,'version':r.version,'body':r.body,'owner':r.owner_id,'sha256':r.sha256,'lineage':r.snapshot,'review':rr.pk if rr else None,'review_history':history,'currently_approved':accepted,'human_revision':r.parent_id is not None,'parent':r.parent_id,'provider_binding_classification':r.result_review.receipt.job.intent['binding']['classification'],'real_model_evaluated':False,'sent':False,'support_state_changed':False,'financial_effect':False}

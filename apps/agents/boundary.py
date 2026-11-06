"""Reviewed projection -> private extraction -> human correction. No business tools."""
import json
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError,PermissionDenied
from django.db import transaction
from django.utils import timezone
from apps.core.models import Evidence
from apps.core.services import lock_case,event,bump
from apps.identity.models import Grant
from apps.identity.services import require
from apps.documents.contracts import digest,validate
from apps.policy.services import active_component,reference_values,decision_authority
from apps.policy.agent_data_validators import COMPONENT
from apps.workflows import readiness
from apps.workflows.readiness_models import IntegrationSelection
from adapters.forecast import KEY
from adapters.readiness import binding
from .boundary_models import EvidenceProjection as Projection,EvidenceProjectionReview as ProjectionReview,EvidenceExtraction as Job,EvidenceExtractionReceipt as Receipt,EvidenceExtractionReview as Review

# Closed adapter inventory, not a broad permission bypass for payroll/HR/Finance.
SOURCE_KINDS=('plan','completion','agent_private_input')
def permitted_source(e):
 if e.kind=='agent_private_ledger':
  from apps.finance.ledger_agent_models import LedgerProjection
  return LedgerProjection.objects.filter(case=e.case,projection__evidence=e).exists()
 if e.kind=='agent_private_support':
  from apps.baas.support_agent_models import SupportProjection
  return SupportProjection.objects.filter(case=e.case,projection__evidence=e).exists()
 return e.kind in SOURCE_KINDS

def source_access(a,p):
 if p.evidence.kind=='agent_private_ledger':
  from apps.finance.ledger_agents import projection_access
  projection_access(a,p)
 if p.evidence.kind=='agent_private_support':
  from apps.baas.support_agent import source_access as access
  access(a,p.case)
def process_allowed(c,process):
 rows=json.loads((settings.BASE_DIR/'contracts/process-map.json').read_text(encoding='utf-8'))['rows']
 if not any(r['id']==process and (c.kind!='support' or r['workflow_family_id']=='AF01') for r in rows):raise ValidationError('Exact supported process required')
def readable(a,c,private=False):
 if not get_user_model().objects.filter(pk=a.pk,is_active=True).exists():raise PermissionDenied('Active data principal required')
 for action in ['case.read','agent.data.read']+(['agent.data.source'] if private else []):require(a,c,action)
def lock_scope(case_id):
 from apps.finance.ledger_agent_models import LedgerProjection
 if LedgerProjection.objects.filter(case_id=case_id).exists():
  from apps.finance.ledger import scope_lock
  scope_lock(case_id)

def locked(a,case_id,action,expected=None):
 lock_scope(case_id)
 c=lock_case(a,case_id,action,expected);lock_principals(c);readable(a,c,True);return c
def lock_principals(c):
 grants=list(Grant.objects.select_for_update().filter(case=c).order_by('pk'))
 list(get_user_model().objects.select_for_update().filter(pk__in={g.user_id for g in grants}).order_by('pk'))
def projection_for(c,pk):
 p=Projection.objects.select_related('case','evidence','actor').filter(case=c,pk=pk).first()
 if not p:raise ValidationError('Exact case projection required')
 return p
def current(p):
 if p.evidence.kind=='agent_private_ledger':
  from apps.finance.ledger_agents import current as native_current
  native_current(p);return
 if p.evidence.kind=='agent_private_support':
  from apps.baas.support_agent import current as native_current
  native_current(p);return
 if Projection.objects.filter(case=p.case,evidence=p.evidence,process_id=p.process_id,purpose=p.purpose,version__gt=p.version).exists() or Evidence.objects.filter(case=p.case,kind=p.evidence.kind,version__gt=p.evidence.version).exists():raise ValidationError('Superseded source/projection requires fresh review')
def rules(c):
 policy=active_component(COMPONENT,c);return policy,reference_values(policy)[0]
def authority(a,c,purpose):
 readable(a,c,True);require(a,c,'agent.data.'+('send' if purpose=='sender' else 'review'))
 p,v=rules(c)
 if a.pk!=v[purpose+'_id']:raise PermissionDenied('Exact configured data principal required')
 return {'policy':p.pk,'role_authority':decision_authority(a,c,v[purpose+'_role'])}

@transaction.atomic
def project(a,case_id,evidence_id,process,purpose,quotes,predecessor=None,expected=None):
 c=locked(a,case_id,'agent.data.project',expected);validate(KEY,purpose);process_allowed(c,process)
 e=Evidence.objects.filter(case=c,pk=evidence_id).first()
 if not e or e.kind in ['agent_private_support','agent_private_ledger'] or not permitted_source(e):raise ValidationError('Use a supported, authorised domain projection source')
 if not isinstance(quotes,list) or not 1<=len(quotes)<=8 or any(not isinstance(q,str) or not q or q not in e.body for q in quotes) or len(set(quotes))!=len(quotes):raise ValidationError('One to eight distinct exact source quotations required')
 payload={'quotes':quotes,'source_sha256':e.sha256,'source_version':e.version}
 if sum(map(len,quotes))>12000:raise ValidationError('Projection engineering ceiling exceeded')
 old=Projection.objects.filter(case=c,evidence=e,process_id=process,purpose=purpose).order_by('-version').first()
 if old and old.sha256==digest(payload):return old
 if predecessor!=(old.pk if old else None):raise ValidationError('Explicit projection predecessor required')
 p=Projection.objects.create(case=c,evidence=e,process_id=process,purpose=purpose,version=old.version+1 if old else 1,payload=payload,sha256=digest(payload),actor=a)
 event(a,c,'agent.data.projected',projection=p.pk);bump(c);return p

def finance_review(a,p,preparers=()):
 if p.evidence.kind=='agent_private_ledger':
  from apps.finance.ledger_agents import egress_review
  egress_review(a,p,preparers)

def visible_projections(a,c):
 ids=[]
 for p in Projection.objects.filter(case=c).select_related('case','evidence').order_by('-pk')[:200]:
  try:source_access(a,p)
  except PermissionDenied:continue
  ids.append(p.pk)
 return Projection.objects.filter(pk__in=ids)

def projection_policy(p):
 current(p);policy,v=rules(p.case)
 if p.evidence_id not in v['evidence_ids'] or p.process_id not in v['process_ids'] or p.purpose!=v['purpose']:raise ValidationError('Exact source/process/purpose egress policy required')
 if len('\n'.join(p.payload['quotes']))>v['max_input_chars']:raise ValidationError('Configured input budget exceeded')
 return policy,v

@transaction.atomic
def review_projection(a,case_id,pk,verdict,expected=None):
 c=locked(a,case_id,'agent.data.review',expected);p=projection_for(c,pk);source_access(a,p);finance_review(a,p,[p.actor_id]);auth=authority(a,c,'reviewer');policy,v=projection_policy(p)
 if verdict not in ['confirm','return','withdraw']:raise ValidationError('Typed review verdict required')
 if v['independent_review'] and a.pk in [p.actor_id,v['sender_id']]:raise PermissionDenied('Independent projection reviewer required')
 r=ProjectionReview.objects.create(projection=p,verdict=verdict,policy=policy,authority=auth,actor=a);event(a,c,'agent.data.projection_reviewed',review=r.pk);bump(c);return r

def context(a,p):
 source_access(a,p);auth=authority(a,p.case,'sender');policy,v=projection_policy(p)
 r=ProjectionReview.objects.select_related('actor').filter(projection=p).order_by('-pk').first()
 if not r or r.verdict!='confirm' or r.policy_id!=policy.pk or r.authority!=authority(r.actor,p.case,'reviewer') or (timezone.now()-r.created_at).total_seconds()>v['review_ttl_seconds']:raise ValidationError('Current reviewed egress projection required')
 finance_review(r.actor,p,[a.pk,p.actor_id])
 if p.evidence.kind=='agent_private_ledger':decision_authority(a,p.case,'Finance')
 s=IntegrationSelection.objects.select_related('contract__case').filter(case=p.case,family='provider').order_by('-version').first()
 if not s or s.contract_id!=v['contract_id']:raise ValidationError('Exact selected provider required')
 g=readiness.gate(p.case,'provider');b,_=binding(s.contract)
 return {'policy':policy.pk,'projection_review':r.pk,'projection_sha256':p.sha256,'authority':auth,'provider_gate':g,'binding':b,'contract':s.contract_id,'max_output_chars':v['max_output_chars'],'max_attempts':v['max_attempts'],'lease_seconds':v['lease_seconds']}

@transaction.atomic
def reserve(a,case_id,pk,key,expected=None):
 c=locked(a,case_id,'agent.data.send',expected);p=projection_for(c,pk);source_access(a,p);validate(KEY,key)
 old=Job.objects.filter(projection=p,intent_key=key).first()
 if old:
  if old.actor_id!=a.pk:raise PermissionDenied('Original intent owner required')
  return old
 intent=context(a,p);_,v=rules(c)
 if Job.objects.filter(projection__case=c,intent__policy=intent['policy']).count()>=v['max_requests']:raise ValidationError('Configured case policy request budget exhausted')
 j=Job.objects.create(projection=p,intent_key=key,operation_key=digest({'case':str(c.pk),'projection':p.pk,'key':key}),intent=intent,actor=a);event(a,c,'agent.data.reserved',job=j.pk);bump(c);return j

def output(p,value,limit):
 if not isinstance(value,dict) or set(value)!={'facts','uncertainties','proposed_actions'} or value['proposed_actions']!=[]:raise ValidationError('Tools/actions are forbidden')
 if not isinstance(value['facts'],list) or len(value['facts'])>8 or not isinstance(value['uncertainties'],list) or len(value['uncertainties'])>16 or any(not isinstance(u,str) or len(u)>2000 for u in value['uncertainties']):raise ValidationError('Malformed bounded output')
 text='\n'.join(p.payload['quotes'])
 for f in value['facts']:
  if not isinstance(f,dict) or set(f)!={'quote'} or not isinstance(f['quote'],str) or not f['quote'] or not any(f['quote'] in q for q in p.payload['quotes']):raise ValidationError('Exact projected source citation required')
 if len(json.dumps(value,ensure_ascii=False))>limit:raise ValidationError('Configured output budget exceeded')
 # Citation provenance is supplied by trusted services, never by model identifiers.
 return dict(value,provenance={'projection':p.pk,'sha256':p.sha256,'evidence':p.evidence_id,'source_sha256':p.evidence.sha256,'source_version':p.evidence.version})

@transaction.atomic
def review_result(a,case_id,receipt_id,verdict,corrected=None,expected=None):
 c=locked(a,case_id,'agent.data.review',expected);r=Receipt.objects.select_related('job__projection__case','job__projection__evidence','job__actor').filter(job__projection__case=c,pk=receipt_id).first()
 if not r:raise ValidationError('Exact case private result required')
 source_access(a,r.job.projection)
 finance_review(a,r.job.projection,[r.job.actor_id,r.job.projection.actor_id])
 auth=authority(a,c,'reviewer');_,v=rules(c)
 if v['independent_review'] and a.pk in [r.job.actor_id,r.job.projection.actor_id]:raise PermissionDenied('Independent result reviewer required')
 if verdict not in ['confirm','correct','return','withdraw']:raise ValidationError('Typed result disposition required')
 value={}
 if verdict in ['confirm','correct']:
  if context(r.job.actor,r.job.projection)!=r.job.intent:raise ValidationError('Current source/provider/policy context required')
  if verdict=='confirm':
   if corrected is not None or not r.valid:raise ValidationError('Only valid unchanged output may be confirmed')
   value=r.result
  else:value=output(r.job.projection,corrected,r.job.intent['max_output_chars'])
 elif corrected is not None:raise ValidationError('Corrections require the correct disposition')
 rr=Review.objects.create(receipt=r,verdict=verdict,result=value,authority=auth,actor=a);event(a,c,'agent.data.result_reviewed',review=rr.pk);bump(c);return rr

@transaction.atomic
def inspect(a,case_id,pk):
 c=locked(a,case_id,'agent.data.read');r=Receipt.objects.select_related('job__projection__case','job__projection__evidence').filter(job__projection__case=c,pk=pk).first()
 if not r:raise ValidationError('Exact case result required')
 source_access(a,r.job.projection)
 rr=Review.objects.select_related('actor').filter(receipt=r).order_by('-pk').first();accepted=False
 if rr and rr.verdict in ['confirm','correct']:
  try:
   accepted=context(r.job.actor,r.job.projection)==r.job.intent and rr.authority==authority(rr.actor,c,'reviewer')
   if r.job.projection.evidence.kind=='agent_private_ledger':
    from apps.finance.ledger_agents import rules as native_rules
    finance_review(rr.actor,r.job.projection,[r.job.actor_id,r.job.projection.actor_id])
    accepted=accepted and (timezone.now()-rr.created_at).total_seconds()<=native_rules(c)[1]['review_ttl_seconds']
  except (PermissionDenied,ValidationError):accepted=False
 history=[{'id':x.pk,'verdict':x.verdict,'actor':x.actor_id,'recorded_at':x.created_at.isoformat(),'result_sha256':digest(x.result)} for x in Review.objects.filter(receipt=r).order_by('-pk')[:20]]
 return {'receipt':r.pk,'valid':r.valid,'unreviewed_result':r.result,'review':rr.pk if rr else None,'reviewed_result':rr.result if rr else None,'review_history':history,'currently_accepted':accepted,'business_effects_authorized':False,'real_model_evaluated':False}

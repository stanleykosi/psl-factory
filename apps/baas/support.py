"""B14 configured support flow, supplied channel references and current human decisions."""
from django.db import transaction,connection
from django.core.exceptions import ValidationError,PermissionDenied
from django.contrib.auth import get_user_model
from django.utils import timezone
from apps.core.models import Case
from apps.core.services import lock_case,event,bump
from apps.identity.services import require
from apps.identity.models import Grant
from apps.pmo.services import subject
from apps.pmo.meetings import scoped_person
from apps.documents.contracts import digest,validate
from apps.policy.services import active_component,reference_values,decision_authority,resolve
from apps.policy.support_validators import INTAKE,FLOW,AUTH,METRICS,SCHEMAS
from adapters.support import SuppliedSupportChannelAdapter
from adapters.hrfinance import timestamp
from adapters.forecast import obj,KEY
from .models import SupportCase,SupportIntake,SupportLink,SupportEvent,SupportResult,SupportReport,SupportReview,SupportMerge
ID={'type':'integer','minimum':1}
RESULT=obj({'status':{'enum':['resolved','not_resolved','unknown']},'kind':{'enum':['backend_reference','financial_corrective']},'reference':KEY,'corrective_request_id':{'anyOf':[ID,{'type':'null'}]},'verification_id':{'anyOf':[ID,{'type':'null'}]}})
def readable(a,c):
 if not get_user_model().objects.filter(pk=a.pk,is_active=True).exists():raise PermissionDenied('Active principal required')
 for action in ['case.read','support.read']:require(a,c,action)
def locked(a,case_id,action,expected=None):
 c=lock_case(a,case_id,action,expected);list(Grant.objects.select_for_update().filter(case=c).order_by('pk'));readable(a,c)
 if c.kind!='support':raise ValidationError('Select a support case')
 return c
def config(c,k):
 p=active_component(k,c);return p,reference_values(p)[0]
def head(c):return SupportEvent.objects.filter(case=c).order_by('-version').first()
def identity(p):return {k:p[k] for k in ['customer_ref','transaction_ref','issue_ref','case_type']}
def linked_current(c):
 _,rules=config(c,INTAKE)
 for link in SupportLink.objects.filter(case=c).select_related('intake'):
  if link.intake.channel not in rules['channels'] or link.intake.payload['case_type'] not in rules['case_types']:raise ValidationError('Current source channel/type policy does not authorise this linked intake')
def canonical(c):
 link=SupportLink.objects.filter(case=c).order_by('pk').first()
 if not link:raise ValidationError('Explicit canonical intake link required')
 return identity(link.intake.payload)
def meaning(flow,state):
 m=next((x['meaning'] for x in flow['states'] if x['key']==state),None)
 if not m:raise ValidationError('Current state is absent from flow; reviewed migration required')
 return m
def authority(a,c,purpose,preparers=()):
 readable(a,c);require(a,c,'support.review' if purpose in ['flow','summary'] else 'support.'+('transition' if purpose=='transition' else purpose));p,v=config(c,AUTH)
 row=next((r for r in v['assignments'] if r['user_id']==a.pk and purpose in r['purposes']),None)
 if not row or (purpose in ['flow','summary'] and v['independent_review'] and a.pk in preparers):raise PermissionDenied('Configured actual independent purpose authority required')
 return {AUTH:p.pk,'role':row['role'],**decision_authority(a,c,row['role'])}
def flow_snapshot(c):
 p,v=config(c,FLOW);a,_=config(c,AUTH);pins={FLOW:p.pk,AUTH:a.pk};subject(c,v['specification_evidence_id'])
 if v['validation_mode']=='af13_required':
  from apps.documents import validation as av
  package=av.package_for(c,v['validation_package_id'])
  if 'B14' not in package.payload['process_ids'] or not any(s.evidence_id==v['specification_evidence_id'] for s in __import__('apps.documents.validation_models',fromlist=['DiscoverySource']).DiscoverySource.objects.filter(case=c,pk__in=package.payload['source_ids'])):raise ValidationError('AF13 package must bind exact B14 flow specification evidence')
  pins['AF13']={k:av.approved_review(package,k).pk for k in ['meaning','expectations','acceptance']}
  if not c.synthetic and package.payload['level']!='operational':raise ValidationError('Operational support requires native owner acceptance; definition or synthetic evidence is insufficient')
  if not c.synthetic:
   sop=active_component('D09.support_sop_ref',c);pins['D09.support_sop_ref']=sop.pk
   if 'B14' not in reference_values(sop)[0]['process_ids']:raise ValidationError('Exact owner-reviewed B14 SOP required')
 elif not c.synthetic:raise ValidationError('Local reviewed-definition flow is synthetic only; operational SOP/native validation remains required')
 return pins
@transaction.atomic
def review_flow(a,case_id,evidence_id,verdict='approve',expected=None):
 c=locked(a,case_id,'support.review',expected);p,_=config(c,FLOW);pins=flow_snapshot(c);auth=authority(a,c,'flow',[p.created_by_id,subject(c,reference_values(p)[0]['specification_evidence_id']).created_by_id])
 if verdict not in ['approve','reject','withdraw']:raise ValidationError('Explicit flow verdict required')
 r=SupportReview.objects.create(case=c,purpose='flow',verdict=verdict,snapshot=pins,authority=auth,evidence=subject(c,evidence_id,'support_review'),actor=a);event(a,c,'support.flow_review',review=r.pk,verdict=verdict);bump(c);return r
def approved_flow(c):
 pins=flow_snapshot(c);r=SupportReview.objects.filter(case=c,purpose='flow').order_by('-pk').first();p,_=config(c,FLOW)
 if not r or r.verdict!='approve' or r.snapshot!=pins or r.authority!=authority(r.actor,c,'flow',[p.created_by_id,subject(c,reference_values(p)[0]['specification_evidence_id']).created_by_id]):raise ValidationError('Exact current Support flow review required')
 return r
@transaction.atomic
def capture(a,case_id,evidence_id,expected=None):
 c=locked(a,case_id,'support.capture',expected);e=subject(c,evidence_id);p=SuppliedSupportChannelAdapter().read(e)
 if timestamp(p['received_at'])>timezone.now():raise ValidationError('Receipt cannot be future-dated')
 key=digest({'tenant':c.tenant,'channel':p['channel'],'message_ref':p['message_ref']})
 with connection.cursor() as cur:cur.execute('SELECT pg_advisory_xact_lock(%s)',[int(key[:15],16)])
 old=SupportIntake.objects.filter(tenant=c.tenant,channel=p['channel'],message_ref=p['message_ref']).first()
 if old:
  if old.case_id!=c.pk or old.sha256!=digest(p):raise ValidationError('Channel identity is already claimed or changed; retain evidence and investigate without merging')
  return old
 r=SupportIntake.objects.create(case=c,tenant=c.tenant,channel=p['channel'],message_ref=p['message_ref'],payload=p,sha256=digest(p),evidence=e,actor=a);event(a,c,'support.intake',intake=r.pk,native_verified=False);bump(c);return r
@transaction.atomic
def link(a,case_id,intake_id,evidence_id,expected=None):
 c=locked(a,case_id,'support.triage',expected);authority(a,c,'triage');_,v=config(c,INTAKE);i=SupportIntake.objects.filter(case=c,pk=intake_id).first()
 if not i or i.channel not in v['channels'] or i.payload['case_type'] not in v['case_types']:raise ValidationError('Configured case channel/type required')
 if SupportMerge.objects.filter(source=c).exists():raise ValidationError('Merged cases retain history; link new work to canonical target')
 first=SupportLink.objects.filter(case=c).order_by('pk').first()
 if first and (identity(first.intake.payload)!=identity(i.payload) or i.payload['transaction_ref'] is None):raise ValidationError('Do not silently combine distinct or unknown transactions/issues')
 old=SupportLink.objects.filter(intake=i).first()
 if old:return old
 r=SupportLink.objects.create(case=c,intake=i,evidence=subject(c,evidence_id,'support_triage'),actor=a);event(a,c,'support.link',link=r.pk,intake=i.pk);bump(c);return r
def owner(c,pk):
 a=scoped_person(c,pk,'support.own')
 if a is None:raise ValidationError('An actual accountable next-action owner is required')
 readable(a,c);return a
def now_at(value,prior=None):
 at=timestamp(value)
 if at>timezone.now() or (prior and at<prior.occurred_at):raise ValidationError('Event times must be ordered and not future-dated')
 return at
def save_event(a,c,action,state,person,e,at,payload):
 last=head(c);r=SupportEvent.objects.create(case=c,version=last.version+1 if last else 1,action=action,state=state,owner=person,actor=a,evidence=e,occurred_at=at,snapshot={'flow_review':approved_flow(c).pk,**flow_snapshot(c)},payload=payload)
 s=SupportCase.objects.get(case=c);_,v=config(c,FLOW);m=meaning(v,state);s.status='resolved' if m in ['resolved','cancelled','merged'] else 'open'
 if m=='resolved':s.resolution=e;s.resolved_at=at
 elif m not in ['cancelled','merged']:s.resolved_at=None
 if action=='respond' and payload.get('response_kind')=='human':s.first_response_at=s.first_response_at or at
 s.save();event(a,c,'support.flow_event',event=r.pk,state=state,transition=action,owner=person.pk);bump(c);return r
@transaction.atomic
def start(a,case_id,owner_id,evidence_id,occurred_at,expected=None):
 c=locked(a,case_id,'support.transition',expected);authority(a,c,'transition');approved_flow(c);_,v=config(c,FLOW);canonical(c);linked_current(c)
 if head(c):raise ValidationError('Case flow already started')
 e=subject(c,evidence_id);legacy=SupportCase.objects.filter(case=c).first();state=v['initial'];payload={'legacy_adopted':False}
 if legacy:
  if v['migration_mode']!='reviewed_legacy_adoption' or e.kind!='support_migration':raise ValidationError('Existing support projection requires explicit reviewed legacy migration')
  state=v['legacy_state_map'][legacy.status];payload={'legacy_adopted':True,'legacy_status':legacy.status,'legacy_first_response_at':legacy.first_response_at.isoformat() if legacy.first_response_at else None,'legacy_resolved_at':legacy.resolved_at.isoformat() if legacy.resolved_at else None,'legacy_resolution_id':legacy.resolution_id}
 else:
  if e.kind!='support_start':raise ValidationError('Explicit support-start evidence required')
  SupportCase.objects.create(case=c,channel='controlled:'+str(c.pk),external_ref=str(c.pk))
 at=now_at(occurred_at)
 if at<min(timestamp(x.intake.payload['received_at']) for x in SupportLink.objects.filter(case=c).select_related('intake')):raise ValidationError('Case cannot start before receipt')
 return save_event(a,c,'adopt' if legacy else 'start',state,owner(c,owner_id),e,at,payload)
def current_result(result):
 c=result.pending.case
 if SupportResult.objects.filter(pending=result.pending).order_by('-pk').first().pk!=result.pk:raise ValidationError('Specialist result superseded; current resolution must be reconsidered')
 auth=authority(result.actor,c,'specialist')
 if auth!=result.authority or result.payload['status']!='resolved':raise ValidationError('Current resolved specialist result required')
 if result.payload['kind']=='financial_corrective':
  from .models import OutcomeVerification,EngineeringOutcome
  from . import corrective
  v=OutcomeVerification.objects.filter(pk=result.payload['verification_id'],delivery__request__case=c,delivery__request_id=result.payload['corrective_request_id']).first()
  if not v or v.outcome.payload['status']!='applied':raise ValidationError('Exact successful Engineering-mediated corrective verification required')
  r=v.delivery.request;corrective.approved(r);require(v.actor,c,'baas.corrective.verify_outcome')
  _,_,command=corrective.config(r);valid=False
  for role in command['verifier_roles']:
   try:valid|=corrective.authority(v.actor,r,role,'verifier_roles')==v.authority
   except PermissionDenied:pass
  if not valid or not get_user_model().objects.filter(pk=v.actor_id,is_active=True).exists():raise ValidationError('Corrective verification authority changed')
  require(v.outcome.actor,c,'baas.engineering.record');require(v.outcome.actor,c,'baas.engineering.receive')
  if decision_authority(v.outcome.actor,c,'Engineering')!=v.outcome.authority:raise ValidationError('Engineering outcome authority changed')
  if r.payload['customer']!=canonical(c)['customer_ref']:raise ValidationError('Corrective customer mismatch')
  if EngineeringOutcome.objects.filter(delivery=v.delivery).order_by('-pk').first().pk!=v.outcome_id:raise ValidationError('Corrective outcome was superseded')
 return result
@transaction.atomic
def specialist_result(a,case_id,pending_id,evidence_id,expected=None):
 c=locked(a,case_id,'support.specialist',expected);auth=authority(a,c,'specialist');p=SupportEvent.objects.filter(case=c,pk=pending_id,action='await_specialist').first()
 if not p or head(c).version<p.version:raise ValidationError('Exact specialist-pending event required')
 e=subject(c,evidence_id,'support_specialist_result')
 v=SuppliedSupportChannelAdapter().read_result(e,RESULT)
 if v['kind']!=p.payload.get('specialist_kind'):raise ValidationError('Specialist result type differs from the exact configured wait')
 if v['kind']=='financial_corrective':
  from .models import CorrectiveRequest
  r=CorrectiveRequest.objects.filter(case=c,pk=v['corrective_request_id']).first()
  if not r or r.payload.get('kind') not in ['corrective_credit','fund_movement'] or r.payload.get('transaction')!=canonical(c)['transaction_ref']:raise ValidationError('Exact case transaction corrective request required')
 result=SupportResult.objects.create(pending=p,actor=a,evidence=e,payload=v,authority=auth)
 if v['status']=='resolved':current_result(result)
 event(a,c,'support.specialist_result',result=result.pk,status=v['status'],financial_execution_authorized=False);bump(c);return result
@transaction.atomic
def transition(a,case_id,action,owner_id,evidence_id,occurred_at,expected=None,response_kind='human',verified_receipt=None):
 c=locked(a,case_id,'support.transition',expected);auth=authority(a,c,'transition');approved_flow(c);linked_current(c);last=head(c);_,v=config(c,FLOW)
 if not last or SupportMerge.objects.filter(source=c).exists():raise ValidationError('Current unmerged support flow required')
 e=subject(c,evidence_id);at=now_at(occurred_at,last);person=owner(c,owner_id);payload={'authority':auth};clock_pins=None
 if action=='respond':
  if last.snapshot!={'flow_review':approved_flow(c).pk,**flow_snapshot(c)}:raise ValidationError('Flow changed; explicit migration required')
  if response_kind not in ['human','bot_ack'] or meaning(v,last.state) in ['resolved','cancelled','merged'] or e.kind!='support_response':raise ValidationError('Response evidence and active case required')
  from . import support_channel as channel
  if response_kind=='human' and (channel.enrolled(c) or verified_receipt is not None):
   if verified_receipt is None:raise ValidationError('Enrolled human response clock requires exact independently reviewed customer receipt')
   clock_pins=channel.clock_context(a,c,verified_receipt)
   if at!=timestamp(clock_pins['time']):raise ValidationError('Clock must use exact verified customer delivery timestamp')
   payload['clock_basis']='reviewed_channel_delivery'
  elif verified_receipt is not None:raise ValidationError('Only human response can attest customer delivery clock')
  payload['response_kind']=response_kind;state=last.state
 elif action=='adopt_flow':
  if e.kind!='support_migration' or v['migration_mode']!='reviewed_legacy_adoption':raise ValidationError('Configured explicit flow migration required')
  state=last.state if any(x['key']==last.state for x in v['states']) else v['legacy_state_map'][SupportCase.objects.get(case=c).status];payload['previous_flow_snapshot']=last.snapshot
 else:
  if last.snapshot!={'flow_review':approved_flow(c).pk,**flow_snapshot(c)}:raise ValidationError('Flow version changed; explicit reviewed adoption required')
  edge=next((x for x in v['edges'] if x['from']==last.state and x['action']==action),None)
  if not edge or e.kind!=edge['evidence_kind']:raise ValidationError('Configured transition and exact evidence kind required')
  state=edge['to']
  if action=='await_specialist':payload['specialist_kind']=edge['specialist_kind']
  pending=SupportEvent.objects.filter(case=c,action='await_specialist').order_by('-version').first()
  reopened=SupportEvent.objects.filter(case=c,action='reopen').order_by('-version').first()
  if edge['require_specialist_result'] or (meaning(v,state)=='resolved' and pending and (not reopened or pending.version>reopened.version)):
   if not pending:raise ValidationError('Specialist pending event required')
   result=SupportResult.objects.filter(pending=pending).order_by('-pk').first()
   if not result:raise ValidationError('Specialist result is missing; no silent closure')
   current_result(result)
   if at<result.created_at:raise ValidationError('Resolution cannot precede its specialist-result record')
   payload['specialist_result_id']=result.pk
 row=save_event(a,c,action,state,person,e,at,payload)
 if clock_pins:channel.record_clock(a,c,row,clock_pins)
 return row
@transaction.atomic
def merge(a,source_id,target_id,evidence_id,occurred_at,expected=None):
 if str(source_id)==str(target_id):raise ValidationError('Distinct source and canonical case required')
 cases={}
 for pk in sorted([source_id,target_id],key=str):cases[str(pk)]=locked(a,pk,'support.merge',expected if str(pk)==str(source_id) else None)
 c,t=cases[str(source_id)],cases[str(target_id)]
 if c.tenant!=t.tenant or c.synthetic!=t.synthetic:raise ValidationError('Same tenant and evidence scope required')
 auth={str(z.pk):authority(a,z,'merge') for z in [c,t]}
 for z in [c,t]:
  approved_flow(z);linked_current(z)
  h=head(z)
  if not h or h.snapshot!={'flow_review':approved_flow(z).pk,**flow_snapshot(z)}:raise ValidationError('Both merge participants need current reviewed flow adoption')
 if SupportMerge.objects.filter(source__in=[c,t]).exists() or SupportMerge.objects.filter(target=c).exists():raise ValidationError('Merge chains/cycles require explicit investigation; preserve all histories')
 if canonical(c)!=canonical(t) or canonical(c)['transaction_ref'] is None:raise ValidationError('Unrelated or unknown transaction/issues cannot merge')
 _,flow=config(c,FLOW);_,other=config(t,FLOW);last=head(c);target=head(t)
 if not flow['merge_enabled'] or not other['merge_enabled'] or not last or not target or last.state not in flow['merge_source_states'] or target.state not in other['merge_target_states'] or meaning(other,target.state) in ['resolved','cancelled','merged']:raise ValidationError('Configured merge and active canonical target required')
 e=subject(c,evidence_id,'support_merge');at=now_at(occurred_at,max([last,target],key=lambda e:e.occurred_at));person=owner(c,last.owner_id)
 r=SupportMerge.objects.create(source=c,target=t,actor=a,evidence=e,snapshot={'source_event':last.pk,'target_event':target.pk,'authority':auth})
 state=next(s['key'] for s in flow['states'] if s['meaning']=='merged');save_event(a,c,'merge',state,person,e,at,{'target_case_id':str(t.pk),'merge_id':r.pk});event(a,t,'support.merged_reference',source_case=str(c.pk),merge=r.pk);bump(t);return r
def snapshot(c):
 from .support_channel import enrolled
 from .support_clock_corrections import projection
 approved=approved_flow(c);last=head(c)
 _,intake_rules=config(c,INTAKE)
 for link in SupportLink.objects.filter(case=c).select_related('intake'):
  if link.intake.channel not in intake_rules['channels'] or link.intake.payload['case_type'] not in intake_rules['case_types']:raise ValidationError('Linked intake no longer matches configured source/type scope')
 if not last:raise ValidationError('Started case required')
 if last.snapshot!={'flow_review':approved.pk,**flow_snapshot(c)}:raise ValidationError('Current flow needs explicit reviewed adoption')
 owner(c,last.owner_id);readable(last.actor,c);require(last.actor,c,'support.transition' if last.action!='merge' else 'support.merge')
 result_ids=[]
 _,flow=config(c,FLOW)
 if meaning(flow,last.state)=='resolved':
  resolution=SupportEvent.objects.filter(case=c,action='resolve').order_by('-version').first()
  reopened=SupportEvent.objects.filter(case=c,action='reopen').order_by('-version').first()
  if resolution and (not reopened or resolution.version>reopened.version) and resolution.payload.get('specialist_result_id'):
   r=SupportResult.objects.get(pk=resolution.payload['specialist_result_id']);current_result(r);result_ids.append(r.pk)
 return {'flow_review':approved.pk,'head':last.pk,'intake_policy':config(c,INTAKE)[0].pk,'links':list(SupportLink.objects.filter(case=c).values_list('pk',flat=True)),'intakes':list(SupportIntake.objects.filter(case=c).values_list('pk',flat=True)),'metric_readiness':resolve(METRICS,c).status,'metric_policy':resolve(METRICS,c).configuration.pk if resolve(METRICS,c).status=='ACTIVE' else None,'specialist_results':result_ids,'merges':list(SupportMerge.objects.filter(target=c).values_list('pk',flat=True)),**({'channel_clock_metric_state':metrics(c),**({'channel_clock_correction_state':projection(c)} if projection(c) else {})} if enrolled(c) else {})}
def metrics(c):
 from .support_metrics import elapsed
 state=resolve(METRICS,c)
 if state.status!='ACTIVE':return {'first_response_seconds':None,'resolution_seconds':None,'finding':'metric_policy_'+state.status.lower()}
 _,rule=config(c,METRICS);links=list(SupportLink.objects.filter(case=c).select_related('intake'));events=list(SupportEvent.objects.filter(case=c).order_by('version'));_,flow=config(c,FLOW)
 receipt=min((x.intake.payload['received_at'] for x in links),key=timestamp,default=None);reopen=next((x.occurred_at.isoformat() for x in reversed(events) if x.action=='reopen'),None)
 response_event=next((x for x in events if x.action=='respond' and (x.payload['response_kind']=='human' or rule['bot_acknowledgement_qualifies']) and (not reopen or rule['reopen_basis']!='since_latest_reopen' or x.occurred_at>=timestamp(reopen))),None)
 from .support_channel import metric_time
 from .support_clock_corrections import projection
 correction=projection(c)
 response_time=metric_time(c,response_event) if response_event else None
 if correction:
  if correction['finding']:return {'first_response_seconds':None,'resolution_seconds':None,'finding':correction['finding']}
  response_time=timestamp(correction['time'])
  if reopen and rule['reopen_basis']=='since_latest_reopen' and response_time<timestamp(reopen):response_time=None
 elif response_event and response_time is None:return {'first_response_seconds':None,'resolution_seconds':None,'finding':'customer_clock_evidence_not_current'}
 response=response_time.isoformat() if response_time else None
 resolved=head(c);resolution=resolved.occurred_at.isoformat() if meaning(flow,resolved.state)=='resolved' else None
 if any(x.action=='adopt' for x in events):return {'first_response_seconds':None,'resolution_seconds':None,'finding':'legacy_event_coverage_incomplete'}
 return elapsed(receipt,response,resolution,reopen,rule)
@transaction.atomic
def prepare_report(a,case_id,evidence_id,expected=None):
 from .support_clock_corrections import coverage_end
 c=locked(a,case_id,'support.report',expected);pins=snapshot(c);last=head(c);_,flow=config(c,FLOW);links=list(SupportLink.objects.filter(case=c).select_related('intake'))
 result={'case_id':str(c.pk),'state':last.state,'meaning':meaning(flow,last.state),'owner_id':last.owner_id,'reopened':SupportEvent.objects.filter(case=c,action='reopen').exists(),'sources':[{'intake_id':x.intake_id,'channel':x.intake.channel,'message_ref':x.intake.message_ref,'evidence_id':x.intake.evidence_id} for x in links],'unlinked_intake_count':SupportIntake.objects.filter(case=c).exclude(supportlink__isnull=False).count(),'metrics':metrics(c),'coverage':'one selected canonical case and its linked supplied references; no exhaustive channel claim','period_start':min((x.intake.payload['received_at'] for x in links),key=timestamp),'period_end':coverage_end(c,last.occurred_at).isoformat(),'native_channel_verified':False,'financial_execution_authorized':False}
 r=SupportReport.objects.create(case=c,actor=a,snapshot=pins,result=result,evidence=subject(c,evidence_id,'support_report'));event(a,c,'support.report_prepared',report=r.pk);bump(c);return r
@transaction.atomic
def review_report(a,case_id,report_id,evidence_id,verdict='approve',expected=None):
 c=locked(a,case_id,'support.review',expected);r=SupportReport.objects.filter(case=c,pk=report_id).first()
 if not r or verdict not in ['approve','reject','withdraw']:raise ValidationError('Exact case report and explicit verdict required')
 auth=authority(a,c,'summary',[r.actor_id]);pins=snapshot(c)
 if verdict=='approve' and pins!=r.snapshot:raise ValidationError('Report context changed; prepare a successor')
 d=SupportReview.objects.create(case=c,purpose='summary',report=r,verdict=verdict,snapshot=pins,authority=auth,evidence=subject(c,evidence_id,'support_review'),actor=a);event(a,c,'support.report_review',review=d.pk,report=r.pk);bump(c);return d
@transaction.atomic
def read_report(a,case_id,report_id):
 c=locked(a,case_id,'support.read');r=SupportReport.objects.filter(case=c,pk=report_id).first()
 if not r or r.snapshot!=snapshot(c):raise ValidationError('Exact current support report required')
 readable(r.actor,c);require(r.actor,c,'support.report');d=r.reviews.order_by('-pk').first()
 if not d or d.verdict!='approve' or d.snapshot!=r.snapshot or d.authority!=authority(d.actor,c,'summary',[r.actor_id]):raise ValidationError('Current actual Support summary review required')
 return {'report_id':r.pk,'review_id':d.pk,'result':r.result,'report_sha256':digest(r.result)}

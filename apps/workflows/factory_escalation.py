"""P44 communication coordination. Native decisions and issue truth remain separate."""
import hashlib,json
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied,ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from apps.core.models import Audit
from apps.core.services import lock_case,add_evidence,event
from apps.core.read_observation import read_observation
from apps.identity.services import require
from apps.identity.models import Grant
from apps.documents.contracts import digest,validate
from apps.documents.models import Template,Publication,PublicationJob,PublicationReceipt
from apps.documents.controlled import current_version,validate_review,publication_requirements
from apps.pmo import escalations as native
from apps.pmo.models import EscalationRequest,EscalationDocumentBinding
from .models import FactoryWork as Work,FactoryActivity as Activity,FactoryAttempt as Attempt,HumanTask
from .factory_delivery import investigation_key
from .factory_handover import pending_job

DEFINITION='pmo-escalation/v1'
KIND='agent_private_escalation_intake'
PROTOCOL='factory-escalation-intake/v1'
ID={'anyOf':[{'type':'integer','minimum':1},{'type':'null'}]}
SCHEMA={'type':'object','properties':{'protocol':{'const':PROTOCOL},'request_id':{'type':'integer','minimum':1},'profile_id':{'type':'integer','minimum':1},'template_id':ID},'required':['protocol','request_id','profile_id','template_id'],'additionalProperties':False}

def finding(exc):return '; '.join(exc.messages) if isinstance(exc,ValidationError) else str(exc)

def inputs(case,request_id,template_id,current=True):
    if type(request_id) is not int or template_id is not None and type(template_id) is not int:raise ValidationError('Exact integer native selections required')
    r=EscalationRequest.objects.select_related('profile__state__issue').filter(pk=request_id,profile__state__issue__case=case).first()
    if not r:raise ValidationError('Choose this case exact native escalation request')
    if current:native.current_request(case,r.pk)
    if template_id and not Template.objects.filter(pk=template_id,case=case,definition__document_type__in=['status_report','project_artifact']).exists():raise ValidationError('Choose this case controlled communication template')
    return r,{'protocol':PROTOCOL,'request_id':r.pk,'profile_id':r.profile_id,'template_id':template_id}

def source(work,actor=None,current=True):
    require(actor or work.actor,work.case,'issue.read');e=work.source_head
    if not e or e.case_id!=work.case_id or e.kind!=KIND or e.sha256!=hashlib.sha256(e.body.encode()).hexdigest():raise ValidationError('Exact escalation source required')
    try:data=json.loads(e.body)
    except (TypeError,ValueError):raise ValidationError('Typed native escalation intake required') from None
    validate(SCHEMA,data)
    audit=Audit.objects.filter(case=work.case,actor_id=e.created_by_id,action__in=['factory.escalation_intake','factory.escalation_source'],data={'evidence_id':e.pk,'sha256':e.sha256}).first()
    r,exact=inputs(work.case,data['request_id'],data['template_id'],current)
    if not audit or data!=exact or [r.profile.state.issue_id,r.direction,r.target]!=[work.request['issue'],work.request['direction'],work.request['target']]:raise ValidationError('Exact issue, direction, destination and source provenance required')
    if current:
        for action in ['case.read','issue.read','evidence.add','factory.start' if audit.action=='factory.escalation_intake' else 'factory.manage']:require(e.created_by,work.case,action)
    return r,data

def capture(actor,case,data,action):
    e=add_evidence(actor,case.pk,KIND,json.dumps(data,sort_keys=True),'psl:'+PROTOCOL)
    event(actor,case,action,evidence_id=e.pk,sha256=e.sha256);return e

@transaction.atomic
def start(actor,case_id,key,request_id,template_id,reference,expected=None):
    from .factory import access
    c=lock_case(actor,case_id,'factory.start',expected);access(actor,c,'factory.start',DEFINITION);require(actor,c,'evidence.add')
    if not isinstance(key,str) or not key.isascii() or not 1<=len(key)<=100 or not isinstance(reference,str) or not reference.strip() or len(reference)>160:raise ValidationError('Bounded work key and communication reference required')
    r,data=inputs(c,request_id,template_id)
    payload={'issue':r.profile.state.issue_id,'direction':r.direction,'target':r.target,'reference':reference}
    business=digest([str(c.pk),DEFINITION,r.profile.state.issue_id,r.direction,r.target]);sha=digest(payload)
    old=Work.objects.filter(case=c).filter(Q(key=key)|Q(definition=DEFINITION,business_key=business)).first()
    if old:
        if old.actor_id!=actor.pk or old.definition!=DEFINITION or old.request_hash!=sha or source(old,actor)[1]!=data:raise ValidationError('IDEMPOTENCY_CONFLICT: correct the existing escalation work')
        return old
    w=Work.objects.create(case=c,actor=actor,key=key,definition=DEFINITION,request=payload,request_hash=sha,business_key=business,source_head=capture(actor,c,data,'factory.escalation_intake'))
    event(actor,c,'factory.started',work=w.pk,definition=DEFINITION);return w

def document(work):
    pk=Attempt.objects.filter(activity__work=work,phase='observed',result__head=work.source_head_id,result__has_key='document_version').order_by('-pk').values_list('result__document_version',flat=True).first()
    b=EscalationDocumentBinding.objects.select_related('version__document','version__template').filter(version_id=pk,request__profile__state__issue_id=work.request['issue']).first()
    return b.version if b else None

def principal(work,value,name):
    u=get_user_model().objects.filter(pk=value[name],is_active=True).first()
    if not u:raise ValidationError('owner_needed: Configure current escalation '+name.replace('_id',''))
    actions=['case.read','issue.read','factory.execute']+(['issue.escalate','document.draft'] if name=='preparer_id' else ['document.publish'])
    try:
        for action in actions:require(u,work.case,action)
    except PermissionDenied:raise ValidationError('owner_needed: Escalation principal lacks current project permissions') from None
    return u

def published(work,actor=None):
    from .factory import profile
    r,data=source(work,actor);decision=native.approved_request(work.case,r);v=document(work)
    if not v:raise ValidationError('Await exact controlled communication')
    b=EscalationDocumentBinding.objects.get(version=v)
    if b.request_id!=r.pk or b.decision_id!=(decision.pk if decision else None) or v.template_id!=data['template_id'] or v.audience!=('client' if r.target=='Client' else 'internal'):raise ValidationError('Exact current request, decision, template and audience required')
    current_version(work.case,v.pk);review=validate_review(work.case,v);policies,recipients,retention=publication_requirements(work.case,v)
    config,value=profile(work,recovery=True);principal(work,value,'preparer_id');user=principal(work,value,'executor_id')
    p=Publication.objects.filter(version=v,factory_work=work,factory_source=work.source_head,factory_policy=config,actor=user).first()
    if not p or p.review_id!=(review.pk if review else None) or p.policies!=policies or p.recipient_ids!=recipients or p.retention_days!=retention:raise ValidationError('Await current work-bound exact communication publication')
    receipts=list(PublicationReceipt.objects.filter(publication=p).order_by('pk'))
    if not PublicationJob.objects.filter(publication=p,status='confirmed').exists() or not receipts or len(receipts)!=len(recipients) or {x.recipient_id for x in receipts}!=set(recipients) or any(x.payload!=v.payload or x.payload_sha256!=v.payload_sha256 for x in receipts):raise ValidationError('Every exact recipient receipt and confirmed communication outcome is required')
    return r,decision,v,p,receipts

def verify(work,actor=None):
    r,d,v,p,receipts=published(work,actor)
    return {'verified':True,'verification_scope':'reviewed_escalation_communication','head':work.source_head_id,'request':r.pk,'profile':r.profile_id,'issue_state':r.profile.state_id,'decision':d.pk if d else None,'direction':r.direction,'target':r.target,'document_version':v.pk,'publication':p.pk,'receipt_ids':[x.pk for x in receipts],'issue_resolution_verified':False}

def report(work,actor=None):
    r,data=source(work,actor);clock=native.timing(r.profile)
    # Observation equality includes threshold changes, not the passage of microseconds.
    for key in ['as_of','elapsed_hours']:clock.pop(key,None)
    n={'request':r.pk,'profile':r.profile_id,'issue_state':r.profile.state_id,'timing':clock,'stage':'decision','finding':'','issue_resolution_verified':False}
    try:
        d=native.approved_request(work.case,r);n.update(decision=d.pk if d else None,stage='communication')
        published(work,actor);n['stage']='complete'
    except (ValidationError,PermissionDenied) as exc:n['finding']=finding(exc)
    return n

@read_observation
def snapshot(work,value,reader=None):
    from .factory import access
    actor=reader or work.execution_actor;access(actor,work.case,'factory.read' if reader is not None else 'factory.execute',DEFINITION)
    r,data=source(work,actor);n=report(work,actor);latest={KIND:work.source_head}
    for e in [r.profile.state.evidence,r.profile.evidence,r.evidence]:latest[e.kind]=e
    missing=[k for k in value['required_evidence_kinds'] if k not in latest]
    stale=[k for k in value['required_evidence_kinds'] if k in latest and latest[k].created_at<timezone.now()-timedelta(seconds=value['max_age_seconds'])]
    jobs=list(PublicationJob.objects.filter(publication__factory_work=work).order_by('pk'));v=document(work);review={'status':'unprepared'}
    if v:
        try:current_version(work.case,v.pk);d=validate_review(work.case,v);review={'status':'ready','id':d.pk if d else None}
        except (ValidationError,PermissionDenied) as exc:review={'status':'held','finding':finding(exc)}
    state={'case_revision':work.case.revision,'profile':work.policy_id,'sources':[(e.pk,e.sha256) for e in latest.values()],'native':n,'checks':{'request':r.pk,'decisions':list(r.decisions.values_list('pk',flat=True))},'document':v.pk if v else None,'review':review,'publication':Publication.objects.filter(version=v,factory_work=work).values_list('pk',flat=True).first() if v else None,'jobs':[(j.pk,j.status) for j in jobs]}
    state['hash']=digest(state);state['work_revision']=work.revision
    return state,latest,missing,stale,[],jobs

def eligible(work,value,state,latest,missing,stale,tasks,jobs):
    job=pending_job(jobs)
    if job:return ['ACT11' if job.status=='pending' else 'ACT12'],'Deliver or reconcile the original communication'
    if any(j.status in ['held','leased'] for j in jobs):return [],'Resolve the original communication delivery before continuing'
    if not Activity.objects.filter(work=work,key=investigation_key(work,state),status='succeeded').exists():return ['ACT04'],'Investigate the exact blocker, immediate impact and native approval needs'
    if missing or stale:return [],'Current configured intake evidence required: '+', '.join(missing+stale)
    if state['native']['stage']=='decision':return [],state['native']['finding']
    if state['native']['stage']=='complete':return ['ACT13'],'Verify the reviewed communication and every recipient receipt, not issue resolution'
    if not state['document']:return ['ACT09'],'Prepare the controlled native communication'
    if state['review']['status']!='ready' and not HumanTask.objects.filter(version_id=state['document']).exists():return ['ACT09'],'Request native review of the retained exact communication'
    if state['review']['status']!='ready':return [],'Await exact document review or explicit source-owned replacement'
    if not state['publication']:return ['ACT11'],'Reserve the reviewed communication for configured recipients'
    return [],state['native']['finding']

def act(work,choice,value,latest,missing,tasks,jobs):
    from .factory import access
    c=lock_case(work.execution_actor,work.case_id,'factory.execute');access(work.execution_actor,c,'factory.execute',DEFINITION)
    list(Grant.objects.select_for_update().filter(case=c).order_by('pk'))
    if c.revision!=work.case.revision:raise ValidationError('STALE_VERSION: escalation sources changed')
    r,data=source(work,work.execution_actor);kind=choice['activity']
    if kind=='ACT04':
        from apps.agents.escalations import investigate_escalations
        run=investigate_escalations(work.execution_actor,c.pk,c.revision,profile_ids=[r.profile_id])
        return {'head':work.source_head_id,'investigation_run':run.pk,'investigation':run.result,'native':report(work,work.execution_actor),'approval_granted':False,'communications_dispatched':False}
    if kind=='ACT09':
        from apps.documents.controlled import request_review
        native.approved_request(c,r);u=principal(work,value,'preparer_id');v=document(work)
        if not data['template_id']:raise ValidationError('Select the controlled communication template')
        if not v:v=native.draft_escalation(u,c.pk,r.pk,data['template_id'],c.revision)
        task=None
        if not (v.audience!='client' and v.template.definition.get('internal_review_required') is False) and not HumanTask.objects.filter(version=v).exists():
            require(u,c,'document.request_review');c.refresh_from_db();task=request_review(u,c.pk,v.pk,c.revision)
        return {'head':work.source_head_id,'request':r.pk,'document_version':v.pk,'native_review_task':task.pk if task else None}
    if kind in ['ACT11','ACT12']:
        job=pending_job(jobs)
        if job:return {'head':work.source_head_id,'publication_job':job.pk,'publication_lookup_only':kind=='ACT12'}
        if kind=='ACT12':raise ValidationError('No original uncertain communication exists')
        from apps.documents.controlled import reserve_publication
        u=principal(work,value,'executor_id');v=document(work)
        if not v:raise ValidationError('Exact observed communication required')
        p=reserve_publication(u,c.pk,v.pk,c.revision,factory_work_id=work.pk)
        return {'head':work.source_head_id,'publication':p.pk}
    if kind=='ACT13':result=verify(work,work.execution_actor);work.status='verified';return result
    raise ValidationError('Native request, client decision and document review remain human commands')

def publication_scope(actor,case,version,work_id):
    from .factory import access,profile
    w=Work.objects.select_related('case','actor','source_head').get(pk=work_id,case=case,definition=DEFINITION)
    access(actor,case,'factory.execute',DEFINITION);config,value=profile(w)
    if w.policy_id!=config.pk or principal(w,value,'executor_id').pk!=actor.pk:raise PermissionDenied('Exact current communication publisher and policy required')
    principal(w,value,'preparer_id')
    if w.cancel_requested or w.status in ['verified','cancelled','followup_needed']:raise ValidationError('Escalation publication is stopped')
    r,data=source(w);decision=native.approved_request(case,r)
    b=EscalationDocumentBinding.objects.filter(version=version,request=r,decision=decision).first()
    if not b or document(w)!=version or version.template_id!=data['template_id']:raise ValidationError('Exact observed current escalation document required')
    return {'factory_work_id':w.pk,'factory_policy_id':config.pk,'factory_source_id':w.source_head_id}

def settled(w):
    from apps.agents.factory_coordinator import pending,has_receipt
    if w.lease_until and w.lease_until>timezone.now() or PublicationJob.objects.filter(publication__factory_work=w,status__in=['pending','unknown','leased','held']).exists():raise ValidationError('Resolve original effects before changing this communication')
    planning=pending(w)
    if planning and not has_receipt(planning):raise ValidationError('Resolve original planning response first')

@transaction.atomic
def correct(actor,work_id,expected,case_expected,request_id,template_id,reason):
    from .factory import access
    w=Work.objects.select_for_update(of=('self',)).select_related('case','actor','source_head').get(pk=work_id,definition=DEFINITION)
    access(actor,w.case,'factory.manage',DEFINITION);c=lock_case(actor,w.case_id,'evidence.add',case_expected);w.case=c
    if type(expected) is not int or w.revision!=expected or w.cancel_requested or w.status in ['cancelled','followup_needed']:raise ValidationError('Refresh active escalation work')
    settled(w)
    if not isinstance(reason,str) or not reason.strip() or len(reason)>2000:raise ValidationError('Explain the explicit source-owned correction')
    old,data=source(w,actor,False);r,new=inputs(c,request_id,template_id)
    if [r.profile.state.issue_id,r.direction,r.target]!=[old.profile.state.issue_id,old.direction,old.target]:raise ValidationError('Successor must retain this exact issue, direction and destination')
    if new==data:
        v=document(w)
        if not v:raise ValidationError('Select a current successor request or changed template')
        cancelled=PublicationJob.objects.filter(publication__version=v,publication__factory_work=w,status='cancelled').exists() and not PublicationReceipt.objects.filter(publication__version=v).exists()
        if not cancelled:
            try:current_version(c,v.pk);validate_review(c,v)
            except (ValidationError,PermissionDenied):
                # A pending human review is not permission to reset the work.
                if HumanTask.objects.filter(version=v,status='open').exists() and not native.binding_findings(EscalationDocumentBinding.objects.get(version=v)):raise ValidationError('Current native review is pending; preserve that wait')
            else:
                try:published(w,actor)
                except (ValidationError,PermissionDenied):
                    if not Publication.objects.filter(version=v,factory_work=w).exists():raise ValidationError('Current reviewed communication awaits publication, not replacement')
                else:raise ValidationError('Current communication remains verified; select a genuine successor')
    before=w.source_head_id;w.source_head=capture(actor,c,new,'factory.escalation_source');w.status='ready';w.finding='';w.revision+=1;w.save()
    event(actor,c,'factory.escalation_corrected',work=w.pk,previous=before,current=w.source_head_id,reason=reason,spent=w.budget_used);return w

@transaction.atomic
def decide(actor,work_id,expected,case_expected,request_id,role,verdict,note,delegated=False):
    from .factory import access
    w=Work.objects.select_for_update(of=('self',)).select_related('case','source_head','actor').get(pk=work_id,definition=DEFINITION)
    access(actor,w.case,'factory.read',DEFINITION);r,_=source(w,actor);settled(w)
    if type(expected) is not int or w.revision!=expected or w.cancel_requested or r.pk!=request_id or w.status=='verified':raise ValidationError('Choose exact current native client decision wait')
    return native.decide_escalation(actor,w.case_id,r.pk,role,verdict,note,case_expected,delegated)

@transaction.atomic
def review(actor,work_id,expected,case_expected,version_id,verdict,note):
    from .factory import access
    from apps.documents.controlled import review_version
    w=Work.objects.select_for_update(of=('self',)).select_related('case','source_head','actor').get(pk=work_id,definition=DEFINITION)
    access(actor,w.case,'factory.read',DEFINITION);source(w,actor);v=document(w);settled(w)
    if type(expected) is not int or w.revision!=expected or w.cancel_requested or not v or v.pk!=version_id:raise ValidationError('Review exact current native communication')
    return review_version(actor,w.case_id,v.pk,verdict,note,case_expected)

def projection(actor,work):
    from .factory import profile
    from apps.policy.services import decision_authority
    r,data=source(work,actor,False);v=document(work);issue='';options=[];next_action='Review current escalation source';n={};changed=False
    try:
        _,value=profile(work,recovery=True);state,*args=snapshot(work,value,reader=actor);n=state['native'];options,next_action=eligible(work,value,state,*args)
        if work.status=='verified':verify(work,actor);next_action='Inspect the communication receipts. Issue resolution is tracked separately.'
    except (ValidationError,PermissionDenied) as exc:issue=finding(exc);next_action=issue;changed=work.status=='verified'
    owners=[];roles=[];verdicts=[]
    live=not work.cancel_requested and work.status not in ['verified','cancelled','followup_needed'] and not (work.lease_until and work.lease_until>timezone.now())
    if live and n.get('stage')=='decision':
        for user in get_user_model().objects.filter(is_active=True,grant__case=work.case,grant__action='issue.escalation_decide',grant__active=True).distinct():
            for role in ['PMO Lead','Head of PMO']:
                try:decision_authority(user,work.case,role,'approve')
                except (ValidationError,PermissionDenied):continue
                owners.append(user.get_full_name() or user.username)
                if user.pk==actor.pk:roles.append(role)
    if live and v and HumanTask.objects.filter(version=v,status='open').exists():
        try:
            current_version(work.case,v.pk);require(actor,work.case,'document.review_controlled')
            for verdict in ['approve','return','reject']:
                try:decision_authority(actor,work.case,'PMO Lead',verdict);verdicts.append(verdict)
                except (ValidationError,PermissionDenied):pass
        except (ValidationError,PermissionDenied):pass
    jobs=list(PublicationJob.objects.filter(publication__factory_work=work).order_by('pk'))
    for job in jobs:
        job.can_operate=False;job.can_retry=False
        try:
            require(actor,work.case,'document.operate')
            job.can_operate=not (work.lease_until and work.lease_until>timezone.now()) and job.status in ['pending','held'] and not PublicationReceipt.objects.filter(publication=job.publication).exists()
            job.can_retry=job.can_operate and job.status=='held' and not work.cancel_requested
        except PermissionDenied:pass
    heads={work.source_head_id}
    for change in Audit.objects.filter(case=work.case,action='factory.escalation_corrected',data__work=work.pk):heads.update([change.data['previous'],change.data['current']])
    from apps.core.models import Evidence
    requests=[]
    for head in Evidence.objects.filter(case=work.case,kind=KIND,pk__in=heads).order_by('pk'):
        requests.append(json.loads(head.body)['request_id'])
    from apps.pmo.models import EscalationDecision
    return {'request':r,'data':data,'native':n,'document':v,'jobs':jobs,'receipts':list(PublicationReceipt.objects.filter(publication__factory_work=work).order_by('pk')),'decision_history':list(EscalationDecision.objects.filter(request_id__in=requests).order_by('pk')),'finding':issue,'readiness_changed':changed,'next_options':options,'next_action':next_action,'owner_names':sorted(set(owners)),'decision_roles':roles,'review_verdicts':verdicts}

def reconcile(actor,work_id,expected,adapter=None):
    from .factory import access,cancellation_status
    from apps.documents.delivery import run_publication_once
    with transaction.atomic():
        w=Work.objects.select_for_update(of=('self',)).select_related('case').get(pk=work_id,definition=DEFINITION)
        access(actor,w.case,'factory.execute',DEFINITION)
        if actor.pk!=w.actor_id:require(actor,w.case,'factory.manage')
        if type(expected) is not int or w.revision!=expected or w.lease_until and w.lease_until>timezone.now():raise ValidationError('STALE_VERSION: refresh original escalation delivery')
        job=PublicationJob.objects.filter(publication__factory_work=w).filter(Q(status='unknown')|Q(status='leased',lease_until__lte=timezone.now())).order_by('pk').first()
        if not job:raise ValidationError('No original uncertain escalation delivery needs reconciliation')
        event(actor,w.case,'factory.reconciliation_requested',work=w.pk,publication_job=job.pk)
    run_publication_once(adapter,case_id=w.case_id,job_id=job.pk,lookup_only=True)
    with transaction.atomic():
        w=Work.objects.select_for_update().get(pk=work_id);job.refresh_from_db()
        w.status=cancellation_status(w) if w.cancel_requested else 'waiting_effect' if job.status=='unknown' else 'blocked' if job.status=='held' else 'ready'
        w.finding=job.error if job.status in ['held','unknown'] else '';w.observation_hash='';w.revision+=1;w.save()
    return w

@transaction.atomic
def operate(actor,work_id,expected,case_expected,job_id,action,reason):
    from .factory import access,cancellation_status
    from apps.documents.delivery import operate_publication
    w=Work.objects.select_for_update(of=('self',)).select_related('case').get(pk=work_id,definition=DEFINITION)
    access(actor,w.case,'factory.read',DEFINITION);require(actor,w.case,'document.operate')
    if any(type(pk) is not int or pk<1 for pk in [expected,case_expected,job_id]) or w.revision!=expected:raise ValidationError('STALE_VERSION: refresh exact escalation and project versions')
    if w.lease_until and w.lease_until>timezone.now():raise ValidationError('Wait for the current worker before operating delivery')
    if not PublicationJob.objects.filter(pk=job_id,publication__factory_work=w).exists():raise ValidationError('Choose this work original delivery')
    if action not in ['cancel','retry'] or not isinstance(reason,str):raise ValidationError('Choose a native recovery action and explain it')
    if PublicationJob.objects.filter(pk=job_id).exclude(status__in=['pending','held']).exists():raise ValidationError('Uncertain original communication requires receipt-only reconciliation; cancellation cannot authorise a replacement')
    operate_publication(actor,w.case_id,job_id,action,reason,case_expected)
    w.status=cancellation_status(w) if w.cancel_requested else 'ready' if action=='retry' else 'blocked'
    w.finding='' if action=='retry' else 'Delivery cancelled. Review a current source package before another publication.'
    w.observation_hash='';w.revision+=1;w.save();return w

@transaction.atomic
def cancel(actor,work_id,expected):
    from .factory import access,manage,cancellation_status
    if type(expected) is not int or expected<1:raise ValidationError('Exact rendered work version required')
    w=Work.objects.select_for_update(of=('self',)).select_related('case').get(pk=work_id,definition=DEFINITION)
    access(actor,w.case,'factory.manage',DEFINITION)
    if w.revision!=expected:raise ValidationError('STALE_VERSION: refresh current escalation work')
    if w.status in ['verified','followup_needed']:raise ValidationError('Delivered or accepted work requires native follow-up')
    if w.status=='cancelled':return w
    if not w.cancel_requested:w=manage(actor,w.pk,w.revision,'cancel')
    if w.lease_until and w.lease_until>timezone.now():return w
    w.status=cancellation_status(w);w.finding='Stopping work cannot undo an already delivered document or recorded communication evidence.'
    w.lease_until=None;w.revision+=1;w.save();return w




"""Separate P61/P62 native evidence flow. No deployment or ordinary change closure."""
import hashlib,json
from copy import deepcopy
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied,ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from apps.core.models import Evidence,Audit
from apps.core.services import lock_case,add_evidence,event
from apps.core.evidence_access import public_evidence
from apps.core.read_observation import read_observation
from apps.identity.services import require
from apps.identity.models import Grant
from apps.documents.contracts import digest,validate
from apps.documents.models import Template,Publication,PublicationJob,PublicationReceipt
from apps.documents.controlled import current_version,validate_review,publication_requirements
from apps.pmo import emergencies as native
from apps.pmo.emergency_documents import draft_retrospective,binding_findings
from apps.pmo.models import EmergencyProfile,EmergencyAuthorization,EmergencyOutcome,EmergencyRetrospectiveRecord,EmergencyDocumentBinding
from adapters.emergencies import LocalEmergencyEvidenceAdapter
from .models import FactoryWork as Work,FactoryActivity as Activity,FactoryAttempt as Attempt,HumanTask
from .factory_delivery import investigation_key
from .factory_handover import pending_job

DEFINITION='pmo-emergency/v1'
KIND='agent_private_emergency_intake'
PROTOCOL='factory-emergency-intake/v1'
ID={'anyOf':[{'type':'integer','minimum':1,'maximum':9223372036854775807},{'type':'null'}]}
INPUT={'type':'object','properties':{'template_id':ID,'authorization_id':ID,'outcome_id':ID,'audience':{'enum':['internal','client']}},'required':['template_id','authorization_id','outcome_id','audience'],'additionalProperties':False}
SCHEMA={'type':'object','properties':{'protocol':{'const':PROTOCOL},'profile_id':{'type':'integer','minimum':1},'inputs':INPUT},'required':['protocol','profile_id','inputs'],'additionalProperties':False}

def finding(exc):return '; '.join(exc.messages) if isinstance(exc,ValidationError) else str(exc)

def input_rows(case,profile,inputs):
    validate(INPUT,inputs)
    if any(inputs[k] is not None and type(inputs[k]) is not int for k in ['template_id','authorization_id','outcome_id']):raise ValidationError('Exact integer native references required')
    if inputs['template_id'] and not Template.objects.filter(case=case,pk=inputs['template_id'],definition__document_type__in=['status_report','project_artifact']).exists():raise ValidationError('Choose this project controlled retrospective template')
    if inputs['authorization_id'] and not EmergencyAuthorization.objects.filter(pk=inputs['authorization_id'],profile=profile).exists():raise ValidationError('Choose preauthorization for this exact Emergency profile')
    if inputs['outcome_id']:
        outcome=EmergencyOutcome.objects.filter(pk=inputs['outcome_id'],profile=profile).first()
        if not outcome or outcome.authorization_id!=inputs['authorization_id']:raise ValidationError('Actual outcome and recorded preauthorization must match this exact profile; no retrospective substitution')

def source(work,actor=None,current=True):
    require(actor or work.actor,work.case,'emergency.read');e=work.source_head
    if not e or e.case_id!=work.case_id or e.kind!=KIND or e.sha256!=hashlib.sha256(e.body.encode()).hexdigest():raise ValidationError('Exact Emergency intake required')
    try:data=json.loads(e.body)
    except (TypeError,ValueError):raise ValidationError('Typed native Emergency intake required') from None
    validate(SCHEMA,data)
    audit=Audit.objects.filter(case=work.case,actor_id=e.created_by_id,action__in=['factory.emergency_intake','factory.emergency_source'],data={'evidence_id':e.pk,'sha256':e.sha256}).first()
    p=native.profile_for(work.case,data['profile_id'],current=False)
    if not audit or p.version.change_id!=work.request['change'] or p.version.category!='Emergency' or not p.version.incident_id:raise ValidationError('Exact incident-linked Emergency provenance required')
    input_rows(work.case,p,data['inputs'])
    if current:
        for action in ['case.read','emergency.read','evidence.add','factory.start' if audit.action=='factory.emergency_intake' else 'factory.manage']:require(e.created_by,work.case,action)
        if data['inputs']['outcome_id']:
            # Native historical retrospective validation preserves actual outcomes across baseline adoption.
            if p.version.change.current_id!=p.version_id or p.version.emergency_profiles.order_by('-pk').first().pk!=p.pk:raise ValidationError('Emergency change revision/profile changed; preserve the original outcome history')
        else:native.profile_for(work.case,p.pk)
    return p,data

def capture(actor,case,profile,inputs,action):
    e=add_evidence(actor,case.pk,KIND,json.dumps({'protocol':PROTOCOL,'profile_id':profile.pk,'inputs':inputs},sort_keys=True),'psl:'+PROTOCOL)
    event(actor,case,action,evidence_id=e.pk,sha256=e.sha256);return e

@transaction.atomic
def start(actor,case_id,key,profile_id,inputs,reference,expected=None):
    from .factory import access
    case=lock_case(actor,case_id,'factory.start',expected);access(actor,case,'factory.start',DEFINITION);require(actor,case,'evidence.add')
    if case.kind!='project' or type(profile_id) is not int or profile_id<1 or not isinstance(key,str) or not key.isascii() or not 1<=len(key)<=100 or not isinstance(reference,str) or not reference.strip() or len(reference)>160:raise ValidationError('Project, exact profile and bounded work identity required')
    p=native.profile_for(case,profile_id,current=not bool(inputs.get('outcome_id')));input_rows(case,p,inputs)
    if p.version.category!='Emergency' or not p.version.incident_id:raise ValidationError('Select an actual incident-linked Emergency profile')
    payload={'change':p.version.change_id,'reference':reference};sha=digest(payload);business=digest([str(case.pk),DEFINITION,p.version.change_id])
    old=Work.objects.filter(case=case).filter(Q(key=key)|Q(definition=DEFINITION,business_key=business)).first()
    if old:
        if old.actor_id!=actor.pk or old.definition!=DEFINITION or old.key==key and old.request_hash!=sha:raise ValidationError('IDEMPOTENCY_CONFLICT: changed Emergency work intent')
        op,data=source(old,actor)
        if op.pk!=p.pk or data['inputs']!=inputs:raise ValidationError('Review changed sources in the existing Emergency work')
        return old
    w=Work.objects.create(case=case,actor=actor,key=key,definition=DEFINITION,request=payload,request_hash=sha,business_key=business,source_head=capture(actor,case,p,inputs,'factory.emergency_intake'))
    event(actor,case,'factory.started',work=w.pk,definition=DEFINITION);return w

def outcome(work,data):
    if not data['inputs']['outcome_id']:raise ValidationError('Await actual implementation evidence and explicit outcome selection; the factory cannot deploy or infer implementation')
    return native.outcome_for(work.case,data['inputs']['outcome_id'])

def stable_retrospective(snapshot):
    result=deepcopy(snapshot);result.get('timing',{}).pop('retrospective_overdue',None)
    # Explicit native authority recovery can preserve the original historical record.
    result.pop('authority_recovery_id',None);return result

def completed(work,data):
    actual=outcome(work,data);current=native.retrospective_inputs(work.case,actual)
    record=EmergencyRetrospectiveRecord.objects.filter(outcome=actual).first()
    if not record:raise ValidationError('Await native human reconciliation of the actual review-bound retrospective')
    if stable_retrospective(record.snapshot)!=stable_retrospective(current):raise ValidationError('Native retrospective source, decisions or timing changed; use source-owned recovery without rewriting history')
    return actual,record,current

def document(work):
    pk=Attempt.objects.filter(activity__work=work,phase='observed',result__head=work.source_head_id,result__has_key='document_version').order_by('-pk').values_list('result__document_version',flat=True).first()
    b=EmergencyDocumentBinding.objects.select_related('version__document','version__template').filter(version_id=pk,outcome__profile__version__change_id=work.request['change']).first()
    return b.version if b else None

def principal(work,value,name):
    u=get_user_model().objects.filter(pk=value[name],is_active=True).first()
    if not u:raise ValidationError('owner_needed: Configure current Emergency '+name.replace('_id',''))
    try:
        for action in ['case.read','emergency.read','factory.execute']+(['emergency.manage','document.draft','document.request_review'] if name=='preparer_id' else ['document.publish']):require(u,work.case,action)
    except PermissionDenied:raise ValidationError('owner_needed: Emergency principal lacks current project permissions') from None
    return u

def published(work,actor=None):
    from .factory import profile
    _,data=source(work,actor);actual,record,current=completed(work,data);v=document(work)
    if not v:raise ValidationError('Await exact controlled retrospective report')
    b=EmergencyDocumentBinding.objects.get(version=v)
    if b.outcome_id!=actual.pk or v.audience!=data['inputs']['audience'] or v.template_id!=data['inputs']['template_id']:raise ValidationError('Exact outcome, template and explicit report audience required')
    current_version(work.case,v.pk);review=validate_review(work.case,v);policies,recipients,retention=publication_requirements(work.case,v)
    config,value=profile(work,recovery=True);principal(work,value,'preparer_id');user=principal(work,value,'executor_id')
    p=Publication.objects.filter(version=v,factory_work=work,factory_source=work.source_head,factory_policy=config,actor=user).first()
    if not p or p.policies!=policies or p.recipient_ids!=recipients or p.retention_days!=retention or p.review_id!=review.pk:raise ValidationError('Await current exact retrospective publication')
    receipts=list(PublicationReceipt.objects.filter(publication=p).order_by('pk'))
    if not receipts or {x.recipient_id for x in receipts}!=set(recipients) or any(x.payload!=v.payload or x.payload_sha256!=v.payload_sha256 for x in receipts):raise ValidationError('Every exact retrospective recipient receipt is required')
    return actual,record,current,v,p,receipts

def report(work,actor=None):
    p,data=source(work,actor);auth=EmergencyAuthorization.objects.filter(pk=data['inputs']['authorization_id'],profile=p).first()
    result={'profile':p.pk,'change_version':p.version_id,'critical_production':p.critical_production,'p1':p.p1,'authorization':auth.pk if auth else None,'outcome':data['inputs']['outcome_id'],'stage':'preauthorization','finding':'','deployment_dispatched':False,'ordinary_change_closed':False}
    if not data['inputs']['outcome_id']:
        try:
            expected=native.preauthorization_inputs(work.case,p)
            if not auth:raise ValidationError('Await actual native preauthorization and explicit selection; no deployment is dispatched')
            require(auth.actor,work.case,'emergency.authorize')
            if auth.snapshot!=expected:raise ValidationError('Selected preauthorization source or authority changed')
            result['stage']='implementation';result['finding']='Record actual past implementation evidence, then explicitly select that native outcome'
        except (ValidationError,PermissionDenied) as exc:result['finding']=finding(exc)
        return result
    actual=outcome(work,data);result.update(stage='retrospective',implemented_at=actual.implemented_at.isoformat(),logged_at=actual.created_at.isoformat(),authorization_preceded_implementation=bool(actual.authorization_id and actual.authorization.created_at<=actual.implemented_at),timing=native.timing(work.case,actual))
    evidence=LocalEmergencyEvidenceAdapter().read(work.case,actual);result['manifest']=evidence['manifest'];result['source_evidence_ids']=evidence['source_evidence_ids']
    try:
        _,record,current=completed(work,data);result.update(stage='report',retrospective_record=record.pk,retrospective_status=record.snapshot['status'],authority_recovery_id=current.get('authority_recovery_id'))
        published(work,actor);result['stage']='complete'
    except (ValidationError,PermissionDenied) as exc:result['finding']=finding(exc)
    return result

@read_observation
def snapshot(work,value,reader=None):
    from .factory import access
    actor=reader or work.execution_actor;access(actor,work.case,'factory.read' if reader is not None else 'factory.execute',DEFINITION)
    p,data=source(work,actor);native_state=report(work,actor)
    ids={p.evidence_id,p.version.evidence_id,p.version.incident_id}|set(p.decisions.values_list('evidence_id',flat=True))|set(native_state.get('source_evidence_ids',[]))
    latest={KIND:work.source_head}
    for e in public_evidence(Evidence.objects.filter(case=work.case,pk__in=ids)).order_by('pk'):
        if e.kind not in latest or latest[e.kind].version<e.version:latest[e.kind]=e
    missing=[k for k in value['required_evidence_kinds'] if k not in latest]
    stale=[k for k in value['required_evidence_kinds'] if k in latest and latest[k].created_at<timezone.now()-timedelta(seconds=value['max_age_seconds'])]
    jobs=list(PublicationJob.objects.filter(publication__factory_work=work).order_by('pk'));v=document(work);review={'status':'unprepared'}
    if v:
        try:current_version(work.case,v.pk);r=validate_review(work.case,v);review={'status':'ready','id':r.pk}
        except (ValidationError,PermissionDenied) as exc:review={'status':'held','finding':finding(exc)}
    state={'case_revision':work.case.revision,'profile':work.policy_id,'sources':[(e.pk,e.sha256) for e in latest.values()],'native':native_state,'checks':{'stage':native_state['stage']},'document':v.pk if v else None,'review':review,'publication':Publication.objects.filter(version=v).values_list('pk',flat=True).first() if v else None,'jobs':[(j.pk,j.status) for j in jobs]}
    state['hash']=digest(state);state['work_revision']=work.revision
    return state,latest,missing,stale,[],jobs

def eligible(work,value,state,latest,missing,stale,tasks,jobs):
    job=pending_job(jobs)
    if job:return ['ACT11' if job.status=='pending' else 'ACT12'],'Deliver or reconcile the original retrospective report'
    if any(j.status in ['held','leased'] for j in jobs):return [],'Resolve the original retrospective delivery before continuing'
    if not Activity.objects.filter(work=work,key=investigation_key(work,state),status='succeeded').exists():return ['ACT04'],'Investigate exact incident, preauthorization, implementation truth and retrospective obligations'
    if missing or stale:return [],'Required current Emergency evidence is missing or stale: '+', '.join(missing+stale)
    if state['native']['stage']=='complete':return ['ACT13'],'Verify native retrospective status and exact report receipts'
    if state['native']['stage']!='report':return [],state['native']['finding']
    if not state['document']:return ['ACT09'],'Prepare the controlled completed-retrospective report'
    if not HumanTask.objects.filter(version_id=state['document']).exists():return ['ACT09'],'Request native review of the retained report'
    if state['review']['status']!='ready':return [],'Await exact outward review or source-owned report rework'
    if not state['publication']:return ['ACT11'],'Reserve the reviewed retrospective report'
    return [],state['native']['finding']

def act(work,choice,value,latest,missing,tasks,jobs):
    from .factory import access
    case=lock_case(work.execution_actor,work.case_id,'factory.execute');access(work.execution_actor,case,'factory.execute',DEFINITION)
    list(Grant.objects.select_for_update().filter(case=case).order_by('pk'))
    if case.revision!=work.case.revision:raise ValidationError('STALE_VERSION: Emergency sources changed')
    _,data=source(work,work.execution_actor);kind=choice['activity']
    if kind=='ACT04':return {'head':work.source_head_id,'native':report(work,work.execution_actor),'source_refs':sorted(e.pk for e in latest.values()),'approval_granted':False,'deployment_dispatched':False}
    if kind=='ACT09':
        from apps.documents.controlled import request_review
        actual,_,_=completed(work,data);u=principal(work,value,'preparer_id');v=document(work)
        if not data['inputs']['template_id']:raise ValidationError('Select the controlled retrospective template')
        if not v:v=draft_retrospective(u,case.pk,actual.pk,data['inputs']['template_id'],data['inputs']['audience'],case.revision)
        task=None;waiting=None
        if not HumanTask.objects.filter(version=v).exists():
            try:current_version(case,v.pk)
            except (ValidationError,PermissionDenied):waiting='Draft retained; complete current source and recipient requirements before review'
            else:case.refresh_from_db();task=request_review(u,case.pk,v.pk,case.revision)
        result={'head':work.source_head_id,'outcome':actual.pk,'document_version':v.pk,'native_review_task':task.pk if task else None}
        if waiting:result['waiting']=waiting
        return result
    if kind in ['ACT11','ACT12']:
        job=pending_job(jobs)
        if job:return {'head':work.source_head_id,'publication_job':job.pk}
        if kind=='ACT12':raise ValidationError('No original uncertain retrospective delivery exists')
        from apps.documents.controlled import reserve_publication
        u=principal(work,value,'executor_id');v=document(work)
        if not v:raise ValidationError('Exact observed retrospective report required')
        p=reserve_publication(u,case.pk,v.pk,case.revision,factory_work_id=work.pk)
        return {'head':work.source_head_id,'publication':p.pk}
    if kind=='ACT13':result=verify(work,work.execution_actor);work.status='verified';return result
    raise ValidationError('Preauthorization, implementation attestation, review and retrospective decisions remain native human commands')

def publication_scope(actor,case,version,work_id):
    from .factory import access,profile
    w=Work.objects.select_related('case','actor','source_head').get(pk=work_id,case=case,definition=DEFINITION)
    access(actor,case,'factory.execute',DEFINITION);config,value=profile(w)
    if w.policy_id!=config.pk or principal(w,value,'executor_id').pk!=actor.pk:raise PermissionDenied('Exact current retrospective publisher and policy required')
    principal(w,value,'preparer_id')
    if w.cancel_requested or w.status in ['verified','cancelled','followup_needed']:raise ValidationError('Emergency publication is stopped')
    _,data=source(w);actual,_,_=completed(w,data);b=EmergencyDocumentBinding.objects.filter(version=version,outcome=actual).first()
    if not b or document(w)!=version or version.template_id!=data['inputs']['template_id'] or version.audience!=data['inputs']['audience']:raise ValidationError('Exact observed source-bound retrospective report required')
    findings=binding_findings(b)
    if findings:raise ValidationError(findings)
    return {'factory_work_id':w.pk,'factory_policy_id':config.pk,'factory_source_id':w.source_head_id}

def verify(work,actor=None):
    actual,record,current,v,p,receipts=published(work,actor)
    return {'verified':True,'verification_scope':'native_emergency_retrospective_and_controlled_report_receipts','head':work.source_head_id,'outcome':actual.pk,'retrospective_record':record.pk,'retrospective_status':record.snapshot['status'],'authorization_preceded_implementation':bool(actual.authorization_id and actual.authorization.created_at<=actual.implemented_at),'authority_recovery_id':current.get('authority_recovery_id'),'document_version':v.pk,'receipt_ids':[r.pk for r in receipts],'deployment_dispatched':False,'ordinary_change_closed':False,'external_authenticity_verified':False}

@transaction.atomic
def correct(actor,work_id,expected,case_expected,profile_id,inputs,reason):
    from .factory import access
    from apps.agents.factory_coordinator import pending,has_receipt
    w=Work.objects.select_for_update(of=('self',)).select_related('case','actor','source_head').get(pk=work_id,definition=DEFINITION)
    access(actor,w.case,'factory.manage',DEFINITION);case=lock_case(actor,w.case_id,'evidence.add',case_expected);w.case=case
    if type(expected) is not int or w.revision!=expected or w.cancel_requested or w.status in ['cancelled','followup_needed']:raise ValidationError('STALE_VERSION: refresh current Emergency work')
    if w.lease_until and w.lease_until>timezone.now() or PublicationJob.objects.filter(publication__factory_work=w,status__in=['pending','unknown','leased','held']).exists():raise ValidationError('Resolve original effects before source correction')
    planning=pending(w)
    if planning and not has_receipt(planning):raise ValidationError('Resolve original planning response before correction')
    if not isinstance(reason,str) or not reason.strip() or len(reason)>2000:raise ValidationError('Explain the source-owned correction')
    old,data=source(w,actor,False);p=native.profile_for(case,profile_id,current=not bool(inputs.get('outcome_id')))
    if p.version.change_id!=old.version.change_id:raise ValidationError('Choose a profile from this exact Emergency change')
    input_rows(case,p,inputs)
    if p.pk==old.pk and data['inputs']==inputs:
        v=document(w)
        if not v:raise ValidationError('Provide changed native source selections')
        cancelled=PublicationJob.objects.filter(publication__version=v,publication__factory_work=w,status='cancelled').exists() and not PublicationReceipt.objects.filter(publication__version=v).exists()
        if not cancelled:
            try:current_version(case,v.pk);validate_review(case,v);published(w,actor)
            except (ValidationError,PermissionDenied):pass
            else:raise ValidationError('Current report and publication remain valid; provide a genuine source correction')
    head=w.source_head_id;w.source_head=capture(actor,case,p,inputs,'factory.emergency_source');w.status='ready';w.finding='';w.revision+=1;w.save()
    event(actor,case,'factory.emergency_corrected',work=w.pk,previous=head,current=w.source_head_id,reason=reason,spent=w.budget_used);return w

@transaction.atomic
def review(actor,work_id,expected,case_expected,version_id,verdict,note):
    from .factory import access
    from apps.documents.controlled import review_version
    w=Work.objects.select_for_update(of=('self',)).select_related('case','source_head','actor').get(pk=work_id,definition=DEFINITION)
    access(actor,w.case,'factory.read',DEFINITION);source(w,actor);v=document(w)
    if type(expected) is not int or w.revision!=expected or w.cancel_requested or w.lease_until and w.lease_until>timezone.now() or not v or v.pk!=version_id:raise ValidationError('STALE_VERSION: select exact current retrospective report')
    return review_version(actor,w.case_id,version_id,verdict,note,case_expected)

@transaction.atomic
def human_action(actor,work_id,expected,case_expected,profile_id,action,values):
    """Explicit native human actions; not registered for agent dispatch."""
    from .factory import access
    w=Work.objects.select_for_update(of=('self',)).select_related('case','source_head','actor').get(pk=work_id,definition=DEFINITION)
    access(actor,w.case,'factory.read',DEFINITION);p,data=source(w,actor)
    if type(expected) is not int or w.revision!=expected or p.pk!=profile_id or w.cancel_requested or w.lease_until and w.lease_until>timezone.now():raise ValidationError('STALE_VERSION: refresh exact Emergency work')
    if action=='preauthorization_decision':result=native.decide_emergency(actor,w.case_id,p.pk,values['role'],values['authority_role'],values['verdict'],values['evidence'],values['note'],case_expected)
    elif action=='authorize':result=native.authorize_emergency(actor,w.case_id,p.pk,case_expected)
    elif action=='capture_outcome':result=native.capture_outcome(actor,w.case_id,p.pk,data['inputs']['authorization_id'],values['implemented_at'],values['evidence'],values['note'],case_expected)
    elif action=='record_review':result=native.record_review(actor,w.case_id,outcome(w,data).pk,values['evidence'],values['note'],case_expected)
    elif action=='retrospective_decision':result=native.decide_retrospective(actor,w.case_id,outcome(w,data).pk,values['role'],values['verdict'],values['evidence'],values['note'],case_expected)
    elif action=='reconcile_retrospective':result=native.reconcile_retrospective(actor,w.case_id,outcome(w,data).pk,case_expected)
    else:raise ValidationError('Choose a native human Emergency action')
    event(actor,w.case,'factory.emergency_human_action',work=w.pk,profile=p.pk,native_action=action,native_record=result.pk);return result

def reconcile(actor,work_id,expected,adapter=None):
    from .factory import access,cancellation_status
    from apps.documents.delivery import run_publication_once
    with transaction.atomic():
        w=Work.objects.select_for_update(of=('self',)).select_related('case').get(pk=work_id,definition=DEFINITION)
        access(actor,w.case,'factory.execute',DEFINITION)
        if actor.pk!=w.actor_id:require(actor,w.case,'factory.manage')
        if type(expected) is not int or w.revision!=expected or w.lease_until and w.lease_until>timezone.now():raise ValidationError('STALE_VERSION: refresh original Emergency delivery')
        job=PublicationJob.objects.filter(publication__factory_work=w).filter(Q(status='unknown')|Q(status='leased',lease_until__lte=timezone.now())).order_by('pk').first()
        if not job:raise ValidationError('No original uncertain Emergency delivery needs reconciliation')
        event(actor,w.case,'factory.reconciliation_requested',work=w.pk,publication_job=job.pk)
    run_publication_once(adapter,case_id=w.case_id,job_id=job.pk)
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
    if any(type(pk) is not int or pk<1 for pk in [expected,case_expected,job_id]) or w.revision!=expected:raise ValidationError('STALE_VERSION: refresh exact change and project versions')
    if w.lease_until and w.lease_until>timezone.now():raise ValidationError('Wait for the current worker before operating delivery')
    if not PublicationJob.objects.filter(pk=job_id,publication__factory_work=w).exists():raise ValidationError('Choose this work original delivery')
    if action not in ['cancel','retry'] or not isinstance(reason,str):raise ValidationError('Choose a native recovery action and explain it')
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
    if w.revision!=expected:raise ValidationError('STALE_VERSION: refresh current change work')
    if w.status in ['verified','followup_needed']:raise ValidationError('Delivered or accepted work requires native follow-up')
    if w.status=='cancelled':return w
    if not w.cancel_requested:w=manage(actor,w.pk,w.revision,'cancel')
    if w.lease_until and w.lease_until>timezone.now():return w
    w.status=cancellation_status(w);w.finding='Stopping work cannot undo an already delivered document or recorded retrospective evidence.'
    w.lease_until=None;w.revision+=1;w.save();return w



@transaction.atomic
def restart(actor,work_id,expected,case_expected,reason):
    from .factory import access
    from apps.agents.factory_coordinator import pending,has_receipt
    w=Work.objects.select_for_update(of=('self',)).select_related('case','source_head','actor').get(pk=work_id,definition=DEFINITION)
    access(actor,w.case,'factory.manage',DEFINITION);case=lock_case(actor,w.case_id,'evidence.add',case_expected);w.case=case
    if type(expected) is not int or w.revision!=expected or w.status!='cancelled' or not w.cancel_requested:raise ValidationError('Only settled stopped preparation can receive a fresh instruction')
    if w.lease_until and w.lease_until>timezone.now() or PublicationJob.objects.filter(publication__factory_work=w,status__in=['pending','unknown','leased','held']).exists():raise ValidationError('Resolve original effects before restarting')
    planning=pending(w)
    if planning and not has_receipt(planning):raise ValidationError('Resolve original planning response before restarting')
    if PublicationReceipt.objects.filter(publication__factory_work=w).exists():raise ValidationError('Delivered reports require native follow-up, not restart')
    if not isinstance(reason,str) or not reason.strip() or len(reason)>2000:raise ValidationError('Explain the fresh preparation instruction')
    p,data=source(w,actor,False)
    if p.version.change.current_id!=p.version_id or p.version.emergency_profiles.order_by('-pk').first().pk!=p.pk:raise ValidationError('Emergency source changed; review its native follow-up')
    old=w.source_head_id;w.source_head=capture(actor,case,p,data['inputs'],'factory.emergency_source');w.cancel_requested=False;w.status='ready';w.finding='';w.lease_until=None;w.fence+=1;w.revision+=1;w.save()
    event(actor,case,'factory.emergency_restarted',work=w.pk,previous=old,current=w.source_head_id,reason=reason,spent=w.budget_used);return w

def projection(actor,work):
    from .factory import access,profile
    from apps.policy.services import decision_authority
    access(actor,work.case,'factory.read',DEFINITION);p,data=source(work,actor,False);v=document(work)
    issue='';options=[];next_action='Review native Emergency prerequisites';current=True
    try:source(work,actor);status=report(work,actor)
    except (ValidationError,PermissionDenied) as exc:status={'stage':'source','finding':finding(exc)};issue=finding(exc);current=False
    jobs=list(PublicationJob.objects.filter(publication__factory_work=work).order_by('pk'));receipts=list(PublicationReceipt.objects.filter(publication__version=v).order_by('pk')) if v else []
    idle=not (work.lease_until and work.lease_until>timezone.now());live=idle and not work.cancel_requested;verdicts=[]
    if live and current and v and HumanTask.objects.filter(version=v,status='open').exists():
        try:
            current_version(work.case,v.pk);require(actor,work.case,'document.review_controlled')
            for verdict in ['approve','return','reject']:
                try:decision_authority(actor,work.case,'PMO Lead',verdict);verdicts.append(verdict)
                except (ValidationError,PermissionDenied):pass
        except (ValidationError,PermissionDenied):pass
    try:
        _,value=profile(work);state,*args=snapshot(work,value,reader=actor);options,next_action=eligible(work,value,state,*args)
    except (ValidationError,PermissionDenied) as exc:next_action=finding(exc)
    changed=False
    if work.status=='verified':
        try:verify(work,actor);next_action='Inspect the recorded retrospective outcome and exact report receipts'
        except (ValidationError,PermissionDenied) as exc:changed=True;issue=finding(exc)
    can_correct=False;can_restart=False
    try:
        require(actor,work.case,'factory.manage');require(actor,work.case,'evidence.add')
        settled=not any(j.status in ['pending','unknown','leased','held'] for j in jobs)
        can_correct=live and work.status not in ['cancelled','followup_needed'] and settled
        can_restart=idle and work.cancel_requested and work.status=='cancelled' and settled and not PublicationReceipt.objects.filter(publication__factory_work=work).exists()
    except PermissionDenied:pass
    for j in jobs:
        j.can_operate=False;j.can_retry=False
        try:
            require(actor,work.case,'document.operate')
            j.can_operate=idle and (j.status in ['pending','unknown','held'] or j.status=='leased' and j.lease_until and j.lease_until<=timezone.now()) and not PublicationReceipt.objects.filter(publication=j.publication).exists()
            j.can_retry=j.can_operate and not work.cancel_requested and j.status=='held'
        except PermissionDenied:pass
    permissions={}
    for name,action in [('preauthorization_decision','emergency.decide'),('authorize','emergency.authorize'),('capture_outcome','emergency.record_outcome'),('record_review','emergency.review'),('retrospective_decision','emergency.retrospective_decide'),('reconcile_retrospective','emergency.manage')]:
        permissions[name]=False
        if live and current and work.status!='verified':
            try:require(actor,work.case,action);permissions[name]=True
            except PermissionDenied:pass
    return {'profile':p,'data':data,'status':status,'document':v,'receipts':receipts,'jobs':jobs,'finding':issue,'readiness_changed':changed,'next_options':options,'next_action':next_action,'can_correct':can_correct,'can_restart':can_restart,'review_verdicts':verdicts,'human':permissions}

"""Native controlled changes. Agents investigate/draft; people assess, decide and sign."""
import hashlib,json
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
from apps.pmo import changes,change_execution as native
from apps.pmo.models import ChangeVersion,ChangeAuthorization,ChangeDocumentBinding,ChangeClosure
from .models import FactoryWork as Work,FactoryActivity as Activity,FactoryAttempt as Attempt,HumanTask
from .factory_delivery import investigation_key
from .factory_handover import pending_job

DEFINITION='pmo-change/v1'
KIND='agent_private_change_intake'
PROTOCOL='factory-change-intake/v1'
ID={'anyOf':[{'type':'integer','minimum':1,'maximum':9223372036854775807},{'type':'null'}]}
INPUT={'type':'object','properties':{'template_id':ID,'authorization_id':ID},'required':['template_id','authorization_id'],'additionalProperties':False}
SCHEMA={'type':'object','properties':{'protocol':{'const':PROTOCOL},'change_version_id':{'type':'integer','minimum':1},'inputs':INPUT},'required':['protocol','change_version_id','inputs'],'additionalProperties':False}

def finding(exc):return '; '.join(exc.messages) if isinstance(exc,ValidationError) else str(exc)

def input_rows(case,version,inputs):
    validate(INPUT,inputs)
    if any(x is not None and type(x) is not int for x in inputs.values()):raise ValidationError('Exact integer source references required')
    if inputs['template_id'] and not Template.objects.filter(case=case,pk=inputs['template_id'],definition__document_type__in=['status_report','project_artifact']).exists():raise ValidationError('Choose this project controlled change template')
    if inputs['authorization_id'] and not ChangeAuthorization.objects.filter(pk=inputs['authorization_id'],version=version).exists():raise ValidationError('Choose the authorization for this exact change revision')

def source(work,actor=None,current=True):
    require(actor or work.actor,work.case,'change.read');e=work.source_head
    if not e or e.case_id!=work.case_id or e.kind!=KIND or e.sha256!=hashlib.sha256(e.body.encode()).hexdigest():raise ValidationError('Exact change intake required')
    try:data=json.loads(e.body)
    except (TypeError,ValueError):raise ValidationError('Typed native change intake required') from None
    validate(SCHEMA,data)
    audit=Audit.objects.filter(case=work.case,actor_id=e.created_by_id,action__in=['factory.change_intake','factory.change_source'],data={'evidence_id':e.pk,'sha256':e.sha256}).first()
    v=ChangeVersion.objects.select_related('change').filter(pk=data['change_version_id'],change__case=work.case).first()
    if not audit or not v or v.change_id!=work.request['change']:raise ValidationError('Same-project native change provenance required')
    if current:
        for action in ['case.read','change.read','evidence.add','factory.start' if audit.action=='factory.change_intake' else 'factory.manage']:require(e.created_by,work.case,action)
        if v.change.current_id!=v.pk:raise ValidationError('Change revision replaced; explicitly select the new native revision')
    input_rows(work.case,v,data['inputs']);return v,data

def capture(actor,case,v,inputs,action):
    e=add_evidence(actor,case.pk,KIND,json.dumps({'protocol':PROTOCOL,'change_version_id':v.pk,'inputs':inputs},sort_keys=True),'psl:'+PROTOCOL)
    event(actor,case,action,evidence_id=e.pk,sha256=e.sha256);return e

@transaction.atomic
def start(actor,case_id,key,version_id,inputs,reference,expected=None):
    from .factory import access
    case=lock_case(actor,case_id,'factory.start',expected);access(actor,case,'factory.start',DEFINITION);require(actor,case,'evidence.add')
    if case.kind!='project' or not isinstance(key,str) or not key.isascii() or not 1<=len(key)<=100 or not isinstance(reference,str) or not reference.strip() or len(reference)>160:raise ValidationError('Project, bounded work identity and description required')
    v=ChangeVersion.objects.select_related('change').filter(pk=version_id,change__case=case).first()
    if not v or v.change.current_id!=v.pk:raise ValidationError('Select this project current native change revision')
    input_rows(case,v,inputs)
    payload={'change':v.change_id,'reference':reference};sha=digest(payload);business=digest([str(case.pk),DEFINITION,v.change_id])
    old=Work.objects.filter(case=case).filter(Q(key=key)|Q(definition=DEFINITION,business_key=business)).first()
    if old:
        if old.actor_id!=actor.pk or old.definition!=DEFINITION or old.key==key and old.request_hash!=sha:raise ValidationError('IDEMPOTENCY_CONFLICT: changed change-work intent')
        ov,data=source(old,actor)
        if ov.pk!=v.pk or data['inputs']!=inputs:raise ValidationError('Correct sources in the existing change work')
        return old
    w=Work.objects.create(case=case,actor=actor,key=key,definition=DEFINITION,request=payload,request_hash=sha,business_key=business,source_head=capture(actor,case,v,inputs,'factory.change_intake'))
    event(actor,case,'factory.started',work=w.pk,definition=DEFINITION);return w

def authorization(work,data):
    if not data['inputs']['authorization_id']:raise ValidationError('Await human impact assessment, prescribed decisions and explicit native authorization selection')
    return native.get_authorization(work.case,data['inputs']['authorization_id'])

def document(work,purpose):
    pk=Attempt.objects.filter(activity__work=work,phase='observed',result__head=work.source_head_id,result__purpose=purpose,result__has_key='document_version').order_by('-pk').values_list('result__document_version',flat=True).first()
    b=ChangeDocumentBinding.objects.select_related('version__document','version__template').filter(version_id=pk,purpose=purpose,authorization__version__change_id=work.request['change']).first()
    return b.version if b else None

def principal(work,value,name):
    u=get_user_model().objects.filter(pk=value[name],is_active=True).first()
    if not u:raise ValidationError('owner_needed: Configure current change '+name.replace('_id',''))
    try:
        for action in ['case.read','change.read','factory.execute']+(['change.manage','document.draft','document.request_review'] if name=='preparer_id' else ['document.publish']):require(u,work.case,action)
    except PermissionDenied:raise ValidationError('owner_needed: Change principal lacks current project permissions') from None
    return u

def published(work,purpose,actor=None):
    from .factory import profile
    _,data=source(work,actor);auth=authorization(work,data);v=document(work,purpose)
    if not v:raise ValidationError('Await exact controlled '+purpose+' document')
    b=ChangeDocumentBinding.objects.get(version=v)
    if b.authorization_id!=auth.pk or b.purpose!=purpose:raise ValidationError('Exact selected change authorization required')
    current_version(work.case,v.pk);review=validate_review(work.case,v);policies,recipients,retention=publication_requirements(work.case,v)
    config,value=profile(work,recovery=True);principal(work,value,'preparer_id');user=principal(work,value,'executor_id')
    p=Publication.objects.filter(version=v,factory_work=work,factory_source=work.source_head,factory_policy=config,actor=user).first()
    if not p or p.policies!=policies or p.recipient_ids!=recipients or p.retention_days!=retention or p.review_id!=review.pk:raise ValidationError('Await current exact '+purpose+' publication')
    receipts=list(PublicationReceipt.objects.filter(publication=p).order_by('pk'))
    if not receipts or {x.recipient_id for x in receipts}!=set(recipients) or any(x.payload!=v.payload or x.payload_sha256!=v.payload_sha256 for x in receipts):raise ValidationError('Every exact '+purpose+' recipient receipt is required')
    return v,p,receipts

def report(work,actor=None):
    v,data=source(work,actor);rows=list(v.assessments.order_by('pk'));decisions=list(v.decisions.order_by('pk'))
    result={'change_version':v.pk,'category':v.category,'assessments':[x.pk for x in rows],'decisions':[x.pk for x in decisions],'authorization':data['inputs']['authorization_id'],'owner_impacts':[{'contributor':x.contributor,'assessment':x.pk,'cost':x.cost_impact,'timeline':x.timeline_impact,'client_facing':x.client_facing,'evidence':x.evidence_id,'impact_details':x.impact_details} for x in rows],'stage':'impact','finding':'','deployment_authorized':False}
    result['execution_impacts']=list(ChangeAuthorization.objects.get(pk=data['inputs']['authorization_id']).execution.order_by('pk').values('pk','kind','impact_details')) if data['inputs']['authorization_id'] else []
    try:
        if v.category=='Emergency':raise ValidationError('Emergency P61/P62 use native preauthorization, incident, implementation and retrospective controls; ordinary change authorization is not applicable')
        changes.impact(v);result['stage']='authorization';auth=authorization(work,data)
        result['stage']='notice';published(work,'notice',actor)
        result['stage']='execution';native.execution_manifest(auth)
        result['stage']='go_live';published(work,'go_live',actor)
        result['stage']='signatures';verify(work,actor);result['stage']='complete'
    except (ValidationError,PermissionDenied) as exc:result['finding']=finding(exc)
    return result

@read_observation
def snapshot(work,value,reader=None):
    from .factory import access
    actor=reader or work.execution_actor;access(actor,work.case,'factory.read' if reader is not None else 'factory.execute',DEFINITION)
    v,data=source(work,actor);native_state=report(work,actor)
    ids={v.evidence_id}|set(v.assessments.values_list('evidence_id',flat=True))|set(v.decisions.values_list('evidence_id',flat=True))
    if data['inputs']['authorization_id']:ids.update(ChangeAuthorization.objects.get(pk=data['inputs']['authorization_id']).execution.values_list('evidence_id',flat=True))
    latest={KIND:work.source_head}
    evidence=Evidence.objects.filter(case=work.case,pk__in=ids)
    allowed=public_evidence(evidence)|evidence.filter(pk=v.evidence_id,source='psl:p56-confirmed-request/v1')
    for e in allowed.order_by('pk'):
        if e.kind not in latest or latest[e.kind].version<e.version:latest[e.kind]=e
    missing=[k for k in value['required_evidence_kinds'] if k not in latest]
    stale=[k for k in value['required_evidence_kinds'] if k in latest and latest[k].created_at<timezone.now()-timedelta(seconds=value['max_age_seconds'])]
    jobs=list(PublicationJob.objects.filter(publication__factory_work=work).order_by('pk'))
    docs={}
    for purpose in ['notice','go_live']:
        d=document(work,purpose);review={'status':'unprepared'}
        if d:
            try:current_version(work.case,d.pk);r=validate_review(work.case,d);review={'status':'ready','id':r.pk}
            except (ValidationError,PermissionDenied) as exc:review={'status':'held','finding':finding(exc)}
        docs[purpose]={'id':d.pk if d else None,'review':review,'publication':Publication.objects.filter(version=d).values_list('pk',flat=True).first() if d else None}
    state={'case_revision':work.case.revision,'profile':work.policy_id,'sources':[(e.pk,e.sha256) for e in latest.values()],'native':native_state,'checks':{'stage':native_state['stage']},'documents':docs,'jobs':[(j.pk,j.status) for j in jobs]}
    state['hash']=digest(state);state['work_revision']=work.revision
    return state,latest,missing,stale,[],jobs

def eligible(work,value,state,latest,missing,stale,tasks,jobs):
    job=pending_job(jobs)
    if job:return ['ACT11' if job.status=='pending' else 'ACT12'],'Deliver or reconcile the original controlled change document'
    if any(j.status in ['held','leased'] for j in jobs):return [],'Resolve the original controlled delivery before continuing'
    if not Activity.objects.filter(work=work,key=investigation_key(work,state),status='succeeded').exists():return ['ACT04'],'Investigate the exact change, owner assessments and native handoffs'
    if missing or stale:return [],'Required current change evidence is missing or stale: '+', '.join(missing+stale)
    stage=state['native']['stage']
    if stage=='complete':return ['ACT13'],'Verify native signed closure and every exact document receipt'
    if stage not in ['notice','go_live']:return [],state['native']['finding']
    d=state['documents'][stage]
    if not d['id']:return ['ACT09'],'Prepare the controlled '+stage.replace('_',' ')+' document'
    if not HumanTask.objects.filter(version_id=d['id']).exists():return ['ACT09'],'Request native review of the retained draft'
    if d['review']['status']!='ready':return [],'Await exact document review or source-owned rework'
    if not d['publication']:return ['ACT11'],'Reserve the reviewed controlled change document'
    return [],state['native']['finding']

def act(work,choice,value,latest,missing,tasks,jobs):
    from .factory import access
    case=lock_case(work.execution_actor,work.case_id,'factory.execute');access(work.execution_actor,case,'factory.execute',DEFINITION)
    list(Grant.objects.select_for_update().filter(case=case).order_by('pk'))
    if case.revision!=work.case.revision:raise ValidationError('STALE_VERSION: change sources changed')
    _,data=source(work,work.execution_actor);kind=choice['activity'];status=report(work,work.execution_actor);purpose=status['stage']
    if kind=='ACT04':return {'head':work.source_head_id,'native':status,'source_refs':sorted(e.pk for e in latest.values()),'decisions_inferred':False}
    if kind=='ACT09':
        from apps.documents.controlled import request_review
        if purpose not in ['notice','go_live']:raise ValidationError('Human native prerequisites remain incomplete')
        auth=authorization(work,data);u=principal(work,value,'preparer_id');v=document(work,purpose)
        if not data['inputs']['template_id']:raise ValidationError('Select the controlled change template')
        if not v:v=native.draft_change_document(u,case.pk,auth.pk,data['inputs']['template_id'],purpose,case.revision,'client')
        task=None;waiting=None
        if not HumanTask.objects.filter(version=v).exists():
            try:current_version(case,v.pk)
            except (ValidationError,PermissionDenied):waiting='Draft retained; complete native source and recipient requirements before review'
            else:case.refresh_from_db();task=request_review(u,case.pk,v.pk,case.revision)
        result={'head':work.source_head_id,'purpose':purpose,'document_version':v.pk,'native_review_task':task.pk if task else None}
        if waiting:result['waiting']=waiting
        return result
    if kind in ['ACT11','ACT12']:
        job=pending_job(jobs)
        if job:return {'head':work.source_head_id,'publication_job':job.pk}
        if kind=='ACT12' or purpose not in ['notice','go_live']:raise ValidationError('No exact original document delivery is eligible')
        from apps.documents.controlled import reserve_publication
        u=principal(work,value,'executor_id');v=document(work,purpose)
        p=reserve_publication(u,case.pk,v.pk,case.revision,factory_work_id=work.pk)
        return {'head':work.source_head_id,'purpose':purpose,'publication':p.pk}
    if kind=='ACT13':result=verify(work,work.execution_actor);work.status='verified';return result
    raise ValidationError('Human assessments, authorization, execution attestations and signatures cannot be executed by the model')

def publication_scope(actor,case,version,work_id):
    from .factory import access,profile
    w=Work.objects.select_related('case','actor','source_head').get(pk=work_id,case=case,definition=DEFINITION)
    access(actor,case,'factory.execute',DEFINITION);config,value=profile(w)
    if w.policy_id!=config.pk or principal(w,value,'executor_id').pk!=actor.pk:raise PermissionDenied('Exact current publisher and policy required')
    principal(w,value,'preparer_id')
    if w.cancel_requested or w.status in ['verified','cancelled','followup_needed']:raise ValidationError('Change publication is stopped')
    _,data=source(w);auth=authorization(w,data);b=ChangeDocumentBinding.objects.filter(version=version,authorization=auth).first()
    if not b or b.purpose not in ['notice','go_live'] or document(w,b.purpose)!=version or version.template_id!=data['inputs']['template_id'] or version.audience!='client':raise ValidationError('Exact observed source-bound change document required')
    if b.purpose=='go_live':published(w,'notice');native.execution_manifest(auth)
    if native.change_binding_findings(b):raise ValidationError(native.change_binding_findings(b))
    return {'factory_work_id':w.pk,'factory_policy_id':config.pk,'factory_source_id':w.source_head_id}

def verify(work,actor=None):
    _,data=source(work,actor);auth=authorization(work,data)
    notice,np,nr=published(work,'notice',actor);v,p,receipts=published(work,'go_live',actor)
    closure=ChangeClosure.objects.filter(authorization=auth,receipt_id__in=[r.pk for r in receipts]).first()
    if not closure or closure.execution_ids!=native.execution_manifest(auth):raise ValidationError('Await actual native PM closure with distinct PM and Client signatures for this exact delivered change')
    return {'verified':True,'verification_scope':'native_controlled_change_delivery_and_human_signature_attestation','head':work.source_head_id,'authorization':auth.pk,'closure':closure.pk,'document_version':v.pk,'notice_version':notice.pk,'receipt_ids':[r.pk for r in nr+receipts],'deployment_authorized':False,'external_authenticity_verified':False}

@transaction.atomic
def correct(actor,work_id,expected,case_expected,version_id,inputs,reason):
    from .factory import access
    w=Work.objects.select_for_update(of=('self',)).select_related('case','actor','source_head').get(pk=work_id,definition=DEFINITION)
    access(actor,w.case,'factory.manage',DEFINITION);case=lock_case(actor,w.case_id,'evidence.add',case_expected);w.case=case
    if type(expected) is not int or w.revision!=expected or w.cancel_requested or w.status in ['cancelled','followup_needed']:raise ValidationError('STALE_VERSION: refresh current change work')
    if w.lease_until and w.lease_until>timezone.now() or PublicationJob.objects.filter(publication__factory_work=w,status__in=['pending','unknown','leased','held']).exists():raise ValidationError('Resolve original effects before source correction')
    from apps.agents.factory_coordinator import pending,has_receipt
    planning=pending(w)
    if planning and not has_receipt(planning):raise ValidationError('Reconcile the original planning response before source correction')
    if not isinstance(reason,str) or not reason.strip() or len(reason)>2000:raise ValidationError('Explain the source-owned correction')
    old,data=source(w,actor,False);v=ChangeVersion.objects.select_related('change').filter(pk=version_id,change_id=old.change_id).first()
    if not v or v.change.current_id!=v.pk:raise ValidationError('Select the current revision of this exact change')
    if ChangeClosure.objects.filter(authorization__version=v).exists():raise ValidationError('Closed native changes require a new revision')
    input_rows(case,v,inputs)
    if old.pk==v.pk and data['inputs']==inputs:
        docs=[document(w,k) for k in ['notice','go_live']]
        if not any(d for d in docs):raise ValidationError('Provide changed native sources')
        for d in docs:
            if d:
                if PublicationJob.objects.filter(publication__version=d,publication__factory_work=w,status='cancelled').exists() and not PublicationReceipt.objects.filter(publication__version=d).exists():break
                try:current_version(case,d.pk);validate_review(case,d)
                except (ValidationError,PermissionDenied):break
        else:raise ValidationError('Current documents require a genuine source correction')
    head=w.source_head_id;w.source_head=capture(actor,case,v,inputs,'factory.change_source');w.status='ready';w.finding='';w.revision+=1;w.save()
    event(actor,case,'factory.change_corrected',work=w.pk,previous=head,current=w.source_head_id,reason=reason);return w

@transaction.atomic
def review(actor,work_id,expected,case_expected,version_id,verdict,note):
    from .factory import access
    from apps.documents.controlled import review_version
    w=Work.objects.select_for_update(of=('self',)).select_related('case','source_head','actor').get(pk=work_id,definition=DEFINITION)
    access(actor,w.case,'factory.read',DEFINITION);source(w,actor)
    if type(expected) is not int or w.revision!=expected or w.cancel_requested or w.lease_until and w.lease_until>timezone.now() or version_id not in [d.pk for d in [document(w,'notice'),document(w,'go_live')] if d]:raise ValidationError('STALE_VERSION: select the exact current change document')
    return review_version(actor,w.case_id,version_id,verdict,note,case_expected)

def reconcile(actor,work_id,expected,adapter=None):
    from .factory import access,cancellation_status
    from apps.documents.delivery import run_publication_once
    with transaction.atomic():
        w=Work.objects.select_for_update(of=('self',)).select_related('case').get(pk=work_id,definition=DEFINITION)
        access(actor,w.case,'factory.execute',DEFINITION)
        if actor.pk!=w.actor_id:require(actor,w.case,'factory.manage')
        if type(expected) is not int or w.revision!=expected or w.lease_until and w.lease_until>timezone.now():raise ValidationError('STALE_VERSION: refresh original change delivery')
        job=PublicationJob.objects.filter(publication__factory_work=w).filter(Q(status='unknown')|Q(status='leased',lease_until__lte=timezone.now())).order_by('pk').first()
        if not job:raise ValidationError('No original uncertain change delivery needs reconciliation')
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
    w.status=cancellation_status(w);w.finding='Stopping work cannot undo an already delivered document or actual sign-off.'
    w.lease_until=None;w.revision+=1;w.save();return w


@transaction.atomic
def close(actor,work_id,expected,case_expected,receipt_id,pm_signature_id,client_signature_id,note):
    from .factory import access
    w=Work.objects.select_for_update(of=('self',)).select_related('case','actor','source_head').get(pk=work_id,definition=DEFINITION)
    access(actor,w.case,'factory.read',DEFINITION);require(actor,w.case,'change.manage')
    if type(expected) is not int or w.revision!=expected or w.cancel_requested or w.lease_until and w.lease_until>timezone.now():raise ValidationError('STALE_VERSION: refresh exact work')
    _,data=source(w,actor);auth=authorization(w,data);published(w,'notice',actor);_,_,receipts=published(w,'go_live',actor)
    if receipt_id not in [x.pk for x in receipts]:raise ValidationError('Select this exact controlled change receipt')
    result=native.close_change(actor,w.case_id,auth.pk,receipt_id,pm_signature_id,client_signature_id,note,case_expected)
    w.status='ready';w.finding='Actual signed closure recorded; verify exact native result';w.revision+=1;w.save();return result

def projection(actor,work):
    from .factory import access,profile
    access(actor,work.case,'factory.read',DEFINITION);v,data=source(work,actor,False)
    issue='';options=[];next_action='Review native change prerequisites';current=True
    try:source(work,actor);status=report(work,actor)
    except (ValidationError,PermissionDenied) as exc:status={'stage':'source','finding':finding(exc)};issue=finding(exc);current=False
    jobs=list(PublicationJob.objects.filter(publication__factory_work=work).order_by('pk'));docs=[]
    live=not work.cancel_requested and not (work.lease_until and work.lease_until>timezone.now())
    from apps.policy.services import decision_authority
    for purpose in ['notice','go_live']:
        d=document(work,purpose)
        if not d:continue
        verdicts=[]
        if live and current and HumanTask.objects.filter(version=d,status='open').exists():
            try:
                current_version(work.case,d.pk);require(actor,work.case,'document.review_controlled')
                for verdict in ['approve','return','reject']:
                    try:decision_authority(actor,work.case,'PMO Lead',verdict);verdicts.append(verdict)
                    except (ValidationError,PermissionDenied):pass
            except (ValidationError,PermissionDenied):pass
        docs.append({'version':d,'purpose':purpose,'verdicts':verdicts,'receipts':list(PublicationReceipt.objects.filter(publication__version=d).order_by('pk'))})
    try:
        _,value=profile(work);state,*args=snapshot(work,value,reader=actor);options,next_action=eligible(work,value,state,*args)
    except (ValidationError,PermissionDenied) as exc:next_action=finding(exc)
    changed=False
    if work.status=='verified':
        try:
            verify(work,actor);next_action='Inspect the recorded signed closure and exact document receipts';options=[]
        except (ValidationError,PermissionDenied) as exc:changed=True;issue=finding(exc)
    can_correct=False;can_close=False
    if live:
        try:
            require(actor,work.case,'factory.manage');require(actor,work.case,'evidence.add')
            can_correct=not ChangeClosure.objects.filter(authorization__version_id=v.change.current_id).exists() and work.status not in ['cancelled','followup_needed'] and not any(j.status in ['pending','unknown','leased','held'] for j in jobs)
        except PermissionDenied:pass
        try:
            require(actor,work.case,'change.manage');decision_authority(actor,work.case,'PM');published(work,'notice',actor);published(work,'go_live',actor)
            can_close=not ChangeClosure.objects.filter(authorization_id=data['inputs']['authorization_id']).exists()
        except (ValidationError,PermissionDenied):pass
    for j in jobs:
        j.can_operate=False;j.can_retry=False
        try:
            require(actor,work.case,'document.operate');j.can_operate=not (work.lease_until and work.lease_until>timezone.now()) and (j.status in ['pending','unknown','held'] or j.status=='leased' and j.lease_until and j.lease_until<=timezone.now()) and not PublicationReceipt.objects.filter(publication=j.publication).exists()
            j.can_retry=j.can_operate and not work.cancel_requested and j.status=='held'
        except PermissionDenied:pass
    can_restart=False
    try:
        require(actor,work.case,'factory.manage');require(actor,work.case,'evidence.add')
        can_restart=work.cancel_requested and work.status=='cancelled' and not (work.lease_until and work.lease_until>timezone.now()) and not any(j.status in ['pending','unknown','leased','held'] for j in jobs) and not PublicationReceipt.objects.filter(publication__factory_work=work).exists()
    except PermissionDenied:pass
    history=[]
    for a in Attempt.objects.filter(activity__work=work,phase='observed',result__has_key='document_version').exclude(result__head=work.source_head_id).order_by('pk'):
        identity=(a.result.get('document_version'),a.result.get('head'))
        if identity not in history:history.append(identity)
    return {'document_history':history,'can_restart':can_restart,'version':v,'data':data,'status':status,'documents':docs,'jobs':jobs,'finding':issue,'readiness_changed':changed,'next_options':options,'next_action':next_action,'can_correct':can_correct,'can_close':can_close}

@transaction.atomic
def human_action(actor,work_id,expected,case_expected,version_id,action,values):
    """Exact work pin for native human commands. Never registered as an agent tool."""
    from .factory import access
    w=Work.objects.select_for_update(of=('self',)).select_related('case','source_head','actor').get(pk=work_id,definition=DEFINITION)
    access(actor,w.case,'factory.read',DEFINITION);v,data=source(w,actor)
    if type(expected) is not int or w.revision!=expected or v.pk!=version_id or w.cancel_requested or w.lease_until and w.lease_until>timezone.now():raise ValidationError('STALE_VERSION: refresh exact change work')
    if v.category=='Emergency':raise ValidationError('Use the separate native Emergency preauthorization and retrospective route')
    if action=='assess':result=changes.assess_change(actor,w.case_id,v.pk,values['contributor'],values['cost_impact'],values['timeline_impact'],values['client_facing'],values['evidence'],values['note'],case_expected,**{k:values.get(k) for k in ['outputs','production_impact','scope_items']})
    elif action=='decide':result=changes.decide_change(actor,w.case_id,v.pk,values['role'],values['verdict'],values['evidence'],values['note'],case_expected)
    elif action=='authorize':result=changes.authorize_change(actor,w.case_id,v.pk,values.get('commercial'),case_expected)
    elif action=='execution':
        auth=authorization(w,data);result=native.record_execution(actor,w.case_id,auth.pk,values['kind'],values['evidence'],values['note'],case_expected,scope_items=values.get('scope_items'),dossier_id=values.get('dossier_id'),candidate_id=values.get('candidate_id'))
    else:raise ValidationError('Choose a native human change action')
    event(actor,w.case,'factory.change_human_action',work=w.pk,change_version=v.pk,native_action=action,native_record=result.pk)
    return result

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
    if PublicationReceipt.objects.filter(publication__factory_work=w).exists():raise ValidationError('Delivered changes require native follow-up, not restart')
    if not isinstance(reason,str) or not reason.strip() or len(reason)>2000:raise ValidationError('Explain the fresh preparation instruction')
    v,data=source(w,actor,False)
    if v.change.current_id!=v.pk or ChangeClosure.objects.filter(authorization__version=v).exists():raise ValidationError('Native change changed or closed; review its source-owned follow-up')
    old=w.source_head_id;w.source_head=capture(actor,case,v,data['inputs'],'factory.change_source');w.cancel_requested=False;w.status='ready';w.finding='';w.lease_until=None;w.fence+=1;w.revision+=1;w.save()
    event(actor,case,'factory.change_restarted',work=w.pk,previous=old,current=w.source_head_id,reason=reason,spent=w.budget_used);return w

"""Post-release evidence → controlled client document → actual human sign-off → native acceptance."""
import json,hashlib
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError,PermissionDenied
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from apps.core.models import Evidence,Audit
from apps.core.evidence_access import public_evidence
from apps.core.services import lock_case,add_evidence,event
from apps.core.read_observation import read_observation
from apps.identity.models import Grant
from apps.identity.services import require
from apps.documents.contracts import digest,validate
from apps.documents.models import Template,Publication,PublicationJob,PublicationReceipt
from apps.documents.controlled import current_version,validate_review,publication_requirements
from apps.policy.services import decision_authority
from apps.pmo import delivery,delivery_closure as native
from apps.pmo.delivery_documents import draft_delivery_document
from apps.pmo.models import DeliveryDocumentBinding
from adapters.delivery import LocalDeliveryAdapter
from .models import FactoryWork as Work,FactoryActivity as Activity,FactoryAttempt as Attempt,HumanTask
from .factory_delivery import investigation_key
from .factory_handover import pending_job
from .factory_closure import owners

DEFINITION='delivery-go-live/v1'
KIND='agent_private_go_live_intake'
PROTOCOL='factory-go-live-intake/v1'
FIELDS=['template_id','checklist','incident_reporting','rollback']
KINDS={'checklist':'deployment_checklist','incident_reporting':'incident_reporting','rollback':'rollback_plan'}
ID={'anyOf':[{'type':'integer','minimum':1,'maximum':9223372036854775807},{'type':'null'}]}
INPUT={'type':'object','properties':{k:ID for k in FIELDS},'required':FIELDS,'additionalProperties':False}
SCHEMA={'type':'object','properties':{'protocol':{'const':PROTOCOL},'dossier_id':{'type':'integer','minimum':1},'inputs':INPUT},
    'required':['protocol','dossier_id','inputs'],'additionalProperties':False}

def finding(exc):return '; '.join(exc.messages) if isinstance(exc,ValidationError) else str(exc)
def selected(data):return {k:data['inputs'][k] for k in KINDS}

def input_rows(case,inputs):
    validate(INPUT,inputs)
    if any(pk is not None and type(pk) is not int for pk in inputs.values()):raise ValidationError('Exact integer references or unprovided values required')
    if inputs['template_id'] is not None and not Template.objects.filter(case=case,pk=inputs['template_id'],definition__document_type='project_artifact').exists():
        raise ValidationError('Choose this project controlled go-live template')
    rows={e.pk:e for e in public_evidence(Evidence.objects.filter(case=case,pk__in=[inputs[k] for k in KINDS if inputs[k] is not None]))}
    for key,kind in KINDS.items():
        pk=inputs[key]
        if pk is not None and (pk not in rows or rows[pk].kind!=kind):raise ValidationError('Choose this project public '+kind.replace('_',' ')+' evidence')
    return rows

def source(work,actor=None,current=True):
    require(actor or work.actor,work.case,'delivery.read');e=work.source_head
    if not e or e.case_id!=work.case_id or e.kind!=KIND or e.sha256!=hashlib.sha256(e.body.encode()).hexdigest():raise ValidationError('Exact native go-live intake required')
    try:data=json.loads(e.body)
    except (ValueError,TypeError):raise ValidationError('Typed go-live intake required') from None
    validate(SCHEMA,data)
    audit=Audit.objects.filter(case=work.case,actor_id=e.created_by_id,action__in=['factory.go_live_intake','factory.go_live_source'],data={'evidence_id':e.pk,'sha256':e.sha256}).first()
    if not audit or data['dossier_id']!=work.request['dossier']:raise ValidationError('Exact same-project go-live provenance required')
    if current:
        for action in ['delivery.read','evidence.add','factory.start' if audit.action=='factory.go_live_intake' else 'factory.manage']:require(e.created_by,work.case,action)
    return delivery.dossier_for(work.case,data['dossier_id'],current=current),data,input_rows(work.case,data['inputs'])

def capture(actor,case,d,inputs,action):
    e=add_evidence(actor,case.pk,KIND,json.dumps({'protocol':PROTOCOL,'dossier_id':d.pk,'inputs':inputs},sort_keys=True),'psl:'+PROTOCOL)
    event(actor,case,action,evidence_id=e.pk,sha256=e.sha256);return e

@transaction.atomic
def start(actor,case_id,key,dossier_id,inputs,reference,expected=None):
    from .factory import access
    case=lock_case(actor,case_id,'factory.start',expected);access(actor,case,'factory.start',DEFINITION);require(actor,case,'evidence.add')
    if case.kind!='project':raise ValidationError('Go-live acceptance requires a project')
    if not isinstance(key,str) or not key.isascii() or not 1<=len(key)<=100 or not isinstance(reference,str) or not reference.strip() or len(reference)>160:
        raise ValidationError('Bounded go-live identity and description required')
    d=delivery.dossier_for(case,dossier_id);input_rows(case,inputs)
    payload={'dossier':d.pk,'reference':reference};business=digest([str(case.pk),DEFINITION,d.candidate_id]);sha=digest(payload)
    old=Work.objects.filter(case=case).filter(Q(key=key)|Q(definition=DEFINITION,business_key=business)).first()
    if old:
        if old.actor_id!=actor.pk or old.definition!=DEFINITION or old.key==key and old.request_hash!=sha:raise ValidationError('IDEMPOTENCY_CONFLICT: changed go-live intent')
        if source(old)[1]['inputs']!=inputs:raise ValidationError('Review changed inputs in the existing go-live work')
        return old
    delivery.ensure_open(d)
    w=Work.objects.create(case=case,actor=actor,key=key,definition=DEFINITION,request=payload,request_hash=sha,business_key=business,
        source_head=capture(actor,case,d,inputs,'factory.go_live_intake'))
    event(actor,case,'factory.started',work=w.pk,definition=DEFINITION);return w

def prerequisites(d,data):
    if any(data['inputs'][k] is None for k in FIELDS):raise ValidationError('Provide the controlled template, deployment checklist, incident reporting and rollback records')
    return native.go_live_inputs(d,selected(data))

def document(work):
    pk=Attempt.objects.filter(activity__work=work,phase='observed',result__head=work.source_head_id,result__has_key='document_version').order_by('-pk').values_list('result__document_version',flat=True).first()
    binding=DeliveryDocumentBinding.objects.select_related('version__document','version__template').filter(version_id=pk,dossier_id=work.request['dossier'],purpose='go_live').first()
    return binding.version if binding else None

def principal(work,value,name):
    user=get_user_model().objects.filter(pk=value[name],is_active=True).first()
    if not user:raise ValidationError('owner_needed: Configure the current go-live '+('PM preparer' if name=='preparer_id' else 'publisher'))
    try:
        for action in ['case.read','delivery.read','factory.execute']+(['delivery.manage','document.draft','document.request_review'] if name=='preparer_id' else ['document.publish']):require(user,work.case,action)
        if name=='preparer_id':decision_authority(user,work.case,'PM')
    except (ValidationError,PermissionDenied):raise ValidationError('owner_needed: Go-live principal needs current project permissions and prescribed PM authority') from None
    return user

def publication(work,version):return Publication.objects.filter(version=version).first() if version else None

def attestation_owners(work,d):
    action='reaffirm_go_live' if native.latest_go_live(d,False) else 'approve'
    result=[]
    for user in owners(work.case,'PM','delivery.manage'):
        try:decision_authority(user,work.case,'PM',action);result.append(user)
        except (ValidationError,PermissionDenied):pass
    return result

def published(work,actor=None):
    """Exact publication/receipts only; this never infers PM or Client sign-off."""
    from .factory import profile
    d,data,_=source(work,actor);prerequisites(d,data);v=document(work)
    if not v or v.audience!='client':raise ValidationError('Exact controlled client go-live document required')
    current_version(work.case,v.pk);review=validate_review(work.case,v);p=publication(work,v)
    policies,recipients,retention=publication_requirements(work.case,v)
    config,value=profile(work,recovery=True);principal(work,value,'preparer_id');publisher=principal(work,value,'executor_id')
    if not p or p.factory_work_id!=work.pk or p.factory_source_id!=work.source_head_id or p.factory_policy_id!=config.pk or p.actor_id!=publisher.pk:
        raise ValidationError('Exact current source-bound go-live publication required')
    if p.policies!=policies or p.recipient_ids!=recipients or p.retention_days!=retention or p.review_id!=review.pk:
        raise ValidationError('Go-live audience, review or policy changed; prepare a current exact package')
    receipts=list(PublicationReceipt.objects.filter(publication=p).order_by('pk'))
    if {r.recipient_id for r in receipts}!=set(recipients) or not receipts:raise ValidationError('Every exact client delivery receipt is required before acceptance')
    if any(r.payload!=v.payload or r.payload_sha256!=v.payload_sha256 for r in receipts):raise ValidationError('Exact go-live receipt payload required')
    return d,data,v,p,receipts

@read_observation
def snapshot(work,value,reader=None):
    from .factory import access
    actor=reader or work.execution_actor
    access(actor,work.case,'factory.read' if reader is not None else 'factory.execute',DEFINITION);d,data,chosen=source(work,actor);current=LocalDeliveryAdapter().read_current(d)
    latest={KIND:work.source_head}
    for e in public_evidence(Evidence.objects.filter(case=work.case,pk__in=set(current['source_evidence_ids'])|set(chosen))).order_by('pk'):
        if e.kind not in latest or e.version>latest[e.kind].version:latest[e.kind]=e
    missing=[k for k in value['required_evidence_kinds'] if k not in latest]
    stale=[k for k in value['required_evidence_kinds'] if k in latest and latest[k].created_at<timezone.now()-timedelta(seconds=value['max_age_seconds'])]
    stale+=['input:'+e.kind for e in chosen.values() if e.created_at<timezone.now()-timedelta(seconds=value['max_age_seconds'])]
    try:checks={'status':'ready','inputs':prerequisites(d,data)}
    except (ValidationError,PermissionDenied) as exc:checks={'status':'held','finding':finding(exc)}
    v=document(work);p=publication(work,v);jobs=list(PublicationJob.objects.filter(publication__factory_work=work).order_by('pk'))
    review={'status':'unprepared'}
    if v:
        try:current_version(work.case,v.pk);r=validate_review(work.case,v);review={'status':'ready','id':r.pk}
        except (ValidationError,PermissionDenied) as exc:review={'status':'held','finding':finding(exc)}
    accepted=native.latest_go_live(d,False)
    state={'case_revision':work.case.revision,'profile':work.policy_id,'sources':[(e.pk,e.sha256) for e in latest.values()],
        'native':current,'checks':checks,'document':v.pk if v else None,'review':review,'publication':p.pk if p else None,
        'jobs':[(j.pk,j.status) for j in jobs],'receipts':list(PublicationReceipt.objects.filter(publication=p).order_by('pk').values_list('pk','payload_sha256')) if p else [],
        'acceptance':accepted.pk if accepted else None,'pm_owners':[u.pk for u in attestation_owners(work,d)]}
    state['hash']=digest(state);state['work_revision']=work.revision
    return state,latest,missing,stale,[],jobs

def eligible(work,value,state,latest,missing,stale,tasks,jobs):
    pending=pending_job(jobs)
    if pending:return ['ACT11' if pending.status=='pending' else 'ACT12'],'Deliver the exact recorded go-live document' if pending.status=='pending' else 'Reconcile the original go-live delivery'
    if any(j.status in ['held','leased'] for j in jobs):return [],'Review the original go-live delivery before continuing'
    if not Activity.objects.filter(work=work,key=investigation_key(work,state),status='succeeded').exists():return ['ACT04'],'Investigate release, checklist, incident reporting and rollback evidence'
    if missing or stale:return [],'Current required go-live evidence is missing or stale: '+', '.join(missing+stale)
    if state['checks']['status']!='ready':return [],state['checks']['finding']
    if not state['document']:
        try:principal(work,value,'preparer_id')
        except ValidationError:return ['ACT10'],'Resolve the current PM report preparer'
        return ['ACT09'],'Prepare the controlled client go-live document'
    v=document(work)
    if not HumanTask.objects.filter(version=v).exists():
        try:current_version(work.case,v.pk)
        except (ValidationError,PermissionDenied) as exc:return [],finding(exc)
        return ['ACT09'],'Request native review of the retained exact draft'
    if state['review']['status']!='ready':return [],'Await the prescribed exact document review or corrected source evidence'
    if not state['publication']:
        try:principal(work,value,'executor_id')
        except ValidationError:return ['ACT10'],'Resolve the current controlled-document publisher'
        return ['ACT11'],'Reserve the exact reviewed client publication'
    try:published(work,actor=work.execution_actor)
    except (ValidationError,PermissionDenied) as exc:return [],finding(exc)
    try:verify(work,actor=work.execution_actor)
    except (ValidationError,PermissionDenied) as exc:
        if not state['pm_owners']:return ['ACT10'],'Resolve current PM authority for actual sign-off or reviewed evidence reaffirmation'
        return [],finding(exc)
    else:return ['ACT13'],'Verify actual PM and Client sign-off against the exact delivered document'

def act(work,choice,value,latest,missing,tasks,jobs):
    from .factory import access
    case=lock_case(work.execution_actor,work.case_id,'factory.execute');access(work.execution_actor,case,'factory.execute',DEFINITION)
    list(Grant.objects.select_for_update().filter(case=case).order_by('pk'))
    if case.revision!=work.case.revision:raise ValidationError('STALE_VERSION: go-live changed while planning')
    d,data,_=source(work,work.execution_actor);kind=choice['activity']
    if kind=='ACT04':
        report=LocalDeliveryAdapter().read_go_live(d,selected(data),data['inputs']['template_id'])
        return {'head':work.source_head_id,'dossier':d.pk,'source_refs':sorted(e.pk for e in latest.values()),
            'checks':report['checks'],'observed_at':report['as_of'],'sign_off_inferred':False}
    if kind=='ACT10':
        v=document(work)
        if not v:principal(work,value,'preparer_id')
        elif not publication(work,v):principal(work,value,'executor_id')
        elif not attestation_owners(work,d):raise ValidationError('owner_needed: Configure actual current PM sign-off or explicit evidence-reaffirmation authority')
        return {'head':work.source_head_id,'current_authority_checked':True}
    if kind=='ACT09':
        prerequisites(d,data);user=principal(work,value,'preparer_id');v=document(work)
        if not v:v=draft_delivery_document(user,case.pk,d.pk,'go_live',data['inputs']['template_id'],selected(data),case.revision)
        task=None;waiting=None
        if not HumanTask.objects.filter(version=v).exists():
            from apps.documents.controlled import request_review
            try:current_version(case,v.pk)
            except (ValidationError,PermissionDenied):waiting='The draft is retained. Complete the current recipient and source requirements before requesting review.'
            else:case.refresh_from_db();task=request_review(user,case.pk,v.pk,case.revision)
        result={'head':work.source_head_id,'document_version':v.pk,'native_review_task':task.pk if task else None,'preparer':user.pk,'sign_off_inferred':False}
        if waiting:result['waiting']=waiting
        return result
    if kind in ['ACT11','ACT12']:
        job=pending_job(jobs)
        if job:return {'head':work.source_head_id,'publication_job':job.pk}
        if kind=='ACT12':raise ValidationError('No original uncertain go-live delivery exists')
        from apps.documents.controlled import reserve_publication
        v=document(work);user=principal(work,value,'executor_id')
        if not v:raise ValidationError('Exact native go-live document required')
        p=reserve_publication(user,case.pk,v.pk,case.revision,factory_work_id=work.pk)
        return {'head':work.source_head_id,'publication':p.pk,'publisher':user.pk}
    if kind=='ACT13':result=verify(work,actor=work.execution_actor);work.status='verified';return result
    raise ValidationError('FORBIDDEN: no registered go-live activity; human sign-off cannot be executed by a model')

def publication_scope(actor,case,version,work_id):
    from .factory import access,profile
    w=Work.objects.select_related('case','actor','source_head').filter(pk=work_id,case=case,definition=DEFINITION).first()
    if not w:raise ValidationError('Exact go-live factory work required')
    access(actor,case,'factory.execute',DEFINITION);config,value=profile(w)
    if w.policy_id!=config.pk or principal(w,value,'executor_id').pk!=actor.pk:raise PermissionDenied('Current exact go-live publisher and profile required')
    principal(w,value,'preparer_id')
    if w.cancel_requested or w.status in ['verified','cancelled','followup_needed']:raise ValidationError('Go-live publication is stopped')
    d,data,_=source(w);v=document(w)
    if not v or v.pk!=version.pk or v.audience!='client':raise ValidationError('Exact observed client go-live version required')
    b=DeliveryDocumentBinding.objects.get(version=v)
    if b.data!=selected(data) or b.snapshot!=prerequisites(d,data):raise ValidationError('Go-live sources changed before publication')
    return {'factory_work_id':w.pk,'factory_policy_id':config.pk,'factory_source_id':w.source_head_id}

def verify(work,actor=None):
    d,data,v,p,receipts=published(work,actor)
    try:accepted=native.accepted_go_live(d)
    except (ValidationError,PermissionDenied) as exc:raise ValidationError('Await actual PM attestation of distinct PM and Client signature evidence: '+finding(exc)) from None
    if accepted.data['receipt_id'] not in [r.pk for r in receipts]:raise ValidationError('Actual PM and Client sign-off must cover this exact delivered document')
    return {'verified':True,'verification_scope':'synthetic_native_go_live_delivery_and_human_signature_attestation','head':work.source_head_id,
        'document_version':v.pk,'publication':p.pk,'receipt_ids':[r.pk for r in receipts],'acceptance':accepted.pk,
        'pm_signature':accepted.data['pm_signature_id'],'client_signature':accepted.data['client_signature_id'],
        'sign_off_inferred':False,'deployment_authorized':False,'financial_release_granted':False,'external_authenticity_verified':False}

@transaction.atomic
def review(actor,work_id,expected,case_expected,version_id,verdict,note):
    from .factory import access
    from apps.documents.controlled import review_version
    if any(type(pk) is not int or pk<1 for pk in [expected,case_expected,version_id]):raise ValidationError('Exact rendered versions required')
    w=Work.objects.select_for_update(of=('self',)).select_related('case','actor','source_head').get(pk=work_id,definition=DEFINITION)
    access(actor,w.case,'factory.read',DEFINITION);source(w,actor);v=document(w)
    if w.revision!=expected or w.cancel_requested or w.lease_until and w.lease_until>timezone.now() or not v or v.pk!=version_id:raise ValidationError('STALE_VERSION: refresh current go-live work')
    return review_version(actor,w.case_id,v.pk,verdict,note,case_expected)

@transaction.atomic
def accept(actor,work_id,expected,case_expected,version_id,receipt_id,pm_signature_id,client_signature_id,note,previous_acceptance_id=None):
    """Human-only console command. It is deliberately absent from agent dispatch."""
    from .factory import access
    if any(type(pk) is not int or pk<1 for pk in [expected,case_expected,version_id,receipt_id,pm_signature_id,client_signature_id]):raise ValidationError('Exact rendered versions, receipt and signature references required')
    w=Work.objects.select_for_update(of=('self',)).select_related('case','actor','source_head').get(pk=work_id,definition=DEFINITION)
    access(actor,w.case,'factory.read',DEFINITION);require(actor,w.case,'delivery.manage');source(w,actor)
    if w.revision!=expected or w.cancel_requested or w.lease_until and w.lease_until>timezone.now():raise ValidationError('STALE_VERSION: refresh current go-live work')
    d,data,v,p,receipts=published(w,actor)
    if version_id!=v.pk or receipt_id not in [r.pk for r in receipts]:raise ValidationError('Select an actual receipt of this exact current document')
    previous=native.latest_go_live(d,False)
    if previous:
        accepted=native.reaffirm_go_live(actor,w.case_id,d.pk,previous_acceptance_id,receipt_id,pm_signature_id,client_signature_id,note,case_expected)
    else:
        if previous_acceptance_id is not None:raise ValidationError('STALE_VERSION: this dossier has no prior acceptance to reaffirm')
        accepted=native.accept_go_live(actor,w.case_id,d.pk,receipt_id,pm_signature_id,client_signature_id,note,case_expected)
    w.status='ready';w.finding='Actual human sign-off recorded; verify the native evidence head';w.observation_hash='';w.revision+=1;w.save()
    event(actor,w.case,'factory.go_live_signoff_recorded',work=w.pk,acceptance=accepted.pk,previous=previous.pk if previous else None)
    return accepted

@transaction.atomic
def correct(actor,work_id,expected,case_expected,inputs,reason):
    from .factory import access
    if any(type(pk) is not int or pk<1 for pk in [expected,case_expected]):raise ValidationError('Exact rendered work and project versions required')
    w=Work.objects.select_for_update(of=('self',)).select_related('case','actor','source_head').get(pk=work_id,definition=DEFINITION)
    access(actor,w.case,'factory.manage',DEFINITION);case=lock_case(actor,w.case_id,'evidence.add',case_expected);w.case=case
    if w.revision!=expected or w.cancel_requested or w.status in ['cancelled','followup_needed']:raise ValidationError('STALE_VERSION: refresh current go-live work')
    if w.lease_until and w.lease_until>timezone.now() or PublicationJob.objects.filter(publication__factory_work=w,status__in=['pending','unknown','leased','held']).exists():raise ValidationError('Resolve the original delivery before correcting go-live sources')
    if not isinstance(reason,str) or not reason.strip() or len(reason)>2000:raise ValidationError('Explain the reviewed source correction in at most2000 characters')
    d,data,_=source(w,actor,current=False);delivery.dossier_for(case,d.pk);delivery.ensure_open(d);input_rows(case,inputs)
    if inputs==data['inputs']:
        v=document(w)
        if not v:raise ValidationError('Declare a genuine source or template correction')
        try:current_version(case,v.pk);published(w,actor)
        except (ValidationError,PermissionDenied):pass
        else:raise ValidationError('This document and its publication contract remain current; provide corrected evidence')
    old=w.source_head_id;w.source_head=capture(actor,case,d,inputs,'factory.go_live_source');w.status='ready';w.finding='';w.revision+=1;w.save()
    event(actor,case,'factory.go_live_corrected',work=w.pk,previous=old,current=w.source_head_id,reason=reason,spent=w.budget_used);return w

def reconcile(actor,work_id,expected,adapter=None):
    from .factory import access,cancellation_status
    from apps.documents.delivery import run_publication_once
    with transaction.atomic():
        w=Work.objects.select_for_update(of=('self',)).select_related('case').get(pk=work_id,definition=DEFINITION)
        access(actor,w.case,'factory.execute',DEFINITION)
        if actor.pk!=w.actor_id:require(actor,w.case,'factory.manage')
        if type(expected) is not int or w.revision!=expected or w.lease_until and w.lease_until>timezone.now():raise ValidationError('STALE_VERSION: refresh original go-live delivery')
        job=PublicationJob.objects.filter(publication__factory_work=w).filter(Q(status='unknown')|Q(status='leased',lease_until__lte=timezone.now())).order_by('pk').first()
        if not job:raise ValidationError('No original uncertain go-live delivery needs reconciliation')
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
    if any(type(pk) is not int or pk<1 for pk in [expected,case_expected,job_id]) or w.revision!=expected:raise ValidationError('STALE_VERSION: refresh exact go-live and project versions')
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
    if w.revision!=expected:raise ValidationError('STALE_VERSION: refresh current go-live work')
    if w.status in ['verified','followup_needed']:raise ValidationError('Delivered or accepted work requires native follow-up')
    if w.status=='cancelled':return w
    if not w.cancel_requested:w=manage(actor,w.pk,w.revision,'cancel')
    if w.lease_until and w.lease_until>timezone.now():return w
    w.status=cancellation_status(w);w.finding='Stopping work cannot undo an already delivered document or actual sign-off.'
    w.lease_until=None;w.revision+=1;w.save();return w

@transaction.atomic
def restart(actor,work_id,expected,case_expected,reason):
    from .factory import access
    if any(type(pk) is not int or pk<1 for pk in [expected,case_expected]):raise ValidationError('Exact rendered versions required')
    w=Work.objects.select_for_update(of=('self',)).select_related('case','actor','source_head').get(pk=work_id,definition=DEFINITION)
    access(actor,w.case,'factory.manage',DEFINITION);case=lock_case(actor,w.case_id,'evidence.add',case_expected);w.case=case
    if w.revision!=expected or w.status!='cancelled' or not w.cancel_requested:raise ValidationError('Only settled stopped preparation can receive a fresh instruction')
    if w.lease_until and w.lease_until>timezone.now() or PublicationJob.objects.filter(publication__factory_work=w,status__in=['pending','unknown','leased','held']).exists():raise ValidationError('Resolve original delivery before a fresh instruction')
    if PublicationReceipt.objects.filter(publication__factory_work=w).exists():raise ValidationError('Delivered documents require native follow-up, not a restart')
    if not isinstance(reason,str) or not reason.strip() or len(reason)>2000:raise ValidationError('Explain the fresh preparation instruction')
    d,data,_=source(w,actor,current=False);delivery.dossier_for(case,d.pk);delivery.ensure_open(d)
    old=w.source_head_id;w.source_head=capture(actor,case,d,data['inputs'],'factory.go_live_source');w.cancel_requested=False
    w.status='ready';w.finding='';w.lease_until=None;w.fence+=1;w.revision+=1;w.save()
    event(actor,case,'factory.go_live_restarted',work=w.pk,previous=old,current=w.source_head_id,reason=reason,spent=w.budget_used);return w

def projection(actor,work):
    from .factory import access,profile
    access(actor,work.case,'factory.read',DEFINITION);d,data,_=source(work,actor,current=False);v=document(work);p=publication(work,v)
    receipts=list(PublicationReceipt.objects.filter(publication=p).order_by('pk')) if p else []
    jobs=list(PublicationJob.objects.filter(publication__factory_work=work).order_by('pk'));issue='';changed=False;intake_current=True
    try:source(work,actor)
    except (ValidationError,PermissionDenied) as exc:issue=finding(exc);intake_current=False
    if intake_current:
        try:prerequisites(d,data)
        except (ValidationError,PermissionDenied) as exc:issue=finding(exc)
    if work.status=='verified':
        try:verify(work,actor=actor)
        except (ValidationError,PermissionDenied) as exc:changed=True;issue=finding(exc)
    live=not work.cancel_requested and not (work.lease_until and work.lease_until>timezone.now())
    previous=native.latest_go_live(d,False)
    pending_review=bool(v and HumanTask.objects.filter(version=v,status='open').exists());review_verdicts=[];can_accept=False;can_correct=False;can_restart=False
    if live:
        if pending_review and intake_current:
            try:
                current_version(work.case,v.pk);require(actor,work.case,'document.review_controlled')
                for verdict in ['approve','return','reject']:
                    try:decision_authority(actor,work.case,'PMO Lead',verdict);review_verdicts.append(verdict)
                    except (ValidationError,PermissionDenied):pass
            except (ValidationError,PermissionDenied):pass
        try:
            published(work,actor);require(actor,work.case,'delivery.manage');decision_authority(actor,work.case,'PM','reaffirm_go_live' if previous else 'approve');delivery.ensure_open(d)
            try:verify(work,actor=actor)
            except (ValidationError,PermissionDenied):can_accept=True
        except (ValidationError,PermissionDenied):pass
        try:
            require(actor,work.case,'factory.manage');require(actor,work.case,'evidence.add');delivery.ensure_open(d)
            can_correct=not any(j.status in ['pending','unknown','leased','held'] for j in jobs)
        except (ValidationError,PermissionDenied):pass
    if not (work.lease_until and work.lease_until>timezone.now()):
        try:
            require(actor,work.case,'factory.manage');require(actor,work.case,'evidence.add');delivery.ensure_open(d)
            can_restart=work.status=='cancelled' and work.cancel_requested and not any(j.status in ['pending','unknown','leased','held'] for j in jobs) and not receipts
        except (ValidationError,PermissionDenied):pass
    next_options=[];next_action=issue or 'Review current go-live preparation and human sign-off evidence'
    try:
        _,value=profile(work);state,*args=snapshot(work,value);next_options,next_action=eligible(work,value,state,*args)
    except (ValidationError,PermissionDenied):pass
    for job in jobs:
        job.can_cancel=job.can_retry=False
        try:
            require(actor,work.case,'document.operate')
            if work.lease_until and work.lease_until>timezone.now():continue
            if job.status in ['confirmed','cancelled'] or job.status=='leased' and job.lease_until and job.lease_until>timezone.now():continue
            if PublicationReceipt.objects.filter(publication=job.publication).exists():continue
            job.can_cancel=True
            if job.status=='held' and not work.cancel_requested:
                original=job.publication;publication_scope(original.actor,work.case,original.version,work.pk)
                current_version(work.case,original.version_id);r=validate_review(work.case,original.version);policies,recipients,_=publication_requirements(work.case,original.version)
                job.can_retry=original.policies==policies and original.recipient_ids==recipients and original.review_id==r.pk
        except (ValidationError,PermissionDenied):pass
    delivery_complete=False
    try:published(work,actor);delivery_complete=True
    except (ValidationError,PermissionDenied):pass
    accepted=previous
    if accepted and accepted.data['receipt_id'] not in [r.pk for r in receipts]:accepted=None
    return {'dossier':d,'data':data,'report':LocalDeliveryAdapter().read_go_live(d,selected(data),data['inputs']['template_id']),
        'document':v,'publication':p,'receipts':receipts,'delivery_complete':delivery_complete,'jobs':jobs,'acceptance':accepted,'previous_acceptance':previous,
        'finding':issue,'readiness_changed':changed,'intake_current':intake_current,'pending_review':pending_review,
        'review_names':[u.get_full_name() or u.username for u in owners(work.case,'PMO Lead','document.review_controlled')],
        'pm_names':[u.get_full_name() or u.username for u in attestation_owners(work,d)],
        'review_verdicts':review_verdicts,'can_accept':can_accept,'can_correct':can_correct,'can_restart':can_restart,
        'can_settle':work.cancel_requested and work.status not in ['cancelled','verified','followup_needed'] and not (work.lease_until and work.lease_until>timezone.now()),
        'next_options':next_options,'next_action':next_action}

def attempt_projection(attempt):
    allowed={'head','dossier','checks','observed_at','document_version','native_review_task','preparer','publication','publisher','verified','verification_scope',
        'receipt_ids','acceptance','pm_signature','client_signature','sign_off_inferred','deployment_authorized','financial_release_granted',
        'external_authenticity_verified','current_authority_checked','waiting'}
    return {k:v for k,v in attempt.result.items() if k in allowed}

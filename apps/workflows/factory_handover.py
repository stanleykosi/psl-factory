"""P37 native handover: scoped drafting/publication, then actual recipient receipt or gaps."""
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
from apps.identity.models import Grant
from apps.identity.services import require
from apps.documents.contracts import digest,validate
from apps.documents.models import Template,Publication,PublicationJob,PublicationReceipt
from apps.documents.controlled import current_version,validate_review,publication_requirements
from apps.pmo import delivery,delivery_closure as closure
from apps.pmo.delivery_documents import draft_delivery_document
from apps.pmo.models import DeliveryRecord,DeliveryDocumentBinding
from adapters.delivery import LocalDeliveryAdapter
from .models import FactoryWork as Work,FactoryActivity as Activity,FactoryAttempt as Attempt,HumanTask
from .factory_delivery import investigation_key

DEFINITION='delivery-handover/v1'
KIND='agent_private_handover_intake'
PROTOCOL='factory-handover-intake/v1'
FIELDS=['template_id','support_document','escalation_document']
ID={'anyOf':[{'type':'integer','minimum':1,'maximum':9223372036854775807},{'type':'null'}]}
INPUT={'type':'object','properties':{k:ID for k in FIELDS},'required':FIELDS,'additionalProperties':False}
SCHEMA={'type':'object','properties':{'protocol':{'const':PROTOCOL},'dossier_id':{'type':'integer','minimum':1},'inputs':INPUT},
    'required':['protocol','dossier_id','inputs'],'additionalProperties':False}


def finding_text(exc):return '; '.join(exc.messages) if isinstance(exc,ValidationError) else str(exc)


def input_rows(case,inputs):
    validate(INPUT,inputs)
    if any(pk is not None and type(pk) is not int for pk in inputs.values()):raise ValidationError('Exact integer references or unprovided values required')
    rows={e.pk:e for e in public_evidence(Evidence.objects.filter(case=case,pk__in=[inputs[k] for k in FIELDS[1:] if inputs[k] is not None]))}
    for kind in FIELDS[1:]:
        pk=inputs[kind]
        if pk is not None and (pk not in rows or rows[pk].kind!=kind):raise ValidationError('Choose this project public '+kind.replace('_',' ')+' evidence')
    if inputs['template_id'] is not None and not Template.objects.filter(case=case,pk=inputs['template_id'],definition__document_type='project_artifact').exists():raise ValidationError('Choose this project controlled project-artifact template')
    return rows


def source(work,actor=None,current=True):
    actor=actor or work.actor;require(actor,work.case,'delivery.read');e=work.source_head
    if not e or e.case_id!=work.case_id or e.kind!=KIND or e.sha256!=hashlib.sha256(e.body.encode()).hexdigest():raise ValidationError('Exact same-project handover intake required')
    try:data=json.loads(e.body)
    except (ValueError,TypeError):raise ValidationError('Typed handover intake required') from None
    validate(SCHEMA,data)
    audit=Audit.objects.filter(case=work.case,actor_id=e.created_by_id,action__in=['factory.handover_intake','factory.handover_source'],data={'evidence_id':e.pk,'sha256':e.sha256}).first()
    if not audit or data['dossier_id']!=work.request['dossier']:raise ValidationError('Native handover provenance and exact dossier required')
    if current:
        for action in ['delivery.read','evidence.add','factory.start' if audit.action=='factory.handover_intake' else 'factory.manage']:require(e.created_by,work.case,action)
    return delivery.dossier_for(work.case,data['dossier_id'],current=current),data,input_rows(work.case,data['inputs'])


def capture(actor,case,d,inputs,action):
    e=add_evidence(actor,case.pk,KIND,json.dumps({'protocol':PROTOCOL,'dossier_id':d.pk,'inputs':inputs},sort_keys=True),'psl:factory-handover-intake/v1')
    event(actor,case,action,evidence_id=e.pk,sha256=e.sha256);return e


@transaction.atomic
def start(actor,case_id,key,dossier_id,inputs,reference,expected=None):
    from .factory import access
    case=lock_case(actor,case_id,'factory.start',expected);access(actor,case,'factory.start',DEFINITION);require(actor,case,'evidence.add')
    if case.kind!='project':raise ValidationError('Project handover requires a project')
    if not isinstance(key,str) or not key.isascii() or not 1<=len(key)<=100 or not isinstance(reference,str) or not reference.strip() or len(reference)>160:raise ValidationError('Bounded handover identity and description required')
    d=delivery.dossier_for(case,dossier_id);delivery.ensure_open(d);input_rows(case,inputs)
    payload={'dossier':d.pk,'reference':reference};business=digest([str(case.pk),DEFINITION,d.candidate_id]);sha=digest(payload)
    old=Work.objects.filter(case=case).filter(Q(key=key)|Q(definition=DEFINITION,business_key=business)).first()
    if old:
        if old.actor_id!=actor.pk or old.definition!=DEFINITION or old.key==key and old.request_hash!=sha:raise ValidationError('IDEMPOTENCY_CONFLICT: changed handover intent')
        if source(old)[1]['inputs']!=inputs:raise ValidationError('Review changed inputs in the existing handover work')
        return old
    w=Work.objects.create(case=case,actor=actor,key=key,definition=DEFINITION,request=payload,request_hash=sha,business_key=business,
        source_head=capture(actor,case,d,inputs,'factory.handover_intake'))
    event(actor,case,'factory.started',work=w.pk,definition=DEFINITION);return w


def document(work):
    pk=Attempt.objects.filter(activity__work=work,phase='observed',result__head=work.source_head_id,result__has_key='document_version').order_by('-pk').values_list('result__document_version',flat=True).first()
    binding=DeliveryDocumentBinding.objects.select_related('version__document','version__template').filter(version_id=pk,dossier_id=work.request['dossier'],purpose='handover').first()
    return binding.version if binding else None


def publisher(work,value):
    user=get_user_model().objects.filter(pk=value['executor_id'],is_active=True).first()
    if not user:raise ValidationError('owner_needed: Configure the authorised handover publisher')
    try:
        for action in ['case.read','delivery.read','factory.execute','document.publish']:require(user,work.case,action)
    except PermissionDenied:raise ValidationError('owner_needed: Handover publisher no longer has current project permissions') from None
    return user


def prerequisites(d,data):
    if any(data['inputs'][k] is None for k in FIELDS):raise ValidationError('Provide the controlled template, support document and escalation document')
    return closure.handover_inputs(d,{k:data['inputs'][k] for k in FIELDS[1:]})


def receipt_state(work,version):
    p=Publication.objects.filter(version=version).first() if version else None
    receipts=list(PublicationReceipt.objects.filter(publication=p).order_by('pk')) if p else []
    rows=[]
    for r in receipts:
        ack=DeliveryRecord.objects.filter(dossier_id=work.request['dossier'],kind='handover',data__receipt_id=r.pk).order_by('-pk').first()
        rows.append({'receipt':r,'ack':ack})
    return p,rows


def snapshot(work,value,reader=None):
    from .factory import access
    actor=reader or work.execution_actor
    access(actor,work.case,'factory.read' if reader is not None else 'factory.execute',DEFINITION);d,data,chosen=source(work,actor)
    native=LocalDeliveryAdapter().read_current(d)
    records=public_evidence(Evidence.objects.filter(case=work.case,pk__in=set(native['source_evidence_ids'])|set(chosen))).order_by('pk')
    latest={KIND:work.source_head}
    for e in records:
        if e.kind not in latest or e.version>latest[e.kind].version:latest[e.kind]=e
    missing=[k for k in value['required_evidence_kinds'] if k not in latest]
    stale=[k for k in value['required_evidence_kinds'] if k in latest and latest[k].created_at<timezone.now()-timedelta(seconds=value['max_age_seconds'])]
    stale+=['input:'+e.kind for e in chosen.values() if e.created_at<timezone.now()-timedelta(seconds=value['max_age_seconds'])]
    try:inputs=prerequisites(d,data);checks={'status':'ready','inputs':inputs}
    except (ValidationError,PermissionDenied) as exc:checks={'status':'held','finding':finding_text(exc)}
    v=document(work);p,receipts=receipt_state(work,v);jobs=list(PublicationJob.objects.filter(publication__factory_work=work).order_by('pk'))
    review={'status':'unprepared'}
    if v:
        try:current_version(work.case,v.pk);r=validate_review(work.case,v);review={'status':'ready','id':r.pk if r else None}
        except (ValidationError,PermissionDenied) as exc:review={'status':'held','finding':finding_text(exc)}
    state={'case_revision':work.case.revision,'profile':work.policy_id,'sources':[(e.pk,e.sha256) for e in latest.values()],
        'native':native,'checks':checks,'document':v.pk if v else None,'review':review,'publication':p.pk if p else None,
        'jobs':[(j.pk,j.status) for j in jobs],'receipts':[(x['receipt'].pk,x['receipt'].payload_sha256,x['ack'].pk if x['ack'] else None,x['ack'].data['status'] if x['ack'] else None) for x in receipts]}
    state['hash']=digest(state);state['work_revision']=work.revision
    return state,latest,missing,stale,[],jobs


def pending_job(jobs):
    return next((j for j in jobs if j.status in ['pending','unknown'] or j.status=='leased' and j.lease_until and j.lease_until<=timezone.now()),None)


def eligible(work,value,state,latest,missing,stale,tasks,jobs):
    # Resolve original effects before preparing any replacement or claiming business completion.
    pending=pending_job(jobs)
    if pending:return ['ACT11' if pending.status=='pending' else 'ACT12'],'Deliver the exact recorded handover' if pending.status=='pending' else 'Reconcile the original handover receipt'
    if any(j.status in ['held','leased'] for j in jobs):return [],'Review the original handover delivery before continuing'
    if not Activity.objects.filter(work=work,key=investigation_key(work,state),status='succeeded').exists():return ['ACT04'],'Investigate archive, support and escalation evidence'
    if missing or stale:return [],'Current required handover evidence is missing or stale: '+', '.join(missing+stale)
    if state['checks']['status']!='ready':return [],state['checks']['finding']
    if not state['document']:return ['ACT09'],'Prepare the native controlled handover package'
    v=document(work)
    if v.template.definition.get('internal_review_required') is not False and not HumanTask.objects.filter(version=v).exists():
        try:current_version(work.case,v.pk)
        except (ValidationError,PermissionDenied) as exc:return [],finding_text(exc)
        return ['ACT09'],'Request the configured review for the existing exact handover draft'
    if state['review']['status']!='ready':return [],'Review the current controlled document or correct its cited prerequisites'
    if not state['publication']:return ['ACT11'],'Reserve exact current internal publication under the configured publisher'
    try:verify(work,actor=work.execution_actor)
    except (ValidationError,PermissionDenied) as exc:return [],finding_text(exc)
    return ['ACT13'],'Verify every actual recipient acknowledgement against current handover evidence'


def act(work,choice,value,latest,missing,tasks,jobs):
    from .factory import access
    case=lock_case(work.execution_actor,work.case_id,'factory.execute');access(work.execution_actor,case,'factory.execute',DEFINITION)
    list(Grant.objects.select_for_update().filter(case=case).order_by('pk'))
    if case.revision!=work.case.revision:raise ValidationError('STALE_VERSION: handover changed while planning')
    d,data,_=source(work,work.execution_actor);kind=choice['activity']
    if kind=='ACT04':return {'head':work.source_head_id,'dossier':d.pk,'source_refs':sorted(latest[k].pk for k in latest),'separate_handover_approval':False}
    if kind=='ACT09':
        prerequisites(d,data)
        v=document(work)
        if not v:v=draft_delivery_document(work.execution_actor,case.pk,d.pk,'handover',data['inputs']['template_id'],{k:data['inputs'][k] for k in FIELDS[1:]},case.revision)
        task=None;waiting=None
        if v.template.definition.get('internal_review_required') is not False and not HumanTask.objects.filter(version=v).exists():
            from apps.documents.controlled import request_review
            try:current_version(case,v.pk)
            except (ValidationError,PermissionDenied):waiting='The draft is retained. Review its current recipient and source requirements before requesting the configured document review.'
            else:
                case.refresh_from_db();task=request_review(work.execution_actor,case.pk,v.pk,case.revision)
        result={'head':work.source_head_id,'document_version':v.pk,'native_review_task':task.pk if task else None,'separate_handover_approval':False}
        if waiting:result['waiting']=waiting
        return result
    if kind in ['ACT11','ACT12']:
        job=pending_job(jobs)
        if job:return {'head':work.source_head_id,'publication_job':job.pk}
        if kind=='ACT12':raise ValidationError('No original uncertain handover delivery exists')
        from apps.documents.controlled import reserve_publication
        v=document(work);user=publisher(work,value)
        if not v:raise ValidationError('Exact native handover document required')
        p=reserve_publication(user,case.pk,v.pk,case.revision,factory_work_id=work.pk)
        return {'head':work.source_head_id,'publication':p.pk,'publisher':user.pk}
    if kind=='ACT13':result=verify(work,actor=work.execution_actor);work.status='verified';return result
    raise ValidationError('FORBIDDEN: unregistered handover activity')


def publication_scope(actor,case,version,work_id):
    from .factory import access,profile
    w=Work.objects.select_related('actor','case','source_head').filter(pk=work_id,case=case,definition=DEFINITION).first()
    if not w:raise ValidationError('Exact handover factory work required')
    access(actor,case,'factory.execute',DEFINITION);config,value=profile(w)
    if w.policy_id!=config.pk or publisher(w,value).pk!=actor.pk:raise PermissionDenied('Current exact handover publisher and profile required')
    if w.cancel_requested or w.status in ['verified','cancelled','followup_needed']:raise ValidationError('Handover publication is stopped')
    d,data,_=source(w);prerequisites(d,data);expected=document(w)
    if not expected or expected.pk!=version.pk:raise ValidationError('Exact observed source-bound handover version required')
    binding=DeliveryDocumentBinding.objects.get(version=version)
    if binding.data!={k:data['inputs'][k] for k in FIELDS[1:]} or binding.snapshot!=prerequisites(d,data):raise ValidationError('Handover sources changed before publication')
    return {'factory_work_id':w.pk,'factory_policy_id':config.pk,'factory_source_id':w.source_head_id}


def verify(work,actor=None):
    d,data,_=source(work,actor);prerequisites(d,data);v=document(work)
    if not v:raise ValidationError('Exact prepared handover document required')
    current_version(work.case,v.pk);review=validate_review(work.case,v);p,rows=receipt_state(work,v)
    policies,recipients,retention=publication_requirements(work.case,v)
    if not p or p.factory_work_id!=work.pk or p.factory_source_id!=work.source_head_id:raise ValidationError('Exact source-bound native handover publication required')
    if p.policies!=policies or p.recipient_ids!=recipients or p.retention_days!=retention or p.review_id!=(review.pk if review else None):raise ValidationError('Handover audience, review or policy changed; review a current package')
    if {x['receipt'].recipient_id for x in rows}!=set(recipients) or not rows:raise ValidationError('Every exact recipient delivery receipt is required')
    binding=DeliveryDocumentBinding.objects.get(version=v);acks=[]
    for item in rows:
        r=item['receipt'];ack=item['ack']
        if r.payload!=v.payload or r.payload_sha256!=v.payload_sha256:raise ValidationError('Exact handover receipt payload required')
        if not ack or ack.actor_id!=r.recipient_id or ack.data['status']!='received' or ack.snapshot!=binding.snapshot:raise ValidationError('Support/Operations must record actual receipt and resolve any handover gaps')
        for action in ['delivery.support_receive','document.receive:internal']:require(ack.actor,work.case,action)
        acks.append(ack.pk)
    return {'verified':True,'verification_scope':'synthetic_native_handover_and_actual_recipient_acknowledgement','head':work.source_head_id,
        'document_version':v.pk,'publication':p.pk,'receipt_ids':[x['receipt'].pk for x in rows],'handover_ids':acks,
        'separate_handover_approval':False,'closure_approved':False,'financial_release_granted':False,'deployment_authorized':False,'external_authenticity_verified':False}


@transaction.atomic
def correct(actor,work_id,expected,case_expected,inputs,reason):
    from .factory import access
    if type(expected) is not int or type(case_expected) is not int:raise ValidationError('Exact work and project versions required')
    w=Work.objects.select_for_update(of=('self',)).select_related('case','actor','source_head').get(pk=work_id,definition=DEFINITION)
    access(actor,w.case,'factory.manage',DEFINITION);case=lock_case(actor,w.case_id,'evidence.add',case_expected);w.case=case
    list(Grant.objects.select_for_update().filter(case=case).order_by('pk'))
    if w.revision!=expected or w.cancel_requested or w.status in ['cancelled','followup_needed']:raise ValidationError('STALE_VERSION: refresh current handover work')
    if w.lease_until and w.lease_until>timezone.now() or PublicationJob.objects.filter(publication__factory_work=w,status__in=['pending','unknown','leased','held']).exists():raise ValidationError('Resolve original delivery and stop the current worker before changing handover inputs')
    if not isinstance(reason,str) or not reason.strip() or len(reason)>2000:raise ValidationError('Explain the source correction in at most2000 characters')
    d,data,_=source(w,actor,current=False);delivery.dossier_for(case,d.pk);delivery.ensure_open(d);input_rows(case,inputs)
    if data['inputs']==inputs:
        v=document(w)
        if not v:raise ValidationError('Declare a genuine source or template correction')
        refresh_needed=False
        try:source(w);current_version(case,v.pk)
        except (ValidationError,PermissionDenied):refresh_needed=True
        p=Publication.objects.filter(version=v).first()
        if p and not refresh_needed:
            refresh_needed=p.job.status=='cancelled' and not PublicationReceipt.objects.filter(publication=p).exists()
            try:
                review=validate_review(case,v);policies,recipients,retention=publication_requirements(case,v)
                refresh_needed=refresh_needed or p.policies!=policies or p.recipient_ids!=recipients or p.retention_days!=retention or p.review_id!=(review.pk if review else None)
            except (ValidationError,PermissionDenied):refresh_needed=True
        if not refresh_needed:raise ValidationError('Declare a genuine source or template correction; this document and its publication contract remain current')
    previous=w.source_head_id;w.source_head=capture(actor,case,d,inputs,'factory.handover_source');w.status='ready';w.finding='';w.revision+=1;w.save()
    event(actor,case,'factory.handover_corrected',work=w.pk,previous=previous,current=w.source_head_id,reason=reason,spent=w.budget_used);return w


@transaction.atomic
def acknowledge(actor,work_id,expected,case_expected,receipt_id,status,evidence_id,note):
    from .factory import access
    w=Work.objects.select_for_update(of=('self',)).select_related('case','actor','source_head').get(pk=work_id,definition=DEFINITION)
    access(actor,w.case,envelope=DEFINITION)
    if any(type(n) is not int or n<1 for n in [expected,case_expected,receipt_id,evidence_id]) or w.revision!=expected:raise ValidationError('STALE_VERSION: refresh the exact handover work and project versions')
    v=document(w)
    if not v or not PublicationReceipt.objects.filter(pk=receipt_id,recipient=actor,publication__version=v,publication__factory_work=w,publication__factory_source=w.source_head).exists():raise ValidationError('Select your own exact current handover receipt')
    return closure.acknowledge_handover(actor,w.case_id,w.request['dossier'],receipt_id,status,evidence_id,note,case_expected)


@transaction.atomic
def review(actor,work_id,expected,case_expected,version_id,verdict,note):
    from .factory import access
    from apps.documents.controlled import review_version
    w=Work.objects.select_for_update(of=('self',)).select_related('case','actor','source_head').get(pk=work_id,definition=DEFINITION)
    access(actor,w.case,envelope=DEFINITION);v=document(w)
    if any(type(n) is not int or n<1 for n in [expected,case_expected,version_id]) or w.revision!=expected or w.cancel_requested or not v or v.pk!=version_id:raise ValidationError('STALE_VERSION: review this exact current handover version')
    current_version(w.case,v.pk)
    return review_version(actor,w.case_id,v.pk,verdict,note,case_expected)


def reconcile(actor,work_id,expected):
    from .factory import access,cancellation_status
    from apps.documents.delivery import run_publication_once
    with transaction.atomic():
        w=Work.objects.select_for_update(of=('self',)).select_related('case').get(pk=work_id,definition=DEFINITION)
        access(actor,w.case,'factory.execute',DEFINITION)
        if actor.pk!=w.actor_id:require(actor,w.case,'factory.manage')
        if w.revision!=expected or w.lease_until and w.lease_until>timezone.now():raise ValidationError('STALE_VERSION: refresh after the current worker stops')
        job=PublicationJob.objects.filter(publication__factory_work=w).filter(Q(status='unknown')|Q(status='leased',lease_until__lte=timezone.now())).order_by('pk').first()
        if not job:raise ValidationError('No original uncertain handover delivery to reconcile')
        event(actor,w.case,'factory.reconciliation_requested',work=w.pk,publication_job=job.pk)
    run_publication_once(case_id=w.case_id,job_id=job.pk)
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
    access(actor,w.case,envelope=DEFINITION);require(actor,w.case,'document.operate')
    if any(type(n) is not int or n<1 for n in [expected,case_expected,job_id]) or w.revision!=expected:raise ValidationError('STALE_VERSION: refresh the exact handover and project versions')
    if w.lease_until and w.lease_until>timezone.now():raise ValidationError('Wait for the current worker before operating its delivery')
    if not PublicationJob.objects.filter(pk=job_id,publication__factory_work=w).exists():raise ValidationError('Select this handover original delivery')
    if action not in ['cancel','retry'] or not isinstance(reason,str):raise ValidationError('Choose a native delivery recovery action and explain it')
    job=operate_publication(actor,w.case_id,job_id,action,reason,case_expected)
    w.status=cancellation_status(w) if w.cancel_requested else 'ready' if action=='retry' else 'blocked'
    w.finding='' if action=='retry' else 'Delivery cancelled. Review a current source package before creating another publication.'
    w.observation_hash='';w.revision+=1;w.save();return w


def projection(actor,work):
    from .factory import access
    access(actor,work.case,envelope=DEFINITION);d,data,rows=source(work,actor,current=False);v=document(work);p,receipts=receipt_state(work,v)
    finding='';changed=False
    try:source(work,actor);prerequisites(d,data)
    except (ValidationError,PermissionDenied) as exc:finding=finding_text(exc)
    if work.status=='verified':
        try:verify(work,actor=actor)
        except (ValidationError,PermissionDenied) as exc:changed=True;finding=finding_text(exc)
    can_correct=False
    try:
        require(actor,work.case,'factory.manage');require(actor,work.case,'evidence.add');delivery.ensure_open(d)
        can_correct=not work.cancel_requested and work.status not in ['cancelled','followup_needed'] and not (work.lease_until and work.lease_until>timezone.now()) and not PublicationJob.objects.filter(publication__factory_work=work,status__in=['pending','unknown','leased','held']).exists()
    except (ValidationError,PermissionDenied):pass
    for item in receipts:
        item['can_ack']=False
        if item['receipt'].recipient_id==actor.pk:
            try:
                require(actor,work.case,'delivery.support_receive');require(actor,work.case,'document.receive:internal');current_version(work.case,v.pk);item['can_ack']=True
            except (ValidationError,PermissionDenied):pass
    can_review=False;review_pending=bool(v and HumanTask.objects.filter(version=v,status='open').exists());review_owners=[]
    if review_pending:
        try:
            from apps.policy.services import active_component,reference_values,decision_authority
            ids={r['user_id'] for r in reference_values(active_component('D05.role_principal_assignments',work.case)) if r['role']=='PMO Lead'}
            for user in get_user_model().objects.filter(pk__in=ids,is_active=True).order_by('pk'):
                try:require(user,work.case,'document.review_controlled');decision_authority(user,work.case,'PMO Lead','approve');review_owners.append(user.get_full_name() or user.username)
                except (ValidationError,PermissionDenied):pass
        except (ValidationError,PermissionDenied):pass
    if review_pending and not work.cancel_requested:
        try:
            from apps.policy.services import decision_authority
            require(actor,work.case,'document.review_controlled');decision_authority(actor,work.case,'PMO Lead','approve');current_version(work.case,v.pk);can_review=True
        except (ValidationError,PermissionDenied):pass
    publication_current=True
    if p:
        try:
            current_version(work.case,v.pk);review=validate_review(work.case,v);policies,recipients,retention=publication_requirements(work.case,v)
            publication_current=p.policies==policies and p.recipient_ids==recipients and p.retention_days==retention and p.review_id==(review.pk if review else None)
            if not publication_current:finding='The document review, recipient or publication policy changed. Review a fresh current package.'
        except (ValidationError,PermissionDenied) as exc:publication_current=False;finding=finding_text(exc)
    pending_owners=[]
    for item in receipts:
        if item['ack'] and item['ack'].data['status']=='received':continue
        user=item['receipt'].recipient
        if not user.is_active:continue
        try:
            require(user,work.case,'delivery.support_receive');require(user,work.case,'document.receive:internal')
            pending_owners.append(user.get_full_name() or user.username)
        except PermissionDenied:pass
    jobs=list(PublicationJob.objects.filter(publication__factory_work=work).select_related('publication__version__document').order_by('pk'))
    for job in jobs:
        job.can_cancel=job.can_retry=False
        try:
            require(actor,work.case,'document.operate')
            if work.lease_until and work.lease_until>timezone.now():continue
            if job.status in ['confirmed','cancelled'] or job.status=='leased' and job.lease_until and job.lease_until>timezone.now():continue
            if PublicationReceipt.objects.filter(publication=job.publication).exists():continue
            job.can_cancel=True
            if job.status=='held' and not work.cancel_requested:
                p=job.publication;publication_scope(p.actor,work.case,p.version,work.pk)
                current_version(work.case,p.version_id);review=validate_review(work.case,p.version);policies,recipients,_=publication_requirements(work.case,p.version)
                job.can_retry=p.policies==policies and p.recipient_ids==recipients and p.review_id==(review.pk if review else None)
        except (ValidationError,PermissionDenied):pass
    return {'dossier':d,'data':data,'inputs':[{'kind':k,'evidence':rows.get(data['inputs'][k]),'missing':data['inputs'][k] is None} for k in FIELDS[1:]],
        'document':v,'publication':p,'receipts':receipts,'finding':finding,'readiness_changed':changed,'can_correct':can_correct,
        'can_review':can_review,'review_pending':review_pending,'review_owner_names':review_owners,'pending_owner_names':pending_owners,
        'publication_current':publication_current,'jobs':jobs}


def attempt_projection(attempt):
    allowed={'head','dossier','source_refs','document_version','native_review_task','publication','publisher','publication_job','verified','verification_scope',
        'receipt_ids','handover_ids','separate_handover_approval','closure_approved','financial_release_granted','deployment_authorized','external_authenticity_verified'}
    return {k:v for k,v in attempt.result.items() if k in allowed}

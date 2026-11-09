"""P40/P42 selected internal leadership report; native source/review/receipt truth stays authoritative."""
import hashlib,json
from datetime import timedelta, timezone as datetime_timezone
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied,ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from apps.core.models import Audit,Evidence
from apps.core.services import lock_case,add_evidence,event
from apps.core.read_observation import read_observation
from apps.identity.services import require
from apps.identity.models import Grant
from apps.documents.contracts import digest,validate
from apps.documents.models import Template,Publication,PublicationJob,PublicationReceipt
from apps.documents.controlled import current_version,validate_review,publication_requirements
from apps.pmo.clocks import aware
from apps.pmo.reporting import report_source_access
from apps.pmo import leadership_reporting as native
from apps.pmo.models import MinutesReportBinding
from adapters.pmo_reporting import LocalPMOReportingAdapter
from .models import FactoryWork as Work,FactoryActivity as Activity,FactoryAttempt as Attempt,HumanTask
from .factory_delivery import investigation_key
from .factory_handover import pending_job

DEFINITION='pmo-leadership-report/v1'
KIND='agent_private_leadership_intake'
PROTOCOL='factory-leadership-report-intake/v1'
ID={'anyOf':[{'type':'integer','minimum':1,'maximum':9223372036854775807},{'type':'null'}]}
INPUT={'type':'object','properties':{'template_id':ID,'content_id':ID,'start_at':{'type':'string','maxLength':64},'end_at':{'type':'string','maxLength':64}},'required':['template_id','content_id','start_at','end_at'],'additionalProperties':False}
SCHEMA={'type':'object','properties':{'protocol':{'const':PROTOCOL},'inputs':INPUT,'manifest':{'type':'object'},'captured_at':{'type':'string'}},'required':['protocol','inputs','manifest','captured_at'],'additionalProperties':False}
DOMAINS={key:{'type':'array','maxItems':200,'uniqueItems':True,'items':{'type':'integer','minimum':1}} for key in native.DOMAINS}
INPUT['properties'].update(kind={'enum':list(native.THEMES)},audience={'enum':['internal','management']},selections={'type':'object','properties':DOMAINS,'required':list(DOMAINS),'additionalProperties':False})
INPUT['required']+=['kind','audience','selections']

def finding(exc):return '; '.join(exc.messages) if isinstance(exc,ValidationError) else str(exc)

def input_rows(case,inputs):
    validate(INPUT,inputs)
    for name in ['template_id','content_id']:
        if inputs[name] is not None and type(inputs[name]) is not int:raise ValidationError('Exact selected identifier or explicit unprovided value required')
    start,end=native.window(inputs['kind'],inputs['start_at'],inputs['end_at'],inputs['audience'])
    if inputs['content_id'] is not None and not Evidence.objects.filter(case=case,pk=inputs['content_id'],kind=native.CONTENT).exists():raise ValidationError('Choose this project human leadership narrative')
    if inputs['template_id'] is not None:
        t=Template.objects.filter(case=case,pk=inputs['template_id'],definition__document_type='status_report').first()
        required={'executive_summary',*native.THEMES[inputs['kind']]}
        if not t or t.definition.get('internal_review_required') != (inputs['kind']=='monthly_executive') or set(t.definition['required_fields'])!=required or set(t.definition['audience_fields'].get(inputs['audience'],[]))!=required:raise ValidationError('Choose the exact leadership theme template with mandatory configured human review')
    return start.astimezone(datetime_timezone.utc),end.astimezone(datetime_timezone.utc)

def inventory(actor,case,inputs):
    start,end=input_rows(case,inputs)
    manifest,sources,gaps=native.inventory(actor,case,start,end,inputs['selections'])
    content=Evidence.objects.filter(case=case,pk=inputs['content_id'],kind=native.CONTENT).first()
    manifest.update(source_mode=native.MODE,selections={k:sorted(ids) for k,ids in inputs['selections'].items()},content={'id':content.pk,'sha256':content.sha256} if content else None)
    if content:
        _, sections = native.content(case, inputs['kind'], content.pk, sources)
        from apps.pmo.incident_reporting import bind
        bind(actor, case, manifest, sections)
    return {'manifest':manifest,'sources':sources,'gaps':gaps}

def source(work,actor=None,current=True):
    reader=actor or work.actor;require(reader,work.case,'report.read');e=work.source_head
    if not e or e.case_id!=work.case_id or e.kind!=KIND or e.sha256!=hashlib.sha256(e.body.encode()).hexdigest():raise ValidationError('Exact private leadership reporting intake required')
    try:data=json.loads(e.body)
    except (TypeError,ValueError):raise ValidationError('Typed leadership report intake required') from None
    validate(SCHEMA,data);input_rows(work.case,data['inputs'])
    report_source_access(reader,work.case,data['manifest'])
    if data['manifest'].get('content') and 'incident_claims' not in data['manifest']:
        from apps.pmo.incident_reporting import legacy_access
        legacy_access(reader, work.case, data['manifest'], e.created_at)
    for action in data['manifest'].get('source_actions',[]):require(reader,work.case,action)
    native.authorize_sources(reader,work.case,{r['id'] for r in data['manifest']['sources']},{row[2] for row in data['manifest'].get('changes',[])})
    audit=Audit.objects.filter(case=work.case,actor_id=e.created_by_id,action__in=['factory.leadership_intake','factory.leadership_source'],data={'evidence_id':e.pk,'sha256':e.sha256}).first()
    if not audit or any(data['inputs'][k]!=work.request[k] for k in ['start_at','end_at','kind','audience']):raise ValidationError('Exact selected report period and source-owned provenance required')
    if current:
        for action in ['case.read','report.read','evidence.add','factory.start' if audit.action=='factory.leadership_intake' else 'factory.manage']:require(e.created_by,work.case,action)
        if inventory(reader,work.case,data['inputs'])['manifest']!=data['manifest']:raise ValidationError('Selected native report inventory changed; explicitly review the current source snapshot')
    return data

def capture(actor,case,inputs,action):
    snapshot=inventory(actor,case,inputs)
    value={'protocol':PROTOCOL,'inputs':inputs,'manifest':snapshot['manifest'],'captured_at':timezone.now().isoformat()}
    e=add_evidence(actor,case.pk,KIND,json.dumps(value,sort_keys=True),'psl:'+PROTOCOL)
    event(actor,case,action,evidence_id=e.pk,sha256=e.sha256);return e

@transaction.atomic
def start(actor,case_id,key,inputs,reference,expected=None):
    from .factory import access
    case=lock_case(actor,case_id,'factory.start',expected);access(actor,case,'factory.start',DEFINITION);require(actor,case,'evidence.add')
    if case.kind!='project' or not isinstance(key,str) or not key.isascii() or not 1<=len(key)<=100 or not isinstance(reference,str) or not reference.strip() or len(reference)>160:raise ValidationError('Project and bounded report work identity required')
    start,end=input_rows(case,inputs)
    inputs=dict(inputs,start_at=start.isoformat(),end_at=end.isoformat())
    payload={k:inputs[k] for k in ['start_at','end_at','kind','audience']};payload['reference']=reference
    sha=digest(payload);business=digest([str(case.pk),DEFINITION,inputs['kind'],inputs['audience'],start.isoformat(),end.isoformat()])
    old=Work.objects.filter(case=case).filter(Q(key=key)|Q(definition=DEFINITION,business_key=business)).first()
    if old:
        if old.actor_id!=actor.pk or old.definition!=DEFINITION or old.key==key and old.request_hash!=sha:raise ValidationError('IDEMPOTENCY_CONFLICT: changed leadership report intent')
        if source(old,actor)['inputs']!=inputs:raise ValidationError('Review changed selections in the existing leadership reporting work')
        return old
    w=Work.objects.create(case=case,actor=actor,key=key,definition=DEFINITION,request=payload,request_hash=sha,business_key=business,source_head=capture(actor,case,inputs,'factory.leadership_intake'))
    event(actor,case,'factory.started',work=w.pk,definition=DEFINITION);return w

def document(work):
    pk=Attempt.objects.filter(activity__work=work,phase='observed',result__head=work.source_head_id,result__has_key='document_version').order_by('-pk').values_list('result__document_version',flat=True).first()
    b=MinutesReportBinding.objects.select_related('version__document','version__template','report').filter(version_id=pk,report__case=work.case,report__kind=work.request['kind'],report__audience=work.request['audience']).first()
    return b.version if b else None

def principal(work,value,name):
    u=get_user_model().objects.filter(pk=value[name],is_active=True).first()
    if not u:raise ValidationError('owner_needed: Configure current leadership report '+name.replace('_id',''))
    actions=['case.read','report.read','factory.execute']+(['report.draft','document.draft','evidence.add']+(['document.request_review'] if work.request['kind']=='monthly_executive' else []) if name=='preparer_id' else ['document.publish'])
    try:
        for action in actions:require(u,work.case,action)
    except PermissionDenied:raise ValidationError('owner_needed: Leadership report principal lacks current exact project permissions') from None
    return u

def bound_document(work,actor=None):
    reader=actor or work.actor;data=source(work,reader);v=document(work)
    if not v:raise ValidationError('Await exact native leadership report draft')
    b=MinutesReportBinding.objects.get(version=v);inputs=data['inputs'];start,end=input_rows(work.case,inputs)
    native.binding_access(reader,v)
    if b.report.start_at!=start or b.report.end_at!=end or b.manifest!=data['manifest'] or v.template_id!=inputs['template_id'] or v.audience!=inputs['audience']:raise ValidationError('Exact leadership period, audience, template and selected sources required')
    manifest,sources,gaps,sections=native.package(reader,work.case,inputs['kind'],start,end,inputs['audience'],inputs['selections'],inputs['content_id'])
    expected={'executive_summary',*native.THEMES[inputs['kind']]}
    projection=Evidence.objects.filter(case=work.case,pk__in=[x['id'] for x in v.source_manifest],kind='ops_leadership_report_projection',source='psl:leadership-report:'+str(b.report_id),created_by_id=v.created_by_id).first()
    if manifest!=b.manifest or {x['heading'] for x in v.payload['sections']}!=expected or set(v.fields)!=expected or not projection or len(v.source_manifest)!=1 or any(x['evidence_ids']!=[projection.pk] for x in v.fields.values()) or any(v.fields.get(k,{}).get('text')!='['+x['coverage']+'] '+x['text'] for k,x in sections.items()):raise ValidationError('Exact human-cited themes and generated-only internal projection required')
    if json.loads(projection.body)!={k:x['text'] for k,x in v.fields.items()}:raise ValidationError('Native generated projection does not match retained fields')
    current_version(work.case,v.pk);return data,v,b

def published(work,actor=None):
    from .factory import profile
    data,v,b=bound_document(work,actor);review=validate_review(work.case,v)
    policies,recipients,retention=publication_requirements(work.case,v)
    config,value=profile(work,recovery=True);principal(work,value,'preparer_id');u=principal(work,value,'executor_id')
    p=Publication.objects.filter(version=v,factory_work=work,factory_source=work.source_head,factory_policy=config,actor=u).first()
    if not p or p.policies!=policies or p.recipient_ids!=recipients or p.retention_days!=retention or p.review_id!=(review.pk if review else None):raise ValidationError('Await current exact reviewed leadership report publication and recipient contract')
    receipts=list(PublicationReceipt.objects.filter(publication=p).order_by('pk'))
    if p.job.status!='confirmed' or not receipts or {r.recipient_id for r in receipts}!=set(recipients) or any(r.payload!=v.payload or r.payload_sha256!=v.payload_sha256 for r in receipts):raise ValidationError('Every exact required client recipient receipt is required')
    return data,v,b,p,receipts

def investigate(work,actor):
    data=source(work,actor,current=False);inputs=data['inputs'];snapshot=inventory(actor,work.case,inputs)
    result={'capability':'A06/A07/A08 selected leadership source coverage','source_head':work.source_head_id,
        'manifest':snapshot['manifest'],'selected_inventory_current':snapshot['manifest']==data['manifest'],
        'commitment_gaps':snapshot['gaps'],'approval_granted':False,'communications_dispatched':False,
        'coverage':'Only explicitly selected native PMO sources. Raw bodies, unselected histories, Finance performance and external systems are not inferred.',
        'next_action':'Resolve missing cited themes, review selected source freshness and obtain configured exact leadership review before internal delivery.'}
    try:
        detail=native.investigate(actor,work.case,inputs['kind'],inputs['start_at'],inputs['end_at'],inputs['audience'],inputs['selections'],inputs['content_id'])
        result.update(detail);result['narrative']={'status':'cited','themes':detail['themes']}
    except ValidationError as exc:result['narrative']={'status':'missing','finding':finding(exc)}
    return result

@read_observation
def snapshot(work,value,reader=None):
    from .factory import access
    actor=reader or work.execution_actor;access(actor,work.case,'factory.read' if reader is not None else 'factory.execute',DEFINITION)
    data=source(work,actor,False);current=True;issue=''
    try:source(work,actor)
    except (ValidationError,PermissionDenied) as exc:current=False;issue=finding(exc)
    latest={KIND:work.source_head};missing=[k for k in value['required_evidence_kinds'] if k not in latest]
    stale=[k for k in value['required_evidence_kinds'] if k in latest and latest[k].created_at<timezone.now()-timedelta(seconds=value['max_age_seconds'])]
    jobs=list(PublicationJob.objects.filter(publication__factory_work=work).order_by('pk'));v=document(work);review={'status':'unprepared'}
    if v:
        try:bound_document(work,actor);r=validate_review(work.case,v);review={'status':'ready','id':r.pk if r else None}
        except (ValidationError,PermissionDenied) as exc:review={'status':'held','finding':finding(exc)}
    state={'case_revision':work.case.revision,'profile':work.policy_id,'sources':[(work.source_head_id,work.source_head.sha256)],'inventory_current':current,'source_finding':issue,
        'checks':{'inventory_current':current},'native':{'stage':'report','manifest':data['manifest']},'document':v.pk if v else None,'review':review,
        'publication':Publication.objects.filter(version=v,factory_work=work).values_list('pk',flat=True).first() if v else None,
        'jobs':[(j.pk,j.status) for j in jobs],'receipts':list(PublicationReceipt.objects.filter(publication__factory_work=work).values_list('pk','payload_sha256'))}
    state['hash']=digest(state);state['work_revision']=work.revision
    return state,latest,missing,stale,[],jobs

def eligible(work,value,state,latest,missing,stale,tasks,jobs):
    job=pending_job(jobs)
    if job:return ['ACT11' if job.status=='pending' else 'ACT12'],'Deliver the selected report' if job.status=='pending' else 'Look up the original report receipt before any new delivery'
    if any(j.status in ['held','leased'] for j in jobs):return [],'Resolve the original report delivery before continuing'
    if not Activity.objects.filter(work=work,key=investigation_key(work,state),status='succeeded').exists():return ['ACT04'],'Investigate selected report sources, unknowns and source-cited claims'
    if not state['inventory_current']:return [],state['source_finding']
    if missing or stale:return [],'Required report evidence missing or stale: '+', '.join(missing+stale)
    if not state['document']:return ['ACT09'],'Prepare the native source-cited leadership report'
    if work.request['kind']=='monthly_executive' and not HumanTask.objects.filter(version_id=state['document']).exists():
        try:native.review_context(document(work))
        except (ValidationError,PermissionDenied) as exc:return [],finding(exc)
        return ['ACT09'],'Request configured leadership review of the retained exact report'
    if state['review']['status']!='ready':return [],'Await current exact configured leadership review or deliberate source-owned rework'
    if not state['publication']:return ['ACT11'],'Reserve the exact reviewed leadership report'
    try:published(work,work.execution_actor)
    except (ValidationError,PermissionDenied) as exc:return [],finding(exc)
    return ['ACT13'],'Verify the exact current report and every required recipient receipt'

def act(work,choice,value,latest,missing,tasks,jobs):
    from .factory import access
    case=lock_case(work.execution_actor,work.case_id,'factory.execute');access(work.execution_actor,case,'factory.execute',DEFINITION)
    list(Grant.objects.select_for_update().filter(case=case).order_by('pk'))
    if case.revision!=work.case.revision:raise ValidationError('STALE_VERSION: report sources changed')
    kind=choice['activity']
    if kind in ['ACT11','ACT12']:
        job=pending_job(jobs)
        if job:return {'head':work.source_head_id,'publication_job':job.pk,'publication_lookup_only':kind=='ACT12'}
        if kind=='ACT12':raise ValidationError('No original uncertain report delivery exists')
    if kind=='ACT04':return {'head':work.source_head_id,'investigation':investigate(work,work.execution_actor),'source_refs':[work.source_head_id],'approval_granted':False}
    data=source(work,work.execution_actor)
    if kind=='ACT09':
        from apps.documents.controlled import request_review
        u=principal(work,value,'preparer_id');inventory(u,case,data['inputs']);v=document(work)
        if not data['inputs']['template_id']:raise ValidationError('Select the controlled leadership template')
        if not v:
            start,end=input_rows(case,data['inputs']);inputs=data['inputs']
            b=native.prepare(u,case.pk,inputs['kind'],start,end,inputs['template_id'],inputs['audience'],inputs['selections'],inputs['content_id'],case.revision,force_revision=True);v=b.version
            if b.manifest!=data['manifest']:raise ValidationError('Selected native inventory changed before draft; review the source successor')
        task=None;waiting=None
        if not HumanTask.objects.filter(version=v).exists():
            try:
                current_version(case,v.pk);role,_=native.review_context(v)
                if role is not None:
                    case.refresh_from_db();task=request_review(u,case.pk,v.pk,case.revision)
            except (ValidationError,PermissionDenied) as exc:waiting='Draft retained; '+finding(exc)
        result={'head':work.source_head_id,'document_version':v.pk,'native_review_task':task.pk if task else None}
        if waiting:result['waiting']=waiting
        return result
    if kind=='ACT11':
        from apps.documents.controlled import reserve_publication
        u=principal(work,value,'executor_id');_,v,_=bound_document(work,work.execution_actor)
        p=reserve_publication(u,case.pk,v.pk,case.revision,factory_work_id=work.pk)
        return {'head':work.source_head_id,'publication':p.pk}
    if kind=='ACT13':result=verify(work,work.execution_actor);work.status='verified';return result
    raise ValidationError('Unregistered report activity; source ownership and configured leadership decisions remain native')

def publication_scope(actor,case,version,work_id):
    from .factory import access,profile
    w=Work.objects.select_related('case','actor','source_head').get(pk=work_id,case=case,definition=DEFINITION)
    access(actor,case,'factory.execute',DEFINITION);config,value=profile(w)
    if w.policy_id!=config.pk or principal(w,value,'executor_id').pk!=actor.pk:raise PermissionDenied('Exact current report publisher and policy required')
    principal(w,value,'preparer_id')
    if w.cancel_requested or w.status in ['verified','cancelled','followup_needed']:raise ValidationError('Leadership report publication is stopped')
    _,v,_=bound_document(w,actor)
    if v.pk!=version.pk:raise ValidationError('Exact observed source-bound leadership report required')
    return {'factory_work_id':w.pk,'factory_policy_id':config.pk,'factory_source_id':w.source_head_id}

def verify(work,actor=None):
    data,v,b,p,receipts=published(work,actor)
    return {'verified':True,'verification_scope':'selected_native_leadership_report_and_exact_internal_recipient_receipts','head':work.source_head_id,'document_version':v.pk,'report':b.report_id,'publication':p.pk,'receipt_ids':[r.pk for r in receipts],
        'source_manifest':data['manifest'],'complete_project_coverage':False,'external_delivery_verified':False,'business_approval_granted':False}

@transaction.atomic
def correct(actor,work_id,expected,case_expected,inputs,reason):
    from .factory import access
    from apps.agents.factory_coordinator import pending,has_receipt
    w=Work.objects.select_for_update(of=('self',)).select_related('case','actor','source_head').get(pk=work_id,definition=DEFINITION)
    access(actor,w.case,'factory.manage',DEFINITION);case=lock_case(actor,w.case_id,'evidence.add',case_expected);w.case=case
    if type(expected) is not int or w.revision!=expected or w.cancel_requested or w.status in ['cancelled','followup_needed']:raise ValidationError('STALE_VERSION: refresh current report work')
    if w.lease_until and w.lease_until>timezone.now() or PublicationJob.objects.filter(publication__factory_work=w,status__in=['pending','unknown','leased','held']).exists():raise ValidationError('Resolve original effects before report source correction')
    planning=pending(w)
    if planning and not has_receipt(planning):raise ValidationError('Resolve original planning response before correction')
    if not isinstance(reason,str) or not reason.strip() or len(reason)>2000:raise ValidationError('Explain the source-owned report correction')
    data=source(w,actor,False);start,end=input_rows(case,inputs);inputs=dict(inputs,start_at=start.isoformat(),end_at=end.isoformat())
    if any(inputs[k]!=data['inputs'][k] for k in ['start_at','end_at','kind','audience']):raise ValidationError('A different reporting period requires separate work; preserve this period history')
    if data['inputs']==inputs and inventory(actor,case,inputs)['manifest']==data['manifest']:
        v=document(w)
        if not v:raise ValidationError('Provide a genuine source or template change')
        cancelled=PublicationJob.objects.filter(publication__version=v,publication__factory_work=w,status='cancelled').exists() and not PublicationReceipt.objects.filter(publication__version=v).exists()
        if not cancelled:
            try:current_version(case,v.pk);validate_review(case,v);published(w,actor)
            except (ValidationError,PermissionDenied):pass
            else:raise ValidationError('Current report and publication remain valid; provide a genuine correction')
    old=w.source_head_id;w.source_head=capture(actor,case,inputs,'factory.leadership_source');w.status='ready';w.finding='';w.observation_hash='';w.revision+=1;w.save()
    event(actor,case,'factory.leadership_corrected',work=w.pk,previous=old,current=w.source_head_id,reason=reason,spent=w.budget_used);return w

@transaction.atomic
def review(actor,work_id,expected,case_expected,version_id,verdict,note):
    from .factory import access
    from apps.documents.controlled import review_version
    w=Work.objects.select_for_update(of=('self',)).select_related('case','source_head','actor').get(pk=work_id,definition=DEFINITION)
    access(actor,w.case,'factory.read',DEFINITION);_,v,_=bound_document(w,actor)
    if type(expected) is not int or w.revision!=expected or w.cancel_requested or w.lease_until and w.lease_until>timezone.now() or v.pk!=version_id:raise ValidationError('STALE_VERSION: select exact current leadership report')
    return review_version(actor,w.case_id,version_id,verdict,note,case_expected)

def reconcile(actor,work_id,expected,adapter=None):
    from .factory import access,cancellation_status
    from apps.documents.delivery import run_publication_once
    with transaction.atomic():
        w=Work.objects.select_for_update(of=('self',)).select_related('case').get(pk=work_id,definition=DEFINITION)
        access(actor,w.case,'factory.execute',DEFINITION)
        if actor.pk!=w.actor_id:require(actor,w.case,'factory.manage')
        if type(expected) is not int or w.revision!=expected or w.lease_until and w.lease_until>timezone.now():raise ValidationError('STALE_VERSION: refresh original report delivery')
        job=PublicationJob.objects.filter(publication__factory_work=w).filter(Q(status='unknown')|Q(status='leased',lease_until__lte=timezone.now())).order_by('pk').first()
        if not job:raise ValidationError('No original uncertain report delivery needs reconciliation')
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
    if any(type(pk) is not int or pk<1 for pk in [expected,case_expected,job_id]) or w.revision!=expected:raise ValidationError('STALE_VERSION: refresh exact report and project versions')
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
    if w.revision!=expected:raise ValidationError('STALE_VERSION: refresh current report work')
    if w.status in ['verified','followup_needed']:raise ValidationError('Delivered or accepted work requires native follow-up')
    if w.status=='cancelled':return w
    if not w.cancel_requested:w=manage(actor,w.pk,w.revision,'cancel')
    if w.lease_until and w.lease_until>timezone.now():return w
    w.status=cancellation_status(w);w.finding='Stopping work cannot undo an already delivered document or recorded report evidence.'
    w.lease_until=None;w.revision+=1;w.save();return w



@transaction.atomic
def restart(actor,work_id,expected,case_expected,reason):
    from .factory import access
    from apps.agents.factory_coordinator import pending,has_receipt
    w=Work.objects.select_for_update(of=('self',)).select_related('case','source_head','actor').get(pk=work_id,definition=DEFINITION)
    access(actor,w.case,'factory.manage',DEFINITION);case=lock_case(actor,w.case_id,'evidence.add',case_expected);w.case=case
    if type(expected) is not int or w.revision!=expected or w.status!='cancelled' or not w.cancel_requested:raise ValidationError('Only settled stopped report preparation can receive a fresh instruction')
    if w.lease_until and w.lease_until>timezone.now() or PublicationJob.objects.filter(publication__factory_work=w,status__in=['pending','unknown','leased','held']).exists():raise ValidationError('Resolve original effects before restarting')
    planning=pending(w)
    if planning and not has_receipt(planning):raise ValidationError('Resolve original planning response before restarting')
    if PublicationReceipt.objects.filter(publication__factory_work=w).exists():raise ValidationError('Delivered reports require native follow-up, not restart')
    if not isinstance(reason,str) or not reason.strip() or len(reason)>2000:raise ValidationError('Explain the fresh report preparation instruction')
    data=source(w,actor)
    old=w.source_head_id;w.source_head=capture(actor,case,data['inputs'],'factory.leadership_source');w.cancel_requested=False;w.status='ready';w.finding='';w.lease_until=None;w.fence+=1;w.revision+=1;w.save()
    event(actor,case,'factory.leadership_restarted',work=w.pk,previous=old,current=w.source_head_id,reason=reason,spent=w.budget_used);return w

def projection(actor,work):
    from .factory import access,profile
    from apps.policy.services import decision_authority
    access(actor,work.case,'factory.read',DEFINITION);data=source(work,actor,False);v=document(work)
    issue='';options=[];next_action='Review selected leadership report sources';current=True
    try:source(work,actor)
    except (ValidationError,PermissionDenied) as exc:issue=finding(exc);current=False
    jobs=list(PublicationJob.objects.filter(publication__factory_work=work).order_by('pk'));receipts=list(PublicationReceipt.objects.filter(publication__version=v,publication__factory_work=work).order_by('pk')) if v else []
    idle=not (work.lease_until and work.lease_until>timezone.now());live=idle and not work.cancel_requested;verdicts=[]
    if live and current and v and HumanTask.objects.filter(version=v,status='open').exists():
        try:
            current_version(work.case,v.pk);require(actor,work.case,'document.review_controlled')
            for verdict in ['approve','return','reject']:
                try:
                    role,_=native.review_context(v)
                    if role is not None:decision_authority(actor,work.case,role,verdict);verdicts.append(verdict)
                except (ValidationError,PermissionDenied):pass
        except (ValidationError,PermissionDenied):pass
    try:
        _,value=profile(work);state,*args=snapshot(work,value,reader=actor);options,next_action=eligible(work,value,state,*args)
    except (ValidationError,PermissionDenied) as exc:next_action=finding(exc)
    changed=False
    if work.status=='verified':
        try:verify(work,actor);next_action='Inspect the reviewed leadership report and every required recipient receipt'
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
    return {'data':data,'document':v,'receipts':receipts,'jobs':jobs,'finding':issue,'readiness_changed':changed,'next_options':options,'next_action':next_action,'can_correct':can_correct,'can_restart':can_restart,'review_verdicts':verdicts}

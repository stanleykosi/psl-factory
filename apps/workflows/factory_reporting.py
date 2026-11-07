"""P41 selected weekly client report; native source/review/receipt truth stays authoritative."""
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
from apps.pmo.reporting import draft_period_report,client_content,report_source_access,client_manifest
from apps.pmo.models import MinutesReportBinding
from adapters.pmo_reporting import LocalPMOReportingAdapter
from .models import FactoryWork as Work,FactoryActivity as Activity,FactoryAttempt as Attempt,HumanTask
from .factory_delivery import investigation_key
from .factory_handover import pending_job

DEFINITION='pmo-weekly-report/v1'
KIND='agent_private_reporting_intake'
PROTOCOL='factory-weekly-report-intake/v1'
ID={'anyOf':[{'type':'integer','minimum':1,'maximum':9223372036854775807},{'type':'null'}]}
INPUT={'type':'object','properties':{'template_id':ID,'content_id':ID,'start_at':{'type':'string','maxLength':64},'end_at':{'type':'string','maxLength':64}},'required':['template_id','content_id','start_at','end_at'],'additionalProperties':False}
SCHEMA={'type':'object','properties':{'protocol':{'const':PROTOCOL},'inputs':INPUT,'manifest':{'type':'object'},'captured_at':{'type':'string'}},'required':['protocol','inputs','manifest','captured_at'],'additionalProperties':False}
SECTIONS={'executive_summary','scope','status','risks','timeline','dependencies','next_steps'}

def finding(exc):return '; '.join(exc.messages) if isinstance(exc,ValidationError) else str(exc)

def input_rows(case,inputs):
    validate(INPUT,inputs)
    pk=inputs['template_id']
    if pk is not None and type(pk) is not int:raise ValidationError('Exact template reference or unprovided value required')
    if inputs['content_id'] is not None and (type(inputs['content_id']) is not int or not Evidence.objects.filter(case=case,pk=inputs['content_id'],kind='agent_private_report_content').exists()):raise ValidationError('Choose this project explicit human-supplied client content source')
    start,end=aware(inputs['start_at'],'Period start'),aware(inputs['end_at'],'Period end')
    if end<=start or end-start>timedelta(days=8):raise ValidationError('Select a positive weekly reporting window of at most eight days; this is not a configured publication cadence')
    if end>timezone.now():raise ValidationError('Selected reporting period must have ended; future progress is unknown')
    if pk:
        t=Template.objects.filter(case=case,pk=pk,definition__document_type='status_report').first()
        if not t or not SECTIONS.issubset(t.definition['required_fields']) or set(t.definition['audience_fields'].get('client',[]))!=SECTIONS:
            raise ValidationError('Choose a case weekly client template requiring exactly summary, progress, risks, milestones/timeline and next steps')
    return start.astimezone(datetime_timezone.utc),end.astimezone(datetime_timezone.utc)

def inventory(actor,case,inputs):
    require(actor,case,'report.read');start,end=input_rows(case,inputs)
    snapshot=LocalPMOReportingAdapter().read_client_facts(case,start,end,timezone.now())
    report_source_access(actor,case,snapshot['manifest'])
    content=Evidence.objects.filter(case=case,pk=inputs['content_id'],kind='agent_private_report_content').first()
    snapshot['manifest']=client_manifest(snapshot,content)
    return snapshot

def source(work,actor=None,current=True):
    reader=actor or work.actor;require(reader,work.case,'report.read');e=work.source_head
    if not e or e.case_id!=work.case_id or e.kind!=KIND or e.sha256!=hashlib.sha256(e.body.encode()).hexdigest():raise ValidationError('Exact private weekly reporting intake required')
    try:data=json.loads(e.body)
    except (TypeError,ValueError):raise ValidationError('Typed weekly report intake required') from None
    validate(SCHEMA,data);input_rows(work.case,data['inputs'])
    report_source_access(reader,work.case,data['manifest'])
    audit=Audit.objects.filter(case=work.case,actor_id=e.created_by_id,action__in=['factory.reporting_intake','factory.reporting_source'],data={'evidence_id':e.pk,'sha256':e.sha256}).first()
    if not audit or any(data['inputs'][k]!=work.request[k] for k in ['start_at','end_at']):raise ValidationError('Exact selected report period and source-owned provenance required')
    if current:
        for action in ['case.read','report.read','evidence.add','factory.start' if audit.action=='factory.reporting_intake' else 'factory.manage']:require(e.created_by,work.case,action)
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
    payload={'start_at':inputs['start_at'],'end_at':inputs['end_at'],'reference':reference,'audience':'client','kind':'weekly_client'}
    sha=digest(payload);business=digest([str(case.pk),DEFINITION,start.isoformat(),end.isoformat()])
    old=Work.objects.filter(case=case).filter(Q(key=key)|Q(definition=DEFINITION,business_key=business)).first()
    if old:
        if old.actor_id!=actor.pk or old.definition!=DEFINITION or old.key==key and old.request_hash!=sha:raise ValidationError('IDEMPOTENCY_CONFLICT: changed weekly report intent')
        if source(old,actor)['inputs']!=inputs:raise ValidationError('Review changed selections in the existing weekly reporting work')
        return old
    w=Work.objects.create(case=case,actor=actor,key=key,definition=DEFINITION,request=payload,request_hash=sha,business_key=business,source_head=capture(actor,case,inputs,'factory.reporting_intake'))
    event(actor,case,'factory.started',work=w.pk,definition=DEFINITION);return w

def document(work):
    pk=Attempt.objects.filter(activity__work=work,phase='observed',result__head=work.source_head_id,result__has_key='document_version').order_by('-pk').values_list('result__document_version',flat=True).first()
    b=MinutesReportBinding.objects.select_related('version__document','version__template','report').filter(version_id=pk,report__case=work.case,report__kind='weekly_client',report__audience='client').first()
    return b.version if b else None

def principal(work,value,name):
    u=get_user_model().objects.filter(pk=value[name],is_active=True).first()
    if not u:raise ValidationError('owner_needed: Configure current weekly report '+name.replace('_id',''))
    actions=['case.read','report.read','factory.execute']+(['report.draft','document.draft','document.request_review'] if name=='preparer_id' else ['document.publish'])
    try:
        for action in actions:require(u,work.case,action)
    except PermissionDenied:raise ValidationError('owner_needed: Weekly report principal lacks current exact project permissions') from None
    return u

def bound_document(work,actor=None):
    data=source(work,actor);v=document(work)
    if not v:raise ValidationError('Await exact native weekly client report draft')
    b=MinutesReportBinding.objects.get(version=v);start,end=input_rows(work.case,data['inputs'])
    if b.report.start_at!=start or b.report.end_at!=end or b.manifest!=data['manifest'] or v.template_id!=data['inputs']['template_id'] or v.audience!='client':raise ValidationError('Exact period, template, client audience and selected native source snapshot required')
    if {x['heading'] for x in v.payload['sections']}!=SECTIONS:raise ValidationError('All four client-report topics and summary are required')
    content,sections=client_content(work.case,inventory(actor or work.actor,work.case,data['inputs']),data['inputs']['content_id'])
    projection=Evidence.objects.filter(case=work.case,pk__in=[x['id'] for x in v.source_manifest],kind='ops_client_report_projection',source='psl:weekly-client-projection:'+str(b.report_id),created_by_id=v.created_by_id).first()
    if not projection or len(v.source_manifest)!=1 or any(x['evidence_ids']!=[projection.pk] for x in v.fields.values()) or any(v.fields.get(k,{}).get('text')!=x['text'] for k,x in sections.items()):raise ValidationError('Exact substantive narrative, private native citations and generated-only outward projection required')
    from apps.pmo.reporting import CLIENT_SCOPE_COVERAGE, CLIENT_DEPENDENCY_COVERAGE
    for key, text in [('scope', CLIENT_SCOPE_COVERAGE), ('dependencies', CLIENT_DEPENDENCY_COVERAGE)]:
        if v.fields.get(key, {}).get('text') != text or not any(s['heading'] == key and s['text'] == text for s in v.payload['sections']):
            raise ValidationError('Exact generated client scope and dependency coverage statements required')
    current_version(work.case,v.pk);return data,v,b

def published(work,actor=None):
    from .factory import profile
    data,v,b=bound_document(work,actor);review=validate_review(work.case,v)
    policies,recipients,retention=publication_requirements(work.case,v)
    config,value=profile(work,recovery=True);principal(work,value,'preparer_id');u=principal(work,value,'executor_id')
    p=Publication.objects.filter(version=v,factory_work=work,factory_source=work.source_head,factory_policy=config,actor=u).first()
    if not p or p.policies!=policies or p.recipient_ids!=recipients or p.retention_days!=retention or p.review_id!=review.pk:raise ValidationError('Await current exact reviewed client report publication and recipient contract')
    receipts=list(PublicationReceipt.objects.filter(publication=p).order_by('pk'))
    if not receipts or {r.recipient_id for r in receipts}!=set(recipients) or any(r.payload!=v.payload or r.payload_sha256!=v.payload_sha256 for r in receipts):raise ValidationError('Every exact required client recipient receipt is required')
    return data,v,b,p,receipts

def investigate(work,actor):
    data=source(work,actor,current=False);s=inventory(actor,work.case,data['inputs']);actions=s['actions']
    narrative={'status':'missing','finding':'Select substantive client-safe source content for all four required themes'}
    try:
        content,sections=client_content(work.case,s,data['inputs']['content_id']);narrative={'status':'cited','content_id':content.pk,'source_sha256':content.sha256,'themes':{k:{'text':v['text'],'evidence_ids':v['evidence_ids']} for k,v in sections.items()},'meaning_and_safety_review_required':True}
    except ValidationError as exc:narrative['finding']=finding(exc)
    return {'narrative':narrative,'capability':'A06/A07/A08 weekly client source coverage and unsupported-claim investigation','source_head':work.source_head_id,'manifest':s['manifest'],'selected_inventory_current':s['manifest']==data['manifest'],
        'counts':{'meetings_in_period':len(s['meetings']),'milestones_in_period':len(s['milestones']),'current_commitments':len(actions),'current_issues':len(s['issues'])},
        'commitment_gaps':[{'action_id':a.pk,'state_id':a.current_id,'evidence_id':a.current.evidence_id,'owner_missing':a.current.owner_id is None,'deadline_missing':a.current.due_at is None} for a in actions if a.current.owner_id is None or a.current.due_at is None],
        'coverage':'Only selected local meeting/action/milestone/issue/change facts. Delivery/RFP/escalation histories, change-approval timelines, external systems, overall progress, complete risk coverage and future dates are not established.',
        'client_projection':'Exact human-supplied cited narrative plus bounded local coverage; raw underlying notes and internal source references are excluded from the outward payload.',
        'unsupported_claims':['Complete project health or risk coverage','Unrecorded milestone progress or dates','Automatic permission to distribute'],
        'next_action':'Refresh changed source selections; prepare the four-topic client-safe draft and obtain current exact PMO Lead review before configured distribution.',
        'approval_granted':False,'communications_dispatched':False}

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
        try:bound_document(work,actor);r=validate_review(work.case,v);review={'status':'ready','id':r.pk}
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
    if not Activity.objects.filter(work=work,key=investigation_key(work,state),status='succeeded').exists():return ['ACT04'],'Investigate selected report sources, unknowns and client-safe claims'
    if not state['inventory_current']:return [],state['source_finding']
    if missing or stale:return [],'Required report evidence missing or stale: '+', '.join(missing+stale)
    if not state['document']:return ['ACT09'],'Prepare the native client-safe weekly report'
    if not HumanTask.objects.filter(version_id=state['document']).exists():return ['ACT09'],'Request native PMO Lead review of the retained exact report'
    if state['review']['status']!='ready':return [],'Await current exact PMO Lead review or deliberate source-owned rework'
    if not state['publication']:return ['ACT11'],'Reserve the exact reviewed weekly client report'
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
        if not data['inputs']['template_id']:raise ValidationError('Select the controlled weekly client template')
        if not v:
            start,end=input_rows(case,data['inputs']);client_content(case,inventory(u,case,data['inputs']),data['inputs']['content_id'])
            b=draft_period_report(u,case.pk,'weekly_client',start,end,data['inputs']['template_id'],'client',case.revision,client_safe=True,client_content_id=data['inputs']['content_id']);v=b.version
            if b.manifest!=data['manifest']:raise ValidationError('Selected native inventory changed before draft; review the source successor')
        task=None;waiting=None
        if not HumanTask.objects.filter(version=v).exists():
            try:current_version(case,v.pk)
            except (ValidationError,PermissionDenied):waiting='Draft retained; complete current source requirements before PMO Lead review'
            else:case.refresh_from_db();task=request_review(u,case.pk,v.pk,case.revision)
        result={'head':work.source_head_id,'document_version':v.pk,'native_review_task':task.pk if task else None}
        if waiting:result['waiting']=waiting
        return result
    if kind=='ACT11':
        from apps.documents.controlled import reserve_publication
        u=principal(work,value,'executor_id');_,v,_=bound_document(work,work.execution_actor)
        p=reserve_publication(u,case.pk,v.pk,case.revision,factory_work_id=work.pk)
        return {'head':work.source_head_id,'publication':p.pk}
    if kind=='ACT13':result=verify(work,work.execution_actor);work.status='verified';return result
    raise ValidationError('Unregistered report activity; source ownership and PMO Lead decisions remain native')

def publication_scope(actor,case,version,work_id):
    from .factory import access,profile
    w=Work.objects.select_related('case','actor','source_head').get(pk=work_id,case=case,definition=DEFINITION)
    access(actor,case,'factory.execute',DEFINITION);config,value=profile(w)
    if w.policy_id!=config.pk or principal(w,value,'executor_id').pk!=actor.pk:raise PermissionDenied('Exact current report publisher and policy required')
    principal(w,value,'preparer_id')
    if w.cancel_requested or w.status in ['verified','cancelled','followup_needed']:raise ValidationError('Weekly report publication is stopped')
    _,v,_=bound_document(w,actor)
    if v.pk!=version.pk:raise ValidationError('Exact observed source-bound weekly report required')
    return {'factory_work_id':w.pk,'factory_policy_id':config.pk,'factory_source_id':w.source_head_id}

def verify(work,actor=None):
    data,v,b,p,receipts=published(work,actor)
    return {'verified':True,'verification_scope':'selected_local_weekly_client_report_and_exact_native_recipient_receipts','head':work.source_head_id,'document_version':v.pk,'report':b.report_id,'publication':p.pk,'receipt_ids':[r.pk for r in receipts],
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
    if any(inputs[k]!=data['inputs'][k] for k in ['start_at','end_at']):raise ValidationError('A different reporting period requires separate work; preserve this period history')
    if data['inputs']==inputs and inventory(actor,case,inputs)['manifest']==data['manifest']:
        v=document(w)
        if not v:raise ValidationError('Provide a genuine source or template change')
        cancelled=PublicationJob.objects.filter(publication__version=v,publication__factory_work=w,status='cancelled').exists() and not PublicationReceipt.objects.filter(publication__version=v).exists()
        if not cancelled:
            try:current_version(case,v.pk);validate_review(case,v);published(w,actor)
            except (ValidationError,PermissionDenied):pass
            else:raise ValidationError('Current report and publication remain valid; provide a genuine correction')
    old=w.source_head_id;w.source_head=capture(actor,case,inputs,'factory.reporting_source');w.status='ready';w.finding='';w.observation_hash='';w.revision+=1;w.save()
    event(actor,case,'factory.reporting_corrected',work=w.pk,previous=old,current=w.source_head_id,reason=reason,spent=w.budget_used);return w

@transaction.atomic
def review(actor,work_id,expected,case_expected,version_id,verdict,note):
    from .factory import access
    from apps.documents.controlled import review_version
    w=Work.objects.select_for_update(of=('self',)).select_related('case','source_head','actor').get(pk=work_id,definition=DEFINITION)
    access(actor,w.case,'factory.read',DEFINITION);_,v,_=bound_document(w,actor)
    if type(expected) is not int or w.revision!=expected or w.cancel_requested or w.lease_until and w.lease_until>timezone.now() or v.pk!=version_id:raise ValidationError('STALE_VERSION: select exact current weekly report')
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
    old=w.source_head_id;w.source_head=capture(actor,case,data['inputs'],'factory.reporting_source');w.cancel_requested=False;w.status='ready';w.finding='';w.lease_until=None;w.fence+=1;w.revision+=1;w.save()
    event(actor,case,'factory.reporting_restarted',work=w.pk,previous=old,current=w.source_head_id,reason=reason,spent=w.budget_used);return w

def projection(actor,work):
    from .factory import access,profile
    from apps.policy.services import decision_authority
    access(actor,work.case,'factory.read',DEFINITION);data=source(work,actor,False);v=document(work)
    issue='';options=[];next_action='Review selected weekly report sources';current=True
    try:source(work,actor)
    except (ValidationError,PermissionDenied) as exc:issue=finding(exc);current=False
    jobs=list(PublicationJob.objects.filter(publication__factory_work=work).order_by('pk'));receipts=list(PublicationReceipt.objects.filter(publication__version=v,publication__factory_work=work).order_by('pk')) if v else []
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
        try:verify(work,actor);next_action='Inspect the reviewed weekly report and every required recipient receipt'
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

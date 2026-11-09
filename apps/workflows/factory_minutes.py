"""P43: cited suggestions, human commitments, current native minutes and optional P53 delivery.

No internal approval chain is invented. Capturing minutes neither completes actions
nor approves a baseline change. Operational extraction has no synthetic fallback.
"""
import hashlib,json,re
from datetime import timedelta
from django.core.exceptions import ValidationError,PermissionDenied
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from apps.core.models import Audit,Evidence
from apps.core.evidence_access import restricted
from apps.core.services import lock_case,add_evidence,event
from apps.identity.services import require
from apps.documents.contracts import digest,validate
from apps.documents.models import Template,Publication,PublicationJob,PublicationReceipt
from apps.pmo import meetings,reporting
from apps.pmo.models import Meeting,MeetingVersion,ActionItem,MinutesReportBinding
from apps.pmo.services import subject
from apps.agents.models import AgentRun
from .models import FactoryWork as Work,FactoryActivity as Activity,FactoryAttempt as Attempt
from .factory_delivery import investigation_key
from .factory_handover import pending_job

DEFINITION='pmo-minutes/v1'
KIND='agent_private_minutes_intake'
PROTOCOL='factory-minutes-intake/v1'
ID={'type':'integer','minimum':1}
NULLID={'anyOf':[ID,{'type':'null'}]}
def obj(properties):return {'type':'object','properties':properties,'required':list(properties),'additionalProperties':False}
def text(limit):return {'type':'string','minLength':1,'maxLength':limit}
SELECTION=obj({'protocol':{'const':PROTOCOL},'meeting_version_id':NULLID,'evidence_id':ID,'template_id':ID,'audience':{'enum':['internal','client']},'publish':{'type':'boolean'}})
FIELDS=obj({'kind':{'enum':meetings.MEETING_KINDS},'occurred_at':text(80),'purpose':text(240),'summary':text(16000),'participant_ids':{'type':'array','maxItems':50,'uniqueItems':True,'items':ID},
 'decisions':{'type':'array','maxItems':50,'items':obj({'text':text(2000),'evidence_id':ID,'change_evidence_id':NULLID})},
 'actions':{'type':'array','maxItems':50,'items':obj({'reference':text(160),'description':text(1000),'owner_id':NULLID,'due_at':{'anyOf':[text(80),{'type':'null'}]},'evidence_id':ID,'change_evidence_id':NULLID,'reason':text(4000)})},
 'existing_action_ids':{'type':'array','maxItems':50,'uniqueItems':True,'items':ID},'note':text(2000)})

def finding(exc):return '; '.join(exc.messages) if isinstance(exc,ValidationError) else str(exc)
def readable(actor,case):
    from apps.core.workbench import active
    active(actor)
    for action in ['case.read','meeting.read']:require(actor,case,action)

def selection(actor,case,data):
    readable(actor,case);validate(SELECTION,data)
    if case.kind!='project' or data['publish']!=(data['audience']=='client'):raise ValidationError('Choose internal repository minutes or explicitly requested client publication')
    e=subject(case,data['evidence_id'],'meeting_notes')
    if restricted(e) or not e.body.strip() or len(e.body)>16000:raise ValidationError('Bounded authorized meeting notes required')
    t=Template.objects.filter(case=case,pk=data['template_id'],definition__document_type='minutes').first()
    if not t or data['audience'] not in t.definition['audience_fields']:raise ValidationError('Same-project minutes template and supported audience required')
    if data['meeting_version_id'] is not None and not MeetingVersion.objects.filter(pk=data['meeting_version_id'],meeting__case=case).exists():raise ValidationError('Select an existing meeting version from this project')
    return e,t

def meeting_intent(case,reference,data):
    m=Meeting.objects.select_related('current').filter(case=case,reference=reference).first()
    selected=data['meeting_version_id']
    if m:
        if selected is None:raise ValidationError('Meeting reference already exists; explicitly select its current version before revising it')
        if m.current_id!=selected:raise ValidationError('STALE_VERSION: select the exact current version of this meeting reference')
    elif selected is not None:raise ValidationError('Selected meeting version does not match the requested meeting reference')
    return m

def source(work,actor=None,current=True):
    actor=actor or work.actor;e=work.source_head
    if not e or e.case_id!=work.case_id or e.kind!=KIND or e.sha256!=hashlib.sha256(e.body.encode()).hexdigest():raise ValidationError('Exact immutable minutes intake required')
    try:data=json.loads(e.body)
    except (TypeError,ValueError):raise ValidationError('Typed minutes source required') from None
    note,template=selection(actor,work.case,data)
    a=Audit.objects.filter(case=work.case,actor_id=e.created_by_id,action__in=['factory.minutes_intake','factory.minutes_source'],data={'evidence_id':e.pk,'sha256':e.sha256}).first()
    if not a:raise ValidationError('Exact minutes intake provenance required')
    if current:
        readable(e.created_by,work.case)
        require(e.created_by,work.case,'factory.start' if a.action=='factory.minutes_intake' else 'factory.manage')
    return data,note,template

def capture(actor,case,data,action):
    e=add_evidence(actor,case.pk,KIND,json.dumps(data,sort_keys=True),'psl:'+PROTOCOL)
    event(actor,case,action,evidence_id=e.pk,sha256=e.sha256);return e

@transaction.atomic
def start(actor,case_id,key,reference,data,expected):
    from .factory import access
    c=lock_case(actor,case_id,'factory.start');access(actor,c,'factory.start',DEFINITION);require(actor,c,'evidence.add');selection(actor,c,data)
    if not isinstance(key,str) or not re.fullmatch(r'[A-Za-z0-9_.:-]{1,100}',key) or not isinstance(reference,str) or not reference.strip() or len(reference)>160:raise ValidationError('Bounded key and meeting reference required')
    request={'reference':reference};sha=digest(request);business=digest([str(c.pk),DEFINITION,reference])
    old=Work.objects.filter(case=c).filter(Q(key=key)|Q(definition=DEFINITION,business_key=business)).first()
    if old:
        if old.actor_id!=actor.pk or old.definition!=DEFINITION or old.request_hash!=sha or source(old,actor)[0]!=data:raise ValidationError('IDEMPOTENCY_CONFLICT: correct existing minutes work')
        return old
    if type(expected) is not int or expected!=c.revision:raise ValidationError('STALE_VERSION: refresh project before intake')
    meeting_intent(c,reference,data)
    w=Work.objects.create(case=c,actor=actor,key=key,definition=DEFINITION,request=request,request_hash=sha,business_key=business,source_head=capture(actor,c,data,'factory.minutes_intake'))
    event(actor,c,'factory.started',work=w.pk,definition=DEFINITION);return w

def observed(work,field):
    return Attempt.objects.filter(activity__work=work,phase='observed',result__head=work.source_head_id,**{'result__has_key':field}).order_by('-pk').values_list('result__'+field,flat=True).first()

def extraction(work):
    return AgentRun.objects.filter(pk=observed(work,'extraction'),case=work.case,process_id='P43').first()

def confirmation(work):
    return Audit.objects.filter(case=work.case,action='factory.minutes_confirmed',data__work=work.pk,data__head=work.source_head_id).order_by('-pk').first()

def confirmed_meeting(work,actor=None):
    data,_,_=source(work,actor);a=confirmation(work)
    if not a:raise ValidationError('Human confirmation of actual decisions, attribution and commitments required')
    readable(a.actor,work.case);require(a.actor,work.case,'meeting.record')
    m=Meeting.objects.select_related('current').filter(case=work.case,reference=work.request['reference'],current_id=a.data['meeting_version']).first()
    if not m or m.current.created_by_id!=a.actor_id:raise ValidationError('Meeting was corrected; confirm the current source and attribution')
    predecessor=data['meeting_version_id']
    if predecessor is None and m.current.number!=1 or predecessor is not None and not MeetingVersion.objects.filter(pk=predecessor,meeting=m,number=m.current.number-1).exists():raise ValidationError('Confirmed minutes must retain the exact selected native predecessor')
    return m

def document(work):
    return MinutesReportBinding.objects.select_related('version__document','version__template','meeting__current').filter(version_id=observed(work,'document_version'),meeting__case=work.case).first()

def settled(work):
    from apps.agents.factory_coordinator import pending,has_receipt
    if work.lease_until and work.lease_until>timezone.now():raise ValidationError('CONFLICT: current worker owns this work')
    p=pending(work)
    if p and not has_receipt(p):raise ValidationError('Reconcile original planning response first')
    if PublicationJob.objects.filter(publication__factory_work=work,status__in=['pending','unknown','leased','held']).exists():raise ValidationError('Resolve original publication before replacing sources')

def human_work(actor,work_id,expected,case_expected):
    from .factory import access
    w=Work.objects.select_for_update(of=('self',)).select_related('case','source_head','actor').get(pk=work_id,definition=DEFINITION)
    access(actor,w.case,'factory.read',DEFINITION);w.case=lock_case(actor,w.case_id,'meeting.read',case_expected)
    if type(expected) is not int or w.revision!=expected or w.cancel_requested or w.status in ['cancelled','followup_needed']:raise ValidationError('Refresh active minutes work')
    settled(w);return w

@transaction.atomic
def confirm(actor,work_id,expected,case_expected,fields,extraction_id):
    w=human_work(actor,work_id,expected,case_expected);data,note,_=source(w,actor);validate(FIELDS,fields)
    prior=confirmation(w)
    if prior:raise ValidationError('This source already has a confirmation; record a source correction first')
    r=extraction(w)
    if extraction_id is not None and (type(extraction_id) is not int or extraction_id<1) or extraction_id!=(r.pk if r else None):raise ValidationError('Inspect the exact latest extraction before confirming attribution')
    if not fields['note'].strip():raise ValidationError('Explain the human attribution and commitment check')
    # Human authors every decision and assignment. Suggestions never supply authority.
    for d in fields['decisions']:
        if d['evidence_id']!=note.pk:raise ValidationError('Confirmed decisions must cite selected meeting notes')
    for a in fields['actions']:
        if a['evidence_id']!=note.pk:raise ValidationError('Confirmed actions must cite selected meeting notes')
    m=meeting_intent(w.case,w.request['reference'],data)
    duplicate=ActionItem.objects.filter(case=w.case,reference__in=[a['reference'] for a in fields['actions']]).order_by('pk').first()
    if duplicate:raise ValidationError('Action reference '+duplicate.reference+' already exists. Retain existing action ID '+str(duplicate.pk)+'; use native action management for owner or deadline changes.')
    v=meetings.record_meeting(actor,w.case_id,w.request['reference'],fields['kind'],fields['occurred_at'],fields['purpose'],fields['summary'],fields['participant_ids'],fields['decisions'],note.pk,w.case.revision,m.pk if m else None)
    for item in fields['actions']:
        w.case.refresh_from_db();meetings.create_action(actor,w.case_id,item['reference'],item['description'],item['owner_id'],item['due_at'],note.pk,item['reason'],w.case.revision,v.meeting_id,change_evidence_id=item['change_evidence_id'])
    linked=set(meetings.meeting_actions(v.meeting).values_list('pk',flat=True))
    for pk in fields['existing_action_ids']:
        if not ActionItem.objects.filter(pk=pk,case=w.case).exists():raise ValidationError('Same-project existing action required')
        if pk not in linked:
            w.case.refresh_from_db();meetings.link_action(actor,w.case_id,v.meeting_id,pk,note.pk,w.case.revision)
    a=event(actor,w.case,'factory.minutes_confirmed',work=w.pk,head=w.source_head_id,meeting_version=v.pk,extraction=extraction_id,fields=fields,scope_changed=False,actions_completed=False)
    w.status='ready';w.finding='';w.revision+=1;w.save();return a

def publisher(work,value):
    from django.contrib.auth import get_user_model
    u=get_user_model().objects.filter(pk=value['executor_id'],is_active=True).first()
    if not u:raise ValidationError('owner_needed: configure the separately authorized minutes publisher')
    for action in ['case.read','meeting.read','factory.execute','document.publish']:require(u,work.case,action)
    return u

def current_document(work,actor=None):
    from apps.documents.controlled import current_version
    data,_,_=source(work,actor);m=confirmed_meeting(work,actor);b=document(work)
    if not b or b.meeting_id!=m.pk or b.version.template_id!=data['template_id'] or b.version.audience!=data['audience']:raise ValidationError('Prepare exact selected native minutes')
    current_version(work.case,b.version_id)
    if b.version.document.current_id!=b.version_id:raise ValidationError('Minutes document was replaced; use a current native version')
    if b.manifest!=reporting.meeting_manifest(m):raise ValidationError('Meeting or action state changed; rebuild current minutes')
    return b

def verify(work,actor=None):
    from .factory import profile
    from apps.documents.controlled import validate_review,publication_requirements
    data,_,_=source(work,actor);b=current_document(work,actor);result={'verified':True,'head':work.source_head_id,'meeting_version':b.meeting.current_id,'document_version':b.version_id,'manifest':b.manifest,'actions_completed':False,'scope_changed':False,'publication':None,'receipt_ids':[]}
    if not data['publish']:return result
    review=validate_review(work.case,b.version);policies,recipients,retention=publication_requirements(work.case,b.version)
    config,value=profile(work,recovery=True);u=publisher(work,value)
    p=Publication.objects.filter(version=b.version,factory_work=work,factory_source=work.source_head,factory_policy=config,actor=u).first()
    if not p or p.review_id!=review.pk or p.policies!=policies or p.recipient_ids!=recipients or p.retention_days!=retention:raise ValidationError('Await exact reviewed outward minutes publication')
    receipts=list(PublicationReceipt.objects.filter(publication=p).order_by('pk'))
    if not receipts or {r.recipient_id for r in receipts}!=set(recipients) or any(r.payload!=b.version.payload or r.payload_sha256!=b.version.payload_sha256 for r in receipts):raise ValidationError('Every exact outward minutes recipient receipt required')
    result.update(publication=p.pk,receipt_ids=[r.pk for r in receipts]);return result

def report(work,actor):
    result={'stage':'confirmation','finding':''}
    try:
        confirmed_meeting(work,actor);result['stage']='draft'
        if not document(work):return result
        result['stage']='rework';current_document(work,actor);result['stage']='publication';verify(work,actor);result['stage']='complete'
    except (ValidationError,PermissionDenied) as exc:result['finding']=finding(exc)
    return result

def snapshot(work,value,reader=None):
    actor=reader or work.execution_actor;data,note,_=source(work,actor);n=report(work,actor);a=confirmation(work);b=document(work)
    jobs=list(PublicationJob.objects.filter(publication__factory_work=work).order_by('pk'))
    latest={KIND:work.source_head,'meeting_notes':note};missing=[k for k in value['required_evidence_kinds'] if k not in latest]
    stale=[k for k in value['required_evidence_kinds'] if k in latest and latest[k].created_at<timezone.now()-timedelta(seconds=value['max_age_seconds'])]
    state={'case_revision':work.case.revision,'profile':work.policy_id,'sources':[(e.pk,e.sha256) for e in latest.values()],'native':n,'checks':{'confirmation':a.pk if a else None,'manifest':reporting.meeting_manifest(b.meeting) if b else None,'document':b.version_id if b else None},'jobs':[(j.pk,j.status) for j in jobs]}
    state['hash']=digest(state);state['work_revision']=work.revision;return state,latest,missing,stale,[],jobs

def eligible(work,value,state,latest,missing,stale,tasks,jobs):
    j=pending_job(jobs)
    if j:return ['ACT11' if j.status=='pending' else 'ACT12'],'Deliver or reconcile the original exact minutes publication'
    if any(j.status in ['held','leased'] for j in jobs):return [],'Resolve original publication before continuing'
    if missing or stale:return [],'Current configured notes required'
    if not Activity.objects.filter(work=work,key=investigation_key(work,state),status='succeeded').exists():return ['ACT04'],'Extract cited proposals and inspect current commitments'
    stage=state['native']['stage']
    if stage=='confirmation':return [],state['native']['finding']
    if stage=='draft':return ['ACT09'],'Prepare current native minutes without completing actions'
    if stage=='complete':return ['ACT13'],'Verify current repository minutes and selected outward receipts'
    if stage=='publication':
        try:
            from apps.documents.controlled import validate_review
            validate_review(work.case,document(work).version);publisher(work,value)
        except (ValidationError,PermissionDenied) as exc:return [],finding(exc)
        return ['ACT11'],'Reserve separately authorized reviewed outward minutes'
    return [],state['native']['finding']

def act(work,choice,value,latest,missing,tasks,jobs):
    from .factory import access
    c=lock_case(work.execution_actor,work.case_id,'factory.execute');access(work.execution_actor,c,'factory.execute',DEFINITION)
    from apps.identity.models import Grant
    list(Grant.objects.select_for_update().filter(case=c).order_by('pk'))
    if c.revision!=work.case.revision:raise ValidationError('STALE_VERSION: minutes context changed')
    data,note,_=source(work,work.execution_actor);kind=choice['activity']
    if kind=='ACT04':
        r=extraction(work)
        if not r and not confirmation(work):
            if value['extraction_provider'] is None:return {'head':work.source_head_id,'extraction':None,'finding':'No approved extraction provider selected; authenticated human capture remains available','human_confirmation_required':True}
            if value['extraction_provider']!='synthetic_meeting_v1' or not c.synthetic:raise ValidationError('Operational meeting interpretation requires an approved provider; human capture remains available')
            from apps.agents.meetings import suggest_commitments
            r=suggest_commitments(work.execution_actor,c.pk,note.pk,c.revision)
        return {'head':work.source_head_id,'extraction':r.pk if r else None,'human_confirmation_required':True,'scope_changed':False,'commitments_assigned':False}
    if kind=='ACT09':
        m=confirmed_meeting(work,work.execution_actor);b=reporting.draft_minutes(work.execution_actor,c.pk,m.pk,data['template_id'],data['audience'],c.revision)
        if data['publish']:
            from apps.documents.controlled import request_review
            c.refresh_from_db();request_review(work.execution_actor,c.pk,b.version_id,c.revision)
        return {'head':work.source_head_id,'document_version':b.version_id,'meeting_version':m.current_id}
    if kind in ['ACT11','ACT12']:
        j=pending_job(jobs)
        if j:return {'head':work.source_head_id,'publication_job':j.pk,'publication_lookup_only':kind=='ACT12'}
        if kind=='ACT12':raise ValidationError('No original uncertain publication')
        from apps.documents.controlled import reserve_publication
        b=current_document(work,work.execution_actor);p=reserve_publication(publisher(work,value),c.pk,b.version_id,c.revision,factory_work_id=work.pk)
        return {'head':work.source_head_id,'publication':p.pk}
    if kind=='ACT13':
        result=verify(work,work.execution_actor);work.status='verified';return result
    raise ValidationError('Human attribution, commitment and owner changes are not agent tools')

def publication_scope(actor,case,version,work_id):
    from .factory import access,profile
    w=Work.objects.select_related('case','source_head','actor').get(pk=work_id,case=case,definition=DEFINITION);access(actor,case,'factory.execute',DEFINITION)
    c,v=profile(w);data,_,_=source(w,actor);b=current_document(w,actor)
    if not data['publish'] or w.policy_id!=c.pk or publisher(w,v).pk!=actor.pk or b.version_id!=version.pk or w.cancel_requested or w.status in ['verified','cancelled','followup_needed']:raise ValidationError('Exact active outward minutes instruction, publisher and version required')
    return {'factory_work_id':w.pk,'factory_policy_id':c.pk,'factory_source_id':w.source_head_id}

@transaction.atomic
def correct(actor,work_id,expected,case_expected,data,reason):
    w=human_work(actor,work_id,expected,case_expected);require(actor,w.case,'factory.manage');selection(actor,w.case,data);meeting_intent(w.case,w.request['reference'],data)
    if not isinstance(reason,str) or not reason.strip() or len(reason)>2000:raise ValidationError('Explain the source-owned correction')
    old=source(w,actor,False)[0]
    if old==data:
        try:current_document(w,actor)
        except (ValidationError,PermissionDenied):pass
        else:
            b=document(w);r=b.version.reviews.order_by('-pk').first()
            stopped=PublicationJob.objects.filter(publication__version=b.version,status='cancelled').exists()
            if not stopped and (not r or r.verdict=='approve'):raise ValidationError('Current minutes await review or are complete; no identical replacement')
    before=w.source_head_id;w.source_head=capture(actor,w.case,data,'factory.minutes_source');w.status='ready';w.finding='';w.revision+=1;w.save()
    event(actor,w.case,'factory.minutes_corrected',work=w.pk,previous=before,current=w.source_head_id,reason=reason);return w

@transaction.atomic
def restart(actor,work_id,expected,case_expected,reason):
    from .factory import access
    w=Work.objects.select_for_update(of=('self',)).select_related('case','source_head','actor').get(pk=work_id,definition=DEFINITION)
    access(actor,w.case,'factory.manage',DEFINITION);w.case=lock_case(actor,w.case_id,'factory.manage',case_expected);settled(w)
    if type(expected) is not int or w.revision!=expected or w.status!='cancelled' or not isinstance(reason,str) or not reason.strip() or len(reason)>2000:raise ValidationError('Refresh settled cancelled work and explain fresh instruction')
    source(w,actor,False);w.status='ready';w.cancel_requested=False;w.finding='';w.revision+=1;w.save();event(actor,w.case,'factory.minutes_restarted',work=w.pk,reason=reason);return w

def projection(actor,work):
    from .factory import profile
    source(work,actor,False);n=report(work,actor);options=[];message=n['finding'];changed=False
    try:
        _,v=profile(work,recovery=True);s,latest,missing,stale,tasks,jobs=snapshot(work,v,reader=actor);options,message=eligible(work,v,s,latest,missing,stale,tasks,jobs)
        if work.status=='verified':verify(work,actor)
    except (ValidationError,PermissionDenied) as exc:message=finding(exc);changed=work.status=='verified';options=[]
    can_review=False;reviewers=[]
    if n['stage']=='publication' and not work.cancel_requested:
        from django.contrib.auth import get_user_model
        from apps.policy.services import decision_authority
        for u in get_user_model().objects.filter(is_active=True,grant__case=work.case,grant__active=True,grant__action='document.review_controlled').distinct():
            try:decision_authority(u,work.case,'PMO Lead','approve')
            except (ValidationError,PermissionDenied):continue
            reviewers.append(u.get_full_name() or u.username);can_review=can_review or actor.pk==u.pk
    m=Meeting.objects.filter(case=work.case,reference=work.request['reference']).first()
    return {'can_review':can_review,'reviewer_names':reviewers,'jobs':list(PublicationJob.objects.filter(publication__factory_work=work).order_by('pk')),'document':document(work),'extraction':extraction(work),'confirmation':confirmation(work),'actions':list(meetings.meeting_actions(m)) if m else [],'native':n,'next_options':options,'next_action':message,'finding':message if not options else '', 'readiness_changed':changed}


def reconcile(actor,work_id,expected,adapter=None):
    from .factory import access,cancellation_status
    from .factory_execution import require_control
    from apps.documents.delivery import run_publication_once
    with transaction.atomic():
        w=Work.objects.select_for_update(of=('self',)).select_related('case').get(pk=work_id,definition=DEFINITION)
        access(actor,w.case,'factory.execute',DEFINITION);require_control(actor,w)
        if type(expected) is not int or w.revision!=expected or w.lease_until and w.lease_until>timezone.now():raise ValidationError('Refresh exact original minutes delivery')
        job=PublicationJob.objects.filter(publication__factory_work=w).filter(Q(status='unknown')|Q(status='leased',lease_until__lte=timezone.now())).order_by('pk').first()
        if not job:raise ValidationError('No original uncertain minutes delivery')
        event(actor,w.case,'factory.reconciliation_requested',work=w.pk,publication_job=job.pk)
    # Receipt lookup only: even authoritative absence cannot silently resend.
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
    if any(type(pk) is not int or pk<1 for pk in [expected,case_expected,job_id]) or w.revision!=expected:raise ValidationError('Refresh exact minutes and project revisions')
    if w.lease_until and w.lease_until>timezone.now():raise ValidationError('Wait for current worker before operating publication')
    if not PublicationJob.objects.filter(pk=job_id,publication__factory_work=w).exists() or action not in ['cancel','retry']:raise ValidationError('Choose the original native delivery and explicit recovery operation')
    operate_publication(actor,w.case_id,job_id,action,reason,case_expected)
    w.status=cancellation_status(w) if w.cancel_requested else 'ready';w.finding='';w.revision+=1;w.save();return w

"""F01 coordination of supplied incumbent references, never ledger posting."""
import hashlib,json,re
from datetime import timedelta
from django.core.exceptions import ValidationError,PermissionDenied
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from apps.core.models import Audit
from apps.core.services import lock_case,add_evidence,event
from apps.identity.services import require
from apps.documents.contracts import digest,validate
from apps.finance import ledger as native
from apps.finance.models import LedgerLineage
from apps.pmo.services import subject
from adapters.ledger import SuppliedQuickBooksReadAdapter
from .models import FactoryWork as Work,FactoryActivity as Activity,FactoryAttempt as Attempt
from .factory_delivery import investigation_key
from .factory_schedules import settled,finding

DEFINITION='finance-ledger/v1'
KIND='agent_private_ledger_intake'
PROTOCOL='factory-ledger-intake/v1'
SCHEMA={'type':'object','properties':{'protocol':{'const':PROTOCOL},'evidence_id':{'type':'integer','minimum':1},'predecessor_id':{'anyOf':[{'type':'integer','minimum':1},{'type':'null'}]}},'required':['protocol','evidence_id','predecessor_id'],'additionalProperties':False}

def readable(actor,case):
    native.readable(actor,case);require(actor,case,'ledger.private.read')

def inputs(actor,case,evidence_id,predecessor_id):
    readable(actor,case)
    data={'protocol':PROTOCOL,'evidence_id':evidence_id,'predecessor_id':predecessor_id};validate(SCHEMA,data)
    if type(evidence_id) is not int or predecessor_id is not None and type(predecessor_id) is not int:raise ValidationError('Exact integer source references required')
    e=subject(case,evidence_id,'ledger_source');body=SuppliedQuickBooksReadAdapter().source(e,native.SOURCE)
    for key in ['treatment_evidence_id','posting_evidence_id']:subject(case,body[key])
    if predecessor_id:
        previous=native.exact(case,predecessor_id)
        if previous.identity!=native.identity(case,body):raise ValidationError('Correction must retain incumbent source identity')
    return data,e,body

def source(work,actor=None,current=True):
    actor=actor or work.actor;readable(actor,work.case);e=work.source_head
    if not e or e.case_id!=work.case_id or e.kind!=KIND or e.sha256!=hashlib.sha256(e.body.encode()).hexdigest():raise ValidationError('Exact private ledger intake required')
    try:data=json.loads(e.body)
    except (ValueError,TypeError):raise ValidationError('Typed ledger intake required') from None
    validate(SCHEMA,data)
    audit=Audit.objects.filter(case=work.case,actor_id=e.created_by_id,action__in=['factory.ledger_intake','factory.ledger_source'],data={'evidence_id':e.pk,'sha256':e.sha256}).first()
    if not audit:raise ValidationError('Exact ledger intake provenance required')
    result=inputs(actor,work.case,data['evidence_id'],data['predecessor_id'])
    if native.identity(work.case,result[2])!=work.request['identity']:raise ValidationError('Original incumbent scope must be preserved')
    if current:
        readable(e.created_by,work.case)
        for action in ['evidence.add','factory.start' if audit.action=='factory.ledger_intake' else 'factory.manage']:require(e.created_by,work.case,action)
    return result

def capture_intake(actor,case,data,action):
    e=add_evidence(actor,case.pk,KIND,json.dumps(data,sort_keys=True),'psl:'+PROTOCOL)
    event(actor,case,action,evidence_id=e.pk,sha256=e.sha256);return e

@transaction.atomic
def start(actor,case_id,key,evidence_id,predecessor_id=None,expected=None):
    from .factory import access
    c=lock_case(actor,case_id,'factory.start',expected);access(actor,c,'factory.start',DEFINITION);require(actor,c,'evidence.add')
    if not isinstance(key,str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:-]{0,99}',key):raise ValidationError('Bounded stable work key required')
    data,e,body=inputs(actor,c,evidence_id,predecessor_id);request={'identity':native.identity(c,body)};business=digest([str(c.pk),DEFINITION,request['identity']])
    old=Work.objects.filter(case=c).filter(Q(key=key)|Q(definition=DEFINITION,business_key=business)).first()
    if old:
        if old.actor_id!=actor.pk or old.definition!=DEFINITION or old.request!=request or source(old,actor,False)[0]!=data:raise ValidationError('IDEMPOTENCY_CONFLICT: correct the existing incumbent reference work')
        return old
    w=Work.objects.create(case=c,actor=actor,key=key,definition=DEFINITION,request=request,request_hash=digest(request),business_key=business,source_head=capture_intake(actor,c,data,'factory.ledger_intake'))
    event(actor,c,'factory.started',work=w.pk,definition=DEFINITION);return w

def lineage(work):
    pk=Attempt.objects.filter(activity__work=work,phase='observed',result__head=work.source_head_id,result__has_key='captured_lineage').order_by('-pk').values_list('result__captured_lineage',flat=True).first()
    return LedgerLineage.objects.select_related('case','actor','evidence').filter(case=work.case,pk=pk).first()

def match(work,w,actor):
    data,e,body=source(work,actor)
    if w is None or w.evidence_id!=e.pk or w.payload!=body or w.predecessor_id!=data['predecessor_id'] or w.identity!=work.request['identity']:raise ValidationError('Exact captured supplied lineage required')
    return w

def verify(work,actor):
    w=match(work,lineage(work),actor);result=native.report(actor,work.case_id,w.pk);x=w.checks.latest('pk');r=x.decisions.latest('pk')
    if r.actor_id in [w.actor_id,x.actor_id]:raise ValidationError('Independent Finance review required for factory verification')
    return {'verified':True,'verification_scope':'selected_supplied_incumbent_reference','head':work.source_head_id,'lineage':w.pk,'source_evidence':w.evidence_id,'check':x.pk,'review':r.pk,'report_sha256':digest(result),'verification_mode':'supplied_read_only','posting_performed':False,'native_authenticity_verified':False,'financial_completeness_verified':False}

def report(work,actor):
    source(work,actor);w=lineage(work);n={'lineage':w.pk if w else None,'stage':'capture','finding':'','check':None,'review':None}
    if not w:return n
    try:
        match(work,w,actor);n['stage']='observation';x=w.checks.order_by('-pk').first()
        if not x:return n
        n['check']=x.pk;native.current(x);n['stage']='review';r=x.decisions.order_by('-pk').first();n['review']=r.pk if r else None
        verify(work,actor);n['stage']='complete'
    except (ValidationError,PermissionDenied) as exc:n['finding']=finding(exc)
    return n

def snapshot(work,value,reader=None):
    from .factory import access
    actor=reader or work.execution_actor;access(actor,work.case,'factory.read' if reader is not None else 'factory.execute',DEFINITION)
    data,e,body=source(work,actor);w=lineage(work);n=report(work,actor);latest={KIND:work.source_head,'ledger_source':e}
    missing=[k for k in value['required_evidence_kinds'] if k not in latest];stale=[k for k in value['required_evidence_kinds'] if k in latest and latest[k].created_at<timezone.now()-timedelta(seconds=value['max_age_seconds'])]
    state={'case_revision':work.case.revision,'profile':work.policy_id,'sources':[(work.source_head_id,work.source_head.sha256)],'native':n,'checks':list(w.checks.values_list('pk',flat=True)) if w else []}
    from .quickbooks_mcp import factory_state
    state['mcp']=factory_state(work,w,reader)
    state['hash']=digest(state);state['work_revision']=work.revision
    return state,latest,missing,stale,[],[]

def eligible(work,value,state,latest,missing,stale,tasks,jobs):
    if not Activity.objects.filter(work=work,key=investigation_key(work,state),status='succeeded').exists():return ['ACT04'],'Investigate exact supplied identity, uncertainty and human review needs'
    if missing or stale:return [],'Current configured supplied evidence required'
    n=state['native']
    if n['stage']=='capture':return ['ACT08'],'Capture supplied incumbent reference without posting'
    mcp=state.get('mcp')
    if mcp and mcp.get('status')=='completed' and not Attempt.objects.filter(activity__work=work,phase='observed',result__mcp_intent=mcp['intent'],result__has_key='mcp_result_evidence').exists():return ['ACT12'],'Reconcile the original MCP observation; no new external read'
    if n['stage']=='observation' and state.get('mcp',{} ) and state['mcp'].get('ready'):return ['ACT11'],'Reserve the configured scoped MCP read; no posting or Finance verification'
    if n['stage']=='complete':return ['ACT13'],'Verify current supplied observation and independent Finance decision'
    return [],n['finding'] or 'Await exact supplied observation or independent Finance decision'

def investigation(work,actor):
    """Read-only selected-evidence assessment using existing native authority/checks.

    Native ledger_agents projections require prior approved lineage and explicit
    field/owner/egress policies. They are not pre-review approval substitutes.
    """
    from types import SimpleNamespace
    data,e,body=source(work,actor);w=lineage(work)
    if w is None:
        candidates=list(LedgerLineage.objects.filter(case=work.case,evidence=e,predecessor_id=data['predecessor_id'],identity=work.request['identity']).order_by('pk')[:2])
        if len(candidates)==1:w=candidates[0]
    issues=[];questions=[];checks=[];citations={e.pk,body['treatment_evidence_id'],body['posting_evidence_id']};policy=None;rules=None
    try:
        policy,rules=native.config(work.case,native.RULES)
        for field in ['provider','realm','entity']:
            checks.append({'field':field,'matches_configured_scope':body[field]==rules[field]})
        checks.extend([{'field':'treatment_evidence_id','matches_configured_scope':body['treatment_evidence_id'] in rules['treatment_evidence_ids']},{'field':'incumbent_user_reference','matches_configured_scope':body['incumbent_user_reference'] in rules['incumbent_user_references']}])
        native.context(w or SimpleNamespace(case=work.case,payload=body))
    except (ValidationError,PermissionDenied) as exc:
        issues.append({'code':'configured_scope','detail':finding(exc)});questions.append('Finance must reconcile the listed source fields with current incumbent scope and treatment evidence.')
    try:native.day(body['transaction_date'])
    except (ValidationError,ValueError,TypeError) as exc:
        issues.append({'code':'transaction_date','detail':finding(exc)});questions.append('Obtain a corrected supplied transaction date; no date is inferred.')
    provenance=[]
    for ref in body['provenance']:
        query=native.FinanceRun.objects.filter(case=work.case,pk=ref['id'],kind='mapping') if ref['kind']=='finance_mapping' else native.ScheduleWork.objects.filter(case=work.case,pk=ref['id'],kind=ref['kind'])
        available=query.exists();provenance.append({'kind':ref['kind'],'id':ref['id'],'same_case_reference_exists':available})
        if not available:issues.append({'code':'provenance','detail':'Selected '+ref['kind']+' reference is not present in this case.'})
    x=w.checks.select_related('evidence').order_by('-pk').first() if w else None;observation={'check':x.pk if x else None,'state':x.payload['state'] if x else None,'mismatched_fields':[],'current':False};decision={'review':None,'verdict':None,'independent':False,'currently_approved':False}
    if x:
        citations.add(x.evidence_id)
        observation['mismatched_fields']=[k for k in ['provider','realm','entity','source_reference','target_reference','transaction_date','accounting_period','treatment_evidence_id'] if x.payload[k]!=body[k]]
        try:
            if rules is None:raise ValidationError('Current verification policy required')
            SuppliedQuickBooksReadAdapter().checked_observation(w,x,native.RESPONSE,rules);native.current(x);observation['current']=True
        except (ValidationError,PermissionDenied) as exc:issues.append({'code':'observation','detail':finding(exc)})
        r=x.decisions.order_by('-pk').first()
        if r:decision.update(review=r.pk,verdict=r.verdict,independent=r.actor_id not in [w.actor_id,x.actor_id]);citations.add(r.evidence_id)
        try:
            native.report(actor,work.case_id,w.pk)
            if not decision['independent']:raise ValidationError('Independent Finance review required')
            decision['currently_approved']=True
        except (ValidationError,PermissionDenied) as exc:issues.append({'code':'review','detail':finding(exc)})
    else:issues.append({'code':'observation','detail':'No observation is recorded for this exact supplied source.'})
    if not observation['current']:questions.append('Obtain exact current found target/version evidence and resolve native holds before any retry is considered. This work has no posting or retry tool.')
    if not decision['currently_approved']:questions.append('Obtain the configured independent Finance decision for the latest exact observation; historical approval is not reused.')
    if any(not p['same_case_reference_exists'] for p in provenance):questions.append('The source owner must correct the selected native provenance references.')
    return {'head':work.source_head_id,'selected_source_evidence':e.pk,'citations':sorted(citations),'reported_outcome':body['outcome'],'target_supplied':body['target_reference'] is not None,'verification_policy':policy.pk if policy else None,'scope_checks':checks,'provenance_checks':provenance,'observation_assessment':observation,'decision_assessment':decision,'findings':issues,'same_identity_count':LedgerLineage.objects.filter(case=work.case,identity=work.request['identity']).count(),'questions':list(dict.fromkeys(questions)),'cross_case_details_read':False,'posting_performed':False,'approval_granted':False,'assessment_mode':'native_selected_evidence_checks','native_authenticity_verified':False}

def act(work,choice,value,latest,missing,tasks,jobs):
    from .factory import access
    actor=work.execution_actor;c=native.locked(actor,work.case_id,'factory.execute');access(actor,c,'factory.execute',DEFINITION)
    if c.revision!=work.case.revision:raise ValidationError('STALE_VERSION: ledger context changed')
    data,e,body=source(work,actor);kind=choice['activity']
    if kind=='ACT04':
        require(actor,c,'agent.ledger');return investigation(work,actor)
    if kind=='ACT08':
        existing=list(LedgerLineage.objects.filter(case=c,evidence=e,predecessor_id=data['predecessor_id'],identity=work.request['identity']).order_by('pk')[:2])
        if len(existing)>1:raise ValidationError('Ambiguous existing captures require native Finance resolution; never recapture or retry')
        w=existing[0] if existing else native.capture(actor,c.pk,e.pk,data['predecessor_id'],c.revision)
        match(work,w,actor)
        return {'head':work.source_head_id,'captured_lineage':w.pk,'reused_existing_lineage':bool(existing),'posting_performed':False}
    if kind=='ACT11':
        from .quickbooks_mcp import factory_state,reserve
        w=match(work,lineage(work),actor);state=factory_state(work,w)
        if not state or not state.get('ready'):raise ValidationError('Current eligible MCP read reservation required')
        intent=reserve(actor,c.pk,w.pk,state['contract'],caller_mode='agent',factory_work=work.pk)
        return {'head':work.source_head_id,'mcp_intent':intent.pk,'mcp_dispatch_intent':intent.pk,'state':'reserved_pending_external_read','posting_performed':False,'finance_verification':False}
    if kind=='ACT12':
        from .quickbooks_mcp import factory_state,reconcile
        w=match(work,lineage(work),actor);state=factory_state(work,w)
        if not state or state.get('status')!='completed':raise ValidationError('Completed original MCP observation required')
        return dict(reconcile(actor,c.pk,state['intent']),head=work.source_head_id)
    if kind=='ACT13':result=verify(work,actor);work.status='verified';return result
    raise ValidationError('Ledger posting and human decisions are not agent capabilities')

@transaction.atomic
def command(actor,work_id,expected,case_expected,action,target=None,evidence=None,verdict=None):
    from .factory import access
    w=Work.objects.select_for_update(of=('self',)).select_related('case','source_head','actor').get(pk=work_id,definition=DEFINITION);access(actor,w.case,'factory.read',DEFINITION)
    if type(expected) is not int or w.revision!=expected or w.cancel_requested or w.status in ['cancelled','followup_needed']:raise ValidationError('Refresh active incumbent work')
    settled(w);s=match(w,lineage(w),actor)
    if action=='observe':
        if target!=s.pk:raise ValidationError('Exact selected lineage required')
        return native.verify(actor,w.case_id,s.pk,evidence,case_expected)
    if action=='review':
        x=s.checks.order_by('-pk').first()
        if not x or target!=x.pk:raise ValidationError('Exact latest selected observation required')
        if actor.pk in [s.actor_id,x.actor_id]:raise PermissionDenied('Independent Finance reviewer required')
        return native.review(actor,w.case_id,x.pk,evidence,verdict,case_expected)
    raise ValidationError('Typed native observation or review command required')

@transaction.atomic
def correct(actor,work_id,expected,case_expected,evidence_id,predecessor_id,reason):
    from .factory import access
    w=Work.objects.select_for_update(of=('self',)).select_related('case','source_head','actor').get(pk=work_id,definition=DEFINITION);access(actor,w.case,'factory.manage',DEFINITION);c=native.locked(actor,w.case_id,'evidence.add',case_expected);w.case=c
    if type(expected) is not int or w.revision!=expected or w.cancel_requested:raise ValidationError('Refresh active incumbent work')
    settled(w)
    if not isinstance(reason,str) or not reason.strip() or len(reason)>2000:raise ValidationError('Bounded correction rationale required')
    old=source(w,actor,False)[0];new,e,body=inputs(actor,c,evidence_id,predecessor_id);s=lineage(w)
    if native.identity(c,body)!=w.request['identity']:raise ValidationError('Correction retains original source identity')
    if new==old:raise ValidationError('Supply corrected evidence; refresh observation or review through native commands')
    if s and predecessor_id!=s.pk:raise ValidationError('Correction must explicitly extend this captured lineage')
    before=w.source_head_id;w.source_head=capture_intake(actor,c,new,'factory.ledger_source');w.status='ready';w.finding='';w.revision+=1;w.save();event(actor,c,'factory.ledger_corrected',work=w.pk,previous=before,current=w.source_head_id,reason=reason);return w

def projection(actor,work):
    from .factory import profile
    readable(actor,work.case);source(work,actor,False);n={'stage':'held'};options=[];message='';changed=False
    try:
        _,v=profile(work,recovery=True);state,latest,missing,stale,tasks,jobs=snapshot(work,v,reader=actor);n=state['native'];options,message=eligible(work,v,state,latest,missing,stale,tasks,jobs)
        if work.status=='verified':verify(work,actor)
    except (ValidationError,PermissionDenied) as exc:message=finding(exc);changed=work.status=='verified'
    w=lineage(work);names=[];can_review=False
    if w and n['stage']=='review' and not work.cancel_requested:
        from django.contrib.auth import get_user_model
        x=w.checks.order_by('-pk').first()
        for reviewer in get_user_model().objects.filter(is_active=True,grant__case=work.case,grant__action='ledger.review',grant__active=True).distinct():
            if not x or reviewer.pk in [w.actor_id,x.actor_id]:continue
            try:readable(reviewer,work.case);native.authority(reviewer,x)
            except (ValidationError,PermissionDenied):continue
            names.append(reviewer.get_full_name() or reviewer.username);can_review=can_review or reviewer.pk==actor.pk
    return {'lineage':w,'native':n,'next_options':options,'next_action':message,'finding':message if not options else '', 'readiness_changed':changed,'reviewer_names':names,'can_review':can_review}

@transaction.atomic
def recheck(actor,work_id,expected,case_expected,reason):
    """Explicitly reopen stale certification, without new source, posting or budget reset."""
    from .factory import access
    w=Work.objects.select_for_update(of=('self',)).select_related('case','source_head','actor').get(pk=work_id,definition=DEFINITION)
    access(actor,w.case,'factory.manage',DEFINITION);w.case=native.locked(actor,w.case_id,'factory.manage',case_expected)
    if type(expected) is not int or w.revision!=expected or w.cancel_requested:raise ValidationError('Refresh active incumbent work')
    settled(w)
    if not isinstance(reason,str) or not reason.strip() or len(reason)>2000:raise ValidationError('Bounded recheck rationale required')
    source(w,actor);w.status='ready';w.finding='';w.revision+=1;w.save();event(actor,w.case,'factory.ledger_recheck',work=w.pk,reason=reason);return w

@transaction.atomic
def restart(actor,work_id,expected,case_expected,reason):
    """Fresh human instruction restarts only settled cancelled coordination."""
    from .factory import access
    w=Work.objects.select_for_update(of=('self',)).select_related('case','source_head','actor').get(pk=work_id,definition=DEFINITION)
    access(actor,w.case,'factory.manage',DEFINITION);w.case=native.locked(actor,w.case_id,'factory.manage',case_expected)
    if type(expected) is not int or w.revision!=expected or w.status!='cancelled':raise ValidationError('Refresh settled cancelled work')
    settled(w)
    if not isinstance(reason,str) or not reason.strip() or len(reason)>2000:raise ValidationError('Bounded fresh instruction required')
    source(w,actor,False);w.status='ready';w.cancel_requested=False;w.finding='';w.revision+=1;w.save();event(actor,w.case,'factory.ledger_restarted',work=w.pk,reason=reason);return w

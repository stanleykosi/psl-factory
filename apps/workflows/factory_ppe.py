"""F07 coordination over native PPE truth. No accounting policy or approval is invented."""
import hashlib,json,re
from datetime import timedelta
from django.core.exceptions import ValidationError,PermissionDenied
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from apps.core.models import Audit
from apps.core.services import lock_case,add_evidence,event
from apps.identity.models import Grant
from apps.identity.services import require
from apps.documents.contracts import digest,validate
from apps.finance import ppe,analysis
from apps.finance.models import FinanceRun,ScheduleWork
from .models import FactoryWork as Work,FactoryActivity as Activity,FactoryAttempt as Attempt
from .factory_delivery import investigation_key

DEFINITION='finance-ppe/v1'
KIND='agent_private_ppe_intake'
PROTOCOL='factory-ppe-intake/v1'
ID={'anyOf':[{'type':'integer','minimum':1},{'type':'null'}]}
SCHEMA={'type':'object','properties':{'protocol':{'const':PROTOCOL},'register_id':{'type':'integer','minimum':1},'prior_id':ID,'ledger_id':ID},'required':['protocol','register_id','prior_id','ledger_id'],'additionalProperties':False}

def finding(exc):return '; '.join(exc.messages) if isinstance(exc,ValidationError) else str(exc)

def inputs(case,register_id,prior_id,ledger_id):
    data={'protocol':PROTOCOL,'register_id':register_id,'prior_id':prior_id,'ledger_id':ledger_id};validate(SCHEMA,data)
    if any(v is not None and type(v) is not int for k,v in data.items() if k!='protocol'):raise ValidationError('Exact integer native references required')
    register=ppe.exact(case,register_id,'ppe_register');ppe.current(register)
    if prior_id:ppe.exact(case,prior_id,'ppe_schedule')
    if ledger_id and not FinanceRun.objects.filter(case=case,pk=ledger_id,kind='mapping').exists():raise ValidationError('Select this case exact accounting note')
    return register,data

def source(work,actor=None,current=True):
    ppe.readable(actor or work.actor,work.case);e=work.source_head
    if not e or e.case_id!=work.case_id or e.kind!=KIND or e.sha256!=hashlib.sha256(e.body.encode()).hexdigest():raise ValidationError('Exact PPE source selection required')
    try:data=json.loads(e.body)
    except (ValueError,TypeError):raise ValidationError('Typed PPE intake required') from None
    validate(SCHEMA,data)
    audit=Audit.objects.filter(case=work.case,actor_id=e.created_by_id,action__in=['factory.ppe_intake','factory.ppe_source'],data={'evidence_id':e.pk,'sha256':e.sha256}).first()
    r=ppe.exact(work.case,data['register_id'],'ppe_register')
    if not audit or r.reference!=work.request['register_reference']:raise ValidationError('Exact native register provenance required')
    if current:
        ppe.current(r)
        for action in ['case.read','finance.read','ppe.read','evidence.add','factory.start' if audit.action=='factory.ppe_intake' else 'factory.manage']:require(e.created_by,work.case,action)
    return r,data

def capture(actor,case,data,action):
    e=add_evidence(actor,case.pk,KIND,json.dumps(data,sort_keys=True),'psl:'+PROTOCOL)
    event(actor,case,action,evidence_id=e.pk,sha256=e.sha256);return e

@transaction.atomic
def start(actor,case_id,key,register_id,prior_id,ledger_id,reference,expected=None):
    from .factory import access
    c=lock_case(actor,case_id,'factory.start',expected);access(actor,c,'factory.start',DEFINITION);ppe.readable(actor,c);require(actor,c,'evidence.add')
    if not isinstance(key,str) or not key.isascii() or not 1<=len(key)<=100 or not isinstance(reference,str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:-]{0,99}',reference):raise ValidationError('Bounded work key and stable PPE schedule reference required')
    r,data=inputs(c,register_id,prior_id,ledger_id)
    payload={'register_reference':r.reference,'reference':reference};sha=digest(payload);business=digest([str(c.pk),DEFINITION,r.reference])
    old=Work.objects.filter(case=c).filter(Q(key=key)|Q(definition=DEFINITION,business_key=business)).first()
    if old:
        if old.actor_id!=actor.pk or old.definition!=DEFINITION or old.request_hash!=sha or source(old,actor)[1]!=data:raise ValidationError('IDEMPOTENCY_CONFLICT: correct the existing PPE work')
        return old
    w=Work.objects.create(case=c,actor=actor,key=key,definition=DEFINITION,request=payload,request_hash=sha,business_key=business,source_head=capture(actor,c,data,'factory.ppe_intake'))
    event(actor,c,'factory.started',work=w.pk,definition=DEFINITION);return w

def schedule(work):
    pk=Attempt.objects.filter(activity__work=work,phase='observed',result__head=work.source_head_id,result__has_key='schedule').order_by('-pk').values_list('result__schedule',flat=True).first()
    return ScheduleWork.objects.select_related('case','actor','parent').filter(pk=pk,case=work.case,kind='ppe_schedule').first()

def report(work,actor):
    r,data=source(work,actor);w=schedule(work)
    result={'register':r.pk,'schedule':w.pk if w else None,'stage':'source_review','finding':'','ledger':data['ledger_id'],'ledger_posted':False,'full_owner_oracle_acceptance':'unresolved'}
    try:
        ppe.approved(r,'register')
        if r.result['date_basis_ambiguous']:ppe.approved(r,'basis')
        result['stage']='calculation'
        if not w:return result
        ppe.current(w)
        if w.payload!={'register_id':r.pk,'prior_id':data['prior_id']} or w.parent_id!=data['ledger_id']:raise ValidationError('Exact selected register, prior and accounting note required')
        if w.result['status']!='ready':raise ValidationError(w.result['findings'])
        result['stage']='output_review';ppe.approved(w,'schedule')
        result['stage']='complete'
    except (ValidationError,PermissionDenied) as exc:result['finding']=finding(exc)
    return result

def snapshot(work,value,reader=None):
    from .factory import access
    actor=reader or work.execution_actor;access(actor,work.case,'factory.read' if reader is not None else 'factory.execute',DEFINITION);ppe.readable(actor,work.case)
    r,data=source(work,actor);native=report(work,actor);w=schedule(work)
    # Private asset values never enter planner evidence or agent investigation results.
    latest={KIND:work.source_head,'ppe_register':r.evidence}
    missing=[k for k in value['required_evidence_kinds'] if k not in latest]
    stale=[k for k in value['required_evidence_kinds'] if k in latest and latest[k].created_at<timezone.now()-timedelta(seconds=value['max_age_seconds'])]
    state={'case_revision':work.case.revision,'profile':work.policy_id,'sources':[(work.source_head_id,work.source_head.sha256)],'native':native,'checks':{'register':r.sha256,'schedule':w.sha256 if w else None,'reviews':list(r.reviews.values_list('pk',flat=True))+list(w.reviews.values_list('pk',flat=True)) if w else list(r.reviews.values_list('pk',flat=True))}}
    state['hash']=digest(state);state['work_revision']=work.revision
    return state,latest,missing,stale,[],[]

def eligible(work,value,state,latest,missing,stale,tasks,jobs):
    if not Activity.objects.filter(work=work,key=investigation_key(work,state),status='succeeded').exists():return ['ACT04'],'Investigate exact register, human reviews and missing rules'
    if missing or stale:return [],'Current configured intake evidence required'
    n=state['native']
    if n['finding']:return [],n['finding']
    if n['stage']=='calculation' and not n['schedule']:return ['ACT08'],'Calculate with native configured PPE rules'
    if n['stage']=='complete':return ['ACT13'],'Verify reviewed schedule and read-only accounting note linkage'
    return [],'Await exact human '+n['stage'].replace('_',' ')

def verify(work,actor):
    ppe.readable(actor,work.case)
    r,data=source(work,actor);w=schedule(work)
    if not w:raise ValidationError('Native schedule required')
    ppe.current(w);review=ppe.approved(w,'schedule');register_review=ppe.approved(r,'register')
    if w.payload!={'register_id':r.pk,'prior_id':data['prior_id']} or w.parent_id!=data['ledger_id'] or w.result['status']!='ready':raise ValidationError('Exact current native source and ready schedule required')
    ledger_reviews=None
    if w.parent:
        # Native certification includes current exact policies, source and human review.
        gaps=analysis.certification_findings(w.parent)
        if gaps:raise ValidationError(gaps)
        if w.parent.kind!='mapping':raise ValidationError('Native PPE requires an exact Finance mapping note')
        ledger_reviews={'source':w.parent.snapshot['source_review'],'rules':w.parent.snapshot['reviews']}
    return {'verified':True,'verification_scope':'selected_supplied_ppe_register_reviewed_schedule_and_read_only_note','head':work.source_head_id,'register':r.pk,'register_review':register_review.pk,'schedule':w.pk,'schedule_sha256':w.sha256,'schedule_review':review.pk,'ledger':w.parent_id,'ledger_reviews':ledger_reviews,'ledger_posted':False,'native_source_verified':False,'full_owner_oracle_acceptance':'unresolved'}

def act(work,choice,value,latest,missing,tasks,jobs):
    from .factory import access
    c=lock_case(work.execution_actor,work.case_id,'factory.execute');access(work.execution_actor,c,'factory.execute',DEFINITION);ppe.readable(work.execution_actor,c)
    list(Grant.objects.select_for_update().filter(case=c).order_by('pk'))
    if c.revision!=work.case.revision:raise ValidationError('STALE_VERSION: native PPE sources changed')
    r,data=source(work,work.execution_actor);kind=choice['activity']
    if kind=='ACT04':return {'head':work.source_head_id,'investigation':report(work,work.execution_actor),'questions':['Finance must supply unknown classification, useful life, residual and method values.','Review exact source, period basis and output. A selected note is read-only, not a ledger posting.'],'financial_values_read':False,'approval_granted':False}
    if kind=='ACT08':
        ppe.approved(r,'register')
        if r.result['date_basis_ambiguous']:ppe.approved(r,'basis')
        w=ppe.prepare(work.execution_actor,c.pk,work.request['reference'],r.pk,data['prior_id'],data['ledger_id'],c.revision)
        return {'head':work.source_head_id,'schedule':w.pk,'status':w.result['status'],'ledger_posted':False}
    if kind=='ACT13':
        require(work.execution_actor,c,'ppe.report');result=verify(work,work.execution_actor);work.status='verified';return result
    raise ValidationError('PPE human decisions cannot be performed by a model')

def settled(w):
    from apps.agents.factory_coordinator import pending,has_receipt
    if w.lease_until and w.lease_until>timezone.now():raise ValidationError('CONFLICT: current worker owns this work')
    p=pending(w)
    if p and not has_receipt(p):raise ValidationError('Reconcile the original planning response before changing this work')

@transaction.atomic
def correct(actor,work_id,expected,case_expected,register_id,prior_id,ledger_id,reason):
    from .factory import access
    w=Work.objects.select_for_update(of=('self',)).select_related('case','source_head','actor').get(pk=work_id,definition=DEFINITION)
    access(actor,w.case,'factory.manage',DEFINITION);ppe.readable(actor,w.case);c=lock_case(actor,w.case_id,'evidence.add',case_expected);w.case=c
    if type(expected) is not int or w.revision!=expected or w.cancel_requested or w.status in ['cancelled','followup_needed']:raise ValidationError('Refresh current active PPE work')
    settled(w);analysis.note(reason);old,data=source(w,actor,False);r,new=inputs(c,register_id,prior_id,ledger_id)
    if r.reference!=old.reference:raise ValidationError('Correction must retain the same native register identity')
    if data==new:
        current=schedule(w)
        if not current:raise ValidationError('Provide changed native source selection')
        try:source(w,actor);ppe.current(current);ppe.approved(current,'schedule')
        except (ValidationError,PermissionDenied):pass
        else:raise ValidationError('Current reviewed output requires a genuine source change')
    before=w.source_head_id;w.source_head=capture(actor,c,new,'factory.ppe_source');w.status='ready';w.finding='';w.revision+=1;w.save()
    event(actor,c,'factory.ppe_corrected',work=w.pk,previous=before,current=w.source_head_id,reason=reason);return w

@transaction.atomic
def review(actor,work_id,expected,case_expected,target,purpose,verdict,evidence,note):
    from .factory import access
    w=Work.objects.select_for_update(of=('self',)).select_related('case','source_head','actor').get(pk=work_id,definition=DEFINITION)
    access(actor,w.case,'factory.read',DEFINITION);r,_=source(w,actor);s=schedule(w)
    if type(expected) is not int or w.revision!=expected or w.cancel_requested:raise ValidationError('Refresh active PPE work')
    settled(w)
    if target!= (r.pk if purpose in ['register','basis'] else s.pk if s and purpose=='schedule' else None):raise ValidationError('Review exact selected native target')
    return ppe.review(actor,w.case_id,target,purpose,verdict,evidence,note,case_expected)

def projection(actor,work):
    from .factory import profile
    ppe.readable(actor,work.case);r,data=source(work,actor,False);s=schedule(work);options=[];changed=False;message='';n={}
    try:
        _,v=profile(work,recovery=True);state,latest,missing,stale,tasks,jobs=snapshot(work,v,reader=actor);n=state['native'];options,message=eligible(work,v,state,latest,missing,stale,tasks,jobs)
        if work.status=='verified':verify(work,actor)
    except (ValidationError,PermissionDenied) as exc:message=finding(exc);changed=work.status=='verified'
    pending_reviews=[];reviewer_names=[];can_review=False
    if not work.cancel_requested and work.status not in ['cancelled','followup_needed']:
        candidates=[(r,'register')]+([(r,'basis')] if r.result['date_basis_ambiguous'] else [])
        if s and s.result['status']=='ready':candidates.append((s,'schedule'))
        from django.contrib.auth import get_user_model
        for target,purpose in candidates:
            try:ppe.current(target);ppe.approved(target,purpose)
            except (ValidationError,PermissionDenied):
                pending_reviews.append({'target':target.pk,'purpose':purpose})
                for user in get_user_model().objects.filter(is_active=True,grant__case=work.case,grant__active=True,grant__action='ppe.review').distinct():
                    try:ppe.authority(user,target,purpose)
                    except (ValidationError,PermissionDenied):continue
                    reviewer_names.append(user.get_full_name() or user.username)
                    if user.pk==actor.pk:can_review=True
    return {'pending_reviews':pending_reviews,'reviewer_names':sorted(set(reviewer_names)),'can_review':can_review,'register':r,'schedule':s,'inputs':data,'next_options':options,'next_action':message,'readiness_changed':changed,'native':n,'finding':message if not options else ''}

@transaction.atomic
def restart(actor,work_id,expected,case_expected,reason):
    """A new human instruction can resume settled preparation, never erase its history."""
    from .factory import access
    w=Work.objects.select_for_update(of=('self',)).select_related('case','source_head','actor').get(pk=work_id,definition=DEFINITION)
    access(actor,w.case,'factory.manage',DEFINITION);lock_case(actor,w.case_id,'factory.manage',case_expected)
    if type(expected) is not int or expected!=w.revision or w.status!='cancelled' or not w.cancel_requested:raise ValidationError('Only settled stopped PPE preparation can receive a fresh instruction')
    settled(w);analysis.note(reason);source(w,actor,False)
    w.cancel_requested=False;w.status='ready';w.finding='';w.revision+=1;w.save()
    event(actor,w.case,'factory.ppe_restarted',work=w.pk,reason=reason,spent=w.budget_used);return w

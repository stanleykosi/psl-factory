"""Selected F12/F13 native preparation. Finance owns treatment, inclusion and reviews."""
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
from apps.finance import schedules as native,analysis
from apps.finance.models import FinanceRun,ScheduleWork,ScheduleAdjustment
from apps.pmo.services import subject
from adapters.schedules import SuppliedScheduleAdapter
from .models import FactoryWork as Work,FactoryActivity as Activity,FactoryAttempt as Attempt
from .factory_delivery import investigation_key

DEFINITION='finance-schedules/v1'
KIND='agent_private_schedules_intake'
PROTOCOL='factory-schedules-intake/v1'
ID={'anyOf':[{'type':'integer','minimum':1},{'type':'null'}]}
SCHEMA={'type':'object','properties':{'protocol':{'const':PROTOCOL},'kind':{'enum':['income','inventory']},'parent_id':ID,'evidence_id':{'type':'integer','minimum':1},'payload':{'anyOf':[native.DETAIL,{'type':'null'}]}},'required':['protocol','kind','parent_id','evidence_id','payload'],'additionalProperties':False}

def finding(exc):return '; '.join(exc.messages) if isinstance(exc,ValidationError) else str(exc)

def inputs(actor,case,kind,parent_id,evidence_id,payload,check=True):
    native.readable(actor,case)
    data={'protocol':PROTOCOL,'kind':kind,'parent_id':parent_id,'evidence_id':evidence_id,'payload':payload};validate(SCHEMA,data)
    if type(evidence_id) is not int or parent_id is not None and type(parent_id) is not int:raise ValidationError('Exact integer native references required')
    e=subject(case,evidence_id,'income_detail' if kind=='income' else 'schedule_inventory')
    parent=FinanceRun.objects.filter(case=case,pk=parent_id,kind='mapping').first() if parent_id else None
    if kind=='income' and not parent:raise ValidationError('Select this case exact mapping note')
    if kind=='inventory' and (parent_id is not None or payload is not None):raise ValidationError('Inventory comes only from exact supplied evidence')
    body=payload if kind=='income' else SuppliedScheduleAdapter().read(e)
    validate(native.DETAIL if kind=='income' else native.INVENTORY_BODY,body)
    if len(json.dumps(data))>120000:raise ValidationError('Bounded supplied schedule input required')
    if check and parent:analysis.ensure_current(parent)
    return data,e,parent,body

def source(work,actor=None,current=True):
    actor=actor or work.actor;native.readable(actor,work.case);e=work.source_head
    if not e or e.case_id!=work.case_id or e.kind!=KIND or e.sha256!=hashlib.sha256(e.body.encode()).hexdigest():raise ValidationError('Exact schedule intake required')
    try:data=json.loads(e.body)
    except (ValueError,TypeError):raise ValidationError('Typed schedule intake required') from None
    validate(SCHEMA,data)
    audit=Audit.objects.filter(case=work.case,actor_id=e.created_by_id,action__in=['factory.schedules_intake','factory.schedules_source'],data={'evidence_id':e.pk,'sha256':e.sha256}).first()
    if not audit or data['kind']!=work.request['kind']:raise ValidationError('Exact schedule source provenance required')
    selected=inputs(actor,work.case,data['kind'],data['parent_id'],data['evidence_id'],data['payload'],current)
    if current:
        native.readable(e.created_by,work.case)
        for action in ['evidence.add','factory.start' if audit.action=='factory.schedules_intake' else 'factory.manage']:require(e.created_by,work.case,action)
    return selected

def capture(actor,case,data,action):
    e=add_evidence(actor,case.pk,KIND,json.dumps(data,sort_keys=True),'psl:'+PROTOCOL)
    event(actor,case,action,evidence_id=e.pk,sha256=e.sha256);return e

@transaction.atomic
def start(actor,case_id,key,kind,parent_id,evidence_id,payload,reference,expected=None):
    from .factory import access
    c=lock_case(actor,case_id,'factory.start',expected);access(actor,c,'factory.start',DEFINITION);require(actor,c,'evidence.add')
    if not isinstance(key,str) or not key.isascii() or not 1<=len(key)<=100 or not isinstance(reference,str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:-]{0,99}',reference):raise ValidationError('Bounded work key and stable schedule reference required')
    data,_,_,_=inputs(actor,c,kind,parent_id,evidence_id,payload)
    request={'kind':kind,'reference':reference};sha=digest(request);business=digest([str(c.pk),DEFINITION,kind,reference])
    old=Work.objects.filter(case=c).filter(Q(key=key)|Q(definition=DEFINITION,business_key=business)).first()
    if old:
        if old.actor_id!=actor.pk or old.definition!=DEFINITION or old.request_hash!=sha or source(old,actor)[0]!=data:raise ValidationError('IDEMPOTENCY_CONFLICT: correct the existing schedules work')
        return old
    w=Work.objects.create(case=c,actor=actor,key=key,definition=DEFINITION,request=request,request_hash=sha,business_key=business,source_head=capture(actor,c,data,'factory.schedules_intake'))
    event(actor,c,'factory.started',work=w.pk,definition=DEFINITION);return w

def schedule(work):
    pk=Attempt.objects.filter(activity__work=work,phase='observed',result__head=work.source_head_id,result__has_key='schedule').order_by('-pk').values_list('result__schedule',flat=True).first()
    return ScheduleWork.objects.select_related('case','actor','parent').filter(pk=pk,case=work.case,kind=work.request['kind'],reference=work.request['reference']).first()

def match(work,w,data,e,parent,body):
    if w.evidence_id!=e.pk or w.parent_id!=(parent.pk if parent else None) or w.payload!=body:raise ValidationError('Exact selected evidence, mapping note and supplied detail required')
    native.current(w)

def report(work,actor):
    data,e,parent,body=source(work,actor);w=schedule(work)
    result={'schedule':w.pk if w else None,'kind':data['kind'],'stage':'preparation','finding':'','ledger_posted':False,'native_workbook_verified':False}
    try:
        if parent:
            gaps=analysis.certification_findings(parent)
            if gaps:raise ValidationError(gaps)
        if not w:return result
        result['stage']='rebuild';match(work,w,data,e,parent,body)
        if w.result['status']!='ready':result['stage']='source_correction';raise ValidationError(w.result['findings'])
        result['stage']='output_review';native.approved(w)
        result['stage']='complete'
    except (ValidationError,PermissionDenied) as exc:result['finding']=finding(exc)
    return result

def snapshot(work,value,reader=None):
    from .factory import access
    actor=reader or work.execution_actor;access(actor,work.case,'factory.read' if reader is not None else 'factory.execute',DEFINITION)
    data,e,parent,body=source(work,actor);w=schedule(work);n=report(work,actor)
    latest={KIND:work.source_head,e.kind:e}
    missing=[k for k in value['required_evidence_kinds'] if k not in latest]
    stale=[k for k in value['required_evidence_kinds'] if k in latest and latest[k].created_at<timezone.now()-timedelta(seconds=value['max_age_seconds'])]
    state={'case_revision':work.case.revision,'profile':work.policy_id,'sources':[(work.source_head_id,work.source_head.sha256)],'native':n,'checks':{'evidence':e.sha256,'parent':parent.operation_key if parent else None,'schedule':w.sha256 if w else None,'reviews':list(w.reviews.values_list('pk',flat=True)) if w else []}}
    state['hash']=digest(state);state['work_revision']=work.revision
    return state,latest,missing,stale,[],[]

def eligible(work,value,state,latest,missing,stale,tasks,jobs):
    if not Activity.objects.filter(work=work,key=investigation_key(work,state),status='succeeded').exists():return ['ACT04'],'Investigate selected evidence, native checks and human review needs'
    if missing or stale:return [],'Current configured intake evidence required'
    n=state['native']
    if n['finding']:return [],n['finding']
    if n['stage']=='preparation':return ['ACT08'],'Prepare exact supplied detail with native schedule rules'
    if n['stage']=='complete':return ['ACT13'],'Verify exact reviewed native output and downstream links'
    return [],'Await native Finance review'

def verify(work,actor):
    data,e,parent,body=source(work,actor);w=schedule(work)
    if not w:raise ValidationError('Native schedule required')
    match(work,w,data,e,parent,body);review=native.approved(w)
    if w.result['status']!='ready':raise ValidationError('Resolve native dependent holds')
    if parent:
        gaps=analysis.certification_findings(parent)
        if gaps:raise ValidationError(gaps)
    return {'verified':True,'verification_scope':'selected_supplied_income_detail' if w.kind=='income' else 'selected_supplied_schedule_dependency_inventory','head':work.source_head_id,'schedule':w.pk,'schedule_sha256':w.sha256,'schedule_review':review.pk,'parent':w.parent_id,'source_evidence':e.pk,'ledger_posted':False,'native_workbook_verified':False,'complete_inventory':w.result.get('complete_inventory',False),'consumer_refs':sorted({x for s in body.get('schedules',[]) for x in s['consumer_refs']}),'adjustment_ids':list(ScheduleAdjustment.objects.filter(work=w).order_by('pk').values_list('adjustment_id',flat=True))}

def act(work,choice,value,latest,missing,tasks,jobs):
    from .factory import access
    c=lock_case(work.execution_actor,work.case_id,'factory.execute');access(work.execution_actor,c,'factory.execute',DEFINITION)
    list(Grant.objects.select_for_update().filter(case=c).order_by('pk'))
    if c.revision!=work.case.revision:raise ValidationError('STALE_VERSION: schedule context changed')
    data,e,parent,body=source(work,work.execution_actor);kind=choice['activity']
    if kind=='ACT04':
        if data['kind']=='income':
            accounts={r['account'] for r in parent.result['rows'] if r['report_line']==body['report_line']}
            findings=[{'key':r['key'],'proposed_treatment':r['relationship'],'duplicate_state':r['duplicate_state'],'source_overlap':bool(accounts & set(r['source_accounts'])),'duplicate_resolution_evidence':r['duplicate_resolution_evidence_id'],'unknown_amount':r['amount'] is None,'account_line_count':len(r['adjustment_lines'])} for r in body['rows']]
        else:
            keys={r['key'] for r in body['schedules']}
            findings=[{'key':r['key'],'owner_selected':r['owner_id'] is not None,'unselected_dependencies':sorted(set(r['dependencies'])-keys),'source_link_count':len(r['source_evidence_ids']),'formula_link_count':len(r['formula_evidence_ids']),'validation_package':r['validation_package_id'],'consumer_refs':r['consumer_refs']} for r in body['schedules']]
        return {'head':work.source_head_id,'source_findings':findings,'investigation':report(work,work.execution_actor),'questions':['Finance must decide manual detail treatment and resolve duplicate evidence.','Supplied inventory does not establish complete native workbook scope. Each schedule needs its own owner, dependencies and AF13 evidence.'],'private_amounts_disclosed':False,'approval_granted':False}
    if kind=='ACT08':
        w=native.prepare(work.execution_actor,c.pk,data['kind'],work.request['reference'],data['parent_id'],data['payload'],e.pk,c.revision)
        return {'head':work.source_head_id,'schedule':w.pk,'status':w.result['status'],'ledger_posted':False}
    if kind=='ACT13':
        require(work.execution_actor,c,'schedules.report');result=verify(work,work.execution_actor);work.status='verified';return result
    raise ValidationError('Human schedule decisions cannot be performed by a model')

def settled(w):
    from apps.agents.factory_coordinator import pending,has_receipt
    if w.lease_until and w.lease_until>timezone.now():raise ValidationError('CONFLICT: current worker owns this work')
    p=pending(w)
    if p and not has_receipt(p):raise ValidationError('Reconcile original planning response first')

@transaction.atomic
def correct(actor,work_id,expected,case_expected,kind,parent_id,evidence_id,payload,reason):
    from .factory import access
    w=Work.objects.select_for_update(of=('self',)).select_related('case','source_head','actor').get(pk=work_id,definition=DEFINITION)
    access(actor,w.case,'factory.manage',DEFINITION);c=lock_case(actor,w.case_id,'evidence.add',case_expected);w.case=c
    if type(expected) is not int or w.revision!=expected or w.cancel_requested or w.status in ['cancelled','followup_needed']:raise ValidationError('Refresh active schedule work')
    settled(w);analysis.note(reason);old=source(w,actor,False)[0];new=inputs(actor,c,kind,parent_id,evidence_id,payload)[0]
    if kind!=w.request['kind']:raise ValidationError('Correction must retain native work kind')
    if old==new:
        try:
            source(w,actor);s=schedule(w)
            if not s:raise ValidationError('No prepared output')
            native.current(s)
        except (ValidationError,PermissionDenied):pass
        else:raise ValidationError('Current target awaits human review or has already been reviewed; do not rebuild that wait')
    before=w.source_head_id;w.source_head=capture(actor,c,new,'factory.schedules_source');w.status='ready';w.finding='';w.revision+=1;w.save()
    event(actor,c,'factory.schedules_corrected',work=w.pk,previous=before,current=w.source_head_id,reason=reason);return w

@transaction.atomic
def review(actor,work_id,expected,case_expected,target,verdict,evidence,note):
    from .factory import access
    w=Work.objects.select_for_update(of=('self',)).select_related('case','source_head','actor').get(pk=work_id,definition=DEFINITION)
    access(actor,w.case,'factory.read',DEFINITION);source(w,actor);s=schedule(w)
    if type(expected) is not int or w.revision!=expected or w.cancel_requested or not s or s.pk!=target:raise ValidationError('Review exact active native target')
    settled(w);return native.review(actor,w.case_id,target,verdict,evidence,note,case_expected)

@transaction.atomic
def export(actor,work_id,expected,case_expected,target,kind,evidence):
    from .factory import access
    w=Work.objects.select_for_update(of=('self',)).select_related('case','source_head','actor').get(pk=work_id,definition=DEFINITION)
    access(actor,w.case,'factory.read',DEFINITION);source(w,actor);s=schedule(w)
    if type(expected) is not int or w.revision!=expected or w.cancel_requested or not s or s.pk!=target:raise ValidationError('Export exact active reviewed target')
    settled(w);return native.export_adjustment(actor,w.case_id,target,kind,evidence,case_expected)

def projection(actor,work):
    from .factory import profile
    native.readable(actor,work.case);source(work,actor,False);s=schedule(work);options=[];changed=False;message='';n={}
    try:
        _,v=profile(work,recovery=True);state,latest,missing,stale,tasks,jobs=snapshot(work,v,reader=actor);n=state['native'];options,message=eligible(work,v,state,latest,missing,stale,tasks,jobs)
        if work.status=='verified':verify(work,actor)
    except (ValidationError,PermissionDenied) as exc:message=finding(exc);changed=work.status=='verified'
    pending_reviews=[];names=[];can_review=False
    if s and n.get('stage')=='output_review' and not work.cancel_requested:
        pending_reviews=[s.pk]
        for user in __import__('django.contrib.auth',fromlist=['get_user_model']).get_user_model().objects.filter(is_active=True,grant__case=work.case,grant__action='schedules.review',grant__active=True).distinct():
            try:native.authority(user,s)
            except (ValidationError,PermissionDenied):continue
            names.append(user.get_full_name() or user.username);can_review=can_review or user.pk==actor.pk
    return {'schedule':s,'next_options':options,'next_action':message,'finding':message if not options else '', 'readiness_changed':changed,'pending_reviews':pending_reviews,'reviewer_names':names,'can_review':can_review,'native':n,'links':list(ScheduleAdjustment.objects.filter(work=s).select_related('adjustment')) if s else []}

@transaction.atomic
def restart(actor,work_id,expected,case_expected,reason):
    from .factory import access
    w=Work.objects.select_for_update(of=('self',)).select_related('case','source_head','actor').get(pk=work_id,definition=DEFINITION)
    access(actor,w.case,'factory.manage',DEFINITION);c=lock_case(actor,w.case_id,'factory.manage',case_expected);analysis.note(reason);settled(w)
    if type(expected) is not int or w.revision!=expected or w.status!='cancelled':raise ValidationError('Refresh settled cancelled work')
    source(w,actor,False);w.status='ready';w.cancel_requested=False;w.finding='';w.revision+=1;w.save();event(actor,c,'factory.schedules_restarted',work=w.pk,reason=reason);return w

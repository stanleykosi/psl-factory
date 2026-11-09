"""F21/F44 reference coordination. Native BU services own all financial decisions."""
import hashlib,json
from datetime import timedelta
from django.db import transaction
from django.db.models import Q
from django.core.exceptions import ValidationError,PermissionDenied
from django.utils import timezone
from apps.core.models import Audit
from apps.core.services import lock_case,add_evidence,event
from apps.identity.services import require
from apps.identity.models import Grant
from apps.documents.contracts import digest,validate
from apps.finance import bu as native,payroll
from apps.finance.bu_models import BUWork,BUReport,BUReceipt
from apps.finance.payroll_models import PayrollRun
from apps.policy.services import active_component,reference_values
from apps.policy.bu_validators import DISCLOSE
from .models import FactoryWork as Work,FactoryActivity as Activity
from .factory_delivery import investigation_key
from .factory_payroll import finding

DEFINITION='finance-bu/v1'
KIND='agent_private_bu_intake'
PROTOCOL='factory-bu-intake/v1'
ID={'type':'integer','minimum':1,'maximum':9223372036854775807}
NULL_ID={'anyOf':[ID,{'type':'null'}]}
COMPARISON={'anyOf':[{'type':'null'},{'type':'object','properties':{'run_id':ID,'metric':{'enum':['revenue','direct_cost','staff_cost','opex','other']}},'required':['run_id','metric'],'additionalProperties':False}]}
INPUT={'type':'object','properties':{'mode':{'enum':['staff','event']},'payroll_id':NULL_ID,'source_id':NULL_ID,'rule_ids':{'type':'array','maxItems':100,'uniqueItems':True,'items':ID},'comparison':COMPARISON},'required':['mode','payroll_id','source_id','rule_ids','comparison'],'additionalProperties':False}
SCHEMA={'type':'object','properties':{'protocol':{'const':PROTOCOL},'inputs':INPUT},'required':['protocol','inputs'],'additionalProperties':False}

def inputs_checked(actor,case,inputs,current=True):
    validate(INPUT,inputs)
    for action in ['case.read','bu.read','bu.private.read']:require(actor,case,action)
    if inputs['mode']=='staff':
        if not inputs['payroll_id'] or inputs['source_id'] or inputs['comparison']:raise ValidationError('Staff work uses only exact payroll and exception rules')
        p=payroll.exact(case,PayrollRun,inputs['payroll_id'])
        if p.kind!='match':raise ValidationError('Choose the exact native F17 match')
        if current:payroll.run_access(actor,p)
        else:
            from apps.policy.payroll_validators import ACCESS
            for action in ['payroll.read','payroll.private.read']:require(actor,case,action)
            v=reference_values(active_component(ACCESS,case))[0];scope=p.request.metadata
            if actor.pk not in v['reader_ids'] or v['entity']!=scope['entity'] or v['currency']!=scope['currency'] or not v['from_period']<=scope['period']<=v['to_period'] or {r['provider'] for r in v['providers']}!=set(scope['providers']):raise PermissionDenied('Not a current reader for this payroll source scope')
        rules=[]
        for pk in inputs['rule_ids']:
            r=native.exact(case,pk)
            if r.kind!='rule' or r.payroll_id!=p.pk:raise ValidationError('Choose exact payroll-bound exception rules')
            if current:native.current(r)
            rules.append(r)
        scope={k:p.request.metadata[k] for k in ['entity','period','currency']}
        return p,rules,scope,p.request.reference
    if not inputs['source_id'] or inputs['payroll_id'] or inputs['rule_ids']:raise ValidationError('Event work uses only exact supplied-event source and optional Finance reference')
    s=native.exact(case,inputs['source_id'])
    if s.kind!='source' or not s.metadata['accepted']:raise ValidationError('Choose an accepted native event source')
    native.private_access(actor,s)
    if current:native.current(s)
    if current and inputs['comparison']:native.finance_comparison(actor,case,s.metadata['scope'],inputs['comparison'])
    return s,[],s.metadata['scope'],s.reference

def source(work,actor=None,current=True):
    actor=actor or work.execution_actor;e=work.source_head
    if not e or e.case_id!=work.case_id or e.kind!=KIND or e.sha256!=hashlib.sha256(e.body.encode()).hexdigest():raise ValidationError('Exact restricted BU intake required')
    try:data=json.loads(e.body)
    except (TypeError,ValueError):raise ValidationError('Typed BU intake required') from None
    validate(SCHEMA,data)
    audit=Audit.objects.filter(case=work.case,actor=e.created_by,action__in=['factory.bu_intake','factory.bu_source'],data={'evidence_id':e.pk,'sha256':e.sha256}).first()
    if not audit:raise ValidationError('Native BU intake provenance required')
    p,rules,scope,ref=inputs_checked(actor,work.case,data['inputs'],current)
    if work.request['mode']!=data['inputs']['mode'] or work.request['source_reference']!=ref or work.request['scope']!=scope:raise ValidationError('BU canonical source identity differs')
    if current:
        for action in ['case.read','bu.read','bu.private.read','evidence.add','factory.start' if audit.action=='factory.bu_intake' else 'factory.manage']:require(e.created_by,work.case,action)
        if e.created_by_id!=actor.pk:inputs_checked(e.created_by,work.case,data['inputs'])
    return p,rules,data['inputs']

def capture(actor,case,inputs,action):
    e=add_evidence(actor,case.pk,KIND,json.dumps({'protocol':PROTOCOL,'inputs':inputs},sort_keys=True),'psl:'+PROTOCOL)
    event(actor,case,action,evidence_id=e.pk,sha256=e.sha256);return e

@transaction.atomic
def start(actor,case_id,key,inputs,reference,expected=None):
    from .factory import access
    c=lock_case(actor,case_id,'factory.start',expected);access(actor,c,'factory.start',DEFINITION);require(actor,c,'evidence.add')
    validate(native.KEY,key)
    if not isinstance(reference,str) or not reference.strip() or len(reference)>160:raise ValidationError('Describe the work without private details')
    p,rules,scope,ref=inputs_checked(actor,c,inputs)
    payload={'mode':inputs['mode'],'source_reference':ref,'scope':scope,'reference':reference};sha=digest(payload);business=digest([str(c.pk),DEFINITION,inputs['mode'],ref,scope])
    old=Work.objects.filter(case=c).filter(Q(key=key)|Q(definition=DEFINITION,business_key=business)).first()
    if old:
        if old.actor_id!=actor.pk or old.definition!=DEFINITION or old.key==key and old.request_hash!=sha:raise ValidationError('IDEMPOTENCY_CONFLICT: changed BU intent')
        if source(old,actor)[2]!=inputs:raise ValidationError('Replace exact sources in the existing BU work')
        return old
    w=Work.objects.create(case=c,actor=actor,key=key,definition=DEFINITION,request=payload,request_hash=sha,business_key=business,source_head=capture(actor,c,inputs,'factory.bu_intake'))
    event(actor,c,'factory.started',work=w.pk,definition=DEFINITION);return w

def key(work,stage):return 'factory-bu:'+digest([work.pk,work.source_head_id,stage])
def result(work):return BUWork.objects.defer('payload').filter(case=work.case,operation_key=key(work,'calculate'),kind=work.request['mode']).first()
def publication(work):return BUReport.objects.defer('payload').filter(work__case=work.case,operation_key=key(work,'publish')).first()
def publication_history(work):return BUReport.objects.filter(work__case=work.case,work__reference='factory-bu-'+str(work.pk))

def checked_result(work,actor,selected=None,current=True):
    p,rules,inputs=selected or source(work,actor);r=result(work)
    if r:
        expected={'payroll':p.pk,'reference':r.reference,'declared_sha256':digest([[x.payload['employee_id'],x.payload['component']] for x in rules]),'rule_ids':sorted(inputs['rule_ids'])} if inputs['mode']=='staff' else {'parent':p.pk,'reference':r.reference,'comparison':inputs['comparison']}
        if r.actor_id!=work.execution_actor.pk or r.reference!='factory-bu-'+str(work.pk) or r.metadata['intent']!=expected:raise ValidationError('Exact native BU working result differs')
        # Selected source already validates this reader's exact payroll/event scope.
        if current:native.current(r)
    return r

def _verify_selected(work,actor,r,review):
    p=publication(work)
    if not r or not p or p.work_id!=r.pk:raise ValidationError('Await exact native aggregate publication')
    policy=active_component(DISCLOSE,work.case);v=reference_values(policy)[0]
    native.private_access(p.actor,r);require(p.actor,work.case,'bu.publish')
    if p.review_id!=review.pk or p.policy_ids!={**native.authority(p.actor,r,'publish'),DISCLOSE:policy.pk}:raise ValidationError('Publication authority or disclosure changed')
    if r.metadata.get('historical'):native.review_current(r,'historical')
    expected={**r.metadata['scope'],'unit':'major_currency','by_bu':r.payload['by_bu'],'company_source_total':r.payload['source_total'],'allocated_total':r.payload['allocated_total'],'company_only':r.payload.get('company_only','0'),'residual':r.payload['residual'],'conserved':True,'source_work':r.pk,'coverage':'selected_supplied_population_only','native_authenticity_verified':False,'destination':v['destination'],'ledger_posted':False,'source_written':False,'disclosure':'aggregate_only'}
    if r.metadata['status']!='complete' or not r.payload['conserved'] or p.payload!=expected:raise ValidationError('Exact native aggregate payload mismatch')
    receipts=list(BUReceipt.objects.filter(report=p).select_related('actor').order_by('pk'))
    if {x.actor_id for x in receipts}!=set(v['recipient_ids']):raise ValidationError('Await each configured recipient’s own aggregate receipt')
    for receipt in receipts:
        require(receipt.actor,work.case,'bu.receive');native.read_report(receipt.actor,p.pk)
    return {'verified':True,'head':work.source_head_id,'work':r.pk,'publication':p.pk,'receipt_ids':[x.pk for x in receipts],'payload_sha256':digest(p.payload),'private_payloads_in_result':False,'ledger_posted':False,'source_written':False,'coverage':'selected_supplied_population_only'}

def verify(work,actor=None):
    actor=actor or work.execution_actor;r=checked_result(work,actor,current=False)
    if not r:raise ValidationError('Await exact native BU result')
    return _verify_selected(work,actor,r,native.review_current(r))

def report(work,actor=None,selected=None):
    actor=actor or work.execution_actor;selected=selected or source(work,actor);p,rules,inputs=selected
    state={'stage':'source_review','finding':'','subjects':[{'id':x.pk,'kind':x.kind} for x in ([p] if inputs['mode']=='event' else rules)],'result':None,'publication':None,'receipt_ids':[]}
    try:
        if inputs['mode']=='staff':payroll.current_review(p)
        for x in ([p] if inputs['mode']=='event' else rules):native.review_current(x)
        state['stage']='calculate';r=checked_result(work,actor,selected,current=False)
        if not r:raise ValidationError('Prepare exact native BU result')
        state['result']={'id':r.pk,'kind':r.kind,'status':r.metadata['status'],'codes':r.metadata['codes']};state['subjects'].append({'id':r.pk,'kind':r.kind})
        state['stage']='result_review';approval=native.review_current(r)
        if r.metadata.get('historical'):state['stage']='historical_review';native.review_current(r,'historical')
        state['stage']='publish';p=publication(work)
        if not p:raise ValidationError('Await actual Finance aggregate publication decision')
        state['publication']=p.pk;state['stage']='receipt';state['receipt_ids']=list(BUReceipt.objects.filter(report=p).values_list('pk',flat=True))
        _verify_selected(work,actor,r,approval);state['stage']='complete'
    except (ValidationError,PermissionDenied) as exc:state['finding']=finding(exc)
    return state

def snapshot(work,value,reader=None):
    from .factory import access
    actor=reader or work.execution_actor;access(actor,work.case,'factory.read' if reader else 'factory.execute',DEFINITION)
    selected=source(work,actor);state=report(work,actor,selected);latest={KIND:work.source_head}
    missing=[k for k in value['required_evidence_kinds'] if k not in latest];stale=[k for k in value['required_evidence_kinds'] if k in latest and latest[k].created_at<timezone.now()-timedelta(seconds=value['max_age_seconds'])]
    observed={'case_revision':work.case.revision,'profile':work.policy_id,'sources':[(e.pk,e.sha256) for e in latest.values()],'native':state,'checks':{'stage':state['stage']}}
    observed['hash']=digest(observed);observed['work_revision']=work.revision
    return observed,latest,missing,stale,[],[]

def eligible(work,value,state,latest,missing,stale,tasks,jobs):
    if not Activity.objects.filter(work=work,key=investigation_key(work,state),status='succeeded').exists():return ['ACT04'],'Investigate exact BU sources, rules and required human decisions'
    if missing or stale:return [],'Required current BU evidence missing or stale'
    if state['native']['stage']=='calculate':return ['ACT08'],'Prepare native calculation using exact selected approved rules'
    if state['native']['stage']=='complete':return ['ACT13'],'Verify aggregate and recipient-owned receipts'
    return [],state['native']['finding']

def act(work,choice,value,latest,missing,tasks,jobs):
    from .factory import access
    actor=work.execution_actor;c=lock_case(actor,work.case_id,'factory.execute');access(actor,c,'factory.execute',DEFINITION);list(Grant.objects.select_for_update().filter(case=c).order_by('pk'))
    if c.revision!=work.case.revision:raise ValidationError('STALE_VERSION: BU source changed')
    selected=source(work,actor);p,rules,inputs=selected;kind=choice['activity']
    if kind=='ACT13':answer=verify(work,actor);work.status='verified';return answer
    state=report(work,actor,selected)
    if kind=='ACT04':
        require(actor,c,'agent.bu')
        from apps.agents.bu import inspect_work
        prepared=result(work);selected_work=([prepared] if prepared else [])+([p] if inputs['mode']=='event' else rules)
        findings=[inspect_work(item) for item in selected_work[:40]]
        return {'findings':findings,'inspection_budget':40,'selected_work_count':len(selected_work),'inspection_complete':len(selected_work)<=40,'head':work.source_head_id,'native':state,'questions':['Actual Finance authority must approve each exact exception and its exclusion. Never reuse prior-month ratios.','Source owners correct event identities or conflicting tags; selected coverage is not whole-company completeness.','Actual reviewers decide historical treatment. Each recipient records their own aggregate receipt.'],'private_payloads_in_result':False,'review_approved':False,'source_written':False}
    if kind=='ACT08':
        if state['stage']!='calculate':raise ValidationError('Native human review required before calculation')
        ref='factory-bu-'+str(work.pk)
        if inputs['mode']=='staff':r=native.staff(actor,c.pk,p.pk,ref,key(work,'calculate'),[[x.payload['employee_id'],x.payload['component']] for x in rules],inputs['rule_ids'],c.revision)
        else:r=native.attribute(actor,c.pk,p.pk,ref,key(work,'calculate'),c.revision,inputs['comparison'])
        return {'head':work.source_head_id,'work':r.pk,'kind':r.kind,'sha256':r.sha256,'status':r.metadata['status'],'codes':r.metadata['codes'],'private_payloads_in_result':False}
    raise ValidationError('Factory cannot approve rules, publish as a human or impersonate recipients')

@transaction.atomic
def human_action(actor,work_id,expected,case_expected,action,values):
    from .factory import access
    w=Work.objects.select_for_update(of=('self',)).select_related('case','source_head','actor').get(pk=work_id,definition=DEFINITION);access(actor,w.case,'factory.read',DEFINITION)
    if type(expected) is not int or expected!=w.revision or w.cancel_requested and action!='receive' or w.lease_until and w.lease_until>timezone.now():raise ValidationError('STALE_VERSION: refresh BU work')
    if action=='receive':
        p=publication(w)
        if not p or values['publication_id']!=p.pk:raise ValidationError('Choose this work exact aggregate')
        return native.receive(actor,w.case_id,p.pk,case_expected)
    p,rules,inputs=source(w,actor)
    if action=='prepare_rule':
        if inputs['mode']!='staff':raise ValidationError('Exception rules require the exact payroll mode')
        return native.rule(actor,w.case_id,p.pk,values['reference'],values['operation_key'],values['payload'],case_expected)
    r=checked_result(w,actor,(p,rules,inputs),current=False)
    if action=='review':
        subjects=([p] if inputs['mode']=='event' else rules)+([r] if r else [])
        if values['work_id'] not in [x.pk for x in subjects]:raise ValidationError('Review an exact selected native BU subject')
        return native.review(actor,w.case_id,values['work_id'],values['purpose'],values['verdict'],values['operation_key'],values['evidence_id'],case_expected)
    if action=='publish':
        if not r:raise ValidationError('Prepare exact result before publication')
        return native.publish(actor,w.case_id,r.pk,key(w,'publish'),case_expected)
    raise ValidationError('Choose an explicit native human action')

@transaction.atomic
def correct(actor,work_id,expected,case_expected,inputs,reason):
    from .factory import access
    from apps.agents.factory_coordinator import pending,has_receipt
    w=Work.objects.select_for_update(of=('self',)).select_related('case','source_head','actor').get(pk=work_id,definition=DEFINITION);access(actor,w.case,'factory.manage',DEFINITION)
    c=lock_case(actor,w.case_id,'evidence.add',case_expected);w.case=c
    if type(expected) is not int or expected!=w.revision or w.cancel_requested or w.status in ['cancelled','followup_needed'] or w.lease_until and w.lease_until>timezone.now():raise ValidationError('STALE_VERSION: refresh current BU work')
    planning=pending(w)
    if planning and not has_receipt(planning):raise ValidationError('Reconcile original planning response before source replacement')
    if not isinstance(reason,str) or not reason.strip() or len(reason)>2000:raise ValidationError('Explain the source-owned replacement without private values')
    p,rules,scope,ref=inputs_checked(actor,c,inputs)
    if ref!=w.request['source_reference'] or scope!=w.request['scope'] or inputs['mode']!=w.request['mode']:raise ValidationError('Keep the original canonical source, period and mode')
    previous=json.loads(w.source_head.body)['inputs']
    if previous==inputs:
        r=result(w);rework=False
        if r:
            latest=r.reviews.filter(purpose=r.kind).order_by('-pk').first()
            rework=r.metadata['status']=='held' or bool(latest and latest.verdict in ['return','revoke'])
            try:native.current(r)
            except (PermissionDenied,ValidationError):rework=True
        if not rework:raise ValidationError('Select replaced sources or a genuinely held, returned or stale result')
    old=w.source_head_id;w.source_head=capture(actor,c,inputs,'factory.bu_source');w.status='ready';w.finding='';w.revision+=1;w.save()
    event(actor,c,'factory.bu_corrected',work=w.pk,previous=old,current=w.source_head_id,reason=reason);return w

@transaction.atomic
def cancel(actor,work_id,expected):
    from .factory import access,manage,cancellation_status
    w=Work.objects.select_for_update(of=('self',)).select_related('case','source_head').get(pk=work_id,definition=DEFINITION);access(actor,w.case,'factory.manage',DEFINITION)
    if type(expected) is not int or expected!=w.revision:raise ValidationError('STALE_VERSION: refresh BU work')
    if w.status in ['verified','followup_needed']:raise ValidationError('Published or verified BU work needs native follow-up')
    if w.status=='cancelled':return w
    if not w.cancel_requested:w=manage(actor,w.pk,w.revision,'cancel')
    if w.lease_until and w.lease_until>timezone.now():return w
    w.status=cancellation_status(w);w.finding='Stopping preparation does not reverse aggregate publication or receipts.';w.lease_until=None;w.revision+=1;w.save();return w

@transaction.atomic
def restart(actor,work_id,expected,case_expected,inputs,configuration_id,instruction_key,reason):
    from .factory import access,profile,adopt_profile
    from .factory_definitions import definition
    from apps.agents.factory_coordinator import pending,has_receipt
    w=Work.objects.select_for_update(of=('self',)).select_related('case','source_head','actor').get(pk=work_id,definition=DEFINITION);access(actor,w.case,'factory.manage',DEFINITION)
    c=lock_case(actor,w.case_id,'evidence.add');w.case=c;validate(native.KEY,instruction_key)
    if not isinstance(reason,str) or not reason.strip() or len(reason)>2000:raise ValidationError('Explain the fresh instruction without private values')
    p,rules,scope,ref=inputs_checked(actor,c,inputs)
    if ref!=w.request['source_reference'] or scope!=w.request['scope'] or inputs['mode']!=w.request['mode']:raise ValidationError('Keep canonical BU source identity')
    config=active_component(definition(DEFINITION)['component'],c)
    if type(configuration_id) is not int or configuration_id!=config.pk:raise ValidationError('Select the exact current execution profile')
    intent={'inputs':inputs,'configuration_id':configuration_id,'reason':reason};sha=digest(intent)
    old=Audit.objects.filter(case=c,action='factory.bu_restarted',data__work=w.pk,data__instruction_key=instruction_key).first()
    if old:
        if old.actor_id!=actor.pk or old.data['intent_sha256']!=sha or old.data['current']!=w.source_head_id or w.cancel_requested:raise ValidationError('Restart instruction differs from current work')
        profile(w);return w
    if type(expected) is not int or type(case_expected) is not int or expected!=w.revision or case_expected!=c.revision:raise ValidationError('STALE_VERSION: refresh workspace and work')
    if publication_history(w).exists():raise ValidationError('A publication exists in this work history; native follow-up required')
    if w.status!='cancelled' or not w.cancel_requested:raise ValidationError('Only settled never-published cancellation can restart')
    if w.lease_until and w.lease_until>timezone.now():raise ValidationError('Wait for original worker to stop')
    planning=pending(w)
    if planning and not has_receipt(planning):raise ValidationError('Reconcile original planning response before restart')
    instruction=add_evidence(actor,c.pk,'agent_private_bu_restart',json.dumps({'work':w.pk,'instruction_key':instruction_key,**intent},sort_keys=True),'psl:bu-restart/v1')
    prior=w.source_head_id;w.source_head=capture(actor,c,inputs,'factory.bu_source');w.cancel_requested=False;w.status='ready';w.finding='';w.lease_until=None;w.observation_hash='';w.fence+=1;w.revision+=1;w.save()
    if w.policy_id!=config.pk:w=adopt_profile(actor,w.pk,w.revision,configuration_id,reason)
    else:profile(w)
    event(actor,c,'factory.bu_restarted',work=w.pk,previous=prior,current=w.source_head_id,instruction=instruction.pk,instruction_key=instruction_key,intent_sha256=sha,configuration=config.pk,spent=w.budget_used,lifetime_allowance=w.budget_limit);return w

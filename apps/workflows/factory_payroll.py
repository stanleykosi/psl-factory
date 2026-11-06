"""Restricted F16–F18 work. Native services own rows, decisions and receipts."""
import hashlib,json
from datetime import timedelta
from django.core.exceptions import PermissionDenied,ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from apps.core.models import Audit
from apps.core.services import lock_case,add_evidence,event
from apps.core.read_observation import read_observation
from apps.identity.services import require
from apps.identity.models import Grant
from apps.documents.contracts import digest,validate
from apps.finance import payroll as native,hrfinance as hr
from apps.finance.payroll_models import PayrollRequest,PayrollInput,PayrollRun,PayrollPublication,PayrollReportReceipt
from apps.finance.hrfinance_models import HRReadSnapshot
from apps.policy.services import active_component,reference_values
from apps.policy.payroll_validators import REPORT,ACCESS
from .models import FactoryWork as Work,FactoryActivity as Activity
from .factory_delivery import investigation_key

DEFINITION='finance-payroll/v1'
KIND='agent_private_payroll_intake'
PROTOCOL='factory-payroll-intake/v1'
ID={'type':'integer','minimum':1,'maximum':9223372036854775807}
INPUT={'type':'object','properties':{'input_ids':{'type':'array','minItems':2,'maxItems':2,'uniqueItems':True,'items':ID},'hr_snapshot_id':{'anyOf':[ID,{'type':'null'}]}},'required':['input_ids','hr_snapshot_id'],'additionalProperties':False}
SCHEMA={'type':'object','properties':{'protocol':{'const':PROTOCOL},'request_id':ID,'inputs':INPUT},'required':['protocol','request_id','inputs'],'additionalProperties':False}

def finding(exc):return '; '.join(exc.messages) if isinstance(exc,ValidationError) else str(exc)

def input_rows(actor,case,q,inputs,current=True):
    validate(INPUT,inputs)
    rows=[native.exact(case,PayrollInput,pk) for pk in inputs['input_ids']]
    if any(i.request_id!=q.pk or not i.metadata['accepted'] for i in rows) or {i.provider for i in rows}!=set(q.metadata['providers']):raise ValidationError('Select the two accepted provider inputs for this exact payroll request')
    if current:
        native.access(q,actor,True)
        for row in rows:native.input_current(row)
    if inputs['hr_snapshot_id']:
        h=hr.exact(case,HRReadSnapshot,inputs['hr_snapshot_id'])
        if current:hr.snapshot_access(actor,h)
        else:
            for action in ['hrfinance.read','hrfinance.snapshot.read']:require(actor,case,action)
            if actor.pk not in h.contract.payload['recipient_ids']:raise PermissionDenied('Not a nominated HR snapshot recipient')
        if h.contract.payload['purpose']!='payroll_matching' or set(h.contract.payload['fields'])!=set(native.REQUIRED) or any(h.contract.payload[k]!=q.metadata[k] for k in ['entity','period']):raise ValidationError('Select the exact minimal HR matching snapshot for this request')
    return rows

def source(work,actor=None,current=True):
    actor=actor or work.actor
    for action in ['case.read','payroll.read','payroll.private.read']:require(actor,work.case,action)
    e=work.source_head
    if not e or e.case_id!=work.case_id or e.kind!=KIND or e.sha256!=hashlib.sha256(e.body.encode()).hexdigest():raise ValidationError('Exact restricted payroll intake required')
    try:data=json.loads(e.body)
    except (TypeError,ValueError):raise ValidationError('Typed payroll intake required') from None
    validate(SCHEMA,data);q=native.exact(work.case,PayrollRequest,data['request_id'])
    audit=Audit.objects.filter(case=work.case,actor_id=e.created_by_id,action__in=['factory.payroll_intake','factory.payroll_source'],data={'evidence_id':e.pk,'sha256':e.sha256}).first()
    if not audit or q.reference!=work.request['payroll_reference']:raise ValidationError('Exact native payroll provenance required')
    # Even history does not turn factory.read into restricted payroll permission.
    if current:native.access(q,actor,True)
    else:
        rules=reference_values(active_component(ACCESS,work.case))[0]
        if actor.pk not in rules['reader_ids']:raise PermissionDenied('Not a current restricted payroll reader')
        if rules['entity']!=q.metadata['entity'] or rules['currency']!=q.metadata['currency'] or not rules['from_period']<=q.metadata['period']<=rules['to_period'] or set(q.metadata['providers'])!={r['provider'] for r in rules['providers']}:raise PermissionDenied('Historical payroll metadata is outside the current source disclosure')
    if current:
        for action in ['case.read','payroll.read','payroll.private.read','evidence.add','factory.start' if audit.action=='factory.payroll_intake' else 'factory.manage']:require(e.created_by,work.case,action)
    input_rows(actor,work.case,q,data['inputs'],current);return q,data

def capture(actor,case,q,inputs,action):
    e=add_evidence(actor,case.pk,KIND,json.dumps({'protocol':PROTOCOL,'request_id':q.pk,'inputs':inputs},sort_keys=True),'psl:'+PROTOCOL)
    event(actor,case,action,evidence_id=e.pk,sha256=e.sha256);return e

@transaction.atomic
def start(actor,case_id,key,request_id,inputs,reference,expected=None):
    from .factory import access
    case=lock_case(actor,case_id,'factory.start',expected);access(actor,case,'factory.start',DEFINITION);require(actor,case,'evidence.add')
    if not isinstance(key,str) or not key.isascii() or not 1<=len(key)<=100 or not isinstance(reference,str) or not reference.strip() or len(reference)>160:raise ValidationError('Bounded work identity and description required')
    q=native.exact(case,PayrollRequest,request_id);input_rows(actor,case,q,inputs)
    payload={'payroll_reference':q.reference,'reference':reference};sha=digest(payload);business=digest([str(case.pk),DEFINITION,q.reference])
    old=Work.objects.filter(case=case).filter(Q(key=key)|Q(definition=DEFINITION,business_key=business)).first()
    if old:
        if old.actor_id!=actor.pk or old.definition!=DEFINITION or old.key==key and old.request_hash!=sha:raise ValidationError('IDEMPOTENCY_CONFLICT: changed payroll intent')
        oq,data=source(old,actor)
        if oq.pk!=q.pk or data['inputs']!=inputs:raise ValidationError('Explicitly replace sources in existing payroll work')
        return old
    w=Work.objects.create(case=case,actor=actor,key=key,definition=DEFINITION,request=payload,request_hash=sha,business_key=business,source_head=capture(actor,case,q,inputs,'factory.payroll_intake'))
    event(actor,case,'factory.started',work=w.pk,definition=DEFINITION);return w

def key(work,stage):return 'factory-payroll:'+digest([work.pk,work.source_head_id,stage])
def selected_request(work):
    data=json.loads(work.source_head.body);validate(SCHEMA,data);return data['request_id']
def run(work,kind):return PayrollRun.objects.defer('result').filter(request_id=selected_request(work),request__case=work.case,operation_key=key(work,kind),kind=kind).first()
def checked_run(work,kind,q,data):
    r=run(work,kind)
    if not r:return None
    parent=run(work,'combine' if kind=='match' else 'match') if kind!='combine' else None
    intent={'input_ids':sorted(data['inputs']['input_ids'])} if kind=='combine' else {'parent_id':parent.pk if parent else None,**({'hr_snapshot_id':data['inputs']['hr_snapshot_id']} if kind=='match' else {})}
    if r.request_id!=q.pk or r.metadata['intent']!=intent or r.parent_id!=(parent.pk if parent else None):raise ValidationError('Native working result differs from exact factory-selected sources')
    return r

def publication(work):return PayrollPublication.objects.defer('payload').filter(request_id=selected_request(work),request__case=work.case,operation_key=key(work,'publish')).first()

def verify(work,actor=None):
    actor=actor or work.execution_actor;q,data=source(work,actor);a=checked_run(work,'aggregate',q,data);p=publication(work)
    if not a or not p or a.request_id!=q.pk or p.run_id!=a.pk:raise ValidationError('Await exact reviewed aggregate publication')
    for stage in ['combine','match']:checked_run(work,stage,q,data)
    native.run_access(actor,a);review=native.current_review(a)
    policy=active_component(REPORT,work.case);rules=reference_values(policy)[0]
    require(p.actor,work.case,'payroll.publish')
    if p.review_id!=review.pk or p.policy_ids!={**native.authority(p.actor,q,'publish'),REPORT:policy.pk} or PayrollPublication.objects.filter(request=q,version__gt=p.version).exists():raise ValidationError('Publication or authority changed; prepare source-owned replacement')
    expected={**{k:q.metadata[k] for k in ['entity','period','currency']},'unit':'major_currency','by_bu':a.result['by_bu'],'eligible_total':a.result['eligible_total'],'source_run':a.pk,'report_version':p.version,'destination':rules['destination'],'disclosure':'aggregate_only','hr_written':False,'ledger_posted':False}
    if p.payload!=expected:raise ValidationError('Exact native aggregate payload mismatch')
    receipts=list(PayrollReportReceipt.objects.filter(publication=p).order_by('pk'))
    if {r.actor_id for r in receipts}!=set(rules['recipient_ids']):raise ValidationError('Await each configured recipient’s own aggregate receipt')
    for receipt in receipts:
        for action in ['case.read','payroll.read','payroll.report.read','payroll.report.receive']:require(receipt.actor,work.case,action)
    return {'verified':True,'head':work.source_head_id,'request':q.pk,'run':a.pk,'publication':p.pk,'payload_sha256':digest(expected),'receipt_ids':[r.pk for r in receipts],'private_payloads_in_result':False,'hr_written':False,'ledger_posted':False,'external_authenticity_verified':False}

def report(work,actor=None):
    actor=actor or work.execution_actor;q,data=source(work,actor);state={'request':q.pk,'inputs':data['inputs'],'stage':'input_review','finding':'','runs':{},'publication':None,'receipt_ids':[]}
    try:
        for pk in data['inputs']['input_ids']:native.current_review(native.exact(work.case,PayrollInput,pk))
        for stage in ['combine','match','aggregate']:
            state['stage']=stage;r=checked_run(work,stage,q,data)
            if not r:raise ValidationError('Prepare native '+stage+' working result')
            native.run_access(actor,r);state['runs'][stage]={'id':r.pk,'sha256':r.sha256,'status':r.metadata['status'],'codes':r.metadata['codes']}
            state['stage']=stage+'_review';native.current_review(r)
        state['stage']='publish';p=publication(work)
        if not p:raise ValidationError('Await actual Finance publication decision')
        state['publication']=p.pk;state['stage']='receipt';state['receipt_ids']=list(p.receipts.values_list('pk',flat=True)) if hasattr(p,'receipts') else list(PayrollReportReceipt.objects.filter(publication=p).values_list('pk',flat=True))
        verify(work,actor);state['stage']='complete'
    except (ValidationError,PermissionDenied) as exc:state['finding']=finding(exc)
    return state

@read_observation
def snapshot(work,value,reader=None):
    from .factory import access
    actor=reader or work.execution_actor;access(actor,work.case,'factory.read' if reader is not None else 'factory.execute',DEFINITION)
    q,data=source(work,actor);state=report(work,actor);latest={KIND:work.source_head,q.evidence.kind:q.evidence}
    missing=[k for k in value['required_evidence_kinds'] if k not in latest]
    stale=[k for k in value['required_evidence_kinds'] if k in latest and latest[k].created_at<timezone.now()-timedelta(seconds=value['max_age_seconds'])]
    observed={'case_revision':work.case.revision,'profile':work.policy_id,'sources':[(e.pk,e.sha256) for e in latest.values()],'native':state,'checks':{'stage':state['stage']}}
    observed['hash']=digest(observed);observed['work_revision']=work.revision
    return observed,latest,missing,stale,[],[]

def eligible(work,value,state,latest,missing,stale,tasks,jobs):
    if not Activity.objects.filter(work=work,key=investigation_key(work,state),status='succeeded').exists():return ['ACT04'],'Investigate exact payroll metadata and required human decisions'
    if missing or stale:return [],'Required current payroll evidence is missing or stale'
    stage=state['native']['stage']
    if stage=='complete':return ['ACT13'],'Verify exact aggregate and recipient-owned receipts'
    if stage in ['combine','match','aggregate']:
        if stage=='match' and not state['native']['inputs']['hr_snapshot_id']:return [],'Select the exact minimal HR snapshot and record your native HR receipt'
        return ['ACT08'],'Prepare native '+stage+' result without approval or source edits'
    return [],state['native']['finding']

def act(work,choice,value,latest,missing,tasks,jobs):
    from .factory import access
    actor=work.execution_actor;case=lock_case(actor,work.case_id,'factory.execute');access(actor,case,'factory.execute',DEFINITION)
    list(Grant.objects.select_for_update().filter(case=case).order_by('pk'))
    if case.revision!=work.case.revision:raise ValidationError('STALE_VERSION: payroll sources changed')
    q,data=source(work,actor);state=report(work,actor);stage=state['stage'];kind=choice['activity']
    if kind=='ACT04':
        require(actor,case,'agent.payroll')
        return {'head':work.source_head_id,'native':state,'private_payloads_read':False,'questions':['Source owners must replace rejected or superseded payroll versions.','HR owns staff fact corrections; never infer employee merges or transfer ratios.','Finance reviews each exact native input and working result; recipients acknowledge their own aggregate.'],'review_approved':False}
    if kind=='ACT08':
        if stage=='combine':r=native.combine(actor,case.pk,q.pk,data['inputs']['input_ids'],key(work,stage),case.revision)
        elif stage=='match':r=native.match(actor,case.pk,run(work,'combine').pk,data['inputs']['hr_snapshot_id'],key(work,stage),case.revision)
        elif stage=='aggregate':r=native.aggregate(actor,case.pk,run(work,'match').pk,key(work,stage),case.revision)
        else:raise ValidationError('Native human review required before further preparation')
        return {'head':work.source_head_id,'run':r.pk,'kind':r.kind,'sha256':r.sha256,'status':r.metadata['status'],'codes':r.metadata['codes'],'private_payloads_in_result':False}
    if kind=='ACT13':result=verify(work,actor);work.status='verified';return result
    raise ValidationError('Factory cannot approve payroll, publish as a human or impersonate recipient receipts')

@transaction.atomic
def correct(actor,work_id,expected,case_expected,request_id,inputs,reason):
    from .factory import access
    w=Work.objects.select_for_update(of=('self',)).select_related('case','source_head','actor').get(pk=work_id,definition=DEFINITION)
    access(actor,w.case,'factory.manage',DEFINITION);case=lock_case(actor,w.case_id,'evidence.add',case_expected);w.case=case
    if type(expected) is not int or expected!=w.revision or w.cancel_requested or w.status in ['cancelled','followup_needed'] or w.lease_until and w.lease_until>timezone.now():raise ValidationError('STALE_VERSION: refresh current payroll work')
    from apps.agents.factory_coordinator import pending,has_receipt
    planning=pending(w)
    if planning and not has_receipt(planning):raise ValidationError('Reconcile original planning response before source replacement')
    if not isinstance(reason,str) or not reason.strip() or len(reason)>2000:raise ValidationError('Explain the source-owned replacement')
    q=native.exact(case,PayrollRequest,request_id)
    if q.reference!=w.request['payroll_reference']:raise ValidationError('Choose the same native payroll request reference')
    input_rows(actor,case,q,inputs)
    prior=json.loads(w.source_head.body)
    if prior['request_id']==q.pk and prior['inputs']==inputs:
        rework=False
        for stage in ['combine','match','aggregate']:
            r=run(w,stage)
            if not r:continue
            review=r.reviews.order_by('-pk').first()
            if r.metadata['status']=='held' or review and review.verdict in ['return','revoke']:rework=True
            try:native.run_current(r)
            except (PermissionDenied,ValidationError):rework=True
        if not rework:raise ValidationError('Select replaced sources or a genuinely held, returned or stale native result; no unchanged replay')
    old=w.source_head_id;w.source_head=capture(actor,case,q,inputs,'factory.payroll_source');w.status='ready';w.finding='';w.revision+=1;w.save()
    event(actor,case,'factory.payroll_corrected',work=w.pk,previous=old,current=w.source_head_id,reason=reason);return w

@transaction.atomic
def human_action(actor,work_id,expected,case_expected,action,values):
    from .factory import access
    w=Work.objects.select_for_update(of=('self',)).select_related('case','source_head','actor').get(pk=work_id,definition=DEFINITION)
    access(actor,w.case,'factory.read',DEFINITION)
    if type(expected) is not int or w.revision!=expected or (w.cancel_requested and action!='receive') or w.lease_until and w.lease_until>timezone.now():raise ValidationError('STALE_VERSION: refresh current payroll work')
    # Recipients need aggregate rights, not raw salary access.
    if action=='receive':
        p=publication(w)
        if not p or values['publication_id']!=p.pk:raise ValidationError('Select this work exact aggregate publication')
        return native.receive_report(actor,w.case_id,p.pk,case_expected)
    q,data=source(w,actor)
    if action=='review':
        refs=data['inputs']['input_ids'] if values['kind']=='input' else [r.pk for r in [run(w,s) for s in ['combine','match','aggregate']] if r]
        if values['subject_id'] not in refs:raise ValidationError('Review an exact current work subject')
        return native.review(actor,w.case_id,values['kind'],values['subject_id'],values['verdict'],values['operation_key'],values['evidence_id'],case_expected)
    if action=='publish':
        a=run(w,'aggregate')
        if not a:raise ValidationError('Prepare the exact aggregate before human publication')
        return native.publish(actor,w.case_id,a.pk,key(w,'publish'),case_expected)
    raise ValidationError('Choose an explicit native human decision')

@transaction.atomic
def cancel(actor,work_id,expected):
    from .factory import access,manage,cancellation_status
    if type(expected) is not int or expected<1:raise ValidationError('Exact rendered work version required')
    w=Work.objects.select_for_update(of=('self',)).select_related('case','source_head').get(pk=work_id,definition=DEFINITION)
    access(actor,w.case,'factory.manage',DEFINITION)
    if w.revision!=expected:raise ValidationError('STALE_VERSION: refresh payroll work')
    if w.status in ['verified','followup_needed']:raise ValidationError('Published or verified work requires native follow-up')
    if w.status=='cancelled':return w
    if not w.cancel_requested:w=manage(actor,w.pk,w.revision,'cancel')
    if w.lease_until and w.lease_until>timezone.now():return w
    w.status=cancellation_status(w);w.finding='Stopping preparation does not undo a published aggregate or recipient receipt.'
    w.lease_until=None;w.revision+=1;w.save();return w

def publication_history(work):
    """All native request versions belonging to this canonical payroll work."""
    return PayrollPublication.objects.filter(request__case=work.case,request__reference=work.request['payroll_reference'])

@transaction.atomic
def restart(actor,work_id,expected,case_expected,request_id,inputs,configuration_id,instruction_key,reason):
    from .factory import access,profile,adopt_profile
    from .factory_definitions import definition
    from apps.agents.factory_coordinator import pending,has_receipt
    w=Work.objects.select_for_update(of=('self',)).select_related('case','source_head','actor').get(pk=work_id,definition=DEFINITION)
    access(actor,w.case,'factory.manage',DEFINITION)
    case=lock_case(actor,w.case_id,'evidence.add');w.case=case
    validate(native.KEY,instruction_key)
    if not isinstance(reason,str) or not reason.strip() or len(reason)>2000:raise ValidationError('Explain the fresh payroll instruction without employee details')
    q=native.exact(case,PayrollRequest,request_id)
    if q.reference!=w.request['payroll_reference']:raise ValidationError('Select the same canonical payroll request')
    input_rows(actor,case,q,inputs)
    config=active_component(definition(DEFINITION)['component'],case)
    if type(configuration_id) is not int or configuration_id!=config.pk:raise ValidationError('Select the exact current execution profile')
    intent={'request_id':q.pk,'inputs':inputs,'configuration_id':configuration_id,'reason':reason}
    sha=digest(intent)
    old=Audit.objects.filter(case=case,action='factory.payroll_restarted',data__work=w.pk,data__instruction_key=instruction_key).first()
    if old:
        if old.actor_id!=actor.pk or old.data['intent_sha256']!=sha or old.data['current']!=w.source_head_id or w.cancel_requested:raise ValidationError('Restart instruction was reused for changed intent or later work')
        profile(w);return w
    if type(expected) is not int or type(case_expected) is not int or w.revision!=expected or case.revision!=case_expected:raise ValidationError('STALE_VERSION: refresh payroll work and workspace')
    if publication_history(w).exists():raise ValidationError('A publication exists in this payroll request history; use native follow-up, not restart')
    if w.status!='cancelled' or not w.cancel_requested:raise ValidationError('Only settled never-published cancellation can receive a fresh instruction')
    if w.lease_until and w.lease_until>timezone.now():raise ValidationError('Wait for the original worker to stop')
    planning=pending(w)
    if planning and not has_receipt(planning):raise ValidationError('Reconcile the original planning response before restarting')
    # No external effect occurs here. Denied native adoption rolls this entire
    # transaction back, including the tentative reopening and instruction.
    instruction=add_evidence(actor,case.pk,'agent_private_payroll_restart_instruction',json.dumps({'work':w.pk,'instruction_key':instruction_key,**intent},sort_keys=True),'psl:payroll-restart/v1')
    prior=w.source_head_id
    w.source_head=capture(actor,case,q,inputs,'factory.payroll_source')
    w.cancel_requested=False;w.status='ready';w.finding='';w.lease_until=None;w.observation_hash='';w.fence+=1;w.revision+=1;w.save()
    if w.policy_id!=config.pk:w=adopt_profile(actor,w.pk,w.revision,configuration_id,reason)
    else:profile(w)
    event(actor,case,'factory.payroll_restarted',work=w.pk,previous=prior,current=w.source_head_id,instruction=instruction.pk,instruction_key=instruction_key,intent_sha256=sha,configuration=config.pk,spent=w.budget_used,lifetime_allowance=w.budget_limit)
    return w

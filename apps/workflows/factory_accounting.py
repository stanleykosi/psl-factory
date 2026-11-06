"""Accounting coordination references native Finance decisions, calculations and receipts."""
import json
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError,PermissionDenied
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from apps.core.services import lock_case,event,add_evidence
from apps.core.models import Evidence
from apps.core.evidence_access import public_evidence
from apps.identity.services import require
from apps.policy.services import resolve,reference_values
from apps.policy.models import Configuration,ScopeApplication
from apps.finance import analysis
from apps.finance.billing import digest
from apps.finance.models import FinanceSource,FinanceRun,FinanceAdjustment,FinanceDocumentBinding
from apps.finance.documents import report_inputs,binding_findings
from apps.documents.models import Publication,PublicationJob,PublicationReceipt
from apps.documents.controlled import reserve_publication,current_version
from adapters.factory_accounting import NativeAccountingAdapter
from .models import FactoryWork as Work,FactoryActivity as Activity,HumanTask,TaskEvent

DEFINITION='finance-accounts/v1'
PROCESS_IDS=['F03','F04','F09','F14','F15','F19','F20','F22','F23']

def process_for_activity(kind,state,value):
    if kind=='ACT08':return 'F03' if not state['mapping'] else 'F22' if value['allocation_mode']=='company_and_bu' and not state['allocation'] else 'F09'
    return 'F23' if state['formula'] or kind in ['ACT09','ACT11','ACT12','ACT13'] else 'F03'

def record_inputs(actor,case,payload):
    value={'schema':'factory-accounting-intake/v1',**payload}
    evidence=add_evidence(actor,case.pk,'agent_private_accounting_intake',json.dumps(value,sort_keys=True),'derived:factory-accounting-inputs',case.revision)
    event(actor,case,'factory.accounting_inputs_recorded',evidence_id=evidence.pk,sha256=evidence.sha256)
    case.refresh_from_db();return evidence

def inputs(work):
    if not work.source_head or work.source_head.kind!='agent_private_accounting_intake' or work.source_head.case_id!=work.case_id:raise ValidationError('Native accounting intake reference required')
    try:value=json.loads(work.source_head.body)
    except (ValueError,TypeError) as exc:raise ValidationError('Typed accounting intake reference required') from exc
    if set(value)!={'schema','source','batch','entity','reference','adjustment_ids'} or value['schema']!='factory-accounting-intake/v1':raise ValidationError('Closed accounting intake schema required')
    if value['batch']!=work.request['batch'] or value['entity']!=work.request['entity'] or value['reference']!=work.request['reference']:raise ValidationError('Accounting intake cannot silently change its original business scope')
    return value

@transaction.atomic
def start(actor,case_id,key,source_id,adjustment_ids,reference,expected):
    from .factory import access
    case=lock_case(actor,case_id,'factory.start',expected);access(actor,case,'factory.start',DEFINITION)
    if type(source_id) is not int:raise ValidationError('Exact native accounting source identity required')
    source=analysis.source_for(case,source_id)
    if not isinstance(key,str) or not 1<=len(key)<=100 or not key.isascii():raise ValidationError('Bounded accounting work identity required')
    if not isinstance(reference,str) or not reference.strip() or len(reference)>100:raise ValidationError('Accounting report reference required')
    if not isinstance(adjustment_ids,list) or len(adjustment_ids)>100 or any(type(pk) is not int for pk in adjustment_ids) or len(set(adjustment_ids))!=len(adjustment_ids):
        raise ValidationError('Declare a unique exact adjustment inventory, including an explicit empty selection')
    if FinanceAdjustment.objects.filter(source=source,pk__in=adjustment_ids).count()!=len(adjustment_ids):raise ValidationError('Adjustments must belong to this exact native source')
    payload={'source':source.pk,'batch':source.batch_id,'entity':source.entity,'reference':reference,'adjustment_ids':sorted(adjustment_ids)}
    business=digest([DEFINITION,str(case.pk),source.batch_id,source.entity]);sha=digest(payload)
    old=Work.objects.filter(case=case).filter(Q(key=key)|Q(definition=DEFINITION,business_key=business)).first()
    if old:
        if old.actor_id!=actor.pk or old.definition!=DEFINITION or old.request_hash!=sha:raise ValidationError('IDEMPOTENCY_CONFLICT: accounting source, scope, adjustments or initiator differs')
        return old
    head=record_inputs(actor,case,payload)
    work=Work.objects.create(case=case,actor=actor,key=key,definition=DEFINITION,request=payload,request_hash=sha,business_key=business,source_head=head)
    event(actor,case,'factory.started',work=work.pk,definition=DEFINITION);return work

def source_for(work,allow_stale=False):
    value=inputs(work);source=FinanceSource.objects.filter(case=work.case,pk=value['source'],batch_id=work.request['batch']).first()
    if not source or source.entity!=work.request['entity']:raise ValidationError('Accounting entity/source changed; source-owned follow-up required')
    return source if allow_stale else analysis.source_for(work.case,source.pk)

def current_run(work,source,kind,parent=None):
    for run in FinanceRun.objects.filter(case=work.case,source=source,kind=kind,parent=parent).order_by('-pk')[:100]:
        if kind=='mapping' and run.request!={'adjustment_ids':inputs(work)['adjustment_ids']}:continue
        try:analysis.ensure_current(run)
        except (ValidationError,PermissionDenied):continue
        return run
    return None

def requirements(work,source,value,formula,mapping=None,allocation=None,reader=None):
    # Ask the native stage service which rules this actual allocation needs.
    # Future formula/BU policy cannot stop an independent mapping preview.
    selected=set(analysis.MAP_COMPONENTS)
    if mapping and value['allocation_mode']=='company_and_bu' and value['bu_metrics']:
        selected.update(analysis.stage_policy_components(reader or work.execution_actor,source,'allocation',mapping,{'metrics':sorted(value['bu_metrics'])}))
    if mapping and (value['allocation_mode']=='company_only' or allocation):selected.add('D06.rule_oracle_refs')
    rows=[{'purpose':'source','subject':'source','id':source.pk,'preparer':source.actor_id}];missing=[];policies={}
    for component in sorted(selected):
        resolution=resolve(component,work.case);policies[component]={'status':resolution.status,'id':resolution.configuration.pk if resolution.configuration else None}
        if resolution.status!='ACTIVE':missing.append(component);continue
        if component in analysis.PURPOSE:
            rows.append({'purpose':analysis.PURPOSE[component],'subject':'configuration','id':resolution.configuration.pk,'preparer':resolution.configuration.created_by_id})
    for pk in inputs(work)['adjustment_ids']:
        row=FinanceAdjustment.objects.filter(source=source,pk=pk).first()
        if not row:raise ValidationError('Selected reporting adjustment needs source-owned correction')
        rows.append({'purpose':'adjustment','subject':'adjustment','id':row.pk,'preparer':row.actor_id})
    if formula and not analysis.certification_findings(formula):rows.append({'purpose':'output','subject':'run','id':formula.pk,'preparer':formula.actor_id})
    for row in rows:row['review']=analysis.current_review(work.case,row['purpose'],**{row['subject']+'_id':row['id']})
    return rows,missing,policies

def route(work,row,value):
    from .factory import access
    result=[]
    for actor in get_user_model().objects.filter(is_active=True,grant__case=work.case,grant__active=True,grant__action='finance.review').distinct().order_by('pk'):
        try:
            access(actor,work.case,envelope=DEFINITION)
            if row['subject']=='configuration':
                app=ScopeApplication.objects.select_related('source__configuration__case').filter(configuration_id=row['id']).first()
                if app:
                    from apps.policy.scopes import authorized
                    authorized(actor,app.source.configuration.case,'policy.read')
        except PermissionDenied:continue
        actions={}
        for verdict in ['approve','return','reject']:
            try:authority=analysis.review_authority(actor,work.case,row['purpose'],value['review_role'],verdict,row['preparer'])
            except (ValidationError,PermissionDenied):continue
            actions[verdict]={k:v for k,v in authority.items() if k!='D05.decision_action_matrix'}
        if actions:result.append({'id':actor.pk,'decisions':actions})
    return result

def packet(work,row,value):
    return {'schema':'factory-accounting-review/v1','work':work.pk,'head':work.source_head_id,'source':source_for(work).pk,'purpose':row['purpose'],
        'subject':row['subject'],'target':row['id'],'role':value['review_role'],'profile':work.policy_id,'candidates':route(work,row,value)}

def document_for(work,formula,value):
    if not formula:return None
    for binding in FinanceDocumentBinding.objects.select_related('version__document').filter(run=formula,version__template_id=value['template_id'],version__audience=value['audience']).order_by('-pk')[:100]:
        try:current_version(work.case,binding.version_id)
        except (ValidationError,PermissionDenied):continue
        if not binding_findings(binding):return binding
    return None

def investigation_key(work,state):return digest(['accounting_investigation',state['source'],state['sources'],state['formula'] or state['allocation'] or state['mapping']])

def snapshot(work,value,reader=None):
    from .factory import access
    access(reader or work.execution_actor,work.case,'factory.read' if reader is not None else 'factory.execute',DEFINITION)
    original_pending=PublicationJob.objects.filter(publication__factory_work=work,status__in=['pending','unknown','leased','held']).exists()
    source=source_for(work,allow_stale=original_pending)
    records=list(public_evidence(Evidence.objects.filter(case=work.case,pk__in=[source.evidence_id,source.batch.evidence_id])).order_by('pk'))
    if len(records)!=len({source.evidence_id,source.batch.evidence_id}):raise PermissionDenied('Native accounting source evidence is unavailable to this production interface')
    latest={e.kind:e for e in records};missing=[k for k in value['required_evidence_kinds'] if k not in latest]
    latest[work.source_head.kind]=work.source_head
    stale=[k for k in value['required_evidence_kinds'] if k in latest and latest[k].created_at<timezone.now()-timedelta(seconds=value['max_age_seconds'])]
    if source.extracted_at<timezone.now()-timedelta(seconds=value['max_age_seconds']):stale.append('source_extraction')
    mapping=current_run(work,source,'mapping');allocation=current_run(work,source,'allocation',mapping) if mapping and value['allocation_mode']=='company_and_bu' else None
    if allocation and allocation.request!={'metrics':sorted(value['bu_metrics'] or [])}:allocation=None
    parent=allocation if value['allocation_mode']=='company_and_bu' else mapping
    formula=current_run(work,source,'formula',parent) if parent else None
    reviews,unconfigured,policies=requirements(work,source,value,formula,mapping,allocation,reader=reader)
    document=document_for(work,formula,value)
    publications=Publication.objects.filter(Q(factory_work=work)|Q(version=document.version if document else None))
    jobs=list(PublicationJob.objects.filter(publication__in=publications).select_related('publication__version').order_by('pk'))
    tasks=list(HumanTask.objects.filter(case=work.case,factory_key__startswith=f'factory:{work.pk}:').order_by('pk'))
    state={'case_revision':work.case.revision,'profile':work.policy_id,'source':source.pk,'head':work.source_head_id,
        'sources':[(e.pk,e.sha256) for e in latest.values()],'mapping':mapping.pk if mapping else None,'allocation':allocation.pk if allocation else None,
        'formula':formula.pk if formula else None,'reviews':reviews,'unconfigured':unconfigured,'policies':policies,
        'document':document.pk if document else None,'jobs':[(j.pk,j.status,j.fence) for j in jobs],
        'tasks':[(t.pk,t.status,t.revision) for t in tasks],
        'receipts':list(PublicationReceipt.objects.filter(publication__in=publications).values_list('pk','operation_key'))}
    state['hash']=digest(state);state['work_revision']=work.revision
    return state,latest,missing,stale,tasks,jobs

def eligible(work,value,state,latest,missing,stale,tasks,jobs):
    if any(j.status=='unknown' or j.status=='leased' and j.lease_until and j.lease_until<=timezone.now() for j in jobs):return ['ACT12'],'Reconcile the original report operation before any new preparation'
    if any(j.status=='leased' for j in jobs):return [],'The native report worker owns the current attempt'
    if any(j.status=='held' for j in jobs):return [],'Original report work needs controlled native recovery'
    if any(j.status=='pending' for j in jobs):return ['ACT11'],'Continue the original native report operation'
    if not Activity.objects.filter(work=work,key=investigation_key(work,state),status='succeeded').exists():return ['ACT04'],'Investigate current accounting evidence and calculation lineage'
    if missing or stale:return [],'Current source evidence is incomplete or stale'
    if state['unconfigured']:return ['ACT10'],'Configure required native accounting rules'
    current_packets={digest(packet(work,r,value)):r for r in state['reviews']}
    if any(t.status=='open' and t.kind=='factory_accounting_review' and
        (digest(t.context.get('packet')) not in current_packets or current_packets[digest(t.context.get('packet'))]['review']['valid']) for t in tasks):
        return ['ACT10'],'Observe native Finance decisions and retire superseded waits'
    pending=[r for r in state['reviews'] if not r['review']['valid']]
    if pending:
        if all(any(t.status=='open' and t.kind=='factory_accounting_review' and t.context.get('packet')==packet(work,r,value) for t in tasks) for r in pending):return [],'Required Finance decisions are waiting on current eligible reviewers'
        return ['ACT10'],'Assemble the required exact Finance decision packets'
    if any(t.status=='open' for t in tasks):return ['ACT10'],'Observe current source-owned Finance decisions'
    if not state['mapping']:return ['ACT08'],'Prepare the native account alignment and control-total preview'
    if value['allocation_mode'] is None or value['allocation_mode']=='company_and_bu' and value['bu_metrics'] is None:return ['ACT10'],'Configure the accounting allocation scope'
    if value['allocation_mode']=='company_and_bu' and not state['allocation']:return ['ACT08'],'Prepare the configured native BU allocation'
    if not state['formula']:return ['ACT08'],'Prepare the configured native formula output'
    formula=FinanceRun.objects.get(pk=state['formula'])
    if analysis.certification_findings(formula):return [],'Resolve the native accounting findings and recheck the source-owned inputs'
    if not state['document']:return ['ACT09'],'Prepare the source-owned aggregate Finance report'
    if not jobs:return ['ACT11'],'Publish the reviewed report through native recipient controls'
    return ['ACT13'],'Verify the exact current report and every intended recipient receipt'

def act(work,choice,value,latest,missing,tasks,jobs):
    from .factory import access
    case=lock_case(work.execution_actor,work.case_id,'factory.execute');access(work.execution_actor,case,'factory.execute',DEFINITION)
    if case.revision!=work.case.revision:raise ValidationError('STALE_VERSION: accounting input changed before the command')
    state,*_=snapshot(work,value);kind=choice['activity']
    source=source_for(work,allow_stale=kind in ['ACT11','ACT12'] and bool(jobs));adapter=NativeAccountingAdapter()
    if kind=='ACT04':
        pk=state['formula'] or state['allocation'] or state['mapping']
        return adapter.investigate(work,source,FinanceRun.objects.get(pk=pk) if pk else None)
    if kind=='ACT10':
        if state['unconfigured']:raise ValidationError('configuration_needed: configure native accounting components '+', '.join(state['unconfigured']))
        if state['mapping'] and (value['allocation_mode'] is None or value['allocation_mode']=='company_and_bu' and value['bu_metrics'] is None):
            raise ValidationError('configuration_needed: explicit company/BU preparation scope is required')
        current={digest(packet(work,r,value)):r for r in state['reviews']};created=[]
        for observed_task in tasks:
            t=HumanTask.objects.select_for_update().get(pk=observed_task.pk)
            if t.kind!='factory_accounting_review' or t.status!='open':continue
            row=current.get(digest(t.context.get('packet')))
            if row and row['review']['valid']:
                t.status='completed';t.revision+=1;t.save(update_fields=['status','revision'])
                TaskEvent.objects.create(task=t,actor=work.execution_actor,action='factory.native_review_observed',data={'native_review':row['review']['id'],'domain':'accounting'})
            elif row is None:
                t.status='returned';t.revision+=1;t.save(update_fields=['status','revision'])
                TaskEvent.objects.create(task=t,actor=work.execution_actor,action='factory.packet_superseded',data={'source':source.pk,'reason':'accounting_subject_changed'})
        for row in state['reviews']:
            if row['review']['valid']:continue
            bound=packet(work,row,value)
            if not bound['candidates']:raise ValidationError('owner_needed: current native Finance review authority is unavailable for '+row['purpose'])
            task,_=HumanTask.objects.get_or_create(case=case,factory_key=f'factory:{work.pk}:accounting:{digest(bound)}',defaults={
                'kind':'factory_accounting_review','created_by':work.execution_actor,'required_role':value['review_role'],
                'context':{'work':work.pk,'purpose':row['purpose'],'packet':bound}})
            if task.status!='open':
                work.status='followup_needed'
                return {'finding':'An earlier exact Finance decision needs source-owned rework or explicit recheck; it is not automatically retried','approval_granted':False}
            created.append(task.pk)
        return {'review_tasks':created,'waiting':'finance_review' if created else None,'approval_granted':False}
    if kind=='ACT08':
        stage='mapping' if not state['mapping'] else 'allocation' if value['allocation_mode']=='company_and_bu' and not state['allocation'] else 'formula'
        parent_id=None if stage=='mapping' else state['mapping'] if stage=='allocation' else state['allocation'] or state['mapping']
        run=adapter.prepare(work,source,stage,FinanceRun.objects.get(pk=parent_id) if parent_id else None,value['bu_metrics'],inputs(work)['adjustment_ids'])
        return {'finance_run':run.pk,'kind':run.kind,'result_status':run.result['status'],'ledger_posted':False}
    if kind=='ACT09':
        if value['template_id'] is None or value['audience'] is None:raise ValidationError('configuration_needed: report template and aggregate audience are required')
        version=adapter.draft(work,FinanceRun.objects.get(pk=state['formula']),value['template_id'],value['audience'])
        return {'document_version':version.pk,'finance_run':state['formula']}
    if kind in ['ACT11','ACT12']:
        unresolved=next((j for j in jobs if j.status in ['pending','unknown','leased']),None)
        if unresolved:return {'publication_job':unresolved.pk,'original_operation':True,'publication_lookup_only':kind=='ACT12'}
        publisher=get_user_model().objects.filter(pk=value['executor_id'],is_active=True).first()
        if publisher is None:raise ValidationError('owner_needed: a current native report publisher is required')
        binding=FinanceDocumentBinding.objects.get(pk=state['document'])
        publication=Publication.objects.filter(version=binding.version).first()
        if publication:return {'publication_job':publication.job.pk,'original_operation':True}
        publication=reserve_publication(publisher,case.pk,binding.version_id,case.revision,factory_work_id=work.pk)
        return {'publication_job':publication.job.pk,'publication':publication.pk}
    if kind=='ACT13':
        result=verified(work,value,state)
        work.status='verified'
        event(work.execution_actor,case,'factory.accounting_verified',work=work.pk,run=state['formula'],publication=result['publication'])
        return result
    raise PermissionDenied('No accounting tool for this activity')

def verified(work,value,state=None):
    state=state if state is not None else snapshot(work,value)[0]
    if not state['formula'] or not state['document']:raise ValidationError('Current native accounting output and document binding required')
    run=FinanceRun.objects.get(pk=state['formula']);report_inputs(run,value['audience'])
    binding=FinanceDocumentBinding.objects.select_related('version').get(pk=state['document'])
    current_version(work.case,binding.version_id)
    if binding_findings(binding):raise ValidationError('Current exact Finance document projection required')
    publication=Publication.objects.select_related('job').filter(version=binding.version).first()
    if publication is None or publication.job.status!='confirmed':raise ValidationError('Native report delivery is not confirmed')
    receipts=list(PublicationReceipt.objects.filter(publication=publication).order_by('pk'))
    if not publication.recipient_ids or sorted(r.recipient_id for r in receipts)!=sorted(publication.recipient_ids):raise ValidationError('Every exact native report recipient receipt is required')
    return {'verified':True,'source':run.source_id,'run':run.pk,'binding':binding.pk,'publication':publication.pk,
        'document_version':binding.version_id,'receipt_ids':[r.pk for r in receipts],'ledger_posted':False}

@transaction.atomic
def claim(actor,task_id,expected):
    from .factory import access,profile
    initial=HumanTask.objects.get(pk=task_id);work=Work.objects.select_for_update(of=('self',)).select_related('case','actor').get(pk=initial.context['work'],case=initial.case,definition=DEFINITION)
    task=HumanTask.objects.select_for_update().get(pk=task_id);access(actor,work.case,envelope=DEFINITION);work.case=lock_case(actor,work.case_id,'finance.review')
    # This native human decision needs current Finance controls, not an agent planner.
    _,value=profile(work,recovery=True);row=review_task(work,task,value,reader=actor)
    if task.status!='open' or task.revision!=expected or task.claimed_by_id not in [None,actor.pk]:raise ValidationError('STALE_VERSION: current open accounting task required')
    if actor.pk not in {r['id'] for r in route(work,row,value)}:raise PermissionDenied('Current native Finance review authority required')
    task.claimed_by=actor;task.revision+=1;task.save(update_fields=['claimed_by','revision'])
    TaskEvent.objects.create(task=task,actor=actor,action='factory.accounting_claimed',data={'work':work.pk});return task

def review_task(work,task,value,reader=None):
    if task.kind!='factory_accounting_review' or work.cancel_requested or work.status in ['verified','cancelled','followup_needed']:raise ValidationError('Current running accounting review required')
    state=snapshot(work,value,reader=reader)[0]
    for row in state['reviews']:
        if not row['review']['valid'] and task.context.get('packet')==packet(work,row,value):return row
    raise ValidationError('STALE_VERSION: native accounting subject, policy or review changed')

@transaction.atomic
def decide(actor,task_id,expected,verdict,evidence_id,reason):
    from .factory import access,profile
    initial=HumanTask.objects.get(pk=task_id);work=Work.objects.select_for_update(of=('self',)).select_related('case','actor').get(pk=initial.context['work'],case=initial.case,definition=DEFINITION)
    task=HumanTask.objects.select_for_update().get(pk=task_id);access(actor,work.case,envelope=DEFINITION)
    case=lock_case(actor,work.case_id,'finance.review');work.case=case
    if task.status!='open' or task.claimed_by_id!=actor.pk or task.revision!=expected:raise ValidationError('STALE_VERSION: current claimed accounting task required')
    _,value=profile(work,recovery=True);row=review_task(work,task,value,reader=actor)
    review=analysis.review(actor,case.pk,row['purpose'],row['id'],value['review_role'],verdict,evidence_id,reason,case.revision)
    task.status='completed' if verdict=='approve' else 'returned';task.revision+=1;task.save(update_fields=['status','revision'])
    TaskEvent.objects.create(task=task,actor=actor,action='factory.accounting_review',data={'native_review':review.pk,'verdict':verdict})
    work.status='ready' if verdict=='approve' else 'followup_needed';work.finding='' if verdict=='approve' else 'Native Finance decision requires source-owned rework';work.revision+=1;work.save()
    return review

def publication_scope(actor,case,version,work_id):
    from .factory import access,profile
    work=Work.objects.select_related('case','actor').get(pk=work_id,case=case,definition=DEFINITION)
    access(actor,case,'factory.execute',DEFINITION);require(actor,case,'finance.publish');require(actor,case,'document.publish')
    config,value=profile(work)
    if value['executor_id']!=actor.pk or work.policy_id!=config.pk:raise PermissionDenied('Exact configured accounting publisher required')
    if work.cancel_requested or work.status in ['verified','cancelled','followup_needed']:raise ValidationError('Accounting publication is stopped')
    state=snapshot(work,value)[0];binding=FinanceDocumentBinding.objects.get(pk=state['document'])
    if binding.version_id!=version.pk or binding.run.source_id!=source_for(work).pk or binding_findings(binding):raise ValidationError('Current exact accounting output and source required')
    return {'factory_work_id':work.pk,'factory_policy_id':config.pk,'factory_source_id':work.source_head_id}

def reconcile(actor,work_id,expected):
    """Read original local receipts without authorising another delivery or new inputs."""
    from .factory import access,cancellation_status
    from apps.documents.delivery import run_publication_once
    with transaction.atomic():
        work=Work.objects.select_for_update(of=('self',)).select_related('case','actor').get(pk=work_id,definition=DEFINITION)
        access(actor,work.case,'factory.execute',DEFINITION);require(actor,work.case,'document.publish')
        from .factory_execution import require_control
        require_control(actor,work)
        if work.revision!=expected:raise ValidationError('STALE_VERSION: accounting work changed')
        if work.lease_until and work.lease_until>timezone.now():raise ValidationError('CONFLICT: worker owns this work')
        job=PublicationJob.objects.filter(publication__factory_work=work).filter(Q(status='unknown')|Q(status='leased',lease_until__lte=timezone.now())).order_by('pk').first()
        if job is None:raise ValidationError('No original uncertain report operation to reconcile')
        event(actor,work.case,'factory.accounting_reconciliation_requested',work=work.pk,job=job.pk,lookup_only=True)
    run_publication_once(case_id=work.case_id,job_id=job.pk,lookup_only=True)
    with transaction.atomic():
        work=Work.objects.select_for_update().get(pk=work_id);job.refresh_from_db()
        if work.revision!=expected:return work
        work.status=cancellation_status(work) if work.cancel_requested else 'waiting_effect' if job.status=='unknown' else 'ready'
        work.finding='The original report result remains uncertain; no new delivery is authorised' if job.status=='unknown' else ''
        work.observation_hash='';work.revision+=1;work.save()
    return work

@transaction.atomic
def recheck(actor,work_id,expected,source_id,adjustment_ids,reason):
    from .factory import access,profile
    work=Work.objects.select_for_update(of=('self',)).select_related('case','actor','source_head').get(pk=work_id,definition=DEFINITION)
    access(actor,work.case,'factory.execute',DEFINITION);case=lock_case(actor,work.case_id,'finance.source')
    if work.revision!=expected:raise ValidationError('STALE_VERSION: accounting work changed')
    if work.cancel_requested or work.status in ['cancelled','waiting_effect'] or work.lease_until and work.lease_until>timezone.now():raise ValidationError('Stopped or currently owned accounting work cannot be reconstituted')
    if PublicationJob.objects.filter(publication__factory_work=work,status__in=['pending','unknown','leased','held']).exists():raise ValidationError('Resolve original native report work before changing inputs')
    source=analysis.source_for(case,source_id)
    if source.batch_id!=work.request['batch'] or source.entity!=work.request['entity']:raise ValidationError('Same original accounting entity and import required; new scope needs a separately reviewed work item')
    if not isinstance(adjustment_ids,list) or len(adjustment_ids)>100 or any(type(pk) is not int for pk in adjustment_ids) or len(set(adjustment_ids))!=len(adjustment_ids) or FinanceAdjustment.objects.filter(source=source,pk__in=adjustment_ids).count()!=len(adjustment_ids):raise ValidationError('Exact current-source adjustment inventory required')
    if not isinstance(reason,str) or not reason.strip() or len(reason)>2000:raise ValidationError('Explain the source-owned accounting recheck')
    profile(work);old=work.source_head_id
    head=record_inputs(actor,case,{'source':source.pk,'batch':source.batch_id,'entity':source.entity,'reference':work.request['reference'],'adjustment_ids':sorted(adjustment_ids)})
    work.source_head=head;work.status='ready';work.finding='';work.revision+=1;work.save()
    event(actor,case,'factory.accounting_rechecked',work=work.pk,previous_head=old,head=head.pk,reason=reason,budget_reset=False)
    return work

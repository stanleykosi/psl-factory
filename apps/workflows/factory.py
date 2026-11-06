"""Bounded native PMO/Finance coordinator. Never owns invoice, decision or receipt truth."""
from datetime import timedelta,date
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied,ValidationError
from django.db import transaction
from django.db.models import Q,Max
from django.utils import timezone
from apps.core.models import Evidence
from apps.core.evidence_access import public_evidence
from apps.core.services import lock_case,event
from apps.identity.services import require,visible_cases
from apps.policy.services import active_component,reference_values
from apps.policy.factory_validators import COMPONENT
from apps.finance import billing,invoices,invoice_delivery
from apps.finance.billing import digest
from apps.finance.models import BillingCoverage,Handoff,InvoiceJob,InvoiceIssue,InvoiceDelivery
from apps.agents.models import AgentRun
from apps.agents.factory_catalogue import SyntheticFactoryCoordinator
from .models import FactoryWork as Work,FactoryActivity as Activity,FactoryAttempt as Attempt,HumanTask,TaskEvent
from .factory_definitions import definition

TERMINAL={'verified','cancelled','blocked','owner_needed','configuration_needed','followup_needed'}

def access(actor,case,action='factory.read',envelope='pmo-finance/v1'):
    if not get_user_model().objects.filter(pk=actor.pk,is_active=True).exists():raise PermissionDenied('Current active actor required')
    for key in ['case.read',definition(envelope)['read'],action]:require(actor,case,key)

def profile(work,*,recovery=False):
    config=active_component(definition(work.definition)['component'],work.case);value=reference_values(config)[0]
    if work.definition!=value['definition']:raise ValidationError('unknown_case: no matching versioned process definition is configured')
    if work.policy_id and work.policy_id!=config.pk:raise ValidationError('policy_changed: explicit revalidation required; budget is not reset')
    if not value['enabled']:raise ValidationError('Factory execution is disabled')
    if value['provider'] is None:raise ValidationError('configuration_needed: select a factory coordinator')
    if value['provider']=='synthetic_factory_v1':
        if not work.case.synthetic:raise ValidationError('Synthetic providers cannot execute operational work')
    elif value['provider']=='governed_factory_v1':
        from apps.agents.factory_coordinator import configured
        if not recovery:
            _,coordination=configured(work)
            if coordination['mode']=='authenticated_planner_v1' and value['lease_seconds']<10:
                raise ValidationError('configuration_needed: provider planning requires a lease of at least ten seconds')
    else:raise ValidationError('Unsupported factory coordinator')
    return config,value

@transaction.atomic
def start(actor,case_id,key,coverage_id,handoff_id,reference,expected):
    case=lock_case(actor,case_id,'factory.start',expected);access(actor,case,'factory.start')
    if case.kind!='project':raise ValidationError('This definition requires an exact PMO project completion handoff')
    if not isinstance(key,str) or not 1<=len(key)<=100 or not key.isascii():raise ValidationError('Bounded work identity required')
    from adapters.billing_usage import KEY
    if not isinstance(reference,str) or not KEY.fullmatch(reference):raise ValidationError('Bounded invoice reference required')
    cov=BillingCoverage.objects.filter(case=case,pk=coverage_id).first()
    handoff=Handoff.objects.filter(case=case,pk=handoff_id).first()
    if not cov or not handoff:raise ValidationError('Exact same-case contract coverage and native PMO handoff required')
    payload={'coverage':cov.pk,'handoff':handoff.pk,'reference':reference,'stage':'completion'};sha=digest(payload)
    from types import SimpleNamespace
    business_key=invoices.obligation(SimpleNamespace(coverage=cov,case_id=case.pk,kind='completion'))
    old=Work.objects.filter(case=case).filter(Q(key=key)|Q(definition='pmo-finance/v1',business_key=business_key)).first()
    if old:
        if old.request_hash!=sha or old.actor_id!=actor.pk:raise ValidationError('IDEMPOTENCY_CONFLICT: same work key has different payload or initiator')
        return old
    work=Work.objects.create(case=case,actor=actor,key=key,business_key=business_key,request=payload,request_hash=sha)
    event(actor,case,'factory.started',work=work.pk,definition=work.definition)
    return work

def sources(work):
    rows=list(public_evidence(Evidence.objects.filter(case=work.case)).order_by('kind','-version').distinct('kind')[:129])
    if len(rows)>128:raise ValidationError('Context budget exceeded; narrow the source scope before agent work')
    return rows

def route(actor,work):
    access(actor,work.case)
    if not work.invoice_id:return []
    from .factory_routing import evaluate
    return list(get_user_model().objects.filter(pk__in=evaluate(work)['eligible_principals']).order_by('pk'))


def assert_review_task_current(work,task):
    if task.context['packet']!=invoices.review_packet(work.invoice):raise ValidationError('STALE_EVIDENCE: publication packet changed')
    from .factory_routing import task_authority_current
    if not task_authority_current(work,task):raise ValidationError('STALE_AUTHORITY: Finance review routing changed; prepare a current decision task')

def invoice_jobs(work):
    """Only recorded factory intents/observations own a job, never invoice association alone."""
    if work.definition!='pmo-finance/v1':return []
    recorded=set()
    for result in Attempt.objects.filter(activity__work=work,activity__kind__in=['ACT11','ACT12'],phase='observed').values_list('result',flat=True):
        for key in ['job','dispatch_job']:
            if type(result.get(key)) is int and result[key]>0:recorded.add(result[key])
    query=InvoiceJob.objects.filter(invoice__case=work.case,invoice__obligation_key=work.business_key,kind__in=['issue','deliver'])
    query=query.filter(Q(intent__factory_execution__work=work.pk)|Q(pk__in=recorded))
    return [job for job in query.select_related('invoice__case').order_by('pk')
        if job.intent.get('factory_execution',{}).get('work',work.pk)==work.pk]

def uncertain_job(job):
    return job.status=='unknown' or job.status=='leased' and job.lease_until is not None and job.lease_until<=timezone.now()

def invoice_job_observation(jobs):
    return [(job.pk,job.status,'expired' if job.status=='leased' and uncertain_job(job) else None) for job in jobs]

def _snapshot(work,value,reader=None):
    if work.definition=='pmo-change/v1':
        from .factory_change import snapshot as change_snapshot
        return change_snapshot(work,value,reader=reader)
    if work.definition=='rfp-response/v1':
        from .factory_rfp import snapshot as rfp_snapshot
        return rfp_snapshot(work,value,reader=reader)
    if work.definition=='finance-accounts/v1':
        from .factory_accounting import snapshot as accounting_snapshot
        return accounting_snapshot(work,value,reader=reader)
    if work.definition=='delivery-go-live/v1':
        from .factory_go_live import snapshot as go_live_snapshot
        return go_live_snapshot(work,value,reader=reader)
    if work.definition=='delivery-closure/v1':
        from .factory_closure import snapshot as closure_snapshot
        return closure_snapshot(work,value,reader=reader)
    if work.definition=='delivery-handover/v1':
        from .factory_handover import snapshot as handover_snapshot
        return handover_snapshot(work,value,reader=reader)
    if work.definition=='delivery-archive/v1':
        from .factory_archive import snapshot as archive_snapshot
        return archive_snapshot(work,value,reader=reader)
    if work.definition=='delivery-hypercare/v1':
        from .factory_hypercare import snapshot as hypercare_snapshot
        return hypercare_snapshot(work,value,reader=reader)
    if work.definition=='delivery-release/v1':
        from .factory_delivery import snapshot as delivery_snapshot
        return delivery_snapshot(work,value,reader=reader)
    if work.definition=='commercial/v1':
        from .factory_commercial import snapshot as commercial_snapshot
        return commercial_snapshot(work,value,reader=reader)
    if work.definition=='planning/v1':
        from .factory_planning import snapshot as planning_snapshot
        return planning_snapshot(work,value,reader=reader)
    access(reader or work.execution_actor,work.case,'factory.read' if reader is not None else 'factory.execute')
    records=sources(work);latest={}
    for e in records:latest.setdefault(e.kind,e)
    missing=[kind for kind in value['required_evidence_kinds'] if kind not in latest]
    stale=[kind for kind in value['required_evidence_kinds'] if kind in latest and latest[kind].created_at<timezone.now()-timedelta(seconds=value['max_age_seconds'])]
    tasks=list(HumanTask.objects.filter(case=work.case,factory_key__startswith=f'factory:{work.pk}:').order_by('pk'))
    jobs=invoice_jobs(work)
    state={'case_revision':work.case.revision,'profile':work.policy_id,'sources':[(e.pk,e.sha256) for e in records],
        'invoice':work.invoice_id,'preparation':work.preparation_id,'jobs':invoice_job_observation(jobs),
        'receipts':list(InvoiceIssue.objects.filter(invoice_id=work.invoice_id).values_list('pk','sha256'))+list(InvoiceDelivery.objects.filter(invoice_id=work.invoice_id).values_list('pk','sha256')) if work.invoice_id else [],
        'tasks':[(t.pk,t.status,t.revision) for t in tasks]}
    if work.invoice_id:
        from .factory_routing import evaluate
        state['routing']=evaluate(work)
    state['hash']=digest(state)
    state['work_revision']=work.revision # concurrency check; excluded from no-progress fingerprint
    return state,latest,missing,stale,tasks,jobs

def snapshot(work,value,reader=None):
    result=_snapshot(work,value,reader)
    if work.execution_binding_id is None:return result
    state=dict(result[0],execution_binding=work.execution_binding_id)
    state['hash']=digest({k:v for k,v in state.items() if k not in ['hash','work_revision']})
    return (state,*result[1:])

def eligible(work,value,observed,latest,missing,stale,tasks,jobs):
    if work.definition=='rfp-response/v1':
        from .factory_rfp import eligible as rfp_eligible
        return rfp_eligible(work,value,observed,latest,missing,stale,tasks,jobs)
    if work.definition=='finance-accounts/v1':
        from .factory_accounting import eligible as accounting_eligible
        return accounting_eligible(work,value,observed,latest,missing,stale,tasks,jobs)
    if work.definition=='pmo-change/v1':
        from .factory_change import eligible as change_eligible
        return change_eligible(work,value,observed,latest,missing,stale,tasks,jobs)
    if work.definition=='delivery-go-live/v1':
        from .factory_go_live import eligible as go_live_eligible
        return go_live_eligible(work,value,observed,latest,missing,stale,tasks,jobs)
    if work.definition=='delivery-closure/v1':
        from .factory_closure import eligible as closure_eligible
        return closure_eligible(work,value,observed,latest,missing,stale,tasks,jobs)
    if work.definition=='delivery-handover/v1':
        from .factory_handover import eligible as handover_eligible
        return handover_eligible(work,value,observed,latest,missing,stale,tasks,jobs)
    if work.definition=='delivery-archive/v1':
        from .factory_archive import eligible as archive_eligible
        return archive_eligible(work,value,observed,latest,missing,stale,tasks,jobs)
    if work.definition=='delivery-hypercare/v1':
        from .factory_hypercare import eligible as hypercare_eligible
        return hypercare_eligible(work,value,observed,latest,missing,stale,tasks,jobs)
    if work.definition=='delivery-release/v1':
        from .factory_delivery import eligible as delivery_eligible
        return delivery_eligible(work,value,observed,latest,missing,stale,tasks,jobs)
    if work.definition=='commercial/v1':
        from .factory_commercial import eligible as commercial_eligible
        return commercial_eligible(work,value,observed,latest,missing,stale,tasks,jobs)
    if work.definition=='planning/v1':
        from .factory_planning import eligible as planning_eligible
        return planning_eligible(work,value,observed,latest,missing,stale,tasks,jobs)
    # Original effects precede changed-source rework and all new-send/review gates.
    if any(uncertain_job(job) for job in jobs):return ['ACT12'],'Observe the original invoice receipt before any new work'
    if any(job.status=='leased' for job in jobs):return [],'Native invoice worker owns the current attempt'
    if any(job.status=='held' for job in jobs):return [],'Native invoice work needs controlled operator recovery'
    if any(job.status=='pending' for job in jobs):return ['ACT11'],'Process the existing controlled invoice reservation'
    if InvoiceIssue.objects.filter(obligation_key=work.business_key).exclude(invoice_id=work.invoice_id).exists():
        raise ValidationError('A prior invoice for this obligation is already issued; retain both drafts and use its native correction workflow')
    if stale:return [],'Stale evidence: '+', '.join(stale)
    investigated=Activity.objects.filter(work=work,kind='ACT04',key=digest(['ACT04',observed['sources']]),status='succeeded').exists()
    if not investigated:return ['ACT04'],'Check source evidence'
    if missing:
        task=next((t for t in tasks if t.kind=='factory_information' and t.status=='open'),None)
        return ([],'Waiting for '+', '.join(missing)) if task else (['ACT05'],'Request missing evidence')
    completion=latest.get('completion')
    if completion and Handoff.objects.get(pk=work.request['handoff'],case=work.case).milestone.evidence_id!=completion.pk:
        return ['ACT06'],'Reconcile changed completion evidence with PMO'
    if work.preparation_id:
        try:billing.ensure_current(work.preparation)
        except ValidationError:
            if work.invoice_id and InvoiceIssue.objects.filter(invoice=work.invoice).exists():raise ValidationError('Issued invoice requires its native correction workflow; do not regenerate the obligation')
            return ['ACT08'],'Prepare a genuinely revised draft from changed source rules'
    if not work.preparation_id:
        reconciled=Activity.objects.filter(work=work,kind='ACT06',status='succeeded').exists()
        return (['ACT08'] if reconciled else ['ACT06','ACT08']),'Reconcile PMO completion and prepare a draft'
    if not work.invoice_id:return ['ACT08'],'Prepare invoice draft'
    # Native packet comparison catches superseded target/destination/source before dispatch.
    packet=invoices.review_packet(work.invoice)
    from .factory_routing import task_authority_current
    task=next((t for t in reversed(tasks) if t.kind=='factory_review' and t.context.get('packet')==packet and task_authority_current(work,t,observed['routing'])),None)
    if not task:
        prepared=Attempt.objects.filter(activity__work=work,activity__kind='ACT09',phase='observed',result__packet_hash=digest(packet)).exists()
        return (['ACT10'],'Resolve current ownership and Finance review') if prepared else (['ACT09'],'Prepare exact review packet')
    if task.status=='open':return [],'Awaiting Finance review'
    if task.status!='completed':return [],'Finance returned or rejected this packet'
    invoices.reviewed(work.invoice)
    if InvoiceDelivery.objects.filter(invoice=work.invoice).exists():return ['ACT13'],'Verify output and receipt'
    pending=next((j for j in jobs if j.status in ['pending','unknown','leased','held']),None)
    if pending:
        if pending.status=='held':return [],'Native invoice work needs controlled operator recovery'
        if pending.status=='leased':return [],'Native invoice worker owns the current attempt'
        return ['ACT12' if pending.status=='unknown' else 'ACT11'],'Reconcile receipt' if pending.status=='unknown' else 'Process approved invoice'
    return ['ACT11'],'Queue approved issuance or delivery'

@transaction.atomic
def claim(work_id):
    work=Work.objects.select_for_update(of=('self',),skip_locked=True).select_related('case','actor','invoice').filter(pk=work_id).first()
    if not work or work.status in TERMINAL or work.lease_until and work.lease_until>timezone.now():return None
    access(work.execution_actor,work.case,'factory.execute',work.definition);config,value=profile(work)
    if work.policy_id is None:
        work.policy=config;work.budget_limit=value['max_tokens']
    work.fence+=1;work.lease_until=timezone.now()+timedelta(seconds=value['lease_seconds']);work.save()
    return work.fence

class LeaseLost(ValidationError):
    """A superseded worker has no authority to change coordination state."""

def fence(work,token):
    if work.fence!=token or not work.lease_until or work.lease_until<=timezone.now():raise LeaseLost('LEASE_LOST: stale factory worker')

def task(work,kind,context,resolver=None):
    key=f'factory:{work.pk}:{kind}:{digest(context)}'
    row,created=HumanTask.objects.get_or_create(factory_key=key,defaults={'case':work.case,'kind':kind,'context':context,'required_role':'Finance' if kind=='factory_review' else 'Governance resolver' if kind=='factory_governance' else 'Process User','created_by':work.execution_actor})
    if created:TaskEvent.objects.create(task=row,actor=work.execution_actor,action='factory.opened',data={'work':work.pk,'resolver':resolver})
    return row

def act(work,choice,value,latest,missing,tasks,jobs):
    if work.execution_binding_id is not None:
        previous_revision=work.case.revision
        work.case=lock_case(work.execution_actor,work.case_id,'factory.execute')
        if work.case.revision!=previous_revision:raise ValidationError('STALE_VERSION: workspace changed before the recovered execution command')
        access(work.execution_actor,work.case,'factory.execute',work.definition)
    if work.definition=='rfp-response/v1':
        from .factory_rfp import act as rfp_act
        return rfp_act(work,choice,value,latest,missing,tasks,jobs)
    if work.definition=='finance-accounts/v1':
        from .factory_accounting import act as accounting_act
        return accounting_act(work,choice,value,latest,missing,tasks,jobs)
    if work.definition=='pmo-change/v1':
        from .factory_change import act as change_act
        return change_act(work,choice,value,latest,missing,tasks,jobs)
    if work.definition=='delivery-go-live/v1':
        from .factory_go_live import act as go_live_act
        return go_live_act(work,choice,value,latest,missing,tasks,jobs)
    if work.definition=='delivery-closure/v1':
        from .factory_closure import act as closure_act
        return closure_act(work,choice,value,latest,missing,tasks,jobs)
    if work.definition=='delivery-handover/v1':
        from .factory_handover import act as handover_act
        return handover_act(work,choice,value,latest,missing,tasks,jobs)
    """One closed command gateway. Trusted scope/targets never come from the model."""
    if work.definition=='delivery-archive/v1':
        from .factory_archive import act as archive_act
        return archive_act(work,choice,value,latest,missing,tasks,jobs)
    if work.definition=='delivery-hypercare/v1':
        from .factory_hypercare import act as hypercare_act
        return hypercare_act(work,choice,value,latest,missing,tasks,jobs)
    if work.definition=='delivery-release/v1':
        from .factory_delivery import act as delivery_act
        return delivery_act(work,choice,value,latest,missing,tasks,jobs)
    if work.definition=='commercial/v1':
        from .factory_commercial import act as commercial_act
        return commercial_act(work,choice,value,latest,missing,tasks,jobs)
    if work.definition=='planning/v1':
        from .factory_planning import act as planning_act
        return planning_act(work,choice,value,latest,missing,tasks,jobs)
    kind=choice['activity'];case=work.case
    if kind=='ACT04':
        if value['provider']=='governed_factory_v1':
            from adapters.factory_invoice_preparation import NativeInvoicePreparationAdapter
            return NativeInvoicePreparationAdapter().investigate(work)
        from apps.agents.services import extract_evidence
        evidence=next(iter(latest.values()),None)
        if evidence is None:raise ValidationError('No authorised evidence available')
        run=extract_evidence(work.execution_actor,case.pk,evidence.pk,'P34')
        return {'agent_run':run.pk,'evidence_ids':[evidence.pk]}
    if kind=='ACT05':
        resolver=value['information_resolver_id']
        if resolver is None:raise ValidationError('owner_needed: information resolver is not configured')
        user=get_user_model().objects.get(pk=resolver);access(user,case,'factory.information')
        t=task(work,'factory_information',{'work':work.pk,'missing':missing,'resolver':resolver,'profile':work.policy_id},resolver)
        return {'task':t.pk,'waiting':'input'}
    if kind in ['ACT06','ACT08']:
        h=Handoff.objects.select_related('milestone__evidence').get(case=case,pk=work.request['handoff'])
        if h.payload['evidence_sha256']!=h.milestone.evidence.sha256 or h.payload['evidence_id']!=h.milestone.evidence_id:raise ValidationError('Native PMO handoff/evidence mismatch')
        if latest.get('completion') and latest['completion'].pk!=h.milestone.evidence_id:raise ValidationError('COMPLETION_SOURCE_CONFLICT: current completion evidence differs from the native PMO milestone; source-owned correction is required')
        if kind=='ACT06':return {'handoff':h.pk,'completion_evidence':h.milestone.evidence_id,'matched':True}
        p=billing.prepare(work.execution_actor,case.pk,work.request['coverage'],'completion',None,h.pk,case.revision)
        work.preparation=p
        if p.result['status']!='prepared':
            work.status='blocked';work.finding='; '.join(p.result['findings'])[:300]
            return {'preparation':p.pk,'blocked':True,'finding':work.finding}
        billing.ensure_current(p)
        # Native calculation provides amount/currency/date; model accepts no financial arguments.
        case.refresh_from_db()
        i=invoices.draft(work.execution_actor,case.pk,p.pk,work.request['reference'],date.fromisoformat(p.result['due_date']),case.revision)
        work.invoice=i;return {'preparation':p.pk,'invoice':i.pk,'amount':i.payload['amount']}
    if kind=='ACT09':
        return {'packet_hash':digest(invoices.review_packet(work.invoice))}
    if kind=='ACT10':
        packet=invoices.review_packet(work.invoice)
        if any(v!='ACTIVE' for v in packet['adapter_readiness'].values()):raise ValidationError('configuration_needed: configure the publication destination/rules; independent Finance draft review remains available')
        from .factory_routing import evaluate,task_authority_current
        routing=evaluate(work)
        for old in tasks:
            superseded=(old.kind=='factory_review' and (old.context['packet']!=packet or not task_authority_current(work,old,routing)) or
                old.kind=='factory_governance' and old.context.get('routing')!=routing)
            if old.status=='open' and superseded:
                TaskEvent.objects.create(task=old,actor=work.execution_actor,action='factory.packet_superseded',data={'invoice':work.invoice_id,'replacement_packet_hash':digest(packet)})
                old.status='returned';old.revision+=1;old.save(update_fields=['status','revision'])
        if routing['missing']:
            t=task(work,'factory_governance',{'work':work.pk,'routing':routing},routing['governance_resolver_id'])
            work.status='owner_needed'
            return {'task':t.pk,'finding':'owner_needed: responsibility or current Finance reviewer needs governance review','routing':routing}
        for old in tasks:
            if old.kind=='factory_governance' and old.status=='open':
                TaskEvent.objects.create(task=old,actor=work.execution_actor,action='factory.owners_resolved',data={'routing':routing,'approval_granted':False})
                old.status='completed';old.revision+=1;old.save(update_fields=['status','revision'])
        t=task(work,'factory_review',{'work':work.pk,'packet':packet,'routing_at_creation':routing})
        return {'task':t.pk,'waiting':'approval'}
    if kind=='ACT12':
        original=next((job for job in jobs if uncertain_job(job)),None)
        if original is None:raise ValidationError('Exact uncertain original factory invoice job required')
        return {'dispatch_job':original.pk,'lookup_only':True,'original_invoice':original.invoice_id}
    if kind=='ACT11':
        executor=value['executor_id']
        if executor is None:raise ValidationError('owner_needed: separate invoice executor is not configured')
        user=get_user_model().objects.get(pk=executor);access(user,case,'factory.execute')
        pending=next((j for j in jobs if j.status in ['pending','unknown']),None)
        if pending:return {'dispatch_job':pending.pk,'executor':executor}
        effect='deliver' if InvoiceIssue.objects.filter(invoice=work.invoice).exists() else 'issue'
        job=invoices.reserve(user,case.pk,work.invoice_id,effect,'Finance',case.revision,factory_work_id=work.pk)
        return {'job':job.pk,'effect':effect}
    if kind=='ACT13':
        i=work.invoice;issue=InvoiceIssue.objects.get(invoice=i);delivery=InvoiceDelivery.objects.get(invoice=i)
        if issue.payload!=i.payload or issue.sha256!=i.sha256 or delivery.payload!=invoices.delivery_payload(i) or delivery.sha256!=digest(delivery.payload):raise ValidationError('Receipt postcondition mismatch')
        packet=invoices.review_packet(i)
        if delivery.recipient_id!=packet['recipient_id']:raise ValidationError('Receipt destination differs from exact review packet')
        # A restored valid native approval can bypass a newer, obsolete routing wait.
        # Retire only superseded coordination tasks after exact receipt verification.
        from .factory_routing import evaluate,task_authority_current
        routing=evaluate(work);retired=[]
        for old in HumanTask.objects.select_for_update().filter(case=case,kind='factory_review',status='open',factory_key__startswith=f'factory:{work.pk}:').order_by('pk'):
            if old.context.get('packet')==packet and task_authority_current(work,old,routing):continue
            TaskEvent.objects.create(task=old,actor=work.execution_actor,action='factory.packet_superseded',data={
                'invoice':i.pk,'replacement_packet_hash':digest(packet),'reason':'verified_output',
                'issue_receipt':issue.pk,'delivery_receipt':delivery.pk})
            old.status='returned';old.revision+=1;old.save(update_fields=['status','revision']);retired.append(old.pk)
        work.status='verified';return {'verified':True,'invoice':i.pk,'issue_receipt':issue.pk,'delivery_receipt':delivery.pk,'retired_review_tasks':retired,'cash_received':False,'environment':'synthetic_mock'}
    raise ValidationError('FORBIDDEN: activity has no registered handler in this process envelope')

@transaction.atomic
def record_failure(work_id,token,exc,planning_attempt_id=None):
    work=Work.objects.select_for_update().get(pk=work_id)
    fence(work,token)
    started=Attempt.objects.filter(activity__work=work,phase='started',fence=token).order_by('-pk').first()
    if started and not Attempt.objects.filter(activity=started.activity,number=started.number,phase='failed').exists():
        Attempt.objects.create(activity=started.activity,number=started.number,phase='failed',fence=token,observation=started.observation,result={'reason':str(exc)[:300]})
        Activity.objects.filter(pk=started.activity_id).update(status='failed')
    if planning_attempt_id:
        original=Attempt.objects.get(pk=planning_attempt_id,activity__work=work,phase='started')
        if not Attempt.objects.filter(activity=original.activity,number=original.number,phase__in=['failed','observed']).exists():
            Attempt.objects.create(activity=original.activity,number=original.number,phase='failed',fence=token,observation=original.observation,result={'reason':str(exc)[:300]})
            Activity.objects.filter(pk=original.activity_id).update(status='failed')
    work.status='owner_needed' if 'owner_needed' in str(exc) else 'configuration_needed' if 'configuration_needed' in str(exc) else 'blocked';work.finding=str(exc)[:300]
    if work.cancel_requested:work.status=cancellation_status(work)
    work.lease_until=None;work.revision+=1;work.save()

def cancellation_status(work):
    from apps.agents.factory_coordinator import pending,has_receipt
    planning=pending(work)
    if planning and not has_receipt(planning):return 'waiting_effect'
    if work.definition=='delivery-closure/v1':
        from apps.pmo.models import DeliveryRecord
        if DeliveryRecord.objects.filter(dossier_id=work.request['dossier'],dossier__case=work.case,kind='closure').exists():return 'followup_needed'
    if work.definition in ['pmo-change/v1','rfp-response/v1','commercial/v1','delivery-handover/v1','delivery-go-live/v1','finance-accounts/v1']:
        from apps.documents.models import PublicationJob,PublicationReceipt
        if PublicationJob.objects.filter(publication__factory_work=work,status__in=['pending','unknown','leased','held']).exists():return 'waiting_effect'
        if PublicationReceipt.objects.filter(publication__factory_work=work).exists():return 'followup_needed'
    if any(job.status in ['pending','unknown','leased','held'] for job in invoice_jobs(work)):return 'waiting_effect'
    if work.definition=='pmo-finance/v1' and InvoiceIssue.objects.filter(obligation_key=work.business_key).exists():return 'followup_needed'
    return 'cancelled'

def run_once(work_id,provider=None,adapter=None):
    """One model decision, independently checked command and observed native result."""
    if provider is not None and not Work.objects.select_related('case').get(pk=work_id).case.synthetic:
        raise PermissionDenied('Test provider injection cannot execute operational work')
    from apps.agents import factory_coordinator as coordinator
    current=Work.objects.select_related('case','actor').get(pk=work_id)
    original=coordinator.pending(current)
    if original and not coordinator.has_receipt(original):
        try:coordinator.reconcile(current.execution_actor,work_id,current.revision)
        except (ValidationError,PermissionDenied):return False
        return Work.objects.get(pk=work_id).status=='ready'
    try:token=claim(work_id)
    except (ValidationError,PermissionDenied) as exc:
        with transaction.atomic():
            work=Work.objects.select_for_update().get(pk=work_id)
            if work.revision!=current.revision or work.fence!=current.fence or work.status in TERMINAL or work.cancel_requested or (work.lease_until and work.lease_until>timezone.now()):
                return False
            work.status='configuration_needed' if not work.policy_id else 'blocked';work.finding=str(exc)[:300];work.revision+=1;work.save()
        return False
    if token is None:return False
    planning_attempt_id=None
    try:
        with transaction.atomic():
            work=Work.objects.select_for_update(of=('self',)).select_related('case','actor','invoice').get(pk=work_id);fence(work,token)
            config,value=profile(work)
            if work.cancel_requested:
                work.status=cancellation_status(work);work.finding='Cancellation does not undo issued or delivered records';work.lease_until=None;work.save();return False
            original=coordinator.pending(work)
            if original:planning_attempt_id=original.pk
            observed,latest,missing,stale,tasks,jobs=snapshot(work,value)
            if original and (original.observation['hash']!=observed['hash'] or original.result['coordinator_policy']!=coordinator.configured(work)[0].pk):
                Attempt.objects.create(activity=original.activity,number=original.number,phase='failed',fence=token,
                    observation=original.observation,result={'reason':'Current native context changed after provider receipt recovery'})
                Activity.objects.filter(pk=original.activity_id).update(status='failed')
                work.lease_until=None;work.revision+=1;work.save();return True
            # Native InvoiceReview is the sole business decision, including decisions entered outside this console.
            if work.invoice_id:
                from apps.finance.models import InvoiceReview
                review=InvoiceReview.objects.filter(invoice=work.invoice).order_by('-pk').first()
                from .factory_routing import task_authority_current,native_review_current
                for t in tasks:
                    if t.kind=='factory_review' and t.status=='open' and review and review.publication_packet==t.context['packet'] and task_authority_current(work,t,observed['routing']) and native_review_current(work,review):
                        TaskEvent.objects.create(task=t,actor=review.actor,action='factory.native_review_observed',data={'native_review':review.pk,'verdict':review.verdict})
                        t.status='completed' if review.verdict=='approve' else 'returned';t.revision+=1;t.save(update_fields=['status','revision'])
                observed,latest,missing,stale,tasks,jobs=snapshot(work,value)
            if work.definition=='pmo-finance/v1' and not missing and not stale:
                for t in tasks:
                    if t.kind=='factory_information' and t.status=='open' and all(k in latest for k in t.context['missing']):
                        TaskEvent.objects.create(task=t,actor=work.execution_actor,action='factory.information_verified',data={'evidence_ids':[latest[k].pk for k in t.context['missing']]})
                        t.status='completed';t.revision+=1;t.save(update_fields=['status','revision'])
                observed,latest,missing,stale,tasks,jobs=snapshot(work,value)
            options,finding=eligible(work,value,observed,latest,missing,stale,tasks,jobs)
            if not options:
                work.status='blocked' if stale or any(j.status=='held' for j in jobs) else 'waiting';work.finding=finding;work.lease_until=None;work.save();return False
            if options==['ACT12'] and work.observation_hash==observed['hash']:
                work.status='waiting_effect';work.finding='Provider result is still unknown. Reconcile the original operation when another observation is available.';work.lease_until=None;work.save();return False
            if not latest:raise ValidationError('Missing initial source evidence; no invented AgentRun source')
            if original:
                activity=original.activity;number=original.number;started=original
                context=original.result['native_context'];observed=dict(original.observation,work_revision=work.revision)
            else:
                reserve=value['tokens_per_call']
                if work.budget_used+reserve>min(work.budget_limit,value['max_tokens']) or work.plan_revision>=value['max_steps'] or work.activities.count()+2>value['max_children']:raise ValidationError('BUDGET_EXHAUSTED: aggregate work allowance includes retries and both plan/child records')
                work.budget_used+=reserve;work.plan_revision+=1;work.save()
                key=digest(['plan',observed['hash'],options])
                activity,created=Activity.objects.get_or_create(work=work,key=key,defaults={'kind':'ACT03','plan_revision':work.plan_revision,'status':'running'})
                number=(activity.attempts.aggregate(n=Max('number'))['n'] or 0)+1
                context={'eligible':options,'evidence_ids':[e.pk for e in latest.values()],'missing':missing,'case_revision':work.case.revision}
                request=coordinator.intent(work,context,activity,number) if value['provider']=='governed_factory_v1' else {}
                started=Attempt.objects.create(activity=activity,number=number,phase='started',fence=token,observation=observed,result=request)
                if value['provider']=='governed_factory_v1':planning_attempt_id=started.pk
        if provider is None and value['provider']=='governed_factory_v1':
            from apps.agents.factory_coordinator import choose
            answer,provider_name=choose(work,context,started,resuming=original is not None)
        else:
            answer=(provider or SyntheticFactoryCoordinator()).choose(context);provider_name='synthetic_factory_v1'
        with transaction.atomic():
            work=Work.objects.select_for_update(of=('self',)).select_related('case','actor','invoice').get(pk=work_id);fence(work,token);profile(work)
            if value['provider']=='governed_factory_v1':coordinator.assert_current(work,started.result)
            if work.cancel_requested:raise ValidationError('Cancellation requested before command')
            fresh,latest,missing,stale,tasks,jobs=snapshot(work,value)
            if fresh['hash']!=observed['hash'] or fresh['work_revision']!=observed['work_revision']:raise ValidationError('STALE_VERSION: case/evidence/decision/work changed while planning')
            if not isinstance(answer,dict) or set(answer)!={'activity','citations'} or answer['activity'] not in options:raise PermissionDenied('FORBIDDEN: model choice is outside current capabilities')
            if not isinstance(answer['citations'],list) or not answer['citations'] or any(type(pk) is not int or pk not in context['evidence_ids'] for pk in answer['citations']):raise ValidationError('Unsupported citation')
            process={'pmo-change/v1':'P57','delivery-go-live/v1':'P33','delivery-closure/v1':'P39','delivery-handover/v1':'P37','delivery-archive/v1':'P36',
                'delivery-hypercare/v1':'P35','delivery-release/v1':'P32','planning/v1':'P26'}.get(work.definition)
            if work.definition=='pmo-change/v1':
                process='P57' if answer['activity']=='ACT04' else 'P60' if observed['native']['stage'] in ['go_live','signatures','complete'] else 'P59'
            if work.definition=='finance-accounts/v1':
                from .factory_accounting import process_for_activity
                process=process_for_activity(answer['activity'],observed,value)
            if work.definition=='rfp-response/v1':
                process='P46' if answer['activity']=='ACT04' else 'P47' if not observed['document'] else 'P49' if observed['submission'] else 'P48'
            if process is None:
                process=('P14' if answer['activity']=='ACT04' else 'P06' if answer['activity']=='ACT08' else 'P07') if work.definition=='commercial/v1' else 'F29' if answer['activity']=='ACT08' else 'F30' if answer['activity'] in ['ACT09','ACT10','ACT11','ACT12','ACT13'] else 'P34'
            run=AgentRun.objects.create(case=work.case,actor=work.execution_actor,evidence=latest[next(iter(latest))],provider=provider_name,process_id=process,result=answer)
            child_key=digest(['ACT04',observed['sources'],work.source_head_id]) if answer['activity']=='ACT04' and work.definition in ['planning/v1','commercial/v1'] else digest(['ACT04',observed['sources']]) if answer['activity']=='ACT04' else digest([activity.key,answer['activity']])
            if work.definition=='finance-accounts/v1' and answer['activity']=='ACT04':
                from .factory_accounting import investigation_key as accounting_investigation_key
                child_key=accounting_investigation_key(work,observed)
            if work.definition=='rfp-response/v1' and answer['activity']=='ACT04':
                from .factory_rfp import investigation_key as rfp_investigation_key
                child_key=rfp_investigation_key(work,observed)
            if work.definition in ['pmo-change/v1','delivery-release/v1','delivery-hypercare/v1','delivery-archive/v1','delivery-handover/v1','delivery-closure/v1','delivery-go-live/v1'] and answer['activity']=='ACT04':
                from .factory_delivery import investigation_key
                child_key=investigation_key(work,observed)
            child,created=Activity.objects.get_or_create(work=work,key=child_key,defaults={'parent':activity,'kind':answer['activity'],'plan_revision':work.plan_revision})
            child_number=(child.attempts.aggregate(n=Max('number'))['n'] or 0)+1
            Attempt.objects.create(activity=child,number=child_number,phase='started',fence=token,observation=fresh)
            result=act(work,answer,value,latest,missing,tasks,jobs)
            child.status='succeeded';child.save(update_fields=['status'])
            Attempt.objects.create(activity=child,number=child_number,phase='observed',fence=token,observation=fresh,result=result,agent_run=run)
            activity.status='succeeded';activity.save(update_fields=['status'])
            Attempt.objects.create(activity=activity,number=number,phase='observed',fence=token,observation=fresh,result={'child':child.pk,'activity':answer['activity']},agent_run=run)
            if work.status not in TERMINAL:work.status='waiting' if result.get('waiting') else 'ready'
            work.finding=result.get('finding',result.get('waiting',''));work.observation_hash=fresh['hash'];work.revision+=1;work.save()
        # Native worker owns effect retries. No transaction is held across adapter calls.
        if result.get('dispatch_job'):
            invoice_delivery.run_once(adapter_for(work,adapter),case_id=work.case_id,job_id=result['dispatch_job'],lookup_only=result.get('lookup_only',False))
        if result.get('approval_job'):
            from apps.pmo import approval_routing
            approval_routing.run_once(adapter,case_id=work.case_id,job_id=result['approval_job'])
        if result.get('publication_job'):
            from apps.documents.delivery import run_publication_once
            run_publication_once(adapter,case_id=work.case_id,job_id=result['publication_job'],lookup_only=result.get('publication_lookup_only',False))
        with transaction.atomic():
            work=Work.objects.select_for_update().get(pk=work_id);fence(work,token);work.lease_until=None
            fields=['lease_until']
            if result.get('publication_lookup_only'):
                from apps.documents.models import PublicationJob
                if PublicationJob.objects.filter(pk=result['publication_job'],status='unknown').exists():
                    work.status='waiting_effect';work.finding='The original report result remains uncertain; receipt lookup authorises no new delivery'
                    work.revision+=1;fields+=['status','finding','revision']
            if result.get('lookup_only') and InvoiceJob.objects.filter(pk=result['dispatch_job'],status='unknown').exists():
                work.status=cancellation_status(work) if work.cancel_requested else 'waiting_effect'
                work.finding='The original invoice result remains uncertain; receipt-only lookup authorises no new send or draft'
                settled={key:val for key,val in fresh.items() if key not in ['hash','work_revision']}
                settled['jobs']=invoice_job_observation(invoice_jobs(work));work.observation_hash=digest(settled)
                work.revision+=1;fields+=['status','finding','observation_hash','revision']
            work.save(update_fields=fields)
        return True
    except LeaseLost:
        return False
    except coordinator.PlanningUnknown:
        try:
            with transaction.atomic():
                work=Work.objects.select_for_update().get(pk=work_id);fence(work,token)
                work.status='waiting_effect';work.finding='Original planning response uncertain; check its receipt without sending another request'
                work.lease_until=None;work.revision+=1;work.save()
        except LeaseLost:
            return False
        return False
    except (ValidationError,PermissionDenied,get_user_model().DoesNotExist,TimeoutError,ConnectionError) as exc:
        try:record_failure(work_id,token,exc,planning_attempt_id)
        except LeaseLost:pass
        return False

def run_until_wait(work_id,provider=None,adapter=None):
    # Each call reserves from the same persisted budget. No new allowance per retry.
    for _ in range(100):
        progressed=run_once(work_id,provider,adapter)
        current=Work.objects.get(pk=work_id)
        if current.status in TERMINAL|{'waiting_effect'}:break
        if not progressed:
            # A lost lease is not a human wait. Re-observe under a fresh native
            # claim; another live owner, cancellation and genuine waits stop here.
            if not current.cancel_requested and current.lease_until and current.lease_until<=timezone.now():continue
            break

@transaction.atomic
def claim_task(actor,task_id,expected):
    initial=HumanTask.objects.select_related('case').get(pk=task_id)
    access(actor,initial.case)
    work=Work.objects.select_for_update(of=('self',)).select_related('case','invoice').get(pk=initial.context['work'],case=initial.case)
    t=HumanTask.objects.select_for_update().select_related('case').get(pk=task_id)
    t.case=lock_case(actor,t.case_id,'case.read')
    access(actor,t.case)
    if t.kind not in ['factory_information','factory_review','factory_governance'] or t.status!='open' or t.revision!=expected:raise ValidationError('STALE_VERSION: task changed')
    # Claiming native human work is independent of agent-planning availability.
    profile(work,recovery=True)
    if work.cancel_requested or work.status in ['verified','cancelled','followup_needed']:raise ValidationError('Stopped work cannot accept new task claims')
    if t.kind=='factory_review':
        assert_review_task_current(work,t)
        if actor.pk not in {u.pk for u in route(actor,work)}:raise PermissionDenied('Current Finance eligibility required')
    elif t.kind=='factory_governance':
        from .factory_routing import evaluate
        if evaluate(work)['governance_resolver_id']!=actor.pk:raise PermissionDenied('Current configured governance resolver required')
    else:
        _,value=profile(work,recovery=True)
        if value['information_resolver_id']!=actor.pk:raise PermissionDenied('Current configured information resolver required')
        access(actor,t.case,'factory.information')
    if t.claimed_by_id not in [None,actor.pk]:raise ValidationError('CONFLICT: task already claimed')
    t.claimed_by=actor;t.revision+=1;t.save(update_fields=['claimed_by','revision'])
    TaskEvent.objects.create(task=t,actor=actor,action='factory.claimed',data={'revision':t.revision});return t

@transaction.atomic
def decide(actor,task_id,expected,verdict,evidence_id,reason):
    initial=HumanTask.objects.select_related('case').get(pk=task_id)
    access(actor,initial.case)
    if initial.kind!='factory_review':raise ValidationError('Exact factory review task required')
    work=Work.objects.select_for_update(of=('self',)).select_related('case','invoice').get(pk=initial.context['work'],case=initial.case)
    t=HumanTask.objects.select_for_update().select_related('case').get(pk=task_id)
    access(actor,t.case)
    if t.kind!='factory_review' or t.status!='open' or t.claimed_by_id!=actor.pk or t.revision!=expected:raise ValidationError('STALE_VERSION: current claimed task required')
    if work.cancel_requested or work.status in ['verified','cancelled','followup_needed']:raise ValidationError('Stopped work cannot accept new review decisions')
    t.case=lock_case(actor,t.case_id,'finance.invoice.review')
    assert_review_task_current(work,t)
    profile(work,recovery=True)
    from .factory_routing import delegated_for
    review=invoices.review(actor,t.case_id,work.invoice_id,'Finance',verdict,evidence_id,reason,t.case.revision,delegated=delegated_for(work,actor))
    TaskEvent.objects.create(task=t,actor=actor,action='factory.review',data={'native_review':review.pk,'packet_hash':digest(t.context['packet']),'verdict':verdict})
    t.status='completed' if verdict=='approve' else 'returned';t.revision+=1;t.save(update_fields=['status','revision'])
    work.status='ready' if verdict=='approve' else 'blocked';work.finding='' if verdict=='approve' else 'Finance returned or rejected this exact packet';work.revision+=1;work.save();return review

@transaction.atomic
def manage(actor,work_id,expected,operation):
    work=Work.objects.select_for_update().select_related('case').get(pk=work_id);access(actor,work.case,'factory.manage',work.definition)
    if work.revision!=expected:raise ValidationError('STALE_VERSION: work changed')
    if work.status in ['verified','cancelled','followup_needed']:raise ValidationError('Completed or stopped work requires its native follow-up or correction workflow')
    if operation=='cancel':
        if work.status in ['verified','cancelled']:raise ValidationError('Completed outcomes need an authorised correction; cancellation cannot undo them')
        work.cancel_requested=True
        # Held work cannot be claimed by a worker to acknowledge a stop.
        if work.status in TERMINAL and not (work.lease_until and work.lease_until>timezone.now()):work.status=cancellation_status(work)
        for task in HumanTask.objects.select_for_update().filter(case=work.case,status='open',factory_key__startswith=f'factory:{work.pk}:'):
            TaskEvent.objects.create(task=task,actor=actor,action='factory.wait_cancelled',data={'work':work.pk})
            task.status='returned';task.revision+=1;task.save(update_fields=['status','revision'])
    elif operation=='resume':
        if work.cancel_requested:raise ValidationError('Cancelled intent cannot silently restart')
        if work.lease_until and work.lease_until>timezone.now():raise ValidationError('CONFLICT: the current worker still owns this work')
        profile(work);work.status='ready';work.finding=''
    else:raise ValidationError('Unknown operator action')
    work.revision+=1;work.save();event(actor,work.case,'factory.'+operation,work=work.pk)
    return work

@transaction.atomic
def adopt_profile(actor,work_id,expected,configuration_id,reason):
    work=Work.objects.select_for_update().select_related('case').get(pk=work_id)
    access(actor,work.case,'factory.manage',work.definition);require(actor,work.case,'policy.activate')
    if work.revision!=expected:raise ValidationError('STALE_VERSION: work changed')
    if work.cancel_requested or work.status in ['verified','cancelled','followup_needed']:raise ValidationError('Stopped or verified work requires its native follow-up workflow')
    if work.lease_until and work.lease_until>timezone.now():raise ValidationError('CONFLICT: wait for the current worker to stop before adopting a profile')
    if not isinstance(reason,str) or not reason.strip() or len(reason)>2000:raise ValidationError('Explain the reviewed profile change in at most2000 characters')
    config=active_component(definition(work.definition)['component'],work.case)
    if type(configuration_id) is not int or config.pk!=configuration_id or config.pk==work.policy_id:raise ValidationError('STALE_VERSION: select the exact changed active execution profile')
    previous=work.policy_id;work.policy=config;_,value=profile(work)
    if work.budget_limit==0 and work.budget_used==0:work.budget_limit=value['max_tokens']
    for task in HumanTask.objects.select_for_update().filter(case=work.case,status='open',factory_key__startswith=f'factory:{work.pk}:'):
        TaskEvent.objects.create(task=task,actor=actor,action='factory.profile_superseded',data={'from_profile':previous,'to_profile':config.pk,'reason':reason})
        task.status='returned';task.revision+=1;task.save(update_fields=['status','revision'])
    work.status='ready';work.finding='';work.revision+=1;work.save()
    event(actor,work.case,'factory.profile_adopted',work=work.pk,previous=previous,current=config.pk,reason=reason,
          spent=work.budget_used,lifetime_allowance=work.budget_limit,effective_allowance=min(work.budget_limit,value['max_tokens']))
    return work

@transaction.atomic
def release_task_claim(actor,task_id,expected,reason):
    task=HumanTask.objects.select_for_update().select_related('case').get(pk=task_id)
    access(actor,task.case,'factory.manage')
    if task.kind not in ['factory_information','factory_review','factory_governance','factory_accounting_review'] or task.status!='open' or task.revision!=expected or task.claimed_by_id is None:raise ValidationError('STALE_VERSION: select a currently claimed open factory task')
    work=Work.objects.get(pk=task.context['work'],case=task.case)
    if work.cancel_requested or work.status in ['verified','cancelled','followup_needed']:raise ValidationError('Stopped work cannot assign another decision')
    if not isinstance(reason,str) or not reason.strip() or len(reason)>2000:raise ValidationError('Explain the claim release in at most2000 characters')
    previous=task.claimed_by_id;task.claimed_by=None;task.revision+=1;task.save(update_fields=['claimed_by','revision'])
    TaskEvent.objects.create(task=task,actor=actor,action='factory.claim_released',data={'previous_principal':previous,'reason':reason})
    return task

def advance(actor,work_id,expected,provider=None,adapter=None):
    with transaction.atomic():
        work=Work.objects.select_for_update().select_related('case').get(pk=work_id)
        access(actor,work.case,'factory.execute',work.definition)
        from .factory_execution import require_control
        require_control(actor,work)
        if work.revision!=expected:raise ValidationError('STALE_VERSION: refresh the work item')
        if work.lease_until and work.lease_until>timezone.now():raise ValidationError('CONFLICT: a worker already owns this work')
    run_until_wait(work.pk,provider,adapter)

@transaction.atomic
def provide_information(actor,task_id,expected,case_revision,kind,body,source):
    t=HumanTask.objects.select_for_update().select_related('case').get(pk=task_id)
    access(actor,t.case,'factory.information')
    work=Work.objects.select_related('case').get(pk=t.context['work'],case=t.case);_,value=profile(work,recovery=True)
    if t.kind!='factory_information' or t.status!='open' or t.claimed_by_id!=actor.pk or t.revision!=expected:raise ValidationError('STALE_VERSION: current claimed information task required')
    if actor.pk!=value['information_resolver_id'] or kind not in t.context['missing']:raise PermissionDenied('Exact configured information resolver and requested source required')
    from apps.core.services import add_evidence
    e=add_evidence(actor,t.case_id,kind,body,source,case_revision)
    TaskEvent.objects.create(task=t,actor=actor,action='factory.information_received',data={'evidence':e.pk})
    t.revision+=1;t.save(update_fields=['revision']);return e

def adapter_for(work,adapter=None):
    from django.conf import settings
    selected=adapter or getattr(settings,'FACTORY_ADAPTERS',{}).get(str(work.case_id))
    if selected is not None and not work.case.synthetic:raise PermissionDenied('Mock factory bindings cannot serve operational data')
    return selected

def reconcile(actor,work_id,expected):
    if Work.objects.filter(pk=work_id,definition='rfp-response/v1').exists():
        from .factory_rfp import reconcile as rfp_reconcile
        return rfp_reconcile(actor,work_id,expected)
    if Work.objects.filter(pk=work_id,definition='pmo-change/v1').exists():
        from .factory_change import reconcile as change_reconcile
        return change_reconcile(actor,work_id,expected)
    if Work.objects.filter(pk=work_id,definition='delivery-go-live/v1').exists():
        from .factory_go_live import reconcile as go_live_reconcile
        return go_live_reconcile(actor,work_id,expected)
    if Work.objects.filter(pk=work_id,definition='delivery-handover/v1').exists():
        from .factory_handover import reconcile as handover_reconcile
        return handover_reconcile(actor,work_id,expected)
    if Work.objects.filter(pk=work_id,definition='commercial/v1').exists():
        from .factory_commercial import reconcile as commercial_reconcile
        return commercial_reconcile(actor,work_id,expected)
    if Work.objects.filter(pk=work_id,definition='planning/v1').exists():
        from .factory_planning import reconcile as planning_reconcile
        return planning_reconcile(actor,work_id,expected)
    with transaction.atomic():
        work=Work.objects.select_for_update().select_related('case','actor').get(pk=work_id)
        access(actor,work.case,'factory.execute')
        from .factory_execution import require_control
        require_control(actor,work)
        if work.revision!=expected:raise ValidationError('STALE_VERSION: work changed')
        if work.lease_until and work.lease_until>timezone.now():raise ValidationError('CONFLICT: worker owns this work')
        profile(work,recovery=True)
        job=next((job for job in invoice_jobs(work) if uncertain_job(job)),None)
        if not job:raise ValidationError('No uncertain native invoice operation to reconcile')
        event(actor,work.case,'factory.reconciliation_requested',work=work.pk,job=job.pk)
    invoice_delivery.run_once(adapter_for(work),case_id=work.case_id,job_id=job.pk,lookup_only=True)
    with transaction.atomic():
        work=Work.objects.select_for_update(of=('self',)).select_related('case','actor','invoice').get(pk=work_id)
        job.refresh_from_db();_,value=profile(work,recovery=True)
        work.status=cancellation_status(work) if work.cancel_requested else 'waiting_effect' if job.status=='unknown' else 'ready'
        work.finding='The original provider result remains uncertain' if job.status=='unknown' else 'Cancellation requires native follow-up for any issued invoice' if work.cancel_requested else ''
        observed,*_=snapshot(work,value);work.observation_hash=observed['hash'] if job.status=='unknown' else ''
        work.revision+=1;work.save()
    return work

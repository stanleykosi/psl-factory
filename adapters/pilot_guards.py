"""Closed native read-only guard registry; transitions are never speculatively run."""
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied,ValidationError,ObjectDoesNotExist
from apps.identity.services import require
from apps.pmo import services as pmo
from apps.pmo.models import Baseline,Decision
from apps.policy.registry import dependencies
from apps.policy.services import PolicyHold,resolve
from apps.policy.impact import configuration
from apps.policy.impact import digest
from apps.finance import invoices,corrections
from apps.baas import support_release
from apps.documents.controlled import guard_reserve_publication
from .role_guard import guard as role_guard
from .clock_guard import guard as clock_guard
from .release_evaluations import payment as payment_guard,hypercare as hypercare_guard
from .cash_guards import verify as cash_verify_guard,allocate as cash_allocate_guard


def issue(a,c,invoice_id,role):return invoices.guard_reserve(a,c,invoice_id,'issue',role)
def deliver(a,c,invoice_id,role):return invoices.guard_reserve(a,c,invoice_id,'deliver',role)
def correct(a,c,correction_id,role):return corrections.guard_reserve(a,c,correction_id,'adjust',role)
def correction_deliver(a,c,correction_id,role):return corrections.guard_reserve(a,c,correction_id,'adjust_deliver',role)

REGISTRY={
 'receipt.verify':('finance.cash.verify',cash_verify_guard,['cash_receipt_id','role','cash_verification_evidence_id']),
 'receipt.allocate':('finance.cash.allocate',cash_allocate_guard,['cash_lot_id','issued_invoice_id','cash_amount','operation_key','role','cash_allocation_evidence_id']),
 'payment.assess':('payment.assess',payment_guard,['dossier_id','coverage_id']),
 'hypercare.evaluate':('delivery.manage',hypercare_guard,['dossier_id']),
 'workflow.clock.evaluate':('meeting.read',clock_guard,['action_state_id']),
 'role.decision.evaluate':('case.read',role_guard,['role','decision_action','delegated']),
 'document.publish':('document.publish',guard_reserve_publication,['version_id']),
 'pmo.baseline.prepare':('baseline.prepare',pmo.guard_prepare,['plan_id','cost_id','sow_id']),
 'pmo.decision.record':('decision.record',pmo.guard_decide,['role']),
 'pmo.baseline.sign':('baseline.sign',pmo.guard_sign,['signature_id']),
 'pmo.milestone.complete':('milestone.complete',pmo.guard_complete,['name','evidence_id']),
 'finance.invoice.issue':('finance.invoice.issue',issue,['invoice_id','role']),
 'finance.invoice.deliver':('finance.invoice.deliver',deliver,['invoice_id','role']),
 'finance.invoice.correct':('finance.invoice.correct',correct,['correction_id','role']),
 'finance.invoice.correction_deliver':('finance.invoice.correction_deliver',correction_deliver,['correction_id','role']),
 'baas.response.decide':('support.response.release',support_release.guard_decide,['packet_id','verdict'])}


def pins(value):
    from apps.policy.registry import components
    known=components();found=set();stack=[value];budget=10000
    while stack:
        budget-=1
        if budget<0:raise ValidationError('Native policy pin projection budget exceeded')
        item=stack.pop()
        if isinstance(item,dict):
            for k,v in item.items():
                if k in known:
                    pk=v.get('id') if isinstance(v,dict) else v
                    if type(pk)==int:found.add(pk)
                if isinstance(v,(dict,list)):stack.append(v)
        elif isinstance(item,list):stack.extend(item)
    return found


def check(observer,case,selection):
    from apps.policy.pilot import context
    from apps.identity.models import Grant
    case=context(observer,case.pk)
    if selection['operation'] in ['receipt.verify','receipt.allocate']:
        from .cash_guards import readable
        readable(observer,case)
    elif selection['operation'] in ['payment.assess','hypercare.evaluate']:
        from .release_evaluations import readable
        readable(observer,case,selection['operation'])
    elif selection['operation'].startswith('pmo.'):require(observer,case,'planning.read')
    elif selection['operation'].startswith('finance.'):require(observer,case,'finance.read')
    elif selection['operation']=='workflow.clock.evaluate':
        from .clock_guard import observer as clock_observer
        clock_observer(observer,case,selection['arguments']['action_state_id'])
    elif selection['operation']=='role.decision.evaluate':
        from .role_guard import readable
        readable(observer,case,selection['arguments'])
    elif selection['operation']=='document.publish':
        from .document_guard import readable
        readable(observer,case,selection['arguments']['version_id'])
    else:support_release.access(observer,case)
    if not Grant.objects.filter(case=case,user_id=selection['user_id']).exists():raise ValidationError('Selected case participant is unavailable')
    actor=get_user_model().objects.get(pk=selection['user_id'])
    operation=selection['operation'];action,guard,fields=REGISTRY[operation];args=selection['arguments']
    result={'operation':operation,'user_id':actor.pk,'required_action':action,'state':'HELD','findings':[],
        'policy_pins':[],'implementation':'shared_native_guard/v1','effects_scheduled':False}
    keys=dependencies(operation)
    if operation=='role.decision.evaluate':
        from .role_guard import required
        keys=required(args);result['native_required_components']=keys
        result['authority_scope']='role_and_decision_action_only';result['business_approval']=False
    if operation=='workflow.clock.evaluate':
        from .clock_guard import required
        keys=required(case);result['native_required_components']=keys
        result['authority_scope']='base_due_reassessment_only';result['business_approval']=False
    for key in keys:
        r=resolve(key,case)
        if r.configuration:
            configuration(observer,case.pk,r.configuration.pk)
            result['policy_pins'].append(r.configuration.pk)
    try:
        if not actor.is_active:raise PermissionDenied()
        require(actor,case,'case.read')
        if args['expected_revision']!=case.revision:raise ValidationError('Stale selected revision')
        native=guard(actor,case,**{k:args[k] for k in fields})
        if operation.startswith('finance.') or operation in ['document.publish','role.decision.evaluate','workflow.clock.evaluate','payment.assess','hypercare.evaluate','receipt.verify','receipt.allocate']:
            result['policy_pins']+=sorted(pins(native[1]))
            result['native_context_sha256']=digest(native[1])
            if native[2]:result['existing_reservation']=native[2].pk
        if operation=='workflow.clock.evaluate':
            result['clock_calculation']={key:native[1][key] for key in ['proposed_base_due_at','input_quality','scope','operational_deadline_unchanged','action_grants_evaluated']}
        if operation in ['payment.assess','hypercare.evaluate']:
            result['evaluation']=native[1]['evaluation']
        if operation=='baas.response.decide':
            result['policy_pins']+=sorted(pins(native[1]))
            result['native_context_sha256']=digest(native[1])
        result['state']='READY_AT_OBSERVATION'
        if result.get('existing_reservation'):result['state']='EXISTING_RESERVATION_SOURCE_RECOVERY'
    except PolicyHold as exc:
        result['findings']=[{'code':'policy_hold','component':r.component,'status':r.status} for r in exc.results]
    except PermissionDenied:result['findings']=[{'code':'native_authority_denied'}]
    except (ValidationError,ObjectDoesNotExist):result['findings']=[{'code':'native_source_sequence_or_revision_hold'}]
    b=Baseline.objects.filter(case=case).first() if operation.startswith('pmo.') else None
    result['head']={'case_revision':case.revision,'baseline':[b.pk,b.plan_id,b.costing_id,b.sow_id,b.signed_id] if b else None,
        'decision_heads':[[role,Decision.objects.filter(case=case,role=role).order_by('-pk').values_list('pk',flat=True).first()]
            for role in (['PM','Head of PMO','CEO','PMO Lead'] if operation.startswith('pmo.') else [])]}
    if operation.startswith('finance.'):
        from apps.finance.models import Invoice,InvoiceReview,InvoiceJob,InvoiceIssue
        if 'correction_id' in args:
            correction=corrections.InvoiceCorrection.objects.filter(case=case,pk=args['correction_id']).first()
            invoice=correction.issue.invoice if correction else None
        else:invoice=Invoice.objects.filter(case=case,pk=args['invoice_id']).first()
        if invoice:
            job=InvoiceJob.objects.filter(invoice=invoice).order_by('-pk').first()
            result['head']['invoice']=[invoice.pk,invoice.sha256,InvoiceReview.objects.filter(invoice=invoice).order_by('-pk').values_list('pk',flat=True).first(),InvoiceIssue.objects.filter(invoice=invoice).values_list('pk',flat=True).first()]
            result['head']['job']=[job.pk,job.status,job.fence,job.attempts] if job else None
            result['policy_pins']+=sorted(pins(invoice.preparation.snapshot))
    if operation=='baas.response.decide':
        packet=support_release.packet_for(case,args['packet_id'])
        result['head']['packet']=[packet.pk,packet.sha256,support_release.Decision.objects.filter(packet=packet).order_by('-pk').values_list('pk',flat=True).first(),support_release.Job.objects.filter(packet=packet).order_by('-pk').values_list('pk',flat=True).first()]
        result['policy_pins']+=sorted(pins(packet.snapshot))
    if operation=='document.publish':
        from .document_guard import head
        result['head']['document'],authority=head(observer,case,args['version_id'])
        result['policy_pins']+=sorted(pins(authority))
    if operation=='role.decision.evaluate':
        from .role_guard import head
        result['head']['role_evaluation']=head(observer,case,actor.pk,args)
    if operation in ['receipt.verify','receipt.allocate']:
        from .cash_guards import head
        result['head']['cash']=head(observer,case,args)
    if operation in ['payment.assess','hypercare.evaluate']:
        from .release_evaluations import head
        result['head']['release_evaluation']=head(observer,case,operation,args)
    if operation=='workflow.clock.evaluate':
        from .clock_guard import head
        result['head']['action_clock']=head(observer,case,args['action_state_id'])
    if operation.startswith('pmo.'):
        from apps.pmo.costing import CostingBinding,readable
        binding=CostingBinding.objects.filter(costing_id=args.get('cost_id') or (b.costing_id if b else None)).select_related('run').first()
        if binding:
            readable(observer,case,True);result['policy_pins']+=sorted(pins(binding.run.snapshot))
            result['head']['generated_costing']=[binding.pk,digest(binding.run.snapshot)]
    result['policy_pins']=sorted(set(result['policy_pins']))
    for pk in result['policy_pins']:configuration(observer,case.pk,pk)
    return result

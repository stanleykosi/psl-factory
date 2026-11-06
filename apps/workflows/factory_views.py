from uuid import uuid4
from urllib.parse import urlencode
from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError,PermissionDenied
from django.http import Http404
from django.shortcuts import render,redirect,get_object_or_404
from django.utils import timezone
from django.db.models import Q
from django.views.decorators.http import require_safe
from django.urls import reverse
from django.utils.dateparse import parse_datetime
from apps.identity.models import Grant
from apps.identity.services import visible_cases
from apps.core.models import Evidence,Case,Audit
from apps.core.evidence_access import public_evidence
from apps.core.templatetags.studio_ui import readable
from apps.core.presentation import workspace_name
from apps.core.workbench import granted,active
from apps.finance.models import BillingCoverage,Handoff,InvoiceJob,InvoiceIssue,InvoiceDelivery
from apps.policy.factory_validators import COMPONENT
from apps.policy.operator_drafts import draft_operator_policy
from apps.policy.services import active_component,reference_values,transition,resolve
from apps.policy.models import Configuration
from .models import FactoryWork,HumanTask
from . import factory as d
from .factory_definitions import DEFINITIONS,definition

QUEUES={'needs_me':'Needs my attention','active':'Active work','decisions':'Decisions','exceptions':'Exceptions','unassigned':'Unassigned','verified':'Verified outcomes'}

# Discovery only: native forms and services still validate the exact project/action.
INTAKES=(
    ('finance-forecast/v1','Prepare a reviewed cash forecast','Connect exact scenario sources, native human decisions and aggregate delivery.',('factory.start','finance.read','evidence.add')),
    ('finance-payroll/v1','Coordinate restricted payroll','Carry exact native payroll inputs through HR matching, human review and aggregate recipient receipt.',('factory.start','payroll.read','payroll.private.read','evidence.add')),
    ('pmo-emergency/v1','Coordinate Emergency evidence','Track native preauthorization, actual implementation and reviewed retrospective report receipts.',('factory.start','emergency.read','evidence.add')),
    ('pmo-change/v1','Coordinate a controlled change','Carry exact native change evidence through human decisions, controlled delivery and signed closure.',('factory.start','change.read','evidence.add')),
    ('rfp-response/v1','Prepare an RFP response','Investigate received requirements, prepare the response and track reviewed submission through the actual customer outcome.',('factory.start','rfp.read','evidence.add')),
    ('finance-accounts/v1','Prepare management accounts','Carry a controlled trial balance through Finance review and an aggregate report.',('factory.start','finance.read','finance.calculate','evidence.add')),
    ('planning/v1','Plan a project','Collect the inputs and prepare the department handoff.',('planning.read','factory.start')),
    ('commercial/v1','Prepare a commercial submission','Carry declared costing through the required reviews and submission.',('factory.start','commercial.prepare','costing.read','costing.source.read')),
    ('delivery-release/v1','Prepare for release','Check current delivery evidence and the required decisions.',('factory.start','delivery.read','evidence.add')),
    ('delivery-hypercare/v1','Follow up a release','Record actual release events and assess the configured stability criteria.',('factory.start','delivery.read','evidence.add')),
    ('delivery-go-live/v1','Obtain go-live acceptance','Prepare the client report and record actual PM and Client sign-off.',('factory.start','delivery.read','evidence.add')),
    ('delivery-archive/v1','Archive project records','Check the declared inventory and record the controlled archive index.',('factory.start','delivery.read','evidence.add')),
    ('delivery-handover/v1','Hand over to Support','Prepare the operating instructions and track recipient receipt or gaps.',('factory.start','delivery.read','evidence.add')),
    ('delivery-closure/v1','Close a project','Prepare the PM report, obtain the prescribed decision and verify recorded closure.',('factory.start','delivery.read','evidence.add')),
    ('pmo-finance/v1','Prepare an invoice','Use PMO completion evidence for Finance review, issuance and delivery.',('finance.read','factory.start')),
)

def intake_options(actor):
    available={}
    for _,_,_,actions in INTAKES:
        if actions not in available:available[actions]=granted(actor,list(actions)).filter(kind='project').exists()
    return [{'definition':name,'title':title,'description':description} for name,title,description,actions in INTAKES if available[actions]]


@login_required
@require_safe
def intake(request):
    queue=request.GET.get('queue','needs_me')
    if queue not in QUEUES:queue='needs_me'
    response=render(request,'factory/intake.html',{'options':intake_options(request.user),'queue':queue,'q':request.GET.get('q','').strip()[:120]})
    response['Cache-Control']='no-store';return response

def visible(actor):
    active(actor)
    scope=Q(pk__in=[])
    for name,spec in DEFINITIONS.items():scope|=Q(definition=name,case_id__in=granted(actor,[spec['read'],'factory.read']).values('pk'))
    return FactoryWork.objects.filter(scope).select_related('case','actor','invoice','source_head')

def permitted(actor,work,action):
    try:d.access(actor,work.case,action,work.definition);return True
    except PermissionDenied:return False

def presentation(actor,work):
    from apps.agents.factory_coordinator import decorate
    return decorate(actor,work,_presentation(actor,work))

def _presentation(actor,work):
    if work.definition=='finance-payroll/v1':
        from .factory_payroll_views import presentation as payroll_presentation
        return payroll_presentation(actor,work)
    if work.definition=='rfp-response/v1':
        from .factory_rfp_views import presentation as rfp_presentation
        return rfp_presentation(actor,work)
    if work.definition=='finance-accounts/v1':
        from .factory_accounting_views import presentation as accounting_presentation
        return accounting_presentation(actor,work)
    from .factory_execution import available_actor,can_control
    execution_owner=available_actor(work);controlled=can_control(actor,work)
    try:d.profile(work);profile_available=True
    except (ValidationError,PermissionDenied):profile_available=False
    try:d.profile(work,recovery=True);recovery_available=True
    except (ValidationError,PermissionDenied):recovery_available=False
    tasks=list(HumanTask.objects.filter(case=work.case,factory_key__startswith=f'factory:{work.pk}:').select_related('claimed_by').order_by('pk'))
    jobs=d.invoice_jobs(work)
    state={'ready':'Ready to continue','waiting':'Waiting','blocked':'Action needed','owner_needed':'Owner needed','configuration_needed':'Setup needed','verified':'Verified','cancelled':'Cancelled','waiting_effect':'Awaiting reconciliation','followup_needed':'Stopped; invoice follow-up needed'}.get(work.status,'Check required')
    blocker=work.finding
    if work.finding:
        if work.status=='owner_needed':blocker='No eligible owner is configured for the dependent action.'
        elif work.status=='configuration_needed':blocker='A valid execution profile is needed before agent work can begin.'
        elif 'BUDGET_EXHAUSTED' in work.finding:blocker='This work has used its configured execution allowance.'
        elif any(s in work.finding for s in ['STALE','policy_changed','changed']):blocker='Source information or authority changed. Recheck it before continuing.'
        elif work.status=='blocked':blocker='A required source, rule or permission needs review before continuing.'
        elif work.finding.startswith('Waiting for '):blocker='Waiting for '+readable(work.finding.removeprefix('Waiting for ')).lower()
    if work.cancel_requested and work.status not in ['cancelled','followup_needed']:state='Cancellation requested'
    elif work.lease_until and work.lease_until>timezone.now():state='Processing'
    elif any(d.uncertain_job(j) for j in jobs):state='Effect uncertain';blocker='Reconcile the original operation before any resend.'
    elif any(t.status=='open' and t.kind=='factory_review' for t in tasks):state='Awaiting Finance decision'
    elif any(t.status=='open' and t.kind=='factory_information' for t in tasks):state='Waiting for information'
    elif work.invoice_id and InvoiceDelivery.objects.filter(invoice_id=work.invoice_id).exists() and work.status!='verified':state='Awaiting verification'
    for t in tasks:
        if t.kind=='factory_review':
            recipient=get_user_model().objects.filter(pk=t.context['packet']['recipient_id'],is_active=True,grant__case=work.case,grant__active=True,grant__action='finance.invoice.receive').first()
            t.recipient_name=(recipient.get_full_name() or recipient.username) if recipient else None
            refs=t.context['packet'].get('factory_sources',{}).get('evidence',{})
            exact={r['id']:(r['version'],r['sha256']) for r in refs.values()}
            t.source_records=[e for e in public_evidence(Evidence.objects.filter(case=work.case,pk__in=exact)) if (e.version,e.sha256)==exact[e.pk]]
        t.can_claim=False;t.can_decide=False;t.can_supply=False;t.can_release=False;t.can_recheck=False;t.allowed_verdicts=[];t.authority_label=None
        if t.status!='open' or work.cancel_requested or work.status in ['verified','cancelled','followup_needed']:continue
        t.can_release=t.claimed_by_id is not None and not work.cancel_requested and work.status not in ['verified','cancelled','followup_needed'] and permitted(actor,work,'factory.manage')
        try:
            d.profile(work,recovery=True)
            if t.kind=='factory_review':
                d.assert_review_task_current(work,t)
                eligible=actor.pk in {u.pk for u in d.route(actor,work)}
                if eligible:
                    from .factory_routing import review_capabilities
                    capabilities=review_capabilities(work,actor);t.allowed_verdicts=capabilities['verdicts']
                    t.authority_label='Your review authority: configured invoice delegate' if capabilities['delegated'] else 'Your review authority: assigned Finance reviewer'
            elif t.kind=='factory_governance':
                from .factory_routing import evaluate
                eligible=evaluate(work)['governance_resolver_id']==actor.pk
            else:
                _,value=d.profile(work,recovery=True);eligible=value['information_resolver_id']==actor.pk and permitted(actor,work,'factory.information')
            t.can_claim=eligible and t.claimed_by_id is None
            t.can_decide=eligible and t.claimed_by_id==actor.pk and t.kind=='factory_review'
            t.can_supply=eligible and t.claimed_by_id==actor.pk and t.kind=='factory_information'
            t.can_recheck=eligible and t.claimed_by_id==actor.pk and t.kind=='factory_governance'
        except (ValidationError,PermissionDenied):pass
    next_action='Review the blocker and current evidence'
    if any(t.can_decide for t in tasks):next_action='Review this exact invoice publication packet'
    elif any(t.can_supply for t in tasks):next_action='Provide the requested source information'
    elif any(t.can_claim for t in tasks):next_action='Claim the available task'
    elif work.status=='verified':next_action='Inspect the verified output and receipts'
    elif any(d.uncertain_job(j) for j in jobs):next_action='Reconcile the original operation before considering another action'
    elif work.status=='followup_needed':next_action='Review the issued invoice through its authorised Finance correction workflow'
    elif work.lease_until and work.lease_until>timezone.now():next_action='Wait for the current worker observation'
    elif work.status in ['ready','waiting']:next_action='Continue eligible work or wait for the current owner'
    if not profile_available and work.status not in ['verified','cancelled','followup_needed'] and not any(t.can_claim or t.can_decide or t.can_supply or t.can_recheck for t in tasks):
        state='Execution rules need review';next_action='Review the current execution profile before continuing';blocker='Execution configuration or its bound version is unavailable. Independent source records remain accessible.'
    if next_action=='Continue eligible work or wait for the current owner' and not permitted(actor,work,'factory.execute'):
        next_action='Inspect current records; execution is not permitted for this account'
    if execution_owner is None and next_action=='Continue eligible work or wait for the current owner':
        next_action='Review execution responsibility before continuing'
    open_task=next((t for t in tasks if t.status=='open'),None)
    owner=(open_task.claimed_by.get_full_name() or open_task.claimed_by.username) if open_task and open_task.claimed_by else 'Unassigned'
    if not open_task and work.status not in ['owner_needed','configuration_needed'] and execution_owner is not None:
        owner=execution_owner.get_full_name() or execution_owner.username
    if work.status in ['verified','cancelled']:owner='No action required'
    adoption=None
    if not work.cancel_requested and work.status not in ['verified','cancelled','followup_needed'] and permitted(actor,work,'factory.manage') and permitted(actor,work,'policy.activate') and not (work.lease_until and work.lease_until>timezone.now()):
        try:
            config=active_component(definition(work.definition)['component'],work.case);value=reference_values(config)[0]
            if work.policy_id is not None and config.pk!=work.policy_id and value['enabled']:
                adoption={'id':config.pk,'revision':config.revision,'value':value,'effective_allowance':min(work.budget_limit,value['max_tokens']) if work.budget_limit else value['max_tokens']}
        except ValidationError:pass
    last_observation=work.activities.filter(attempts__phase='started').order_by('-attempts__created_at').values_list('attempts__created_at',flat=True).first()
    row={'work':work,'tasks':tasks,'jobs':jobs,'state':state,'blocker':blocker,'next_action':next_action,'owner':owner,'adoption':adoption,'evidence_as_of':last_observation,'review_needs_update':False,'review_ready':False,
        'can_advance':profile_available and execution_owner is not None and controlled and not work.cancel_requested and not (work.lease_until and work.lease_until>timezone.now()) and work.status not in d.TERMINAL|{'waiting_effect'},
        'can_reconcile':recovery_available and not (work.lease_until and work.lease_until>timezone.now()) and controlled and any(d.uncertain_job(j) for j in jobs),
        'can_manage':permitted(actor,work,'factory.manage'),'can_cancel':permitted(actor,work,'factory.manage') and work.status not in ['verified','cancelled'] and not work.cancel_requested,'needs_me':any(t.can_claim or t.can_decide or t.can_supply for t in tasks) or execution_owner is not None and execution_owner.pk==actor.pk and work.status=='ready'}
    if work.definition=='pmo-finance/v1' and work.invoice_id:
        from .factory_routing import evaluate,task_authority_current
        row['routing']=evaluate(work)
        row['reviewer_findings']=sorted({r['summary'] for r in row['routing'].get('reviewer_findings',[])})
        row['responsibility_names']=responsibility_names(work.case,row['routing']['binding']['value'])
        reviews=[t for t in tasks if t.kind=='factory_review' and t.status in ['open','completed']]
        if (reviews and profile_available and work.status in ['ready','waiting'] and not work.cancel_requested
                and not (work.lease_until and work.lease_until>timezone.now())
                and not any(j.status in ['pending','unknown','leased','held'] for j in jobs)
                and not any(t.status=='open' and t.kind!='factory_review' for t in tasks)):
            try:packet=d.invoices.review_packet(work.invoice)
            except (ValidationError,PermissionDenied):packet=None
            current=[t for t in reviews if packet is not None and t.context.get('packet')==packet and task_authority_current(work,t,row['routing'])]
            if not current:
                row.update(review_needs_update=True,state='Review needs updating',owner='Unassigned',
                    blocker='The earlier review cannot be verified against current invoice information, Finance rules or assignments.',
                    next_action='Update the Finance review before continuing' if row['can_advance'] else 'Inspect the changed review rules; routing cannot be updated by this account',
                    advance_label='Update Finance review',needs_me=row['can_advance'])
            elif any(t.status=='completed' for t in current) and any(t.status=='open' and t not in current for t in reviews):
                from apps.policy.factory_routing_validators import principal
                try:
                    d.invoices.reviewed(work.invoice)
                    executor=principal(work.case,d.profile(work)[1]['executor_id'])
                except (ValidationError,PermissionDenied):pass
                else:
                    row.update(review_ready=True,state='Finance approval available',
                        owner=(executor.get_full_name() or executor.username) if executor else 'Unassigned',
                        blocker='The earlier exact approval is current. The newer review no longer applies and will remain in the history.',
                        next_action='Continue approved invoice work' if row['can_advance'] else 'Inspect the current approval; execution is not permitted for this account',
                        advance_label='Continue approved invoice work',needs_me=row['can_advance'])
        if work.status=='owner_needed' and 'responsibility' in work.finding:
            resolver=get_user_model().objects.filter(pk=row['routing']['governance_resolver_id']).first()
            row.update(state='Owner needed',owner=(resolver.get_full_name() or resolver.username) if resolver else 'Unassigned',
                next_action='Review responsibility assignments and recheck the current Finance route',
                needs_me=any(t.can_claim or t.can_recheck for t in tasks),department_wait=True)
    if work.definition=='planning/v1':
        from .factory_planning import operator_projection
        row.update(operator_projection(actor,work))
    if work.definition=='commercial/v1':
        from .factory_commercial import projection
        row['commercial']=projection(actor,work)
        row['jobs']=row['commercial']['jobs']
        if any(j.status=='unknown' for j in row['jobs']):
            row.update(state='Client delivery uncertain',next_action='Reconcile the original client document delivery',can_advance=False,
                can_reconcile=controlled and not (work.lease_until and work.lease_until>timezone.now()))
        if work.status=='followup_needed':row.update(state='Stopped; client document follow-up needed',next_action='Review the delivered client version through its native follow-up controls')
        if row['commercial'].get('readiness_changed'):
            row.update(state='Prior commercial submission needs review',next_action='Review changed source or authority before resuming',readiness_changed=True,
                can_reassess=permitted(actor,work,'factory.manage'),needs_me=permitted(actor,work,'factory.manage'))
        if row['commercial']['decision_roles'] or row['commercial']['can_document_review'] or row['commercial']['owner_reviews']:
            row.update(needs_me=True,next_action='Review the exact native commercial or costing subject',owner=actor.get_full_name() or actor.username,department_wait=True)
    if work.definition=='delivery-release/v1':
        from .factory_delivery import projection
        row['delivery']=projection(actor,work)
        if row['delivery']['planning_owner_names']:row['owner']=', '.join(row['delivery']['planning_owner_names'][:3])
        if work.status=='waiting':
            prerequisite=next((c for c in row['delivery']['checks'].values() if c['status']=='held'),None)
            if prerequisite:row.update(blocker=prerequisite['summary'],next_action=prerequisite['summary'])
        if work.status=='verified':row.update(next_action='Inspect the release readiness record and source approvals')
        if row['delivery']['can_decide']:row.update(needs_me=True,next_action='Review this exact Planning exit',owner=actor.get_full_name() or actor.username,department_wait=True)
        if row['delivery']['readiness_changed']:
            row.update(state='Prior release evidence needs review',next_action='Review changed native delivery sources or authority',readiness_changed=True,
                can_reassess=permitted(actor,work,'factory.manage'),needs_me=permitted(actor,work,'factory.manage'))
        if work.status=='followup_needed':row.update(state='Delivery follow-up needed',next_action='Review native delivery records')
    if work.definition=='delivery-hypercare/v1':
        from .factory_hypercare import projection
        row['hypercare']=projection(actor,work)
        if work.status=='waiting':
            prerequisite=next((c for c in row['hypercare']['checks'].values() if c['status']=='held'),None)
            if prerequisite:row.update(blocker=prerequisite['summary'],next_action=prerequisite['summary'])
            elif row['hypercare']['assessment'] and row['hypercare']['assessment'].snapshot['qualified'] is not True:
                row.update(blocker='Current stability observations remain unknown or fail the configured criteria.',next_action='Obtain corrected source observations before qualification')
        if work.status=='configuration_needed' and profile_available:
            if resolve('D11.hypercare_criteria_ref',work.case).status=='ACTIVE':
                row.update(state='Prerequisites need recheck',blocker='A current stability rule is available. Recheck the held work and any remaining source requirements.',next_action='Recheck corrected prerequisites')
            else:row.update(state='Stability rules need review',blocker='A current stability period, confirmation and metric rule is required.',next_action='Review the current stability criteria')
        if work.status=='verified':row.update(next_action='Inspect the qualified assessment and its source observations')
        if row['hypercare']['can_record_release'] or row['hypercare']['can_accept_go_live']:
            row.update(needs_me=True,owner=actor.get_full_name() or actor.username,
                next_action='Record the actual observed release' if row['hypercare']['can_record_release'] else 'Review the exact go-live acceptance evidence',
                department_wait=row['hypercare']['can_accept_go_live'])
        if row['hypercare']['readiness_changed']:
            row.update(state='Prior stability qualification needs review',next_action='Review changed observations or source authority',readiness_changed=True,
                can_reassess=permitted(actor,work,'factory.manage'),needs_me=permitted(actor,work,'factory.manage'))
    if work.definition in ['delivery-release/v1','delivery-hypercare/v1']:
        panel=row['delivery'] if work.definition=='delivery-release/v1' else row['hypercare']
        row['can_advance']&=panel['intake_current' if work.definition=='delivery-release/v1' else 'intake_valid']
        row['source_instruction_needed']=not panel['intake_authority_current']
        if row['source_instruction_needed']:
            row['can_advance']=False;row['state']='Project instruction needs review'
            if not (work.definition=='delivery-hypercare/v1' and (panel['can_record_release'] or panel['can_accept_go_live'])):
                row['next_action']='A current source owner must review the project instruction'
        if panel['can_reaffirm']:
            row.update(state='Project instruction needs review',next_action='Review the current project instruction and source responsibility',
                owner=actor.get_full_name() or actor.username,needs_me=True,can_advance=False)
    if work.definition=='delivery-archive/v1':
        from .factory_archive import projection
        row['archive']=projection(actor,work)
        row['can_advance']=row['can_advance'] and row['archive']['intake_current']
        if work.status not in ['verified','cancelled']:
            prerequisite=next((c for c in row['archive']['checks'].values() if c['status']=='held'),None)
            if prerequisite:row.update(blocker=prerequisite['summary'],next_action=prerequisite['summary'])
            if not profile_available:row.update(state='Execution setup needed',blocker='Set the execution limits. A permitted archive operator is needed when creating a new index.',next_action='Review archive execution settings')
        if row['archive']['can_correct'] and work.status not in ['verified','cancelled']:row['needs_me']=True
        if row['archive']['can_restart']:
            row.update(owner=actor.get_full_name() or actor.username,next_action='Review a fresh instruction before resuming stopped archive work')
        elif row['archive']['can_settle']:
            row.update(owner=actor.get_full_name() or actor.username,next_action='Complete the recorded stop before issuing a new instruction')
        if work.status=='verified':row.update(next_action='Inspect the current archive index and its exact evidence references')
        if row['archive']['readiness_changed']:
            row.update(state='Prior archive index needs review',next_action='Review changed inventory, storage rules or authority',readiness_changed=True,
                can_reassess=permitted(actor,work,'factory.manage'),needs_me=permitted(actor,work,'factory.manage'))
    if work.definition=='delivery-handover/v1':
        from .factory_handover import projection
        row['handover']=projection(actor,work);row['jobs']=row['handover']['jobs']
        pending_ack=[x for x in row['handover']['receipts'] if not x['ack'] or x['ack'].data['status']!='received']
        own_ack=any(x['can_ack'] for x in pending_ack)
        if row['handover']['finding'] and work.status in ['ready','waiting']:
            row.update(blocker=row['handover']['finding'],next_action=row['handover']['finding'])
            if work.status=='waiting':row['can_advance']=False
        if work.status=='waiting' and pending_ack:
            names=row['handover']['pending_owner_names']
            row.update(owner=', '.join(names) if names else 'Unassigned',next_action='Record actual receipt or resolve the handover gaps' if names else 'Review the current Support and Operations recipient authority',can_advance=False)
        if row['handover']['review_pending']:
            names=row['handover']['review_owner_names']
            row.update(owner=', '.join(names) if names else 'Unassigned',next_action='Review this exact controlled handover document' if names else 'Configure current controlled-document review authority',can_advance=False)
        if row['handover']['can_review']:
            row.update(needs_me=True,owner=actor.get_full_name() or actor.username,next_action='Review this exact controlled handover document',department_wait=True)
        if own_ack:row.update(needs_me=True,owner=actor.get_full_name() or actor.username,department_wait=True)
        if not row['handover']['publication_current']:
            row.update(owner=(actor.get_full_name() or actor.username) if row['handover']['can_correct'] else 'Unassigned',
                next_action='Review changed document, recipient or publication policy before a fresh package',needs_me=row['handover']['can_correct'])
        elif row['handover']['can_correct'] and (row['handover']['finding'] or pending_ack and not row['handover']['pending_owner_names']):row['needs_me']=True
        if work.status=='owner_needed':row.update(blocker='Current handover execution authority needs review.',next_action='Review the configured handover publisher and its current project permissions')
        if work.status=='configuration_needed':row.update(blocker='Execution settings need review before the agent can continue.',next_action='Review handover operating limits')
        if any(j.status=='held' for j in row['jobs']):row.update(state='Handover delivery needs review',next_action='Review the held original delivery and its permitted recovery actions',can_advance=False)
        if any(j.status=='unknown' or j.status=='leased' and j.lease_until and j.lease_until<=timezone.now() for j in row['jobs']):
            row.update(state='Handover delivery uncertain',next_action='Reconcile the original internal delivery',can_advance=False,
                can_reconcile=controlled and not (work.lease_until and work.lease_until>timezone.now()))
        if work.status=='followup_needed':row.update(state='Stopped; delivered handover needs follow-up',next_action='Review the original delivered package and actual recipient records')
        if work.status=='verified':row.update(next_action='Inspect the current handover package and actual recipient acknowledgements')
        if row['handover']['readiness_changed']:
            row.update(state='Prior handover needs review',next_action='Review changed documents, audience, authority or recipient gaps',readiness_changed=True,
                can_reassess=row['handover']['can_correct'] or own_ack,needs_me=row['handover']['can_correct'] or own_ack)
    if work.definition=='delivery-closure/v1':
        from .factory_closure import projection
        row['closure']=projection(actor,work);panel=row['closure'];row['can_advance']&=bool(panel['next_options']) and panel['intake_current']
        row['next_action']=panel['next_action'];row['readiness_changed']=panel['readiness_changed']
        row['blocker']=panel['finding'] or (panel['next_action'] if not panel['next_options'] and work.status not in ['verified','cancelled','followup_needed'] else '')
        if panel['pending_review']:
            row.update(state='Awaiting document review',owner=', '.join(panel['reviewer_names']) or 'Unassigned',department_wait=panel['can_review'],needs_me=panel['can_review'])
        elif panel['closure'] and work.status!='verified':row.update(state='Closure recorded; verification pending',next_action='Verify the exact recorded closure and prescribed decision')
        elif panel['document'] and panel['report']['ready_to_prepare'] and not (panel['decision'] and panel['decision'].data['verdict']=='approve'):
            row.update(state='Awaiting closure decision',owner=', '.join(panel['decision_names']) or 'Unassigned',department_wait=bool(panel['verdicts']),needs_me=bool(panel['verdicts']))
        if work.status=='verified':row.update(next_action='Inspect the recorded closure, exact report and prescribed decision')
        if panel['readiness_changed']:row.update(state='Recorded closure needs review',next_action='Review changed native source or authority; recorded closure remains in history',can_advance=False)
        if work.status=='followup_needed':row.update(state='Stopped; recorded closure needs follow-up',next_action='Inspect the existing native closure; stopping work cannot reopen it')
        row['can_reassess']=False
    if work.definition=='finance-forecast/v1':
        from .factory_forecast import projection
        row['forecast']=projection(actor,work);panel=row['forecast'];row['jobs']=panel['jobs']
        row.update(next_action=panel['next_action'],blocker=panel['finding'],readiness_changed=panel['readiness_changed'])
        row['can_advance']=row['can_advance'] and bool(panel['next_options']) and panel['intake_current']
        row['can_reconcile']=recovery_available and controlled and not (work.lease_until and work.lease_until>timezone.now()) and any(d.uncertain_job(j) for j in panel['jobs'])
        if panel['review_roles']:row.update(needs_me=True,department_wait=True,owner=actor.get_full_name() or actor.username,state='Awaiting native forecast review')
        if panel['readiness_changed']:row['state']='Recorded forecast evidence changed'
    if work.definition=='pmo-emergency/v1':
        from .factory_emergency import projection
        row['emergency']=projection(actor,work);panel=row['emergency'];row['jobs']=panel['jobs']
        row.update(next_action=panel['next_action'],blocker=panel['finding'],readiness_changed=panel['readiness_changed'])
        row['can_advance']=row['can_advance'] and bool(panel['next_options'])
        row['can_reconcile']=recovery_available and controlled and not (work.lease_until and work.lease_until>timezone.now()) and any(d.uncertain_job(j) for j in panel['jobs'])
        if panel['readiness_changed']:row['state']='Retrospective evidence needs review'
    if work.definition=='pmo-change/v1':
        from .factory_change import projection
        row['change']=projection(actor,work);panel=row['change'];row['jobs']=panel['jobs']
        row.update(next_action=panel['next_action'],blocker=panel['finding'],readiness_changed=panel['readiness_changed'])
        row['can_advance']=row['can_advance'] and bool(panel['next_options'])
        row['can_reconcile']=recovery_available and controlled and not (work.lease_until and work.lease_until>timezone.now()) and any(d.uncertain_job(j) for j in panel['jobs'])
        if panel['readiness_changed']:row['state']='Verified change evidence changed'
    if work.definition=='delivery-go-live/v1':
        from .factory_go_live import projection
        row['go_live']=projection(actor,work);panel=row['go_live'];row['jobs']=panel['jobs']
        row['can_advance']&=bool(panel['next_options']) and panel['intake_current']
        row.update(next_action=panel['next_action'],readiness_changed=panel['readiness_changed'],
            blocker=panel['finding'] or (panel['next_action'] if not panel['next_options'] and work.status not in ['verified','cancelled','followup_needed'] else ''))
        if panel['pending_review'] and not work.cancel_requested:
            row.update(state='Awaiting document review',owner=', '.join(panel['review_names']) or 'Unassigned',
                needs_me=bool(panel['review_verdicts']),department_wait=bool(panel['review_verdicts']))
        elif panel['delivery_complete'] and not panel['acceptance'] and not work.cancel_requested:
            row.update(state='Awaiting PM and Client sign-off',owner=', '.join(panel['pm_names']) or 'Unassigned',
                needs_me=panel['can_accept'],department_wait=panel['can_accept'])
        elif panel['publication'] and not panel['acceptance'] and not work.cancel_requested:
            row.update(state='Awaiting client document delivery',needs_me=False,department_wait=False)
        if any(j.status in ['unknown','leased'] and (j.status=='unknown' or j.lease_until and j.lease_until<=timezone.now()) for j in panel['jobs']):
            row.update(state='Document delivery uncertain',next_action='Reconcile the original go-live delivery before further work',can_advance=False,
                can_reconcile=controlled and not (work.lease_until and work.lease_until>timezone.now()))
        if any(j.status=='held' for j in panel['jobs']):row.update(state='Document delivery needs review',next_action='Review the original delivery and current permitted recovery actions',can_advance=False)
        if work.status=='verified':row.update(next_action='Inspect actual sign-off and continue into release stability follow-up')
        if panel['readiness_changed']:row.update(state='Recorded acceptance needs review',next_action='Review changed source, audience or authority; earlier acceptance remains in history',can_advance=False)
        if work.status=='followup_needed':row.update(state='Stopped; delivered document needs follow-up',next_action='Inspect original delivery and actual sign-off; stopping cannot undo them',can_advance=False)
        row['can_reassess']=False
    if row.get('readiness_changed'):
        row['owner']=(actor.get_full_name() or actor.username) if row.get('can_reassess') else 'Unassigned'
    # Retained native reviews and stale evidence do not reactivate stopped agent intent.
    if work.status=='cancelled':
        row.update(state='Cancelled',owner='No action required',blocker='',
            next_action='Inspect the stopped work and its retained history',needs_me=False,department_wait=False,
            can_advance=False,can_reconcile=False,can_cancel=False,can_reassess=False,adoption=None)
        for task in tasks:task.can_claim=task.can_decide=task.can_supply=task.can_release=task.can_recheck=False
        if row.get('archive',{}).get('can_restart'):
            row.update(owner=actor.get_full_name() or actor.username,
                next_action='Review a fresh instruction before resuming stopped archive work',needs_me=True)
    elif work.status=='followup_needed':
        row.update(can_advance=False,can_cancel=False,can_reassess=False,adoption=None)
        if work.definition=='pmo-finance/v1':
            row.update(state='Stopped; invoice follow-up needed',
                next_action='Review the issued invoice through its authorised Finance correction workflow')
    if execution_owner is None and row['state']=='Ready to continue':
        row['state']='Worker authority needs review'
    row['execution_owner_needed']=execution_owner is None and not work.cancel_requested and work.status not in ['verified','cancelled','followup_needed']
    return row

@login_required
def index(request):
    # Retain legacy filtered workspace links while making the root a work-first surface.
    if any(k in request.GET for k in ['kind','area','tenant']):
        from apps.core.workbench_views import home
        return home(request)
    queue=request.GET.get('queue','needs_me');q=request.GET.get('q','').strip()[:120]
    if queue not in QUEUES:queue='needs_me'
    query=visible(request.user)
    if q:query=query.filter(Q(request__reference__icontains=q)|Q(case__title__icontains=q)|Q(key__icontains=q))
    if queue=='verified':query=query.filter(status='verified')
    elif queue=='exceptions':query=query.filter(status__in=['blocked','owner_needed','configuration_needed','waiting_effect','followup_needed','ready','waiting'])|query.filter(invoice__invoicejob__status='unknown')|query.filter(definition__in=['finance-forecast/v1','finance-payroll/v1','pmo-emergency/v1','pmo-change/v1','rfp-response/v1','planning/v1','commercial/v1','delivery-release/v1','delivery-hypercare/v1','delivery-archive/v1','delivery-handover/v1','delivery-closure/v1','delivery-go-live/v1','finance-accounts/v1'],status='verified')
    elif queue=='needs_me':query=query.exclude(status='cancelled').exclude(status='verified',definition='pmo-finance/v1')
    else:query=query.exclude(status__in=['verified','cancelled'])
    query=query.distinct().order_by('-updated_at','-pk');items=[]
    # Explicit bounded evaluated coverage: no global totals from a first page.
    for work in query[:101]:
        row=presentation(request.user,work)
        if queue=='verified' and row.get('readiness_changed'):continue
        if queue=='exceptions' and work.status=='verified' and not row.get('readiness_changed'):continue
        if queue=='exceptions' and work.status in ['ready','waiting'] and not (row.get('review_needs_update') or row.get('adoption') or row.get('coordination_needed') or row.get('execution_owner_needed') or row.get('source_instruction_needed') or row.get('source_followup_needed') or row.get('operation_followup_needed') or row.get('outcome_selection_needed') or row.get('held_publication_needs_operator') or any(d.uncertain_job(j) for j in row['jobs']) or row['state']=='Execution rules need review'):continue
        if queue=='needs_me' and not row['needs_me']:continue
        if queue=='decisions' and (row.get('review_needs_update') or row.get('review_ready') or not (row.get('department_wait') or any(t.status=='open' and t.kind=='factory_review' for t in row['tasks']))):continue
        if queue=='unassigned' and row['owner']!='Unassigned':continue
        items.append(row)
    evaluated=query.count()
    response=render(request,'factory/queue.html',{'rows':items[:50],
        'intake_available':bool(intake_options(request.user)),'queue':queue,'queues':QUEUES,'q':q,'as_of':timezone.now(),
        'evaluated':min(evaluated,101),'limited':len(items)>50 or evaluated>101,'sample_mode':bool(items) and all(r['work'].case.synthetic for r in items)})
    response['Cache-Control']='no-store';return response

class StartForm(forms.Form):
    key=forms.CharField(widget=forms.HiddenInput,max_length=100)
    case=forms.ModelChoiceField(queryset=Case.objects.none())
    coverage=forms.ModelChoiceField(queryset=BillingCoverage.objects.none(),label='Contract and service')
    handoff=forms.ModelChoiceField(queryset=Handoff.objects.none(),label='PMO completion received by Finance')
    reference=forms.CharField(max_length=100,label='Invoice reference')
    revision=forms.IntegerField(min_value=1,widget=forms.HiddenInput)
    def __init__(self,actor,data=None,case_id=None):
        super().__init__(data=data,initial={'key':uuid4().hex})
        cases=granted(actor,['finance.read','factory.start']).filter(kind='project');self.fields['case'].queryset=cases
        self.fields['case'].label_from_instance=workspace_name
        selected=cases.filter(pk=case_id).first() if case_id else None
        if selected:
            self.fields['case'].initial=selected;self.fields['revision'].initial=selected.revision
            self.fields['coverage'].queryset=BillingCoverage.objects.filter(case=selected)
            self.fields['handoff'].queryset=Handoff.objects.filter(case=selected).select_related('milestone')
            self.fields['handoff'].label_from_instance=lambda h:h.milestone.name

@login_required
def create(request):
    envelope=request.POST.get('definition',request.GET.get('definition','pmo-finance/v1'))
    if envelope not in DEFINITIONS:raise Http404
    if envelope=='rfp-response/v1':
        from .factory_rfp_views import create as create_rfp
        return create_rfp(request)
    if envelope=='finance-accounts/v1':
        from .factory_accounting_views import create as create_accounting
        return create_accounting(request)
    if envelope=='finance-forecast/v1':
        from .factory_forecast_views import create as create_forecast
        return create_forecast(request)
    if envelope=='finance-payroll/v1':
        from .factory_payroll_views import create as create_payroll
        return create_payroll(request)
    if envelope=='pmo-emergency/v1':
        from .factory_emergency_views import create as create_emergency
        return create_emergency(request)
    if envelope=='pmo-change/v1':
        from .factory_change_views import create as create_change
        return create_change(request)
    if envelope=='delivery-go-live/v1':
        from .factory_go_live_views import create as create_go_live
        return create_go_live(request)
    if envelope=='delivery-closure/v1':
        from .factory_closure_views import create as create_closure
        return create_closure(request)
    if envelope=='delivery-handover/v1':
        from .factory_handover_views import create as create_handover
        return create_handover(request)
    if envelope=='delivery-archive/v1':
        from .factory_archive_views import create as create_archive
        return create_archive(request)
    if envelope=='delivery-hypercare/v1':return create_delivery(request,envelope)
    if envelope=='delivery-release/v1':return create_delivery(request)
    if envelope=='commercial/v1':return create_commercial(request)
    if envelope=='planning/v1':return create_planning(request)
    case_id=request.POST.get('case') if request.method=='POST' else request.GET.get('case')
    try:form=StartForm(request.user,request.POST if request.method=='POST' else None,case_id)
    except (ValueError,ValidationError):
        form=StartForm(request.user,data={});form.is_valid();form.add_error(None,'Choose an available workspace.')
    if request.method=='POST' and form.is_valid():
        v=form.cleaned_data
        try:
            work=d.start(request.user,v['case'].pk,v['key'],v['coverage'].pk,v['handoff'].pk,v['reference'],v['revision'])
            return redirect('factory_detail',work_id=work.pk)
        except ValidationError as exc:form.add_error(None,str(exc))
    return render(request,'factory/start.html',{'form':form,'available_cases':granted(request.user,['finance.read','factory.start']).filter(kind='project')})

@login_required
def detail(request,work_id):
    work=get_object_or_404(visible(request.user),pk=work_id)
    if work.definition=='rfp-response/v1':
        from .factory_rfp_views import detail as rfp_detail
        return rfp_detail(request,work)
    if work.definition=='finance-accounts/v1':
        from .factory_accounting_views import detail as accounting_detail
        return accounting_detail(request,work)
    if work.definition=='finance-forecast/v1':
        from .factory_forecast_views import detail as forecast_detail
        return forecast_detail(request,work)
    if work.definition=='finance-payroll/v1':
        from .factory_payroll_views import detail as payroll_detail
        return payroll_detail(request,work)
    if work.definition=='pmo-emergency/v1':
        from .factory_emergency_views import detail as emergency_detail
        return emergency_detail(request,work)
    if work.definition=='pmo-change/v1':
        from .factory_change_views import detail as change_detail
        return change_detail(request,work)
    if work.definition=='delivery-go-live/v1':
        from .factory_go_live_views import detail as go_live_detail
        return go_live_detail(request,work)
    if work.definition=='delivery-closure/v1':
        from .factory_closure_views import detail as closure_detail
        return closure_detail(request,work)
    if work.definition=='delivery-handover/v1':
        from .factory_handover_views import detail as handover_detail
        return handover_detail(request,work)
    if work.definition=='delivery-archive/v1':
        from .factory_archive_views import detail as archive_detail
        return archive_detail(request,work)
    return_queue=request.GET.get('queue','needs_me');q=request.GET.get('q','')[:120]
    if return_queue not in QUEUES:return_queue='needs_me'
    if request.method=='POST':
        try:
            operation=request.POST.get('action');revision=int(request.POST.get('revision','0'))
            if operation=='observe_department' and work.definition!='planning/v1' or operation=='reassess' and work.definition not in ['planning/v1','commercial/v1','delivery-release/v1','delivery-hypercare/v1']:raise ValidationError('Choose an action available for this work')
            if operation=='advance':d.advance(request.user,work.pk,revision)
            elif operation=='reassess':
                if work.definition=='delivery-hypercare/v1':
                    from .factory_hypercare import reassess
                elif work.definition=='delivery-release/v1':
                    from .factory_delivery import reassess
                elif work.definition=='commercial/v1':
                    from .factory_commercial import reassess
                else:
                    from .factory_planning import reassess
                reassess(request.user,work.pk,revision,request.POST.get('reason',''))
            elif operation=='observe_department':
                from .factory_planning import observe_department
                observe_department(request.user,work.pk,revision,int(request.POST.get('request','0')),int(request.POST.get('receipt','0')),int(request.POST.get('evidence','0')))
            elif operation=='commercial_decision':
                if work.definition!='commercial/v1':raise ValidationError('Commercial work required')
                from .factory_commercial import decide
                decide(request.user,work.pk,revision,request.POST.get('kind'),request.POST.get('target'),request.POST.get('verdict'),int(request.POST.get('evidence','0')),request.POST.get('note',''))
            elif operation=='delivery_decision':
                if work.definition!='delivery-release/v1':raise ValidationError('Delivery work required')
                from .factory_delivery import decide
                decide(request.user,work.pk,revision,request.POST.get('verdict'),int(request.POST.get('evidence','0')),request.POST.get('note',''),int(request.POST.get('case_revision','0')),request.POST.get('packet',''))
            elif operation=='hypercare_observation':
                if work.definition!='delivery-hypercare/v1':raise ValidationError('Release follow-up work required')
                from .factory_hypercare import observe
                kind=request.POST.get('kind')
                if kind=='release':
                    data={'readiness':int(request.POST['readiness']) if request.POST.get('readiness') else None,
                        'released_at':request.POST.get('released_at',''),'reference':request.POST.get('reference',''),
                        'evidence':int(request.POST.get('evidence','0')),'note':request.POST.get('note','')}
                elif kind=='acceptance':data={'receipt':int(request.POST.get('receipt','0')),'pm_signature':int(request.POST.get('pm_signature','0')),
                    'client_signature':int(request.POST.get('client_signature','0')),'packet':request.POST.get('packet',''),'note':request.POST.get('note','')}
                else:raise ValidationError('Choose an actual release or go-live acceptance observation')
                observe(request.user,work.pk,revision,int(request.POST.get('case_revision','0')),kind,data)
            elif operation=='reconcile':d.reconcile(request.user,work.pk,revision)
            elif operation in ['resume','cancel']:d.manage(request.user,work.pk,revision,operation)
            elif operation=='adopt_profile':d.adopt_profile(request.user,work.pk,revision,int(request.POST.get('configuration','0')),request.POST.get('reason',''))
            elif operation=='release_claim':
                t=get_object_or_404(HumanTask,case=work.case,pk=request.POST.get('task'),factory_key__startswith=f'factory:{work.pk}:')
                d.release_task_claim(request.user,t.pk,int(request.POST.get('task_revision','0')),request.POST.get('reason',''))
            elif operation=='claim':
                t=get_object_or_404(HumanTask,case=work.case,pk=request.POST.get('task'),factory_key__startswith=f'factory:{work.pk}:')
                d.claim_task(request.user,t.pk,int(request.POST.get('task_revision','0')))
            elif operation=='decide':
                t=get_object_or_404(HumanTask,case=work.case,pk=request.POST.get('task'),factory_key__startswith=f'factory:{work.pk}:')
                d.decide(request.user,t.pk,int(request.POST.get('task_revision','0')),request.POST.get('verdict'),int(request.POST.get('evidence','0')),request.POST.get('reason',''))
            elif operation=='responsibility_recheck':
                from .factory_routing import recheck
                t=get_object_or_404(HumanTask,case=work.case,pk=request.POST.get('task'),factory_key__startswith=f'factory:{work.pk}:')
                recheck(request.user,t.pk,int(request.POST.get('task_revision','0')),request.POST.get('reason',''))
            elif operation=='information':
                t=get_object_or_404(HumanTask,case=work.case,pk=request.POST.get('task'),factory_key__startswith=f'factory:{work.pk}:')
                d.provide_information(request.user,t.pk,int(request.POST.get('task_revision','0')),int(request.POST.get('case_revision','0')),request.POST.get('kind'),request.POST.get('body',''),request.POST.get('source',''))
            else:raise ValidationError('Choose a current available action')
            messages.success(request,'Action recorded. Check the current work and receipt status.')
            return redirect(request.get_full_path())
        except (ValidationError,ValueError) as exc:messages.error(request,str(exc))
        work=get_object_or_404(visible(request.user),pk=work_id)
    row=presentation(request.user,work)
    from apps.agents.factory_catalogue import CATALOGUE
    activities=list(work.activities.prefetch_related('attempts').order_by('pk'))
    for activity in activities:
        activity.title=CATALOGUE[activity.kind].title
        for attempt in activity.attempts.all():
            if work.definition=='delivery-hypercare/v1':
                from .factory_hypercare import attempt_projection
                attempt.display_result=attempt_projection(attempt)
            elif work.definition=='delivery-release/v1':
                from .factory_delivery import attempt_projection
                attempt.display_result=attempt_projection(attempt)
            elif work.definition=='planning/v1':
                from .factory_planning import attempt_projection
                attempt.display_result=attempt_projection(attempt)
            elif work.definition=='commercial/v1':
                from .factory_commercial import attempt_projection
                attempt.display_result=attempt_projection(attempt)
            attempt.summary='Activity started with current source references.' if attempt.phase=='started' else 'The activity could not continue.' if attempt.phase=='failed' else 'A native result or next activity was recorded.'
            if attempt.result.get('verified'):
                attempt.summary={'planning/v1':'The current planning artifact and internal delivery handoff match.',
                    'commercial/v1':'Declared costing, the reviewed client version and its recipient receipts match.',
                    'delivery-release/v1':'Native release-evidence readiness matches the current delivery prerequisites.',
                    'delivery-hypercare/v1':'Current observations meet the configured stability criteria; closure and financial release remain separate.'}.get(work.definition,'Native invoice and delivery receipts match the expected output.')
            elif attempt.result.get('dispatch_job'):attempt.summary='Processing was requested from the native invoice worker. Inspect receipts for the observed result.'
            elif attempt.result.get('waiting')=='approval':attempt.summary='The exact publication packet is waiting for an eligible Finance decision.'
            elif attempt.result.get('waiting')=='input':attempt.summary='A native information task records the missing source and configured resolver.'
    proofs=Evidence.objects.filter(case=work.case,kind='invoice_review')
    job_ids=[j.pk for j in row['jobs']]
    history=Audit.objects.filter(case=work.case,action__startswith='invoice.effect_',data__job__in=job_ids).order_by('pk')
    if work.definition=='planning/v1':
        from apps.pmo import planning
        row['planning']=planning.report(request.user,work.case_id)
        row['packet']=work.source_head
        try:planning.read(work.case,work.source_head,'packet','coordinate')
        except (ValidationError,PermissionDenied):row['packet']=None
        row['current_packet']=planning.latest(work.case,'packet')
        from .factory_planning import owner_panels
        row['owner_panels']=owner_panels(request.user,work)
        from apps.pmo.models import DeliverySource
        row['handoff']=DeliverySource.objects.filter(dossier__case=work.case,kind='scope_baseline',evidence_id=row['planning'].get('readiness_id')).first() if row['planning'].get('readiness_id') else None
    template='factory/hypercare_detail.html' if work.definition=='delivery-hypercare/v1' else 'factory/delivery_detail.html' if work.definition=='delivery-release/v1' else 'factory/commercial_detail.html' if work.definition=='commercial/v1' else 'factory/planning_detail.html' if work.definition=='planning/v1' else 'factory/detail.html'
    response=render(request,template,{'case':work.case,'row':row,'activities':activities,'review_evidence':proofs,'effect_history':history,'can_configure':permitted(request.user,work,'policy.configure'),'queue':return_queue,'q':q,'as_of':timezone.now()})
    response['Cache-Control']='no-store';return response

def responsibility_names(case,value,cache=None):
    """Nominations are readable facts, never authority; do not expose foreign accounts."""
    from apps.policy.factory_routing_validators import principal
    labels={'process_owner_id':'Invoice process owner','activity_owner_id':'Review routing owner',
        'policy_owner_id':'Review policy owner','governance_resolver_id':'Responsibility resolver'}
    rows=[];cache={} if cache is None else cache
    for key,label in labels.items():
        pk=value.get(key) if isinstance(value,dict) else None
        cache_key=(case._state.db,str(case.pk),pk,key=='governance_resolver_id') if pk is None or type(pk) is int else None
        if cache_key in cache:
            rows.append({'label':label,**cache[cache_key]});continue
        person=None
        if type(pk) is int and pk>0:
            person=get_user_model().objects.filter(pk=pk,grant__case=case).distinct().first()
        name=(person.get_full_name() or person.username) if person else 'Not assigned' if pk is None else 'Account unavailable in this workspace'
        status='Unknown' if pk is None else 'Current workspace access' if person and principal(case,pk,key=='governance_resolver_id') else 'Access needs review'
        fact={'name':name,'status':status}
        if cache_key is not None:cache[cache_key]=fact
        rows.append({'label':label,**fact})
    return rows

def responsibility_context(request,case):
    """Only authorised native work and bounded filters can become return navigation."""
    query_key=request.GET.get('work','')
    work_key=request.POST.get('work',query_key) if request.method=='POST' else query_key
    if request.method=='POST' and query_key and work_key!=query_key:raise Http404
    work=None
    if work_key:
        if not work_key.isascii() or not work_key.isdecimal() or len(work_key)>19 or not 1<=int(work_key)<=2**63-1:raise Http404
        work=get_object_or_404(visible(request.user),pk=int(work_key),case=case,definition='pmo-finance/v1')
    queue=request.POST.get('queue',request.GET.get('queue','needs_me'))
    if queue not in QUEUES:queue='needs_me'
    q=request.POST.get('q',request.GET.get('q','')).strip()[:120]
    suffix='?'+urlencode({'work':work.pk,'queue':queue,'q':q}) if work else ''
    return {'selected_work':work,'queue':queue,'q':q,'configuration_url':request.path+suffix,
        'return_url':reverse('factory_detail',args=[work.pk])+'?'+urlencode({'queue':queue,'q':q}) if work else None}

class ResponsibilityForm(forms.Form):
    availability_mode=forms.ChoiceField(required=False,label='Check reviewer availability?',choices=[('', 'Not decided'),
        ('not_applied','Do not apply availability windows'),('current_window_required','Require a confirmed available window')],
        help_text='When required, missing or unconfirmed periods hold only the affected decision. An absent reviewer needs an already authorised substitute.')
    authority_mode=forms.ChoiceField(required=False,label='Who may review invoices?',choices=[('', 'Not decided'),
        ('direct_only','Assigned Finance reviewers'),('direct_or_configured_delegate','Assigned Finance reviewers or configured delegates')],
        help_text='Delegates still need current authority for this project, decision, amount, currency and dates. An unknown choice holds only the dependent review.')
    process_owner_id=forms.ModelChoiceField(queryset=get_user_model().objects.none(),required=False,label='Invoice process owner')
    activity_owner_id=forms.ModelChoiceField(queryset=get_user_model().objects.none(),required=False,label='Review routing owner')
    policy_owner_id=forms.ModelChoiceField(queryset=get_user_model().objects.none(),required=False,label='Review policy owner')
    governance_resolver_id=forms.ModelChoiceField(queryset=get_user_model().objects.none(),required=False,label='Responsibility resolver')
    evidence=forms.ModelChoiceField(queryset=Evidence.objects.none(),label='Recorded configuration decision')
    def __init__(self,case,*args,**kwargs):
        super().__init__(*args,**kwargs)
        from apps.policy.factory_routing_validators import principal,OWNERS
        users=list(get_user_model().objects.filter(is_active=True,grant__case=case,grant__active=True,grant__action='factory.read').distinct())
        for name in (*OWNERS,'governance_resolver_id'):
            ids=[u.pk for u in users if principal(case,u.pk,name=='governance_resolver_id')]
            self.fields[name].queryset=get_user_model().objects.filter(pk__in=ids).order_by('username')
            self.fields[name].label_from_instance=lambda user:user.get_full_name() or user.username
            self.fields[name].help_text='Leave blank when unknown. Selection does not grant permission to approve invoices.'
        self.fields['evidence'].queryset=Evidence.objects.filter(case=case,kind='policy_decision')

@login_required
def responsibility_configuration(request,case_id):
    from apps.core.views import accessible_case
    from apps.policy.factory_routing_validators import COMPONENT as responsibility,OWNERS,METHOD_V2,METHOD_V3
    from apps.policy.availability_forms import ReviewerAvailabilityForm
    from apps.policy.reviewer_availability import draft_record as draft_availability
    from apps.policy.reviewer_availability_validators import COMPONENT as AVAILABILITY
    from apps.policy.impact import configuration as readable_configuration
    from apps.policy.role_forms import InvoiceDelegationForm
    from apps.policy.role_assignments import draft_invoice_delegation
    case=accessible_case(request.user,case_id);d.access(request.user,case,'policy.configure')
    context=responsibility_context(request,case)
    binding=resolve(responsibility,case)
    current_value=reference_values(binding.configuration)[0] if binding.status=='ACTIVE' else None
    form=ResponsibilityForm(case,request.POST if request.method=='POST' and request.POST.get('action')=='draft' else None)
    if not form.is_bound and current_value:form.initial['authority_mode']=current_value.get('authority_mode','direct_only')
    if not form.is_bound and current_value:form.initial['availability_mode']=current_value.get('availability_mode','not_applied')
    delegate_form=InvoiceDelegationForm(request.user,case,request.POST if request.method=='POST' and request.POST.get('action')=='invoice_delegation_draft' else None,prefix='invoice_delegate')
    availability_form=ReviewerAvailabilityForm(request.user,case,request.POST if request.method=='POST' and request.POST.get('action')=='availability_draft' else None,prefix='reviewer_availability')
    if request.method=='POST':
        try:
            if request.POST.get('action')=='draft' and form.is_valid():
                value={name:form.cleaned_data[name].pk if form.cleaned_data[name] else None for name in (*OWNERS,'governance_resolver_id')}
                method=(METHOD_V3 if 'availability_mode' in request.POST or current_value and current_value['method']==METHOD_V3 else
                    current_value['method'] if 'authority_mode' not in request.POST and current_value else METHOD_V2)
                value.update(definition='pmo-finance/v1',process_id='F30',activity='ACT10',method=method)
                if method in [METHOD_V2,METHOD_V3]:value['authority_mode']=(current_value.get('authority_mode','direct_only') if 'authority_mode' not in request.POST and current_value else form.cleaned_data['authority_mode'] or None)
                if method==METHOD_V3:value['availability_mode']=(current_value.get('availability_mode') if 'availability_mode' not in request.POST and current_value else form.cleaned_data['availability_mode'] or None)
                draft_operator_policy(request.user,case.pk,responsibility,value,form.cleaned_data['evidence'].pk,timezone.now())
                messages.success(request,'Responsibility draft saved for validation.');return redirect(context['configuration_url'])
            elif request.POST.get('action')=='invoice_delegation_draft' and delegate_form.is_valid():
                data=delegate_form.cleaned_data
                draft_invoice_delegation(request.user,case.pk,delegate_form.record(),data['evidence'].pk,data['effective_from'],data['source_configuration'],data['replacement'] or None)
                messages.success(request,'Invoice delegation draft saved. Review it before activation.');return redirect(context['configuration_url'])
            elif request.POST.get('action')=='delegation_transition':
                if not delegate_form.source_available:raise PermissionDenied('Current delegation source access required')
                config=get_object_or_404(Configuration,case=case,component='D05.delegation_rules',pk=int(request.POST.get('configuration','0')))
                readable_configuration(request.user,case.pk,config.pk)
                transition(request.user,config.pk,request.POST.get('state'));return redirect(context['configuration_url'])
            elif request.POST.get('action')=='availability_draft' and availability_form.is_valid():
                data=availability_form.cleaned_data
                draft_availability(request.user,case.pk,availability_form.record(),data['evidence'].pk,data['effective_from'],data['source_configuration'],data['replacement'] or None)
                messages.success(request,'Availability draft saved for validation.');return redirect(context['configuration_url'])
            elif request.POST.get('action')=='availability_transition':
                if not availability_form.source_available:raise PermissionDenied('Current availability source access required')
                config=get_object_or_404(Configuration,case=case,component=AVAILABILITY,pk=int(request.POST.get('configuration','0')))
                readable_configuration(request.user,case.pk,config.pk)
                transition(request.user,config.pk,request.POST.get('state'));return redirect(context['configuration_url'])
            elif request.POST.get('action')=='transition':
                config=get_object_or_404(Configuration,case=case,component=responsibility,pk=int(request.POST.get('configuration','0')))
                transition(request.user,config.pk,request.POST.get('state'));return redirect(context['configuration_url'])
        except (ValidationError,ValueError) as exc:
            (delegate_form if request.POST.get('action')=='invoice_delegation_draft' else
                availability_form if request.POST.get('action')=='availability_draft' else form).add_error(None,str(exc))
    configs=list(Configuration.objects.filter(case=case,component=responsibility).prefetch_related('states').order_by('-pk'))
    names_cache={}
    can_activate=Grant.objects.filter(case=case,user=request.user,active=True,action='policy.activate').exists()
    for config in configs:
        state=max(config.states.all(),key=lambda s:s.pk,default=None);current=state.state if state else 'unknown'
        config.current_status=current.capitalize()
        config.can_validate=current=='draft';config.can_activate=can_activate and current=='validated';config.can_revoke=can_activate and current=='active'
        try:config.settings_value=reference_values(config)[0] if config.envelope.get('value') is not None else None
        except (ValidationError,KeyError,TypeError):config.settings_value=None
        config.nominees=responsibility_names(case,config.settings_value,names_cache)
        config.effective_at=parse_datetime(config.envelope.get('effective_from',''))
    mode_label=lambda value:('Not decided' if value is None or value.get('authority_mode','direct_only') is None else
        'Assigned Finance reviewers or configured delegates' if value.get('authority_mode')=='direct_or_configured_delegate' else 'Assigned Finance reviewers')
    delegation_versions=[]
    if delegate_form.source_available:
        for config in Configuration.objects.filter(case=case,component='D05.delegation_rules').prefetch_related('states').order_by('-pk')[:20]:
            try:readable_configuration(request.user,case.pk,config.pk)
            except PermissionDenied:continue
            state=max(config.states.all(),key=lambda s:s.pk,default=None);current=state.state if state else 'unknown'
            config.current_status=current.capitalize();config.can_validate=current=='draft';config.can_activate=can_activate and current=='validated';config.can_revoke=can_activate and current=='active'
            delegation_versions.append(config)
    availability_versions=[]
    if availability_form.source_available:
        for config in Configuration.objects.filter(case=case,component=AVAILABILITY).prefetch_related('states').order_by('-pk')[:20]:
            try:readable_configuration(request.user,case.pk,config.pk)
            except PermissionDenied:continue
            state=max(config.states.all(),key=lambda s:s.pk,default=None);current=state.state if state else 'unknown'
            config.current_status=current.capitalize();config.can_validate=current=='draft';config.can_activate=can_activate and current=='validated';config.can_revoke=can_activate and current=='active'
            availability_versions.append(config)
    availability_label=('Not decided' if current_value is None or current_value.get('availability_mode','not_applied') is None else
        'Confirmed available window required' if current_value.get('availability_mode')=='current_window_required' else 'Availability windows not applied')
    context.update(case=case,form=form,configurations=configs,current_names=responsibility_names(case,current_value,names_cache),
        current_configured=binding.status=='ACTIVE',current_authority_mode=mode_label(current_value),invoice_delegation_form=delegate_form,
        delegation_versions=delegation_versions,reviewer_availability_form=availability_form,availability_versions=availability_versions,
        current_availability_mode=availability_label,as_of=timezone.now())
    response=render(request,'factory/responsibility.html',context);response['Cache-Control']='no-store';return response

class ProfileForm(forms.Form):
    provider=forms.ChoiceField(required=False,label='Coordinator selection',choices=[('','Not decided'),('synthetic_factory_v1','Isolated test coordinator'),('governed_factory_v1','Configured coordinator')])
    max_steps=forms.IntegerField(min_value=1,max_value=100,label='Maximum agent decisions')
    max_tokens=forms.IntegerField(min_value=1,max_value=1000000,label='Shared token allowance')
    tokens_per_call=forms.IntegerField(min_value=1,max_value=32000,label='Tokens reserved per decision')
    max_children=forms.IntegerField(min_value=1,max_value=100,label='Maximum activity records')
    max_depth=forms.IntegerField(min_value=1,max_value=5,label='Maximum delegation depth')
    lease_seconds=forms.IntegerField(min_value=1,max_value=300,label='Worker lease in seconds')
    max_age_seconds=forms.IntegerField(min_value=1,max_value=31536000,label='Maximum evidence age in seconds')
    required_evidence_kinds=forms.CharField(label='Required source types, separated by commas')
    information_resolver_id=forms.ModelChoiceField(queryset=get_user_model().objects.none(),required=False,label='Information resolver')
    executor_id=forms.ModelChoiceField(queryset=get_user_model().objects.none(),required=False,label='Invoice executor')
    evidence=forms.ModelChoiceField(queryset=Evidence.objects.none(),label='Recorded configuration decision')
    enabled=forms.BooleanField(required=False,label='Enable this execution profile')
    def __init__(self,case,*args,definition='pmo-finance/v1',**kwargs):
        super().__init__(*args,**kwargs);self.case=case;self.fields['evidence'].queryset=Evidence.objects.filter(case=case,kind='policy_decision')
        for field,action in [('information_resolver_id','factory.information'),('executor_id','factory.execute')]:
            self.fields[field].queryset=get_user_model().objects.filter(is_active=True,grant__case=case,grant__active=True,grant__action=action).distinct()
        if definition in ['delivery-go-live/v1','pmo-change/v1','pmo-emergency/v1']:
            preparers=get_user_model().objects.filter(is_active=True)
            for action in ['case.read','emergency.read' if definition=='pmo-emergency/v1' else 'change.read' if definition=='pmo-change/v1' else 'delivery.read','factory.execute','emergency.manage' if definition=='pmo-emergency/v1' else 'change.manage' if definition=='pmo-change/v1' else 'delivery.manage','document.draft','document.request_review']:
                preparers=preparers.filter(grant__case=case,grant__active=True,grant__action=action)
            self.fields['preparer_id']=forms.ModelChoiceField(queryset=preparers.distinct(),required=False,label='Existing Emergency report preparer' if definition=='pmo-emergency/v1' else 'Existing change preparer' if definition=='pmo-change/v1' else 'Existing PM for report preparation',
                help_text='Selection does not grant Emergency or document permissions.' if definition=='pmo-emergency/v1' else 'Selection does not grant change or document permissions.' if definition=='pmo-change/v1' else 'Selection does not confer PM authority. Current business-role assignment is checked again at execution.')

    def clean_provider(self):
        value=self.cleaned_data['provider']
        if value=='synthetic_factory_v1' and not self.case.synthetic:raise forms.ValidationError('Synthetic factory provider cannot activate for operational data')
        return value

@login_required
def configuration(request,case_id):
    from apps.core.views import accessible_case
    envelope=request.POST.get('definition',request.GET.get('definition','pmo-finance/v1'))
    if envelope not in DEFINITIONS:raise Http404
    spec=definition(envelope);component=spec['component']
    case=accessible_case(request.user,case_id);d.access(request.user,case,'policy.configure',envelope)
    form_class=ProfileForm
    if envelope=='finance-forecast/v1':
        from .factory_forecast_views import ForecastProfileForm
        form_class=ForecastProfileForm
    elif envelope=='finance-accounts/v1':
        from .factory_accounting_views import AccountingProfileForm
        form_class=AccountingProfileForm
    elif envelope=='rfp-response/v1':
        from .factory_rfp_views import RFPProfileForm
        form_class=RFPProfileForm
    form=form_class(case,request.POST if request.method=='POST' else None,definition=envelope)
    if envelope in ['finance-payroll/v1','pmo-emergency/v1','pmo-change/v1','planning/v1','commercial/v1','delivery-release/v1','delivery-hypercare/v1','delivery-archive/v1','delivery-handover/v1','delivery-closure/v1','delivery-go-live/v1']:
        for name in (['executor_id','information_resolver_id'] if envelope in ['finance-payroll/v1','planning/v1','delivery-release/v1','delivery-hypercare/v1'] else ['information_resolver_id']):
            form.fields[name].widget=forms.HiddenInput();form.fields[name].disabled=True
    if envelope in ['pmo-emergency/v1','pmo-change/v1','commercial/v1','delivery-handover/v1','delivery-go-live/v1']:
        form.fields['executor_id'].label='Controlled document publisher'
        form.fields['executor_id'].queryset=form.fields['executor_id'].queryset.filter(grant__case=case,grant__active=True,grant__action='document.publish').distinct()
        if envelope in ['pmo-emergency/v1','pmo-change/v1','delivery-handover/v1','delivery-go-live/v1']:
            for action in ['case.read','emergency.read' if envelope=='pmo-emergency/v1' else 'change.read' if envelope=='pmo-change/v1' else 'delivery.read']:
                form.fields['executor_id'].queryset=form.fields['executor_id'].queryset.filter(grant__case=case,grant__active=True,grant__action=action).distinct()
    if envelope in ['delivery-archive/v1','delivery-closure/v1']:
        form.fields['executor_id'].label='Closure finaliser' if envelope=='delivery-closure/v1' else 'Archive operator'
        for action in ['case.read','delivery.read','delivery.manage']:
            form.fields['executor_id'].queryset=form.fields['executor_id'].queryset.filter(grant__case=case,grant__active=True,grant__action=action).distinct()
    if request.method=='POST' and request.POST.get('action')=='draft' and form.is_valid():
        value=dict(form.cleaned_data);proof=value.pop('evidence')
        value['required_evidence_kinds']=[v.strip() for v in value['required_evidence_kinds'].split(',') if v.strip()]
        for name in ['information_resolver_id','executor_id']+(['preparer_id'] if envelope in ['finance-forecast/v1','delivery-go-live/v1','pmo-change/v1','pmo-emergency/v1'] else []):value[name]=value[name].pk if value[name] else None
        if envelope=='finance-accounts/v1':
            value['template_id']=value['template_id'].pk if value['template_id'] else None
            for name in ['allocation_mode','audience','bu_metrics']:value[name]=value[name] or None
        if envelope=='rfp-response/v1':
            value['template_id']=value['template_id'].pk if value['template_id'] else None
            value['route_key']=value['route_key'] or None
        selected=value.pop('provider') or None
        if 'provider' not in request.POST:selected='synthetic_factory_v1' if case.synthetic else None
        value.update(definition=envelope,review_role=None if envelope in ['finance-forecast/v1','finance-payroll/v1','pmo-emergency/v1','pmo-change/v1','rfp-response/v1','planning/v1','commercial/v1','delivery-release/v1','delivery-hypercare/v1','delivery-archive/v1','delivery-handover/v1','delivery-closure/v1','delivery-go-live/v1'] else 'Finance',provider=selected)
        try:
            draft_operator_policy(request.user,case.pk,component,value,proof.pk,timezone.now());messages.success(request,'Draft saved. Validate it before activation.');return redirect(request.path+'?definition='+envelope)
        except ValidationError as exc:form.add_error(None,str(exc))
    elif request.method=='POST' and request.POST.get('action')=='transition':
        try:pk=int(request.POST.get('configuration','0'))
        except ValueError:messages.error(request,'Choose an available configuration version.');return redirect(request.path)
        config=get_object_or_404(Configuration,case=case,component=component,pk=pk)
        from apps.policy.models import ScopeApplication
        from apps.policy.scopes import authorized as source_authorized
        application=ScopeApplication.objects.select_related('source__configuration__case').filter(configuration=config).first()
        if application:source_authorized(request.user,application.source.configuration.case,'policy.read')
        try:transition(request.user,config.pk,request.POST.get('state'));return redirect(request.path+'?definition='+envelope)
        except ValidationError as exc:messages.error(request,str(exc))
    configs=list(Configuration.objects.filter(case=case,component=component).prefetch_related('states').order_by('-pk'))
    can_activate=Grant.objects.filter(case=case,user=request.user,active=True,action='policy.activate').exists()
    readable_configs=[]
    from apps.policy.models import ScopeApplication
    from apps.policy.scopes import authorized as source_authorized
    for config in configs:
        application=ScopeApplication.objects.select_related('source__configuration__case').filter(configuration=config).first()
        if application:
            try:source_authorized(request.user,application.source.configuration.case,'policy.read')
            except PermissionDenied:continue
        readable_configs.append(config)
        current=max(config.states.all(),key=lambda s:s.pk).state
        config.can_validate=current=='draft';config.can_activate=can_activate and current=='validated';config.can_revoke=can_activate and current=='active'
        try:config.settings_value=reference_values(config)[0]
        except (ValidationError,KeyError):config.settings_value=None
    response=render(request,'factory/configuration.html',{'case':case,'form':form,'configurations':readable_configs,'definition':envelope,'definition_title':spec['title']});response['Cache-Control']='no-store';return response

class PlanningStartForm(forms.Form):
    definition=forms.CharField(initial='planning/v1',widget=forms.HiddenInput)
    key=forms.CharField(max_length=100,widget=forms.HiddenInput)
    case=forms.ModelChoiceField(queryset=Case.objects.none(),label='Project')
    packet=forms.ModelChoiceField(queryset=Evidence.objects.none(),label='Current planning packet')
    reference=forms.CharField(max_length=100,label='Work reference')
    revision=forms.IntegerField(min_value=1,widget=forms.HiddenInput)
    def __init__(self,actor,data=None,case_id=None):
        super().__init__(data=data,initial={'key':uuid4().hex})
        cases=granted(actor,['planning.read','factory.start']).filter(kind='project');self.fields['case'].queryset=cases
        self.fields['case'].label_from_instance=workspace_name
        selected=cases.filter(pk=case_id).first() if case_id else None
        if selected:
            self.fields['case'].initial=selected;self.fields['revision'].initial=selected.revision
            packet=Evidence.objects.filter(case=selected,kind='planning_packet').order_by('-version').first()
            self.fields['packet'].queryset=Evidence.objects.filter(pk=packet.pk) if packet else Evidence.objects.none()
            self.fields['packet'].label_from_instance=lambda e:'Planning packet, version '+str(e.version)

def create_planning(request):
    from .factory_planning import start
    case_id=request.POST.get('case') if request.method=='POST' else request.GET.get('case')
    try:form=PlanningStartForm(request.user,request.POST if request.method=='POST' else None,case_id)
    except (ValueError,ValidationError):
        form=PlanningStartForm(request.user,data={});form.is_valid();form.add_error(None,'Choose an available project.')
    if request.method=='POST' and form.is_valid():
        v=form.cleaned_data
        try:
            work=start(request.user,v['case'].pk,v['key'],v['packet'].pk,v['reference'],v['revision']);return redirect('factory_detail',work_id=work.pk)
        except ValidationError as exc:form.add_error(None,str(exc))
    return render(request,'factory/planning_start.html',{'form':form,'available_cases':granted(request.user,['planning.read','factory.start']).filter(kind='project')})

class CommercialStartForm(forms.Form):
    definition=forms.CharField(initial='commercial/v1',widget=forms.HiddenInput)
    key=forms.CharField(max_length=100,widget=forms.HiddenInput)
    case=forms.ModelChoiceField(queryset=Case.objects.none(),label='Project')
    reference=forms.CharField(max_length=100,label='Commercial work reference')
    predecessor=forms.IntegerField(required=False,widget=forms.HiddenInput)
    revision=forms.IntegerField(min_value=1,widget=forms.HiddenInput)
    def __init__(self,actor,data=None,case_id=None):
        from apps.pmo import commercial_intake
        from apps.pmo.costing_models import CostingRule,CostingOracle
        from apps.pmo.models import CommercialRevision,CommercialCase
        from apps.documents.models import Template
        super().__init__(data=data,initial={'key':uuid4().hex})
        cases=granted(actor,['factory.start','commercial.prepare','costing.read','costing.source.read']).filter(kind='project')
        self.fields['case'].queryset=cases;self.fields['case'].label_from_instance=workspace_name
        selected=cases.filter(pk=case_id).first() if case_id else None
        specs={'requirements':('Requirements',['requirements']),'plan':('Project plan',['plan']),
            'engineering_estimate':('Engineering effort and timeline',['engineering_estimate']),'security_estimate':('Security effort and timeline',['security_estimate']),
            'sow':('SOW content',['sow']),'inputs':('Declared costing inputs',['p14_inputs']),'context_id':('Request or client feedback context',['requirements','client_feedback','change_request'])}
        for key,(label,kinds) in specs.items():
            query=Evidence.objects.filter(case=selected,kind__in=kinds) if selected else Evidence.objects.none()
            self.fields[key]=forms.ModelChoiceField(queryset=query,required=False,label=label)
            self.fields[key].label_from_instance=lambda e:e.source+' · version '+str(e.version)
        for key,label,query in [('rule_id','Calculator rule',CostingRule.objects.filter(case=selected)),('oracle_id','Independent example set',CostingOracle.objects.filter(rule__case=selected)),
            ('template_id','Client SOW template',Template.objects.filter(case=selected,definition__document_type='sow')),('predecessor_id','Prior commercial proposal',CommercialRevision.objects.filter(dossier__case=selected))]:
            self.fields[key]=forms.ModelChoiceField(queryset=query if selected else query.none(),required=False,label=label)
            self.fields[key].label_from_instance=lambda obj:getattr(obj,'reference',getattr(obj,'name','Proposal'))+' · '+str(getattr(obj,'version',getattr(obj,'number','')))
        if selected:
            self.fields['case'].initial=selected;self.fields['revision'].initial=selected.revision
            old=commercial_intake.latest(selected)
            if old:
                self.fields['predecessor'].initial=old.pk
                try:
                    for key,value in commercial_intake.read(actor,selected,old).items():self.fields[key].initial=value
                except (ValidationError,PermissionDenied):pass
            self.fields['predecessor_id'].initial=CommercialCase.objects.filter(case=selected).values_list('current_id',flat=True).first()

def create_commercial(request):
    from django.db import transaction
    from apps.pmo import commercial_intake
    from .factory_commercial import start
    case_id=request.POST.get('case') if request.method=='POST' else request.GET.get('case')
    try:form=CommercialStartForm(request.user,request.POST if request.method=='POST' else None,case_id)
    except (ValueError,ValidationError):
        form=CommercialStartForm(request.user,data={});form.is_valid();form.add_error(None,'Choose an available project.')
    if request.method=='POST' and form.is_valid():
        v=form.cleaned_data
        from adapters.commercial_intake import FIELDS
        values={key:v[key].pk if v[key] else None for key in FIELDS}
        try:
            with transaction.atomic():
                head=commercial_intake.capture(request.user,v['case'].pk,values,v['predecessor'],v['revision'])
                work=start(request.user,v['case'].pk,v['key'],head.pk,v['reference'])
            return redirect('factory_detail',work_id=work.pk)
        except ValidationError as exc:form.add_error(None,'; '.join(exc.messages))
    return render(request,'factory/commercial_start.html',{'form':form,'available_cases':granted(request.user,['factory.start','commercial.prepare','costing.read','costing.source.read']).filter(kind='project')})


class DeliveryStartForm(forms.Form):
    definition=forms.CharField(initial='delivery-release/v1',widget=forms.HiddenInput)
    key=forms.CharField(max_length=100,widget=forms.HiddenInput)
    case=forms.ModelChoiceField(queryset=Case.objects.none(),label='Project')
    dossier=forms.ModelChoiceField(queryset=Case.objects.none(),label='Delivery candidate')
    reference=forms.CharField(max_length=100,label='Delivery work reference')
    revision=forms.IntegerField(min_value=1,widget=forms.HiddenInput)
    def __init__(self,actor,data=None,case_id=None):
        from apps.pmo.models import DeliveryDossier
        super().__init__(data=data,initial={'key':uuid4().hex})
        cases=granted(actor,['factory.start','delivery.read','evidence.add']).filter(kind='project')
        self.fields['case'].queryset=cases;self.fields['case'].label_from_instance=workspace_name
        selected=cases.filter(pk=case_id).first() if case_id else None
        self.fields['dossier'].queryset=DeliveryDossier.objects.filter(case=selected).select_related('candidate') if selected else DeliveryDossier.objects.none()
        self.fields['dossier'].label_from_instance=lambda row:row.candidate.reference
        if selected:self.fields['case'].initial=selected;self.fields['revision'].initial=selected.revision

def create_delivery(request,envelope='delivery-release/v1'):
    if envelope=='delivery-hypercare/v1':
        from .factory_hypercare import start
    else:
        from .factory_delivery import start
    case_id=request.POST.get('case') if request.method=='POST' else request.GET.get('case')
    try:form=DeliveryStartForm(request.user,request.POST if request.method=='POST' else None,case_id)
    except (ValueError,ValidationError):
        form=DeliveryStartForm(request.user,data={});form.is_valid();form.add_error(None,'Choose an available project.')
    form.fields['definition'].initial=envelope
    if request.method=='GET' and request.GET.get('dossier'):
        try:
            if form.fields['dossier'].queryset.filter(pk=request.GET['dossier']).exists():form.fields['dossier'].initial=request.GET['dossier']
        except (ValueError,ValidationError):messages.error(request,'Choose an available delivery candidate.')
    if request.method=='POST' and form.is_valid():
        v=form.cleaned_data
        try:
            work=start(request.user,v['case'].pk,v['key'],v['dossier'].pk,v['reference'],v['revision']);return redirect('factory_detail',work_id=work.pk)
        except ValidationError as exc:form.add_error(None,str(exc))
    return render(request,'factory/delivery_start.html',{'form':form,'definition':envelope,
        'intake_title':'Start release follow-up' if envelope=='delivery-hypercare/v1' else 'Start delivery work',
        'available_cases':granted(request.user,['factory.start','delivery.read','evidence.add']).filter(kind='project')})

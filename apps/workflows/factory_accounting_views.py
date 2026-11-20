from uuid import uuid4,UUID
from urllib.parse import urlencode
from django import forms
from django.contrib import messages
from django.core.exceptions import ValidationError,PermissionDenied
from django.db.models import Max
from django.shortcuts import get_object_or_404,render,redirect
from django.http import Http404
from django.urls import reverse
from django.utils import timezone
from apps.identity.services import visible_cases,require
from apps.identity.models import Grant
from apps.core.evidence_access import public_evidence
from apps.core.read_observation import read_observation
from apps.finance.models import FinanceSource,FinanceAdjustment,FinanceRun
from apps.core.models import Evidence, Audit
from . import factory_accounting_intake as intake
from apps.documents.models import Template,PublicationReceipt
from . import factory as runtime,factory_accounting as service
from .models import FactoryActivity,HumanTask
from .factory_views import ProfileForm, QUEUES
from .factory_progress_views import StartWithBackground, start_work

REVIEW_LABELS = {'source': 'the trial-balance source', 'mapping': 'the mapping rule', 'allocation': 'the allocation rule',
                 'formula': 'the formula rule', 'adjustment': 'the reporting adjustment', 'output': 'the prepared accounting report'}

class AccountingProfileForm(ProfileForm):
    allocation_mode=forms.ChoiceField(required=False,label='Preparation scope',choices=[('','Not decided'),('company_only','Company totals'),('company_and_bu','Company and business units')])
    bu_metrics=forms.MultipleChoiceField(required=False,label='Business-unit figures to allocate',choices=[(k,k.replace('_',' ').title()) for k in ['revenue','direct_cost','staff_cost','opex','other']])
    template_id=forms.ModelChoiceField(queryset=Template.objects.none(),required=False,label='Reviewed aggregate report template')
    audience=forms.ChoiceField(required=False,label='Report audience',choices=[('','Not decided'),('internal','Internal'),('group','Group')])
    def __init__(self,case,*args,**kwargs):
        super().__init__(case,*args,**kwargs)
        self.fields['template_id'].queryset=Template.objects.filter(case=case,definition__document_type='finance_report').order_by('name','version')
        self.fields['executor_id'].label='Report publisher'
        for action in ['finance.read','finance.publish','document.publish']:
            self.fields['executor_id'].queryset=self.fields['executor_id'].queryset.filter(grant__case=case,grant__active=True,grant__action=action).distinct()

class StartForm(StartWithBackground):
    source=forms.ModelChoiceField(queryset=FinanceSource.objects.none(),label='Current controlled trial-balance source')
    adjustment_ids=forms.ModelMultipleChoiceField(queryset=FinanceAdjustment.objects.none(),required=False,label='Supplemental reporting adjustments')
    inventory_confirmed=forms.BooleanField(label='I have checked this adjustment selection; none selected means no supplemental adjustments')
    reference=forms.CharField(max_length=100,label='Report work reference')
    revision=forms.IntegerField(min_value=1,widget=forms.HiddenInput)
    def __init__(self,case,*args,**kwargs):
        super().__init__(*args,**kwargs)
        heads=FinanceSource.objects.filter(case=case).values('batch_id').annotate(head=Max('pk')).values('head')
        self.fields['source'].queryset=FinanceSource.objects.filter(case=case,pk__in=heads).select_related('batch').order_by('-pk')
        self.fields['source'].label_from_instance=lambda s:f"{s.entity} · extracted {s.extracted_at:%d %b %Y %H:%M %Z}"
        self.fields['adjustment_ids'].queryset=FinanceAdjustment.objects.filter(source__case=case).order_by('source_id','reference','number')
        self.fields['adjustment_ids'].label_from_instance=lambda a:f'{a.reference} · revision {a.number}'
        self.initial['revision']=case.revision

class SuppliedIntakeForm(forms.Form):
    unit_declaration=forms.JSONField(required=False,help_text="Exact evidenced finance-source-units/v1 envelope for an existing import; blank is unknown, not assumed major currency.")
    key=forms.CharField(max_length=100,widget=forms.HiddenInput)
    evidence=forms.ModelChoiceField(queryset=Evidence.objects.none(),label='Supplied unchanged CSV evidence')
    source_evidence=forms.ModelChoiceField(queryset=Evidence.objects.none(),label='Extraction context evidence')
    entity=forms.CharField(max_length=100)
    period=forms.RegexField(r'^\d{4}-(0[1-9]|1[0-2])$',label='Declared reporting period (YYYY-MM)')
    currency=forms.RegexField(r'^[A-Z]{3}$',label='Declared source currency')
    accounting_basis=forms.CharField(max_length=100)
    extracted_at=forms.DateTimeField(label='Actual extraction/as-of time')
    completeness=forms.ChoiceField(choices=[('unknown','Unknown'),('partial','Partial'),('complete','Complete')])
    control_total=forms.CharField(max_length=64,required=False,label='Supplied control total (leave blank if unknown)')
    reference=forms.CharField(max_length=100,label='Report work reference')
    inventory_confirmed=forms.BooleanField(label='Start with no supplemental reporting adjustments; later changes require explicit rework')
    revision=forms.IntegerField(min_value=1,widget=forms.HiddenInput)

    def __init__(self,case,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.fields['evidence'].queryset=Evidence.objects.filter(case=case,kind='financial_input')
        self.fields['source_evidence'].queryset=Evidence.objects.filter(case=case,kind='finance_source')
        self.initial.update(key='supplied:'+str(uuid4()),revision=case.revision)


class ConfirmUnitsForm(forms.Form):
    unit = forms.ChoiceField(label='How are amounts shown in the file?', choices=[('', 'Choose units'), *intake.UNIT_CHOICES])
    proof = forms.ModelChoiceField(queryset=Evidence.objects.none(), label='Source evidence for the units')
    note = forms.CharField(label='Where did you confirm the units?', max_length=2000, widget=forms.Textarea(attrs={'rows': 3}))
    revision = forms.IntegerField(min_value=1, widget=forms.HiddenInput)

    def __init__(self, case, *args, **kwargs):
        super().__init__(*args, **kwargs)
        evidence = public_evidence(case.evidence.filter(kind='finance_source').defer('body'))
        self.fields['proof'].queryset = evidence.filter(pk__in=evidence.order_by('-version').values('pk')[:50]).order_by('-version')
        self.fields['proof'].label_from_instance = lambda record: f'{record.source} · version {record.version}'
        self.initial['revision'] = case.revision


def create(request):
    cases=[]
    for case in visible_cases(request.user).order_by('title'):
        try:
            runtime.access(request.user,case,'factory.start',service.DEFINITION);require(request.user,case,'evidence.add')
        except PermissionDenied:continue
        cases.append(case)
    selected=request.GET.get('case')
    if not selected:
        field=forms.ModelChoiceField(queryset=visible_cases(request.user).filter(pk__in=[c.pk for c in cases]),label='Workspace')
        return render(request,'factory/accounting_start.html',{'workspace_field':field.widget.render('case',None,attrs={'id':'accounting-workspace'}),'definition':service.DEFINITION})
    try:UUID(selected)
    except (ValueError,TypeError,AttributeError):raise Http404 from None
    case=get_object_or_404(visible_cases(request.user).filter(pk__in=[c.pk for c in cases]),pk=selected)
    action=request.POST.get('action','existing') if request.method=='POST' else None
    form=StartForm(case,request.POST if action=='existing' else None)
    supplied=SuppliedIntakeForm(case,request.POST if action=='supplied' else None,prefix='supplied')
    unit_receipt = None
    confirm_units = None
    intake_view = request.path + '?' + urlencode({'definition': service.DEFINITION, 'case': str(case.pk)})
    unit_selection = request.GET.get('units')
    if unit_selection is not None:
        if not unit_selection.isascii() or not unit_selection.isdecimal() or len(unit_selection) > 18:
            raise Http404
        intake.authority(request.user, case)
        unit_receipt = get_object_or_404(Audit, case=case, actor=request.user, action=intake.RECEIPT, pk=int(unit_selection))
        if not intake.can_confirm_units(unit_receipt, intake.latest(unit_receipt)):
            raise Http404
        confirm_units = ConfirmUnitsForm(case, request.POST if action == 'confirm_units' else None)
    result=None
    if request.method=='POST':
        try:
            if action=='existing' and form.is_valid():
                v=form.cleaned_data
                return start_work(request, lambda: service.start(request.user, case.pk, 'accounting:'+str(uuid4()),
                                  v['source'].pk, [a.pk for a in v['adjustment_ids']], v['reference'], v['revision']),
                                  v['background'])
            if action=='supplied' and supplied.is_valid():
                v=supplied.cleaned_data
                context={k:v[k] for k in ['entity','period','currency','accounting_basis','extracted_at','completeness']}
                context.update(control_total=v['control_total'] or None,source_evidence_id=v['source_evidence'].pk,unit_declaration=v['unit_declaration'])
                result=intake.submit(request.user,case.pk,v['key'],v['evidence'].pk,context,v['reference'],v['revision'])
            elif action=='resume':
                try:receipt_id=int(request.POST.get('receipt',''));revision=int(request.POST.get('revision',''))
                except (ValueError,TypeError):raise ValidationError('Exact receipt and current revision required')
                result=intake.resume(request.user,case.pk,receipt_id,revision)
            elif action == 'confirm_units':
                if confirm_units is None:
                    raise Http404
                if confirm_units.is_valid():
                    values = confirm_units.cleaned_data
                    result = intake.confirm_units(request.user, case.pk, unit_receipt.pk, values['unit'],
                                                  values['proof'].pk, values['note'], values['revision'])
            if result:
                if result['status']=='started':return redirect(reverse('factory_detail',args=[result['work']]))
                messages.warning(request,'Intake preserved: '+result['status'].replace('_',' ')+'. '+str(result['findings']))
                return redirect(intake_view if action == 'confirm_units' else request.get_full_path())
        except ValidationError as exc:
            target = confirm_units if action == 'confirm_units' else supplied if action == 'supplied' else form
            target.add_error(None, exc)
    case.refresh_from_db()
    receipts=[{'receipt':r,'result':intake.latest(r)} for r in Audit.objects.filter(case=case,actor=request.user,action=intake.RECEIPT).order_by('-pk')[:30]]
    superseded = set(Audit.objects.filter(case=case, actor=request.user, action=intake.UNITS_CONFIRMED,
                                         data__previous__in=[item['receipt'].pk for item in receipts])
                     .values_list('data__previous', flat=True))
    for item in receipts:
        item['missing_units'] = intake.can_confirm_units(item['receipt'], item['result'])
        if item['missing_units'] and item['receipt'].pk not in superseded:
            item['confirm_url'] = f"{intake_view}&units={item['receipt'].pk}"
    response=render(request,'factory/accounting_start.html',{'case':case,'form':form,'supplied_form':supplied,'receipts':receipts,
        'definition':service.DEFINITION,'unit_form':confirm_units,'unit_receipt':unit_receipt,'intake_view':intake_view});response['Cache-Control']='no-store';return response

@read_observation
def presentation(actor,work,*,include_progress=False):
    from apps.agents.factory_coordinator import decorate
    return decorate(actor,work,_presentation(actor,work,include_progress=include_progress))

def _presentation(actor,work,*,include_progress=False):
    runtime.access(actor,work.case,envelope=service.DEFINITION)
    def permitted(action):
        try:runtime.access(actor,work.case,action,service.DEFINITION);return True
        except PermissionDenied:return False
    tasks=list(HumanTask.objects.filter(case=work.case,kind='factory_accounting_review',context__work=work.pk).select_related('claimed_by').order_by('pk'))
    from .factory_execution import available_actor
    execution_owner=available_actor(work)
    value=None;observed=None;finding='';current=False;planning_ready=False;formula=None;options=[];jobs=[]
    try:
        _,value=runtime.profile(work,recovery=True);observed,latest,missing,stale,_,jobs=service.snapshot(work,value,reader=actor);current=True
        if work.status!='verified':options,_=service.eligible(work,value,observed,latest,missing,stale,tasks,jobs)
        formula=FinanceRun.objects.filter(pk=observed['formula']).first()
    except (ValidationError,PermissionDenied):finding='Review the current execution settings and source permissions before continuing.'
    if current:
        if execution_owner is None:finding='A current execution owner is required before further agent work. Existing Finance decisions remain available to authorised reviewers.'
        else:
            try:runtime.profile(work);planning_ready=True
            except (ValidationError,PermissionDenied):finding='Choose how this work will be coordinated before further agent work. Existing Finance decisions remain available to authorised reviewers.'
    for task in tasks:
        task.can_claim=task.can_decide=False;task.verdicts=[]
        task.label = 'Review ' + REVIEW_LABELS.get(task.context.get('purpose'), 'Finance evidence')
        if value is None or task.status!='open':continue
        try:
            row=service.review_task(work,task,value,reader=actor)
            candidate=next((c for c in service.route(work,row,value) if c['id']==actor.pk),None)
        except (ValidationError,PermissionDenied):continue
        if candidate:
            task.can_claim=task.claimed_by_id is None;task.can_decide=task.claimed_by_id==actor.pk;task.verdicts=list(candidate['decisions'])
    actionable=[t for t in tasks if t.can_claim or t.can_decide]
    waiting=[t for t in tasks if t.status=='open']
    status={'ready':'Ready to continue','waiting':'Work in progress','verified':'Verified','configuration_needed':'Configuration needed',
        'owner_needed':'Owner needed','blocked':'Accounting inputs need review','waiting_effect':'Report result uncertain','cancelled':'Cancelled','followup_needed':'Source-owned follow-up needed'}.get(work.status,'Check required')
    can_advance=current and planning_ready and bool(options) and permitted('factory.execute') and (execution_owner and actor.pk==execution_owner.pk or permitted('factory.manage')) and not work.cancel_requested and not (work.lease_until and work.lease_until>timezone.now()) and work.status not in ['verified','cancelled','followup_needed','configuration_needed','owner_needed','blocked','waiting_effect']
    owner='Unassigned';next_action='Continue eligible accounting work' if can_advance else 'Inspect current native sources and the permitted next action'
    if actionable:
        status='Awaiting Finance decision';owner=actor.get_full_name() or actor.username;next_action='Review the exact source, rule or accounting output'
    elif waiting:
        status='Awaiting Finance decision';claimed=next((t.claimed_by for t in waiting if t.claimed_by_id),None)
        owner=(claimed.get_full_name() or claimed.username) if claimed else 'Unassigned';next_action='Wait for a currently authorised Finance reviewer'
    elif can_advance:owner=execution_owner.get_full_name() or execution_owner.username
    if not current and finding:
        status='Execution rules need review';next_action='Review current source and execution rules before further work'
    elif not planning_ready and not waiting:
        status='Execution owner needs review' if execution_owner is None else 'Work coordination needs setup'
        next_action='Review execution authority before continuing' if execution_owner is None else 'Choose how this work will be coordinated'
    changed=False
    if work.status=='verified':
        owner='No action required';next_action='Inspect the reviewed report and native recipient receipts'
        try:service.verified(work,value,observed)
        except (ValidationError,PermissionDenied,TypeError):
            changed=True;status='Published report needs review';next_action='Review changed source or authority; earlier publication remains in the history'
    if work.cancel_requested or work.status in ['cancelled','followup_needed']:
        can_advance=False
        for task in tasks:task.can_claim=task.can_decide=False
        actionable=[]
    adoption=None
    if permitted('factory.manage') and permitted('policy.activate') and not work.cancel_requested and work.status not in ['verified','cancelled','followup_needed']:
        from apps.policy.services import resolve,reference_values
        resolved=resolve('OPS.factory_accounting_execution',work.case)
        if resolved.status=='ACTIVE' and work.policy_id and resolved.configuration.pk!=work.policy_id:
            proposal=reference_values(resolved.configuration)[0]
            if proposal['enabled']:adoption={'id':resolved.configuration.pk,'revision':resolved.configuration.revision,'effective_allowance':min(work.budget_limit,proposal['max_tokens'])}
    blocker=finding or work.finding
    if blocker.startswith('['):blocker='Review the recorded exception and current settings before continuing.'
    can_reassess = (permitted('factory.execute') and permitted('finance.source') and not work.cancel_requested
                    and work.status not in ('cancelled', 'waiting_effect')
                    and not (work.lease_until and work.lease_until > timezone.now())
                    and not service.PublicationJob.objects.filter(publication__factory_work=work,
                        status__in=('pending', 'unknown', 'leased', 'held')).exists())
    source_followup = work.status == 'followup_needed' and not work.cancel_requested
    if source_followup:
        next_action = ('Review the returned report and recheck the source records' if can_reassess
                       else 'Wait for a source owner to check the returned report')
    delivery_due = service.PublicationJob.objects.filter(publication__factory_work=work).filter(
        service.Q(status='unknown') | service.Q(status='leased', lease_until__lte=timezone.now())).exists()
    can_reconcile = (delivery_due and permitted('factory.execute') and permitted('document.publish')
                     and (execution_owner and actor.pk == execution_owner.pk or permitted('factory.manage'))
                     and not (work.lease_until and work.lease_until > timezone.now()))
    if delivery_due and work.status not in ('verified', 'cancelled', 'followup_needed'):
        status = 'Report delivery uncertain'
        can_advance = False
        next_action = ('Check the original report receipts' if can_reconcile
                       else 'Wait for an authorised person to check the original report receipts')
    progress = accounting_progress(work, observed, options, jobs) if include_progress and current else None
    return {'work':work,'state':status,'next_action':next_action,'owner':owner,'needs_me':bool(actionable) or can_advance or can_reconcile or (source_followup and can_reassess),
        'department_wait':bool(actionable),'tasks':tasks,'jobs':[],'can_advance':can_advance,'can_cancel':permitted('factory.manage') and work.status not in ['verified','cancelled','followup_needed'],
        'can_reconcile':can_reconcile,
        'can_reassess':can_reassess,
        'readiness_changed':changed,'blocker':blocker,'profile_available':value is not None,'adoption':adoption,
        'coordination_needed':current and not planning_ready and execution_owner is not None,'execution_owner_needed':current and execution_owner is None,'can_configure_coordination':permitted('policy.configure'),
        'accounting':{'state':observed,'formula':formula,'value':value,'progress':progress},'evidence_as_of':work.updated_at}


def accounting_progress(work, observed, options, jobs):
    from .factory_progress import current_plan_step

    if work.status == 'verified':
        return None
    now = timezone.now()
    unresolved = [job for job in jobs if job.status in ('pending', 'unknown', 'leased', 'held')]
    if any(job.status == 'unknown' or job.status == 'leased' and
           (job.lease_until is None or job.lease_until <= now) for job in unresolved):
        return {'label': 'Delivery is uncertain. Check the original report receipts.', 'watching': False}
    if any(job.status == 'held' for job in unresolved):
        return {'label': 'Report delivery needs recovery.', 'watching': False}
    if any(job.status == 'leased' for job in unresolved):
        return {'label': 'Report delivery is in progress.', 'watching': True}
    if unresolved:
        return {'label': 'The report is queued for delivery.', 'watching': True}

    labels = {'ACT04': 'Investigating the accounting sources.', 'ACT08': 'Calculating the accounting figures.',
              'ACT09': 'Drafting the accounting report.', 'ACT13': 'Verifying the report receipts.'}
    label = labels.get(current_plan_step(work, observed['hash'], options))
    return {'label': label, 'watching': True} if label else None

def detail(request,work,focus=None):
    from .factory_execution import can_control
    from .screen_focus import require_action

    runtime.access(request.user,work.case,envelope=service.DEFINITION)
    queue=request.GET.get('queue','needs_me');q=request.GET.get('q','')[:120]
    if queue not in QUEUES:queue='needs_me'
    url=request.path+'?'+urlencode({'queue':queue,'q':q})
    if request.method=='POST':
        try:
            action=request.POST.get('action');revision=int(request.POST.get('revision','0'))
            require_action(work, focus, action)
            target=None
            if action in ['claim','decide']:
                target=get_object_or_404(HumanTask,pk=int(request.POST.get('task','0')),case=work.case,kind='factory_accounting_review',context__work=work.pk)
            if action=='advance':
                from .factory_progress import set_progress, wake_waiting
                set_progress(request.user, work.pk, revision, True)
                wake_waiting(work.pk)
                messages.success(request, 'Accounting work can continue in the background. Check this work item for decisions and receipts.')
                return redirect(url)
            elif action=='claim':service.claim(request.user,target.pk,int(request.POST['task_revision']))
            elif action=='decide':service.decide(request.user,target.pk,int(request.POST['task_revision']),request.POST.get('verdict'),int(request.POST['evidence']),request.POST.get('reason',''))
            elif action=='cancel':runtime.manage(request.user,work.pk,revision,'cancel')
            elif action=='reconcile':service.reconcile(request.user,work.pk,revision)
            elif action=='recheck_reviewers':service.recheck_reviewers(request.user,work.pk,revision)
            elif action=='adopt_profile':runtime.adopt_profile(request.user,work.pk,revision,int(request.POST['configuration']),request.POST.get('reason',''))
            elif action=='recheck':
                source_id=int(request.POST['source']);raw=request.POST.get('adjustments','')
                ids=[int(v.strip()) for v in raw.split(',') if v.strip()]
                service.recheck(request.user,work.pk,revision,source_id,ids,request.POST.get('reason',''))
            else:raise ValidationError('Choose an available accounting action')
            messages.success(request,'Action recorded. Inspect the current native result and receipts.');return redirect(url)
        except (ValidationError,ValueError,KeyError) as exc:
            messages.error(request,'; '.join(exc.messages) if isinstance(exc,ValidationError) else 'Complete the requested fields using current records.');return redirect(url)
    row=presentation(request.user,work,include_progress=not focus)
    routing_hold = service.review_routing_hold(work)
    held_labels = sorted({REVIEW_LABELS.get(subject['purpose'], 'Finance evidence') for subject in routing_hold})
    review_controls = set(Grant.objects.filter(case=work.case, user=request.user, active=True,
                          action__in=['policy.read', 'factory.manage']).values_list('action', flat=True)) if routing_hold else set()
    source_choices=FinanceSource.objects.filter(case=work.case,batch_id=work.request['batch'],entity=work.request['entity']).order_by('-pk')
    current_inputs = {}
    if row['can_reassess'] and focus != 'decision':
        try:
            current_inputs = service.inputs(work)
        except ValidationError:
            row['can_reassess'] = False
    observed=row['accounting']['state'] or {}
    receipt_ids=[pk for pk,_ in observed.get('receipts',[])]
    receipts=PublicationReceipt.objects.filter(publication__version__document__case=work.case).filter(
        service.Q(publication__factory_work=work)|service.Q(pk__in=receipt_ids)).select_related('recipient').order_by('pk')
    from apps.agents.factory_catalogue import CATALOGUE
    activities=list(FactoryActivity.objects.filter(work=work).prefetch_related('attempts').order_by('pk')) if not focus else []
    for activity in activities:activity.business_title=CATALOGUE[activity.kind].title if activity.kind in CATALOGUE else 'Recorded agent work'
    for receipt in receipts:
        receipt.current_recipient_name=(receipt.recipient.get_full_name() or receipt.recipient.username) if receipt.recipient.is_active and Grant.objects.filter(case=work.case,user=receipt.recipient,active=True,action='finance.read').exists() else 'Historical recipient'
    response=render(request,'factory/accounting_detail.html',{'case':work.case,'row':row,'queue':queue,'q':q,
        'review_evidence':public_evidence(work.case.evidence.filter(kind='finance_review')).order_by('-pk'),
        'sources':source_choices,'current_source':current_inputs.get('source'),
        'current_adjustments':', '.join(map(str, current_inputs.get('adjustment_ids', []))),
        'receipts':receipts,'activities':activities,'held_review_labels':held_labels,
        'can_read_review_rules':'policy.read' in review_controls,
        'can_recheck_reviewers':focus!='decision' and 'factory.manage' in review_controls and can_control(request.user, work),
        'intake_provenance':intake.provenance(request.user,work) if not focus else None,'focus':focus})
    response['Cache-Control']='no-store';return response

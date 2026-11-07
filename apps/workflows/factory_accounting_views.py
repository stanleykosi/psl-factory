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
from apps.finance.models import FinanceSource,FinanceAdjustment,FinanceRun
from apps.core.models import Evidence, Audit
from . import factory_accounting_intake as intake
from apps.documents.models import Template,PublicationReceipt
from . import factory as runtime,factory_accounting as service
from .models import FactoryActivity,HumanTask
from .factory_views import ProfileForm

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

class StartForm(forms.Form):
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
    result=None
    if request.method=='POST':
        try:
            if action=='existing' and form.is_valid():
                v=form.cleaned_data
                work=service.start(request.user,case.pk,'accounting:'+str(uuid4()),v['source'].pk,[a.pk for a in v['adjustment_ids']],v['reference'],v['revision'])
                return redirect(reverse('factory_detail',args=[work.pk]))
            if action=='supplied' and supplied.is_valid():
                v=supplied.cleaned_data
                context={k:v[k] for k in ['entity','period','currency','accounting_basis','extracted_at','completeness']}
                context.update(control_total=v['control_total'] or None,source_evidence_id=v['source_evidence'].pk,unit_declaration=v['unit_declaration'])
                result=intake.submit(request.user,case.pk,v['key'],v['evidence'].pk,context,v['reference'],v['revision'])
            elif action=='resume':
                try:receipt_id=int(request.POST.get('receipt',''));revision=int(request.POST.get('revision',''))
                except (ValueError,TypeError):raise ValidationError('Exact receipt and current revision required')
                result=intake.resume(request.user,case.pk,receipt_id,revision)
            if result:
                if result['status']=='started':return redirect(reverse('factory_detail',args=[result['work']]))
                messages.warning(request,'Intake preserved: '+result['status'].replace('_',' ')+'. '+str(result['findings']))
                return redirect(request.get_full_path())
        except ValidationError as exc:
            (supplied if action=='supplied' else form).add_error(None,str(exc))
    case.refresh_from_db()
    receipts=[{'receipt':r,'result':intake.latest(r)} for r in Audit.objects.filter(case=case,actor=request.user,action=intake.RECEIPT).order_by('-pk')[:30]]
    response=render(request,'factory/accounting_start.html',{'case':case,'form':form,'supplied_form':supplied,'receipts':receipts,'definition':service.DEFINITION});response['Cache-Control']='no-store';return response

def presentation(actor,work):
    from apps.agents.factory_coordinator import decorate
    return decorate(actor,work,_presentation(actor,work))

def _presentation(actor,work):
    runtime.access(actor,work.case,envelope=service.DEFINITION)
    def permitted(action):
        try:runtime.access(actor,work.case,action,service.DEFINITION);return True
        except PermissionDenied:return False
    tasks=list(HumanTask.objects.filter(case=work.case,kind='factory_accounting_review',context__work=work.pk).select_related('claimed_by').order_by('pk'))
    from .factory_execution import available_actor
    execution_owner=available_actor(work)
    value=None;observed=None;finding='';current=False;planning_ready=False;formula=None;options=[]
    try:
        _,value=runtime.profile(work,recovery=True);observed,latest,missing,stale,_,jobs=service.snapshot(work,value,reader=actor);current=True
        options,_=service.eligible(work,value,observed,latest,missing,stale,tasks,jobs)
        formula=FinanceRun.objects.filter(pk=observed['formula']).first()
    except (ValidationError,PermissionDenied):finding='Review the current execution settings and source permissions before continuing.'
    if current:
        if execution_owner is None:finding='A current execution owner is required before further agent work. Existing Finance decisions remain available to authorised reviewers.'
        else:
            try:runtime.profile(work);planning_ready=True
            except (ValidationError,PermissionDenied):finding='Choose how this work will be coordinated before further agent work. Existing Finance decisions remain available to authorised reviewers.'
    for task in tasks:
        task.can_claim=task.can_decide=False;task.verdicts=[]
        task.label={'source':'Review the trial-balance source','mapping':'Review the mapping rule','allocation':'Review the allocation rule',
            'formula':'Review the formula rule','adjustment':'Review the reporting adjustment','output':'Review the prepared accounting report'}.get(task.context.get('purpose'),'Review Finance evidence')
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
    return {'work':work,'state':status,'next_action':next_action,'owner':owner,'needs_me':bool(actionable) or can_advance,
        'department_wait':bool(actionable),'tasks':tasks,'jobs':[],'can_advance':can_advance,'can_cancel':permitted('factory.manage') and work.status not in ['verified','cancelled','followup_needed'],
        'can_reconcile':permitted('factory.execute') and permitted('document.publish') and (execution_owner and actor.pk==execution_owner.pk or permitted('factory.manage')) and service.PublicationJob.objects.filter(publication__factory_work=work).filter(service.Q(status='unknown')|service.Q(status='leased',lease_until__lte=timezone.now())).exists() and not (work.lease_until and work.lease_until>timezone.now()),
        'can_reassess':permitted('factory.execute') and permitted('finance.source') and not work.cancel_requested,
        'readiness_changed':changed,'blocker':blocker,'profile_available':value is not None,'adoption':adoption,
        'coordination_needed':current and not planning_ready and execution_owner is not None,'execution_owner_needed':current and execution_owner is None,'can_configure_coordination':permitted('policy.configure'),
        'accounting':{'state':observed,'formula':formula,'value':value},'evidence_as_of':work.updated_at}

def detail(request,work):
    runtime.access(request.user,work.case,envelope=service.DEFINITION)
    queue=request.GET.get('queue','needs_me');q=request.GET.get('q','')[:120]
    if queue not in ['needs_me','active','decisions','exceptions','unassigned','verified']:queue='needs_me'
    url=reverse('factory_detail',args=[work.pk])+'?'+urlencode({'queue':queue,'q':q})
    if request.method=='POST':
        try:
            action=request.POST.get('action');revision=int(request.POST.get('revision','0'))
            target=None
            if action in ['claim','decide']:
                target=get_object_or_404(HumanTask,pk=int(request.POST.get('task','0')),case=work.case,kind='factory_accounting_review',context__work=work.pk)
            if action=='advance':
                runtime.access(request.user,work.case,'factory.execute',service.DEFINITION)
                from .factory_execution import require_control
                require_control(request.user,work)
                if work.revision!=revision:raise ValidationError('STALE_VERSION: accounting work changed')
                runtime.run_until_wait(work.pk)
            elif action=='claim':service.claim(request.user,target.pk,int(request.POST['task_revision']))
            elif action=='decide':service.decide(request.user,target.pk,int(request.POST['task_revision']),request.POST.get('verdict'),int(request.POST['evidence']),request.POST.get('reason',''))
            elif action=='cancel':runtime.manage(request.user,work.pk,revision,'cancel')
            elif action=='reconcile':service.reconcile(request.user,work.pk,revision)
            elif action=='adopt_profile':runtime.adopt_profile(request.user,work.pk,revision,int(request.POST['configuration']),request.POST.get('reason',''))
            elif action=='recheck':
                source_id=int(request.POST['source']);raw=request.POST.get('adjustments','')
                ids=[int(v.strip()) for v in raw.split(',') if v.strip()]
                service.recheck(request.user,work.pk,revision,source_id,ids,request.POST.get('reason',''))
            else:raise ValidationError('Choose an available accounting action')
            messages.success(request,'Action recorded. Inspect the current native result and receipts.');return redirect(url)
        except (ValidationError,ValueError,KeyError) as exc:
            messages.error(request,'; '.join(exc.messages) if isinstance(exc,ValidationError) else 'Complete the requested fields using current records.');return redirect(url)
    row=presentation(request.user,work)
    source_choices=FinanceSource.objects.filter(case=work.case,batch_id=work.request['batch'],entity=work.request['entity']).order_by('-pk')
    observed=row['accounting']['state'] or {}
    receipt_ids=[pk for pk,_ in observed.get('receipts',[])]
    receipts=PublicationReceipt.objects.filter(publication__version__document__case=work.case).filter(
        service.Q(publication__factory_work=work)|service.Q(pk__in=receipt_ids)).select_related('recipient').order_by('pk')
    from apps.agents.factory_catalogue import CATALOGUE
    activities=list(FactoryActivity.objects.filter(work=work).prefetch_related('attempts').order_by('pk'))
    for activity in activities:activity.business_title=CATALOGUE[activity.kind].title if activity.kind in CATALOGUE else 'Recorded agent work'
    for receipt in receipts:
        receipt.current_recipient_name=(receipt.recipient.get_full_name() or receipt.recipient.username) if receipt.recipient.is_active and Grant.objects.filter(case=work.case,user=receipt.recipient,active=True,action='finance.read').exists() else 'Historical recipient'
    response=render(request,'factory/accounting_detail.html',{'case':work.case,'row':row,'queue':queue,'q':q,
        'review_evidence':public_evidence(work.case.evidence.filter(kind='finance_review')).order_by('-pk'),
        'sources':source_choices,'receipts':receipts,'activities':activities,'intake_provenance':intake.provenance(request.user,work)})
    response['Cache-Control']='no-store';return response

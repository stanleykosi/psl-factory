"""Typed primary F01 console. Human observations and decisions stay native."""
from uuid import uuid4
from django import forms
from django.contrib import messages
from django.core.exceptions import ValidationError,PermissionDenied
from django.shortcuts import render,redirect
from django.views.decorators.http import require_http_methods
from django.views.decorators.cache import never_cache
from apps.core.models import Audit,Case,Evidence
from apps.core.workbench import granted
from apps.finance import ledger
from apps.finance.models import LedgerLineage
from . import factory,factory_ledger as domain
from .factory_progress_views import StartWithBackground, start_work
from .quickbooks_mcp import factory_read_status
from .screen_focus import require_action

class InputsForm(forms.Form):
    def __init__(self,case,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.fields['evidence_id']=forms.ModelChoiceField(queryset=Evidence.objects.filter(case=case,kind='ledger_source').order_by('-pk'),label='Exact supplied incumbent source')
        self.fields['predecessor_id']=forms.ModelChoiceField(queryset=LedgerLineage.objects.filter(case=case).order_by('-pk'),required=False,label='Exact predecessor for a correction')
    def ids(self):
        d=self.cleaned_data;return [d['evidence_id'].pk,d['predecessor_id'].pk if d['predecessor_id'] else None]

class StartForm(StartWithBackground):
    definition=forms.CharField(initial=domain.DEFINITION,widget=forms.HiddenInput)
    key=forms.CharField(max_length=100,widget=forms.HiddenInput)
    case=forms.ModelChoiceField(queryset=Case.objects.none())
    revision=forms.IntegerField(min_value=1,widget=forms.HiddenInput)
    def __init__(self,actor,*args,case_id=None,**kwargs):
        super().__init__(*args,**kwargs);cases=granted(actor,['factory.start','finance.read','ledger.read','ledger.private.read','evidence.add']);self.fields['case'].queryset=cases
        self.selected=cases.filter(pk=case_id).first() if case_id else None
        if self.selected:self.fields['case'].initial=self.selected;self.fields['revision'].initial=self.selected.revision
        if not self.is_bound:self.fields['key'].initial='ledger-'+uuid4().hex

@never_cache
@require_http_methods(['GET','HEAD','POST'])
def create(request):
    data=request.POST if request.method=='POST' else None
    try:form=StartForm(request.user,data,case_id=(data or request.GET).get('case'))
    except (ValueError,ValidationError):form=StartForm(request.user,data={});form.is_valid();form.add_error(None,'Choose an available case')
    inputs=InputsForm(form.selected,data) if form.selected else None
    if request.method=='POST' and form.is_valid() and inputs and inputs.is_valid():
        try:
            d=form.cleaned_data
            if d['definition']!=domain.DEFINITION or set(request.POST)-set(form.fields)-set(inputs.fields)-{'csrfmiddlewaretoken'}:raise ValidationError('Exact typed incumbent command required')
            return start_work(request, lambda: domain.start(request.user, d['case'].pk, d['key'],
                              *inputs.ids(), d['revision']), d['background'])
        except ValidationError as exc:form.add_error(None,domain.finding(exc))
    return render(request,'factory/ledger_start.html',{'form':form,'inputs_form':inputs,'case':form.selected})

@never_cache
@require_http_methods(['GET','HEAD','POST'])
def detail(request,work,focus=None):
    from .factory_views import presentation,permitted
    data,e,body=domain.source(work,request.user,False)
    form=InputsForm(work.case,request.POST if request.method=='POST' and request.POST.get('action')=='correct' else None,initial=data) if focus in (None,'recovery') and permitted(request.user,work,'factory.manage') else None
    if request.method=='POST':
        try:
            p=request.POST;a=p.get('action');revision=int(p.get('revision','0'));case_revision=int(p.get('case_revision','0'))
            require_action(work,focus,a)
            allowed={'advance':set(),'recheck':{'reason'},'restart':{'reason'},'resume':set(),'cancel':set(),'correct':{'evidence_id','predecessor_id','reason'},'observe':{'target','evidence','outcome'},'review':{'target','evidence','verdict','reason'},'adopt_profile':{'configuration','reason'}}
            if a not in allowed or set(p)-allowed[a]-{'action','revision','case_revision','csrfmiddlewaretoken'}:raise ValidationError('Choose an exact typed incumbent command')
            if a=='advance':
                from .factory_progress import set_progress
                set_progress(request.user,work.pk,revision,True)
            elif a=='restart':domain.restart(request.user,work.pk,revision,case_revision,p.get('reason',''))
            elif a=='recheck':domain.recheck(request.user,work.pk,revision,case_revision,p.get('reason',''))
            elif a in ['resume','cancel']:factory.manage(request.user,work.pk,revision,a)
            elif a=='correct':
                if not form or not form.is_valid():raise ValidationError('Choose exact native sources')
                domain.correct(request.user,work.pk,revision,case_revision,*form.ids(),p.get('reason',''))
            elif a in ['observe','review']:
                domain.command(request.user,work.pk,revision,case_revision,a,int(p.get('target','0')),
                               int(p.get('evidence','0')),p.get('verdict'),outcome=p.get('outcome'),reason=p.get('reason',''))
            elif a=='adopt_profile':factory.adopt_profile(request.user,work.pk,revision,int(p.get('configuration','0')),p.get('reason',''))
            messages.success(request,'Native incumbent reference work updated');return redirect(request.get_full_path())
        except (ValidationError,ValueError) as exc:messages.error(request,domain.finding(exc));work.refresh_from_db();work.case.refresh_from_db()
    row=presentation(request.user,work);w=row['ledger']['lineage'];x=w.checks.order_by('-pk').first() if w else None;can_review=False;can_approve=False
    conflict=domain.conflicting_source(work,data,w)
    decision=x.decisions.order_by('-pk').first() if x else None
    rejected=decision and decision.verdict=='reject'
    rejection=Audit.objects.filter(case=work.case,action='ledger.review',data__decision=decision.pk).values_list('data__reason',flat=True).first() if rejected else None
    if x and not rejected and not conflict and focus in (None,'decision') and request.user.pk not in [w.actor_id,x.actor_id]:
        try:ledger.authority(request.user,x)
        except (ValidationError,PermissionDenied):pass
        else:can_review=True
        if can_review:
            try:ledger.current(x)
            except (ValidationError,PermissionDenied):pass
            else:can_approve=True
    active=not work.cancel_requested and work.status not in ['cancelled','followup_needed']
    if active and conflict:
        row.update(state='Duplicate source refused',next_action='Compare the earlier source and use its lineage for any correction',can_advance=False)
        if form and not form.is_bound and not w:form.initial['predecessor_id']=conflict.pk
    elif active and rejected:
        row.update(state='Observation rejected',next_action='Supply fresh observation proof or correct the source in the same lineage',can_advance=False)
    elif row['state']=='Verified':
        row['next_action']='Inspect the approved reference and its observation'
    can_observe=active and w is not None and not conflict and focus in (None,'response') and permitted(request.user,work,'ledger.verify')
    return render(request,'factory/ledger_detail.html',{'row':row,'case':work.case,'focus':focus,
        'queue':request.GET.get('queue','needs_me'),'q':request.GET.get('q','')[:120],
        'source':body,'source_evidence':e,'conflict':conflict,'rejected':rejected,'rejection':rejection,'inputs_form':form,'check':x,
        'can_review':active and can_review,'can_approve':can_approve,'can_observe':can_observe,
        'observations':Evidence.objects.filter(case=work.case,kind='quickbooks_verification').order_by('-pk') if can_observe else [],
        'review_evidence':Evidence.objects.filter(case=work.case,kind__in=['finance_review','policy_decision']).order_by('-pk') if can_review else [],
        'decisions':x.decisions.order_by('-pk') if x else [],'activities':work.activities.prefetch_related('attempts').order_by('pk') if not focus else [],
        'can_restart':work.status=='cancelled' and form is not None,'can_correct':active and form is not None,
        'can_configure':permitted(request.user,work,'policy.configure'),'mcp_read':factory_read_status(request.user,work)})

"""Typed primary F01 console. Human observations and decisions stay native."""
from uuid import uuid4
from django import forms
from django.contrib import messages
from django.core.exceptions import ValidationError,PermissionDenied
from django.shortcuts import render,redirect
from django.views.decorators.http import require_http_methods
from django.views.decorators.cache import never_cache
from apps.core.models import Case,Evidence
from apps.core.workbench import granted
from apps.finance import ledger
from apps.finance.models import LedgerLineage
from . import factory,factory_ledger as domain
from .quickbooks_mcp import factory_read_status

class InputsForm(forms.Form):
    def __init__(self,case,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.fields['evidence_id']=forms.ModelChoiceField(queryset=Evidence.objects.filter(case=case,kind='ledger_source').order_by('-pk'),label='Exact supplied incumbent source')
        self.fields['predecessor_id']=forms.ModelChoiceField(queryset=LedgerLineage.objects.filter(case=case).order_by('-pk'),required=False,label='Exact predecessor for a correction')
    def ids(self):
        d=self.cleaned_data;return [d['evidence_id'].pk,d['predecessor_id'].pk if d['predecessor_id'] else None]

class StartForm(forms.Form):
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
            w=domain.start(request.user,d['case'].pk,d['key'],*inputs.ids(),d['revision']);return redirect('factory_detail',w.pk)
        except ValidationError as exc:form.add_error(None,domain.finding(exc))
    return render(request,'factory/ledger_start.html',{'form':form,'inputs_form':inputs,'case':form.selected})

@never_cache
@require_http_methods(['GET','HEAD','POST'])
def detail(request,work):
    from .factory_views import presentation,permitted
    data,e,body=domain.source(work,request.user,False)
    form=InputsForm(work.case,request.POST if request.method=='POST' and request.POST.get('action')=='correct' else None,initial=data)
    if request.method=='POST':
        try:
            p=request.POST;a=p.get('action');revision=int(p.get('revision','0'));case_revision=int(p.get('case_revision','0'))
            allowed={'advance':set(),'recheck':{'reason'},'restart':{'reason'},'resume':set(),'cancel':set(),'correct':{'evidence_id','predecessor_id','reason'},'observe':{'target','evidence'},'review':{'target','evidence','verdict'},'adopt_profile':{'configuration','reason'}}
            if a not in allowed or set(p)-allowed[a]-{'action','revision','case_revision','csrfmiddlewaretoken'}:raise ValidationError('Choose an exact typed incumbent command')
            if a=='advance':factory.advance(request.user,work.pk,revision)
            elif a=='restart':domain.restart(request.user,work.pk,revision,case_revision,p.get('reason',''))
            elif a=='recheck':domain.recheck(request.user,work.pk,revision,case_revision,p.get('reason',''))
            elif a in ['resume','cancel']:factory.manage(request.user,work.pk,revision,a)
            elif a=='correct':
                if not form.is_valid():raise ValidationError('Choose exact native sources')
                domain.correct(request.user,work.pk,revision,case_revision,*form.ids(),p.get('reason',''))
            elif a in ['observe','review']:domain.command(request.user,work.pk,revision,case_revision,a,int(p.get('target','0')),int(p.get('evidence','0')),p.get('verdict'))
            elif a=='adopt_profile':factory.adopt_profile(request.user,work.pk,revision,int(p.get('configuration','0')),p.get('reason',''))
            messages.success(request,'Native incumbent reference work updated');return redirect(request.get_full_path())
        except (ValidationError,ValueError) as exc:messages.error(request,str(exc));work.refresh_from_db();work.case.refresh_from_db()
    row=presentation(request.user,work);w=row['ledger']['lineage'];x=w.checks.order_by('-pk').first() if w else None;can_review=False
    if x and request.user.pk not in [w.actor_id,x.actor_id]:
        try:ledger.authority(request.user,x)
        except (ValidationError,PermissionDenied):pass
        else:can_review=True
    active=not work.cancel_requested and work.status not in ['cancelled','followup_needed']
    return render(request,'factory/ledger_detail.html',{'row':row,'case':work.case,'inputs_form':form,'check':x,'can_review':active and can_review,'can_observe':active and w is not None and permitted(request.user,work,'ledger.verify'),'observations':Evidence.objects.filter(case=work.case,kind='quickbooks_verification').order_by('-pk'),'review_evidence':Evidence.objects.filter(case=work.case,kind__in=['finance_review','policy_decision']).order_by('-pk'),'decisions':x.decisions.order_by('-pk') if x else [],'activities':work.activities.order_by('pk'),'can_restart':work.status=='cancelled' and permitted(request.user,work,'factory.manage'),'can_correct':active and permitted(request.user,work,'factory.manage'),'can_configure':permitted(request.user,work,'policy.configure'),'mcp_read':factory_read_status(request.user,work)})

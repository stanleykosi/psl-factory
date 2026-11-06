"""Primary asset work console; native services own every decision and result."""
from uuid import uuid4
from django import forms
from django.contrib import messages
from django.core.exceptions import ValidationError,PermissionDenied
from django.shortcuts import render,redirect
from django.views.decorators.http import require_http_methods
from django.views.decorators.cache import never_cache
from apps.core.models import Case,Evidence
from apps.core.workbench import granted
from apps.finance import ppe
from apps.finance.models import ScheduleWork,FinanceRun
from . import factory,factory_ppe as domain

class InputsForm(forms.Form):
    def __init__(self,case,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.fields['register_id']=forms.ModelChoiceField(queryset=ScheduleWork.objects.filter(case=case,kind='ppe_register').order_by('-pk'),label='Exact supplied register')
        self.fields['prior_id']=forms.ModelChoiceField(queryset=ScheduleWork.objects.filter(case=case,kind='ppe_schedule').order_by('-pk'),required=False,label='Prior approved schedule')
        self.fields['ledger_id']=forms.ModelChoiceField(queryset=FinanceRun.objects.filter(case=case,kind='mapping').order_by('-pk'),required=False,label='Exact read-only accounting note')
    def ids(self):return [self.cleaned_data[k].pk if self.cleaned_data[k] else None for k in ['register_id','prior_id','ledger_id']]

class StartForm(forms.Form):
    definition=forms.CharField(initial=domain.DEFINITION,widget=forms.HiddenInput)
    key=forms.CharField(max_length=100,widget=forms.HiddenInput)
    case=forms.ModelChoiceField(queryset=Case.objects.none())
    reference=forms.RegexField(r'^[A-Za-z0-9][A-Za-z0-9_.:-]{0,99}$',label='Stable schedule reference')
    revision=forms.IntegerField(min_value=1,widget=forms.HiddenInput)
    def __init__(self,actor,*args,case_id=None,**kwargs):
        super().__init__(*args,**kwargs);cases=granted(actor,['factory.start','finance.read','ppe.read','evidence.add']);self.fields['case'].queryset=cases
        self.selected=cases.filter(pk=case_id).first() if case_id else None
        if self.selected:self.fields['case'].initial=self.selected;self.fields['revision'].initial=self.selected.revision
        if not self.is_bound:self.fields['key'].initial='PPE-'+uuid4().hex

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
            if d['definition']!=domain.DEFINITION or set(request.POST)-set(form.fields)-set(inputs.fields)-{'csrfmiddlewaretoken'}:raise ValidationError('Exact typed PPE command required')
            w=domain.start(request.user,d['case'].pk,d['key'],*inputs.ids(),d['reference'],d['revision']);return redirect('factory_detail',w.pk)
        except ValidationError as exc:form.add_error(None,domain.finding(exc))
    return render(request,'factory/ppe_start.html',{'form':form,'inputs_form':inputs,'case':form.selected})

@never_cache
@require_http_methods(['GET','HEAD','POST'])
def detail(request,work):
    from .factory_views import presentation,permitted
    ppe.readable(request.user,work.case);r,data=domain.source(work,request.user,False)
    form=InputsForm(work.case,request.POST if request.method=='POST' and request.POST.get('action')=='correct' else None,initial=data)
    if request.method=='POST':
        try:
            p=request.POST;a=p.get('action');revision=int(p.get('revision','0'));case_revision=int(p.get('case_revision','0'))
            allowed={'advance':set(),'resume':set(),'cancel':set(),'restart':{'reason'},'correct':{'register_id','prior_id','ledger_id','reason'},'review':{'target','purpose','verdict','evidence','note'},'adopt_profile':{'configuration','reason'}}
            if a not in allowed or set(p)-allowed[a]-{'action','revision','case_revision','csrfmiddlewaretoken'}:raise ValidationError('Choose an exact typed PPE command')
            if a=='advance':factory.advance(request.user,work.pk,revision)
            elif a in ['resume','cancel']:factory.manage(request.user,work.pk,revision,a)
            elif a=='correct':
                if not form.is_valid():raise ValidationError('Choose exact native sources')
                domain.correct(request.user,work.pk,revision,case_revision,*form.ids(),p.get('reason',''))
            elif a=='restart':domain.restart(request.user,work.pk,revision,case_revision,p.get('reason',''))
            elif a=='review':domain.review(request.user,work.pk,revision,case_revision,int(p.get('target','0')),p.get('purpose',''),p.get('verdict',''),int(p.get('evidence','0')),p.get('note',''))
            elif a=='adopt_profile':factory.adopt_profile(request.user,work.pk,revision,int(p.get('configuration','0')),p.get('reason',''))
            messages.success(request,'Native PPE work updated');return redirect(request.get_full_path())
        except (ValidationError,ValueError) as exc:messages.error(request,str(exc));work.refresh_from_db();work.case.refresh_from_db()
    row=presentation(request.user,work);s=row['ppe']['schedule'];reviews=[]
    candidates=[] if work.cancel_requested or work.status in ['cancelled','followup_needed'] else [(r,['register','basis'] if r.result['date_basis_ambiguous'] else ['register']),(s,['schedule'])]
    for target,purposes in candidates:
        if not target:continue
        for purpose in purposes:
            try:ppe.authority(request.user,target,purpose)
            except (ValidationError,PermissionDenied):continue
            reviews.append({'target':target.pk,'purpose':purpose})
    return render(request,'factory/ppe_detail.html',{'row':row,'case':work.case,'inputs_form':form,'reviews':reviews,'review_evidence':Evidence.objects.filter(case=work.case,kind__in=['finance_review','ppe_basis_explanation']).order_by('-pk'),'activities':work.activities.order_by('pk'),'can_correct':permitted(request.user,work,'factory.manage') and not work.cancel_requested,'can_restart':work.status=='cancelled' and permitted(request.user,work,'factory.manage'),'can_configure':permitted(request.user,work,'policy.configure')})

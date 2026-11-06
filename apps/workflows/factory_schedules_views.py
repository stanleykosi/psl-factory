"""Primary selected schedule work console; native services own every decision and result."""
from uuid import uuid4
from django import forms
from django.contrib import messages
from django.core.exceptions import ValidationError,PermissionDenied
from django.shortcuts import render,redirect
from django.views.decorators.http import require_http_methods
from django.views.decorators.cache import never_cache
from apps.core.models import Case,Evidence
from apps.core.workbench import granted
from apps.finance import schedules
from apps.finance.models import ScheduleWork,FinanceRun
from . import factory,factory_schedules as domain

class InputsForm(forms.Form):
    kind=forms.ChoiceField(choices=[('income','Income detail'),('inventory','Selected schedule inventory')])
    payload=forms.JSONField(required=False,widget=forms.Textarea,label='Exact supplied income detail JSON (leave blank for inventory)')
    def __init__(self,case,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.fields['parent_id']=forms.ModelChoiceField(queryset=FinanceRun.objects.filter(case=case,kind='mapping').order_by('-pk'),required=False,label='Exact mapping note (income only)')
        self.fields['evidence_id']=forms.ModelChoiceField(queryset=Evidence.objects.filter(case=case,kind__in=['income_detail','schedule_inventory']).order_by('-pk'),label='Exact supplied evidence')
    def ids(self):
        d=self.cleaned_data
        return [d['kind'],d['parent_id'].pk if d['parent_id'] else None,d['evidence_id'].pk,d['payload']]

class StartForm(forms.Form):
    definition=forms.CharField(initial=domain.DEFINITION,widget=forms.HiddenInput)
    key=forms.CharField(max_length=100,widget=forms.HiddenInput)
    case=forms.ModelChoiceField(queryset=Case.objects.none())
    reference=forms.RegexField(r'^[A-Za-z0-9][A-Za-z0-9_.:-]{0,99}$',label='Stable schedule reference')
    revision=forms.IntegerField(min_value=1,widget=forms.HiddenInput)
    def __init__(self,actor,*args,case_id=None,**kwargs):
        super().__init__(*args,**kwargs);cases=granted(actor,['factory.start','finance.read','schedules.read','evidence.add']);self.fields['case'].queryset=cases
        self.selected=cases.filter(pk=case_id).first() if case_id else None
        if self.selected:self.fields['case'].initial=self.selected;self.fields['revision'].initial=self.selected.revision
        if not self.is_bound:self.fields['key'].initial='schedule-'+uuid4().hex

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
            if d['definition']!=domain.DEFINITION or set(request.POST)-set(form.fields)-set(inputs.fields)-{'csrfmiddlewaretoken'}:raise ValidationError('Exact typed schedule command required')
            w=domain.start(request.user,d['case'].pk,d['key'],*inputs.ids(),d['reference'],d['revision']);return redirect('factory_detail',w.pk)
        except ValidationError as exc:form.add_error(None,domain.finding(exc))
    return render(request,'factory/schedules_start.html',{'form':form,'inputs_form':inputs,'case':form.selected})

@never_cache
@require_http_methods(['GET','HEAD','POST'])
def detail(request,work):
    from .factory_views import presentation,permitted
    schedules.readable(request.user,work.case);data,e,parent,body=domain.source(work,request.user,False)
    initial=dict(data)
    if not permitted(request.user,work,'schedules.report'):initial['payload']=None
    form=InputsForm(work.case,request.POST if request.method=='POST' and request.POST.get('action')=='correct' else None,initial=initial)
    if request.method=='POST':
        try:
            p=request.POST;a=p.get('action');revision=int(p.get('revision','0'));case_revision=int(p.get('case_revision','0'))
            allowed={'advance':set(),'resume':set(),'cancel':set(),'restart':{'reason'},'correct':{'kind','parent_id','evidence_id','payload','reason'},'review':{'target','verdict','evidence','note'},'export':{'target','kind','evidence'},'adopt_profile':{'configuration','reason'}}
            if a not in allowed or set(p)-allowed[a]-{'action','revision','case_revision','csrfmiddlewaretoken'}:raise ValidationError('Choose an exact typed schedule command')
            if a=='advance':factory.advance(request.user,work.pk,revision)
            elif a in ['resume','cancel']:factory.manage(request.user,work.pk,revision,a)
            elif a=='correct':
                if not form.is_valid():raise ValidationError('Choose exact native sources')
                domain.correct(request.user,work.pk,revision,case_revision,*form.ids(),p.get('reason',''))
            elif a=='restart':domain.restart(request.user,work.pk,revision,case_revision,p.get('reason',''))
            elif a=='review':domain.review(request.user,work.pk,revision,case_revision,int(p.get('target','0')),p.get('verdict',''),int(p.get('evidence','0')),p.get('note',''))
            elif a=='export':domain.export(request.user,work.pk,revision,case_revision,int(p.get('target','0')),p.get('kind',''),int(p.get('evidence','0')))
            elif a=='adopt_profile':factory.adopt_profile(request.user,work.pk,revision,int(p.get('configuration','0')),p.get('reason',''))
            messages.success(request,'Native schedule work updated');return redirect(request.get_full_path())
        except (ValidationError,ValueError) as exc:messages.error(request,str(exc));work.refresh_from_db();work.case.refresh_from_db()
    row=presentation(request.user,work);s=row['schedules']['schedule'];reviews=[]
    if s and not work.cancel_requested and work.status not in ['cancelled','followup_needed']:
        try:schedules.authority(request.user,s)
        except (ValidationError,PermissionDenied):pass
        else:reviews.append({'target':s.pk})
    return render(request,'factory/schedules_detail.html',{'row':row,'case':work.case,'inputs_form':form,'reviews':reviews,'review_evidence':Evidence.objects.filter(case=work.case,kind='finance_review').order_by('-pk'),'adjustment_evidence':Evidence.objects.filter(case=work.case,kind='finance_adjustment').order_by('-pk'),'can_export':s is not None and s.kind=='income' and permitted(request.user,work,'schedules.adjust') and permitted(request.user,work,'finance.adjust'),'activities':work.activities.order_by('pk'),'can_correct':permitted(request.user,work,'factory.manage') and not work.cancel_requested and (work.request['kind']!='income' or permitted(request.user,work,'schedules.report')),'can_restart':work.status=='cancelled' and permitted(request.user,work,'factory.manage'),'can_configure':permitted(request.user,work,'policy.configure')})

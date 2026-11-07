"""Exact P44 intake, owned human decisions and controlled communication review."""
from uuid import uuid4
from django import forms
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import render,redirect
from django.views.decorators.http import require_http_methods
from django.views.decorators.cache import never_cache
from apps.core.models import Case
from apps.core.workbench import granted
from apps.documents.models import Template
from apps.pmo.models import EscalationRequest
from . import factory,factory_escalation as domain

class InputsForm(forms.Form):
    def __init__(self,case,*args,issue_id=None,**kwargs):
        super().__init__(*args,**kwargs)
        rows=EscalationRequest.objects.filter(profile__state__issue__case=case).select_related('profile__state__issue')
        if issue_id:rows=rows.filter(profile__state__issue_id=issue_id)
        self.fields['request_id']=forms.ModelChoiceField(queryset=rows.order_by('-pk'),label='Exact native request and source profile')
        self.fields['request_id'].label_from_instance=lambda r:f'{r.profile.state.issue.reference} · {r.direction} to {r.target} · request {r.pk}, profile {r.profile_id}'
        self.fields['template_id']=forms.ModelChoiceField(queryset=Template.objects.filter(case=case,definition__document_type__in=['status_report','project_artifact']),required=False,label='Controlled communication template')
    def ids(self):return [self.cleaned_data['request_id'].pk,self.cleaned_data['template_id'].pk if self.cleaned_data['template_id'] else None]

class StartForm(forms.Form):
    definition=forms.CharField(initial=domain.DEFINITION,widget=forms.HiddenInput)
    key=forms.CharField(max_length=100,widget=forms.HiddenInput)
    case=forms.ModelChoiceField(queryset=Case.objects.none())
    reference=forms.CharField(max_length=160,label='Communication work description')
    revision=forms.IntegerField(min_value=1,widget=forms.HiddenInput)
    def __init__(self,actor,*args,case_id=None,**kwargs):
        super().__init__(*args,**kwargs);cases=granted(actor,['issue.read','factory.start','evidence.add']);self.fields['case'].queryset=cases
        self.selected=cases.filter(pk=case_id).first() if case_id else None
        if self.selected:self.fields['case'].initial=self.selected;self.fields['revision'].initial=self.selected.revision
        if not self.is_bound:self.fields['key'].initial='ESCALATION-'+uuid4().hex

@never_cache
@require_http_methods(['GET','HEAD','POST'])
def create(request):
    data=request.POST if request.method=='POST' else None
    try:form=StartForm(request.user,data,case_id=request.POST.get('case') if data else request.GET.get('case'))
    except (ValueError,ValidationError):form=StartForm(request.user,{});form.is_valid();form.add_error(None,'Choose an accessible case')
    inputs=InputsForm(form.selected,data) if form.selected else None
    if request.method=='POST' and form.is_valid() and inputs and inputs.is_valid():
        try:
            d=form.cleaned_data
            if d['definition']!=domain.DEFINITION:raise ValidationError('Choose the registered escalation definition')
            w=domain.start(request.user,d['case'].pk,d['key'],*inputs.ids(),d['reference'],d['revision']);return redirect('factory_detail',w.pk)
        except ValidationError as exc:form.add_error(None,domain.finding(exc))
    return render(request,'factory/escalation_start.html',{'form':form,'inputs_form':inputs,'case':form.selected})

@never_cache
@require_http_methods(['GET','HEAD','POST'])
def detail(request,work):
    from .factory_views import presentation,permitted
    r,data=domain.source(work,request.user,False)
    form=InputsForm(work.case,request.POST if request.method=='POST' and request.POST.get('action')=='correct' else None,issue_id=r.profile.state.issue_id,initial=data)
    if request.method=='POST':
        try:
            p=request.POST;action=p.get('action');revision=int(p.get('revision','0'));case_revision=int(p.get('case_revision','0'))
            if action=='advance':factory.advance(request.user,work.pk,revision)
            elif action=='correct':
                if not form.is_valid():raise ValidationError(form.errors.as_text())
                domain.correct(request.user,work.pk,revision,case_revision,*form.ids(),p.get('reason',''))
            elif action=='decision':domain.decide(request.user,work.pk,revision,case_revision,int(p.get('request','0')),p.get('role',''),p.get('verdict',''),p.get('note',''),p.get('delegated')=='on')
            elif action=='review':domain.review(request.user,work.pk,revision,case_revision,int(p.get('version','0')),p.get('verdict',''),p.get('note',''))
            elif action=='cancel':domain.cancel(request.user,work.pk,revision)
            elif action=='resume':factory.manage(request.user,work.pk,revision,'resume')
            elif action=='reconcile':domain.reconcile(request.user,work.pk,revision)
            elif action=='operate_delivery':domain.operate(request.user,work.pk,revision,case_revision,int(p.get('job','0')),p.get('operation',''),p.get('reason',''))
            elif action=='adopt_profile':factory.adopt_profile(request.user,work.pk,revision,int(p.get('configuration','0')),p.get('reason',''))
            else:raise ValidationError('Choose an explicit current action')
            messages.success(request,'Communication action recorded. Issue resolution remains separate.');return redirect(request.get_full_path())
        except (ValidationError,ValueError) as exc:messages.error(request,str(exc));work.refresh_from_db();work.case.refresh_from_db()
    row=presentation(request.user,work)
    return render(request,'factory/escalation_detail.html',{'row':row,'case':work.case,'inputs_form':form,'can_configure':permitted(request.user,work,'policy.configure'),'activities':work.activities.order_by('pk')})

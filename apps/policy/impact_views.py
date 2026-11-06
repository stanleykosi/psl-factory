from django import forms
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError,PermissionDenied
from django.shortcuts import get_object_or_404,render,redirect
from apps.core.models import Case,Evidence
from adapters import policy_impact as adapter
from . import impact
from .scopes import authorized
from .models import Configuration,ImpactAssessment
from .scope_views import ConfigurationChoice


def choices(actor,case):
    result=[]
    for key in adapter.REGISTRY:
        try:adapter.authorize(actor,case,key)
        except PermissionDenied:continue
        result.append((key,key))
    return result


class CaptureForm(forms.Form):
    previous=ConfigurationChoice(queryset=Configuration.objects.none(),label='Affected local policy')
    successor=ConfigurationChoice(queryset=Configuration.objects.none(),label='Currently active local successor')
    adapters=forms.MultipleChoiceField(choices=[],widget=forms.CheckboxSelectMultiple)
    evidence=forms.ModelChoiceField(queryset=Evidence.objects.none(),label='Review evidence')
    reason=forms.CharField(max_length=2000,widget=forms.Textarea)

    def __init__(self,actor,case,*args,**kwargs):
        super().__init__(*args,**kwargs)
        for name in ['previous','successor']:
            self.fields[name].queryset=Configuration.objects.filter(case=case,scope_source__isnull=True).order_by('-pk')
        self.fields['evidence'].queryset=Evidence.objects.filter(case=case,kind='policy_decision')
        self.fields['adapters'].choices=choices(actor,case)


class ReviewForm(forms.Form):
    verdict=forms.ChoiceField(choices=[('accept','Accept engineering reassessment'),('reject','Reject'),('defer','Defer')])
    evidence=forms.ModelChoiceField(queryset=Evidence.objects.none())
    reason=forms.CharField(max_length=2000,widget=forms.Textarea)
    def __init__(self,case,*args,**kwargs):
        super().__init__(*args,**kwargs);self.fields['evidence'].queryset=Evidence.objects.filter(case=case,kind='policy_decision')


@login_required
def workbench(request,case_id):
    case=impact.context(request.user,case_id)
    form=CaptureForm(request.user,case,request.POST if request.method=='POST' else None)
    error=None
    if request.method=='POST' and form.is_valid():
        v=form.cleaned_data
        try:
            row=impact.capture(request.user,case.pk,v['previous'].pk,v['successor'].pk,v['adapters'],v['evidence'].pk,v['reason'])
            return redirect('policy_impact_assessment',case_id=case.pk,pk=row.pk)
        except ValidationError as exc:error=str(exc)
    # IDs and local policy links only; inspect enforces each stored domain/source permission again.
    records=ImpactAssessment.objects.filter(previous__case=case).order_by('-pk')[:100]
    response=render(request,'policy_impact.html',dict(case=case,form=form,error=error,records=records,uncovered=adapter.UNCOVERED))
    response['Cache-Control']='no-store';return response


@login_required
def assessment(request,case_id,pk):
    case=impact.context(request.user,case_id);get_object_or_404(ImpactAssessment,pk=pk,previous__case=case)
    report=impact.inspect(request.user,case.pk,pk);form=ReviewForm(case,request.POST if request.method=='POST' else None);error=None
    if request.method=='POST' and form.is_valid():
        v=form.cleaned_data
        try:
            impact.review(request.user,case.pk,pk,v['verdict'],v['evidence'].pk,v['reason'])
            return redirect('policy_impact_assessment',case_id=case.pk,pk=pk)
        except ValidationError as exc:error=str(exc)
    response=render(request,'policy_impact_assessment.html',dict(case=case,report=report,form=form,error=error))
    response['Cache-Control']='no-store';return response


@login_required
def records(request,case_id,configuration_id,key):
    case=impact.context(request.user,case_id);get_object_or_404(Configuration,case=case,pk=configuration_id)
    error=None;report=None
    try:report=impact.page(request.user,case.pk,configuration_id,key,request.GET.get('cursor'))
    except ValidationError as exc:error=str(exc)
    response=render(request,'policy_impact_records.html',dict(case=case,report=report,error=error))
    response['Cache-Control']='no-store';return response


@login_required
def investigation(request,case_id,pk):
    from apps.agents.policy_impact import investigate
    case=impact.context(request.user,case_id);get_object_or_404(ImpactAssessment,pk=pk,previous__case=case)
    response=render(request,'policy_impact_investigation.html',dict(case=case,report=investigate(request.user,case.pk,pk)))
    response['Cache-Control']='no-store';return response

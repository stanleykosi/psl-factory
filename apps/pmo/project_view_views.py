import json
from django import forms
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import Http404,JsonResponse
from django.shortcuts import render,redirect
from django.utils import timezone
from apps.core.models import Case
from apps.core.views import accessible_case
from apps.core.workbench import active
from apps.identity.services import require
from apps.policy.operator_drafts import draft_operator_policy
from apps.policy.project_view_validators import COMPONENT,VALUE
from . import project_view as d

@login_required
def index(request):
    response=render(request,'pmo/project_views.html',{'rows':d.discover(request.user)})
    response['Cache-Control']='no-store';return response

@login_required
def audience(request,case_id,key):
    active(request.user)
    case=Case.objects.filter(pk=case_id,grant__user=request.user,grant__active=True,grant__action='project.view').first()
    if not case:raise Http404
    try:
        if request.GET.get('inspect')=='1':
            from apps.agents.project_view import investigate
            return JsonResponse(investigate(request.user,case.pk,key),headers={'Cache-Control':'no-store'})
        value=d.projection(request.user,case.pk,key)
        from apps.identity.models import Grant
        response=render(request,'pmo/project_view.html',{'projection':value,'can_inspect':Grant.objects.filter(case=case,user=request.user,action='agent.project_view',active=True).exists(),'case_id':str(case.pk),'audience':key})
    except ValidationError as exc:
        response=render(request,'pmo/project_view.html',{'case_id':str(case.pk),'audience':key,'hold':str(exc)},status=409)
    response['Cache-Control']='no-store';return response

@login_required
def configuration(request,case_id):
    case=accessible_case(request.user,case_id);require(request.user,case,'policy.read')
    class Criteria(forms.Form):
        content=forms.JSONField(widget=forms.Textarea)
        evidence=forms.ModelChoiceField(case.evidence.filter(kind='policy_decision'))
    form=Criteria(request.POST if request.method=='POST' else None)
    if request.method=='POST':
        require(request.user,case,'policy.configure')
        if form.is_valid():
            try:
                draft_operator_policy(request.user,case.pk,COMPONENT,form.cleaned_data['content'],form.cleaned_data['evidence'].pk,timezone.now())
                return redirect('case',case_id=case.pk)
            except ValidationError as exc:form.add_error(None,str(exc))
    response=render(request,'pmo/project_view_configuration.html',{'case':case,'form':form,'schema':json.dumps(VALUE,indent=2)})
    response['Cache-Control']='no-store';return response

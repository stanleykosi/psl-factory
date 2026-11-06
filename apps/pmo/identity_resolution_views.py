import json
from django import forms
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import render,redirect
from django.http import JsonResponse
from django.utils import timezone
from apps.core.views import accessible_case
from apps.core.evidence_access import public_evidence
from apps.identity.models import Grant
from apps.identity.services import visible_cases,require
from apps.policy.identity_resolution_validators import COMPONENT,VALUE
from apps.policy.document_validators import ROLES
from apps.policy.operator_drafts import draft_operator_policy
from apps.policy.services import resolve as policy_status
from . import identity_resolution as d

@login_required
def workbench(request,case_id):
    c=accessible_case(request.user,case_id);d.readable(request.user,c)
    others=visible_cases(request.user).filter(kind='project',tenant=c.tenant,synthetic=c.synthetic).exclude(pk=c.pk).filter(pk__in=Grant.objects.filter(user=request.user,active=True,action='engagement.read').values('case_id'))
    selected_id=request.POST.get('other_case_id') if request.method=='POST' else request.GET.get('other_case')
    try:other=others.filter(pk=selected_id).first() if selected_id else None
    except (ValidationError,ValueError):other=None
    class Selection(forms.Form):other_case=forms.ModelChoiceField(others,required=False)
    selection=Selection(initial={'other_case':other})
    own=public_evidence(c.evidence.all()).filter(kind__in=['engagement_source','engagement_assignment','engagement_registration','product_input','rfp_outcome','plan'])
    other_proofs=public_evidence(other.evidence.all()).filter(kind__in=['engagement_source','engagement_assignment','engagement_registration','product_input','rfp_outcome','plan']) if other else own.none()
    class DecisionForm(forms.Form):
        other_case_id=forms.UUIDField(widget=forms.HiddenInput)
        relation=forms.ChoiceField(choices=[('unresolved','Still unresolved'),('distinct','Distinct engagement'),('alias','Source is an identity alias of the target')])
        role=forms.ChoiceField(choices=[(r,r) for r in ROLES])
        evidence_id=forms.ModelChoiceField(own)
        other_evidence_id=forms.ModelChoiceField(other_proofs)
        reason=forms.CharField(max_length=1000,widget=forms.Textarea)
        key=forms.CharField(max_length=100)
    class PolicyForm(forms.Form):
        content=forms.JSONField(widget=forms.Textarea)
        evidence_id=forms.ModelChoiceField(c.evidence.filter(kind='policy_decision'))
    action=request.POST.get('action')
    form=DecisionForm(request.POST if request.method=='POST' and action=='resolve' else None,initial={'other_case_id':other.pk if other else None})
    policy=PolicyForm(request.POST if request.method=='POST' and action=='policy' else None)
    grants=set(Grant.objects.filter(case=c,user=request.user,active=True).values_list('action',flat=True))
    try:
        if request.method=='POST' and action=='resolve' and form.is_valid():
            if other is None:raise ValidationError('Choose an authorized target engagement')
            v={k:(x.pk if hasattr(x,'pk') else x) for k,x in form.cleaned_data.items()}
            d.resolve(request.user,c.pk,**v);messages.success(request,'Human identity finding recorded; no case records or access were transferred.')
            return redirect('identity_resolution',case_id=c.pk)
        if request.method=='POST' and action=='policy' and policy.is_valid():
            draft_operator_policy(request.user,c.pk,COMPONENT,policy.cleaned_data['content'],policy.cleaned_data['evidence_id'].pk,timezone.now())
            messages.success(request,'Identity criteria draft recorded; validate and activate through the policy workbench.')
            return redirect('identity_resolution',case_id=c.pk)
        if request.method=='POST' and action=='investigate':
            require(request.user,c,'agent.engagement')
            return JsonResponse(d.report(request.user,c.pk),headers={'Cache-Control':'no-store'})
    except ValidationError as exc:(policy if action=='policy' else form).add_error(None,str(exc))
    response=render(request,'pmo/identity_resolution.html',{'case':c,'other':other,'selection':selection,'form':form,'policy_form':policy,'grants':grants,'schema':json.dumps(VALUE,indent=2),'policy_status':policy_status(COMPONENT,c).status,'result':d.report(request.user,c.pk)})
    response['Cache-Control']='no-store';return response

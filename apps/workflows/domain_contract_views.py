import json
from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import render,redirect,get_object_or_404
from django.utils import timezone
from apps.core.views import accessible_case
from apps.core.services import add_evidence
from apps.policy.operator_drafts import draft_operator_policy
from apps.policy.domain_contract_validators import COMPONENT,VALUE
from apps.policy.services import resolve
from apps.agents import domain_contracts as agent
from . import domain_contracts as d

def commands(case,data=None):
    contracts=d.Contract.objects.filter(plan__case=case).order_by('-pk')
    definitions={
      'evidence':('Record source-owned contract evidence',{'body':forms.CharField(max_length=4000,widget=forms.Textarea),'source':forms.CharField(max_length=500)}),
      'capture':('Capture versioned provider or destination contract',{
          'plan':forms.ModelChoiceField(d.d.Plan.objects.filter(case=case)),
          'reference':forms.CharField(max_length=100),'kind':forms.ChoiceField(choices=[('provider','Provider receipt'),('destination','Destination preflight')]),
          'payload':forms.JSONField(widget=forms.Textarea),'evidence':forms.ModelChoiceField(case.evidence.filter(kind='integration_contract')),
          'predecessor':forms.ModelChoiceField(contracts,required=False)}),
      'policy':('Draft domain contract criteria',{'content':forms.JSONField(widget=forms.Textarea),'evidence':forms.ModelChoiceField(case.evidence.filter(kind='policy_decision'))}),
      'review':('Independently review contract or observation',{'contract':forms.ModelChoiceField(contracts),
          'observation':forms.ModelChoiceField(d.Observation.objects.filter(contract__plan__case=case),required=False),
          'verdict':forms.ChoiceField(choices=[('approve','Approve exact evidence'),('hold','Hold')]),
          'rationale':forms.CharField(max_length=1000,widget=forms.Textarea),'operation_key':forms.CharField(max_length=100)}),
      'probe':('Verify domain receipt or preflight destination',{'contract':forms.ModelChoiceField(contracts),'operation_key':forms.CharField(max_length=100),'effect_key':forms.CharField(max_length=64,required=False)}),
      'investigate':('Investigate current contracts and prerequisites',{'contract':forms.ModelChoiceField(contracts)}),
    }
    return [(action,label,type('DomainContractCommand',(forms.Form,),{'action':forms.CharField(initial=action,widget=forms.HiddenInput),**fields})(data if data and data.get('action')==action else None)) for action,(label,fields) in definitions.items()]

@login_required
@transaction.atomic
def workbench(request,case_id):
    case=accessible_case(request.user,case_id);d.d.access(request.user,case,locked=request.method=='GET')
    forms_list=commands(case,request.POST if request.method=='POST' else None)
    if request.method=='POST':
        try:
            form=next((f for action,_,f in forms_list if action==request.POST.get('action')),None)
            if form is None or not form.is_valid():raise ValidationError('Valid typed command required')
            values=form.cleaned_data.copy();action=values.pop('action')
            if action=='evidence':
                d.d.access(request.user,case,'capture')
                add_evidence(request.user,case.pk,'integration_contract',values['body'],values['source'])
            elif action=='capture':
                values['plan_id']=values.pop('plan').pk;values['evidence_id']=values.pop('evidence').pk
                values['predecessor']=values['predecessor'].pk if values['predecessor'] else None
                d.capture(request.user,case.pk,**values)
            elif action=='policy':
                d.d.access(request.user,case,'configure')
                draft_operator_policy(request.user,case.pk,COMPONENT,values['content'],values['evidence'].pk,timezone.now())
            else:
                values['contract_id']=values.pop('contract').pk
                if action=='review':
                    o=values.pop('observation');values['observation_id']=o.pk if o else None
                    d.review(request.user,case.pk,**values)
                elif action=='probe':d.probe(request.user,case.pk,**values)
                else:return JsonResponse(agent.investigate(request.user,case.pk,**values),headers={'Cache-Control':'no-store'})
            messages.success(request,'Immutable contract/evidence history recorded; dependent activation remains unavailable')
            return redirect('domain_contracts',case_id=case.pk)
        except (ValidationError,ValueError,KeyError,ConnectionError):messages.error(request,'Command held: verify exact source scope, current independent criteria, supported protocol and deployment binding')
    response=render(request,'workflows/domain_contracts.html',{'case':case,'commands':forms_list,
        'policy_status':resolve(COMPONENT,case).status,'criteria_schema':json.dumps(VALUE,indent=2),
        'provider_schema':json.dumps(d.adapter.PROVIDER,indent=2),'destination_schema':json.dumps(d.adapter.DESTINATION,indent=2),
        'contracts':d.Contract.objects.filter(plan__case=case).order_by('-pk')[:50],
        'observations':d.Observation.objects.filter(contract__plan__case=case).order_by('-pk')[:50],
        'reviews':d.Review.objects.filter(contract__plan__case=case).order_by('-pk')[:50]})
    response['Cache-Control']='no-store';return response

@login_required
def report(request,case_id,contract_id):
    case=accessible_case(request.user,case_id);get_object_or_404(d.Contract,plan__case=case,pk=contract_id)
    return JsonResponse(d.report(request.user,case.pk,contract_id),headers={'Cache-Control':'no-store'})

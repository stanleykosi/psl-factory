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
from apps.policy.services import resolve
from apps.policy.operator_drafts import draft_operator_policy
from apps.policy.reconstitution_validators import COMPONENT,VALUE,DISPOSITIONS
from apps.agents import reconstitution as agent
from . import reconstitution as d


def commands(c,data=None):
    plans=d.Plan.objects.filter(case=c).order_by('-pk')
    definitions={
      'capture':('Capture complete reconstitution inventory',{'recovery':forms.ModelChoiceField(d.cold.Job.objects.filter(plan__case=c,status='confirmed')),'reference':forms.CharField(max_length=100),'profile_ref':forms.CharField(max_length=100)}),
      'policy':('Draft reconstitution criteria',{'content':forms.JSONField(widget=forms.Textarea),'evidence':forms.ModelChoiceField(c.evidence.filter(kind='policy_decision'))}),
      'reserve':('Queue receipt evidence or reviewed plan publication',{'plan':forms.ModelChoiceField(plans),'kind':forms.ChoiceField(choices=[(k,k) for k in ['receipt','publish']]),'effect_key':forms.CharField(max_length=64,initial='all'),'operation_key':forms.CharField(max_length=100)}),
      'dispose':('Record independent effect disposition',{'plan':forms.ModelChoiceField(plans),'effect_key':forms.CharField(max_length=64),'verdict':forms.ChoiceField(choices=[(k,k) for k in DISPOSITIONS]),'probe':forms.ModelChoiceField(d.Job.objects.filter(plan__case=c,kind='receipt',status='confirmed'),required=False),'rationale':forms.CharField(max_length=1000,widget=forms.Textarea),'operation_key':forms.CharField(max_length=100)}),
      'review':('Review complete inert reconstitution plan',{'plan':forms.ModelChoiceField(plans),'verdict':forms.ChoiceField(choices=[('approve','Approve reviewed plan'),('hold','Hold')]),'rationale':forms.CharField(max_length=1000,widget=forms.Textarea),'operation_key':forms.CharField(max_length=100)}),
      'retry':('Reconcile original held intent',{'job':forms.ModelChoiceField(d.Job.objects.filter(plan__case=c))}),
      'investigate':('Investigate exact effects and holds',{'plan':forms.ModelChoiceField(plans)}),
    }
    return [(action,label,type('ReconstitutionCommand',(forms.Form,),{'action':forms.CharField(initial=action,widget=forms.HiddenInput),**fields})(data if data and data.get('action')==action else None)) for action,(label,fields) in definitions.items()]


@login_required
@transaction.atomic
def workbench(request,case_id):
    c=accessible_case(request.user,case_id);d.access(request.user,c,locked=request.method=='GET')
    forms_list=commands(c,request.POST if request.method=='POST' else None)
    if request.method=='POST':
        try:
            form=next((f for action,_,f in forms_list if action==request.POST.get('action')),None)
            if form is None or not form.is_valid():raise ValidationError('Valid typed reconstitution command required')
            v=form.cleaned_data.copy();action=v.pop('action')
            if action=='capture':d.capture(request.user,c.pk,v.pop('recovery').pk,**v)
            elif action=='policy':
                d.access(request.user,c,'configure')
                draft_operator_policy(request.user,c.pk,COMPONENT,v['content'],v['evidence'].pk,timezone.now())
            elif action=='reserve':d.reserve(request.user,c.pk,v.pop('plan').pk,**v)
            elif action=='dispose':
                v['probe_id']=v.pop('probe').pk if v.get('probe') else None
                v.pop('probe',None)
                d.dispose(request.user,c.pk,v.pop('plan').pk,**v)
            elif action=='review':d.review(request.user,c.pk,v.pop('plan').pk,**v)
            elif action=='retry':d.retry(request.user,c.pk,v['job'].pk)
            else:return JsonResponse(agent.investigate(request.user,c.pk,v['plan'].pk),headers={'Cache-Control':'no-store'})
            messages.success(request,'Reconstitution history recorded; no archived business job dispatched')
            return redirect('reconstitution',case_id=c.pk)
        except (ValidationError,ValueError,KeyError):messages.error(request,'Command held: check current criteria, exact scope, receipt evidence and independent decisions')
    d.access(request.user,c)
    response=render(request,'workflows/reconstitution.html',{'case':c,'commands':forms_list,'schema':json.dumps(VALUE,indent=2),
        'policy_status':resolve(COMPONENT,c).status,'plans':d.Plan.objects.filter(case=c).order_by('-pk')[:20],'jobs':d.Job.objects.filter(plan__case=c).order_by('-pk')[:50],
        'dispositions':d.Disposition.objects.filter(plan__case=c).select_related('plan').order_by('-pk')[:50],
        'reviews':d.Review.objects.filter(plan__case=c).select_related('plan').order_by('-pk')[:30]})
    response['Cache-Control']='no-store';return response


@login_required
def report(request,case_id,plan_id):
    c=accessible_case(request.user,case_id);get_object_or_404(d.Plan,case=c,pk=plan_id)
    return JsonResponse(d.report(request.user,c.pk,plan_id),headers={'Cache-Control':'no-store'})

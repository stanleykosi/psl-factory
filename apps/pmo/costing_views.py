from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import JsonResponse,Http404
from django.shortcuts import render,redirect
from django.utils import timezone
from apps.core.views import accessible_case
from apps.identity.models import Grant
from apps.finance.forms import CommandForm
from apps.policy.services import resolve
from apps.policy.costing_validators import COMPONENT,SCHEMAS
from apps.policy.costing_drafts import draft_costing_policy
from apps.agents.costing import investigate
from apps.agents.models import AgentRun
from adapters.costing import RULE,ORACLE,VALUE,ARRAY
from . import costing as d
from .costing_models import CostingRule,CostingOracle,CostingReview,CostingRun,CostingBinding,CostingAF13Binding

def commands(a,c,data=None):
    grants=set(Grant.objects.filter(case=c,user=a,active=True).values_list('action',flat=True))
    def ev(kind):return forms.ModelChoiceField(c.evidence.filter(kind=kind))
    integer=lambda:forms.IntegerField(min_value=1)
    defs={
      'rule':('Capture calculator contract version','costing.capture',{'reference':forms.CharField(max_length=100),'evidence':ev('p14_rule'),'predecessor':forms.IntegerField(required=False,min_value=1)}),
      'oracle':('Capture independent normal and exception examples','costing.oracle.capture',{'rule':forms.ModelChoiceField(CostingRule.objects.filter(case=c)),'reference':forms.CharField(max_length=100),'evidence':ev('p14_oracle'),'predecessor':forms.IntegerField(required=False,min_value=1)}),
      'rule_review':('Confirm, dispute or withdraw rule source','costing.rule.review',{'rule':forms.ModelChoiceField(CostingRule.objects.filter(case=c)),'verdict':forms.ChoiceField(choices=[(x,x) for x in ['confirm','dispute','withdraw']]),'operation_key':forms.CharField(max_length=100),'evidence':ev('p14_review')}),
      'oracle_review':('Independently validate exact oracle','costing.oracle.review',{'rule':forms.ModelChoiceField(CostingRule.objects.filter(case=c)),'oracle':forms.ModelChoiceField(CostingOracle.objects.filter(rule__case=c)),'verdict':forms.ChoiceField(choices=[(x,x) for x in ['confirm','dispute','withdraw']]),'operation_key':forms.CharField(max_length=100),'evidence':ev('p14_review')}),
      'policy':('Draft original structured P14 configuration','policy.configure',{'content':forms.JSONField(widget=forms.Textarea),'evidence':ev('policy_decision'),'effective_from':forms.DateTimeField(initial=timezone.now)}),
      'calculate':('Calculate exact plan and estimate inputs','costing.calculate',{'plan':ev('plan'),'engineering':ev('engineering_estimate'),'security':ev('security_estimate'),'inputs':ev('p14_inputs'),'operation_key':forms.CharField(max_length=100)}),
      'bind':('Create cost evidence for existing case approvals','costing.bind',{'run':forms.ModelChoiceField(CostingRun.objects.filter(case=c))}),
      'af13':('Bind local calculation and oracle to reviewed P14 package','costing.af13.bind',{'run':forms.ModelChoiceField(CostingRun.objects.filter(case=c)),'package':forms.ModelChoiceField(c.validationpackage_set.all())}),
      'investigate':('Investigate rule and independent oracle gaps','agent.costing',{})}
    return [{'title':title,'form':type('P14'+k,(CommandForm,),fields)(data if data is not None and data.get('action')==k else None,initial={'action':k,'revision':c.revision},auto_id='id_'+k+'_%s')} for k,(title,permission,fields) in defs.items() if permission in grants and (k=='investigate' or 'costing.source.read' in grants)]

@login_required
def workbench(request,case_id):
    c=accessible_case(request.user,case_id);d.readable(request.user,c);forms=commands(request.user,c,request.POST if request.method=='POST' else None)
    if request.method=='POST':
        try:
            f=next((x['form'] for x in forms if x['form']['action'].value()==request.POST.get('action')),None)
            if not f or not f.is_valid() or set(request.POST)-set(f.fields)-{'csrfmiddlewaretoken'}:raise ValidationError('Valid permitted typed command required')
            v=f.cleaned_data;a=request.user;k=v['action'];rev=v['revision'];eid=v['evidence'].pk if v.get('evidence') else None
            if k=='rule':d.capture_rule(a,c.pk,v['reference'],eid,rev,v['predecessor'])
            elif k=='oracle':d.capture_oracle(a,c.pk,v['rule'].pk,v['reference'],eid,rev,v['predecessor'])
            elif k.endswith('_review'):d.review(a,c.pk,v['rule'].pk,v['oracle'].pk if k=='oracle_review' else None,v['verdict'],v['operation_key'],eid,rev)
            elif k=='policy':
                from django.db import transaction
                with transaction.atomic():d.locked(a,c.pk,'policy.configure',rev);draft_costing_policy(a,c.pk,v['content'],eid,v['effective_from'])
            elif k=='calculate':d.run(a,c.pk,v['plan'].pk,v['engineering'].pk,v['security'].pk,v['inputs'].pk,v['operation_key'],rev)
            elif k=='bind':d.bind(a,c.pk,v['run'].pk,rev)
            elif k=='af13':d.bind_af13(a,c.pk,v['run'].pk,v['package'].pk,rev)
            elif k=='investigate':investigate(a,c.pk,rev)
            messages.success(request,'P14 evidence history updated; no case approval, invoice or native workbook verification inferred')
        except (ValidationError,ValueError,TypeError) as exc:messages.error(request,str(exc))
        return redirect('costing',case_id=c.pk)
    response=render(request,'pmo/costing.html',{'case':c,'investigations':AgentRun.objects.filter(case=c,actor=request.user,provider='deterministic-costing-v1').order_by('-pk')[:5],'policy':resolve(COMPONENT,c),'reviews':CostingReview.objects.filter(rule__case=c).order_by('-pk')[:40],'rules':CostingRule.objects.filter(case=c).order_by('-pk')[:25],'oracles':CostingOracle.objects.filter(rule__case=c).order_by('-pk')[:25],'runs':[{'row':r,'report':d.report(request.user,c.pk,r.pk)} for r in CostingRun.objects.filter(case=c).order_by('-pk')[:25]],'bindings':CostingBinding.objects.filter(run__case=c),'af13':CostingAF13Binding.objects.filter(run__case=c),'commands':forms,'schemas':{'rule':RULE,'oracle':ORACLE,'inputs':ARRAY(VALUE,1),'policy':SCHEMAS}});response['Cache-Control']='no-store';return response

@login_required
def report(request,case_id,pk):
    c=accessible_case(request.user,case_id);return JsonResponse(d.report(request.user,c.pk,pk),headers={'Cache-Control':'no-store'})

@login_required
def source(request,case_id,kind,pk):
    c=accessible_case(request.user,case_id);d.readable(request.user,c,True)
    model=CostingRule if kind=='rule' else CostingOracle if kind=='oracle' else None
    row=model.objects.filter(**({'case':c} if kind=='rule' else {'rule__case':c}),pk=pk).first() if model else None
    if not row:raise Http404
    return JsonResponse({'id':row.pk,'payload':row.payload,'sha256':row.sha256,'native_workbook_verified':False},headers={'Cache-Control':'no-store'})

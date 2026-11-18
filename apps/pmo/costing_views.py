from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied,ValidationError
from django.contrib.auth import get_user_model
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
from adapters.costing import RULE,ORACLE,VALUE,ARRAY,calculate,compare
from . import costing as d
from .costing_models import CostingRule,CostingOracle,CostingReview,CostingRun,CostingBinding,CostingAF13Binding
from .costing_proposal_models import CostingProposal
from . import costing_proposals
from apps.policy.costing_proposal_validators import COMPONENT as PROPOSAL_REVIEW
from apps.policy.document_validators import ROLES

def commands(a,c,data=None):
    grants=set(Grant.objects.filter(case=c,user=a,active=True).values_list('action',flat=True))
    def ev(kind):return forms.ModelChoiceField(c.evidence.filter(kind=kind))
    integer=lambda:forms.IntegerField(min_value=1)
    defs={
      'proposal':('Propose a calculator change','costing.capture',{'base':forms.ModelChoiceField(CostingRule.objects.filter(case=c)), 'evidence':ev('p14_rule'), 'reason':forms.CharField(max_length=2000,widget=forms.Textarea), 'operation_key':forms.CharField(max_length=100,label='Proposal reference')}),
      'proposal_policy':('Prepare calculator reviewer settings','policy.configure',{'reviewer':forms.ModelChoiceField(get_user_model().objects.filter(is_active=True,grant__case=c,grant__action='costing.rule.review',grant__active=True).distinct(),required=False), 'role':forms.ChoiceField(choices=[('', 'Not yet chosen')]+[(role,role) for role in ROLES],required=False), 'evidence':ev('policy_decision'), 'effective_from':forms.DateTimeField(initial=timezone.now)}),
      'rule':('Record a rule version','costing.capture',{'reference':forms.CharField(max_length=100),'evidence':ev('p14_rule'),'predecessor':forms.IntegerField(required=False,min_value=1)}),
      'oracle':('Record independent worked examples','costing.oracle.capture',{'rule':forms.ModelChoiceField(CostingRule.objects.filter(case=c)),'reference':forms.CharField(max_length=100),'evidence':ev('p14_oracle'),'predecessor':forms.IntegerField(required=False,min_value=1)}),
      'rule_review':('Confirm, dispute or withdraw rule source','costing.rule.review',{'rule':forms.ModelChoiceField(CostingRule.objects.filter(case=c)),'verdict':forms.ChoiceField(choices=[(x,x) for x in ['confirm','dispute','withdraw']]),'operation_key':forms.CharField(max_length=100),'evidence':ev('p14_review')}),
      'oracle_review':('Review the independent worked examples','costing.oracle.review',{'rule':forms.ModelChoiceField(CostingRule.objects.filter(case=c)),'oracle':forms.ModelChoiceField(CostingOracle.objects.filter(rule__case=c)),'verdict':forms.ChoiceField(choices=[(x,x) for x in ['confirm','dispute','withdraw']]),'operation_key':forms.CharField(max_length=100),'evidence':ev('p14_review')}),
      'policy':('Prepare costing settings for review','policy.configure',{'content':forms.JSONField(widget=forms.Textarea),'evidence':ev('policy_decision'),'effective_from':forms.DateTimeField(initial=timezone.now)}),
      'calculate':('Calculate exact plan and estimate inputs','costing.calculate',{'plan':ev('plan'),'engineering':ev('engineering_estimate'),'security':ev('security_estimate'),'inputs':ev('p14_inputs'),'operation_key':forms.CharField(max_length=100)}),
      'bind':('Create cost evidence for existing case approvals','costing.bind',{'run':forms.ModelChoiceField(CostingRun.objects.filter(case=c))}),
      'af13':('Link calculation to owner validation','costing.af13.bind',{'run':forms.ModelChoiceField(CostingRun.objects.filter(case=c)),'package':forms.ModelChoiceField(c.validationpackage_set.all())}),
      'investigate':('Check rule and worked-example evidence','agent.costing',{})}
    return [{'title':title,'form':type('P14'+k,(CommandForm,),fields)(data if data is not None and data.get('action')==k else None,initial={'action':k,'revision':c.revision},auto_id='id_'+k+'_%s')} for k,(title,permission,fields) in defs.items() if permission in grants and (k=='investigate' or 'costing.source.read' in grants)]

@login_required
def workbench(request,case_id):
    c=accessible_case(request.user,case_id);d.readable(request.user,c);forms=commands(request.user,c,request.POST if request.method=='POST' else None)
    if request.method=='POST':
        try:
            f=next((x['form'] for x in forms if x['form']['action'].value()==request.POST.get('action')),None)
            if not f or not f.is_valid() or set(request.POST)-set(f.fields)-{'csrfmiddlewaretoken'}:raise ValidationError('Valid permitted typed command required')
            v=f.cleaned_data;a=request.user;k=v['action'];rev=v['revision'];eid=v['evidence'].pk if v.get('evidence') else None
            if k=='proposal':costing_proposals.propose(a,c.pk,v['base'].pk,eid,v['reason'],v['operation_key'],rev)
            elif k=='proposal_policy':
                from apps.policy.operator_drafts import draft_operator_policy
                from django.db import transaction
                with transaction.atomic():
                    d.locked(a,c.pk,'policy.configure',rev)
                    draft_operator_policy(a,c.pk,PROPOSAL_REVIEW,{'reviewer_id':v['reviewer'].pk if v['reviewer'] else None,'reviewer_role':v['role'] or None,'independent_review':True},eid,v['effective_from'])
            elif k=='rule':d.capture_rule(a,c.pk,v['reference'],eid,rev,v['predecessor'])
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
    response=render(request,'pmo/costing.html',{
        'case':c,
        'investigations':AgentRun.objects.filter(case=c,actor=request.user,
            provider='deterministic-costing-v1').order_by('-pk')[:5],
        'policy':resolve(COMPONENT,c),
        'reviews':CostingReview.objects.filter(rule__case=c).select_related('actor').order_by('-pk')[:40],
        'rules':CostingRule.objects.filter(case=c).order_by('-pk')[:25],
        'proposals':CostingProposal.objects.filter(base__case=c).select_related('base','actor','decision').order_by('-pk')[:25]
            if Grant.objects.filter(case=c,user=request.user,action='costing.source.read',active=True).exists() else [],
        'oracles':CostingOracle.objects.filter(rule__case=c).select_related('rule').order_by('-pk')[:25],
        'runs':[{'row':row,'report':d.report(request.user,c.pk,row.pk)}
            for row in CostingRun.objects.filter(case=c).order_by('-pk')[:25]],
        'bindings':CostingBinding.objects.filter(run__case=c),
        'af13':CostingAF13Binding.objects.filter(run__case=c),
        'commands':forms,
        'schemas':{'rule':RULE,'oracle':ORACLE,'inputs':ARRAY(VALUE,1),'policy':SCHEMAS},
    })
    response['Cache-Control']='no-store'
    return response

@login_required
def report(request,case_id,pk):
    c=accessible_case(request.user,case_id)
    report=d.report(request.user,c.pk,pk)
    if request.GET.get('view')=='page':
        response=render(request,'pmo/costing_report.html',{'case':c,'report':report})
        response['Cache-Control']='no-store'
        return response
    return JsonResponse(report,headers={'Cache-Control':'no-store'})

@login_required
def source(request,case_id,kind,pk):
    c=accessible_case(request.user,case_id);d.readable(request.user,c,True)
    model=CostingRule if kind=='rule' else CostingOracle if kind=='oracle' else None
    row=model.objects.filter(**({'case':c} if kind=='rule' else {'rule__case':c}),pk=pk).first() if model else None
    if not row:raise Http404
    if request.GET.get('view')=='page':
        rule=row if kind=='rule' else row.rule
        owner_ids={rule.payload.get('owner_id'),rule.payload.get('oracle_owner_id')}-{None}
        people=get_user_model().objects.in_bulk(owner_ids)
        findings=[]
        try:d.confirmed(rule,row if kind=='oracle' else None)
        except (ValidationError,PermissionDenied):findings.append('Current source-owner confirmation is required.')
        examples=[]
        if kind=='oracle':
            for scenario in row.payload['scenarios']:
                actual=calculate(rule.payload,scenario['inputs'])
                examples.append({'key':scenario['key'],'scenario':scenario['scenario'],
                    'inputs':scenario['inputs'],'expected':scenario['expected'],
                    'actual':actual,'matches':compare(actual,scenario['expected'])})
        previous=CostingRule.objects.filter(case=c,reference=rule.reference,version__lt=rule.version).order_by('-version').first()
        old_parameters={parameter['key']:parameter for parameter in previous.payload['parameters']} if previous else {}
        parameters=[{'current':parameter,'previous':old_parameters.get(parameter['key'])} for parameter in rule.payload['parameters']]
        result=render(request,'pmo/costing_source.html',{'case':c,'record':row,'kind':kind,'rule':rule,
            'parameters':parameters,'previous':previous,'examples':examples,'findings':findings,
            'rule_owner':people.get(rule.payload.get('owner_id')),
            'examples_owner':people.get(rule.payload.get('oracle_owner_id')),
            'reviews':CostingReview.objects.filter(rule=rule,oracle=row if kind=='oracle' else None)
                .select_related('actor').order_by('-pk')[:20]})
        result['Cache-Control']='no-store'
        return result
    return JsonResponse({'id':row.pk,'payload':row.payload,'sha256':row.sha256,'native_workbook_verified':False},headers={'Cache-Control':'no-store'})

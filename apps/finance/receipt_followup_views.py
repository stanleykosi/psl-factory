import json
from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.shortcuts import render,redirect
from django.utils import timezone
from apps.core.views import accessible_case
from apps.core.services import add_evidence
from apps.policy.operator_drafts import draft_operator_policy
from apps.policy.invoice_receipt_validators import FOLLOWUP,SCHEMAS
from apps.agents import receipt_followup as agent
from . import receipt_followup as d
from . import followup_successors as s
from apps.policy.followup_successor_validators import COMPONENT as SUCCESSORS,VALUE as SUCCESSOR_VALUE,KINDS
from apps.policy.followup_transport_validators import INBOUND,SCHEMAS as TRANSPORT_SCHEMAS
from .transport_models import FinanceAuthenticatedIntake

def commands(c,data=None):
    requests=d.Request.objects.filter(case=c)
    definitions={
      'evidence':('Record supplied companion handoff evidence',{'body':forms.CharField(max_length=4000,widget=forms.Textarea),'source':forms.CharField(max_length=500)}),
      'receive':('Receive untrusted companion metadata for Finance investigation',{'projection':forms.JSONField(widget=forms.Textarea),'evidence_id':forms.ModelChoiceField(c.evidence.filter(kind='integration_contract'))}),
      'policy':('Draft current Finance owner criteria',{'content':forms.JSONField(widget=forms.Textarea),'evidence_id':forms.ModelChoiceField(c.evidence.filter(kind='policy_decision'))}),
      'intake_policy':('Draft authenticated source intake criteria',{'content':forms.JSONField(widget=forms.Textarea),'evidence_id':forms.ModelChoiceField(c.evidence.filter(kind='policy_decision'))}),
      'successor_policy':('Draft independent successor lineage criteria',{'content':forms.JSONField(widget=forms.Textarea),'evidence_id':forms.ModelChoiceField(c.evidence.filter(kind='policy_decision'))}),
      'propose_successor':('Propose source-owned financial successor lineage',{'request_id':forms.ModelChoiceField(requests),'original_id':forms.ModelChoiceField(d.InvoiceJob.objects.filter(invoice__case=c)),
          'successor_id':forms.ModelChoiceField(d.InvoiceJob.objects.filter(invoice__case=c)),'relation':forms.ChoiceField(choices=[(x,x.replace('_',' ')) for x in KINDS]),
          'evidence_id':forms.ModelChoiceField(c.evidence.filter(kind__in=s.EVIDENCE)),'note':forms.CharField(max_length=1000,widget=forms.Textarea),'operation_key':forms.CharField(max_length=100)}),
      'review_successor':('Independently approve or hold lineage only',{'proposal_id':forms.ModelChoiceField(s.Proposal.objects.filter(followup__case=c)),
          'verdict':forms.ChoiceField(choices=[('approve','Approve lineage'),('hold','Hold lineage')]),'evidence_id':forms.ModelChoiceField(c.evidence.filter(kind__in=s.EVIDENCE)),
          'note':forms.CharField(max_length=1000,widget=forms.Textarea),'operation_key':forms.CharField(max_length=100)}),
      'decide':('Record source-owned disposition',{'request_id':forms.ModelChoiceField(requests),'verdict':forms.ChoiceField(choices=[(x,x.replace('_',' ')) for x in ['investigate','link_current_intent','decline']]),
          'job_id':forms.ModelChoiceField(d.InvoiceJob.objects.filter(invoice__case=c),required=False),'note':forms.CharField(max_length=1000,widget=forms.Textarea),'operation_key':forms.CharField(max_length=100)}),
      'investigate':('Investigate current evidence and holds',{'request_id':forms.ModelChoiceField(requests)})}
    return [(a,label,type('ReceiptFollowupCommand',(forms.Form,),{'action':forms.CharField(initial=a,widget=forms.HiddenInput),**fields})(data if data and data.get('action')==a else None)) for a,(label,fields) in definitions.items()]

@login_required
def workbench(request,case_id):
    c=accessible_case(request.user,case_id);d.access(request.user,c);fs=commands(c,request.POST if request.method=='POST' else None)
    if request.method=='POST':
        try:
            f=next((f for a,_,f in fs if a==request.POST.get('action')),None)
            if f is None or not f.is_valid():raise ValidationError('Typed Finance follow-up command required')
            v=f.cleaned_data.copy();action=v.pop('action')
            for k in ['request_id','job_id','evidence_id','proposal_id','original_id','successor_id']:
                if k in v:v[k]=v[k].pk if v[k] else None
            if action=='evidence':
                d.access(request.user,c,'receive');add_evidence(request.user,c.pk,'integration_contract',v['body'],v['source'])
            elif action=='receive':d.receive(request.user,c.pk,**v)
            elif action=='decide':d.decide(request.user,c.pk,**v)
            elif action=='propose_successor':s.propose(request.user,c.pk,**v)
            elif action=='review_successor':s.review(request.user,c.pk,**v)
            elif action=='successor_policy':draft_operator_policy(request.user,c.pk,SUCCESSORS,v['content'],v['evidence_id'],timezone.now())
            elif action=='intake_policy':draft_operator_policy(request.user,c.pk,INBOUND,v['content'],v['evidence_id'],timezone.now())
            elif action=='policy':draft_operator_policy(request.user,c.pk,FOLLOWUP,v['content'],v['evidence_id'],timezone.now())
            else:return JsonResponse(agent.investigate(request.user,c.pk,**v),headers={'Cache-Control':'no-store'})
            messages.success(request,'Source Finance evidence recorded; financial execution requires its normal current controls')
            return redirect('finance_receipt_followup',case_id=c.pk)
        except (ValidationError,ValueError,KeyError):messages.error(request,'Held: check exact case, metadata, current owner criteria and explicit intent')
    response=render(request,'finance/receipt_followup.html',{'case':c,'commands':fs,'schema':json.dumps(SCHEMAS[FOLLOWUP][1],indent=2),
        'requests':d.Request.objects.filter(case=c).order_by('-pk')[:50],'decisions':d.Decision.objects.filter(followup__case=c).order_by('-pk')[:50],
        'intake_schema':json.dumps(TRANSPORT_SCHEMAS[INBOUND][1],indent=2),'intake_receipts':FinanceAuthenticatedIntake.objects.filter(followup__case=c).order_by('-pk')[:50],
        'successor_schema':json.dumps(SUCCESSOR_VALUE,indent=2),'proposals':s.Proposal.objects.filter(followup__case=c).order_by('-pk')[:50],
        'successor_reviews':s.Review.objects.filter(proposal__followup__case=c).order_by('-pk')[:50]})
    response['Cache-Control']='no-store';return response

from django import forms
from apps.finance.forms import CommandForm
from apps.policy.document_validators import ROLES
from apps.policy.partner_validators import SCHEMAS
from .models import PartnerRecord,PartnerReport,PartnerFinanceJob,PartnerFinanceReceipt
from django.contrib.auth import get_user_model

def commands(case,data=None):
    def choice(xs):return forms.ChoiceField(choices=[(x,x) for x in xs])
    def select(model):return forms.ModelChoiceField(model.objects.filter(**{'case' if model is PartnerRecord else 'record__case' if model is PartnerReport else 'report__record__case':case}))
    def ev(kind=None):return forms.ModelChoiceField(case.evidence.filter(**({'kind':kind} if kind else {})))
    def text():return forms.CharField(max_length=4000,widget=forms.Textarea(attrs={'rows':2}))
    role=lambda:choice(ROLES)
    defs={
      'capture':('Capture partner source',{'kind':choice(['agreement','onboarding','activity']),'reference':forms.CharField(max_length=100),'evidence':ev()}),
      'agreement':('Validate terms or record renewal intent',{'record':select(PartnerRecord),'purpose':choice(['terms','renewal']),'verdict':choice(['approve','return','reject','review_renewal','review_notice','no_action','undecided']),'role':role(),'evidence':ev('partner_decision'),'reason':text()}),
      'stage':('Record authorised onboarding history',{'record':select(PartnerRecord),'operation':choice(['enter','pause','resume']),'stage':forms.CharField(max_length=100),'occurred_at':forms.DateTimeField(),'role':role(),'evidence':ev('partner_stage'),'required_evidence_ids':forms.JSONField(initial=[])}),
      'followup':('Create owned internal follow-up',{'record':select(PartnerRecord),'source_key':forms.CharField(max_length=100),'owner_id':forms.ModelChoiceField(get_user_model().objects.filter(is_active=True,grant__case=case,grant__action='action.own',grant__active=True).distinct(),label='Owner'),'due_at':forms.DateTimeField(),'role':role(),'evidence':ev(),'reason':text()}),
      'report':('Calculate activity report',{'record':select(PartnerRecord)}),
      'review':('Review exact activity report',{'report':select(PartnerReport),'verdict':choice(['approve','return','reject']),'role':role(),'evidence':ev('partner_decision')}),
      'reserve':('Reserve Finance handoff',{'report':select(PartnerReport),'role':role()}),
      'operate':('Reconcile held Finance handoff',{'job':select(PartnerFinanceJob),'operation':choice(['retry','cancel','replace_intent']),'reason':text()}),
      'import':('Finance accept explicit meter quantities',{'receipt':select(PartnerFinanceReceipt),'role':role(),'evidence':ev('partner_decision')}),
      'investigate':('Investigate partner evidence',{}),
      'policy':('Draft partner policy',{'component':choice(SCHEMAS),'content':forms.JSONField(widget=forms.Textarea(attrs={'rows':8})),'evidence':ev('policy_decision'),'effective_from':forms.DateTimeField()})}
    result=[]
    for key,(label,fields) in defs.items():
        f=CommandForm(data if data and data.get('action')==key else None,initial={'action':key,'revision':case.revision},auto_id='partner_'+key+'_%s');f.fields.update(fields);result.append({'action':key,'label':label,'form':f})
    return result

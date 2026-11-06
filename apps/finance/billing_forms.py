from django import forms
from apps.policy.billing_validators import SUPPORTED
from .models import BillingCoverage,BillingUsage,BillingPreparation,Handoff
from .forms import CommandForm

def commands(case,data=None):
    def choice(v):return forms.ChoiceField(choices=[(x,x) for x in v])
    def e(kind):return forms.ModelChoiceField(case.evidence.filter(kind=kind))
    def select(model,optional=False):return forms.ModelChoiceField(model.objects.filter(**({'coverage__case':case} if model is BillingUsage else {'case':case})),required=not optional)
    defs={
      'coverage':('Record client/service coverage version',dict({k:forms.CharField(max_length=100) for k in ['reference','customer','service','contract','amount_basis']},currency=forms.CharField(max_length=3),from_period=forms.CharField(max_length=7),to_period=forms.CharField(max_length=7),completeness=choice(['unknown','partial','complete']),evidence=e('billing_coverage'))),
      'usage':('Capture supplied usage CSV',{'coverage':select(BillingCoverage),'evidence':e('billing_usage'),'provider_ref':forms.CharField(max_length=100,required=False),'extracted_at':forms.DateTimeField(required=False),'completeness':choice(['unknown','partial','complete'])}),
      'prepare':('Prepare usage or contract stage',{'coverage':select(BillingCoverage),'kind':choice(['usage','signed_sow','uat','completion']),'usage':select(BillingUsage,True),'handoff':select(Handoff,True)}),
      'policy':('Draft typed billing configuration',{'component':choice(sorted(SUPPORTED)),'content':forms.JSONField(widget=forms.Textarea(attrs={'rows':7})),
        'evidence':e('policy_decision'),'effective_from':forms.DateTimeField()}),
      'investigate':('Investigate exact billing lineage',{'coverage':select(BillingCoverage),'preparation':select(BillingPreparation,True)})}
    result=[]
    for action,(label,fields) in defs.items():
        form=CommandForm(data if data and data.get('action')==action else None,initial={'action':action,'revision':case.revision},auto_id='billing_'+action+'_%s');form.fields.update(fields)
        result.append({'label':label,'form':form,'action':action})
    return result

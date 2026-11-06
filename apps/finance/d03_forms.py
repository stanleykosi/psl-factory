from django import forms
from apps.finance.forms import CommandForm
from apps.identity.models import Grant
from apps.core.evidence_access import public_evidence
from apps.policy.d03_validators import SCHEMAS
from .models import BillingCoverage,Invoice,BillingEvidenceSource,BillingReleaseAssessment
def commands(a,c,data=None):
 grants=set(Grant.objects.filter(case=c,user=a,active=True).values_list('action',flat=True))
 def ev(kind):return forms.ModelChoiceField(c.evidence.filter(kind=kind))
 def choice(keys):return forms.ChoiceField(choices=[(x,x) for x in keys])
 def invoices():return forms.ModelChoiceField(Invoice.objects.filter(case=c,preparation__kind='usage'))
 defs={
 'source':('Capture or revise exact source evidence','d03.capture',{'reference':forms.CharField(max_length=100),'payload':forms.JSONField(widget=forms.Textarea),'predecessor':forms.IntegerField(required=False,min_value=1),'evidence':ev('d03_source')}),
 'review':('Confirm or dispute source meaning and contract','d03.review',{'source':forms.ModelChoiceField(BillingEvidenceSource.objects.filter(case=c)),'verdict':choice(['confirm','dispute','withdraw']),'meaning':choice(['prices','signature','other','unresolved','flow_contract']),'operation_key':forms.CharField(max_length=100),'evidence':ev('d03_review')}),
 'enroll':('Enroll exact BaaS coverage in evidence-bound dispatch','d03.enroll',{'coverage':forms.ModelChoiceField(BillingCoverage.objects.filter(case=c)),'evidence':ev('d03_enrollment')}),
 'observe':('Record current control result or access failure','d03.observe',{'invoice':invoices(),'evidence':forms.ModelChoiceField(c.evidence.filter(kind__startswith='d03_control_'))}),
 'assess':('Assess exact invoice/effect evidence','d03.assess',{'invoice':invoices(),'effect':choice(['issue','deliver'])}),
 'bind':('Bind assessed evidence without adding invoice approval','d03.bind',{'assessment':forms.ModelChoiceField(BillingReleaseAssessment.objects.filter(invoice__case=c))}),
 'policy':('Draft original D03 source or control configuration','policy.configure',{'component':choice(SCHEMAS),'content':forms.JSONField(widget=forms.Textarea),'evidence':ev('policy_decision'),'effective_from':forms.DateTimeField()}),
 'investigate':('Investigate source wording and release evidence gaps','agent.billing_evidence',{})}
 return [{'title':title,'form':type('D03'+k,(CommandForm,),fields)(data if data is not None and data.get('action')==k else None,initial={'action':k,'revision':c.revision},auto_id='id_'+k+'_%s')} for k,(title,permission,fields) in defs.items() if permission in grants]

from django import forms
from apps.finance.forms import CommandForm
from apps.identity.models import Grant
from apps.policy.approval_validators import SCHEMAS
from .models import DeliveryCandidate,ApprovalRequest,ApprovalSourceReceipt,ApprovalObservation,ApprovalRouteJob

def commands(a,c,data=None):
 grants=set(Grant.objects.filter(case=c,user=a,active=True).values_list('action',flat=True))
 systems=[x.split(':',1)[1] for x in grants if x.startswith('approval.source.read:')]
 receipts=ApprovalSourceReceipt.objects.filter(request__case=c,system__in=systems)
 def ev(kind):return forms.ModelChoiceField(c.evidence.filter(kind=kind))
 def choice(keys):return forms.ChoiceField(choices=[(k,k) for k in keys])
 def req():return forms.ModelChoiceField(ApprovalRequest.objects.filter(case=c))
 defs={
 'request':('Capture prerequisite request subject','approval.request',{'reference':forms.CharField(max_length=100),'candidate':forms.ModelChoiceField(DeliveryCandidate.objects.filter(case=c)),'kind':forms.CharField(max_length=100),'build_ref':forms.CharField(required=False,max_length=100),'release_ref':forms.CharField(required=False,max_length=100),'predecessor':forms.IntegerField(required=False,min_value=1),'evidence':ev('approval_request')}),
 'contract':('Department evidence-contract acceptance or withdrawal','approval.contract',{'kind':forms.CharField(max_length=100),'verdict':choice(['accept','withdraw']),'evidence':ev('approval_contract_review')}),
 'capture':('Capture supplied source receipt','approval.capture',{'request':req(),'evidence':ev('approval_source')}),
 'observe':('Record source observation or access failure','approval.verify',{'receipt':forms.ModelChoiceField(receipts),'evidence':ev('approval_observation')}),
 'route':('Route request or configured reminder','approval.route',{'request':req(),'purpose':choice(['request','reminder'])}),
 'operate':('Recover held routing job','approval.operate',{'job':forms.ModelChoiceField(ApprovalRouteJob.objects.filter(request__case=c)),'operation':choice(['retry','cancel','replace_intent']),'reason':forms.CharField(max_length=400)}),
 'export':('Bind synthetic referenced gate evidence','approval.export_gate',{'observation':forms.ModelChoiceField(ApprovalObservation.objects.filter(receipt__in=receipts))}),
 'policy':('Draft typed prerequisite configuration','policy.configure',{'component':choice(SCHEMAS),'content':forms.JSONField(widget=forms.Textarea),'evidence':ev('policy_decision'),'effective_from':forms.DateTimeField()}),
 'investigate':('Investigate prerequisite gaps','agent.approvals',{})}
 return [{'title':title,'form':type('Approval'+k,(CommandForm,),fields)(data if data is not None and data.get('action')==k else None,initial={'action':k,'revision':c.revision},auto_id='id_'+k+'_%s')} for k,(title,permission,fields) in defs.items() if permission in grants]

from django import forms
from .forms import CommandForm
from .recognition_models import ProgressPacket
from apps.policy.recognition_validators import SCHEMAS

def commands(case,data=None):
 def evidence(required=True):return forms.ModelChoiceField(case.evidence.all(),required=required)
 defs={'prepare':('Capture versioned progress packet',{'reference':forms.CharField(max_length=100),'payload':forms.JSONField(widget=forms.Textarea(attrs={'rows':12})),'evidence':evidence()}),'investigate':('Investigate evidence and draft PM questions',{}),'policy':('Draft Finance/PM review configuration',{'component':forms.ChoiceField(choices=[(k,k) for k in SCHEMAS]),'content':forms.JSONField(widget=forms.Textarea(attrs={'rows':8})),'evidence':evidence(),'effective_from':forms.DateTimeField()})}
 for action,title in [('preview_input','Capture private proposed input (unbound observation only)'),('attest','PM attest exact packet'),('request','Send to local Finance review inbox'),('receive','Finance acknowledge receipt only'),('review','Finance record disposition')]:
  fields={'packet':forms.ModelChoiceField(ProgressPacket.objects.filter(case=case)),'operation_key':forms.CharField(max_length=100),'note':forms.CharField(max_length=4000,widget=forms.Textarea(attrs={'rows':2})),'evidence':evidence()}
  if action=='review':fields.update(verdict=forms.ChoiceField(choices=[(v,v) for v in ['reviewed','return','disputed']]),decision_evidence=evidence(False))
  defs[action]=(title,fields)
 return [{'action':k,'title':title,'form':type('Recognition'+k,(CommandForm,),fields)(data if data is not None and data.get('action')==k else None,initial={'action':k,'revision':case.revision},auto_id='id_'+k+'_%s')} for k,(title,fields) in defs.items()]

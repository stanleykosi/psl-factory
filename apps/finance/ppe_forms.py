from django import forms
from apps.identity.models import Grant
from apps.policy.ppe_validators import SCHEMAS
from .forms import CommandForm
from .models import ScheduleWork,FinanceRun
def commands(actor,c,data=None):
 def choice(v):return forms.ChoiceField(choices=[(k,k) for k in v])
 def work(kind=None,required=True):return forms.ModelChoiceField(ScheduleWork.objects.filter(case=c,kind=kind) if kind else ScheduleWork.objects.filter(case=c,kind__startswith='ppe_'),required=required)
 def ev(kinds):return forms.ModelChoiceField(c.evidence.filter(kind__in=kinds))
 defs={'capture':('Capture supplied asset register','ppe.capture',{'reference':forms.CharField(max_length=100),'evidence':ev(['ppe_register'])}),
 'prepare':('Reconcile and calculate a schedule','ppe.prepare',{'reference':forms.CharField(max_length=100),'register':work('ppe_register'),'prior':work('ppe_schedule',False),'ledger':forms.ModelChoiceField(FinanceRun.objects.filter(case=c,kind='mapping'),required=False)}),
 'review':('Record actual human source, date-basis or schedule decision','ppe.review',{'work':work(),'purpose':choice(['register','basis','schedule']),'verdict':choice(['approve','return','reject','revoke']),'evidence':ev(['finance_review','ppe_basis_explanation']),'note':forms.CharField(max_length=4000,widget=forms.Textarea)}),
 'policy':('Draft typed PPE policy and supplied oracles','policy.configure',{'component':choice(SCHEMAS),'content':forms.JSONField(widget=forms.Textarea(attrs={'rows':12})),'evidence':ev(['policy_decision']),'effective_from':forms.DateTimeField()}),
 'investigate':('Investigate asset, rule and date-basis gaps','agent.ppe',{})}
 grants=set(Grant.objects.filter(case=c,user=actor,active=True).values_list('action',flat=True));out=[]
 for action,(title,permission,fields) in defs.items():
  if permission in grants:out.append({'title':title,'form':type('PPE'+action,(CommandForm,),fields)(data if data is not None and data.get('action')==action else None,initial={'action':action,'revision':c.revision},auto_id='id_'+action+'_%s')})
 return out

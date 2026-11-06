from django import forms
from apps.identity.models import Grant
from apps.policy.schedule_validators import SCHEMAS
from .forms import CommandForm
from .models import FinanceRun
from .schedule_models import ScheduleWork

def commands(actor,case,data=None):
 def choice(values):return forms.ChoiceField(choices=[(x,x) for x in values])
 def ev(kind):return forms.ModelChoiceField(case.evidence.filter(kind=kind))
 def work():return forms.ModelChoiceField(ScheduleWork.objects.defer('payload','result').filter(case=case,kind__in=['income','inventory']))
 defs={
  'income':('Prepare income detail and adjustment reconciliation','schedules.prepare',{'reference':forms.CharField(max_length=100),'parent':forms.ModelChoiceField(FinanceRun.objects.defer('result').filter(case=case,kind='mapping')),'payload':forms.JSONField(widget=forms.Textarea(attrs={'rows':12})),'evidence':ev('income_detail')}),
  'inventory':('Capture supplied schedule inventory','schedules.prepare',{'reference':forms.CharField(max_length=100),'evidence':ev('schedule_inventory')}),
  'review':('Review exact income or bounded inventory','schedules.review',{'work':work(),'verdict':choice(['approve','return','reject','revoke']),'evidence':ev('finance_review'),'note':forms.CharField(max_length=4000,widget=forms.Textarea)}),
  'adjust':('Export a reviewed reporting adjustment','schedules.adjust',{'work':work(),'kind':choice(['additive','reclassification']),'evidence':ev('finance_adjustment')}),
  'investigate':('Investigate held evidence and draft owner questions','agent.schedules',{}),
  'policy':('Draft typed income/schedule policy','policy.configure',{'component':choice(SCHEMAS),'content':forms.JSONField(widget=forms.Textarea(attrs={'rows':12})),'evidence':ev('policy_decision'),'effective_from':forms.DateTimeField()})}
 grants=set(Grant.objects.filter(case=case,user=actor,active=True).values_list('action',flat=True));result=[]
 for action,(title,permission,fields) in defs.items():
  if permission not in grants:continue
  f=type('Schedule'+action,(CommandForm,),fields)(data if data is not None and data.get('action')==action else None,initial={'action':action,'revision':case.revision},auto_id='id_'+action+'_%s')
  result.append({'action':action,'title':title,'form':f})
 return result

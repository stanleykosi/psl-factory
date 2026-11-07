from django import forms
from apps.identity.models import Grant
from apps.policy.hrfinance_validators import SCHEMAS
from .forms import CommandForm
from .hrfinance_models import HRFinanceNeed,HRDisclosure,HRReadSnapshot,HRHandoffRecord

def commands(actor,case,data=None):
 def select(model,required=True):
  path='case' if model==HRFinanceNeed else 'need__case' if model==HRDisclosure else 'contract__need__case'
  q=model.objects.defer('payload') if model==HRReadSnapshot else model.objects
  return forms.ModelChoiceField(q.filter(**{path:case}),required=required)
 def evidence(kind):return forms.ModelChoiceField(case.evidence.filter(kind=kind))
 from apps.workflows.models import HumanTask
 from .hr_scope import PURPOSE,REPLIES
 def scope_task():return forms.ModelChoiceField(HumanTask.objects.filter(case=case,context__purpose=PURPOSE,status='open'))
 key=lambda:forms.CharField(max_length=100)
 defs={
 'scope_request':('Assign safe scope question internally',{'snapshot':select(HRReadSnapshot)}),
 'scope_reply':('Answer assigned scope question',{'scope_task':scope_task(),'task_revision':forms.IntegerField(min_value=1),'reply':forms.ChoiceField(choices=[(v,v.replace('_',' ')) for v in REPLIES])}),
 'scope_cancel':('Cancel original scope question',{'scope_task':scope_task(),'task_revision':forms.IntegerField(min_value=1)}),
 'need':('State Finance reporting need',{'reference':key(),'payload':forms.JSONField(widget=forms.Textarea(attrs={'rows':10})),'evidence':evidence('hr_finance_need')}),
 'contract':('Prepare minimal read-only disclosure',{'need':select(HRFinanceNeed),'operation_key':key(),'evidence':evidence('hr_contract_source')}),
 'authorize':('HR approve, return or revoke disclosure',{'contract':select(HRDisclosure),'verdict':forms.ChoiceField(choices=[(v,v) for v in ['approve','return','revoke']]),'operation_key':key(),'evidence':evidence('hr_disclosure_decision')}),
 'capture':('HR supply an authorised read-only export',{'contract':select(HRDisclosure),'operation_key':key(),'body':forms.CharField(max_length=256000,widget=forms.Textarea(attrs={'rows':10}),help_text='Do not use the shared evidence form for staff/payroll rows. Out-of-contract fields are rejected; values are not logged or retained.')}),
 'receive':('Finance acknowledge exact period snapshot',{'snapshot':select(HRReadSnapshot),'operation_key':key(),'evidence':evidence('hr_disclosure_decision')}),
 'correction':('Finance route a correction to HR',{'snapshot':select(HRReadSnapshot),'operation_key':key(),'evidence':evidence('hr_correction_request')}),
 'respond':('HR link corrected successor export',{'request_record':select(HRHandoffRecord),'successor':select(HRReadSnapshot),'operation_key':key(),'evidence':evidence('hr_correction_response')}),
 'bind':('Draft allocation input references',{'snapshot':select(HRReadSnapshot),'evidence':evidence('policy_decision')}),
 'investigate':('Investigate scope and freshness without reading staff rows',{}),
 'policy':('Draft typed HR disclosure configuration',{'component':forms.ChoiceField(choices=[(k,k) for k in SCHEMAS]),'content':forms.JSONField(widget=forms.Textarea(attrs={'rows':10})),'evidence':evidence('policy_decision'),'effective_from':forms.DateTimeField()})}
 grants=set(Grant.objects.filter(case=case,user=actor,active=True).values_list('action',flat=True));result=[]
 for action,(title,fields) in defs.items():
  permission='agent.hrfinance' if action in ['investigate','scope_request','scope_cancel'] else 'hrfinance.respond' if action=='scope_reply' else 'policy.configure' if action=='policy' else 'hrfinance.'+action
  if permission not in grants:continue
  f=type('HRFinance'+action,(CommandForm,),fields)(data if data is not None and data.get('action')==action else None,initial={'action':action,'revision':case.revision},auto_id='id_'+action+'_%s')
  result.append({'action':action,'title':title,'form':f})
 return result

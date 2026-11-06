from django import forms
from apps.identity.models import Grant
from apps.policy.bu_validators import SCHEMAS
from .forms import CommandForm
from .bu_models import BUWork,BUReport
from .payroll_models import PayrollRun

def commands(actor,case,data=None):
 def work(kind=None):
  q=BUWork.objects.defer('payload').filter(case=case)
  if kind:q=q.filter(kind=kind)
  return forms.ModelChoiceField(q)
 key=lambda:forms.CharField(max_length=100)
 evidence=lambda:forms.ModelChoiceField(case.evidence.filter(kind='bu_review'))
 payroll=lambda:forms.ModelChoiceField(PayrollRun.objects.defer('result').filter(request__case=case,kind='match'))
 defs={
 'rule':('Prepare restricted individual exception rule',{'payroll':payroll(),'reference':key(),'operation_key':key(),'payload':forms.JSONField(widget=forms.Textarea(attrs={'rows':8}))}),
 'staff':('Allocate staff costs with exact standard-pool exclusions',{'payroll':payroll(),'reference':key(),'operation_key':key(),'declared':forms.JSONField(help_text='Private pairs: employee reference and component; every exception needs a current reviewed rule.'),'rule_ids':forms.JSONField(help_text='Exact private rule IDs, not source text authority.')}),
 'capture':('Source owner capture event export',{'reference':key(),'operation_key':key(),'scope':forms.JSONField(),'body':forms.CharField(max_length=256000,widget=forms.Textarea(attrs={'rows':10}))}),
 'event':('Prepare event attribution and company roll-up',{'source':work('source'),'reference':key(),'operation_key':key(),'comparison':forms.JSONField(required=False,help_text='Optional exact Finance allocation run_id/metric; required only when configured.')}),
 'review':('Review exact private rule/source/output',{'work':work(),'purpose':forms.ChoiceField(choices=[(v,v) for v in ['rule','staff','source','event','historical']]),'verdict':forms.ChoiceField(choices=[(v,v) for v in ['approve','return','revoke']]),'operation_key':key(),'evidence':evidence()}),
 'publish':('Publish reviewed aggregate report',{'work':work(),'operation_key':key()}),
 'receive':('Acknowledge permitted aggregate',{'report':forms.ModelChoiceField(BUReport.objects.defer('payload').filter(work__case=case))}),
 'investigate':('Investigate references and draft owner questions',{}),
 'policy':('Draft typed BU policy',{'component':forms.ChoiceField(choices=[(k,k) for k in SCHEMAS]),'content':forms.JSONField(widget=forms.Textarea(attrs={'rows':10})),'evidence':forms.ModelChoiceField(case.evidence.filter(kind='policy_decision')),'effective_from':forms.DateTimeField()})}
 grants=set(Grant.objects.filter(case=case,user=actor,active=True).values_list('action',flat=True));result=[]
 for action,(title,fields) in defs.items():
  permission='policy.configure' if action=='policy' else 'agent.bu' if action=='investigate' else 'bu.'+action
  if permission not in grants:continue
  f=type('BU'+action,(CommandForm,),fields)(data if data is not None and data.get('action')==action else None,initial={'action':action,'revision':case.revision},auto_id='id_'+action+'_%s')
  result.append({'action':action,'title':title,'form':f})
 return result

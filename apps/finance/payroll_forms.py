from django import forms
from apps.identity.models import Grant
from apps.policy.payroll_validators import SCHEMAS
from .forms import CommandForm
from .payroll_models import PayrollRequest,PayrollInput,PayrollRun,PayrollPublication
from .hrfinance_models import HRReadSnapshot

class PayrollCaptureForm(CommandForm):
 file = forms.FileField(required=False, label='Payroll export file', widget=forms.ClearableFileInput(attrs={'accept':'.json,application/json'}))

 def clean(self):
  values=super().clean()
  file,body=values.get('file'),values.get('body')
  if bool(file)==bool(body):raise forms.ValidationError('Choose one export file or paste its contents.')
  if file:
   if file.size>256000:raise forms.ValidationError('Choose an export up to 256,000 bytes.')
   try:values['body']=file.read(256001).decode('utf-8-sig')
   except UnicodeDecodeError as exc:raise forms.ValidationError('Choose a UTF-8 JSON export.') from exc
  return values


def commands(actor,case,data=None,files=None):
 def select(model,multiple=False,kind=None):
  if model==PayrollRequest:q=model.objects.filter(case=case)
  elif model==HRReadSnapshot:q=model.objects.defer('payload').filter(contract__need__case=case)
  else:q=model.objects.filter(request__case=case)
  if model in [PayrollInput,PayrollPublication]:q=q.defer('payload')
  if model==PayrollRun:
   q=q.defer('result')
   if kind:q=q.filter(kind=kind)
  cls=forms.ModelMultipleChoiceField if multiple else forms.ModelChoiceField
  return cls(q)
 def evidence(kind):return forms.ModelChoiceField(case.evidence.filter(kind=kind))
 key=lambda:forms.CharField(max_length=100)
 defs={
 'request':('State restricted two-source payroll need',{'reference':key(),'metadata':forms.JSONField(widget=forms.Textarea(attrs={'rows':7})),'evidence':evidence('payroll_need')}),
 'capture':('Supply an authorised payroll export',{'request_record':select(PayrollRequest),'provider':key(),'operation_key':key(),'body':forms.CharField(required=False,max_length=256000,widget=forms.Textarea(attrs={'rows':7}),label='Paste export contents')}),
 'combine':('Prepare restricted source combination',{'request_record':select(PayrollRequest),'inputs':select(PayrollInput,True),'operation_key':key()}),
 'match':('Match to the HR-authorised effective-period view',{'parent':select(PayrollRun,kind='combine'),'hr_snapshot':select(HRReadSnapshot),'operation_key':key()}),
 'aggregate':('Prepare permitted BU staff-cost totals',{'parent':select(PayrollRun,kind='match'),'operation_key':key()}),
 'review':('Finance review exact input or working version',{'subject_kind':forms.ChoiceField(choices=[('input','input'),('run','run')]),'subject_id':forms.IntegerField(min_value=1),'verdict':forms.ChoiceField(choices=[(v,v) for v in ['approve','return','revoke']]),'operation_key':key(),'evidence':evidence('payroll_review')}),
 'publish':('Publish reviewed aggregate to local BU report',{'run':select(PayrollRun,kind='aggregate'),'operation_key':key()}),
 'receive':('Acknowledge exact BU report version',{'publication':select(PayrollPublication)}),
 'hr_correction':('Route an HR matching correction by reference',{'run':select(PayrollRun,kind='match'),'operation_key':key(),'evidence':evidence('hr_correction_request')}),
 'investigate':('Investigate metadata and draft owner questions',{}),
 'policy':('Draft typed payroll rule or authority',{'component':forms.ChoiceField(choices=[(k,k) for k in SCHEMAS]),'content':forms.JSONField(widget=forms.Textarea(attrs={'rows':10})),'evidence':evidence('policy_decision'),'effective_from':forms.DateTimeField()})}
 grants=set(Grant.objects.filter(case=case,user=actor,active=True).values_list('action',flat=True));result=[]
 for action,(title,fields) in defs.items():
  permission='agent.payroll' if action=='investigate' else 'policy.configure' if action=='policy' else 'payroll.report.receive' if action=='receive' else 'payroll.'+action
  if permission not in grants:continue
  bound=data is not None and data.get('action')==action
  base=PayrollCaptureForm if action=='capture' else CommandForm
  f=type('Payroll'+action,(base,),fields)(data if bound else None,files if bound else None,
     initial={'action':action,'revision':case.revision},auto_id='id_'+action+'_%s')
  result.append({'action':action,'title':title,'form':f})
 return result

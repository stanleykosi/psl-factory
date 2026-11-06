"""Engineering JSON gateway extension; not a claim about any vendor API."""
import json
from django.core.exceptions import ValidationError
from apps.documents.contracts import validate
from apps.workflows.readiness_models import IntegrationContract
from adapters.readiness import binding,http,RECEIPT

class PrivateEvidenceAdapter:
 def request(self,*args,**kwargs):
  try:
   value=http(*args,**kwargs);json.dumps(value,allow_nan=False);return value
  except (ValueError,RecursionError):raise ConnectionError('Malformed private provider transport response') from None
 def runtime(self,j):
  contract=IntegrationContract.objects.get(pk=j.intent['contract']);public,private=binding(contract)
  if public!=j.intent['binding']:raise ValidationError('Provider binding changed; reconcile with the original endpoint')
  return contract,private
 def lookup(self,j):
  _,private=self.runtime(j)
  value=self.request(private,'/extractions/'+j.operation_key);validate(RECEIPT,value)
  if value['operation_key']!=j.operation_key:raise ValidationError('Exact extraction receipt identity required')
  if value['status']=='not_found':
   if value['result'] is not None:raise ValidationError('Ambiguous extraction receipt')
   return None
  if value['status']=='failed':return {'facts':[],'uncertainties':[],'proposed_actions':['provider_failed']}
  if value['result'] is None:raise ValidationError('Completed extraction receipt lacks output')
  return value['result']
 def extract(self,j):
  contract,private=self.runtime(j)
  return self.request(private,'/extract',method='POST',key=j.operation_key,body={'model_id':contract.payload['model_id'],'purpose':j.projection.purpose,'process_id':j.projection.process_id,'data_scope':'reviewed_exact_quotes_v1','input':j.projection.payload['quotes'],'tools':[]})

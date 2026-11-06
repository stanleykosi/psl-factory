"""PSL-owned read-only receipt gateway protocol. No vendor API or dispatch assumption."""
from types import SimpleNamespace
from django.core.exceptions import ValidationError
from apps.documents.contracts import validate,digest
from adapters.forecast import obj,KEY
from adapters.readiness import binding as target_binding,http,VERSION
HASH={'type':'string','pattern':'^[a-f0-9]{64}$'}
NULLTIME={'anyOf':[{'type':'string'}, {'type':'null'}]}
IDENTITY=obj({'protocol':{'const':'psl.support-receipt/v1'},'receipt_key':HASH,'case_ref':{'type':'string'},'tenant':KEY,'channel_ref':KEY,'account_ref':KEY,'customer_ref':KEY,'recipient_ref':KEY,'sender_ref':KEY,'external_ref':KEY,'receipt_version':KEY,'packet_sha256':HASH,'message_sha256':HASH})
RECEIPT=obj(dict(IDENTITY['properties'],principal_ref=KEY,contract_version=VERSION,status={'enum':['delivered','pending','failed','retracted']},human_response={'type':'boolean'},sent_at=NULLTIME,delivered_at=NULLTIME))
def binding(case,v):
 proxy=SimpleNamespace(case=case,payload={'kind':'adapter','implementation':'authenticated_json_v1','target_key':v['target_key'],'credential_ref':v['credential_ref'],'credential_revision':v['credential_revision'],'family':'supportchannel','principal_ref':v['principal_ref'],'contract_version':v['contract_version'],'model_id':None})
 return target_binding(proxy)
class SupportChannelAdapter:
 def lookup(self,job):
  from apps.baas.support_channel_models import SupportChannelReceipt
  r=SupportChannelReceipt.objects.filter(job=job).first()
  if r:
   if r.sha256!=digest(r.payload) or r.binding!=job.intent['binding']:raise ValidationError('Committed channel check receipt mismatch')
  return r
 def verify(self,job):
  from apps.baas.support_channel import rules,validate_result
  _,v=rules(job.claim.case);b,private=binding(job.claim.case,v)
  if b!=job.intent['binding']:raise ValidationError('Original channel target/credential binding changed')
  result=http(private,'/support-receipts/'+job.claim.payload['receipt_key'])
  validate_result(job.claim,result,v);return result

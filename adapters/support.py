import json
from django.core.exceptions import ValidationError
from apps.documents.contracts import validate
from adapters.forecast import obj,KEY
from adapters.hrfinance import timestamp
MESSAGE=obj({'channel':KEY,'message_ref':KEY,'customer_ref':KEY,'transaction_ref':{'anyOf':[KEY,{'type':'null'}]},'issue_ref':KEY,'case_type':KEY,'received_at':{'type':'string'},'content_reference':KEY})
class SuppliedSupportChannelAdapter:
 def read(self,evidence):
  p=self.parse(evidence,MESSAGE,'support_intake');timestamp(p['received_at']);return p
 def read_result(self,evidence,schema):return self.parse(evidence,schema,'support_specialist_result')
 def parse(self,evidence,schema,kind):
  if evidence.kind!=kind or len(evidence.body)>100000:raise ValidationError('Bounded support intake evidence required')
  def pairs(items):
   out={}
   for k,v in items:
    if k in out:raise ValueError('Duplicate field')
    out[k]=v
   return out
  try:p=json.loads(evidence.body,object_pairs_hook=pairs,parse_constant=lambda _:(_ for _ in ()).throw(ValueError()))
  except (ValueError,TypeError,RecursionError):raise ValidationError('Strict finite message JSON required')
  validate(schema,p);return p
class LocalSupportReportAdapter:
 def read(self,actor,case_id,report_id):
  from apps.baas.support import read_report
  return read_report(actor,case_id,report_id)

from django.core.exceptions import ValidationError
from adapters.hrfinance import timestamp
def elapsed(receipt,response,resolution,reopened,rule):
 if rule['reopen_basis']=='undefined' and reopened:return {'first_response_seconds':None,'resolution_seconds':None,'finding':'reopened_clock_undefined'}
 anchor=reopened if reopened and rule['reopen_basis']=='since_latest_reopen' else receipt
 if not anchor:return {'first_response_seconds':None,'resolution_seconds':None,'finding':'missing_receipt'}
 values={};invalid=False
 for key,at in [('first_response_seconds',response),('resolution_seconds',resolution)]:
  if at is None:values[key]=None;continue
  seconds=(timestamp(at)-timestamp(anchor)).total_seconds()
  if seconds<0:values[key]=None;invalid=True
  else:values[key]=str(seconds)
 values['finding']='invalid_event_order' if invalid else None;return values

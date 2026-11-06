"""Engineering internal release contract; no assumed customer channel authority."""
from django.core.exceptions import ValidationError,PermissionDenied
from django.contrib.auth import get_user_model
from adapters.forecast import obj
from .document_validators import typed
from .schedule_validators import ID
COMPONENT='B14.response_release'
FIELDS=['body','issue_ref','case_type']
VALUE=obj({'releaser_id':ID,'recipient_id':ID,'independent_release':{'type':'boolean'},'fields':{'type':'array','minItems':1,'maxItems':3,'uniqueItems':True,'items':{'enum':FIELDS}},'route':{'const':'internal_authorised_inbox_v1'},'receipt_meaning':{'const':'internal_storage_only'},'release_ttl_seconds':{'type':'integer','minimum':1,'maximum':604800},'max_attempts':{'type':'integer','minimum':1,'maximum':10},'lease_seconds':{'type':'integer','minimum':5,'maximum':300}})
SCHEMAS={COMPONENT:('schema:psl/support-response-release/v1',VALUE)}
def principal(c,v,key):
 from apps.baas import support_agent as native,support
 from apps.identity.services import require
 a=get_user_model().objects.filter(pk=v[key+'_id'],is_active=True).first()
 if not a:raise ValidationError('Active exact release principal required')
 native.source_access(a,c);require(a,c,'support.response.'+('release' if key=='releaser' else 'receive'))
 if key=='releaser':support.authority(a,c,'summary')
 return a

def validate_reference(component,target,case,runtime=False):
 v=typed(target,*SCHEMAS[component])
 if case.kind!='support':raise ValidationError('Support scope required')
 if not runtime:
  try:
   for key in ['releaser','recipient']:principal(case,v,key)
  except PermissionDenied:raise ValidationError('Actual scoped native source and release/receive grants required') from None

import copy
from django.core.exceptions import ValidationError,PermissionDenied
from django.contrib.auth import get_user_model
from adapters.forecast import obj
from .document_validators import typed,ROLES
from apps.identity.models import Grant
ADAPTER='INT.adapter_readiness';PROVIDER='INT.provider_readiness'
VALUE=obj({'probe_user_id':{'type':'integer','minimum':1},'probe_role':{'enum':ROLES},'reviewer_id':{'type':'integer','minimum':1},'reviewer_role':{'enum':ROLES},'independent_review':{'type':'boolean'},'freshness_seconds':{'type':'integer','minimum':1,'maximum':31536000},'require_receipt_probe':{'type':'boolean'},'allow_synthetic_target':{'type':'boolean'},'lease_seconds':{'type':'integer','minimum':10,'maximum':120},'max_attempts':{'type':'integer','minimum':1,'maximum':10}})
PROVIDER_VALUE=copy.deepcopy(VALUE);PROVIDER_VALUE['properties']['require_receipt_probe']={'const':False}
SCHEMAS={ADAPTER:('schema:psl/integration-readiness/v1',VALUE),PROVIDER:('schema:psl/integration-readiness/v1',PROVIDER_VALUE)}
NATIVE_SCHEMA='schema:psl/integration-readiness/v2'
NATIVE_VALUE=copy.deepcopy(VALUE)
NATIVE_VALUE['properties']['native_publication_job_ids']={'type':'array','minItems':1,'maxItems':100,'uniqueItems':True,'items':{'type':'integer','minimum':1}}
NATIVE_VALUE['required'].append('native_publication_job_ids')

PRIVATE_COMPONENT='INT.private_protection_readiness'
PRIVATE_SCHEMA='schema:psl/private-protection-readiness/v1'
PRIVATE_VALUE=copy.deepcopy(VALUE)
PRIVATE_VALUE['properties']['private_protection_job_ids']={'type':'array','minItems':1,'maxItems':100,'uniqueItems':True,'items':{'type':'integer','minimum':1}}
PRIVATE_VALUE['required'].append('private_protection_job_ids')
SCHEMAS[PRIVATE_COMPONENT]=(PRIVATE_SCHEMA,PRIVATE_VALUE)
FILE_SCHEMA='schema:psl/private-protection-readiness/v2'
FILE_VALUE=copy.deepcopy(PRIVATE_VALUE)
FILE_VALUE['properties']['private_protection_job_ids']['minItems']=0
FILE_VALUE['properties']['private_file_job_ids']={'type':'array','minItems':1,'maxItems':100,'uniqueItems':True,'items':{'type':'integer','minimum':1}}
FILE_VALUE['required'].append('private_file_job_ids')

ACCEPTED_COMPONENT='INT.accepted_protection_readiness'
ACCEPTED_SCHEMA='schema:psl/accepted-protection-readiness/v1'
ACCEPTED_VALUE=copy.deepcopy(VALUE)
ACCEPTED_VALUE['properties']['accepted_protection_job_ids']={'type':'array','minItems':1,'maxItems':100,'uniqueItems':True,'items':{'type':'integer','minimum':1}}
ACCEPTED_VALUE['required'].append('accepted_protection_job_ids')
SCHEMAS[ACCEPTED_COMPONENT]=(ACCEPTED_SCHEMA,ACCEPTED_VALUE)

def validate_reference(component,target,case,runtime=False):
 native=component==ADAPTER and target.schema_ref==NATIVE_SCHEMA
 private=component==PRIVATE_COMPONENT
 file=private and target.schema_ref==FILE_SCHEMA
 v=typed(target,FILE_SCHEMA,FILE_VALUE) if file else typed(target,PRIVATE_SCHEMA,PRIVATE_VALUE) if private else typed(target,NATIVE_SCHEMA,NATIVE_VALUE) if native else typed(target,*SCHEMAS[component])
 if component==ACCEPTED_COMPONENT:
  from apps.workflows.accepted_protection_readiness import validate_policy
  validate_policy(case,v,runtime)
 if private:
  from apps.workflows.private_protection_readiness import validate_policy
  validate_policy(case,v,runtime)
 if file:
  from apps.workflows.private_file_readiness import validate_policy as file_policy
  file_policy(case,v,runtime)
 if native:
  from apps.finance.publication_readiness import validate_policy
  validate_policy(case,v,runtime)
 if not case.synthetic and v['allow_synthetic_target']:raise ValidationError('Synthetic endpoints cannot be operational targets')
 if not runtime:
  for key,action in [('probe_user_id','integration.probe'),('reviewer_id','integration.review')]:
   if not get_user_model().objects.filter(pk=v[key],is_active=True).exists() or not Grant.objects.filter(case=case,user_id=v[key],action=action,active=True).exists():raise ValidationError('Actual scoped integration principals/grants required')

   from .services import decision_authority
   try:decision_authority(get_user_model().objects.get(pk=v[key]),case,v['probe_role' if key=='probe_user_id' else 'reviewer_role'])
   except PermissionDenied:raise ValidationError('Actual current D05 role assignment required') from None

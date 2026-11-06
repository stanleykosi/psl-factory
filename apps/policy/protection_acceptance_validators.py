"""Independent AF13 protection owner and acceptance interfaces; no source-policy cycle."""
from django.core.exceptions import ValidationError,PermissionDenied
from django.contrib.auth import get_user_model
from apps.identity.services import require
from .validation_validators import PROTECTION_OWNER as OWNER,PROTECTION_ACCEPTANCE as COMPONENT,PROTECTION_OWNER_SCHEMA as OWNER_SCHEMA,PROTECTION_OWNER_VALUE as OWNER_VALUE,PROTECTION_SCHEMA as SCHEMA,PROTECTION_VALUE as VALUE,PROTECTION_FILE_SCHEMA as FILE_SCHEMA,PROTECTION_FILE_VALUE as FILE_VALUE,process_ids
from .document_validators import typed

def validate_reference(component,target,case,runtime=False):
 if component==OWNER:
  v=typed(target,OWNER_SCHEMA,OWNER_VALUE);keys=[]
  if v['allow_preparer_review']:raise ValidationError('Independent private protection owner review required')
  for row in v['assignments']:
   process_ids(row['process_ids']);a=get_user_model().objects.filter(pk=row['user_id'],is_active=True).first()
   if not a:raise ValidationError('Actual active protection owner required')
   keys.extend((row['user_id'],p,k) for p in row['process_ids'] for k in row['purposes'])
   if not runtime:
    from .services import decision_authority
    try:
     require(a,case,'validation.read')
     for purpose in row['purposes']:require(a,case,'validation.accept' if purpose=='acceptance' else 'validation.review')
     decision_authority(a,case,row['role'])
    except PermissionDenied:raise ValidationError('Actual scoped protection owner grants and D05 authority required') from None
  if len(keys)!=len(set(keys)):raise ValidationError('Ambiguous duplicate protection owner responsibility')
 else:
  v=typed(target,FILE_SCHEMA,FILE_VALUE) if target.schema_ref==FILE_SCHEMA else typed(target,SCHEMA,VALUE)
  if not v['independent_acceptor'] or not v['independent_tester']:raise ValidationError('Independent private protection acceptance and testing required')
  from apps.documents.protection_acceptance import validate_inventory
  validate_inventory(case,v,runtime)

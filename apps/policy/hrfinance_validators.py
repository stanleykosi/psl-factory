"""F35 finite read-only disclosure contracts; never HR source writes."""
from datetime import date,timedelta
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError,PermissionDenied
from apps.documents.contracts import validate
from adapters.forecast import obj,KEY
from .document_validators import typed
AUTHORITY='F35.authority_rules'
DISCLOSURE='F35.disclosure_rules'
ID={'type':'integer','minimum':1}
FIELDS=['employee_id','bu','effective_from','effective_until','role','monthly_pay','currency']
REQUIRED=['employee_id','bu','effective_from','effective_until']
MONTH={'type':'string','pattern':r'^\d{4}-(0[1-9]|1[0-2])$'}
IDS={'type':'array','minItems':1,'maxItems':100,'uniqueItems':True,'items':ID}
FIELD_LIST={'type':'array','minItems':4,'maxItems':7,'uniqueItems':True,'items':{'enum':FIELDS}}
TEXT={'type':'string','minLength':1,'maxLength':1000}
SCHEMAS={
 AUTHORITY:('schema:psl/hr-finance-authority/v1',obj({'human_only':{'const':True},'assignments':{'type':'array','minItems':1,'maxItems':100,'items':obj({'user_id':ID,'purpose':{'enum':['authorize','receive','respond']},'role':{'enum':['HR','Finance']}})}})),
 DISCLOSURE:('schema:psl/hr-finance-disclosure/v1',obj({'source_view':KEY,'employee_key_semantics':{'const':'opaque_exact_case_sensitive'},'effective_until_semantics':{'enum':['inclusive','exclusive']},'route':{'const':'supplied_export_read_only'},'allowed_fields':FIELD_LIST,'recipient_ids':IDS,'purposes':{'type':'array','minItems':1,'maxItems':30,'uniqueItems':True,'items':KEY},'from_period':MONTH,'to_period':MONTH,'max_age_seconds':{'type':'integer','minimum':1},'retention_seconds':{'type':'integer','minimum':1},'retention_mode':{'const':'restrict_after_expiry'},'correction_route':TEXT,'source_evidence_id':ID}))}
BASIS_SCHEMA=obj({'snapshot_id':ID,'sha256':{'type':'string','pattern':'^[a-f0-9]{64}$'},'entity':KEY,'period':MONTH})
BASIS_SCHEMAS={'D07.effective_membership_ref':'schema:psl/hr-finance-membership/v1','D07.authorized_input_refs':'schema:psl/hr-finance-authorized-basis/v1'}
def handles(component,target):return component in SCHEMAS or component in BASIS_SCHEMAS and target.schema_ref==BASIS_SCHEMAS[component]
def validate_reference(component,target,case,runtime=False):
 if component in SCHEMAS:
  v=typed(target,*SCHEMAS[component])
  if component==AUTHORITY:
   seen=set()
   for r in v['assignments']:
    if r['role']!=('Finance' if r['purpose']=='receive' else 'HR'):raise ValidationError('HR owns disclosure/corrections; Finance receives')
    if not get_user_model().objects.filter(pk=r['user_id'],is_active=True).exists():raise ValidationError('Active actual human required')
    key=(r['user_id'],r['purpose'])
    if key in seen:raise ValidationError('Duplicate HR/Finance responsibility')
    seen.add(key)
  else:
   if not set(REQUIRED)<=set(v['allowed_fields']):raise ValidationError('Explicit identity/BU/effective-date fields required')
   if ('monthly_pay' in v['allowed_fields'])!=('currency' in v['allowed_fields']):raise ValidationError('Pay requires explicit currency and vice versa')
   if v['from_period']>v['to_period']:raise ValidationError('Disclosure periods reversed')
   if get_user_model().objects.filter(pk__in=v['recipient_ids'],is_active=True).count()!=len(v['recipient_ids']):raise ValidationError('Active actual recipients required')
   from apps.pmo.services import subject
   e=subject(case,v['source_evidence_id'],'hr_contract_source')
   if case.evidence.filter(kind=e.kind,version__gt=e.version).exists():raise ValidationError('Source-view evidence superseded')
   try:timezone.now()+timedelta(seconds=v['retention_seconds'])
   except (OverflowError,ValueError):raise ValidationError('Retention exceeds supported datetime range')
 else:
  v=typed(target,BASIS_SCHEMAS[component],BASIS_SCHEMA)
  from apps.finance.hrfinance import basis_snapshot,current_snapshot
  try:s=basis_snapshot(case,v);current_snapshot(s,for_use=True)
  except PermissionDenied:raise ValidationError('HR disclosure authority or recipient access no longer current')

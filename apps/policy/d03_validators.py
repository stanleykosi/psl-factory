from django.core.exceptions import ValidationError,PermissionDenied
from adapters.forecast import obj,KEY
from .document_validators import typed
STATEMENT='D03.verified_billing_statement';CONTROLS='D03.invoice_release_control_refs'
ID={'type':'integer','minimum':1};HASH={'type':'string','pattern':'^[a-f0-9]{64}$'}
REQUIREMENT=obj({'key':KEY,'evidence_kind':{'type':'string','pattern':'^d03_control_[a-z0-9_]{1,30}$'}})
REQUIREMENTS={'type':'array','maxItems':30,'items':REQUIREMENT}
IMPLEMENTATIONS=['internal_invoice_register_v1','incumbent_reference_only','unsupported_native']
REF={'source_id':ID,'source_sha256':HASH,'review_id':ID}
SCHEMAS={STATEMENT:('schema:psl/verified-billing-statement/v1',obj(REF)),CONTROLS:('schema:psl/invoice-release-evidence/v1',obj({**REF,'coverage_id':ID,'effect':{'enum':['issue','deliver']},'implementation':{'enum':IMPLEMENTATIONS},'flow_ref':KEY,'flow_version':KEY,'environment_ref':KEY,'max_age_seconds':{'type':'integer','minimum':1,'maximum':31536000},'requirements':REQUIREMENTS}))}
def validate_reference(component,target,case,runtime=False):
 v=typed(target,*SCHEMAS[component])
 from apps.finance import billing_evidence as d
 s=d.exact_source(case,v['source_id'])
 try:r=d.confirmed(s)
 except PermissionDenied:raise ValidationError('Finance source-confirmation authority/access is no longer current')
 if s.sha256!=v['source_sha256'] or r.pk!=v['review_id']:raise ValidationError('Exact current Finance-confirmed source/version/review required')
 if s.kind!=('statement' if component==STATEMENT else 'flow_contract'):raise ValidationError('Wrong source kind for D03 component')
 if component==STATEMENT and r.meaning=='unresolved':raise ValidationError('Unresolved prices/sign wording cannot activate a verified statement')
 if component==CONTROLS:
  from apps.finance.models import BillingCoverage
  from apps.finance.billing import coverage_current
  c=BillingCoverage.objects.filter(case=case,pk=v['coverage_id']).first()
  if not c or not coverage_current(c):raise ValidationError('Exact current billing coverage required')
  if any(v[k]!=s.payload[k] for k in ['flow_ref','flow_version','environment_ref']):raise ValidationError('Control policy differs from confirmed flow/environment version')
  if s.payload['implementation'] is None or v['implementation']!=s.payload['implementation']:raise ValidationError('Implementation must match the Finance-confirmed source contract')
  declared=s.payload['effect_requirements']
  if declared is None or declared[v['effect']] is None or v['requirements']!=declared[v['effect']]:raise ValidationError('Exact explicitly confirmed effect prerequisites required; unknown is not empty')
  if len({x['key'] for x in v['requirements']})!=len(v['requirements']):raise ValidationError('Distinct explicit control keys required')
def validate_collection(component,values):
 if component==CONTROLS and len({(x['coverage_id'],x['effect']) for x in values})!=len(values):raise ValidationError('One exact control contract per coverage/effect required')

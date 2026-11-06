"""F33 review configuration; no revenue formula is supplied or executed."""
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from adapters.forecast import obj
from .document_validators import typed
AUTHORITY='F33.authority_rules'
REVIEW='F33.recognition_review_rules'
ID={'type':'integer','minimum':1}
CATEGORIES=['estimate','completion','acceptance','price','cash']
SCHEMAS={
 AUTHORITY:('schema:psl/recognition-authority/v1',obj({'human_only':{'const':True},'assignments':{'type':'array','minItems':1,'maxItems':100,'items':obj({'user_id':ID,'purpose':{'enum':['attest','review']},'role':{'enum':['PM','Finance']}})}})),
 REVIEW:('schema:psl/recognition-review/v1',obj({'policy_evidence_id':ID,'required_categories':{'type':'array','minItems':1,'uniqueItems':True,'items':{'enum':['estimate','completion','acceptance','price']}},'independent_reviewer':{'type':'boolean'},'decision_reference_required':{'type':'boolean'},'accounting_execution':{'const':'external_human_decision_only'}}))}
def validate_reference(component,target,case,runtime=False):
 v=typed(target,*SCHEMAS[component])
 if case.kind!='project':raise ValidationError('F33 requires a project case')
 if component==AUTHORITY:
  keys=[]
  for r in v['assignments']:
   if r['role']!={'attest':'PM','review':'Finance'}[r['purpose']]:raise ValidationError('PM attests; Finance reviews')
   if not get_user_model().objects.filter(pk=r['user_id'],is_active=True).exists():raise ValidationError('Active actual human required')
   keys.append((r['user_id'],r['purpose']))
  if len(keys)!=len(set(keys)):raise ValidationError('Duplicate responsibility')
 else:
  from apps.core.models import Evidence
  e=Evidence.objects.filter(case=case,pk=v['policy_evidence_id'],kind='recognition_policy').first()
  if not e:raise ValidationError('Exact scoped recognition-policy evidence required')
  if Evidence.objects.filter(case=case,kind=e.kind,version__gt=e.version).exists():raise ValidationError('Recognition policy evidence superseded')

"""Supplemental engineering controls, not an invented Support SOP."""
from django.core.exceptions import ValidationError,PermissionDenied
from django.contrib.auth import get_user_model
from adapters.forecast import obj,KEY
from .document_validators import typed
from .schedule_validators import ID
FIELDS=['channel','customer_ref','transaction_ref','issue_ref','case_type','received_at','content_reference']
COMPONENT='B14.agent_projection'
VALUE=obj({'intake_ids':{'type':'array','minItems':1,'maxItems':100,'uniqueItems':True,'items':ID},'fields':{'type':'array','minItems':1,'maxItems':8,'uniqueItems':True,'items':{'enum':FIELDS}},'purpose':KEY,'projector_id':ID,'owner_id':ID,'reviewer_id':ID,'independent_review':{'type':'boolean'},'max_draft_chars':{'type':'integer','minimum':1,'maximum':12000},'review_ttl_seconds':{'type':'integer','minimum':1,'maximum':604800}})
SCHEMAS={COMPONENT:('schema:psl/support-agent-projection/v1',VALUE)}
def validate_reference(component,target,case,runtime=False):
 v=typed(target,*SCHEMAS[component])
 from apps.baas.support_models import SupportIntake
 if case.kind!='support' or SupportIntake.objects.filter(case=case,pk__in=v['intake_ids']).count()!=len(v['intake_ids']):raise ValidationError('Exact support case intake inventory required')
 if not runtime:
  from apps.identity.models import Grant
  from apps.baas import support
  for key,action,purpose in [('projector_id','support.agent.project','triage'),('owner_id','support.agent.draft','transition'),('reviewer_id','support.agent.review','summary')]:
   a=get_user_model().objects.filter(pk=v[key],is_active=True).first()
   if not a or not all(Grant.objects.filter(case=case,user=a,action=x,active=True).exists() for x in ['case.read','support.read','support.private.read','agent.data.read','agent.data.source',action]+(['support.own'] if key=='owner_id' else ['agent.data.project','evidence.add'] if key=='projector_id' else [])):raise ValidationError('Actual scoped source/draft principals required')
   try:support.authority(a,case,purpose)
   except (PermissionDenied,ValidationError):raise ValidationError('Current native Support and D05 authority required') from None
  if v['independent_review'] and v['reviewer_id'] in [v['owner_id'],v['projector_id']]:raise ValidationError('Independent Support reviewer required')

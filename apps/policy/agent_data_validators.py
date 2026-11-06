"""Engineering egress contract; values are explicit owner inputs, never defaults."""
from django.core.exceptions import ValidationError, PermissionDenied
from django.contrib.auth import get_user_model
from adapters.forecast import obj, KEY
from .document_validators import typed, ROLES

COMPONENT='INT.agent_data'
VALUE=obj({
 'contract_id':{'type':'integer','minimum':1},
 'evidence_ids':{'type':'array','minItems':1,'maxItems':100,'uniqueItems':True,'items':{'type':'integer','minimum':1}},
 'process_ids':{'type':'array','minItems':1,'maxItems':122,'uniqueItems':True,'items':KEY},
 'purpose':KEY,'sender_id':{'type':'integer','minimum':1},'sender_role':{'enum':ROLES},
 'reviewer_id':{'type':'integer','minimum':1},'reviewer_role':{'enum':ROLES},
 'independent_review':{'type':'boolean'},'max_input_chars':{'type':'integer','minimum':1,'maximum':12000},
 'max_output_chars':{'type':'integer','minimum':100,'maximum':16000},
 'max_requests':{'type':'integer','minimum':1,'maximum':100},
 'review_ttl_seconds':{'type':'integer','minimum':1,'maximum':604800},
 'lease_seconds':{'type':'integer','minimum':10,'maximum':120},
 'max_attempts':{'type':'integer','minimum':1,'maximum':10},
 'tools':{'const':[]},'data_scope':{'const':'reviewed_exact_quotes_v1'}})
SCHEMAS={COMPONENT:('schema:psl/agent-data/v1',VALUE)}

def validate_reference(component,target,case,runtime=False):
 v=typed(target,*SCHEMAS[component])
 from apps.workflows.readiness_models import IntegrationContract
 from apps.agents.boundary import permitted_source, process_allowed
 from apps.core.models import Evidence
 contract=IntegrationContract.objects.filter(pk=v['contract_id'],case=case,payload__kind='provider',payload__implementation='authenticated_json_v1').first()
 if not contract:raise ValidationError('Exact case provider gateway required')
 from adapters.factory_planner_contracts import PROTOCOL
 if contract.payload['contract_version']==PROTOCOL:raise ValidationError('Planning-only protocol cannot authorise private evidence extraction')
 for pk in v['evidence_ids']:
  e=Evidence.objects.filter(pk=pk,case=case).first()
  if not e or not permitted_source(e):raise ValidationError('Source needs a reviewed domain projection adapter')
 for process in v['process_ids']:process_allowed(case,process)
 if not runtime:
  from apps.identity.models import Grant
  from .services import decision_authority
  for stem,action in [('sender','agent.data.send'),('reviewer','agent.data.review')]:
   a=get_user_model().objects.filter(pk=v[stem+'_id'],is_active=True).first()
   if not a or not all(Grant.objects.filter(case=case,user=a,action=x,active=True).exists() for x in ['case.read','agent.data.read','agent.data.source',action]):raise ValidationError('Actual scoped data principal/grants required')
   for pk in v['evidence_ids']:
    e=Evidence.objects.get(pk=pk,case=case)
    if e.kind=='agent_private_ledger':
     from apps.finance.ledger_agents import projection_access
     try:projection_access(a,e.evidenceprojection_set.first())
     except PermissionDenied:raise ValidationError('Native private Finance source grants required for data principals') from None
     if v[stem+'_role']!='Finance':raise ValidationError('Finance role required for private Finance egress')
    if e.kind=='agent_private_support':
     from apps.baas.support_agent import source_access
     try:source_access(a,case)
     except PermissionDenied:raise ValidationError('Native support source grants required for data principals') from None
   try:decision_authority(a,case,v[stem+'_role'])
   except PermissionDenied:raise ValidationError('Actual current D05 data role required') from None
  if v['independent_review'] and v['sender_id']==v['reviewer_id']:raise ValidationError('Independent sender/reviewer required')

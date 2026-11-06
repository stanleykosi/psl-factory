from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from adapters.forecast import obj,KEY
from .document_validators import typed,ROLES
from .schedule_validators import ID
ROUTES='P02.owner_routes';CONTRACTS='P02.evidence_contracts'
GATE_ROLES={'qa_exit':['QA'],'uat_product_manager':['Product'],'uat_product_owner':['Product','Product Owner'],'uat_client':['Client'],'engineering_go':['Engineering','Engineering Lead'],'glpi_security':['Security Manager','Security Lead'],'glpi_cto':['CTO'],'glpi_ceo':['CEO'],'go_live_pm':['PM'],'go_live_client':['Client']}
ROUTE=obj({'kind':KEY,'gate_kind':{'anyOf':[KEY,{'type':'null'}]},'source_owner':{'type':'string','minLength':1,'maxLength':100},'owner_id':ID,'owner_role':{'enum':ROLES},'source_actor_ref':KEY,'system':KEY,'route_mode':{'enum':['internal_inbox_v1','unsupported_remote']}})
CONTRACT=obj({'kind':KEY,'contract_evidence_id':ID,'mode':{'enum':['owner_supplied_reference_v1','native_read_v1']},'signature_assurance':{'const':'reference_only'},'ordering':{'enum':['decided_at_monotonic_v1','unimplemented_native_order']},'max_age_seconds':{'type':'integer','minimum':1,'maximum':31536000},'required_subject_fields':{'type':'array','uniqueItems':True,'items':{'enum':['build_ref','release_ref']}},'reminders_enabled':{'type':'boolean'},'minimum_reminder_interval_seconds':{'type':'integer','minimum':1},'maximum_reminders':{'type':'integer','minimum':0,'maximum':20}})
SCHEMAS={ROUTES:('schema:psl/approval-owner-routes/v1',obj({'lease_seconds':{'type':'integer','minimum':15,'maximum':300},'max_attempts':{'type':'integer','minimum':1,'maximum':10},'routes':{'type':'array','minItems':1,'maxItems':50,'items':ROUTE}})),CONTRACTS:('schema:psl/approval-evidence-contracts/v1',obj({'contracts':{'type':'array','minItems':1,'maxItems':50,'items':CONTRACT}}))}
def validate_reference(component,target,case,runtime=False):
 from apps.pmo.gates import GATE_OWNERS
 from apps.pmo.services import subject
 from apps.identity.models import Grant
 v=typed(target,*SCHEMAS[component]);rows=v['routes' if component==ROUTES else 'contracts']
 if len({r['kind'] for r in rows})!=len(rows):raise ValidationError('Unambiguous prerequisite kind required')
 for r in rows:
  if component==ROUTES:
   planning_roles={'planning_scope':'Product Owner','planning_estimates':'Engineering Lead'}
   if r['kind'] in planning_roles and (r['gate_kind'] is not None or r['owner_role']!=planning_roles[r['kind']]):raise ValidationError('Planning scope and estimates retain their distinct source-prescribed owners')
   if r['gate_kind'] is not None and (r['gate_kind'] not in GATE_OWNERS or r['source_owner']!=GATE_OWNERS[r['gate_kind']]):raise ValidationError('Preserve exact source-prescribed gate owner label; mapping is not an authority transfer')
   if r['gate_kind'] is not None and r['owner_role'] not in GATE_ROLES[r['gate_kind']]:raise ValidationError('PMO cannot acquire another department gate through configuration')
   if not get_user_model().objects.filter(pk=r['owner_id'],is_active=True).exists():raise ValidationError('Actual active department owner required')
   if not runtime:
    from .services import decision_authority
    person=get_user_model().objects.get(pk=r['owner_id']);decision_authority(person,case,r['owner_role'])
    if not Grant.objects.filter(case=case,user=person,action='approval.receive',active=True).exists():raise ValidationError('Actual owner requires explicit case inbox receive grant')
  else:
   subject(case,r['contract_evidence_id'])
   if r['reminders_enabled'] and r['maximum_reminders']==0:raise ValidationError('Enabled reminders require a positive bounded budget')

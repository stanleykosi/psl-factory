"""D11 migration evidence parameters. No deployment or accounting policy defaults."""
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from adapters.forecast import obj,KEY
from .document_validators import typed,ROLES
from .validation_validators import process_ids,PROCESS_IDS
COMPONENT='D11.migration_evidence_rules'
KINDS=['backup','rollback','reconciliation','access','fallback','rollout','execution','restore']
ID={'type':'integer','minimum':1}
SCHEMAS={COMPONENT:('schema:psl/migration-evidence/v1',obj({
 'process_ids':PROCESS_IDS,
 'inventory_mode':{'enum':['local_evidence_manifest_v1','supplied_only_v1','unsupported_native']},
 'required_kinds':{'type':'array','minItems':1,'uniqueItems':True,'items':{'enum':KINDS}},
 'proof_systems':{'type':'array','minItems':1,'maxItems':30,'uniqueItems':True,'items':KEY},
 'max_age_seconds':{'type':'integer','minimum':1,'maximum':31536000},
 'allow_owner_preparer_review':{'type':'boolean'},
 'assignments':{'type':'array','minItems':2,'maxItems':2,'items':obj({'purpose':{'enum':['owner','independent']},'user_id':ID,'role':{'enum':ROLES}})}
}))}
def validate_reference(component,target,case,runtime=False):
 v=typed(target,*SCHEMAS[component]);process_ids(v['process_ids'])
 if {r['purpose'] for r in v['assignments']}!={'owner','independent'} or len({r['user_id'] for r in v['assignments']})!=2:raise ValidationError('Distinct actual owner and independent readiness reviewer required')
 from apps.identity.services import require
 from .services import decision_authority
 for r in v['assignments']:
  person=get_user_model().objects.filter(pk=r['user_id'],is_active=True).first()
  if not person:raise ValidationError('Actual active readiness principal required')
  if not runtime:
   decision_authority(person,case,r['role']);require(person,case,'migration.review');require(person,case,'migration.read');require(person,case,'migration.evidence.read')

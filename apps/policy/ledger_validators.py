from django.core.exceptions import ValidationError,PermissionDenied
from django.contrib.auth import get_user_model
from adapters.forecast import obj,KEY
from .document_validators import typed
from .schedule_validators import ID
RULES='F01.verification_rules'
AUTH='F01.review_authority'
RESOLUTION='F01.conflict_rules'
PROJECTION='F01.agent_projection'
HANDOFF='F01.validation_handoff'
PUBLICATION='F01.accepted_publication'
METADATA_FIELDS=['handoff','handoff_version','handoff_sha256','package','package_sha256','draft','draft_sha256','acceptance','af13_acceptance','classification']
FIELDS=['provider','realm','entity','source_reference','target_reference','transaction_date','accounting_period','incumbent_version']
SCHEMAS={RULES:('schema:psl/ledger-verification/v1',obj({'entity':KEY,'realm':KEY,'provider':{'const':'quickbooks'},'mode':{'const':'supplied_read_only'},'incumbent_user_references':{'type':'array','minItems':1,'maxItems':100,'uniqueItems':True,'items':KEY},'max_age_seconds':{'type':'integer','minimum':1,'maximum':31536000},'evidence_kind':{'const':'quickbooks_verification'},'treatment_evidence_ids':{'type':'array','minItems':1,'maxItems':100,'uniqueItems':True,'items':ID}})),AUTH:('schema:psl/ledger-authority/v1',obj({'independent_reviewer':{'type':'boolean'},'user_ids':{'type':'array','minItems':1,'maxItems':100,'uniqueItems':True,'items':ID}}))}
SCHEMAS[RESOLUTION]=('schema:psl/ledger-conflict-rules/v1',obj({'proposer_id':ID,'reviewer_id':ID,'independent_review':{'const':True},'allowed_modes':{'type':'array','minItems':1,'uniqueItems':True,'items':{'enum':['duplicate_alias','reference_correction']}},'allow_cross_case':{'type':'boolean'},'max_members':{'type':'integer','minimum':2,'maximum':100},'decision_ttl_seconds':{'type':'integer','minimum':1,'maximum':31536000},'basis':{'const':'exact_supplied_source_target_version'},'post_decision_verification':{'const':True},'posting_permitted':{'const':False}}))

SCHEMAS[PROJECTION]=('schema:psl/ledger-agent-projection/v1',obj({'lineage_ids':{'type':'array','minItems':1,'maxItems':100,'uniqueItems':True,'items':ID},'fields':{'type':'array','minItems':1,'maxItems':8,'uniqueItems':True,'items':{'enum':FIELDS}},'purpose':KEY,'projector_id':ID,'owner_id':ID,'reviewer_id':ID,'independent_review':{'const':True},'max_draft_chars':{'type':'integer','minimum':1,'maximum':12000},'review_ttl_seconds':{'type':'integer','minimum':1,'maximum':604800}}))

SCHEMAS[HANDOFF]=('schema:psl/finance-validation-handoff/v1',obj({'package_ids':{'type':'array','minItems':1,'maxItems':100,'uniqueItems':True,'items':ID},'recipient_id':ID,'acceptor_id':ID,'independent_acceptance':{'const':True},'freshness_seconds':{'type':'integer','minimum':1,'maximum':604800}}))

SCHEMAS[PUBLICATION]=('schema:psl/accepted-finance-publication/v1',obj({'handoff_ids':{'type':'array','minItems':1,'maxItems':100,'uniqueItems':True,'items':ID},'template_ids':{'type':'array','minItems':1,'maxItems':100,'uniqueItems':True,'items':ID},'fields':{'type':'array','minItems':1,'uniqueItems':True,'items':{'enum':METADATA_FIELDS}},'audience':{'enum':['internal','management','client']},'recipient_ids':{'type':'array','minItems':1,'maxItems':100,'uniqueItems':True,'items':ID},'reviewer_id':ID,'publisher_id':ID,'independent_review':{'const':True},'review_ttl_seconds':{'type':'integer','minimum':1,'maximum':604800}}))

def resolution_principal(case,v,key):
 from apps.finance.ledger import readable
 from apps.identity.services import require
 from .services import decision_authority
 a=get_user_model().objects.filter(pk=v[key+'_id'],is_active=True).first()
 if not a:raise ValidationError('Actual active resolution principal required')
 readable(a,case);require(a,case,'ledger.resolve' if key=='proposer' else 'ledger.resolve_review');decision_authority(a,case,'Finance');return a

def validate_reference(component,target,case,runtime=False):
 v=typed(target,*SCHEMAS[component])
 if component==PUBLICATION:
  from apps.finance.accepted_documents import validate_policy
  validate_policy(case,v,runtime);return
 if component==HANDOFF:
  from apps.finance import acceptance as handoff
  from apps.documents.validation_models import ValidationPackage
  packages=list(ValidationPackage.objects.filter(case=case,pk__in=v['package_ids']))
  if len(packages)!=len(v['package_ids']) or any('F01' not in p.payload['process_ids'] or HANDOFF in p.payload['policy_components'] for p in packages):raise ValidationError('Exact case F01 validation package inventory required')
  if v['recipient_id']==v['acceptor_id']:raise ValidationError('Independent recipient and acceptor required')
  if not runtime:
   try:
    for p in packages:
     for key in ['recipient','acceptor']:
      a=get_user_model().objects.filter(pk=v[key+'_id'],is_active=True).first()
      if not a:raise ValidationError('Actual active handoff principal required')
      handoff.participant(a,p,key,v)
   except PermissionDenied:raise ValidationError('Actual native private Finance/AF13 authority required') from None
  return
 if component==PROJECTION:
  from apps.finance.ledger_models import LedgerLineage
  if LedgerLineage.objects.filter(case=case,pk__in=v['lineage_ids']).count()!=len(v['lineage_ids']):raise ValidationError('Exact case F01 source inventory required')
  if v['reviewer_id'] in [v['projector_id'],v['owner_id']]:raise ValidationError('Independent Finance draft reviewer required')
  if not runtime:
   from apps.finance.ledger_agents import authority
   try:
    for key in ['projector','owner','reviewer']:
     a=get_user_model().objects.filter(pk=v[key+'_id'],is_active=True).first()
     if not a:raise ValidationError('Actual active Finance principal required')
     authority(a,case,key,value=v)
   except PermissionDenied:raise ValidationError('Actual private Finance source/action/D05 grants required') from None
  return
 if component==RESOLUTION:
  if v['proposer_id']==v['reviewer_id']:raise ValidationError('Independent Finance resolution reviewer required')
  if not runtime:
   try:
    for key in ['proposer','reviewer']:resolution_principal(case,v,key)
   except PermissionDenied:raise ValidationError('Actual scoped Finance role and resolution grants required') from None
  return
 if component==RULES:
  from apps.pmo.services import subject
  for pk in v['treatment_evidence_ids']:subject(case,pk)
 else:
  if get_user_model().objects.filter(pk__in=v['user_ids'],is_active=True).count()!=len(v['user_ids']):raise ValidationError('Actual active Finance principals required')

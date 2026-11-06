"""Explicit engineering receipt-gateway/clock contracts, not assumed vendor capabilities."""
from django.core.exceptions import ValidationError,PermissionDenied
from django.contrib.auth import get_user_model
from adapters.forecast import obj,KEY
from adapters.readiness import VERSION
from .document_validators import typed
from .schedule_validators import ID
RECEIPTS='B14.channel_receipts';CLOCK='B14.channel_clock'
CORRECTIONS='B14.clock_corrections'
RULE=obj({'contract_evidence_id':ID,'sender_ref':KEY,'target_key':{'type':'string','pattern':'^endpoint:[a-z][a-z0-9_.-]{0,79}$'},'credential_ref':{'type':'string','pattern':'^secret:[a-z][a-z0-9_.-]{0,79}$'},'credential_revision':KEY,'principal_ref':KEY,'contract_version':VERSION,'channel_ref':KEY,'account_ref':KEY,'customer_ref':KEY,'recipient_ref':KEY,'verifier_id':ID,'reviewer_id':ID,'independent_review':{'const':True},'review_ttl_seconds':{'type':'integer','minimum':1,'maximum':604800},'lease_seconds':{'type':'integer','minimum':10,'maximum':120},'max_attempts':{'type':'integer','minimum':1,'maximum':10},'protocol':{'const':'psl.support-receipt/v1'}})
CLOCK_RULE=obj({'attestor_id':ID,'basis':{'const':'reviewed_human_customer_delivery'},'late_event_handling':{'const':'hold_for_correction'},'max_receipt_age_seconds':{'type':'integer','minimum':1,'maximum':31536000}})
CORRECTION_RULE=obj({'proposer_id':ID,'reviewer_id':ID,'source_author_id':{'anyOf':[ID,{'type':'null'}]},'independent_review':{'const':True},'allowed_modes':{'type':'array','minItems':1,'uniqueItems':True,'items':{'enum':['revalidate','replace','late','withdraw']}},'allow_source_revision':{'type':'boolean'},'basis':{'const':'reviewed_human_customer_delivery'},'history_handling':{'const':'immutable_events_separate_metric_projection'},'max_receipt_age_seconds':{'type':'integer','minimum':1,'maximum':31536000},'review_ttl_seconds':{'type':'integer','minimum':1,'maximum':604800}})
SCHEMAS={RECEIPTS:('schema:psl/support-channel-receipts/v1',RULE),CLOCK:('schema:psl/support-channel-clock/v1',CLOCK_RULE),CORRECTIONS:('schema:psl/support-clock-corrections/v1',CORRECTION_RULE)}

def correction_principal(c,v,key):
 from apps.baas import support,support_channel
 a=get_user_model().objects.filter(pk=v[key+'_id'],is_active=True).first()
 if not a:raise ValidationError('Active configured correction principal required')
 support_channel.access(a,c,{'proposer':'correct','reviewer':'correct_review','source_author':'successor'}[key])
 support.authority(a,c,'summary' if key=='reviewer' else 'transition')
 return a
def principal(c,v,key):
 from apps.baas import support_agent as native,support
 from apps.identity.services import require
 a=get_user_model().objects.filter(pk=v[key+'_id'],is_active=True).first()
 if not a:raise ValidationError('Active configured channel principal required')
 native.source_access(a,c);require(a,c,'support.channel.'+{'verifier':'verify','reviewer':'review','attestor':'attest'}[key])
 support.authority(a,c,'summary' if key=='reviewer' else 'transition')
 return a

def validate_reference(component,target,case,runtime=False):
 v=typed(target,*SCHEMAS[component])
 if case.kind!='support':raise ValidationError('Exact Support scope required')
 from apps.baas import support
 if component==CORRECTIONS:
  if v['proposer_id']==v['reviewer_id']:raise ValidationError('Independent correction reviewer required')
  if v['allow_source_revision'] and v['source_author_id'] is None:raise ValidationError('Enabled source revision requires its actual author')
  if not runtime:
   try:
    for key in ['proposer','reviewer']+(['source_author'] if v['allow_source_revision'] else []):correction_principal(case,v,key)
   except PermissionDenied:raise ValidationError('Actual native source/correction/Support/D05 authority required') from None
  return
 if component==RECEIPTS:
  from apps.core.models import Evidence
  if not Evidence.objects.filter(case=case,pk=v['contract_evidence_id'],kind='agent_private_support_channel_contract').exists():raise ValidationError('Exact private channel protocol/meaning evidence required')
  if support.canonical(case)['customer_ref']!=v['customer_ref']:raise ValidationError('Exact canonical customer identity required')
  if v['verifier_id']==v['reviewer_id']:raise ValidationError('Independent channel reviewer required')
 else:
  _,metrics=support.config(case,'B14.metric_rules')
  if metrics['bot_acknowledgement_qualifies']:raise ValidationError('This human-delivery clock contract cannot qualify bot acknowledgements')
 if not runtime:
  try:
   for key in ['verifier','reviewer'] if component==RECEIPTS else ['attestor']:principal(case,v,key)
  except PermissionDenied:raise ValidationError('Actual native source/channel/Support/D05 authority required') from None

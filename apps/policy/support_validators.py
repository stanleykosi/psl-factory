from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from adapters.forecast import obj,KEY
from .document_validators import typed
from .schedule_validators import ID
INTAKE='B14.intake_rules';FLOW='B14.flow_rules';AUTH='B14.authority';METRICS='B14.metric_rules'
MEANINGS=['received','investigating','specialist_pending','resolved','unresolved','cancelled','merged']
ACTIONS=['investigate','await_specialist','resolve','reopen','cancel','mark_unresolved','resume']
EDGE=obj({'action':{'enum':ACTIONS},'from':KEY,'to':KEY,'evidence_kind':KEY,'require_specialist_result':{'type':'boolean'},'specialist_kind':{'enum':[None,'backend_reference','financial_corrective']}})
SCHEMAS={INTAKE:('schema:psl/support-intake/v1',obj({'channels':{'type':'array','minItems':1,'maxItems':30,'uniqueItems':True,'items':KEY},'case_types':{'type':'array','minItems':1,'maxItems':30,'uniqueItems':True,'items':KEY},'identity_method':{'const':'exact_customer_transaction_issue_v1'}})),FLOW:('schema:psl/support-flow/v1',obj({'specification_evidence_id':ID,'validation_mode':{'enum':['support_reviewed_definition','af13_required']},'validation_package_id':{'anyOf':[ID,{'type':'null'}]},'migration_mode':{'enum':['new_cases_only','reviewed_legacy_adoption']},'legacy_state_map':obj({'open':KEY,'resolved':KEY}),'initial':KEY,'states':{'type':'array','minItems':7,'maxItems':20,'items':obj({'key':KEY,'meaning':{'enum':MEANINGS}})},'edges':{'type':'array','minItems':1,'maxItems':50,'items':EDGE},'merge_enabled':{'type':'boolean'},'merge_source_states':{'type':'array','minItems':1,'uniqueItems':True,'items':KEY},'merge_target_states':{'type':'array','minItems':1,'uniqueItems':True,'items':KEY},'examples':{'type':'array','minItems':5,'maxItems':20,'items':obj({'scenario':{'enum':['normal','specialist','duplicate','reopened','unresolved']},'actions':{'type':'array','maxItems':20,'items':{'enum':ACTIONS}},'expected_state':KEY,'specialist_result_present':{'type':'boolean'},'expected_hold':{'type':'boolean'}})}})),AUTH:('schema:psl/support-authority/v1',obj({'independent_review':{'type':'boolean'},'assignments':{'type':'array','minItems':1,'maxItems':100,'items':obj({'user_id':ID,'role':{'enum':['Support','Engineering','Reconciliation']},'purposes':{'type':'array','minItems':1,'uniqueItems':True,'items':{'enum':['flow','triage','transition','merge','summary','specialist']}}})}})),METRICS:('schema:psl/support-metrics/v1',obj({'implementation':{'const':'elapsed_seconds_v1'},'bot_acknowledgement_qualifies':{'type':'boolean'},'reopen_basis':{'enum':['undefined','since_original_receipt','since_latest_reopen']},'oracles':{'type':'array','minItems':2,'maxItems':20,'items':obj({'receipt':{'type':'string'},'response':{'anyOf':[{'type':'string'},{'type':'null'}]},'resolution':{'anyOf':[{'type':'string'},{'type':'null'}]},'reopened':{'anyOf':[{'type':'string'},{'type':'null'}]},'expected':obj({'first_response_seconds':{'anyOf':[{'type':'string'},{'type':'null'}]},'resolution_seconds':{'anyOf':[{'type':'string'},{'type':'null'}]},'finding':{'anyOf':[KEY,{'type':'null'}]}})})}}))}
from .summary_validators import SCHEMAS as SUMMARY_SCHEMAS,validate_reference as validate_summary
SCHEMAS.update(SUMMARY_SCHEMAS)

def validate_reference(component,target,case,runtime=False):
 if component in SUMMARY_SCHEMAS:return validate_summary(component,target,case,runtime)
 from apps.pmo.services import subject
 v=typed(target,*SCHEMAS[component])
 if component==FLOW:
  subject(case,v['specification_evidence_id']);states={s['key']:s['meaning'] for s in v['states']}
  if len(states)!=len(v['states']) or len(set(states.values()))!=len(states) or set(states.values())!=set(MEANINGS) or states.get(v['initial'])!='received':raise ValidationError('Distinct configured states must cover all supported meanings and start at received')
  if states.get(v['legacy_state_map']['open']) in ['resolved','merged','cancelled'] or states.get(v['legacy_state_map']['open']) is None or states.get(v['legacy_state_map']['resolved'])!='resolved':raise ValidationError('Explicit valid legacy projection map required')
  if any(k not in states or states[k]=='merged' for k in v['merge_source_states']) or any(k not in states or states[k] in ['resolved','cancelled','merged'] for k in v['merge_target_states']):raise ValidationError('Explicit supported merge source/active target states required')
  seen=set()
  for e in v['edges']:
   key=(e['from'],e['action'])
   if key in seen or e['from'] not in states or e['to'] not in states or e['from']==e['to']:raise ValidationError('Distinct unambiguous state transitions required')
   seen.add(key)
   if (states[e['to']]=='specialist_pending')!=(e['action']=='await_specialist') or (e['action']=='await_specialist')!=(e['specialist_kind'] is not None):raise ValidationError('Explicit typed specialist wait required')
   if states[e['from']] in ['resolved','cancelled'] and e['action']!='reopen':raise ValidationError('Closed states leave only through explicit reopening')
   if e['action']=='resolve' and states[e['to']]!='resolved':raise ValidationError('Resolution action must identify resolved state')
   if states[e['from']]=='merged' or states[e['to']]=='merged':raise ValidationError('Merge uses the dedicated two-case human decision')
   if states[e['from']]=='specialist_pending' and states[e['to']]=='resolved' and not e['require_specialist_result']:raise ValidationError('Specialist result cannot be bypassed')
   if e['action']=='reopen' and (states[e['from']] not in ['resolved','cancelled'] or states[e['to']] in ['resolved','cancelled','merged']):raise ValidationError('Reopening requires a closed source and active target')
   if states[e['to']]=='resolved' and e['action']!='resolve':raise ValidationError('Resolution requires explicit resolve action')
  if {e['scenario'] for e in v['examples']}!=set(['normal','specialist','duplicate','reopened','unresolved']):raise ValidationError('Normal/specialist/duplicate/reopen/unresolved acceptance examples required')
  for example in v['examples']:
   state=v['initial'];hold=False
   for action in example['actions']:
    edge=next((e for e in v['edges'] if e['from']==state and e['action']==action),None)
    if not edge or (edge['require_specialist_result'] and not example['specialist_result_present']):hold=True;break
    state=edge['to']
   if state!=example['expected_state'] or hold!=example['expected_hold']:raise ValidationError('Flow differs from supplied acceptance example')
  if v['validation_mode']=='af13_required':
   from apps.documents.validation import package_for
   if not v['validation_package_id'] or 'B14' not in package_for(case,v['validation_package_id']).payload['process_ids']:raise ValidationError('Exact B14 AF13 package required')
 elif component==AUTH:
  keys=[]
  for r in v['assignments']:
   if not get_user_model().objects.filter(pk=r['user_id'],is_active=True).exists():raise ValidationError('Actual active principal required')
   if r['role']!='Support' and any(p!='specialist' for p in r['purposes']):raise ValidationError('Support owns flow and case decisions; other roles may supply specialist evidence only')
   keys.extend((r['user_id'],p) for p in r['purposes'])
  if len(keys)!=len(set(keys)):raise ValidationError('Unambiguous purpose authority required')
 elif component==METRICS:
  from apps.baas.support_metrics import elapsed
  if not any(o['expected']['finding'] is None and o['expected']['first_response_seconds'] is not None for o in v['oracles']) or not any(o['expected']['finding'] is not None for o in v['oracles']):raise ValidationError('Known and invalid/undefined metric oracles required')
  for o in v['oracles']:
   if elapsed(o['receipt'],o['response'],o['resolution'],o['reopened'],v)!=o['expected']:raise ValidationError('Metric differs from supplied oracle')

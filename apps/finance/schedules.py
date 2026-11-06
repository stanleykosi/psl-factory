"""Versioned income explanations and selected-scope schedule inventory, never a ledger."""
import re,json
from decimal import localcontext
from django.db import transaction
from django.core.exceptions import ValidationError,PermissionDenied
from django.contrib.auth import get_user_model
from apps.core.services import lock_case,event,bump
from apps.identity.models import Grant
from apps.identity.services import require
from apps.pmo.services import subject
from apps.documents.contracts import validate,digest
from apps.documents import validation as acceptance
from apps.policy.services import resolve,active_component,reference_values,decision_authority
from apps.policy.schedule_validators import INCOME,INVENTORY,AUTH,ID,DEC,scale
from adapters.forecast import obj,KEY
from adapters.schedules import SuppliedScheduleAdapter
from .models import FinanceRun
from .schedule_models import ScheduleWork,ScheduleReview,ScheduleAdjustment
from . import analysis
from .rules import decimal,number,total
NULL_ID={'anyOf':[ID,{'type':'null'}]}
IDS={'type':'array','maxItems':100,'uniqueItems':True,'items':ID}
KEYS={'type':'array','maxItems':100,'uniqueItems':True,'items':KEY}
ROW=obj({'key':KEY,'relationship':{'enum':['disaggregation','reclassification','additive']},'amount':DEC,'unit':KEY,'source_accounts':KEYS,'evidence_id':ID,'duplicate_state':{'enum':['not_assessed','already_represented','separately_justified']},'duplicate_resolution_evidence_id':NULL_ID,'adjustment_lines':{'type':'array','maxItems':100,'items':obj({'account':KEY,'amount':{'type':'string','maxLength':64}})}})
DETAIL=obj({'entity':KEY,'period':{'type':'string','pattern':r'^\d{4}-(0[1-9]|1[0-2])$'},'currency':KEY,'report_line':KEY,'source_unit':KEY,'target_unit':KEY,'rows':{'type':'array','minItems':1,'maxItems':100,'items':ROW}})
SCHEDULE=obj({'key':KEY,'purpose':{'type':'string','minLength':1,'maxLength':1000},'owner_id':NULL_ID,'dependencies':KEYS,'source_evidence_ids':IDS,'formula_evidence_ids':IDS,'manual_cell_evidence_ids':IDS,'consumer_refs':KEYS,'restricted':{'type':'boolean'},'validation_package_id':NULL_ID,'gaps':{'type':'array','maxItems':50,'uniqueItems':True,'items':{'type':'string','minLength':1,'maxLength':1000}}})
INVENTORY_BODY=obj({'workbook_evidence_id':NULL_ID,'coverage':{'enum':['partial','declared_complete']},'schedules':{'type':'array','minItems':1,'maxItems':100,'items':SCHEDULE}})

def readable(actor,case):
 for key in ['case.read','finance.read','schedules.read']:require(actor,case,key)

def locked(actor,case_id,action,expected=None):
 c=lock_case(actor,case_id,action,expected)
 list(Grant.objects.select_for_update().filter(case=c).order_by('pk'));readable(actor,c)
 return c

def exact(case,pk):
 w=ScheduleWork.objects.select_related('case','actor','parent','evidence').filter(case=case,pk=pk,kind__in=['income','inventory']).first()
 if not w:raise ValidationError('Select this case exact income/inventory version')
 return w

def policy_snapshot(case,key):
 p=resolve(key,case)
 return {'status':p.status,'id':p.configuration.pk if p.configuration else None}

def inputs(actor,case,kind,parent,payload):
 readable(actor,case);require(actor,case,'schedules.prepare')
 key=INCOME if kind=='income' else INVENTORY
 pins={'policy':policy_snapshot(case,key),'evidence':[]}
 if kind=='income':
  if not parent or parent.case_id!=case.pk or parent.kind!='mapping':raise ValidationError('Use this case exact Finance mapping note version')
  analysis.ensure_current(parent);require(actor,case,'finance.calculate')
  pins['parent']={'id':parent.pk,'key':parent.operation_key,'source_review':analysis.current_review(case,'source',source=parent.source)}
  ids={r['evidence_id'] for r in payload['rows']}|{r['duplicate_resolution_evidence_id'] for r in payload['rows'] if r['duplicate_resolution_evidence_id']}
 else:
  ids=set()
  if payload['workbook_evidence_id']:ids.add(payload['workbook_evidence_id'])
  pins['packages']=[]
  for s in payload['schedules']:
   ids.update(s['source_evidence_ids']+s['formula_evidence_ids']+s['manual_cell_evidence_ids'])
   if s['validation_package_id']:
    p=acceptance.package_for(case,s['validation_package_id']);acceptance.package_current(p)
    if 'F13' not in p.payload['process_ids']:raise ValidationError('Schedule validation package must cover F13')
    if p.reference!=s['key']:raise ValidationError('AF13 package reference must identify this exact schedule key; another schedule acceptance cannot be reused')
    reviews=[]
    for purpose in ['meaning','expectations','acceptance']:
     latest=acceptance.latest_review(p,purpose)
     try:r=acceptance.approved_review(p,purpose);valid=True
     except (ValidationError,PermissionDenied):valid=False
     reviews.append({'purpose':purpose,'id':latest.pk if latest else None,'valid':valid})
    pins['packages'].append({'schedule':s['key'],'id':p.pk,'sha256':p.sha256,'level':p.payload['level'],'reviews':reviews})
 for pk in sorted(ids):
  e=subject(case,pk);pins['evidence'].append([e.pk,e.sha256])
 return pins

def income_result(case,parent,payload):
 findings=[];rows=payload['rows'];result={'findings':findings,'parent_run_id':parent.pk,'report_line':payload['report_line'],'rows':rows,'ledger_posted':False,'source_written':False}
 policy=resolve(INCOME,case)
 if policy.status!='ACTIVE':return dict(result,status='held',findings=['income_rule_unconfigured'],parent_amount=None,adjusted_total=None)
 rule=reference_values(active_component(INCOME,case))[0]
 for k in ['entity','period','currency','report_line','source_unit','target_unit']:
  if payload[k]!=rule[k]:raise ValidationError('Income rule scope/unit differs: '+k)
 data=parent.result
 if any(payload[k]!=data[k] for k in ['entity','period','currency']) or payload['source_unit']!=data['unit']:raise ValidationError('Parent scope/unit differs; no implicit conversion')
 if analysis.certification_findings(parent):findings.append('parent_not_certifiable')
 selected=[r for r in data['rows'] if r['report_line']==payload['report_line']]
 if not selected:findings.append('parent_line_missing')
 amount=number(total(r['amount'] for r in selected));converted=scale(amount,rule['factor'])
 children=[];additive=[];reclasses=[];accounts={r['account'] for r in selected}
 seen=set()
 for r in rows:
  if r['unit']!=payload['target_unit']:raise ValidationError('Manual amount must already use the declared target unit; scale only parent once')
  if r['amount'] is None:findings.append('unknown_manual_amount:'+r['key'])
  else:decimal(r['amount'])
  relation=r['relationship']
  if relation not in rule['allowed_relationships']:findings.append('relationship_not_configured:'+r['key'])
  if relation=='disaggregation':
   children.append(r['amount'])
   if r['adjustment_lines']:raise ValidationError('A child breakdown cannot export an adjustment')
  else:
   (additive if relation=='additive' else reclasses).append(r['amount'])
   if r['duplicate_state']!='separately_justified':findings.append('duplicate_unresolved:'+r['key'])
   overlap=bool(accounts & set(r['source_accounts']))
   if overlap and (rule['source_overlap']=='hold' or not r['duplicate_resolution_evidence_id']):findings.append('source_overlap_requires_resolution:'+r['key'])
   for account in r['source_accounts']:
    identity=(relation,account)
    if identity in seen:findings.append('repeated_manual_source:'+r['key'])
    seen.add(identity)
   if r['adjustment_lines']:
    for line in r['adjustment_lines']:decimal(line['amount'])
    if r['amount'] is None or total(x['amount'] for x in r['adjustment_lines'])!=decimal(r['amount']):findings.append('adjustment_lines_do_not_reconcile:'+r['key'])
 with localcontext() as ctx:
  ctx.prec=512
  child=total(children);reclass=total(reclasses) if reclasses else decimal('0');extra=total(additive) if additive else decimal('0')
  residual=None if not children or child is None or converted is None else decimal(converted)-child
  if children and (residual is None or abs(residual)>decimal(rule['child_tolerance'],nonnegative=True)):findings.append('child_parent_difference')
  if reclass is None or reclass!=0:findings.append('reclassification_not_zero')
  final=None if converted is None or extra is None or reclass is None else number(decimal(converted)+extra+reclass)
  if final is not None:decimal(final)
 return dict(result,status='held' if findings else 'ready',parent_amount=amount,converted_parent=converted,factor=rule['factor'],child_total=number(child),child_residual=number(residual),additive_total=number(extra),reclassification_total=number(reclass),adjusted_total=final,target_unit=payload['target_unit'])

def inventory_result(case,payload,pins):
 policy=resolve(INVENTORY,case);rule=reference_values(active_component(INVENTORY,case))[0] if policy.status=='ACTIVE' else None
 findings=[];output=[];bykey={s['key']:s for s in payload['schedules']}
 missing=sorted(set(rule['required_keys'])-set(bykey)) if rule else []
 if not rule:findings.append('inventory_rule_unconfigured')
 if not payload['workbook_evidence_id']:findings.append('native_workbook_missing')
 if payload['coverage']!='declared_complete':findings.append('workbook_coverage_partial')
 for s in payload['schedules']:
  gaps=list(s['gaps'])
  if not payload['workbook_evidence_id']:gaps.append('workbook_missing')
  gaps.extend('missing_dependency:'+k for k in s['dependencies'] if k not in bykey)
  if not s['owner_id'] or not get_user_model().objects.filter(pk=s['owner_id'],is_active=True).exists():gaps.append('actual_owner_missing')
  if not s['source_evidence_ids']:gaps.append('source_links_missing')
  if not s['formula_evidence_ids']:gaps.append('formula_definition_missing')
  if not s['consumer_refs']:gaps.append('consumer_links_missing')
  package=next((p for p in pins['packages'] if p['schedule']==s['key']),None)
  if not package:gaps.append('owner_validation_package_missing')
  elif not all(r['valid'] for r in package['reviews']):gaps.append('current_owner_examples_acceptance_missing')
  else:
   p=acceptance.package_for(case,package['id']);meaning=acceptance.approved_review(p,'meaning')
   if meaning.actor_id!=s['owner_id']:gaps.append('meaning_review_not_actual_schedule_owner')
   source_evidence=set(acceptance.DiscoverySource.objects.filter(case=case,pk__in=p.payload['source_ids']).values_list('evidence_id',flat=True))
   required=set(s['source_evidence_ids']+s['formula_evidence_ids']+s['manual_cell_evidence_ids'])
   if payload['workbook_evidence_id']:required.add(payload['workbook_evidence_id'])
   if not required<=source_evidence:gaps.append('acceptance_does_not_bind_schedule_sources')
   if not rule or package['level'] not in rule['accepted_levels']:gaps.append('acceptance_level_not_configured')
  output.append({'key':s['key'],'included':not gaps and bool(rule),'gaps':sorted(set(gaps)),'acceptance_level':package['level'] if package else None})
 # A cycle or excluded upstream cannot be hidden behind accepted downstream evidence.
 visiting=set();done=set()
 def visit(key):
  if key in visiting:raise ValidationError('Schedule dependency cycle')
  if key in done:return
  visiting.add(key)
  for dep in bykey[key]['dependencies']:
   if dep in bykey:visit(dep)
  visiting.remove(key);done.add(key)
 for key in bykey:visit(key)
 for _ in output:
  for r in output:
   blocked=[k for k in bykey[r['key']]['dependencies'] if not next((x['included'] for x in output if x['key']==k),False)]
   if blocked:r['included']=False;r['gaps']=sorted(set(r['gaps']+['upstream_excluded:'+k for k in blocked]))
 if missing:findings.append('required_schedules_missing')
 if not rule or rule['monthly_performance']=='undecided':findings.append('monthly_performance_decision_pending')
 return {'status':'ready' if rule else 'held','findings':findings,'schedules':output,'missing_required':missing,'monthly_performance':rule['monthly_performance'] if rule else 'undecided','coverage':payload['coverage'],'complete_inventory':not findings and all(r['included'] for r in output),'native_workbook_verified':False,'ledger_posted':False}

@transaction.atomic
def prepare(actor,case_id,kind,reference,parent_id,payload,evidence_id,expected=None):
 c=locked(actor,case_id,'schedules.prepare',expected)
 if kind not in ['income','inventory'] or not isinstance(reference,str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:-]{0,99}',reference):raise ValidationError('Typed work kind/reference required')
 evidence=subject(c,evidence_id,'income_detail' if kind=='income' else 'schedule_inventory')
 if kind=='inventory':
  if parent_id is not None or payload is not None:raise ValidationError('Inventory is captured from exact supplied evidence, not replacement payload')
  payload=SuppliedScheduleAdapter().read(evidence)
 validate(DETAIL if kind=='income' else INVENTORY_BODY,payload)
 if len(json.dumps(payload,allow_nan=False))>100000:raise ValidationError('Bounded work payload required')
 rows=payload['rows'] if kind=='income' else payload['schedules']
 if len({r['key'] for r in rows})!=len(rows):raise ValidationError('Distinct detail/schedule keys required')
 if kind=='income':
  for row in rows:
   if row['amount'] is not None:decimal(row['amount'])
   for line in row['adjustment_lines']:decimal(line['amount'])
 parent=FinanceRun.objects.filter(case=c,pk=parent_id).first() if parent_id else None
 pins=inputs(actor,c,kind,parent,payload)
 result=income_result(c,parent,payload) if kind=='income' else inventory_result(c,payload,pins)
 intent={'case':str(c.pk),'actor':actor.pk,'kind':kind,'reference':reference,'payload':payload,'evidence':evidence.pk,'snapshot':pins}
 key=digest(intent);old=ScheduleWork.objects.filter(operation_key=key).first()
 if old:
  if ScheduleWork.objects.filter(case=c,kind=kind,reference=reference,version__gt=old.version).exists():raise ValidationError('Historical intent cannot replace the current version; supply revised evidence')
  return old
 version=(ScheduleWork.objects.filter(case=c,kind=kind,reference=reference).order_by('-version').values_list('version',flat=True).first() or 0)+1
 w=ScheduleWork.objects.create(case=c,reference=reference,version=version,kind=kind,parent=parent,payload=payload,snapshot=pins,result=result,sha256=digest({'intent':intent,'result':result}),operation_key=key,evidence=evidence,actor=actor)
 event(actor,c,'finance.schedule_prepared',work=w.pk,kind=kind,status=result['status'],ledger_posted=False);bump(c);return w

def current(w):
 if ScheduleWork.objects.filter(case=w.case,kind=w.kind,reference=w.reference,version__gt=w.version).exists():raise ValidationError('Work was superseded; preserve historical review and create a successor')
 w.actor.refresh_from_db(fields=['is_active'])
 if inputs(w.actor,w.case,w.kind,w.parent,w.payload)!=w.snapshot:raise ValidationError('Source, policy, acceptance or access changed; rebuild and review')
 return w

def authority(actor,w):
 readable(actor,w.case);require(actor,w.case,'schedules.review')
 config=active_component(AUTH,w.case);rules=reference_values(config)[0]
 if not any(a['user_id']==actor.pk and w.kind in a['purposes'] for a in rules['assignments']):raise PermissionDenied('Configured human Finance review authority required')
 if rules['independent_reviewer'] and actor.pk==w.actor_id:raise PermissionDenied('Independent reviewer required')
 return dict(decision_authority(actor,w.case,'Finance'),**{AUTH:config.pk})

def approved(w):
 current(w);r=w.reviews.order_by('-pk').first()
 if not r or r.verdict!='approve':raise ValidationError('Current exact human approval required')
 r.actor.refresh_from_db(fields=['is_active'])
 if authority(r.actor,w)!=r.authority or r.snapshot!=w.snapshot:raise ValidationError('Human authority or review context changed')
 return r

@transaction.atomic
def review(actor,case_id,work_id,verdict,evidence_id,note,expected=None):
 c=locked(actor,case_id,'schedules.review',expected);w=exact(c,work_id)
 if verdict not in ['approve','return','reject','revoke']:raise ValidationError('Typed human verdict required')
 analysis.note(note);auth=authority(actor,w)
 if verdict=='approve':
  current(w)
  if w.result['status']!='ready':raise ValidationError('Resolve dependent work holds before approval')
 if verdict=='revoke' and (not w.reviews.exists() or w.reviews.order_by('-pk').first().verdict!='approve'):raise ValidationError('Prior approval required for revocation')
 r=ScheduleReview.objects.create(work=w,verdict=verdict,authority=auth,snapshot=w.snapshot,evidence=subject(c,evidence_id,'finance_review'),note=note,actor=actor)
 event(actor,c,'finance.schedule_reviewed',work=w.pk,review=r.pk,verdict=verdict);bump(c);return r

@transaction.atomic
def export_adjustment(actor,case_id,work_id,kind,evidence_id,expected=None):
 c=locked(actor,case_id,'schedules.adjust',expected);require(actor,c,'finance.adjust');w=exact(c,work_id);r=approved(w)
 if w.kind!='income' or kind not in ['additive','reclassification']:raise ValidationError('Only reviewed reporting adjustments can be exported')
 rows=[x for x in w.payload['rows'] if x['relationship']==kind]
 rule=reference_values(active_component(INCOME,c))[0]
 if w.payload['source_unit']!=w.payload['target_unit'] or decimal(rule['factor'])!=1:raise ValidationError('Export needs a separately reviewed source-unit adjustment; income detail remains available')
 if not rows or any(not x['adjustment_lines'] for x in rows):raise ValidationError('Every selected manual adjustment needs exact source-unit account lines')
 lines=[line for row in rows for line in row['adjustment_lines']]
 if len(lines)>100:raise ValidationError('Adjustment line budget exceeded')
 old=ScheduleAdjustment.objects.filter(work=w,kind=kind).first()
 if old:
  if old.adjustment.evidence_id!=evidence_id:raise ValidationError('Existing export receipt has different evidence; reconcile prior intent')
  return old
 identities={(x['evidence_id'],x['key']) for x in rows}
 for previous in ScheduleAdjustment.objects.filter(work__case=c,work__parent__source_id=w.parent.source_id,kind=kind).select_related('work'):
  if previous.work.reference!=w.reference and identities & {(x['evidence_id'],x['key']) for x in previous.work.payload['rows'] if x['relationship']==kind}:raise ValidationError('Manual detail already exported under another reference; reconcile existing adjustment lineage')
 reference='schedule:'+digest({'reference':w.reference,'kind':kind})[:48]
 a=analysis.adjustment(actor,c.pk,w.parent.source_id,reference,kind,lines,evidence_id,'Reviewed income detail #'+str(w.pk)+'; independent Finance adjustment approval remains required',None)
 link=ScheduleAdjustment.objects.create(work=w,review=r,kind=kind,adjustment=a)
 event(actor,c,'finance.schedule_adjustment_exported',work=w.pk,adjustment=a.pk,ledger_posted=False);bump(c);return link

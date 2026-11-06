from apps.core.evidence_access import public_evidence,restricted
"""AF13 evidence discovery and selected-scope validation, never deployment or policy activation."""
import json
from django.db import transaction
from apps.finance import acceptance_evaluation as evaluation
from django.core.exceptions import ValidationError,PermissionDenied
from django.utils import timezone
from apps.core.services import lock_case,event,bump,add_evidence
from apps.identity.models import Grant
from apps.identity.services import require
from apps.policy.services import resolve,active_component,reference_values,decision_authority
from apps.policy.registry import components
from apps.policy.validation_validators import OWNER,ACCEPTANCE,PROCESS_IDS,process_ids
from apps.pmo.services import subject
from apps.pmo.clocks import aware
from apps.pmo.meetings import create_action,scoped_person
from .contracts import validate,digest
from .validation_models import DiscoverySource,ValidationExample,ValidationPackage,ValidationReview,ValidationReplay,ValidationFollowup
from adapters.forecast import obj,KEY
from adapters.validation_evidence import FrozenPackEvidenceAdapter,SuppliedReplayAdapter

ID={'type':'integer','minimum':1}
IDS={'type':'array','maxItems':100,'uniqueItems':True,'items':ID}
TEXT={'type':'string','maxLength':4000}
CLASSIFICATIONS=['documented_policy','source_description','narrated_practice','proposed_design','owner_clarification','test_evidence']
CLAUSE=obj({'key':KEY,'quote':{'type':'string','minLength':1,'maxLength':4000},'locator':{'type':'string','minLength':1,'maxLength':500},'classification':{'enum':CLASSIFICATIONS},'process_ids':PROCESS_IDS})
SOURCE=obj({'document_kind':{'enum':['support_sop','reconciliation_brief','pmo_sop','walkthrough','policy_amendment','test_report','other']},'source_version':{'anyOf':[{'type':'string','minLength':1,'maxLength':100},{'type':'null'}]},'source_date':{'anyOf':[{'type':'string','pattern':r'^\d{4}-\d{2}-\d{2}$'},{'type':'null'}]},'owner_label':{'anyOf':[{'type':'string','minLength':1,'maxLength':240},{'type':'null'}]},'classification':{'enum':CLASSIFICATIONS},'process_ids':PROCESS_IDS,'clauses':{'type':'array','maxItems':100,'items':CLAUSE}})
GAP=obj({'key':KEY,'description':{'type':'string','minLength':1,'maxLength':1000},'process_ids':PROCESS_IDS,'state':{'enum':['open','resolved']},'evidence_id':{'anyOf':[ID,{'type':'null'}]}})
PACKAGE=obj({'process_ids':PROCESS_IDS,'source_ids':dict(IDS,minItems=1),'example_ids':IDS,'policy_components':{'type':'array','maxItems':60,'uniqueItems':True,'items':KEY},'level':{'enum':['definition','synthetic_implementation','operational']},'purpose':{'enum':['B13','P13','P15']},'gaps':{'type':'array','maxItems':100,'items':GAP},'build_ref':TEXT,'role_list':{'type':'array','maxItems':100,'uniqueItems':True,'items':{'type':'string','minLength':1,'maxLength':240}},'manual_fallback':TEXT,'rollout_plan':TEXT,'migration_plan':TEXT,'support_owner_id':{'anyOf':[ID,{'type':'null'}]}})

def locked(actor,case_id,action,expected=None):
    from apps.finance.ledger import scope_lock
    scope_lock(case_id)
    case=lock_case(actor,case_id,action,expected)
    list(Grant.objects.select_for_update().filter(case=case).order_by('pk'))
    require(actor,case,'validation.read');require(actor,case,'case.read')
    evaluation.locked(case.pk)
    return case

def finite(value):
    try:body=json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)
    except (TypeError,ValueError):raise ValidationError('Use finite JSON values')
    if not isinstance(value,dict) or len(body)>16000:raise ValidationError('Use a bounded JSON object (16000 characters)')
    return digest(value)

def version(model,case,reference):
    if not isinstance(reference,str) or not reference.strip() or len(reference)>100:raise ValidationError('Bounded reference required')
    return (model.objects.filter(case=case,reference=reference).order_by('-version').values_list('version',flat=True).first() or 0)+1

def source_current(source):
    if DiscoverySource.objects.filter(case=source.case,reference=source.reference).order_by('-version').first().pk!=source.pk:raise ValidationError('Source version changed; reconcile the new clauses')
    if source.sha256!=digest({'metadata':source.metadata,'evidence':source.evidence.sha256}):raise ValidationError('Source content/hash mismatch')

@transaction.atomic
def capture_source(actor,case_id,reference,evidence_id,metadata,expected):
    from datetime import date
    case=locked(actor,case_id,'validation.source.capture',expected);e=subject(case,evidence_id);validate(SOURCE,metadata)
    if restricted(e):raise ValidationError('Restricted source receipts require their source-scoped interface')
    process_ids(metadata['process_ids'])
    if metadata['source_date'] is not None:
        try:source_date=date.fromisoformat(metadata['source_date'])
        except ValueError:raise ValidationError('Use an actual ISO calendar date or explicit unknown')
        if source_date>timezone.localdate():raise ValidationError('Actual source date cannot be in the future')
    keys=[]
    for c in metadata['clauses']:
        process_ids(c['process_ids']);keys.append(c['key'])
        if c['quote'] not in e.body or not set(c['process_ids'])<=set(metadata['process_ids']):raise ValidationError('Clause needs an exact source quote and declared process scope')
    if len(keys)!=len(set(keys)):raise ValidationError('Clause keys must be unique')
    r=DiscoverySource.objects.create(case=case,reference=reference,version=version(DiscoverySource,case,reference),evidence=e,metadata=metadata,sha256=digest({'metadata':metadata,'evidence':e.sha256}),actor=actor)
    event(actor,case,'validation.source_captured',source=r.pk,classification=metadata['classification'],authority_granted=False);bump(case);return r

@transaction.atomic
def import_pack(actor,case_id,path,reference,metadata,expected):
    case=locked(actor,case_id,'validation.source.capture',expected)
    body,sha=FrozenPackEvidenceAdapter().read(path)
    e=add_evidence(actor,case.pk,'procedure_source',body,'frozen-pack:'+path+'#'+sha)
    return capture_source(actor,case.pk,reference,e.pk,metadata,None)

@transaction.atomic
def capture_example(actor,case_id,reference,ids,scenario,expected_output,evidence_id,expected):
    case=locked(actor,case_id,'validation.example.capture',expected);process_ids(ids);finite(expected_output)
    if scenario not in ['normal','exception']:raise ValidationError('Choose normal or meaningful exception')
    r=ValidationExample.objects.create(case=case,reference=reference,version=version(ValidationExample,case,reference),process_ids=ids,scenario=scenario,expected=expected_output,evidence=subject(case,evidence_id),actor=actor)
    event(actor,case,'validation.example_captured',example=r.pk);bump(case);return r

def manifest(case,payload):
    sources=[];examples=[]
    for pk in payload['source_ids']:
        r=DiscoverySource.objects.filter(case=case,pk=pk).first()
        if not r:raise ValidationError('Source is outside this case')
        source_current(r);sources.append([r.pk,r.sha256])
    for pk in payload['example_ids']:
        e=ValidationExample.objects.filter(case=case,pk=pk).first()
        if not e:raise ValidationError('Example is outside this case')
        if ValidationExample.objects.filter(case=case,reference=e.reference).order_by('-version').first().pk!=e.pk:raise ValidationError('Example changed; new expectations review required')
        if not set(e.process_ids)<=set(payload['process_ids']):raise ValidationError('Example exceeds selected process scope')
        examples.append([e.pk,finite(e.expected),e.evidence.sha256])
    policies={}
    for key in payload['policy_components']:
        if key not in components() or key in [OWNER,ACCEPTANCE,'AF13.protection_acceptance_rules','AF13.protection_owner_rules']:raise ValidationError('Select existing independent domain components, not recursive AF13 authority rules')
        p=resolve(key,case);policies[key]={'status':p.status,'id':p.configuration.pk if p.configuration else None}
    return {'sources':sources,'examples':examples,'policies':policies}

@transaction.atomic
def prepare_package(actor,case_id,reference,payload,evidence_id,expected):
    case=locked(actor,case_id,'validation.package.prepare',expected);validate(PACKAGE,payload);process_ids(payload['process_ids'])
    # A generic revision cannot invalidate a private reference without source access.
    from apps.finance.acceptance import package_access
    for prior in ValidationPackage.objects.filter(case=case,reference=reference):package_access(actor,prior)
    keys=[]
    for g in payload['gaps']:
        process_ids(g['process_ids']);keys.append(g['key'])
        if not set(g['process_ids'])<=set(payload['process_ids']):raise ValidationError('Gap exceeds selected process scope')
        if g['evidence_id']:subject(case,g['evidence_id'])
        if g['state']=='resolved' and not g['evidence_id']:raise ValidationError('A claimed resolved gap needs scoped evidence')
    if len(keys)!=len(set(keys)):raise ValidationError('Gap keys must be unique')
    pins=manifest(case,payload)
    scope=set(payload['process_ids'])
    covered=set(p for source in DiscoverySource.objects.filter(case=case,pk__in=payload['source_ids']) for p in source.metadata['process_ids'])
    if not scope<=covered:raise ValidationError('Each selected process needs an identified supplied source (gaps may still remain)')
    r=ValidationPackage.objects.create(case=case,reference=reference,version=version(ValidationPackage,case,reference),payload=payload,manifest=pins,sha256=digest({'payload':payload,'manifest':pins}),evidence=subject(case,evidence_id),actor=actor)
    event(actor,case,'validation.package_prepared',package=r.pk,level=payload['level']);bump(case);return r

def _private_access(actor,p):
    from apps.finance.acceptance import package_access
    package_access(actor,p)

def package_for(case,pk):
    p=ValidationPackage.objects.select_related('case','actor').filter(case=case,pk=pk).first()
    if not p:raise ValidationError('Select this case validation package')
    return p

def package_current(p):
    if ValidationPackage.objects.filter(case=p.case,reference=p.reference).order_by('-version').first().pk!=p.pk:raise ValidationError('Package was revised; old reviews remain historical')
    if p.manifest!=manifest(p.case,p.payload):raise ValidationError('Bound source/example/domain-policy changed; create a revised package')

def owner_authority(actor,p,kind):
    require(actor,p.case,'validation.review' if kind!='acceptance' else 'validation.accept')
    from .protection_acceptance import binding as protection_binding
    protection=protection_binding(p)
    key='AF13.protection_owner_rules' if protection else OWNER
    config=active_component(key,p.case);v=reference_values(config)[0]
    rows=[r for r in v['assignments'] if r['user_id']==actor.pk and kind in r['purposes']]
    covered=set();pins={key:config.pk}
    for r in rows:
        relevant=set(r['process_ids']) & set(p.payload['process_ids'])
        if relevant:covered.update(relevant);pins.update(decision_authority(actor,p.case,r['role']))
    if not set(p.payload['process_ids'])<=covered:raise PermissionDenied('Human owner authority does not cover every selected process/purpose')
    from apps.finance.acceptance import package_access
    package_access(actor,p)
    preparers={p.actor_id}
    if kind=='expectations':preparers.update(ValidationExample.objects.filter(case=p.case,pk__in=p.payload['example_ids']).values_list('actor_id',flat=True))
    if not v['allow_preparer_review'] and actor.pk in preparers:raise PermissionDenied('Configured independent owner review required')
    return pins

def latest_review(p,kind):return p.reviews.filter(kind=kind).order_by('-pk').first()

def approved_review(p,kind):
    if p.finance_handoffs.exists() or hasattr(p,'private_readiness_packet') or hasattr(p,'private_protection_packet') or ValidationReplay.objects.filter(package=p,provenance__format__in=['psl.native-validation/v1','psl.native-validation/v2']).exists():return evaluation.confirmed(p.case_id,('af13',p.pk,kind),lambda:_approved_review(p,kind))
    return _approved_review(p,kind)

def _approved_review(p,kind):
    package_current(p);r=latest_review(p,kind)
    if not r or r.verdict!='approve':raise ValidationError('Current exact owner '+kind+' approval required')
    if owner_authority(r.actor,p,kind)!=r.authority:raise ValidationError('Owner authority changed; new review required')
    if r.snapshot!=review_inputs(p,kind,r.actor):raise ValidationError('Review inputs changed; new review required')
    return r

def example_coverage(p):
    rows=list(ValidationExample.objects.filter(case=p.case,pk__in=p.payload['example_ids']))
    missing=[f'{pid}/{kind}' for pid in p.payload['process_ids'] for kind in ['normal','exception'] if not any(pid in e.process_ids and e.scenario==kind for e in rows)]
    if missing:raise ValidationError('Owner examples missing: '+', '.join(missing))
    return rows

def review_inputs(p,kind,actor):
    package_current(p);value={'package':p.sha256}
    from apps.finance.acceptance import review_pins
    native=review_pins(p,actor)
    if native is not None:value['finance_handoff']=native
    from apps.finance.readiness_acceptance import review_pins as private_pins
    private=private_pins(p,actor,kind)
    if private is not None:value['private_readiness']=private
    from .protection_acceptance import review_pins as protection_pins
    protection=protection_pins(p,actor,kind)
    if protection is not None:value['private_protection']=protection
    if kind=='expectations':
        value['meaning']=approved_review(p,'meaning').pk;example_coverage(p)
    if kind=='acceptance':
        from apps.pmo.costing import package_readiness as costing_readiness
        costing=costing_readiness(p,actor)
        if costing['status']=='reassessment_required':raise ValidationError('Bound P14 calculation/oracle changed; reassess before acceptance')
        if costing['status']=='local_rule_oracle_verified':value['costing_binding']=costing['binding']
        value['meaning']=approved_review(p,'meaning').pk;expect=approved_review(p,'expectations');value['expectations']=expect.pk
        criteria=active_component('AF13.protection_acceptance_rules' if protection is not None else ACCEPTANCE,p.case);rules=reference_values(criteria)[0];value['criteria']=criteria.pk
        if p.payload['level']=='operational' and 'native_execution' not in rules:raise ValidationError('Configure native execution criteria; supplied reports and synthetic comparisons are insufficient')
        if p.payload['level'] not in rules['allowed_levels']:raise ValidationError('Selected acceptance level is not configured')
        if rules['independent_acceptor'] and actor.pk in [p.actor_id,expect.actor_id]:raise PermissionDenied('Configured independent acceptance principal required')
        if any(g['state']=='open' for g in p.payload['gaps']) or any(x['status']!='ACTIVE' for x in p.manifest['policies'].values()):raise ValidationError('Open evidence gaps or selected domain policy holds remain unresolved')
        value['replays']=[]
        if p.payload['level']!='definition':
            for key in ['build_ref','manual_fallback','rollout_plan','migration_plan']:
                if not p.payload[key].strip():raise ValidationError('Implementation acceptance needs explicit '+key)
            if not p.payload['role_list'] or not p.payload['support_owner_id']:raise ValidationError('Implementation acceptance needs role list and nominated support owner')
            scoped_person(p.case,p.payload['support_owner_id'],'validation.support')
            for e in example_coverage(p):
                r=ValidationReplay.objects.filter(package=p,example=e).order_by('-pk').first()
                if not r or r.expectation_review_id!=expect.pk or not r.result['matches']:raise ValidationError('Current matching evaluation after approved expectations required for every example')
                require(r.actor,p.case,'validation.replay.record')
                from .native_validation import native,current
                if native(r):current(r,actor)
                elif p.payload['level']=='operational' or r.provenance['evidence_class']!='synthetic_fixture' or not p.case.synthetic:raise ValidationError('Supplied external reports do not establish native operational or local synthetic implementation acceptance')
                if rules['independent_tester'] and r.actor_id in [p.actor_id,expect.actor_id]:raise PermissionDenied('Configured independent tester required')
                if rules['independent_acceptor'] and r.actor_id==actor.pk:raise PermissionDenied('Configured acceptor must be independent from evaluation recorder')
                value['replays'].append(r.pk)
    return value

@transaction.atomic
@evaluation.evaluated
def review(actor,case_id,package_id,kind,verdict,operation_key,evidence_id,reason,expected):
    case=locked(actor,case_id,'validation.accept' if kind=='acceptance' else 'validation.review',expected);p=package_for(case,package_id);_private_access(actor,p)
    if kind not in ['meaning','expectations','acceptance'] or verdict not in ['approve','return','disputed','reject','revoke']:raise ValidationError('Choose a typed review purpose and verdict')
    if not operation_key.strip() or len(operation_key)>100 or not reason.strip() or len(reason)>4000:raise ValidationError('Bounded operation key and actual review rationale required')
    e=subject(case,evidence_id)
    old=ValidationReview.objects.filter(package=p,operation_key=operation_key).first()
    if old:
        if (old.actor_id,old.kind,old.verdict,old.evidence_id,old.reason)!=(actor.pk,kind,verdict,e.pk,reason):raise ValidationError('Review key conflicts with previous intent')
        return old # historical receipt, never a current-use assertion
    authority=owner_authority(actor,p,kind)
    if verdict=='revoke' and (not latest_review(p,kind) or latest_review(p,kind).verdict!='approve'):raise ValidationError('Only a prior approval can be revoked')
    pins=review_inputs(p,kind,actor) if verdict=='approve' else {'package':p.sha256}
    r=ValidationReview.objects.create(package=p,kind=kind,verdict=verdict,operation_key=operation_key,authority=authority,snapshot=pins,evidence=e,reason=reason,actor=actor)
    evaluation.changed();event(actor,case,'agent.data.finance_validation_review' if p.finance_handoffs.exists() or hasattr(p,'private_readiness_packet') or hasattr(p,'private_protection_packet') else 'validation.review_recorded',review=r.pk,kind=kind,verdict=verdict,production_authorized=False);bump(case);return r

@transaction.atomic
@evaluation.evaluated
def record_replay(actor,case_id,package_id,evidence_id,operation_key,expected):
    case=locked(actor,case_id,'validation.replay.record',expected);p=package_for(case,package_id);_private_access(actor,p);evidence=subject(case,evidence_id)
    v=SuppliedReplayAdapter().read(evidence);finite(v['actual'])
    if not operation_key.strip() or len(operation_key)>100:raise ValidationError('Bounded replay operation key required')
    old=ValidationReplay.objects.filter(package=p,operation_key=operation_key).first()
    if old:
        if old.actor_id!=actor.pk or old.evidence_id!=evidence.pk:raise ValidationError('Replay operation key conflicts with prior report')
        return old
    approved=approved_review(p,'expectations')
    example=ValidationExample.objects.filter(case=case,pk=v['example_id']).first()
    if not example or example.pk not in p.payload['example_ids'] or v['build_ref']!=p.payload['build_ref']:raise ValidationError('Report must bind the selected example and exact build')
    if v['evidence_class']=='synthetic_fixture' and not case.synthetic:raise ValidationError('Synthetic replay cannot enter an operational case')
    actual_hash=finite(v['actual']);expected_hash=finite(example.expected)
    row=ValidationReplay.objects.create(package=p,example=example,expectation_review=approved,operation_key=operation_key,actual=v['actual'],provenance={k:x for k,x in v.items() if k not in ['actual','example_id']},result={'matches':actual_hash==expected_hash,'implementation':'json_equality/v1','actual_sha256':actual_hash,'expected_sha256':expected_hash,'execution_evidence':'supplied_report_only','underlying_workflow_executed':False},evidence=evidence,actor=actor)
    evaluation.changed();event(actor,case,'agent.data.finance_validation_replay' if hasattr(p,'private_readiness_packet') or hasattr(p,'private_protection_packet') else 'validation.report_compared',replay=row.pk,matches=row.result['matches']);bump(case);return row

@transaction.atomic
def followup(actor,case_id,package_id,gap_key,owner_id,due_at,evidence_id,reason,expected):
    case=locked(actor,case_id,'validation.followup',expected);p=package_for(case,package_id);_private_access(actor,p)
    gap=next((g for g in p.payload['gaps'] if g['key']==gap_key and g['state']=='open'),None)
    if not gap:raise ValidationError('Select an actual open gap in this exact package')
    old=ValidationFollowup.objects.filter(package=p,gap_key=gap_key).first()
    if old:return old
    if owner_id is None or due_at is None:raise ValidationError('Assign an actual owner and explicit deadline')
    due=aware(due_at)
    item=create_action(actor,case.pk,f'AF13-{p.pk}-{gap_key}'[:160],gap['description'],owner_id,due,evidence_id,reason,None)
    row=ValidationFollowup.objects.create(package=p,gap_key=gap_key,action=item,actor=actor);event(actor,case,'agent.data.finance_validation_followup' if hasattr(p,'private_readiness_packet') or hasattr(p,'private_protection_packet') else 'validation.followup_created',followup=row.pk);return row

@transaction.atomic
@evaluation.evaluated
def position(p,actor=None):
    from apps.finance.ledger import scope_lock
    scope_lock(p.case_id);evaluation.locked(p.case_id)
    from apps.finance.acceptance import package_access
    package_access(actor,p)
    holds=[]
    try:package_current(p)
    except (ValidationError,PermissionDenied) as exc:holds.append(str(exc))
    reviews={}
    for kind in ['meaning','expectations','acceptance']:
        r=latest_review(p,kind)
        try:approved_review(p,kind);state='current_approved'
        except (ValidationError,PermissionDenied,ConnectionError) as exc:state=str(exc)
        reviews[kind]={'latest':r.pk if r else None,'verdict':r.verdict if r else 'pending','use_status':state}
    from .migration_readiness import package_readiness
    migration=package_readiness(p,actor)
    from apps.pmo.costing import package_readiness as costing_readiness
    costing=costing_readiness(p,actor)
    return {'costing_readiness':costing,'migration_readiness':migration,'package':p.pk,'level':p.payload['level'],'scope':p.payload['process_ids'],'holds':holds,'reviews':reviews,'production_authorized':False,'policy_activated':False}

@transaction.atomic
@evaluation.evaluated
def acceptance_report(actor,case_id,review_id):
    from apps.core.models import Case
    case=locked(actor,case_id,'validation.export')
    r=ValidationReview.objects.select_related('package__case').filter(package__case=case,pk=review_id,kind='acceptance').first()
    if not r:raise ValidationError('Select this case acceptance record')
    state=position(r.package,actor)
    return {'review':r.pk,'verdict':r.verdict,'package':r.package_id,'sha256':r.package.sha256,'status':state,'requested_record_is_current':state['reviews']['acceptance']['latest']==r.pk and state['reviews']['acceptance']['use_status']=='current_approved','reported_evidence_only':True,'deployment_authorized':False,'whole_product_accepted':False}

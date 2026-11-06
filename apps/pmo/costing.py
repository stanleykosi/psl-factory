"""P14 evidence discovery, declared calculation and independent examples; no invented model approvals."""
from django.db import transaction
from django.core.exceptions import ValidationError,PermissionDenied
from django.contrib.auth import get_user_model
from apps.core.services import lock_case,event,bump,add_evidence
from apps.identity.models import Grant
from apps.identity.services import require
from apps.documents.contracts import digest,validate
from apps.policy.services import active_component,reference_values,decision_authority
from apps.policy.costing_validators import COMPONENT
from adapters.costing import SuppliedCostingContractAdapter,graph,calculate,compare,read,ARRAY,VALUE,KEY
from .services import subject
from .costing_models import CostingRule,CostingOracle,CostingReview,CostingRun,CostingBinding,CostingAF13Binding

def readable(a,c,source=False):
    if not get_user_model().objects.filter(pk=a.pk,is_active=True).exists():raise PermissionDenied('Current active principal required')
    require(a,c,'case.read');require(a,c,'costing.read')
    if source:require(a,c,'costing.source.read')

def locked(a,case_id,action,expected=None):
    c=lock_case(a,case_id,action,expected);list(Grant.objects.select_for_update().filter(case=c).order_by('pk'));readable(a,c)
    if c.kind!='project':raise ValidationError('Exact project costing scope required')
    return c

def rule_for(c,pk):
    r=CostingRule.objects.select_related('case','actor').filter(case=c,pk=pk).first()
    if not r:raise ValidationError('Exact case costing rule required')
    return r

def oracle_for(r,pk):
    o=CostingOracle.objects.filter(rule=r,pk=pk).first()
    if not o:raise ValidationError('Oracle must identify this exact rule')
    return o

def current_source(r,o=None):
    if CostingRule.objects.filter(case=r.case,reference=r.reference,version__gt=r.version).exists() or r.sha256!=digest(r.payload):raise ValidationError('Rule source superseded or hash changed')
    if o and (o.rule_id!=r.pk or o.sha256!=digest(o.payload) or CostingOracle.objects.filter(rule=r,reference=o.reference,version__gt=o.version).exists()):raise ValidationError('Independent oracle changed; revalidate expectations')

@transaction.atomic
def capture_rule(a,case_id,reference,evidence_id,expected=None,predecessor=None):
    c=locked(a,case_id,'costing.capture',expected);readable(a,c,True);validate(KEY,reference);e=subject(c,evidence_id,'p14_rule');v=SuppliedCostingContractAdapter().read_rule(e);graph(v)
    if not c.synthetic and v['source_class']=='synthetic_fixture':raise ValidationError('Synthetic calculator cannot enter operational scope')
    if v['owner_id'] is not None and v['owner_id']==v['oracle_owner_id']:raise ValidationError('Independent oracle owner must differ from rule owner')
    for param in v['parameters']:subject(c,param['evidence_id'],'p14_parameter')
    old=CostingRule.objects.filter(case=c,reference=reference).order_by('-version').first()
    if old and old.sha256==digest(v):return old
    if (old.pk if old else None)!=predecessor:raise ValidationError('Explicit current rule predecessor required')
    r=CostingRule.objects.create(case=c,reference=reference,version=old.version+1 if old else 1,payload=v,sha256=digest(v),evidence=e,actor=a);event(a,c,'costing.rule_captured',rule=r.pk,native_workbook_verified=False);bump(c);return r

@transaction.atomic
def capture_oracle(a,case_id,rule_id,reference,evidence_id,expected=None,predecessor=None):
    c=locked(a,case_id,'costing.oracle.capture',expected);readable(a,c,True);r=rule_for(c,rule_id);current_source(r);validate(KEY,reference);e=subject(c,evidence_id,'p14_oracle');v=SuppliedCostingContractAdapter().read_oracle(e)
    if any(v[k]!=r.payload[k] for k in ['calculator_ref','calculator_version']) or v['rule_sha256']!=r.sha256:raise ValidationError('Oracle must pin exact calculator/rule version')
    if not c.synthetic and v['source_class']=='synthetic_fixture':raise ValidationError('Synthetic examples cannot enter operational scope')
    if len({x['key'] for x in v['scenarios']})!=len(v['scenarios']) or {x['scenario'] for x in v['scenarios']}!={'normal','exception'}:raise ValidationError('Distinct independent normal and exception examples required')
    # Capture mismatches now; only dependent confirmation/activation holds.
    for row in v['scenarios']:calculate(r.payload,row['inputs'])
    old=CostingOracle.objects.filter(rule=r,reference=reference).order_by('-version').first()
    if old and old.sha256==digest(v):return old
    if (old.pk if old else None)!=predecessor:raise ValidationError('Explicit current oracle predecessor required')
    o=CostingOracle.objects.create(rule=r,reference=reference,version=old.version+1 if old else 1,payload=v,sha256=digest(v),evidence=e,actor=a);event(a,c,'costing.oracle_captured',oracle=o.pk);bump(c);return o

def authority(a,r,o=None):
    readable(a,r.case,True);require(a,r.case,'costing.oracle.review' if o else 'costing.rule.review');v=r.payload
    if v['oracle_owner_id' if o else 'owner_id'] is None or v['oracle_role' if o else 'owner_role'] is None:raise ValidationError('Configure the relevant actual costing evidence owner and role before confirmation')
    if a.pk!=v['oracle_owner_id' if o else 'owner_id']:raise PermissionDenied('Exact configured costing evidence owner required; case approval grants do not appoint model owners')
    if o and a.pk in [r.actor_id,v['owner_id']]:raise PermissionDenied('Oracle reviewer must be independent of rule preparer and owner')
    return decision_authority(a,r.case,v['oracle_role' if o else 'owner_role'])

def oracle_results(r,o,require_match=False):
    rows=[];known=held=False
    for x in o.payload['scenarios']:
        actual=calculate(r.payload,x['inputs']);match=compare(actual,x['expected']);known|=actual['status']=='known';held|=actual['status']=='held';rows.append({'key':x['key'],'matches':match,'actual':actual,'expected_sha256':digest(x['expected'])})
    if require_match and (not all(x['matches'] for x in rows) or not known or not held):raise ValidationError('Independent examples must match and cover known and held/unknown outcomes')
    return rows

@transaction.atomic
def review(a,case_id,rule_id,oracle_id,verdict,operation_key,evidence_id,expected=None):
    c=locked(a,case_id,'costing.oracle.review' if oracle_id else 'costing.rule.review',expected);r=rule_for(c,rule_id);o=oracle_for(r,oracle_id) if oracle_id else None;auth=authority(a,r,o);validate(KEY,operation_key)
    if verdict not in ['confirm','dispute','withdraw']:raise ValidationError('Typed source confirmation disposition required')
    e=subject(c,evidence_id,'p14_review');pins={'rule':r.sha256,'oracle':o.sha256 if o else None};old=CostingReview.objects.filter(rule=r,operation_key=operation_key).first()
    if old:
        if (old.actor_id,old.oracle_id,old.verdict,old.evidence_id)!=(a.pk,oracle_id,verdict,e.pk):raise ValidationError('Review key conflicts with historical intent')
        return old
    if verdict=='confirm':
        current_source(r,o)
        if o:confirmed(r);oracle_results(r,o,True)
    row=CostingReview.objects.create(rule=r,oracle=o,verdict=verdict,operation_key=operation_key,authority=auth,snapshot=pins,evidence=e,actor=a);event(a,c,'costing.evidence_reviewed',review=row.pk,case_cost_approved=False);bump(c);return row

def confirmed(r,o=None):
    current_source(r,o);row=CostingReview.objects.filter(rule=r,oracle=o).select_related('actor').order_by('-pk').first()
    if not row or row.verdict!='confirm':raise ValidationError('Current rule/independent oracle confirmation required')
    if row.authority!=authority(row.actor,r,o) or row.snapshot!={'rule':r.sha256,'oracle':o.sha256 if o else None}:raise ValidationError('Evidence owner authority/source changed')
    return row

def configured(c):
    p=active_component(COMPONENT,c);v=reference_values(p)[0];r=rule_for(c,v['rule_id']);o=oracle_for(r,v['oracle_id']);return p,r,o,v

@transaction.atomic
def run(a,case_id,plan_id,engineering_id,security_id,inputs_id,operation_key,expected=None):
    c=locked(a,case_id,'costing.calculate',expected);readable(a,c,True);validate(KEY,operation_key);p,r,o,v=configured(c)
    sources={k:subject(c,pk,kind) for k,pk,kind in [('plan',plan_id,'plan'),('engineering',engineering_id,'engineering_estimate'),('security',security_id,'security_estimate')]};e=subject(c,inputs_id,'p14_inputs');inputs=read(e.body,ARRAY(VALUE,1));pins={'policy':p.pk,'contract':v,'sources':{k:[ev.pk,ev.sha256] for k,ev in sources.items()},'inputs_sha256':e.sha256}
    old=CostingRun.objects.filter(case=c,operation_key=operation_key).first()
    if old:
        if old.snapshot!=pins or old.actor_id!=a.pk or old.evidence_id!=e.pk:raise ValidationError('Calculation key conflicts; never overwrite a prior calculation')
        return old
    result=calculate(r.payload,inputs);result['oracle_results']=oracle_results(r,o,True)
    row=CostingRun.objects.create(case=c,rule=r,operation_key=operation_key,snapshot=pins,inputs=inputs,result=result,evidence=e,actor=a);event(a,c,'costing.calculated',run=row.pk,status=result['status']);bump(c);return row

def current_run(row,require_known=True):
    readable(row.actor,row.case,True);require(row.actor,row.case,'costing.calculate');p,r,o,v=configured(row.case)
    if row.rule_id!=r.pk or row.snapshot['policy']!=p.pk or row.snapshot['contract']!=v:raise ValidationError('Costing policy/rule/oracle changed; calculate a new exact version')
    if require_known and row.result['status']!='known':raise ValidationError('Unknown costing cannot become commercial costing evidence')
    return r,o

@transaction.atomic
def bind(a,case_id,run_id,expected=None):
    c=locked(a,case_id,'costing.bind',expected);readable(a,c,True);row=CostingRun.objects.select_related('case','actor').filter(case=c,pk=run_id).first()
    if not row:raise ValidationError('Exact case calculation required')
    current_run(row);old=CostingBinding.objects.filter(run=row).first()
    if old:return old
    # Deliberately no amounts/raw source in generic commercial evidence.
    e=add_evidence(a,c.pk,'costing','P14 declared calculation #'+str(row.pk)+'; exact source/independent oracle lineage '+digest(row.snapshot)+'; existing case-cost approvals still required','local:p14-calculation')
    b=CostingBinding.objects.create(run=row,costing=e,snapshot={'run':digest(row.snapshot),'plan':row.snapshot['sources']['plan'][0]},actor=a);event(a,c,'costing.bound',binding=b.pk);bump(c);return b

def verify_costing(cost,plan_id):
    b=CostingBinding.objects.select_related('run__case','run__actor','actor').filter(costing=cost).first()
    if not b:return # Legacy supplied costing remains independent; no global invented gate.
    readable(b.actor,cost.case,True);require(b.actor,cost.case,'costing.bind');current_run(b.run)
    if b.snapshot!={'run':digest(b.run.snapshot),'plan':plan_id}:raise ValidationError('Generated costing belongs to another exact plan')

def af13_examples(p,o):
    from apps.documents.validation_models import ValidationExample
    examples=list(ValidationExample.objects.filter(case=p.case,pk__in=p.payload['example_ids']))
    for scenario in o.payload['scenarios']:
        expected_output={'oracle_sha256':o.sha256,'scenario_sha256':digest(scenario)}
        if not any(ex.scenario==scenario['scenario'] and ex.expected==expected_output and ex.process_ids==['P14'] for ex in examples):raise ValidationError('AF13 examples must pin every independently reviewed oracle scenario/input/output')

@transaction.atomic
def bind_af13(a,case_id,run_id,package_id,expected=None):
    from apps.documents import validation as af
    c=locked(a,case_id,'costing.af13.bind',expected);readable(a,c,True);row=CostingRun.objects.select_related('case','actor').filter(case=c,pk=run_id).first()
    if not row:raise ValidationError('Exact case calculation required')
    r,o=current_run(row);p=af.package_for(c,package_id);af.package_current(p)
    if (hasattr(p,'private_readiness_packet') or hasattr(p,'private_protection_packet')):raise ValidationError('Private readiness evidence needs its scoped native adapter')
    if p.payload['process_ids']!=['P14'] or COMPONENT not in p.payload['policy_components']:raise ValidationError('Exact P14 package and selected costing policy required; no wider readiness claim')
    af13_examples(p,o)
    # Existing AF13 human reviews remain independent; do not create acceptance here.
    approved={kind:af.approved_review(p,kind) for kind in ['meaning','expectations']}
    for rr in approved.values():readable(rr.actor,c,True)
    reviews={kind:rr.pk for kind,rr in approved.items()}
    pins={'run':digest(row.snapshot),'package':p.sha256,'reviews':reviews,'oracle_results_sha256':digest(row.result['oracle_results'])}
    old=CostingAF13Binding.objects.filter(run=row,package=p).first()
    if old:
        if old.snapshot!=pins:raise ValidationError('AF13 reviews changed; prepare a new exact package')
        return old
    b=CostingAF13Binding.objects.create(run=row,package=p,snapshot=pins,actor=a);event(a,c,'costing.af13_bound',binding=b.pk,acceptance_granted=False);bump(c);return b

def package_readiness(p,a=None):
    b=CostingAF13Binding.objects.filter(package=p).select_related('run__case','run__actor','actor').order_by('-pk').first()
    if not b:return {'status':'not_bound','native_workbook_verified':False}
    try:
        if a:readable(a,p.case)
        readable(b.actor,p.case,True);require(b.actor,p.case,'costing.af13.bind');r,o=current_run(b.run);af13_examples(p,o)
        from apps.documents.validation import approved_review,package_current
        package_current(p)
        reviews={k:approved_review(p,k) for k in ['meaning','expectations']}
        for rr in reviews.values():readable(rr.actor,p.case,True)
        if b.snapshot['reviews']!={k:rr.pk for k,rr in reviews.items()}:raise ValidationError('AF13 reviews changed')
        return {'status':'local_rule_oracle_verified','binding':b.pk,'run':b.run_id,'native_workbook_verified':False,'acceptance_granted':False}
    except (ValidationError,PermissionDenied):return {'status':'reassessment_required','binding':b.pk,'native_workbook_verified':False}

@transaction.atomic
def report(a,case_id,run_id):
    c=locked(a,case_id,'costing.read');row=CostingRun.objects.select_related('case','actor').filter(case=c,pk=run_id).first()
    if not row:raise ValidationError('Exact case calculation required')
    holds=[]
    try:current_run(row)
    except (ValidationError,PermissionDenied) as exc:holds.append(str(exc))
    value={'run':row.pk,'recorded_status':row.result['status'],'current_usable':not holds,'holds':holds,'native_workbook_verified':False,'cost_approved':False,'invoice_created':False}
    if Grant.objects.filter(case=c,user=a,action='costing.source.read',active=True).exists():value.update(result=row.result,snapshot=row.snapshot,inputs=row.inputs)
    return value

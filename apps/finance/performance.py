"""Explicit budget/period inventories and authorised historical replacement.

Engineering implementation. No automatic restatement, accounting posting or policy defaults.
"""
import re
from django.core.exceptions import ValidationError,PermissionDenied
from django.db import transaction
from django.utils import timezone
from apps.core.services import lock_case,event,bump
from apps.identity.services import require
from apps.pmo.services import subject
from apps.policy.services import active_component,reference_values
from apps.policy.models import Configuration
from .models import FinanceRun,FinanceReview,FinanceBudget,FinancePeriod,FinanceRestatement,FinancePerformance,FinancePerformanceDecision
from . import analysis

METHOD='D06.unit_sign_currency_period'
RESTATEMENT='D10.restatement_rule_id'


def method(case):
    config=active_component(METHOD,case);value=reference_values(config)[0].get('performance')
    if not value:raise ValidationError('Configure explicit fiscal periods, budget treatment, metrics and comparison oracles (source conventions v3)')
    return config,value


def exact(case,model,pk):
    item=model.objects.filter(case=case,pk=pk).first()
    if not item:raise ValidationError('Select an exact subject from this Finance case')
    return item


def latest_period(period):
    while True:
        child=FinancePeriod.objects.filter(predecessor=period).first()
        if not child:return period
        period=child


@transaction.atomic
def capture_budget(actor,case_id,reference,cadence,effective_at,completeness,evidence_id,approval_id,expected,*,accounting_basis=None):
    case=lock_case(actor,case_id,'finance.budget',expected)
    if not isinstance(reference,str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:-]{0,99}',reference):raise ValidationError('Supply an explicit budget version family identifier')
    if not effective_at or timezone.is_naive(effective_at) or effective_at>timezone.now():raise ValidationError('Budget effective assertion must be actual and aware')
    if completeness not in ['complete','partial','unknown']:raise ValidationError('Declare budget completeness')
    if accounting_basis is not None and (not isinstance(accounting_basis,str) or not accounting_basis.strip() or len(accounting_basis)>100):raise ValidationError('Budget accounting basis must be explicit or unknown')
    evidence=subject(case,evidence_id,'finance_budget');approval=subject(case,approval_id,'finance_budget_approval')
    from adapters.finance_budgets import read_budget
    rows,findings=read_budget(evidence.body,cadence)
    budget=FinanceBudget.objects.create(case=case,reference=reference,number=FinanceBudget.objects.filter(case=case,reference=reference).count()+1,
        cadence=cadence,accounting_basis=accounting_basis,effective_at=effective_at,completeness=completeness,evidence=evidence,approval_evidence=approval,rows=rows,findings=findings,actor=actor)
    event(actor,case,'finance.budget_captured',budget=budget.pk,findings=len(findings));bump(case);return budget


def output_review(run):
    findings=analysis.certification_findings(run)
    review=analysis.current_review(run.case,'output',run=run)
    if findings or not review['valid']:raise ValidationError(findings or ['Current configured Finance output review required'])
    return FinanceReview.objects.get(pk=review['id'])


def _restatement_snapshot(item):
    policy=active_component(RESTATEMENT,item.case);rule=reference_values(policy)[0]
    if latest_period(item.original).pk!=item.original_id:raise ValidationError('Restatement original already has a replacement')
    review=output_review(item.proposed)
    old=item.original.manifest;new=item.proposed.result
    if any(old[k]!=new[k] for k in ['entity','period','currency']):raise ValidationError('A replacement must preserve entity, period and currency')
    if item.original.run.source.accounting_basis!=item.proposed.source.accounting_basis:raise ValidationError('Accounting-basis change requires a separately supported policy; this replacement interface does not authorise it')
    if not rule['allow_bu_scope_change'] and set(old['result']['by_bu'])!=set(new['by_bu']):raise ValidationError('BU scope change is not permitted by current restatement policy')
    affected=[r.pk for r in FinancePerformance.objects.filter(case=item.case) if item.original_id in r.request['period_ids']+r.request['prior_ids']]
    if affected!=item.impact['performance_ids']:raise ValidationError('Affected report inventory changed; prepare a fresh impact request')
    return {'policy':policy.pk,'rule':rule,'original':item.original_id,'proposed_key':item.proposed.operation_key,'output_review':review.pk,
            'request_hash':item.evidence.sha256,'rationale':item.rationale,'impact':item.impact}


def decision_snapshot(item,purpose):
    if purpose=='budget':
        if FinanceBudget.objects.filter(case=item.case,reference=item.reference).order_by('-number').first().pk!=item.pk:raise ValidationError('Select the current explicit budget revision')
        if item.findings or item.completeness!='complete':raise ValidationError('Budget contains dimension/amount/completeness exceptions')
        return {'budget':item.pk,'source_hash':item.evidence.sha256,'approval_hash':item.approval_evidence.sha256,'rows_hash':analysis.digest(item.rows),'accounting_basis':item.accounting_basis}
    if purpose=='period_method':
        config,value=method(item.case)
        if config.pk!=item.pk:raise ValidationError('Review the exact active period method')
        return {'configuration':config.pk,'method_hash':analysis.digest(value)}
    if purpose=='performance':
        ensure_current(item)
        if item.result['status']!='complete':raise ValidationError('Resolve source, budget, month and metric exceptions before performance approval')
        config,_=method(item.case)
        if not current_decision(item.case,'period_method',configuration=config)['valid']:raise ValidationError('Current fiscal/comparison method review required')
        return {'performance':item.pk,'key':item.operation_key,'result_hash':analysis.digest(item.result)}
    if purpose=='restatement':return _restatement_snapshot(item)
    raise ValidationError('Unsupported performance decision purpose')


def current_decision(case,purpose,**target):
    record=FinancePerformanceDecision.objects.filter(case=case,purpose=purpose,**target).order_by('-pk').first()
    if not record:return {'id':None,'valid':False,'verdict':'missing'}
    valid=False;finding=''
    try:
        require(record.actor,case,'finance.review')
        item=record.budget or record.performance or record.restatement or record.configuration
        preparer=item.created_by_id if record.configuration_id else item.actor_id
        authority=analysis.review_authority(record.actor,case,purpose,record.role,record.verdict,preparer)
        strip=lambda value:{k:v for k,v in value.items() if k!='D05.decision_action_matrix'}
        valid=record.verdict=='approve' and strip(authority)==strip(record.authority) and record.snapshot==decision_snapshot(item,purpose)
    except (ValidationError,PermissionDenied) as exc:finding=str(exc)
    return {'id':record.pk,'valid':valid,'verdict':record.verdict,'finding':finding}


@transaction.atomic
def decide(actor,case_id,purpose,target_id,role,verdict,evidence_id,note,expected):
    case=lock_case(actor,case_id,'finance.review',expected);analysis.note(note)
    targets={'budget':(FinanceBudget,'budget'),'performance':(FinancePerformance,'performance'),
             'restatement':(FinanceRestatement,'restatement'),'period_method':(Configuration,'configuration')}
    if purpose not in targets or verdict not in ['approve','return','reject']:raise ValidationError('Select a configured Finance performance purpose and verdict')
    model,field=targets[purpose];item=exact(case,model,target_id)
    if purpose=='period_method' and item.component!=METHOD:raise ValidationError('Select the fiscal/comparison configuration')
    snapshot=decision_snapshot(item,purpose) if verdict=='approve' else {'subject':item.pk}
    authority=analysis.review_authority(actor,case,purpose,role,verdict,item.created_by_id if field=='configuration' else item.actor_id)
    record=FinancePerformanceDecision.objects.create(case=case,purpose=purpose,role=role,verdict=verdict,snapshot=snapshot,authority=authority,
        evidence=subject(case,evidence_id,'finance_review'),note=note,actor=actor,**{field:item})
    event(actor,case,'finance.performance_decision',decision=record.pk,purpose=purpose,verdict=verdict);bump(case);return record


def _period_manifest(run,review):
    chain=[];cursor=run
    while cursor:
        chain.append({'run':cursor.pk,'key':cursor.operation_key,'snapshot':cursor.snapshot});cursor=cursor.parent
    config=Configuration.objects.get(pk=run.snapshot['policies']['D06.rule_oracle_refs']['id'])
    rules=reference_values(config)
    contracts={r['key']:{k:v for k,v in r.items() if k not in ['from_period','to_period','oracle_evidence_id','oracles']} for r in rules
               if r['entity']==run.result['entity'] and r['from_period']<=run.result['period']<=r['to_period']}
    return {k:run.result[k] for k in ['entity','period','currency']}|{'result':run.result,'result_hash':analysis.digest(run.result),
        'review':review.pk,'chain':chain,'metric_contracts':contracts}


@transaction.atomic
def seal_period(actor,case_id,run_id,restatement_id,expected):
    case=lock_case(actor,case_id,'finance.seal',expected);run=exact(case,FinanceRun,run_id)
    if run.kind!='formula':raise ValidationError('Seal a reviewed monthly formula output')
    review=output_review(run);manifest=_period_manifest(run,review)
    existing=FinancePeriod.objects.filter(run=run).first()
    if existing:
        if existing.restatement_id!=restatement_id:raise ValidationError('This run is already sealed with different provenance')
        return existing
    previous=FinancePeriod.objects.filter(case=case,manifest__entity=manifest['entity'],manifest__period=manifest['period']).order_by('-pk').first()
    request=None
    if previous:
        if restatement_id is None:raise ValidationError('An existing period needs an explicitly approved historical replacement')
        request=exact(case,FinanceRestatement,restatement_id)
        if request.original_id!=previous.pk or request.proposed_id!=run.pk or not current_decision(case,'restatement',restatement=request)['valid']:raise ValidationError('Current exact restatement authority required')
    elif restatement_id is not None:raise ValidationError('A first seal cannot use a replacement request')
    result=FinancePeriod.objects.create(case=case,run=run,output_review=review,predecessor=previous,restatement=request,manifest=manifest,actor=actor)
    event(actor,case,'finance.period_sealed',period=result.pk,predecessor=previous.pk if previous else None);bump(case);return result


def period_acceptance(period):
    """Historical arithmetic stays pinned; current human grants and explicit revocations still apply."""
    from apps.policy.models import PolicyState
    require(period.actor,period.case,'finance.seal');require(period.run.actor,period.case,'finance.calculate')
    if analysis.digest(period.run.result)!=period.manifest['result_hash']:raise ValidationError('Sealed result hash differs')
    reviews={period.output_review_id};policies=set()
    for stage in period.manifest['chain']:
        snap=stage['snapshot'];policies.update(v['id'] for v in snap['policies'].values() if v['id'])
        reviews.update(v['id'] for v in snap['reviews'].values() if v['id']);reviews.add(snap['source_review']['id'])
        reviews.update(v['review']['id'] for v in snap['adjustments'])
    for pk in policies:
        state=PolicyState.objects.filter(configuration_id=pk).order_by('-pk').first()
        if not state or state.state=='revoked':raise ValidationError('Sealed source/rule policy explicitly revoked')
    for record in FinanceReview.objects.filter(pk__in=reviews):
        require(record.actor,period.case,'finance.review')
        latest=analysis.current_review(period.case,record.purpose,**({'source':record.source} if record.source_id else {'run':record.run} if record.run_id else {'configuration':record.configuration} if record.configuration_id else {'adjustment':record.adjustment}))
        # Source conventions are allowed to advance after a period seal. Recheck selected human authority,
        # retaining the source/schema policy versions accepted at sealing rather than today's month.
        item=record.source or record.run or record.configuration or record.adjustment
        current=analysis.review_authority(record.actor,period.case,record.purpose,record.role,record.verdict,item.created_by_id if record.configuration_id else item.actor_id)
        ignore={'D05.decision_action_matrix','D06.source_schema_ref','D06.unit_sign_currency_period'}
        if record.verdict!='approve' or latest['id']!=record.pk or {k:v for k,v in current.items() if k not in ignore}!={k:v for k,v in record.authority.items() if k not in ignore}:raise ValidationError('Sealed review authority changed or decision superseded')
    if period.restatement_id:
        decision=FinancePerformanceDecision.objects.filter(restatement_id=period.restatement_id,purpose='restatement').order_by('-pk').first()
        if not decision or decision.verdict!='approve':raise ValidationError('Historical replacement decision is missing or withdrawn')
        require(decision.actor,period.case,'finance.review')
        authority=analysis.review_authority(decision.actor,period.case,'restatement',decision.role,'approve',period.restatement.actor_id)
        strip=lambda value:{k:v for k,v in value.items() if k!='D05.decision_action_matrix'}
        state=PolicyState.objects.filter(configuration_id=decision.snapshot['policy']).order_by('-pk').first()
        if strip(authority)!=strip(decision.authority) or not state or state.state=='revoked' or decision.snapshot['proposed_key']!=period.run.operation_key:raise ValidationError('Historical replacement authority/policy is no longer valid')
    return {'period':period.pk,'run_key':period.run.operation_key,'hash':period.manifest['result_hash'],'current_head':latest_period(period).pk,'accounting_basis':period.run.source.accounting_basis}


@transaction.atomic
def request_restatement(actor,case_id,original_id,proposed_id,evidence_id,rationale,expected):
    case=lock_case(actor,case_id,'finance.restatement',expected);analysis.note(rationale)
    original=exact(case,FinancePeriod,original_id);proposed=exact(case,FinanceRun,proposed_id)
    if proposed.kind!='formula' or any(original.manifest[k]!=proposed.result[k] for k in ['entity','period','currency']):raise ValidationError('Proposed replacement must preserve entity/period/currency')
    affected=[]
    for report in FinancePerformance.objects.filter(case=case):
        if original.pk in report.request['period_ids']+report.request['prior_ids']:affected.append(report.pk)
    item=FinanceRestatement.objects.create(case=case,original=original,proposed=proposed,evidence=subject(case,evidence_id,'finance_restatement'),rationale=rationale,
        impact={'performance_ids':affected,'old_bu_keys':sorted(original.manifest['result']['by_bu']),'new_bu_keys':sorted(proposed.result['by_bu'])},actor=actor)
    event(actor,case,'finance.restatement_requested',request=item.pk,impact=item.impact);bump(case);return item


def _inventory(case,ids):
    if not isinstance(ids,list) or len(ids)>12 or any(type(pk) is not int for pk in ids) or len(set(ids))!=len(ids):raise ValidationError('Select at most twelve distinct sealed period IDs')
    return [exact(case,FinancePeriod,pk) for pk in ids]


def performance_inputs(actor,case,request):
    require(actor,case,'finance.performance');config,value=method(case)
    if request['cutoff'] not in value['periods']:raise ValidationError('Cutoff must belong to the explicitly configured fiscal year')
    selected=_inventory(case,request['period_ids']);prior=_inventory(case,request['prior_ids'])
    budget=exact(case,FinanceBudget,request['budget_id']) if request['budget_id'] else None
    periods=[];restatement=None
    for item in selected+prior:
        acceptance=period_acceptance(item)
        if acceptance['current_head']!=item.pk:
            policy=active_component(RESTATEMENT,case)
            if reference_values(policy)[0]['historical_selection']!='explicit_original_or_current':raise ValidationError('Current policy requires the revised period, not the original')
            restatement=policy.pk
        periods.append(acceptance)
    decision=current_decision(case,'budget',budget=budget) if budget else {'id':None,'valid':False,'verdict':'missing'}
    return {'calculation_implementation':'finance-performance/v2','method':config.pk,'method_hash':analysis.digest(value),'method_review':current_decision(case,'period_method',configuration=config),
        'periods':periods,'budget':budget.pk if budget else None,'budget_review':decision,'restatement_policy':restatement},value,selected,prior,budget


def ensure_current(report):
    snapshot,*_=performance_inputs(report.actor,report.case,report.request)
    if snapshot!=report.snapshot:raise ValidationError('Performance input, current period head, method, budget or human authority changed; rebuild')
    return report


@transaction.atomic
def build(actor,case_id,cutoff,period_ids,budget_id,prior_ids,expected):
    case=lock_case(actor,case_id,'finance.performance',expected)
    request={'cutoff':cutoff,'period_ids':period_ids,'budget_id':budget_id,'prior_ids':prior_ids}
    snapshot,value,periods,prior,budget=performance_inputs(actor,case,request)
    from .performance_calculation import calculate
    result=calculate(value,request,periods,prior,budget,snapshot)
    key=analysis.digest({'case':str(case.pk),'actor':actor.pk,'request':request,'snapshot':snapshot})
    old=FinancePerformance.objects.filter(operation_key=key).first()
    if old:return old
    report=FinancePerformance.objects.create(case=case,request=request,snapshot=snapshot,result=result,operation_key=key,actor=actor)
    event(actor,case,'finance.performance_built',performance=report.pk,status=result['status']);bump(case);return report

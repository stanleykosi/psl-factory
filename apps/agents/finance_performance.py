from django.core.exceptions import ValidationError,PermissionDenied
from django.db import transaction
from apps.core.services import lock_case,event
from apps.identity.services import require
from apps.finance.models import FinancePerformance,FinancePeriod,FinanceBudget
from apps.finance import performance
from apps.policy.models import Configuration
from apps.policy.services import reference_values
from .models import AgentRun


@transaction.atomic
def investigate(actor,case_id,performance_id,expected):
    case=lock_case(actor,case_id,'agent.performance',expected);require(actor,case,'finance.read')
    report=performance.exact(case,FinancePerformance,performance_id);current=True;findings=list(report.result['findings'])
    try:performance.ensure_current(report)
    except (ValidationError,PermissionDenied) as exc:current=False;findings+=getattr(exc,'messages',[str(exc)])
    citations=set();monthly=[]
    for period in FinancePeriod.objects.filter(case=case,pk__in=report.request['period_ids']+report.request['prior_ids']):
        citations.update(period.run.result['source_evidence_ids']);citations.add(period.output_review.evidence_id)
        if period.restatement_id:citations.add(period.restatement.evidence_id)
        monthly.append({'period':period.manifest['period'],'seal':period.pk,'source_run':period.run_id,'predecessor':period.predecessor_id,'hash':period.manifest['result_hash']})
    if report.request['budget_id']:
        budget=FinanceBudget.objects.get(case=case,pk=report.request['budget_id']);citations.update([budget.evidence_id,budget.approval_evidence_id])
    config=Configuration.objects.get(pk=report.snapshot['method']);method=reference_values(config)[0]['performance'];citations.add(method['oracle_evidence_id'])
    result={'capability':'A03/A05/A07 bounded budget, period inventory and performance investigation','performance':report.pk,'current':current,
        'findings':findings[:100],'monthly_lineage':monthly,'included_periods':report.result['included_periods'],
        'company_metrics':report.result['company'],'ratio_definition':method['ratio'],'budget_method':method['budget_method'],
        'citations':list(case.evidence.filter(pk__in=citations).values('id','kind','sha256')),
        'next_work':'Resolve missing month/budget dimensions and incompatible metric definitions. Review exact figures and explicit historical replacement before publication.',
        'approval_granted':False,'policy_changed':False,'history_rewritten':False,'ledger_posted':False,'external_authenticity_verified':False}
    source=case.evidence.filter(pk__in=citations).first()
    log=AgentRun.objects.create(case=case,actor=actor,evidence=source,provider='deterministic-finance-performance-v1',process_id='F26',result=result)
    event(actor,case,'agent.finance_performance',run=log.pk,performance=report.pk);return log

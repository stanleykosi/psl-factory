"""Bounded, deterministic A05/A03/A06/A07 diagnostic, not a model evaluation."""
from django.db import transaction
from django.core.exceptions import ValidationError,PermissionDenied
from apps.core.services import lock_case,event,bump
from apps.identity.services import require
from apps.agents.models import AgentRun
from apps.finance import forecast
from apps.finance.models import ForecastRun,ForecastMatch,ForecastActual,ForecastActualVerification,ForecastReview,ForecastMatchReversal,InvoiceCorrection

@transaction.atomic
def investigate(actor,case_id,run_id,expected):
    case=lock_case(actor,case_id,'agent.forecast',expected);require(actor,case,'finance.read');run=forecast.exact(case,ForecastRun,run_id)
    findings=list(run.result['findings'])
    try:forecast.ensure_current(run);current=True
    except (ValidationError,PermissionDenied) as exc:findings.append(str(exc));current=False
    sources=[run.scenario.evidence]
    for i in run.scenario.payload['items']+run.scenario.payload['openings']:sources.append(case.evidence.get(pk=i['evidence_id']))
    for a in ForecastActual.objects.filter(case=case):sources.append(a.evidence)
    sources += [v.evidence for v in ForecastActualVerification.objects.filter(actual__case=case)]
    sources += [v.evidence for v in ForecastReview.objects.filter(run=run)]
    sources += [v.evidence for v in ForecastMatch.objects.filter(case=case)]
    sources += [v.evidence for v in ForecastMatchReversal.objects.filter(match__case=case)]
    selected_issues=[i['issue_id'] for i in run.scenario.payload['items'] if i['issue_id']]
    sources += [r.evidence for r in InvoiceCorrection.objects.filter(case=case,issue_id__in=selected_issues)]
    method_id=run.manifest['method']['id']
    if method_id:
        from apps.policy.models import Configuration
        from apps.policy.services import reference_values
        c=Configuration.objects.get(case=case,pk=method_id)
        if run.manifest['method']['status']=='ACTIVE':sources.append(case.evidence.get(pk=reference_values(c)[0]['oracle_evidence_id']))
    result={'capabilities':['A05','A03','A06','A07'],'current':current,'findings':findings,'scope':run.result['scope'],
        'assumptions':[{'item':i['key'],'owner':i['owner'],'original_due':i['original_due'],'expected_on':i['expected_on'],'remaining':i['residual']} for i in run.result['items']],
        'actual_links':list(ForecastMatch.objects.filter(case=case).values('pk','root_id','item_key','actual_id','amount')),
        'citations':[{'id':e.pk,'sha256':e.sha256,'kind':e.kind} for e in {e.pk:e for e in sources}.values()],
        'next_steps':['Review omitted, unknown and out-of-horizon assumptions with Finance.','Reconcile unmatched actuals and source reversals before roll-forward.','Obtain exact human review before audience publication.'],
        'approval_granted':False,'cash_mutated':False,'execution_authorized':False,'tools':['case_evidence_read','forecast_lineage_compare']}
    for r in result['actual_links']:r['amount']=str(r['amount'])
    log=AgentRun.objects.create(case=case,actor=actor,evidence=run.scenario.evidence,process_id='F39',provider='deterministic-forecast-v1',result=result)
    event(actor,case,'agent.forecast_investigated',run=run.pk,agent_run=log.pk);bump(case);return log

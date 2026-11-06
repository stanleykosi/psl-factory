"""Native typed preparation tools; no duplicated arithmetic or ledger posting."""
from apps.core.services import event
from apps.finance import analysis
from apps.finance.documents import draft_report
from apps.agents.finance_analysis import investigate_finance
from apps.agents.models import AgentRun
from apps.identity.services import require

class NativeAccountingAdapter:
    def investigate(self,work,source,run=None):
        require(work.execution_actor,work.case,'agent.finance')
        require(work.execution_actor,work.case,'finance.read')
        from apps.workflows.factory_accounting_intake import provenance
        intake = provenance(work.execution_actor, work, execution=True)
        if run is not None:
            log=investigate_finance(work.execution_actor,work.case_id,run.pk,work.case.revision)
            return {'agent_run':log.pk,'source':source.pk,'finance_run':run.pk,'intake_provenance':intake}
        result={'capability':'A03/A05 accounting source investigation','source':source.pk,'batch':source.batch_id,
            'intake_provenance':intake,'entity':source.entity,'completeness':source.completeness,'control_total_known':source.control_total is not None,
            'extracted_at':source.extracted_at.isoformat(),'citations':[source.evidence_id,source.batch.evidence_id],
            'source_authenticity':'Not established by a controlled import','approval_granted':False,'ledger_posted':False,
            'next_work':'Use native mapping and configured source/rule reviews; unknown data is not zero.'}
        log=AgentRun.objects.create(case=work.case,actor=work.execution_actor,evidence=source.evidence,provider='deterministic-finance-source-v1',process_id='F03',result=result)
        event(work.execution_actor,work.case,'agent.accounting_source_investigated',agent_run=log.pk,source=source.pk)
        return {'agent_run':log.pk,'source':source.pk,'intake_provenance':intake}

    def prepare(self,work,source,kind,parent,metrics,adjustment_ids):
        if kind=='mapping':return analysis.map_source(work.execution_actor,work.case_id,source.pk,adjustment_ids,work.case.revision)
        if kind=='allocation':return analysis.allocate(work.execution_actor,work.case_id,parent.pk,metrics,work.case.revision)
        return analysis.calculate(work.execution_actor,work.case_id,parent.pk,work.case.revision)

    def draft(self,work,run,template,audience):
        return draft_report(work.execution_actor,work.case_id,run.pk,template,audience,work.case.revision)

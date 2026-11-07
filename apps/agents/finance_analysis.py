from django.core.exceptions import ValidationError,PermissionDenied
from django.db import transaction
from apps.core.services import lock_case,event
from apps.identity.services import require
from apps.finance.models import FinanceRun
from apps.finance.analysis import ensure_current,certification_findings
from .models import AgentRun

@transaction.atomic
def investigate_finance(actor,case_id,run_id,expected):
    case=lock_case(actor,case_id,'agent.finance',expected);require(actor,case,'finance.read')
    run=FinanceRun.objects.filter(case=case,pk=run_id).first()
    if not run:raise ValidationError('Select this case Finance preview')
    from apps.finance.statement_ppe import recipient_access
    recipient_access(run,[actor.pk])
    findings=list(run.result.get('findings',[]));chain=[];citations=set();cursor=run
    while cursor:
        chain.append({'run':cursor.pk,'kind':cursor.kind,'operation_key':cursor.operation_key,'policies':cursor.snapshot['policies'],'reviews':cursor.snapshot['reviews']})
        citations.update(cursor.result.get('source_evidence_ids',[]));citations.update([cursor.source.evidence_id,cursor.source.batch.evidence_id])
        cursor=cursor.parent
    current=True
    try:
        ensure_current(run)
        if run.kind in ['formula','statement']:findings+=certification_findings(run)
    except (ValidationError,PermissionDenied) as exc:
        current=False;findings+=getattr(exc,'messages',[str(exc)])
    from apps.policy.models import Configuration
    from apps.policy.services import reference_values
    for step in chain:
        for component,state in step['policies'].items():
            if state['id']:
                c=Configuration.objects.get(pk=state['id']);citations.update(int(x.split(':')[-1]) for x in c.envelope['evidence_refs'])
                if component=='D06.rule_oracle_refs':citations.update(x['oracle_evidence_id'] for x in reference_values(c))
                if component in ['D07.authorized_input_refs','D07.effective_membership_ref']:citations.update(x['evidence_id'] for x in reference_values(c))
    # No raw membership/employee rows or automatic account/BU/policy patches leave this tool.
    from apps.finance.source_units import inspect as inspect_units
    source_units=run.source.unit_state
    result={'source_units':source_units,'capability':'A03/A05/A07 bounded Finance lineage and exception investigation','run':run.pk,'status':run.result['status'],'current':current,'findings':findings[:100],
        'lineage':chain,'citations':list(case.evidence.filter(pk__in=citations).values('id','kind','sha256')),
        'company_metrics':run.result.get('company',{}),'bu_comparison':run.result.get('bu_comparison',{}),
        'next_work':'Resolve exact unmapped/unknown/source/basis and rule-review findings; rebuild previews after approved changes. Investigate conserved totals and rounding residuals before configured Finance output review.',
        'approval_granted':False,'ledger_posted':False,'rules_changed':False,'external_authenticity_verified':False,
        'oracle_scope':'Synthetic tests validate the configured algorithm; original workbook/provider equivalence requires actual owner oracles.'}
    if run.kind=='statement':
        result['statement_inputs']=[dict(item['declaration'],source_operation_key=item['operation_key'],review_id=item['review']['id'],source_evidence_ids=item.get('source_evidence_ids',[])) for item in run.snapshot['inputs']]
        result['scope']='Selected statement lines only; full statement oracle remains deferred.'
    log=AgentRun.objects.create(case=case,actor=actor,evidence=run.source.evidence,provider='deterministic-finance-lineage-v1',process_id='F23',result=result)
    event(actor,case,'agent.finance_investigation',run=log.pk,finance_run=run.pk);return log


@transaction.atomic
def investigate_mapping_draft(actor, case_id, source_id, configuration_id, expected):
    """Deterministic, ephemeral triage; no model guesses or retained private rows."""
    case = lock_case(actor, case_id, 'agent.finance', expected)
    from apps.finance.mapping_diagnostics import preview_mapping_draft
    result = preview_mapping_draft(actor, case.pk, source_id, configuration_id, expected)
    return dict(result, capability='F03 deterministic draft mapping exception investigation',
        external_authenticity_verified=False)


def inspect_source_units(actor, case_id, source_id):
    """Read-only typed source investigation, including sources held before mapping."""
    from apps.core.models import Case
    from apps.finance.analysis import source_for
    case=Case.objects.get(pk=case_id)
    require(actor,case,'case.read');require(actor,case,'finance.read');require(actor,case,'agent.finance')
    source=source_for(case,source_id)
    return {'source':source.pk,'batch':source.batch_id,'source_hash':source.batch.source_sha256,
            'source_units':source.unit_state,'numeric_result':None,'ledger_posted':False,
            'external_authenticity_verified':False}

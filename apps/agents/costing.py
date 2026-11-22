from django.db import transaction
from django.core.exceptions import ValidationError,PermissionDenied
from apps.core.services import add_evidence,event,bump
from apps.pmo import costing as d
from apps.pmo.costing_models import CostingRule,CostingOracle,CostingRun
from apps.pmo.costing_proposal_models import CostingProposal
from apps.identity.models import Grant
from apps.policy.services import resolve
from apps.policy.costing_validators import COMPONENT
from adapters.costing import LocalCostingProposalAdapter
from .models import AgentRun

@transaction.atomic
def investigate(a,case_id,expected=None):
    c=d.locked(a,case_id,'agent.costing',expected);questions=[]
    source_allowed=Grant.objects.filter(case=c,user=a,action='costing.source.read',active=True).exists()
    comparisons=[]
    for r in CostingRule.objects.filter(case=c).select_related('case').order_by('-pk')[:20]:
        try:d.confirmed(r);status='owner_confirmation_current'
        except (ValidationError,PermissionDenied):status='owner_confirmation_required_or_stale'
        if source_allowed:
            o=CostingOracle.objects.filter(rule=r).order_by('-pk').first()
            if o:comparisons.append({'rule':r.pk,'oracle':o.pk,'checks':[{'scenario_index':index,'matches':x['matches']} for index,x in enumerate(d.oracle_results(r,o),1)]})
        questions.append({'rule':r.pk,'version':r.version,'status':status,'questions':['Confirm exact calculator/version and rate, formula, unit, margin, tax, currency, rounding and override lineage.','Obtain independent normal and exception outputs; do not derive expected results with this calculator.']})
    for row in CostingRun.objects.filter(case=c).select_related('case','actor').order_by('-pk')[:20]:
        try:d.current_run(row);status='current_known'
        except (ValidationError,PermissionDenied):status='held_or_stale'
        questions.append({'run':row.pk,'recorded_status':row.result['status'],'unknown_operand_count':sum(x.startswith('unknown:') for x in row.result['findings']) if source_allowed else None,'division_by_zero_count':sum(x.startswith('division_by_zero:') for x in row.result['findings']) if source_allowed else None,'status':status,'question':'Trace missing operands or changed evidence; calculate a successor without changing historical results or case approvals.'})
    proposals=[]
    studio_source=None
    if source_allowed:
        try:
            _,rule,oracle,value=d.configured(c,a)
            if 'studio_source_id' in value:
                studio_source={'source':value['studio_source_id'],'rule':rule.pk,'oracle':oracle.pk}
        except (ValidationError,PermissionDenied):
            pass
        from apps.pmo.costing_proposals import current
        for proposal in CostingProposal.objects.filter(base__case=c,decision__isnull=True).select_related('base__case','actor').order_by('-pk')[:20]:
            try:current(proposal);status='awaiting_independent_review'
            except (PermissionDenied,ValidationError):status='source_reassessment_required'
            item={'proposal':proposal.pk,'base_version':proposal.base.version,'status':status}
            example_sets=list(CostingOracle.objects.filter(rule=proposal.base).values_list('pk',flat=True)[:2])
            if len(example_sets)==1:
                comparison=LocalCostingProposalAdapter().read(a,c.pk,proposal.pk,example_sets[0])
                item['example_checks']=[{'example_index':index,'proposed_matches':example['after_matches']}
                    for index,example in enumerate(comparison['examples'],1)]
            proposals.append(item)
    e=add_evidence(a,c.pk,'agent_costing','Bounded P14 evidence/lineage investigation; no raw financial source or automatic model/case decision','local:deterministic-costing-v1')
    r=AgentRun.objects.create(case=c,actor=a,evidence=e,process_id='P14',provider='deterministic-costing-v1',result={'independent_comparisons':comparisons,'questions':questions,'pending_version_proposals':proposals,'studio_source':studio_source,'policy_status':resolve(COMPONENT,c).status,'source_body_read':False,'expected_outputs_generated':False,'case_cost_approved':False,'native_workbook_verified':False,'financial_execution':False});event(a,c,'agent.costing',run=r.pk);bump(c);return r

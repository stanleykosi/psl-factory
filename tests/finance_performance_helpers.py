import copy,json
from datetime import timedelta
from django.conf import settings
from django.utils import timezone
from apps.core.services import add_evidence
from apps.finance import analysis,performance
from .finance_analysis_helpers import fixture,policy,pipeline
from .helpers import rev


def fixture_performance():
    a,c,e,f,configs,source,template,recipient=fixture()
    p=json.loads((settings.BASE_DIR/'fixtures/finance-performance.json').read_text(encoding='utf-8'))
    authority=copy.deepcopy(f['authority'])
    authority['finance'] += [{'purpose':purpose,'role':'Finance','actions':['approve','return','reject'],'allow_preparer_review':True} for purpose in ['budget','performance','period_method','restatement']]
    policy(a,c,'D05.decision_action_matrix',authority,e['policy_decision'])
    oracle=add_evidence(a,c.pk,'finance_oracle',json.dumps(p['method']['oracles'],sort_keys=True),'synthetic:comparison-oracles')
    method=copy.deepcopy(p['method']);method['oracle_evidence_id']=oracle.pk
    cfg=policy(a,c,'D06.unit_sign_currency_period',dict(f['conventions'],performance=method),e['policy_decision'])
    performance.decide(a,c.pk,'period_method',cfg.pk,'Finance','approve',e['finance_review'].pk,'Synthetic fiscal/comparison method reviewed',rev(c))
    analysis.review(a,c.pk,'source',source.pk,'Finance','approve',e['finance_review'].pk,'Source conventions including explicit fiscal interface reviewed',rev(c))
    _,_,run=pipeline(a,c,source)
    analysis.review(a,c.pk,'output',run.pk,'Finance','approve',e['finance_review'].pk,'Exact monthly output reviewed',rev(c))
    sealed=performance.seal_period(a,c.pk,run.pk,None,rev(c))
    budget_source=add_evidence(a,c.pk,'finance_budget',p['csv'],'synthetic:budget')
    budget_approval=add_evidence(a,c.pk,'finance_budget_approval','Explicit synthetic budget approval source','synthetic:budget-owner')
    budget=performance.capture_budget(a,c.pk,'SYNTHETIC-BUDGET','monthly',timezone.now()-timedelta(days=1),'complete',budget_source.pk,budget_approval.pk,rev(c),accounting_basis='accrual')
    performance.decide(a,c.pk,'budget',budget.pk,'Finance','approve',e['finance_review'].pk,'Exact synthetic budget reviewed',rev(c))
    return a,c,e,f,p,method,cfg,source,sealed,budget,template,recipient


def build(data):
    a,c,e,f,p,method,cfg,source,sealed,budget,t,recipient=data
    return performance.build(a,c.pk,'2026-10',[sealed.pk],budget.pk,[],rev(c))

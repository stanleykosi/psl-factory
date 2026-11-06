import copy,io,json
from datetime import timedelta
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from apps.core.models import Case
from apps.core.services import add_evidence
from apps.finance.models import FinanceSource
from apps.finance import analysis,performance
from apps.policy.finance_drafts import draft_finance_policy
from apps.policy.services import active_component,reference_values,transition


class Command(BaseCommand):
    help='Create isolated synthetic budget/YTD performance through real local services; leave final review/publication to the UI'
    def add_arguments(self,parser):parser.add_argument('--username',default='studio-demo')
    @transaction.atomic
    def handle(self,*args,**options):
        output=io.StringIO()
        call_command('seed_finance_analysis_demo',username=options['username'],title='Synthetic Finance budget and YTD performance',stdout=output)
        seeded=json.loads(output.getvalue());case=Case.objects.get(pk=seeded['case']);actor=get_user_model().objects.get(username=options['username'])
        source=FinanceSource.objects.get(pk=seeded['source']);fixture=json.loads((settings.BASE_DIR/'fixtures/finance-performance.json').read_text(encoding='utf-8'))
        def revision():case.refresh_from_db();return case.revision
        def evidence(kind,body):return add_evidence(actor,case.pk,kind,body,'synthetic:performance-demo')
        owner=evidence('policy_decision','Synthetic explicit fiscal/budget/comparison/authority choices only, not operational PSL policy')
        review_evidence=evidence('finance_review','Synthetic exact current review evidence')
        def policy(key,value):
            cfg=draft_finance_policy(actor,case.pk,key,value,owner.pk,timezone.now()-timedelta(days=1));transition(actor,cfg.pk,'validated');transition(actor,cfg.pk,'active');return cfg
        authority=copy.deepcopy(reference_values(active_component('D05.decision_action_matrix',case))[0])
        authority['finance'] += [{'purpose':purpose,'role':'Finance','actions':['approve','return','reject'],'allow_preparer_review':True} for purpose in ['budget','performance','period_method','restatement']]
        policy('D05.decision_action_matrix',authority)
        oracle=evidence('finance_oracle',json.dumps(fixture['method']['oracles'],sort_keys=True));method=dict(fixture['method'],oracle_evidence_id=oracle.pk)
        conventions=dict(reference_values(active_component('D06.unit_sign_currency_period',case))[0],performance=method)
        cfg=policy('D06.unit_sign_currency_period',conventions)
        performance.decide(actor,case.pk,'period_method',cfg.pk,'Finance','approve',review_evidence.pk,'Synthetic exact fiscal/metric method reviewed',revision())
        analysis.review(actor,case.pk,'source',source.pk,'Finance','approve',review_evidence.pk,'Exact source conventions accepted',revision())
        mapped=analysis.map_source(actor,case.pk,source.pk,[],revision());allocated=analysis.allocate(actor,case.pk,mapped.pk,['revenue','direct_cost','staff_cost','opex'],revision());run=analysis.calculate(actor,case.pk,allocated.pk,revision())
        analysis.review(actor,case.pk,'output',run.pk,'Finance','approve',review_evidence.pk,'Exact synthetic monthly values accepted',revision())
        sealed=performance.seal_period(actor,case.pk,run.pk,None,revision())
        budget_input=evidence('finance_budget',fixture['csv']);approval=evidence('finance_budget_approval','Synthetic written company/BU budget approval evidence')
        budget=performance.capture_budget(actor,case.pk,'SYNTHETIC-FY2026','monthly',timezone.now()-timedelta(days=1),'complete',budget_input.pk,approval.pk,revision(),accounting_basis='accrual')
        performance.decide(actor,case.pk,'budget',budget.pk,'Finance','approve',review_evidence.pk,'Exact synthetic budget source/version accepted',revision())
        projection=copy.deepcopy(reference_values(active_component('D10.audience_projection_rules',case))[0]);projection['audiences'][0].update(columns=['actual','budget','variance','prior','ratio'],charts=True)
        policy('D10.audience_projection_rules',projection);policy('D10.restatement_rule_id',fixture['restatement'])
        result=performance.build(actor,case.pk,'2026-10',[sealed.pk],budget.pk,[],revision())
        self.stdout.write(json.dumps({'case':str(case.pk),'performance':result.pk,'sealed_period':sealed.pk,'budget':budget.pk,'template':seeded['template'],
            'review_evidence':review_evidence.pk,'status':result.result['status'],'performance_review':'not_recorded','publication':'not_reserved','ledger_posted':False}))

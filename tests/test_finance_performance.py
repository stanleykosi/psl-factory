import copy,json
from datetime import timedelta
from django.conf import settings
from django.core.exceptions import ValidationError,PermissionDenied
from django.db import connection,DatabaseError,transaction
from django.test import TestCase
from django.utils import timezone
from apps.core.services import add_evidence
from apps.finance import performance,analysis
from apps.finance.models import FinanceBudget,FinancePeriod,FinancePerformance
from apps.identity.models import Grant
from .finance_performance_helpers import fixture_performance,build
from .finance_analysis_helpers import policy,pipeline
from apps.policy.services import reference_values
from apps.finance.services import capture_import
from .helpers import rev
from apps.policy.services import transition
from apps.finance.documents import draft_report
from apps.documents.controlled import reserve_publication,preflight
from apps.documents.delivery import run_publication_once
from apps.documents.models import PublicationReceipt,PublicationJob
from apps.agents.finance_performance import investigate


class FinancePerformanceTests(TestCase):
    @classmethod
    def setUpTestData(cls):cls.data=fixture_performance()

    def test_explicit_budget_ytd_comparison_and_undefined_ratio(self):
        report=build(self.data)
        self.assertEqual(connection.vendor,'postgresql');self.assertEqual(report.result['status'],'complete')
        pbt=report.result['company']['pbt']
        self.assertEqual(pbt['value'],'609.99');self.assertEqual(pbt['budget'],'500.00');self.assertEqual(pbt['variance'],'109.99');self.assertEqual(pbt['ratio'],'122.00')
        self.assertIsNone(report.result['by_bu']['beta']['revenue']['ratio']);self.assertEqual(report.result['by_bu']['beta']['revenue']['ratio_status'],'unknown_zero_denominator')
        self.assertFalse(report.result['historical_values_rewritten']);self.assertEqual(report.pk,build(self.data).pk)

    def test_budget_capture_independent_and_unknowns_hold_approval(self):
        a,c,e,_,p,*_=self.data
        source=add_evidence(a,c.pk,'finance_budget',p['csv'].replace(',500,NGN',',,NGN'),'synthetic:unknown-budget')
        approval=add_evidence(a,c.pk,'finance_budget_approval','Synthetic approval evidence','synthetic:owner')
        budget=performance.capture_budget(a,c.pk,'UNKNOWN','monthly',timezone.now()-timedelta(hours=1),'unknown',source.pk,approval.pk,rev(c))
        self.assertTrue(budget.findings)
        with self.assertRaises(ValidationError):performance.decide(a,c.pk,'budget',budget.pk,'Finance','approve',e['finance_review'].pk,'Cannot certify unknown',rev(c))

    def test_missing_month_is_unknown_and_history_is_immutable(self):
        a,c,*_=self.data;budget=self.data[9]
        report=performance.build(a,c.pk,'2026-11',[self.data[8].pk],budget.pk,[],rev(c))
        self.assertEqual(report.result['status'],'needs_attention');self.assertIsNone(report.result['company']['pbt']['value'])
        for name in ['financebudget','financeperiod','financeperformance','financeperformancedecision']:
            with self.assertRaises(DatabaseError),transaction.atomic():
                with connection.cursor() as cursor:cursor.execute('DELETE FROM finance_'+name)

    def budget(self,csv,reference='CHANGED',cadence='monthly',completeness='complete',basis='accrual'):
        a,c,e,*_=self.data
        evidence=add_evidence(a,c.pk,'finance_budget',csv,'synthetic:changed-budget')
        approval=add_evidence(a,c.pk,'finance_budget_approval','Synthetic explicit approved source','synthetic:approval')
        b=performance.capture_budget(a,c.pk,reference,cadence,timezone.now()-timedelta(days=1),completeness,evidence.pk,approval.pk,rev(c),accounting_basis=basis)
        return b

    def change_method(self,method):
        a,c,e,f,*_=self.data
        oracle=add_evidence(a,c.pk,'finance_oracle',json.dumps(method['oracles'],sort_keys=True),'synthetic:changed-method-oracles');method['oracle_evidence_id']=oracle.pk
        cfg=policy(a,c,'D06.unit_sign_currency_period',dict(f['conventions'],performance=method),e['policy_decision'])
        performance.decide(a,c.pk,'period_method',cfg.pk,'Finance','approve',e['finance_review'].pk,'Exact method reviewed',rev(c));return cfg

    def approve_and_document(self,report):
        a,c,e,*_=self.data
        projection=copy.deepcopy(self.data[3]['projection']);projection['audiences'][0].update(columns=['actual','budget','variance','prior','ratio'],charts=True)
        policy(a,c,'D10.audience_projection_rules',projection,e['policy_decision'])
        performance.decide(a,c.pk,'performance',report.pk,'Finance','approve',e['finance_review'].pk,'Exact fiscal comparison reviewed',rev(c))
        return draft_report(a,c.pk,report.pk,self.data[10].pk,'internal',rev(c),performance=True)

    def replacement(self):
        a,c,e,f,p,method,cfg,source,sealed,budget,t,recipient=self.data
        adjustment_evidence=add_evidence(a,c.pk,'finance_adjustment','Synthetic reporting correction source','synthetic:corrected')
        adjustment=analysis.adjustment(a,c.pk,source.pk,'CORRECTION','additive',[{'account':'sales','amount':'-100'}],adjustment_evidence.pk,'Written reporting correction',rev(c))
        analysis.review(a,c.pk,'adjustment',adjustment.pk,'Finance','approve',e['finance_review'].pk,'Exact reporting overlay reviewed',rev(c))
        mapped=analysis.map_source(a,c.pk,source.pk,[adjustment.pk],rev(c));allocated=analysis.allocate(a,c.pk,mapped.pk,['revenue','direct_cost','staff_cost','opex'],rev(c));proposed=analysis.calculate(a,c.pk,allocated.pk,rev(c))
        analysis.review(a,c.pk,'output',proposed.pk,'Finance','approve',e['finance_review'].pk,'Corrected monthly figures reviewed',rev(c))
        request_evidence=add_evidence(a,c.pk,'finance_restatement','Written correction and historical change rationale','synthetic:written-request')
        request=performance.request_restatement(a,c.pk,sealed.pk,proposed.pk,request_evidence.pk,'Correct source reporting overlay; preserve the original',rev(c))
        return proposed,request

    def test_reviewed_projection_delivery_agent_and_ui(self):
        a,c,e,*_=self.data;report=build(self.data);document=self.approve_and_document(report)
        self.assertFalse(preflight(document));reserve_publication(a,c.pk,document.pk,rev(c));self.assertTrue(run_publication_once())
        receipt=PublicationReceipt.objects.get();payload=json.dumps(receipt.payload)
        self.assertIn('122.00',payload);self.assertIn('signed_grouped_bars_v1',payload);self.assertNotIn('opaque-synthetic',payload)
        self.client.force_login(self.data[11]);self.assertContains(self.client.get('/documents/inbox/'),'Reviewed charts from this exact published payload')
        self.assertContains(self.client.get('/documents/inbox/'),'109.99')
        agent=investigate(a,c.pk,report.pk,rev(c));self.assertFalse(agent.result['history_rewritten']);self.assertIn(self.data[9].approval_evidence_id,[x['id'] for x in agent.result['citations']])
        self.client.force_login(a);url=f'/cases/{c.pk}/finance/performance/'
        self.assertContains(self.client.get(url),'Budget, YTD performance and historical rework');self.assertContains(self.client.get(url),'609.99')
        self.assertEqual(self.client.post(url,{'action':'build','cutoff':'2026-10','periods':[self.data[8].pk],'budget':self.data[9].pk,'revision':rev(c)}).status_code,302)

    def test_budget_supersession_holds_queued_publication_without_rewriting(self):
        a,c,e,*_=self.data;report=build(self.data);d=self.approve_and_document(report);reserve_publication(a,c.pk,d.pk,rev(c))
        self.budget(self.data[4]['csv'],reference=self.data[9].reference)
        self.assertTrue(preflight(d));run_publication_once();self.assertEqual(PublicationJob.objects.get().status,'held');self.assertFalse(PublicationReceipt.objects.exists())
        self.assertEqual(report.result['company']['pbt']['budget'],'500.00')

    def test_annual_explicit_weights_and_no_invented_twelfths(self):
        a,c,e,*_=self.data;method=copy.deepcopy(self.data[5]);method['budget_method']='annual_explicit_weights'
        method['annual_weights']=[{'period':p,'weight':'1' if i==0 else '0'} for i,p in enumerate(method['periods'])]
        self.change_method(method)
        b=self.budget(self.data[4]['csv'].replace('2026-10','FY2026'),cadence='annual')
        performance.decide(a,c.pk,'budget',b.pk,'Finance','approve',e['finance_review'].pk,'Exact annual budget',rev(c))
        report=performance.build(a,c.pk,'2026-10',[self.data[8].pk],b.pk,[],rev(c));self.assertEqual(report.result['status'],'complete');self.assertEqual(report.result['company']['pbt']['budget'],'500.00')
        method['annual_weights'][0]['weight']='0.5'
        with self.assertRaises(ValidationError):self.change_method(method)

    def test_duplicate_months_wrong_units_and_required_prior_hold(self):
        a,c,e,*_=self.data
        with self.assertRaises(ValidationError):performance.build(a,c.pk,'2026-10',[self.data[8].pk,self.data[8].pk],self.data[9].pk,[],rev(c))
        b=self.budget(self.data[4]['csv'].replace('major_currency','thousands_currency'))
        performance.decide(a,c.pk,'budget',b.pk,'Finance','approve',e['finance_review'].pk,'Known dimensions but incompatible to actual',rev(c))
        r=performance.build(a,c.pk,'2026-10',[self.data[8].pk],b.pk,[],rev(c));self.assertIsNone(r.result['company']['pbt']['budget']);self.assertEqual(r.result['status'],'needs_attention')
        method=copy.deepcopy(self.data[5]);method['prior_required']=True;self.change_method(method)
        r=build(self.data);self.assertEqual(r.result['status'],'needs_attention');self.assertIsNone(r.result['company']['pbt']['prior'])

    def test_restatement_requires_independent_policy_and_human_authority(self):
        a,c,e,*_=self.data;old_report=build(self.data);proposed,request=self.replacement()
        self.assertEqual(request.impact['performance_ids'],[old_report.pk])
        with self.assertRaises(ValidationError):performance.seal_period(a,c.pk,proposed.pk,None,rev(c))
        with self.assertRaises(ValidationError):performance.decide(a,c.pk,'restatement',request.pk,'Finance','approve',e['finance_review'].pk,'Policy absent',rev(c))
        policy(a,c,'D10.restatement_rule_id',self.data[4]['restatement'],e['policy_decision'])
        performance.decide(a,c.pk,'restatement',request.pk,'Finance','approve',e['finance_review'].pk,'Explicit exact replacement authorised',rev(c))
        revised=performance.seal_period(a,c.pk,proposed.pk,request.pk,rev(c))
        self.assertEqual(revised.predecessor_id,self.data[8].pk);self.assertEqual(self.data[8].manifest['result']['company']['pbt']['value'],'609.99');self.assertEqual(revised.manifest['result']['company']['pbt']['value'],'709.99')
        with self.assertRaises(ValidationError):performance.ensure_current(old_report)
        new=performance.build(a,c.pk,'2026-10',[revised.pk],self.data[9].pk,[],rev(c));self.assertEqual(new.result['company']['pbt']['value'],'709.99')
        self.assertEqual(FinancePeriod.objects.count(),2)

    def test_invalid_fiscal_oracle_and_projection_rules(self):
        method=copy.deepcopy(self.data[5]);method['periods'][0]='2026-09'
        with self.assertRaises(ValidationError):self.change_method(method)
        method=copy.deepcopy(self.data[5]);method['oracles'][0]['expected']['ratio']='999'
        with self.assertRaises(ValidationError):self.change_method(method)
        a,c,e,*_=self.data;projection=copy.deepcopy(self.data[3]['projection']);projection['audiences'][0].update(columns=['ratio'],charts=True)
        with self.assertRaises(ValidationError):policy(a,c,'D10.audience_projection_rules',projection,e['policy_decision'])

    def test_record_action_revocation_and_missing_authority_are_narrow(self):
        a,c,e,*_=self.data;report=build(self.data)
        Grant.objects.filter(case=c,user=a,action='finance.review').update(active=False)
        with self.assertRaises(PermissionDenied):performance.decide(a,c.pk,'performance',report.pk,'Finance','approve',e['finance_review'].pk,'No grant',rev(c))
        with self.assertRaises(PermissionDenied):performance.period_acceptance(self.data[8])

    def two_month_report(self,basis='accrual'):
        a,c,e,f,p,method,cfg,source,october,budget,t,recipient=self.data
        method=copy.deepcopy(method);method['periods']=['2026-09']+method['periods'][:-1];method['bu_keys']=[]
        method['metrics'].append({'key':'asset_display','label':'Assets closing','aggregation':'last_period','unit':'thousands_currency'})
        oracle=add_evidence(a,c.pk,'finance_oracle',json.dumps(method['oracles'],sort_keys=True),'synthetic:two-month-method');method['oracle_evidence_id']=oracle.pk
        cfg=policy(a,c,'D06.unit_sign_currency_period',dict(f['conventions'],period='2026-09',performance=method),e['policy_decision'])
        performance.decide(a,c.pk,'period_method',cfg.pk,'Finance','approve',e['finance_review'].pk,'September fiscal year explicitly selected',rev(c))
        for component in ['D06.account_bu_maps','D06.rule_oracle_refs']:
            rules=copy.deepcopy(reference_values(performance.active_component(component,c)))
            for rule in rules:rule['from_period']='2026-09';rule['to_period']='2026-10'
            conf=policy(a,c,component,rules,e['policy_decision'])
            analysis.review(a,c.pk,analysis.PURPOSE[component],conf.pk,'Finance','approve',e['finance_review'].pk,'Explicit two-period rule range',rev(c))
        input=add_evidence(a,c.pk,'financial_input',f['csv'].replace('2026-10','2026-09').replace('asset,500','asset,400'),'synthetic:september-export')
        batch=capture_import(a,c.pk,input.pk,rev(c))
        september=analysis.capture_source(a,c.pk,batch.pk,'synthetic-company',basis,timezone.now()-timedelta(hours=1),'complete','-209.99',e['finance_source'].pk,rev(c))
        analysis.review(a,c.pk,'source',september.pk,'Finance','approve',e['finance_review'].pk,'Exact September source accepted',rev(c))
        mapped=analysis.map_source(a,c.pk,september.pk,[],rev(c));run=analysis.calculate(a,c.pk,mapped.pk,rev(c))
        analysis.review(a,c.pk,'output',run.pk,'Finance','approve',e['finance_review'].pk,'Exact September output accepted',rev(c))
        september=performance.seal_period(a,c.pk,run.pk,None,rev(c))
        csv=p['csv']+''.join(p['csv'].replace('2026-10','2026-09').splitlines(keepends=True)[1:])
        csv+='synthetic-company,2026-09,company,,asset_display,0.40,NGN,thousands_currency\nsynthetic-company,2026-10,company,,asset_display,0.50,NGN,thousands_currency\n'
        b=self.budget(csv)
        performance.decide(a,c.pk,'budget',b.pk,'Finance','approve',e['finance_review'].pk,'Exact two-period budget accepted',rev(c))
        report=performance.build(a,c.pk,'2026-10',[october.pk,september.pk],b.pk,[],rev(c))
        return report,october

    def test_two_month_ytd_flow_sum_stock_close_and_pinned_history(self):
        report,october=self.two_month_report()
        self.assertEqual(report.result['status'],'complete');self.assertEqual(report.result['company']['pbt']['value'],'1219.98')
        self.assertEqual(report.result['company']['pbt']['budget'],'1000.00');self.assertEqual(report.result['company']['asset_display']['value'],'0.50')
        self.assertEqual(report.result['company']['asset_display']['budget'],'0.50')
        self.assertEqual(report.result['included_periods'],['2026-09','2026-10'])
        # Historical October arithmetic remains exact despite today's September profile/rule revisions.
        performance.period_acceptance(october)

    def test_mixed_accounting_basis_is_not_silently_aggregated(self):
        report,_=self.two_month_report(basis='cash')
        self.assertEqual(report.result['status'],'needs_attention')
        self.assertTrue(any('accounting basis mismatch' in f for f in report.result['findings']))

    def test_replacement_holds_queued_original_and_preserves_local_receipts(self):
        a,c,e,*_=self.data;original_report=build(self.data);d=self.approve_and_document(original_report);reserve_publication(a,c.pk,d.pk,rev(c))
        proposed,request=self.replacement();policy(a,c,'D10.restatement_rule_id',self.data[4]['restatement'],e['policy_decision'])
        performance.decide(a,c.pk,'restatement',request.pk,'Finance','approve',e['finance_review'].pk,'Exact replacement authorised',rev(c))
        performance.seal_period(a,c.pk,proposed.pk,request.pk,rev(c));run_publication_once()
        self.assertEqual(PublicationJob.objects.get().status,'held');self.assertFalse(PublicationReceipt.objects.exists());self.assertIn('609.99',json.dumps(d.payload))

    def test_changed_impact_inventory_requires_fresh_written_request(self):
        a,c,e,*_=self.data;proposed,request=self.replacement()
        build(self.data)
        policy(a,c,'D10.restatement_rule_id',self.data[4]['restatement'],e['policy_decision'])
        with self.assertRaises(ValidationError):performance.decide(a,c.pk,'restatement',request.pk,'Finance','approve',e['finance_review'].pk,'Impact changed',rev(c))

    def test_self_review_denial_and_foreign_record_are_not_admin_authority(self):
        from .helpers import setup_case
        a,c,e,*_=self.data;authority=copy.deepcopy(self.data[3]['authority'])
        authority['finance'] += [{'purpose':p,'role':'Finance','actions':['approve'],'allow_preparer_review':False} for p in ['budget','performance','period_method','restatement']]
        policy(a,c,'D05.decision_action_matrix',authority,e['policy_decision'])
        with self.assertRaises(PermissionDenied):performance.decide(a,c.pk,'budget',self.data[9].pk,'Finance','approve',e['finance_review'].pk,'No self appointment',rev(c))
        other,case=setup_case(username='other-performance');other.is_superuser=True;other.save()
        with self.assertRaises(PermissionDenied):performance.build(other,c.pk,'2026-10',[self.data[8].pk],self.data[9].pk,[],rev(c))
        with self.assertRaises(ValidationError):performance.build(other,case.pk,'2026-10',[self.data[8].pk],self.data[9].pk,[],rev(case))

    def test_invalid_budget_dimensions_and_future_effective_assertions(self):
        a,c,e,*_=self.data;p=self.data[4]
        b=self.budget(p['csv']+p['csv'].splitlines(keepends=True)[1]);self.assertTrue(any('Duplicate' in x for x in b.findings))
        with self.assertRaises(ValidationError):performance.capture_budget(a,c.pk,'FUTURE','monthly',timezone.now()+timedelta(days=1),'complete',b.evidence_id,b.approval_evidence_id,rev(c))
        with self.assertRaises(ValidationError):self.budget('wrong,columns\n1,2\n')

    def test_rendered_charts_match_only_immutable_public_projection(self):
        from apps.finance.presentation import present
        report=build(self.data);document=self.approve_and_document(report)
        rendered=present(document.payload);self.assertTrue(rendered['charts']);self.assertEqual(rendered['multiplier'],'100')
        self.assertNotIn('opaque-synthetic',json.dumps(rendered));self.assertFalse(present({'type':'status_report'}))
        payload=copy.deepcopy(document.payload)
        section=next(x for x in payload['sections'] if x['heading']=='financial_metrics');data=json.loads(section['text'])
        data['chart_spec']['data'][0]['actual']='999';section['text']=json.dumps(data)
        self.assertIsNone(present(payload))

    def test_unknown_or_incompatible_budget_basis_holds_only_comparison(self):
        a,c,e,*_=self.data
        for basis in [None,'cash']:
            budget=self.budget(self.data[4]['csv'],reference='BASIS-'+str(basis),basis=basis)
            performance.decide(a,c.pk,'budget',budget.pk,'Finance','approve',e['finance_review'].pk,'Captured source assertion reviewed; basis remains explicit',rev(c))
            report=performance.build(a,c.pk,'2026-10',[self.data[8].pk],budget.pk,[],rev(c))
            self.assertEqual(report.result['status'],'needs_attention');self.assertIsNone(report.result['company']['pbt']['budget'])
            self.assertEqual(report.result['company']['pbt']['value'],'609.99')

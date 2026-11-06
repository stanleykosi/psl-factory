import copy,json
from decimal import Decimal
from datetime import timedelta
from django.core.exceptions import ValidationError,PermissionDenied
from django.db import connection,transaction,DatabaseError
from django.test import TestCase
from django.utils import timezone
from apps.core.services import add_evidence
from apps.identity.models import Grant
from apps.policy.services import transition,PolicyHold,reference_values
from apps.finance import analysis
from apps.finance.models import FinanceRun,FinanceReview,FinanceSource
from apps.finance.documents import draft_report
from apps.documents.controlled import preflight,reserve_publication,request_review
from apps.documents.delivery import run_publication_once
from apps.documents.models import PublicationReceipt,PublicationJob
from apps.agents.finance_analysis import investigate_finance
from apps.finance.services import capture_import
from apps.documents.controlled import create_version,register_template
from .helpers import rev,setup_case
from .finance_analysis_helpers import fixture,policy,pipeline,METRICS

class FinanceAnalysisTests(TestCase):
    @classmethod
    def setUpTestData(cls):cls.a,cls.c,cls.e,cls.f,cls.configs,cls.source,cls.t,cls.recipient=fixture()

    def test_connected_mapping_formula_bu_review_and_local_aggregate_delivery(self):
        a,c,e,s=self.a,self.c,self.e,self.source;m,b,r=pipeline(a,c,s)
        self.assertEqual(connection.vendor,'postgresql');self.assertEqual(m.result['status'],'complete');self.assertEqual(b.result['status'],'complete');self.assertEqual(r.result['status'],'complete')
        self.assertEqual(r.result['company']['pbt']['value'],'609.99');self.assertEqual(r.result['by_bu']['alpha']['pbt']['value'],'889.99');self.assertEqual(r.result['by_bu']['beta']['pbt']['value'],'-280.00')
        self.assertEqual(r.result['company']['asset_display']['value'],'0.50');self.assertEqual(r.result['company']['asset_display']['unit'],'thousands_currency')
        self.assertTrue(all(x['conserved'] for x in b.result['conservation'].values()));self.assertFalse(analysis.certification_findings(r))
        analysis.review(a,c.pk,'output',r.pk,'Finance','approve',e['finance_review'].pk,'Reviewed exact Finance values and source lineage',rev(c))
        d=draft_report(a,c.pk,r.pk,self.t.pk,'internal',rev(c));self.assertFalse(preflight(d))
        with self.assertRaises(ValidationError):request_review(a,c.pk,d.pk,rev(c))
        reserve_publication(a,c.pk,d.pk,rev(c));self.assertTrue(run_publication_once())
        receipt=PublicationReceipt.objects.get();self.assertEqual(receipt.recipient_id,self.recipient.pk)
        payload=json.dumps(receipt.payload);self.assertIn('609.99',payload);self.assertNotIn('opaque-synthetic',payload);self.assertNotIn('staff_pool',payload)
        self.assertFalse(r.result['ledger_posted']);self.assertEqual(r.result['bu_comparison']['pbt']['difference'],'0.00')

    def test_lineage_agent_ui_and_idempotent_rebuild(self):
        a,c,e,s=self.a,self.c,self.e,self.source;m,b,r=pipeline(a,c,s)
        self.assertEqual(m.pk,analysis.map_source(a,c.pk,s.pk,[],rev(c)).pk)
        self.assertEqual(r.pk,analysis.calculate(a,c.pk,b.pk,rev(c)).pk)
        run=investigate_finance(a,c.pk,r.pk,rev(c));self.assertFalse(run.result['ledger_posted']);self.assertFalse(run.result['approval_granted']);self.assertTrue(run.result['citations']);self.assertEqual(len(run.result['lineage']),3)
        self.assertTrue(run.result['current']);self.assertIn(e['finance_basis'].pk,[x['id'] for x in run.result['citations']]);self.assertNotIn('opaque-synthetic',json.dumps(run.result))
        self.client.force_login(a);url=f'/cases/{c.pk}/finance/'
        self.assertContains(self.client.get(url),'Finance mapping, history and BU allocation');self.assertContains(self.client.get(url),'609.99')
        self.assertEqual(self.client.post(url,{'action':'investigate','run':r.pk,'revision':rev(c)}).status_code,302)
        self.assertContains(self.client.get(f'/cases/{c.pk}/'),f'href="{url}"')

    def test_later_source_or_rule_change_invalidates_queued_effect(self):
        a,c,e,s=self.a,self.c,self.e,self.source;m,b,r=pipeline(a,c,s)
        analysis.review(a,c.pk,'output',r.pk,'Finance','approve',e['finance_review'].pk,'Reviewed',rev(c));d=draft_report(a,c.pk,r.pk,self.t.pk,'internal',rev(c));reserve_publication(a,c.pk,d.pk,rev(c))
        policy(a,c,'D07.rounding_residual_rule_id',dict(self.f['rounding'],residual='hold',residual_bu=None),e['policy_decision'])
        self.client.force_login(a);self.assertContains(self.client.get(f'/cases/{c.pk}/finance/'),'Stale preview')
        self.assertTrue(preflight(d));run_publication_once();self.assertEqual(PublicationJob.objects.get().status,'held');self.assertFalse(PublicationReceipt.objects.exists())

    def test_postgres_immutability_of_source_run_and_import(self):
        m,b,r=pipeline(self.a,self.c,self.source)
        for table in ['finance_financialimport','finance_importvalidation','finance_financesource','finance_financerun','finance_financereview']:
            with self.assertRaises(DatabaseError),transaction.atomic():
                with connection.cursor() as cur:cur.execute('DELETE FROM '+table)

    def imported(self,csv,complete='complete',control=None):
        e=add_evidence(self.a,self.c.pk,'financial_input',csv,'synthetic:changed-export')
        batch=capture_import(self.a,self.c.pk,e.pk,rev(self.c))
        return analysis.capture_source(self.a,self.c.pk,batch.pk,'synthetic-company','accrual',timezone.now()-timedelta(hours=1),complete,control,self.e['finance_source'].pk,rev(self.c))

    def configure_basis(self,basis):
        e=add_evidence(self.a,self.c.pk,'finance_basis',json.dumps(basis,sort_keys=True),'synthetic:basis-revision')
        policy(self.a,self.c,'D07.effective_membership_ref',dict(basis,evidence_id=e.pk),self.e['policy_decision'])
        policy(self.a,self.c,'D07.authorized_input_refs',[{'entity':'synthetic-company','period':basis['period'],'provider':'HR','evidence_id':e.pk,'purpose':'allocation_basis'}],self.e['policy_decision'])
        return e

    def test_unknown_is_not_zero_and_missing_accounts_have_no_iferror_default(self):
        for csv in [self.f['csv'].replace('sales,-1000','sales,'),self.f['csv'].replace('sales,-1000,NGN,2026-10\n','')]:
            source=self.imported(csv);m=analysis.map_source(self.a,self.c.pk,source.pk,[],rev(self.c));r=analysis.calculate(self.a,self.c.pk,m.pk,rev(self.c))
            self.assertEqual(m.result['status'],'needs_attention');self.assertIsNone(r.result['company']['revenue']['value']);self.assertIsNone(r.result['company']['pbt']['value'])
            self.assertEqual(r.result['company']['asset_display']['value'],'0.50')
            with self.assertRaises(ValidationError):analysis.review(self.a,self.c.pk,'output',r.pk,'Finance','approve',self.e['finance_review'].pk,'Cannot certify unknowns',rev(self.c))

    def test_explicit_zero_negative_and_source_sign_are_preserved(self):
        source=self.imported(self.f['csv'].replace('sales,-1000','sales,0'))
        m=analysis.map_source(self.a,self.c.pk,source.pk,[],rev(self.c));r=analysis.calculate(self.a,self.c.pk,m.pk,rev(self.c))
        self.assertEqual(m.result['rows'][0]['amount'],'0');self.assertEqual(r.result['company']['revenue']['value'],'0.00');self.assertEqual(r.result['company']['pbt']['value'],'-390.01')

    def test_unmapped_duplicate_and_explicit_row_handling(self):
        source=self.imported(self.f['csv']+'mystery,5,NGN,2026-10\n');m=analysis.map_source(self.a,self.c.pk,source.pk,[],rev(self.c))
        self.assertTrue(any('Unmapped' in f for f in m.result['findings']));self.assertIsNone(m.result['rows'][-1]['report_line'])
        source=self.imported(self.f['csv'].replace('sales,-1000,NGN,2026-10','sales,-500,NGN,2026-10\nsales,-500,NGN,2026-10'))
        m=analysis.map_source(self.a,self.c.pk,source.pk,[],rev(self.c));self.assertTrue(any('Duplicate source' in f for f in m.result['findings']))
        maps=copy.deepcopy(self.f['mapping']);maps[0]['source_rows']='preserve_explicit_rows';policy(self.a,self.c,'D06.account_bu_maps',maps,self.e['policy_decision'])
        m=analysis.map_source(self.a,self.c.pk,source.pk,[],rev(self.c));self.assertEqual(m.result['status'],'complete')
        r=analysis.calculate(self.a,self.c.pk,m.pk,rev(self.c));self.assertEqual(r.result['company']['revenue']['value'],'1000.00')

    def test_currency_period_and_effective_mapping_conflicts_do_not_silently_convert(self):
        for csv in [self.f['csv'].replace('sales,-1000,NGN','sales,-1000,USD'),self.f['csv'].replace('sales,-1000,NGN,2026-10','sales,-1000,NGN,2026-09')]:
            s=self.imported(csv);m=analysis.map_source(self.a,self.c.pk,s.pk,[],rev(self.c));self.assertIsNone(m.result['rows'][0]['amount']);self.assertTrue(m.result['findings'])
        maps=copy.deepcopy(self.f['mapping']);maps[0]['from_period']=maps[0]['to_period']='2026-09';policy(self.a,self.c,'D06.account_bu_maps',maps,self.e['policy_decision'])
        m=analysis.map_source(self.a,self.c.pk,self.source.pk,[],rev(self.c));self.assertTrue(any('Unmapped' in f for f in m.result['findings']))

    def test_invalid_overlap_double_attribution_and_rule_oracles(self):
        a,c,e=self.a,self.c,self.e
        maps=copy.deepcopy(self.f['mapping']);maps.append(dict(maps[0],key='duplicate_map'))
        with self.assertRaises(ValidationError):policy(a,c,'D06.account_bu_maps',maps,e['policy_decision'])
        maps=copy.deepcopy(self.f['mapping']);maps[0]['pool']='double_count'
        with self.assertRaises(ValidationError):policy(a,c,'D06.account_bu_maps',maps,e['policy_decision'])
        rules=copy.deepcopy(reference_values(self.configs['D06.rule_oracle_refs']));rules[0]['terms'][0]['coefficient']='1'
        with self.assertRaises(ValidationError):policy(a,c,'D06.rule_oracle_refs',rules,e['policy_decision'])
        rules=copy.deepcopy(reference_values(self.configs['D06.rule_oracle_refs']));rules[-1]['divisor']='1000000'
        with self.assertRaises(ValidationError):policy(a,c,'D06.rule_oracle_refs',rules,e['policy_decision'])

    def test_formula_graph_cycles_and_missing_dependency_are_rejected(self):
        from apps.finance.rules import formula_order
        rules=copy.deepcopy(reference_values(self.configs['D06.rule_oracle_refs']))
        rules[0]['terms']=[{'kind':'formula','key':'pbt','coefficient':'1','value_stage':'rounded_formula'}]
        with self.assertRaises(ValidationError):formula_order(rules)
        rules[0]['terms'][0]['key']='absent'
        with self.assertRaises(ValidationError):formula_order(rules)

    def test_rounding_residual_is_visible_conserved_and_not_waived(self):
        a,c=self.a,self.c;policy(a,c,'D07.rounding_residual_rule_id',dict(self.f['rounding'],residual='hold',residual_bu=None),self.e['policy_decision'])
        m=analysis.map_source(a,c.pk,self.source.pk,[],rev(c));b=analysis.allocate(a,c.pk,m.pk,METRICS,rev(c));r=b.result['conservation']['opex']
        self.assertEqual(r['allocated'],'100.02');self.assertEqual(r['residual'],'-0.01');self.assertTrue(r['conserved']);self.assertEqual(b.result['status'],'needs_attention')

    def test_missing_headcount_holds_only_its_pool(self):
        a,c=self.a,self.c;transition(a,self.configs['D07.effective_membership_ref'].pk,'revoked')
        m=analysis.map_source(a,c.pk,self.source.pk,[],rev(c));b=analysis.allocate(a,c.pk,m.pk,METRICS,rev(c))
        by_account={x['account']:x for x in b.result['rows']};self.assertEqual(by_account['staff_pool']['status'],'held');self.assertEqual(by_account['staff_pool']['unallocated'],'90')
        self.assertEqual(by_account['shared_opex']['status'],'allocated');self.assertEqual(by_account['sales']['status'],'allocated')

    def test_fixed_pools_do_not_depend_on_unrelated_missing_hr_rules(self):
        a,c=self.a,self.c;pools=copy.deepcopy(self.f['pools']);pools[1].update(method='fixed_weights',weights=[{'bu':'alpha','weight':'2'},{'bu':'beta','weight':'1'}]);policy(a,c,'D07.allocation_pool_rules',pools,self.e['policy_decision'])
        m=analysis.map_source(a,c.pk,self.source.pk,[],rev(c));b=analysis.allocate(a,c.pk,m.pk,METRICS,rev(c));self.assertEqual(b.result['status'],'complete')
        transition(a,self.configs['D07.effective_membership_ref'].pk,'revoked');analysis.ensure_current(b)
        self.assertNotIn('D07.effective_membership_ref',b.snapshot['policies'])

    def test_unknown_zero_or_incomplete_basis_never_becomes_an_allocation(self):
        a,c=self.a,self.c
        for change in ['unknown','partial','zero']:
            basis=copy.deepcopy(self.f['basis'])
            if change=='unknown':basis['rows'][0]['weight']=None
            elif change=='partial':basis['completeness']='partial'
            else:
                for row in basis['rows']:row['weight']='0'
                policy(a,c,'D07.join_overlap_rule_id',dict(self.f['join'],weight_semantics='explicit_fte'),self.e['policy_decision'])
            self.configure_basis(basis);m=analysis.map_source(a,c.pk,self.source.pk,[],rev(c));b=analysis.allocate(a,c.pk,m.pk,METRICS,rev(c))
            staff=next(x for x in b.result['rows'] if x['account']=='staff_pool');self.assertEqual(staff['status'],'held');self.assertEqual(staff['unallocated'],'90');self.assertTrue(b.result['conservation']['staff_cost']['conserved'])

    def test_basis_evidence_and_duplicates_are_validated(self):
        a,c=self.a,self.c;basis=dict(self.f['basis'],evidence_id=self.e['finance_basis'].pk);basis['rows']=list(basis['rows'])+[basis['rows'][0]]
        with self.assertRaises(ValidationError):policy(a,c,'D07.effective_membership_ref',basis,self.e['policy_decision'])
        basis=dict(self.f['basis'],evidence_id=self.e['finance_basis'].pk);basis['completeness']='partial'
        with self.assertRaises(ValidationError):policy(a,c,'D07.effective_membership_ref',basis,self.e['policy_decision'])

    def test_exclusions_unknown_bu_and_excess_precision_are_not_dropped(self):
        a,c=self.a,self.c;pools=copy.deepcopy(self.f['pools']);pools[0]['excluded_accounts']=['shared_opex'];policy(a,c,'D07.allocation_pool_rules',pools,self.e['policy_decision'])
        m=analysis.map_source(a,c.pk,self.source.pk,[],rev(c));b=analysis.allocate(a,c.pk,m.pk,METRICS,rev(c));self.assertEqual(b.result['conservation']['opex']['unallocated'],'100.01')
        pools[0]['excluded_accounts']=[];pools[0]['weights'][0]['bu']='missing_bu';policy(a,c,'D07.allocation_pool_rules',pools,self.e['policy_decision'])
        b=analysis.allocate(a,c.pk,m.pk,METRICS,rev(c));self.assertEqual(b.result['conservation']['opex']['unallocated'],'100.01')
        policy(a,c,'D07.allocation_pool_rules',self.f['pools'],self.e['policy_decision']);s=self.imported(self.f['csv'].replace('shared_opex,100.01','shared_opex,100.005'))
        m=analysis.map_source(a,c.pk,s.pk,[],rev(c));b=analysis.allocate(a,c.pk,m.pk,METRICS,rev(c));self.assertEqual(b.result['conservation']['opex']['unallocated'],'100.005')

    def test_reporting_adjustments_need_review_and_do_not_post(self):
        a,c,e=self.a,self.c,self.e
        adj=analysis.adjustment(a,c.pk,self.source.pk,'ADJ-1','reclassification',[{'account':'direct_cost','amount':'10'},{'account':'shared_opex','amount':'-10'}],e['finance_adjustment'].pk,'Supported reporting reclassification',rev(c))
        with self.assertRaises(ValidationError):analysis.map_source(a,c.pk,self.source.pk,[adj.pk],rev(c))
        analysis.review(a,c.pk,'adjustment',adj.pk,'Finance','approve',e['finance_review'].pk,'Reviewed source and reason',rev(c))
        m=analysis.map_source(a,c.pk,self.source.pk,[adj.pk],rev(c));self.assertEqual(m.result['source_control']['difference'],'0.00');self.assertEqual(len(m.result['rows']),7);self.assertFalse(m.result['ledger_posted'])
        r=analysis.calculate(a,c.pk,m.pk,rev(c));self.assertEqual(r.result['company']['expenses']['value'],'390.01')
        with self.assertRaises(ValidationError):analysis.adjustment(a,c.pk,self.source.pk,'ADJ-2','reclassification',[{'account':'direct_cost','amount':'10'}],e['finance_adjustment'].pk,'Unbalanced',rev(c))

    def test_adjustment_revision_preserves_old_and_invalidates_selected_run(self):
        a,c,e=self.a,self.c,self.e
        def adjust(amount):return analysis.adjustment(a,c.pk,self.source.pk,'ADJ-1','additive',[{'account':'direct_cost','amount':amount}],e['finance_adjustment'].pk,'Actual supported reporting-only correction',rev(c))
        old=adjust('10');analysis.review(a,c.pk,'adjustment',old.pk,'Finance','approve',e['finance_review'].pk,'Reviewed',rev(c));m=analysis.map_source(a,c.pk,self.source.pk,[old.pk],rev(c))
        new=adjust('11');self.assertEqual(new.number,2)
        with self.assertRaises(ValidationError):analysis.ensure_current(m)
        self.assertEqual(old.lines[0]['amount'],'10')

    def test_missing_review_authority_does_not_disable_capture_or_previews(self):
        a,c=self.a,self.c;transition(a,self.configs['D05.decision_action_matrix'].pk,'revoked')
        m=analysis.map_source(a,c.pk,self.source.pk,[],rev(c));r=analysis.calculate(a,c.pk,m.pk,rev(c));self.assertEqual(r.result['company']['pbt']['value'],'609.99')
        self.assertTrue(analysis.certification_findings(r))
        with self.assertRaises(PolicyHold):analysis.review(a,c.pk,'source',self.source.pk,'Finance','approve',self.e['finance_review'].pk,'Authority missing',rev(c))

    def test_unreviewed_rules_and_return_block_output_not_draft_computation(self):
        a,c,e=self.a,self.c,self.e;new=policy(a,c,'D06.account_bu_maps',self.f['mapping'],e['policy_decision'])
        m=analysis.map_source(a,c.pk,self.source.pk,[],rev(c));r=analysis.calculate(a,c.pk,m.pk,rev(c));self.assertEqual(r.result['status'],'complete');self.assertTrue(analysis.certification_findings(r))
        analysis.review(a,c.pk,'mapping',new.pk,'Finance','return',e['finance_review'].pk,'Mapping clarification needed',rev(c))
        with self.assertRaises(ValidationError):analysis.ensure_current(m)

    def test_source_total_controls_and_unknown_completeness_hold_certification(self):
        a,c,e=self.a,self.c,self.e
        for completeness,total in [('unknown','-109.99'),('complete',None),('complete','0')]:
            s=analysis.capture_source(a,c.pk,self.source.batch_id,'synthetic-company','accrual',timezone.now()-timedelta(hours=1),completeness,total,e['finance_source'].pk,rev(c))
            analysis.review(a,c.pk,'source',s.pk,'Finance','approve',e['finance_review'].pk,'Exact declared source context reviewed',rev(c))
            m,b,r=pipeline(a,c,s);self.assertTrue(analysis.certification_findings(r))

    def test_policy_missing_invalid_expired_future_and_revoked_scope(self):
        a,c,e=self.a,self.c,self.e
        transition(a,self.configs['D06.account_bu_maps'].pk,'revoked')
        with self.assertRaises(PolicyHold):analysis.map_source(a,c.pk,self.source.pk,[],rev(c))
        from apps.policy.finance_drafts import draft_finance_policy
        cfg=draft_finance_policy(a,c.pk,'D06.account_bu_maps',self.f['mapping'],e['policy_decision'].pk,timezone.now()+timedelta(days=1));transition(a,cfg.pk,'validated');transition(a,cfg.pk,'active')
        with self.assertRaises(PolicyHold):analysis.map_source(a,c.pk,self.source.pk,[],rev(c))
        from apps.policy.services import save_draft
        expired=dict(cfg.envelope,effective_from=(timezone.now()-timedelta(days=2)).isoformat(),effective_until=(timezone.now()-timedelta(days=1)).isoformat())
        old=save_draft(a,c.pk,expired);transition(a,old.pk,'validated');transition(a,old.pk,'active')
        with self.assertRaises(PolicyHold):analysis.map_source(a,c.pk,self.source.pk,[],rev(c))
        with self.assertRaises(ValidationError):policy(a,c,'D07.rounding_residual_rule_id',dict(self.f['rounding'],decimal_places=-1),e['policy_decision'])

    def test_scoped_action_stale_admin_and_recipient_revocation(self):
        a,c,e=self.a,self.c,self.e;outsider,other=setup_case(username='finance-outsider');outsider.is_superuser=True;outsider.is_staff=True;outsider.save()
        with self.assertRaises(PermissionDenied):analysis.map_source(outsider,c.pk,self.source.pk,[],rev(c))
        with self.assertRaises(ValidationError):analysis.map_source(outsider,other.pk,self.source.pk,[],rev(other))
        old=rev(c);m=analysis.map_source(a,c.pk,self.source.pk,[],old)
        # Reusing an identical run makes no mutation; a distinct stage does.
        analysis.allocate(a,c.pk,m.pk,METRICS,rev(c))
        with self.assertRaises(ValidationError):analysis.calculate(a,c.pk,m.pk,old)
        _,_,r=pipeline(a,c,self.source);analysis.review(a,c.pk,'output',r.pk,'Finance','approve',e['finance_review'].pk,'Reviewed',rev(c));d=draft_report(a,c.pk,r.pk,self.t.pk,'internal',rev(c));reserve_publication(a,c.pk,d.pk,rev(c))
        Grant.objects.filter(case=c,user=self.recipient,action='finance.read').update(active=False);run_publication_once();self.assertFalse(PublicationReceipt.objects.exists());self.assertEqual(PublicationJob.objects.get().status,'held')

    def test_no_default_self_review_and_real_distinct_principal(self):
        from django.contrib.auth import get_user_model
        from apps.policy.services import register_reference
        from .helpers import activate
        a,c,e=self.a,self.c,self.e;authority=copy.deepcopy(self.f['authority'])
        for entry in authority['finance']:entry['allow_preparer_review']=False
        policy(a,c,'D05.decision_action_matrix',authority,e['policy_decision'])
        with self.assertRaises(PermissionDenied):analysis.review(a,c.pk,'source',self.source.pk,'Finance','approve',e['finance_review'].pk,'Cannot self appoint',rev(c))
        reviewer=get_user_model().objects.create_user(username='appointed-finance-reviewer');Grant.objects.create(case=c,user=reviewer,action='finance.review')
        refs=[]
        for user in [a,reviewer]:refs.append(register_reference(a,c.pk,'finance:principal:'+str(user.pk),'schema:psl/role-assignment/v1',{'role':'Finance','user_id':user.pk},e['policy_decision'].pk).ref)
        activate(a,c,'D05.role_principal_assignments',refs,e['policy_decision'])
        r=analysis.review(reviewer,c.pk,'source',self.source.pk,'Finance','approve',e['finance_review'].pk,'Actual distinct principal review',rev(c));self.assertEqual(r.actor_id,reviewer.pk)

    def test_unbound_finance_document_or_client_projection_cannot_publish(self):
        a,c,e=self.a,self.c,self.e
        fields={k:{'text':'Unbound financial assertion','evidence_ids':[e['finance_review'].pk]} for k in ['executive_summary','financial_metrics','bu_totals']}
        v=create_version(a,c.pk,self.t.pk,'Unbound metrics','internal',fields,rev(c));self.assertTrue(preflight(v))
        with self.assertRaises(ValidationError):reserve_publication(a,c.pk,v.pk,rev(c))
        projection=copy.deepcopy(self.f['projection']);projection['audiences'][0]['audience']='client'
        with self.assertRaises(ValidationError):policy(a,c,'D10.audience_projection_rules',projection,e['policy_decision'])

    def test_report_publisher_role_and_domain_review_revocation_hold_delivery(self):
        a,c,e=self.a,self.c,self.e;m,b,r=pipeline(a,c,self.source)
        analysis.review(a,c.pk,'output',r.pk,'Finance','approve',e['finance_review'].pk,'Reviewed',rev(c));d=draft_report(a,c.pk,r.pk,self.t.pk,'internal',rev(c));reserve_publication(a,c.pk,d.pk,rev(c))
        Grant.objects.filter(case=c,user=a,action='finance.review').update(active=False)
        run_publication_once();self.assertFalse(PublicationReceipt.objects.exists());self.assertEqual(PublicationJob.objects.get().status,'held')

    def test_delivered_finance_inbox_rechecks_current_finance_read(self):
        a,c,e=self.a,self.c,self.e;_,_,r=pipeline(a,c,self.source)
        analysis.review(a,c.pk,'output',r.pk,'Finance','approve',e['finance_review'].pk,'Reviewed',rev(c))
        d=draft_report(a,c.pk,r.pk,self.t.pk,'internal',rev(c));reserve_publication(a,c.pk,d.pk,rev(c));run_publication_once()
        self.client.force_login(self.recipient)
        self.assertContains(self.client.get('/documents/inbox/'),'Finance configured output')
        Grant.objects.filter(case=c,user=self.recipient,action='finance.read').update(active=False)
        self.assertNotContains(self.client.get('/documents/inbox/'),'Finance configured output')
        self.assertEqual(PublicationReceipt.objects.count(),1)

    def test_exact_source_account_names_with_spaces_and_no_implicit_trim(self):
        maps=copy.deepcopy(self.f['mapping']);maps[0]['account']='4000 Sales income'
        policy(self.a,self.c,'D06.account_bu_maps',maps,self.e['policy_decision'])
        source=self.imported(self.f['csv'].replace('sales,-1000','4000 Sales income,-1000'))
        self.client.force_login(self.a);url=f'/cases/{self.c.pk}/finance/'
        self.assertEqual(self.client.post(url,{'action':'map','source':source.pk,'revision':rev(self.c)}).status_code,302)
        mapped=FinanceRun.objects.get(source=source,kind='mapping')
        self.assertEqual(mapped.result['status'],'complete')
        self.assertEqual(mapped.result['rows'][0]['account'],'4000 Sales income')
        self.assertEqual(self.client.post(url,{'action':'allocate','parent':mapped.pk,'metrics':METRICS,'revision':rev(self.c)}).status_code,302)
        allocated=FinanceRun.objects.get(source=source,kind='allocation')
        self.assertEqual(self.client.post(url,{'action':'calculate','parent':allocated.pk,'revision':rev(self.c)}).status_code,302)
        self.assertContains(self.client.get(url),'609.99');self.assertContains(self.client.get(url),'BU metrics and company comparison')
        maps[0]['account']=' 4000 Sales income'
        with self.assertRaises(ValidationError):policy(self.a,self.c,'D06.account_bu_maps',maps,self.e['policy_decision'])

    def test_future_actual_basis_and_duplicate_oracle_scenarios_rejected(self):
        basis=copy.deepcopy(self.f['basis']);basis['as_of']=(timezone.now()+timedelta(days=40)).isoformat();basis['period']=basis['as_of'][:7]
        with self.assertRaises(ValidationError):self.configure_basis(basis)
        formulas=copy.deepcopy(self.f['formulas'])
        for rule in formulas:
            rule['oracles'][1]['key']=rule['oracles'][0]['key']
            evidence=add_evidence(self.a,self.c.pk,'finance_oracle',json.dumps(rule['oracles'],sort_keys=True),'synthetic:duplicate-oracle-key')
            rule['oracle_evidence_id']=evidence.pk
        with self.assertRaises(ValidationError):policy(self.a,self.c,'D06.rule_oracle_refs',formulas,self.e['policy_decision'])

    def test_formula_depth_budget_is_independent_of_configuration_order(self):
        from apps.finance.rules import formula_order
        rules=[]
        for index in range(32):
            rules.append({'key':f'f{index}','scope':'company_and_bu','output_unit':'major_currency',
                          'terms':[] if index==0 else [{'kind':'formula','key':f'f{index-1}'}]})
        for ordered in [rules,list(reversed(rules))]:
            with self.assertRaises(ValidationError):formula_order(ordered)

    def test_source_convention_revision_requires_fresh_source_acceptance(self):
        _,_,old=pipeline(self.a,self.c,self.source)
        policy(self.a,self.c,'D06.unit_sign_currency_period',self.f['conventions'],self.e['policy_decision'])
        with self.assertRaises(ValidationError):analysis.ensure_current(old)
        _,_,preview=pipeline(self.a,self.c,self.source)
        self.assertEqual(preview.result['company']['pbt']['value'],'609.99')
        self.assertTrue(analysis.certification_findings(preview))
        analysis.review(self.a,self.c.pk,'source',self.source.pk,'Finance','approve',self.e['finance_review'].pk,'New exact source conventions accepted',rev(self.c))
        _,_,reviewed=pipeline(self.a,self.c,self.source)
        self.assertFalse(analysis.certification_findings(reviewed))

    def test_unrelated_authority_namespace_preserves_finance_reviews(self):
        _,_,output=pipeline(self.a,self.c,self.source)
        authority=copy.deepcopy(self.f['authority']);authority['rfp']={'outcome_roles':['CEO']}
        policy(self.a,self.c,'D05.decision_action_matrix',authority,self.e['policy_decision'])
        analysis.ensure_current(output);self.assertFalse(analysis.certification_findings(output))
        authority['finance']=[entry for entry in authority['finance'] if entry['purpose']!='formula']
        policy(self.a,self.c,'D05.decision_action_matrix',authority,self.e['policy_decision'])
        with self.assertRaises(ValidationError):analysis.ensure_current(output)
        preview=analysis.calculate(self.a,self.c.pk,output.parent_id,rev(self.c))
        self.assertEqual(preview.result['company']['pbt']['value'],'609.99');self.assertTrue(analysis.certification_findings(preview))

    def test_malformed_typed_operation_lists_fail_validation_without_runs(self):
        with self.assertRaises(ValidationError):analysis.map_source(self.a,self.c.pk,self.source.pk,[{}],rev(self.c))
        self.assertFalse(FinanceRun.objects.exists())
        mapped=analysis.map_source(self.a,self.c.pk,self.source.pk,[],rev(self.c))
        with self.assertRaises(ValidationError):analysis.allocate(self.a,self.c.pk,mapped.pk,[{}],rev(self.c))
        self.assertFalse(FinanceRun.objects.filter(kind='allocation').exists())

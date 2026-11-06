import copy,json
from django.test import TestCase
from django.core.exceptions import ValidationError,PermissionDenied
from django.db import DatabaseError,transaction,connection
from django.utils import timezone
from django.contrib.auth import get_user_model
from apps.core.models import Case
from apps.identity.models import Grant
from apps.finance import billing
from apps.finance.models import BillingCoverage,BillingUsage,BillingPreparation,Handoff
from apps.policy.finance_drafts import draft_finance_policy
from apps.policy.services import transition
from apps.agents.billing import investigate
from apps.pmo.services import complete_milestone
from apps.workflows.services import run_once
from .helpers import setup_case,rev,signed
from .billing_helpers import coverage,prices,usage,prepare,policy,evidence,stage_policy,FIXTURE

class BillingTests(TestCase):
    def setUp(self):self.a,self.c=setup_case();self.cov=coverage(self.a,self.c)
    def test_missing_policy_holds_calculation_but_capture_and_agent_work(self):
        u=usage(self.a,self.c,self.cov);p=prepare(self.a,self.c,self.cov,u=u)
        self.assertEqual(p.result['status'],'held');self.assertIsNone(p.result['total'])
        self.assertIn('D08.effective_price_rule_refs: MISSING',p.result['findings'])
        log=investigate(self.a,self.c.pk,self.cov.pk,p.pk,rev(self.c))
        self.assertFalse(log.result['current']);self.assertFalse(log.result['approval_granted'])
        self.assertIn(u.evidence_id,[x['id'] for x in log.result['citations']])
    def test_exact_pricing_lineage_idempotence_and_no_financial_effect(self):
        configs=prices(self.a,self.c,self.cov);u=usage(self.a,self.c,self.cov);p=prepare(self.a,self.c,self.cov,u=u)
        self.assertEqual(p.result['status'],'prepared');self.assertEqual(p.result['total'],'32.25')
        self.assertEqual(p.result['lines'][0]['net'],'30.00');self.assertEqual(p.result['lines'][0]['tax'],'2.25')
        self.assertEqual(p.snapshot['usage_hash'],u.evidence.sha256);self.assertEqual(len(p.snapshot['policies']),2)
        self.assertEqual(prepare(self.a,self.c,self.cov,u=u).pk,p.pk);self.assertEqual(BillingPreparation.objects.count(),1)
        billing.ensure_current(p)
        self.assertFalse(any(p.result[k] for k in ['invoice_issued','ledger_posted','cash_received','release_authorized']))
    def test_unknown_is_not_zero_and_real_zero_remains_zero(self):
        prices(self.a,self.c,self.cov)
        body=json.loads(FIXTURE.read_text(encoding='utf-8'))['csv']
        u=usage(self.a,self.c,self.cov,body.replace(',12\n',',\n'));p=prepare(self.a,self.c,self.cov,u=u)
        self.assertIsNone(p.result['total']);self.assertIsNone(p.result['lines'][0]['net'])
        u=usage(self.a,self.c,self.cov,body.replace('tx-example-1','zero').replace(',12\n',',0\n'))
        self.assertEqual(prepare(self.a,self.c,self.cov,u=u).result['total'],'0.00')
    def test_duplicate_source_and_transaction_corrections_never_silently_bill(self):
        prices(self.a,self.c,self.cov);usage(self.a,self.c,self.cov)
        with self.assertRaises(ValidationError):usage(self.a,self.c,self.cov)
        body=json.loads(FIXTURE.read_text(encoding='utf-8'))['csv'].replace(',12\n',',13\n')
        second=usage(self.a,self.c,self.cov,body)
        self.assertTrue(any('previously captured transaction' in f for f in second.findings))
        self.assertEqual(prepare(self.a,self.c,self.cov,u=second).result['status'],'held')
    def test_malformed_and_mixed_scope_usage_and_negative_quantities_hold(self):
        prices(self.a,self.c,self.cov)
        with self.assertRaises(ValidationError):usage(self.a,self.c,self.cov,'quantity,rate\n1,3\n')
        body=json.loads(FIXTURE.read_text(encoding='utf-8'))['csv'].replace('client-example','another').replace(',12\n',',-1\n')
        u=usage(self.a,self.c,self.cov,body);p=prepare(self.a,self.c,self.cov,u=u)
        self.assertIsNone(u.rows[0]['quantity']);self.assertEqual(p.result['status'],'held')
    def test_policy_oracle_tampering_and_unsupported_tier_method_fail_validation(self):
        f=json.loads(FIXTURE.read_text(encoding='utf-8'));m=f['arithmetic'];e=evidence(self.a,self.c,'billing_oracle',json.dumps(m['oracles']));m['oracle_evidence_id']=e.pk
        m['oracles'][0]['total']='999.00'
        with self.assertRaises(ValidationError):policy(self.a,self.c,'D08.tax_tier_rounding_rules',m)
        r=dict(f['rule'],coverage_id=self.cov.pk,implementation='invented_tier_v1')
        with self.assertRaises(ValidationError):policy(self.a,self.c,'D08.effective_price_rule_refs',[r])
        self.assertEqual(BillingPreparation.objects.count(),0)
    def test_overlapping_prices_and_wrong_contract_reference_fail(self):
        f=json.loads(FIXTURE.read_text(encoding='utf-8'));r=dict(f['rule'],coverage_id=self.cov.pk)
        with self.assertRaises(ValidationError):policy(self.a,self.c,'D08.effective_price_rule_refs',[r,dict(r,key='overlap')])
        with self.assertRaises(ValidationError):policy(self.a,self.c,'D12.contract_version_ref',{'coverage_id':self.cov.pk,'signed_evidence_id':self.cov.evidence_id,'signed_sha256':self.cov.evidence.sha256})
    def test_revoked_and_new_coverage_leave_prior_figures_immutable_and_stale(self):
        configs=prices(self.a,self.c,self.cov);u=usage(self.a,self.c,self.cov);p=prepare(self.a,self.c,self.cov,u=u)
        transition(self.a,configs[0].pk,'revoked')
        with self.assertRaises(ValidationError):billing.ensure_current(p)
        held=prepare(self.a,self.c,self.cov,u=u);self.assertEqual(held.result['status'],'held')
        prices(self.a,self.c,self.cov);p2=prepare(self.a,self.c,self.cov,u=u)
        c2=coverage(self.a,self.c);self.assertEqual(c2.version,2)
        with self.assertRaises(ValidationError):billing.ensure_current(p2)
        p.refresh_from_db();self.assertEqual(p.result['total'],'32.25')
    def test_cross_case_and_admin_do_not_grant_authority(self):
        other=Case.objects.create(tenant=self.c.tenant,title='Private',kind='project',synthetic=True)
        with self.assertRaises(ValidationError):billing.prepare(self.a,self.c.pk,999999,'signed_sow',None,None,rev(self.c))
        self.a.is_superuser=True;self.a.is_staff=True;self.a.save()
        Grant.objects.filter(user=self.a,case=self.c,action='finance.billing.capture').update(active=False)
        with self.assertRaises(PermissionDenied):usage(self.a,self.c,self.cov)
        self.client.force_login(self.a);self.assertEqual(self.client.get(f'/cases/{other.pk}/finance/billing/').status_code,404)
    def test_stale_revision_and_wrong_usage_selection_rejected(self):
        u=usage(self.a,self.c,self.cov)
        with self.assertRaises(ValidationError):billing.prepare(self.a,self.c.pk,self.cov.pk,'usage',u.pk,None,0)
        with self.assertRaises(ValidationError):prepare(self.a,self.c,self.cov,kind='signed_sow',u=u)
    def test_opening_stage_does_not_depend_on_other_predicates_or_contract_total(self):
        e=signed(self.a,self.c);stage_policy(self.a,self.c,self.cov,e['signature'])
        p=prepare(self.a,self.c,self.cov,kind='signed_sow')
        self.assertEqual(p.result['status'],'prepared');self.assertEqual(p.result['total'],'30.00')
        self.assertNotIn('D12.uat_billing_predicate_ref',p.snapshot['policies']);billing.ensure_current(p)
        held=prepare(self.a,self.c,self.cov,kind='uat');self.assertIsNone(held.result['total'])
        self.assertIn('D12.uat_billing_predicate_ref: MISSING',held.result['findings'])
    def test_stage_uses_exact_pmo_handoff_not_uat_acceptance_or_release_guess(self):
        e=signed(self.a,self.c);stage_policy(self.a,self.c,self.cov,e['signature'])
        policy(self.a,self.c,'D12.stage_terms',[{'coverage_id':self.cov.pk,'stage':'uat','amount':'40.00','due_date':'2026-11-02'}])
        policy(self.a,self.c,'D12.uat_billing_predicate_ref',{'coverage_id':self.cov.pk,'stage':'uat','milestone_name':'Reached contractual UAT'})
        complete_milestone(self.a,self.c.pk,'Release',e['completion'].pk,rev(self.c));run_once();wrong=Handoff.objects.get(milestone__name='Release')
        self.assertEqual(prepare(self.a,self.c,self.cov,kind='uat',h=wrong).result['status'],'held')
        complete_milestone(self.a,self.c.pk,'Reached contractual UAT',e['completion'].pk,rev(self.c));run_once();h=Handoff.objects.get(milestone__name='Reached contractual UAT')
        p=prepare(self.a,self.c,self.cov,kind='uat',h=h);self.assertEqual(p.result['total'],'40.00');billing.ensure_current(p)
        self.assertEqual(p.handoff.milestone.completed_by,self.a)
    def test_stage_missing_amount_or_due_date_preserves_evidence_without_default_split(self):
        e=signed(self.a,self.c);stage_policy(self.a,self.c,self.cov,e['signature'])
        policy(self.a,self.c,'D12.stage_terms',[{'coverage_id':self.cov.pk,'stage':'signed_sow','amount':None,'due_date':None}])
        p=prepare(self.a,self.c,self.cov,kind='signed_sow');self.assertIsNone(p.result['total']);self.assertIsNone(p.result['due_date'])
        self.assertIn('Stage amount unknown',p.result['findings'])
    def test_policy_and_usage_screens_call_real_services_and_keep_holds_visible(self):
        self.client.force_login(self.a);url=f'/cases/{self.c.pk}/finance/billing/'
        e=evidence(self.a,self.c,'billing_usage',json.loads(FIXTURE.read_text(encoding='utf-8'))['csv'])
        self.assertEqual(self.client.post(url,{'action':'usage','coverage':self.cov.pk,'evidence':e.pk,'completeness':'unknown','revision':rev(self.c)}).status_code,302)
        u=BillingUsage.objects.get()
        self.assertEqual(self.client.post(url,{'action':'prepare','coverage':self.cov.pk,'kind':'usage','usage':u.pk,'revision':rev(self.c)}).status_code,302)
        response=self.client.get(url);self.assertContains(response,'D08.effective_price_rule_refs: MISSING');self.assertContains(response,'Unknown')
        f=json.loads(FIXTURE.read_text(encoding='utf-8'));e=evidence(self.a,self.c,'policy_decision','Synthetic UI decision')
        response=self.client.post(url,{'action':'policy','component':'D08.effective_price_rule_refs','content':json.dumps([dict(f['rule'],coverage_id=self.cov.pk)]),'evidence':e.pk,'effective_from':timezone.now().isoformat(),'revision':rev(self.c)})
        self.assertEqual(response.status_code,302)
    def test_current_agent_cites_oracle_and_has_no_approval_or_effect_tools(self):
        prices(self.a,self.c,self.cov);u=usage(self.a,self.c,self.cov);p=prepare(self.a,self.c,self.cov,u=u)
        run=investigate(self.a,self.c.pk,self.cov.pk,p.pk,rev(self.c));self.assertTrue(run.result['current'])
        self.assertTrue(any(x['kind']=='billing_oracle' for x in run.result['citations']))
        self.assertFalse(run.result['invoice_issued']);self.assertFalse(run.result['external_authenticity_verified'])
    def test_postgresql_append_only_guards_reject_direct_bypass(self):
        self.assertEqual(connection.vendor,'postgresql');u=usage(self.a,self.c,self.cov);p=prepare(self.a,self.c,self.cov,u=u)
        for table,pk,column in [('finance_billingcoverage',self.cov.pk,'reference'),('finance_billingusage',u.pk,'source_sha256'),('finance_billingpreparation',p.pk,'kind')]:
            with self.assertRaises(DatabaseError),transaction.atomic():
                with connection.cursor() as cursor:cursor.execute(f'UPDATE {table} SET {column}=%s WHERE id=%s',['tamper',pk])
        self.assertEqual(BillingCoverage.objects.get(pk=self.cov.pk).reference,self.cov.reference)

    def test_unknown_extraction_context_is_explicit_and_future_assertions_rejected(self):
        from datetime import timedelta
        f=json.loads(FIXTURE.read_text(encoding='utf-8'));e=evidence(self.a,self.c,'billing_usage',f['csv'])
        with self.assertRaises(ValidationError):billing.capture_usage(self.a,self.c.pk,self.cov.pk,e.pk,rev(self.c),{'provider_ref':'data-example','extracted_at':(timezone.now()+timedelta(days=1)).isoformat(),'completeness':'complete'})
        u=billing.capture_usage(self.a,self.c.pk,self.cov.pk,e.pk,rev(self.c))
        self.assertEqual(u.source_context,{'provider_ref':None,'extracted_at':None,'completeness':'unknown'})
    def test_expired_policy_holds_only_preparation_and_keeps_capture_available(self):
        from datetime import timedelta
        configs=prices(self.a,self.c,self.cov)
        from apps.policy.services import save_draft
        env=copy.deepcopy(configs[0].envelope);env['effective_from']=(timezone.now()-timedelta(days=3)).isoformat();env['effective_until']=(timezone.now()-timedelta(days=1)).isoformat()
        config=save_draft(self.a,self.c.pk,env);transition(self.a,config.pk,'validated');transition(self.a,config.pk,'active')
        u=usage(self.a,self.c,self.cov);p=prepare(self.a,self.c,self.cov,u=u)
        self.assertEqual(p.result['status'],'held');self.assertTrue(any('EXPIRED' in x for x in p.result['findings']))
    def test_invoice_preparer_grant_withdrawal_invalidates_pending_use(self):
        prices(self.a,self.c,self.cov);u=usage(self.a,self.c,self.cov);p=prepare(self.a,self.c,self.cov,u=u)
        Grant.objects.filter(user=self.a,case=self.c,action='finance.billing.prepare').update(active=False)
        with self.assertRaises(PermissionDenied):billing.ensure_current(p)
    def test_decimal_rounding_is_explicit_and_no_implicit_fx(self):
        from apps.finance.billing_math import price
        f=json.loads(FIXTURE.read_text(encoding='utf-8'));m=f['arithmetic']
        self.assertEqual(price('1','0.005',dict(m,tax_rate='0',rounding='half_up'))['net'],'0.01')
        self.assertEqual(price('1','0.005',dict(m,tax_rate='0',rounding='half_even'))['net'],'0.00')
        r=dict(f['rule'],coverage_id=self.cov.pk,currency='USD')
        with self.assertRaises(ValidationError):policy(self.a,self.c,'D08.effective_price_rule_refs',[r])

    def test_expected_period_inventory_never_turns_missing_usage_into_zero_or_billed(self):
        u=usage(self.a,self.c,self.cov)
        inventory=billing.coverage_inventory(self.cov)
        self.assertEqual(len(inventory),12);self.assertEqual(inventory[0]['status'],'usage_present_unknown')
        self.assertEqual(inventory[1]['status'],'missing_usage');self.assertEqual(inventory[1]['usage_batches'],[])
        with self.assertRaises(ValidationError):coverage(self.a,self.c,to_period='2099-01')

    def test_oracle_evidence_matching_but_incorrect_arithmetic_is_rejected(self):
        f=json.loads(FIXTURE.read_text(encoding='utf-8'));m=f['arithmetic'];m['oracles'][0]['total']='999.00'
        e=evidence(self.a,self.c,'billing_oracle',json.dumps(m['oracles']));m['oracle_evidence_id']=e.pk
        with self.assertRaisesMessage(ValidationError,'algorithm differs'):policy(self.a,self.c,'D08.tax_tier_rounding_rules',m)
    def test_completion_is_its_own_configured_handoff_and_precision_is_not_rounded_away(self):
        e=signed(self.a,self.c);stage_policy(self.a,self.c,self.cov,e['signature'])
        policy(self.a,self.c,'D12.stage_terms',[{'coverage_id':self.cov.pk,'stage':'completion','amount':'30.001','due_date':'2026-11-03'}])
        policy(self.a,self.c,'D12.completion_billing_predicate_ref',{'coverage_id':self.cov.pk,'stage':'completion','milestone_name':'Contract completion criterion'})
        complete_milestone(self.a,self.c.pk,'Contract completion criterion',e['completion'].pk,rev(self.c));run_once();h=Handoff.objects.get()
        p=prepare(self.a,self.c,self.cov,kind='completion',h=h)
        self.assertIn('Stage amount exceeds configured precision',p.result['findings']);self.assertIsNone(p.result['total'])
        policy(self.a,self.c,'D12.stage_terms',[{'coverage_id':self.cov.pk,'stage':'completion','amount':'30.00','due_date':'2026-11-03'}])
        self.assertEqual(prepare(self.a,self.c,self.cov,kind='completion',h=h).result['total'],'30.00')
    def test_newer_price_policy_requires_new_preparation_preserving_original(self):
        prices(self.a,self.c,self.cov);u=usage(self.a,self.c,self.cov);p=prepare(self.a,self.c,self.cov,u=u)
        f=json.loads(FIXTURE.read_text(encoding='utf-8'));r=dict(f['rule'],coverage_id=self.cov.pk,rate='5.00')
        policy(self.a,self.c,'D08.effective_price_rule_refs',[r])
        with self.assertRaises(ValidationError):billing.ensure_current(p)
        new=prepare(self.a,self.c,self.cov,u=u);self.assertEqual(new.result['total'],'64.50')
        p.refresh_from_db();self.assertEqual(p.result['total'],'32.25')

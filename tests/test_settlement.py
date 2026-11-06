import json,copy
from datetime import timedelta
from decimal import Decimal
from django.test import TestCase
from django.core.exceptions import ValidationError,PermissionDenied
from django.db import transaction,connection,DatabaseError
from django.utils import timezone
from apps.core.models import Case
from apps.identity.models import Grant
from apps.policy.services import active_component,transition
from apps.finance import invoices,cash,receivables,invoice_delivery
from apps.finance.models import Invoice,InvoiceIssue,InvoiceDelivery,InvoiceJob,InvoiceReview,CashReceipt,CashVerification,CashAllocation,CashReversal,ReceivableSnapshot
from apps.agents.receivables import investigate
from adapters.invoices import TimeoutAfterInvoiceAccept
from .helpers import rev
from .billing_helpers import evidence,policy,coverage,usage,prepare,prices,FIXTURE as USAGE_FIXTURE
from .settlement_helpers import fixture,draft,approve,issue,receipt,assign,allocate,FIXTURE

class SettlementTests(TestCase):
    def setUp(self):self.a,self.c,self.cov,self.p,self.e=fixture()
    def snap(self):return receivables.snapshot(self.a,self.c.pk,timezone.localdate(),rev(self.c))
    def test_generation_review_issuance_delivery_are_separate_real_facts(self):
        i=draft(self.a,self.c,self.p);self.assertEqual(InvoiceIssue.objects.count(),0)
        with self.assertRaises(ValidationError):invoices.reserve(self.a,self.c.pk,i.pk,'issue','Finance',rev(self.c))
        approve(self.a,self.c,i,self.e);j=invoices.reserve(self.a,self.c.pk,i.pk,'issue','Finance',rev(self.c));self.assertEqual(InvoiceIssue.objects.count(),0)
        invoice_delivery.run_once();self.assertEqual(InvoiceIssue.objects.count(),1);self.assertEqual(InvoiceDelivery.objects.count(),0)
        invoices.reserve(self.a,self.c.pk,i.pk,'deliver','Finance',rev(self.c));invoice_delivery.run_once()
        delivery=InvoiceDelivery.objects.get();self.assertEqual(delivery.payload['amount'],'32.25');self.assertNotIn('preparation_key',delivery.payload)
        self.assertNotIn('rule',delivery.payload['lines'][0]);self.assertEqual(self.snap().result['groups'][0]['receivable'],'32.25000000')
    def test_missing_issuance_policy_does_not_prevent_draft_or_reported_cash(self):
        config=active_component('D08.adapter_contract_ref',self.c);transition(self.a,config.pk,'revoked')
        i=draft(self.a,self.c,self.p);approve(self.a,self.c,i,self.e)
        with self.assertRaises(ValidationError):invoices.reserve(self.a,self.c.pk,i.pk,'issue','Finance',rev(self.c))
        r,_=receipt(self.a,self.c,verify=False);self.assertEqual(CashReceipt.objects.count(),1)
    def test_unknown_after_accept_reconciles_before_later_grant_revocation(self):
        i=draft(self.a,self.c,self.p);approve(self.a,self.c,i,self.e);j=invoices.reserve(self.a,self.c.pk,i.pk,'issue','Finance',rev(self.c))
        invoice_delivery.run_once(TimeoutAfterInvoiceAccept());j.refresh_from_db();self.assertEqual(j.status,'unknown')
        self.assertEqual(InvoiceIssue.objects.count(),1)
        Grant.objects.filter(case=self.c,user=self.a,action='finance.invoice.issue').update(active=False)
        invoice_delivery.run_once();j.refresh_from_db();self.assertEqual(j.status,'confirmed');self.assertEqual(InvoiceIssue.objects.count(),1)
    def test_newer_invoice_revision_blocks_old_reservation_and_single_canonical_debt(self):
        i=draft(self.a,self.c,self.p);approve(self.a,self.c,i,self.e);old=invoices.reserve(self.a,self.c.pk,i.pk,'issue','Finance',rev(self.c))
        newer=draft(self.a,self.c,self.p);self.assertEqual(newer.version,2);approve(self.a,self.c,newer,self.e);invoices.reserve(self.a,self.c.pk,newer.pk,'issue','Finance',rev(self.c))
        invoice_delivery.run_once();old.refresh_from_db();self.assertEqual(old.status,'held');invoice_delivery.run_once()
        self.assertEqual(InvoiceIssue.objects.count(),1);self.assertEqual(InvoiceIssue.objects.get().invoice_id,newer.pk)
        with self.assertRaises(ValidationError):draft(self.a,self.c,self.p)
    def test_returned_review_holds_worker_then_explicit_intent_replacement_resumes(self):
        i=draft(self.a,self.c,self.p);approve(self.a,self.c,i,self.e);j=invoices.reserve(self.a,self.c.pk,i.pk,'issue','Finance',rev(self.c))
        invoices.review(self.a,self.c.pk,i.pk,'Finance','return',self.e['invoice_review'].pk,'Return exact document',rev(self.c))
        invoice_delivery.run_once();j.refresh_from_db();self.assertEqual(j.status,'held')
        approve(self.a,self.c,i,self.e)
        invoice_delivery.operate(self.a,self.c.pk,j.pk,'replace_intent','Fresh current review reservation',rev(self.c))
        self.assertEqual(InvoiceJob.objects.count(),2);invoice_delivery.run_once();self.assertEqual(InvoiceIssue.objects.count(),1)
    def test_cancel_is_sticky_and_does_not_cancel_a_proven_obligation(self):
        i=draft(self.a,self.c,self.p);approve(self.a,self.c,i,self.e);j=invoices.reserve(self.a,self.c.pk,i.pk,'issue','Finance',rev(self.c))
        invoice_delivery.operate(self.a,self.c.pk,j.pk,'cancel','Explicit cancellation',rev(self.c));self.assertFalse(invoice_delivery.run_once());self.assertEqual(InvoiceIssue.objects.count(),0)
        with self.assertRaises(ValidationError):invoice_delivery.operate(self.a,self.c.pk,j.pk,'retry','Forbidden retry',rev(self.c))
    def test_recipient_revocation_holds_delivery_but_never_removes_issued_debt(self):
        i=draft(self.a,self.c,self.p);issue(self.a,self.c,i,self.e);j=invoices.reserve(self.a,self.c.pk,i.pk,'deliver','Finance',rev(self.c))
        Grant.objects.filter(case=self.c,user=self.a,action='finance.invoice.receive').update(active=False)
        invoice_delivery.run_once();j.refresh_from_db();self.assertEqual(j.status,'held');self.assertEqual(InvoiceDelivery.objects.count(),0)
        self.assertEqual(self.snap().result['groups'][0]['receivable'],'32.25000000')
    def test_reported_unknown_and_unverified_cash_never_settle_debt(self):
        iss=issue(self.a,self.c,draft(self.a,self.c,self.p),self.e)
        r,_=receipt(self.a,self.c,verify=False);unknown,_=receipt(self.a,self.c,None,'unknown',False)
        proof=evidence(self.a,self.c,'cash_verification',json.dumps(unknown.payload))
        with self.assertRaises(ValidationError):cash.verify(self.a,self.c.pk,unknown.pk,'Finance',proof.pk,rev(self.c))
        s=self.snap();self.assertEqual(len(s.result['reported_unverified']),2);self.assertEqual(s.result['groups'][0]['verified_cash'],'0')
    def test_cash_before_invoice_unmatched_assignment_and_partial_allocation(self):
        r,l=receipt(self.a,self.c);self.assertEqual(self.snap().result['unmatched_cash'][0]['amount'],'50.00000000')
        assign(self.a,self.c,r,self.cov,self.e);iss=issue(self.a,self.c,draft(self.a,self.c,self.p),self.e)
        a=allocate(self.a,self.c,l,iss,'20.00',self.e);self.assertEqual(allocate(self.a,self.c,l,iss,'20.00',self.e).pk,a.pk)
        s=self.snap();g=s.result['groups'][0];self.assertEqual(g['receivable'],'12.25000000');self.assertEqual(g['verified_cash'],'50.00000000');self.assertEqual(g['unallocated_cash'],'30.00000000')
        self.assertFalse(s.result['deployment_authorized']);self.assertFalse(s.result['ledger_posted'])
    def test_multiple_receipts_settle_one_invoice_and_excess_stays_unallocated(self):
        iss=issue(self.a,self.c,draft(self.a,self.c,self.p),self.e)
        r,l=receipt(self.a,self.c,'10.00');assign(self.a,self.c,r,self.cov,self.e);allocate(self.a,self.c,l,iss,'10.00',self.e)
        r2,l2=receipt(self.a,self.c,'50.00','cash-2');assign(self.a,self.c,r2,self.cov,self.e);allocate(self.a,self.c,l2,iss,'22.25',self.e)
        g=self.snap().result['groups'][0];self.assertEqual(Decimal(g['receivable']),0);self.assertEqual(Decimal(g['verified_cash']),60);self.assertEqual(Decimal(g['unallocated_cash']),Decimal('27.75'))
    def test_one_receipt_can_settle_multiple_invoices_without_creating_cash(self):
        first=issue(self.a,self.c,draft(self.a,self.c,self.p),self.e)
        body=json.loads(USAGE_FIXTURE.read_text(encoding='utf-8'))['csv'].replace('tx-example-1','tx-example-2')
        u=usage(self.a,self.c,self.cov,body);p=prepare(self.a,self.c,self.cov,u=u);second=issue(self.a,self.c,draft(self.a,self.c,p,'INV-SECOND'),self.e)
        r,l=receipt(self.a,self.c);assign(self.a,self.c,r,self.cov,self.e);allocate(self.a,self.c,l,first,'32.25',self.e);allocate(self.a,self.c,l,second,'17.75',self.e,'match-2')
        g=self.snap().result['groups'][0];self.assertEqual(Decimal(g['receivable']),Decimal('14.50'));self.assertEqual(Decimal(g['verified_cash']),50);self.assertEqual(Decimal(g['unallocated_cash']),0)
    def test_both_capacities_precision_and_operation_identity_are_enforced(self):
        iss=issue(self.a,self.c,draft(self.a,self.c,self.p),self.e);r,l=receipt(self.a,self.c,'20.00');assign(self.a,self.c,r,self.cov,self.e)
        for amount in ['20.01','32.26','0','-1','NaN','0.001']:
            with self.assertRaises(ValidationError):allocate(self.a,self.c,l,iss,amount,self.e)
        allocate(self.a,self.c,l,iss,'10',self.e)
        with self.assertRaises(ValidationError):allocate(self.a,self.c,l,iss,'11',self.e)
    def test_duplicate_receipt_identity_is_idempotent_changed_amount_is_investigation(self):
        r,l=receipt(self.a,self.c);e=evidence(self.a,self.c,'cash_report',json.dumps(r.payload));self.assertEqual(cash.report(self.a,self.c.pk,e.pk,rev(self.c)).pk,r.pk)
        value=dict(r.payload,amount='51');e=evidence(self.a,self.c,'cash_report',json.dumps(value))
        with self.assertRaises(ValidationError):cash.report(self.a,self.c.pk,e.pk,rev(self.c))
        self.assertEqual(CashVerification.objects.count(),1)
    def test_full_lot_reversal_reopens_debt_and_subtracts_cash_exactly_once(self):
        iss=issue(self.a,self.c,draft(self.a,self.c,self.p),self.e);r,l=receipt(self.a,self.c);assign(self.a,self.c,r,self.cov,self.e);a=allocate(self.a,self.c,l,iss,'32.25',self.e)
        cash.reverse(self.a,self.c.pk,'lot',l.pk,'Finance',self.e['cash_correction'].pk,'Full evidenced reversal',rev(self.c))
        self.assertEqual(CashReversal.objects.count(),2);g=self.snap().result['groups'][0]
        self.assertEqual(Decimal(g['receivable']),Decimal('32.25'));self.assertEqual(Decimal(g['verified_cash']),0);self.assertEqual(Decimal(g['unallocated_cash']),0)
        with self.assertRaises(ValidationError):cash.reverse(self.a,self.c.pk,'lot',l.pk,'Finance',self.e['cash_correction'].pk,'Second reversal refused',rev(self.c))
        with self.assertRaises(ValidationError):allocate(self.a,self.c,l,iss,'1',self.e,'after-reversal')
    def test_allocation_reversal_preserves_cash_and_full_reversal_later_does_not_double_reverse(self):
        iss=issue(self.a,self.c,draft(self.a,self.c,self.p),self.e);r,l=receipt(self.a,self.c);assign(self.a,self.c,r,self.cov,self.e);a=allocate(self.a,self.c,l,iss,'10',self.e)
        cash.reverse(self.a,self.c.pk,'allocation',a.pk,'Finance',self.e['cash_correction'].pk,'Unmatch exact allocation',rev(self.c))
        self.assertEqual(cash.cash_remaining(l),50);self.assertEqual(cash.open_amount(iss),Decimal('32.25'))
        cash.reverse(self.a,self.c.pk,'lot',l.pk,'Finance',self.e['cash_correction'].pk,'Full lot reversal',rev(self.c));self.assertEqual(CashReversal.objects.count(),2)
    def test_reassignment_reverses_existing_allocations_atomically_before_contract_move(self):
        iss=issue(self.a,self.c,draft(self.a,self.c,self.p),self.e);r,l=receipt(self.a,self.c);assign(self.a,self.c,r,self.cov,self.e);allocate(self.a,self.c,l,iss,'20',self.e)
        other=coverage(self.a,self.c,reference='other',contract='other-contract');assign(self.a,self.c,r,other,self.e)
        self.assertEqual(cash.open_amount(iss),Decimal('32.25'));self.assertEqual(cash.cash_remaining(l),50)
        with self.assertRaises(ValidationError):allocate(self.a,self.c,l,iss,'1',self.e,'wrong-contract')
    def test_missing_correction_policy_does_not_block_receipt_capture_or_independent_snapshot(self):
        iss=issue(self.a,self.c,draft(self.a,self.c,self.p),self.e);r,l=receipt(self.a,self.c);assign(self.a,self.c,r,self.cov,self.e);allocate(self.a,self.c,l,iss,'10',self.e)
        transition(self.a,active_component('D14.legal_document_requirements',self.c).pk,'revoked')
        with self.assertRaises(ValidationError):cash.reverse(self.a,self.c.pk,'lot',l.pk,'Finance',self.e['cash_correction'].pk,'Missing legal policy',rev(self.c))
        self.assertEqual(CashReversal.objects.count(),0);receipt(self.a,self.c,ref='independent',verify=False);self.assertEqual(len(self.snap().result['reported_unverified']),1)
    def test_configured_separation_and_admin_flags_never_manufacture_human_authority(self):
        f=json.loads(FIXTURE.read_text(encoding='utf-8'));policy(self.a,self.c,'D14.recorder_authority_ref',dict(f['recorder'],allow_reporter_verify=False))
        r,_=receipt(self.a,self.c,verify=False);proof=evidence(self.a,self.c,'cash_verification',json.dumps(r.payload))
        with self.assertRaises(PermissionDenied):cash.verify(self.a,self.c.pk,r.pk,'Finance',proof.pk,rev(self.c))
        i=draft(self.a,self.c,self.p);self.a.is_superuser=True;self.a.is_staff=True;self.a.save()
        transition(self.a,active_component('D05.role_principal_assignments',self.c).pk,'revoked')
        with self.assertRaises(ValidationError):approve(self.a,self.c,i,self.e)
    def test_policy_semantics_reject_unknown_effects_and_bad_reversal_shapes(self):
        f=json.loads(FIXTURE.read_text(encoding='utf-8'))
        with self.assertRaises(ValidationError):policy(self.a,self.c,'D08.duplicate_correction_rules',dict(f['identity'],on_unknown='blind_retry'))
        with self.assertRaises(ValidationError):policy(self.a,self.c,'D14.adjustment_correction_rule_refs',[dict(f['reversals'][0],implementation='partial_refund')])
        with self.assertRaises(ValidationError):policy(self.a,self.c,'D14.legal_document_requirements',[f['legal'][0],f['legal'][0]])
    def test_receivable_as_of_and_scope_are_not_caller_subsets_or_invented_zeros(self):
        issue(self.a,self.c,draft(self.a,self.c,self.p),self.e)
        with self.assertRaises(ValidationError):receivables.snapshot(self.a,self.c.pk,timezone.localdate()-timedelta(days=1),rev(self.c))
        transition(self.a,active_component('D14.allocation_rule_ref',self.c).pk,'revoked')
        s=self.snap();self.assertIsNone(s.result['groups'][0]['overdue']);self.assertEqual(Decimal(s.result['groups'][0]['receivable']),Decimal('32.25'))
        self.assertIn('UNKNOWN',s.result['payment_assessment'])
    def test_bounded_agent_cites_cash_and_review_sources_without_execution_tools(self):
        issue(self.a,self.c,draft(self.a,self.c,self.p),self.e);r,l=receipt(self.a,self.c);s=self.snap()
        log=investigate(self.a,self.c.pk,s.pk,rev(self.c));self.assertTrue(log.result['current']);self.assertFalse(log.result['allocation_executed'])
        self.assertTrue(any(x['kind']=='cash_verification' for x in log.result['citations']))
        receipt(self.a,self.c,ref='new-pending',verify=False);log=investigate(self.a,self.c.pk,s.pk,rev(self.c));self.assertFalse(log.result['current'])
    def test_staff_forms_and_recipient_inbox_use_real_services_and_scoped_projection(self):
        self.client.force_login(self.a);url=f'/cases/{self.c.pk}/finance/settlement/'
        response=self.client.post(url,{'action':'draft','preparation':self.p.pk,'reference':'UI-INVOICE','due_date':timezone.localdate().isoformat(),'revision':rev(self.c)})
        self.assertEqual(response.status_code,302);i=Invoice.objects.get();issue(self.a,self.c,i,self.e)
        invoices.reserve(self.a,self.c.pk,i.pk,'deliver','Finance',rev(self.c));invoice_delivery.run_once()
        self.assertContains(self.client.get('/finance/invoices/inbox/'),'UI-INVOICE');self.assertNotContains(self.client.get('/finance/invoices/inbox/'),'preparation_key')
        self.assertContains(self.client.get(url),'Issued obligation')
        Grant.objects.filter(case=self.c,user=self.a,action='finance.invoice.receive').update(active=False)
        self.assertNotContains(self.client.get('/finance/invoices/inbox/'),'UI-INVOICE')
    def test_cross_case_and_stale_revision_are_denied(self):
        with self.assertRaises(ValidationError):invoices.draft(self.a,self.c.pk,self.p.pk,'STALE',None,0)
        private=Case.objects.create(tenant=self.c.tenant,title='Private',kind='project',synthetic=True)
        self.client.force_login(self.a);self.assertEqual(self.client.get(f'/cases/{private.pk}/finance/settlement/').status_code,404)
        with self.assertRaises(ValidationError):cash.verify(self.a,self.c.pk,999999,'Finance',self.e['cash_correction'].pk,rev(self.c))
    def test_postgresql_guards_protect_history_and_reserved_intent(self):
        self.assertEqual(connection.vendor,'postgresql');i=draft(self.a,self.c,self.p);approve(self.a,self.c,i,self.e);j=invoices.reserve(self.a,self.c.pk,i.pk,'issue','Finance',rev(self.c))
        for sql in ['UPDATE finance_invoice SET amount=1 WHERE id=%s',"UPDATE finance_invoicejob SET intent='{}' WHERE id=%s"]:
            with self.assertRaises(DatabaseError),transaction.atomic():
                with connection.cursor() as cursor:cursor.execute(sql,[i.pk if 'SET amount' in sql else j.pk])

    def test_configured_due_terms_and_usage_completeness_hold_only_issuance(self):
        i=invoices.draft(self.a,self.c.pk,self.p.pk,'NO-DUE',None,rev(self.c));approve(self.a,self.c,i,self.e)
        with self.assertRaisesMessage(ValidationError,'due terms'):invoices.reserve(self.a,self.c.pk,i.pk,'issue','Finance',rev(self.c))
        f=json.loads(FIXTURE.read_text(encoding='utf-8'));policy(self.a,self.c,'D08.adapter_contract_ref',dict(f['adapter'],recipient_id=self.a.pk,require_due_date=False,allow_partial_usage=False))
        with self.assertRaisesMessage(ValidationError,'fresh exact-packet review'):
            invoices.reserve(self.a,self.c.pk,i.pk,'issue','Finance',rev(self.c))
        approve(self.a,self.c,i,self.e)
        with self.assertRaisesMessage(ValidationError,'incomplete usage'):invoices.reserve(self.a,self.c.pk,i.pk,'issue','Finance',rev(self.c))
        self.assertEqual(Invoice.objects.count(),1);self.assertEqual(InvoiceIssue.objects.count(),0)
    def test_source_policy_revocation_holds_verification_without_erasing_historical_cash(self):
        r,l=receipt(self.a,self.c);transition(self.a,active_component('D14.receipt_verification_source_ref',self.c).pk,'revoked')
        newer,_=receipt(self.a,self.c,ref='pending-source',verify=False);proof=evidence(self.a,self.c,'cash_verification',json.dumps(newer.payload))
        with self.assertRaises(ValidationError):cash.verify(self.a,self.c.pk,newer.pk,'Finance',proof.pk,rev(self.c))
        s=self.snap();self.assertEqual(Decimal(s.result['unmatched_cash'][0]['amount']),50);self.assertEqual(len(s.result['reported_unverified']),1)
    def test_mixed_currency_cannot_allocate_and_snapshot_keeps_dimensions_separate(self):
        iss=issue(self.a,self.c,draft(self.a,self.c,self.p),self.e);f=json.loads(FIXTURE.read_text(encoding='utf-8'))
        policy(self.a,self.c,'D14.receipt_verification_source_ref',dict(f['source'],currency='USD'))
        value={'source':'synthetic-bank','transaction_ref':'usd-cash','customer':self.cov.customer,'amount':'50.00','currency':'USD','amount_basis':'gross_including_tax','received_at':timezone.now().isoformat()}
        report=evidence(self.a,self.c,'cash_report',json.dumps(value));r=cash.report(self.a,self.c.pk,report.pk,rev(self.c));proof=evidence(self.a,self.c,'cash_verification',json.dumps(value));l=cash.verify(self.a,self.c.pk,r.pk,'Finance',proof.pk,rev(self.c));assign(self.a,self.c,r,self.cov,self.e)
        with self.assertRaisesMessage(ValidationError,'currency/basis differ'):allocate(self.a,self.c,l,iss,'1',self.e)
        self.assertEqual({g['currency'] for g in self.snap().result['groups']},{'USD','NGN'})
    def test_configured_independent_provenance_locator_is_required_but_not_bank_authenticity(self):
        from apps.core.services import add_evidence
        f=json.loads(FIXTURE.read_text(encoding='utf-8'));policy(self.a,self.c,'D14.receipt_verification_source_ref',dict(f['source'],require_independent_evidence=True))
        r,_=receipt(self.a,self.c,verify=False);proof=evidence(self.a,self.c,'cash_verification',json.dumps(r.payload))
        with self.assertRaises(ValidationError):cash.verify(self.a,self.c.pk,r.pk,'Finance',proof.pk,rev(self.c))
        proof=add_evidence(self.a,self.c.pk,'cash_verification',json.dumps(r.payload),'synthetic:independent-statement-locator')
        self.assertEqual(cash.verify(self.a,self.c.pk,r.pk,'Finance',proof.pk,rev(self.c)).amount,50)
    def test_reassignment_without_correction_policy_rolls_back_all_allocations_and_ownership(self):
        iss=issue(self.a,self.c,draft(self.a,self.c,self.p),self.e);r,l=receipt(self.a,self.c);a=assign(self.a,self.c,r,self.cov,self.e);allocate(self.a,self.c,l,iss,'20',self.e)
        other=coverage(self.a,self.c,reference='other',contract='other-contract');transition(self.a,active_component('D14.legal_document_requirements',self.c).pk,'revoked')
        with self.assertRaises(ValidationError):assign(self.a,self.c,r,other,self.e)
        self.assertEqual(cash.assigned(r).pk,a.pk);self.assertEqual(CashReversal.objects.count(),0);self.assertEqual(cash.open_amount(iss),Decimal('12.25'))
    def test_unknown_without_acceptance_has_bounded_reconciliation_and_no_blind_operator_retry(self):
        from adapters.invoices import InternalInvoiceAdapter
        class NoAcceptance(InternalInvoiceAdapter):
            def deliver(self,pk,fence):raise TimeoutError('Synthetic before acceptance uncertainty')
        i=draft(self.a,self.c,self.p);approve(self.a,self.c,i,self.e);j=invoices.reserve(self.a,self.c.pk,i.pk,'issue','Finance',rev(self.c))
        invoice_delivery.run_once(NoAcceptance());j.refresh_from_db();self.assertEqual(j.status,'unknown')
        with self.assertRaises(ValidationError):invoice_delivery.operate(self.a,self.c.pk,j.pk,'cancel','Uncertain cancellation forbidden',rev(self.c))
        for _ in range(3):invoice_delivery.run_once(NoAcceptance())
        j.refresh_from_db();self.assertEqual(j.status,'held');self.assertEqual(InvoiceIssue.objects.count(),0)
        self.assertEqual(self.snap().result['unbilled_drafts'][0]['invoice'],i.pk)
    def test_wide_exact_decimal_statement_is_not_rounded_by_default_decimal_context(self):
        from adapters.cash_statements import parse
        value={'source':'synthetic-bank','transaction_ref':'wide','customer':self.cov.customer,'amount':'12345678901234567890123.12345678','currency':'NGN','amount_basis':'gross_including_tax','received_at':timezone.now().isoformat()}
        self.assertEqual(parse(json.dumps(value))['amount'],value['amount'])
    def test_agent_match_suggestions_are_individual_alternatives_and_never_execute(self):
        iss=issue(self.a,self.c,draft(self.a,self.c,self.p),self.e);r,l=receipt(self.a,self.c);assign(self.a,self.c,r,self.cov,self.e);s=self.snap()
        run=investigate(self.a,self.c.pk,s.pk,rev(self.c));suggestion=run.result['matching_alternatives'][0]
        self.assertTrue(suggestion['human_selection_required']);self.assertTrue(suggestion['alternatives_not_combined']);self.assertEqual(Decimal(suggestion['maximum_individual_amount']),Decimal('32.25'));self.assertEqual(CashAllocation.objects.count(),0)

    def test_full_cash_staff_path_calls_real_services_including_full_reversal(self):
        self.client.force_login(self.a);url=f'/cases/{self.c.pk}/finance/settlement/'
        def post(action,**data):
            result=self.client.post(url,dict(action=action,revision=rev(self.c),**data));self.assertEqual(result.status_code,302,result.content[:500]);return result
        i=draft(self.a,self.c,self.p)
        post('review',invoice=i.pk,role='Finance',verdict='approve',evidence=self.e['invoice_review'].pk,reason='UI exact configured review')
        post('reserve',invoice=i.pk,kind='issue',role='Finance');invoice_delivery.run_once();iss=InvoiceIssue.objects.get()
        value={'source':'synthetic-bank','transaction_ref':'ui-cash','customer':self.cov.customer,'amount':'50','currency':'NGN','amount_basis':'gross_including_tax','received_at':timezone.now().isoformat()}
        e=evidence(self.a,self.c,'cash_report',json.dumps(value));proof=evidence(self.a,self.c,'cash_verification',json.dumps(value))
        post('report',evidence=e.pk);r=CashReceipt.objects.get();post('verify',receipt=r.pk,role='Finance',evidence=proof.pk);l=CashVerification.objects.get()
        post('assign',receipt=r.pk,coverage=self.cov.pk,role='Finance',evidence=self.e['cash_correction'].pk,reason='UI contract assignment')
        post('allocate',lot=l.pk,issue=iss.pk,amount='20.00',operation_key='ui-match',role='Finance',evidence=self.e['cash_allocation'].pk)
        post('snapshot',as_of=timezone.localdate().isoformat());s=ReceivableSnapshot.objects.get();self.assertEqual(Decimal(s.result['groups'][0]['receivable']),Decimal('12.25'))
        self.assertContains(self.client.get(url),'Current captured records');post('investigate',snapshot=s.pk)
        post('reverse',target='lot',lot=l.pk,role='Finance',evidence=self.e['cash_correction'].pk,reason='UI evidenced full reversal')
        self.assertEqual(cash.open_amount(iss),Decimal('32.25'));self.assertContains(self.client.get(url),'Historical snapshot')
    def test_invoice_policy_draft_ui_uses_versioned_semantic_lifecycle(self):
        self.client.force_login(self.a);url=f'/cases/{self.c.pk}/finance/settlement/';f=json.loads(FIXTURE.read_text(encoding='utf-8'));e=evidence(self.a,self.c,'policy_decision','UI synthetic draft, not operational approval')
        response=self.client.post(url,{'action':'policy','component':'D14.allocation_rule_ref','content':json.dumps(f['matching']),'evidence':e.pk,'effective_from':timezone.now().isoformat(),'revision':rev(self.c)})
        self.assertEqual(response.status_code,302)
        from apps.policy.models import Configuration
        cfg=Configuration.objects.filter(case=self.c,component='D14.allocation_rule_ref').order_by('-pk').first()
        self.assertEqual(cfg.states.order_by('-pk').first().state,'draft');transition(self.a,cfg.pk,'validated');transition(self.a,cfg.pk,'active')

    def test_transaction_identity_cannot_create_duplicate_cash_in_another_case(self):
        from apps.core.services import add_evidence
        r,l=receipt(self.a,self.c);other=Case.objects.create(tenant=self.c.tenant,title='Other engagement',kind='project',synthetic=True)
        for action in ['evidence.add','finance.cash.record']:Grant.objects.create(case=other,user=self.a,action=action)
        e=add_evidence(self.a,other.pk,'cash_report',json.dumps(r.payload),'synthetic:other-case')
        with self.assertRaisesMessage(ValidationError,'already registered in this tenant'):cash.report(self.a,other.pk,e.pk,rev(other))
        self.assertEqual(CashReceipt.objects.count(),1);self.assertEqual(CashVerification.objects.count(),1)
    def test_cash_sql_history_guards_cover_amounts_and_source_identity(self):
        i=draft(self.a,self.c,self.p);iss=issue(self.a,self.c,i,self.e);r,l=receipt(self.a,self.c);assign(self.a,self.c,r,self.cov,self.e);a=allocate(self.a,self.c,l,iss,'10',self.e)
        commands=[('UPDATE finance_cashreceipt SET tenant=%s WHERE id=%s',['other-tenant',r.pk]),('UPDATE finance_cashverification SET amount=%s WHERE id=%s',[1,l.pk]),('UPDATE finance_cashallocation SET amount=%s WHERE id=%s',[20,a.pk])]
        for sql,args in commands:
            with self.assertRaises(DatabaseError),transaction.atomic():
                with connection.cursor() as cursor:cursor.execute(sql,args)

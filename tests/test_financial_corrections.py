from django.test import TransactionTestCase
from decimal import Decimal
from django.test import TestCase
from django.core.exceptions import ValidationError,PermissionDenied
from django.db import transaction,DatabaseError,connection
import copy,json
from django.utils import timezone
from apps.finance import cash,corrections,cash_successors,receivables,invoice_delivery,financial_reviews
from apps.finance.models import InvoiceCorrectionAcceptance,CashSuccessorAcceptance,CashVerification,CashReversal
from .helpers import rev
from .settlement_helpers import receipt,assign,allocate
from .correction_helpers import fixture,note,apply,successor,review,FIXTURE
from .billing_helpers import policy,evidence
from apps.policy.services import active_component,reference_values,transition
from apps.finance.models import InvoiceIssue,InvoiceJob,InvoiceCorrection,InvoiceCorrectionDelivery,CashReceipt,CashAllocation,FinancialCorrectionReview
from apps.identity.models import Grant
from adapters.invoices import TimeoutAfterInvoiceAccept
from apps.agents.financial_corrections import investigate

class FinancialCorrectionTests(TransactionTestCase):
    def setUp(self):self.a,self.c,self.cov,self.iss,self.e=fixture(identity=self._testMethodName in {'test_pending_and_unknown_note_never_erase_proven_debt','test_timeout_after_applied_note_reconciles_before_revoked_executor'})
    def test_credit_debit_void_adjust_existing_canonical_obligation(self):
        for kind,amount,expected,ref in [('credit','5.00','27.25','CR-1'),('debit','3.00','30.25','DB-1'),('void',None,'0.00','VD-1')]:
            n=note(self.a,self.c,self.iss,self.e,kind,amount,ref);j=apply(self.a,self.c,n,self.e);j.refresh_from_db();self.assertEqual(j.status,'confirmed',j.error)
            self.assertEqual(corrections.adjusted_face(self.iss),Decimal(expected));self.assertEqual(cash.open_amount(self.iss),Decimal(expected))
        self.assertEqual(InvoiceCorrectionAcceptance.objects.count(),3)
        self.assertEqual(self.iss.invoice.amount,Decimal('32.25'))
    def test_credit_reverses_live_allocations_without_reducing_verified_cash(self):
        r,l=receipt(self.a,self.c);assign(self.a,self.c,r,self.cov,self.e);allocate(self.a,self.c,l,self.iss,'32.25',self.e)
        n=note(self.a,self.c,self.iss,self.e,amount='5.00');job=apply(self.a,self.c,n,self.e);job.refresh_from_db();self.assertEqual(job.status,'confirmed',job.error)
        self.assertEqual(cash.open_amount(self.iss),Decimal('27.25'));self.assertEqual(cash.cash_remaining(l),50);self.assertEqual(CashReversal.objects.count(),1)
    def test_successor_after_full_reversal_counts_only_new_verified_lot(self):
        r,l=receipt(self.a,self.c);assign(self.a,self.c,r,self.cov,self.e);allocate(self.a,self.c,l,self.iss,'20',self.e)
        s=successor(self.a,self.c,l,self.e)
        with self.assertRaises(ValidationError):review(self.a,self.c,s,self.e,'cash')
        cash.reverse(self.a,self.c.pk,'lot',l.pk,'Finance',self.e['cash_correction'].pk,'Full original lot reversal',rev(self.c))
        review(self.a,self.c,s,self.e,'cash');a=cash_successors.apply(self.a,self.c.pk,s.pk,'Finance',rev(self.c))
        self.assertEqual(a.lot.amount,40);self.assertEqual(CashVerification.objects.count(),2);self.assertEqual(cash.cash_remaining(l),0)
        snap=receivables.snapshot(self.a,self.c.pk,timezone.localdate(),rev(self.c));self.assertEqual(Decimal(snap.result['groups'][0]['verified_cash']),40)
        self.assertEqual(cash_successors.apply(self.a,self.c.pk,s.pk,'Finance',rev(self.c)).pk,a.pk)

    def test_note_capture_survives_missing_policy_but_effect_is_held(self):
        transition(self.a,active_component('D14.adjustment_correction_rule_refs',self.c).pk,'revoked')
        n=note(self.a,self.c,self.iss,self.e)
        with self.assertRaises(ValidationError):review(self.a,self.c,n,self.e)
        self.assertEqual(InvoiceCorrection.objects.count(),1);self.assertEqual(corrections.adjusted_face(self.iss),Decimal('32.25'))
        log=investigate(self.a,self.c.pk,'invoice',n.pk,rev(self.c));self.assertTrue(log.result['findings']);self.assertFalse(log.result['correction_executed'])
    def test_pending_and_unknown_note_never_erase_proven_debt(self):
        from adapters.invoices import InternalInvoiceAdapter
        class BeforeAcceptance(InternalInvoiceAdapter):
            def deliver(self,pk,fence):raise TimeoutError('Synthetic correction outcome not accepted')
        n=note(self.a,self.c,self.iss,self.e);review(self.a,self.c,n,self.e);j=corrections.reserve(self.a,self.c.pk,n.pk,'adjust','Finance',rev(self.c))
        invoice_delivery.run_once(BeforeAcceptance());j.refresh_from_db();self.assertEqual(j.status,'unknown')
        s=receivables.snapshot(self.a,self.c.pk,timezone.localdate(),rev(self.c));self.assertEqual(Decimal(s.result['groups'][0]['receivable']),Decimal('32.25'));self.assertEqual(len(s.result['uncertain_corrections']),1)
        with self.assertRaises(ValidationError):invoice_delivery.operate(self.a,self.c.pk,j.pk,'cancel','Cannot assume no effect',rev(self.c))
    def test_timeout_after_applied_note_reconciles_before_revoked_executor(self):
        n=note(self.a,self.c,self.iss,self.e);review(self.a,self.c,n,self.e);j=corrections.reserve(self.a,self.c.pk,n.pk,'adjust','Finance',rev(self.c))
        invoice_delivery.run_once(TimeoutAfterInvoiceAccept());j.refresh_from_db();self.assertEqual(j.status,'unknown');self.assertEqual(corrections.adjusted_face(self.iss),Decimal('27.25'))
        Grant.objects.filter(case=self.c,user=self.a,action='finance.invoice.correct').update(active=False)
        invoice_delivery.run_once();j.refresh_from_db();self.assertEqual(j.status,'confirmed');self.assertEqual(InvoiceCorrectionAcceptance.objects.count(),1)
    def test_only_one_unresolved_note_can_reserve_against_an_obligation(self):
        n=note(self.a,self.c,self.iss,self.e,reference='NOTE-A');review(self.a,self.c,n,self.e);corrections.reserve(self.a,self.c.pk,n.pk,'adjust','Finance',rev(self.c))
        other=note(self.a,self.c,self.iss,self.e,reference='NOTE-B');review(self.a,self.c,other,self.e)
        with self.assertRaises(ValidationError):corrections.reserve(self.a,self.c.pk,other.pk,'adjust','Finance',rev(self.c))
        r,l=receipt(self.a,self.c);assign(self.a,self.c,r,self.cov,self.e)
        with self.assertRaisesMessage(ValidationError,'reserved or uncertain'):allocate(self.a,self.c,l,self.iss,'1',self.e)
    def test_cash_change_before_note_reservation_stales_exact_review(self):
        n=note(self.a,self.c,self.iss,self.e);review(self.a,self.c,n,self.e)
        r,l=receipt(self.a,self.c);assign(self.a,self.c,r,self.cov,self.e);allocate(self.a,self.c,l,self.iss,'10',self.e)
        with self.assertRaises(ValidationError):corrections.reserve(self.a,self.c.pk,n.pk,'adjust','Finance',rev(self.c))
        newer=corrections.capture(self.a,self.c.pk,self.iss.pk,n.evidence_id,n.allocation_evidence_id,'Fresh exact financial state',rev(self.c))
        self.assertEqual(newer.version,2);j=apply(self.a,self.c,newer,self.e);j.refresh_from_db();self.assertEqual(j.status,'confirmed')
    def test_changed_method_after_review_holds_effect_without_rewriting_note(self):
        n=note(self.a,self.c,self.iss,self.e);review(self.a,self.c,n,self.e);j=corrections.reserve(self.a,self.c.pk,n.pk,'adjust','Finance',rev(self.c))
        identity=reference_values(active_component('D08.duplicate_correction_rules',self.c))[0];identity['correction']['decimal_places']=3;policy(self.a,self.c,'D08.duplicate_correction_rules',identity)
        invoice_delivery.run_once();j.refresh_from_db();self.assertEqual(j.status,'held');self.assertEqual(InvoiceCorrectionAcceptance.objects.count(),0)
    def test_credit_never_exceeds_face_and_unknown_amount_stays_unknown(self):
        for amount,ref in [('32.26','TOO-MUCH'),(None,'UNKNOWN'),('0.001','PRECISION')]:
            n=note(self.a,self.c,self.iss,self.e,amount=amount,reference=ref)
            with self.assertRaises(ValidationError):review(self.a,self.c,n,self.e)
        self.assertEqual(InvoiceCorrectionAcceptance.objects.count(),0)
    def test_holding_allocation_policy_never_implicitly_unmatches_cash(self):
        r,l=receipt(self.a,self.c);assign(self.a,self.c,r,self.cov,self.e);allocate(self.a,self.c,l,self.iss,'32.25',self.e)
        identity=reference_values(active_component('D08.duplicate_correction_rules',self.c))[0];identity['correction']['credit_allocation_conflict']='hold';policy(self.a,self.c,'D08.duplicate_correction_rules',identity)
        n=note(self.a,self.c,self.iss,self.e)
        with self.assertRaises(ValidationError):review(self.a,self.c,n,self.e)
        self.assertEqual(CashReversal.objects.count(),0);self.assertEqual(cash.cash_remaining(l),Decimal('17.75'))
    def test_no_reversal_permission_rolls_back_credit_and_allocations(self):
        r,l=receipt(self.a,self.c);assign(self.a,self.c,r,self.cov,self.e);allocate(self.a,self.c,l,self.iss,'32.25',self.e)
        n=note(self.a,self.c,self.iss,self.e);review(self.a,self.c,n,self.e)
        Grant.objects.filter(case=self.c,user=self.a,action='finance.cash.reverse').update(active=False)
        with self.assertRaises(PermissionDenied):corrections.reserve(self.a,self.c.pk,n.pk,'adjust','Finance',rev(self.c))
        self.assertEqual(CashReversal.objects.count(),0);self.assertEqual(InvoiceCorrectionAcceptance.objects.count(),0)
    def test_void_frees_cash_closes_only_same_obligation_and_is_terminal(self):
        r,l=receipt(self.a,self.c);assign(self.a,self.c,r,self.cov,self.e);allocate(self.a,self.c,l,self.iss,'20',self.e)
        n=note(self.a,self.c,self.iss,self.e,'void',None,'VOID');j=apply(self.a,self.c,n,self.e);j.refresh_from_db();self.assertEqual(j.status,'confirmed',j.error)
        self.assertEqual(cash.open_amount(self.iss),0);self.assertEqual(cash.cash_remaining(l),50)
        with self.assertRaises(ValidationError):note(self.a,self.c,self.iss,self.e,'debit','1','REOPEN')
        self.assertEqual(InvoiceIssue.objects.count(),1)
    def test_applied_credit_delivery_is_independent_and_private_projection(self):
        n=note(self.a,self.c,self.iss,self.e);apply(self.a,self.c,n,self.e);self.assertEqual(InvoiceCorrectionDelivery.objects.count(),0)
        corrections.reserve(self.a,self.c.pk,n.pk,'adjust_deliver','Finance',rev(self.c));invoice_delivery.run_once();d=InvoiceCorrectionDelivery.objects.get()
        self.assertEqual(d.payload['kind'],'credit');self.assertNotIn('source_hash',d.payload);self.assertNotIn('obligation_key',d.payload)
        self.client.force_login(self.a);self.assertContains(self.client.get('/finance/invoices/inbox/'),n.reference)
        Grant.objects.filter(case=self.c,user=self.a,action='finance.invoice.receive').update(active=False)
        self.assertNotContains(self.client.get('/finance/invoices/inbox/'),n.reference)
    def test_returned_review_and_case_admin_cannot_authorize_credit(self):
        n=note(self.a,self.c,self.iss,self.e);review(self.a,self.c,n,self.e)
        financial_reviews.review(self.a,self.c.pk,'invoice',n.pk,'Finance','return',self.e['review'].pk,'Return exact note',rev(self.c))
        with self.assertRaises(ValidationError):corrections.reserve(self.a,self.c.pk,n.pk,'adjust','Finance',rev(self.c))
        self.a.is_superuser=True;self.a.save();transition(self.a,active_component('D05.role_principal_assignments',self.c).pk,'revoked')
        with self.assertRaises(ValidationError):review(self.a,self.c,n,self.e)
    def test_wrong_note_dimensions_reference_and_schema_cannot_grant_authority(self):
        from apps.policy.services import register_reference,save_draft
        from .helpers import envelope
        value={'document_ref':'WRONG','invoice_reference':'not-this-invoice','kind':'credit','amount':'5','currency':'NGN','amount_basis':'gross_including_tax'}
        e=evidence(self.a,self.c,'invoice_credit_note',json.dumps(value))
        with self.assertRaises(ValidationError):corrections.capture(self.a,self.c.pk,self.iss.pk,e.pk,None,'Wrong target',rev(self.c))
        owner=evidence(self.a,self.c,'policy_decision','Synthetic wrong component test');rule=json.loads(FIXTURE.read_text(encoding='utf-8'))['rules'][0]
        ref=register_reference(self.a,self.c.pk,'wrong-domain','schema:psl/financial-correction/v1',rule,owner.pk)
        cfg=save_draft(self.a,self.c.pk,envelope(self.c,'D14.receipt_verification_source_ref',ref.ref,owner))
        with self.assertRaises(ValidationError):transition(self.a,cfg.pk,'validated')
    def test_corrected_cash_preserves_global_identity_and_never_copies_old_allocations(self):
        r,l=receipt(self.a,self.c);assign(self.a,self.c,r,self.cov,self.e);allocate(self.a,self.c,l,self.iss,'20',self.e)
        cash.reverse(self.a,self.c.pk,'lot',l.pk,'Finance',self.e['cash_correction'].pk,'Full parent reversal',rev(self.c));s=successor(self.a,self.c,l,self.e);review(self.a,self.c,s,self.e,'cash');a=cash_successors.apply(self.a,self.c.pk,s.pk,'Finance',rev(self.c))
        self.assertEqual(CashReceipt.objects.count(),1);r.refresh_from_db();self.assertEqual(r.payload['amount'],'50');self.assertEqual(cash.lot_payload(a.lot)['amount'],'40')
        self.assertEqual(CashAllocation.objects.filter(lot=a.lot).count(),0);allocate(self.a,self.c,a.lot,self.iss,'10',self.e,'new-lot-match')
        snap=receivables.snapshot(self.a,self.c.pk,timezone.localdate(),rev(self.c));self.assertEqual(Decimal(snap.result['groups'][0]['verified_cash']),40);self.assertEqual(Decimal(snap.result['groups'][0]['unallocated_cash']),30)
        with self.assertRaises(ValidationError):cash.report(self.a,self.c.pk,s.evidence_id,rev(self.c))
    def test_multiple_corrected_generations_sum_each_gross_less_reversal_once(self):
        r,l=receipt(self.a,self.c);assign(self.a,self.c,r,self.cov,self.e)
        for amount in ['40.00','60.00']:
            cash.reverse(self.a,self.c.pk,'lot',l.pk,'Finance',self.e['cash_correction'].pk,'Reverse exact predecessor once',rev(self.c))
            s=successor(self.a,self.c,l,self.e,amount);review(self.a,self.c,s,self.e,'cash');l=cash_successors.apply(self.a,self.c.pk,s.pk,'Finance',rev(self.c)).lot
        snap=receivables.snapshot(self.a,self.c.pk,timezone.localdate(),rev(self.c));self.assertEqual(Decimal(snap.result['groups'][0]['verified_cash']),60);self.assertEqual(CashVerification.objects.count(),3)
    def test_only_one_accepted_successor_per_parent_and_old_parent_cannot_branch(self):
        r,l=receipt(self.a,self.c);cash.reverse(self.a,self.c.pk,'lot',l.pk,'Finance',self.e['cash_correction'].pk,'Parent reversal',rev(self.c))
        first=successor(self.a,self.c,l,self.e,'40');second=successor(self.a,self.c,l,self.e,'45');review(self.a,self.c,first,self.e,'cash');review(self.a,self.c,second,self.e,'cash')
        cash_successors.apply(self.a,self.c.pk,first.pk,'Finance',rev(self.c))
        with self.assertRaises(ValidationError):cash_successors.apply(self.a,self.c.pk,second.pk,'Finance',rev(self.c))
        self.assertEqual(CashSuccessorAcceptance.objects.count(),1)
    def test_successor_unknown_or_mismatched_verification_cannot_create_cash(self):
        r,l=receipt(self.a,self.c);cash.reverse(self.a,self.c.pk,'lot',l.pk,'Finance',self.e['cash_correction'].pk,'Parent reversal',rev(self.c))
        s=successor(self.a,self.c,l,self.e,None)
        with self.assertRaises(ValidationError):review(self.a,self.c,s,self.e,'cash')
        value=dict(cash.lot_payload(l),amount='40');report=evidence(self.a,self.c,'cash_report',json.dumps(value));proof=evidence(self.a,self.c,'cash_verification',json.dumps(dict(value,amount='41')))
        s=cash_successors.capture(self.a,self.c.pk,l.pk,report.pk,proof.pk,self.e['cash_correction'].pk,'Mismatched proof',rev(self.c))
        with self.assertRaises(ValidationError):review(self.a,self.c,s,self.e,'cash')
        self.assertEqual(CashVerification.objects.count(),1)
    def test_successor_does_not_change_customer_currency_or_transaction_identity(self):
        r,l=receipt(self.a,self.c)
        for field,value in [('customer','another-client'),('currency','USD'),('transaction_ref','new-transaction')]:
            body=dict(cash.lot_payload(l),amount='40',**{field:value});report=evidence(self.a,self.c,'cash_report',json.dumps(body));proof=evidence(self.a,self.c,'cash_verification',json.dumps(body))
            with self.assertRaises(ValidationError):cash_successors.capture(self.a,self.c.pk,l.pk,report.pk,proof.pk,self.e['cash_correction'].pk,'Forbidden dimension change',rev(self.c))
    def test_successor_unmatched_policy_explicitly_clears_assignment_without_allocating(self):
        r,l=receipt(self.a,self.c);assign(self.a,self.c,r,self.cov,self.e);cash.reverse(self.a,self.c.pk,'lot',l.pk,'Finance',self.e['cash_correction'].pk,'Full predecessor reversal',rev(self.c))
        rules=reference_values(active_component('D14.adjustment_correction_rule_refs',self.c))
        for x in rules:
            if x['target']=='cash_successor':x['assignment']='unmatched'
        policy(self.a,self.c,'D14.adjustment_correction_rule_refs',rules)
        s=successor(self.a,self.c,l,self.e);review(self.a,self.c,s,self.e,'cash');cash_successors.apply(self.a,self.c.pk,s.pk,'Finance',rev(self.c))
        self.assertIsNone(cash.assigned(r).coverage_id);snap=receivables.snapshot(self.a,self.c.pk,timezone.localdate(),rev(self.c));self.assertTrue(any(Decimal(x['amount'])==40 for x in snap.result['unmatched_cash']))
    def test_successor_source_policy_change_stales_review_and_preserves_capture(self):
        r,l=receipt(self.a,self.c);cash.reverse(self.a,self.c.pk,'lot',l.pk,'Finance',self.e['cash_correction'].pk,'Reverse first',rev(self.c));s=successor(self.a,self.c,l,self.e);review(self.a,self.c,s,self.e,'cash')
        transition(self.a,active_component('D14.receipt_verification_source_ref',self.c).pk,'revoked')
        with self.assertRaises(ValidationError):cash_successors.apply(self.a,self.c.pk,s.pk,'Finance',rev(self.c))
        self.assertEqual(CashVerification.objects.count(),1)
    def test_correction_postgresql_guards_reject_direct_history_mutation(self):
        self.assertEqual(connection.vendor,'postgresql');n=note(self.a,self.c,self.iss,self.e);apply(self.a,self.c,n,self.e)
        for sql,pk in [('UPDATE finance_invoicecorrection SET amount=1 WHERE id=%s',n.pk),("UPDATE finance_invoicecorrectionacceptance SET sha256='wrong' WHERE id=%s",InvoiceCorrectionAcceptance.objects.get().pk)]:
            with self.assertRaises(DatabaseError),transaction.atomic():
                with connection.cursor() as cursor:cursor.execute(sql,[pk])

    def test_full_correction_staff_ui_calls_real_services_and_preserves_one_debt(self):
        self.client.force_login(self.a);url=f'/cases/{self.c.pk}/finance/corrections/'
        def post(action,**data):
            response=self.client.post(url,dict(action=action,revision=rev(self.c),**data));self.assertEqual(response.status_code,302,response.content[:500])
        doc={'document_ref':'UI-CREDIT','invoice_reference':self.iss.invoice.reference,'kind':'credit','amount':'5','currency':'NGN','amount_basis':'gross_including_tax'}
        source=evidence(self.a,self.c,'invoice_credit_note',json.dumps(doc))
        post('note',issue=self.iss.pk,evidence=source.pk,allocation_evidence=self.e['cash_correction'].pk,reason='UI exact legal note')
        n=InvoiceCorrection.objects.get();post('review',kind='invoice',correction=n.pk,role='Finance',verdict='approve',evidence=self.e['review'].pk,reason='UI exact current correction approved')
        post('reserve',correction=n.pk,effect='adjust',role='Finance');invoice_delivery.run_once();self.assertContains(self.client.get(url),'Applied')
        post('reserve',correction=n.pk,effect='adjust_deliver',role='Finance');invoice_delivery.run_once();self.assertEqual(InvoiceCorrectionDelivery.objects.count(),1)
        r,l=receipt(self.a,self.c);cash.reverse(self.a,self.c.pk,'lot',l.pk,'Finance',self.e['cash_correction'].pk,'UI predecessor preparation',rev(self.c))
        value=dict(cash.lot_payload(l),amount='40');reported=evidence(self.a,self.c,'cash_report',json.dumps(value));verified=evidence(self.a,self.c,'cash_verification',json.dumps(value))
        post('successor',parent=l.pk,report=reported.pk,verification=verified.pk,legal=self.e['cash_correction'].pk,reason='UI corrected cash statement')
        from apps.finance.models import CashSuccessor
        s=CashSuccessor.objects.get();post('review',kind='cash',successor=s.pk,role='Finance',verdict='approve',evidence=self.e['review'].pk,reason='UI exact successor approved')
        post('apply_successor',successor=s.pk,role='Finance');self.assertContains(self.client.get(url),'Accepted lot')
        post('investigate',kind='cash',successor=s.pk);self.assertEqual(InvoiceIssue.objects.count(),1);self.assertEqual(CashVerification.objects.count(),2)
    def test_correction_policy_ui_retains_draft_then_validates_typed_version(self):
        self.client.force_login(self.a);url=f'/cases/{self.c.pk}/finance/corrections/'
        content=reference_values(active_component('D08.duplicate_correction_rules',self.c))[0];owner=evidence(self.a,self.c,'policy_decision','Synthetic correction-method UI draft')
        response=self.client.post(url,{'action':'policy','component':'D08.duplicate_correction_rules','content':json.dumps(content),'evidence':owner.pk,'effective_from':timezone.now().isoformat(),'revision':rev(self.c)})
        self.assertEqual(response.status_code,302)
        from apps.policy.models import Configuration
        c=Configuration.objects.filter(case=self.c,component='D08.duplicate_correction_rules').order_by('-pk').first();self.assertEqual(c.states.order_by('-pk').first().state,'draft');self.assertEqual(c.envelope['value']['schema_ref'],'schema:psl/invoice-identity/v2')
        transition(self.a,c.pk,'validated');transition(self.a,c.pk,'active')
    def test_successor_review_checks_current_source_precision_before_approval(self):
        r,l=receipt(self.a,self.c);cash.reverse(self.a,self.c.pk,'lot',l.pk,'Finance',self.e['cash_correction'].pk,'Parent reversal',rev(self.c));s=successor(self.a,self.c,l,self.e,'40.001')
        with self.assertRaisesMessage(ValidationError,'precision'):review(self.a,self.c,s,self.e,'cash')
        self.assertEqual(CashSuccessorAcceptance.objects.count(),0)
    def test_invoice_correction_remains_available_after_original_preparer_grant_withdrawal(self):
        Grant.objects.filter(case=self.c,user=self.a,action='finance.billing.prepare').update(active=False)
        n=note(self.a,self.c,self.iss,self.e);j=apply(self.a,self.c,n,self.e);j.refresh_from_db();self.assertEqual(j.status,'confirmed',j.error)
        self.assertEqual(corrections.adjusted_face(self.iss),Decimal('27.25'))
    def test_successor_agent_cites_original_and_corrected_sources_without_effect_tools(self):
        r,l=receipt(self.a,self.c);s=successor(self.a,self.c,l,self.e)
        log=investigate(self.a,self.c.pk,'cash',s.pk,rev(self.c));self.assertTrue(log.result['findings']);self.assertFalse(log.result['cash_mutated']);self.assertFalse(log.result['approval_granted'])
        self.assertEqual(log.result['lineage']['parent_lot'],l.pk);self.assertIn(s.verification_evidence_id,[x['id'] for x in log.result['citations']])

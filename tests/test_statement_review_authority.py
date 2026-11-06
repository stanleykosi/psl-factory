"""Native statement-only authority guards, including the legacy v1 branch."""
import copy
from django.test import TestCase
from django.db import connection,transaction,DatabaseError
from apps.finance import analysis
from apps.finance.conventions import PRODUCER,CONVERSION
from apps.finance.documents import draft_report
from apps.documents.controlled import preflight
from apps.documents.models import Publication
from apps.identity.models import Grant
from tests import test_finance_statements as statement_tests
from tests import test_finance_conventions as convention_tests
from tests.finance_analysis_helpers import policy
from tests.helpers import rev

class StatementAuthorityChecks:
    def native_current(self,run):
        with connection.cursor() as cursor:
            cursor.execute('SELECT psl_statement_conventions_current(%s)',[run.pk])
            return cursor.fetchone()[0]

    def prepared(self,target):
        source_actor=self.reviewer if target=='source' else self.a
        source_review=analysis.review(source_actor,self.c.pk,'output',self.r.pk,'Finance','approve',self.e['finance_review'].pk,'Exact source review for isolated authority check',rev(self.c))
        value=copy.deepcopy(self.contract_value);value['inputs'][0]['source_review']=source_review.pk
        if value.get('convention_mode')=='producer_verified':
            producer_value=copy.deepcopy(self.producer_value);producer_value['declarations'][0]['source_review']=source_review.pk
            producer=policy(self.a,self.c,PRODUCER,producer_value,self.e['policy_decision'])
            value['inputs'][0]['producer_contract_id']=producer.pk
            for kind,config in [('producer',producer),('conversion',self.conversion)]:
                actor=self.reviewer if target==kind else self.a
                analysis.review(actor,self.c.pk,'formula',config.pk,'Finance','approve',self.e['finance_review'].pk,'Explicit independent declaration review',rev(self.c))
        contract=self.configure(value)
        if target!='contract':analysis.review(self.a,self.c.pk,'formula',contract.pk,'Finance','approve',self.e['finance_review'].pk,'Keep contract review distinct',rev(self.c))
        run=self.assemble(contract)
        actor=self.reviewer if target=='output' else self.a
        analysis.review(actor,self.c.pk,'output',run.pk,'Finance','approve',self.e['finance_review'].pk,'Exact selected statement output review',rev(self.c))
        document=draft_report(self.a,self.c.pk,run.pk,self.template.pk,'internal',rev(self.c))
        self.assertTrue(self.native_current(run));self.assertFalse(preflight(document))
        return run,document

    def assert_native_blocked(self,run,document):
        self.assertFalse(self.native_current(run));self.assertTrue(preflight(document))
        with self.assertRaisesMessage(DatabaseError,'Exact current reviewed producer'),transaction.atomic():
            Publication.objects.create(version=document,actor=self.a,policies={},recipient_ids=[self.recipient.pk],retention_days=30,operation_key='denied-current-authority')

    def withdraw(self,target):
        run,document=self.prepared(target)
        Grant.objects.filter(case=self.c,user=self.reviewer,action='finance.review').update(active=False)
        self.assertFalse(analysis.certification_findings(self.r))
        self.assertEqual(analysis.current_review(self.c,'output',run=self.r)['valid'],target!='source')
        self.assert_native_blocked(run,document)

    def test_distinct_contract_reviewer_grant_withdrawal_blocks_sql(self):self.withdraw('contract')
    def test_distinct_source_reviewer_grant_withdrawal_blocks_sql(self):self.withdraw('source')
    def test_distinct_output_reviewer_grant_withdrawal_blocks_sql(self):self.withdraw('output')

    def test_inactive_reviewer_blocks_native_statement(self):
        run,document=self.prepared('contract')
        # Native policy invalidates an assignment inventory containing an inactive nominee.
        # Unlike single-grant withdrawal, this can also invalidate other reviews of that inventory.
        self.reviewer.is_active=False;self.reviewer.save(update_fields=['is_active'])
        self.assert_native_blocked(run,document)

    def test_changed_preparer_rule_blocks_native_statement(self):
        run,document=self.prepared('output')
        authority=copy.deepcopy(self.f['authority'])
        for row in authority['finance']:
            if row['purpose']=='formula':row['allow_preparer_review']=False
        policy(self.a,self.c,'D05.decision_action_matrix',authority,self.e['policy_decision'])
        self.assert_native_blocked(run,document)

    def test_new_output_review_does_not_reauthorize_an_old_document_binding(self):
        run,document=self.prepared('contract')
        analysis.review(self.a,self.c.pk,'output',run.pk,'Finance','approve',self.e['finance_review'].pk,'New exact output review',rev(self.c))
        self.assertTrue(self.native_current(run));self.assertTrue(preflight(document))
        with self.assertRaisesMessage(DatabaseError,'Exact current reviewed producer'),transaction.atomic():
            Publication.objects.create(version=document,actor=self.a,policies={},recipient_ids=[self.recipient.pk],retention_days=30,operation_key='denied-stale-output-binding')

    def test_unrelated_matrix_namespace_does_not_invent_new_review_requirement(self):
        run,document=self.prepared('contract')
        authority=copy.deepcopy(self.f['authority']);authority['rules']=[{'role':'PM','actions':['return']}]
        policy(self.a,self.c,'D05.decision_action_matrix',authority,self.e['policy_decision'])
        self.assertTrue(self.native_current(run));self.assertFalse(preflight(document))

    def test_output_review_digit_boundary_keeps_binding_exact(self):
        run,document=self.prepared('contract')
        with connection.cursor() as cursor:
            cursor.execute('SELECT coalesce(max(id),0) FROM finance_financereview')
            boundary=10**len(str(cursor.fetchone()[0]+2))
            cursor.execute("SELECT setval(pg_get_serial_sequence('finance_financereview','id'),%s)",[boundary-2])
        prior=analysis.review(self.a,self.c.pk,'output',run.pk,'Finance','approve',self.e['finance_review'].pk,'Output immediately before decimal ID boundary',rev(self.c))
        self.assertEqual(prior.pk,boundary-1)
        old_document=draft_report(self.a,self.c.pk,run.pk,self.template.pk,'internal',rev(self.c))
        current=analysis.review(self.a,self.c.pk,'output',run.pk,'Finance','approve',self.e['finance_review'].pk,'Output at decimal ID boundary',rev(self.c))
        self.assertEqual(current.pk,boundary)
        self.assertTrue(self.native_current(run));self.assertTrue(preflight(old_document))
        with self.assertRaisesMessage(DatabaseError,'Exact current reviewed producer'),transaction.atomic():
            Publication.objects.create(version=old_document,actor=self.a,policies={},recipient_ids=[self.recipient.pk],retention_days=30,operation_key='denied-lexical-output-binding')
        fresh_document=draft_report(self.a,self.c.pk,run.pk,self.template.pk,'internal',rev(self.c))
        self.assertFalse(preflight(fresh_document))
        Publication.objects.create(version=fresh_document,actor=self.a,policies={},recipient_ids=[self.recipient.pk],retention_days=30,operation_key='exact-numeric-output-binding')

class LegacyStatementAuthorityTests(StatementAuthorityChecks,TestCase):
    configure=classmethod(statement_tests.StatementTests.configure.__func__)
    assemble=statement_tests.StatementTests.assemble
    @classmethod
    def setUpTestData(cls):statement_tests.StatementTests.setUpTestData.__func__(cls)

class ConvertedStatementAuthorityTests(StatementAuthorityChecks,TestCase):
    configure=classmethod(convention_tests.ConventionTests.configure.__func__)
    reviewed=classmethod(convention_tests.ConventionTests.reviewed.__func__)
    assemble=convention_tests.ConventionTests.assemble
    @classmethod
    def setUpTestData(cls):convention_tests.ConventionTests.setUpTestData.__func__(cls)
    def test_distinct_producer_reviewer_grant_withdrawal_blocks_sql(self):self.withdraw('producer')
    def test_distinct_conversion_reviewer_grant_withdrawal_blocks_sql(self):self.withdraw('conversion')

    def test_review_ids_cross_decimal_digit_boundary_numerically(self):
        # ORDER BY an unqualified id::text output alias would choose 999 over 1000.
        # Sequences are intentionally advanced only in this isolated PostgreSQL test DB.
        with connection.cursor() as cursor:
            cursor.execute('SELECT coalesce(max(id),0) FROM finance_financereview')
            boundary=10**len(str(cursor.fetchone()[0]+2))
            cursor.execute("SELECT setval(pg_get_serial_sequence('finance_financereview','id'),%s)",[boundary-2])
        prior=analysis.review(self.a,self.c.pk,'output',self.r.pk,'Finance','approve',self.e['finance_review'].pk,'Review immediately before decimal ID boundary',rev(self.c))
        self.assertEqual(prior.pk,boundary-1)
        run,document=self.prepared('contract')
        self.assertEqual(run.snapshot['inputs'][0]['declaration']['source_review'],boundary)
        self.assertTrue(self.native_current(run));self.assertFalse(preflight(document))

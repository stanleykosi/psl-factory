"""Synthetic F08 selected-boundary acceptance. No live owner policy implied."""
import copy,json
from django.test import TestCase,SimpleTestCase
from django.core.exceptions import ValidationError
from django.db import DatabaseError,transaction
from apps.core.services import add_evidence
from apps.finance import analysis,statements
from apps.finance.conventions import PRODUCER,CONVERSION
from apps.finance.rules import evaluate
from apps.finance.models import FinanceRun
from apps.policy.services import reference_values,transition
from tests.finance_analysis_helpers import policy,pipeline,METRICS
from tests import test_finance_statements as statement_tests
from tests.helpers import rev

class ConventionTests(TestCase):
    configure=classmethod(statement_tests.StatementTests.configure.__func__)
    assemble=statement_tests.StatementTests.assemble

    @classmethod
    def setUpTestData(cls):
        statement_tests.StatementTests.setUpTestData.__func__(cls)
        rules=copy.deepcopy(reference_values(cls.configs['D06.rule_oracle_refs']))
        rule=copy.deepcopy(rules[-1]);rule.update(key='Note.L1',terms=[{'kind':'line','key':'asset','coefficient':'-1','value_stage':'base_value'}])
        rule['oracles']=[{'key':'known','inputs':[{'kind':'line','key':'asset','value':'500'}],'expected':'-500'},{'key':'unknown','inputs':[{'kind':'line','key':'asset','value':None}],'expected':None}]
        rule['oracle_evidence_id']=add_evidence(cls.a,cls.c.pk,'finance_oracle',json.dumps(rule['oracles']),'synthetic:F08-N01-formula').pk
        rules.append(rule);config=policy(cls.a,cls.c,'D06.rule_oracle_refs',rules,cls.e['policy_decision'])
        analysis.review(cls.a,cls.c.pk,'formula',config.pk,'Finance','approve',cls.e['finance_review'].pk,'Explicit synthetic algebra',rev(cls.c))
        cls.m,cls.b,cls.r=pipeline(cls.a,cls.c,cls.source)
        cls.output_review=analysis.review(cls.reviewer,cls.c.pk,'output',cls.r.pk,'Finance','approve',cls.e['finance_review'].pk,'Exact native formula output',rev(cls.c))
        cls.producer_value={'declarations':[{'key':'note-source','source_run':cls.r.pk,'operation_key':cls.r.operation_key,'source_review':cls.output_review.pk,'metric':'Note.L1','unit':'major_currency','convention':'source-debit','evidence_id':cls.e['finance_review'].pk}]}
        cls.producer=cls.reviewed(PRODUCER,cls.producer_value)
        examples=[{'kind':kind,'input':amount,'expected':expected} for kind,amount,expected in [('positive','500','-500'),('negative','-500','500'),('zero','0','0'),('unknown',None,None)]]
        oracle=add_evidence(cls.a,cls.c.pk,'finance_oracle',json.dumps(examples),'synthetic:F08-conversion-oracles')
        cls.conversion_value={'declarations':[{'key':'reverse','from_convention':'source-debit','to_convention':'note-credit','unit':'major_currency','operation':'reverse_sign','factor':'-1','evidence_id':cls.e['finance_review'].pk,'oracle_evidence_id':oracle.pk,'oracles':examples}]}
        cls.conversion=cls.reviewed(CONVERSION,cls.conversion_value)
        cls.contract_value=copy.deepcopy(cls.contract_value);cls.contract_value['convention_mode']='producer_verified'
        cls.contract_value['oracle_evidence_id']=add_evidence(cls.a,cls.c.pk,'finance_oracle',json.dumps({'C30':'500'}),'synthetic:F08-N01-output').pk
        cls.contract_value['inputs'][0].update(source_run=cls.r.pk,source_review=cls.output_review.pk,metric='Note.L1',source_kind='note',source_location='Note!L1',source_sign='source-debit',destination_sign='note-credit',transfer='reverse_sign',producer_contract_id=cls.producer.pk,producer_key='note-source',conversion_contract_id=cls.conversion.pk,conversion_key='reverse')
        cls.contract=cls.configure(cls.contract_value)

    @classmethod
    def reviewed(cls,component,value):
        config=policy(cls.a,cls.c,component,value,cls.e['policy_decision'])
        analysis.review(cls.a,cls.c.pk,'formula',config.pk,'Finance','approve',cls.e['finance_review'].pk,'Owner-configured synthetic declaration review',rev(cls.c))
        return config

    def test_f08_n01_converts_once_preserves_source_and_explains_ui(self):
        run=self.assemble();self.assertEqual(run.result['company']['C30']['value'],'500.00')
        self.assertEqual(self.r.result['company']['Note.L1']['value'],'-500.00')
        pin=run.snapshot['inputs'][0]['convention_transfer'];self.assertEqual(pin['applications'],1)
        self.assertEqual(pin['producer']['id'],self.producer.pk);self.assertEqual(pin['conversion']['id'],self.conversion.pk)
        self.assertEqual(self.assemble().pk,run.pk)
        self.client.force_login(self.a);response=self.client.get(f'/cases/{self.c.pk}/finance/')
        self.assertContains(response,'Producer verified');self.assertContains(response,'applied once')
        from apps.agents.finance_analysis import investigate_finance
        log=investigate_finance(self.a,self.c.pk,run.pk,rev(self.c));self.assertFalse(log.result['approval_granted'])

    def test_f08_e01_no_statement_reinterpretation_or_second_conversion(self):
        run=self.assemble()
        with self.assertRaises(ValidationError):statements.assemble(self.a,self.c.pk,run.pk,self.contract.pk,rev(self.c))
        value=copy.deepcopy(self.contract_value);value['inputs'][0]['source_run']=run.pk
        with self.assertRaises(ValidationError):self.configure(value)
        value=copy.deepcopy(self.contract_value);value['inputs'][0]['source_sign']='note-credit'
        with self.assertRaises(ValidationError):self.assemble(self.configure(value))

    def test_missing_declaration_holds_only_statement(self):
        value=copy.deepcopy(self.contract_value);value['inputs'][0]['producer_contract_id']=None
        run=self.assemble(self.configure(value));self.assertEqual(run.result['status'],'needs_attention')
        self.assertEqual(run.result['company']['C30']['value'],'-500.00')
        self.assertFalse(analysis.certification_findings(self.r))
        self.assertTrue(analysis.current_review(self.c,'output',run=self.r)['valid'])
        with self.assertRaises(ValidationError):analysis.review(self.a,self.c.pk,'output',run.pk,'Finance','approve',self.e['finance_review'].pk,'Held output',rev(self.c))

    def test_factory_missing_producer_holds_only_selected_statement(self):
        from tests.factory_accounting_helpers import configured
        from apps.workflows import factory
        value=copy.deepcopy(self.contract_value);value['inputs'][0]['producer_contract_id']=None
        contract=self.configure(value)
        work=configured(self.a,self.c,self.e,self.source,self.template,METRICS,statement_contract_id=contract.pk)['work']
        factory.run_until_wait(work.pk);work.refresh_from_db()
        self.assertEqual(work.status,'configuration_needed',work.finding)
        self.assertIn(PRODUCER,work.finding)
        self.assertFalse(analysis.certification_findings(self.r))
        self.assertTrue(analysis.current_review(self.c,'output',run=self.r)['valid'])
        self.assertFalse(FinanceRun.objects.filter(kind='statement').exists())

    def test_exact_operation_review_metric_unit_and_ids_required(self):
        for key,bad in [('operation_key','not-the-run'),('source_review',999999),('metric','not-a-metric'),('unit','thousands_currency')]:
            with self.subTest(key=key):
                value=copy.deepcopy(self.producer_value);value['declarations'][0][key]=bad
                with self.assertRaises(ValidationError):self.reviewed(PRODUCER,value)
        for key,bad in [('source_sign','other'),('destination_sign','other'),('transfer','identity'),('producer_key','other'),('conversion_key','other')]:
            with self.subTest(key=key):
                value=copy.deepcopy(self.contract_value);value['inputs'][0][key]=bad
                with self.assertRaises(ValidationError):self.assemble(self.configure(value))
        value=copy.deepcopy(self.conversion_value);value['declarations'][0]['unit']='thousands_currency'
        config=self.reviewed(CONVERSION,value)
        value=copy.deepcopy(self.contract_value);value['inputs'][0]['conversion_contract_id']=config.pk
        with self.assertRaises(ValidationError):self.assemble(self.configure(value))

    def test_finite_factor_and_four_real_evidenced_oracles(self):
        for factor in ['0','2','NaN','Infinity',1]:
            value=copy.deepcopy(self.conversion_value);value['declarations'][0]['factor']=factor
            with self.assertRaises(ValidationError):self.reviewed(CONVERSION,value)
        for index,bad in [(0,'500'),(1,'-500'),(2,'1'),(3,'0')]:
            value=copy.deepcopy(self.conversion_value);row=value['declarations'][0];row['oracles'][index]['expected']=bad
            row['oracle_evidence_id']=add_evidence(self.a,self.c.pk,'finance_oracle',json.dumps(row['oracles']),'synthetic:invalid-golden').pk
            with self.assertRaises(ValidationError):self.reviewed(CONVERSION,value)
        value=copy.deepcopy(self.conversion_value);value['declarations'][0]['oracles'][0]['input']='300'
        with self.assertRaises(ValidationError):self.reviewed(CONVERSION,value)

    def test_high_precision_oracles_use_the_exact_runtime_operation(self):
        from apps.finance.conventions import apply_conversion
        value=copy.deepcopy(self.conversion_value);row=value['declarations'][0]
        exact='12345678901234567890123.12345678'
        row['oracles'][0].update(input=exact,expected='-'+exact)
        row['oracle_evidence_id']=add_evidence(self.a,self.c.pk,'finance_oracle',json.dumps(row['oracles']),'synthetic:exact-high-precision').pk
        self.reviewed(CONVERSION,value)
        self.assertEqual(apply_conversion(exact,row),'-'+exact)
        row['oracles'][0]['expected']='-12345678901234567890123.12346'
        row['oracle_evidence_id']=add_evidence(self.a,self.c.pk,'finance_oracle',json.dumps(row['oracles']),'synthetic:incorrect-rounded-oracle').pk
        with self.assertRaises(ValidationError):self.reviewed(CONVERSION,value)

    def test_duplicate_producer_identity_cannot_claim_two_conventions(self):
        for convention in ['opposite-sign','source-debit']:
            value=copy.deepcopy(self.producer_value)
            other=dict(value['declarations'][0],key='second-name',convention=convention)
            value['declarations'].append(other)
            with self.assertRaises(ValidationError):self.reviewed(PRODUCER,value)

    def test_withdrawn_conversion_review_blocks_native_publication_guard(self):
        from apps.finance.documents import draft_report
        from apps.documents.models import Publication
        run=self.assemble()
        analysis.review(self.reviewer,self.c.pk,'output',run.pk,'Finance','approve',self.e['finance_review'].pk,'Reviewed selected output',rev(self.c))
        doc=draft_report(self.a,self.c.pk,run.pk,self.template.pk,'internal',rev(self.c))
        analysis.review(self.a,self.c.pk,'formula',self.conversion.pk,'Finance','return',self.e['finance_review'].pk,'Withdraw conversion',rev(self.c))
        with self.assertRaises(ValidationError):analysis.ensure_current(run)
        with self.assertRaisesMessage(DatabaseError,'Exact current reviewed producer'),transaction.atomic():
            Publication.objects.create(version=doc,actor=self.a,policies={},recipient_ids=[self.recipient.pk],retention_days=30,operation_key='forged-convention-publication')

    def test_identity_uses_exact_reviewed_producer_without_reversal(self):
        value=copy.deepcopy(self.conversion_value);row=value['declarations'][0]
        row.update(operation='identity',factor='1',to_convention='source-debit')
        for example in row['oracles']:example['expected']=example['input']
        row['oracle_evidence_id']=add_evidence(self.a,self.c.pk,'finance_oracle',json.dumps(row['oracles']),'synthetic:identity').pk
        conversion=self.reviewed(CONVERSION,value)
        value=copy.deepcopy(self.contract_value);value['inputs'][0].update(transfer='identity',destination_sign='source-debit',conversion_contract_id=conversion.pk)
        value['oracle_evidence_id']=add_evidence(self.a,self.c.pk,'finance_oracle',json.dumps({'C30':'-500'}),'synthetic:identity-result').pk
        run=self.assemble(self.configure(value));self.assertEqual(run.result['company']['C30']['value'],'-500.00');self.assertEqual(run.result['status'],'complete')

    def test_revocation_and_review_withdrawal_stale_rebuild(self):
        run=self.assemble()
        analysis.review(self.a,self.c.pk,'formula',self.producer.pk,'Finance','return',self.e['finance_review'].pk,'Withdraw producer declaration',rev(self.c))
        with self.assertRaises(ValidationError):analysis.ensure_current(run)
        analysis.review(self.a,self.c.pk,'formula',self.producer.pk,'Finance','approve',self.e['finance_review'].pk,'New review not old snapshot',rev(self.c))
        with self.assertRaises(ValidationError):analysis.ensure_current(run)
        run=self.assemble();transition(self.a,self.conversion.pk,'revoked')
        with self.assertRaises(ValidationError):analysis.ensure_current(run)

    def test_queued_publication_rechecks_declaration(self):
        from apps.finance.documents import draft_report
        from apps.documents.controlled import reserve_publication
        from apps.documents.delivery import run_publication_once
        from apps.documents.models import PublicationReceipt
        run=self.assemble();analysis.review(self.reviewer,self.c.pk,'output',run.pk,'Finance','approve',self.e['finance_review'].pk,'Selected converted lines',rev(self.c))
        doc=draft_report(self.a,self.c.pk,run.pk,self.template.pk,'internal',rev(self.c))
        publication=reserve_publication(self.a,self.c.pk,doc.pk,rev(self.c))
        transition(self.a,self.conversion.pk,'revoked');run_publication_once(job_id=publication.job.pk)
        self.assertFalse(PublicationReceipt.objects.exists())

    def test_unknown_zero_and_positive_boundary_values(self):
        from apps.finance.conventions import transfer
        row=self.contract_value['inputs'][0]
        for amount,expected in [(None,None),('0','0'),('500','-500')]:
            actual,pin,findings=transfer(self.c,row,self.r,{'unit':'major_currency','value':amount})
            self.assertEqual(actual,expected);self.assertEqual(pin['source_value'],amount)
            self.assertEqual(pin['applications'],1);self.assertFalse(findings)

    def test_native_guard_rejects_revoked_conversion(self):
        from django.db import connection
        run=self.assemble()
        analysis.review(self.a,self.c.pk,'output',run.pk,'Finance','approve',self.e['finance_review'].pk,'Native publication boundary review',rev(self.c))
        with connection.cursor() as cursor:
            cursor.execute('SELECT psl_statement_conventions_current(%s)',[run.pk]);self.assertTrue(cursor.fetchone()[0])
        transition(self.a,self.conversion.pk,'revoked')
        with connection.cursor() as cursor:
            cursor.execute('SELECT psl_statement_conventions_current(%s)',[run.pk]);self.assertFalse(cursor.fetchone()[0])

    def test_native_factory_publication_guards(self):
        statement_tests.StatementTests.test_factory_selected_statement_reaches_native_receipts(self)

    def test_superseded_producer_blocks_reuse(self):
        run=self.assemble()
        self.reviewed(PRODUCER,self.producer_value)
        with self.assertRaises(ValidationError):analysis.ensure_current(run)

    def test_configured_authority_not_invented_independent_reviewer(self):
        from django.core.exceptions import PermissionDenied
        # Existing configured rule permits preparer review; setup uses it for both new components.
        self.assertTrue(analysis.current_review(self.c,'formula',configuration=self.conversion)['valid'])
        authority=copy.deepcopy(self.f['authority'])
        for rule in authority['finance']:
            if rule['purpose']=='formula':rule['allow_preparer_review']=False
        policy(self.a,self.c,'D05.decision_action_matrix',authority,self.e['policy_decision'])
        self.assertFalse(analysis.current_review(self.c,'formula',configuration=self.conversion)['valid'])
        with self.assertRaises(PermissionDenied):analysis.review(self.a,self.c.pk,'formula',self.conversion.pk,'Finance','approve',self.e['finance_review'].pk,'Not allowed by new authority',rev(self.c))


class AlgebraUnchangedTests(SimpleTestCase):
    def test_f08_n02_and_valid_subtraction_are_not_convention_inference(self):
        rule={'terms':[{'kind':'line','key':'I153','coefficient':'-1'}],'divisor':'1000','output_unit':'thousands_currency','decimal_places':2,'rounding':'half_even'}
        self.assertEqual(evaluate(rule,{('line','I153'):'-5000'})['value'],'5.00')
        rule.update(terms=[{'kind':'line','key':'income','coefficient':'1'},{'kind':'line','key':'cost','coefficient':'-1'}],divisor='1',output_unit='major_currency')
        self.assertEqual(evaluate(rule,{('line','income'):'1000',('line','cost'):'250'})['value'],'750.00')

    def test_migration_composition_preserves_every_predecessor_branch(self):
        from importlib import import_module
        workflow=import_module('apps.workflows.migrations.0065_statement_conventions')
        self.assertEqual(workflow.SQL.replace(workflow.REPLACEMENT,workflow.ORIGINAL),workflow.PREVIOUS)
        documents=import_module('apps.documents.migrations.0022_statement_conventions')
        self.assertEqual(documents.SQL.replace(documents.GUARD,''),documents.PREVIOUS)
        # A cast output alias must never order native review identities lexically.
        self.assertNotRegex(workflow.CURRENT+documents.GUARD,r'SELECT\s+id::text\s+FROM\b[^;]*?ORDER\s+BY\s+id\s+DESC')

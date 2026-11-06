import copy,json
from importlib import import_module
from django.test import TestCase
from django.core.exceptions import ValidationError
from django.db import connection,transaction,DatabaseError
from django.contrib.auth import get_user_model
from apps.core.services import add_evidence
from apps.identity.models import Grant
from apps.policy.services import register_reference,reference_values,transition
from apps.finance import analysis,statements
from apps.finance.models import FinanceRun,FinanceStatementInput
from apps.finance.documents import draft_report
from apps.documents.controlled import preflight,reserve_publication
from apps.documents.delivery import run_publication_once
from apps.documents.models import PublicationReceipt
from tests.finance_analysis_helpers import fixture,policy,pipeline,METRICS
from tests.helpers import rev,activate,ACTIONS

class StatementTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.a,cls.c,cls.e,cls.f,cls.configs,cls.source,cls.template,cls.recipient=fixture()
        cls.reviewer=get_user_model().objects.create_user(username='independent-reviewer')
        for action in ACTIONS:Grant.objects.create(case=cls.c,user=cls.reviewer,action=action)
        refs=[]
        for user in [cls.a,cls.reviewer]:
            refs.append(register_reference(cls.a,cls.c.pk,'statement-role-'+str(user.pk),'schema:psl/role-assignment/v1',{'role':'Finance','user_id':user.pk},cls.e['policy_decision'].pk).ref)
        activate(cls.a,cls.c,'D05.role_principal_assignments',refs,cls.e['policy_decision'])
        analysis.review(cls.a,cls.c.pk,'source',cls.source.pk,'Finance','approve',cls.e['finance_review'].pk,'Reviewed after assignment revision',rev(cls.c))
        rules=copy.deepcopy(reference_values(cls.configs['D06.rule_oracle_refs']))
        rule=copy.deepcopy(rules[-1])
        rule.update(key='SOCE.I17',scope='company_only',terms=[{'kind':'line','key':'asset','coefficient':'0.024','value_stage':'base_value'}],divisor='1',output_unit='major_currency',decimal_places=2)
        rule['oracles']=[{'key':'known','inputs':[{'kind':'line','key':'asset','value':'500'}],'expected':'12'}, {'key':'unknown','inputs':[{'kind':'line','key':'asset','value':None}],'expected':None}]
        oracle=add_evidence(cls.a,cls.c.pk,'finance_oracle',json.dumps(rule['oracles']),'synthetic:SOCE-selected-line')
        rule['oracle_evidence_id']=oracle.pk;rules.append(rule)
        cls.configs['D06.rule_oracle_refs']=policy(cls.a,cls.c,'D06.rule_oracle_refs',rules,cls.e['policy_decision'])
        for key,purpose in analysis.PURPOSE.items():
            analysis.review(cls.a,cls.c.pk,purpose,cls.configs[key].pk,'Finance','approve',cls.e['finance_review'].pk,'Native rules reviewed',rev(cls.c))
        cls.m,cls.b,cls.r=pipeline(cls.a,cls.c,cls.source)
        cls.output_review=analysis.review(cls.reviewer,cls.c.pk,'output',cls.r.pk,'Finance','approve',cls.e['finance_review'].pk,'Independent selected source review',rev(cls.c))
        cls.oracle=add_evidence(cls.a,cls.c.pk,'finance_oracle',json.dumps({'C30':'12'}),'synthetic:selected-statement-oracle')
        cls.contract_value={'entity':cls.r.result['entity'],'period':cls.r.result['period'],'accounting_basis':'accrual','currency':'NGN','scope':'selected_statement_lines',
            'inputs':[{'destination':'C30','source_run':cls.r.pk,'source_review':cls.output_review.pk,'metric':'SOCE.I17','source_location':'SOCE!I17','source_kind':'soce','unit':'major_currency','source_sign':'equity_positive','destination_sign':'equity_positive','transfer':'identity'}],
            'oracle_evidence_id':cls.oracle.pk}
        cls.contract=cls.configure(cls.contract_value)
        projection=copy.deepcopy(cls.f['projection']);projection['audiences'][0].update(formula_keys=['C30'],bu_keys=[],include_company=True)
        policy(cls.a,cls.c,'D10.audience_projection_rules',projection,cls.e['policy_decision'])

    @classmethod
    def configure(cls,value):
        contract=policy(cls.a,cls.c,'D06.statement_contract',value,cls.e['policy_decision'])
        analysis.review(cls.reviewer,cls.c.pk,'formula',contract.pk,'Finance','approve',cls.e['finance_review'].pk,'Independent explicit statement declarations reviewed',rev(cls.c))
        return contract

    def assemble(self,contract=None):
        return statements.assemble(self.a,self.c.pk,self.r.pk,(contract or self.contract).pk,rev(self.c))

    def test_native_http_review_agent_report_receipt_and_identity(self):
        self.assertEqual(self.r.result['company']['SOCE.I17']['value'],'12.00')
        self.client.force_login(self.a)
        url=f'/cases/{self.c.pk}/finance/'
        self.assertContains(self.client.get(url),'Bind reviewed statement inputs')
        response=self.client.post(url,{'action':'statement','parent':self.r.pk,'contract':self.contract.pk,'revision':rev(self.c)})
        self.assertEqual(response.status_code,302)
        run=FinanceRun.objects.get(kind='statement');self.assertEqual(run.result['company']['C30']['value'],'12.00')
        self.assertEqual(self.assemble().pk,run.pk);self.assertEqual(run.statement_inputs.count(),1)
        self.assertFalse(run.result['whole_statement_certified']);self.assertFalse(analysis.certification_findings(run))
        from apps.agents.finance_analysis import investigate_finance
        log=investigate_finance(self.a,self.c.pk,run.pk,rev(self.c));self.assertFalse(log.result['approval_granted'])
        analysis.review(self.reviewer,self.c.pk,'output',run.pk,'Finance','approve',self.e['finance_review'].pk,'Selected lines reviewed only',rev(self.c))
        document=draft_report(self.a,self.c.pk,run.pk,self.template.pk,'internal',rev(self.c));self.assertFalse(preflight(document))
        reserve_publication(self.a,self.c.pk,document.pk,rev(self.c));self.assertTrue(run_publication_once())
        payload=json.dumps(PublicationReceipt.objects.get().payload)
        self.assertIn('12.00',payload);self.assertNotIn('SOCE!I17',payload);self.assertIn('full statement',payload)
        self.assertContains(self.client.get(url),'12.00')

    def test_mismatched_basis_period_units_and_signs_never_convert(self):
        for field,value in [('period','2026-09'),('accounting_basis','cash'),('currency','USD'),('entity','other')]:
            contract=copy.deepcopy(self.contract_value);contract[field]=value
            configured=self.configure(contract)
            with self.assertRaises(ValidationError):self.assemble(configured)
        contract=copy.deepcopy(self.contract_value);contract['inputs'][0]['source_sign']=' '
        with self.assertRaises(ValidationError):self.configure(contract)
        contract=copy.deepcopy(self.contract_value);contract['inputs'][0]['unit']='thousands_currency'
        configured=self.configure(contract)
        with self.assertRaises(ValidationError):self.assemble(configured)
        contract=copy.deepcopy(self.contract_value);contract['inputs'][0]['destination_sign']='equity_negative'
        run=self.assemble(self.configure(contract));self.assertEqual(run.result['company']['C30']['value'],'12.00');self.assertEqual(run.result['status'],'needs_attention')
        with self.assertRaises(ValidationError):analysis.review(self.a,self.c.pk,'output',run.pk,'Finance','approve',self.e['finance_review'].pk,'Cannot approve conversion',rev(self.c))

    def test_missing_oracle_sign_holds_and_review_withdrawal_invalidates(self):
        value=copy.deepcopy(self.contract_value);value['oracle_evidence_id']=None;value['inputs'][0]['source_sign']=None
        run=self.assemble(self.configure(value));self.assertEqual(run.result['status'],'needs_attention')
        with self.assertRaises(ValidationError):draft_report(self.a,self.c.pk,run.pk,self.template.pk,'internal',rev(self.c))
        self.configure(self.contract_value);run=self.assemble(self.configure(self.contract_value))
        analysis.review(self.reviewer,self.c.pk,'output',self.r.pk,'Finance','return',self.e['finance_review'].pk,'Withdrawn source review',rev(self.c))
        with self.assertRaises(ValidationError):analysis.ensure_current(run)

    def test_postgres_binding_immutability_and_foreign_review(self):
        run=self.assemble()
        with self.assertRaises(DatabaseError),transaction.atomic():FinanceStatementInput.objects.filter(statement=run).update(metric='forged')
        row=run.statement_inputs.get()
        with self.assertRaises(DatabaseError),transaction.atomic():
            FinanceStatementInput.objects.create(statement=run,source_run=self.r,source_review=self.output_review,destination='forged',metric=row.metric,contract=self.contract,declaration=row.declaration)
        value=copy.deepcopy(self.contract_value);value['inputs'][0]['source_review']=999999
        with self.assertRaises(ValidationError):self.configure(value)

    def test_existing_formula_proof_is_byte_identical(self):
        module=import_module('apps.workflows.migrations.0063_statement_verification')
        self.assertEqual(module.SQL.replace(module.REPLACEMENT,module.ORIGINAL),module.PREVIOUS)
        self.assertIn(module.query,module.REPLACEMENT)
        documents=import_module('apps.documents.migrations.0020_statement_scope')
        self.assertEqual(documents.SQL.replace(documents.BRANCH,''),documents.PREVIOUS)
        self.assertEqual(self.r.result['company']['revenue']['value'],'1000.00')

    def test_factory_selected_statement_reaches_native_receipts(self):
        from tests.factory_accounting_helpers import configured
        from apps.workflows import factory,factory_accounting
        from apps.workflows.models import HumanTask
        state=configured(self.a,self.c,self.e,self.source,self.template,METRICS,statement_contract_id=self.contract.pk)
        work=state['work']
        with self.assertRaises(DatabaseError),transaction.atomic():type(work).objects.filter(pk=work.pk).update(status='verified')
        for _ in range(5):
            factory.run_until_wait(work.pk);work.refresh_from_db()
            if work.status=='verified':break
            tasks=list(HumanTask.objects.filter(case=self.c,kind='factory_accounting_review',status='open'))
            self.assertTrue(tasks,work.finding)
            for task in tasks:
                task=factory_accounting.claim(self.reviewer,task.pk,task.revision)
                factory_accounting.decide(self.reviewer,task.pk,task.revision,'approve',self.e['finance_review'].pk,'Independent factory selected-lines approval')
        self.assertEqual(work.status,'verified',work.finding)
        self.assertEqual(PublicationReceipt.objects.count(),1)
        self.assertEqual(FinanceRun.objects.filter(kind='statement').count(),1)
        analysis.review(self.reviewer,self.c.pk,'output',self.r.pk,'Finance','return',self.e['finance_review'].pk,'Selected input review withdrawn after delivery',rev(self.c))
        with self.assertRaises(DatabaseError),transaction.atomic():type(work).objects.filter(pk=work.pk).update(status='verified')

    def test_committed_receipt_recovery_survives_statement_contract_withdrawal(self):
        from adapters.publications import PublicationTimeoutAfterAccept
        run=self.assemble()
        analysis.review(self.reviewer,self.c.pk,'output',run.pk,'Finance','approve',self.e['finance_review'].pk,'Selected lines reviewed',rev(self.c))
        document=draft_report(self.a,self.c.pk,run.pk,self.template.pk,'internal',rev(self.c))
        publication=reserve_publication(self.a,self.c.pk,document.pk,rev(self.c))
        run_publication_once(adapter=PublicationTimeoutAfterAccept())
        publication.job.refresh_from_db();self.assertEqual(publication.job.status,'unknown')
        receipt_ids=list(PublicationReceipt.objects.values_list('pk',flat=True));self.assertTrue(receipt_ids)
        transition(self.a,self.contract.pk,'revoked')
        self.assertTrue(preflight(document))
        run_publication_once(job_id=publication.job.pk,lookup_only=True)
        publication.job.refresh_from_db();self.assertEqual(publication.job.status,'confirmed')
        self.assertEqual(list(PublicationReceipt.objects.values_list('pk',flat=True)),receipt_ids)


    def test_configured_preparer_review_allowed_and_forbidden(self):
        from django.core.exceptions import PermissionDenied
        review=analysis.review(self.a,self.c.pk,'output',self.r.pk,'Finance','approve',self.e['finance_review'].pk,'Configured preparer review allowed',rev(self.c))
        value=copy.deepcopy(self.contract_value);value['inputs'][0]['source_review']=review.pk
        contract=policy(self.a,self.c,'D06.statement_contract',value,self.e['policy_decision'])
        analysis.review(self.a,self.c.pk,'formula',contract.pk,'Finance','approve',self.e['finance_review'].pk,'Configured preparer contract review allowed',rev(self.c))
        run=self.assemble(contract);self.assertFalse(analysis.certification_findings(run))
        authority=copy.deepcopy(self.f['authority'])
        for row in authority['finance']:
            if row['purpose'] in ['output','formula']:row['allow_preparer_review']=False
        policy(self.a,self.c,'D05.decision_action_matrix',authority,self.e['policy_decision'])
        analysis.review(self.reviewer,self.c.pk,'formula',self.configs['D06.rule_oracle_refs'].pk,'Finance','approve',self.e['finance_review'].pk,'Rule reviewed under current separation policy',rev(self.c))
        fresh=analysis.calculate(self.a,self.c.pk,self.b.pk,rev(self.c))
        with self.assertRaises(PermissionDenied):
            analysis.review(self.a,self.c.pk,'output',fresh.pk,'Finance','approve',self.e['finance_review'].pk,'Forbidden preparer review',rev(self.c))
        analysis.review(self.reviewer,self.c.pk,'output',fresh.pk,'Finance','approve',self.e['finance_review'].pk,'Configured distinct reviewer allowed',rev(self.c))
        with self.assertRaises(PermissionDenied):
            analysis.review(self.a,self.c.pk,'formula',contract.pk,'Finance','approve',self.e['finance_review'].pk,'Forbidden preparer contract review',rev(self.c))
        with self.assertRaises(ValidationError):analysis.ensure_current(run)

    def test_foreign_case_source_cannot_enter_contract(self):
        a,c,e,f,configs,source,template,recipient=fixture(username='foreign-statement-maker',recipient_username='foreign-statement-reader')
        m,b,run=pipeline(a,c,source)
        review=analysis.review(a,c.pk,'output',run.pk,'Finance','approve',e['finance_review'].pk,'Foreign native source reviewed',rev(c))
        value=copy.deepcopy(self.contract_value);value['inputs'][0].update(source_run=run.pk,source_review=review.pk)
        with self.assertRaises(ValidationError):self.configure(value)


    def test_executing_actor_read_revocations_hold_assembly_and_currentness(self):
        from django.core.exceptions import PermissionDenied
        run=self.assemble()
        for action in ['finance.read','case.read']:
            grant=Grant.objects.get(case=self.c,user=self.a,action=action)
            grant.active=False;grant.save()
            with self.assertRaises(PermissionDenied):self.assemble()
            with self.assertRaises(PermissionDenied):analysis.ensure_current(run)
            grant.active=True;grant.save()
        self.assertFalse(analysis.certification_findings(run))


    def test_selected_statement_policy_holds_only_statement_not_upstream_calculation(self):
        from datetime import timedelta
        from django.utils import timezone
        from tests.factory_accounting_helpers import configured
        from apps.workflows import factory
        source=analysis.capture_source(self.a,self.c.pk,self.source.batch_id,self.source.entity,'accrual',timezone.now()-timedelta(minutes=1),'complete',self.source.control_total,self.e['finance_source'].pk,rev(self.c))
        analysis.review(self.a,self.c.pk,'source',source.pk,'Finance','approve',self.e['finance_review'].pk,'Current source accepted',rev(self.c))
        transition(self.a,self.contract.pk,'revoked')
        work=configured(self.a,self.c,self.e,source,self.template,METRICS,statement_contract_id=self.contract.pk)['work']
        factory.run_until_wait(work.pk);work.refresh_from_db()
        for kind in ['mapping','allocation','formula']:self.assertTrue(FinanceRun.objects.filter(source=source,kind=kind).exists(),kind+': '+work.finding)
        self.assertFalse(FinanceRun.objects.filter(source=source,kind='statement').exists())
        from apps.workflows.models import HumanTask
        from apps.workflows import factory_accounting
        task=HumanTask.objects.get(case=self.c,kind='factory_accounting_review',status='open')
        task=factory_accounting.claim(self.a,task.pk,task.revision)
        factory_accounting.decide(self.a,task.pk,task.revision,'approve',self.e['finance_review'].pk,'Native base output reviewed before statement policy exists')
        factory.run_until_wait(work.pk);work.refresh_from_db()
        self.assertEqual(work.status,'configuration_needed');self.assertIn('D06.statement_contract',work.finding)
        self.assertFalse(PublicationReceipt.objects.exists())

    def test_multi_source_statement_and_agent_preserve_selected_evidence_inventory(self):
        from datetime import timedelta
        from django.utils import timezone
        from apps.finance.services import capture_import,validate_import
        from apps.agents.finance_analysis import investigate_finance
        lines=self.f['csv'].splitlines();csv='\n'.join([lines[0],*reversed(lines[1:])])+'\n'
        source_evidence=add_evidence(self.a,self.c.pk,'financial_input',csv,'synthetic:second-reviewed-note-export')
        context_evidence=add_evidence(self.a,self.c.pk,'finance_source','Second synthetic note context','synthetic:second-note-context')
        batch=capture_import(self.a,self.c.pk,source_evidence.pk,rev(self.c));validate_import(self.a,self.c.pk,batch.pk,rev(self.c))
        source=analysis.capture_source(self.a,self.c.pk,batch.pk,self.source.entity,'accrual',timezone.now()-timedelta(minutes=1),'complete',self.source.control_total,context_evidence.pk,rev(self.c))
        analysis.review(self.a,self.c.pk,'source',source.pk,'Finance','approve',self.e['finance_review'].pk,'Second note source accepted',rev(self.c))
        m,b,other=pipeline(self.a,self.c,source)
        review=analysis.review(self.reviewer,self.c.pk,'output',other.pk,'Finance','approve',self.e['finance_review'].pk,'Exact second note output reviewed',rev(self.c))
        value=copy.deepcopy(self.contract_value)
        value['inputs'].append(dict(value['inputs'][0],destination='NoteA',source_run=other.pk,source_review=review.pk,metric='asset_display',source_location='AssetNote!B4',source_kind='note',unit='thousands_currency',source_sign='asset_positive',destination_sign='asset_positive'))
        oracle=add_evidence(self.a,self.c.pk,'finance_oracle',json.dumps({'C30':'12','NoteA':'0.50'}),'synthetic:multi-source-selected-lines')
        value['oracle_evidence_id']=oracle.pk
        run=self.assemble(self.configure(value))
        expected=set(self.r.result['source_evidence_ids'])|set(other.result['source_evidence_ids'])|{oracle.pk}
        self.assertEqual(set(run.result['source_evidence_ids']),expected)
        self.assertEqual(run.result['anchor_source_evidence_ids'],self.r.result['source_evidence_ids'])
        log=investigate_finance(self.a,self.c.pk,run.pk,rev(self.c))
        self.assertTrue(expected <= {item['id'] for item in log.result['citations']})
        selected=next(row for row in log.result['statement_inputs'] if row['destination']=='NoteA')
        self.assertEqual(selected['source_run'],other.pk);self.assertEqual(set(selected['source_evidence_ids']),set(other.result['source_evidence_ids']))

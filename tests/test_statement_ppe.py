"""Synthetic native F07 -> F09 identity transfer; no owner accounting policy claim."""
import copy,json
from django.test import TestCase
from django.core.exceptions import ValidationError,PermissionDenied
from django.db import connection,transaction,DatabaseError
from apps.finance import analysis,ppe,statements
from apps.finance.models import FinanceStatementPPEInput,FinanceRun
from apps.policy.services import transition,reference_values
from apps.policy.statement_ppe import mapping
from apps.policy.statement_completeness import inventory,METHOD
from apps.identity.models import Grant
from tests import ppe_helpers as ph
from tests.finance_analysis_helpers import pipeline,policy
from tests.schedule_helpers import evidence
from tests.helpers import rev

class StatementPPETests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.f=ph.fixture();f=cls.f
        cls.work=ph.prepare(f);cls.review=ph.review(f,cls.work)
        _,_,cls.anchor=pipeline(f['actor'],f['case'],f['source'])
        analysis.review(f['reviewer'],f['case'].pk,'output',cls.anchor.pk,'Finance','approve',f['e']['finance_review'].pk,'Synthetic anchor output reviewed',rev(f['case']))
        cls.value={**{k:cls.anchor.result[k] for k in ['entity','period','currency']},'accounting_basis':'accrual',
            'scope':'selected_statement_lines','inputs':[], 'oracle_evidence_id':None,'completeness':None}
        cls.row={'source_type':'ppe_schedule','schedule_id':cls.work.pk,'schedule_sha256':cls.work.sha256,
            'register_id':f['register'].pk,'schedule_review_id':cls.review.pk,'destination':'Note8','metric':'book_value',
            'source_location':'totals.book_value','source_kind':'note','unit':'major_currency',
            'source_sign':'asset_positive','destination_sign':'asset_positive','transfer':'identity',
            'mapping_evidence_id':1,'coverage':{**{k:cls.work.result['scope'][k] for k in ['period_start','period_end','label_as_of']},
            'method':'explicit_reviewed_coverage','explanation':'Synthetic October selected-line snapshot covering 1–20 October only; no extrapolation'}}

    def configure(self,row=None,value=None):
        f=self.f;v=copy.deepcopy(value or self.value);r=copy.deepcopy(row or self.row)
        r['mapping_evidence_id']=evidence(f,'policy_decision',json.dumps(mapping(r,v))).pk
        v['inputs']=[r]
        amount={'cost':'1000','accumulated':'500.00','book_value':'500.00','charge':'100.00'}[r['metric']]
        v['oracle_evidence_id']=evidence(f,'finance_oracle',json.dumps({r['destination']:amount})).pk
        v['completeness']={'inventory_evidence_id':1,'layout':[{k:r[k] for k in ['destination','source_kind','unit','destination_sign']}],
            'checks':[{'key':'ppe_selected','method':METHOD,'destinations':[r['destination']],'oracle_evidence_id':None}]}
        oracle={**{k:v[k] for k in ['entity','period','currency','accounting_basis']},'check_key':'ppe_selected','method':METHOD,
            'values':{r['destination']:{'value':amount,'unit':r['unit']}}}
        v['completeness']['checks'][0]['oracle_evidence_id']=evidence(f,'finance_oracle',json.dumps(oracle)).pk
        v['completeness']['inventory_evidence_id']=evidence(f,'policy_decision',json.dumps(inventory(v))).pk
        c=policy(f['actor'],f['case'],'D06.statement_contract',v,f['e']['policy_decision'])
        analysis.review(f['reviewer'],f['case'].pk,'formula',c.pk,'Finance','approve',f['e']['finance_review'].pk,'Independent explicit PPE identity mapping reviewed',rev(f['case']))
        return c

    def assemble(self,contract=None):
        f=self.f;c=contract or self.configure()
        return statements.assemble(f['actor'],f['case'].pk,self.anchor.pk,c.pk,rev(f['case']))

    def test_exact_native_total_inventory_review_and_source_evidence(self):
        run=self.assemble();self.assertEqual(connection.vendor,'postgresql')
        self.assertEqual(run.result['company']['Note8']['value'],'500.00')
        self.assertEqual(run.result['status'],'complete');self.assertFalse(run.result['whole_statement_certified'])
        self.assertEqual(run.statement_inputs.count(),0)
        row=run.statement_ppe_inputs.get();self.assertEqual(row.schedule_id,self.work.pk);self.assertEqual(row.schedule_review_id,self.review.pk)
        self.assertEqual(row.declaration['source_location'],'totals.book_value')
        self.assertIn(self.f['register'].evidence_id,run.result['source_evidence_ids'])
        self.assertIn(self.review.evidence_id,run.result['source_evidence_ids'])
        self.assertEqual(statements.ensure_current(run),run)
        self.assertFalse(analysis.certification_findings(run))
        self.assertEqual(self.assemble(row.contract).pk,run.pk)

    def test_mixed_formula_and_ppe_inputs_preserve_independent_inventories(self):
        c=self.configure();v=copy.deepcopy(reference_values(c)[0]);f=self.f
        review=analysis.current_review(f['case'],'output',run=self.anchor)
        row={'destination':'Revenue','source_run':self.anchor.pk,'source_review':review['id'],
             'metric':'revenue','source_location':'Ledger!Revenue','source_kind':'note','unit':'major_currency',
             'source_sign':'income_positive','destination_sign':'income_positive','transfer':'identity'}
        v['inputs'].append(row)
        self.assertEqual(self.anchor.result['company']['revenue']['value'],'1000.00')
        v['oracle_evidence_id']=evidence(f,'finance_oracle',json.dumps({'Note8':'500.00','Revenue':'1000.00'})).pk
        v['completeness']['layout'].append({k:row[k] for k in ['destination','source_kind','unit','destination_sign']})
        check=v['completeness']['checks'][0];check['destinations'].append('Revenue')
        oracle={**{k:v[k] for k in ['entity','period','currency','accounting_basis']},'check_key':check['key'],'method':METHOD,
                'values':{'Note8':{'value':'500.00','unit':'major_currency'},'Revenue':{'value':'1000.00','unit':'major_currency'}}}
        check['oracle_evidence_id']=evidence(f,'finance_oracle',json.dumps(oracle)).pk
        v['completeness']['inventory_evidence_id']=evidence(f,'policy_decision',json.dumps(inventory(v))).pk
        c=policy(f['actor'],f['case'],'D06.statement_contract',v,f['e']['policy_decision'])
        analysis.review(f['reviewer'],f['case'].pk,'formula',c.pk,'Finance','approve',f['e']['finance_review'].pk,'Independent mixed native sources reviewed',rev(f['case']))
        run=self.assemble(c)
        self.assertEqual(run.statement_inputs.count(),1);self.assertEqual(run.statement_ppe_inputs.count(),1)
        self.assertEqual(run.result['company']['Revenue']['value'],'1000.00')
        self.assertEqual(run.result['company']['Note8']['value'],'500.00')
        self.assertEqual(statements.ensure_current(run),run);self.assertFalse(run.result['whole_statement_certified'])

    def test_all_existing_totals_transfer_without_arithmetic(self):
        for metric in ['cost','accumulated','book_value','charge']:
            row=copy.deepcopy(self.row);row.update(metric=metric,source_location='totals.'+metric)
            run=self.assemble(self.configure(row))
            self.assertEqual(run.result['company']['Note8']['value'],self.work.result['totals'][metric])

    def test_invalid_field_hash_review_unit_sign_and_dates_rejected(self):
        for key,value in [('source_location','Notes8!B4'),('schedule_sha256','0'*64),('schedule_review_id',self.review.pk+999),
                          ('register_id',self.f['register'].pk+999),('unit','thousands_currency'),('source_sign',None),('destination_sign','negative')]:
            row=copy.deepcopy(self.row);row[key]=value
            with self.subTest(key=key),self.assertRaises(ValidationError):self.configure(row)
        row=copy.deepcopy(self.row);row['coverage']['period_end']='2026-09-30'
        with self.assertRaises(ValidationError):self.configure(row)

    def test_mapping_evidence_cannot_be_substituted_or_note_only(self):
        c=self.configure();v=reference_values(c)[0];v['inputs'][0]['mapping_evidence_id']=self.f['e']['policy_decision'].pk
        with self.assertRaises(ValidationError):policy(self.f['actor'],self.f['case'],'D06.statement_contract',v,self.f['e']['policy_decision'])
        v=copy.deepcopy(self.value);v['inputs']=[self.row];v.pop('completeness')
        with self.assertRaises(ValidationError):policy(self.f['actor'],self.f['case'],'D06.statement_contract',v,self.f['e']['policy_decision'])

    def test_period_basis_entity_and_currency_are_explicit(self):
        for key,change in [('entity','other'),('currency','USD'),('period','2026-09'),('accounting_basis','cash')]:
            value=copy.deepcopy(self.value);value[key]=change
            with self.subTest(key=key),self.assertRaises(ValidationError):self.assemble(self.configure(value=value))

    def test_schedule_review_revocation_invalidates_without_history_change(self):
        run=self.assemble();saved=copy.deepcopy(run.result)
        ph.review(self.f,self.work,verdict='revoke')
        with self.assertRaises(ValidationError):statements.ensure_current(run)
        run.refresh_from_db();self.assertEqual(run.result,saved);self.assertEqual(run.statement_ppe_inputs.count(),1)

    def test_source_successor_invalidates(self):
        run=self.assemble();body=copy.deepcopy(self.f['ppe']['body']);body['completeness']='partial';ph.capture(self.f,body)
        with self.assertRaises(ValidationError):statements.ensure_current(run)

    def test_schedule_successor_invalidates(self):
        run=self.assemble()
        # Same reviewed register, but a changed selected comparison creates a successor.
        ph.prepare(self.f,ledger=False)
        with self.assertRaises(ValidationError):statements.ensure_current(run)

    def test_policy_and_reviewer_withdrawal_invalidate(self):
        run=self.assemble();Grant.objects.filter(case=self.f['case'],user=self.f['reviewer'],action='ppe.review').update(active=False)
        with self.assertRaises((ValidationError,PermissionDenied)):statements.ensure_current(run)

    def test_configuration_withdrawal_invalidate(self):
        run=self.assemble();c=ph.policy(self.f,'F07.calculation_rules',self.f['ppe']['calculation']);transition(self.f['actor'],c.pk,'revoked')
        with self.assertRaises(ValidationError):statements.ensure_current(run)

    def test_immutable_inventory_and_forged_insert_denied(self):
        run=self.assemble();row=run.statement_ppe_inputs.get()
        with self.assertRaises(DatabaseError),transaction.atomic():FinanceStatementPPEInput.objects.filter(pk=row.pk).update(metric='charge')
        with self.assertRaises(DatabaseError),transaction.atomic():FinanceStatementPPEInput.objects.filter(pk=row.pk).delete()
        with self.assertRaises(DatabaseError),transaction.atomic():FinanceStatementPPEInput.objects.create(statement=run,schedule=self.work,schedule_review=self.review,
            destination='forged',metric='book_value',contract=row.contract,declaration=row.declaration)

    def test_http_get_is_read_only_and_revoked_reader_cannot_see_ppe_output(self):
        run=self.assemble();f=self.f;self.client.force_login(f['actor']);count=FinanceRun.objects.count()
        url=f'/cases/{f["case"].pk}/finance/'
        analysis.review(f['reviewer'],f['case'].pk,'output',run.pk,'Finance','approve',f['e']['finance_review'].pk,'PPE_PRIVATE_REVIEW_SENTINEL',rev(f['case']))
        response=self.client.get(url);self.assertContains(response,'PPE schedule');self.assertEqual(FinanceRun.objects.count(),count)
        Grant.objects.filter(case=f['case'],user=f['actor'],action='ppe.read').update(active=False)
        self.assertNotContains(self.client.get(url),'PPE schedule '+str(self.work.pk))
        self.assertNotContains(self.client.get(url),'PPE_PRIVATE_REVIEW_SENTINEL')

    def test_recipient_source_permission_is_current(self):
        from apps.finance.statement_ppe import recipient_access
        run=self.assemble();f=self.f;recipient_access(run,[f['reviewer'].pk])
        Grant.objects.filter(case=f['case'],user=f['reviewer'],action='ppe.read').update(active=False)
        with self.assertRaises(PermissionDenied):recipient_access(run,[f['reviewer'].pk])

    def test_exact_calendar_month_does_not_silently_extend_source_dates(self):
        row=copy.deepcopy(self.row);row['coverage']['method']='exact_calendar_month'
        with self.assertRaises(ValidationError):self.configure(row)

    def test_cross_case_schedule_cannot_be_selected(self):
        other=ph.fixture(username='other-owner',reviewer_username='other-reviewer',recipient_username='other-recipient')
        work=ph.prepare(other);review=ph.review(other,work)
        row=copy.deepcopy(self.row);row.update(schedule_id=work.pk,schedule_sha256=work.sha256,schedule_review_id=review.pk,register_id=other['register'].pk)
        with self.assertRaises(ValidationError):self.configure(row)

    def test_agent_and_history_respect_current_source_read_access(self):
        from apps.agents.finance_analysis import investigate_finance
        run=self.assemble();f=self.f
        log=investigate_finance(f['actor'],f['case'].pk,run.pk,rev(f['case']))
        self.assertEqual(log.result['statement_inputs'][0]['schedule_id'],self.work.pk)
        self.client.force_login(f['actor']);url=f'/cases/{f["case"].pk}/finance/'
        self.assertContains(self.client.get(url),'Cited Finance investigation #'+str(log.pk))
        Grant.objects.filter(case=f['case'],user=f['actor'],action='ppe.read').update(active=False)
        self.assertNotContains(self.client.get(url),'Cited Finance investigation #'+str(log.pk))
        with self.assertRaises(PermissionDenied):investigate_finance(f['actor'],f['case'].pk,run.pk,rev(f['case']))

    def test_migrated_sql_currentness_reuses_native_ppe_guards(self):
        run=self.assemble()
        with connection.cursor() as cursor:
            cursor.execute('SELECT psl_statement_ppe_current(%s)',[run.pk]);self.assertTrue(cursor.fetchone()[0])
        ph.review(self.f,self.work,verdict='revoke')
        with connection.cursor() as cursor:
            cursor.execute('SELECT psl_statement_ppe_current(%s)',[run.pk]);self.assertFalse(cursor.fetchone()[0])

    def test_migrated_factory_native_chain_and_receipt(self):
        # Uses actual migrated 0079/0030 guards without test-local replacement.
        from tests.factory_accounting_helpers import configured
        from tests.finance_analysis_helpers import METRICS
        from apps.documents.models import Template,PublicationReceipt
        from apps.workflows import factory,factory_accounting
        from apps.workflows.models import HumanTask
        f=self.f;c=self.configure()
        for action in ['case.read','ppe.read']:Grant.objects.get_or_create(case=f['case'],user=f['recipient'],action=action)
        projection=copy.deepcopy(f['base']['projection']);projection['audiences'][0].update(formula_keys=['Note8'],bu_keys=[],include_company=True)
        policy(f['actor'],f['case'],'D10.audience_projection_rules',projection,f['e']['policy_decision'])
        template=Template.objects.get(case=f['case'],definition__document_type='finance_report')
        state=configured(f['actor'],f['case'],f['e'],f['source'],template,METRICS,statement_contract_id=c.pk)
        work=state['work']
        for _ in range(5):
            factory.run_until_wait(work.pk);work.refresh_from_db()
            if work.status=='verified':break
            tasks=list(HumanTask.objects.filter(case=f['case'],kind='factory_accounting_review',status='open'))
            self.assertTrue(tasks,work.finding)
            for task in tasks:
                task=factory_accounting.claim(f['reviewer'],task.pk,task.revision)
                factory_accounting.decide(f['reviewer'],task.pk,task.revision,'approve',f['e']['finance_review'].pk,'Independent selected PPE statement output review')
        self.assertEqual(work.status,'verified',work.finding)
        self.assertEqual(PublicationReceipt.objects.count(),1)
        run=FinanceRun.objects.get(kind='statement');self.assertEqual(run.statement_ppe_inputs.get().schedule_id,self.work.pk)
        self.assertFalse(run.result['whole_statement_certified'])
        Grant.objects.filter(case=f['case'],user=f['recipient'],action='ppe.read').update(active=False)
        with self.assertRaises(PermissionDenied):factory_accounting.verified(work,state['value'])
        with self.assertRaises(DatabaseError),transaction.atomic():type(work).objects.filter(pk=work.pk).update(status='verified')
        Grant.objects.filter(case=f['case'],user=f['recipient'],action='ppe.read').update(active=True)
        ph.review(f,self.work,verdict='revoke')
        with self.assertRaises(DatabaseError),transaction.atomic():type(work).objects.filter(pk=work.pk).update(status='verified')

    def test_native_publication_requires_source_reader_and_historical_inbox_rechecks(self):
        from apps.finance.documents import draft_report
        from apps.documents.models import Template,PublicationReceipt
        from apps.documents.controlled import reserve_publication
        from apps.documents.delivery import run_publication_once
        f=self.f;run=self.assemble()
        projection=copy.deepcopy(f['base']['projection']);projection['audiences'][0].update(formula_keys=['Note8'],bu_keys=[],include_company=True)
        policy(f['actor'],f['case'],'D10.audience_projection_rules',projection,f['e']['policy_decision'])
        analysis.review(f['reviewer'],f['case'].pk,'output',run.pk,'Finance','approve',f['e']['finance_review'].pk,'Independent selected PPE line reviewed',rev(f['case']))
        template=Template.objects.get(case=f['case'],definition__document_type='finance_report')
        document=draft_report(f['actor'],f['case'].pk,run.pk,template.pk,'internal',rev(f['case']))
        from apps.core.evidence_access import restricted,public_evidence,public_agent_runs
        from apps.core.models import Evidence
        from apps.agents.models import AgentRun
        from apps.agents.finance_analysis import investigate_finance
        from apps.documents.controlled import create_version
        derived=Evidence.objects.get(case=f['case'],source='derived:ppe-statement:'+str(run.pk))
        self.assertTrue(restricted(derived));self.assertFalse(public_evidence(Evidence.objects.filter(pk=derived.pk)).exists())
        log=investigate_finance(f['actor'],f['case'].pk,run.pk,rev(f['case']))
        self.assertFalse(public_agent_runs(AgentRun.objects.filter(pk=log.pk)).exists())
        with self.assertRaises(ValidationError):create_version(f['actor'],f['case'].pk,template.pk,'Forbidden generic PPE copy','internal',document.fields,rev(f['case']))
        with self.assertRaises(PermissionDenied):reserve_publication(f['actor'],f['case'].pk,document.pk,rev(f['case']))
        for action in ['case.read','ppe.read']:Grant.objects.get_or_create(case=f['case'],user=f['recipient'],action=action)
        reserve_publication(f['actor'],f['case'].pk,document.pk,rev(f['case']));self.assertTrue(run_publication_once())
        receipt=PublicationReceipt.objects.get();payload=json.dumps(receipt.payload)
        self.assertIn('500.00',payload);self.assertNotIn('asset_id',payload);self.assertNotIn('opening_cost',payload)
        self.client.force_login(f['recipient'])
        from django.urls import reverse
        url=reverse('document_inbox')
        self.assertContains(self.client.get(url),'500.00')
        Grant.objects.filter(case=f['case'],user=f['recipient'],action='ppe.read').update(active=False)
        self.assertNotContains(self.client.get(url),'500.00')

    def test_output_review_requires_current_ppe_source_read_access(self):
        run=self.assemble();f=self.f
        Grant.objects.filter(case=f['case'],user=f['reviewer'],action='ppe.read').update(active=False)
        with self.assertRaises(PermissionDenied):analysis.review(f['reviewer'],f['case'].pk,'output',run.pk,'Finance','approve',f['e']['finance_review'].pk,'No source access',rev(f['case']))

    def prepared_document(self):
        from apps.finance.documents import draft_report
        from apps.finance.models import FinanceStatementPPEProjection
        from apps.documents.models import Template
        f=self.f;run=self.assemble()
        projection=copy.deepcopy(f['base']['projection']);projection['audiences'][0].update(formula_keys=['Note8'],bu_keys=[],include_company=True)
        policy(f['actor'],f['case'],'D10.audience_projection_rules',projection,f['e']['policy_decision'])
        analysis.review(f['reviewer'],f['case'].pk,'output',run.pk,'Finance','approve',f['e']['finance_review'].pk,'Native PPE line reviewed',rev(f['case']))
        template=Template.objects.get(case=f['case'],definition__document_type='finance_report')
        document=draft_report(f['actor'],f['case'].pk,run.pk,template.pk,'internal',rev(f['case']))
        return run,FinanceStatementPPEProjection.objects.get(run=run),document

    def test_projection_sql_identity_creator_hash_rebinding_and_immutability(self):
        from apps.finance.models import FinanceStatementPPEProjection
        from apps.core.services import add_evidence
        run,proof,document=self.prepared_document();f=self.f
        for change in ['value','creator','run','hash']:
            data=copy.deepcopy(proof.projection)
            if change=='value':data['company']['Note8']['value']='999'
            creator=f['reviewer'] if change=='creator' else f['actor']
            e=add_evidence(creator,f['case'].pk,'finance_report_snapshot',json.dumps(data,sort_keys=True),'derived:ppe-statement:'+str(run.pk),rev(f['case']))
            with self.subTest(change=change),self.assertRaises(DatabaseError),transaction.atomic():
                FinanceStatementPPEProjection.objects.create(run=self.anchor if change=='run' else run,evidence=e,actor=f['actor'],
                    snapshot=proof.snapshot,projection=data,payload_hash='0'*64 if change=='hash' else e.sha256)
        with self.assertRaises(DatabaseError),transaction.atomic():FinanceStatementPPEProjection.objects.filter(pk=proof.pk).update(run=self.anchor)
        with self.assertRaises(DatabaseError),transaction.atomic():FinanceStatementPPEProjection.objects.filter(pk=proof.pk).delete()

    def test_cross_case_projection_and_generic_private_forgery_are_denied(self):
        from apps.finance.models import FinanceStatementPPEProjection,FinanceDocumentBinding
        from apps.finance import statement_ppe_documents as native
        from apps.core.services import add_evidence
        from apps.documents.controlled import create_version
        run,proof,document=self.prepared_document();f=self.f
        other=ph.fixture(username='projection-foreign',reviewer_username='projection-foreign-reviewer',recipient_username='projection-foreign-recipient')
        foreign=add_evidence(other['actor'],other['case'].pk,'finance_report_snapshot',proof.evidence.body,'derived:ppe-statement:'+str(run.pk),rev(other['case']))
        with self.assertRaises(DatabaseError),transaction.atomic():FinanceStatementPPEProjection.objects.create(run=run,evidence=foreign,actor=f['actor'],snapshot=proof.snapshot,projection=proof.projection,payload_hash=foreign.sha256)
        fake=add_evidence(f['actor'],f['case'].pk,'finance_report_snapshot',proof.evidence.body,'derived:ppe-statement:'+str(run.pk),rev(f['case']))
        fields=copy.deepcopy(document.fields)
        for field in fields.values():field['evidence_ids']=[fake.pk]
        with self.assertRaises(ValidationError):create_version(f['actor'],f['case'].pk,document.template_id,'Forged private snapshot','internal',fields,rev(f['case']))
        unsaved=FinanceStatementPPEProjection(run=run,evidence=fake,actor=f['actor'],snapshot=proof.snapshot,projection=proof.projection,payload_hash=fake.sha256)
        with self.assertRaises(ValidationError):native.create_version(f['actor'],unsaved,document.template,document.document.title,'internal',fields,rev(f['case']))
        with self.assertRaises(ValidationError):native.create_version(f['actor'],proof,document.template,document.document.title,'internal',fields,rev(f['case']))
        public=evidence(f,'document_source','Not an authorized native PPE projection')
        for field in fields.values():field['evidence_ids']=[public.pk]
        forged=create_version(f['actor'],f['case'].pk,document.template_id,document.document.title,'internal',fields,rev(f['case']))
        with self.assertRaises(DatabaseError),transaction.atomic():FinanceDocumentBinding.objects.create(version=forged,run=run,snapshot=proof.snapshot)

    def test_private_projection_gets_preserve_all_rows_and_generic_agent_hiding_is_model_bound(self):
        from tests.test_statement_completeness import StatementCompletenessTests
        from apps.core.evidence_access import public_agent_runs,public_evidence
        from apps.agents.models import AgentRun
        from django.urls import reverse
        run,proof,document=self.prepared_document();f=self.f
        log=AgentRun.objects.create(case=f['case'],actor=f['actor'],evidence=f['e']['finance_source'],provider='deterministic-finance-lineage-v1',process_id='F09',result={'run':run.pk,'company_metrics':run.result['company']})
        self.assertFalse(public_agent_runs(AgentRun.objects.filter(pk=log.pk)).exists())
        ordinary=AgentRun.objects.create(case=f['case'],actor=f['actor'],evidence=f['e']['finance_source'],provider='deterministic-finance-lineage-v1',process_id='F09',result={'run':self.anchor.pk,'company_metrics':self.anchor.result['company']})
        self.assertTrue(public_agent_runs(AgentRun.objects.filter(pk=ordinary.pk)).exists())
        self.assertFalse(public_evidence(type(proof.evidence).objects.filter(pk=proof.evidence_id)).exists())
        from apps.core.evidence_access import ppe_statement_private
        instance=type(proof.evidence).objects.get(pk=proof.evidence_id)
        instance.source='no-marker-on-this-reader-instance'
        self.assertTrue(ppe_statement_private(instance))
        self.client.force_login(f['actor'])
        # Warm any lazy session/permission presentation before the exact read-only inventory.
        self.client.get(f'/cases/{f["case"].pk}/finance/')
        before=StatementCompletenessTests.rowsets(self)
        self.client.get(f'/cases/{f["case"].pk}/finance/')
        self.client.get(f'/cases/{f["case"].pk}/')
        self.client.get(f'/cases/{f["case"].pk}/documents/')
        self.client.get(reverse('document_inbox'))
        self.assertEqual(before,StatementCompletenessTests.rowsets(self))

    def test_projection_creator_authority_withdrawal_matches_native_and_sql(self):
        from apps.finance.statement_ppe_documents import validate
        run,proof,document=self.prepared_document();f=self.f
        Grant.objects.filter(case=f['case'],user=f['actor'],action='document.draft').update(active=False)
        with self.assertRaises(PermissionDenied):validate(proof)
        with connection.cursor() as cursor:
            cursor.execute('SELECT psl_statement_ppe_document_valid(%s,%s,%s::jsonb)',[run.pk,document.pk,json.dumps(proof.snapshot)])
            self.assertFalse(cursor.fetchone()[0])

    def test_native_ledger_basis_cannot_be_overridden_by_mapping_declaration(self):
        value=copy.deepcopy(self.value);value['accounting_basis']='cash'
        with self.assertRaisesMessage(ValidationError,'native ledger comparison basis differs'):self.configure(value=value)

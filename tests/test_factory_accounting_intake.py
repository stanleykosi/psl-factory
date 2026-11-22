"""F02 supplied-file entry into native accounting, with explicit local receipts."""
import json
from pathlib import Path
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import connection
from django.test import TestCase, Client
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone
from apps.core.models import Audit, Case, Evidence
from apps.core.services import add_evidence
from apps.finance.models import FinancialImport, FinanceSource, FinanceRun, ImportValidation
from apps.finance.services import capture_import
from apps.identity.models import Grant
from apps.policy.services import transition
from apps.workflows import factory_accounting_intake as intake, factory_accounting as accounting, factory
from apps.workflows.models import FactoryWork, HumanTask
from tests.finance_analysis_helpers import fixture, policy, METRICS, declared_units
from tests.helpers import rev


class AccountingSuppliedIntakeTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.data=fixture(username='supplied-maker',recipient_username='supplied-reader')

    def test_workspace_selector_uses_named_batched_exact_grants(self):
        actor, case, *_ = self.data
        self.client.force_login(actor)
        url = reverse('factory_create') + '?definition=finance-accounts/v1'
        listed = self.client.get(url)
        self.assertNotContains(listed, 'Case object')
        with CaptureQueriesContext(connection) as baseline:
            self.client.get(url)
        hidden = Case.objects.create(tenant=case.tenant, title='SAMPLE hidden accounting selector', kind='project', synthetic=True)
        Grant.objects.create(case=hidden, user=actor, action='case.read')
        workspaces = Case.objects.bulk_create([
            Case(tenant=case.tenant, title=f'SAMPLE accounting selector {index}', kind='project', synthetic=True)
            for index in range(24)
        ])
        Grant.objects.bulk_create([Grant(case=item, user=actor, action=action) for item in workspaces
                                   for action in ('case.read', 'factory.start', 'finance.read', 'evidence.add')])
        with CaptureQueriesContext(connection) as expanded:
            listed = self.client.get(url)
        self.assertLessEqual(len(expanded), len(baseline) + 2)
        self.assertContains(listed, 'SAMPLE accounting selector 23')
        self.assertNotContains(listed, hidden.title)
        self.assertEqual(self.client.get(url + '&case=' + str(hidden.pk)).status_code, 404)

    def supplied(self,body=None,with_units=False):
        a,c,e,values,configs,source,template,recipient=self.data
        evidence=add_evidence(a,c.pk,'financial_input',body if body is not None else values['csv']+'\n','synthetic:supplied-export',rev(c))
        context={'entity':source.entity,'period':'2026-10','currency':source.batch.rows[0]['currency'],
                 'accounting_basis':source.accounting_basis,'extracted_at':source.extracted_at,
                 'completeness':'complete','control_total':source.control_total,'source_evidence_id':source.evidence_id}
        if with_units:
            # Bind explicit synthetic units to this exact supplied import, not the old source.
            batch=capture_import(a,c.pk,evidence.pk,rev(c))
            context['unit_declaration']=declared_units(a,c,batch)
        return evidence,context

    def submit(self,key='submission-1',body=None,changes=None,with_units=True):
        a,c,*_=self.data;evidence,context=self.supplied(body,with_units=with_units)
        context.update(changes or {})
        return intake.submit(a,c.pk,key,evidence.pk,context,'Supplied report',rev(c)),evidence,context

    def test_repeat_submission_receipts_share_import_source_and_work(self):
        a,c,*_=self.data
        result,evidence,context=self.submit()
        counts=(FinancialImport.objects.count(),FinanceSource.objects.count(),FactoryWork.objects.count())
        second=intake.submit(a,c.pk,'submission-2',evidence.pk,context,'Supplied report',rev(c))
        self.assertEqual(result['status'],'started');self.assertEqual(second['work'],result['work'])
        self.assertNotEqual(second['receipt'],result['receipt'])
        self.assertEqual(counts,(FinancialImport.objects.count(),FinanceSource.objects.count(),FactoryWork.objects.count()))
        self.assertEqual(Audit.objects.filter(action=intake.RECEIPT).count(),2)
        again=intake.submit(a,c.pk,'submission-1',evidence.pk,context,'Supplied report',rev(c))
        self.assertEqual(again,result);self.assertEqual(Audit.objects.filter(action=intake.RECEIPT).count(),2)
        with self.assertRaises(ValidationError):intake.submit(a,c.pk,'submission-1',evidence.pk,context,'Changed report',rev(c))

    def test_missing_conventions_preserves_import_then_resumes(self):
        a,c,e,values,configs,*_=self.data
        transition(a,configs['D06.source_schema_ref'].pk,'revoked')
        result,_,_=self.submit()
        self.assertEqual(result['status'],'configuration_needed');self.assertFalse(FactoryWork.objects.exists())
        batch=FinancialImport.objects.get(pk=result['batch']);self.assertEqual(batch.rows[0]['amount'],self.data[5].batch.rows[0]['amount'])
        count=FinancialImport.objects.count()
        policy(a,c,'D06.source_schema_ref',{'columns':['account','amount','currency','period']},e['policy_decision'])
        resumed=intake.resume(a,c.pk,result['receipt'],rev(c))
        self.assertEqual(resumed['status'],'started');self.assertEqual(FinancialImport.objects.count(),count)
        self.assertEqual(Audit.objects.filter(action=intake.RECEIPT).count(),1)

    def test_declared_period_mismatch_quarantines_before_mapping(self):
        result,_,_=self.submit(changes={'period':'2026-09'})
        self.assertEqual(result['status'],'quarantined');self.assertIn('period',str(result['findings']))
        self.assertFalse(FactoryWork.objects.exists());self.assertFalse(FinanceRun.objects.exists())

    def test_policy_currency_mismatch_quarantines_native_validation(self):
        a,c,e,values,*_=self.data
        currency=self.data[5].batch.rows[0]['currency'];other='USD' if currency!='USD' else 'EUR'
        result,_,_=self.submit(body=values['csv'].replace(currency,other),changes={'currency':other})
        self.assertEqual(result['status'],'quarantined');self.assertIn('currency',str(result['findings']))
        self.assertEqual(ImportValidation.objects.get(pk=result['validation']).status,'invalid')
        self.assertFalse(FactoryWork.objects.exists())

    def test_malformed_source_has_durable_receipt_and_unknown_is_not_zero(self):
        a,c,*_=self.data
        result,_,_=self.submit(body='wrong,columns\n1,2',with_units=False)
        self.assertEqual(result['status'],'quarantined');self.assertIsNone(Audit.objects.get(pk=result['receipt']).data['batch'])
        result,_,_=self.submit(key='unknown',body='account,amount,currency,period\nA,,USD,2026-10\n',changes={'currency':'USD'},with_units=False)
        self.assertEqual(result['status'],'quarantined')
        self.assertIsNone(FinancialImport.objects.get(pk=result['batch']).rows[0]['amount'])
        self.assertFalse(FactoryWork.objects.exists())

    def test_withdrawn_authority_stale_revision_and_foreign_receipt_do_not_write(self):
        a,c,*_=self.data;evidence,context=self.supplied()
        revision=rev(c);add_evidence(a,c.pk,'finance_source','A newer source assertion','synthetic:new',revision)
        with self.assertRaises(ValidationError):intake.submit(a,c.pk,'stale',evidence.pk,context,'Report',revision)
        self.assertFalse(Audit.objects.filter(action=intake.RECEIPT).exists())
        Grant.objects.filter(case=c,user=a,action='finance.import').update(active=False)
        with self.assertRaises(PermissionDenied):intake.submit(a,c.pk,'denied',evidence.pk,context,'Report',rev(c))
        self.assertFalse(Audit.objects.filter(action=intake.RECEIPT).exists())
        Grant.objects.filter(case=c,user=a,action='finance.import').update(active=True)
        with self.assertRaises(PermissionDenied):intake.resume(a,c.pk,999999,rev(c))

    def test_cross_case_evidence_and_changed_identity_are_rejected(self):
        from tests.helpers import setup_case
        a,c,*_=self.data;other,foreign=setup_case(username='foreign-supplier')
        foreign_evidence=add_evidence(other,foreign.pk,'financial_input','account,amount,currency,period\nA,1,USD,2026-10','synthetic:foreign')
        _,context=self.supplied()
        with self.assertRaises(ValidationError):intake.submit(a,c.pk,'foreign',foreign_evidence.pk,context,'Report',rev(c))
        self.assertFalse(Audit.objects.filter(action=intake.RECEIPT).exists())

    def test_revised_export_preserves_original_receipt_and_import(self):
        a,c,e,values,*_=self.data
        first,_,_=self.submit();old=FinancialImport.objects.get(pk=first['batch'])
        second,_,_=self.submit(key='revision-2',body=values['csv']+'\n\n')
        self.assertNotEqual(first['batch'],second['batch']);self.assertNotEqual(first['work'],second['work'])
        old.refresh_from_db();self.assertEqual(old.source_sha256,Audit.objects.get(pk=first['receipt']).data['request']['sha256'])

    def test_http_confirm_units_starts_successor_from_the_same_unchanged_file(self):
        a, c, evidence, *_ = self.data
        held, source_file, _ = self.submit(with_units=False)
        self.assertEqual(held['status'], 'source_units_needed')
        import_count = FinancialImport.objects.count()
        self.client.force_login(a)
        start = reverse('factory_create') + f'?definition=finance-accounts/v1&case={c.pk}'
        form_url = start + f"&units={held['receipt']}"
        self.assertContains(self.client.get(start), 'Confirm file units')
        self.assertContains(self.client.get(form_url), 'Confirm units and resubmit')
        payload = {'action': 'confirm_units', 'unit': 'major_currency', 'proof': evidence['finance_source'].pk,
                   'note': 'The synthetic export header confirms amounts are in currency units.', 'revision': rev(c)}
        response = self.client.post(form_url, payload)
        link = Audit.objects.get(action=intake.UNITS_CONFIRMED, data__previous=held['receipt'])
        successor = Audit.objects.get(pk=link.data['successor'], action=intake.RECEIPT)
        current = intake.latest(successor)
        self.assertEqual(current['status'], 'started')
        self.assertRedirects(response, reverse('factory_detail', args=[current['work']]), fetch_redirect_response=False)
        self.assertEqual(successor.data['request']['evidence_id'], source_file.pk)
        self.assertEqual(successor.data['request']['sha256'], source_file.sha256)
        self.assertEqual(current['batch'], held['batch'])
        self.assertEqual(FinancialImport.objects.count(), import_count)
        self.assertEqual(intake.latest(Audit.objects.get(pk=held['receipt'])), held)
        self.assertFalse(FinanceRun.objects.exists())
        self.assertNotContains(self.client.get(start), 'Confirm file units')
        repeated = intake.confirm_units(a, c.pk, held['receipt'], payload['unit'], payload['proof'], payload['note'], rev(c))
        self.assertEqual(repeated, current)
        self.assertEqual(Audit.objects.filter(action=intake.UNITS_CONFIRMED).count(), 1)

    def test_api_supplied_import_unit_confirmation_preserves_original_and_queues_work(self):
        actor, case, evidence, *_ = self.data
        source_file, context = self.supplied(with_units=False)
        context['extracted_at'] = context['extracted_at'].isoformat()
        self.client.force_login(actor)
        url = f'/api/v1/projects/{case.pk}/accounting-intake'
        page = self.client.get(url)
        self.assertEqual(page.status_code, 200, page.content)
        self.assertIn(source_file.pk, [proof['id'] for proof in page.json()['extracts']])
        response = self.client.post(url, {'case_revision': page.json()['case_revision'], 'idempotency_key': 'intake-api',
                                          'reference': 'Account-file-test', 'evidence_id': source_file.pk, 'context': context},
                                    content_type='application/json')
        self.assertEqual(response.status_code, 201, response.content)
        held = response.json()
        self.assertEqual(held['status'], 'source_units_needed')
        self.assertTrue(held['can_confirm_units'])
        self.assertIsNone(held['work_id'])
        confirm = {'case_revision': held['case_revision'], 'action': 'confirm_units', 'unit': 'major_currency',
                   'evidence_id': evidence['finance_source'].pk, 'note': 'The synthetic file shows currency units.'}
        response = self.client.post(f"{url}/{held['id']}", confirm, content_type='application/json')
        self.assertEqual(response.status_code, 200, response.content)
        successor = response.json()
        self.assertEqual(successor['status'], 'started')
        self.assertEqual(successor['batch_id'], held['batch_id'])
        self.assertEqual(FactoryWork.objects.get(pk=successor['work_id']).background_progress.status, 'queued')
        receipts = {item['id']: item for item in self.client.get(url).json()['submissions']}
        self.assertEqual(receipts[held['id']]['successor_id'], successor['id'])
        self.assertFalse(receipts[held['id']]['can_confirm_units'])
        self.assertEqual(receipts[held['id']]['status'], 'source_units_needed')

    def test_api_malformed_extract_stays_in_history_while_corrected_file_needs_units(self):
        actor, case, *_ = self.data
        self.client.force_login(actor)
        url = f'/api/v1/projects/{case.pk}/accounting-intake'
        for key, body, expected in [('malformed', 'wrong,columns\n1,2', 'quarantined'),
                                    ('corrected', None, 'source_units_needed')]:
            file, context = self.supplied(body=body, with_units=False)
            response = self.client.post(url, {'case_revision': rev(case), 'idempotency_key': key,
                'reference': 'Sample-corrected-trial-balance', 'evidence_id': file.pk,
                'context': {**context, 'extracted_at': context['extracted_at'].isoformat()}},
                content_type='application/json')
            self.assertEqual(response.status_code, 201, response.content)
            self.assertEqual(response.json()['status'], expected)
            self.assertIsNone(response.json()['work_id'])
        self.assertCountEqual([row['status'] for row in self.client.get(url).json()['submissions']],
                              ['quarantined', 'source_units_needed'])
        self.assertFalse(FinanceRun.objects.exists())

    def test_confirming_thousands_records_evidence_but_keeps_calculation_on_hold(self):
        a, c, evidence, *_ = self.data
        held, _, _ = self.submit(with_units=False)
        proof = evidence['finance_source'].pk
        grant = Grant.objects.get(case=c, user=a, action='finance.source')
        grant.active = False
        grant.save(update_fields=['active'])
        with self.assertRaises(PermissionDenied):
            intake.confirm_units(a, c.pk, held['receipt'], 'thousands_currency', proof, 'Checked synthetic footer.', rev(c))
        self.assertFalse(Audit.objects.filter(action=intake.UNITS_CONFIRMED).exists())
        grant.active = True
        grant.save(update_fields=['active'])
        result = intake.confirm_units(a, c.pk, held['receipt'], 'thousands_currency', proof, 'Checked synthetic footer.', rev(c))
        self.assertEqual(result['status'], 'source_units_needed')
        self.assertEqual(result['source_units']['status'], 'unsupported')
        self.assertFalse(FactoryWork.objects.exists())
        self.assertFalse(FinanceRun.objects.exists())

    def test_approved_conversion_resumes_same_file_and_maps_exact_figures(self):
        from decimal import Decimal
        from apps.finance import analysis
        from tests.helpers import activate

        actor, case, proof, *_ = self.data
        held, file, _ = self.submit(with_units=False)
        declared = intake.confirm_units(actor, case.pk, held['receipt'], 'thousands_currency',
            proof['finance_source'].pk, 'Checked the sample file footer.', rev(case))
        source = FinanceSource.objects.get(pk=declared['source'])
        rule = {'entity': source.entity, 'period': '2026-10', 'currency': source.batch.rows[0]['currency'],
                'feed': 'trial-balance', 'units': ['thousands_currency'], 'control_total_unit': 'as_declared_in_file',
                'adjustment_unit': 'major_currency'}
        config = activate(actor, case, 'D06.import_unit_conversion', rule, proof['policy_decision'])
        started = intake.resume(actor, case.pk, declared['receipt'], rev(case))
        self.assertEqual(started['status'], 'started')
        self.assertEqual(intake.resume(actor, case.pk, declared['receipt'], rev(case)), started)
        run = analysis.map_source(actor, case.pk, source.pk, [], rev(case))
        self.assertEqual(run.snapshot['source_units']['policy'], config.pk)
        row = next(row for row in run.result['rows'] if row['origin'] == 'import' and row['amount'] is not None)
        self.assertEqual(Decimal(row['amount']), Decimal(row['raw_amount']) * 1000)
        self.assertEqual(source.batch.evidence_id, file.pk)
        self.assertEqual(Decimal(run.result['source_control']['difference']), Decimal(0))
        transition(actor, config.pk, 'revoked')
        with self.assertRaises(ValidationError):
            analysis.map_source(actor, case.pk, source.pk, [], rev(case))

    def test_http_confirm_millions_preserves_exact_source_and_holds_calculation(self):
        actor, case, evidence, *_ = self.data
        held, source_file, _ = self.submit(with_units=False)
        original = Audit.objects.get(pk=held['receipt'])
        source = FinanceSource.objects.get(pk=held['source'])
        original_rows = source.batch.rows
        import_count = FinancialImport.objects.count()
        self.client.force_login(actor)
        start = reverse('factory_create') + f'?definition=finance-accounts/v1&case={case.pk}'
        units_form = start + f"&units={original.pk}"
        self.assertContains(self.client.get(units_form), '<option value="millions_currency">Millions</option>', html=True)

        proof = evidence['finance_source']
        reason = 'The supplied synthetic footer states the amounts are in millions.'
        response = self.client.post(units_form, {'action': 'confirm_units', 'unit': 'millions_currency',
            'proof': proof.pk, 'note': reason, 'revision': rev(case)})
        self.assertRedirects(response, start, fetch_redirect_response=False)
        confirmation = Audit.objects.get(case=case, action=intake.UNITS_CONFIRMED, data__previous=original.pk)
        successor = Audit.objects.get(pk=confirmation.data['successor'], action=intake.RECEIPT)
        result = intake.latest(successor)
        self.assertEqual(result['status'], 'source_units_needed')
        self.assertEqual(result['source_units']['status'], 'unsupported')
        self.assertEqual(confirmation.data['proof'], proof.pk)
        self.assertEqual(confirmation.data['reason'], reason)
        self.assertEqual(confirmation.data['unit'], 'millions_currency')
        self.assertEqual(successor.data['request']['evidence_id'], source_file.pk)
        self.assertEqual(successor.data['request']['sha256'], source_file.sha256)
        self.assertEqual(result['batch'], source.batch_id)
        self.assertEqual(result['validation'], held['validation'])
        self.assertNotEqual(result['source'], source.pk)

        recorded = FinanceSource.objects.get(pk=result['source'])
        self.assertEqual(recorded.batch.rows, original_rows)
        self.assertEqual(FinancialImport.objects.count(), import_count)
        self.assertEqual(recorded.unit_declaration, result['source_units']['declaration'])
        declaration = Evidence.objects.get(pk=confirmation.data['unit_evidence'])
        self.assertEqual(recorded.unit_declaration['declarations'], [{'feed': 'trial-balance',
            'unit': 'millions_currency', 'evidence': {'id': declaration.pk, 'version': declaration.version,
                                                    'sha256': declaration.sha256}}])
        self.assertEqual(json.loads(declaration.body)['source_sha256'], source_file.sha256)
        self.assertEqual(intake.latest(original), held)
        self.assertFalse(FactoryWork.objects.exists())
        self.assertFalse(FinanceRun.objects.exists())
        self.assertContains(self.client.get(start), 'File units: Millions. Calculation needs a reviewed conversion for this source.')
        self.assertEqual(intake.confirm_units(actor, case.pk, original.pk, 'millions_currency', proof.pk,
                                             reason, rev(case)), result)
        self.assertEqual(Audit.objects.filter(case=case, action=intake.UNITS_CONFIRMED).count(), 1)

    def test_http_supplied_intake_to_reviewed_accounts_and_recipient_receipt(self):
        from apps.policy.operator_drafts import draft_operator_policy
        from apps.documents.models import PublicationReceipt
        a,c,e,values,configs,old_source,template,recipient=self.data
        value=json.loads(Path('fixtures/factory-accounting.json').read_text());value.pop('classification')
        value.update(information_resolver_id=a.pk,executor_id=a.pk,template_id=template.pk,bu_metrics=METRICS)
        profile=draft_operator_policy(a,c.pk,'OPS.factory_accounting_execution',value,e['policy_decision'].pk,timezone.now())
        transition(a,profile.pk,'validated');transition(a,profile.pk,'active')
        evidence,context=self.supplied(with_units=True);client=Client();client.force_login(a)
        url=reverse('factory_create')+'?definition=finance-accounts/v1&case='+str(c.pk)
        before=(Audit.objects.count(),FinancialImport.objects.count(),FinanceSource.objects.count())
        response=client.get(url);self.assertContains(response,'Start from a supplied trial balance')
        self.assertEqual(before,(Audit.objects.count(),FinancialImport.objects.count(),FinanceSource.objects.count()))
        data={'action':'supplied','supplied-key':'http-intake','supplied-evidence':evidence.pk,
              'supplied-source_evidence':context.pop('source_evidence_id'),'supplied-reference':'Supplied report',
              'supplied-unit_declaration':json.dumps(context.pop('unit_declaration')),
              'supplied-revision':rev(c),'supplied-inventory_confirmed':'on',
              **{'supplied-'+k:(v.isoformat() if hasattr(v,'isoformat') else v) for k,v in context.items()}}
        response=client.post(url,data);self.assertEqual(response.status_code,302)
        work=FactoryWork.objects.get();self.assertNotEqual(work.request['source'],old_source.pk)
        factory.run_until_wait(work.pk)
        # Native source review is mandatory; the intake does not confer approval.
        source_task=HumanTask.objects.get(case=c,kind='factory_accounting_review',context__purpose='source',status='open')
        task=accounting.claim(a,source_task.pk,source_task.revision)
        accounting.decide(a,task.pk,task.revision,'approve',e['finance_review'].pk,'Synthetic supplied extraction reviewed')
        factory.run_until_wait(work.pk)
        output_task=HumanTask.objects.get(case=c,kind='factory_accounting_review',context__purpose='output',status='open')
        task=accounting.claim(a,output_task.pk,output_task.revision)
        accounting.decide(a,task.pk,task.revision,'approve',e['finance_review'].pk,'Synthetic exact output reviewed')
        factory.run_until_wait(work.pk);work.refresh_from_db()
        self.assertEqual(work.status,'verified',work.finding)
        receipt=PublicationReceipt.objects.get(publication__factory_work=work)
        self.assertEqual(receipt.recipient_id,recipient.pk)
        self.assertFalse(FinanceRun.objects.get(pk=receipt.publication.version.financedocumentbinding.run_id).result['ledger_posted'])
        detail = client.get(f'/api/v1/work/{work.pk}/accounting')
        self.assertEqual(detail.status_code, 200, detail.content)
        exact = detail.json()
        self.assertEqual(exact['publication']['receipt_ids'], [receipt.pk])
        self.assertFalse(exact['publication']['ledger_posted'])
        self.assertIsNotNone(exact['allocation_id'])
        command = {key: exact[key] for key in ('expected_revision', 'case_revision', 'source_id')}
        reassessed = client.post(f'/api/v1/work/{work.pk}/accounting',
                                 {**command, 'action': 'reassess', 'adjustment_ids': [],
                                  'reason': 'The source owner requested a further current comparison.'},
                                 content_type='application/json')
        self.assertEqual(reassessed.status_code, 200, reassessed.content)
        self.assertTrue(PublicationReceipt.objects.filter(pk=receipt.pk).exists())

    def test_http_missing_inventory_and_csrf_do_not_capture(self):
        a,c,*_=self.data;evidence,context=self.supplied();client=Client();client.force_login(a)
        url=reverse('factory_create')+'?definition=finance-accounts/v1&case='+str(c.pk)
        data={'action':'supplied','supplied-key':'missing-inventory','supplied-evidence':evidence.pk,
              'supplied-source_evidence':context.pop('source_evidence_id'),'supplied-reference':'Report','supplied-revision':rev(c),
              **{'supplied-'+k:(v.isoformat() if hasattr(v,'isoformat') else v) for k,v in context.items()}}
        response=client.post(url,data);self.assertEqual(response.status_code,200)
        self.assertIn('inventory_confirmed',response.context['supplied_form'].errors)
        self.assertFalse(Audit.objects.filter(action=intake.RECEIPT).exists())
        secure=Client(enforce_csrf_checks=True);secure.force_login(a)
        self.assertEqual(secure.post(url,data).status_code,403)

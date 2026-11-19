"""Source-owned row quarantine on native PostgreSQL; legacy contracts stay strict."""
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from hashlib import sha256
from io import BytesIO,StringIO
from contextlib import redirect_stdout
import json
from pathlib import Path
from unittest.mock import patch
from threading import Barrier
from xml.etree import ElementTree as ET
from zipfile import ZipFile

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied,ValidationError
from django.db import connection,close_old_connections
from django.test import TestCase,TransactionTestCase
from django.urls import reverse
from django.utils import timezone

from apps.agents.payroll import investigate
from apps.finance import payroll as native,payroll_row_controls as controls
from apps.finance.payroll_models import PayrollInput,PayrollRun,PayrollReview,PayrollPublication
from apps.identity.models import Grant
from apps.policy.payroll_validators import ACCESS,MERGE,SCHEMAS
from apps.policy.models import Configuration
from apps.policy.payroll_drafts import draft_payroll_policy
from apps.policy.operator_drafts import draft_operator_policy
from apps.policy.services import resolve,reference_values,transition
from apps.workflows import factory_payroll
from tests.helpers import rev
from tests.payroll_helpers import fixture,policy,capture,approve,pipeline,body
from tests.test_design_payroll_sources import worksheet,COLUMNS


def configured(*,mode='hold_conflicting_rows',currency='row_currency'):
    f=fixture();access=deepcopy(f['config']['access']);merge=deepcopy(f['config']['merge'])
    access.update(format='psl.payroll-access/v2',row_handling=mode,currency_mode=currency)
    merge.update(format='psl.payroll-merge/v2',duplicate_within_source={
        None:None,'reject_export':'reject','hold_conflicting_rows':'hold_conflicting_rows'}[mode])
    f['policies'][ACCESS]=policy(f,ACCESS,access);f['policies'][MERGE]=policy(f,MERGE,merge)
    f['config']['access']=access;f['config']['merge']=merge
    for index in [0,1]:
        for row in f['config']['exports'][index]['rows']:
            if currency!='request_currency':row['currency']='TEST'
    f['inputs']=[capture(f,index,'source-v2-'+str(index)) for index in [0,1]]
    return f


def conflicts(f):
    rows=[{'row_ref':'B1','employee_id':'E002','component':'BASIC','amount':'150','currency':'TEST'},
          {'row_ref':'B2','employee_id':'E002','component':'BASIC','amount':'200','currency':'TEST'},
          {'row_ref':'B3','employee_id':'E004','component':'BASIC','amount':'50','currency':None}]
    f['inputs'][1]=capture(f,1,'conflicting-v2',rows=rows,control_total='400')
    return f['inputs'][1]


def currency_sheet():
    with ZipFile(BytesIO(worksheet())) as archive:parts={name:archive.read(name) for name in archive.namelist()}
    ns='{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
    document=ET.fromstring(parts['xl/worksheets/sheet2.xml'])
    for row,value in zip(document.iter(ns+'row'),['Currency','TEST']):
        cell=ET.SubElement(row,ns+'c',{'r':'E'+row.get('r'),'t':'inlineStr'})
        ET.SubElement(ET.SubElement(cell,ns+'is'),ns+'t').text=value
    parts['xl/worksheets/sheet2.xml']=ET.tostring(document)
    output=BytesIO()
    with ZipFile(output,'w') as archive:
        for name,content in parts.items():archive.writestr(name,content)
    return output.getvalue()


class PayrollRowContractTests(TestCase):
    @classmethod
    def setUpTestData(cls):cls.f=configured()

    def test_duplicate_and_missing_currency_rows_are_private_unknowns_while_good_rows_match(self):
        f=self.f;source=conflicts(f)
        self.assertTrue(source.metadata['accepted']);self.assertEqual(source.metadata['status'],'held')
        self.assertEqual(source.payload['row_validation']['held_rows'],3)
        self.assertEqual([row['amount'] for row in source.payload['rows']],[None,None,None])
        self.assertEqual([row['source_amount'] for row in source.payload['rows']],['150','200','50'])
        self.assertEqual([row['data_row'] for row in source.payload['rows']],[1,2,3])
        self.assertNotIn('E002',json.dumps(source.metadata))
        combined=native.combine(f['preparer'],f['case'].pk,f['request'].pk,[row.pk for row in f['inputs']],'draft-combine',rev(f['case']))
        self.assertEqual(combined.metadata['status'],'held')
        from apps.finance.payroll_working import rows as working_rows
        panel=working_rows(combined.result,combined.kind)
        self.assertEqual((panel['total'],panel['source_rows'],panel['item_label']),(3,4,'working pay items'))
        matched=native.match(f['preparer'],f['case'].pk,combined.pk,f['hr'].pk,'draft-match',rev(f['case']))
        rows={row['employee_id']:row for row in matched.result['rows']}
        self.assertEqual((rows['E001']['amount'],rows['E001']['bu']),('100','BU-A'))
        self.assertIsNone(rows['E002']['amount']);self.assertIsNone(rows['E004']['amount'])
        total=native.aggregate(f['preparer'],f['case'].pk,matched.pk,'draft-totals',rev(f['case']))
        self.assertIsNone(total.result['eligible_total']);self.assertEqual(total.metadata['status'],'held')
        self.assertFalse(PayrollReview.objects.exists());self.assertFalse(PayrollPublication.objects.exists())
        with self.assertRaises(ValidationError):approve(f,total)
        self.assertEqual(connection.vendor,'postgresql')

    def test_corrected_successor_needs_fresh_native_reviews_before_report_and_receipt(self):
        f=self.f;old=conflicts(f)
        corrected=capture(f,1,'source-owner-corrected-v2',source_version='B-corrected-v2')
        f['inputs'][1]=corrected
        combined,matched,total,publication=pipeline(f,prefix='v2-corrected')
        self.assertEqual(native.read_publication(f['manager'],publication.pk)['by_bu'],{'BU-A':'250.00'})
        receipt=native.receive_report(f['manager'],f['case'].pk,publication.pk,rev(f['case']))
        self.assertEqual(receipt.publication_id,publication.pk)
        self.assertTrue(PayrollInput.objects.filter(pk=old.pk).exists())
        with self.assertRaises(ValidationError):native.private_input(f['preparer'],f['case'].pk,old.pk)

    def test_factory_can_prepare_all_held_drafts_without_approving_conflicting_rows(self):
        f=self.f;conflicts(f)
        value=json.loads(Path('fixtures/factory-payroll.json').read_text());value.pop('classification')
        cfg=draft_operator_policy(f['owner'],f['case'].pk,'OPS.factory_payroll_execution',value,f['e']['policy_decision'].pk,timezone.now())
        transition(f['owner'],cfg.pk,'validated');transition(f['owner'],cfg.pk,'active')
        work=factory_payroll.start(f['preparer'],f['case'].pk,'V2-HELD-DRAFTS',f['request'].pk,
            {'input_ids':[row.pk for row in f['inputs']],'hr_snapshot_id':f['hr'].pk},'SAMPLE source row investigation',rev(f['case']))
        for stage in ['combine','match','aggregate']:
            work.refresh_from_db()
            result=factory_payroll.human_action(f['preparer'],work.pk,work.revision,rev(f['case']),'working',{'stage':stage})
            self.assertEqual(result.metadata['status'],'held')
        state=factory_payroll.report(work,f['preparer'])
        self.assertEqual(set(state['working_runs']),{'combine','match','aggregate'})
        self.assertNotIn('E001',json.dumps(state));self.assertFalse(PayrollReview.objects.exists())

    def test_unsupported_fields_and_spoofed_projection_still_reject_without_retention(self):
        f=self.f
        for key,value in [('medical','PRIVATE-SENTINEL'),('quarantine_codes',['invented-authority']),('data_row',1)]:
            rows=deepcopy(f['config']['exports'][1]['rows']);rows[0][key]=value
            source=capture(f,1,'forbidden-'+key,rows=rows)
            self.assertFalse(source.metadata['accepted']);self.assertEqual(source.payload,{})

    def test_private_row_projection_retains_original_amount_but_agent_never_reads_it(self):
        f=self.f;source=conflicts(f);self.client.force_login(f['preparer'])
        response=self.client.get(reverse('payroll_inspect',args=[f['case'].pk,'input',source.pk]))
        self.assertContains(response,'Source amount: 150');self.assertContains(response,'Data row 2')
        self.assertContains(response,'Currency is missing');self.assertEqual(response['Cache-Control'],'no-store')
        self.assertEqual((response.context['working']['total'],response.context['working']['source_rows']),(3,3))
        def forbidden(_):raise AssertionError('Metadata investigation loaded private rows')
        with patch.object(PayrollInput,'payload',property(forbidden)),patch.object(PayrollRun,'result',property(forbidden)):
            result=investigate(f['preparer'],f['case'].pk,rev(f['case'])).result
        self.assertNotIn('E002',json.dumps(result));self.assertFalse(result['private_payloads_read'])
        self.assertTrue(any('currency' in question for finding in result['findings'] for question in finding['questions']))
        self.client.force_login(f['manager'])
        self.assertEqual(self.client.get(reverse('payroll_inspect',args=[f['case'].pk,'input',source.pk])).status_code,403)

    def test_currency_mismatch_is_not_converted_and_non_scalar_currency_is_not_retained(self):
        f=self.f
        for number,currency in enumerate(['USD',{'medical':'PRIVATE-CURRENCY-SENTINEL'}]):
            rows=deepcopy(f['config']['exports'][1]['rows']);rows[0]['currency']=currency
            source=capture(f,1,'currency-'+str(number),rows=rows)
            self.assertIsNone(source.payload['rows'][0]['amount'])
            if isinstance(currency,dict):self.assertNotIn('PRIVATE-CURRENCY-SENTINEL',json.dumps(source.payload))
            else:self.assertEqual(source.payload['rows'][0]['source_currency'],'USD')

    def test_five_column_csv_and_excel_use_exact_layout_and_keep_formula_rejection(self):
        f=self.f;access=deepcopy(f['config']['access']);columns={**COLUMNS,'currency':'Currency'}
        access['providers'][1]['spreadsheet_layouts']=[{'format':'csv','delimiter':',','columns':columns},
                                                     {'format':'xlsx','sheet':'Payroll','columns':columns}]
        policy(f,ACCESS,access)
        declared={'source_version':'five-column','extracted_at':(timezone.now()-timedelta(seconds=1)).isoformat(),
                  'completeness':'complete','control_total':'150'}
        missing=b'Ref,Staff ID,Pay code,Total,Currency\nB1,E002,BASIC,150,\n'
        for format_,content in [('csv',missing),('xlsx',currency_sheet())]:
            result=native.capture(f['owner'],f['case'].pk,f['request'].pk,'PAY-B','mapped-'+format_,'',rev(f['case']),
                                  spreadsheet=(format_,content,declared))
            self.assertEqual(result.source_sha256,sha256(content).hexdigest());self.assertTrue(result.metadata['accepted'])
            if format_=='csv':
                self.assertIsNone(result.payload['rows'][0]['amount']);self.assertIn('missing_row_currency',result.metadata['codes'])
            else:self.assertEqual(result.metadata['status'],'complete')
        result=native.capture(f['owner'],f['case'].pk,f['request'].pk,'PAY-B','formula-v2','',rev(f['case']),
                              spreadsheet=('xlsx',worksheet(formula=True),declared))
        self.assertFalse(result.metadata['accepted']);self.assertEqual(result.payload,{})

    def test_v2_retry_binds_original_source_bytes_and_refuses_changed_intent(self):
        f=self.f;source_body=body(f,1,source_version='stable-v2')
        first=native.capture(f['owner'],f['case'].pk,f['request'].pk,'PAY-B','stable-v2',source_body,rev(f['case']))
        repeated=native.capture(f['owner'],f['case'].pk,f['request'].pk,'PAY-B','stable-v2',source_body,rev(f['case']))
        self.assertEqual(first.pk,repeated.pk)
        with self.assertRaises(ValidationError):native.capture(f['owner'],f['case'].pk,f['request'].pk,'PAY-B','stable-v2',source_body+' ',rev(f['case']))

    def test_source_owner_revocation_blocks_private_projection_before_loading_rows(self):
        f=self.f;source=conflicts(f)
        Grant.objects.filter(user=f['owner'],case=f['case'],action='payroll.capture').update(active=False)
        def forbidden(_):raise AssertionError('Revoked owner source payload was loaded')
        with patch.object(PayrollInput,'payload',property(forbidden)),self.assertRaises(PermissionDenied):
            native.private_input(f['preparer'],f['case'].pk,source.pk)


class PayrollRowConfigurationTests(TestCase):
    def test_isolated_preview_fixture_preserves_source_work_and_recipient_privacy(self):
        import runpy
        get_user_model().objects.create_user('psl-agent-trial')
        with patch.dict('os.environ',{'PSL_PAYROLL_ROW_FIXTURE':'1'}),redirect_stdout(StringIO()):
            values=runpy.run_path('tests/railway_payroll_rows_seed.py');result=values['prepare']()
            self.assertTrue(result['already_prepared']);self.assertEqual(result,values['prepare']())
        from apps.core.models import Case
        from apps.workflows.models import FactoryWork
        from apps.identity.models import Grant
        source=Case.objects.get(pk=result['case']);recipient=Case.objects.get(pk=result['recipient_case'])
        self.assertFalse(PayrollRun.objects.filter(request__case=source).exists())
        self.assertFalse(PayrollReview.objects.filter(request__case=source).exists())
        self.assertFalse(PayrollPublication.objects.filter(request__case=source).exists())
        self.assertEqual(FactoryWork.objects.get(case=source).pk,result['work'])
        operator=get_user_model().objects.get(username='psl-agent-trial')
        self.assertFalse(Grant.objects.filter(case=recipient,user=operator,action='payroll.private.read',active=True).exists())
        self.client.force_login(operator);page=self.client.get(reverse('design_payroll_matching',args=[recipient.pk]))
        self.assertContains(page,'250.00');self.assertNotContains(page,'PRIVATE-SAMPLE-001')

    def test_recipient_matching_view_shows_only_current_reviewed_totals(self):
        f=fixture();combined,matched,total,publication=pipeline(f);self.client.force_login(f['manager'])
        url=reverse('design_payroll_matching',args=[f['case'].pk])
        def forbidden(_):raise AssertionError('Recipient matching view read private working rows')
        with patch.object(PayrollInput,'payload',property(forbidden)),patch.object(PayrollRun,'result',property(forbidden)):
            page=self.client.get(url)
        self.assertContains(page,'Individual pay is restricted');self.assertContains(page,'250.00')
        self.assertNotContains(page,'E001');self.assertNotContains(page,'Source amount:');self.assertIsNone(page.context['working'])
        self.assertNotContains(page,'HR-authorised view and corrections');self.assertNotContains(page,'Business rule settings')
        capture(f,1,'newer-recipient-source',source_version='B-new')
        page=self.client.get(url);self.assertNotContains(page,'250.00');self.assertContains(page,'previous totals are unavailable')
        Grant.objects.filter(user=f['manager'],case=f['case'],action='payroll.report.read').update(active=False)
        self.assertIsNone(self.client.get(url).context['recipient_report'])

    def test_unknown_controls_hold_affected_rows_and_valid_export_currency_rows_stay_available(self):
        f=configured(mode=None,currency='request_currency')
        rows=deepcopy(f['config']['exports'][1]['rows']);rows.append({**rows[0],'row_ref':'B2'})
        source=capture(f,1,'undecided-conflict',rows=rows,control_total='300')
        self.assertTrue(source.metadata['accepted']);self.assertIn('row_handling_rule_unconfigured',source.metadata['codes'])
        self.assertIsNone(source.payload['rows'][0]['amount'])
        self.assertEqual(f['inputs'][0].metadata['status'],'complete')

    def test_v1_remains_strict(self):
        f=fixture();rows=deepcopy(f['config']['exports'][1]['rows']);rows.append({**rows[0],'row_ref':'B2'})
        source=capture(f,1,'reject-conflict',rows=rows,control_total='300')
        self.assertFalse(source.metadata['accepted']);self.assertEqual(source.payload,{})
        self.assertNotIn('currency',SCHEMAS[ACCESS][1]['properties']['providers']['items']['properties']['spreadsheet_layouts']['items']['oneOf'][0]['properties']['columns']['properties'])

    def test_v2_explicit_reject_mode_rejects_the_source(self):
        f=configured(mode='reject_export');rows=deepcopy(f['config']['exports'][1]['rows']);rows.append({**rows[0],'row_ref':'B2'})
        source=capture(f,1,'reject-conflict',rows=rows,control_total='300')
        self.assertFalse(source.metadata['accepted']);self.assertEqual(source.payload,{})

    def test_configuration_ui_saves_undecided_successor_drafts_without_activation(self):
        f=fixture();self.client.force_login(f['owner']);url=reverse('payroll_row_controls',args=[f['case'].pk])
        page=self.client.get(url);self.assertContains(page,'Payroll source row checks')
        data={'revision':rev(f['case']),'access_id':f['policies'][ACCESS].pk,'merge_id':f['policies'][MERGE].pk,
              'access_head':f['policies'][ACCESS].pk,'merge_head':f['policies'][MERGE].pk,
              'row_handling':'','currency_mode':'','evidence':f['e']['policy_decision'].pk}
        self.assertRedirects(self.client.post(url,data),url)
        review=self.client.get(url);self.assertContains(review,'Saved source-control versions');self.assertContains(review,'Not decided')
        from apps.core.models import Audit
        audit=Audit.objects.get(case=f['case'],action='payroll.row_control_drafts')
        self.assertEqual((audit.data['previous_access'],audit.data['previous_merge']),(f['policies'][ACCESS].pk,f['policies'][MERGE].pk))
        self.assertFalse(audit.data['activated'])
        self.assertEqual(resolve(ACCESS,f['case']).configuration.pk,f['policies'][ACCESS].pk)
        current=controls.prepare(f['owner'],f['case'])
        with self.assertRaises(ValidationError):controls.draft(f['owner'],f['case'].pk,data['revision'],{
            'access_id':data['access_id'],'merge_id':data['merge_id'],'access_head':data['access_head'],
            'merge_head':data['merge_head'],'row_handling':None,'currency_mode':None,'headers':{}},f['e']['policy_decision'].pk)
        Grant.objects.filter(user=f['owner'],case=f['case'],action='policy.read').update(active=False)
        self.assertEqual(self.client.get(url).status_code,403)


class PayrollRowControlConcurrencyTests(TransactionTestCase):
    def test_two_reviewers_of_one_snapshot_save_one_pair_of_drafts(self):
        f=fixture();prepared=controls.prepare(f['owner'],f['case']);version=rev(f['case']);barrier=Barrier(2)
        command={'access_id':prepared['access'].pk,'merge_id':prepared['merge'].pk,
                 'access_head':prepared['access_head'],'merge_head':prepared['merge_head'],
                 'row_handling':None,'currency_mode':None,'headers':{}}
        before=Configuration.objects.filter(case=f['case'],component__in=[ACCESS,MERGE]).count()
        def save(number):
            close_old_connections()
            try:
                actor=get_user_model().objects.get(pk=f['owner'].pk);barrier.wait(timeout=10)
                controls.draft(actor,f['case'].pk,version,command,f['e']['policy_decision'].pk)
                return 'saved'
            except (ValidationError,PermissionDenied):return 'held'
            finally:close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(save,[1,2]))
        self.assertCountEqual(results,['saved','held'])
        self.assertEqual(Configuration.objects.filter(case=f['case'],component__in=[ACCESS,MERGE]).count(),before+2)
        self.assertEqual(resolve(ACCESS,f['case']).configuration.pk,prepared['access'].pk)

"""Independent source-unit boundary tests. No performance/sign implementation coverage."""
import copy
import json
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import DatabaseError, transaction
from django.test import TestCase
from apps.core.services import add_evidence
from apps.finance import analysis
from apps.finance.models import FinanceSource, FinanceRun
from apps.finance.source_units import inspect, capture, evidence_identity
from apps.agents.finance_analysis import inspect_source_units
from apps.identity.models import Grant
from .finance_analysis_helpers import fixture
from .helpers import rev


class SourceUnitBoundary777Tests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.a,cls.c,cls.e,cls.f,cls.configs,cls.source,cls.t,cls.recipient=fixture()

    def envelope(self, units=('major_currency',), key='explicit-input-A', feeds=None):
        b=self.source.batch
        value={'schema':'finance-source-units/v1','batch':{'id':b.pk,'sha256':b.source_sha256},'input_key':key,'declarations':[]}
        for i,unit in enumerate(units):
            feed=feeds[i] if feeds else 'feed-'+str(i)
            body={'schema':'finance-source-unit-assertion/v1','batch_id':b.pk,'source_sha256':b.source_sha256,'input_key':key,'feed':feed,'unit':unit}
            evidence=add_evidence(self.a,self.c.pk,'finance_source_unit',json.dumps(body,sort_keys=True),evidence_identity(b.pk,key,feed))
            value['declarations'].append({'feed':feed,'unit':unit,'evidence':{'id':evidence.pk,'version':evidence.version,'sha256':evidence.sha256}})
        return value

    def source_with(self, value=None):
        s=self.source
        return analysis.capture_source(self.a,self.c.pk,s.batch_id,s.entity,s.accounting_basis,s.extracted_at,s.completeness,s.control_total,s.evidence_id,rev(self.c),unit_declaration=value)

    def mapping(self,s):
        return analysis.map_source(self.a,self.c.pk,s.pk,[],rev(self.c))

    def test_new_omission_is_unknown_and_creates_no_run(self):
        s=self.source_with()
        self.assertEqual(inspect(s)['status'],'unknown')
        before=FinanceRun.objects.count()
        with self.assertRaisesMessage(ValidationError,'unknown'):self.mapping(s)
        self.assertEqual(FinanceRun.objects.count(),before)

    def test_exact_conflicting_two_feed_assertions_hold_before_mapping(self):
        value=self.envelope(('major_currency','thousands_currency'))
        s=self.source_with(value)
        self.assertEqual(inspect(s)['status'],'conflict')
        self.assertEqual(s.unit_declaration,value)
        with self.assertRaisesMessage(ValidationError,'conflict'):self.mapping(s)
        self.assertFalse(FinanceRun.objects.filter(source=s).exists())
        report=inspect_source_units(self.a,self.c.pk,s.pk)
        self.assertIsNone(report['numeric_result'])
        self.assertEqual(report['source_units']['declaration'],value)

    def test_equal_units_map_unchanged_no_second_scaling(self):
        s=self.source_with(self.envelope(('major_currency','major_currency')))
        run=self.mapping(s)
        self.assertEqual(run.result['status'],'complete')
        for row in run.result['rows']:
            if row['origin']=='import':self.assertEqual(row['amount'],row['raw_amount'])
        self.assertEqual(run.snapshot['source_units']['status'],'declared_major_currency')
        self.assertEqual(run.snapshot['source_units']['declaration'],s.unit_declaration)
        self.assertFalse(run.result['ledger_posted'])
        analysis.ensure_current(run)

    def test_single_thousands_is_unsupported_not_converted(self):
        s=self.source_with(self.envelope(('thousands_currency',)))
        with self.assertRaisesMessage(ValidationError,'unsupported'):self.mapping(s)

    def test_unknown_feed_is_not_overridden_by_known_feed(self):
        s=self.source_with(self.envelope(('unknown','major_currency')))
        with self.assertRaisesMessage(ValidationError,'unknown'):self.mapping(s)

    def test_explicit_linkage_must_match_each_evidenced_assertion(self):
        value=self.envelope();value['input_key']='other-input'
        with self.assertRaises(ValidationError):self.source_with(value)

    def test_evidence_version_hash_and_import_pins_are_exact(self):
        value=self.envelope()
        for path in ('version','sha256'):
            bad=copy.deepcopy(value);bad['declarations'][0]['evidence'][path]=999 if path=='version' else '0'*64
            with self.assertRaises(ValidationError):self.source_with(bad)
        bad=copy.deepcopy(value);bad['batch']['id']+=1
        with self.assertRaises(ValidationError):self.source_with(bad)
        bad=copy.deepcopy(value);bad['batch']['sha256']='0'*64
        with self.assertRaises(ValidationError):self.source_with(bad)

    def test_duplicate_feed_and_missing_evidence_fail_closed(self):
        value=self.envelope();value['declarations'].append(copy.deepcopy(value['declarations'][0]))
        with self.assertRaises(ValidationError):self.source_with(value)
        value=self.envelope();del value['declarations'][0]['evidence']
        with self.assertRaises(ValidationError):self.source_with(value)

    def test_colon_pairs_remain_distinct_evidence_currentness_identities(self):
        from django.db import connection
        first=self.source_with(self.envelope(key='A:B',feeds=['C']))
        run=self.mapping(first)
        second=self.envelope(key='A',feeds=['B:C'])
        self.assertNotEqual(evidence_identity(first.batch_id,'A:B','C'),evidence_identity(first.batch_id,'A','B:C'))
        analysis.ensure_current(run)
        self.assertEqual(self.mapping(first).pk,run.pk)
        with connection.cursor() as cursor:
            cursor.execute('SELECT psl_source_units(%s,%s,%s::jsonb)',[str(self.c.pk),first.batch_id,json.dumps(first.unit_declaration)])
            self.assertEqual(cursor.fetchone()[0],'declared_major_currency')
        successor=self.source_with(second)
        self.assertEqual(self.mapping(successor).result['status'],'complete')
        with self.assertRaises(ValidationError):analysis.ensure_current(run)

    def test_new_evidence_revision_stales_old_result(self):
        s=self.source_with(self.envelope());run=self.mapping(s)
        self.envelope(('thousands_currency',))
        with self.assertRaises(ValidationError):analysis.ensure_current(run)
        with self.assertRaises(ValidationError):self.mapping(s)
        run.refresh_from_db()
        self.assertEqual(run.snapshot['source_units']['status'],'declared_major_currency')

    def test_source_revision_cannot_launder_previous_results(self):
        s=self.source_with(self.envelope());run=self.mapping(s)
        self.source_with(self.envelope(('major_currency',),key='new-explicit-input'))
        with self.assertRaises(ValidationError):analysis.ensure_current(run)
        self.assertEqual(FinanceRun.objects.get(pk=run.pk).source_id,s.pk)

    def test_source_and_evidence_permissions_are_not_approval(self):
        s=self.source_with(self.envelope())
        Grant.objects.filter(case=self.c,user=self.a,action='finance.read').update(active=False)
        with self.assertRaises(PermissionDenied):inspect_source_units(self.a,self.c.pk,s.pk)

    def test_foreign_case_evidence_cannot_supply_a_declaration(self):
        from .helpers import setup_case
        actor,case=setup_case(username='other-source-owner')
        value=self.envelope()
        body={'schema':'finance-source-unit-assertion/v1','batch_id':self.source.batch_id,'source_sha256':self.source.batch.source_sha256,
              'input_key':value['input_key'],'feed':'feed-0','unit':'major_currency'}
        e=add_evidence(actor,case.pk,'finance_source_unit',json.dumps(body),evidence_identity(self.source.batch_id,value['input_key'],'feed-0'))
        value['declarations'][0]['evidence']={'id':e.pk,'version':e.version,'sha256':e.sha256}
        with self.assertRaises(ValidationError):self.source_with(value)

    def test_policy_revocation_stales_typed_preview(self):
        from apps.policy.services import transition
        s=self.source_with(self.envelope());run=self.mapping(s)
        transition(self.a,self.configs['D06.unit_sign_currency_period'].pk,'revoked')
        with self.assertRaises(ValidationError):analysis.ensure_current(run)

    def test_declaration_history_cannot_be_rewritten(self):
        s=self.source_with(self.envelope())
        with self.assertRaises(DatabaseError),transaction.atomic():
            FinanceSource.objects.filter(pk=s.pk).update(unit_declaration=None)
        s.refresh_from_db()
        self.assertEqual(inspect(s)['status'],'declared_major_currency')

    def test_factory_unknown_to_explicit_submission_preserves_receipts_and_retries(self):
        from apps.core.models import Audit
        from apps.workflows import factory_accounting_intake as intake
        from apps.workflows.models import FactoryWork
        s=self.source
        context={'entity':s.entity,'period':'2026-10','currency':s.batch.rows[0]['currency'],
                 'accounting_basis':s.accounting_basis,'extracted_at':s.extracted_at,
                 'completeness':s.completeness,'control_total':s.control_total,'source_evidence_id':s.evidence_id}
        first=intake.submit(self.a,self.c.pk,'777-unknown',s.batch.evidence_id,context,'Source unit contrast',rev(self.c))
        self.assertEqual(first['status'],'source_units_needed')
        self.assertFalse(FactoryWork.objects.filter(case=self.c).exists())
        old=copy.deepcopy(Audit.objects.get(pk=first['receipt']).data)
        self.assertEqual(intake.submit(self.a,self.c.pk,'777-unknown',s.batch.evidence_id,context,'Source unit contrast',rev(self.c)),first)
        explicit=dict(context,unit_declaration=self.envelope())
        second=intake.submit(self.a,self.c.pk,'777-declared',s.batch.evidence_id,explicit,'Source unit contrast',rev(self.c))
        self.assertEqual(second['status'],'started')
        self.assertNotEqual(second['source'],first['source'])
        selected=FinanceSource.objects.get(pk=second['source'])
        self.assertEqual(self.mapping(selected).result['status'],'complete')
        self.assertEqual(intake.submit(self.a,self.c.pk,'777-declared',s.batch.evidence_id,explicit,'Source unit contrast',rev(self.c)),second)
        retry=intake.submit(self.a,self.c.pk,'777-unknown',s.batch.evidence_id,context,'Source unit contrast',rev(self.c))
        self.assertEqual(retry,first)
        repeated=intake.submit(self.a,self.c.pk,'777-declared-again',s.batch.evidence_id,explicit,'Source unit contrast',rev(self.c))
        self.assertEqual(repeated['work'],second['work'])
        self.assertEqual(repeated['source'],second['source'])
        self.assertNotEqual(repeated['receipt'],second['receipt'])
        with self.assertRaises(DatabaseError),transaction.atomic():
            Audit.objects.filter(pk=first['receipt']).update(data=dict(old,unit_declaration=explicit['unit_declaration']))
        self.assertEqual(Audit.objects.get(pk=first['receipt']).data,old)
        self.assertTrue(Audit.objects.filter(action=intake.RESULT,data=first,case=self.c).exists())
        self.assertEqual(FinanceSource.objects.filter(batch=s.batch).order_by('-pk').first().pk,selected.pk)
        self.assertEqual(FactoryWork.objects.filter(case=self.c).count(),1)

    def test_raw_json_null_and_malformed_nested_pins_rejected(self):
        from django.db.models import JSONField, Value
        s=self.source;good=self.envelope()
        invalid=[Value(None,output_field=JSONField()),{},[],dict(good,schema=None)]
        for pin in (None,{},[],{'id':True,'version':1,'sha256':'a'*64},
                    {'id':1,'version':None,'sha256':'a'*64},{'id':1,'version':1,'sha256':None}):
            bad=copy.deepcopy(good);bad['declarations'][0]['evidence']=pin;invalid.append(bad)
        for value in invalid:
            with self.subTest(value=str(value)),self.assertRaises(DatabaseError),transaction.atomic():
                FinanceSource.objects.create(case=self.c,batch=s.batch,entity=s.entity,accounting_basis=s.accounting_basis,
                    extracted_at=s.extracted_at,completeness=s.completeness,control_total=s.control_total,evidence=s.evidence,actor=self.a,unit_declaration=value)

    def test_raw_null_source_cannot_impersonate_historical_record(self):
        s=self.source
        with self.assertRaises(DatabaseError),transaction.atomic():
            FinanceSource.objects.create(case=self.c,batch=s.batch,entity=s.entity,accounting_basis=s.accounting_basis,
                extracted_at=s.extracted_at,completeness=s.completeness,control_total=s.control_total,evidence=s.evidence,actor=self.a)

    def test_raw_source_with_forged_evidence_is_rejected(self):
        s=self.source;value=self.envelope();value['declarations'][0]['unit']='thousands_currency'
        with self.assertRaises(DatabaseError),transaction.atomic():
            FinanceSource.objects.create(case=self.c,batch=s.batch,entity=s.entity,accounting_basis=s.accounting_basis,
                extracted_at=s.extracted_at,completeness=s.completeness,control_total=s.control_total,evidence=s.evidence,actor=self.a,unit_declaration=value)

    def test_raw_known_result_for_unknown_source_is_rejected(self):
        s=self.source_with()
        with self.assertRaises(DatabaseError),transaction.atomic():
            FinanceRun.objects.create(case=self.c,source=s,kind='mapping',request={},snapshot={},result={'status':'complete','rows':[{'amount':'1'}]},operation_key='f'*64,actor=self.a)

    def test_raw_forged_declaration_snapshot_is_rejected(self):
        s=self.source_with(self.envelope());run=self.mapping(s)
        bad=copy.deepcopy(run.snapshot);bad['source_units']['declaration']['batch']['sha256']='0'*64
        with self.assertRaises(DatabaseError),transaction.atomic():
            FinanceRun.objects.create(case=self.c,source=s,kind='mapping',request=run.request,snapshot=bad,result=run.result,operation_key='e'*64,actor=self.a)

    def test_ui_exposes_unknown_reason_without_claiming_legacy(self):
        self.source_with()
        self.client.force_login(self.a)
        from django.urls import reverse
        response=self.client.get(reverse('finance_analysis',args=[self.c.pk]))
        self.assertContains(response,'Source unit: unknown')
        self.assertContains(response,'no conversion')


from types import SimpleNamespace
from django.test import SimpleTestCase


class SourceUnitShape777Tests(SimpleTestCase):
    def setUp(self):
        self.batch=SimpleNamespace(pk=42,source_sha256='a'*64)

    def test_missing_is_versioned_unknown_not_a_known_unit(self):
        value=capture(self.batch,None)
        self.assertEqual(value['declarations'],[])
        self.assertEqual(inspect(SimpleNamespace(batch=self.batch,unit_declaration=value))['status'],'unknown')

    def test_legacy_is_explicitly_undeclared(self):
        state=inspect(SimpleNamespace(batch=self.batch,unit_declaration=None))
        self.assertEqual(state['status'],'legacy_undeclared')
        self.assertIsNone(state['declaration'])

    def test_unlinked_rows_rejected_without_evidence_lookup(self):
        value=capture(self.batch,None)
        value['declarations']=[{'feed':'feed','unit':'major_currency','evidence':{}}]
        with self.assertRaisesMessage(ValidationError,'linkage'):capture(self.batch,value)

    def test_foreign_import_and_unrecognized_shape_rejected(self):
        value=capture(self.batch,None);value['batch']['id']=43
        with self.assertRaises(ValidationError):capture(self.batch,value)
        value=capture(self.batch,None);value['unit']='major_currency'
        with self.assertRaises(ValidationError):capture(self.batch,value)

"""Synthetic explicit semantics, not an operational percentage or owner oracle."""
import json
from copy import deepcopy
from datetime import timedelta
from django.test import SimpleTestCase, TestCase
from django.core.exceptions import ValidationError, PermissionDenied
from django.utils import timezone
from django.urls import reverse
from apps.core.services import add_evidence
from apps.policy.allocation_coverage import checked_weights, evidence_payload
from apps.policy.bu_validators import STAFF
from apps.policy.bu_drafts import draft_bu_policy
from apps.policy.services import resolve, transition
from apps.finance import bu, bu_math, payroll, analysis
from apps.finance.models import BUReport, BUWork
from .bu_helpers import fixture, policy, staff, publish
from .helpers import rev


def contract(mode='declared_shares', population=None, denominator='100'):
    return dict(version='allocation-coverage/v1', mode=mode,
                population=population or ['BU-A', 'BU-B'], completeness='complete',
                denominator=denominator, basis='synthetic-owner-supplied-basis', evidence_id=1)


def staff_value(f, weights=('50','50'), mode='declared_shares', denominator='100'):
    v=deepcopy(f['bu_config']['staff']);v['standard_method']='fixed_weights'
    v['standard_weights']=[{'bu':b,'weight':w} for b,w in zip(['BU-A','BU-B'],weights)]
    v['weight_contract']=contract(mode,[r['bu'] for r in v['standard_weights']],denominator)
    e=add_evidence(f['preparer'],f['case'].pk,'bu_pool_contract',json.dumps(evidence_payload(v,True)),'synthetic:explicit-pool-coverage')
    v['weight_contract']['evidence_id']=v['pool_contract_evidence_id']=e.pk
    return v


class CoverageMathTests(SimpleTestCase):
    def test_explicit_relative_one_one_and_two_one(self):
        for values in [('1','1'),('2','1')]:
            rows=[{'bu':b,'weight':w} for b,w in zip(['BU-A','BU-B'],values)]
            self.assertEqual(set(checked_weights(rows,contract('relative_weights',denominator=None))),{'BU-A','BU-B'})
    def test_incomplete_overfull_missing_invalid_contracts_hold(self):
        rows=[{'bu':'BU-A','weight':'40'},{'bu':'BU-B','weight':'40'}]
        variants=[(rows,contract()),([dict(r,weight='60') for r in rows],contract()),
                  (rows,contract(denominator=None)),(rows,contract(denominator='0')),
                  (rows,contract(population=['BU-A'])),(rows,dict(contract(),mode='unknown')),
                  (rows,dict(contract(),completeness='partial')),
                  (rows,dict(contract(),version='unknown')),
                  ([rows[0],rows[0]],contract()),([dict(rows[0],weight='-1'),rows[1]],contract())]
        for weights,value in variants:
            with self.subTest(value=value,weights=weights),self.assertRaises(ValidationError):checked_weights(weights,value)
    def test_literal_F20_pool100_50_50_excludes_E900_and_conserves(self):
        financial={'components':['BASIC'],'standard_pool_ref':'synthetic-pool','standard_method':'fixed_weights',
                   'standard_weights':[{'bu':'BU-A','weight':'50'},{'bu':'BU-B','weight':'50'}],
                   'weight_contract':contract(),'rounding':{'decimal_places':2,'rounding':'half_even','residual':'hold','residual_bu':None}}
        rows=[{'employee_id':emp,'component':'BASIC','amount':'100','bu':'BU-A'} for emp in ['E002','E900']]
        rules=[dict(employee_id='E900',component='BASIC',standard_pool_ref='synthetic-pool',weights=[{'bu':'BU-A','weight':'70'},{'bu':'BU-B','weight':'30'}])]
        result,codes=bu_math.staff(rows,[['E900','BASIC']],rules,financial,['BU-A','BU-B','OTHER'])
        self.assertEqual(codes,[]);self.assertEqual(result['rows'][0]['allocations'],{'BU-A':'50.00','BU-B':'50.00'})
        self.assertTrue(result['rows'][1]['excluded_from_standard_pool']);self.assertTrue(result['conserved'])
        financial['standard_weights']=[dict(r,weight='40') for r in financial['standard_weights']]
        result,codes=bu_math.staff(rows,[['E900','BASIC']],rules,financial,['BU-A','BU-B','OTHER'])
        self.assertIn('allocation_coverage_share_total_incomplete',codes);self.assertEqual(result['rows'][0]['allocations'],{})
        self.assertEqual(result['rows'][1]['allocations'],{'BU-A':'70.00','BU-B':'30.00'})


class CoverageNativeTests(TestCase):
    @classmethod
    def setUpTestData(cls):cls.f=fixture()
    def test_native_literal_pool_report_receipt_and_private_lineage(self):
        f=self.f
        from .payroll_helpers import capture, combined, approve
        row=dict(f['config']['exports'][1]['rows'][0],amount='100')
        f['inputs'][1]=capture(f,1,key='literal100',rows=[row],control_total='100',source_version='B-literal100');c=combined(f,key='literal100');approve(f,c)
        m=payroll.match(f['preparer'],f['case'].pk,c.pk,f['hr'].pk,'literal-match',rev(f['case']));approve(f,m);f['match']=m
        value=staff_value(f);p=policy(f,STAFF,value);w=staff(f);self.assertEqual(w.metadata['codes'],[])
        standard=next(r for r in w.payload['rows'] if r['employee_id']=='E002')
        self.assertEqual(standard['allocations'],{'BU-A':'50.00','BU-B':'50.00'})
        self.assertEqual(w.payload['by_bu'],{'BU-A':'120.00','BU-B':'80.00'})
        self.assertEqual(w.payload['weight_contract'],value['weight_contract']);self.assertEqual(w.metadata['policy_ids'][STAFF],p.pk)
        report=publish(f,w);bu.receive(f['manager'],f['case'].pk,report.pk,rev(f['case']))
        self.assertNotIn('E900',json.dumps(bu.read_report(f['manager'],report.pk)))
        with self.assertRaises(PermissionDenied):bu.read_private(f['manager'],f['case'].pk,w.pk)
    def test_relative_two_one_and_approved_subset_preserved(self):
        f=self.f;value=staff_value(f,('2','1'),'relative_weights',None);policy(f,STAFF,value);w=staff(f)
        self.assertEqual(w.payload['by_bu'],{'BU-A':'170.00','BU-B':'80.00'});self.assertTrue(w.payload['conserved'])
        value=staff_value(f,('1',),'relative_weights',None);policy(f,STAFF,value)
        from .bu_helpers import rule, review
        r=rule(f,key='subset-rule');review(f,r);w=staff(f,key='subset',rules=[r.pk])
        self.assertEqual(w.metadata['codes'],[]);self.assertEqual(w.payload['by_bu'],{'BU-A':'220.00','BU-B':'30.00'})
    def test_invalid_draft_retained_but_cannot_validate_or_normalize(self):
        f=self.f;value=staff_value(f,('40','40'));p=draft_bu_policy(f['preparer'],f['case'].pk,STAFF,value,f['e']['policy_decision'].pk,timezone.now())
        self.assertEqual(p.states.last().state,'draft')
        with self.assertRaisesMessage(ValidationError,'allocation_coverage_share_total_incomplete'):transition(f['preparer'],p.pk,'validated')
        self.assertEqual(BUWork.objects.filter(kind='staff').count(),0);self.assertEqual(BUReport.objects.count(),0)
    def test_current_evidence_replacement_revokes_report_without_rewrite(self):
        f=self.f;value=staff_value(f);policy(f,STAFF,value);w=staff(f);report=publish(f,w);original=deepcopy(report.payload)
        add_evidence(f['preparer'],f['case'].pk,'bu_pool_contract',json.dumps(evidence_payload(value,True)),'synthetic:replacement')
        self.assertEqual(resolve(STAFF,f['case']).status,'INVALID')
        with self.assertRaises(ValidationError):bu.read_report(f['manager'],report.pk)
        report.refresh_from_db();self.assertEqual(report.payload,original)
    def test_revoked_policy_and_future_period_hold_current_allocation(self):
        f=self.f;value=staff_value(f);p=policy(f,STAFF,value);w=staff(f);report=publish(f,w)
        transition(f['preparer'],p.pk,'revoked')
        with self.assertRaises(ValidationError):bu.read_report(f['manager'],report.pk)
        value=staff_value(f);value['from_period']=value['to_period']='2026-10'
        e=add_evidence(f['preparer'],f['case'].pk,'bu_pool_contract',json.dumps(evidence_payload(value,True)),'synthetic:future')
        value['weight_contract']['evidence_id']=value['pool_contract_evidence_id']=e.pk;policy(f,STAFF,value)
        with self.assertRaisesMessage(ValidationError,'Rule entity/effective period does not match'):staff(f,key='future',rules=[])
    def test_ui_draft_shows_explicit_contract_without_private_data(self):
        f=self.f;self.client.force_login(f['preparer']);response=self.client.get(reverse('bu',args=[f['case'].pk]))
        self.assertContains(response,'declared_shares');self.assertContains(response,'No operational default');self.assertNotContains(response,'E900')
    def test_independent_pool_and_future_evidence_do_not_stale_current_pool(self):
        f=self.f;value=staff_value(f);policy(f,STAFF,value);w=staff(f);report=publish(f,w)
        other=evidence_payload(value,True);other['pool']='independent-pool-B'
        add_evidence(f['preparer'],f['case'].pk,'bu_pool_contract',json.dumps(other),'synthetic:pool-B')
        future=evidence_payload(value,True);future['from_period']=future['to_period']='2026-10'
        add_evidence(f['preparer'],f['case'].pk,'bu_pool_contract',json.dumps(future),'synthetic:future-pool-A')
        self.assertEqual(resolve(STAFF,f['case']).status,'ACTIVE');self.assertTrue(bu.read_report(f['manager'],report.pk)['conserved'])

    def test_v2_matched_bu_retains_original_pool_evidence_currentness(self):
        f=self.f;v=deepcopy(f['bu_config']['staff']);v['weight_contract']=None
        policy(f,STAFF,v);w=staff(f);report=publish(f,w)
        add_evidence(f['preparer'],f['case'].pk,'bu_pool_contract','Synthetic replacement of the original matched-BU pool contract','synthetic:matched-pool-replaced')
        self.assertEqual(resolve(STAFF,f['case']).status,'INVALID')
        with self.assertRaises(ValidationError):bu.read_report(f['manager'],report.pk)

    def test_exact_evidence_mismatch_and_v2_missing_contract_rejected(self):
        f=self.f;value=staff_value(f);value['weight_contract']['basis']='changed-basis'
        with self.assertRaisesMessage(ValidationError,'differs from its cited pool evidence'):policy(f,STAFF,value)
        value=staff_value(f);value['weight_contract']=None
        with self.assertRaisesMessage(ValidationError,'Explicit fixed-weight coverage contract required'):policy(f,STAFF,value)


class FinancePoolCoverageTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        from .finance_analysis_helpers import fixture as finance_fixture
        cls.a,cls.c,cls.e,cls.f,cls.configs,cls.source,_,_=finance_fixture()
    def configure(self, weights=('2','1'), mode='relative_weights', denominator=None):
        from .finance_analysis_helpers import policy as finance_policy
        v=deepcopy(self.f['pools'][0]);v['weights']=[{'bu':b,'weight':w} for b,w in zip(['alpha','beta'],weights)]
        v['weight_contract']=contract(mode,[r['bu'] for r in v['weights']],denominator)
        e=add_evidence(self.a,self.c.pk,'finance_pool_contract',json.dumps(evidence_payload(v)),'synthetic:finance-pool-coverage')
        v['weight_contract']['evidence_id']=e.pk
        p=finance_policy(self.a,self.c,'D07.allocation_pool_rules',[v],self.e['policy_decision'])
        analysis.review(self.a,self.c.pk,'allocation',p.pk,'Finance','approve',self.e['finance_review'].pk,'Synthetic explicit relative pool review',rev(self.c))
        return v,p
    def test_native_relative_weights_and_lineage_currentness(self):
        v,p=self.configure();mapping=analysis.map_source(self.a,self.c.pk,self.source.pk,[],rev(self.c))
        run=analysis.allocate(self.a,self.c.pk,mapping.pk,['opex'],rev(self.c))
        self.assertEqual(run.result['status'],'complete');row=next(r for r in run.result['rows'] if r['treatment']=='pool')
        self.assertEqual(row['basis']['weight_contract'],v['weight_contract']);self.assertEqual(row['denominator'],'3')
        self.assertTrue(run.result['conservation']['opex']['conserved'])
        transition(self.a,p.pk,'revoked')
        with self.assertRaises(ValidationError):analysis.ensure_current(run)
    def test_native_declared_shares_and_replaced_evidence(self):
        v,p=self.configure(('50','50'),'declared_shares','100');mapping=analysis.map_source(self.a,self.c.pk,self.source.pk,[],rev(self.c))
        run=analysis.allocate(self.a,self.c.pk,mapping.pk,['opex'],rev(self.c));self.assertEqual(run.result['status'],'complete')
        add_evidence(self.a,self.c.pk,'finance_pool_contract',json.dumps(evidence_payload(v)),'synthetic:pool-replacement')
        with self.assertRaises(ValidationError):analysis.ensure_current(run)
    def test_invalid_share_draft_never_becomes_active(self):
        with self.assertRaisesMessage(ValidationError,'allocation_coverage_share_total_incomplete'):self.configure(('40','40'),'declared_shares','100')


from .test_factory_bu import FactoryBUTests
class CoverageFactoryTests(FactoryBUTests):
    @classmethod
    def setUpTestData(cls):super().setUpTestData();assert_staff_migrated_sql()
    def test_explicit_coverage_native_factory_receipt_and_stale_hold(self):
        f=self.f;v=staff_value(f);policy(f,STAFF,v);p=self.pipeline();self.finish(p)
        r=bu.exact(f['case'],p.work_id);self.assertEqual(r.payload['weight_contract'],v['weight_contract'])
        add_evidence(f['preparer'],f['case'].pk,'bu_pool_contract',json.dumps(evidence_payload(v,True)),'synthetic:factory-pool-replacement')
        from apps.workflows import factory_bu
        with self.assertRaises(ValidationError):factory_bu.verify(self.work,f['preparer'])
        from django.db import DatabaseError,transaction
        from apps.workflows.models import FactoryWork
        with self.assertRaises(DatabaseError),transaction.atomic():FactoryWork.objects.filter(pk=self.work.pk).update(status='verified')


def assert_staff_migrated_sql():
    """Require actual0082 and literal function equality; never install provisional SQL."""
    import importlib,difflib
    from django.db import connection
    m=importlib.import_module('apps.workflows.migrations.0082_allocation_coverage')
    removed=[line for line in difflib.ndiff(m.PARENT_SQL.splitlines(),m.SQL.splitlines()) if line.startswith('- ')]
    if removed:raise AssertionError('Existing BU clauses must remain byte-identical')
    assert_finance_migrated_sql()
    with connection.cursor() as cur:
        cur.execute("SELECT count(*) FROM django_migrations WHERE app='workflows' AND name='0082_allocation_coverage'")
        if cur.fetchone()[0]!=1:raise AssertionError('Actual workflows0082 is required')
        cur.execute("SELECT prosrc FROM pg_proc WHERE oid='psl_bu_current(bigint,integer)'::regprocedure")
        if cur.fetchone()[0]!=m.SQL.split('AS $$',1)[1].rsplit('$$;',1)[0]:raise AssertionError('Scoped staff guard differs from actual0082')


class CoverageSQLStaffTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.f=fixture();assert_staff_migrated_sql()
    def predicate(self,w):
        from django.db import connection
        with connection.cursor() as cur:
            cur.execute('SELECT psl_bu_current(%s)',[w.pk]);return cur.fetchone()[0]
    def test_sql_v2_scoped_evidence_and_forged_result_pin(self):
        from copy import copy
        f=self.f;v=staff_value(f);policy(f,STAFF,v);w=staff(f);self.assertTrue(self.predicate(w))
        forged=copy(w);forged.pk=None;forged.operation_key='forged-weight-pin';forged.reference='forged-weight-pin';forged.payload=deepcopy(w.payload)
        forged.payload['weight_contract']['denominator']='99';type(forged).objects.bulk_create([forged])
        self.assertFalse(self.predicate(forged));self.assertTrue(self.predicate(w))
        independent=evidence_payload(v,True);independent['pool']='independent-pool-B'
        add_evidence(f['preparer'],f['case'].pk,'bu_pool_contract',json.dumps(independent),'synthetic:sql-B')
        self.assertTrue(self.predicate(w))
        add_evidence(f['preparer'],f['case'].pk,'bu_pool_contract',json.dumps(evidence_payload(v,True)),'synthetic:sql-A-replaced')
        self.assertFalse(self.predicate(w))
    def test_sql_absent_null_wrong_types_fail_closed(self):
        from django.db import connection
        f=self.f;baseline=staff_value(f)
        variants=[('mode',None),('mode',[]),('mode','unknown'),('mode','__absent__'),
                  ('method',None),('method',{}),('method','__absent__'),
                  ('evidence_id',None),('evidence_id',{}),('evidence_id','__string_id__'),('evidence_id','__absent__'),
                  ('denominator',None),('denominator',100),('denominator',[]),('denominator','__absent__')]
        for key,bad in variants:
            v=deepcopy(baseline)
            if key=='method':
                if bad=='__absent__':v.pop('standard_method')
                else:v['standard_method']=bad
            elif key!='evidence_id':
                if bad=='__absent__':v['weight_contract'].pop(key)
                else:v['weight_contract'][key]=bad
            e=add_evidence(f['preparer'],f['case'].pk,'bu_pool_contract',json.dumps(evidence_payload(v,True)),'synthetic:sql-malformed-contract')
            v['pool_contract_evidence_id']=v['weight_contract']['evidence_id']=e.pk
            if key=='evidence_id':
                if bad=='__absent__':v['weight_contract'].pop(key)
                else:v['weight_contract'][key]=str(e.pk) if bad=='__string_id__' else bad
            with self.subTest(key=key,bad=bad),connection.cursor() as cur:
                cur.execute('SELECT psl_allocation_v2_contract_current(%s,%s::jsonb,true)',[f['case'].pk,json.dumps(v)])
                self.assertIs(cur.fetchone()[0],False)
    def test_sql_claimed_v2_reference_requires_exact_artifact_identity(self):
        from django.db import connection
        from apps.policy.services import save_draft
        f=self.f;v=staff_value(f);p=policy(f,STAFF,v)
        for bad in [None,'missing-reference',{}]:
            envelope=deepcopy(p.envelope);envelope['value']['artifact_ref']=bad
            draft=save_draft(f['preparer'],f['case'].pk,envelope)
            with self.subTest(reference=bad),connection.cursor() as cur:
                cur.execute('SELECT psl_allocation_v2_policy_current(%s,%s)',[f['case'].pk,draft.pk]);self.assertIs(cur.fetchone()[0],False)

    def test_sql_supported_v1_staff_behavior_unchanged(self):
        w=staff(self.f);self.assertTrue(self.predicate(w));report=publish(self.f,w)
        self.assertTrue(bu.read_report(self.f['manager'],report.pk)['conserved'])
        from copy import copy
        forged=copy(w);forged.pk=None;forged.reference=forged.operation_key='forged-v2-on-v1'
        forged.payload=deepcopy(w.payload);forged.payload['weight_semantics']='explicit_contract';forged.payload['weight_contract']=contract()
        type(forged).objects.bulk_create([forged]);self.assertFalse(self.predicate(forged))

    def test_sql_rejects_incomplete_and_future_scope_is_independent(self):
        from django.db import connection
        f=self.f;v=staff_value(f);policy(f,STAFF,v);w=staff(f)
        future=evidence_payload(v,True);future['from_period']=future['to_period']='2026-10'
        add_evidence(f['preparer'],f['case'].pk,'bu_pool_contract',json.dumps(future),'synthetic:sql-future')
        self.assertTrue(self.predicate(w))
        forged=deepcopy(v);forged['standard_weights']=[dict(r,weight='40') for r in forged['standard_weights']]
        with connection.cursor() as cur:
            cur.execute('SELECT psl_allocation_v2_contract_current(%s,%s::jsonb,true)',[f['case'].pk,json.dumps(forged)])
            self.assertFalse(cur.fetchone()[0])


def assert_finance_migrated_sql():
    """No provisional DDL: require the actual0066 history and literal bodies."""
    import importlib,re
    from django.db import connection
    sql=importlib.import_module('apps.finance.migrations.0066_allocation_coverage').SQL
    functions=re.findall(r'CREATE FUNCTION (\w+)\(.*? AS \$\$(.*?)\$\$;',sql,re.S)
    if len(functions)!=4:raise AssertionError('Expected four narrow Finance functions')
    with connection.cursor() as cur:
        cur.execute("SELECT count(*) FROM django_migrations WHERE app='finance' AND name='0066_allocation_coverage'")
        if cur.fetchone()[0]!=1:raise AssertionError('Actual Finance0066 migration is required')
        for name,body in functions:
            cur.execute("SELECT prosrc FROM pg_proc WHERE pronamespace='public'::regnamespace AND proname=%s",[name])
            if cur.fetchall()!=[(body,)]:raise AssertionError('Finance guard differs: '+name)


class CoverageSQLFinanceTests(FinancePoolCoverageTests):
    @classmethod
    def setUpTestData(cls):super().setUpTestData();assert_finance_migrated_sql()
    def test_v2_insert_pins_and_scoped_evidence(self):
        from copy import copy
        from django.db import DatabaseError,transaction,connection
        v,p=self.configure(('50','50'),'declared_shares','100')
        mapping=analysis.map_source(self.a,self.c.pk,self.source.pk,[],rev(self.c))
        run=analysis.allocate(self.a,self.c.pk,mapping.pk,['opex'],rev(self.c));self.assertEqual(run.result['status'],'complete')
        independent=evidence_payload(v);independent['pool']='independent-pool-B'
        add_evidence(self.a,self.c.pk,'finance_pool_contract',json.dumps(independent),'synthetic:sql-finance-B')
        analysis.ensure_current(run)
        with connection.cursor() as cur:
            cur.execute('SELECT psl_allocation_v2_result_current(%s,%s,%s::jsonb)',[self.c.pk,p.pk,json.dumps(run.result)])
            self.assertTrue(cur.fetchone()[0])
        forged=copy(run);forged.pk=None;forged.operation_key='forged-coverage-result';forged.result=deepcopy(run.result)
        row=next(r for r in forged.result['rows'] if r['treatment']=='pool');row['basis']['weight_contract']['denominator']='99'
        with self.assertRaisesMessage(DatabaseError,'Explicit v2 allocation coverage'),transaction.atomic():type(forged).objects.bulk_create([forged])
        for case in ['missing_pin','wrong_pool']:
            changed=copy(run);changed.pk=None;changed.operation_key='forged-'+case;changed.snapshot=deepcopy(run.snapshot);changed.result=deepcopy(run.result)
            if case=='missing_pin':changed.snapshot['policies']['D07.allocation_pool_rules']['id']=None
            else:next(r for r in changed.result['rows'] if r['treatment']=='pool')['pool']='not-the-pinned-pool'
            with self.subTest(case=case),self.assertRaisesMessage(DatabaseError,'Explicit v2 allocation coverage'),transaction.atomic():type(changed).objects.bulk_create([changed])
        add_evidence(self.a,self.c.pk,'finance_pool_contract',json.dumps(evidence_payload(v)),'synthetic:sql-finance-replaced')
        stale=copy(run);stale.pk=None;stale.operation_key='stale-coverage-result'
        with self.assertRaisesMessage(DatabaseError,'Explicit v2 allocation coverage'),transaction.atomic():type(stale).objects.bulk_create([stale])

    def test_v1_allocation_and_unrelated_formula_inserts_unchanged(self):
        from .finance_analysis_helpers import METRICS
        mapping=analysis.map_source(self.a,self.c.pk,self.source.pk,[],rev(self.c))
        run=analysis.allocate(self.a,self.c.pk,mapping.pk,METRICS,rev(self.c))
        self.assertEqual(run.result['status'],'complete')
        formula=analysis.calculate(self.a,self.c.pk,run.pk,rev(self.c))
        self.assertEqual(formula.kind,'formula');self.assertEqual(formula.result['status'],'complete')


class FinanceCoveragePrimitiveSQLTests(TestCase):
    @classmethod
    def setUpTestData(cls):cls.f=fixture();assert_finance_migrated_sql()
    def test_actual0066_contract_null_and_wrong_type_guards(self):
        CoverageSQLStaffTests.test_sql_absent_null_wrong_types_fail_closed(self)
    def test_actual0066_artifact_identity_guards(self):
        CoverageSQLStaffTests.test_sql_claimed_v2_reference_requires_exact_artifact_identity(self)

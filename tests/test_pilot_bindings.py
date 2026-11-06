import copy,io,json,os,subprocess,sys
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError,PermissionDenied
from django.core.management import call_command,load_command_class,CommandError
from django.db import transaction,DatabaseError,connection
from django.test import TestCase,TransactionTestCase,Client,override_settings
from django.urls import reverse
from django.utils import timezone
from apps.core.models import Audit,Evidence
from apps.identity.models import Grant
from apps.policy import pilot,pilot_bindings as d,pilot_binding_validators as v
from apps.policy.models import PilotBinding,PilotBindingReview,PilotRuntimeReceipt
from apps.policy.services import transition,resolve
from apps.pmo.models import Decision,Baseline,Milestone
from apps.pmo import services as pmo
from apps.workflows.models import Outbox
from adapters import pilot_guards,pilot_runtime,pilot_preflight
from tests.helpers import setup_case,prepared,rev
from tests.test_pilot_preflight import selection


def fixture(prefix='native-pilot'):
    a,c=setup_case(username=prefix);e=prepared(a,c)
    b=get_user_model().objects.create_user(username=prefix+'-reviewer')
    Grant.objects.bulk_create([Grant(case=c,user=b,action=k) for k in Grant.objects.filter(case=c,user=a).values_list('action',flat=True)])
    p=selection(a,c);p['operations']=list(pilot_guards.REGISTRY)
    contract=pilot.configure(a,c.pk,p)
    example=json.loads((settings.BASE_DIR/'fixtures/pilot-bindings.json').read_text(encoding='utf-8'))
    actual=pilot_preflight.technical();deploy=dict(example['deployment'],expected={k:actual[k] for k in ['source_identity','schema_identity','database_identity']})
    payload={'format':'psl.pilot-bindings/v1','guards':[{'operation':'pmo.decision.record','user_id':a.pk,'arguments':{'role':'PM','expected_revision':rev(c)}}],'deployment':deploy}
    binding=d.configure(a,c.pk,contract.pk,payload)
    profiles={}
    for role in ['web','worker']:
        profiles[deploy[role+'_key_ref']]=dict(example['profile'],role=role,principal_id=a.pk,case_id=str(c.pk),families=deploy['families'] if role=='worker' else [],secret_env='PSL_PILOT_TEST_'+role.upper())
    return {'a':a,'b':b,'c':c,'e':e,'contract':contract,'binding':binding,'payload':payload,'profiles':profiles}


def environments():return {'PSL_PILOT_TEST_WEB':'explicit-synthetic-web-role-token-123456789','PSL_PILOT_TEST_WORKER':'explicit-synthetic-worker-role-token-987654321'}


class NativeGuardTests(TestCase):
    def setUp(self):self.f=fixture()

    def test_shared_guard_matches_actual_decision_and_does_not_write_domain_records(self):
        f=self.f;before=(Decision.objects.count(),Milestone.objects.count(),Outbox.objects.count(),Evidence.objects.count())
        result=d.report(f['a'],f['c'],f['contract'])
        self.assertEqual(result['native_guards'][0]['state'],'READY_AT_OBSERVATION')
        pack=pilot.capture(f['a'],f['c'].pk,f['contract'].pk)
        self.assertTrue(pilot.inspect(f['a'],f['c'].pk,pack.pk)['current'])
        checks={p['operation']:p['domain_runtime_guards'] for p in pack.snapshot['policies']}
        self.assertEqual(checks['pmo.decision.record'],'READY_AT_OBSERVATION')
        self.assertEqual(checks['pmo.baseline.prepare'],'NOT_EVALUATED')
        self.assertFalse(result['native_guard_coverage_complete'])
        self.assertIn('pmo.baseline.prepare',result['unbound_operations'])
        self.assertEqual(before,(Decision.objects.count(),Milestone.objects.count(),Outbox.objects.count(),Evidence.objects.count()))
        pmo.decide(f['a'],f['c'].pk,'PM',rev(f['c']))
        self.assertFalse(pilot.inspect(f['a'],f['c'].pk,pack.pk)['current'])
        self.assertEqual(d.report(f['a'],f['c'],f['contract'])['native_guards'][0]['state'],'HELD')

    def test_sequence_signature_and_milestone_guards_use_actual_native_services(self):
        f=self.f;a,c,e=f['a'],f['c'],f['e']
        def check(op,**args):
            c.refresh_from_db()
            return pilot_guards.check(a,c,{'operation':op,'user_id':a.pk,'arguments':dict(args,expected_revision=c.revision)})['state']
        self.assertEqual(check('pmo.decision.record',role='Head of PMO'),'HELD')
        self.assertEqual(check('pmo.baseline.sign',signature_id=e['signature'].pk),'HELD')
        for role in ['PM','Head of PMO','CEO','PMO Lead']:pmo.decide(a,c.pk,role,rev(c))
        self.assertEqual(check('pmo.baseline.sign',signature_id=e['signature'].pk),'READY_AT_OBSERVATION')
        pmo.sign_baseline(a,c.pk,e['signature'].pk,rev(c))
        self.assertEqual(check('pmo.milestone.complete',name='Exact delivery',evidence_id=e['completion'].pk),'READY_AT_OBSERVATION')
        self.assertEqual(Outbox.objects.count(),0)
        pmo.complete_milestone(a,c.pk,'Exact delivery',e['completion'].pk,rev(c))
        self.assertEqual(check('pmo.milestone.complete',name='Exact delivery',evidence_id=e['completion'].pk),'HELD')
        self.assertEqual(Outbox.objects.count(),1)

    def test_missing_revoked_authority_and_observer_rights_are_distinct(self):
        f=self.f;p=resolve('D05.role_principal_assignments',f['c']).configuration
        transition(f['a'],p.pk,'revoked')
        result=d.report(f['a'],f['c'],f['contract'])['native_guards'][0]
        self.assertEqual(result['state'],'HELD');self.assertEqual(result['findings'][0]['code'],'policy_hold')
        Grant.objects.filter(user=f['a'],case=f['c'],action='planning.read').update(active=False)
        with self.assertRaises(PermissionDenied):d.report(f['a'],f['c'],f['contract'])

    def test_closed_binding_validator_and_foreign_sources(self):
        f=self.f;other,c=setup_case(username='binding-foreign');e=prepared(other,c)
        for field,value in [('guards',[]),('format','arbitrary'),('credential','do not accept this')]:
            p=copy.deepcopy(f['payload']);p[field]=value
            with self.assertRaises(ValidationError):v.validate(f['contract'],p)
        p=copy.deepcopy(f['payload']);p['guards'][0]['user_id']=other.pk
        with self.assertRaises(ValidationError):v.validate(f['contract'],p)
        p=copy.deepcopy(f['payload']);p['guards']=[{'operation':'pmo.baseline.sign','user_id':f['a'].pk,'arguments':{'expected_revision':1,'signature_id':e['signature'].pk}}]
        with self.assertRaises(ValidationError):v.validate(f['contract'],p)
        p=copy.deepcopy(f['payload']);p['deployment']['worker_key_ref']=p['deployment']['web_key_ref']
        with self.assertRaises(ValidationError):v.validate(f['contract'],p)

    def test_independent_engineering_review_is_not_business_approval_and_revocation_invalidates(self):
        f=self.f
        with self.assertRaises(PermissionDenied):d.review(f['a'],f['c'].pk,f['binding'].pk,'accept','Self review')
        d.review(f['b'],f['c'].pk,f['binding'].pk,'accept','Synthetic technical selection only')
        self.assertTrue(d.report(f['a'],f['c'],f['contract'])['review_current']);self.assertEqual(Decision.objects.count(),0)
        pack=pilot.capture(f['a'],f['c'].pk,f['contract'].pk)
        Grant.objects.filter(case=f['c'],user=f['b'],action='pilot.binding.review').update(active=False)
        self.assertFalse(pilot.inspect(f['a'],f['c'].pk,pack.pk)['current'])

    def test_exact_contract_binding_and_unknown_operation_coverage(self):
        f=self.f;new=pilot.configure(f['a'],f['c'].pk,f['contract'].payload,f['contract'].pk)
        value=pilot.observation(f['a'],f['c'],new.payload,new)
        self.assertEqual(value['bindings']['state'],'UNCONFIGURED')
        with self.assertRaises(ValidationError):d.review(f['b'],f['c'].pk,f['binding'].pk,'accept','Old selection')
        self.assertIn('16 declared native',d.report(f['a'],f['c'],f['contract'])['coverage'])

    def test_report_and_native_guard_enforce_case_access_before_record_lookup(self):
        f=self.f
        Grant.objects.filter(case=f['c'],user=f['a'],action='case.read').update(active=False)
        with patch('apps.policy.pilot_bindings.PilotBinding.objects.select_related') as query:
            with self.assertRaises(PermissionDenied):d.report(f['a'],f['c'],f['contract'])
            query.assert_not_called()
        with self.assertRaises(PermissionDenied):pilot_guards.check(f['a'],f['c'],f['payload']['guards'][0])
        Grant.objects.filter(case=f['c'],user=f['a'],action='case.read').update(active=True)
        other,case=setup_case(username='foreign-report-owner')
        contract=pilot.configure(other,case.pk,selection(other,case))
        with patch('apps.policy.pilot_bindings.PilotBinding.objects.select_related') as query:
            with self.assertRaises(ValidationError):d.report(f['a'],f['c'],contract)
            query.assert_not_called()

    def test_sql_history_identity_and_self_review_guards(self):
        f=self.f;b=f['binding']
        with self.assertRaises(DatabaseError),transaction.atomic():PilotBinding.objects.filter(pk=b.pk).update(sha256='0'*64)
        with self.assertRaises(DatabaseError),transaction.atomic():PilotBindingReview.objects.create(binding=b,actor=f['a'],sha256=b.sha256,verdict='accept',reason='self')
        with self.assertRaises(DatabaseError),transaction.atomic():PilotRuntimeReceipt.objects.create(binding=b,payload={'role':'worker'},sha256='0'*64,signature='1'*64)

    def test_csrf_ui_binding_selection_review_web_observation_and_agent(self):
        from apps.agents.pilot import investigate
        f=self.f;client=Client(enforce_csrf_checks=True);client.force_login(f['b'])
        url=reverse('pilot_binding',args=[f['c'].pk,f['binding'].pk]);response=client.get(url)
        self.assertContains(response,'Native operation guards');self.assertEqual(response['Cache-Control'],'no-store')
        self.assertEqual(client.post(url,{'verdict':'accept','reason':'test'}).status_code,403)
        response=client.post(url,{'verdict':'accept','reason':'Engineering only','csrfmiddlewaretoken':client.cookies['csrftoken'].value})
        self.assertEqual(response.status_code,302)
        client.force_login(f['a'])
        with override_settings(PILOT_RUNTIME_IDENTITIES=f['profiles']),patch.dict(os.environ,environments()):
            response=client.post(url,{'command':'observe_web','csrfmiddlewaretoken':client.cookies['csrftoken'].value})
            self.assertEqual(response.status_code,302)
        form=client.get(reverse('pilot_bindings',args=[f['c'].pk,f['contract'].pk]));self.assertContains(form,'Expected fingerprints')
        pack=pilot.capture(f['a'],f['c'].pk,f['contract'].pk);self.assertEqual(investigate(f['a'],f['c'].pk,pack.pk)['effect_tools'],[])


class RuntimeBindingTests(TestCase):
    def setUp(self):
        self.f=fixture('runtime-binding');self.settings=override_settings(PILOT_RUNTIME_IDENTITIES=self.f['profiles']);self.settings.enable();self.addCleanup(self.settings.disable)
        self.env=patch.dict(os.environ,environments());self.env.start();self.addCleanup(self.env.stop)
        d.review(self.f['b'],self.f['c'].pk,self.f['binding'].pk,'accept','Technical identity binding')

    def emit(self,role='web',family=None):return d.emit(self.f['a'],self.f['c'].pk,self.f['binding'].pk,role,family)
    def report(self):return d.report(self.f['a'],self.f['c'],self.f['contract'])

    def test_actual_native_receipts_same_process_is_insufficient(self):
        self.emit('worker','handoff');self.assertFalse(self.report()['independent_processes'])
        self.emit();self.emit('worker','handoff')
        self.assertFalse(self.report()['independent_processes']);self.assertFalse(self.report()['worker_deployment_ready'])
        with patch('adapters.pilot_runtime.BOOT','synthetic-other-process'):
            self.emit('worker','handoff')
        result=self.report();self.assertTrue(result['worker_deployment_ready']);self.assertFalse(result['operational_acceptance'])
        self.assertNotIn(environments()['PSL_PILOT_TEST_WEB'],json.dumps(result));self.assertEqual(result['effect_tools'],[])
        pilot.configure(self.f['a'],self.f['c'].pk,self.f['contract'].payload,self.f['contract'].pk)
        self.assertFalse(self.report()['contract_current']);self.assertFalse(self.report()['worker_deployment_ready'])

    def test_startup_build_pin_rejects_changed_source_and_legacy_receipts(self):
        web=self.emit()
        self.assertEqual(web.payload['format'],'psl.pilot-runtime/v2')
        with override_settings(PROCESS_BUILD_IDENTITY='0'*64):
            with self.assertRaises(ValidationError):self.emit()
            self.assertFalse(self.report()['receipts'][0]['current'])
        legacy=copy.deepcopy(web.payload);legacy['format']='psl.pilot-runtime/v1';legacy.pop('process_build_identity')
        PilotRuntimeReceipt.objects.create(binding=self.f['binding'],payload=legacy,sha256=pilot_runtime.digest(legacy),signature=web.signature)
        self.assertFalse(self.report()['receipts'][0]['current'])

    def test_physical_schema_drift_invalidates_receipts_with_unchanged_migration_heads(self):
        self.emit()
        self.assertTrue(self.report()['receipts'][0]['current'])
        before=pilot_preflight.technical()['migration_identity']
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute('SET CONSTRAINTS ALL IMMEDIATE')
                cursor.execute('CREATE INDEX psl_pilot_fixture_index ON policy_pilotruntimereceipt(created_at)')
            self.assertEqual(pilot_preflight.technical()['migration_identity'],before)
            self.assertFalse(self.report()['receipts'][0]['current'])
            transaction.set_rollback(True)
        self.assertTrue(self.report()['receipts'][0]['current'])
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute('SET CONSTRAINTS ALL IMMEDIATE')
                cursor.execute('ALTER TABLE policy_pilotruntimereceipt ALTER COLUMN signature TYPE varchar(65)')
            self.assertEqual(pilot_preflight.technical()['migration_identity'],before)
            self.assertFalse(self.report()['receipts'][0]['current'])
            transaction.set_rollback(True)
        self.assertTrue(self.report()['receipts'][0]['current'])

    def test_expired_rotated_revoked_and_bad_signatures_never_use_older_success(self):
        web=self.emit()
        with patch.dict(os.environ,{'PSL_PILOT_TEST_WEB':'rotated-new-synthetic-key-material-1111111'}):self.assertFalse(self.report()['receipts'][0]['current'])
        with patch('django.utils.timezone.now',return_value=timezone.now()+timedelta(seconds=301)):
            self.assertFalse(self.report()['receipts'][0]['current'])
        Grant.objects.filter(case=self.f['c'],user=self.f['a'],action='pilot.runtime.observe').update(active=False)
        self.assertFalse(self.report()['receipts'][0]['current'])
        Grant.objects.filter(case=self.f['c'],user=self.f['a'],action='pilot.runtime.observe').update(active=True)
        PilotRuntimeReceipt.objects.create(binding=self.f['binding'],payload=web.payload,sha256=web.sha256,signature='0'*64)
        self.assertFalse(self.report()['receipts'][0]['current'])
        with self.assertRaises(DatabaseError),transaction.atomic():PilotRuntimeReceipt.objects.filter(pk=web.pk).update(signature='1'*64)

    def test_no_role_alias_secret_installation_or_cross_family_claim(self):
        with patch.dict(os.environ,{'PSL_PILOT_TEST_WORKER':environments()['PSL_PILOT_TEST_WEB']}):
            with self.assertRaises(ValidationError):self.emit()
        with self.assertRaises(ValidationError):self.emit('worker','invoice')
        with self.assertRaises(ValidationError):self.emit('web','handoff')
        with override_settings(PILOT_RUNTIME_IDENTITIES={}):
            with self.assertRaises(ValidationError):self.emit()
        self.assertEqual(PilotRuntimeReceipt.objects.count(),0)

    def test_all_sixteen_native_worker_entrypoints_support_observe_only(self):
        f=self.f;p=copy.deepcopy(f['payload']);p['deployment']['families']=list(v.WORKERS)
        contract=pilot.configure(f['a'],f['c'].pk,f['contract'].payload,f['contract'].pk)
        binding=d.configure(f['a'],f['c'].pk,contract.pk,p)
        profiles=copy.deepcopy(f['profiles']);profiles['fixture-worker']['families']=list(v.WORKERS)
        with override_settings(PILOT_RUNTIME_IDENTITIES=profiles):
            for family,module in v.WORKERS.items():
                command=load_command_class(module.split('.management.')[0],module.rsplit('.',1)[1]);parser=command.create_parser('manage.py',module.rsplit('.',1)[1])
                args=['--pilot-binding',str(binding.pk),'--pilot-observe-only']
                for action in parser._actions:
                    if action.required:
                        self.assertIn(action.dest,['case','case_id']);args.extend([action.option_strings[0],str(f['c'].pk)])
                output=io.StringIO();call_command(command,*args,stdout=output)
                self.assertIn('business worker not invoked',output.getvalue())
                self.assertTrue(PilotRuntimeReceipt.objects.filter(binding=binding,payload__family=family).exists())
        self.assertEqual(Outbox.objects.count(),0)


class NativeProcessTests(TransactionTestCase):
    @override_settings(DEBUG=True,SESSION_COOKIE_SECURE=False,CSRF_COOKIE_SECURE=False)
    def test_independent_actual_worker_process_observes_without_claiming_pending_work(self):
        f=fixture('independent-runtime');a,c=f['a'],f['c']
        for role in ['PM','Head of PMO','CEO','PMO Lead']:pmo.decide(a,c.pk,role,rev(c))
        pmo.sign_baseline(a,c.pk,f['e']['signature'].pk,rev(c));pmo.complete_milestone(a,c.pk,'Pending real fixture handoff',f['e']['completion'].pk,rev(c))
        with override_settings(PILOT_RUNTIME_IDENTITIES=f['profiles']),patch.dict(os.environ,environments()):
            d.emit(a,c.pk,f['binding'].pk,'web');d.review(f['b'],c.pk,f['binding'].pk,'accept','Independent technical review')
            env=os.environ.copy();env.update(PGDATABASE=connection.settings_dict['NAME'],PSL_PILOT_RUNTIME_IDENTITIES=json.dumps(f['profiles']),PSL_ENV='development',PSL_SECRET_KEY=settings.SECRET_KEY)
            result=subprocess.run([sys.executable,'manage.py','work_outbox','--pilot-binding',str(f['binding'].pk),'--pilot-observe-only'],env=env,capture_output=True,text=True,timeout=45)
            self.assertEqual(result.returncode,0,result.stderr);self.assertIn('business worker not invoked',result.stdout)
            self.assertTrue(d.report(a,c,f['contract'])['worker_deployment_ready'])
            job=Outbox.objects.get();self.assertEqual(job.status,'pending');self.assertEqual(job.attempts,0)
            Grant.objects.filter(case=c,user=a,action='pilot.runtime.observe').update(active=False)
            result=subprocess.run([sys.executable,'manage.py','work_outbox','--pilot-binding',str(f['binding'].pk),'--pilot-observe-only'],env=env,capture_output=True,text=True,timeout=45)
            self.assertNotEqual(result.returncode,0);self.assertNotIn(environments()['PSL_PILOT_TEST_WORKER'],result.stderr)

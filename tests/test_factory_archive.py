import json
from pathlib import Path
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError,PermissionDenied
from django.db import connection,transaction,DatabaseError
from django.test import TestCase,TransactionTestCase
from django.urls import reverse
from django.utils import timezone
from apps.core.models import Evidence
from apps.core.services import add_evidence
from apps.identity.models import Grant
from apps.policy.operator_drafts import draft_operator_policy
from apps.policy.services import transition
from apps.pmo import delivery_closure as closure
from apps.pmo.models import DeliveryRecord
from apps.workflows import factory,factory_archive as archive
from apps.workflows.models import FactoryWork,HumanTask
from tests.test_delivery import DeliveryFixture
from tests.helpers import rev,setup_case


def configure(f,owner=True,tokens=20000):
    value=json.loads(Path('fixtures/factory-archive.json').read_text());value.pop('classification')
    value.update(executor_id=f.operator.pk if owner else None,max_tokens=tokens)
    p=draft_operator_policy(f.actor,f.case.pk,'OPS.factory_archive_execution',value,f.e['policy_decision'].pk,timezone.now())
    transition(f.actor,p.pk,'validated');transition(f.actor,p.pk,'active');return p


def setup(profile=True,owner=True,known=True):
    f=DeliveryFixture();f.setup_delivery()
    f.operator=get_user_model().objects.create_user(username='synthetic-archive-operator')
    Grant.objects.bulk_create([Grant(case=f.case,user=f.operator,action=a) for a in ['case.read','delivery.read','factory.execute','delivery.manage']])
    f.inventory={k:f.evidence(k).pk if known else None for k in archive.CORE_KINDS}
    if profile:f.profile=configure(f,owner)
    f.work=archive.start(f.actor,f.case.pk,'ARCHIVE-1',f.d.pk,f.inventory,'Final project evidence',rev(f.case));return f


def ready(f):
    f.accepted();f.storage()
    f.source('technical_finalization',evidence=Evidence.objects.get(pk=f.inventory['technical_document']))


class FactoryArchiveTests(TestCase):
    def test_stopped_work_with_a_superseded_unsigned_baseline_cannot_offer_or_execute_restart(self):
        from tests.helpers import prepared
        from apps.pmo.services import prepare_baseline
        from apps.pmo.delivery import open_dossier
        from apps.pmo.gates import register_candidate
        actor,case=setup_case(username='synthetic-unsigned-archive');e=prepared(actor,case)
        candidate=register_candidate(actor,case.pk,'Unsigned archive candidate',e['requirements'].pk,rev(case))
        dossier=open_dossier(actor,case.pk,candidate.pk,e['plan'].pk,'Declared before final project evidence',rev(case))
        inventory={kind:add_evidence(actor,case.pk,kind,'Synthetic '+kind,'synthetic:archive').pk for kind in archive.CORE_KINDS}
        work=archive.start(actor,case.pk,'UNSIGNED-ARCHIVE',dossier.pk,inventory,'Declared project archive',rev(case))
        archive.cancel(actor,work.pk,work.revision);work.refresh_from_db()
        self.assertTrue(archive.projection(actor,work)['can_restart'])
        new={kind:add_evidence(actor,case.pk,kind,'Synthetic revised '+kind,'synthetic:archive').pk for kind in ['plan','costing','sow']}
        prepare_baseline(actor,case.pk,new['plan'],new['costing'],new['sow'],rev(case));work.refresh_from_db()
        self.assertFalse(archive.projection(actor,work)['can_restart'])
        self.client.force_login(actor);self.assertNotContains(self.client.get(reverse('factory_detail',args=[work.pk])),'Resume stopped archive work')
        with self.assertRaisesMessage(ValidationError,'Delivery baseline changed'):
            archive.restart(actor,work.pk,work.revision,rev(case),'Cannot restart the obsolete delivery dossier')
        work.refresh_from_db();self.assertEqual(work.status,'cancelled');self.assertEqual(work.budget_used,0)

    def test_stop_settlement_waits_for_an_active_lease_then_preserves_original_work(self):
        f=setup();original=f.work.source_head_id
        FactoryWork.objects.filter(pk=f.work.pk).update(lease_until=timezone.now()+timedelta(minutes=1))
        archive.cancel(f.actor,f.work.pk,f.work.revision);f.work.refresh_from_db()
        self.assertTrue(f.work.cancel_requested);self.assertNotEqual(f.work.status,'cancelled')
        self.assertFalse(archive.projection(f.actor,f.work)['can_settle'])
        with self.assertRaises(ValidationError):archive.restart(f.actor,f.work.pk,f.work.revision,rev(f.case),'Worker has not stopped')
        FactoryWork.objects.filter(pk=f.work.pk).update(lease_until=timezone.now()-timedelta(seconds=1))
        f.work.refresh_from_db()
        self.assertTrue(archive.projection(f.actor,f.work)['can_settle'])
        archive.cancel(f.actor,f.work.pk,f.work.revision);f.work.refresh_from_db();self.assertEqual(f.work.status,'cancelled')
        self.client.force_login(f.actor);page=self.client.get(reverse('factory_detail',args=[f.work.pk]))
        self.assertEqual(page.context['row']['owner'],f.actor.username)
        self.assertContains(page,'Review a fresh instruction before resuming stopped archive work')
        archive.restart(f.actor,f.work.pk,f.work.revision,rev(f.case),'Fresh instruction after expired local worker lease')
        f.work.refresh_from_db();self.assertNotEqual(f.work.source_head_id,original);self.assertFalse(f.work.cancel_requested)
        self.assertEqual(f.work.budget_used,0);self.assertFalse(DeliveryRecord.objects.filter(dossier=f.d,kind='archive').exists())

    def test_current_engineering_finalization_must_match_the_exact_declared_technical_document(self):
        f=setup();ready(f);new=f.evidence('technical_document','Synthetic revised final technical document')
        inventory=dict(f.inventory,technical_document=new.pk)
        archive.correct(f.actor,f.work.pk,f.work.revision,rev(f.case),inventory,'Declare the newly supplied exact technical document')
        factory.run_until_wait(f.work.pk);f.work.refresh_from_db();self.assertEqual(f.work.status,'waiting',f.work.finding)
        self.assertFalse(DeliveryRecord.objects.filter(dossier=f.d,kind='archive').exists())
        f.source('technical_finalization',evidence=new);factory.run_until_wait(f.work.pk);f.work.refresh_from_db()
        self.assertEqual(f.work.status,'verified',f.work.finding);self.assertEqual(archive.assessed(f.work).data['inventory'],inventory)

    def test_operator_revoked_while_planning_cannot_create_the_native_index(self):
        f=setup();ready(f);factory.run_once(f.work.pk)
        class Revoke:
            def choose(self,context):
                Grant.objects.filter(case=f.case,user=f.operator,action='delivery.manage').update(active=False)
                return {'activity':context['eligible'][0],'citations':context['evidence_ids']}
        factory.run_once(f.work.pk,provider=Revoke());f.work.refresh_from_db();self.assertEqual(f.work.status,'blocked',f.work.finding)
        self.assertFalse(DeliveryRecord.objects.filter(dossier=f.d,kind='archive').exists())
        factory.manage(f.actor,f.work.pk,f.work.revision,'resume');factory.run_until_wait(f.work.pk);f.work.refresh_from_db()
        self.assertEqual(f.work.status,'owner_needed',f.work.finding)

    def test_configuration_rejects_invented_approvals_private_sources_and_ungranted_operator(self):
        from types import SimpleNamespace
        from apps.policy.factory_validators import validate_reference,ARCHIVE_COMPONENT,ARCHIVE_SCHEMA
        f=setup(profile=False);other=get_user_model().objects.create_user(username='ungranted-archive-admin',is_superuser=True)
        value=json.loads(Path('fixtures/factory-archive.json').read_text());value.pop('classification')
        for changes in [{'review_role':'Head of PMO'},{'information_resolver_id':f.actor.pk},{'executor_id':other.pk},
            {'required_evidence_kinds':['p14_inputs']},{'tokens_per_call':20001},{'physical_purge':True}]:
            with self.assertRaises(ValidationError):validate_reference(ARCHIVE_COMPONENT,SimpleNamespace(schema_ref=ARCHIVE_SCHEMA,content=dict(value,**changes)),f.case)
        self.assertEqual(validate_reference(ARCHIVE_COMPONENT,SimpleNamespace(schema_ref=ARCHIVE_SCHEMA,content=value),f.case),value)

    def test_source_correction_http_binds_current_project_work_and_exact_public_choices(self):
        f=setup();ready(f);new=f.evidence('test_results','Synthetic current owner-supplied test results')
        values=dict(f.inventory,test_results=new.pk);self.client.force_login(f.actor);url=reverse('factory_detail',args=[f.work.pk])
        payload={'action':'correct_inventory','revision':f.work.revision,'case_revision':rev(f.case),'reason':'Use the exact current test results',
            **{'inventory_'+kind:pk for kind,pk in values.items()}}
        self.assertRedirects(self.client.post(url,payload),url);f.work.refresh_from_db()
        self.assertEqual(archive.source(f.work)[1]['inventory'],values)
        self.assertContains(self.client.post(url,payload),'Stale revision')
        self.assertFalse(DeliveryRecord.objects.filter(dossier=f.d,kind='archive').exists())

    def test_agent_creates_native_index_as_configured_operator_without_archive_approval_or_hypercare_gate(self):
        self.assertEqual(connection.vendor,'postgresql');f=setup();ready(f);factory.run_until_wait(f.work.pk);f.work.refresh_from_db()
        self.assertEqual(f.work.status,'verified',f.work.finding);r=archive.assessed(f.work)
        self.assertEqual(r.actor_id,f.operator.pk);self.assertEqual(r.data['inventory'],f.inventory);self.assertEqual(closure.current_archive(f.d).pk,r.pk)
        proof=archive.verify(f.work)
        for flag in ['external_bytes_verified','external_authenticity_verified','physical_purge_performed','support_handover_received','closure_approved','financial_release_granted','deployment_authorized']:self.assertIs(proof[flag],False)
        self.assertFalse(DeliveryRecord.objects.filter(dossier=f.d,kind__in=['hypercare','closure']).exists())
        self.assertFalse(HumanTask.objects.filter(case=f.case,kind='factory_review').exists())
        self.client.force_login(f.actor);page=self.client.get(reverse('factory_detail',args=[f.work.pk]))
        self.assertContains(page,'current archive index matches');self.assertNotContains(page,'Approve archive')

    def test_capture_and_inventory_correction_before_execution_or_business_rule_configuration(self):
        f=setup(profile=False,known=False);old=f.work.source_head_id;factory.run_until_wait(f.work.pk);f.work.refresh_from_db()
        self.assertEqual(f.work.status,'configuration_needed');self.assertEqual(f.work.budget_used,0)
        self.client.force_login(f.actor);url=reverse('factory_detail',args=[f.work.pk]);self.assertContains(self.client.get(url),'Not yet provided.')
        self.assertContains(self.client.get(reverse('factory_create')+'?definition=delivery-archive/v1&case='+str(f.case.pk)),'Start archive work')
        configure(f);f.inventory={k:f.evidence(k).pk for k in archive.CORE_KINDS}
        archive.correct(f.actor,f.work.pk,f.work.revision,rev(f.case),f.inventory,'Declare exact newly supplied source artifacts')
        factory.run_until_wait(f.work.pk);f.work.refresh_from_db();self.assertEqual(f.work.status,'configuration_needed',f.work.finding)
        self.assertFalse(DeliveryRecord.objects.filter(dossier=f.d,kind='archive').exists());self.assertTrue(Evidence.objects.filter(pk=old).exists())
        ready(f);factory.manage(f.actor,f.work.pk,f.work.revision,'resume');factory.run_until_wait(f.work.pk);f.work.refresh_from_db()
        self.assertEqual(f.work.status,'verified',f.work.finding)

    def test_missing_operator_holds_only_index_then_reviewed_profile_adoption_retains_original_allowance(self):
        f=setup(owner=False);ready(f);factory.run_until_wait(f.work.pk);f.work.refresh_from_db()
        self.assertEqual(f.work.status,'owner_needed',f.work.finding);spent=f.work.budget_used
        self.assertFalse(DeliveryRecord.objects.filter(dossier=f.d,kind='archive').exists())
        p=configure(f,tokens=40000);factory.adopt_profile(f.actor,f.work.pk,f.work.revision,p.pk,'Recorded synthetic archive operator and explicit reviewed adoption')
        factory.run_until_wait(f.work.pk);f.work.refresh_from_db();self.assertEqual(f.work.status,'verified',f.work.finding)
        self.assertEqual(f.work.budget_limit,20000);self.assertGreater(f.work.budget_used,spent)
        self.assertEqual(archive.assessed(f.work).actor_id,f.operator.pk)

    def test_foreign_private_wrong_kind_noninteger_stale_and_unauthorised_inventory_is_rejected(self):
        f=setup();other,case=setup_case(username='foreign-archive');foreign=add_evidence(other,case.pk,'technical_document','Foreign source','synthetic:foreign')
        private=add_evidence(f.actor,f.case.pk,'p14_inputs','PRIVATE-ARCHIVE-COST-DATA','synthetic:private')
        for values in [dict(f.inventory,technical_document=foreign.pk),dict(f.inventory,technical_document=f.e['requirements'].pk),
            dict(f.inventory,p14_inputs=private.pk),dict(f.inventory,technical_document=float(f.inventory['technical_document']))]:
            with self.assertRaises(ValidationError):archive.correct(f.actor,f.work.pk,f.work.revision,rev(f.case),values,'Denied source correction')
        with self.assertRaises(ValidationError):archive.correct(f.actor,f.work.pk,True,rev(f.case),f.inventory,'Invalid work version type')
        with self.assertRaises(ValidationError):archive.correct(f.actor,f.work.pk,f.work.revision,rev(f.case)-1,f.inventory,'Stale project version')
        with self.assertRaises(DatabaseError),transaction.atomic():FactoryWork.objects.filter(pk=f.work.pk).update(status='verified')
        Grant.objects.filter(case=f.case,user=f.actor,action='factory.manage').update(active=False)
        with self.assertRaises(PermissionDenied):archive.correct(f.actor,f.work.pk,f.work.revision,rev(f.case),f.inventory,'No correction authority')
        self.assertFalse(DeliveryRecord.objects.filter(dossier=f.d,kind='archive').exists())

    def test_declared_inventory_and_storage_successors_preserve_native_indexes_and_lifetime_work(self):
        f=setup();ready(f);factory.run_until_wait(f.work.pk);f.work.refresh_from_db();first=archive.assessed(f.work);head=f.work.source_head_id;spent=f.work.budget_used
        changed=dict(f.inventory,test_results=f.evidence('test_results','Synthetic successor test results').pk)
        archive.correct(f.actor,f.work.pk,f.work.revision,rev(f.case),changed,'Use the current owner-supplied test results')
        factory.run_until_wait(f.work.pk);f.work.refresh_from_db();self.assertEqual(f.work.status,'verified',f.work.finding)
        self.assertNotEqual(f.work.source_head_id,head);self.assertNotEqual(archive.assessed(f.work).pk,first.pk)
        self.assertTrue(DeliveryRecord.objects.filter(pk=first.pk).exists());self.assertGreater(f.work.budget_used,spent)
        f.storage();self.assertTrue(archive.projection(f.actor,f.work)['readiness_changed'])
        archive.reassess(f.actor,f.work.pk,f.work.revision,'Review the new current storage rule version')
        factory.run_until_wait(f.work.pk);f.work.refresh_from_db();self.assertEqual(f.work.status,'verified',f.work.finding)
        self.assertEqual(f.work.budget_limit,20000);self.assertEqual(DeliveryRecord.objects.filter(dossier=f.d,kind='archive').count(),3)

    def test_existing_native_index_is_observed_without_an_operator_appointment_or_duplicate(self):
        f=setup(owner=False);ready(f)
        r=closure.archive_artifacts(f.actor,f.case.pk,f.d.pk,f.inventory,f.e['requirements'].pk,'Existing human native archive index',rev(f.case))
        factory.run_until_wait(f.work.pk);f.work.refresh_from_db();self.assertEqual(f.work.status,'verified',f.work.finding)
        self.assertEqual(archive.assessed(f.work).pk,r.pk);self.assertEqual(DeliveryRecord.objects.filter(dossier=f.d,kind='archive').count(),1)

    def test_cancelled_local_index_work_restarts_by_fresh_human_instruction_without_budget_or_effect_replay(self):
        f=setup();ready(f)
        class Cancel:
            def choose(self,context):
                f.work.refresh_from_db();factory.manage(f.actor,f.work.pk,f.work.revision,'cancel')
                return {'activity':context['eligible'][0],'citations':context['evidence_ids']}
        factory.run_once(f.work.pk,provider=Cancel());f.work.refresh_from_db();spent=f.work.budget_used
        self.assertEqual(f.work.status,'cancelled');self.assertFalse(DeliveryRecord.objects.filter(dossier=f.d,kind='archive').exists())
        archive.restart(f.actor,f.work.pk,f.work.revision,rev(f.case),'New human instruction after the synthetic cancellation')
        factory.run_until_wait(f.work.pk);f.work.refresh_from_db();self.assertEqual(f.work.status,'verified',f.work.finding)
        self.assertEqual(f.work.budget_limit,20000);self.assertGreater(f.work.budget_used,spent);self.assertEqual(DeliveryRecord.objects.filter(dossier=f.d,kind='archive').count(),1)

    def test_cancel_after_native_index_then_resume_observes_original_index_once(self):
        f=setup();ready(f)
        for _ in range(8):
            factory.run_once(f.work.pk);f.work.refresh_from_db()
            if DeliveryRecord.objects.filter(dossier=f.d,kind='archive').exists():break
        row=archive.assessed(f.work);self.assertIsNotNone(row);self.assertNotEqual(f.work.status,'verified')
        archive.cancel(f.actor,f.work.pk,f.work.revision);f.work.refresh_from_db();self.assertEqual(f.work.status,'cancelled')
        archive.restart(f.actor,f.work.pk,f.work.revision,rev(f.case),'Observe the already-created local index after a fresh human instruction')
        factory.run_until_wait(f.work.pk);f.work.refresh_from_db();self.assertEqual(f.work.status,'verified',f.work.finding)
        self.assertEqual(archive.assessed(f.work).pk,row.pk);self.assertEqual(DeliveryRecord.objects.filter(dossier=f.d,kind='archive').count(),1)

    def test_private_run_projections_read_only_controls_and_revoked_source_authority(self):
        f=setup();ready(f);factory.run_until_wait(f.work.pk);f.work.refresh_from_db()
        reader=get_user_model().objects.create_user(username='synthetic-archive-reader')
        Grant.objects.bulk_create([Grant(case=f.case,user=reader,action=a) for a in ['case.read','delivery.read','factory.read']])
        Grant.objects.filter(case=f.case,user=f.actor,action='factory.start').update(active=False)
        self.client.force_login(reader);page=self.client.get(reverse('factory_detail',args=[f.work.pk]))
        self.assertEqual(page.status_code,200);self.assertContains(page,'intake authority');self.assertNotContains(page,'Update declared inventory')
        self.assertNotContains(page,'Continue eligible work');self.assertTrue(archive.projection(reader,f.work)['readiness_changed'])
        generic=self.client.get(reverse('case',args=[f.case.pk]));self.assertEqual(list(generic.context['runs']),[])


class FactoryArchiveConcurrencyTests(TransactionTestCase):
    def test_real_worker_exit_rolls_back_index_then_recovers_one_native_output(self):
        import os,sys,subprocess
        f=setup();ready(f);env=dict(os.environ,PGDATABASE=connection.settings_dict['NAME'])
        result=subprocess.run([sys.executable,'-m','tests.factory_worker_scenario',str(f.work.pk),'interrupt_after_action'],env=env,capture_output=True,timeout=120)
        self.assertEqual(result.returncode,38,result.stderr.decode());f.work.refresh_from_db();spent=f.work.budget_used
        self.assertFalse(DeliveryRecord.objects.filter(dossier=f.d,kind='archive').exists());self.assertTrue(f.work.activities.filter(attempts__phase='started').exists())
        FactoryWork.objects.filter(pk=f.work.pk).update(lease_until=timezone.now()-timedelta(seconds=1))
        result=subprocess.run([sys.executable,'-m','tests.factory_worker_scenario',str(f.work.pk),'resume'],env=env,capture_output=True,timeout=120)
        self.assertEqual(result.returncode,0,result.stderr.decode());factory.run_until_wait(f.work.pk);f.work.refresh_from_db()
        self.assertEqual(f.work.status,'verified',f.work.finding);self.assertGreater(f.work.budget_used,spent)
        self.assertEqual(f.work.budget_limit,20000);self.assertEqual(DeliveryRecord.objects.filter(dossier=f.d,kind='archive').count(),1)

    def test_two_first_forms_share_one_native_intake_and_budget(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier
        from django.db import close_old_connections
        f=DeliveryFixture();f.setup_delivery();inventory={k:f.evidence(k).pk for k in archive.CORE_KINDS};barrier=Barrier(2)
        def enter(n):
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                return archive.start(f.actor,f.case.pk,'ARCHIVE-RACE-'+str(n),f.d.pk,inventory,'One declared archive intent').pk
            finally:close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:ids=list(pool.map(enter,[1,2]))
        self.assertEqual(ids[0],ids[1]);self.assertEqual(FactoryWork.objects.filter(case=f.case).count(),1)
        self.assertEqual(Evidence.objects.filter(case=f.case,kind=archive.KIND).count(),1)

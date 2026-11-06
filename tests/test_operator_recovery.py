import copy,json
from datetime import timedelta
from django.test import TestCase,override_settings
from django.core.exceptions import ValidationError,PermissionDenied
from django.db import connection,transaction,DatabaseError
from django.utils import timezone
from apps.identity.models import Grant
from apps.workflows import protection as d,operator_delivery as worker
from apps.workflows.operator_recovery import snapshot,recover
from apps.workflows.operator_inventory import jobs
from apps.workflows.operator_models import OperatorInventory,RecoveryPlan,RecoveryProof,RecoveryJob,RecoveryArtifact,RecoveryAssessment,RecoveryReview
from apps.policy.operator_validators import OPERATOR,PROTECTION
from apps.policy.services import transition,resolve
from adapters.operator_protection import TimeoutAfterMetadataAccept,target_identity,storage_root
from apps.agents.operations import investigate
from .operator_helpers import fixture,evidence,policy,effect,connected,proof,provision_test_database
from .helpers import rev

@override_settings(OPERATOR_DRILL_DATABASE='test_psl_drill_operators')
class OperatorRecoveryTests(TestCase):
    @classmethod
    def setUpTestData(cls):provision_test_database()
    def setUp(self):self.f=fixture()
    def test_real_metadata_export_sealed_backup_and_separate_postgres_restore_review(self):
        f=self.f;e,b,r=connected(f);self.assertEqual(e.sha256,b.sha256);self.assertEqual(r.sha256,e.sha256);self.assertTrue(r.receipt['native_isolated_postgres_write']);self.assertFalse(r.receipt['full_database_restore'])
        result=d.assess(f['actor'],f['case'].pk,f['plan'].pk,'assessment');self.assertTrue(result.result['documentary_complete']);self.assertTrue(result.result['native_metadata_drill_verified']);self.assertEqual(result.result['objectives'],{'rpo':'unknown','rto':'unknown'})
        rr=d.review(f['reviewer'],f['case'].pk,result.pk,'confirm','review',f['review_evidence'].pk);self.assertTrue(d.report(f['reviewer'],f['case'].pk,result.pk)['review_current']);self.assertFalse(d.report(f['reviewer'],f['case'].pk,result.pk)['operational_ready'])
    def test_review_current_rechecks_reviewer_source_visibility(self):
        f=self.f;connected(f);r=d.assess(f['actor'],f['case'].pk,f['plan'].pk,'review-grants');d.review(f['reviewer'],f['case'].pk,r.pk,'confirm','review-grants',f['review_evidence'].pk)
        Grant.objects.filter(case=f['case'],user=f['reviewer'],action='finance.read').update(active=False);self.assertFalse(d.report(f['actor'],f['case'].pk,r.pk)['review_current'])
    def test_only_currently_leased_work_is_reported_as_an_expired_lease(self):
        f=self.f;connected(f);RecoveryJob.objects.filter(plan=f['plan']).update(lease_until=timezone.now()-timedelta(seconds=1));rows=jobs(f['actor'],f['case'])[0];self.assertTrue(all(not r['lease_expired'] and r['lease_until'] is None for r in rows));self.assertEqual(investigate(f['actor'],f['case'].pk).result['job_findings'],[])
        p=d.capture_plan(f['actor'],f['case'].pk,'lease-diagnostics',f['plan'].payload,evidence(f,'ops_plan').pk);j=worker.reserve(f['actor'],f['case'].pk,p.pk,'export');pk,fence=worker.claim();self.assertEqual(pk,j.pk);RecoveryJob.objects.filter(pk=pk).update(lease_until=timezone.now()-timedelta(seconds=1));row=next(r for r in jobs(f['actor'],f['case'])[0] if r['id']==pk and r['family']=='protection');self.assertTrue(row['lease_expired']);self.assertEqual(len(investigate(f['actor'],f['case'].pk).result['job_findings']),1)
    def test_inventory_before_policy_and_no_raw_body_errors_or_intents(self):
        f=self.f;transition(f['actor'],f['policies'][0].pk,'revoked');r=snapshot(f['actor'],f['case'].pk,'snapshot');self.assertFalse(r.manifest['errors_or_intents_exported']);self.assertFalse(r.manifest['evidence_bodies_read'])
        with self.assertRaises(ValidationError):worker.reserve(f['actor'],f['case'].pk,f['plan'].pk,'export')
        proof(f,changes={'outcome':'unknown'});self.assertEqual(RecoveryProof.objects.count(),1)
    def test_reference_only_holds_restore_but_export_and_backup_work(self):
        f=self.f;v=dict(f['values']['protection'],restore_adapter='reference_only');policy(f,PROTECTION,v);_,e=effect(f,'export');_,b=effect(f,'backup',e.pk)
        with self.assertRaises(ValidationError):worker.reserve(f['actor'],f['case'].pk,f['plan'].pk,'restore',b.pk)
    def test_source_report_cannot_claim_native_execution_and_unknown_stays_unknown(self):
        f=self.f
        for k in ['export','backup','restore']:proof(f,k)
        r=d.assess(f['actor'],f['case'].pk,f['plan'].pk,'reported');self.assertTrue(r.result['documentary_complete']);self.assertFalse(r.result['native_metadata_drill_verified']);self.assertFalse(r.result['full_database_restore_verified'])
        proof(f,changes={'receipt_version':'v2','outcome':'unknown'});self.assertFalse(d.report(f['actor'],f['case'].pk,r.pk)['current_documentary_complete'])
    def test_actual_native_receipt_lookup_after_lost_response_and_revocation(self):
        f=self.f;_,e=effect(f,'export');_,b=effect(f,'backup',e.pk);j=worker.reserve(f['actor'],f['case'].pk,f['plan'].pk,'restore',b.pk);worker.run_once(TimeoutAfterMetadataAccept());j.refresh_from_db();self.assertEqual(j.status,'unknown')
        Grant.objects.filter(case=f['case'],user=f['actor'],action='ops.restore').update(active=False);worker.run_once();j.refresh_from_db();self.assertEqual(j.status,'confirmed');self.assertEqual(RecoveryArtifact.objects.filter(job=j).count(),1)
    def test_pending_export_holds_after_scope_read_revocation_and_replaces_intent(self):
        f=self.f;j=worker.reserve(f['actor'],f['case'].pk,f['plan'].pk,'export');Grant.objects.filter(case=f['case'],user=f['actor'],action='finance.read').update(active=False);worker.run_once();j.refresh_from_db();self.assertEqual(j.status,'held')
        worker.operate(f['actor'],f['case'].pk,j.pk,'replace_intent','Narrow current source visibility');worker.run_once();self.assertEqual(RecoveryArtifact.objects.count(),1);self.assertNotIn('finance.read',RecoveryArtifact.objects.get().manifest['source_grants'])
    def test_sealed_artifact_conflict_is_not_overwritten_or_blindly_retried(self):
        f=self.f;_,e=effect(f,'export');j=worker.reserve(f['actor'],f['case'].pk,f['plan'].pk,'backup',e.pk);path=storage_root()/(j.operation_key+'.json');path.parent.mkdir(parents=True,exist_ok=True);self.assertTrue(path.resolve().is_relative_to(storage_root().resolve()));path.write_bytes(b'conflicting synthetic file')
        worker.run_once();j.refresh_from_db();self.assertEqual(j.status,'held');self.assertEqual(path.read_bytes(),b'conflicting synthetic file');self.assertFalse(RecoveryArtifact.objects.filter(job=j).exists())
    def test_supplied_receipt_duplicates_conflicts_future_dates_and_scope(self):
        f=self.f;r=proof(f);self.assertEqual(d.capture_proof(f['actor'],f['case'].pk,f['plan'].pk,r.evidence_id).pk,r.pk)
        for changes in [{'outcome':'failed'},{'receipt_version':'v2','recorded_at':(timezone.now()+timedelta(hours=1)).isoformat()},{'receipt_version':'v2','scope':'reported_full_database'}]:
            with self.assertRaises(ValidationError):proof(f,changes=changes)
    def test_native_target_must_be_an_explicit_separate_database(self):
        for name in [None,'psl','test_psl',connection.settings_dict['NAME'],'postgres','arbitrary-server']:
            with override_settings(OPERATOR_DRILL_DATABASE=name):
                with self.assertRaises(ValidationError):target_identity()
    def test_current_assessment_and_review_invalidate_after_new_unknown_report(self):
        f=self.f;connected(f);r=d.assess(f['actor'],f['case'].pk,f['plan'].pk,'ready');d.review(f['reviewer'],f['case'].pk,r.pk,'confirm','ready-review',f['review_evidence'].pk)
        proof(f,changes={'outcome':'unavailable'});self.assertFalse(d.report(f['reviewer'],f['case'].pk,r.pk)['review_current']);self.assertEqual(RecoveryArtifact.objects.count(),3)
    def test_independent_authority_and_admin_flags_cannot_review(self):
        f=self.f;connected(f);r=d.assess(f['actor'],f['case'].pk,f['plan'].pk,'ready')
        with self.assertRaises(PermissionDenied):d.review(f['actor'],f['case'].pk,r.pk,'confirm','self-review',f['review_evidence'].pk)
        Grant.objects.filter(case=f['case'],user=f['reviewer'],action='ops.review').update(active=False)
        with self.assertRaises(PermissionDenied):d.review(f['reviewer'],f['case'].pk,r.pk,'confirm','revoked-review',f['review_evidence'].pk)
    def test_direct_protection_recovery_requires_configured_recovery_purpose(self):
        f=self.f;j=worker.reserve(f['actor'],f['case'].pk,f['plan'].pk,'export');Grant.objects.filter(case=f['case'],user=f['actor'],action='ops.recover').update(active=False)
        with self.assertRaises(PermissionDenied):worker.operate(f['actor'],f['case'].pk,j.pk,'cancel','Grant alone is insufficient')
        Grant.objects.filter(case=f['case'],user=f['actor'],action='ops.recover').update(active=True);v=copy.deepcopy(f['values']['operator']);v['operators'][0]['purposes'].remove('recover');policy(f,OPERATOR,v)
        with self.assertRaises(PermissionDenied):worker.operate(f['actor'],f['case'].pk,j.pk,'cancel','Configured purpose required')
        j.refresh_from_db();self.assertEqual(j.status,'pending')
    def test_policy_validators_and_effect_explicit_replacement(self):
        f=self.f
        with self.assertRaises(ValidationError):
            with transaction.atomic():policy(f,PROTECTION,dict(f['values']['protection'],lease_seconds=0))
        j=worker.reserve(f['actor'],f['case'].pk,f['plan'].pk,'export');policy(f,PROTECTION,f['values']['protection']);worker.run_once();j.refresh_from_db();self.assertEqual(j.status,'held')
        with self.assertRaises(ValidationError):worker.operate(f['actor'],f['case'].pk,j.pk,'retry','Intent changed')
        worker.operate(f['actor'],f['case'].pk,j.pk,'replace_intent','Explicit current policy');worker.run_once();self.assertEqual(RecoveryArtifact.objects.count(),1)
    def test_actual_ui_post_snapshot_and_source_access(self):
        f=self.f;self.client.force_login(f['actor']);url=f"/cases/{f['case'].pk}/operations/";self.assertContains(self.client.get(url),'Operator recovery and protection evidence');self.assertEqual(self.client.post(url,{'action':'snapshot','revision':rev(f['case']),'operation_key':'ui-snapshot'}).status_code,302);self.assertEqual(OperatorInventory.objects.count(),1)
        self.assertEqual(self.client.get(url+f'source/plan/{f["plan"].pk}/').status_code,200);Grant.objects.filter(case=f['case'],user=f['actor']).exclude(action__in=['case.read','ops.read']).update(active=False);self.assertContains(self.client.get(url),'Read-only access.');self.assertEqual(self.client.get(url+f'source/plan/{f["plan"].pk}/').status_code,403)
    def test_native_effect_assessment_and_review_forms_use_real_services(self):
        f=self.f;url=f"/cases/{f['case'].pk}/operations/";self.client.force_login(f['actor']);input_id=None
        for kind in ['export','backup','restore']:
            data={'action':kind,'revision':rev(f['case']),'plan':f['plan'].pk}
            if input_id:data['artifact']=input_id
            self.assertEqual(self.client.post(url,data).status_code,302);worker.run_once();artifact=RecoveryArtifact.objects.get(job__plan=f['plan'],job__kind=kind);input_id=artifact.pk
        self.assertEqual(self.client.post(url,{'action':'assess','revision':rev(f['case']),'plan':f['plan'].pk,'operation_key':'ui-assess'}).status_code,302);r=RecoveryAssessment.objects.get(plan=f['plan']);self.client.force_login(f['reviewer'])
        self.assertEqual(self.client.post(url,{'action':'review','revision':rev(f['case']),'assessment':r.pk,'verdict':'confirm','operation_key':'ui-review','evidence':f['review_evidence'].pk}).status_code,302);self.assertTrue(d.report(f['actor'],f['case'].pk,r.pk)['review_current'])
    def test_export_download_rechecks_every_original_source_grant(self):
        f=self.f;_,e=effect(f,'export');self.client.force_login(f['actor']);url=f"/cases/{f['case'].pk}/operations/artifact/{e.pk}/";self.assertEqual(self.client.get(url).status_code,200);Grant.objects.filter(case=f['case'],user=f['actor'],action='finance.read').update(active=False);self.assertEqual(self.client.get(url).status_code,403)
    def test_private_reports_cannot_be_repackaged_and_agent_keeps_no_raw_source(self):
        f=self.f;r=proof(f);agent=investigate(f['actor'],f['case'].pk);self.assertFalse(agent.result['source_body_read']);self.assertFalse(agent.result['recovery_executed'])
        from apps.agents.services import extract_evidence
        from apps.agents.meetings import suggest_commitments
        with self.assertRaises(ValidationError):extract_evidence(f['actor'],f['case'].pk,r.evidence_id,'P13')
        with self.assertRaises(ValidationError):suggest_commitments(f['actor'],f['case'].pk,r.evidence_id,rev(f['case']))
    def test_supplied_full_database_reports_and_objectives_never_claim_native_restore(self):
        f=self.f;payload=dict(f['plan'].payload,scope='reported_full_database',source_ref='synthetic-external-db',target_ref='synthetic-isolated-target',expected_record_count=123,expected_manifest_sha256='a'*64);f['plan']=d.capture_plan(f['actor'],f['case'].pk,'full-report',payload,evidence(f,'ops_plan').pk)
        policy(f,PROTECTION,dict(f['values']['protection'],rpo_seconds=10,rto_seconds=20))
        for kind in ['export','backup','restore']:proof(f,kind)
        r=d.assess(f['actor'],f['case'].pk,f['plan'].pk,'reported-full');self.assertTrue(r.result['documentary_complete']);self.assertEqual(r.result['objectives'],{'rpo':'unknown','rto':'unknown'});self.assertFalse(r.result['native_metadata_drill_verified']);self.assertFalse(r.result['full_database_restore_verified'])
        with self.assertRaises(ValidationError):worker.reserve(f['actor'],f['case'].pk,f['plan'].pk,'export')
        proof(f,changes={'receipt_version':'v2','elapsed_seconds':21,'source_lag_seconds':11});r=d.assess(f['actor'],f['case'].pk,f['plan'].pk,'reported-objectives');self.assertFalse(r.result['documentary_complete']);self.assertEqual(r.result['objectives'],{'rpo':'reported_exceeded','rto':'reported_exceeded'})
    def test_actual_target_guard_and_current_availability_preserve_native_history(self):
        from adapters.operator_protection import target_connect
        import psycopg
        f=self.f;_,_,artifact=connected(f);r=d.assess(f['actor'],f['case'].pk,f['plan'].pk,'available');d.review(f['reviewer'],f['case'].pk,r.pk,'confirm','available-review',f['review_evidence'].pk)
        with self.assertRaises(psycopg.errors.RaiseException):
            with target_connect() as conn:conn.execute('UPDATE psl_metadata_drill_receipt SET sha256=sha256 WHERE operation_key=%s',[artifact.job.operation_key])
        with override_settings(OPERATOR_DRILL_DATABASE=None):self.assertFalse(d.report(f['actor'],f['case'].pk,r.pk)['review_current'])
        self.assertEqual(RecoveryArtifact.objects.count(),3);self.assertTrue(d.report(f['actor'],f['case'].pk,r.pk)['review_current'])
    def test_supplied_external_receipt_identity_cannot_be_reclaimed_by_another_case(self):
        f=self.f;r=proof(f);other=fixture(prefix='other-operator')
        with self.assertRaises(ValidationError):proof(other,changes={'external_ref':r.external_ref})
        self.assertEqual(RecoveryProof.objects.count(),1)
    def test_sql_history_and_reserved_intents_are_immutable(self):
        f=self.f;snapshot(f['actor'],f['case'].pk,'sql');connected(f);proof(f);r=d.assess(f['actor'],f['case'].pk,f['plan'].pk,'sql-assess');d.review(f['reviewer'],f['case'].pk,r.pk,'confirm','sql-review',f['review_evidence'].pk)
        for model in [OperatorInventory,RecoveryPlan,RecoveryProof,RecoveryArtifact,RecoveryAssessment,RecoveryReview]:
            with self.assertRaises(DatabaseError):
                with transaction.atomic():
                    with connection.cursor() as cur:cur.execute('UPDATE '+model._meta.db_table+' SET id=id WHERE id=%s',[model.objects.first().pk])
        with self.assertRaises(DatabaseError):
            with transaction.atomic():
                with connection.cursor() as cur:cur.execute("UPDATE workflows_recoveryjob SET kind='restore' WHERE id=%s",[RecoveryJob.objects.first().pk])

class UnconfiguredOperatorTests(TestCase):
    @classmethod
    def setUpTestData(cls):cls.f=fixture(configured=False,known=False)
    def test_missing_policy_does_not_prevent_inventory_or_report_capture(self):
        f=self.f;snapshot(f['actor'],f['case'].pk,'missing');proof(f,changes={'outcome':'unknown'});self.assertEqual(resolve(PROTECTION,f['case']).status,'MISSING');self.assertIsNone(f['plan'].payload['expected_record_count'])
        with self.assertRaises(ValidationError):worker.reserve(f['actor'],f['case'].pk,f['plan'].pk,'export')

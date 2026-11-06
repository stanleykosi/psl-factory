import copy,json
from datetime import timedelta
from django.test import TestCase
from django.core.exceptions import ValidationError,PermissionDenied
from django.db import connection,transaction,DatabaseError
from django.utils import timezone
from apps.documents import migration_readiness as d,validation as af
from apps.documents.migration_models import MigrationPlan,MigrationProof,MigrationObservation,MigrationAssessment,MigrationReadinessReview,MigrationAF13Binding
from apps.identity.models import Grant
from apps.policy.services import transition,resolve
from apps.policy.migration_validators import COMPONENT
from apps.agents.migration import investigate
from .migration_helpers import fixture,proof,policy,evidence,assessed,review,bound
from .helpers import rev
class MigrationReadinessTests(TestCase):
 @classmethod
 def setUpTestData(cls):cls.f=fixture()
 def test_connected_inventory_reports_owner_independent_review_and_af13_binding(self):
  f=self.f;r,b=bound(f);value=d.report(f['actor'],f['case'].pk,r.pk);self.assertTrue(value['documentary_readiness_reviewed']);self.assertFalse(value['operational_ready']);self.assertFalse(value['native_migration_execution_verified']);self.assertFalse(value['deployment_authorized'])
  self.assertEqual(af.position(f['package'],f['actor'])['migration_readiness']['status'],'documentary_reviewed')
  self.assertEqual(d.bind(f['acceptor'],f['case'].pk,r.pk).pk,b.pk)
  with self.assertRaises(ValidationError):af.review(f['acceptor'],f['case'].pk,f['package'].pk,'acceptance','approve','not-native',f['decision_evidence'].pk,'A supplied report cannot establish operational acceptance',None)
 def test_missing_policy_holds_assessment_not_plan_or_report_capture(self):
  f=self.f;transition(f['actor'],f['migration_policy'].pk,'revoked');s=proof(f);d.observe_inventory(f['actor'],f['case'].pk,f['plan'].pk)
  with self.assertRaises(ValidationError):d.assess(f['actor'],f['case'].pk,f['plan'].pk)
  self.assertEqual(s.plan_id,f['plan'].pk);self.assertEqual(MigrationAssessment.objects.count(),0)
 def test_missing_proofs_produce_specific_findings(self):
  f=self.f;r=d.assess(f['actor'],f['case'].pk,f['plan'].pk);self.assertFalse(r.result['documentary_complete']);self.assertIn('Missing rollback evidence',r.result['findings'])
  with self.assertRaises(ValidationError):review(f,r)
 def test_unknown_inventory_never_becomes_zero(self):
  f=self.f;v=copy.deepcopy(f['plan'].payload);v['expected_record_count']=None;f['plan']=d.capture_plan(f['actor'],f['case'].pk,f['plan'].reference,v,f['plan_evidence'].pk,f['package'].pk,predecessor=f['plan'].pk);r=assessed(f)
  self.assertIsNone(f['plan'].payload['expected_record_count']);self.assertIn('expected_record_count remains unknown',r.result['findings']);self.assertFalse(r.result['documentary_complete'])
 def test_failed_unknown_and_missing_reconciliation_counts_hold_review(self):
  f=self.f;r=assessed(f)
  proof(f,'restore',{'receipt_version':'v2','outcome':'unknown'});proof(f,'reconciliation',{'receipt_version':'v2','record_count':None})
  r=d.assess(f['actor'],f['case'].pk,f['plan'].pk);self.assertIn('restore report is failed or unknown',r.result['findings']);self.assertIn('Reconciliation count/digest unknown or differs from declared inventory',r.result['findings'])
 def test_duplicate_receipt_idempotency_and_conflict(self):
  f=self.f;p=proof(f);self.assertEqual(d.capture_proof(f['actor'],f['case'].pk,f['plan'].pk,p.evidence_id).pk,p.pk)
  with self.assertRaises(ValidationError):proof(f,changes={'outcome':'failed'})
  self.assertEqual(MigrationProof.objects.count(),1)
 def test_exact_build_source_target_and_clock_schema(self):
  f=self.f
  for changes in [{'build_ref':'wrong'},{'plan_sha256':'0'*64},{'source_version':'wrong'},{'target_ref':'wrong'},{'recorded_at':(timezone.now()+timedelta(hours=1)).isoformat()},{'evidence_class':'native_execution'}]:
   with self.assertRaises(ValidationError):proof(f,changes=changes)
  e=evidence(f,'migration_proof','{"plan_id":1,"plan_id":2}')
  with self.assertRaises(ValidationError):d.capture_proof(f['actor'],f['case'].pk,f['plan'].pk,e.pk)
 def test_inventory_adapter_rejects_arbitrary_source_scope(self):
  f=self.f;v=copy.deepcopy(f['plan'].payload);v['source_ref']='another-case';p=d.capture_plan(f['actor'],f['case'].pk,'other-source',v,f['plan_evidence'].pk,f['package'].pk)
  with self.assertRaises(ValidationError):d.observe_inventory(f['actor'],f['case'].pk,p.pk)
  self.assertFalse(MigrationObservation.objects.exists())
 def test_native_inventory_is_metadata_only_and_never_migration_execution(self):
  f=self.f;o=d.observe_inventory(f['actor'],f['case'].pk,f['plan'].pk);self.assertEqual(o.payload['record_count'],1);self.assertNotIn('body',o.payload['records'][0]);self.assertTrue(o.payload['native_inventory_read']);self.assertFalse(o.payload['restore_executed']);self.assertFalse(o.payload['migration_executed'])
 def test_stale_policy_proof_inventory_and_review_require_reassessment(self):
  f=self.f;r,b=bound(f);proof(f,'backup',{'receipt_version':'v2'})
  self.assertFalse(d.report(f['actor'],f['case'].pk,r.pk)['documentary_readiness_reviewed']);self.assertEqual(d.package_readiness(f['package'],f['actor'])['status'],'stale_or_held')
  with self.assertRaises(ValidationError):review(f,r,'independent',key='new-independent')
 def test_new_policy_requires_new_assessment(self):
  f=self.f;r=assessed(f);v=copy.deepcopy(f['config_migration']);v['max_age_seconds']=3600;policy(f,v)
  with self.assertRaises(ValidationError):d.current_assessment(r)
 def test_current_source_creator_and_inventory_authority_are_rechecked(self):
  f=self.f;r,b=bound(f);Grant.objects.filter(case=f['case'],user=f['actor'],action='migration.inventory').update(active=False)
  self.assertFalse(d.report(f['owner'],f['case'].pk,r.pk)['documentary_readiness_reviewed'])
 def test_review_revocation_and_d05_authority_change_hold_binding(self):
  f=self.f;r,b=bound(f);review(f,r,'owner','withdraw',key='withdraw-owner');self.assertFalse(d.report(f['actor'],f['case'].pk,r.pk)['documentary_readiness_reviewed'])
 def test_preparer_and_unconfigured_admin_cannot_review(self):
  f=self.f;r=assessed(f);f['actor'].is_superuser=True;f['actor'].save()
  with self.assertRaises(PermissionDenied):d.review(f['actor'],f['case'].pk,r.pk,'owner','approve','admin',f['review_evidence'].pk,'No authority from admin status')
  with self.assertRaises(PermissionDenied):d.review(f['owner'],f['case'].pk,r.pk,'independent','approve','same-owner',f['review_evidence'].pk,'Wrong principal')
 def test_invalid_policy_values_and_duplicate_principals(self):
  f=self.f
  for key,value in [('max_age_seconds',0),('process_ids',['P99']),('required_kinds',[])]:
   v=copy.deepcopy(f['config_migration']);v[key]=value
   with self.assertRaises(ValidationError):
    with transaction.atomic():policy(f,v)
  v=copy.deepcopy(f['config_migration']);v['assignments'][1]['user_id']=f['owner'].pk
  with self.assertRaises(ValidationError):policy(f,v)
 def test_unsupported_inventory_mode_holds_only_readiness(self):
  f=self.f;v=copy.deepcopy(f['config_migration']);v['inventory_mode']='unsupported_native';policy(f,v);r=assessed(f);self.assertFalse(r.result['documentary_complete']);self.assertIn('Native inventory adapter unavailable for configured source mode',r.result['findings'])
 def test_expired_evidence_not_renewed_by_reassessment(self):
  f=self.f;r=assessed(f)
  from unittest.mock import patch
  with patch('apps.documents.migration_readiness.timezone.now',return_value=timezone.now()+timedelta(days=2)):
   with self.assertRaises(ValidationError):d.current_assessment(r)
 def test_sql_history_guard_for_all_six_models(self):
  f=self.f;r,b=bound(f)
  for model in [MigrationPlan,MigrationProof,MigrationObservation,MigrationAssessment,MigrationReadinessReview,MigrationAF13Binding]:
   row=model.objects.first()
   with self.assertRaises(DatabaseError):
    with transaction.atomic():
     with connection.cursor() as cur:cur.execute('UPDATE '+model._meta.db_table+' SET id=id WHERE id=%s',[row.pk])
 def test_agent_and_ui_are_scoped_and_read_only_without_action_grants(self):
  f=self.f;r,b=bound(f);run=investigate(f['actor'],f['case'].pk);self.assertFalse(run.result['source_body_read']);self.assertFalse(run.result['migration_executed'])
  self.client.force_login(f['actor']);url=f"/cases/{f['case'].pk}/migration/";self.assertContains(self.client.get(url),'Migration evidence and AF13 readiness');self.assertEqual(self.client.get(url+f'report/{r.pk}/').status_code,200)
  Grant.objects.filter(case=f['case'],user=f['actor']).exclude(action__in=['case.read','migration.read']).update(active=False)
  self.assertContains(self.client.get(url),'Read-only access.');self.assertEqual(self.client.get(url+f'evidence/{f["plan"].pk}/').status_code,403)
  self.assertNotContains(self.client.get(f"/cases/{f['case'].pk}/"),'synthetic-operator');self.assertEqual(d.package_readiness(f['package'],f['tester'])['status'],'access_required')
 def test_source_receipt_cannot_be_repackaged_as_general_af13_source(self):
  f=self.f;p=proof(f)
  with self.assertRaises(ValidationError):af.capture_source(f['actor'],f['case'].pk,'leak',p.evidence_id,f['source'].metadata,None)
 def test_support_owner_revocation_holds_readiness(self):
  f=self.f;r,b=bound(f);Grant.objects.filter(case=f['case'],user=f['actor'],action='validation.support').update(active=False)
  self.assertFalse(d.report(f['owner'],f['case'].pk,r.pk)['documentary_readiness_reviewed'])
 def test_plan_supersession_and_changed_expectations_hold_old_binding(self):
  f=self.f;r,b=bound(f);v=copy.deepcopy(f['plan'].payload);v['target_version']='target-v2';d.capture_plan(f['actor'],f['case'].pk,f['plan'].reference,v,f['plan_evidence'].pk,f['package'].pk,predecessor=f['plan'].pk)
  self.assertEqual(d.package_readiness(f['package'],f['actor'])['status'],'stale_or_held')
  with self.assertRaises(ValidationError):d.current_assessment(r)
 def test_ui_successful_typed_inventory_and_assessment_commands(self):
  f=self.f;self.client.force_login(f['actor']);url=f"/cases/{f['case'].pk}/migration/"
  for action in ['inventory','assess']:
   self.assertEqual(self.client.post(url,{'action':action,'plan':f['plan'].pk,'revision':rev(f['case'])}).status_code,302)
  self.assertEqual(MigrationObservation.objects.count(),1);self.assertEqual(MigrationAssessment.objects.count(),1)
 def test_af13_missing_context_and_open_gaps_prevent_ready_review(self):
  f=self.f;v=copy.deepcopy(f['package'].payload);v['manual_fallback']='';v['gaps']=[{'key':'missing-sop','description':'Actual SOP still missing','process_ids':['B13'],'state':'open','evidence_id':None}]
  p=af.prepare_package(f['actor'],f['case'].pk,'context-gaps',v,f['decision_evidence'].pk,None)
  from .validation_helpers import review as af_review
  f['package']=p;af_review(f);af_review(f,'expectations');f['plan']=d.capture_plan(f['actor'],f['case'].pk,'context-gaps',f['plan'].payload,f['plan_evidence'].pk,p.pk);r=assessed(f)
  self.assertIn('AF13 manual_fallback remains missing',r.result['findings']);self.assertIn('AF13 selected scope retains unresolved evidence gaps',r.result['findings'])
  with self.assertRaises(ValidationError):review(f,r)
 def test_readiness_reviewer_needs_current_source_evidence_access(self):
  f=self.f;r,b=bound(f);Grant.objects.filter(case=f['case'],user=f['owner'],action='migration.evidence.read').update(active=False)
  self.assertFalse(d.report(f['actor'],f['case'].pk,r.pk)['documentary_readiness_reviewed']);self.assertEqual(d.package_readiness(f['package'],f['actor'])['status'],'stale_or_held')
  with self.assertRaises(PermissionDenied):review(f,r,key='new-review-without-source')
 def test_plan_cannot_claim_readiness_for_a_broader_af13_package(self):
  f=self.f;v=copy.deepcopy(f['plan'].payload);v['process_ids']=['P15']
  with self.assertRaises(ValidationError):d.capture_plan(f['actor'],f['case'].pk,'narrower-scope',v,f['plan_evidence'].pk,f['package'].pk)
 def test_af13_read_only_ui_hides_ungranted_decision_forms(self):
  f=self.f;Grant.objects.get_or_create(case=f['case'],user=f['tester'],action='migration.read');self.client.force_login(f['tester']);url=f"/cases/{f['case'].pk}/validation/"
  # The tester has replay permission, but no source, owner decision or policy authority.
  response=self.client.get(url);self.assertNotContains(response,'Record owner review or acceptance decision');self.assertNotContains(response,'Draft typed owner, acceptance or SOP policy');self.assertNotContains(response,'Capture procedure or clarification')
  self.assertEqual(self.client.post(url,{'action':'review','package':f['package'].pk,'kind':'acceptance','verdict':'approve','operation_key':'not-granted','evidence':f['decision_evidence'].pk,'reason':'Cannot grant authority','revision':rev(f['case'])}).status_code,200)
 def test_synthetic_execution_receipt_cannot_enter_operational_case(self):
  f=self.f
  from apps.core.models import Case
  Case.objects.filter(pk=f['case'].pk).update(synthetic=False)
  with self.assertRaises(ValidationError):proof(f,'execution')
  self.assertFalse(MigrationProof.objects.exists())

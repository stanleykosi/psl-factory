import copy,json,os
from datetime import timedelta
from django.test import TestCase,override_settings
from django.core.exceptions import ValidationError,PermissionDenied
from django.db import connection,transaction,DatabaseError
from django.utils import timezone
from apps.identity.models import Grant
from apps.workflows import readiness as d,readiness_delivery as w
from apps.workflows.readiness_models import IntegrationContract,IntegrationProbe,IntegrationObservation,IntegrationAssessment,IntegrationReview,IntegrationSelection
from apps.policy.readiness_validators import ADAPTER,PROVIDER
from apps.policy.services import transition
from apps.agents.integrations import investigate
from apps.agents.readiness_gateway import canary
from adapters.readiness import binding
from .readiness_helpers import fixture,evidence,policy,probe,ready,handoff,endpoint
from .helpers import rev

@override_settings(READINESS_DATABASE_REVISION='fixture-v1')
class ReadinessTests(TestCase):
 def setUp(self):self.f=fixture()
 def test_actual_database_identity_health_review_and_enrollment(self):
  f=self.f;r=ready(f);self.assertTrue(r.result['capability_ready']);self.assertFalse(r.result['operational_ready']);self.assertFalse(IntegrationObservation.objects.get().payload['password_authentication_proven']);d.select(f['actor'],f['case'].pk,f['contract'].pk,f['selection_evidence'].pk);self.assertEqual(d.gate(f['case'],'handoff')['assessment'],r.pk)
 def test_enrolled_handoff_holds_then_dispatches_without_bypassing_finance(self):
  from apps.workflows.services import run_once
  from apps.finance.models import Handoff
  f=self.f;j=handoff(f);d.select(f['actor'],f['case'].pk,f['contract'].pk,f['selection_evidence'].pk);run_once();j.refresh_from_db();self.assertEqual(j.status,'held');self.assertFalse(Handoff.objects.exists())
  v=dict(f['rules'],require_receipt_probe=True);policy(f,ADAPTER,v);probe(f);_,obs=probe(f,'receipt',source_id=j.pk);self.assertEqual(obs.payload['business_receipt'],'not_found');r=d.assess(f['actor'],f['case'].pk,f['contract'].pk,'bridge');d.review(f['reviewer'],f['case'].pk,r.pk,'confirm','bridge-review',f['review_evidence'].pk)
  from apps.workflows.operator_recovery import operate_handoff
  # Source service retains its own retry grants/actor; no source effect is mocked.
  operate_handoff(f['actor'],f['case'],j.pk,'retry','Current readiness reviewed');run_once();j.refresh_from_db();self.assertEqual(j.status,'confirmed');self.assertEqual(Handoff.objects.count(),1)
 def test_receipt_first_recovery_survives_later_readiness_failure(self):
  from apps.workflows.services import run_once
  from adapters.finance import TimeoutAfterAccept
  from apps.finance.models import Handoff
  f=self.f;j=handoff(f);ready(f);d.select(f['actor'],f['case'].pk,f['contract'].pk,f['selection_evidence'].pk);run_once(TimeoutAfterAccept());j.refresh_from_db();self.assertEqual(j.status,'unknown');transition(f['actor'],f['policy'].pk,'revoked');run_once();j.refresh_from_db();self.assertEqual(j.status,'confirmed');self.assertEqual(Handoff.objects.count(),1)
 def test_supplied_success_never_proves_authenticated_readiness(self):
  f=self.f;d.supplied(f['actor'],f['case'].pk,f['contract'].pk,'supplied',evidence(f,'integration_report',{'contract_sha256':f['contract'].sha256,'kind':'health','outcome':'passed','recorded_at':timezone.now().isoformat(),'source_ref':'synthetic-owner-report'}).pk);r=d.assess(f['actor'],f['case'].pk,f['contract'].pk,'supplied');self.assertFalse(r.result['capability_ready'])
 def test_new_unavailable_report_preserves_native_history_but_invalidates_review(self):
  f=self.f;r=ready(f);d.supplied(f['actor'],f['case'].pk,f['contract'].pk,'unavailable',evidence(f,'integration_report',{'contract_sha256':f['contract'].sha256,'kind':'health','outcome':'unavailable','recorded_at':timezone.now().isoformat(),'source_ref':'synthetic-outage'}).pk);self.assertFalse(d.report(f['actor'],f['case'].pk,r.pk)['review_current']);self.assertEqual(IntegrationObservation.objects.filter(job__isnull=False).count(),1)
 def test_configured_independent_reviewer_and_current_source_grants(self):
  f=self.f;probe(f);r=d.assess(f['actor'],f['case'].pk,f['contract'].pk,'review')
  with self.assertRaises(PermissionDenied):d.review(f['actor'],f['case'].pk,r.pk,'confirm','self',f['review_evidence'].pk)
  d.review(f['reviewer'],f['case'].pk,r.pk,'confirm','independent',f['review_evidence'].pk);Grant.objects.filter(case=f['case'],user=f['reviewer'],action='workflow.read').update(active=False);self.assertFalse(d.report(f['actor'],f['case'].pk,r.pk)['review_current'])
 def test_missing_runtime_revision_and_unknown_contract_hold_only_probes(self):
  f=self.f
  with override_settings(READINESS_DATABASE_REVISION=None):
   with self.assertRaises(ValidationError):w.reserve(f['actor'],f['case'].pk,f['contract'].pk,'missing-revision','health')
  payload=dict(f['contract'].payload,target_key=None,credential_ref=None,credential_revision=None);r=d.capture(f['actor'],f['case'].pk,'pending',payload,evidence(f,'integration_contract').pk);self.assertIsNone(r.payload['credential_ref']);self.assertIsNone(d.gate(f['case'],'invoice'))
 def test_pending_or_held_new_probe_invalidates_earlier_positive_assessment(self):
  f=self.f;r=ready(f);j=w.reserve(f['actor'],f['case'].pk,f['contract'].pk,'refresh','health');self.assertFalse(d.report(f['actor'],f['case'].pk,r.pk)['review_current']);Grant.objects.filter(case=f['case'],user=f['actor'],action='integration.probe').update(active=False);w.run_once();j.refresh_from_db();self.assertEqual(j.status,'held');self.assertFalse(d.report(f['reviewer'],f['case'].pk,r.pk)['current_ready'])
 def test_policy_validation_requires_actual_role_not_a_claimed_label(self):
  f=self.f
  with self.assertRaises(ValidationError):
   with transaction.atomic():policy(f,ADAPTER,dict(f['rules'],reviewer_role='CEO'))
 def test_handoff_adapter_rechecks_source_authority_under_effect_lock(self):
  from adapters.finance import InternalFinanceAdapter
  from apps.finance.models import Handoff
  f=self.f;j=handoff(f);Grant.objects.filter(case=f['case'],user=f['actor'],action='milestone.complete').update(active=False)
  with self.assertRaises(PermissionDenied):InternalFinanceAdapter().deliver(j)
  self.assertFalse(Handoff.objects.exists())
 def test_policy_change_and_probe_revocation_hold_undispatched_work(self):
  f=self.f;j=w.reserve(f['actor'],f['case'].pk,f['contract'].pk,'pending','health');Grant.objects.filter(case=f['case'],user=f['actor'],action='integration.probe').update(active=False);w.run_once();j.refresh_from_db();self.assertEqual(j.status,'held');self.assertFalse(IntegrationObservation.objects.exists())
 def test_source_receipt_probe_is_scoped_to_exact_case(self):
  f=self.f;other=fixture(prefix='other');j=handoff(other)
  with self.assertRaises(ValidationError):w.reserve(f['actor'],f['case'].pk,f['contract'].pk,'wrong-case','receipt',j.pk)
 def test_strict_reference_only_contract_and_supplied_identity_controls(self):
  f=self.f
  for changes in [{'credential_ref':'Bearer-raw-token'},{'target_key':'https://unreviewed.example'},{'secret':'raw'}]:
   with self.assertRaises(ValidationError):d.capture(f['actor'],f['case'].pk,'invalid',dict(f['contract'].payload,**changes),evidence(f,'integration_contract').pk)
  with self.assertRaises(ValidationError):
   with transaction.atomic():policy(f,ADAPTER,dict(f['rules'],freshness_seconds=0))
 def test_ui_real_posts_and_private_source_boundary(self):
  f=self.f;self.client.force_login(f['actor']);url=f"/cases/{f['case'].pk}/integrations/";self.assertContains(self.client.get(url),'Adapter and provider readiness');self.assertEqual(self.client.post(url,{'action':'probe','revision':rev(f['case']),'contract':f['contract'].pk,'operation_key':'ui-probe','kind':'health','source_job':''}).status_code,302);w.run_once();self.assertEqual(IntegrationObservation.objects.count(),1)
  self.assertEqual(self.client.post(url,{'action':'assess','revision':rev(f['case']),'contract':f['contract'].pk,'operation_key':'ui-assess'}).status_code,302);r=IntegrationAssessment.objects.get();self.client.force_login(f['reviewer']);self.assertEqual(self.client.post(url,{'action':'review','revision':rev(f['case']),'assessment':r.pk,'verdict':'confirm','operation_key':'ui-review','evidence':f['review_evidence'].pk}).status_code,302);self.assertTrue(d.report(f['reviewer'],f['case'].pk,r.pk)['review_current'])
  Grant.objects.filter(case=f['case'],user=f['reviewer']).exclude(action__in=['case.read','integration.read']).update(active=False);self.assertContains(self.client.get(url),'Read-only access.');self.assertEqual(self.client.get(url+f'source/contract/{f["contract"].pk}/').status_code,403)
 def test_private_evidence_and_agent_do_not_repackage_credentials(self):
  f=self.f;run=investigate(f['actor'],f['case'].pk);self.assertFalse(run.result['secrets_read']);self.assertFalse(run.result['private_source_sent'])
  from apps.agents.services import extract_evidence
  with self.assertRaises(ValidationError):extract_evidence(f['actor'],f['case'].pk,f['contract'].evidence_id,'P13')
 def test_scoped_handoff_cli_does_not_claim_another_case(self):
  from django.core.management import call_command
  from io import StringIO
  f=self.f;old=handoff(f);other=fixture(prefix='scoped-handoff');j=handoff(other);call_command('work_outbox','--case',str(other['case'].pk),'--limit','1',stdout=StringIO());old.refresh_from_db();j.refresh_from_db();self.assertEqual((old.status,old.attempts,old.fence),('pending',0,0));self.assertEqual(j.status,'confirmed')
 def test_scoped_probe_cli_does_not_claim_another_case(self):
  from django.core.management import call_command
  from io import StringIO
  f=self.f;old=w.reserve(f['actor'],f['case'].pk,f['contract'].pk,'old-case','health');other=fixture(prefix='scoped-probe');j=w.reserve(other['actor'],other['case'].pk,other['contract'].pk,'new-case','health');call_command('work_integration_readiness','--case',str(other['case'].pk),'--limit','1',stdout=StringIO());old.refresh_from_db();j.refresh_from_db();self.assertEqual((old.status,old.attempts,old.fence),('pending',0,0));self.assertEqual(j.status,'confirmed')
 def test_sql_history_and_probe_intents_are_immutable(self):
  f=self.f;r=ready(f);d.select(f['actor'],f['case'].pk,f['contract'].pk,f['selection_evidence'].pk)
  for model in [IntegrationContract,IntegrationObservation,IntegrationAssessment,IntegrationReview,IntegrationSelection]:
   with self.assertRaises(DatabaseError):
    with transaction.atomic():
     with connection.cursor() as cur:cur.execute('UPDATE '+model._meta.db_table+' SET id=id WHERE id=%s',[model.objects.first().pk])
  with self.assertRaises(DatabaseError):
   with transaction.atomic():
    with connection.cursor() as cur:cur.execute("UPDATE workflows_integrationprobe SET intent_key='changed' WHERE id=%s",[IntegrationProbe.objects.first().pk])

class ProviderReadinessTests(TestCase):
 def setUp(self):self.f=fixture(kind='provider')
 def test_real_authenticated_http_canary_and_selected_gateway(self):
  f=self.f
  with endpoint() as state:
   probe(f);j,o=probe(f,'evaluation');self.assertTrue(o.payload['oracle_match']);self.assertFalse(o.payload['private_source_sent']);r=d.assess(f['actor'],f['case'].pk,f['contract'].pk,'provider');self.assertTrue(r.result['synthetic_provider_evaluated']);self.assertFalse(r.result['real_model_evaluated']);d.review(f['reviewer'],f['case'].pk,r.pk,'confirm','provider',f['review_evidence'].pk);d.select(f['actor'],f['case'].pk,f['contract'].pk,f['selection_evidence'].pk);next_job=canary(f['actor'],f['case'].pk,'selected-canary');w.run_once();next_job.refresh_from_db();self.assertEqual(next_job.status,'confirmed');self.assertEqual(state['calls'],2)
 def test_lost_response_recovers_provider_receipt_once_after_sender_revocation(self):
  f=self.f
  with endpoint() as state:
   state['lose_response']=True;j=w.reserve(f['actor'],f['case'].pk,f['contract'].pk,'lost-response','evaluation');w.run_once();j.refresh_from_db();self.assertEqual(j.status,'unknown');Grant.objects.filter(case=f['case'],user=f['actor'],action='integration.probe').update(active=False);w.run_once();j.refresh_from_db();self.assertEqual(j.status,'confirmed');self.assertEqual(state['calls'],1)
 def test_wrong_identity_unavailable_and_mismatched_oracle_never_ready(self):
  f=self.f
  with endpoint() as state:
   state['principal']='principal:wrong';_,h=probe(f);self.assertEqual(h.payload['outcome'],'failed');state['bad_output']=True;_,e=probe(f,'evaluation');self.assertEqual(e.payload['outcome'],'failed');r=d.assess(f['actor'],f['case'].pk,f['contract'].pk,'bad');self.assertFalse(r.result['capability_ready']);run=investigate(f['actor'],f['case'].pk);self.assertEqual(run.result['diagnostics']['identity_mismatch_count'],1);self.assertEqual(run.result['diagnostics']['oracle_mismatch_count'],1)
 def test_new_failed_health_probe_holds_old_review_and_exposes_no_secret(self):
  f=self.f
  with endpoint() as state:
   probe(f);probe(f,'evaluation');r=d.assess(f['actor'],f['case'].pk,f['contract'].pk,'initial');d.review(f['reviewer'],f['case'].pk,r.pk,'confirm','initial',f['review_evidence'].pk);state['status']='unavailable';probe(f,'health',key='unavailable-refresh');self.assertFalse(d.report(f['actor'],f['case'].pk,r.pk)['review_current'])
 def test_missing_model_is_capturable_but_cannot_invoke_an_implicit_model(self):
  f=self.f;payload=dict(f['contract'].payload,model_id=None);r=d.capture(f['actor'],f['case'].pk,'unknown-model',payload,evidence(f,'integration_contract').pk)
  with endpoint():
   with self.assertRaises(ValidationError):w.reserve(f['actor'],f['case'].pk,r.pk,'unknown-model','evaluation')
  self.assertEqual(IntegrationProbe.objects.count(),0)
 def test_rotation_same_revision_holds_old_intent_and_redacts_auth_error(self):
  f=self.f
  with endpoint() as state:
   j=w.reserve(f['actor'],f['case'].pk,f['contract'].pk,'rotation','health');os.environ['PSL_TEST_READINESS_TOKEN']='synthetic-replacement';w.run_once();j.refresh_from_db();self.assertEqual(j.status,'held');self.assertFalse(IntegrationObservation.objects.exists())
   j=w.reserve(f['actor'],f['case'].pk,f['contract'].pk,'wrong-auth','health');w.run_once();j.refresh_from_db();self.assertEqual(j.status,'held');self.assertNotIn(state['secret'],str(list(IntegrationProbe.objects.values())))
 def test_redirect_is_not_followed_and_synthetic_target_cannot_be_operational(self):
  f=self.f
  with endpoint() as state:
   state['redirect']=True;j=w.reserve(f['actor'],f['case'].pk,f['contract'].pk,'redirect','health');w.run_once();j.refresh_from_db();self.assertEqual(j.status,'unknown')
   f['case'].synthetic=False;f['case'].save(update_fields=['synthetic']);f['contract'].case=f['case']
   with self.assertRaises(ValidationError):binding(f['contract'])

class UnconfiguredReadinessTests(TestCase):
 def test_capture_reports_and_investigation_before_policy_or_credentials(self):
  f=fixture(configured=False,known=False);d.supplied(f['actor'],f['case'].pk,f['contract'].pk,'unknown',evidence(f,'integration_report',{'contract_sha256':f['contract'].sha256,'kind':'health','outcome':'unknown','recorded_at':timezone.now().isoformat(),'source_ref':'unconfigured'}).pk);self.assertFalse(investigate(f['actor'],f['case'].pk).result['secrets_read'])
  with self.assertRaises(ValidationError):w.reserve(f['actor'],f['case'].pk,f['contract'].pk,'not-ready','health')

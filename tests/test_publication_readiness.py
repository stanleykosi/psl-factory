import copy,json
from datetime import timedelta
from unittest.mock import patch
from django.test import TestCase,override_settings
from django.core.exceptions import ValidationError,PermissionDenied
from django.db import transaction,connection,DatabaseError
from django.urls import reverse
from django.utils import timezone
from apps.finance import publication_readiness as n,accepted_documents as p
from apps.workflows import readiness as r,readiness_delivery as w
from apps.workflows.readiness_models import IntegrationContract,IntegrationObservation,IntegrationProbe
from apps.documents.delivery import claim_publication,run_publication_once
from apps.documents.models import PublicationReceipt
from apps.identity.models import Grant
from apps.policy.readiness_validators import ADAPTER
from apps.policy.services import transition
from apps.agents.models import AgentRun
from apps.agents.integrations import investigate
from apps.core.evidence_access import public_timeline
from adapters.publications import PublicationTimeoutAfterAccept
from .publication_readiness_helpers import fixture,capture,configure,enrolled,probe,assessed
from .readiness_helpers import endpoint,policy
from .helpers import rev

class PublicationReadinessTests(TestCase):
 @classmethod
 def setUpTestData(cls):
  cls.enterClassContext(endpoint());cls.enterClassContext(override_settings(READINESS_DATABASE_REVISION='fixture-v1'));cls.f=fixture()
 def test_exact_health_receipt_review_enrollment_and_native_delivery(self):
  f=self.f;enrolled(f);b=n.binding(f['contract']);self.assertEqual(b.job_id,f['job'].pk);self.assertTrue(r.report(f['actor'],f['case'].pk,f['assessment'].pk)['review_current'])
  obs=list(IntegrationObservation.objects.filter(contract=f['contract']));self.assertEqual({x.payload['kind'] for x in obs},{'health','receipt'});self.assertTrue(all(x.payload['native_publication']['sha256']==b.sha256 for x in obs))
  receipt=next(x for x in obs if x.payload['kind']=='receipt');self.assertEqual(receipt.payload['receipt_provenance']['state'],'not_found');self.assertNotIn('TX-001',json.dumps([x.payload for x in obs]));self.assertNotIn('sections',json.dumps(b.snapshot))
  lease=claim_publication();p.deliver(*lease);self.assertEqual(PublicationReceipt.objects.filter(publication=f['publication']).count(),1)
  self.assertFalse(r.report(f['actor'],f['case'].pk,f['assessment'].pk)['current_ready']);assessed(f,'after-delivery');self.assertTrue(r.report(f['actor'],f['case'].pk,f['assessment'].pk)['review_current'])
  found=IntegrationObservation.objects.filter(contract=f['contract'],payload__kind='receipt').latest('pk');self.assertEqual(found.payload['receipt_provenance']['state'],'found');self.assertEqual(found.payload['receipt_provenance']['receipts'][0]['payload_sha256'],f['version'].payload_sha256)
 def test_missing_v2_policy_holds_native_enrollment_and_probes_not_public_contracts(self):
  f=self.f;f['contract']=capture(f)
  with self.assertRaises(ValidationError):r.select(f['actor'],f['case'].pk,f['contract'].pk,f['selection_evidence'].pk)
  with self.assertRaises(ValidationError):probe(f,'health')
  basic=dict(f['readiness_rules']);basic.pop('native_publication_job_ids');policy(f,ADAPTER,basic);legacy=r.capture(f['actor'],f['case'].pk,'public-only',f['contract_payload'],f['contract_evidence'].pk)
  j=w.reserve(f['actor'],f['case'].pk,legacy.pk,'public-health','health');w.run_once(case_id=f['case'].pk);j.refresh_from_db();self.assertEqual(j.status,'confirmed');self.assertEqual(n.Binding.objects.count(),1)
  with self.assertRaises(ValidationError):probe(f,'health')
 def test_v2_policy_validates_exact_native_inventory_independence_and_private_principals(self):
  f=self.f
  for changes in [{'native_publication_job_ids':[999999]},{'independent_review':False},{'require_receipt_probe':False},{'reviewer_id':f['actor'].pk},{'probe_user_id':f['audience_user'].pk}]:
   with self.subTest(changes=changes),self.assertRaises((ValidationError,PermissionDenied)):policy(f,ADAPTER,dict(f['readiness_rules'],**changes))
  Grant.objects.filter(case=f['case'],user=f['recipient'],action='ledger.private.read').update(active=False)
  with self.assertRaises(ValidationError):configure(f)
 def test_native_provenance_cannot_be_queried_through_public_or_other_job_intents(self):
  f=self.f;enrolled(f,False);legacy=r.capture(f['actor'],f['case'].pk,'public',f['contract_payload'],f['contract_evidence'].pk)
  with self.assertRaises(ValidationError):w.reserve(f['actor'],f['case'].pk,legacy.pk,'wrong-interface','receipt',f['job'].pk)
  with self.assertRaises(ValidationError):w.reserve(f['actor'],f['case'].pk,f['contract'].pk,'wrong-source','receipt',999999)
  with self.assertRaises(ValidationError):r.capture(f['actor'],f['case'].pk,'native',f['contract_payload'],f['contract_evidence'].pk,predecessor=f['contract'].pk)
 def test_private_source_revocation_denies_contract_observation_report_forms_and_guidance(self):
  from apps.workflows.readiness_views import commands
  f=self.f;enrolled(f);obs=IntegrationObservation.objects.filter(contract=f['contract']).first();before=AgentRun.objects.count();self.assertTrue(n.investigate(f['actor'],f['case'])['findings']);self.assertEqual(AgentRun.objects.count(),before)
  Grant.objects.filter(case=f['case'],user=f['actor'],action='ledger.private.read').update(active=False)
  with self.assertRaises(PermissionDenied):r.contract_access(f['actor'],f['contract'])
  with self.assertRaises(PermissionDenied):r.report(f['actor'],f['case'].pk,f['assessment'].pk)
  self.assertFalse(r.visible_contracts(f['actor'],f['case']).filter(pk=f['contract'].pk).exists())
  for row in commands(f['actor'],f['case']):
   for field in row['form'].fields.values():
    if getattr(field,'queryset',None) is not None and field.queryset.model is IntegrationContract:self.assertFalse(field.queryset.filter(pk=f['contract'].pk).exists())
  self.client.force_login(f['actor'])
  for url in [reverse('integration_source',args=[f['case'].pk,'contract',f['contract'].pk]),reverse('integration_source',args=[f['case'].pk,'observation',obs.pk]),reverse('integration_report',args=[f['case'].pk,f['assessment'].pk])]:self.assertEqual(self.client.get(url).status_code,403)
 def test_generic_agent_and_timeline_omit_native_provenance(self):
  f=self.f;enrolled(f);before=AgentRun.objects.count();value=n.investigate(f['actor'],f['case']);self.assertFalse(value['persisted_agent_run']);self.assertEqual(AgentRun.objects.count(),before)
  allowed=r.IntegrationAssessment.objects.filter(contract__case=f['case'],contract__finance_publication_readiness__isnull=True).exclude(contract__payload__family__in=['supportresponse','supportchannel','ledgerdata']).count();run=investigate(f['actor'],f['case'].pk);self.assertEqual(len(run.result['assessments']),allowed);self.assertNotIn('native_binding',json.dumps(run.result));self.assertFalse(public_timeline(f['case']).filter(data__contract=f['contract'].pk).exists())
 def test_enrollment_is_per_exact_job_and_public_documents_stay_independent(self):
  f=self.f;enrolled(f,False);self.assertIsNone(r.gate(f['case'],'publication'));self.assertIsNone(r.gate(f['case'],'publication',source_job=999999))
  with self.assertRaises(ValidationError):r.gate(f['case'],'publication',source_job=f['job'].pk)
  lease=claim_publication()
  with self.assertRaises(ValidationError):p.deliver(*lease)
  self.assertEqual(PublicationReceipt.objects.count(),0)
 def test_health_policy_expiry_and_review_withdrawal_hold_current_not_history(self):
  f=self.f;enrolled(f)
  r.review(f['recipient'],f['case'].pk,f['assessment'].pk,'withdraw','withdraw',f['review_evidence'].pk);self.assertFalse(r.report(f['actor'],f['case'].pk,f['assessment'].pk)['review_current']);self.assertEqual(f['assessment'].integrationreview_set.count(),2)
  future=max(r.timestamp(x.payload['observed_at']) for x in IntegrationObservation.objects.filter(contract=f['contract']))+timedelta(seconds=3601)
  with patch('apps.workflows.readiness.timezone.now',return_value=future):self.assertFalse(r.report(f['actor'],f['case'].pk,f['assessment'].pk)['current_ready'])
  transition(f['actor'],f['readiness_policy'].pk,'revoked');self.assertFalse(r.report(f['actor'],f['case'].pk,f['assessment'].pk)['current_ready'])
 def test_receipt_first_publication_recovery_survives_revoked_native_readiness_and_source(self):
  f=self.f;enrolled(f);run_publication_once(PublicationTimeoutAfterAccept());f['job'].refresh_from_db();self.assertEqual(f['job'].status,'unknown');self.assertEqual(PublicationReceipt.objects.count(),1)
  transition(f['actor'],f['readiness_policy'].pk,'revoked');Grant.objects.filter(case=f['case'],user=f['actor'],action='ledger.private.read').update(active=False);run_publication_once();f['job'].refresh_from_db();self.assertEqual(f['job'].status,'confirmed');self.assertEqual(PublicationReceipt.objects.count(),1)
 def test_probe_receipt_recovery_and_operator_retry_preserve_original_budget(self):
  f=self.f;enrolled(f,False);j=w.reserve(f['actor'],f['case'].pk,f['contract'].pk,'budget','health');j.status='held';j.attempts=1;j.save(update_fields=['status','attempts']);w.operate(f['actor'],f['case'].pk,j.pk,'retry','Exact original intent');j.refresh_from_db();self.assertEqual(j.attempts,1)
  w.run_once(case_id=f['case'].pk);j.refresh_from_db();self.assertEqual(j.status,'confirmed');j.status='unknown';j.save(update_fields=['status']);Grant.objects.filter(case=f['case'],user=f['actor'],action='ledger.private.read').update(active=False);w.run_once(case_id=f['case'].pk);j.refresh_from_db();self.assertEqual(j.status,'confirmed');self.assertEqual(IntegrationObservation.objects.filter(job=j).count(),1)
 def test_real_http_native_capture_probe_policy_schema_and_private_source_projection(self):
  f=self.f;self.client.force_login(f['actor']);url=reverse('integration_readiness',args=[f['case'].pk]);self.assertEqual(self.client.post(url,{'action':'capture','revision':rev(f['case']),'reference':'http-native','payload':json.dumps(f['contract_payload']),'evidence':f['contract_evidence'].pk,'predecessor':'','native_publication_job':f['job'].pk}).status_code,302);f['contract']=IntegrationContract.objects.get(reference='http-native')
  self.assertEqual(self.client.post(url,{'action':'policy','revision':rev(f['case']),'component':ADAPTER,'content':json.dumps(f['readiness_rules']),'evidence':f['e'].pk,'effective_from':(timezone.now()-timedelta(seconds=1)).isoformat()}).status_code,302)
  from apps.policy.models import Configuration
  cfg=Configuration.objects.filter(case=f['case'],component=ADAPTER).order_by('-revision').first();self.assertEqual(cfg.envelope['value']['schema_ref'],'schema:psl/integration-readiness/v2');self.assertEqual(cfg.states.latest('pk').state,'draft');configure(f)
  self.assertEqual(self.client.post(url,{'action':'probe','revision':rev(f['case']),'contract':f['contract'].pk,'operation_key':'http-health','kind':'health','source_job':''}).status_code,302);w.run_once(case_id=f['case'].pk)
  response=self.client.get(reverse('integration_source',args=[f['case'].pk,'contract',f['contract'].pk]));self.assertEqual(response.status_code,200);self.assertEqual(response['Cache-Control'],'no-store');self.assertEqual(response.json()['native_publication']['job'],f['job'].pk)
  response=self.client.get(url);self.assertEqual(response.status_code,200);self.assertEqual(response['Cache-Control'],'no-store');self.assertContains(response,'Private Finance publication guidance')
 def test_database_binding_is_immutable_and_foreign_contract_source_is_rejected(self):
  from apps.core.models import Case
  f=self.f;contract=capture(f);b=n.binding(contract)
  with self.assertRaises(DatabaseError),transaction.atomic():
   with connection.cursor() as cur:cur.execute('UPDATE finance_financepublicationreadiness SET sha256=%s WHERE id=%s',['0'*64,b.pk])
  c=Case.objects.create(tenant=f['case'].tenant,title='Wrong readiness case',kind='project',synthetic=True);wrong=IntegrationContract.objects.create(case=c,reference='wrong',version=1,payload=f['contract_payload'],sha256=r.digest(f['contract_payload']),evidence=f['contract_evidence'],actor=f['actor'])
  with self.assertRaises(DatabaseError),transaction.atomic():n.Binding.objects.create(contract=wrong,job=f['job'],actor=f['actor'],snapshot=b.snapshot,sha256=b.sha256)

 def test_public_publication_receipt_adapter_and_enrollment_stay_independent(self):
  from apps.documents.controlled import register_template,create_version,reserve_publication
  from .document_helpers import artifact
  f=self.f;enrolled(f,False)
  t=register_template(f['actor'],f['case'].pk,'Public progress',{'document_type':'project_artifact','required_fields':['executive_summary'],'internal_review_required':False,'audience_fields':{'internal':['executive_summary']}},f['e'].pk,rev(f['case']))
  artifact(f['actor'],f['case'],'D11.template_storage_retention_rules','schema:psl/document-storage/v1',{'template_ids':[f['template'].pk,t.pk],'repository':'internal-versioned','retention_days':30},f['e'])
  version=create_version(f['actor'],f['case'].pk,t.pk,'Public progress','internal',{'executive_summary':{'text':'Synthetic public progress','evidence_ids':[f['e'].pk]}},rev(f['case']))
  public=reserve_publication(f['actor'],f['case'].pk,version.pk,rev(f['case']));self.assertIsNone(r.gate(f['case'],'publication'))
  c=r.capture(f['actor'],f['case'].pk,'public-receipt',f['contract_payload'],f['contract_evidence'].pk);j=w.reserve(f['actor'],f['case'].pk,c.pk,'public-receipt','receipt',public.job.pk);w.run_once(case_id=f['case'].pk);j.refresh_from_db();self.assertEqual(j.status,'confirmed')
  obs=IntegrationObservation.objects.get(job=j);self.assertNotIn('native_publication',obs.payload);self.assertEqual(obs.payload['business_receipt'],'not_found')

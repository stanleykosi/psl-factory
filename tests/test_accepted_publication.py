import copy,json
from datetime import timedelta
from unittest.mock import patch
from django.test import TestCase
from django.core.exceptions import ValidationError,PermissionDenied
from django.db import transaction,DatabaseError,connection
from django.urls import reverse
from django.utils import timezone
from apps.identity.models import Grant
from apps.policy.services import transition
from apps.policy.ledger_validators import PUBLICATION
from apps.finance import accepted_documents as d,acceptance as h
from apps.documents.controlled import create_version,reserve_publication
from apps.documents.delivery import claim_publication,run_publication_once
from apps.documents.models import PublicationReceipt,PublicationJob
from apps.agents.models import AgentRun
from apps.agents.accepted_finance import investigate
from apps.agents.documents import check_document
from apps.workflows.operator_inventory import jobs,bundle,readable_manifest
from adapters.publications import PublicationTimeoutAfterAccept,InternalPublicationAdapter
from .accepted_publication_helpers import ready,draft,reviewed
from .finance_acceptance_helpers import decide
from .ledger_helpers import policy
from .readiness_helpers import endpoint
from .helpers import rev

class AcceptedPublicationTests(TestCase):
 @classmethod
 def setUpTestData(cls):
  cls.enterClassContext(endpoint());cls.f=ready()
 def test_full_separate_review_publication_and_exact_recipient_inbox(self):
  f=self.f;c=f['case'];v=draft(f)
  self.assertEqual(AgentRun.objects.count(),0)
  with self.assertRaises(ValidationError):d.publish(f['acceptor'],c.pk,v.pk)
  with self.assertRaises(PermissionDenied):d.review(f['actor'],c.pk,v.pk,'approve','Self approval denied')
  d.review(f['recipient'],c.pk,v.pk,'approve','Exact metadata reviewed');p=d.publish(f['acceptor'],c.pk,v.pk);self.assertEqual(d.publish(f['acceptor'],c.pk,v.pk).pk,p.pk)
  lease=claim_publication();self.assertEqual(lease[0],p.job.pk);d.deliver(*lease)
  receipt=PublicationReceipt.objects.get(publication=p);self.assertEqual(receipt.payload,v.payload);self.assertNotIn(f['draft'].body,json.dumps(receipt.payload));self.assertNotIn('TX-001',json.dumps(receipt.payload));self.assertEqual(Grant.objects.filter(case=c,user=f['audience_user']).count(),1)
  self.client.force_login(f['audience_user']);response=self.client.get(reverse('document_inbox'));self.assertContains(response,'Accepted Finance / AF13 metadata');self.assertEqual(response['Cache-Control'],'no-store')
  Grant.objects.filter(case=c,user=f['audience_user']).update(active=False);self.assertNotContains(self.client.get(reverse('document_inbox')),'Accepted Finance / AF13 metadata')
 def test_missing_policy_holds_only_native_document_not_acceptance_history(self):
  f=self.f;transition(f['actor'],f['publication_policy'].pk,'revoked')
  with self.assertRaises(ValidationError):draft(f)
  self.assertTrue(h.report(f['actor'],f['case'].pk,f['handoff'].pk)['scoped_acceptance_current']);self.assertEqual(d.Binding.objects.count(),0)
 def test_typed_fields_inventory_audience_and_independence_validation(self):
  f=self.f
  for changes in [{'fields':['body']},{'handoff_ids':[999999]},{'template_ids':[999999]},{'reviewer_id':f['actor'].pk},{'publisher_id':f['recipient'].pk},{'audience':'management'},{'recipient_ids':[f['actor'].pk]},{'review_ttl_seconds':0}]:
   with self.subTest(changes=changes):
    value=dict(f['publication_rules'],**changes)
    # actor has receive grants, so a different recipient remains a valid explicit policy; use absent grant instead.
    if changes=={'recipient_ids':[f['actor'].pk]}:Grant.objects.filter(case=f['case'],user=f['actor'],action='document.receive:internal').update(active=False)
    with self.assertRaises((ValidationError,PermissionDenied)):policy(f,PUBLICATION,value)
 def test_acceptance_withdrawal_stales_publication_and_no_fallback_to_af13_approval(self):
  f=self.f;v=reviewed(f);p=d.publish(f['acceptor'],f['case'].pk,v.pk);decide(f,'accept','withdraw');lease=claim_publication()
  with self.assertRaises(ValidationError):d.deliver(*lease)
  self.assertEqual(PublicationReceipt.objects.count(),0);self.assertTrue(d.report(f['actor'],f['case'].pk,v.pk)['findings']);self.assertEqual(v.reviews.count(),1)
 def test_policy_successor_and_review_ttl_require_new_reviewed_projection(self):
  f=self.f;v=reviewed(f);r=v.reviews.get()
  with patch('apps.finance.accepted_documents.timezone.now',return_value=r.created_at+timedelta(seconds=601)):
   self.assertTrue(h.report(f['actor'],f['case'].pk,f['handoff'].pk)['scoped_acceptance_current'])
   with self.assertRaises(ValidationError):d.publish(f['acceptor'],f['case'].pk,v.pk)
  policy(f,PUBLICATION,dict(f['publication_rules'],fields=['handoff']))
  with self.assertRaises(ValidationError):d.publish(f['acceptor'],f['case'].pk,v.pk)
  newer=draft(f,document_id=v.document_id);self.assertEqual(newer.number,2);self.assertEqual(len(newer.payload['sections']),1)
 def test_uncertain_effect_reconciles_committed_receipts_after_source_revocation(self):
  f=self.f;v=reviewed(f);p=d.publish(f['acceptor'],f['case'].pk,v.pk);run_publication_once(PublicationTimeoutAfterAccept());p.job.refresh_from_db();self.assertEqual(p.job.status,'unknown');self.assertEqual(PublicationReceipt.objects.count(),1)
  Grant.objects.filter(case=f['case'],user=f['actor'],action='ledger.private.read').update(active=False)
  run_publication_once();p.job.refresh_from_db();self.assertEqual(p.job.status,'confirmed');self.assertEqual(PublicationReceipt.objects.count(),1)
  with self.assertRaises(PermissionDenied):d.report(f['actor'],f['case'].pk,v.pk)
 def test_cached_source_private_ui_generic_agent_and_operator_export_boundaries(self):
  f=self.f;v=reviewed(f);d.publish(f['acceptor'],f['case'].pk,v.pk);manifest=bundle(f['actor'],f['case'],500);self.assertTrue(investigate(f['actor'],f['case'].pk)['findings']);self.assertEqual(AgentRun.objects.count(),0)
  with self.assertRaises(PermissionDenied):reserve_publication(f['actor'],f['case'].pk,v.pk,rev(f['case']))
  with self.assertRaises(ValidationError):check_document(f['actor'],f['case'].pk,v.pk)
  with self.assertRaises(ValidationError):create_version(f['actor'],f['case'].pk,f['template'].pk,'Bypass','internal',{},rev(f['case']))
  from apps.finance.forecast_forms import commands
  forms=commands(f['case']);self.assertFalse(next(x for x in forms if x['action']=='publish')['form'].fields['version'].queryset.filter(pk=v.pk).exists())
  Grant.objects.filter(case=f['case'],user=f['actor'],action='ledger.private.read').update(active=False)
  with self.assertRaises(PermissionDenied):readable_manifest(f['actor'],f['case'],manifest)
  self.client.force_login(f['actor']);self.assertEqual(self.client.get(reverse('accepted_finance_report',args=[f['case'].pk,v.pk])).status_code,403)
 def test_real_http_draft_review_publish_and_generic_documents_hide_native(self):
  f=self.f;c=f['case'];url=reverse('accepted_finance',args=[c.pk]);self.client.force_login(f['actor']);self.assertEqual(self.client.get(url).status_code,200)
  self.assertEqual(self.client.post(url,{'action':'draft','revision':rev(c),'handoff':f['handoff'].pk,'template':f['template'].pk,'audience':'internal','document_id':''}).status_code,302);v=d.Version.objects.get(template=f['template'])
  self.client.force_login(f['recipient']);self.assertEqual(self.client.post(url,{'action':'review','revision':rev(c),'version':v.pk,'verdict':'approve','note':'Independent HTTP review'}).status_code,302)
  self.client.force_login(f['acceptor']);self.assertEqual(self.client.post(url,{'action':'publish','revision':rev(c),'version':v.pk}).status_code,302);self.assertEqual(d.Publication.objects.count(),1)
  self.client.force_login(f['actor']);self.assertEqual(self.client.post(url,{'action':'template','revision':rev(c),'name':'Malformed template','definition':'[]','evidence':f['e'].pk}).status_code,302);self.assertEqual(d.Template.objects.filter(case=c).count(),1)
  self.assertEqual(self.client.get(reverse('accepted_finance_report',args=[c.pk,999999])).status_code,404)
  self.assertEqual(self.client.get(reverse('accepted_finance_report',args=['00000000-0000-0000-0000-000000000001',v.pk])).status_code,404)
  self.assertEqual(self.client.post(url,{'action':'policy','revision':rev(c),'content':json.dumps(f['publication_rules']),'evidence':f['e'].pk,'effective_from':timezone.now().isoformat()}).status_code,302)
  from apps.policy.models import Configuration
  configs=Configuration.objects.filter(case=c,component=PUBLICATION).order_by('-revision');self.assertEqual(configs.count(),2);self.assertEqual(configs.first().states.latest('pk').state,'draft')
  self.assertEqual(self.client.get(reverse('accepted_finance_report',args=[c.pk,v.pk]))['Cache-Control'],'no-store');self.assertNotContains(self.client.get(reverse('documents',args=[c.pk])),'Accepted Finance / AF13 metadata')
 def test_database_binding_immutable_and_cross_case_lineage_denied(self):
  f=self.f;v=draft(f);b=d.binding(v)
  with self.assertRaises(DatabaseError),transaction.atomic():
   with connection.cursor() as cur:cur.execute('UPDATE finance_acceptedfinancedocument SET sha256=%s WHERE id=%s',['0'*64,b.pk])
  with self.assertRaises(DatabaseError),transaction.atomic():
   with connection.cursor() as cur:cur.execute('UPDATE documents_version SET audience=%s WHERE id=%s',['client',v.pk])
  from apps.core.models import Case
  foreign=Case.objects.create(tenant=f['case'].tenant,title='Wrong document case',kind='project',synthetic=True)
  doc=d.Document.objects.create(case=foreign,title=v.document.title,owner=f['actor'])
  wrong=d.Version.objects.create(document=doc,number=1,template=f['template'],audience=v.audience,fields={},source_manifest=v.source_manifest,baseline_manifest={},payload=v.payload,payload_sha256=v.payload_sha256,created_by=f['actor'])
  with self.assertRaises(DatabaseError),transaction.atomic():d.Binding.objects.create(version=wrong,handoff=f['handoff'],policy=f['publication_policy'],snapshot=b.snapshot,sha256=b.sha256)


 def test_held_operator_retry_preserves_attempt_budget_and_unknown_cannot_cancel(self):
  from apps.documents.delivery import operate_publication
  f=self.f;v=reviewed(f);p=d.publish(f['acceptor'],f['case'].pk,v.pk);j=p.job;j.status='held';j.attempts=2;j.save(update_fields=['status','attempts'])
  operate_publication(f['actor'],f['case'].pk,j.pk,'retry','Retry unchanged source-authorised intent',None);j.refresh_from_db();self.assertEqual((j.status,j.attempts),('pending',2))
  j.status='unknown';j.save(update_fields=['status'])
  with self.assertRaises(ValidationError):operate_publication(f['actor'],f['case'].pk,j.pk,'cancel','Cannot assume no effect',None)
  self.assertEqual(d.Publication.objects.count(),1)
 def test_review_withdrawal_and_source_successor_hold_new_effects(self):
  f=self.f;v=reviewed(f);p=d.publish(f['acceptor'],f['case'].pk,v.pk);d.review(f['recipient'],f['case'].pk,v.pk,'withdraw','Withdraw exact document review');lease=claim_publication()
  with self.assertRaises(ValidationError):d.deliver(*lease)
  self.assertEqual(PublicationReceipt.objects.count(),0)
  d.review(f['recipient'],f['case'].pk,v.pk,'approve','New review does not silently replace reserved decision')
  with self.assertRaises(ValidationError):d.deliver(*lease)
  h.prepare(f['actor'],f['case'].pk,f['draft'].pk,f['package'].pk,f['handoff'].reference,f['handoff'].pk)
  with self.assertRaises(ValidationError):d.publish(f['acceptor'],f['case'].pk,v.pk)

 def test_d11_recipient_expansion_cannot_broaden_approved_metadata_audience(self):
  from apps.policy.services import register_reference
  from .helpers import activate
  f=self.f;v=reviewed(f)
  r=register_reference(f['actor'],f['case'].pk,'extra-recipient','schema:psl/document-recipient/v1',{'audience':'internal','user_id':f['actor'].pk},f['e'].pk)
  activate(f['actor'],f['case'],'D11.recipient_grant_refs',['accepted-metadata-recipient',r.ref],f['e'])
  with self.assertRaises(ValidationError):d.publish(f['acceptor'],f['case'].pk,v.pk)
  self.assertEqual(d.Publication.objects.count(),0);self.assertTrue(h.report(f['actor'],f['case'].pk,f['handoff'].pk)['scoped_acceptance_current'])

 def test_missing_d11_only_holds_publication_not_native_drafting_or_review(self):
  from apps.policy.services import active_component
  f=self.f;transition(f['actor'],active_component('D11.template_storage_retention_rules',f['case']).pk,'revoked')
  v=reviewed(f);self.assertEqual(v.reviews.get().verdict,'approve')
  with self.assertRaises(ValidationError):d.publish(f['acceptor'],f['case'].pk,v.pk)
  self.assertEqual(d.Publication.objects.count(),0)

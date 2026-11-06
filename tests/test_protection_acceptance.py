import copy,json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from datetime import timedelta
from django.test import TestCase,override_settings
from django.conf import settings
from django.core.exceptions import ValidationError,PermissionDenied
from django.db import transaction,DatabaseError
from django.utils import timezone
from django.urls import reverse
from apps.documents import protection_acceptance as d,validation as af
from apps.documents.protection_models import PrivateProtectionPacket
from apps.workflows import readiness as r,operator_delivery as ow
from apps.identity.models import Grant
from apps.policy.protection_acceptance_validators import COMPONENT,OWNER,SCHEMA,OWNER_SCHEMA
from apps.policy.services import transition
from apps.agents import protection_acceptance as agent
from apps.agents.models import AgentRun
from apps.core.evidence_access import public_timeline
from adapters.operator_protection import NativeMetadataProtectionAdapter
from .protection_acceptance_helpers import fixture,package,prepare,rules,owners,configure,reviews
from .private_protection_helpers import assessed
from .readiness_helpers import endpoint
from .operator_helpers import provision_test_database,evidence
from .validation_helpers import policy
from .helpers import rev

@override_settings(OPERATOR_DRILL_DATABASE='test_psl_drill_operators',READINESS_DATABASE_REVISION='fixture-v1')
class ProtectionAcceptanceTests(TestCase):
 @classmethod
 def setUpTestData(cls):
  cls.enterClassContext(endpoint());provision_test_database();tmp=cls.enterClassContext(TemporaryDirectory(prefix='protection-owner-',dir=settings.BASE_DIR/'.runtime'));cls.enterClassContext(patch('adapters.operator_protection.storage_root',return_value=Path(tmp)))
  cls.base=fixture();cls.fixture_now=timezone.now()
 def setUp(self):
  self.f=dict(self.base)
  # Keep shared synthetic source proof inside its original window across long runs.
  # Expiry scenarios explicitly advance this external clock; worker/fence tests use real time.
  self.enterContext(patch('django.utils.timezone.now',return_value=self.fixture_now))
 def ready(self):
  f=self.f;f['protection_owner_policy']=owners(f);f['protection_policy']=configure(f);f['protection_reviews']=reviews(f);return f
 def test_closed_native_packet_three_human_reviews_export_and_source_policy_independence(self):
  f=self.ready();v=d.export(f['actor'],f['case'].pk,f['protection_packet'].pk)
  self.assertEqual(v['acceptance_review'],f['protection_reviews'][-1].pk);self.assertEqual(v['evidence']['restore_job'],f['restore'].pk)
  self.assertFalse(v['current_authority_restored']);self.assertFalse(v['full_database_restore']);self.assertFalse(v['operational_acceptance']);self.assertNotIn('TX-001',json.dumps(v));self.assertNotIn('accepted_private_readiness',json.dumps(v))
  from apps.finance.readiness_acceptance import export
  self.assertTrue(export(f['actor'],f['case'].pk,f['packet'].pk));self.assertTrue(r.report(f['actor'],f['case'].pk,f['private_assessment'].pk)['review_current'])
 def test_capture_and_configured_negative_decisions_before_missing_acceptance_criteria(self):
  f=self.f;self.assertFalse(d.report(f['actor'],f['case'].pk,f['protection_packet'].pk)['evidence_current']);owners(f)
  af.review(f['recipient'],f['case'].pk,f['protection_package'].pk,'meaning','return','missing-criteria-return',f['protection_owner_evidence'].pk,'Retain evidence; criteria remain unknown',None)
  with self.assertRaises(ValidationError):af.review(f['recipient'],f['case'].pk,f['protection_package'].pk,'meaning','approve','missing-criteria-positive',f['protection_owner_evidence'].pk,'Cannot approve current evidence yet',None)
  self.assertEqual(PrivateProtectionPacket.objects.count(),1)
 def test_policy_validates_exact_inventory_owner_scope_authority_and_private_grants(self):
  f=self.f;owners(f)
  for changes in [{'inventory':[]},{'inventory':[{'package_id':f['protection_package'].pk,'assessment_id':999999}]},{'receipt_requirement':'invented'},{'freshness_seconds':None}]:
   with self.subTest(changes=changes),self.assertRaises(ValidationError):configure(f,rules(f,**changes))
  other=r.assess(f['actor'],f['case'].pk,f['private_contract'].pk,'different-bound-assessment')
  with self.assertRaisesMessage(ValidationError,'bound private protection assessment'):configure(f,rules(f,inventory=[{'package_id':f['protection_package'].pk,'assessment_id':other.pk}]))
  bad=copy.deepcopy(f['owner_rules']);bad['assignments'][0]['user_id']=999999
  with self.assertRaises(ValidationError):owners(f,bad)
  Grant.objects.filter(case=f['case'],user=f['acceptor'],action='ledger.private.read').update(active=False)
  with self.assertRaises(ValidationError):configure(f)
 def test_acceptor_cannot_be_packet_or_transport_preparer_or_reviewer(self):
  f=self.f;v=copy.deepcopy(f['owner_rules']);v['assignments'][1]['user_id']=f['recipient'].pk;owners(f,v);configure(f)
  for kind in ['meaning','expectations']:af.review(f['recipient'],f['case'].pk,f['protection_package'].pk,kind,'approve',kind,f['protection_owner_evidence'].pk,'Explicit synthetic '+kind,None)
  with self.assertRaises(PermissionDenied):af.review(f['recipient'],f['case'].pk,f['protection_package'].pk,'acceptance','approve','self-transport',f['protection_owner_evidence'].pk,'Must not accept own transport proof',None)
 def test_owner_withdrawal_retains_history_without_revoking_original_source_acceptance(self):
  f=self.ready();af.review(f['acceptor'],f['case'].pk,f['protection_package'].pk,'acceptance','revoke','withdraw-owner',f['protection_owner_evidence'].pk,'Withdraw this selected owner acceptance',None)
  with self.assertRaises(ValidationError):d.export(f['actor'],f['case'].pk,f['protection_packet'].pk)
  self.assertEqual(d.report(f['actor'],f['case'].pk,f['protection_packet'].pk)['status']['reviews']['acceptance']['verdict'],'revoke')
  from apps.finance.readiness_acceptance import export
  self.assertTrue(export(f['actor'],f['case'].pk,f['packet'].pk))
 def test_revoked_source_denies_cached_reports_exports_reviews_revisions_and_ui_choices(self):
  f=self.ready();self.client.force_login(f['actor']);url=reverse('protection_acceptance_report',args=[f['case'].pk,f['protection_packet'].pk]);self.assertEqual(self.client.get(url).status_code,200)
  Grant.objects.filter(case=f['case'],user=f['actor'],action='ledger.private.read').update(active=False)
  for call in [lambda:d.report(f['actor'],f['case'].pk,f['protection_packet'].pk),lambda:d.export(f['actor'],f['case'].pk,f['protection_packet'].pk),lambda:package(f,'protection-owner-package')]:
   with self.assertRaises(PermissionDenied):call()
  self.assertEqual(self.client.get(url).status_code,403);self.assertFalse(d.visible(f['actor'],f['case']).exists());self.assertEqual(agent.investigate(f['actor'],f['case'].pk)['findings'],[])
  Grant.objects.filter(case=f['case'],user=f['acceptor'],action='ledger.private.read').update(active=False)
  with self.assertRaises(PermissionDenied):af.review(f['acceptor'],f['case'].pk,f['protection_package'].pk,'acceptance','approve','owner-acceptance',f['protection_owner_evidence'].pk,'Explicit synthetic protection evidence acceptance',None)
 def test_transport_withdrawal_and_policy_changes_hold_current_use_but_allow_negative_owner_decision(self):
  f=self.ready();r.review(f['reviewer'],f['case'].pk,f['private_assessment'].pk,'withdraw','transport-withdraw',f['private_review_evidence'].pk)
  self.assertFalse(d.report(f['actor'],f['case'].pk,f['protection_packet'].pk)['evidence_current'])
  af.review(f['acceptor'],f['case'].pk,f['protection_package'].pk,'acceptance','revoke','source-held-withdraw',f['protection_owner_evidence'].pk,'Withdraw while transport held',None)
 def test_acceptance_policy_supersession_revocation_and_fresh_packet_expiry(self):
  f=self.ready();configure(f,rules(f,receipt_requirement='found'))
  with self.assertRaises(ValidationError):d.export(f['actor'],f['case'].pk,f['protection_packet'].pk)
  package(f,'fresh-expiry-package');prepare(f,'fresh-expiry-packet');f['protection_policy']=configure(f,rules(f,freshness_seconds=300));reviews(f,'fresh-expiry')
  future=timezone.now()+timedelta(seconds=301)
  with patch('apps.documents.protection_acceptance.timezone.now',return_value=future):
   self.assertFalse(d.report(f['actor'],f['case'].pk,f['protection_packet'].pk)['evidence_current'])
  transition(f['actor'],f['protection_policy'].pk,'revoked')
  af.review(f['acceptor'],f['case'].pk,f['protection_package'].pk,'acceptance','revoke','criteria-revoked',f['protection_owner_evidence'].pk,'Owner authority remains independently configured',None)
 def test_successor_needs_fresh_package_explicit_parent_and_new_owner_reviews(self):
  f=self.ready();old=f['protection_packet'];package(f,'successor-package')
  with self.assertRaises(ValidationError):prepare(f)
  new=prepare(f,predecessor=old.pk);self.assertEqual(new.parent_id,old.pk)
  with self.assertRaises(ValidationError):d.export(f['actor'],f['case'].pk,old.pk)
  configure(f);reviews(f,'successor');self.assertEqual(d.export(f['actor'],f['case'].pk,new.pk)['packet'],new.pk)
 def test_database_immutable_exact_lineage_fresh_scope_and_bidirectional_source_cycles(self):
  f=self.ready();b=f['protection_packet']
  with self.assertRaises(DatabaseError),transaction.atomic():PrivateProtectionPacket.objects.filter(pk=b.pk).update(snapshot={})
  p=package(f,'sql-package');value=dict(b.snapshot,package=p.pk,package_sha256=p.sha256)
  with self.assertRaises(DatabaseError),transaction.atomic():PrivateProtectionPacket.objects.create(case=f['case'],reference='sql-bad',version=1,package=p,assessment=f['assessment'],actor=f['actor'],snapshot=value,sha256=d.digest(value))
  with self.assertRaises(ValidationError):d.prepare(f['actor'],f['case'].pk,f['private_assessment'].pk,f['owner_package'].pk,'cycle')
  from apps.finance import readiness_acceptance as source
  with self.assertRaises(ValidationError):source.prepare(f['actor'],f['case'].pk,f['assessment'].pk,b.package_id,'cycle-source')
  from apps.finance.acceptance_models import PrivateReadinessPacket,FinanceHandoff
  with self.assertRaises(DatabaseError),transaction.atomic():PrivateReadinessPacket.objects.create(case=f['case'],reference='sql-cycle',version=1,package=b.package,assessment=f['assessment'],actor=f['actor'],snapshot=f['packet'].snapshot,sha256=f['packet'].sha256)
  h=f['handoff'];values={field.name:getattr(h,field.name) for field in h._meta.fields if field.name not in ['id','created_at','package','reference','version']}
  with self.assertRaises(DatabaseError),transaction.atomic():FinanceHandoff.objects.create(**values,package=b.package,reference='sql-cycle-handoff',version=1)
 def test_private_live_agent_generic_omissions_and_real_http_typed_prepare_policy_review(self):
  f=self.ready();before=AgentRun.objects.count();self.assertTrue(agent.investigate(f['actor'],f['case'].pk)['findings']);self.assertEqual(AgentRun.objects.count(),before)
  from apps.agents.validation import investigate
  run=investigate(f['actor'],f['case'].pk,None);self.assertFalse(any(x['package']==f['protection_package'].pk for x in run.result['packages']));self.assertFalse(public_timeline(f['case']).filter(action__startswith='agent.data.protection_acceptance').exists())
  self.client.force_login(f['actor']);url=reverse('protection_acceptance',args=[f['case'].pk]);response=self.client.get(url);self.assertEqual(response.status_code,200);self.assertEqual(response['Cache-Control'],'no-store');self.assertContains(response,'Private protection readiness')
  p=package(f,'http-package');self.assertEqual(self.client.post(url,{'action':'prepare','revision':rev(f['case']),'assessment':f['private_assessment'].pk,'package':p.pk,'reference':'http-packet'}).status_code,302)
  self.assertTrue(PrivateProtectionPacket.objects.filter(reference='http-packet').exists())
  from apps.policy.models import Configuration
  count=Configuration.objects.filter(component=COMPONENT).count()
  self.assertEqual(self.client.post(url,{'action':'policy','revision':rev(f['case']),'component':COMPONENT,'content':json.dumps(rules(f)),'evidence':f['e'].pk,'effective_from':timezone.now().isoformat()}).status_code,302)
  from apps.policy.models import Configuration
  self.assertEqual(Configuration.objects.filter(component=COMPONENT).count(),count+1)
  self.assertEqual(Configuration.objects.filter(component=COMPONENT).latest('pk').envelope['value']['schema_ref'],SCHEMA)
  self.assertEqual(self.client.get(reverse('protection_acceptance_export',args=[f['case'].pk,f['protection_packet'].pk])).status_code,200)
  self.assertEqual(self.client.get(reverse('protection_acceptance_report',args=[f['case'].pk,999999])).status_code,404)
  http_packet=PrivateProtectionPacket.objects.get(reference='http-packet');self.client.force_login(f['recipient'])
  self.assertEqual(self.client.post(url,{'action':'review','revision':rev(f['case']),'packet':http_packet.pk,'kind':'meaning','verdict':'return','operation_key':'http-owner-return','reason':'Actual synthetic owner requests more evidence','evidence':f['protection_owner_evidence'].pk}).status_code,302)
  self.assertTrue(http_packet.package.reviews.filter(operation_key='http-owner-return',verdict='return',actor=f['recipient']).exists())
 def test_http_review_form_requires_granted_actions_and_limits_decision_types(self):
  from uuid import uuid4
  f=self.f;self.client.force_login(f['actor']);grants=Grant.objects.filter(case=f['case'],user=f['actor'],action__in=['validation.review','validation.accept'])
  for route in ['protection_acceptance_report','protection_acceptance_export','private_readiness_report','private_readiness_export']:
   self.assertEqual(self.client.get(reverse(route,args=[uuid4(),1])).status_code,404)
  for route in ['protection_acceptance','private_readiness_acceptance']:
   with self.subTest(route=route):
    self.assertEqual(self.client.get(reverse(route,args=[uuid4()])).status_code,404)
    url=reverse(route,args=[f['case'].pk]);grants.update(active=False)
    response=self.client.get(url);self.assertEqual(response.status_code,200);self.assertNotContains(response,'Record separate AF13 owner decision');self.assertFalse(any(x['key']=='review' for x in response.context['commands']))
    self.assertEqual(self.client.post(url,{'action':'review'}).status_code,403)
    for action,expected in [('validation.review',['meaning','expectations']),('validation.accept',['acceptance'])]:
     grants.update(active=False);grants.filter(action=action).update(active=True)
     response=self.client.get(url);self.assertEqual(response.status_code,200);form=next(x['form'] for x in response.context['commands'] if x['key']=='review');self.assertEqual([k for k,_ in form.fields['kind'].choices],expected)
  Grant.objects.filter(case=f['case'],user=f['actor'],action='ledger.private.read').update(active=False)
  for route in ['protection_acceptance','private_readiness_acceptance']:
   response=self.client.get(reverse(route,args=[f['case'].pk]));self.assertEqual(response.status_code,200);self.assertEqual(response.context['rows'],[])
   self.assertFalse(next(x['form'] for x in response.context['commands'] if x['key']=='prepare').fields['assessment'].queryset.exists())
 def test_selected_four_process_synthetic_acceptance_keeps_independent_tester_and_source_policy(self):
  f=self.f;ids=['F01','B13','P13','P15'];original=af.DiscoverySource.objects.get(pk=f['package'].payload['source_ids'][0]);metadata=copy.deepcopy(original.metadata);metadata['process_ids']=ids
  for clause in metadata['clauses']:clause['process_ids']=ids
  src=af.capture_source(f['actor'],f['case'].pk,'protection-synthetic-scope',original.evidence_id,metadata,None);examples=[]
  for kind,value in [('normal',{'metadata_only':True}),('exception',{'restore_authority':False})]:examples.append(af.capture_example(f['actor'],f['case'].pk,'protection-implementation-'+kind,ids,kind,value,f['e'].pk,None))
  p=package(f,'implementation-package',dict(f['package'].payload,process_ids=ids,source_ids=[src.pk],example_ids=[e.pk for e in examples],level='synthetic_implementation',role_list=['Finance','Process owners'],manual_fallback='Hold uncertain effects and inspect original receipts',rollout_plan='Synthetic scope only',migration_plan='No production migration claimed',support_owner_id=f['actor'].pk));prepare(f,'implementation-packet');owners(f);configure(f)
  for kind in ['meaning','expectations']:af.review(f['recipient'],f['case'].pk,p.pk,kind,'approve','implementation-'+kind,f['protection_owner_evidence'].pk,'Explicit selected synthetic '+kind,None)
  with self.assertRaises(ValidationError):af.review(f['acceptor'],f['case'].pk,p.pk,'acceptance','approve','before-comparison',f['protection_owner_evidence'].pk,'Comparisons missing',None)
  from django.contrib.auth import get_user_model
  from apps.core.management.commands.seed_demo import ACTIONS
  tester=get_user_model().objects.create_user(username='protection-independent-tester');Grant.objects.bulk_create([Grant(case=f['case'],user=tester,action=x) for x in ACTIONS]);rows=[];reports=[]
  for e in examples:
   v={'example_id':e.pk,'actual':e.expected,'build_ref':p.payload['build_ref'],'run_ref':'synthetic:'+e.scenario,'environment':'isolated-postgresql-tests','evidence_class':'synthetic_fixture'};ev=evidence(f,'validation_result',json.dumps(v));reports.append(ev);rows.append(af.record_replay(tester,f['case'].pk,p.pk,ev.pk,'compare-'+e.scenario,None))
  accepted=af.review(f['acceptor'],f['case'].pk,p.pk,'acceptance','approve','selected-synthetic',f['protection_owner_evidence'].pk,'Selected synthetic protection evidence only',None)
  v=d.export(f['actor'],f['case'].pk,f['protection_packet'].pk);self.assertEqual(v['process_ids'],ids);self.assertEqual(v['acceptance_review'],accepted.pk);self.assertTrue(all(not row.result['underlying_workflow_executed'] for row in rows))
  from apps.finance.readiness_acceptance import export
  self.assertTrue(export(f['actor'],f['case'].pk,f['packet'].pk))
  Grant.objects.filter(case=f['case'],user=tester,action='ledger.private.read').update(active=False)
  with self.assertRaises(PermissionDenied):af.record_replay(tester,f['case'].pk,p.pk,reports[0].pk,'compare-normal',None)
 def test_z_actual_receipt_change_requires_fresh_assessment_packet_and_found_criteria(self):
  f=self.ready();old=f['protection_packet'];lease=ow.claim();value=ow.dispatch(*lease,NativeMetadataProtectionAdapter());ow.finish(*lease,'confirmed',value)
  self.assertFalse(d.report(f['actor'],f['case'].pk,old.pk)['evidence_current']);assessed(f,'found-restore');package(f,'found-owner-package');new=prepare(f,predecessor=old.pk);configure(f,rules(f,receipt_requirement='found'));reviews(f,'found-owner')
  v=d.export(f['actor'],f['case'].pk,new.pk);self.assertEqual(v['evidence']['receipt_state'],'found');self.assertFalse(v['full_database_restore'])

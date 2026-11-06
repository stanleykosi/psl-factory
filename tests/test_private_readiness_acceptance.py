import json
from datetime import timedelta
from unittest.mock import patch
from django.test import TestCase,override_settings
from django.core.exceptions import ValidationError,PermissionDenied
from django.db import transaction,connection,DatabaseError
from django.urls import reverse
from django.utils import timezone
from apps.finance import readiness_acceptance as d
from apps.documents import validation as af
from apps.workflows import readiness as r
from apps.identity.models import Grant
from apps.agents.models import AgentRun
from apps.agents import private_readiness as agent
from apps.agents.validation import investigate
from apps.core.evidence_access import public_timeline
from apps.policy.services import transition
from apps.policy.validation_validators import ACCEPTANCE,PRIVATE_SCHEMA
from .private_readiness_helpers import fixture,configure,rules,reviews,package
from .publication_readiness_helpers import assessed
from .readiness_helpers import endpoint
from .helpers import rev

class PrivateReadinessAcceptanceTests(TestCase):
 @classmethod
 def setUpTestData(cls):
  cls.enterClassContext(endpoint());cls.enterClassContext(override_settings(READINESS_DATABASE_REVISION='fixture-v1'));cls.base=fixture()
 def setUp(self):self.f=dict(self.base)
 def test_separate_human_reviews_and_closed_accepted_metadata_export(self):
  f=self.f;configure(f)
  with self.assertRaises(ValidationError):d.export(f['actor'],f['case'].pk,f['packet'].pk)
  rows=reviews(f);value=d.export(f['actor'],f['case'].pk,f['packet'].pk)
  self.assertEqual(value['acceptance_review'],rows[-1].pk);self.assertEqual(value['acceptor'],f['acceptor'].pk);self.assertFalse(value['operational_acceptance']);self.assertFalse(value['deployment_authorized'])
  self.assertEqual(value['evidence']['receipt_state'],'not_found');self.assertEqual(value['evidence']['assessment'],f['assessment'].pk);self.assertNotIn('sections',json.dumps(value));self.assertNotIn('TX-001',json.dumps(value));self.assertNotIn('body',value)
  self.assertTrue(af.acceptance_report(f['actor'],f['case'].pk,rows[-1].pk)['requested_record_is_current']);self.assertEqual(d.prepare(f['actor'],f['case'].pk,f['assessment'].pk,f['owner_package'].pk,'capability-owner').pk,f['packet'].pk)
 def test_missing_private_policy_holds_approvals_not_preparation_or_return(self):
  f=self.f;self.assertEqual(d.Packet.objects.count(),1)
  with self.assertRaises(ValidationError):reviews(f)
  row=af.review(f['recipient'],f['case'].pk,f['owner_package'].pk,'meaning','return','return',f['owner_evidence'].pk,'Need configured private criteria',None);self.assertEqual(row.verdict,'return')
  self.assertTrue(r.report(f['actor'],f['case'].pk,f['assessment'].pk)['review_current']);configure(f);self.assertEqual(len(reviews(f)),3)
 def test_policy_validates_exact_scope_inventory_and_private_owner_grants(self):
  f=self.f
  for change in [{'inventory':[{'package_id':999999,'assessment_id':f['assessment'].pk}]},{'inventory':[{'package_id':f['owner_package'].pk,'assessment_id':999999}]},{'freshness_seconds':0},{'receipt_requirement':'automatically_accepted'},{'independent_transport_acceptor':False}]:
   with self.subTest(change=change),self.assertRaises(ValidationError):configure(f,rules(f,**change))
  Grant.objects.filter(case=f['case'],user=f['acceptor'],action='ledger.private.read').update(active=False)
  with self.assertRaises(ValidationError):configure(f)
 def test_receipt_requirement_and_policy_revocation_are_narrow_holds(self):
  f=self.f;configure(f,rules(f,receipt_requirement='found'))
  with self.assertRaisesRegex(ValidationError,'committed native receipt'):reviews(f)
  self.assertTrue(r.report(f['actor'],f['case'].pk,f['assessment'].pk)['review_current']);cfg=configure(f);reviews(f);transition(f['actor'],cfg.pk,'revoked')
  with self.assertRaises(ValidationError):d.export(f['actor'],f['case'].pk,f['packet'].pk)
  self.assertEqual(f['owner_package'].reviews.count(),3)
 def test_transport_reviewer_cannot_self_accept_and_new_negative_owner_decision_never_falls_back(self):
  f=self.f;configure(f);rows=reviews(f)
  with self.assertRaises(PermissionDenied):d.review_pins(f['owner_package'],f['recipient'],'acceptance')
  af.review(f['acceptor'],f['case'].pk,f['owner_package'].pk,'acceptance','revoke','withdraw-owner',f['owner_evidence'].pk,'Withdrawing scoped approval',None)
  with self.assertRaises(ValidationError):d.export(f['actor'],f['case'].pk,f['packet'].pk)
  self.assertFalse(af.acceptance_report(f['actor'],f['case'].pk,rows[-1].pk)['requested_record_is_current'])
 def test_new_probe_or_transport_withdrawal_requires_new_packet_and_explicit_successor(self):
  f=self.f;configure(f);reviews(f);r.review(f['recipient'],f['case'].pk,f['assessment'].pk,'withdraw','transport-withdraw',f['review_evidence'].pk)
  self.assertFalse(d.report(f['actor'],f['case'].pk,f['packet'].pk)['evidence_current'])
  with self.assertRaises(ValidationError):d.export(f['actor'],f['case'].pk,f['packet'].pk)
  assessed(f,'fresh-transport');package(f,'readiness-owner-successor')
  with self.assertRaises(ValidationError):d.prepare(f['actor'],f['case'].pk,f['assessment'].pk,f['owner_package'].pk,'capability-owner')
  b=d.prepare(f['actor'],f['case'].pk,f['assessment'].pk,f['owner_package'].pk,'capability-owner',f['packet'].pk);self.assertEqual(b.version,2);configure(f);reviews(f)
  self.assertFalse(d.report(f['actor'],f['case'].pk,f['packet'].pk)['evidence_current']);self.assertEqual(d.export(f['actor'],f['case'].pk,b.pk)['packet'],b.pk)
 def test_revoked_source_denies_cached_reports_generic_export_and_historical_review_retry(self):
  from apps.finance.acceptance import visible_packages
  f=self.f;configure(f);rows=reviews(f);d.export(f['actor'],f['case'].pk,f['packet'].pk)
  Grant.objects.filter(case=f['case'],user=f['actor'],action='ledger.private.read').update(active=False)
  for call in [lambda:d.report(f['actor'],f['case'].pk,f['packet'].pk),lambda:d.export(f['actor'],f['case'].pk,f['packet'].pk),lambda:af.acceptance_report(f['actor'],f['case'].pk,rows[-1].pk)]:
   with self.assertRaises(PermissionDenied):call()
  self.assertFalse(visible_packages(f['actor'],f['case']).filter(pk=f['owner_package'].pk).exists());self.assertFalse(d.visible(f['actor'],f['case']).exists())
  with self.assertRaises(PermissionDenied):af.prepare_package(f['actor'],f['case'].pk,f['owner_package'].reference,dict(f['owner_package'].payload),f['e'].pk,None)
  self.client.force_login(f['actor'])
  for name in ['private_readiness_report','private_readiness_export']:self.assertEqual(self.client.get(reverse(name,args=[f['case'].pk,f['packet'].pk])).status_code,403)
  Grant.objects.filter(case=f['case'],user=f['recipient'],action='ledger.private.read').update(active=False)
  with self.assertRaises(PermissionDenied):af.review(f['recipient'],f['case'].pk,f['owner_package'].pk,'meaning','approve','private-meaning',f['owner_evidence'].pk,'Actual isolated synthetic human decision: meaning',None)
 def test_generic_agent_timeline_omit_private_proof_and_live_agent_has_no_effect_tools(self):
  f=self.f;configure(f);reviews(f);before=AgentRun.objects.count();value=agent.investigate(f['actor'],f['case'].pk);self.assertTrue(value['findings']);self.assertEqual(value['business_effect_tools'],[]);self.assertEqual(AgentRun.objects.count(),before)
  run=investigate(f['actor'],f['case'].pk,None);self.assertFalse(any(x['package']==f['owner_package'].pk for x in run.result['packages']));self.assertNotIn('native_internal_capability_metadata',json.dumps(run.result));self.assertFalse(public_timeline(f['case']).filter(data__packet=f['packet'].pk).exists());self.assertFalse(public_timeline(f['case']).filter(data__review__in=[x.pk for x in f['owner_package'].reviews.all()]).exists())
 def test_packet_database_immutability_and_case_lineage(self):
  from apps.core.models import Case
  f=self.f;b=f['packet']
  with self.assertRaises(DatabaseError),transaction.atomic():
   with connection.cursor() as c:c.execute('UPDATE finance_privatereadinesspacket SET sha256=%s WHERE id=%s',['0'*64,b.pk])
  other=Case.objects.create(tenant=f['case'].tenant,kind='project',title='Wrong private packet case',synthetic=True)
  with self.assertRaisesRegex(DatabaseError,'Exact fresh private readiness'),transaction.atomic():d.Packet.objects.create(case=other,reference='wrong',version=1,package=f['owner_package'],assessment=f['assessment'],actor=f['actor'],snapshot=b.snapshot,sha256=b.sha256)
 def test_packet_expiry_and_transport_error_hold_current_without_erasing_history(self):
  f=self.f;configure(f);reviews(f)
  with patch('apps.finance.readiness_acceptance.timezone.now',return_value=f['packet'].created_at+timedelta(seconds=3601)):
   with self.assertRaises(ValidationError):d.export(f['actor'],f['case'].pk,f['packet'].pk)
  with patch('adapters.finance_publication_readiness.FinancePublicationReadinessAdapter.receipts',side_effect=ConnectionError('Unavailable')):
   with self.assertRaises(ConnectionError):d.export(f['actor'],f['case'].pk,f['packet'].pk)
   self.assertFalse(d.report(f['actor'],f['case'].pk,f['packet'].pk)['evidence_current'])
  self.assertEqual(f['owner_package'].reviews.count(),3)
 def test_http_owner_decisions_policy_draft_and_private_exports(self):
  from apps.policy.models import Configuration
  f=self.f;configure(f);url=reverse('private_readiness_acceptance',args=[f['case'].pk]);self.client.force_login(f['actor']);response=self.client.get(url);self.assertEqual(response.status_code,200);self.assertEqual(response['Cache-Control'],'no-store');self.assertContains(response,'Typed acceptance configuration')
  response=self.client.post(url,{'action':'policy','revision':rev(f['case']),'content':json.dumps(rules(f)),'evidence':f['e'].pk,'effective_from':(timezone.now()-timedelta(seconds=1)).isoformat()});self.assertEqual(response.status_code,302)
  cfg=Configuration.objects.filter(case=f['case'],component=ACCEPTANCE).latest('pk');self.assertEqual(cfg.envelope['value']['schema_ref'],PRIVATE_SCHEMA);self.assertEqual(cfg.states.latest('pk').state,'draft')
  for kind in ['meaning','expectations','acceptance']:
   self.client.force_login(f['acceptor'] if kind=='acceptance' else f['recipient']);response=self.client.post(url,{'action':'review','revision':rev(f['case']),'packet':f['packet'].pk,'kind':kind,'verdict':'approve','operation_key':'http-'+kind,'reason':'Explicit synthetic owner '+kind,'evidence':f['owner_evidence'].pk});self.assertEqual(response.status_code,302)
  self.client.force_login(f['actor']);response=self.client.get(reverse('private_readiness_export',args=[f['case'].pk,f['packet'].pk]));self.assertEqual(response.status_code,200);self.assertFalse(response.json()['whole_product_accepted']);self.assertEqual(response['Cache-Control'],'no-store')
  for name in ['private_readiness_report','private_readiness_export']:self.assertEqual(self.client.get(reverse(name,args=[f['case'].pk,999999])).status_code,404)

 def test_committed_receipt_change_invalidates_old_packet_and_found_successor_is_accepted(self):
  from apps.documents.delivery import claim_publication
  from apps.finance import accepted_documents
  f=self.f;lease=claim_publication();accepted_documents.deliver(*lease)
  self.assertFalse(d.report(f['actor'],f['case'].pk,f['packet'].pk)['evidence_current'])
  assessed(f,'with-committed-receipt');package(f,'committed-owner')
  successor=d.prepare(f['actor'],f['case'].pk,f['assessment'].pk,f['owner_package'].pk,'capability-owner',f['packet'].pk)
  configure(f,rules(f,receipt_requirement='found'));reviews(f);value=d.export(f['actor'],f['case'].pk,successor.pk)
  self.assertEqual(value['evidence']['receipt_state'],'found');self.assertFalse(value['evidence']['business_acceptance'])

 def test_fresh_package_cannot_reuse_original_handoff_or_bind_after_owner_review(self):
  f=self.f
  with self.assertRaises(ValidationError):d.prepare(f['actor'],f['case'].pk,f['assessment'].pk,f['package'].pk,'recursive')
  p=package(f,'already-reviewed');af.review(f['recipient'],f['case'].pk,p.pk,'meaning','approve','old-owner-meaning',f['owner_evidence'].pk,'Original definition reviewed',None)
  with self.assertRaises(ValidationError):d.prepare(f['actor'],f['case'].pk,f['assessment'].pk,p.pk,'retroactive')
  from apps.finance import acceptance
  with self.assertRaises(ValidationError):acceptance.prepare(f['actor'],f['case'].pk,f['draft'].pk,f['packet'].package_id,'recursive-finance')

 def test_http_typed_agent_preparation_and_revoked_form_inventory(self):
  from apps.finance.readiness_acceptance_views import commands
  from apps.documents.validation_forms import commands as af_commands
  f=self.f;p=package(f,'http-evidence');self.client.force_login(f['actor']);url=reverse('private_readiness_acceptance',args=[f['case'].pk])
  before=AgentRun.objects.count();response=self.client.post(url,{'action':'prepare','revision':rev(f['case']),'assessment':f['assessment'].pk,'package':p.pk,'reference':'http-prepared','predecessor':''});self.assertEqual(response.status_code,302);self.assertTrue(d.Packet.objects.filter(reference='http-prepared',package=p).exists());self.assertEqual(AgentRun.objects.count(),before)
  Grant.objects.filter(case=f['case'],user=f['actor'],action='ledger.private.read').update(active=False)
  for rows in [commands(f['actor'],f['case']),af_commands(f['case'],actor=f['actor'])]:
   for row in rows:
    for field in row['form'].fields.values():
     q=getattr(field,'queryset',None)
     if q is not None and q.model is af.ValidationPackage:self.assertFalse(q.filter(pk=p.pk).exists())

 def test_selected_synthetic_implementation_needs_independent_tester_and_all_af13_scope(self):
  from django.contrib.auth import get_user_model
  from apps.core.management.commands.seed_demo import ACTIONS
  from apps.policy.validation_validators import OWNER
  from .validation_helpers import policy
  from .ledger_helpers import evidence
  from apps.finance import accepted_documents
  f=self.f;ids=['F01','B13','P13','P15'];owner=json.loads(json.dumps(f['owner_rules']))
  for row in owner['assignments']:row['process_ids']=ids
  policy(f['actor'],f['case'],OWNER,owner,f['e'])
  original=af.DiscoverySource.objects.get(pk=f['package'].payload['source_ids'][0]);metadata=json.loads(json.dumps(original.metadata));metadata['process_ids']=ids
  for clause in metadata['clauses']:clause['process_ids']=ids
  source=af.capture_source(f['actor'],f['case'].pk,'synthetic-capability-scope',original.evidence_id,metadata,None);examples=[]
  for kind,value in [('normal',{'read_only':True}),('exception',{'native_authenticity':'unknown'})]:examples.append(af.capture_example(f['actor'],f['case'].pk,'implementation-'+kind,ids,kind,value,f['e'].pk,None))
  payload=dict(f['package'].payload,process_ids=ids,source_ids=[source.pk],example_ids=[x.pk for x in examples],level='synthetic_implementation',role_list=['Finance','Process User','Automation Team'],manual_fallback='Inspect original source and hold uncertain effects',rollout_plan='Isolated synthetic scope only',migration_plan='No production migration asserted',support_owner_id=f['actor'].pk)
  p=package(f,'implementation-owner',payload);b=d.prepare(f['actor'],f['case'].pk,f['assessment'].pk,p.pk,'capability-owner',f['packet'].pk);configure(f)
  for kind in ['meaning','expectations']:af.review(f['recipient'],f['case'].pk,p.pk,kind,'approve','implementation-'+kind,f['owner_evidence'].pk,'Explicit synthetic '+kind,None)
  with self.assertRaises(ValidationError):af.review(f['acceptor'],f['case'].pk,p.pk,'acceptance','approve','missing-evaluation',f['owner_evidence'].pk,'Not yet evaluated',None)
  tester=get_user_model().objects.create_user(username='private-implementation-tester');Grant.objects.bulk_create([Grant(case=f['case'],user=tester,action=x) for x in ACTIONS]);rows=[];reports=[]
  for example in examples:
   value={'example_id':example.pk,'actual':example.expected,'build_ref':p.payload['build_ref'],'run_ref':'synthetic:'+example.scenario,'environment':'isolated-postgresql-tests','evidence_class':'synthetic_fixture'}
   e=evidence(f,'validation_result',json.dumps(value));reports.append(e);rows.append(af.record_replay(tester,f['case'].pk,p.pk,e.pk,'implementation-'+example.scenario,None))
  accepted=af.review(f['acceptor'],f['case'].pk,p.pk,'acceptance','approve','implementation-accepted',f['owner_evidence'].pk,'Selected synthetic scope only; not operational acceptance',None)
  value=d.export(f['actor'],f['case'].pk,b.pk);self.assertEqual(value['process_ids'],ids);self.assertEqual(value['level'],'synthetic_implementation');self.assertEqual(value['acceptance_review'],accepted.pk);self.assertFalse(value['operational_acceptance']);self.assertFalse(value['whole_product_accepted'])
  self.assertTrue(all(x.result['matches'] and not x.result['underlying_workflow_executed'] for x in rows));self.assertEqual(len(accepted.snapshot['replays']),2)
  with self.assertRaises(ValidationError):accepted_documents.current(accepted_documents.binding(f['version']))
  Grant.objects.filter(case=f['case'],user=tester,action='ledger.private.read').update(active=False)
  with self.assertRaises(PermissionDenied):af.record_replay(tester,f['case'].pk,p.pk,reports[0].pk,'implementation-normal',None)

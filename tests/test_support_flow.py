import json,copy
from datetime import timedelta
from django.test import TestCase,Client
from django.utils import timezone
from django.core.exceptions import ValidationError,PermissionDenied
from django.db import connection,transaction,DatabaseError
from apps.baas import support as d
from apps.baas.services import support_action
from apps.baas.models import SupportCase,SupportIntake,SupportEvent,SupportReview,SupportMerge
from apps.policy.support_validators import INTAKE,FLOW,AUTH,METRICS
from apps.policy.services import transition as policy_transition
from apps.identity.models import Grant
from apps.agents.support import investigate
from adapters.support import LocalSupportReportAdapter
from .helpers import rev
from .support_helpers import fixture,capture,ready,act,result,report,policy,evidence
class SupportFlowTests(TestCase):
 def setUp(self):self.f=fixture()
 def test_b14_n01_connected_specialist_flow_ownership_response_and_report(self):
  f=self.f;self.assertEqual(connection.vendor,'postgresql');ready(f);act(f,'respond',f['t']+timedelta(minutes=15));act(f,'investigate',f['t']+timedelta(minutes=16));pending=act(f,'await_specialist',f['t']+timedelta(minutes=17));result(f,pending);end=act(f,'resolve');r=report(f);v=LocalSupportReportAdapter().read(f['reviewer'],f['case'].pk,r.pk)['result'];self.assertEqual(v['meaning'],'resolved');self.assertEqual(v['metrics']['first_response_seconds'],'900.0');self.assertEqual(end.owner_id,f['actor'].pk);self.assertFalse(v['financial_execution_authorized']);self.assertFalse(v['native_channel_verified'])
 def test_b14_e01_missing_specialist_and_resume_bypass_are_blocked(self):
  f=self.f;ready(f);act(f,'investigate');p=act(f,'await_specialist')
  with self.assertRaises(ValidationError):act(f,'resolve')
  act(f,'resume')
  with self.assertRaises(ValidationError):act(f,'resolve')
  result(f,p,'unknown')
  with self.assertRaises(ValidationError):act(f,'resolve')
  self.assertNotEqual(d.head(f['case']).state,'resolved')
 def test_channel_dedup_is_idempotent_and_changed_source_is_held(self):
  f=self.f;i=capture(f);self.assertEqual(capture(f).pk,i.pk)
  with self.assertRaises(ValidationError):capture(f,{'issue_ref':'other'})
  self.assertEqual(SupportIntake.objects.count(),1)
 def test_b01_two_channels_explicit_links_and_unrelated_issues_preserved(self):
  f=self.f;ready(f);i=capture(f,{'channel':'whatsapp','message_ref':'WA-1'});d.link(f['actor'],f['case'].pk,i.pk,f['e']['support_triage'].pk,rev(f['case']));bad=capture(f,{'message_ref':'OTHER','transaction_ref':'TX-OTHER'})
  with self.assertRaises(ValidationError):d.link(f['actor'],f['case'].pk,bad.pk,f['e']['support_triage'].pk)
  r=report(f);self.assertEqual(len(r.result['sources']),2);self.assertEqual(r.result['unlinked_intake_count'],1)
 def test_missing_policy_does_not_block_capture(self):
  f=fixture('unconfigured',configured=False);i=capture(f)
  with self.assertRaises(ValidationError):d.link(f['actor'],f['case'].pk,i.pk,f['e']['support_triage'].pk)
  self.assertTrue(i.pk)
 def test_missing_metric_rule_keeps_unknown_but_summary_can_be_reviewed(self):
  f=self.f;ready(f);policy_transition(f['actor'],f['policies'][METRICS].pk,'revoked');r=report(f);self.assertIsNone(r.result['metrics']['first_response_seconds']);self.assertIn('metric_policy',r.result['metrics']['finding']);self.assertTrue(d.read_report(f['reviewer'],f['case'].pk,r.pk))
 def test_response_bot_does_not_silently_qualify_and_reopen_is_explicit(self):
  f=self.f;ready(f);d.transition(f['actor'],f['case'].pk,'respond',f['actor'].pk,f['e']['support_response'].pk,(f['t']+timedelta(minutes=1)).isoformat(),rev(f['case']),'bot_ack');self.assertIsNone(d.metrics(f['case'])['first_response_seconds']);act(f,'respond',f['t']+timedelta(minutes=15));act(f,'investigate');act(f,'resolve');r=report(f);act(f,'reopen')
  with self.assertRaises(ValidationError):d.read_report(f['actor'],f['case'].pk,r.pk)
  reopened=report(f);self.assertTrue(reopened.result['reopened']);self.assertEqual(reopened.result['metrics']['finding'],'reopened_clock_undefined')
 def test_bad_event_times_and_source_authority_fields_rejected(self):
  f=self.f;ready(f)
  with self.assertRaises(ValidationError):act(f,'respond',f['t']-timedelta(minutes=1))
  with self.assertRaises(ValidationError):act(f,'respond',timezone.now()+timedelta(days=1))
  with self.assertRaises(ValidationError):capture(f,{'grant_authority':'yes','message_ref':'bad'})
 def test_legacy_actions_cannot_bypass_controlled_specialist_flow(self):
  f=self.f;ready(f);act(f,'investigate');act(f,'await_specialist')
  for action in ['respond','resolve','reopen']:
   with self.assertRaises(ValidationError):support_action(f['actor'],f['case'].pk,action,f['e']['support_transition'].pk,rev(f['case']))
 def test_actual_owner_and_review_authority_are_required_and_rechecked(self):
  f=self.f
  with self.assertRaises(PermissionDenied):d.review_flow(f['actor'],f['case'].pk,f['e']['support_review'].pk)
  ready(f);r=report(f);Grant.objects.filter(case=f['case'],user=f['reviewer'],action='support.review').update(active=False)
  with self.assertRaises(PermissionDenied):d.read_report(f['actor'],f['case'].pk,r.pk)
 def test_revoked_owner_and_cached_inactive_actor_block_actions(self):
  f=self.f;ready(f);Grant.objects.filter(case=f['case'],user=f['actor'],action='support.own').update(active=False)
  with self.assertRaises(ValidationError):act(f,'investigate')
  type(f['actor']).objects.filter(pk=f['actor'].pk).update(is_active=False)
  with self.assertRaises(PermissionDenied):capture(f,{'message_ref':'inactive'})
 def test_policy_successor_requires_new_flow_review_and_explicit_adoption(self):
  f=self.f;ready(f);r=report(f);flow=copy.deepcopy(f['v']['flow']);flow['migration_mode']='reviewed_legacy_adoption';policy(f,FLOW,flow)
  with self.assertRaises(ValidationError):act(f,'investigate')
  d.review_flow(f['reviewer'],f['case'].pk,f['e']['support_review'].pk)
  with self.assertRaises(ValidationError):act(f,'investigate')
  d.transition(f['actor'],f['case'].pk,'adopt_flow',f['actor'].pk,f['e']['support_migration'].pk,timezone.now().isoformat());act(f,'investigate')
  with self.assertRaises(ValidationError):d.read_report(f['actor'],f['case'].pk,r.pk)
 def test_legacy_projection_requires_explicit_migration_and_keeps_timestamps(self):
  f=self.f;old=SupportCase.objects.create(case=f['case'],channel='legacy',external_ref='legacy-1',first_response_at=f['t']);i=capture(f);d.link(f['actor'],f['case'].pk,i.pk,f['e']['support_triage'].pk);d.review_flow(f['reviewer'],f['case'].pk,f['e']['support_review'].pk)
  with self.assertRaises(ValidationError):d.start(f['actor'],f['case'].pk,f['actor'].pk,f['e']['support_start'].pk,timezone.now().isoformat())
  flow=copy.deepcopy(f['v']['flow']);flow['migration_mode']='reviewed_legacy_adoption';policy(f,FLOW,flow);d.review_flow(f['reviewer'],f['case'].pk,f['e']['support_review'].pk);w=d.start(f['actor'],f['case'].pk,f['actor'].pk,f['e']['support_migration'].pk,timezone.now().isoformat());self.assertEqual(w.payload['legacy_first_response_at'],f['t'].isoformat());self.assertEqual(d.metrics(f['case'])['finding'],'legacy_event_coverage_incomplete')
 def test_same_identity_merge_preserves_both_case_histories_and_rights(self):
  f=self.f;g=fixture('merge',people=[f['actor'],f['reviewer'],f['specialist']]);ready(f);ready(g);m=d.merge(f['actor'],f['case'].pk,g['case'].pk,f['e']['support_merge'].pk,timezone.now().isoformat());self.assertEqual(m.target_id,g['case'].pk);self.assertEqual(d.head(f['case']).state,'merged');self.assertEqual(d.head(g['case']).state,'received');self.assertEqual(SupportEvent.objects.count(),3)
  with self.assertRaises(ValidationError):act(f,'investigate')
 def test_b14_e01_unrelated_merge_and_inaccessible_target_rejected(self):
  f=self.f;g=fixture('unrelated',people=[f['actor'],f['reviewer'],f['specialist']]);g['v']['message']['transaction_ref']='DIFFERENT';ready(f);ready(g)
  with self.assertRaises(ValidationError):d.merge(f['actor'],f['case'].pk,g['case'].pk,f['e']['support_merge'].pk,timezone.now().isoformat())
  Grant.objects.filter(case=g['case'],user=f['actor'],action='support.merge').update(active=False)
  with self.assertRaises(PermissionDenied):d.merge(f['actor'],f['case'].pk,g['case'].pk,f['e']['support_merge'].pk,timezone.now().isoformat())
  self.assertEqual(SupportMerge.objects.count(),0)
 def test_wrong_case_evidence_and_current_result_supersession(self):
  f=self.f;g=fixture('foreign');ready(f);act(f,'investigate');p=act(f,'await_specialist')
  with self.assertRaises(ValidationError):d.specialist_result(f['specialist'],f['case'].pk,p.pk,g['e']['support_review'].pk)
  result(f,p);act(f,'resolve');r=report(f);result(f,p,'unknown')
  with self.assertRaises(ValidationError):d.read_report(f['actor'],f['case'].pk,r.pk)
 def test_no_financial_execution_from_specialist_text(self):
  f=self.f;ready(f);act(f,'investigate');p=act(f,'await_specialist')
  with self.assertRaises(ValidationError):result(f,p,kind='financial_corrective',request_id=999,verification_id=999)
  self.assertNotEqual(d.head(f['case']).state,'resolved')
 def test_policy_validators_reject_unsafe_flow_and_bad_oracles(self):
  f=self.f;flow=copy.deepcopy(f['v']['flow']);flow['edges'][2]['require_specialist_result']=False
  with self.assertRaises(ValidationError):policy(f,FLOW,flow)
  metrics=copy.deepcopy(f['v']['metrics']);metrics['oracles'][0]['expected']['first_response_seconds']='1'
  with self.assertRaises(ValidationError):policy(f,METRICS,metrics)
  auth=copy.deepcopy(f['v']['authority']);auth['assignments'][0]['user_id']=999999
  with self.assertRaises(ValidationError):policy(f,AUTH,auth)
 def test_append_only_postgresql_guards(self):
  f=self.f;ready(f);act(f,'investigate');p=act(f,'await_specialist');result(f,p);act(f,'resolve');report(f)
  for name in ['supportintake','supportlink','supportevent','supportresult','supportreport','supportreview']:
   with self.assertRaises(DatabaseError),transaction.atomic():
    with connection.cursor() as cur:cur.execute('DELETE FROM baas_'+name)
 def test_agent_ui_and_reviewed_report_are_scoped_no_store_and_typed(self):
  f=self.f;ready(f);r=report(f);agent=investigate(f['actor'],f['case'].pk);self.assertFalse(agent.result['closure_authorized']);self.assertFalse(agent.result['customer_text_read']);client=Client();client.force_login(f['actor']);url=f"/cases/{f['case'].pk}/support/";response=client.get(url);self.assertEqual(response.status_code,200);self.assertContains(response,'Customer support');self.assertEqual(response['Cache-Control'],'no-store');self.assertEqual(client.get(url+f'reports/{r.pk}/').status_code,200);self.assertEqual(client.get('/support/inbox/').status_code,200)
  count=SupportIntake.objects.count();response=client.post(url,{'action':'capture','revision':rev(f['case']),'evidence':f['e']['support_start'].pk,'grant_authority':'yes'});self.assertEqual(response.status_code,302);self.assertEqual(SupportIntake.objects.count(),count)

 def test_af13_exact_owner_package_and_revocation_hold_runtime_not_intake(self):
  from .support_helpers import owner_package
  from apps.documents import validation as av
  f=self.f;p=owner_package(f);ready(f);r=report(f);self.assertEqual(p.payload['level'],'definition');self.assertFalse(r.result['native_channel_verified']);av.review(f['reviewer'],f['case'].pk,p.pk,'acceptance','revoke','support-revoke',f['e']['policy_decision'].pk,'Revoke synthetic acceptance',rev(f['case']))
  with self.assertRaises(ValidationError):act(f,'investigate')
  self.assertTrue(capture(f,{'message_ref':'after-revoke'}).pk)
 def test_financial_specialist_requires_actual_corrective_delivery_and_verification(self):
  from django.conf import settings
  from apps.policy.services import register_reference
  from .helpers import activate
  from . import reconciliation_helpers as rh
  from apps.baas import reconciliation as recon
  f=self.f;a,c,specialist=f['actor'],f['case'],f['specialist'];r=register_reference(a,c.pk,'support-finance-role','schema:psl/role-assignment/v1',{'role':'Finance','user_id':a.pk},f['e']['policy_decision'].pk)
  from apps.policy.services import active_component
  refs=active_component('D05.role_principal_assignments',c).envelope['value'];activate(a,c,'D05.role_principal_assignments',refs+[r.ref],f['e']['policy_decision']);rules=json.loads((settings.BASE_DIR/'fixtures/baas-reconciliation.json').read_text(encoding='utf-8'));rules['commands']['recipient_id']=specialist.pk;rh.policy(a,c,recon.CONTRACT,rules['contract']);rh.policy(a,c,recon.COMMANDS,rules['commands']);batches={kind:rh.batch(a,c,kind) for kind in ['ledger','settlement','queue']};run=rh.run(a,c,batches);request=rh.request(a,c,run);delivery=rh.delivery(a,c,request);outcome=rh.outcome(specialist,c,delivery);verified=rh.verify(a,c,outcome)
  flow=copy.deepcopy(f['v']['flow'])
  for edge in flow['edges']:
   if edge['action']=='await_specialist':edge['specialist_kind']='financial_corrective'
  policy(f,FLOW,flow);f['v']['message'].update(transaction_ref='tx-1',customer_ref='customer-1');ready(f);act(f,'investigate');pending=act(f,'await_specialist')
  with self.assertRaises(ValidationError):result(f,pending,kind='backend_reference')
  with self.assertRaises(ValidationError):result(f,pending,kind='financial_corrective',request_id=request.pk)
  result(f,pending,kind='financial_corrective',request_id=request.pk,verification_id=verified.pk);act(f,'resolve');self.assertEqual(report(f).result['meaning'],'resolved')
 def test_specialist_kind_and_merge_states_are_typed_policy(self):
  f=self.f;ready(f);act(f,'investigate');p=act(f,'await_specialist')
  with self.assertRaises(ValidationError):result(f,p,kind='financial_corrective')
  flow=copy.deepcopy(f['v']['flow']);flow['merge_target_states']=['resolved']
  with self.assertRaises(ValidationError):policy(f,FLOW,flow)
 def test_successful_typed_ui_commands_do_not_activate_policy_or_forge_roles(self):
  from apps.policy.models import Configuration
  f=self.f;client=Client();client.force_login(f['actor']);url=f"/cases/{f['case'].pk}/support/";e=evidence(f,'support_intake',f['v']['message']);self.assertEqual(client.post(url,{'action':'capture','revision':rev(f['case']),'evidence':e.pk}).status_code,302);i=SupportIntake.objects.get();self.assertEqual(client.post(url,{'action':'link','revision':rev(f['case']),'intake':i.pk,'evidence':f['e']['support_triage'].pk}).status_code,302);client.force_login(f['reviewer']);self.assertEqual(client.post(url,{'action':'flow_review','revision':rev(f['case']),'evidence':f['e']['support_review'].pk,'verdict':'approve'}).status_code,302);client.force_login(f['actor']);self.assertEqual(client.post(url,{'action':'start','revision':rev(f['case']),'owner':f['actor'].pk,'evidence':f['e']['support_start'].pk,'occurred_at':f['t'].isoformat()}).status_code,302);self.assertTrue(d.head(f['case']));old=f['policies'][METRICS];self.assertEqual(client.post(url,{'action':'policy','revision':rev(f['case']),'component':METRICS,'content':json.dumps(f['v']['metrics']),'evidence':f['e']['policy_decision'].pk,'effective_from':timezone.now().isoformat()}).status_code,302);new=Configuration.objects.filter(case=f['case'],component=METRICS).order_by('-pk').first();self.assertNotEqual(old.pk,new.pk);self.assertEqual(new.states.latest('pk').state,'draft')
 def test_non_synthetic_flow_cannot_use_synthetic_definition_as_operational_acceptance(self):
  f=self.f;f['case'].synthetic=False;f['case'].save(update_fields=['synthetic'])
  with self.assertRaises(ValidationError):d.review_flow(f['reviewer'],f['case'].pk,f['e']['support_review'].pk)
 def test_merge_history_is_postgresql_immutable_and_preserves_target_access(self):
  f=self.f;g=fixture('merge-guard',people=[f['actor'],f['reviewer'],f['specialist']]);ready(f);ready(g);m=d.merge(f['actor'],f['case'].pk,g['case'].pk,f['e']['support_merge'].pk,timezone.now().isoformat())
  with self.assertRaises(DatabaseError),transaction.atomic():
   with connection.cursor() as cur:cur.execute('DELETE FROM baas_supportmerge WHERE id=%s',[m.pk])
  Grant.objects.filter(case=g['case'],user=f['actor'],action='support.read').update(active=False);client=Client();client.force_login(f['actor']);response=client.get(f"/cases/{f['case'].pk}/support/");self.assertNotContains(response,str(g['case'].pk))

 def test_reopened_case_can_recover_from_superseded_historical_specialist_result(self):
  f=self.f;ready(f);act(f,'investigate');p=act(f,'await_specialist');result(f,p);act(f,'resolve');old=report(f);result(f,p,'unknown')
  with self.assertRaises(ValidationError):d.read_report(f['actor'],f['case'].pk,old.pk)
  act(f,'reopen');self.assertTrue(report(f).result['reopened']);new=act(f,'await_specialist');result(f,new);act(f,'resolve');self.assertEqual(report(f).result['meaning'],'resolved')
 def test_source_policy_revocation_and_narrow_scope_hold_dependent_transitions(self):
  f=self.f;ready(f);v=copy.deepcopy(f['v']['intake']);v['channels']=['whatsapp'];policy(f,INTAKE,v)
  with self.assertRaises(ValidationError):act(f,'investigate')
  self.assertTrue(capture(f,{'channel':'whatsapp','message_ref':'fresh-allowed'}).pk)
 def test_strict_specialist_result_rejects_duplicate_json_authority_fields(self):
  f=self.f;ready(f);act(f,'investigate');p=act(f,'await_specialist');e=evidence(f,'support_specialist_result','{"status":"unknown","status":"resolved","kind":"backend_reference","reference":"R","corrective_request_id":null,"verification_id":null}')
  with self.assertRaises(ValidationError):d.specialist_result(f['specialist'],f['case'].pk,p.pk,e.pk)

 def test_missing_accountable_owner_is_a_typed_hold_without_state_change(self):
  f=self.f;ready(f);before=d.head(f['case']).pk
  with self.assertRaises(ValidationError):d.transition(f['actor'],f['case'].pk,'investigate',None,f['e']['support_transition'].pk,timezone.now().isoformat())
  self.assertEqual(d.head(f['case']).pk,before)

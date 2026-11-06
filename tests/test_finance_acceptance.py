import copy,json
from datetime import timedelta
from unittest.mock import patch
from django.test import TestCase
from django.core.exceptions import PermissionDenied,ValidationError
from django.db import transaction,connection,DatabaseError
from django.urls import reverse
from django.utils import timezone
from apps.identity.models import Grant
from apps.policy.services import transition
from apps.policy.ledger_validators import HANDOFF
from apps.finance import acceptance as d,ledger_agents as finance
from apps.documents import validation as af13
from apps.agents.models import AgentRun
from apps.core.evidence_access import public_evidence,public_timeline
from .finance_acceptance_helpers import fixture,draft,handoff,decide,validate,af13_reviews
from .ledger_helpers import policy,evidence
from .readiness_helpers import endpoint
from .helpers import rev

class FinanceAcceptanceTests(TestCase):
 @classmethod
 def setUpTestData(cls):cls.f=fixture()
 def test_full_receipt_validation_af13_reviews_and_independent_handoff_acceptance(self):
  f=self.f
  with endpoint():
   h=handoff(f);self.assertFalse(d.report(f['recipient'],f['case'].pk,h.pk)['scoped_acceptance_current'])
   with self.assertRaises(ValidationError):decide(f,'validate')
   decide(f,'receive')
   with self.assertRaises(ValidationError):decide(f,'accept')
   decide(f,'validate');af13_reviews(f);self.assertFalse(d.report(f['acceptor'],f['case'].pk,h.pk)['scoped_acceptance_current']);decision=decide(f,'accept');value=d.report(f['acceptor'],f['case'].pk,h.pk);self.assertTrue(value['scoped_acceptance_current']);self.assertFalse(value['posted']);self.assertFalse(value['whole_product_accepted']);self.assertEqual(decision.snapshot['af13_acceptance'],f['af13_reviews'][-1].pk)
   self.assertTrue(af13.acceptance_report(f['acceptor'],f['case'].pk,f['af13_reviews'][-1].pk)['requested_record_is_current']);self.assertNotIn('body',json.dumps(h.snapshot));self.assertEqual(len(d.Handoff.objects.all()),1)
 def test_missing_routing_holds_only_handoff_not_original_finance_or_af13(self):
  f=self.f;transition(f['actor'],f['handoff_policy'].pk,'revoked')
  with endpoint():
   draft(f)
   with self.assertRaises(ValidationError):handoff(f)
   self.assertTrue(finance.approved_evidence(f['actor'],f['case'].pk,f['draft'].pk));self.assertIsNone(d.review_pins(f['package'],f['recipient']))
   af13_reviews(f);self.assertTrue(af13.approved_review(f['package'],'acceptance'))
 def test_typed_routing_inventory_principals_grants_and_independence(self):
  f=self.f
  for changes in [{'package_ids':[999999]},{'acceptor_id':f['recipient'].pk},{'independent_acceptance':False},{'freshness_seconds':0}]:
   with self.assertRaises(ValidationError),transaction.atomic():policy(f,HANDOFF,dict(f['routing'],**changes))
  Grant.objects.filter(case=f['case'],user=f['acceptor'],action='ledger.private.read').update(active=False)
  with self.assertRaises(ValidationError),transaction.atomic():policy(f,HANDOFF,f['routing'])
 def test_receipt_is_not_validation_and_native_binding_stales_prior_af13_reviews(self):
  f=self.f;af13_reviews(f)
  with endpoint():
   h=handoff(f);decide(f,'receive')
   with self.assertRaises(ValidationError):af13.approved_review(f['package'],'meaning')
   with self.assertRaises(ValidationError):af13.review(f['recipient'],f['case'].pk,f['package'].pk,'meaning','approve','premature',f['e'].pk,'Receipt does not validate',None)
   self.assertFalse(d.report(f['recipient'],f['case'].pk,h.pk)['states']['validate']['current'])
 def test_wrong_principals_cannot_receive_validate_or_accept(self):
  f=self.f
  with endpoint():
   h=handoff(f)
   for a,phase in [(f['actor'],'receive'),(f['acceptor'],'validate'),(f['recipient'],'accept')]:
    with self.assertRaises(PermissionDenied):d.decide(a,f['case'].pk,h.pk,phase,'confirm','wrong-'+phase,'Wrong human')
 def test_receive_withdrawal_invalidates_validation_af13_and_acceptance_without_erasure(self):
  f=self.f
  with endpoint():
   validate(f);af13_reviews(f);accepted=decide(f,'accept');decide(f,'receive','withdraw');value=d.report(f['recipient'],f['case'].pk,f['handoff'].pk);self.assertFalse(value['scoped_acceptance_current']);self.assertEqual(d.Decision.objects.get(pk=accepted.pk).verdict,'confirm')
   with self.assertRaises(ValidationError):af13.approved_review(f['package'],'acceptance')
 def test_af13_acceptance_revocation_invalidates_handoff_current_use(self):
  f=self.f
  with endpoint():
   validate(f);af13_reviews(f);decide(f,'accept');af13.review(f['acceptor'],f['case'].pk,f['package'].pk,'acceptance','revoke','revoke',f['e'].pk,'Explicit human revocation',None);self.assertFalse(d.report(f['recipient'],f['case'].pk,f['handoff'].pk)['scoped_acceptance_current'])
 def test_source_revision_requires_explicit_single_handoff_successor_and_new_decisions(self):
  f=self.f
  with endpoint():
   h=handoff(f);new=finance.revise(f['actor'],f['case'].pk,f['draft'].pk,'Explicit human source revision');finance.review(f['reviewer'],f['case'].pk,new.pk,'approve');self.assertFalse(d.report(f['recipient'],f['case'].pk,h.pk)['states']['receive']['current'])
   with self.assertRaises(ValidationError):d.prepare(f['actor'],f['case'].pk,new.pk,f['package'].pk,h.reference)
   successor=d.prepare(f['actor'],f['case'].pk,new.pk,f['package'].pk,h.reference,h.pk);self.assertEqual(successor.parent_id,h.pk);self.assertEqual(successor.version,2)
   self.assertEqual(d.prepare(f['actor'],f['case'].pk,new.pk,f['package'].pk,h.reference,h.pk).pk,successor.pk)
 def test_policy_replacement_revocation_and_ttl_hold_current_not_history(self):
  f=self.f;rules=dict(f['routing'],freshness_seconds=600);policy(f,HANDOFF,rules)
  with endpoint():
   validate(f);af13_reviews(f);decide(f,'accept');h=f['handoff']
   with patch('apps.finance.acceptance.timezone.now',return_value=h.created_at+timedelta(seconds=rules['freshness_seconds']+1)):
    # Upstream source/result/draft windows are still valid: only this handoff expires.
    self.assertTrue(finance.approved_evidence(f['actor'],f['case'].pk,f['draft'].pk))
    self.assertFalse(d.report(f['recipient'],f['case'].pk,h.pk)['scoped_acceptance_current'])
   self.assertTrue(d.report(f['recipient'],f['case'].pk,h.pk)['scoped_acceptance_current']);policy(f,HANDOFF,rules);self.assertFalse(d.report(f['recipient'],f['case'].pk,h.pk)['scoped_acceptance_current']);self.assertEqual(d.Handoff.objects.count(),1)
 def test_private_revocation_denies_cached_handoff_package_form_report_and_ui(self):
  f=self.f
  with endpoint():validate(f);af13_reviews(f);decide(f,'accept')
  Grant.objects.filter(case=f['case'],user=f['recipient'],action='ledger.private.read').update(active=False)
  with self.assertRaises(PermissionDenied):d.report(f['recipient'],f['case'].pk,f['handoff'].pk)
  with self.assertRaises(PermissionDenied):af13.acceptance_report(f['recipient'],f['case'].pk,f['af13_reviews'][-1].pk)
  self.client.force_login(f['recipient']);self.assertEqual(self.client.get(reverse('finance_acceptance',args=[f['case'].pk])).status_code,403);response=self.client.get(reverse('validation',args=[f['case'].pk]));self.assertEqual(response.status_code,200);self.assertNotContains(response,'Separate explicit synthetic AF13')
 def test_private_agent_is_bounded_no_decisions_or_generic_output_and_generic_agent_omits_binding(self):
  from apps.agents.finance_acceptance import investigate
  from apps.agents.validation import investigate as generic
  f=self.f
  with endpoint():
   validate(f);before=d.Decision.objects.count();count=AgentRun.objects.count();value=investigate(f['recipient'],f['case'].pk);self.assertEqual(len(value['findings']),1);self.assertEqual(AgentRun.objects.count(),count);self.assertEqual(d.Decision.objects.count(),before);r=generic(f['actor'],f['case'].pk,None);self.assertEqual(r.result['packages'],[])
   self.assertFalse(public_timeline(f['case']).filter(action__startswith='agent.data.finance_').exists())
 def test_real_http_prepare_receive_validate_af13_accept_and_export_no_store(self):
  f=self.f
  with endpoint():
   draft(f);self.client.force_login(f['actor']);url=reverse('finance_acceptance',args=[f['case'].pk]);self.assertContains(self.client.get(url),'Finance recipient validation and acceptance');response=self.client.post(url,{'action':'prepare','revision':rev(f['case']),'draft':f['draft'].pk,'package':f['package'].pk,'reference':'http'});self.assertEqual(response.status_code,302);f['handoff']=d.Handoff.objects.get();self.client.force_login(f['recipient'])
   for phase in ['receive','validate']:self.assertEqual(self.client.post(url,{'action':phase,'revision':rev(f['case']),'handoff':f['handoff'].pk,'verdict':'confirm','operation_key':phase,'reason':'Explicit HTTP human decision'}).status_code,302)
   af13_reviews(f);self.client.force_login(f['acceptor']);self.client.post(url,{'action':'accept','revision':rev(f['case']),'handoff':f['handoff'].pk,'verdict':'confirm','operation_key':'accept','reason':'Exact AF13 approved scope'});response=self.client.get(reverse('finance_acceptance_report',args=[f['case'].pk,f['handoff'].pk]));self.assertEqual(response['Cache-Control'],'no-store');self.assertTrue(response.json()['scoped_acceptance_current'])
 def test_intent_idempotence_sql_immutability_and_wrong_actor_lineage(self):
  f=self.f
  with endpoint():
   h=handoff(f);self.assertEqual(handoff(f).pk,h.pk);r=decide(f,'receive');self.assertEqual(decide(f,'receive').pk,r.pk)
   with self.assertRaises(ValidationError):d.decide(f['recipient'],f['case'].pk,h.pk,'receive','confirm','receive-confirm','Changed reason')
   for table,pk in [('finance_financehandoff',h.pk),('finance_financehandoffdecision',r.pk)]:
    with self.assertRaises(DatabaseError),transaction.atomic(),connection.cursor() as cur:cur.execute('UPDATE '+table+' SET created_at=now() WHERE id=%s',[pk])
   with self.assertRaises(DatabaseError),transaction.atomic():d.Decision.objects.create(handoff=h,operation_key='forged',phase='accept',verdict='confirm',reason='Forged',snapshot={'handoff':h.pk,'sha256':h.sha256},authority={},actor=f['recipient'])
 def test_historical_foreign_source_grant_loss_denies_handoff_and_acceptance_export(self):
  from .ledger_resolution_helpers import second_case,propose,confirm,current
  from .ledger_helpers import capture,verify
  from apps.core.management.commands.seed_demo import ACTIONS
  f=self.f;g=second_case(f);g['case'].tenant=f['case'].tenant;g['case'].save(update_fields=['tenant']);Grant.objects.bulk_create([Grant(case=g['case'],user=f['acceptor'],action=k) for k in ACTIONS]);w=capture(g);verify(g,w);verify(f,f['lineage']);confirm(f,propose(f,f['lineage'],[w]));current(f,f['lineage'])
  with endpoint():
   validate(f);af13_reviews(f);decide(f,'accept');Grant.objects.filter(case=g['case'],user=f['recipient'],action='ledger.private.read').update(active=False)
   for call in [lambda:d.report(f['recipient'],f['case'].pk,f['handoff'].pk),lambda:af13.acceptance_report(f['recipient'],f['case'].pk,f['af13_reviews'][-1].pk)]:
    with self.assertRaises(PermissionDenied):call()
   self.assertFalse(d.visible_packages(f['recipient'],f['case']).exists())
 def test_package_revision_requires_routing_and_explicit_successor_not_automatic_retarget(self):
  f=self.f
  with endpoint():
   h=handoff(f);p=af13.prepare_package(f['actor'],f['case'].pk,f['package'].reference,dict(f['package'].payload,build_ref='fixture-v2'),f['e'].pk,None)
   self.assertFalse(d.report(f['recipient'],f['case'].pk,h.pk)['states']['receive']['current'])
   with self.assertRaises(ValidationError):d.prepare(f['actor'],f['case'].pk,f['draft'].pk,p.pk,h.reference,h.pk)
   policy(f,HANDOFF,dict(f['routing'],package_ids=[p.pk]));successor=d.prepare(f['actor'],f['case'].pk,f['draft'].pk,p.pk,h.reference,h.pk);self.assertEqual(successor.package_id,p.pk)
   with self.assertRaises(ValidationError):d.review_pins(f['package'],f['recipient'])
 def test_provider_binding_teardown_and_result_review_withdrawal_hold_current_acceptance(self):
  from apps.agents import boundary as gateway
  f=self.f
  with endpoint():
   validate(f);af13_reviews(f);decide(f,'accept');self.assertTrue(d.report(f['recipient'],f['case'].pk,f['handoff'].pk)['scoped_acceptance_current']);gateway.review_result(f['reviewer'],f['case'].pk,f['receipt'].pk,'withdraw');self.assertFalse(d.report(f['recipient'],f['case'].pk,f['handoff'].pk)['scoped_acceptance_current'])
  value=d.report(f['recipient'],f['case'].pk,f['handoff'].pk);self.assertFalse(value['scoped_acceptance_current']);self.assertEqual(value['body'],f['draft'].body)
 def test_operational_level_cannot_be_accepted_from_private_draft_or_receipt(self):
  f=self.f
  with endpoint():
   p=af13.prepare_package(f['actor'],f['case'].pk,'operational-scope',dict(f['package'].payload,level='operational'),f['e'].pk,None);f['package']=p;policy(f,HANDOFF,dict(f['routing'],package_ids=[p.pk]));validate(f)
   for kind in ['meaning','expectations']:af13.review(f['recipient'],f['case'].pk,p.pk,kind,'approve',kind,f['e'].pk,'Exact supplied scope',None)
   with self.assertRaises(ValidationError):af13.review(f['acceptor'],f['case'].pk,p.pk,'acceptance','approve','operational',f['e'].pk,'Cannot infer operational acceptance',None)
   with self.assertRaises(ValidationError):decide(f,'accept')
 def test_routing_revocation_and_recipient_role_change_invalidate_new_request(self):
  from .validation_helpers import policy as validation_policy
  from apps.policy.validation_validators import OWNER
  f=self.f
  with endpoint():
   validate(f);af13_reviews(f);decide(f,'accept');self.assertTrue(d.report(f['recipient'],f['case'].pk,f['handoff'].pk)['scoped_acceptance_current']);rules=copy.deepcopy(f['owner_rules']);rules['assignments'][0]['purposes']=['meaning'];validation_policy(f['actor'],f['case'],OWNER,rules,f['e']);self.assertFalse(d.report(f['recipient'],f['case'].pk,f['handoff'].pk)['scoped_acceptance_current'])
   transition(f['actor'],f['handoff_policy'].pk,'revoked');self.assertFalse(d.report(f['recipient'],f['case'].pk,f['handoff'].pk)['states']['receive']['current'])
 def test_routing_reassignment_cannot_grant_new_people_old_record_decision_rights(self):
  from .validation_helpers import policy as validation_policy
  from apps.policy.validation_validators import OWNER
  f=self.f
  with endpoint():
   h=handoff(f);rules=copy.deepcopy(f['owner_rules'])
   for row in rules['assignments']:row['purposes']=['meaning','expectations','acceptance']
   validation_policy(f['actor'],f['case'],OWNER,rules,f['e']);policy(f,HANDOFF,dict(f['routing'],recipient_id=f['acceptor'].pk,acceptor_id=f['recipient'].pk))
   for actor,phase in [(f['acceptor'],'receive'),(f['recipient'],'accept')]:
    with self.assertRaises(PermissionDenied):d.decide(actor,f['case'].pk,h.pk,phase,'return','retarget-'+phase,'New route cannot alter the old addressed record')
   self.assertEqual(d.Decision.objects.count(),0)
   self.client.force_login(f['acceptor']);response=self.client.post(reverse('finance_acceptance',args=[f['case'].pk]),{'action':'receive','revision':rev(f['case']),'handoff':h.pk,'verdict':'return','operation_key':'http-retarget','reason':'Wrong record addressee'});self.assertEqual(response.status_code,403)

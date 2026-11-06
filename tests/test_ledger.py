import copy,json
from datetime import timedelta
from django.test import TestCase,Client
from django.core.exceptions import ValidationError,PermissionDenied
from django.utils import timezone
from django.db import connection,transaction,DatabaseError
from apps.finance import ledger
from apps.finance.models import LedgerLineage,LedgerCheck,LedgerDecision
from apps.policy.ledger_validators import RULES,AUTH
from apps.policy.services import transition
from apps.identity.models import Grant
from apps.agents.ledger import investigate
from .ledger_helpers import fixture,capture,verify,review,evidence,policy
class LedgerTests(TestCase):
 def setUp(self):self.f=fixture()
 def test_f01_n01_tx001_qb101_lineage_no_second_post(self):
  f=self.f;w=capture(f);x=verify(f,w);review(f,x);r=ledger.report(f['reviewer'],f['case'].pk,w.pk)
  self.assertEqual(connection.vendor,'postgresql');self.assertEqual(r['source']['source_reference'],'TX-001');self.assertEqual(r['incumbent']['target_reference'],'QB-101');self.assertFalse(r['posting_performed']);self.assertFalse(r['native_authenticity_verified'])
 def test_f01_e01_duplicate_source_invalidates_previous_review(self):
  f=self.f;w=capture(f);x=verify(f,w);review(f,x);duplicate=capture(f);self.assertEqual(verify(f,duplicate).status,'held')
  with self.assertRaises(ValidationError):ledger.report(f['actor'],f['case'].pk,w.pk)
 def test_unknown_notfound_multiple_are_not_retry_authority(self):
  f=self.f;w=capture(f)
  for state in ['unknown','not_found','multiple']:
   x=verify(f,w,{'state':state});self.assertEqual(x.status,'held')
   with self.assertRaises(ValidationError):review(f,x)
 def test_uncertain_then_corrected_reference_needs_fresh_check_review(self):
  f=self.f;p=copy.deepcopy(f['v']['source']);p.update(target_reference=None,outcome='uncertain');w=capture(f,p);self.assertEqual(verify(f,w,{'state':'unknown','target_reference':None}).status,'held');p.update(target_reference='QB-101',outcome='reported_posted');s=capture(f,p,w.pk);x=verify(f,s)
  with self.assertRaises(ValidationError):ledger.report(f['actor'],f['case'].pk,s.pk)
  review(f,x);self.assertEqual(ledger.report(f['actor'],f['case'].pk,s.pk)['lineage_id'],s.pk);self.assertEqual(LedgerLineage.objects.count(),2)
 def test_corrected_posted_reference_retains_old_history(self):
  f=self.f;w=capture(f);x=verify(f,w);review(f,x);p=copy.deepcopy(w.payload);p['target_reference']='QB-102';s=capture(f,p,w.pk)
  with self.assertRaises(ValidationError):ledger.report(f['actor'],f['case'].pk,w.pk)
  review(f,verify(f,s));self.assertEqual(ledger.report(f['actor'],f['case'].pk,s.pk)['incumbent']['target_reference'],'QB-102');self.assertEqual(w.payload['target_reference'],'QB-101')
 def test_mismatched_response_and_extra_authority_are_rejected(self):
  f=self.f;w=capture(f)
  for changes in [{'realm':'other'},{'source_reference':'other'},{'treatment_evidence_id':999},{'transaction_date':'2026-10-02'},{'post_again':True}]:
   with self.assertRaises(ValidationError):verify(f,w,changes)
  self.assertEqual(LedgerCheck.objects.count(),0)
 def test_target_mismatch_and_missing_version_are_held(self):
  f=self.f;w=capture(f)
  for changes in [{'target_reference':'other'},{'incumbent_version':None}]:self.assertEqual(verify(f,w,changes).status,'held')
 def test_future_and_expired_observations_rejected(self):
  f=self.f;w=capture(f)
  for at in [timezone.now()+timedelta(hours=1),timezone.now()-timedelta(hours=2)]:
   with self.assertRaises(ValidationError):verify(f,w,{'observed_at':at.isoformat()})
 def test_missing_policy_holds_verification_but_source_capture_works(self):
  f=self.f;transition(f['actor'],f['rule_policy'].pk,'revoked');w=capture(f)
  with self.assertRaises(ValidationError):verify(f,w)
 def test_policy_successor_invalidates_existing_decision(self):
  f=self.f;w=capture(f);x=verify(f,w);review(f,x);policy(f,RULES,f['v']['rules'])
  with self.assertRaises(ValidationError):ledger.report(f['actor'],f['case'].pk,w.pk)
 def test_review_is_independent_and_rechecked_on_read(self):
  f=self.f;w=capture(f);x=verify(f,w)
  with self.assertRaises(PermissionDenied):ledger.review(f['actor'],f['case'].pk,x.pk,f['e'].pk)
  review(f,x);Grant.objects.filter(case=f['case'],user=f['reviewer'],action='ledger.review').update(active=False)
  with self.assertRaises(PermissionDenied):ledger.report(f['actor'],f['case'].pk,w.pk)
 def test_inactive_cached_actor_and_rejected_decision(self):
  f=self.f;w=capture(f);x=verify(f,w);review(f,x);review(f,x,'reject')
  with self.assertRaises(ValidationError):ledger.report(f['actor'],f['case'].pk,w.pk)
  type(f['actor']).objects.filter(pk=f['actor'].pk).update(is_active=False)
  with self.assertRaises(PermissionDenied):capture(f)
 def test_same_target_different_source_held(self):
  f=self.f;w=capture(f);p=copy.deepcopy(w.payload);p['source_reference']='TX-002';s=capture(f,p);self.assertEqual(verify(f,w).status,'held');self.assertEqual(verify(f,s).status,'held')
 def test_cross_case_identity_and_evidence_are_scoped(self):
  from .helpers import setup_case
  f=self.f;w=capture(f);a,c=setup_case(username='other-case');e=__import__('apps.core.services',fromlist=['add_evidence']).add_evidence(a,c.pk,'ledger_source',json.dumps(w.payload),'synthetic')
  with self.assertRaises(ValidationError):ledger.capture(a,c.pk,e.pk,w.pk)
  with self.assertRaises(ValidationError):ledger.verify(a,c.pk,w.pk,e.pk)
 def test_strict_source_json_and_scoped_provenance(self):
  f=self.f
  for body in [json.dumps(f['v']['source'])[:-1]+',"realm":"evil"}',json.dumps(dict(f['v']['source'],provenance=[{'kind':'finance_mapping','id':999999}]))]:
   e=evidence(f,'ledger_source',body)
   with self.assertRaises(ValidationError):ledger.capture(f['actor'],f['case'].pk,e.pk)
 def test_append_only_postgresql_guards(self):
  f=self.f;w=capture(f);x=verify(f,w);r=review(f,x)
  for table,pk in [('ledgerlineage',w.pk),('ledgercheck',x.pk),('ledgerdecision',r.pk)]:
   with self.assertRaises(DatabaseError),transaction.atomic():
    with connection.cursor() as cur:cur.execute('DELETE FROM finance_'+table+' WHERE id=%s',[pk])
 def test_agent_and_ui_are_scoped_typed_and_no_store(self):
  f=self.f;w=capture(f);x=verify(f,w);review(f,x);a=investigate(f['actor'],f['case'].pk);self.assertFalse(a.result['posting_performed']);self.assertEqual(a.process_id,'F01');client=Client();client.force_login(f['actor']);url=f"/cases/{f['case'].pk}/finance/ledger/";r=client.get(url);self.assertEqual(r.status_code,200);self.assertContains(r,'TX-001');self.assertContains(r,'QB-101');self.assertEqual(r['Cache-Control'],'no-store');r=client.get(url+str(w.pk)+'/report/');self.assertEqual(r.status_code,200)
  before=LedgerLineage.objects.count();r=client.post(url,{'action':'capture','revision':f['case'].revision,'evidence':w.evidence_id,'predecessor':'','grant_authority':'yes'});self.assertEqual(r.status_code,302);self.assertEqual(LedgerLineage.objects.count(),before)
 def test_policy_schema_and_actual_principal_validation(self):
  f=self.f
  for k,v in [(RULES,dict(f['v']['rules'],mode='post_and_retry')),(AUTH,{'independent_reviewer':True,'user_ids':[999999]})]:
   with self.assertRaises(ValidationError):policy(f,k,v)

 def test_same_identity_cross_case_never_grants_a_second_verified_route(self):
  f=self.f;w=capture(f);x=verify(f,w);review(f,x);g=fixture('second-preparer','second-reviewer');other=capture(g)
  self.assertEqual(other.identity,w.identity);self.assertEqual(verify(g,other).status,'held')
  with self.assertRaises(ValidationError):ledger.report(f['actor'],f['case'].pk,w.pk)
 def test_typed_ui_capture_verify_review_and_policy_draft(self):
  from .helpers import rev
  f=self.f;client=Client();client.force_login(f['actor']);url=f"/cases/{f['case'].pk}/finance/ledger/";e=evidence(f,'ledger_source',f['v']['source']);r=client.post(url,{'action':'capture','revision':rev(f['case']),'evidence':e.pk,'predecessor':''});self.assertEqual(r.status_code,302);w=LedgerLineage.objects.get();verify(f,w);x=w.checks.get();client.force_login(f['reviewer']);r=client.post(url,{'action':'review','revision':rev(f['case']),'verification':x.pk,'evidence':f['e'].pk,'verdict':'approve'});self.assertEqual(r.status_code,302);self.assertTrue(x.decisions.exists());client.force_login(f['actor']);r=client.post(url,{'action':'policy','revision':rev(f['case']),'component':RULES,'content':json.dumps(f['v']['rules']),'evidence':f['e'].pk,'effective_from':timezone.now().isoformat()});self.assertEqual(r.status_code,302)
 def test_mapping_and_ppe_references_are_exact_connected_records(self):
  from .ppe_helpers import fixture as ppe_fixture
  g=ppe_fixture('connected-preparer','connected-reviewer','connected-reader');f=self.f
  # References from another case cannot be laundered through source text.
  p=copy.deepcopy(f['v']['source']);p['provenance']=[{'kind':'finance_mapping','id':g['parent'].pk},{'kind':'ppe_register','id':g['register'].pk}]
  with self.assertRaises(ValidationError):capture(f,p)
  # Use existing actual service-produced mapping/register in its own case.
  e=__import__('apps.core.services',fromlist=['add_evidence']).add_evidence(g['actor'],g['case'].pk,'ledger_source',json.dumps(dict(p,treatment_evidence_id=g['e']['policy_decision'].pk,posting_evidence_id=g['e']['policy_decision'].pk)),'synthetic:connected')
  w=ledger.capture(g['actor'],g['case'].pk,e.pk);self.assertEqual(w.payload['provenance'][0]['id'],g['parent'].pk);self.assertEqual(w.payload['provenance'][1]['id'],g['register'].pk)

 def test_configured_incumbent_user_and_current_capture_rights(self):
  f=self.f;p=copy.deepcopy(f['v']['source']);p['incumbent_user_reference']='unapproved-user';w=capture(f,p)
  with self.assertRaises(ValidationError):verify(f,w)
  w=capture(f,dict(f['v']['source'],source_reference='TX-NEW',target_reference='QB-NEW'));x=verify(f,w);review(f,x);Grant.objects.filter(case=f['case'],user=f['actor'],action='ledger.capture').update(active=False)
  with self.assertRaises(PermissionDenied):ledger.report(f['reviewer'],f['case'].pk,w.pk)
 def test_strict_dates_and_foreign_read_access(self):
  f=self.f;p=copy.deepcopy(f['v']['source']);p['transaction_date']='20261001'
  with self.assertRaises(ValidationError):capture(f,p)
  w=capture(f);x=verify(f,w);review(f,x);Grant.objects.filter(case=f['case'],user=f['reviewer'],action='ledger.read').update(active=False);client=Client();client.force_login(f['reviewer']);self.assertEqual(client.get(f"/cases/{f['case'].pk}/finance/ledger/{w.pk}/report/").status_code,403)

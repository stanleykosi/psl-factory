from copy import deepcopy
from datetime import timedelta
from unittest.mock import patch
from django.test import TestCase
from django.utils import timezone
from django.db import transaction,connection,DatabaseError
from django.core.exceptions import ValidationError,PermissionDenied
from django.urls import reverse
from apps.finance import ledger,ledger_resolution as d
from apps.policy.ledger_validators import RESOLUTION,RULES
from apps.policy.services import transition
from apps.identity.models import Grant
from apps.core.evidence_access import public_evidence,public_timeline
from .ledger_resolution_helpers import fixture,aliases,propose,confirm,fresh,current,second_case
from .ledger_helpers import evidence,policy,capture,verify,review
from .helpers import rev

class LedgerResolutionTests(TestCase):
 @classmethod
 def setUpTestData(cls):cls.f=fixture()
 def test_duplicate_alias_resolution_requires_fresh_post_decision_read_and_original_finance_review(self):
  f=self.f;a,b=aliases(f);old=a.checks.latest('pk');r=propose(f,a,[b]);confirm(f,r)
  with self.assertRaises(ValidationError):review(f,old)
  report=current(f,a);self.assertEqual(report['source']['source_reference'],'TX-001');self.assertEqual(report['incumbent']['target_reference'],'QB-101');self.assertFalse(report['posting_performed']);self.assertFalse(report['native_authenticity_verified'])
  with self.assertRaises(ValidationError):ledger.report(f['actor'],f['case'].pk,b.pk)
  self.assertEqual(ledger.LedgerLineage.objects.count(),2)
 def test_corrected_reference_uses_exact_new_incumbent_evidence_and_retains_prior_history(self):
  f=self.f;old=capture(f);verify(f,old);value=dict(old.payload,target_reference='QB-102');new=capture(f,value,old.pk)
  self.assertEqual(fresh(f,new).status,'held');verify(f,old,{'target_reference':'QB-102'})
  r=propose(f,new,[old],mode='reference_correction');confirm(f,r);result=current(f,new);self.assertEqual(result['incumbent']['target_reference'],'QB-102');old.refresh_from_db();self.assertEqual(old.payload['target_reference'],'QB-101');self.assertEqual(new.predecessor_id,old.pk)
 def test_freed_incorrect_target_can_be_claimed_by_an_independent_source_only_after_exact_resolution(self):
  f=self.f;old=capture(f);new=capture(f,dict(old.payload,target_reference='QB-102'),old.pk);other=capture(f,dict(old.payload,source_reference='TX-002'));verify(f,old,{'target_reference':'QB-102'});verify(f,new);verify(f,other)
  r=propose(f,new,[old],[old,new,other],mode='reference_correction');confirm(f,r);self.assertEqual(current(f,new)['incumbent']['target_reference'],'QB-102');self.assertEqual(current(f,other)['incumbent']['target_reference'],'QB-101')
 def test_unknown_multiple_notfound_or_unversioned_reads_cannot_be_adjudicated(self):
  f=self.f;a,b=aliases(f)
  for changes in [{'state':'unknown'},{'state':'not_found'},{'state':'multiple'},{'incumbent_version':None}]:
   verify(f,b,changes)
   with self.assertRaises(ValidationError):propose(f,a,[b])
  self.assertFalse(d.Resolution.objects.exists())
 def test_missing_policy_keeps_normal_capture_verify_and_independent_original_review_working(self):
  f=fixture('resolution-missing',False);a=capture(f);x=verify(f,a);review(f,x);self.assertFalse(ledger.report(f['actor'],f['case'].pk,a.pk)['posting_performed']);b=capture(f);verify(f,b)
  with self.assertRaises(ValidationError):propose(f,a,[b])
 def test_revocation_cannot_restore_legacy_correction_bypass(self):
  f=self.f;transition(f['actor'],f['resolution_policy'].pk,'revoked');a=capture(f);new=capture(f,dict(a.payload,target_reference='QB-102'),a.pk);self.assertEqual(verify(f,new).status,'held')
  with self.assertRaises(ValidationError):review(f,new.checks.latest('pk'))
 def test_typed_policy_unknowns_real_roles_permissions_and_mandatory_independence(self):
  f=self.f
  for change in [{'proposer_id':None},{'reviewer_id':f['actor'].pk},{'independent_review':False},{'allowed_modes':['post_again']},{'posting_permitted':True},{'max_members':1},{'decision_ttl_seconds':0},{'post_decision_verification':False}]:
   with self.assertRaises(ValidationError),transaction.atomic():policy(f,RESOLUTION,dict(f['conflicts'],**change))
  Grant.objects.filter(case=f['case'],user=f['reviewer'],action='ledger.resolve_review').update(active=False)
  with self.assertRaises(ValidationError),transaction.atomic():policy(f,RESOLUTION,f['conflicts'])
 def test_self_review_and_unconfigured_actor_cannot_confirm(self):
  f=self.f;a,b=aliases(f);r=propose(f,a,[b])
  with self.assertRaises(PermissionDenied):d.review(f['actor'],f['case'].pk,r.pk,'confirm',f['resolution_review_evidence'].pk)
  self.assertFalse(d.Review.objects.exists())
 def test_exact_complete_population_and_no_different_transaction_retirement(self):
  f=self.f;a,b=aliases(f);other=capture(f,dict(a.payload,source_reference='TX-002'));verify(f,other)
  with self.assertRaises(ValidationError):propose(f,a,[b])
  with self.assertRaises(ValidationError):propose(f,a,[other],[a,b,other])
 def test_ambiguous_target_or_treatment_cannot_be_waived(self):
  f=self.f;a,b=aliases(f);verify(f,b,{'incumbent_version':'another-version'})
  with self.assertRaises(ValidationError):propose(f,a,[b])
  verify(f,b);other=capture(f,dict(a.payload,treatment_evidence_id=evidence(f,'policy_decision','different economic treatment').pk));policy(f,RULES,dict(f['v']['rules'],treatment_evidence_ids=[f['e'].pk,other.payload['treatment_evidence_id']]));verify(f,a);verify(f,b);verify(f,other)
  with self.assertRaises(ValidationError):propose(f,a,[b,other])
 def test_pending_overlap_withdrawal_and_return_never_fall_back_to_old_disposition(self):
  f=self.f;a,b=aliases(f);r=propose(f,a,[b]);confirm(f,r);current(f,a);new=propose(f,a,[b],reference='successor',predecessor=None)
  with self.assertRaises(ValidationError):ledger.report(f['actor'],f['case'].pk,a.pk)
  confirm(f,new,'return')
  with self.assertRaises(ValidationError):ledger.report(f['actor'],f['case'].pk,a.pk)
  with self.assertRaises(ValidationError):confirm(f,r)
 def test_withdrawal_stales_existing_report_and_fresh_check(self):
  f=self.f;a,b=aliases(f);r=propose(f,a,[b]);confirm(f,r);current(f,a);confirm(f,r,'withdraw')
  with self.assertRaises(ValidationError):ledger.report(f['actor'],f['case'].pk,a.pk)
  self.assertTrue(ledger.LedgerDecision.objects.filter(verdict='approve').exists())
 def test_population_new_duplicate_and_adverse_later_read_require_new_decision(self):
  f=self.f;a,b=aliases(f);r=propose(f,a,[b]);confirm(f,r);current(f,a);verify(f,a,{'state':'unknown'})
  with self.assertRaises(ValidationError):ledger.report(f['actor'],f['case'].pk,a.pk)
  fresh(f,a);c=capture(f)
  with self.assertRaises(ValidationError):d.accepted(r)
 def test_old_observation_reuploaded_after_review_does_not_become_fresh(self):
  f=self.f;a,b=aliases(f);at=a.checks.latest('pk').payload['observed_at'];r=propose(f,a,[b]);confirm(f,r);self.assertEqual(verify(f,a,{'observed_at':at}).status,'held')
 def test_policy_role_grant_and_age_changes_hold_current_use_without_history_mutation(self):
  f=self.f;a,b=aliases(f);r=propose(f,a,[b]);confirm(f,r);current(f,a)
  with patch('apps.finance.ledger_resolution.timezone.now',return_value=timezone.now()+timedelta(hours=2)):
   with self.assertRaises(ValidationError):d.accepted(r)
  Grant.objects.filter(case=f['case'],user=f['reviewer'],action='ledger.resolve_review').update(active=False)
  with self.assertRaises((ValidationError,PermissionDenied)):ledger.report(f['actor'],f['case'].pk,a.pk)
  self.assertEqual(d.Review.objects.count(),1)
 def test_successor_reference_requires_explicit_predecessor_and_preserves_key_intent(self):
  f=self.f;a,b=aliases(f);r=propose(f,a,[b]);self.assertEqual(propose(f,a,[b]).pk,r.pk);fresh(f,a)
  with self.assertRaises(ValidationError):propose(f,a,[b])
  next_row=propose(f,a,[b],predecessor=r.pk);self.assertEqual(next_row.version,2);self.assertEqual(next_row.predecessor_id,r.pk)
 def test_cross_case_conflict_needs_actual_permissions_and_configuration_in_every_case(self):
  f=self.f;g=second_case(f);a=capture(f);b=capture(g);verify(f,a);verify(g,b);r=propose(f,a,[b]);confirm(f,r);current(f,a)
  Grant.objects.filter(case=g['case'],user=f['reviewer'],action='ledger.resolve_review').update(active=False)
  with self.assertRaises(ValidationError):ledger.report(f['actor'],f['case'].pk,a.pk)
  Grant.objects.filter(case=g['case'],user=f['actor'],action='ledger.read').update(active=False);self.assertFalse(d.visible_packets(f['actor'],f['case']));self.assertFalse(d.visible_evidence(f['actor'],f['case']).exists())
 def test_cross_case_disabled_and_hidden_scope_cannot_be_bypassed(self):
  f=self.f;g=second_case(f,False);a=capture(f);b=capture(g);verify(f,a);verify(g,b)
  with self.assertRaises(ValidationError):propose(f,a,[b])
  policy(f,RESOLUTION,dict(f['conflicts'],allow_cross_case=True));policy(g,RESOLUTION,dict(f['conflicts'],allow_cross_case=True));Grant.objects.filter(case=g['case'],user=f['actor'],action='ledger.resolve').update(active=False)
  with self.assertRaises(PermissionDenied):propose(f,a,[b])
 def test_actual_staff_forms_independent_review_and_no_store(self):
  f=self.f;a,b=aliases(f);self.client.force_login(f['actor']);url=reverse('ledger',args=[f['case'].pk]);response=self.client.post(url,{'action':'resolve','revision':rev(f['case']),'selected':a.pk,'members':[a.pk,b.pk],'retired':[b.pk],'mode':'duplicate_alias','reference':'ui','predecessor':'','evidence':f['resolution_evidence'].pk,'reason':'Human chooses duplicate alias'});self.assertEqual(response.status_code,302);r=d.Resolution.objects.get();self.client.force_login(f['reviewer']);response=self.client.post(url,{'action':'resolve_review','revision':rev(f['case']),'resolution':r.pk,'verdict':'confirm','evidence':f['resolution_review_evidence'].pk});self.assertEqual(response.status_code,302);self.assertEqual(d.accepted(r)[0].verdict,'confirm');response=self.client.get(url);self.assertEqual(response['Cache-Control'],'no-store');self.assertContains(response,'Human claim dispositions')
 def test_agent_and_generic_evidence_do_not_expose_cross_case_sources_or_execute_decisions(self):
  f=self.f;a,b=aliases(f);propose(f,a,[b]);from apps.agents.ledger import investigate
  value=investigate(f['actor'],f['case'].pk);self.assertFalse(value.result['resolution_decision_executed']);self.assertFalse(value.result['cross_case_source_details_read']);self.assertFalse(d.Review.objects.exists());self.assertFalse(public_evidence(f['case'].evidence.all()).filter(kind='ledger_resolution').exists());self.assertFalse(public_timeline(f['case']).filter(action__startswith='agent.data.ledger_resolution').exists())
 def test_sql_immutability_exact_member_and_resolution_lineage_guards(self):
  f=self.f;a,b=aliases(f);r=propose(f,a,[b]);rr=confirm(f,r);m=r.members.first()
  for table,pk in [('ledgerresolution',r.pk),('ledgerresolutionmember',m.pk),('ledgerresolutionreview',rr.pk)]:
   with self.assertRaises(DatabaseError),transaction.atomic():
    with connection.cursor() as cursor:cursor.execute('DELETE FROM finance_'+table+' WHERE id=%s',[pk])
  with self.assertRaises(DatabaseError),transaction.atomic():d.Member.objects.create(resolution=r,lineage=b,verification=a.checks.latest('pk'),disposition='selected')

 def test_corrected_successor_after_alias_resolution_explicitly_covers_prior_aliases(self):
  f=self.f;a,b=aliases(f);r=propose(f,a,[b]);confirm(f,r);current(f,a)
  new=capture(f,dict(a.payload,target_reference='QB-102'),a.pk)
  for w in [a,b,new]:fresh(f,w,{'target_reference':'QB-102'})
  successor=propose(f,new,[a,b],mode='reference_correction',reference='corrected-after-alias')
  confirm(f,successor);self.assertEqual(current(f,new)['incumbent']['target_reference'],'QB-102')
  with self.assertRaises(ValidationError):d.accepted(r)

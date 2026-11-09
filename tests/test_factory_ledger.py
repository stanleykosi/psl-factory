"""Independent F01 factory, synthetic supplied evidence and real native services."""
import copy
from datetime import timedelta
from django.test import TestCase
from django.core.exceptions import ValidationError,PermissionDenied
from django.db import connection,transaction,DatabaseError
from django.utils import timezone
from apps.identity.models import Grant
from apps.core.evidence_access import public_evidence,public_agent_runs
from apps.core.models import Evidence
from apps.agents.models import AgentRun
from apps.finance import ledger
from apps.finance.models import LedgerLineage
from apps.policy.operator_drafts import draft_operator_policy
from apps.policy.services import transition
from apps.workflows import factory,factory_ledger as flow
from apps.workflows.models import FactoryWork
from .ledger_helpers import fixture,evidence,verify,review,capture
from .helpers import rev
from .ledger_factory_provisional import install

class FactoryLedgerTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass();install()
    fixture_factory=staticmethod(fixture)
    def setUp(self):
        self.f=self.fixture_factory();f=self.f
        value={'definition':flow.DEFINITION,'max_steps':40,'max_tokens':50000,'tokens_per_call':100,'max_children':100,'max_depth':3,'lease_seconds':30,'max_age_seconds':86400,'required_evidence_kinds':[flow.KIND],'information_resolver_id':None,'executor_id':None,'review_role':None,'provider':'synthetic_factory_v1','enabled':True}
        self.policy=draft_operator_policy(f['actor'],f['case'].pk,'OPS.factory_ledger_execution',value,f['e'].pk,timezone.now()-timedelta(seconds=1));transition(f['actor'],self.policy.pk,'validated');transition(f['actor'],self.policy.pk,'active')
        self.source=evidence(f,'ledger_source',f['v']['source'])
    def start(self):
        f=self.f;self.work=flow.start(f['actor'],f['case'].pk,'ledger-1',self.source.pk,None,rev(f['case']));return self.work
    def advance(self):
        factory.run_until_wait(self.work.pk);self.work.refresh_from_db();self.work.case.refresh_from_db();return self.work
    def accepted(self):
        self.start();self.advance();w=flow.lineage(self.work);self.assertIsNotNone(w,self.work.finding);x=verify(self.f,w);review(self.f,x);self.advance();self.assertEqual(self.work.status,'verified',self.work.finding);return w,x
    def rows(self):
        with connection.cursor() as c:
            c.execute("SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename");result={}
            for n, in c.fetchall():c.execute('SELECT to_jsonb(t)::text FROM '+connection.ops.quote_name(n)+' t ORDER BY to_jsonb(t)::text');result[n]=c.fetchall()
            return result
    def test_native_chain_current_history_and_read_preservation(self):
        w,x=self.accepted();f=self.f;p=flow.verify(self.work,f['actor']);self.assertFalse(p['posting_performed']);self.assertFalse(p['native_authenticity_verified']);self.assertFalse(p['financial_completeness_verified'])
        self.assertTrue(self.work.activities.filter(kind='ACT04',status='succeeded').exists());self.assertEqual(LedgerLineage.objects.count(),1)
        self.client.force_login(f['actor']);before=self.rows();response=self.client.get('/work/'+str(self.work.pk)+'/');self.assertContains(response,'Supplied incumbent transaction reference');self.assertContains(response,'Private scoped agent activity');self.assertContains(response,'current at that time');self.assertEqual(before,self.rows())
        self.assertEqual(flow.start(f['actor'],f['case'].pk,'ledger-1',self.source.pk,None,rev(f['case'])).pk,self.work.pk)
        review(f,x,'reject');self.assertTrue(flow.projection(f['actor'],self.work)['readiness_changed'])
        with self.assertRaises(ValidationError):flow.verify(self.work,f['actor'])
        with self.assertRaises(DatabaseError),transaction.atomic():FactoryWork.objects.filter(pk=self.work.pk).update(status='verified')
    def test_private_reader_and_generic_disclosure_denied(self):
        self.accepted();f=self.f
        self.assertFalse(public_evidence(Evidence.objects.all()).filter(pk=self.work.source_head_id).exists());self.assertFalse(public_agent_runs(AgentRun.objects.all()).filter(process_id='F01').exists())
        Grant.objects.filter(case=f['case'],user=f['reviewer'],action='ledger.private.read').update(active=False);self.client.force_login(f['reviewer']);before=self.rows();r=self.client.get('/work/'+str(self.work.pk)+'/');self.assertIn(r.status_code,[403,404]);self.assertEqual(before,self.rows())
    def test_uncertain_observation_never_retries_or_verifies(self):
        self.start();self.advance();w=flow.lineage(self.work);verify(self.f,w,{'state':'unknown','target_reference':None,'incumbent_version':None});self.advance();self.assertNotEqual(self.work.status,'verified');self.assertEqual(LedgerLineage.objects.count(),1)
        with self.assertRaises(ValidationError):flow.verify(self.work,self.f['actor'])
    def test_correction_requires_new_review_preserves_prior_history(self):
        w,x=self.accepted();f=self.f;body=copy.deepcopy(f['v']['source']);body['outcome']='uncertain';e=evidence(f,'ledger_source',body)
        flow.correct(f['actor'],self.work.pk,self.work.revision,rev(f['case']),e.pk,w.pk,'Correct supplied source status');self.advance();new=flow.lineage(self.work);self.assertNotEqual(new.pk,w.pk);self.assertEqual(new.predecessor_id,w.pk);self.assertTrue(x.decisions.exists());self.assertNotEqual(self.work.status,'verified')
        nx=verify(f,new);review(f,nx);self.advance();self.assertEqual(self.work.status,'verified',self.work.finding)
    def test_typed_human_commands_and_stale_revisions(self):
        self.start();self.advance();f=self.f;w=flow.lineage(self.work);x=verify(f,w)
        with self.assertRaises(PermissionDenied):flow.command(f['actor'],self.work.pk,self.work.revision,rev(f['case']),'review',x.pk,f['e'].pk,'approve')
        with self.assertRaises(ValidationError):flow.command(f['reviewer'],self.work.pk,self.work.revision-1,rev(f['case']),'review',x.pk,f['e'].pk,'approve')
        flow.command(f['reviewer'],self.work.pk,self.work.revision,rev(f['case']),'review',x.pk,f['e'].pk,'approve');self.advance();self.assertEqual(self.work.status,'verified',self.work.finding)
    def test_duplicate_claim_and_revoked_verifier_hold_current_output(self):
        w,x=self.accepted();f=self.f;capture(f)
        with self.assertRaises(ValidationError):flow.verify(self.work,f['actor'])
        self.assertTrue(flow.projection(f['actor'],self.work)['readiness_changed'])
    def test_cancellation_no_capture_and_unknown_command(self):
        self.start();f=self.f;factory.manage(f['actor'],self.work.pk,self.work.revision,'cancel');self.advance();self.assertEqual(self.work.status,'cancelled');self.assertEqual(LedgerLineage.objects.count(),0)
        with self.assertRaises(ValidationError):flow.command(f['reviewer'],self.work.pk,self.work.revision,rev(f['case']),'review',1,f['e'].pk,'approve')

    def test_exact_http_intake_and_commands_reject_extra_fields(self):
        f=self.f;self.client.force_login(f['actor'])
        response=self.client.post(__import__('django.urls',fromlist=['reverse']).reverse('factory_create'),{'definition':flow.DEFINITION,'case':str(f['case'].pk),'key':'http-ledger','revision':rev(f['case']),'evidence_id':self.source.pk,'predecessor_id':''})
        self.assertEqual(response.status_code,302,response.content);self.work=FactoryWork.objects.get(key='http-ledger');self.advance()
        before=self.rows();r=self.client.post('/work/'+str(self.work.pk)+'/',{'action':'observe','revision':self.work.revision,'case_revision':rev(f['case']),'target':flow.lineage(self.work).pk,'evidence':self.source.pk,'post_to_quickbooks':'yes'});self.assertEqual(r.status_code,200);self.assertEqual(before,self.rows())
    def test_recheck_current_observation_reuses_lineage_and_budget(self):
        w,x=self.accepted();f=self.f;spent=self.work.budget_used;verify(f,w,{'state':'unknown'});flow.recheck(f['actor'],self.work.pk,self.work.revision,rev(f['case']),'Inspect changed incumbent evidence');self.advance();self.assertNotEqual(self.work.status,'verified');self.assertGreaterEqual(self.work.budget_used,spent);self.assertEqual(LedgerLineage.objects.count(),1)
        nx=verify(f,w);review(f,nx);self.advance();self.assertEqual(self.work.status,'verified',self.work.finding)

    def test_existing_native_lineage_is_reused_not_recaptured(self):
        f=self.f;w=ledger.capture(f['actor'],f['case'].pk,self.source.pk,None,rev(f['case']));x=verify(f,w);review(f,x)
        self.start();self.advance();self.assertEqual(self.work.status,'verified',self.work.finding);self.assertEqual(flow.lineage(self.work).pk,w.pk);self.assertEqual(LedgerLineage.objects.count(),1)
    def test_agent_cannot_select_posting_or_human_approval(self):
        self.start()
        class Malicious:
            def choose(self,context):return {'activity':'ACT13','citations':context['evidence_ids']}
        factory.run_once(self.work.pk,provider=Malicious());self.work.refresh_from_db();self.assertEqual(self.work.status,'blocked');self.assertEqual(LedgerLineage.objects.count(),0)
    def test_expired_supplied_observation_is_held_without_mutation(self):
        self.start();self.advance();f=self.f;w=flow.lineage(self.work);before=self.rows()
        with self.assertRaises(ValidationError):verify(f,w,{'observed_at':(timezone.now()-timedelta(days=2)).isoformat()})
        self.assertEqual(w.checks.count(),0)

    def test_explicit_cancelled_restart_preserves_budget_and_original_identity(self):
        self.start();f=self.f;factory.manage(f['actor'],self.work.pk,self.work.revision,'cancel');self.advance();spent=self.work.budget_used;head=self.work.source_head_id
        flow.restart(f['actor'],self.work.pk,self.work.revision,rev(f['case']),'Resume supplied reference review');self.advance();self.assertEqual(self.work.source_head_id,head);self.assertGreaterEqual(self.work.budget_used,spent);self.assertEqual(LedgerLineage.objects.count(),1)
    def test_queue_review_owner_is_independent_configured_finance(self):
        self.start();self.advance();f=self.f;verify(f,flow.lineage(self.work));self.work.case.refresh_from_db()
        from apps.workflows.factory_views import presentation
        row=presentation(f['actor'],self.work);self.assertFalse(row['ledger']['can_review']);self.assertFalse(row['needs_me']);self.assertIn(f['reviewer'].username,row['owner'])
        row=presentation(f['reviewer'],self.work);self.assertTrue(row['ledger']['can_review']);self.assertTrue(row['needs_me'])

    def test_revoked_intake_authority_cannot_prevent_safe_cancellation(self):
        self.start();f=self.f;Grant.objects.filter(case=f['case'],user=f['actor'],action='factory.start').update(active=False)
        evidence_count=Evidence.objects.count();head=self.work.source_head_id
        factory.manage(f['actor'],self.work.pk,self.work.revision,'cancel');self.advance();self.assertEqual(self.work.status,'cancelled');self.assertEqual(LedgerLineage.objects.count(),0)
        self.assertEqual(Evidence.objects.count(),evidence_count);self.assertEqual(self.work.source_head_id,head);self.assertFalse(self.work.activities.filter(kind='ACT13').exists())
        with self.assertRaises(ValidationError):factory.manage(f['actor'],self.work.pk,self.work.revision,'resume')
        with self.assertRaises(ValidationError):flow.recheck(f['actor'],self.work.pk,self.work.revision,rev(f['case']),'Cannot reopen a cancelled intent')
        self.work.refresh_from_db();self.assertEqual(self.work.status,'cancelled');self.assertEqual(Evidence.objects.count(),evidence_count)

    def test_private_investigation_identifies_exact_configured_scope_and_review_gaps(self):
        f=self.f;self.source=evidence(f,'ledger_source',dict(f['v']['source'],realm='unconfigured-realm',outcome='uncertain'));self.start();before=self.rows()
        assessment=flow.investigation(self.work,f['actor']);self.assertEqual(before,self.rows());self.assertIn({'field':'realm','matches_configured_scope':False},assessment['scope_checks']);self.assertIn('configured_scope',[x['code'] for x in assessment['findings']]);self.assertFalse(assessment['decision_assessment']['currently_approved']);self.assertEqual(assessment['observation_assessment']['state'],None);self.assertIn(self.source.pk,assessment['citations'])
        self.assertEqual(LedgerLineage.objects.count(),0);self.assertFalse(assessment['posting_performed']);self.assertFalse(assessment['cross_case_details_read'])
    def test_investigation_changes_with_native_uncertainty_and_independent_review(self):
        self.start();self.advance();f=self.f;w=flow.lineage(self.work);x=verify(f,w,{'state':'unknown','incumbent_version':None})
        unknown=flow.investigation(self.work,f['actor']);self.assertEqual(unknown['observation_assessment']['state'],'unknown');self.assertFalse(unknown['observation_assessment']['current']);self.assertTrue(unknown['findings'])
        x=verify(f,w);review(f,x);before=self.rows();accepted=flow.investigation(self.work,f['actor']);self.assertEqual(before,self.rows());self.assertTrue(accepted['observation_assessment']['current']);self.assertTrue(accepted['decision_assessment']['currently_approved']);self.assertEqual(accepted['findings'],[]);self.assertFalse(accepted['approval_granted'])

from .ledger_resolution_helpers import fixture as resolution_fixture,second_case,propose,confirm,current,fresh
class FactoryLedgerResolutionTests(FactoryLedgerTests):
    fixture_factory=staticmethod(resolution_fixture)
    # Inherit only helpers, not duplicate baseline tests with different policy assumptions.
    test_native_chain_current_history_and_read_preservation=None
    test_private_reader_and_generic_disclosure_denied=None
    test_uncertain_observation_never_retries_or_verifies=None
    test_correction_requires_new_review_preserves_prior_history=None
    test_typed_human_commands_and_stale_revisions=None
    test_duplicate_claim_and_revoked_verifier_hold_current_output=None
    test_cancellation_no_capture_and_unknown_command=None
    test_exact_http_intake_and_commands_reject_extra_fields=None
    test_recheck_current_observation_reuses_lineage_and_budget=None
    test_existing_native_lineage_is_reused_not_recaptured=None
    test_agent_cannot_select_posting_or_human_approval=None
    test_expired_supplied_observation_is_held_without_mutation=None
    test_explicit_cancelled_restart_preserves_budget_and_original_identity=None
    test_queue_review_owner_is_independent_configured_finance=None
    test_revoked_intake_authority_cannot_prevent_safe_cancellation=None
    test_private_investigation_identifies_exact_configured_scope_and_review_gaps=None
    test_investigation_changes_with_native_uncertainty_and_independent_review=None
    def resolved(self,cross=False,target=False):
        f=self.f;self.start();self.advance();selected=flow.lineage(self.work)
        if target:
            other=capture(f,dict(selected.payload,source_reference='TX-002'));verify(f,other)
            correction=evidence(f,'ledger_source',dict(selected.payload,target_reference='QB-102'))
            flow.correct(f['actor'],self.work.pk,self.work.revision,rev(f['case']),correction.pk,selected.pk,'Correct mistaken target reference');self.advance();new=flow.lineage(self.work)
            verify(f,selected,{'target_reference':'QB-102'});verify(f,new)
            r=propose(f,new,[selected],[selected,new,other],mode='reference_correction');selected=new
        else:
            g=second_case(f) if cross else f;other=capture(g);verify(f,selected);verify(g,other);r=propose(f,selected,[other])
        self.advance();self.assertNotEqual(self.work.status,'verified');confirm(f,r);current(f,selected);self.advance();self.assertEqual(self.work.status,'verified',self.work.finding)
        return selected,r
    def test_resolved_same_case_alias_then_withdrawal(self):
        selected,r=self.resolved();confirm(self.f,r,'withdraw')
        with self.assertRaises(ValidationError):flow.verify(self.work,self.f['actor'])
        with self.assertRaises(DatabaseError),transaction.atomic():FactoryWork.objects.filter(pk=self.work.pk).update(status='verified')
    def test_resolved_cross_case_alias_then_participant_grant_revocation(self):
        selected,r=self.resolved(cross=True);other=r.members.exclude(lineage=selected).get().lineage
        Grant.objects.filter(case=other.case,user=self.f['reviewer'],action='ledger.resolve_review').update(active=False)
        with self.assertRaises(ValidationError):flow.verify(self.work,self.f['actor'])
        with self.assertRaises(DatabaseError),transaction.atomic():FactoryWork.objects.filter(pk=self.work.pk).update(status='verified')
    def test_resolved_target_correction_then_stale_policy(self):
        selected,r=self.resolved(target=True);transition(self.f['actor'],self.f['resolution_policy'].pk,'revoked')
        with self.assertRaises(ValidationError):flow.verify(self.work,self.f['actor'])
        with self.assertRaises(DatabaseError),transaction.atomic():FactoryWork.objects.filter(pk=self.work.pk).update(status='verified')

    def test_resolution_uses_current_policy_context_for_existing_observations(self):
        from .ledger_helpers import policy
        from apps.policy.ledger_validators import RULES
        f=self.f;self.start();self.advance();selected=flow.lineage(self.work);other=capture(f);verify(f,selected);verify(f,other)
        policy(f,RULES,dict(f['v']['rules'],max_age_seconds=7200))
        r=propose(f,selected,[other]);confirm(f,r);current(f,selected);self.advance();self.assertEqual(self.work.status,'verified',self.work.finding)

    def test_retained_target_claim_gets_its_own_factory_output_after_resolution(self):
        selected,r=self.resolved(target=True);f=self.f;other=r.members.get(disposition='retained').lineage;current(f,other)
        retained=flow.start(f['actor'],f['case'].pk,'retained-target',other.evidence_id,None,rev(f['case']))
        factory.run_until_wait(retained.pk);retained.refresh_from_db();self.assertEqual(retained.status,'verified',retained.finding);self.assertEqual(flow.lineage(retained).pk,other.pk)
        confirm(f,r,'withdraw')
        with self.assertRaises(ValidationError):flow.verify(retained,f['actor'])
        with self.assertRaises(DatabaseError),transaction.atomic():FactoryWork.objects.filter(pk=retained.pk).update(status='verified')

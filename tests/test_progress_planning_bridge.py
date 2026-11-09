"""Native/SQL agreement for the full Planning bridge consumed by P28."""
import copy,json
from django.test import TestCase
from django.db import connection
from django.core.exceptions import ValidationError,PermissionDenied
from django.utils import timezone
from apps.core.services import add_evidence
from apps.identity.models import Grant
from apps.pmo import planning,delivery,approvals,progress
from apps.pmo.models import ApprovalObservation
from tests import planning_helpers as h
from tests.helpers import rev

class ProgressPlanningBridgeTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.f=h.fixture(username='progress-bridge');h.observe(cls.f)
        f=cls.f;cls.ready=planning.prepare(f['a'],f['c'].pk,f['packet'].pk)
        cls.dossier=delivery.open_dossier(f['a'],f['c'].pk,f['pair']['candidate_id'],f['e']['plan'].pk,'Exact native plan bridge',rev(f['c']))
        source=planning.bridge(f['a'],f['c'].pk,cls.ready.pk,cls.dossier.pk);delivery.verify_source(f['a'],f['c'].pk,source.pk,rev(f['c']))
        for kind in delivery.PLANNING:
            if kind=='scope_baseline':continue
            row=delivery.capture_source(f['a'],f['c'].pk,cls.dossier.pk,kind,'synthetic:'+kind,f['e']['requirements'].pk,{'requires_ui':False,'client_signoff_required':False} if kind=='ui_applicability' else {},rev(f['c']))
            delivery.verify_source(f['a'],f['c'].pk,row.pk,rev(f['c']))
        cls.plan=delivery.decide_planning(f['a'],f['c'].pk,cls.dossier.pk,'approve',f['e']['plan'].pk,'Exact approved current readiness',rev(f['c']))

    def sql(self):
        with connection.cursor() as cursor:
            cursor.execute('SELECT psl_progress_readiness(%s),psl_progress_plan(%s)',[self.ready.pk,self.plan.pk]);return cursor.fetchone()

    def assert_held(self):
        with self.assertRaises((ValidationError,PermissionDenied)):planning.current_readiness(self.f['c'],self.ready.pk)
        self.assertEqual(self.sql(),(False,False))

    def test_full_source_bridge_native_sql_agree_and_new_correlated_effect_is_allowed(self):
        self.assertTrue(planning.current_readiness(self.f['c'],self.ready.pk));self.assertEqual(self.sql(),(True,True))
        f=self.f;a,c=f['a'],f['c'];e=f['e']
        source=progress.configure(a,c.pk,self.dossier.pk,'Engineering','Supplied board','BRIDGED-28',a.pk,'synthetic_mock',e['requirements'].pk,rev(c))
        observation=progress.observe(a,c.pk,source.pk,None,'r1',timezone.now(),'available',{'activity_ref':'A1','dependency_ref':'D1','summary':'Actual dependency delay','timeline_impact':True,'scope_change':False},rev(c))
        from apps.pmo.issues import log_issue
        from apps.pmo.escalations import capture_profile
        state=log_issue(a,c.pk,'BRIDGED-ISSUE','Dependency delay','Dependency',a.pk,'Obtain owner recovery evidence',e['requirements'].pk,'Authoritative issue',rev(c))
        profile=capture_profile(a,c.pk,state.issue_id,state.pk,'unclassified',True,None,e['requirements'].pk,'Actual impact',rev(c))
        row=progress.correlate(a,c.pk,observation.pk,None,self.plan.pk,state.issue_id,state.pk,profile.pk,'Observed effect on A1, not an approved amendment',e['requirements'].pk,rev(c))
        self.assertEqual(progress.correlation_current(row).pk,row.pk)

    def test_current_alignment_successor_invalidates_native_and_sql_without_rewriting_history(self):
        from apps.pmo.meetings import record_meeting
        f=self.f;m=f['meetings']['prd_walkthrough']
        record_meeting(f['a'],f['c'].pk,m.meeting.reference,'alignment',m.occurred_at,m.purpose,'Corrected actual meeting notes',m.participant_ids,m.decisions,m.evidence_id,rev(f['c']),m.meeting_id)
        self.assert_held()

    def test_department_observation_replacement_invalidates_exact_native_and_sql_pins(self):
        f=self.f;old=ApprovalObservation.objects.get(pk=planning.current_readiness(f['c'],self.ready.pk)['inputs']['observations']['scope'])
        payload=dict(old.payload,observed_at=timezone.now().isoformat())
        evidence=h.evidence(f,'approval_observation',payload)
        approvals.observe(f['owners']['scope'],f['c'].pk,old.receipt_id,evidence.pk)
        self.assert_held()

    def test_current_owner_grant_revocation_and_reader_source_scope_hold_both(self):
        f=self.f;grant=Grant.objects.get(case=f['c'],user=f['owners']['scope'],action='approval.verify');grant.active=False;grant.save()
        self.assert_held();grant.active=True;grant.save();self.assertEqual(self.sql(),(True,True))
        Grant.objects.filter(case=f['c'],user=f['a'],action='approval.source.read:synthetic-planning-scope').update(active=False)
        self.assert_held()

    def test_withdrawn_department_contract_and_missing_criteria_hold_both(self):
        f=self.f;evidence=h.evidence(f,'approval_contract_review','Owner withdrew source contract')
        approvals.review_contract(f['owners']['scope'],f['c'].pk,'planning_scope',evidence.pk,'withdraw')
        self.assert_held()

    def test_unknown_source_packet_and_untrusted_ready_text_do_not_become_approved(self):
        f=self.f;payload=copy.deepcopy(f['payload']);payload['prd_id']=None
        planning.capture(f['a'],f['c'].pk,payload,f['packet'].pk);self.assert_held()
        fake=add_evidence(f['a'],f['c'].pk,'planning_readiness',self.ready.body,'untrusted:copy')
        with self.assertRaises(ValidationError):planning.current_readiness(f['c'],fake.pk)
        with connection.cursor() as cur:
            cur.execute('SELECT psl_progress_readiness(%s)',[fake.pk]);self.assertFalse(cur.fetchone()[0])

    def test_age_policy_and_plan_authority_expiry_agree_without_newer_draft_staleness(self):
        f=self.f;add_evidence(f['a'],f['c'].pk,'plan','Unselected newer draft','synthetic:draft')
        self.assertEqual(self.sql(),(True,True));self.assertTrue(planning.current_readiness(f['c'],self.ready.pk))
        Grant.objects.filter(case=f['c'],user=f['a'],action='delivery.planning_decide').update(active=False)
        with self.assertRaises(PermissionDenied):delivery.approved_plan(self.dossier)
        self.assertEqual(self.sql(),(True,False))

    def test_canonical_identity_handles_unicode_and_control_characters(self):
        from apps.documents.contracts import digest
        data={'unicode':'é😀','escaped':'x\n"\\','integer':123,'nested':[True,None,{'s':'é'}]}
        with connection.cursor() as cur:
            cur.execute("SELECT encode(sha256(convert_to(psl_progress_canonical(%s::jsonb),'UTF8')),'hex')",[json.dumps(data)]);self.assertEqual(cur.fetchone()[0],digest(data))

    def test_actual_alignment_age_expiry_holds_without_mutating_recorded_dates(self):
        import time
        from datetime import timedelta
        f=self.f;first=f['meetings']['prd_walkthrough'];rules=copy.deepcopy(f['rules'])
        rules['alignment_max_age_seconds']=int((timezone.now()-first.occurred_at).total_seconds())+30
        h.criteria(f,rules)
        self.ready=planning.prepare(f['a'],f['c'].pk,f['packet'].pk)
        source=planning.bridge(f['a'],f['c'].pk,self.ready.pk,self.dossier.pk);delivery.verify_source(f['a'],f['c'].pk,source.pk,rev(f['c']))
        self.plan=delivery.decide_planning(f['a'],f['c'].pk,self.dossier.pk,'approve',f['e']['plan'].pk,'Current shorter explicit alignment window',rev(f['c']))
        self.assertEqual(self.sql(),(True,True))
        remaining=(first.occurred_at+timedelta(seconds=rules['alignment_max_age_seconds'])-timezone.now()).total_seconds()
        time.sleep(max(0,remaining)+0.05)
        self.assert_held()

    def test_actual_signed_comparison_and_revoked_reviewer_agree_without_amending_baseline(self):
        f=self.f;a,c,e=f['a'],f['c'],f['e']
        from apps.pmo.services import decide,sign_baseline
        from apps.pmo.models import Baseline
        from tests.signature_helpers import packet_for
        for role in ['PM','Head of PMO','CEO','PMO Lead']:decide(a,c.pk,role,rev(c))
        packet_for(a,c,e);sign_baseline(a,c.pk,e['signature'].pk,rev(c))
        before=Baseline.objects.get(case=c).signed_id
        rules=copy.deepcopy(f['rules']);rules.update(comparison_reviewer_id=f['owners']['scope'].pk,comparison_reviewer_role='Product Owner');h.criteria(f,rules)
        proof=h.evidence(f,'planning_comparison_evidence','Actual human-reviewed source match')
        planning.compare(f['owners']['scope'],c.pk,f['packet'].pk,'no_difference',proof.pk)
        ready=planning.prepare(a,c.pk,f['packet'].pk)
        self.assertTrue(planning.current_readiness(c,ready.pk)['comparison_required'])
        with connection.cursor() as cur:
            cur.execute('SELECT psl_progress_readiness(%s)',[ready.pk]);self.assertTrue(cur.fetchone()[0])
        Grant.objects.filter(case=c,user=f['owners']['scope'],action='planning.compare').update(active=False)
        with self.assertRaises((PermissionDenied,ValidationError)):planning.current_readiness(c,ready.pk)
        with connection.cursor() as cur:
            cur.execute('SELECT psl_progress_readiness(%s)',[ready.pk]);self.assertFalse(cur.fetchone()[0])
        self.assertEqual(Baseline.objects.get(case=c).signed_id,before)

    def test_exact_excluded_source_null_declaration_and_owner_response_match_sql(self):
        from apps.pmo import planning_sources as sources
        f=self.f;a,c=f['a'],f['c'];p=copy.deepcopy(f['payload'])
        p['source_correlations'][0].update(state='conflicting',document_version=None,target_scope_id=None,evidence_id=None)
        packet=planning.capture(a,c.pk,p,f['packet'].pk)
        replacement=h.evidence(f,'scope_baseline','Explicit owner supplied replacement scope')
        proof=h.evidence(f,'planning_clarification','Actual source owner replacement/PRD/scope interpretation')
        owner=f['owners']['scope'];item=sources.clarify(a,c.pk,packet.pk,'scope_id',owner.pk)
        resolution=sources.resolve(owner,c.pk,packet.pk,'scope_id',item.pk,item.current.number,'exclude_in_successor',proof.pk,replacement.pk,p['prd_id'],replacement.pk)
        corrected=copy.deepcopy(p);corrected['scope_id']=replacement.pk
        corrected['source_correlations'][0].update(state='excluded',resolution_id=resolution.pk)
        for row in corrected['source_correlations'][1:]:row.update(target_scope_id=replacement.pk,evidence_id=proof.pk)
        corrected['source_correlations'].append(dict(p['source_correlations'][0],key='replacement-scope',source_id=replacement.pk,state='current',document_version='owner-v2',target_scope_id=replacement.pk,evidence_id=proof.pk))
        successor=planning.capture(a,c.pk,corrected,packet.pk)
        for purpose,meeting in f['meetings'].items():planning.align(a,c.pk,successor.pk,purpose,meeting.pk)
        f['pair']=planning.open_requests(a,c.pk,successor.pk);h.observe(f)
        ready=planning.prepare(a,c.pk,successor.pk)
        self.assertEqual(planning.current_readiness(c,ready.pk)['inputs']['source_correlation']['resolution_ids'],[resolution.pk])
        with connection.cursor() as cur:
            cur.execute('SELECT psl_progress_readiness(%s)',[ready.pk]);self.assertTrue(cur.fetchone()[0])
        Grant.objects.filter(case=c,user=owner,action='planning.participate').update(active=False)
        with self.assertRaises((PermissionDenied,ValidationError)):planning.current_readiness(c,ready.pk)
        with connection.cursor() as cur:
            cur.execute('SELECT psl_progress_readiness(%s)',[ready.pk]);self.assertFalse(cur.fetchone()[0])

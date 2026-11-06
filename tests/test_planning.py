import copy,json
from django.test import TestCase,Client
from django.core.exceptions import ValidationError,PermissionDenied
from django.urls import reverse
from django.utils import timezone
from apps.identity.models import Grant
from apps.core.models import Audit
from apps.core.services import add_evidence
from apps.pmo import planning as d,delivery
from apps.pmo.models import Baseline
from apps.policy.planning_validators import COMPONENT
from apps.policy.services import active_component,transition
from apps.agents.planning import investigate
from tests import planning_helpers as h
from tests.helpers import rev

class PlanningTests(TestCase):
    @classmethod
    def setUpTestData(cls):cls.f=h.fixture()

    def test_pre_signature_packet_separate_source_decisions_real_delivery_planning_bridge(self):
        f=self.f;a,c,e=f['a'],f['c'],f['e']
        self.assertIsNone(Baseline.objects.get(case=c).signed_id)
        with self.assertRaises(ValidationError):d.prepare(a,c.pk,f['packet'].pk)
        h.observe(f);ready=d.prepare(a,c.pk,f['packet'].pk)
        self.assertEqual(d.prepare(a,c.pk,f['packet'].pk).pk,ready.pk)
        self.assertFalse(d.current_readiness(c,ready.pk)['inputs']['native_verified'])
        self.assertEqual(len(d.current_readiness(c,ready.pk)['inputs']['observations']),2)
        dossier=delivery.open_dossier(a,c.pk,f['pair']['candidate_id'],e['plan'].pk,'Planning source packet, still unsigned',rev(c))
        source=d.bridge(a,c.pk,ready.pk,dossier.pk);self.assertEqual(d.bridge(a,c.pk,ready.pk,dossier.pk).pk,source.pk)
        delivery.verify_source(a,c.pk,source.pk,rev(c));delivery.verified_source(dossier,'scope_baseline')
        for kind in delivery.PLANNING:
            if kind=='scope_baseline':continue
            payload={'requires_ui':False,'client_signoff_required':False} if kind=='ui_applicability' else {}
            item=delivery.capture_source(a,c.pk,dossier.pk,kind,'synthetic:'+kind,e['plan'].pk,payload,rev(c));delivery.verify_source(a,c.pk,item.pk,rev(c))
        decision=delivery.decide_planning(a,c.pk,dossier.pk,'approve',e['plan'].pk,'Actual current planning gate after separate source references',rev(c))
        self.assertEqual(decision.kind,'planning_decision');self.assertIsNone(Baseline.objects.get(case=c).signed_id)
        from apps.pmo.services import decide,sign_baseline
        for role in ['PM','Head of PMO','CEO','PMO Lead']:decide(a,c.pk,role,rev(c))
        sign_baseline(a,c.pk,e['signature'].pk,rev(c))
        self.assertEqual(d.prepare(a,c.pk,f['packet'].pk).pk,ready.pk)
        delivery.verified_source(dossier,'scope_baseline')
        successor=d.capture(a,c.pk,f['payload'],f['packet'].pk)
        with self.assertRaises(ValidationError):d.current_readiness(c,ready.pk)
        with self.assertRaises(ValidationError):delivery.verified_source(dossier,'scope_baseline')
        self.assertNotEqual(successor.pk,f['packet'].pk)

    def test_capture_before_missing_rules_unknowns_only_hold_readiness_and_generic_text_has_no_provenance(self):
        f=self.f;a,c=f['a'],f['c'];transition(a,active_component(COMPONENT,c).pk,'revoked')
        payload=copy.deepcopy(f['payload']);payload['prd_id']=None
        packet=d.capture(a,c.pk,payload,f['packet'].pk)
        self.assertIsNone(d.packet(c,packet.pk)[1]['payload']['prd_id'])
        with self.assertRaises(ValidationError):d.prepare(a,c.pk,packet.pk)
        fake=add_evidence(a,c.pk,'planning_readiness',json.dumps({'packet_id':packet.pk,'comparison_required':False,'inputs':{}}),'untrusted:source-text')
        with self.assertRaises(ValidationError):d.current_readiness(c,fake.pk)
        client=Client();client.force_login(a);self.assertContains(client.get(reverse('planning',args=[c.pk])),'Requirements, alignment and planning sources')
        self.assertEqual(client.get(reverse('case',args=[c.pk])).status_code,200)
        self.assertEqual(investigate(a,c.pk)['unknown_source_fields'],['prd_id'])

    def test_current_source_owner_and_contract_withdrawal_hold_without_deleting_history(self):
        f=self.f;h.observe(f);ready=d.prepare(f['a'],f['c'].pk,f['packet'].pk)
        Grant.objects.filter(case=f['c'],user=f['owners']['scope'],action='approval.verify').update(active=False)
        with self.assertRaises(PermissionDenied):d.current_readiness(f['c'],ready.pk)
        Grant.objects.filter(case=f['c'],user=f['owners']['scope'],action='approval.verify').update(active=True)
        from apps.pmo import approvals
        evidence=h.evidence(f,'approval_contract_review','Actual source-contract withdrawal')
        approvals.review_contract(f['owners']['scope'],f['c'].pk,'planning_scope',evidence.pk,'withdraw')
        with self.assertRaises(ValidationError):d.current_readiness(f['c'],ready.pk)
        self.assertTrue(f['c'].evidence.filter(pk=ready.pk).exists())

    def test_distinct_sessions_current_meeting_versions_contacts_and_questions_are_enforced(self):
        f=self.f;h.observe(f)
        d.align(f['a'],f['c'].pk,f['packet'].pk,'scope_estimate_alignment',f['meetings']['prd_walkthrough'].pk)
        with self.assertRaises(ValidationError):d.prepare(f['a'],f['c'].pk,f['packet'].pk)
        d.align(f['a'],f['c'].pk,f['packet'].pk,'scope_estimate_alignment',f['meetings']['scope_estimate_alignment'].pk)
        rules=copy.deepcopy(f['rules']);rules['require_named_contacts']=['Security'];h.criteria(f,rules)
        with self.assertRaises(ValidationError):d.prepare(f['a'],f['c'].pk,f['packet'].pk)
        self.assertEqual(d.report(f['a'],f['c'].pk)['status'],'dependent_readiness_held')

    def test_signed_comparison_is_configured_current_human_control_and_does_not_change_contract(self):
        f=self.f;a,c,e=f['a'],f['c'],f['e'];h.observe(f)
        from apps.pmo.services import decide,sign_baseline
        for role in ['PM','Head of PMO','CEO','PMO Lead']:decide(a,c.pk,role,rev(c))
        sign_baseline(a,c.pk,e['signature'].pk,rev(c));before=Baseline.objects.get(case=c).signed_id
        with self.assertRaises(ValidationError):d.prepare(a,c.pk,f['packet'].pk)
        rules=copy.deepcopy(f['rules']);rules.update(comparison_reviewer_id=f['owners']['scope'].pk,comparison_reviewer_role='Product Owner');h.criteria(f,rules)
        proof=h.evidence(f,'planning_comparison_evidence','Actual synthetic source-backed comparison')
        with self.assertRaises(PermissionDenied):d.compare(a,c.pk,f['packet'].pk,'no_difference',proof.pk)
        d.compare(f['owners']['scope'],c.pk,f['packet'].pk,'difference_unresolved',proof.pk)
        with self.assertRaises(ValidationError):d.prepare(a,c.pk,f['packet'].pk)
        with self.assertRaises(ValidationError):d.compare(f['owners']['scope'],c.pk,f['packet'].pk,'no_difference',proof.pk)
        corrected=h.evidence(f,'planning_comparison_evidence','New independent supporting evidence for corrected human comparison')
        d.compare(f['owners']['scope'],c.pk,f['packet'].pk,'no_difference',corrected.pk)
        ready=d.prepare(a,c.pk,f['packet'].pk);self.assertTrue(d.current_readiness(c,ready.pk)['comparison_required'])
        self.assertEqual(Baseline.objects.get(case=c).signed_id,before)
        add_evidence(a,c.pk,'planning_contract_comparison','malformed untrusted generic source','untrusted:source')
        with self.assertRaises(ValidationError):d.current_readiness(c,ready.pk)
        d.compare(f['owners']['scope'],c.pk,f['packet'].pk,'no_difference',corrected.pk)
        self.assertTrue(d.current_readiness(c,d.prepare(a,c.pk,f['packet'].pk).pk)['comparison_required'])

    def test_ui_capture_agent_and_csrf_use_actual_services(self):
        f=self.f;a,c=f['a'],f['c'];client=Client(enforce_csrf_checks=True);client.force_login(a)
        url=reverse('planning',args=[c.pk]);self.assertContains(client.get(url),'Typed capture interface')
        payload={'action':'capture','revision':rev(c),'payload':json.dumps(f['payload']),'predecessor':f['packet'].pk}
        self.assertEqual(client.post(url,payload).status_code,403)
        payload['csrfmiddlewaretoken']=client.cookies['csrftoken'].value
        self.assertEqual(client.post(url,payload).status_code,302)
        packet,_=d.packet(c);self.assertNotEqual(packet.pk,f['packet'].pk)
        response=client.post(url,{'action':'investigate','revision':rev(c),'csrfmiddlewaretoken':client.cookies['csrftoken'].value})
        self.assertEqual(response.status_code,200);self.assertEqual(response.json()['effect_tools'],[])

    def test_question_action_heads_and_current_formal_meeting_versions_hold_successors(self):
        from apps.pmo.meetings import create_action,change_action,record_meeting
        f=self.f;a,c,e=f['a'],f['c'],f['e']
        item=create_action(a,c.pk,'PLANNING-QUESTION','Actual unresolved planning gap',a.pk,None,e['requirements'].pk,'Source-backed question',rev(c))
        payload=copy.deepcopy(f['payload']);payload['questions']=[{'key':'Q1','detail':'Scope clarification','state':'unresolved','action_id':item.pk,'evidence_id':e['requirements'].pk}]
        p=d.capture(a,c.pk,payload,f['packet'].pk)
        for purpose,m in f['meetings'].items():d.align(a,c.pk,p.pk,purpose,m.pk)
        f['pair']=d.open_requests(a,c.pk,p.pk);h.observe(f)
        with self.assertRaises(ValidationError):d.prepare(a,c.pk,p.pk)
        rules=copy.deepcopy(f['rules']);rules['blocking_question_states']=[];rules['allowed_action_states']=['open'];h.criteria(f,rules)
        ready=d.prepare(a,c.pk,p.pk)
        m=f['meetings']['prd_walkthrough']
        record_meeting(a,c.pk,m.meeting.reference,'alignment',m.occurred_at,m.purpose,'Actual corrected meeting version',m.participant_ids,m.decisions,m.evidence_id,rev(c),m.meeting_id)
        with self.assertRaises(ValidationError):d.current_readiness(c,ready.pk)
        change_action(a,c.pk,item.pk,'start',e['requirements'].pk,'Action head changed',rev(c),item.current.number)
        with self.assertRaises(ValidationError):d.packet(c,p.pk)

    def test_policy_validator_rejects_wrong_owner_and_invalid_readiness_rules(self):
        from django.db import transaction
        from apps.policy.approval_validators import ROUTES
        from apps.policy.approval_drafts import draft_approval_policy
        f=self.f
        for key,value in [('alignment_max_age_seconds',0),('allowed_action_states',['invented']),('comparison_reviewer_id',999999)]:
            rules=copy.deepcopy(f['rules']);rules[key]=value
            with self.assertRaises(ValidationError),transaction.atomic():h.criteria(f,rules)
        rules=copy.deepcopy(f['rules']);rules['comparison_reviewer_id']=f['owners']['scope'].pk
        with self.assertRaises(ValidationError),transaction.atomic():h.criteria(f,rules)
        routes={'lease_seconds':30,'max_attempts':3,'routes':[dict(f['routes']['scope'],owner_role='PM',owner_id=f['a'].pk)]}
        p=draft_approval_policy(f['a'],f['c'].pk,ROUTES,routes,f['e']['policy_decision'].pk,timezone.now())
        with self.assertRaises(ValidationError):transition(f['a'],p.pk,'validated')

    def test_planning_bodies_are_domain_private_and_readiness_source_reads_are_current(self):
        from django.contrib.auth import get_user_model
        from apps.agents.services import extract_evidence
        from apps.documents.controlled import register_template,create_version
        f=self.f;a,c,e=f['a'],f['c'],f['e']
        payload=copy.deepcopy(f['payload']);payload['questions']=[{'key':'PRIVATE-Q','detail':'PRIVATE-PLANNING-SENTINEL','state':'resolved','action_id':None,'evidence_id':e['requirements'].pk}]
        p=d.capture(a,c.pk,payload,f['packet'].pk)
        for purpose,m in f['meetings'].items():d.align(a,c.pk,p.pk,purpose,m.pk)
        f['pair']=d.open_requests(a,c.pk,p.pk);h.observe(f);ready=d.prepare(a,c.pk,p.pk)
        reader=get_user_model().objects.create_user('planning-reader')
        for action in ['case.read','planning.read','approval.read']:Grant.objects.create(case=c,user=reader,action=action)
        client=Client();client.force_login(reader);response=client.get(reverse('case',args=[c.pk]))
        self.assertNotContains(response,'PRIVATE-PLANNING-SENTINEL')
        self.assertNotIn('readiness_inputs',d.report(reader,c.pk))
        self.assertContains(client.get(reverse('planning',args=[c.pk])),'PRIVATE-PLANNING-SENTINEL')
        for item in [p,ready]:
            with self.assertRaises(ValidationError):extract_evidence(a,c.pk,item.pk,'P17')
        template=register_template(a,c.pk,'Planning generic-body boundary',{'document_type':'project_artifact','required_fields':['executive_summary'],'audience_fields':{'internal':['executive_summary']}},e['policy_decision'].pk,rev(c))
        with self.assertRaises(ValidationError):create_version(a,c.pk,template.pk,'No private planning copy','internal',{'executive_summary':{'text':'No private source body','evidence_ids':[p.pk]}},rev(c))
        Grant.objects.filter(case=c,user=a,action='approval.source.read:synthetic-planning-scope').update(active=False)
        with self.assertRaises(PermissionDenied):d.current_readiness(c,ready.pk)
        self.assertTrue(c.evidence.filter(pk=ready.pk).exists())


from django.test import TransactionTestCase
class PlanningConcurrencyTests(TransactionTestCase):
    def test_two_postgresql_connections_capture_one_current_successor(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier
        from django.db import close_old_connections
        from django.contrib.auth import get_user_model
        f=h.fixture(configured=False,username='planning-race');barrier=Barrier(2)
        def writer():
            close_old_connections()
            try:
                a=get_user_model().objects.get(pk=f['a'].pk);barrier.wait(timeout=10)
                try:return ('created',d.capture(a,f['c'].pk,f['payload'],f['packet'].pk).pk)
                except ValidationError:return ('stale',None)
            finally:close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures=[pool.submit(writer) for _ in range(2)];results=[x.result(timeout=40) for x in futures]
        self.assertEqual(sorted(x[0] for x in results),['created','stale'])
        self.assertEqual(f['c'].evidence.filter(kind='planning_packet').count(),2)

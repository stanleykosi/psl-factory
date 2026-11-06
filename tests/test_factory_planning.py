import json,copy
from pathlib import Path
from django.test import TestCase
from django.urls import reverse
from django.db import connection,transaction,DatabaseError
from django.core.exceptions import ValidationError,PermissionDenied
from django.utils import timezone
from apps.identity.models import Grant
from apps.core.models import Evidence,Audit
from apps.core.evidence_access import public_evidence,public_timeline
from apps.policy.operator_drafts import draft_operator_policy
from apps.policy.services import transition
from apps.pmo import planning
from apps.pmo.models import DeliverySource,DeliveryDossier,ApprovalRequest,ApprovalRouteJob,ApprovalRouteReceipt
from apps.workflows import factory,factory_planning
from apps.workflows.models import FactoryWork,FactoryActivity,FactoryAttempt,HumanTask
from tests.planning_helpers import fixture,observe,evidence,supplied_observation
from tests.helpers import rev

def setup(configured=True,department_configured=True):
    f=fixture(configured=department_configured,username='factory-planning-human')
    value=json.loads(Path('fixtures/factory-planning.json').read_text());value.pop('classification')
    f['profile_values']=value
    if configured:
        p=draft_operator_policy(f['a'],f['c'].pk,'OPS.factory_planning_execution',value,f['e']['policy_decision'].pk,timezone.now())
        transition(f['a'],p.pk,'validated');transition(f['a'],p.pk,'active');f['profile']=p
    f['work']=factory_planning.start(f['a'],f['c'].pk,'PLAN-1',f['packet'].pk,'Planning factory example',rev(f['c']))
    return f

class FactoryPlanningTests(TestCase):
    def test_missing_department_policy_retains_requests_and_holds_only_delivery(self):
        f=setup(department_configured=False);w=f['work']
        successor=planning.capture(f['a'],f['c'].pk,f['payload'],f['packet'].pk)
        factory.run_until_wait(w.pk);w.refresh_from_db()
        self.assertEqual(w.status,'owner_needed',w.finding);self.assertEqual(w.source_head_id,successor.pk)
        self.assertEqual(ApprovalRequest.objects.filter(case=f['c']).count(),4)
        self.assertFalse(ApprovalRouteJob.objects.filter(request__case=f['c']).exists())
        pair=planning.open_requests(f['a'],f['c'].pk,successor.pk)
        self.assertEqual(len(pair['requests']),2)
        used=w.budget_used;factory.run_until_wait(w.pk);w.refresh_from_db();self.assertEqual(w.budget_used,used)
        self.assertFalse(HumanTask.objects.filter(case=f['c']).exists())

    def test_exact_department_panel_records_only_native_owner_observation(self):
        f=setup();w=f['work'];factory.run_until_wait(w.pk)
        receipt,proof=supplied_observation(f,'scope');other,wrong=supplied_observation(f,'estimates')
        self.client.force_login(f['owners']['scope']);url=reverse('factory_detail',args=[w.pk])
        page=self.client.get(url);self.assertContains(page,'Product Owner source review');self.assertNotContains(page,'Engineering Lead source review')
        w.refresh_from_db();revision=w.revision
        with self.assertRaises(PermissionDenied):factory_planning.observe_department(f['owners']['scope'],w.pk,revision,receipt.request_id,receipt.pk,wrong.pk)
        response=self.client.post(url,{'action':'observe_department','revision':revision,'request':receipt.request_id,'receipt':receipt.pk,'evidence':proof.pk})
        self.assertEqual(response.status_code,302)
        observation=receipt.observations.get();self.assertEqual(observation.actor_id,f['owners']['scope'].pk)
        self.assertEqual(observation.evidence_id,proof.pk);self.assertFalse(HumanTask.objects.filter(case=f['c']).exists())
        with self.assertRaises(ValidationError):factory_planning.observe_department(f['owners']['scope'],w.pk,revision,receipt.request_id,receipt.pk,proof.pk)
        self.assertNotContains(self.client.get(url),'Product Owner source review')
        self.assertFalse(other.observations.exists());self.assertFalse(DeliverySource.objects.filter(dossier__case=f['c']).exists())

    def test_connected_owner_wait_then_current_readiness_and_delivery_handoff(self):
        self.assertEqual(connection.vendor,'postgresql');f=setup();w=f['work']
        Grant.objects.filter(case=f['c'],user=f['a'],action='finance.read').update(active=False)
        factory.run_until_wait(w.pk);w.refresh_from_db()
        self.assertEqual(w.status,'waiting',w.finding);self.assertIn('department',w.finding)
        used=w.budget_used;factory.run_until_wait(w.pk);w.refresh_from_db();self.assertEqual(w.budget_used,used)
        self.assertFalse(HumanTask.objects.filter(case=f['c']).exists())
        observe(f);factory.run_until_wait(w.pk);w.refresh_from_db()
        self.assertEqual(w.status,'verified',w.finding)
        self.assertEqual(DeliveryDossier.objects.filter(case=f['c']).count(),1)
        self.assertEqual(DeliverySource.objects.filter(dossier__case=f['c']).count(),1)
        result=FactoryAttempt.objects.get(activity__work=w,activity__kind='ACT13',phase='observed').result
        self.assertFalse(result['native_verified']);self.assertEqual(result['verification_scope'],'current_planning_artifact_and_internal_handoff')
        self.assertEqual(set(result['owner_observations']),{'scope','estimates'})
        self.assertFalse(w.invoice_id);self.assertFalse(w.preparation_id)
        self.assertEqual(ApprovalRequest.objects.filter(case=f['c']).count(),2)
        self.assertEqual(ApprovalRouteReceipt.objects.filter(job__request__case=f['c']).count(),2)
        self.assertTrue(all(not r.payload['approval_granted'] for r in ApprovalRouteReceipt.objects.filter(job__request__case=f['c'])))

    def test_successor_packet_keeps_business_identity_and_spent_allowance(self):
        f=setup();w=f['work'];factory.run_until_wait(w.pk);w.refresh_from_db();spent=w.budget_used
        successor=planning.capture(f['a'],f['c'].pk,f['payload'],f['packet'].pk)
        same=factory_planning.start(f['a'],f['c'].pk,'NEW-FORM',successor.pk,'Revised planning',rev(f['c']))
        self.assertEqual(same.pk,w.pk)
        factory.run_until_wait(w.pk);w.refresh_from_db()
        self.assertEqual(w.source_head_id,successor.pk);self.assertEqual(w.budget_limit,20000);self.assertGreater(w.budget_used,spent)
        self.assertEqual(w.request['packet'],f['packet'].pk);self.assertEqual(w.status,'waiting',w.finding)
        self.assertEqual(ApprovalRequest.objects.filter(case=f['c']).count(),4)
        with self.assertRaises(DatabaseError),transaction.atomic():FactoryWork.objects.filter(pk=w.pk).update(source_head=f['packet'])

    def test_missing_profile_holds_execution_not_capture(self):
        f=setup(False);factory.run_until_wait(f['work'].pk);f['work'].refresh_from_db()
        self.assertEqual(f['work'].status,'configuration_needed');self.assertEqual(f['work'].budget_used,0)

    def test_restricted_source_and_invented_reviewer_rejected(self):
        f=setup(False)
        for values in [dict(f['profile_values'],required_evidence_kinds=['planning_packet']),dict(f['profile_values'],review_role='PM')]:
            with self.assertRaises(ValidationError):
                with transaction.atomic():
                    p=draft_operator_policy(f['a'],f['c'].pk,'OPS.factory_planning_execution',values,f['e']['policy_decision'].pk,timezone.now());transition(f['a'],p.pk,'validated')

    def test_forged_packet_and_premature_verified_status_rejected(self):
        f=setup();w=f['work']
        forged=evidence(f,'planning_packet',f['packet'].body)
        with self.assertRaises(DatabaseError),transaction.atomic():FactoryWork.objects.filter(pk=w.pk).update(source_head=forged)
        with self.assertRaises(DatabaseError),transaction.atomic():FactoryWork.objects.filter(pk=w.pk).update(status='verified')
        with self.assertRaises(ValidationError):factory_planning.start(f['a'],f['c'].pk,'FORGED',forged.pk,'forged',rev(f['c']))

    def test_private_projection_is_not_generic_evidence_or_timeline(self):
        f=setup();factory.run_until_wait(f['work'].pk)
        self.assertFalse(public_evidence(Evidence.objects.filter(case=f['c'])).filter(kind__startswith='planning_').exists())
        self.assertFalse(public_timeline(f['c']).filter(action__startswith='factory.').exists())
        from apps.agents.models import AgentRun
        for run in AgentRun.objects.filter(case=f['c'],provider='synthetic_factory_v1'):
            self.assertNotIn(run.evidence.kind,planning.KINDS.values());self.assertEqual(set(run.result),{'activity','citations'})
        self.client.force_login(f['a']);response=self.client.get(reverse('factory_detail',args=[f['work'].pk]))
        self.assertEqual(response.status_code,200)
        self.assertContains(response,'Department-owned decisions')
        Grant.objects.filter(case=f['c'],user=f['a'],action='planning.read').update(active=False)
        self.assertEqual(self.client.get(reverse('factory_detail',args=[f['work'].pk])).status_code,404)

    def test_history_does_not_disclose_another_department_through_investigation(self):
        f=setup();observe(f);factory.run_until_wait(f['work'].pk)
        run=FactoryAttempt.objects.get(activity__work=f['work'],activity__kind='ACT04',phase='observed')
        self.assertIn('readiness_inputs',run.result['investigation']) # The durable native fact is retained.
        self.client.force_login(f['owners']['scope'])
        response=self.client.get(reverse('factory_detail',args=[f['work'].pk]))
        self.assertEqual(response.status_code,200)
        self.assertNotContains(response,'readiness_inputs');self.assertNotContains(response,'owner_observations')
        self.assertContains(response,'Some department sources are outside your current access.')
        Grant.objects.filter(case=f['c'],user=f['a'],action='planning.coordinate').update(active=False)
        response=self.client.get(reverse('factory_detail',args=[f['work'].pk]))
        self.assertNotContains(response,f['packet'].body,html=False)
        self.assertContains(response,'current authority and provenance review')

    def test_malicious_activity_cannot_record_owner_acceptance(self):
        f=setup()
        class Malicious:
            def choose(self,context):return {'activity':'approval.observe','citations':context['evidence_ids'][:1]}
        factory.run_once(f['work'].pk,provider=Malicious());f['work'].refresh_from_db()
        self.assertEqual(f['work'].status,'blocked');self.assertFalse(DeliverySource.objects.filter(dossier__case=f['c']).exists())

    def test_planning_ui_and_profile_are_available_without_finance_grant(self):
        f=setup();Grant.objects.filter(case=f['c'],user=f['a'],action='finance.read').update(active=False)
        self.client.force_login(f['a'])
        for url,text in [(reverse('home')+'?queue=active','Start work'),(reverse('factory_create')+'?definition=planning/v1&case='+str(f['c'].pk),'Current planning packet'),(reverse('factory_configuration',args=[f['c'].pk])+'?definition=planning/v1','Planning and delivery handoff')]:
            response=self.client.get(url);self.assertContains(response,text);self.assertNotContains(response,'Case object (')

    def test_department_owner_sees_own_wait_in_primary_queue(self):
        f=setup();factory.run_until_wait(f['work'].pk)
        owner=f['owners']['scope'];self.client.force_login(owner)
        response=self.client.get(reverse('home')+'?queue=needs_me')
        self.assertContains(response,'Planning factory example');self.assertContains(response,'record your own observation')
        observe(f);response=self.client.get(reverse('home')+'?queue=decisions')
        self.assertNotContains(response,'Planning factory example')

    def test_lost_internal_route_response_reconciles_same_receipt_without_approval(self):
        f=setup();w=f['work']
        from adapters.approvals import InternalApprovalRoutingAdapter
        class Lost(InternalApprovalRoutingAdapter):
            def deliver(self,pk,fence):
                super().deliver(pk,fence);raise TimeoutError('Synthetic response lost after internal receipt')
        # Investigation, reservation, selected delivery loses its response.
        factory.run_once(w.pk);factory.run_once(w.pk);factory.run_once(w.pk,adapter=Lost())
        job=ApprovalRouteJob.objects.filter(request__case=f['c'],status='unknown').get()
        self.assertEqual(ApprovalRouteReceipt.objects.filter(job=job).count(),1)
        factory.run_until_wait(w.pk);job.refresh_from_db();w.refresh_from_db()
        self.assertEqual(job.status,'confirmed');self.assertEqual(w.status,'waiting',w.finding)
        self.assertEqual(ApprovalRouteReceipt.objects.filter(job=job).count(),1)
        self.assertFalse(DeliverySource.objects.filter(dossier__case=f['c']).exists())

    def test_changed_execution_profile_holds_native_request_before_delivery(self):
        f=setup();w=f['work'];factory.run_once(w.pk);factory.run_once(w.pk)
        job=ApprovalRouteJob.objects.filter(request__case=f['c']).first()
        values=dict(f['profile_values'],max_tokens=30000)
        p=draft_operator_policy(f['a'],f['c'].pk,'OPS.factory_planning_execution',values,f['e']['policy_decision'].pk,timezone.now())
        transition(f['a'],p.pk,'validated');transition(f['a'],p.pk,'active')
        from apps.pmo import approval_routing
        approval_routing.run_once(case_id=f['c'].pk,job_id=job.pk);job.refresh_from_db()
        self.assertEqual(job.status,'held');self.assertFalse(ApprovalRouteReceipt.objects.filter(job=job).exists())
        w.refresh_from_db();spent=w.budget_used
        factory.adopt_profile(f['a'],w.pk,w.revision,p.pk,'Synthetic reviewed execution profile successor')
        w.refresh_from_db();self.assertEqual(w.budget_used,spent);self.assertEqual(w.budget_limit,20000)

    def test_cancelled_factory_cannot_dispatch_reserved_department_requests(self):
        f=setup();w=f['work'];factory.run_once(w.pk);factory.run_once(w.pk);w.refresh_from_db()
        factory.manage(f['a'],w.pk,w.revision,'cancel')
        from apps.pmo import approval_routing
        for job in ApprovalRouteJob.objects.filter(request__case=f['c']):
            approval_routing.run_once(case_id=f['c'].pk,job_id=job.pk);job.refresh_from_db();self.assertEqual(job.status,'held')
        self.assertFalse(ApprovalRouteReceipt.objects.filter(job__request__case=f['c']).exists())

    def test_readiness_is_reprepared_after_criteria_successor_without_losing_history(self):
        f=setup();observe(f)
        old=planning.prepare(f['a'],f['c'].pk,f['packet'].pk)
        from tests.planning_helpers import criteria
        criteria(f,dict(f['rules'],alignment_max_age_seconds=f['rules']['alignment_max_age_seconds']+1))
        factory.run_until_wait(f['work'].pk);f['work'].refresh_from_db()
        self.assertEqual(f['work'].status,'verified',f['work'].finding)
        self.assertTrue(Evidence.objects.filter(pk=old.pk).exists())
        self.assertNotEqual(planning.latest(f['c'],'ready').pk,old.pk)

    def test_verified_handoff_detects_changed_sources_and_requires_reviewed_reassessment(self):
        f=setup();observe(f);w=f['work'];factory.run_until_wait(w.pk);w.refresh_from_db()
        self.assertEqual(w.status,'verified',w.finding);spent=w.budget_used
        with self.assertRaises(ValidationError):factory_planning.reassess(f['a'],w.pk,w.revision,'No changes')
        successor=planning.capture(f['a'],f['c'].pk,f['payload'],f['packet'].pk)
        self.client.force_login(f['a'])
        self.assertContains(self.client.get(reverse('home')+'?queue=exceptions'),'Prior handoff needs recheck')
        self.assertNotContains(self.client.get(reverse('home')+'?queue=verified'),'Planning factory example')
        self.assertNotContains(self.client.get(reverse('factory_detail',args=[w.pk])),'Current readiness evidence is recorded in delivery dossier')
        self.assertContains(self.client.get(reverse('factory_detail',args=[w.pk])),'Reassess changed planning evidence')
        factory_planning.reassess(f['a'],w.pk,w.revision,'Review exact successor planning packet')
        factory.run_until_wait(w.pk);w.refresh_from_db()
        self.assertEqual(w.source_head_id,successor.pk);self.assertEqual(w.status,'waiting',w.finding)
        self.assertGreater(w.budget_used,spent);self.assertEqual(w.budget_limit,20000)
        for purpose,meeting in f['meetings'].items():planning.align(f['a'],f['c'].pk,successor.pk,purpose,meeting.pk)
        f['pair']=planning.open_requests(f['a'],f['c'].pk,successor.pk);observe(f)
        factory.run_until_wait(w.pk);w.refresh_from_db();self.assertEqual(w.status,'verified',w.finding)
        self.assertEqual(DeliverySource.objects.filter(dossier__case=f['c']).count(),2)
        self.assertContains(self.client.get(reverse('home')+'?queue=verified'),'Planning factory example')
        self.assertEqual(FactoryWork.objects.filter(case=f['c']).count(),1)

from django.test import TransactionTestCase

class FactoryPlanningConcurrencyTests(TransactionTestCase):
    def test_two_connections_share_intake_and_one_claim(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier
        from django.db import close_old_connections
        from django.contrib.auth import get_user_model
        f=setup();barrier=Barrier(2)
        def intake(n):
            close_old_connections()
            try:
                actor=get_user_model().objects.get(pk=f['a'].pk);barrier.wait(timeout=10)
                return factory_planning.start(actor,f['c'].pk,'FORM-'+str(n),f['packet'].pk,'Same planning engagement',None).pk
            finally:close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:ids=list(pool.map(intake,[1,2]))
        self.assertEqual(ids,[f['work'].pk]*2)
        barrier=Barrier(2)
        def claim(n):
            close_old_connections()
            try:barrier.wait(timeout=10);return factory.claim(f['work'].pk)
            finally:close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:claims=list(pool.map(claim,[1,2]))
        self.assertEqual(sum(value is not None for value in claims),1)

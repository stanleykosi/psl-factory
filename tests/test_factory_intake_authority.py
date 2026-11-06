"""Fresh human instructions preserve original sources, money boundaries and spent allowance."""
import json
from datetime import timedelta
from pathlib import Path
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied,ValidationError
from django.db import DatabaseError,transaction
from django.test import TestCase,Client
from django.urls import reverse
from django.utils import timezone
from apps.core.models import Evidence,Audit
from apps.core.services import add_evidence,event
from apps.identity.models import Grant
from apps.policy.operator_drafts import draft_operator_policy
from apps.policy.services import transition
from apps.policy.factory_recovery_validators import COMPONENT,METHOD
from apps.workflows import factory,factory_delivery as delivery,factory_hypercare as hypercare,factory_execution
from apps.workflows.models import FactoryWork
from apps.agents.models import AgentRun
from tests.test_delivery import DeliveryFixture
from tests.test_factory_delivery import release_sources
from tests.helpers import rev


class IntakeAuthorityTests(TestCase):
    def setup_work(self,module):
        f=DeliveryFixture();f.setup_delivery()
        if module is delivery:release_sources(f)
        else:f.accepted();f.criteria();f.observations()
        value=json.loads(Path('fixtures/factory-delivery.json' if module is delivery else 'fixtures/factory-hypercare.json').read_text());value.pop('classification')
        config=draft_operator_policy(f.actor,f.case.pk,'OPS.factory_delivery_execution' if module is delivery else 'OPS.factory_hypercare_execution',value,f.e['policy_decision'].pk,timezone.now())
        transition(f.actor,config.pk,'validated');transition(f.actor,config.pk,'active')
        starter=get_user_model().objects.create_user(username='previous-intake-worker')
        for action in ['case.read','factory.read','factory.start','factory.execute','delivery.read','delivery.manage','agent.delivery','evidence.add']:
            Grant.objects.create(case=f.case,user=starter,action=action)
        f.work=module.start(starter,f.case.pk,'FRESH-INSTRUCTION',f.d.pk,'Project instruction recovery',rev(f.case));f.starter=starter
        self.assertTrue(factory.run_once(f.work.pk));f.work.refresh_from_db()
        self.assertGreater(f.work.budget_used,0);self.assertTrue(AgentRun.objects.filter(case=f.case,actor=starter).exists())
        return f

    def finish_with_current_worker(self,f):
        now=timezone.now()
        rule=dict(definition=f.work.definition,method=METHOD,principal_id=f.actor.pk,reviewer_id=f.actor.pk,
            review_role='PM',independent_of_worker=False,valid_from=now.isoformat(),valid_until=(now+timedelta(hours=1)).isoformat())
        config=draft_operator_policy(f.actor,f.case.pk,COMPONENT,{'rules':[rule]},f.e['policy_decision'].pk,now)
        transition(f.actor,config.pk,'validated');transition(f.actor,config.pk,'active')
        factory_execution.bind(f.actor,f.work.pk,f.work.revision,f.e['policy_decision'].pk,'Explicit synthetic current worker after source review')
        factory.run_until_wait(f.work.pk);f.work.refresh_from_db();self.assertEqual(f.work.status,'verified',f.work.finding)

    def check_reaffirmation(self,module):
        f=self.setup_work(module);work=f.work;head=work.source_head;spent=work.budget_used;limit=work.budget_limit
        Grant.objects.filter(case=f.case,user=f.starter,action='delivery.read').update(active=False)
        with self.assertRaises(PermissionDenied):delivery.subject(work,f.actor)
        delivery.subject(work,f.actor,current=False) # Explicit authorised historical reading is not current authority.
        self.client.force_login(f.actor)
        page=self.client.get(reverse('factory_detail',args=[work.pk]));self.assertContains(page,'Review project instruction')
        self.assertNotContains(page,'Continue eligible work')
        self.assertIn(work.pk,[r['work'].pk for r in self.client.get(reverse('home'),{'queue':'exceptions'}).context['rows']])
        _,packet=delivery.reaffirmation(f.actor,work);expected=work.revision;case_expected=rev(f.case)
        url=reverse('factory_intake_reaffirm',args=[work.pk]);self.assertEqual(self.client.get(url)['Cache-Control'],'no-store')
        self.assertEqual(Client(enforce_csrf_checks=True).post(url,{}).status_code,403)
        response=self.client.post(url,{'revision':expected,'case_revision':case_expected,'packet':packet,
            'evidence':f.e['requirements'].pk,'reason':'Current source owner reviewed the unchanged project and supplied a fresh instruction'})
        self.assertEqual(response.status_code,302,response.content[:300]);work.refresh_from_db()
        self.assertNotEqual(work.source_head_id,head.pk);self.assertEqual(work.source_head.body,head.body)
        self.assertEqual(work.actor_id,f.starter.pk);self.assertEqual(work.source_head.created_by_id,f.actor.pk)
        self.assertEqual(work.budget_used,spent);self.assertEqual(work.budget_limit,limit)
        self.assertEqual(Evidence.objects.get(pk=head.pk).created_by_id,f.starter.pk)
        self.assertTrue(Audit.objects.filter(case=f.case,action='factory.delivery_intake_reaffirmed',data__previous=head.pk).exists())
        delivery.subject(work,f.actor)
        with self.assertRaises(ValidationError):delivery.reaffirm(f.actor,work.pk,expected,case_expected,f.e['requirements'].pk,'Stale replay',packet)
        self.finish_with_current_worker(f)
        self.assertEqual(work.actor_id,f.starter.pk);self.assertGreater(work.budget_used,spent)
        self.assertEqual(module.verify(work,actor=f.actor)['head'],work.source_head_id)
        current=module.projection(f.actor,work);self.assertFalse(current['readiness_changed']);self.assertFalse(current['can_reaffirm'])
        self.assertTrue(current['intake_authority_current'])

    def test_release_instruction_recovery_to_current_native_readiness(self):self.check_reaffirmation(delivery)
    def test_hypercare_instruction_recovery_to_current_native_qualification(self):self.check_reaffirmation(hypercare)

    def test_current_authority_cannot_be_relabelled_and_sql_requires_fresh_review(self):
        f=self.setup_work(delivery);w=f.work
        with self.assertRaisesMessage(ValidationError,'still current'):delivery.reaffirmation(f.actor,w)
        Grant.objects.filter(case=f.case,user=f.starter,action='factory.start').update(active=False)
        self.assertFalse(delivery.projection(f.actor,w)['intake_authority_current'])
        with self.assertRaises(DatabaseError),transaction.atomic():
            e=add_evidence(f.actor,f.case.pk,delivery.KIND,w.source_head.body,'synthetic:forged-intake')
            event(f.actor,f.case,'factory.delivery_intake',evidence_id=e.pk,sha256=e.sha256)
            FactoryWork.objects.filter(pk=w.pk).update(source_head=e,status='ready')
        f.case.refresh_from_db();w.refresh_from_db()
        self.client.force_login(f.actor)
        self.assertIn(w.pk,[r['work'].pk for r in self.client.get(reverse('home'),{'queue':'exceptions'}).context['rows']])
        # Permission text, a current reader or an agent result cannot become a fresh instruction.
        Grant.objects.filter(case=f.case,user=f.actor,action='factory.start').update(active=False)
        with self.assertRaises(PermissionDenied):delivery.reaffirmation(f.actor,w)

    def test_stale_private_and_unqualified_instructions_hold_without_worker_or_history_changes(self):
        f=self.setup_work(delivery);w=f.work
        Grant.objects.filter(case=f.case,user=f.starter,action='factory.start').update(active=False)
        self.client.force_login(f.starter)
        self.assertNotContains(self.client.get(reverse('factory_detail',args=[w.pk])),'Continue eligible work')
        self.assertEqual(self.client.get(reverse('factory_intake_reaffirm',args=[w.pk])).status_code,403)
        _,packet=delivery.reaffirmation(f.actor,w);head=w.source_head_id;spent=w.budget_used
        expected_case=rev(f.case);f.evidence('requirements','Actual new project evidence after the displayed instruction')
        with self.assertRaises(ValidationError):delivery.reaffirm(f.actor,w.pk,w.revision,expected_case,f.e['requirements'].pk,'Stale displayed context',packet)
        w.refresh_from_db();_,packet=delivery.reaffirmation(f.actor,w)
        with self.assertRaises(ValidationError):delivery.reaffirm(f.actor,w.pk,w.revision,rev(f.case),f.e['requirements'].pk,'Changed displayed packet','0'*64)
        private=add_evidence(f.actor,f.case.pk,'agent_private_instruction','Synthetic unavailable private evidence','synthetic:private')
        w.refresh_from_db();_,packet=delivery.reaffirmation(f.actor,w)
        with self.assertRaisesMessage(ValidationError,'public project evidence'):
            delivery.reaffirm(f.actor,w.pk,w.revision,rev(f.case),private.pk,'Cannot publish private supporting evidence',packet)
        with self.assertRaises(ValidationError):delivery.reaffirm(f.actor,w.pk,True,rev(f.case),f.e['requirements'].pk,'Boolean is not a work revision',packet)
        w.refresh_from_db();self.assertEqual(w.source_head_id,head);self.assertEqual(w.budget_used,spent)
        self.assertFalse(Audit.objects.filter(case=f.case,action='factory.delivery_intake_reaffirmed').exists())

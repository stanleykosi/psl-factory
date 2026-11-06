"""Planning contracts grant neither private-data access nor another operator's authority."""
import json
from pathlib import Path
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from apps.core.services import add_evidence
from apps.identity.models import Grant
from apps.policy.readiness_drafts import draft_readiness_policy
from apps.policy.services import transition
from apps.workflows import factory
from apps.workflows.models import FactoryAttempt,FactoryPlanningReceipt
from apps.finance.models import FinanceRun
from tests.factory_coordinator_helpers import gateway
from tests.readiness_helpers import endpoint


class FactoryPlannerBoundaryTests(TestCase):
    def test_planning_contract_cannot_validate_private_extraction_policy(self):
        with endpoint() as state:
            f=gateway(state,prefix='private-boundary')
            rules=json.loads(Path('fixtures/agent-data.json').read_text())['rules']
            rules.update(contract_id=f['contract'].pk,evidence_ids=[f['source'].evidence_id],
                sender_id=f['actor'].pk,reviewer_id=f['actor'].pk)
            policy=draft_readiness_policy(f['actor'],f['case'].pk,'INT.agent_data',rules,
                f['evidence']['policy_decision'].pk,timezone.now())
            with self.assertRaisesMessage(ValidationError,'Planning-only protocol cannot authorise private evidence extraction'):
                transition(f['actor'],policy.pk,'validated')
            self.assertEqual(policy.states.latest('pk').state,'draft')
            self.assertEqual(state.get('private_inputs',[]),[])
            self.assertEqual(state.get('planning_calls',0),0)

    def test_execute_grant_does_not_allow_nonowner_to_advance_another_operators_work(self):
        with endpoint() as state:
            f=gateway(state,prefix='owner-boundary');work=f['work']
            other=get_user_model().objects.create_user(username='other-accounting-executor')
            Grant.objects.bulk_create([Grant(case=f['case'],user=other,action=action)
                for action in ['case.read','finance.read','factory.read','factory.execute']])
            self.client.force_login(other);url=reverse('factory_detail',args=[work.pk])
            self.assertEqual(self.client.get(url).status_code,200)
            before=work.revision
            self.assertEqual(self.client.post(url,{'action':'advance','revision':before}).status_code,403)
            work.refresh_from_db();self.assertEqual(work.revision,before);self.assertEqual(work.budget_used,0)
            self.assertEqual(state.get('planning_calls',0),0);self.assertFalse(FinanceRun.objects.exists())

    def test_recovered_plan_is_retired_when_current_native_context_has_changed(self):
        with endpoint() as state:
            f=gateway(state,prefix='context-boundary');work=f['work'];state['lose_planning_response']=True
            factory.run_once(work.pk);work.refresh_from_db();spent=work.budget_used
            add_evidence(f['actor'],f['case'].pk,'factory_information','New source observation after uncertain planning','synthetic:context-change')
            self.assertTrue(factory.run_once(work.pk)) # Original receipt only.
            self.assertTrue(factory.run_once(work.pk)) # Retire stale choice, execute nothing.
            work.refresh_from_db();self.assertEqual(work.budget_used,spent)
            self.assertEqual(state['planning_calls'],1);self.assertEqual(FactoryPlanningReceipt.objects.count(),1)
            self.assertTrue(FactoryAttempt.objects.filter(phase='failed',result__reason__startswith='Current native context changed').exists())
            self.assertFalse(FinanceRun.objects.exists())

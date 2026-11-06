"""A real expired coordination claim is reclaimed without fabricating a human wait."""
from copy import deepcopy
from time import sleep
from django.test import TransactionTestCase
from django.utils import timezone
from apps.agents.factory_catalogue import SyntheticFactoryCoordinator
from apps.agents.models import AgentRun
from apps.documents.models import PublicationReceipt
from apps.pmo.models import RFPResponse
from apps.workflows import factory
from apps.workflows.models import FactoryWork,FactoryAttempt
from tests import factory_rfp_helpers as helpers


class FactoryRFPWorkerExpiryTests(TransactionTestCase):
    def test_supervisor_reclaims_real_expired_worker_then_stops_at_actual_source_wait(self):
        data=helpers.configured();payload=deepcopy(data['payload']);payload['response_evidence']=None
        work=helpers.start(data,payload=payload);original_head=work.source_head_id;starter=work.actor_id
        class ExpireFirstDecision(SyntheticFactoryCoordinator):
            calls=0
            expired_fence=None
            initial_spent=None
            def choose(self,context):
                self.calls+=1
                if self.calls==1:
                    claimed=FactoryWork.objects.get(pk=work.pk)
                    self.expired_fence=claimed.fence;self.initial_spent=claimed.budget_used
                    # Native configured lease actually elapses; no DB timestamp is edited.
                    sleep(max(0,(claimed.lease_until-timezone.now()).total_seconds())+.2)
                return super().choose(context)
        provider=ExpireFirstDecision()
        factory.run_until_wait(work.pk,provider=provider);work.refresh_from_db()
        self.assertGreaterEqual(provider.calls,2)
        self.assertGreater(work.fence,provider.expired_fence)
        self.assertEqual(work.status,'waiting',work.finding);self.assertIsNone(work.lease_until)
        self.assertIn('Select the response',work.finding)
        self.assertEqual(work.source_head_id,original_head);self.assertEqual(work.actor_id,starter)
        self.assertGreater(work.budget_used,provider.initial_spent);self.assertEqual(work.budget_limit,30000)
        self.assertEqual(AgentRun.objects.filter(case=data['case'],provider='deterministic-rfp-investigation-v1').count(),1)
        self.assertFalse(FactoryAttempt.objects.filter(activity__work=work,phase='observed',fence=provider.expired_fence).exists())
        self.assertFalse(RFPResponse.objects.exists());self.assertFalse(PublicationReceipt.objects.exists())

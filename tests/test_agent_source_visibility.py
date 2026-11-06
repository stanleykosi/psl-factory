from django.test import TestCase
from django.urls import reverse
from apps.core.services import add_evidence
from apps.agents.models import AgentRun
from apps.identity.models import Grant
from tests.helpers import setup_case

class AgentSourceVisibilityTests(TestCase):
    def test_generic_workspace_excludes_private_domain_runs_but_retains_public_runs(self):
        actor,case=setup_case(username='agent-visibility-human')
        # Durable domain records are fixtures; the reader is the actual authenticated UI.
        for kind,marker in [('requirements','VISIBLE_PUBLIC_AGENT_RESULT'),('p14_inputs','RESTRICTED_COSTING_AGENT_RESULT'),('planning_packet','RESTRICTED_PLANNING_AGENT_RESULT'),('agent_private_commercial_intake','RESTRICTED_COMMERCIAL_AGENT_RESULT')]:
            e=add_evidence(actor,case.pk,kind,'Synthetic source for reader isolation: '+marker,'synthetic:agent-source-visibility')
            AgentRun.objects.create(case=case,actor=actor,evidence=e,process_id='P14',provider='synthetic-domain-reader-fixture',result={'facts':[{'quote':marker,'evidence_id':e.pk,'version':e.version}],'uncertainties':[]})
        self.client.force_login(actor)
        response=self.client.get(reverse('case',args=[case.pk]))
        self.assertEqual(response.status_code,200)
        self.assertContains(response,'VISIBLE_PUBLIC_AGENT_RESULT')
        for marker in ['RESTRICTED_COSTING_AGENT_RESULT','RESTRICTED_PLANNING_AGENT_RESULT','RESTRICTED_COMMERCIAL_AGENT_RESULT']:self.assertNotContains(response,marker)
        self.assertEqual(AgentRun.objects.filter(case=case).count(),4)

    def test_agent_extract_does_not_replace_case_or_current_reader_access(self):
        actor,case=setup_case(username='agent-visibility-revoked')
        self.client.force_login(actor)
        Grant.objects.filter(case=case,user=actor,action='case.read').update(active=False)
        self.assertEqual(self.client.get(reverse('case',args=[case.pk])).status_code,404)

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.urls import reverse

from apps.pmo import delivery
from apps.pmo.models import GateRecord
from apps.workflows import factory, factory_delivery
from apps.workflows.models import FactoryWork
from tests.helpers import rev
from tests.railway_project_delivery_seed import prepare


class ProjectDeliveryWalkthroughTests(TestCase):
    def setUp(self):
        self.assertEqual(connection.vendor, 'postgresql')
        self.reviewer = get_user_model().objects.create_user('sample-project-delivery-reviewer')

    def test_missing_planning_owner_then_distinct_reviewer_with_exact_sources(self):
        sample = prepare(self.reviewer, 'planning')
        work = FactoryWork.objects.select_related('case', 'actor').get(pk=sample['work'])
        self.assertNotEqual(work.actor, self.reviewer)
        dossier = delivery.dossier_for(work.case, sample['dossier'])
        self.assertEqual(set(delivery.planning_inputs(dossier)['sources']), set(delivery.PLANNING))
        self.assertEqual(factory_delivery.planning_owners(work.case), [])
        self.assertIsNone(delivery.latest(dossier, 'planning_decision', False))

        self.client.force_login(self.reviewer)
        url = sample['decision_path']
        waiting = self.client.get(url)
        self.assertContains(waiting, 'Planning approver needed')
        self.assertContains(waiting, 'Unassigned')
        self.assertNotContains(waiting, 'Approve exact Planning exit')

        for transition in ('validated', 'active'):
            response = self.client.post(sample['case_policy_path'], {
                'action': transition, 'configuration': sample['role_draft'],
            })
            self.assertRedirects(response, sample['case_policy_path'], fetch_redirect_response=False)
        self.assertEqual(factory_delivery.planning_owners(work.case), [self.reviewer.pk])
        self.assertContains(self.client.get(url), 'Approve exact Planning exit')

        decision = {'action': 'delivery_decision', 'verdict': 'approve', 'revision': work.revision,
                    'case_revision': rev(work.case), 'evidence': sample['planning_evidence'],
                    'packet': factory_delivery.projection(self.reviewer, work)['decision_packet'],
                    'note': 'Independently reviewed the current sample Planning sources.'}
        self.client.force_login(work.actor)
        self.assertNotContains(self.client.get(url), 'Approve exact Planning exit')
        self.assertContains(self.client.post(url, decision), 'current exact Planning exit sources and authority')
        self.assertIsNone(delivery.latest(dossier, 'planning_decision', False))

        self.client.force_login(self.reviewer)
        self.assertContains(self.client.post(url, decision | {'packet': '0' * 64}),
                            'current exact Planning exit sources and authority')
        self.assertIsNone(delivery.latest(dossier, 'planning_decision', False))
        self.assertRedirects(self.client.post(url, decision), url, fetch_redirect_response=False)
        accepted = delivery.approved_plan(dossier)
        self.assertEqual((accepted.actor, accepted.evidence_id), (self.reviewer, sample['planning_evidence']))
        self.assertEqual(accepted.snapshot, delivery.planning_inputs(dossier))
        self.assertIsNone(delivery.latest(dossier, 'release_ready', False))
        self.assertIsNone(delivery.latest(dossier, 'release_outcome', False))
        self.assertTrue(prepare(self.reviewer, 'planning')['existing_work_preserved'])
        self.assertEqual(delivery.approved_plan(dossier).pk, accepted.pk)

    def test_glpi_gate_stops_readiness_until_exact_approval_is_verified(self):
        sample = prepare(self.reviewer, 'glpi')
        work = FactoryWork.objects.select_related('case').get(pk=sample['work'])
        dossier = delivery.dossier_for(work.case, sample['dossier'])
        public = factory_delivery.projection(self.reviewer, work)
        self.assertEqual(public['checks']['planning_decision']['status'], 'ready')
        self.assertIn('glpi_ceo', public['checks']['release_evidence']['finding'])
        self.assertIsNone(delivery.latest(dossier, 'release_ready', False))

        self.client.force_login(self.reviewer)
        url = reverse('factory_detail', args=[work.pk])
        self.assertContains(self.client.get(url), 'Link the actual GLPI request and its current deployment approvals')
        documents = reverse('documents', args=[work.case_id])
        page = self.client.get(documents)
        self.assertContains(page, 'Capture owning-team gate evidence')
        self.assertContains(page, 'Record source reference')
        gate_form = page.context['gate_form']
        for name in ('candidate', 'kind', 'external_ref', 'evidence'):
            self.assertContains(page, f'id="{gate_form[name].id_for_label}"', count=1)
        self.assertEqual(list(gate_form.fields['candidate'].queryset.values_list('pk', flat=True)), [sample['candidate']])
        self.assertIn('glpi_ceo', dict(gate_form.fields['kind'].choices))
        self.assertTrue(gate_form.fields['evidence'].queryset.filter(pk=sample['gate_evidence']).exists())
        capture = {'action': 'gate', 'candidate': sample['candidate'], 'kind': 'glpi_ceo',
                   'external_ref': sample['release_reference'], 'evidence': sample['gate_evidence'],
                   'revision': rev(work.case)}
        self.assertRedirects(self.client.post(documents, capture), documents, fetch_redirect_response=False)
        gate = GateRecord.objects.get(candidate=dossier.candidate, kind='glpi_ceo')
        self.assertEqual((gate.external_ref, gate.evidence_id, gate.source_owner),
                         (sample['release_reference'], sample['gate_evidence'], 'CEO'))
        self.assertFalse(gate.verifications.exists())
        reported = self.client.get(documents)
        self.assertContains(reported, f'glpi_ceo · {sample["release_reference"]} · CEO')
        self.assertContains(reported, 'Verify owning-source record (synthetic adapter)')
        factory.run_until_wait(work.pk)
        self.assertIsNone(delivery.latest(dossier, 'release_ready', False))
        self.assertContains(self.client.get(url), 'Link the actual GLPI request and its current deployment approvals')

        verify = {'action': 'gate_verify', 'record': gate.pk, 'revision': rev(work.case)}
        self.assertRedirects(self.client.post(documents, verify), documents, fetch_redirect_response=False)
        self.assertEqual(gate.verifications.get().result['decision'], 'accepted')
        factory.run_until_wait(work.pk)
        work.refresh_from_db()
        self.assertEqual(work.status, 'verified', work.finding)
        readiness = factory_delivery.prepared(work)
        self.assertIn(gate.pk, [pair[0] for pair in readiness.snapshot['glpi']])
        self.assertContains(self.client.get(url), f'Release readiness record {readiness.pk} is retained')
        self.assertFalse(readiness.snapshot['deployment_authorized'])
        self.assertIsNone(delivery.latest(dossier, 'release_outcome', False))

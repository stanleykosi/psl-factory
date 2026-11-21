from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.urls import reverse

from apps.core.models import Case, Evidence
from apps.documents.models import Publication, Version
from apps.pmo.models import CommercialDocumentBinding
from apps.workflows.models import HumanTask
from tests.helpers import rev
from tests.railway_sow_review_seed import CORRECTED, ORIGINAL, TRIAL, prepare, proposal


class StandaloneSOWReviewTests(TestCase):
    def setUp(self):
        self.trial = get_user_model().objects.create_user(TRIAL)

    def review(self, prepared, case, verb, note):
        self.client.force_login(self.trial)
        return self.client.post(prepared['url'], {'action': 'review', 'revision': rev(case),
                                                  'verdict': f'{verb}:0', 'note': note})

    def test_trial_compares_and_approves_exact_statement_without_delivery(self):
        self.assertEqual(connection.vendor, 'postgresql')
        prepared = prepare('approve')
        case = Case.objects.get(pk=prepared['case'])
        self.assertEqual(prepared['task_status'], 'open')
        self.client.force_login(self.trial)
        compare = self.client.get(prepared['url'] + '?compare=1')
        self.assertContains(compare, 'Statement of work · v2')
        self.assertContains(compare, 'Current template verified')
        self.assertContains(compare, 'Current approved costing')
        self.assertContains(compare, 'Both drafts use the same costing evidence.')
        self.assertContains(compare, 'Waiting for PMO Lead review.')
        self.assertContains(compare, '<dt>Before</dt>', html=True)
        self.assertContains(compare, ORIGINAL)
        self.assertContains(compare, CORRECTED)
        self.assertContains(self.client.get(prepared['previous']), 'SAMPLE original wording needs the handover detail')
        self.assertContains(self.client.get(reverse('commercial', args=[case.pk])), prepared['url'])
        wrong_effect = self.client.post(prepared['url'], {'action': 'publish', 'revision': rev(case)})
        self.assertEqual(wrong_effect.status_code, 400)
        self.assertFalse(Publication.objects.filter(version__document__case=case).exists())
        self.assertRedirects(self.review(prepared, case, 'approve', 'SAMPLE exact version checked'), prepared['url'])
        self.assertContains(self.client.get(prepared['url']), 'SAMPLE exact version checked')
        confirmed = prepare('approve')
        self.assertEqual(confirmed['task_status'], 'completed')
        self.assertTrue(confirmed['preserved'])
        self.assertFalse(Publication.objects.filter(version__document__case=case).exists())

    def test_return_proof_survives_a_corrected_source_version_and_fresh_review(self):
        prepared = prepare('return')
        case = Case.objects.get(pk=prepared['case'])
        self.assertRedirects(self.review(prepared, case, 'return', 'SAMPLE check the exact checklist label'), prepared['url'])
        self.assertContains(self.client.get(prepared['url']), 'Returned to the project manager')
        self.assertContains(self.client.get(prepared['url']), 'SAMPLE check the exact checklist label')
        other = prepare('approve')
        alien = reverse('design_sow_review', args=[case.pk, other['version']])
        self.assertEqual(self.client.get(alien).status_code, 404)
        owner = get_user_model().objects.get(pk=prepared['preparer'])
        original = CommercialDocumentBinding.objects.get(version_id=prepared['version'])
        proof = {kind: Evidence.objects.get(pk=ref, case=case) for kind, ref in original.revision.sources.items()}
        revised = 'SAMPLE: deliver for the same clinic and include the signed-off printed handover checklist.'
        candidate = proposal(owner, case, proof, revised)
        self.assertEqual(self.client.post(prepared['url'], {'action': 'prepare', 'revision': rev(case),
                                                            'proposal': candidate.pk}).status_code, 400)
        self.client.force_login(owner)
        self.assertContains(self.client.get(prepared['url']), 'Prepare the corrected version')
        prepare_post = self.client.post(prepared['url'], {'action': 'prepare', 'revision': rev(case),
                                                         'proposal': candidate.pk})
        successor = Version.objects.get(commercialdocumentbinding__revision=candidate)
        self.assertEqual(successor.number, 3)
        successor_url = reverse('design_sow_review', args=[case.pk, successor.pk])
        self.assertRedirects(prepare_post, successor_url)
        self.assertFalse(successor.reviews.exists())
        self.assertFalse(HumanTask.objects.filter(version=successor).exists())
        self.assertEqual(self.client.post(successor_url, {'action': 'request', 'revision': rev(case)}).status_code, 302)
        self.client.force_login(self.trial)
        review_page = self.client.get(successor_url + '?compare=1')
        self.assertContains(review_page, 'Waiting for PMO Lead review.')
        self.assertContains(review_page, CORRECTED)
        self.assertContains(review_page, revised)
        self.assertContains(self.client.get(prepared['url']), 'SAMPLE check the exact checklist label')
        self.assertFalse(Publication.objects.filter(version__document__case=case).exists())

"""Both native closure gates honor the selected template's required review."""

from django.db import connection
from django.test import TestCase
from django.urls import reverse

from apps.documents.controlled import request_review, review_version
from apps.identity.models import Grant
from apps.pmo import delivery_closure
from apps.pmo.delivery_documents import draft_delivery_document
from tests.helpers import rev
from tests.test_factory_closure import setup


class NativeClosureReviewGateTests(TestCase):
    def test_delivery_workbench_requires_current_exact_document_review(self):
        self.assertEqual(connection.vendor, 'postgresql')
        fixture = setup(review=True, capture=False)
        actor, case, dossier = fixture.actor, fixture.case, fixture.d
        inputs = {name: fixture.inputs[name] for name in ('retrospective_id', 'report_evidence_id')}
        url = reverse('delivery', args=[case.pk])
        self.client.force_login(actor)

        def draft(data, previous=None):
            return draft_delivery_document(actor, case.pk, dossier.pk, 'closure', fixture.inputs['template_id'], data,
                                           rev(case), previous_version_id=previous)

        def approve_document(version):
            request_review(actor, case.pk, version.pk, rev(case))
            review_version(actor, case.pk, version.pk, 'approve', 'Reviewed this exact sample closure report.', rev(case))

        def approve_closure(version):
            return self.client.post(url, {'action': 'closure_decision', 'dossier': dossier.pk, 'version': version.pk,
                                          'verdict': 'approve', 'evidence': fixture.e['requirements'].pk,
                                          'note': 'Head of PMO checked the exact sample closure packet.',
                                          'revision': rev(case)})

        def finish():
            return self.client.post(url, {'action': 'close', 'dossier': dossier.pk, 'revision': rev(case)})

        original = draft(inputs)
        decisions = dossier.records.filter(kind='closure_decision')
        closures = dossier.records.filter(kind='closure')
        self.assertContains(approve_closure(original), 'approval of this exact outward projection is required')
        self.assertFalse(decisions.exists())
        self.assertFalse(closures.exists())

        approve_document(original)
        self.assertRedirects(approve_closure(original), url, fetch_redirect_response=False)
        prior = decisions.get()
        quality_grant = Grant.objects.filter(case=case, user=actor, action='document.review_controlled')
        self.assertEqual(quality_grant.update(active=False), 1)
        self.assertEqual(delivery_closure.closure_inputs(dossier, inputs), prior.snapshot)
        self.assertEqual(approve_closure(original).status_code, 403)
        self.assertEqual(finish().status_code, 403)
        self.assertFalse(closures.exists())
        self.assertEqual(decisions.get().pk, prior.pk)
        quality_grant.update(active=True)

        replacement_evidence = fixture.evidence('closure_report', 'A revised synthetic closure report with corrected lessons.')
        successor = draft(dict(inputs, report_evidence_id=replacement_evidence.pk), previous=original.pk)
        self.assertContains(approve_closure(original), 'A newer document revision is current')
        self.assertContains(finish(), 'A newer document revision is current')
        self.assertContains(approve_closure(successor), 'approval of this exact outward projection is required')
        self.assertFalse(closures.exists())

        approve_document(successor)
        self.assertRedirects(approve_closure(successor), url, fetch_redirect_response=False)
        self.assertRedirects(finish(), url, fetch_redirect_response=False)
        self.assertEqual(closures.get().data['version_id'], successor.pk)
        self.assertEqual(decisions.count(), 2)
        self.assertTrue(decisions.filter(pk=prior.pk, data__version_id=original.pk).exists())

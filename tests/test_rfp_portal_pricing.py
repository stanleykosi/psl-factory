import json

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.core.services import add_evidence
from apps.documents.controlled import reserve_publication
from apps.documents.models import Publication
from apps.pmo import rfp, rfp_followup, rfp_portal, rfp_pricing
from apps.workflows import factory, factory_rfp
from tests import factory_rfp_helpers as helpers
from tests.helpers import rev


class PortalPricingTests(TestCase):
    def test_portal_does_not_dispatch_and_comparison_survives_verified_route(self):
        f = helpers.configured(portal=True)
        actor, case = f['actor'], f['case']
        quote = add_evidence(actor, case.pk, 'rfp_commercial_terms', json.dumps({
            'schema': rfp_pricing.QUOTE, 'terms': 'Synthetic priced service', 'amount': '100.00',
            'currency': 'NGN', 'basis': 'whole_contract'}), 'synthetic:reviewed-quote')
        f['payload']['public_terms'] = quote.pk
        work = helpers.start(f)
        response, version = helpers.reviewed_document(f, work)
        factory.run_until_wait(work.pk)
        self.assertFalse(Publication.objects.exists())
        with self.assertRaisesMessage(ValidationError, 'manual client portal'):
            reserve_publication(actor, case.pk, version.pk, rev(case))

        receipt = {'schema': rfp_portal.SCHEMA, 'version': version.pk, 'sha256': version.payload_sha256,
                   'destination': f['route']['destination_ref'], 'reference': 'PORTAL-01',
                   'received_at': timezone.now().isoformat()}
        wrong = add_evidence(actor, case.pk, 'rfp_portal_receipt', json.dumps({**receipt, 'sha256': 'wrong'}), 'synthetic:wrong-receipt')
        with self.assertRaisesMessage(ValidationError, 'matching the exact approved pack'):
            rfp_portal.record(actor, case.pk, version.pk, wrong.pk, 'Sample operator check', rev(case))
        evidence = add_evidence(actor, case.pk, 'rfp_portal_receipt', json.dumps(receipt), 'synthetic:portal-receipt')
        from apps.pmo.models import RFPSubmission

        self.client.force_login(actor)
        api = f'/api/v1/work/{work.pk}'
        portal = api + '/bid-pack/portal-receipt'
        options = self.client.get(portal).json()
        self.assertTrue(options['ready'])
        self.assertEqual(options['version_id'], version.pk)
        payload = {'case_revision': options['case_revision'], 'version_id': version.pk,
                   'evidence_id': evidence.pk, 'attestation': 'Sample operator check'}
        rejected = self.client.post(portal, {**payload, 'evidence_id': wrong.pk}, content_type='application/json')
        self.assertEqual(rejected.status_code, 422, rejected.content)
        saved = self.client.post(portal, payload, content_type='application/json')
        self.assertEqual(saved.status_code, 201, saved.content)
        submission = RFPSubmission.objects.get(pk=saved.json()['submission_id'])
        self.assertEqual(self.client.get(portal).json()['receipt']['id'], submission.portal_receipt.pk)
        self.assertEqual(submission.receipt_ids, [])
        self.assertEqual(rfp_portal.record(actor, case.pk, version.pk, evidence.pk, 'Sample operator check', rev(case)), submission)
        moment = timezone.now()
        pending = rfp.outcome(actor, case.pk, submission.pk, 'unknown', moment, 'Client', None,
                              'Sample no-reply check', rev(case), followup_on=timezone.localdate(moment))
        self.assertEqual(len(list(rfp_followup.reminders(actor))), 1)
        draft = rfp_followup.draft(actor,case.pk,pending.pk,rev(case))
        self.assertEqual(rfp_followup.draft(actor,case.pk,pending.pk,rev(case)), draft)
        rfp_followup.review(actor,case.pk,pending.pk,draft.pk,'Reviewed sample follow-up',0,rev(case))
        self.assertEqual(rfp_followup.panel(actor,case,pending)['text'], 'Reviewed sample follow-up')
        award = add_evidence(actor, case.pk, 'rfp_outcome', json.dumps({
            'schema': rfp_pricing.AWARD, 'submission': submission.pk, 'amount': '101.25',
            'currency': 'NGN', 'basis': 'whole_contract'}), 'synthetic:award')
        with self.assertRaisesMessage(ValidationError, 'must match the selected award proof'):
            rfp.outcome(actor, case.pk, submission.pk, 'won', timezone.now(), 'Client', award.pk,
                        'Actual synthetic award', rev(case), award_amount='100.00', award_currency='NGN')
        rfp.outcome(actor, case.pk, submission.pk, 'won', timezone.now(), 'Client', award.pk,
                    'Actual synthetic award', rev(case), award_amount='101.25', award_currency='NGN')
        factory.run_until_wait(work.pk)
        work.refresh_from_db()
        self.assertEqual(work.status, 'verified', work.finding)
        self.assertEqual(factory_rfp.verify(work)['portal_receipt'], submission.portal_receipt.pk)
        self.assertFalse(Publication.objects.exists())
        decision = self.client.get(api + '/bid-outcomes', {'submission_id': submission.pk}).json()
        self.assertEqual(decision['outcome']['id'], decision['handoff']['outcome_id'])
        self.assertEqual(decision['outcome']['comparison']['quote_amount'], '100.00')
        self.assertEqual(decision['outcome']['comparison']['quote_currency'], 'NGN')
        self.assertEqual(list(rfp_followup.reminders(actor)), [])
        self.assertIsNone(rfp_followup.panel(actor,case,pending))
        self.client.force_login(actor)
        page = self.client.get(reverse('factory_work_response', args=[work.pk]))
        self.assertContains(page, 'PORTAL-01')
        self.assertContains(page, 'The award differs from the reviewed submitted quote.')
        self.assertContains(page, 'NGN 100.00')
        self.assertContains(page, 'NGN 101.25')

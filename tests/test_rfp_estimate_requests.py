import json
from datetime import timedelta
from hashlib import sha256
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.db import DatabaseError, transaction
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from adapters.rfp_estimate_requests import receipt_fields
from apps.agents import assistant
from apps.agents.models import CaseUpload
from apps.core.evidence_access import public_evidence
from apps.core.services import add_evidence
from apps.pmo import rfp, rfp_estimate_model, rfp_estimate_requests as service
from apps.pmo.models import RFPEstimateDispatch, RFPEstimateMailbox, RFPEstimateReceipt, RFPSubmission
from apps.policy.operator_drafts import draft_operator_policy
from apps.policy.rfp_estimate_request_validators import COMPONENT
from apps.policy.services import transition
from tests import factory_rfp_helpers
from tests.helpers import rev


class RFPEstimateRequestTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.sample = factory_rfp_helpers.configured(include_security=False)
        cls.work = factory_rfp_helpers.start(cls.sample)
        cls.actor, cls.case = cls.work.actor, cls.work.case
        cls.evidence = cls.sample['evidence']['policy_decision']
        cls.path = reverse('factory_rfp_security_estimate', args=[cls.work.pk])

    def configure(self, method='synthetic_mailbox', *, channel='email', destination='security@example.invalid', attachment=False):
        value = {'routes': [{'channel': channel, 'contact': 'Sample Security', 'destination': destination,
                            'method': method, 'allow_attachment': attachment}]}
        cfg = draft_operator_policy(self.actor, self.case.pk, COMPONENT, value, self.evidence.pk, timezone.now())
        transition(self.actor, cfg.pk, 'validated')
        transition(self.actor, cfg.pk, 'active')
        return cfg

    def prepared(self):
        return service.prepare(self.actor, self.work.pk, rev(self.case))

    def review(self, draft, *, channel='email'):
        return service.review(self.actor, self.work.pk, rev(self.case), draft.pk, channel,
                              timezone.localdate()+timedelta(days=1), 'Human-edited sample estimate request', self.evidence.pk)

    def test_unknown_estimate_can_be_drafted_without_contact_and_released_after_human_review(self):
        self.client.force_login(self.actor)
        page = self.client.get(self.path)
        self.assertContains(page, 'Owner needed')
        self.assertContains(page, 'Record an estimate that has arrived')
        self.assertContains(self.client.get(reverse('factory_rfp_pricing', args=[self.work.pk])), 'Ask Security for an estimate')
        self.assertContains(self.client.post(self.path, {'action': 'prepare', 'revision': rev(self.case)}, follow=True), 'Prepared draft')
        draft = self.prepared()
        self.assertFalse(public_evidence(self.case.evidence.filter(pk=draft.evidence_id)).exists())
        with self.assertRaisesMessage(ValidationError, 'reviewed Security contact'):
            self.review(draft)
        self.configure()
        post = {'action': 'review', 'revision': rev(self.case), 'draft': draft.pk, 'channel': 'email',
                'due_on': timezone.localdate().isoformat(), 'body': 'Human-edited sample estimate request',
                'evidence': self.evidence.pk}
        self.assertContains(self.client.post(self.path, post, follow=True), 'Release reviewed request')
        self.assertFalse(RFPEstimateDispatch.objects.exists())
        reviewed = self.work.estimate_requests.get()
        result = {'action': 'release', 'revision': rev(self.case), 'request': reviewed.pk}
        self.assertContains(self.client.post(self.path, result, follow=True), 'Delivery confirmed')
        dispatch = RFPEstimateDispatch.objects.get()
        self.assertEqual(dispatch.request.payload['body'], post['body'])
        self.assertEqual(RFPEstimateMailbox.objects.get().sha256, reviewed.sha256)
        self.assertEqual(RFPEstimateReceipt.objects.get().reference, dispatch.mailbox.reference)
        self.assertEqual(service.release(self.actor, self.work.pk, rev(self.case), reviewed.pk).pk, dispatch.pk)
        with self.assertRaises(DatabaseError), transaction.atomic():
            RFPEstimateReceipt.objects.filter(dispatch=dispatch).update(reference='changed')
        self.assertFalse(RFPSubmission.objects.exists())
        root = rfp.root(self.case)
        self.assertFalse(root.current_intake.contributions.filter(team='Security').exists())
        rfp.contribute(self.actor, self.case.pk, 'Security', self.sample['evidence']['security_estimate'].pk, rev(self.case))
        self.assertContains(self.client.get(self.path), 'Delivery confirmed')
        with self.assertRaisesMessage(ValidationError, 'estimate is already recorded'):
            self.prepared()

    def test_api_missing_estimate_review_and_synthetic_delivery_receipt(self):
        self.client.force_login(self.actor)
        url = f'/api/v1/work/{self.work.pk}/bid-pricing'
        pricing = self.client.get(url)
        self.assertEqual(pricing.status_code, 200, pricing.content)
        self.assertTrue(pricing.json()['security_estimate_missing'])
        estimate = f'/api/v1/work/{self.work.pk}/security-estimate'
        page = self.client.get(estimate)
        self.assertEqual(page.status_code, 200, page.content)
        self.assertEqual(page.json()['channels'], [])
        created = self.client.post(estimate, {'action': 'prepare', 'case_revision': page.json()['case_revision']},
                                   content_type='application/json')
        self.assertEqual(created.status_code, 201, created.content)
        self.configure()
        selected = self.client.get(estimate).json()
        values = {'action': 'review', 'case_revision': selected['case_revision'], 'draft_id': selected['draft_id'],
                  'channel': 'email', 'due_on': timezone.localdate().isoformat(), 'body': 'Synthetic Security scope request.',
                  'evidence_id': self.evidence.pk, 'attachment_id': None, 'model_turn_id': None}
        reviewed = self.client.post(estimate, values, content_type='application/json')
        self.assertEqual(reviewed.status_code, 201, reviewed.content)
        self.assertFalse(RFPEstimateDispatch.objects.exists())
        sent = self.client.post(estimate, {'action': 'release', 'case_revision': reviewed.json()['case_revision'],
            'request_id': reviewed.json()['id']}, content_type='application/json')
        self.assertEqual(sent.status_code, 201, sent.content)
        receipt = RFPEstimateReceipt.objects.get(dispatch_id=sent.json()['id'])
        self.assertEqual(self.client.get(estimate).json()['receipt']['reference'], receipt.reference)
        self.assertFalse(rfp.root(self.case).current_intake.contributions.filter(team='Security').exists())

    def test_changed_destination_holds_original_and_manual_receipt_requires_matching_evidence(self):
        rule = self.configure('manual_receipt')
        draft = self.prepared()
        reviewed = self.review(draft)
        transition(self.actor, rule.pk, 'revoked')
        with self.assertRaisesMessage(ValidationError, 'current source, destination or authority changed'):
            service.release(self.actor, self.work.pk, rev(self.case), reviewed.pk)
        self.assertFalse(RFPEstimateDispatch.objects.exists())
        self.configure('manual_receipt', channel='whatsapp', destination='+15555550121')
        reviewed = self.review(draft, channel='whatsapp')
        dispatch = service.release(self.actor, self.work.pk, rev(self.case), reviewed.pk)
        self.assertFalse(RFPEstimateReceipt.objects.exists())
        self.assertFalse(RFPEstimateMailbox.objects.exists())
        wrong_proof = add_evidence(self.actor, self.case.pk, 'rfp_estimate_receipt', '{}', 'synthetic:witness')
        with self.assertRaisesMessage(ValidationError, 'original request'):
            service.record_receipt(self.actor, self.work.pk, rev(self.case), dispatch.pk, 'sample-receipt', True,
                                   wrong_proof.pk)
        proof = add_evidence(self.actor, self.case.pk, 'rfp_estimate_receipt',
                             json.dumps(receipt_fields(dispatch, 'sample-receipt', True)), 'synthetic:witness')
        receipt = service.record_receipt(self.actor, self.work.pk, rev(self.case), dispatch.pk, 'sample-receipt', True, proof.pk)
        self.assertTrue(receipt.delivered)
        self.assertFalse(public_evidence(self.case.evidence.filter(pk=proof.pk)).exists())
        self.assertEqual(RFPEstimateReceipt.objects.count(), 1)

    def test_tola_uses_only_selected_bid_metadata_and_review_pins_human_text(self):
        self.configure(attachment=True)
        self.client.force_login(self.actor)
        env = {'OPENROUTER_MODEL': 'synthetic-test-model', 'OPENROUTER_API_KEY': 'synthetic-test-key'}
        with patch.dict('os.environ', {'OPENROUTER_MODEL': env['OPENROUTER_MODEL']}, clear=True):
            self.assertContains(self.client.get(self.path), 'Draft with Tola')
            response = self.client.post(self.path, {'action': 'prepare_tola', 'revision': rev(self.case)}, follow=True)
        self.assertContains(response, 'Tola is preparing wording from the selected bid.')
        _, scope = service.scope(self.actor, self.work)
        turn = rfp_estimate_model.latest(self.actor, self.work, scope)
        self.assertEqual(turn.status, 'queued')
        with patch.dict('os.environ', env), patch.object(assistant.openrouter, 'answer', return_value={
                'answer': 'Please share the Security estimate for the sample bid.', 'citations': ['S1'], 'next_work': '',
        }) as model:
            self.assertTrue(assistant.worker_once())
        self.assertEqual([item['label'] for item in model.call_args.args[3]], ['Received bid request'])
        self.assertContains(self.client.get(self.path), 'Suggested by Tola')
        draft = service.current_draft(self.actor, self.work, scope)
        data = b'Synthetic private bid attachment'
        file = CaseUpload.objects.create(case=self.case, actor=self.actor, name='Sample bid attachment.pdf',
                                         size=len(data), sha256=sha256(data).hexdigest(), key='synthetic-security-attachment')
        reviewed = service.review(self.actor, self.work.pk, rev(self.case), draft.pk, 'email', timezone.localdate(),
                                  'Human revision of the synthetic model wording', self.evidence.pk,
                                  attachment_id=file.pk, model_turn=turn.pk)
        self.assertEqual(reviewed.payload['model_draft']['turn'], str(turn.pk))
        self.assertFalse(RFPEstimateDispatch.objects.exists())
        with patch('adapters.case_uploads.read', return_value=data) as read:
            dispatch = service.release(self.actor, self.work.pk, rev(self.case), reviewed.pk)
        read.assert_called_once_with(file)
        self.assertEqual(dispatch.mailbox.payload['body'], 'Human revision of the synthetic model wording')
        self.assertEqual(dispatch.mailbox.payload['attachment']['sha256'], file.sha256)

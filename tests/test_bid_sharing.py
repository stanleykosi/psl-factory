from types import SimpleNamespace
from uuid import uuid4
from unittest.mock import patch

from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.agents import assistant
from apps.agents.assistant_models import AssistantConversation, AssistantTurn
from apps.documents.contracts import digest
from apps.identity.models import Grant
from apps.pmo import bid_sharing as sharing, rfp, winning_answers
from apps.pmo.models import RFPCase
from apps.workflows import factory, factory_rfp
from tests.factory_rfp_helpers import configured, reviewed_document, start
from tests.helpers import setup_case, rev


class BidSharingTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner, cls.source = setup_case(username='bid-owner')
        data = configured('ORIGINAL-ATLAS', context=(cls.owner, cls.source))
        work = start(data)
        cls.response, _ = reviewed_document(data, work)
        factory.run_until_wait(work.pk)
        submission = factory_rfp.submission_for(work)
        rfp.outcome(cls.owner, cls.source.pk, submission.pk, 'won', timezone.now(), 'Client',
            data['evidence']['rfp_outcome'].pk, 'Client confirmed the award.', rev(cls.source))
        factory.run_until_wait(work.pk)
        cls.bid = RFPCase.objects.get(case=cls.source)
        cls.member, cls.target = setup_case(username='other-project-pm')
        configured('SECOND-BID', context=(cls.member, cls.target))
        Grant.objects.get_or_create(user=cls.member, case=cls.target, action='agent.extract')
        cls.body = 'The client asked for evening training on Wednesdays.'
        sharing.record_note(cls.owner, cls.source, cls.bid.pk, cls.body, uuid4())

    def publish(self):
        return sharing.set_visibility(self.owner, self.source, self.bid.pk, 'public', 0)

    def test_public_opens_original_and_reuse_then_private_withdraws_both(self):
        user, workspace = self.member, self.target
        self.client.force_login(user)
        url = reverse('bid_record', args=[workspace.pk, self.bid.pk])
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertFalse(Grant.objects.filter(user=user, case=self.source).exists())
        public = self.publish()
        page = self.client.get(url)
        for fact in (self.body, 'Client confirmed the award.', self.response.matrix[0]['response']):
            self.assertContains(page, fact)
        self.assertNotContains(page, 'Save sharing')
        self.assertEqual(self.client.post(url, {'action':'sharing', 'visibility':'private'}).status_code, 403)
        self.assertFalse(sharing.workspaces(user).filter(pk=self.source.pk).exists())
        _, pin, citation = winning_answers.options(user, workspace)[0]
        self.assertEqual(citation['url'], url)
        self.assertEqual(winning_answers.read(user, workspace, pin), citation)
        chat = AssistantConversation.objects.create(actor=user, case=workspace, persona='tola')
        sources, _ = assistant.tool_context(chat)
        self.assertIn(self.body, str(sources))
        selected = next(s for s in sources if s['url'] == url)
        AssistantTurn.objects.create(pk=uuid4(), conversation=chat, question='What did the client request?',
            status='answered', answer=self.body, sources=[selected], context_hash=digest(sources))
        sharing.set_visibility(self.owner, self.source, self.bid.pk, 'private', public.pk)
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(winning_answers.options(user, workspace), [])
        with self.assertRaises(PermissionDenied):
            winning_answers.read(user, workspace, pin)
        self.assertNotIn(self.body, str(assistant.tool_context(chat)))
        self.assertNotContains(self.client.get(reverse('assistant_thread', args=[chat.pk])), self.body)
        own = SimpleNamespace(actor=self.owner, case=self.source, persona='tola')
        self.assertIn(self.body, str(sharing.chat_sources(own)))

    def test_current_owner_only_private_default_and_stale_edits(self):
        self.assertFalse(sharing.available(self.owner, self.source).get(pk=self.bid.pk).is_public)
        with self.assertRaises(PermissionDenied):
            sharing.record_note(self.member, self.target, self.bid.pk, 'unauthorised', uuid4())
        public = self.publish()
        self.assertEqual(self.publish().pk, public.pk)
        private = sharing.set_visibility(self.owner, self.source, self.bid.pk, 'private', public.pk)
        with self.assertRaises(ValidationError):
            self.publish()
        self.assertGreater(private.pk, public.pk)
        self.assertEqual(self.bid.sharing_decisions.count(), 2)

    def test_other_organisation_live_projects_and_other_departments_are_excluded(self):
        self.publish()
        user, other = setup_case(username='different-company')
        for tenant, synthetic in [('another company', True), (self.source.tenant, False)]:
            other.tenant, other.synthetic = tenant, synthetic
            other.save()
            self.assertFalse(sharing.available(user, other).filter(pk=self.bid.pk).exists())
        Grant.objects.filter(user=self.member, case=self.target, action='rfp.read').update(active=False)
        with self.assertRaises(PermissionDenied):
            sharing.available(self.member, self.target)
        self.assertEqual(sharing.chat_sources(SimpleNamespace(persona='chidi')), [])

    def test_file_download_and_extracted_text_follow_the_same_visibility(self):
        from tests.test_rfp import fixture
        from tests.test_rfp_intake_upload import PRIVATE_TEXT, word_file

        owner, case = setup_case(username='uploaded-bid-owner')
        _, _, evidence, _, _ = fixture(record_intake=False, context=(owner, case))
        self.client.force_login(owner)
        file = word_file()
        original = file.read()
        file.seek(0)
        with patch('adapters.case_uploads.put'):
            page = self.client.post(reverse('rfp', args=[case.pk]), {'action':'intake', 'revision':rev(case),
                'reference':'ORIGINAL-DOCUMENT', 'received_at':timezone.now().isoformat(), 'deadline_status':'unknown',
                'note':'Client sent their brief.', 'rfp_file':file})
            self.assertEqual(page.status_code, 302)
        bid = RFPCase.objects.get(case=case)
        rfp.assign(owner, case.pk, owner, 'CEO', evidence['policy_decision'].pk, 'Original bid owner.', rev(case))
        public = sharing.set_visibility(owner, case, bid.pk, 'public', 0)
        self.client.force_login(self.member)
        url = reverse('bid_original_file', args=[self.target.pk, bid.pk])
        chat = SimpleNamespace(actor=self.member, case=self.target, persona='tola')
        with patch('adapters.case_uploads.read', return_value=original) as storage:
            self.assertEqual(b''.join(self.client.get(url).streaming_content), original)
            self.assertIn(PRIVATE_TEXT, str(sharing.chat_sources(chat, 'ORIGINAL-DOCUMENT')))
            sharing.set_visibility(owner, case, bid.pk, 'private', public.pk)
            storage.reset_mock()
            self.assertEqual(self.client.get(url).status_code, 404)
            self.assertNotIn(PRIVATE_TEXT, str(sharing.chat_sources(chat, 'ORIGINAL-DOCUMENT')))
            storage.assert_not_called()

    def test_explicit_private_replaces_an_older_project_release(self):
        from tests.helpers import activate
        from apps.pmo.models import RFPDisposition
        outcome = RFPDisposition.objects.get(rfp=self.bid).outcome_id
        activate(self.owner, self.source, 'OPS.winning_bid_reuse', {'answers': [
            {'outcome_id':outcome, 'requirement':'R1', 'destination':str(self.target.pk)}]},
            self.source.evidence.filter(kind='policy_decision').first())
        for action in ('case.read', 'rfp.read'):
            Grant.objects.create(user=self.member, case=self.source, action=action)
        _, pin, _ = winning_answers.options(self.member, self.target)[0]
        sharing.set_visibility(self.owner, self.source, self.bid.pk, 'private', 0)
        self.assertEqual(winning_answers.options(self.member, self.target), [])
        with self.assertRaises(PermissionDenied):
            winning_answers.read(self.member, self.target, pin)

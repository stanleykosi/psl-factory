import os
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
from uuid import uuid4

from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import close_old_connections, connection
from django.test import TestCase, TransactionTestCase
from django.urls import reverse

from adapters import commercial_rework as contract
from apps.agents import file_draft_reviews, upload_jobs
from apps.agents.upload_views import upload_file
from apps.core.evidence_access import public_evidence, public_timeline
from apps.core.models import Evidence
from apps.core.services import add_evidence
from apps.documents.services import review_document
from apps.identity.models import Grant
from apps.pmo import commercial_rework as domain
from apps.pmo.commercial import draft_submission
from apps.pmo.models import CommercialRevision
from tests.helpers import rev
from tests.test_commercial_client_response import CommercialClientFixture


class ReworkFixture(CommercialClientFixture):
    def setup_rework(self):
        self.setup_client_response()
        self.proof = upload_file(self.actor, self.case, SimpleUploadedFile('SAMPLE-client-changes.txt',
            b'SAMPLE client requests a clearer delivery description. No price or date change is approved.'))
        self.metadata, self.response = self.record(outcome='changes_requested')
        with patch.dict(os.environ, {'OPENROUTER_MODEL': 'synthetic/model', 'OPENROUTER_API_KEY': 'fake'}), \
             patch('adapters.openrouter.review', return_value={'summary': 'Review the delivery description.',
                   'quotes': ['1'], 'gaps': ['Confirm actual scope, costs and dates independently.']}):
            self.job = domain.ask_agent(self.actor, self.case.pk, self.metadata.pk, rev(self.case))[0]
            self.assertTrue(upload_jobs.run_once())
        self.job.refresh_from_db()
        file_draft_reviews.retain(self.actor, self.case, self.job.pk,
            {'draft': file_draft_reviews.draft_digest(self.job), 'summary': 'SAMPLE human-reviewed description task.',
             'gaps': 'No financial change is authorised by this source.', 'note': 'SAMPLE source reviewed by a human.'})
        self.job.refresh_from_db()

    def capture(self, **values):
        data = {'sources': {kind: self.e[kind].pk for kind in contract.SOURCE_KINDS},
                'scope': 'SAMPLE revised scope: describe the existing delivery clearly. No invented terms.',
                'note': 'SAMPLE human checked the proposed wording and exact sources.', 'confirmed': True,
                'key': uuid4(), 'expected': rev(self.case), 'predecessor': None}
        data.update(values)
        return domain.capture(self.actor, self.case.pk, self.metadata.pk, self.job.pk, **data)


class CommercialReworkTests(ReworkFixture, TestCase):
    def setUp(self):
        self.setup_rework()

    def test_rework_browser_fixture_is_additive_and_does_not_create_responses_or_model_jobs(self):
        from django.contrib.auth import get_user_model
        from apps.agents.models import AgentJob, CaseUpload
        from apps.pmo.models import ClientResponse
        from tests.railway_commercial_client_seed import prepare_rework
        get_user_model().objects.create_user(username='psl-agent-trial')
        guard = {'PSL_COMMERCIAL_CLIENT_FIXTURE': '1', 'RAILWAY_ENVIRONMENT_NAME': 'design-acceptance'}
        with patch.dict(os.environ, guard):
            fixture = prepare_rework()
            replay = prepare_rework()
        self.assertEqual(replay['case'], fixture['case'])
        self.assertEqual(replay['current_proposal'], fixture['current_proposal'])
        self.assertTrue(replay['preserved_existing'])
        self.assertEqual(CaseUpload.objects.filter(case_id=fixture['case']).count(), 2)
        self.assertFalse(ClientResponse.objects.filter(revision__dossier__case_id=fixture['case']).exists())
        self.assertFalse(AgentJob.objects.filter(upload__case_id=fixture['case']).exists())

    def test_client_change_screen_saves_and_prepares_exact_reviewed_scope(self):
        self.client.force_login(self.actor)
        url = reverse('commercial_client_response', args=[self.case.pk])
        page = self.client.get(url)
        self.assertContains(page, 'Write the revised scope')
        self.assertContains(page, 'SAMPLE human-reviewed description task.')
        posted = {'action': 'save_revision', 'revision': rev(self.case), 'operation_key': uuid4(),
                  'job': self.job.pk, 'scope': 'SAMPLE clarified delivery description.', 'confirmed': 'on',
                  'note': 'SAMPLE human checked the exact requested change.',
                  **{kind: self.e[kind].pk for kind in contract.SOURCE_KINDS}}
        self.assertEqual(self.client.post(url, posted).status_code, 302)
        draft = domain.latest(self.case)
        self.assertContains(self.client.get(url), 'SAMPLE clarified delivery description.')
        self.assertEqual(self.client.post(url, {'action': 'prepare_revision', 'revision': rev(self.case),
                                                'draft': draft.pk}).status_code, 302)
        self.assertContains(self.client.get(url), 'The revised proposal is prepared and waiting for fresh commercial decisions.')
        self.assertFalse(CommercialRevision.objects.get(previous=self.proposal).decisions.exists())

    def test_reviewed_agent_advice_editable_scope_fresh_proposal_and_no_inherited_approval(self):
        draft = self.capture()
        value, _, _, result = domain.read(self.actor, self.case, draft)
        self.assertEqual(result['summary'], 'SAMPLE human-reviewed description task.')
        self.assertFalse(public_evidence(Evidence.objects.filter(pk=draft.pk)).exists())
        self.assertFalse(public_timeline(self.case).filter(action='commercial.rework_drafted').exists())
        revision = domain.prepare_revision(self.actor, self.case.pk, draft.pk, rev(self.case))
        self.assertEqual(revision.previous_id, self.proposal.pk)
        self.assertEqual(revision.context_id, self.response.evidence_id)
        self.assertEqual(Evidence.objects.get(pk=revision.sources['sow']).body, value['scope'])
        self.assertEqual(revision.sources['costing'], self.proposal.sources['costing'])
        self.assertFalse(revision.decisions.exists())
        self.assertFalse(revision.commercialdocumentbinding_set.exists())
        with self.assertRaises(ValidationError):
            draft_submission(self.actor, self.case.pk, revision.pk, self.template.pk, rev(self.case))
        repeated = domain.prepare_revision(self.actor, self.case.pk, draft.pk, rev(self.case))
        self.assertEqual(repeated.pk, revision.pk)
        self.assertEqual(CommercialRevision.objects.count(), 2)
        self.assertTrue(self.response.receipt_id)

    def test_unknowns_save_but_hold_only_preparation_and_current_correction_can_continue(self):
        draft = self.capture(sources={kind: None for kind in contract.SOURCE_KINDS})
        before = self.case.evidence.filter(kind='sow').count()
        with self.assertRaisesMessage(ValidationError, 'The draft is saved'):
            domain.prepare_revision(self.actor, self.case.pk, draft.pk, rev(self.case))
        self.assertEqual(self.case.evidence.filter(kind='sow').count(), before)
        corrected = self.capture(predecessor=draft.pk)
        with self.assertRaisesMessage(ValidationError, 'current revision draft'):
            domain.prepare_revision(self.actor, self.case.pk, draft.pk, rev(self.case))
        self.assertEqual(domain.prepare_revision(self.actor, self.case.pk, corrected.pk, rev(self.case)).number, 2)
        self.assertTrue(Evidence.objects.filter(pk=draft.pk).exists())

    def test_corrected_response_or_returned_review_cannot_prepare_from_old_advice(self):
        draft = self.capture()
        review_document(self.actor, self.case.pk, self.job.file_review.evidence_id,
                        'returned', 'SAMPLE revised review needed.', rev(self.case))
        with self.assertRaisesMessage(ValidationError, 'current accepted human review'):
            domain.prepare_revision(self.actor, self.case.pk, draft.pk, rev(self.case))
        review_document(self.actor, self.case.pk, self.job.file_review.evidence_id,
                        'accepted', 'SAMPLE explicitly reviewed again.', rev(self.case))
        self.record(outcome='declined', predecessor=self.metadata.pk)
        with self.assertRaisesMessage(ValidationError, 'current client request'):
            domain.prepare_revision(self.actor, self.case.pk, draft.pk, rev(self.case))
        self.assertEqual(CommercialRevision.objects.count(), 1)

    def test_original_authority_private_read_and_native_provenance_remain_required(self):
        from django.contrib.auth import get_user_model
        draft = self.capture()
        reader = get_user_model().objects.create_user(username='sample-rework-reader')
        for action in ['case.read', 'commercial.read']:
            Grant.objects.create(user=reader, case=self.case, action=action)
        deferred = domain.latest(self.case)
        with self.assertRaises(PermissionDenied):
            domain.read(reader, self.case, deferred)
        self.assertIn('body', deferred.get_deferred_fields())
        Grant.objects.create(user=reader, case=self.case, action='commercial.proof.read')
        self.assertEqual(domain.read(reader, self.case, deferred)[0]['job'], self.job.pk)
        forged = add_evidence(self.actor, self.case.pk, contract.KIND, draft.body, draft.source)
        with self.assertRaisesMessage(ValidationError, 'native provenance'):
            domain.read(self.actor, self.case, forged)
        Grant.objects.filter(user=self.actor, case=self.case, action='commercial.prepare').update(active=False)
        deferred = Evidence.objects.defer('body').get(pk=draft.pk)
        with self.assertRaises(PermissionDenied):
            domain.read(reader, self.case, deferred)
        self.assertIn('body', deferred.get_deferred_fields())

    def test_malformed_unknown_owner_values_and_changed_plan_cannot_bypass_native_costing(self):
        for values in [{'scope': ' '}, {'confirmed': False}, {'key': 'incorrect-key'}]:
            with self.assertRaises(ValidationError):
                self.capture(**values)
        changed_plan = add_evidence(self.actor, self.case.pk, 'plan', 'SAMPLE genuinely revised plan.', 'synthetic:rework-plan')
        draft = self.capture(sources={kind: changed_plan.pk if kind == 'plan' else self.e[kind].pk
                                      for kind in contract.SOURCE_KINDS})
        with self.assertRaises(ValidationError):
            domain.prepare_revision(self.actor, self.case.pk, draft.pk, rev(self.case))
        self.assertEqual(CommercialRevision.objects.count(), 1)


class CommercialReworkConcurrencyTests(ReworkFixture, TransactionTestCase):
    def setUp(self):
        self.setup_rework()

    def test_two_connections_prepare_one_native_revision_and_retain_the_draft(self):
        draft = self.capture()
        expected = rev(self.case)
        def prepare():
            close_old_connections()
            try:
                return domain.prepare_revision(self.actor, self.case.pk, draft.pk, expected).pk
            except ValidationError:
                return 'stale'
            finally:
                connection.close()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: prepare(), range(2)))
        self.assertEqual(results.count('stale'), 1)
        self.assertEqual(CommercialRevision.objects.count(), 2)
        self.assertTrue(Evidence.objects.filter(pk=draft.pk).exists())

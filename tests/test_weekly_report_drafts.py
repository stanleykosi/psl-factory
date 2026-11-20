from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.core.models import Evidence
from apps.documents.models import ControlledReview, Publication, PublicationJob, Version
from apps.identity.models import Grant
from apps.workflows import factory_reporting as reporting
from apps.workflows.factory_progress import run_once as run_progress, set_progress
from apps.workflows.models import (
    FactoryActivity, FactoryProgress, FactoryWork, HumanTask, WeeklyReportDraftVersion,
)
from tests import test_factory_reporting as native
from tests.document_helpers import artifact
from tests.helpers import rev


class WeeklyReportDraftTests(TestCase):
    configure = native.FactoryReportingTests.configure
    start_work = native.FactoryReportingTests.start_work
    advance = native.FactoryReportingTests.advance
    review = native.FactoryReportingTests.review

    def setUp(self):
        native.FactoryReportingTests.setUp(self)
        self.client.force_login(self.actor)

    def counts(self):
        return tuple(model.objects.count() for model in (
            Evidence, FactoryWork, FactoryActivity, FactoryProgress, Version,
            HumanTask, ControlledReview, Publication, PublicationJob,
        ))

    def completed_parts(self):
        return dict(self.narrative, **{
            name + '_citations': [self.notes.pk] for name in self.narrative
        })

    def test_private_intake_keeps_partial_fields_without_starting_and_fences_submission(self):
        url = reverse('factory_create')
        query = {'definition': reporting.DEFINITION, 'case': self.case.pk}
        revision = rev(self.case)
        base = dict(query, revision=revision, key='DRAFT-WEEKLY-PRIVATE')
        original = self.counts()
        first = dict(base, action='save_draft', status='Early private report wording',
                     status_citations=[self.notes.pk], background='on')
        self.assertEqual(self.client.post(url, first).status_code, 302)
        saved = WeeklyReportDraftVersion.objects.get(author=self.actor, case=self.case)
        self.assertEqual(self.counts(), original)
        self.assertEqual(rev(self.case), revision)
        reopened = self.client.get(url, query)
        self.assertContains(reopened, 'Private draft saved')
        self.assertContains(reopened, first['status'])
        self.assertEqual(reopened.context['form'].initial['draft_version'], saved.pk)
        self.assertEqual(reopened.context['inputs_form'].initial['status_citations'], [self.notes.pk])
        self.assertEqual(reopened.context['inputs_form'].initial['start_at'], '')

        Grant.objects.create(user=self.preparer, case=self.case, action='factory.start')
        self.client.force_login(self.preparer)
        self.assertNotContains(self.client.get(url, query), first['status'])
        forged = self.client.post(url, dict(first, draft_version=saved.pk))
        self.assertContains(forged, 'The saved draft changed.')
        self.assertEqual(WeeklyReportDraftVersion.objects.count(), 1)
        self.client.force_login(self.actor)

        start_grant = Grant.objects.filter(user=self.actor, case=self.case, action='factory.start')
        start_grant.update(active=False)
        unavailable = self.client.get(url, query)
        self.assertNotIn(first['status'], unavailable.content.decode())
        self.client.post(url, dict(first, draft_version=saved.pk))
        self.assertEqual(WeeklyReportDraftVersion.objects.count(), 1)
        start_grant.update(active=True)

        second = dict(first, status='Second private report wording', draft_version=saved.pk)
        self.assertEqual(self.client.post(url, second).status_code, 302)
        current = WeeklyReportDraftVersion.objects.latest('pk')
        self.assertNotEqual(current.pk, saved.pk)
        self.assertContains(self.client.post(url, dict(second, status='Stale correction')), 'The saved draft changed.')
        self.assertEqual(WeeklyReportDraftVersion.objects.count(), 2)
        incomplete = dict(base, action='start', draft_version=current.pk,
                          start_at=self.inputs['start_at'], end_at=self.inputs['end_at'],
                          reference='Private sample weekly report')
        self.assertContains(self.client.post(url, incomplete), 'Choose a client report template before continuing.')
        self.assertEqual(self.counts(), original)

        valid = dict(incomplete, template_id=self.template.pk, background='on', **self.completed_parts())
        self.assertEqual(self.client.post(url, valid).status_code, 302)
        work = FactoryWork.objects.get(case=self.case, key=base['key'])
        self.assertTrue(FactoryProgress.objects.filter(work=work).exists())
        self.assertEqual(WeeklyReportDraftVersion.objects.latest('pk').submitted_work_id, work.pk)
        submitted = self.counts()
        self.assertContains(self.client.post(url, dict(valid, revision=rev(self.case))), 'The saved draft changed.')
        self.assertEqual(self.counts(), submitted)
        self.assertEqual(WeeklyReportDraftVersion.objects.count(), 3)

    def test_returned_report_retains_its_exact_decision_and_private_correction_until_submit(self):
        artifact(self.actor, self.case, 'D05.decision_action_matrix', 'schema:psl/decision-actions/v1',
                 {'rules': [{'role': 'PMO Lead', 'actions': ['return']}]}, self.owner)
        self.start_work()
        progress = set_progress(self.actor, self.work.pk, self.work.revision, True)
        self.advance()
        earlier = self.review('return')
        self.advance()
        self.assertEqual(run_progress(), progress.pk)
        progress.refresh_from_db()
        self.assertEqual(progress.status, 'waiting')
        available = progress.available_at
        self.work.refresh_from_db()
        decision = earlier.reviews.get(verdict='return')
        source = self.work.source_head_id
        revision = self.work.revision
        case_revision = rev(self.case)
        url = reverse('factory_detail', args=[self.work.pk]) + '?edit=1'
        baseline = self.counts()
        before = self.client.get(url)
        self.assertContains(before, 'Returned for changes')
        self.assertContains(before, 'Save draft')
        self.assertEqual(before.context['inputs_form'].initial['status_citations'], [self.notes.pk])
        partial = {'action': 'save_draft', 'revision': revision, 'case_revision': case_revision,
                   'start_at': self.inputs['start_at'], 'end_at': self.inputs['end_at'],
                   'template_id': self.template.pk, 'status': 'Private returned correction wording',
                   'status_citations': [self.notes.pk], 'reason': 'Reviewing additional sample source'}
        self.assertEqual(self.client.post(url, partial).status_code, 302)
        draft = WeeklyReportDraftVersion.objects.get(work=self.work, author=self.actor)
        self.assertEqual((draft.source_head_id, draft.return_review_id), (source, decision.pk))
        self.work.refresh_from_db()
        self.assertEqual((self.work.source_head_id, self.work.revision), (source, revision))
        self.assertEqual(self.counts(), baseline)
        self.assertEqual(rev(self.case), case_revision)
        progress.refresh_from_db()
        self.assertEqual(progress.available_at, available)
        reopened = self.client.get(url)
        self.assertContains(reopened, partial['status'])
        self.assertContains(reopened, decision.note)
        self.assertEqual(reopened.context['correction_reason'], partial['reason'])
        self.assertEqual(reopened.context['inputs_form'].initial['status_citations'], [self.notes.pk])
        self.assertEqual(reopened.context['inputs_form'].initial['next_steps'], '')

        other = self.preparer
        for action in ('factory.read', 'factory.manage'):
            Grant.objects.create(user=other, case=self.case, action=action)
        self.client.force_login(other)
        self.assertNotContains(self.client.get(url), partial['status'])
        self.assertContains(self.client.post(url, dict(partial, draft_version=draft.pk)), 'The saved draft changed.')
        self.assertEqual(WeeklyReportDraftVersion.objects.count(), 1)
        self.client.force_login(self.actor)
        invalid = dict(partial, action='correct', draft_version=draft.pk)
        self.assertContains(self.client.post(url, invalid), 'Choose at least one record for this part.')
        self.assertEqual(self.counts(), baseline)

        valid = dict(invalid, **self.completed_parts())
        valid['status'] = partial['status']
        self.assertEqual(self.client.post(url, valid).status_code, 302)
        self.work.refresh_from_db()
        self.assertNotEqual(self.work.source_head_id, source)
        self.assertEqual(WeeklyReportDraftVersion.objects.latest('pk').submitted_work_id, self.work.pk)
        progress.refresh_from_db()
        self.assertEqual(progress.status, 'waiting')
        self.assertLessEqual(progress.available_at, timezone.now())
        self.assertEqual(FactoryProgress.objects.filter(work=self.work).count(), 1)
        submitted = self.counts()
        old_action = dict(valid, revision=self.work.revision, case_revision=rev(self.case))
        self.assertContains(self.client.post(url, old_action), 'The saved draft changed.')
        self.assertEqual(self.counts(), submitted)
        self.advance()
        successor = reporting.document(self.work)
        self.assertNotEqual(successor.pk, earlier.pk)
        self.assertEqual(successor.fields['status']['text'], partial['status'])
        self.assertTrue(HumanTask.objects.filter(version=successor, status='open').exists())
        self.assertTrue(ControlledReview.objects.filter(pk=decision.pk, version=earlier, verdict='return').exists())
        self.assertFalse(Publication.objects.filter(factory_work=self.work).exists())

"""Exact same-entity leadership coverage and controlled distribution on PostgreSQL."""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import DatabaseError, connection, transaction
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.core.models import Case
from apps.core.services import add_evidence
from apps.documents.controlled import reserve_publication, review_version
from apps.documents.models import Publication, PublicationReceipt
from apps.identity.models import Grant
from apps.pmo import leadership_project_scope as coverage
from apps.pmo.meetings import record_meeting
from apps.pmo.models import MinutesReportBinding
from apps.policy.models import Configuration
from apps.policy.operator_drafts import draft_operator_policy
from apps.policy.role_assignments import COMPONENT, draft
from apps.policy.services import active_component, reference_values, transition
from apps.workflows import factory, factory_leadership as flow
from apps.workflows.models import FactoryWork, HumanTask
from tests.helpers import rev
from tests import test_factory_leadership


class LeadershipProjectScopeTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        sample = test_factory_leadership.FactoryLeadershipTests()
        sample.setUp()
        cls.actor = sample.actor
        cls.case = sample.case
        cls.proof = sample.owner
        cls.template = sample.template
        cls.recipient = sample.recipient
        cls.start = sample.start
        cls.end = timezone.now()
        cls.reviewer = get_user_model().objects.create_user('separate-monthly-reviewer')
        for actor, actions in (
            (cls.recipient, ('case.read', 'report.read', 'meeting.read')),
            (cls.reviewer, ('case.read', 'report.read', 'meeting.read', 'factory.read', 'document.review_controlled')),
        ):
            for action in actions:
                Grant.objects.get_or_create(case=cls.case, user=actor, action=action)
        assignments = reference_values(active_component(COMPONENT, cls.case))
        role = draft(cls.actor, cls.case.pk, [*assignments, {'role': 'PMO Lead', 'user_id': cls.reviewer.pk}],
                     cls.proof.pk, timezone.now())
        transition(cls.actor, role.pk, 'validated')
        transition(cls.actor, role.pk, 'active')

    def project(self, title, *, tenant=None, report_access=True):
        case = Case.objects.create(tenant=tenant or self.case.tenant, synthetic=True, title=title, kind='project')
        actions = ('case.read', 'meeting.read', 'meeting.record', 'meeting.participate', 'evidence.add')
        if report_access:
            actions += ('report.read',)
        Grant.objects.bulk_create([Grant(case=case, user=self.actor, action=action) for action in actions])
        meeting = self.record(case, 'SAMPLE-LEADERSHIP-MEETING')
        return case, meeting

    def record(self, case, reference):
        source = add_evidence(self.actor, case.pk, 'meeting_notes', 'Synthetic source body never copied into a report.',
                              'synthetic:leadership-project-coverage')
        return record_meeting(self.actor, case.pk, reference, 'status', self.end - timedelta(minutes=1),
                              'Fictional status', 'Fictional programme progress', [self.actor.pk], [], source.pk, rev(case))

    def post_start(self, key, *, start=None, end=None):
        return self.client.post(reverse('factory_create'), {
            'definition': flow.DEFINITION, 'scope': coverage.MODE, 'kind': 'monthly_executive', 'case': self.case.pk,
            'revision': rev(self.case), 'key': key, 'reference': 'Synthetic group leadership report',
            'audience': 'internal', 'start_at': (start or self.start).isoformat(), 'end_at': (end or self.end).isoformat(),
            'template_id': self.template.pk, 'domains': ['meetings', 'changes'],
        })

    def enable(self):
        url = reverse('factory_create')
        self.assertRedirects(self.client.post(url, {'definition': flow.DEFINITION, 'scope': coverage.MODE,
            'kind': 'monthly_executive', 'case': self.case.pk, 'action': 'draft_project_scope', 'enabled': 'yes',
            'revision': rev(self.case), 'evidence': self.proof.pk, 'effective_from': timezone.now().isoformat()}),
            reverse('policy', args=[self.case.pk]), fetch_redirect_response=False)
        config = Configuration.objects.get(case=self.case, component=coverage.COMPONENT)
        for state in ('validated', 'active'):
            self.assertRedirects(self.client.post(reverse('policy', args=[self.case.pk]), {
                'configuration': config.pk, 'action': state,
            }), reverse('policy', args=[self.case.pk]), fetch_redirect_response=False)
        return config

    def test_leads_generate_both_reports_over_all_same_organisation_projects(self):
        from tests.helpers import admit_department

        second, _ = self.project('Included PSL project')
        empty = Case.objects.create(tenant=self.case.tenant, synthetic=True, title='PSL project without records',
                                    kind='project')
        self.project('Another organisation', tenant='outside-leadership-test')
        Case.objects.create(tenant=self.case.tenant, synthetic=False, title='Outside the sample', kind='project')
        for action in ('case.read', 'report.read'):
            Grant.objects.create(case=empty, user=self.actor, action=action)
        pmo, member = admit_department(self.actor, self.case, 'pmo-lead', member=True)
        finance, _ = admit_department(self.actor, self.case, 'finance-lead')
        intake = f'/api/v1/projects/{self.case.pk}/leadership-report-intake'
        kinds = ('internal_tuesday', 'monthly_executive')
        expected = {str(project.pk) for project in (self.case, second, empty)}
        for actor in (pmo, finance):
            self.client.force_login(actor)
            for kind in kinds:
                options = self.client.get(intake, {'kind': kind})
                self.assertEqual(options.status_code, 200, options.content)
                self.assertTrue(options.json()['automatic_project_scope'])
                template = self.template.pk if kind == 'monthly_executive' else None
                response = self.client.post(intake, {'action': 'start', 'case_revision': options.json()['revision'],
                    'key': f'synthetic-{actor.pk}-{kind}', 'reference': 'PSL company-wide report', 'background': False,
                    'selection': {'kind': kind, 'audience': 'internal', 'template_id': template,
                                  'start_at': self.start.isoformat(), 'end_at': self.end.isoformat()}, 'sections': None},
                    content_type='application/json')
                self.assertEqual(response.status_code, 201, response.content)
                work = FactoryWork.objects.select_related('source_head', 'case').get(pk=response.json()['work_id'])
                report = flow.source(work, actor)
                register = report['manifest']['project_scope']
                self.assertEqual({project['case'] for project in register['projects']}, expected)
                self.assertIn(register['register_id'], coverage.citations(report['manifest']))
                detail = self.client.get(f'/api/v1/work/{work.pk}/leadership-report')
                self.assertEqual(detail.status_code, 200, detail.content)
                self.assertEqual(detail.json()['coverage']['scope'], 'all_psl_projects')
                self.assertEqual({row['id'] for row in detail.json()['coverage']['project_register']}, expected)
                meeting_count = next(row['count'] for row in detail.json()['coverage']['counts'] if row['domain'] == 'meetings')
                self.assertGreaterEqual(meeting_count, 1) if actor == pmo else self.assertEqual(meeting_count, 0)
                if template:
                    factory.run_until_wait(work.pk)
                    work.refresh_from_db()
                    document = flow.document(work)
                    self.assertIsNotNone(document, work.finding)
                    self.assertIn(empty.title, document.fields['executive_summary']['text'])
                    self.assertEqual(MinutesReportBinding.objects.get(version=document).report.scope_owner_id, actor.pk)
        self.client.force_login(member)
        self.assertIn(self.client.get(intake, {'kind': kinds[0]}).status_code, (403, 404))

    def test_scope_requires_owner_enablement_and_every_exact_recipient_permission(self):
        self.assertEqual(connection.vendor, 'postgresql')
        second, meeting = self.project('Included authorised project')
        unrelated, _ = self.project('Inaccessible same-entity project', report_access=False)
        outside, _ = self.project('Other entity project', tenant='outside-leadership-test')
        self.client.force_login(self.actor)
        new = reverse('factory_create')
        open_intake = {'definition': flow.DEFINITION, 'case': self.case.pk, 'scope': coverage.MODE, 'kind': 'monthly_executive'}
        self.assertContains(self.client.get(new, open_intake), 'Multi-project coverage needs an approved rule')
        self.assertContains(self.post_start('SAMPLE-COVERED-LEADERSHIP'), 'Multi-project coverage needs an approved rule')
        self.assertFalse(FactoryWork.objects.filter(case=self.case, definition=flow.DEFINITION).exists())
        config = self.enable()
        start = self.post_start('SAMPLE-COVERED-LEADERSHIP')
        work = FactoryWork.objects.get(case=self.case, definition=flow.DEFINITION)
        path = reverse('factory_detail', args=[work.pk])
        self.assertRedirects(start, path, fetch_redirect_response=False)
        scope = flow.source(work, self.actor)['manifest']['project_scope']
        self.assertEqual(scope['configuration'], config.pk)
        self.assertEqual(scope['record_counts'], {'changes': 0, 'meetings': 2})
        subjects = {item['case']: item for item in scope['projects']}
        self.assertEqual(set(subjects), {str(self.case.pk), str(second.pk)})
        self.assertEqual(subjects[str(second.pk)]['unavailable_domains'], ['changes'])
        self.assertEqual(subjects[str(second.pk)]['inventory']['meetings'], [[meeting.meeting_id, meeting.pk, meeting.evidence_id]])
        serialized = str(scope)
        for excluded in (unrelated, outside):
            self.assertNotIn(str(excluded.pk), serialized)
        page = self.client.get(path)
        self.assertContains(page, 'Included authorised project')
        self.assertNotContains(page, 'Inaccessible same-entity project')
        self.assertNotContains(page, 'Other entity project')
        self.assertFalse(Publication.objects.filter(factory_work=work).exists())

        factory.run_until_wait(work.pk)
        work.refresh_from_db()
        report = flow.document(work)
        self.assertIsNotNone(report, work.finding)
        self.assertEqual(MinutesReportBinding.objects.get(version=report).manifest['project_scope'], scope)
        self.assertIn('Project coverage: 2', report.fields['executive_summary']['text'])
        self.assertNotIn('Synthetic source body', str(report.payload))
        self.assertTrue(HumanTask.objects.filter(version=report, status='open').exists())
        self.client.force_login(self.reviewer)
        decision = reverse('factory_invoice_decision', args=[work.pk])
        self.assertEqual(self.client.get(decision).status_code, 403)
        for action in ('case.read', 'report.read', 'meeting.read'):
            Grant.objects.create(case=second, user=self.reviewer, action=action)
        self.assertContains(self.client.get(decision), 'Approve exact report')
        self.assertRedirects(self.client.post(decision, {'action': 'review', 'verdict': 'approve', 'version': report.pk,
            'revision': work.revision, 'case_revision': rev(self.case), 'note': 'Reviewed exact limited synthetic coverage.'}),
            decision, fetch_redirect_response=False)
        approved = report.reviews.get()
        self.assertEqual(approved.actor_id, self.reviewer.pk)

        with self.assertRaisesMessage(ValidationError, 'through its reviewed work item'):
            reserve_publication(self.actor, self.case.pk, report.pk, rev(self.case))
        with self.assertRaisesMessage(DatabaseError, 'Exact current project coverage'), transaction.atomic():
            Publication.objects.create(version=report, review=approved, actor=self.actor, policies={},
                                       recipient_ids=[self.recipient.pk], retention_days=30, operation_key='forged:group')
        factory.run_until_wait(work.pk)
        work.refresh_from_db()
        self.assertFalse(Publication.objects.filter(factory_work=work).exists())
        for action in ('case.read', 'report.read', 'meeting.read'):
            Grant.objects.create(case=second, user=self.recipient, action=action)
        if work.status in ('blocked', 'configuration_needed', 'owner_needed'):
            factory.manage(self.actor, work.pk, work.revision, 'resume')
        factory.run_until_wait(work.pk)
        work.refresh_from_db()
        self.assertEqual(work.status, 'verified', work.finding)
        verification = flow.verify(work, self.actor)
        self.assertFalse(verification['complete_project_coverage'])
        publication = Publication.objects.get(factory_work=work, version=report, review=approved)
        receipt = PublicationReceipt.objects.get(publication=publication, recipient=self.recipient)
        self.assertEqual(verification['receipt_ids'], [receipt.pk])
        self.assertEqual(receipt.payload_sha256, report.payload_sha256)

    def test_scope_detects_new_current_source_and_refuses_review_of_the_old_version(self):
        self.assertEqual(connection.vendor, 'postgresql')
        second, _ = self.project('Editable fictional project')
        self.client.force_login(self.actor)
        self.enable()
        self.assertEqual(self.post_start('SAMPLE-SCOPE-DRIFT').status_code, 302)
        work = FactoryWork.objects.get(case=self.case, definition=flow.DEFINITION)
        factory.run_until_wait(work.pk)
        work.refresh_from_db()
        version = flow.document(work)
        first = work.source_head_id
        self.assertIsNotNone(version, work.finding)
        self.record(second, 'SAMPLE-NEW-CURRENT-MEETING')
        with self.assertRaisesMessage(ValidationError, 'source snapshot changed'):
            review_version(self.actor, self.case.pk, version.pk, 'approve', 'Cannot use earlier coverage.', rev(self.case))
        self.assertFalse(version.reviews.exists())
        self.assertFalse(Publication.objects.filter(factory_work=work).exists())
        data = flow.source(work, self.actor, False)
        updated = dict(data['inputs'], content_id=None, scope={'domains': ['meetings', 'changes']})
        flow.correct(self.actor, work.pk, work.revision, rev(self.case), updated, 'Review the additional sample record.')
        work.refresh_from_db()
        self.assertNotEqual(work.source_head_id, first)
        factory.run_until_wait(work.pk)
        work.refresh_from_db()
        revised = flow.document(work)
        self.assertNotEqual(revised.pk, version.pk)
        self.assertTrue(HumanTask.objects.filter(version=revised, status='open').exists())
        self.assertEqual(flow.source(work, self.actor)['manifest']['project_scope']['record_counts']['meetings'], 3)
        self.assertFalse(revised.reviews.exists())
        self.assertTrue(MinutesReportBinding.objects.filter(version=version).exists())

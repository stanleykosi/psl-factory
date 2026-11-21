import os
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from apps.agents.models import AgentJob, CaseUpload
from apps.agents.upload_jobs import ROLES
from apps.core.models import Case
from apps.documents.controlled import register_template
from apps.identity.models import Grant
from tests.document_helpers import DEFINITION
from tests.factory_helpers import fixture
from tests.helpers import rev


class DesignConsolidationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        sample = fixture(username='screen-operator')
        private = fixture(username='private-screen-operator')
        cls.actor, cls.case, cls.work = sample['actor'], sample['case'], sample['work']
        cls.template_owner = sample['evidence']['policy_decision']
        cls.other = private['case']
        cls.upload = CaseUpload.objects.create(
            case=cls.case, actor=cls.actor, name='permitted.txt', key='permitted', sha256='test', size=5,
        )
        cls.job = AgentJob.objects.create(upload=cls.upload, actor=cls.actor, role='A01', status='draft',
                                          result={'summary': 'Private draft body'})

    def test_sign_in_and_factory_navigation_use_native_session(self):
        url = reverse('design_overview')
        self.assertRedirects(self.client.get(url), f"{reverse('login')}?next={url}", fetch_redirect_response=False)
        self.client.post(reverse('login'), {'username': self.actor.username, 'password': 'test-only-password'})
        response = self.client.get(url)
        self.assertContains(response, 'factory-design.css')
        self.assertContains(response, 'Invoice preparation and delivery')
        self.assertContains(response, '1 open')
        self.assertNotContains(response, '2 open')
        self.assertIn('no-store', response.headers['Cache-Control'])

    def test_sign_in_can_switch_to_exact_scoped_destination_with_work_email(self):
        user = get_user_model().objects.create_user('sample-other-session', email='preparer@example.invalid',
                                                     password='synthetic-other-session-only')
        Grant.objects.create(case=self.case, user=user, action='case.read')
        self.client.force_login(self.actor)
        target = reverse('design_project', args=[self.case.pk])
        login = reverse('login', query={'next': target})
        page = self.client.get(login)
        self.assertContains(page, 'continue to the work you opened')
        self.assertContains(page, 'Keep me signed in')
        self.assertNotContains(page, self.case.title)
        result = self.client.post(login, {'username': 'PREPARER@example.invalid',
                                         'password': 'synthetic-other-session-only', 'next': target})
        self.assertRedirects(result, target, fetch_redirect_response=False)
        self.assertEqual(int(self.client.session['_auth_user_id']), user.pk)
        self.assertTrue(self.client.session.get_expire_at_browser_close())

        kept = self.client.post(login, {'username': user.username, 'password': 'synthetic-other-session-only',
                                       'next': target, 'remember': 'on'})
        self.assertRedirects(kept, target, fetch_redirect_response=False)
        self.assertFalse(self.client.session.get_expire_at_browser_close())

    def test_sign_in_rejects_ambiguous_email_and_unsafe_destination(self):
        users = get_user_model().objects
        for name in ('sample-email-first', 'sample-email-second'):
            users.create_user(name, email='shared@example.invalid', password='synthetic-shared-email-only')
        login = reverse('login')
        bad = self.client.post(login, {'username': 'shared@example.invalid', 'password': 'synthetic-shared-email-only'})
        self.assertIsNotNone(bad.context['form'].errors.get('__all__'))
        self.assertFalse(self.client.session.get('_auth_user_id'))
        good = self.client.post(login, {'username': 'sample-email-first', 'password': 'synthetic-shared-email-only',
                                       'next': 'https://example.invalid/private/'})
        self.assertRedirects(good, reverse('getting_started'), fetch_redirect_response=False)

    def test_project_links_are_limited_by_case_and_action(self):
        self.client.force_login(self.actor)
        url = reverse('design_project', args=[self.case.pk])
        response = self.client.get(url)
        self.assertContains(response, reverse('issues', args=[self.case.pk]))
        self.assertContains(response, reverse('factory_detail', args=[self.work.pk]))
        self.assertEqual(self.client.get(reverse('design_project', args=[self.other.pk])).status_code, 404)
        Grant.objects.filter(case=self.case, user=self.actor, action__in=['issue.read', 'finance.read']).update(active=False)
        response = self.client.get(url)
        self.assertNotContains(response, reverse('issues', args=[self.case.pk]))
        self.assertNotContains(response, reverse('factory_detail', args=[self.work.pk]))

    def test_project_journey_orders_work_and_limits_finance_and_assistant_to_current_scope(self):
        from apps.agents.assistant_models import AssistantConversation
        from apps.core.services import add_evidence
        from apps.workflows import factory_minutes
        from tests.meeting_helpers import MINUTES_DEFINITION

        self.client.force_login(self.actor)
        notes = add_evidence(self.actor, self.case.pk, 'meeting_notes', 'Sample chronology source', 'synthetic:journey')
        template = register_template(self.actor, self.case.pk, 'Journey minutes', MINUTES_DEFINITION,
                                     self.template_owner.pk, rev(self.case))
        selection = {'protocol': factory_minutes.PROTOCOL, 'evidence_id': notes.pk, 'template_id': template.pk,
                     'meeting_version_id': None, 'audience': 'internal', 'publish': False}
        for index in range(22):
            factory_minutes.start(self.actor, self.case.pk, f'sample-journey-{index}', f'SAMPLE-JOURNEY-{index:02}',
                                  selection, rev(self.case))
        path = reverse('design_project', args=[self.case.pk])
        page = self.client.get(path)
        self.assertContains(page, 'Project work, oldest first')
        self.assertEqual(page.context['journey']['items'][0]['id'], self.work.pk)
        self.assertEqual(page.context['journey']['total'], 23)
        self.assertEqual(page.context['journey']['waiting'], int(self.work.status in ('waiting', 'waiting_effect')))
        self.assertContains(page, 'Reviewed contract stages')
        self.assertContains(page, 'Invoice deliveries recorded')
        self.assertNotContains(page, 'SAMPLE-JOURNEY-21')
        self.assertContains(self.client.get(path, {'page': 2}), 'SAMPLE-JOURNEY-21')

        target = reverse('assistant_start', args=['tola'])
        selected = self.client.get(target, {'workspace': self.case.pk})
        self.assertEqual(selected.context['form'].initial['workspace'], self.case.pk)
        self.assertIsNone(self.client.get(target, {'workspace': self.other.pk}).context['form'].initial['workspace'])
        self.assertFalse(AssistantConversation.objects.exists())

        Grant.objects.filter(case=self.case, user=self.actor, action__in=['finance.read', 'agent.extract']).update(active=False)
        page = self.client.get(path)
        self.assertNotContains(page, 'Invoice deliveries recorded')
        self.assertNotContains(page, 'Ask Tola about this project')
        self.assertNotContains(page, reverse('factory_detail', args=[self.work.pk]))

    def test_leadership_reader_is_available_to_scoped_access_configuration(self):
        from apps.identity.actions import ACTIONS

        self.assertIn('report.read', ACTIONS)
        self.client.force_login(self.actor)
        url = reverse('leadership_report', args=[self.case.pk, 'monthly_executive'])
        self.assertContains(self.client.get(url), 'Prepare the monthly leadership report')
        self.assertEqual(self.client.get(reverse('leadership_report', args=[self.case.pk, 'unknown'])).status_code, 404)
        Grant.objects.filter(case=self.case, user=self.actor, action='report.read').update(active=False)
        self.assertEqual(self.client.get(url).status_code, 403)

    def test_onboarding_and_password_use_same_shell_and_do_not_grant_access(self):
        user = get_user_model().objects.create_user('new-operator', password='synthetic-new-account')
        response = self.client.post(reverse('login'), {'username': user.username, 'password': 'synthetic-new-account'},
                                    follow=True)
        self.assertContains(response, 'Ask for workspace access')
        self.assertContains(response, 'factory-design.css')
        self.assertFalse(Grant.objects.filter(user=user).exists())
        self.assertContains(self.client.get(reverse('password_change')), 'Save password')
        self.assertContains(self.client.get(reverse('case_create')), 'Workspace access needed')
        Grant.objects.create(case=self.case, user=user, action='case.read')
        self.assertRedirects(self.client.get(reverse('getting_started')), reverse('home'),
                             fetch_redirect_response=False)

    def test_project_tabs_use_current_grants_and_native_milestone(self):
        self.client.force_login(self.actor)
        Grant.objects.get_or_create(case=self.case, user=self.actor, action='milestone.complete')
        milestones = reverse('design_project_tab', args=[self.case.pk, 'milestones'])
        self.assertContains(self.client.get(milestones), 'Contract completion criterion')
        self.assertContains(self.client.get(reverse('design_project_tab', args=[self.case.pk, 'money'])), 'Open invoices and receipts')
        self.assertEqual(self.client.get(reverse('design_project_tab', args=[self.other.pk, 'milestones'])).status_code, 404)
        Grant.objects.filter(case=self.case, user=self.actor, action='finance.read').update(active=False)
        self.assertContains(self.client.get(reverse('design_project_tab', args=[self.case.pk, 'money'])),
                            'Finance access required',status_code=403)

    def test_exact_project_action_uses_native_ownership_deadline_and_revision(self):
        from django.utils import timezone
        from apps.pmo.meetings import create_action

        self.client.force_login(self.actor)
        item = create_action(self.actor, self.case.pk, 'SCREEN-ACTION', 'Check the approval evidence', self.actor.pk,
                             None, self.template_owner.pk, 'Synthetic action', rev(self.case))
        url = reverse('design_project_action', args=[self.case.pk, item.pk])
        self.assertContains(self.client.get(reverse('design_project_tab', args=[self.case.pk, 'actions'])), url)
        due = timezone.localtime().replace(second=0, microsecond=0)
        values = {'operation': 'assign', 'owner': self.actor.pk, 'due_at': due.isoformat(),
                  'evidence': self.template_owner.pk, 'reason': 'Deadline recorded', 'revision': rev(self.case), 'action_revision': 1}
        self.assertRedirects(self.client.post(url, values), url, fetch_redirect_response=False)
        item.refresh_from_db()
        self.assertEqual(item.current.due_at, due)
        self.assertContains(self.client.post(url, {**values, 'revision': rev(self.case)}), 'stale action revision')
        self.assertRedirects(self.client.post(url, {**values, 'operation': 'complete', 'revision': rev(self.case),
                             'action_revision': 2}), url, fetch_redirect_response=False)
        self.assertContains(self.client.get(url), 'Completed')
        actions=reverse('design_project_tab',args=[self.case.pk,'actions'])
        self.assertContains(self.client.get(actions,{'state':'completed','owner':self.actor.pk}),'Check the approval evidence')
        self.assertNotContains(self.client.get(actions,{'owner':'unassigned'}),'Check the approval evidence')
        self.assertContains(self.client.get(actions,{'owner':'999999999999'}),'Select a valid choice')
        foreign = reverse('design_project_action', args=[self.other.pk, item.pk])
        self.assertEqual(self.client.get(foreign).status_code, 404)

    def test_project_action_reassignment_preserves_progress_and_rejects_another_stale_owner(self):
        from datetime import timedelta
        from django.db import connection
        from django.utils import timezone
        from apps.pmo.meetings import change_action, create_action

        self.assertEqual(connection.vendor, 'postgresql')
        users = get_user_model().objects
        successor = users.create_user('next-project-action-owner')
        alternative = users.create_user('other-project-action-owner')
        Grant.objects.bulk_create([
            Grant(case=self.case, user=user, action=action)
            for user in (successor, alternative)
            for action in ('case.read', 'meeting.read', 'action.own', 'action.work')
        ])
        due = timezone.now() + timedelta(days=1, seconds=23)
        item = create_action(self.actor, self.case.pk, 'SCREEN-OWNER-CHANGE', 'Check the sample handover',
                             self.actor.pk, due, self.template_owner.pk, 'Fictional commitment', rev(self.case))
        started = change_action(self.actor, self.case.pk, item.pk, 'start', self.template_owner.pk,
                                'Started the fictional commitment', rev(self.case), 1)
        url = reverse('design_project_action', args=[self.case.pk, item.pk])
        self.client.force_login(self.actor)
        page = self.client.get(url)
        form = page.context['reassign_form']
        self.assertContains(page, 'The deadline and progress stay the same.')
        self.assertNotIn('due_at', form.fields)
        options = form.fields['owner'].queryset
        self.assertFalse(options.filter(pk=self.actor.pk).exists())
        self.assertEqual(options.filter(pk__in=(successor.pk, alternative.pk)).count(), 2)

        command = {'operation': 'reassign', 'owner': successor.pk, 'evidence': self.template_owner.pk,
                   'reason': 'Current sample owner takes over the action', 'revision': rev(self.case),
                   'action_revision': started.number}
        self.assertRedirects(self.client.post(url, {**command, 'due_at': (due + timedelta(days=1)).isoformat()}),
                             url, fetch_redirect_response=False)
        item.refresh_from_db()
        assigned = item.current
        self.assertEqual((assigned.owner_id, assigned.status, assigned.due_at, assigned.due_basis),
                         (successor.pk, 'in_progress', due, started.due_basis))
        self.assertEqual(list(item.states.order_by('number').values_list('number', 'owner_id', 'status', 'due_at')), [
            (1, self.actor.pk, 'open', due), (2, self.actor.pk, 'in_progress', due),
            (3, successor.pk, 'in_progress', due),
        ])
        page = self.client.get(url)
        self.assertNotContains(page, 'Complete action')
        self.assertContains(page, 'Current sample owner takes over the action')

        stale = {**command, 'owner': alternative.pk, 'revision': rev(self.case),
                 'reason': 'A stale second assignment must not replace the current owner'}
        page = self.client.post(url, stale)
        self.assertContains(page, 'stale action revision')
        self.assertContains(page, stale['reason'])
        item.refresh_from_db()
        self.assertEqual(item.current_id, assigned.pk)
        self.assertEqual(item.states.count(), 3)

        self.client.force_login(successor)
        page = self.client.get(url)
        self.assertIsNone(page.context['reassign_form'])
        self.assertContains(page, 'Complete action')
        self.assertEqual(self.client.post(url, {**stale, 'action_revision': assigned.number}).status_code, 403)
        item.refresh_from_db()
        self.assertEqual(item.current_id, assigned.pk)

    def test_department_assistant_entry_keeps_file_reviews_on_their_project(self):
        self.client.force_login(self.actor)
        assistant = reverse('design_agents')
        files = reverse('case_uploads', args=[self.case.pk])
        response = self.client.get(assistant)
        for title, _ in ROLES.values():
            self.assertNotContains(response, title)
        self.assertNotContains(response, f'{files}#agent-job-{self.job.pk}')
        self.assertNotContains(response, 'Private draft body')
        files_page = self.client.get(files)
        self.assertContains(files_page, 'Private draft body')
        self.assertContains(files_page, 'Queue a fresh draft with source excerpts')
        self.assertNotContains(files_page, 'Save as reviewed case evidence')
        Grant.objects.filter(case=self.case, user=self.actor, action='agent.extract').update(active=False)
        self.assertNotContains(self.client.get(assistant), 'permitted.txt')
        self.assertNotContains(self.client.get(files), 'Private draft body')

    def test_template_catalog_reads_controlled_versions_and_revokes_access(self):
        self.client.force_login(self.actor)
        Grant.objects.get_or_create(case=self.case, user=self.actor, action='document.template')
        Grant.objects.get_or_create(case=self.case, user=self.actor, action='document.read')
        for _ in range(2):
            register_template(self.actor, self.case.pk, 'Controlled weekly layout', DEFINITION,
                              self.template_owner.pk, rev(self.case))
        url = reverse('design_project_tab', args=[self.case.pk, 'templates'])
        response = self.client.get(url)
        self.assertContains(response, 'Controlled weekly layout · Version 2')
        self.assertContains(response, 'Controlled weekly layout · Version 1')
        self.assertContains(response, reverse('template_current', args=[self.case.pk]))
        self.assertEqual(self.client.get(url, {'templates': 'invalid'}).status_code, 400)
        Grant.objects.filter(case=self.case, user=self.actor, action='document.read').update(active=False)
        self.assertEqual(self.client.get(url).status_code, 403)

    @patch.dict(os.environ, {'OPENROUTER_MODEL': 'synthetic', 'OPENROUTER_API_KEY': 'synthetic'})
    def test_department_chat_does_not_offer_a_manual_specialist_dispatch(self):
        self.client.force_login(self.actor)
        assistant = reverse('design_agents')
        source = b'Synthetic acceptance evidence.\n'
        with patch('adapters.case_uploads.put') as store:
            for role in ROLES:
                response = self.client.post(assistant, {'workspace': self.case.pk, 'role': role,
                                                       'file': SimpleUploadedFile('source.txt', source)})
                self.assertEqual(response.status_code, 405)
            store.assert_not_called()
            self.assertFalse(AgentJob.objects.filter(upload__name='source.txt').exists())

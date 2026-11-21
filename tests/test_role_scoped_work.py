from datetime import timedelta
import os
from unittest.mock import patch
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import DatabaseError, connection, transaction
from django.http import Http404
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone
from jsonschema import Draft202012Validator, FormatChecker

from apps.core.factory_api.urls import contract
from apps.core.services import add_evidence
from apps.documents import controlled
from apps.identity import intake, role_factory_decisions, role_native_decisions, role_work, scope_moves, staff, teams
from apps.identity.models import Grant
from apps.identity.services import require
from apps.identity.staff_models import StaffInvitation
from apps.identity.team_models import StaffAssignment, StaffMembership, StaffReviewUse
from apps.policy.services import active_component, register_reference, transition
from tests.document_helpers import DEFINITION, drafted
from tests.helpers import activate, rev


PASSWORD = 'Synthetic feedback after review 42!'


class RoleScopedWorkTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        users = get_user_model().objects
        cls.root = users.create_superuser('team-fixture-root')
        cls.admin = users.create_user('team-fixture-admin')
        access = ['case.read', 'action.manage', 'action.own', 'action.work', 'evidence.add', 'document.read',
                  'document.draft', 'document.template', 'document.request_review', 'document.review_controlled',
                  'policy.configure', 'policy.activate', 'factory.read', 'report.read']
        cls.delegation_value = {'format':'psl.tenant-access/v3', 'create_cases':True, 'manage_access':True,
                                'kinds':['project'], 'allowed_actions':access, 'initial_actions':access,
                                'classification':'synthetic', 'staff_lifecycle':{'invite_minutes':30, 'allow_invite':True,
                                    'allow_deactivation':True, 'allow_profile_edit':True, 'allow_roster':True}}
        cls.expiry = timezone.now() + timedelta(hours=2)
        cls.delegation = intake.provision(cls.root, cls.admin, 'synthetic-team-scope', cls.delegation_value,
                                         cls.expiry, True, 'Synthetic workspace invitation authority')
        cls.case = intake.create_case(cls.admin, 'synthetic-team-scope', 'role-work', 'Synthetic project', 'project')
        cls.other = intake.create_case(cls.admin, 'synthetic-team-scope', 'role-work-other', 'Other synthetic project', 'project')
        cls.team = teams.create_team(cls.admin, cls.case.pk, 'pmo-lead', 'Planning team')
        cls.peer_team = teams.create_team(cls.admin, cls.case.pk, 'pmo-lead', 'Delivery team')

    def invitation(self, role, mode, team=None, *, username=None):
        username = username or 'synthetic-' + uuid4().hex[:12]
        actor = self.admin
        if mode=='member':
            actor = self.admitted(role,'lead',team).user
        return staff.invite_person(actor,self.case.pk,username,username,f'{username}@example.test',rev(self.case),
                                   role=role,mode=mode,team_id=team.pk if team else None)

    def admitted(self, role='pmo-lead', mode='member', team=None):
        if role == 'pmo-lead' and team is None:
            team = self.team
        _, token = self.invitation(role, mode, team)
        return StaffMembership.objects.select_related('user').get(user=staff.accept(token, PASSWORD))

    def assign(self, member, title):
        return role_work.assign_action(self.admin, self.case.pk, member.pk, reference=f'TASK-{uuid4()}',
                                      description=title, reason='Reviewed synthetic assignment', expected=rev(self.case))

    def api(self, path, data=None, *, client=None):
        client = client or self.client
        return client.get('/api/v1'+path) if data is None else client.post('/api/v1'+path, data, content_type='application/json')

    def checked(self, response, path, method='get'):
        self.assertEqual(response.status_code, 200, response.content[:500])
        self.assertIn('no-store', response['Cache-Control'])
        schema = contract()['paths']['/api/v1'+path][method]['responses']['200']['content']['application/json']['schema']
        Draft202012Validator(schema, format_checker=FormatChecker()).validate(response.json())
        return response.json()

    def test_admin_lands_on_my_work_without_business_approval_access(self):
        user = get_user_model().objects.create_user('staff-only-administrator',password=PASSWORD)
        value = {**self.delegation_value,'allowed_actions':['case.read','action.manage','evidence.add','action.own','action.work'],
                 'initial_actions':['case.read','action.manage','evidence.add']}
        intake.provision(self.root,user,'synthetic-staff-start',value,self.expiry,True,'Synthetic staff-only role')
        case = intake.create_case(user,'synthetic-staff-start','starter','Starter workspace','project')
        response = self.client.post(reverse('login'),{'username':user.username,'password':PASSWORD})
        self.assertRedirects(response,reverse('home'),fetch_redirect_response=False)
        page = self.client.get(reverse('home'))
        self.assertContains(page,'<h1>Admin</h1>',html=True)
        self.assertContains(page,'Manage teams and assignments')
        for label in ('Projects', 'Overview', 'Assistant', 'Start work', 'Menu'):
            self.assertContains(page, label)
        self.assertNotContains(page,self.case.title)
        dashboard = self.checked(self.api('/role-dashboard'),'/role-dashboard')
        self.assertEqual([(item['role'],item['mode']) for item in dashboard['positions']],[('admin','administrator')])
        self.assertEqual(dashboard['decisions'],[])
        self.assertEqual(dashboard['approval_desks'],[])
        self.assertEqual(self.client.get(dashboard['positions'][0]['manage_url']).status_code,200)
        for action in ('finance.read','finance.invoice.review','issue.escalation_decide'):
            with self.assertRaises(PermissionDenied):
                require(user,case,action)
        for role, label in (('pmo-lead','PMO Lead'),('finance-lead','Finance Lead')):
            team = teams.create_team(user,case.pk,role,label)
            _, token = staff.invite_person(user,case.pk,f'staff-start-{role}',label,f'{role}@example.test',
                                            rev(case),role=role,mode='lead',team_id=team.pk)
            staff.accept(token,PASSWORD,role_required=True)
            client = Client()
            client.post(reverse('login'),{'username':f'staff-start-{role}','password':PASSWORD})
            lead_page = client.get(reverse('home'))
            self.assertContains(lead_page,f'<h1>{label}</h1>',html=True)
            self.assertContains(lead_page,'Invite a teammate')
            self.assertNotContains(lead_page,'Manage teams and assignments')

    def test_role_accounts_keep_the_full_factory_shell_and_scoped_destinations(self):
        finance_team = teams.create_team(self.admin, self.case.pk, 'finance-lead', 'Finance')
        hr_team = teams.create_team(self.admin, self.case.pk, 'hr', 'People')
        positions = [
            (self.admitted(mode='lead'), ['tola'], 'engagement/v1'),
            (self.admitted('finance-lead', 'lead', finance_team), ['tola', 'chidi'], 'finance-accounts/v1'),
            (self.admitted('hr', 'lead', hr_team), ['zainab'], None),
            (self.admitted('cto', 'standalone'), [], None),
            (self.admitted('ceo', 'standalone'), [], None),
            (self.admitted(), [], None),
        ]
        for position, agents, starter in positions:
            with self.subTest(role=position.role, mode=position.mode):
                self.client.force_login(position.user)
                page = self.client.get(reverse('home'))
                self.assertContains(page, f'<h1>{teams.scope_label(position.role, position.mode)}</h1>', html=True)
                self.assertNotContains(page, 'Role dashboard')
                if position.mode == 'lead':
                    invite_url = reverse('staff_team_invite', args=[self.case.pk, position.team_id])
                    self.assertContains(page, invite_url)
                    self.assertContains(self.client.get(invite_url), f'href="{reverse("home")}"')
                else:
                    self.assertNotContains(page, 'Invite a teammate')
                for label in ('My work', 'Projects', 'Overview', 'Assistant', 'Start work', 'Menu'):
                    self.assertContains(page, label)
                profile = self.checked(self.api('/me'), '/me')
                keys = {entry['key'] for entry in profile['destinations']}
                self.assertTrue({'my_work', 'projects', 'overview', 'assistant', 'setup'} <= keys)
                self.assertNotIn('role_dashboard', keys)
                self.assertEqual(profile['assistant_agents'], agents)
                self.assertFalse(Grant.objects.filter(user=position.user, case=self.case, active=True).exists())
                for route in ('workspace_overview', 'design_overview', 'design_agents', 'factory_intake', 'design_setup'):
                    self.assertEqual(self.client.get(reverse(route)).status_code, 200)
                chooser = self.client.get(reverse('factory_intake'))
                self.assertContains(chooser, 'Log an engagement and connect planning')
                self.assertContains(chooser, 'Prepare management accounts')
                projects = self.checked(self.api('/projects'), '/projects')['items']
                self.assertEqual([row['case_id'] for row in projects], [str(self.case.pk)] if agents else [])
                self.assertEqual(self.client.get(reverse('design_project', args=[self.other.pk])).status_code, 404)
                self.assertEqual(self.client.get(reverse('case', args=[self.case.pk])).status_code, 404)
                if starter:
                    self.assertIn(starter, profile['startable_lines'])
                    self.assertContains(self.client.get(reverse('factory_create'), {'definition': starter}), self.case.pk)
                else:
                    self.assertEqual(profile['startable_lines'], [])

    def test_pmo_lead_can_start_native_work_and_team_scope_survives_navigation(self):
        from apps.workflows.models import FactoryWork

        preparer = self.admitted(mode='lead')
        teammate = self.admitted(mode='lead')
        outsider = self.admitted(mode='lead', team=self.peer_team)
        member = self.admitted()
        evidence = add_evidence(self.admin, self.case.pk, 'engagement_source', 'Synthetic client request', 'client brief')
        self.client.force_login(preparer.user)
        response = self.client.post(reverse('factory_create'), {
            'definition': 'engagement/v1', 'case': self.case.pk, 'key': 'role-navigation-engagement',
            'route': 'B', 'evidence': evidence.pk, 'reference': 'TEST-NEW-ENGAGEMENT', 'revision': rev(self.case),
        })
        self.assertEqual(response.status_code, 302, response.content[:1000])
        work = FactoryWork.objects.get(case=self.case, actor=preparer.user, definition='engagement/v1')
        self.assertRedirects(response, reverse('factory_detail', args=[work.pk]))
        self.assertContains(self.client.get(reverse('home'), {'queue': 'mine'}), 'TEST-NEW-ENGAGEMENT')
        for position, available in ((preparer, True), (teammate, True), (outsider, False), (member, False)):
            self.client.force_login(position.user)
            self.assertEqual(self.api(f'/work/{work.pk}').status_code, 200 if available else 404)
        for action in ('factory.execute', 'finance.read', 'document.review', 'delivery.planning_decide'):
            with self.assertRaises(PermissionDenied):
                require(preparer.user, self.case, action)
        teams.revoke(self.admin, self.case.pk, teammate.pk, 'Synthetic membership ended')
        self.client.force_login(teammate.user)
        self.assertEqual(self.api(f'/work/{work.pk}').status_code, 404)
        self.assertEqual(self.checked(self.api('/me'), '/me')['assistant_agents'], [])

    @patch.dict(os.environ, {'OPENROUTER_MODEL': 'synthetic', 'OPENROUTER_API_KEY': 'synthetic'})
    def test_lead_can_review_own_file_draft_without_case_wide_document_review(self):
        from apps.agents.models import AgentJob
        from apps.agents.upload_jobs import run_once
        from apps.documents.models import Review

        lead, other = self.admitted(mode='lead'), self.admitted(mode='lead', team=self.peer_team)
        source = b'Synthetic confirmed meeting date.'
        self.client.force_login(lead.user)
        with patch('adapters.case_uploads.put'):
            response = self.client.post(reverse('design_agents'), {
                'workspace': self.case.pk, 'role': 'A01',
                'file': SimpleUploadedFile('brief.txt', source, content_type='text/plain'),
            })
        self.assertEqual(response.status_code, 302, response.content[:500])
        job = AgentJob.objects.get(actor=lead.user)
        files = reverse('case_uploads', args=[self.case.pk])
        download = reverse('case_upload_download', args=[self.case.pk, job.upload_id])
        with patch('adapters.case_uploads.read', return_value=source), patch('adapters.openrouter.review',
                return_value={'summary': 'Synthetic meeting', 'quotes': ['1'], 'gaps': []}):
            self.assertTrue(run_once())
        self.assertContains(self.client.get(files), 'Synthetic meeting')
        self.client.force_login(other.user)
        self.assertEqual(self.client.get(download).status_code, 404)
        self.assertEqual(self.client.post(files, {'action': 'review', 'job': job.pk, 'note': 'Other lead'}).status_code, 404)
        self.client.force_login(lead.user)
        self.assertEqual(self.client.post(files, {'action': 'review', 'job': job.pk, 'note': 'Read original'}).status_code, 302)
        self.assertTrue(Review.objects.filter(actor=lead.user, evidence__kind='agent_review_note').exists())
        with self.assertRaises(PermissionDenied):
            require(lead.user, self.case, 'document.review')

    def update(self, row, operation):
        path = f'/role-work/{row.pk}'
        value = self.checked(self.api(path), '/role-work/{assignment_id}')
        return self.api(path+'/actions', {'operation':operation, 'expected':value['revision'], 'case_expected':value['case_revision'],
            'action_revision':value['action_revision'], 'reason':'Exact synthetic progress and outcome evidence'})

    def admission_in(self, actor, case, role, permissions):
        base = self.delegation_value.copy()
        base.update(create_cases=False, initial_actions=['case.read'], allowed_actions=sorted(permissions | {'case.read'}))
        delegation = intake.provision(self.root, actor, case.tenant, base, self.expiry, True, 'Synthetic delegated team desk')
        team = teams.create_team(actor, case.pk, role, 'Synthetic reviewers')
        name = 'scoped-reviewer-' + uuid4().hex[:10]
        _, token = staff.invite(actor,case.pk,name,'Synthetic reviewer',f'{name}@example.test',[],rev(case),
            role_scope={'role':role,'mode':'lead','team_id':team.pk}, expected_authority=delegation.pk)
        user = staff.accept(token,PASSWORD)
        return StaffMembership.objects.select_related('user').get(user=user)

    def decide(self, entry, verdict):
        path = f'/role-work/{entry.pk}'
        detail = self.checked(self.api(path), '/role-work/{assignment_id}')
        body = {'verdict':verdict,'note':'Reviewed exact synthetic native decision','expected':detail['revision'],
                'case_expected':detail['case_revision'],'token':detail['review']['token']}
        return self.checked(self.api(path+'/decision',body), '/role-work/{assignment_id}/decision', 'post')

    def add_nomination(self, actor, case, evidence, member, role):
        ref = register_reference(actor,case.pk,f'factory-review-scope:{member.pk}','schema:psl/role-assignment/v1',
                                 {'role':role,'user_id':member.user_id},evidence.pk)
        previous = active_component('D05.role_principal_assignments',case)
        return activate(actor,case,'D05.role_principal_assignments',[*previous.envelope['value'],ref.ref],evidence)

    def test_01_pmo_member_peer_lead_transfer_and_native_action(self):
        first, second = self.admitted(), self.admitted()
        lead, outsider = self.admitted(mode='lead'), self.admitted(mode='lead', team=self.peer_team)
        one, two = self.assign(first, 'Review planning milestones'), self.assign(second, 'Prepare risk follow-up')
        hidden = self.assign(outsider, 'Other team work')
        path = reverse('role_work_detail', args=[one.pk])
        self.client.force_login(first.user)
        own = self.checked(self.api('/role-dashboard'), '/role-dashboard')
        self.assertEqual([row['id'] for row in own['actions']], [one.pk])
        self.assertContains(self.client.get(path), 'Start work')
        self.assertEqual(self.client.get(reverse('role_work_detail', args=[two.pk])).status_code, 404)
        self.assertEqual(self.api(f'/role-work/{two.pk}').status_code, 404)
        self.assertEqual(self.client.get(reverse('case', args=[self.case.pk])).status_code, 404)
        self.assertEqual(self.api(f'/projects/{self.case.pk}').status_code, 404)
        with self.assertRaises(PermissionDenied):
            require(first.user, self.case, 'action.work')
        with self.assertRaises(ValidationError):
            intake.change_access(self.admin, self.case.pk, first.user_id, 'case.read', True, 'Would widen workspace access')
        with self.assertRaises(DatabaseError), transaction.atomic():
            Grant.objects.create(user=first.user, case=self.case, action='case.read')
        self.checked(self.update(one, 'start'), '/role-work/{assignment_id}/actions', 'post')

        self.client.force_login(lead.user)
        dashboard = self.checked(self.api('/role-dashboard'), '/role-dashboard')
        self.assertTrue(dashboard['has_teams'])
        self.assertEqual({row['id'] for row in dashboard['actions']}, {one.pk,two.pk})
        home = self.client.get(reverse('home'))
        self.assertContains(home, one.action.current.description)
        self.assertContains(home, two.action.current.description)
        self.assertNotContains(home, hidden.action.current.description)
        self.assertRedirects(self.client.get('/my-role/?page=2'),
                             reverse('home') + '?assignments_page=2#assignments', fetch_redirect_response=False)
        self.assertNotContains(self.client.get(path), 'Mark complete')
        self.assertEqual(self.update(one, 'complete').status_code, 403)
        self.assertEqual(self.api(f'/role-work/{hidden.pk}').status_code, 404)
        role_work.transfer(self.admin, self.case.pk, one.pk, second.pk, 'Reviewed handover to peer', rev(self.case))
        self.client.force_login(first.user)
        self.assertEqual(self.client.get(path).status_code, 404)
        self.client.force_login(second.user)
        self.assertEqual(self.update(one, 'complete').json()['state'], 'completed')
        one.action.refresh_from_db()
        self.assertEqual(one.action.current.owner_id, second.user_id)
        self.assertEqual(one.action.current.status, 'completed')
        teams.revoke(self.admin, self.case.pk, lead.pk, 'End synthetic team oversight')
        self.client.force_login(lead.user)
        self.assertEqual(self.api(f'/role-work/{one.pk}').status_code, 404)
        self.assertEqual(connection.vendor, 'postgresql')

    def test_02_real_pmo_approval_preserves_source_and_current_authority(self):
        reviewer, unassigned = self.admitted(mode='lead'), self.admitted()
        owner = add_evidence(self.admin, self.case.pk, 'policy_decision', 'Synthetic approval configuration', 'synthetic:role-work')
        source = add_evidence(self.admin, self.case.pk, 'completion', 'Synthetic report source', 'synthetic:role-work')
        ref = register_reference(self.admin, self.case.pk, 'team-approval-nomination', 'schema:psl/role-assignment/v1',
                                 {'role':'PMO Lead', 'user_id':reviewer.user_id}, owner.pk)
        cfg = activate(self.admin, self.case, 'D05.role_principal_assignments', [ref.ref], owner)
        template = controlled.register_template(self.admin, self.case.pk, 'Synthetic status report', DEFINITION, owner.pk, rev(self.case))
        from tests.document_helpers import artifact

        artifact(self.admin, self.case, 'D11.template_storage_retention_rules', 'schema:psl/document-storage/v1',
                 {'template_ids':[template.pk], 'repository':'internal-versioned','retention_days':30}, owner)
        version = drafted(self.admin, self.case, template, source)
        task = controlled.request_review(self.admin, self.case.pk, version.pk, rev(self.case))
        entry = role_work.assign_review(self.admin, self.case.pk, reviewer.pk, task.pk, rev(self.case))
        held = role_work.assign_review(self.admin, self.case.pk, unassigned.pk, task.pk, rev(self.case))
        self.client.force_login(unassigned.user)
        self.assertEqual(self.api('/role-dashboard').json()['decisions'], [])
        self.assertIsNone(self.api(f'/role-work/{held.pk}').json()['review'])
        self.assertEqual(self.api(f'/role-work/{entry.pk}').status_code, 404)

        self.client.force_login(reviewer.user)
        self.assertEqual([row['id'] for row in self.api('/role-dashboard').json()['decisions']], [entry.pk])
        self.assertContains(self.client.get(reverse('home'), {'queue': 'decisions'}),
                            reverse('role_work_detail', args=[entry.pk]))
        view = self.checked(self.api(f'/role-work/{entry.pk}'), '/role-work/{assignment_id}')
        self.assertEqual(view['review']['verdicts'], ['approve'])
        self.assertNotIn('PRIVATE TRACE', str(view))
        body = {'expected':view['revision'], 'case_expected':view['case_revision'], 'token':view['review']['token'],
                'verdict':'approve', 'note':'Independent review of the exact synthetic report'}
        url = f'/role-work/{entry.pk}/decision'
        self.assertEqual(self.api(url, {**body,'token':'0'*64}).status_code, 409)
        result = self.checked(self.api(url, body), '/role-work/{assignment_id}/decision', 'post')
        task.refresh_from_db()
        self.assertEqual(task.status, 'completed')
        self.assertEqual(StaffReviewUse.objects.get(review_id=result['review_id']).assignment_id, entry.pk)
        self.assertEqual(controlled.validate_review(self.case, version).pk, result['review_id'])
        self.assertEqual(self.api(url, body).status_code, 409)
        transition(self.admin, cfg.pk, 'revoked')
        with self.assertRaises((ValidationError, PermissionDenied)):
            controlled.validate_review(self.case, version)

    def test_03_all_six_roles_open_my_work_after_reviewed_invites(self):
        for role in teams.FOCUS:
            with self.subTest(role=role):
                standalone = role in ('ceo','cto')
                team = None if standalone else teams.create_team(self.admin, self.case.pk, role, f'Sample {role} team')
                mode = 'standalone' if standalone else 'member'
                row, token = self.invitation(role, mode, team)
                invite = Client()
                accept = reverse('staff_accept_invite')
                page = invite.post(accept, {'action':'preview','token':token})
                self.assertContains(page, teams.scope_label(role, mode))
                self.assertContains(page, teams.MODE_LABELS[mode])
                if team:
                    self.assertContains(page, team.name)
                result = invite.post(accept, {'action':'accept','token':token,'password':PASSWORD,'confirm':PASSWORD})
                self.assertRedirects(result, reverse('login'), fetch_redirect_response=False)
                member = StaffMembership.objects.select_related('user').get(invitation=row)
                self.assertEqual(member.role, role)
                self.assign(member, f'Own sample {role} assignment')
                target = invite.post(reverse('login'), {'username':row.username,'password':PASSWORD})
                self.assertRedirects(target, reverse('home'), fetch_redirect_response=False)
                value = self.checked(self.api('/role-dashboard', client=invite), '/role-dashboard')
                self.assertEqual(value['positions'][0]['role'], role)
                self.assertEqual([item['title'] for item in value['actions']], [f'Own sample {role} assignment'])
                self.assertEqual(value['decisions'], [])
                self.assertFalse(Grant.objects.filter(user=member.user, case=self.case, active=True).exists())
                self.assertEqual(invite.get(reverse('staff_teams', args=[self.case.pk])).status_code, 404)
                page = invite.get(reverse('home'))
                self.assertContains(page, f'<h1>{teams.scope_label(role, mode)}</h1>', html=True)
                self.assertContains(page, f'Own sample {role} assignment')
                with self.assertRaises(ValidationError):
                    staff.accept(token, PASSWORD)

    def test_04_admin_invite_form_pins_role_and_current_delegation(self):
        self.client.force_login(self.admin)
        url = reverse('staff_invites', args=[self.case.pk])
        page = self.client.get(url)
        self.assertContains(page, 'Role and work scope')
        posts = {**page.context['form'].initial,'username':'synthetic-invited-lead','name':'Synthetic lead',
                 'email':'synthetic-invited-lead@example.test', 'base_role':'pmo-lead','role_mode':'lead','team':self.team.pk}
        pending = self.client.post(url, posts)
        self.assertContains(pending, 'Invitation is ready')
        link = pending.context['invitation_link']
        token = link.split('#')[1]
        self.assertEqual(staff.pending(token).role_scope['team_id'], self.team.pk)
        intake.provision(self.root, self.admin, self.case.tenant, self.delegation_value, self.expiry,
                         True, 'Superseded synthetic invitation authority')
        with self.assertRaises(ValidationError):
            staff.accept(token, PASSWORD)
        self.assertNotContains(self.client.post(url, {**posts,'username':'synthetic-stale-invite'}), 'Invitation is ready')

    def test_05_bad_scope_and_cross_project_assignment_are_rejected(self):
        other = teams.create_team(self.admin, self.other.pk, 'pmo-lead', 'Outside team')
        lead = self.admitted(mode='lead')
        for args in [('ceo','lead',self.team),('hr','standalone',None),('pmo-lead','member',other),('hr','member',self.team)]:
            with self.subTest(args=args), self.assertRaises((PermissionDenied,ValidationError)):
                role,mode,team = args
                staff.invite_person(lead.user if mode=='member' else self.admin,self.case.pk,'invalid-role',
                    'Invalid role','invalid@example.test',rev(self.case),role=role,mode=mode,team_id=team.pk if team else None)
        member = self.admitted()
        with self.assertRaises(StaffMembership.DoesNotExist):
            role_work.assign_action(self.admin, self.other.pk, member.pk, reference='FOREIGN', description='A foreign project',
                                    reason='Rejected scope change', expected=rev(self.other))
        self.assertFalse(StaffAssignment.objects.filter(membership=member).exists())

    def test_06_finance_native_schedule_decision_and_current_output(self):
        from apps.finance import schedules
        from apps.policy.schedule_validators import AUTH
        from tests.schedule_helpers import fixture, inventory, policy

        f = fixture(username='scoped-schedule-preparer')
        actor, case, proof = f['actor'], f['case'], f['e']['policy_decision']
        member = self.admission_in(actor,case,'finance-lead',role_native_decisions.SCHEDULE_ACTIONS)
        nomination = register_reference(actor,case.pk,'scoped-finance-reviewer','schema:psl/role-assignment/v1',
                                        {'role':'Finance','user_id':member.user_id},proof.pk)
        old = active_component('D05.role_principal_assignments',case)
        activate(actor,case,'D05.role_principal_assignments',[*old.envelope['value'],nomination.ref],proof)
        cfg = policy(f,AUTH,{'independent_reviewer':True,'assignments':[{'user_id':member.user_id,'role':'Finance','purposes':['inventory']}]})
        work = inventory(f, reference='scoped-inventory')
        assignment = role_native_decisions.assign(actor,case.pk,member.pk,'schedule',work.pk,rev(case))
        self.client.force_login(member.user)
        self.assertEqual([item['id'] for item in self.api('/role-dashboard').json()['decisions']],[assignment.pk])
        result = self.decide(assignment,'approve')
        self.assertEqual(schedules.approved(work).pk,result['review_id'])
        self.assertEqual(self.api('/role-dashboard').json()['decisions'],[])
        self.assertFalse(Grant.objects.filter(user=member.user,case=case).exists())
        transition(actor,cfg.pk,'revoked')
        with self.assertRaises((PermissionDenied,ValidationError)):
            schedules.approved(work)

    def test_07_hr_native_correction_uses_exact_export_metadata(self):
        from apps.finance import hrfinance
        from apps.policy.hrfinance_validators import AUTHORITY, DISCLOSURE
        from tests.hrfinance_helpers import capture, fixture, policy

        f = fixture(configure=False)
        hr, case, finance, evidence = f['hr'], f['case'], f['finance'], f['e']
        member = self.admission_in(hr,case,'hr',role_native_decisions.HR_ACTIONS)
        nomination = register_reference(hr,case.pk,'scoped-hr-reviewer','schema:psl/role-assignment/v1',
                                        {'role':'HR','user_id':member.user_id},evidence['owner'].pk)
        old = active_component('D05.role_principal_assignments',case)
        activate(hr,case,'D05.role_principal_assignments',[*old.envelope['value'],nomination.ref],evidence['owner'])
        f['config']['authority']['assignments'][1]['user_id'] = member.user_id
        policy(hr,case,AUTHORITY,f['config']['authority'],evidence['owner'])
        policy(hr,case,DISCLOSURE,f['config']['disclosure'],evidence['owner'])
        f['contract'] = hrfinance.contract(finance,case.pk,f['need'].pk,'scope-setup',evidence['hr_contract_source'].pk,rev(case))
        hrfinance.decide(hr,case.pk,f['contract'].pk,'approve','scope-approval',evidence['hr_disclosure_decision'].pk,rev(case))
        snapshot = capture(f)
        correction = hrfinance.correction(finance,case.pk,snapshot.pk,'scope-correction',evidence['hr_correction_request'].pk,rev(case))
        successor = capture(f,key='scope-successor',source_version='scope-v2')
        with self.assertRaises(Http404):
            role_native_decisions.assign(hr,case.pk,member.pk,'hr',correction.pk,rev(case),snapshot.pk)
        assignment = role_native_decisions.assign(hr,case.pk,member.pk,'hr',correction.pk,rev(case),successor.pk)
        self.client.force_login(member.user)
        value = self.checked(self.api(f'/role-work/{assignment.pk}'), '/role-work/{assignment_id}')
        self.assertNotIn('employee_id', str(value))
        decision = self.decide(assignment,'approve')
        response = hrfinance.correction_disposition(correction).get(pk=decision['review_id'])
        self.assertEqual(response.snapshot_id, successor.pk)
        self.assertTrue(response.payload['new_finance_receipt_required'])
        self.assertFalse(response.payload['source_write'])
        self.assertEqual(self.api('/role-dashboard').json()['decisions'],[])
        with self.assertRaises(PermissionDenied):
            hrfinance.read_snapshot(member.user, successor)

    def test_08_reviewed_move_carries_existing_actions_and_keeps_other_workspace_access(self):
        from apps.pmo.meetings import create_action

        person = get_user_model().objects.create_user('existing-synthetic-pmo')
        accesses = ('case.read','action.own','action.work','report.read')
        for action in accesses:
            intake.change_access(self.admin,self.case.pk,person.pk,action,True,'Synthetic original project access')
        intake.change_access(self.admin,self.other.pk,person.pk,'case.read',True,'Independent project access')
        proof = add_evidence(self.admin,self.case.pk,'project_note','Synthetic action ownership proof','synthetic:role-move')
        item = create_action(self.admin,self.case.pk,'CURRENT-PMO-ACTION','Carry my PMO work',person.pk,None,
                             proof.pk,'Original action commitment',rev(self.case))
        query = {'role':'pmo-lead','mode':'member','team_id':self.team.pk}
        url = f'/setup/{self.case.pk}/people/{person.pk}/team-scope'
        self.client.force_login(self.admin)
        page = self.client.get(reverse('staff_scope_move',args=[self.case.pk,person.pk]),query)
        self.assertContains(page,'Carry my PMO work')
        self.assertContains(page,'View the workspace')
        preview = self.checked(self.api(url+'?role=pmo-lead&mode=member&team_id='+str(self.team.pk)),
                               '/setup/{case_id}/people/{person_id}/team-scope')
        self.assertCountEqual(preview['removed'],accesses)
        self.assertEqual(preview['carried_actions'][0]['id'],item.pk)
        pin = {'fingerprint':preview['fingerprint'],'operation':str(uuid4()),'reason':'Reviewed synthetic team transition','confirmed':True}
        intake.change_access(self.admin,self.case.pk,person.pk,'report.read',True,'Changed the current access record')
        self.assertEqual(self.api(url,{**query,**pin}).status_code,409)
        preview = self.api(url+'?role=pmo-lead&mode=member&team_id='+str(self.team.pk)).json()
        body = {**query,**pin,'fingerprint':preview['fingerprint']}
        moved = self.checked(self.api(url,body),'/setup/{case_id}/people/{person_id}/team-scope','post')
        self.assertEqual(self.api(url,body).json(),moved)
        self.assertEqual(self.api(url,{**body,'reason':'Different request'}).status_code,409)
        assignment = StaffAssignment.objects.get(membership_id=moved['membership_id'],action=item)
        self.assertFalse(Grant.objects.filter(case=self.case,user=person,active=True).exists())
        self.assertEqual(item.current.owner_id,person.pk)
        require(person,self.other,'case.read')
        self.client.force_login(person)
        self.assertEqual(self.api(f'/projects/{self.case.pk}').status_code,404)
        self.assertEqual(self.api(f'/projects/{self.other.pk}').status_code,200)
        self.assertEqual(self.update(assignment,'complete').json()['state'],'completed')

    def test_09_move_holds_while_an_existing_decision_is_claimed(self):
        from apps.workflows.models import HumanTask

        person = get_user_model().objects.create_user('existing-synthetic-reviewer')
        intake.change_access(self.admin,self.case.pk,person.pk,'case.read',True,'Original reviewer access')
        HumanTask.objects.create(case=self.case,kind='factory_review',factory_key='synthetic-move-held-decision',
                                 created_by=self.admin,claimed_by=person)
        query = (self.admin,self.case,person.pk,'pmo-lead','member',self.team.pk)
        preview = scope_moves.prepare(*query)
        self.assertIn('Release this person’s open decision claims first.',preview['holds'])
        with self.assertRaises(ValidationError):
            scope_moves.apply(self.admin,self.case.pk,*query[2:],preview['fingerprint'],uuid4(),'Reviewed scope move')
        require(person,self.case,'case.read')
        self.assertFalse(StaffMembership.objects.filter(user=person).exists())

    def test_10_scoped_invoice_decision_reaches_native_review_without_issuing(self):
        from apps.finance import invoices
        from apps.finance.models import InvoiceIssue, InvoiceJob
        from apps.workflows import factory
        from tests.factory_helpers import fixture
        from tests.obligation_helpers import factory_identified

        f = fixture(username='scope-invoice-preparer')
        a,case,work = f['actor'],f['case'],f['work']
        member = self.admission_in(a,case,'finance-lead',role_factory_decisions.permissions(work,'invoice'))
        self.add_nomination(a,case,f['evidence']['policy_decision'],member,'Finance')
        factory.run_until_wait(work.pk)
        work = factory_identified(f)
        self.client.force_login(a)
        native = self.checked(self.api('/role-dashboard'),'/role-dashboard')
        self.assertTrue(any(item['work_id']==work.pk for item in native['workspace_decisions']))
        result = self.checked(self.api(f'/setup/{case.pk}/team-decisions',{'membership_id':member.pk,
            'work_id':work.pk,'kind':'invoice','expected':rev(case)}),'/setup/{case_id}/team-decisions','post')
        row = StaffAssignment.objects.get(pk=result['assignment_id'],work=work)
        current = factory.manage(a,work.pk,work.revision,'resume')
        factory.run_until_wait(current.pk)
        self.client.force_login(member.user)
        self.assertEqual(self.api(f'/work/{work.pk}').status_code,404)
        result = self.decide(row,'approve')
        self.assertEqual(invoices.reviewed(work.invoice).pk,result['review_id'])
        self.assertFalse(InvoiceJob.objects.filter(invoice=work.invoice).exists())
        self.assertFalse(InvoiceIssue.objects.filter(invoice=work.invoice).exists())
        self.assertFalse(Grant.objects.filter(user_id=member.user_id,case=case,active=True).exists())
        teams.revoke(a,case.pk,member.pk,'Synthetic reviewer left the role')
        with self.assertRaises((ValidationError,PermissionDenied)):
            invoices.reviewed(work.invoice)

    def test_11_scoped_planning_approval_reaches_current_native_gate(self):
        from django.db import connection

        from apps.pmo import delivery
        from tests.test_factory_delivery import setup

        f = setup()
        for kind in delivery.PLANNING:
            f.source(kind,{'requires_ui':False,'client_signoff_required':False} if kind=='ui_applicability' else {})
        member = self.admission_in(f.actor,f.case,'pmo-lead',role_factory_decisions.permissions(f.work,'planning'))
        self.add_nomination(f.actor,f.case,f.e['policy_decision'],member,'PMO Lead')
        row = role_factory_decisions.assign(f.actor,f.case.pk,member.pk,f.work.pk,'planning',f.d.pk,f.e['plan'].pk,rev(f.case))
        self.client.force_login(member.user)
        result = self.decide(row,'approve')
        self.assertEqual(delivery.approved_plan(f.d).pk,result['review_id'])
        with connection.cursor() as cursor:
            cursor.execute('SELECT psl_progress_plan(%s)',[result['review_id']])
            self.assertTrue(cursor.fetchone()[0])
        self.assertFalse(Grant.objects.filter(user_id=member.user_id,case=f.case,active=True).exists())
        teams.revoke(f.actor,f.case.pk,member.pk,'Synthetic Planning reviewer left')
        with self.assertRaises(PermissionDenied):
            delivery.approved_plan(f.d)
        with connection.cursor() as cursor:
            cursor.execute('SELECT psl_progress_plan(%s)',[result['review_id']])
            self.assertFalse(cursor.fetchone()[0])

    def test_12_scoped_accounting_subject_review_uses_native_routing(self):
        from django.db import connection

        from apps.finance import analysis
        from apps.workflows import factory
        from apps.workflows.models import HumanTask
        from tests.factory_accounting_helpers import configured
        from tests.finance_analysis_helpers import fixture, METRICS

        a,case,proof,_,_,source,template,_ = fixture(username='scoped-accounting-preparer',recipient_username='scoped-accounting-recipient')
        work = configured(a,case,proof,source,template,METRICS)['work']
        member = self.admission_in(a,case,'finance-lead',role_factory_decisions.permissions(work,'accounting'))
        self.add_nomination(a,case,proof['policy_decision'],member,'Finance')
        factory.run_until_wait(work.pk)
        task = HumanTask.objects.filter(case=case,kind='factory_accounting_review',status='open').order_by('pk').first()
        self.assertIsNotNone(task)
        packet = task.context['packet']
        row = role_factory_decisions.assign(a,case.pk,member.pk,work.pk,'accounting',task.pk,None,rev(case))
        work.refresh_from_db()
        factory.manage(a,work.pk,work.revision,'resume')
        factory.run_until_wait(work.pk)
        self.client.force_login(member.user)
        result = self.decide(row,'approve')
        approved = analysis.current_review(case,packet['purpose'],**{packet['subject']+'_id':packet['target']})
        self.assertEqual(approved['id'],result['review_id'])
        self.assertTrue(approved['valid'])
        with connection.cursor() as cursor:
            cursor.execute('SELECT psl_schedules_finance_review_current(%s)',[result['review_id']])
            self.assertTrue(cursor.fetchone()[0])

    def test_13_scoped_head_closure_decision_allows_native_finalisation(self):
        from apps.pmo.models import DeliveryRecord
        from apps.workflows import factory, factory_closure
        from tests.signature_helpers import reaffirm_for
        from tests.test_delivery import DeliveryFixture
        from tests.test_factory_closure import setup

        f = DeliveryFixture()
        f.setup_delivery()
        member = self.admission_in(f.actor,f.case,'pmo-lead',{'case.read','delivery.read','factory.read','delivery.closure_decide'})
        self.add_nomination(f.actor,f.case,f.e['policy_decision'],member,'Head of PMO')
        reaffirm_for(f.actor,f.case)
        f.closure_selected = f.closing()
        f = setup(base=f)
        factory.run_until_wait(f.work.pk)
        f.work.refresh_from_db()
        version = factory_closure.document(f.work)
        row = role_factory_decisions.assign(f.actor,f.case.pk,member.pk,f.work.pk,'closure',version.pk,f.e['requirements'].pk,rev(f.case))
        self.client.force_login(member.user)
        result = self.decide(row,'approve')
        self.assertFalse(DeliveryRecord.objects.filter(dossier=f.d,kind='closure').exists())
        factory.run_until_wait(f.work.pk)
        f.work.refresh_from_db()
        self.assertEqual(factory_closure.verify(f.work)['decision'],result['review_id'])

    def test_14_scoped_go_live_document_review_keeps_signoff_separate(self):
        from apps.documents.controlled import validate_review
        from apps.documents.models import PublicationReceipt
        from apps.pmo.models import DeliveryRecord
        from apps.workflows import factory, factory_go_live
        from tests.signature_helpers import reaffirm_for
        from tests.test_delivery import DeliveryFixture
        from tests.test_factory_go_live import setup

        f = DeliveryFixture()
        f.setup_delivery()
        member = self.admission_in(f.actor,f.case,'pmo-lead',{'case.read','delivery.read','factory.read',
                                                            'document.read','document.review_controlled'})
        self.add_nomination(f.actor,f.case,f.e['policy_decision'],member,'PMO Lead')
        reaffirm_for(f.actor,f.case)
        f.release()
        f = setup(base=f)
        factory.run_until_wait(f.work.pk)
        f.work.refresh_from_db()
        version = factory_go_live.document(f.work)
        row = role_factory_decisions.assign(f.actor,f.case.pk,member.pk,f.work.pk,'document',version.pk,None,rev(f.case))
        self.client.force_login(member.user)
        result = self.decide(row,'approve')
        self.assertEqual(validate_review(f.case,version).pk,result['review_id'])
        factory.run_until_wait(f.work.pk)
        f.work.refresh_from_db()
        receipt = PublicationReceipt.objects.get(publication__version=version)
        self.assertEqual(receipt.publication.review_id,result['review_id'])
        self.assertEqual(receipt.publication.actor_id,f.publisher.pk)
        self.assertFalse(DeliveryRecord.objects.filter(dossier=f.d,kind='go_live').exists())

    def test_15_scoped_client_escalation_requires_a_separate_communication_review(self):
        from apps.documents.models import Publication
        from apps.pmo import escalations
        from apps.workflows import factory_escalation
        from tests.test_factory_escalation import FactoryEscalationTests

        f = FactoryEscalationTests()
        f.setUp()
        member = self.admission_in(f.a,f.c,'pmo-lead',{'case.read','issue.read','factory.read','issue.escalation_decide'})
        self.add_nomination(f.a,f.c,f.owner,member,'Head of PMO')
        work = f.start()
        f.advance()
        row = role_factory_decisions.assign(f.a,f.c.pk,member.pk,work.pk,'escalation',f.r.pk,None,rev(f.c))
        self.client.force_login(member.user)
        result = self.decide(row,'approve')
        self.assertEqual(escalations.approved_request(f.c,f.r).pk,result['review_id'])
        f.advance()
        self.assertIsNotNone(factory_escalation.document(f.w),f.w.finding)
        self.assertFalse(Publication.objects.filter(factory_work=f.w).exists())
        f.review()
        self.assertEqual(f.finish()['decision'],result['review_id'])

    def test_16_my_work_links_only_current_specialist_desks_in_that_workspace(self):
        reviewer = get_user_model().objects.create_user(username='synthetic-specialist-desk-reviewer')
        Grant.objects.bulk_create([
            Grant(user=reviewer,case=self.case,action=action)
            for action in ('case.read','payment.read','finance.read','delivery.read','payment.exception.decide','rfp.read')
        ] + [
            Grant(user=reviewer,case=self.other,action=action)
            for action in ('case.read','rfp.review','finance.forecast.review')
        ])
        self.client.force_login(reviewer)
        url = reverse('payment_controls',args=[self.case.pk])
        response = self.checked(self.api('/role-dashboard'),'/role-dashboard')
        self.assertEqual([desk['url'] for desk in response['approval_desks']],[url])
        self.assertContains(self.client.get(reverse('home'), {'queue': 'decisions'}),url)
        self.assertEqual(self.client.get(url).status_code,200)
        Grant.objects.filter(user=reviewer,case=self.case,action='payment.exception.decide').update(active=False)
        self.assertEqual(self.checked(self.api('/role-dashboard'),'/role-dashboard')['approval_desks'],[])

    def test_17_scoped_weekly_report_review_uses_outward_projection_only(self):
        from apps.documents.models import PublicationReceipt
        from apps.workflows import factory_reporting
        from tests.test_factory_reporting import FactoryReportingTests

        f = FactoryReportingTests()
        f.setUp()
        member = self.admission_in(f.actor,f.case,'pmo-lead',{'case.read','report.read','factory.read',
                                                            'document.read','document.review_controlled'})
        self.add_nomination(f.actor,f.case,f.owner,member,'PMO Lead')
        work = f.start_work()
        f.advance()
        version = factory_reporting.document(f.work)
        self.assertIsNotNone(version,f.work.finding)
        row = role_factory_decisions.assign(f.actor,f.case.pk,member.pk,work.pk,'document',version.pk,None,rev(f.case))
        self.client.force_login(member.user)
        page = self.client.get(reverse('role_work_detail',args=[row.pk]))
        self.assertContains(page,f.narrative['status'])
        self.assertNotContains(page,'PRIVATE DIAGNOSIS')
        self.assertEqual(self.api(f'/work/{work.pk}').status_code,404)
        with self.assertRaises(PermissionDenied):
            require(member.user,f.case,'meeting.read')
        result = self.decide(row,'approve')
        f.advance()
        receipt = PublicationReceipt.objects.get(publication__version=version)
        self.assertEqual(receipt.publication.review_id,result['review_id'])
        self.assertEqual(factory_reporting.verify(f.work)['receipt_ids'],[receipt.pk])

    def test_18_pmo_finance_and_hr_leads_invite_only_their_team_members(self):
        for role, label in (('pmo-lead','PMO'),('finance-lead','Finance'),('hr','HR')):
            team = teams.create_team(self.admin,self.case.pk,role,label)
            lead = self.admitted(role,'lead',team)
            self.client.force_login(lead.user)
            url = reverse('staff_team_invite',args=[self.case.pk,team.pk])
            dashboard = self.checked(self.api('/role-dashboard'),'/role-dashboard')
            self.assertEqual(dashboard['positions'][0]['invite_url'],url)
            other_team = self.peer_team if role=='pmo-lead' else self.team
            self.assertEqual(self.client.get(reverse('staff_team_invite',args=[self.case.pk,other_team.pk])).status_code,404)
            self.assertEqual(self.client.get(reverse('staff_invites',args=[self.case.pk])).status_code,404)
            page = self.client.get(url)
            post = {**page.context['form'].initial,'username':f'synthetic-managed-{role}','name':label+' Test Member',
                    'email':f'{role}-member@example.test'}
            self.assertNotContains(self.client.post(url,{**post,'base_role':'ceo'}),'Invitation is ready')
            with self.assertRaises(PermissionDenied):
                staff.invite_person(lead.user,self.case.pk,post['username'],post['name'],post['email'],rev(self.case),
                                    role='finance-lead' if role!='finance-lead' else 'hr',mode='member',team_id=team.pk)
            response = self.client.post(url,post)
            self.assertContains(response,'Invitation is ready')
            token = response.context['invitation_link'].split('#')[1]
            join = reverse('staff_accept_invite')
            recipient = Client()
            self.assertContains(recipient.post(join,{'action':'preview','token':token}),team.name)
            self.assertEqual(recipient.post(join,{'token':token,'password':PASSWORD,'confirm':PASSWORD}).status_code,302)
            member = StaffMembership.objects.get(user__username=post['username'])
            self.assertEqual((member.role,member.mode,member.team_id),(role,'member',team.pk))
            self.assertEqual(member.invitation.inviting_membership_id,lead.pk)
            self.assertFalse(Grant.objects.filter(user=member.user,case=self.case).exists())
            self.client.force_login(member.user)
            self.assertEqual(self.client.get(url).status_code,404)
            self.client.force_login(self.admin)
            self.assertContains(self.client.get(reverse('staff_roster'),{'q':post['username']}),post['name'])
            self.assertContains(self.client.get(reverse('staff_person',args=[member.user_id])),team.name)

    def test_19_unscoped_links_and_revoked_lead_links_cannot_create_accounts(self):
        join = reverse('staff_accept_invite')
        _,old_token = staff.invite(self.admin,self.case.pk,'earlier-pending','Earlier colleague',
                                    'legacy@example.test',['case.read'],rev(self.case))
        lead = self.admitted(mode='lead')
        pending,token = staff.invite_person(lead.user,self.case.pk,'pending-member','Pending colleague','pending@example.test',
                                           rev(self.case),role='pmo-lead',mode='member',team_id=self.team.pk)
        teams.revoke(self.admin,self.case.pk,lead.pk,'Synthetic lead handover')
        for code in (old_token, token):
            self.assertContains(self.client.post(join,{'action':'preview','token':code}),'invitation is unavailable')
            response = self.client.post(join,{'token':code,'password':PASSWORD,'confirm':PASSWORD})
            self.assertContains(response,'invitation',status_code=200)
        self.assertFalse(get_user_model().objects.filter(username__in=['earlier-pending','pending-member']).exists())
        with self.assertRaises(PermissionDenied):
            staff.invite_person(self.admin,self.case.pk,'blocked-admin','Blocked Admin','blocked@example.test',
                rev(self.case),role='pmo-lead',mode='member',team_id=self.team.pk)
        with self.assertRaises(DatabaseError), transaction.atomic():
            StaffInvitation.objects.create(case=self.case,username='unreviewed-role',name='Unreviewed role',
                email='unreviewed@example.test',actions=[],role_scope=teams.scope_pin(self.case,'pmo-lead','member',self.team.pk),
                number=1,token_hash=uuid4().hex*2,expires_at=timezone.now()+timedelta(minutes=15),
                actor=lead.user,authority=self.delegation,inviting_membership=lead)
        next_lead = self.admitted(mode='lead')
        self.client.force_login(next_lead.user)
        path = reverse('staff_team_renew',args=[self.case.pk,self.team.pk,pending.pk])
        form = self.client.get(path).context['form']
        response = self.client.post(path,form.initial)
        self.assertContains(response,'Invitation is ready')
        current = StaffInvitation.objects.get(case=self.case,username=pending.username,number=2)
        self.assertEqual(current.inviting_membership_id,next_lead.pk)

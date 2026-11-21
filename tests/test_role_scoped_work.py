from datetime import timedelta
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import DatabaseError, connection, transaction
from django.http import Http404
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone
from jsonschema import Draft202012Validator, FormatChecker

from apps.core.factory_api.urls import contract
from apps.core.services import add_evidence
from apps.documents import controlled
from apps.identity import intake, role_native_decisions, role_work, staff, teams
from apps.identity.models import Grant
from apps.identity.services import require
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
        return staff.invite(self.admin, self.case.pk, username, username, f'{username}@example.test', [], rev(self.case),
                            expected_authority=self.delegation.pk,
                            role_scope={'role':role, 'mode':mode, 'team_id':team.pk if team else None})

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

    def test_03_all_six_role_dashboards_and_reviewed_invites(self):
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
                self.assertRedirects(target, reverse('role_dashboard'), fetch_redirect_response=False)
                value = self.checked(self.api('/role-dashboard', client=invite), '/role-dashboard')
                self.assertEqual(value['positions'][0]['role'], role)
                self.assertEqual([item['title'] for item in value['actions']], [f'Own sample {role} assignment'])
                self.assertEqual(value['decisions'], [])
                self.assertFalse(Grant.objects.filter(user=member.user, case=self.case, active=True).exists())
                self.assertEqual(invite.get(reverse('staff_teams', args=[self.case.pk])).status_code, 404)
                self.assertContains(invite.get(reverse('role_dashboard')), teams.FOCUS[role][1])
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
        for args in [('ceo','lead',self.team),('hr','standalone',None),('pmo-lead','member',other),('hr','member',self.team)]:
            with self.subTest(args=args), self.assertRaises(ValidationError):
                self.invitation(*args)
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

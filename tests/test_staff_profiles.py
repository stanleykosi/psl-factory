"""Named access uses native grants; it cannot nominate project decision makers."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from threading import Barrier
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied,ValidationError
from django.db import DatabaseError,close_old_connections,connection,transaction
from django.test import TestCase,TransactionTestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from apps.core.models import Case
from apps.documents.contracts import digest
from apps.identity import intake,staff,staff_profiles
from apps.identity.intake_models import AccessChange,TenantAuthority
from apps.identity.models import Grant
from apps.identity.staff_models import StaffAdmission,StaffInvitation,StaffProfileChange
from apps.policy.models import Configuration
from tests.helpers import rev
from tests.test_staff_accounts import fixture


PROFILES=[{'key':'sample-contributor','label':'SAMPLE project contributor',
           'actions':['case.read','action.own','meeting.read']},
          {'key':'sample-reader','label':'SAMPLE workspace reader','actions':['case.read']}]


def configured():
    data=fixture();value=deepcopy(data['value'])
    value['staff_lifecycle'].update(profiles=deepcopy(PROFILES),allow_profile_edit=True,allow_reactivation=None)
    data['authority']=intake.provision(data['root'],data['actor'],'staff-accounts',value,
        data['authority'].expires_at,True,'Synthetic named access profiles, not project nominations')
    data['value']=value
    return data


def apply(data,**kwargs):
    case=data['scopes'][0]['case'];case.refresh_from_db()
    prepared=staff_profiles.review(data['actor'],case,data['target'].pk)
    return staff_profiles.apply(data['actor'],case.pk,data['target'].pk,kwargs.get('key','sample-contributor'),
        kwargs.get('fingerprint',prepared['fingerprint']),'Synthetic reviewed access change',kwargs.get('operation',uuid4()))


class StaffProfileTests(TestCase):
    @classmethod
    def setUpTestData(cls):cls.data=configured()

    def test_historical_profiles_keep_their_history_but_cannot_admit_staff_in_the_app(self):
        data = self.data
        starting, additional = [scope['case'] for scope in data['scopes']]
        actor = data['actor']
        self.client.force_login(actor)
        path = reverse('staff_invites', args=[starting.pk])
        form = self.client.get(path).context['form']
        response = self.client.post(path, {
            'name': 'Sample invited staff', 'username': 'sample-cross-workspace-invite', 'email': 'cross-sample@example.invalid',
            'profile': 'sample-reader', 'revision': rev(starting), 'project_review': form.initial['project_review'],
            f'profile_{additional.pk.hex}': 'sample-contributor',
        })
        self.assertNotContains(response,'Invitation is ready')
        invitation, token = staff.invite(actor,starting.pk,'sample-cross-workspace-invite','Sample invited staff',
            'cross-sample@example.invalid',['case.read'],rev(starting),profile_key='sample-reader',
            expected_authority=data['authority'].pk,workspace_choices={additional.pk:(rev(additional),'sample-contributor')})
        self.assertEqual(invitation.workspace_profiles, [staff.workspace_pin(additional, PROFILES[0])])
        self.client.logout()
        accept_path = reverse('staff_accept_invite')
        preview = self.client.post(accept_path, {'action': 'preview', 'token': token})
        self.assertContains(preview,'invitation is unavailable')
        self.assertFalse(StaffAdmission.objects.filter(invitation=invitation).exists())
        person = staff.accept(token, 'Synthetic!access.acceptance.204')
        grants = set(Grant.objects.filter(user=person, active=True).values_list('case_id', 'action'))
        self.assertEqual(grants, {(starting.pk, 'case.read'), *((additional.pk, action) for action in PROFILES[0]['actions'])})
        self.assertEqual(staff_profiles.labels([starting.pk, additional.pk], person.pk),
                         {starting.pk: PROFILES[1]['label'], additional.pk: PROFILES[0]['label']})
        self.assertEqual(StaffProfileChange.objects.filter(invitation=invitation).count(), 2)
        with self.assertRaises(ValidationError):
            staff.accept(token, 'Synthetic!access.repeated.204')

    def test_all_current_project_invitation_never_grants_a_later_project_or_a_stale_scope(self):
        data = self.data
        starting, additional = [scope['case'] for scope in data['scopes']]
        actor = data['actor']
        invite_args = (actor, starting.pk, 'sample-all-projects', 'Sample staff member', 'sample-all@example.invalid',
                       ['case.read'], rev(starting))
        with self.assertRaisesMessage(ValidationError, 'managed project list changed'):
            staff.invite(*invite_args, profile_key='sample-reader', all_current_projects=True,
                         expected_authority=data['authority'].pk)
        with self.assertRaisesMessage(ValidationError, 'same named profile'):
            staff.invite(*invite_args, profile_key='sample-reader', all_current_projects=True,
                         expected_authority=data['authority'].pk,
                         workspace_choices={additional.pk: (rev(additional), PROFILES[0]['key'])})
        invitation, token = staff.invite(*invite_args, profile_key='sample-reader', all_current_projects=True,
                                         expected_authority=data['authority'].pk,
                                         workspace_choices={additional.pk: (rev(additional), 'sample-reader')})
        newer = intake.create_case(actor, starting.tenant, 'later-workspace', 'Later managed project', 'project')
        person = staff.accept(token, 'Synthetic!access.snapshot.704')
        self.assertFalse(Grant.objects.filter(user=person, case=newer).exists())
        self.assertEqual(set(StaffProfileChange.objects.filter(invitation=invitation).values_list('case_id', flat=True)),
                         {starting.pk, additional.pk})
        _, withdrawn = staff.invite(actor, starting.pk, 'sample-withdrawn-scope', 'Sample withdrawn invitation',
                                    'withdrawn@example.invalid', ['case.read'], rev(starting), profile_key='sample-reader',
                                    expected_authority=data['authority'].pk,
                                    workspace_choices={additional.pk: (rev(additional), 'sample-reader')})
        intake.change_access(actor, additional.pk, actor.pk, 'case.read', False, 'Synthetic loss of management access')
        with self.assertRaises(PermissionDenied):
            staff.accept(withdrawn, 'Synthetic!access.withdrawn.31')
        self.assertFalse(get_user_model().objects.filter(username='sample-withdrawn-scope').exists())

    def test_invite_revalidates_reviewed_authority_before_resolving_extra_profiles(self):
        data = self.data
        starting, additional = [scope['case'] for scope in data['scopes']]
        authority = data['authority']
        reviewed_choices = {additional.pk: (rev(additional), PROFILES[0]['key'])}
        widened = deepcopy(data['value'])
        widened['staff_lifecycle']['profiles'][0]['actions'].append('policy.read')
        intake.provision(data['root'], data['actor'], starting.tenant, widened, authority.expires_at,
                         True, 'Synthetic profile definitions changed after review')
        with self.assertRaisesMessage(ValidationError, 'Invitation authority changed'):
            staff.invite(data['actor'], starting.pk, 'sample-outdated-profile', 'Sample new colleague',
                         'sample-outdated@example.invalid', ['case.read'], rev(starting), profile_key='sample-reader',
                         expected_authority=authority.pk, workspace_choices=reviewed_choices)
        self.assertFalse(StaffInvitation.objects.filter(username='sample-outdated-profile').exists())

    def test_workspace_departure_disables_invited_account_after_its_last_pinned_workspace(self):
        data = self.data
        actor = data['actor']
        first, second = [scope['case'] for scope in data['scopes']]
        for index, order in enumerate([(first, second), (second, first)]):
            with self.subTest(order=[case.pk for case in order]):
                _, token = staff.invite(actor, first.pk, f'last-workspace-{index}', 'Sample departing colleague',
                    'departure@example.invalid', ['case.read'], rev(first), profile_key='sample-reader',
                    expected_authority=data['authority'].pk, workspace_choices={second.pk: (rev(second), 'sample-reader')})
                person = staff.accept(token, 'Synthetic!sample.last-scope.744')
                removed = staff.deactivate(actor, order[0].pk, person.pk, {}, None, 'Sample departing first workspace', rev(order[0]))
                self.assertFalse(removed.account_disabled)
                person.refresh_from_db()
                self.assertTrue(person.is_active)
                removed = staff.deactivate(actor, order[1].pk, person.pk, {}, None, 'Sample departing last workspace', rev(order[1]))
                self.assertTrue(removed.account_disabled)
                person.refresh_from_db()
                self.assertFalse(person.is_active)
                self.assertFalse(Grant.objects.filter(user=person, active=True).exists())

    def test_batched_preview_reads_full_invitation_with_bounded_queries(self):
        data = self.data
        actor = data['actor']
        first, second = [scope['case'] for scope in data['scopes']]
        more = Case.objects.bulk_create([
            Case(tenant=first.tenant, title=f'Sample preview workspace {number}', kind='project', synthetic=True)
            for number in range(staff.MAX_INVITED_WORKSPACES - 2)
        ])
        Grant.objects.bulk_create([Grant(case=case, user=actor, action='case.read') for case in more])
        profiles = {case.pk: (case.revision, PROFILES[0]['key']) for case in more}
        profiles[second.pk] = (rev(second), PROFILES[0]['key'])
        row, token = staff.invite(actor, first.pk, 'sample-bulk-preview', 'Sample colleague',
            'preview@example.invalid', PROFILES[0]['actions'], rev(first), profile_key=PROFILES[0]['key'],
            expected_authority=data['authority'].pk, workspace_choices=profiles, all_current_projects=True)
        self.assertEqual(len(row.workspace_profiles), staff.MAX_INVITED_WORKSPACES - 1)
        self.assertEqual(len(row.actions) + sum(len(pin['actions']) for pin in row.workspace_profiles),
                         staff.MAX_COMBINED_INVITATION_ACTIONS)
        with CaptureQueriesContext(connection) as captured:
            self.assertEqual(staff.pending(token).pk, row.pk)
        self.assertLessEqual(len(captured), 12)
        self.assertFalse(StaffAdmission.objects.filter(invitation=row).exists())

    def test_combined_invite_bounds_native_and_direct_postgresql_effects(self):
        data = self.data
        first, second = [scope['case'] for scope in data['scopes']]
        widened = deepcopy(data['value'])
        actions = ['case.read', *[action for action in widened['allowed_actions'] if action != 'case.read'][:149]]
        wide = {'key': 'sample-wide-profile', 'label': 'Sample many access functions', 'actions': actions}
        widened['staff_lifecycle']['profiles'].append(wide)
        authority = intake.provision(data['root'], data['actor'], first.tenant, widened, data['authority'].expires_at,
                                    True, 'Synthetic boundary for combined invitation limits')
        with self.assertRaisesMessage(ValidationError, 'up to 150 workspace access functions'):
            staff.invite(data['actor'], first.pk, 'sample-too-wide', 'Sample colleague', 'limit@example.invalid',
                         ['case.read'], rev(first), profile_key='sample-reader', expected_authority=authority.pk,
                         workspace_choices={second.pk: (rev(second), wide['key'])})
        self.assertFalse(StaffInvitation.objects.filter(username='sample-too-wide').exists())
        with self.assertRaisesMessage(DatabaseError, 'Combined invitations may grant up to 150'), transaction.atomic():
            StaffInvitation.objects.create(case=first, username='sample-direct-too-wide', name='Sample colleague',
                email='limit@example.invalid', actions=['case.read'], number=1, token_hash='e' * 64,
                expires_at=authority.expires_at, authority=authority, actor=data['actor'], profile_key='sample-reader',
                profile_label=PROFILES[1]['label'], profile_sha256=digest(PROFILES[1]),
                workspace_profiles=[staff.workspace_pin(second, wide)])

    def test_handover_never_loads_or_names_restricted_bu_work(self):
        import json
        from pathlib import Path

        from django.utils import timezone
        from apps.policy.operator_drafts import draft_operator_policy
        from apps.policy.services import transition
        from apps.workflows import factory_bu
        from tests.bu_helpers import fixture as bu_fixture, source

        data = bu_fixture()
        case, preparer, manager = data['case'], data['preparer'], data['manager']
        profile = json.loads(Path('fixtures/factory-bu.json').read_text())
        profile.pop('classification')
        configuration = draft_operator_policy(preparer, case.pk, 'OPS.factory_bu_execution', profile,
                                               data['e']['policy_decision'].pk, timezone.now())
        transition(preparer, configuration.pk, 'validated')
        transition(preparer, configuration.pk, 'active')
        Grant.objects.get_or_create(case=case, user=manager, action='factory.read')
        sample = source(data)
        work = factory_bu.start(preparer, case.pk, 'sample-private-work-handover', {
            'mode': 'event', 'payroll_id': None, 'source_id': sample.pk, 'rule_ids': [], 'comparison': None,
        }, 'Sample restricted title never shown on Staff', rev(case))
        self.client.force_login(manager)
        self.assertEqual(self.client.get(reverse('factory_detail', args=[work.pk])).status_code, 403)
        with CaptureQueriesContext(connection) as captured:
            handover = staff.handover_links(manager, case, preparer)
        self.assertEqual(handover, {'rows': [], 'other_work': True})
        self.assertFalse(any('"workflows_factorywork"."request"' in item['sql'] for item in captured))

    def test_native_generic_invoice_claim_handover_uses_the_work_route(self):
        from apps.workflows import factory
        from apps.workflows.models import HumanTask
        from tests.factory_helpers import fixture as invoice_fixture

        data = invoice_fixture(username='staff-sample-invoice-worker')
        case, worker, work = data['case'], data['actor'], data['work']
        operator = get_user_model().objects.create_user(username='staff-sample-claim-operator')
        Grant.objects.bulk_create([Grant(case=case, user=operator, action=action)
                                   for action in ['case.read', 'factory.read', 'factory.manage', 'finance.read']])
        factory.run_until_wait(work.pk)
        task = HumanTask.objects.get(case=case, kind='factory_review', status='open')
        claimed = factory.claim_task(worker, task.pk, task.revision)
        handover = staff.handover_links(operator, case, worker)
        row = next(row for row in handover['rows'] if row['pk'] == work.pk)
        self.assertTrue(row['can_release_claim'])
        self.client.force_login(operator)
        route = reverse('factory_detail', args=[work.pk])
        self.assertContains(self.client.get(route), 'Release task claim')
        response = self.client.post(route, {'action': 'release_claim', 'task': task.pk,
            'task_revision': claimed.revision, 'reason': 'Sample staff departure review'})
        self.assertEqual(response.status_code, 302)
        task.refresh_from_db()
        self.assertIsNone(task.claimed_by_id)

    def test_exact_profile_adds_native_access_and_retains_roles_and_action_ownership(self):
        d=self.data;policies=Configuration.objects.count();row=apply(d)
        actions=set(Grant.objects.filter(user=d['target'],case=d['scopes'][0]['case'],active=True).values_list('action',flat=True))
        self.assertEqual(actions,set(PROFILES[0]['actions']))
        self.assertEqual(row.before_actions,['action.own','case.read'])
        self.assertEqual(row.grant_audit_head,AccessChange.objects.filter(case=row.case,subject=row.user).latest('pk').pk)
        self.assertEqual(Configuration.objects.count(),policies)
        d['scopes'][0]['item'].refresh_from_db()
        self.assertEqual(d['scopes'][0]['item'].current.number,1)
        self.assertEqual(staff_profiles.labels([row.case_id],row.user_id)[row.case_id],PROFILES[0]['label'])

    def test_removing_action_ownership_requires_handover_and_rolls_back(self):
        d=self.data;before=Grant.objects.filter(user=d['target'],active=True).count()
        with self.assertRaisesMessage(ValidationError,'Hand over'):apply(d,key='sample-reader')
        self.assertEqual(Grant.objects.filter(user=d['target'],active=True).count(),before)
        self.assertFalse(StaffProfileChange.objects.exists())

    def test_stale_access_and_audit_aba_are_rejected(self):
        d=self.data;case=d['scopes'][0]['case'];case.refresh_from_db()
        prior=staff_profiles.review(d['actor'],case,d['target'].pk)
        for enabled in [False,True]:intake.change_access(d['actor'],case.pk,d['target'].pk,'case.read',enabled,'Synthetic changed and restored access')
        with self.assertRaisesMessage(ValidationError,'changed'):apply(d,fingerprint=prior['fingerprint'])
        self.assertFalse(StaffProfileChange.objects.exists())

    def test_retry_returns_original_receipt_only_for_exact_current_request(self):
        d=self.data;case=d['scopes'][0]['case'];case.refresh_from_db();operation=uuid4()
        prepared=staff_profiles.review(d['actor'],case,d['target'].pk)
        row=apply(d,operation=operation,fingerprint=prepared['fingerprint'])
        self.assertEqual(apply(d,operation=operation,fingerprint=prepared['fingerprint']).pk,row.pk)
        with self.assertRaises(ValidationError):apply(d,key='sample-reader',operation=operation,fingerprint=prepared['fingerprint'])
        self.assertEqual(StaffProfileChange.objects.count(),1)

    def test_profile_metadata_batch_is_exact_and_has_no_historical_payload_loading(self):
        d=self.data;row=apply(d);case=row.case
        bindings=[(case.pk,u.pk) for u in [d['target'],d['successor']]]
        with CaptureQueriesContext(connection) as queries:labels=staff_profiles.binding_labels(bindings)
        self.assertEqual(labels[(case.pk,d['target'].pk)],PROFILES[0]['label'])
        self.assertEqual(labels[(case.pk,d['successor'].pk)],'Individual workspace access')
        self.assertEqual(set(labels),set(bindings));self.assertEqual(len(queries),3)
        sql=' '.join(q['sql'] for q in queries)
        self.assertNotIn('"before_actions"',sql);self.assertNotIn('"after_actions"',sql)
        with self.assertRaises(ValueError):staff_profiles.binding_labels([(case.pk,i) for i in range(26)])

    def test_roster_profile_labels_are_bounded_and_current_after_individual_change(self):
        d=self.data;apply(d);self.client.force_login(d['actor'])
        with CaptureQueriesContext(connection) as queries:
            page=self.client.get(reverse('staff_roster'),{'q':d['target'].username})
        self.assertContains(page,PROFILES[0]['label']);self.assertLess(len(queries),55)
        self.assertContains(page,'Profile shown for the first workspace')
        self.assertContains(self.client.get(reverse('case_access',args=[d['scopes'][0]['case'].pk])),'Review named access')
        for enabled in [False,True]:intake.change_access(d['actor'],d['scopes'][0]['case'].pk,d['target'].pk,
            'meeting.read',enabled,'Synthetic explicit individual access change')
        self.assertContains(self.client.get(reverse('staff_roster'),{'q':d['target'].username}),'Access changed')

    def test_unconfigured_profile_controls_hold_only_dependent_change(self):
        d=self.data;value=deepcopy(d['value']);value['staff_lifecycle']['allow_profile_edit']=None
        intake.provision(d['root'],d['actor'],'staff-accounts',value,d['authority'].expires_at,True,'Profile editing remains undecided')
        with self.assertRaises(PermissionDenied):apply(d)
        self.assertTrue(staff.authority(d['actor'],d['scopes'][0]['case'],'allow_invite'))

    def test_scope_self_inactive_and_privileged_targets_cannot_be_edited(self):
        d=self.data;case=d['scopes'][0]['case']
        for target in [d['actor'],d['root']]:
            with self.assertRaises(PermissionDenied):staff_profiles.review(d['actor'],case,target.pk)
        d['target'].is_active=False;d['target'].save(update_fields=['is_active'])
        with self.assertRaises(PermissionDenied):staff_profiles.review(d['actor'],case,d['target'].pk)

    def test_named_invitation_accepts_exact_profile_once_without_nominating_roles(self):
        d=self.data;case=d['scopes'][0]['case'];case.refresh_from_db();policies=Configuration.objects.count()
        row,token=staff.invite(d['actor'],case.pk,'named-new-colleague','SAMPLE new colleague','named@example.invalid',
            PROFILES[0]['actions'],case.revision,profile_key=PROFILES[0]['key'])
        user=staff.accept(token,'Synthetic!NamedInvite.732')
        receipt=StaffProfileChange.objects.get(invitation=row)
        self.assertEqual(receipt.user_id,user.pk)
        self.assertEqual(receipt.before_actions,[])
        self.assertEqual(set(receipt.after_actions),set(PROFILES[0]['actions']))
        self.assertEqual(Configuration.objects.count(),policies)
        with self.assertRaises(ValidationError):staff.accept(token,'Synthetic!NamedInvite.732')
        self.assertEqual(StaffAdmission.objects.filter(invitation=row).count(),1)

    def test_version_change_holds_invitation_until_explicit_renewal(self):
        d=self.data;case=d['scopes'][0]['case'];case.refresh_from_db()
        row,token=staff.invite(d['actor'],case.pk,'renew-named-colleague','SAMPLE colleague','named@example.invalid',
            PROFILES[0]['actions'],case.revision,profile_key=PROFILES[0]['key'])
        cfg=staff_profiles.configure(d['root'],d['authority'].pk,PROFILES,'Synthetic profile version review')
        with self.assertRaises(ValidationError):staff.accept(token,'Synthetic!NamedInvite.732')
        self.assertFalse(get_user_model().objects.filter(username=row.username).exists())
        case.refresh_from_db()
        successor,newtoken=staff.invite(d['actor'],case.pk,row.username,row.name,row.email,PROFILES[0]['actions'],
            case.revision,preceding=row.pk,profile_key=PROFILES[0]['key'])
        self.assertEqual(successor.authority_id,cfg.pk)
        self.assertEqual(successor.number,2)
        staff.accept(newtoken,'Synthetic!NamedInvite.732')

    def test_profile_source_literal_rechecks_native_route_and_rolls_back_acceptance(self):
        d=self.data;value=deepcopy(d['value']);literal='approval.source.read:sample-system'
        value['allowed_actions'].append(literal)
        profile={'key':'sample-source','label':'SAMPLE source reader','actions':['case.read',literal]}
        value['staff_lifecycle']['profiles'].append(profile)
        intake.provision(d['root'],d['actor'],'staff-accounts',value,d['authority'].expires_at,True,'Synthetic exact external source scope')
        case=d['scopes'][0]['case'];case.refresh_from_db()
        row,token=staff.invite(d['actor'],case.pk,'missing-route-person','SAMPLE source reader','route@example.invalid',
            profile['actions'],case.revision,profile_key=profile['key'])
        with self.assertRaises(ValidationError):staff.accept(token,'Synthetic!NamedInvite.732')
        self.assertFalse(get_user_model().objects.filter(username=row.username).exists())
        self.assertFalse(StaffAdmission.objects.filter(invitation=row).exists())

    def test_http_profile_review_cancel_save_and_paged_access_metadata(self):
        d=self.data;case=d['scopes'][0]['case'];self.client.force_login(d['actor'])
        url=reverse('staff_profile_access',args=[case.pk,d['target'].pk])
        page=self.client.get(url);self.assertContains(page,'Save reviewed access');self.assertContains(page,'Cancel')
        self.assertFalse(StaffProfileChange.objects.exists());form=page.context['form']
        post={'profile':PROFILES[0]['key'],'fingerprint':form.initial['fingerprint'],'operation':form.initial['operation'],
              'reason':'Synthetic HTTP reviewed profile','confirmed':'on'}
        self.assertEqual(self.client.post(url,post).status_code,302)
        with CaptureQueriesContext(connection) as queries:
            detail=self.client.get(reverse('staff_person',args=[d['target'].pk]))
        self.assertContains(detail,PROFILES[0]['label']);self.assertLess(len(queries),55)
        self.assertEqual(len(detail.context['workspaces']),2)
        Grant.objects.filter(case=case,user=d['target'],action='meeting.read').update(active=False)
        self.assertContains(self.client.get(reverse('staff_person',args=[d['target'].pk])),'Access changed')
        Grant.objects.filter(case=case,user=d['actor'],action='case.read').update(active=False)
        self.assertEqual(self.client.get(url).status_code,404)

    def test_pending_roster_excludes_replaced_and_accepted_and_other_scopes(self):
        d=self.data;case=d['scopes'][0]['case'];case.refresh_from_db()
        row,oldtoken=staff.invite(d['actor'],case.pk,'pending-visible','SAMPLE pending','pending@example.invalid',
            PROFILES[0]['actions'],case.revision,profile_key=PROFILES[0]['key'])
        case.refresh_from_db()
        new,token=staff.invite(d['actor'],case.pk,row.username,row.name,row.email,PROFILES[0]['actions'],case.revision,
                             preceding=row.pk,profile_key=PROFILES[0]['key'])
        self.client.force_login(d['actor'])
        page=self.client.get(reverse('staff_roster'),{'q':'pending-visible'})
        self.assertEqual([i.pk for i in page.context['invitations']],[new.pk])
        self.assertContains(page,PROFILES[0]['label']);self.assertContains(page,'Renew invitation')
        self.assertNotContains(page,token);self.assertNotContains(page,oldtoken)
        staff.accept(token,'Synthetic!NamedInvite.732')
        self.assertEqual(self.client.get(reverse('staff_roster'),{'q':'pending-visible'}).context['invitations'].paginator.count,0)

    def test_configuration_ui_versions_definitions_and_preserves_grants_expiry_and_unknowns(self):
        d=self.data;self.client.force_login(d['root']);before=Grant.objects.count()
        url=reverse('staff_profile_configuration',args=[d['authority'].pk])
        self.assertContains(self.client.get(url),'Named access profiles')
        post={'authority':d['authority'].pk,'reason':'Synthetic configured named access',
              'form-TOTAL_FORMS':'2','form-INITIAL_FORMS':'2','form-MIN_NUM_FORMS':'0','form-MAX_NUM_FORMS':'30',
              'form-0-key':PROFILES[0]['key'],'form-0-label':PROFILES[0]['label'],'form-0-actions':PROFILES[0]['actions'],
              'form-1-DELETE':'on'}
        self.assertEqual(self.client.post(url,post).status_code,302)
        cfg=TenantAuthority.objects.filter(user=d['actor'],tenant='staff-accounts').latest('version')
        self.assertEqual(cfg.value['staff_lifecycle']['profiles'],[PROFILES[0]])
        self.assertIsNone(cfg.value['staff_lifecycle']['allow_reactivation'])
        self.assertEqual(cfg.expires_at,d['authority'].expires_at);self.assertEqual(Grant.objects.count(),before)
        self.assertContains(self.client.post(url,post),'Delegation changed')
        self.client.force_login(d['actor']);self.assertEqual(self.client.get(url).status_code,403)

    def test_configuration_rejects_missing_existing_profile_review(self):
        d=self.data;self.client.force_login(d['root']);url=reverse('staff_profile_configuration',args=[d['authority'].pk])
        post={'authority':d['authority'].pk,'reason':'Synthetic malformed review',
              'form-TOTAL_FORMS':'0','form-INITIAL_FORMS':'0','form-MIN_NUM_FORMS':'0','form-MAX_NUM_FORMS':'30'}
        self.assertContains(self.client.post(url,post),'Review every existing profile')
        self.assertEqual(TenantAuthority.objects.filter(user=d['actor'],tenant='staff-accounts').latest('version').pk,d['authority'].pk)

    def test_legacy_delegation_cannot_invite_without_role_administration(self):
        d=self.data;value=deepcopy(d['value']);value['format']='psl.tenant-access/v1'
        value['staff_lifecycle']={'invite_minutes':30,'allow_invite':True,'allow_deactivation':True}
        intake.provision(d['root'],d['actor'],'staff-accounts',value,d['authority'].expires_at,True,'Legacy exact access remains supported')
        case=d['scopes'][0]['case'];case.refresh_from_db();self.client.force_login(d['actor'])
        response=self.client.post(reverse('staff_invites',args=[case.pk]),{'name':'SAMPLE legacy colleague',
            'username':'legacy-profile-free','email':'legacy@example.invalid','actions':['case.read'],'revision':case.revision})
        self.assertEqual(response.status_code,403)
        self.assertFalse(StaffInvitation.objects.filter(username='legacy-profile-free').exists())

    def test_typed_and_sql_controls_reject_invalid_profiles_and_unknown_extra_fields(self):
        d=self.data
        invalids=[{'profiles':[PROFILES[0],PROFILES[0]]},{'profiles':[{'key':'bad','label':'Bad','actions':['action.own']}]},
                  {'profiles':[{'key':'bad','label':' Bad','actions':['case.read']}]},
                  {'profiles':[{'key':'bad','label':'Bad','actions':['case.read'],'approver':True}]},
                  {'allow_profile_edit':'yes'},{'allow_roster':None,'allow_profile_edit':True}]
        for changes in invalids:
            value=deepcopy(d['value']);value['staff_lifecycle'].update(changes)
            with self.subTest(changes=changes):
                with self.assertRaises(ValidationError):intake.checked(value)
                with self.assertRaises(DatabaseError),transaction.atomic():
                    TenantAuthority.objects.create(user=d['actor'],tenant='staff-accounts',version=3,enabled=True,value=value,
                        actor=d['root'],expires_at=d['authority'].expires_at,reason='Malformed synthetic profile')

    def test_history_is_immutable_and_fabricated_profile_label_is_rejected_by_postgresql(self):
        row=apply(self.data)
        with self.assertRaises(DatabaseError),transaction.atomic():StaffProfileChange.objects.filter(pk=row.pk).update(reason='Overwrite')
        values={f.name:getattr(row,f.name) for f in row._meta.fields if f.name not in ['id','created_at']}
        values.update(operation=uuid4(),profile_label='Invented account authority')
        with self.assertRaises(DatabaseError),transaction.atomic():StaffProfileChange.objects.create(**values)


class StaffProfileConcurrencyTests(TransactionTestCase):
    def test_two_connections_commit_one_reviewed_profile_successor(self):
        d=configured();case=d['scopes'][0]['case'];case.refresh_from_db()
        prepared=staff_profiles.review(d['actor'],case,d['target'].pk);barrier=Barrier(2)
        def change(number):
            close_old_connections()
            try:
                actor=get_user_model().objects.get(pk=d['actor'].pk);barrier.wait(timeout=10)
                row=staff_profiles.apply(actor,case.pk,d['target'].pk,PROFILES[0]['key'],prepared['fingerprint'],
                    'Concurrent synthetic profile review',uuid4())
                return 'saved'
            except (ValidationError,PermissionDenied):return 'held'
            finally:close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(change,[1,2]))
        self.assertCountEqual(results,['saved','held']);self.assertEqual(StaffProfileChange.objects.count(),1)

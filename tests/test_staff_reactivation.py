"""Native restoration cannot revive access, old nominations or old device sessions."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from threading import Barrier
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied,ValidationError
from django.db import close_old_connections
from django.test import Client,TestCase,TransactionTestCase
from django.urls import reverse
from django.utils import timezone

from apps.identity import intake,staff_profiles,staff_reactivation as domain
from apps.identity.models import Grant,StaffAccountChange
from apps.policy.role_assignments import draft
from apps.policy.services import transition
from tests.test_staff_accounts import command
from tests.test_staff_profiles import PROFILES,configured


def departed(data=None):
    data=data or configured();value=deepcopy(data['value']);value['staff_lifecycle']['allow_reactivation']=True
    cfg=intake.provision(data['root'],data['actor'],'staff-accounts',value,data['authority'].expires_at,True,
                         'SAMPLE explicit restoration authority; fresh access is still separate')
    data.update(value=value,authority=cfg)
    data['departure']=command(data)
    return data


def remove_old_nominations(data):
    sources=[]
    for scope in data['scopes']:
        cfg=draft(data['actor'],scope['case'].pk,[{'role':'PMO Lead','user_id':data['successor'].pk}],
                  scope['proof'].pk,timezone.now())
        transition(data['actor'],cfg.pk,'validated');transition(data['actor'],cfg.pk,'active');sources.append(cfg)
    return sources


def restore(data,**kwargs):
    prepared=domain.prepare(data['actor'],data['target'].pk)
    return domain.restore(data['actor'],data['target'].pk,kwargs.get('fingerprint',prepared['fingerprint']),
        'SAMPLE fresh all-workspace restoration review',kwargs.get('operation',uuid4()))


class StaffReactivationTests(TestCase):
    @classmethod
    def setUpTestData(cls):cls.data=departed()

    def test_old_nomination_is_held_until_native_owner_review_removes_it(self):
        d=self.data;prepared=domain.prepare(d['actor'],d['target'].pk)
        self.assertTrue(any('previous project roles' in text for text in prepared['blocked']))
        with self.assertRaisesMessage(ValidationError,'previous project roles'):restore(d)
        self.assertFalse(get_user_model().objects.get(pk=d['target'].pk).is_active)
        self.assertFalse(StaffAccountChange.objects.filter(kind='reactivated').exists())
        remove_old_nominations(d)
        self.assertEqual(domain.prepare(d['actor'],d['target'].pk)['blocked'],[])

    def test_immutable_access_history_keeps_a_previous_scope_in_the_review(self):
        d=self.data
        Grant.objects.filter(case=d['scopes'][1]['case'],user=d['target']).delete()
        prepared=domain.prepare(d['actor'],d['target'].pk)
        self.assertEqual({s['case'].pk for s in prepared['scopes']},{s['case'].pk for s in d['scopes']})
        self.assertTrue(prepared['blocked'])

    def test_coordinator_read_is_bounded_and_contains_no_credential_or_grant_payload(self):
        from apps.agents.staff_accounts import investigate_restoration
        d=self.data;result=investigate_restoration(d['actor'],d['target'].pk)
        assistance=result['assistance'];packet=assistance['packet']
        self.assertEqual(assistance['agent_role'],'O01');self.assertEqual(len(packet['scopes']),2)
        self.assertTrue(packet['human_review_required']);self.assertFalse(packet['old_access_restored'])
        self.assertEqual(packet['effect_tools'],[])
        self.assertEqual(set(packet),{'format','person','scopes','findings','old_access_restored','human_review_required','effect_tools'})
        self.assertFalse(StaffAccountChange.objects.filter(kind='reactivated').exists())

    def test_restoration_keeps_every_old_grant_closed_and_records_fresh_epoch(self):
        d=self.data;remove_old_nominations(d);change=restore(d)
        self.assertTrue(get_user_model().objects.get(pk=d['target'].pk).is_active)
        self.assertEqual(change.kind,'reactivated');self.assertGreater(change.pk,d['departure'].pk)
        self.assertFalse(change.manifest['access_restored'])
        self.assertEqual(change.manifest['reviewed']['departure'],d['departure'].pk)
        self.assertEqual(len(change.manifest['reviewed']['scopes']),2)
        self.assertFalse(Grant.objects.filter(user=d['target'],active=True).exists())
        for scope in d['scopes']:
            scope['item'].refresh_from_db()
            self.assertEqual(scope['item'].current.number,2)
            self.assertIsNone(scope['item'].current.owner_id)
            self.assertEqual(scope['item'].current.due_at,scope['due'])

    def test_fresh_profile_is_separately_reviewed_and_does_not_restore_old_ownership(self):
        d=self.data;remove_old_nominations(d);restore(d);case=d['scopes'][0]['case'];case.refresh_from_db()
        prepared=staff_profiles.review(d['actor'],case,d['target'].pk)
        row=staff_profiles.apply(d['actor'],case.pk,d['target'].pk,PROFILES[1]['key'],prepared['fingerprint'],
                                 'SAMPLE new reader allocation after restoration',uuid4())
        self.assertEqual(row.before_actions,[]);self.assertEqual(row.after_actions,['case.read'])
        self.assertEqual(list(Grant.objects.filter(user=d['target'],active=True).values_list('action',flat=True)),['case.read'])

    def test_unknown_reactivation_control_does_not_disable_other_staff_functions(self):
        d=self.data;value=deepcopy(d['value']);value['staff_lifecycle']['allow_reactivation']=None
        intake.provision(d['root'],d['actor'],'staff-accounts',value,d['authority'].expires_at,True,'Operational restoration authority undecided')
        with self.assertRaises(PermissionDenied):domain.prepare(d['actor'],d['target'].pk)
        self.client.force_login(d['actor']);self.assertContains(self.client.get(reverse('staff_roster')),d['target'].email)
        self.assertEqual(self.client.get(reverse('staff_invites',args=[d['scopes'][0]['case'].pk])).status_code,200)

    def test_unmanaged_previous_scope_is_not_disclosed_or_partially_restored(self):
        from apps.core.models import Case
        d=self.data;other=Case.objects.create(tenant='elsewhere',title='PRIVATE outside restoration scope',synthetic=True)
        Grant.objects.create(case=other,user=d['target'],action='case.read',active=False)
        with self.assertRaises(PermissionDenied):domain.prepare(d['actor'],d['target'].pk)
        self.client.force_login(d['actor'])
        page=self.client.get(reverse('staff_account_reactivation',args=[d['target'].pk]))
        self.assertContains(page,'every affected workspace');self.assertNotContains(page,other.title)
        self.assertFalse(get_user_model().objects.get(pk=d['target'].pk).is_active)

    def test_role_source_read_permission_is_required_before_nomination_checks(self):
        d=self.data;Grant.objects.filter(user=d['actor'],action='policy.read').update(active=False)
        with self.assertRaises(PermissionDenied):domain.prepare(d['actor'],d['target'].pk)
        self.client.force_login(d['actor']);page=self.client.get(reverse('staff_account_reactivation',args=[d['target'].pk]))
        self.assertNotContains(page,'previous project roles')
        self.assertContains(page,'role-source access')

    def test_active_grants_on_an_inactive_account_are_not_carried_forward(self):
        d=self.data;remove_old_nominations(d)
        Grant.objects.filter(user=d['target'],case=d['scopes'][0]['case'],action='case.read').update(active=True)
        with self.assertRaisesMessage(ValidationError,'remaining active access'):restore(d)
        self.assertFalse(get_user_model().objects.get(pk=d['target'].pk).is_active)

    def test_stale_delegation_and_subject_identity_require_new_review(self):
        d=self.data;remove_old_nominations(d);prepared=domain.prepare(d['actor'],d['target'].pk)
        get_user_model().objects.filter(pk=d['target'].pk).update(email='changed-sample@example.invalid')
        with self.assertRaisesMessage(ValidationError,'changed'):restore(d,fingerprint=prepared['fingerprint'])
        prepared=domain.prepare(d['actor'],d['target'].pk)
        intake.provision(d['root'],d['actor'],'staff-accounts',d['value'],d['authority'].expires_at,True,'SAMPLE newer delegation review')
        with self.assertRaisesMessage(ValidationError,'changed'):restore(d,fingerprint=prepared['fingerprint'])

    def test_same_policy_state_change_requires_a_fresh_review(self):
        d=self.data;sources=remove_old_nominations(d);prepared=domain.prepare(d['actor'],d['target'].pk)
        transition(d['actor'],sources[0].pk,'revoked')
        with self.assertRaisesMessage(ValidationError,'changed'):restore(d,fingerprint=prepared['fingerprint'])
        self.assertFalse(get_user_model().objects.get(pk=d['target'].pk).is_active)

    def test_http_get_cancel_and_restore_require_current_review_without_restoring_access(self):
        d=self.data;remove_old_nominations(d);self.client.force_login(d['actor'])
        url=reverse('staff_account_reactivation',args=[d['target'].pk]);page=self.client.get(url)
        self.assertContains(page,'Restore sign-in without old access');self.assertContains(page,'Cancel')
        self.assertFalse(get_user_model().objects.get(pk=d['target'].pk).is_active)
        form=page.context['form'];post={'fingerprint':form.initial['fingerprint'],'operation':form.initial['operation'],
            'reason':'SAMPLE HTTP fresh restoration','confirmed':'on'}
        self.assertRedirects(self.client.post(url,post),reverse('staff_person',args=[d['target'].pk]),fetch_redirect_response=False)
        detail=self.client.get(reverse('staff_person',args=[d['target'].pk]))
        self.assertContains(detail,'Active');self.assertContains(detail,'Review access')
        self.assertFalse(Grant.objects.filter(user=d['target'],active=True).exists())

    def test_invalid_identity_fingerprint_or_operation_never_restores_the_account(self):
        d=self.data;remove_old_nominations(d)
        for fingerprint,operation in [('invalid',uuid4()),('0'*64,'bad-uuid')]:
            with self.assertRaises(ValidationError):domain.restore(d['actor'],d['target'].pk,fingerprint,'SAMPLE invalid command',operation)
        self.assertFalse(get_user_model().objects.get(pk=d['target'].pk).is_active)


class StaffReactivationSessionsTests(TestCase):
    def test_real_predeparture_device_sessions_cannot_revive_after_controlled_reactivation(self):
        d=configured();devices=[Client(),Client()]
        for device in devices:self.assertTrue(device.login(username=d['target'].username,password='Synthetic!staff.account.51'))
        departed(d);remove_old_nominations(d);restore(d)
        for device in devices:self.assertEqual(device.get(reverse('design_setup')).status_code,302)
        self.assertFalse(Grant.objects.filter(user=d['target'],active=True).exists())
        self.assertTrue(Client().login(username=d['target'].username,password='Synthetic!staff.account.51'))


class StaffReactivationConcurrencyTests(TransactionTestCase):
    def test_two_connections_restore_signin_once_without_old_grants(self):
        d=departed();remove_old_nominations(d);prepared=domain.prepare(d['actor'],d['target'].pk);barrier=Barrier(2)
        def run(number):
            close_old_connections()
            try:
                actor=get_user_model().objects.get(pk=d['actor'].pk);barrier.wait(timeout=10)
                domain.restore(actor,d['target'].pk,prepared['fingerprint'],'SAMPLE concurrent restoration',uuid4())
                return 'restored'
            except (PermissionDenied,ValidationError):return 'held'
            finally:close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:outcomes=list(pool.map(run,[1,2]))
        self.assertCountEqual(outcomes,['restored','held'])
        self.assertEqual(StaffAccountChange.objects.filter(kind='reactivated').count(),1)
        self.assertFalse(Grant.objects.filter(user=d['target'],active=True).exists())

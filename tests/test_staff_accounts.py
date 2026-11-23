"""Synthetic account departure through native grants, actions and HTTP controls."""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied,ValidationError
from django.db import DatabaseError,close_old_connections,connection,transaction
from django.test import Client,TestCase,TransactionTestCase,override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from apps.core import account_delivery,alerts
from apps.core.models import Case
from apps.core.services import add_evidence
from apps.identity import intake,staff,staff_accounts as domain
from apps.identity.actions import ACTIONS
from apps.identity.models import Grant,StaffAccountChange,StaffDeparture,TenantAuthority
from apps.pmo.meetings import create_action
from apps.policy.role_assignments import draft as draft_roles
from apps.policy.services import transition
from config.contact_runtime import ContactRuntime,Route
from tests.helpers import rev


def fixture():
    users=get_user_model().objects
    root=users.create_superuser('account-bootstrap')
    operator=users.create_user('account-manager')
    target=users.create_user('departing-staff',password='Synthetic!staff.account.51',email='departing@example.invalid')
    successor=users.create_user('remaining-staff')
    value={'format':'psl.tenant-access/v3','create_cases':True,'manage_access':True,'kinds':['project'],
           'allowed_actions':list(dict.fromkeys(ACTIONS)),'initial_actions':list(dict.fromkeys(ACTIONS)),
           'classification':'synthetic','staff_lifecycle':{'invite_minutes':30,'allow_invite':True,
             'allow_deactivation':True,'allow_roster':True,'allow_account_deactivation':True,'allow_unassigned_departure':True}}
    authority=intake.provision(root,operator,'staff-accounts',value,timezone.now()+timedelta(hours=2),True,'Synthetic all-scope departure test')
    scopes=[]
    for number in [1,2]:
        case=intake.create_case(operator,'staff-accounts',f'account-scope-{number}',f'Staff workspace {number}','project')
        for user in [target,successor]:
            for action in ['case.read','action.own']:
                intake.change_access(operator,case.pk,user.pk,action,True,'Synthetic exact participant access')
        proof=add_evidence(operator,case.pk,'policy_decision','Synthetic account handover evidence','synthetic:staff')
        policy=draft_roles(operator,case.pk,[{'role':'PMO Lead','user_id':u.pk} for u in [target,successor]],proof.pk,timezone.now())
        transition(operator,policy.pk,'validated');transition(operator,policy.pk,'active')
        due=timezone.now()+timedelta(days=2)
        item=create_action(operator,case.pk,f'account-action-{number}','Verify staff handover '+str(number),
                           target.pk,due,proof.pk,'Explicit synthetic assignment',rev(case))
        scopes.append({'case':case,'proof':proof,'item':item,'due':due})
    return {'root':root,'actor':operator,'target':target,'successor':successor,'authority':authority,'value':value,'scopes':scopes}


def command(data,**kwargs):
    prepared=domain.prepare(data['actor'],data['target'].pk)
    return domain.deactivate(data['actor'],data['target'].pk,prepared['fingerprint'],
        kwargs.get('replacements',{s['item'].pk:None for s in data['scopes']}),
        kwargs.get('evidence',{str(s['case'].pk):s['proof'].pk for s in data['scopes']}),
        'Synthetic account departure reviewed',uuid4())


class StaffAccountTests(TestCase):
    @classmethod
    def setUpTestData(cls):cls.data=fixture()

    def test_complete_departure_preserves_deadlines_history_and_unassigned_owner(self):
        d=self.data;s1,s2=d['scopes']
        change=command(d,replacements={s1['item'].pk:None,s2['item'].pk:d['successor'].pk})
        d['target'].refresh_from_db()
        self.assertFalse(d['target'].is_active)
        self.assertFalse(Grant.objects.filter(user=d['target'],active=True).exists())
        self.assertEqual(StaffDeparture.objects.filter(user=d['target']).count(),2)
        self.assertEqual(len(change.manifest['reviewed']['scopes']),2)
        for s,owner in [(s1,None),(s2,d['successor'].pk)]:
            s['item'].refresh_from_db()
            self.assertEqual((s['item'].current.owner_id,s['item'].current.due_at),(owner,s['due']))
            self.assertEqual(s['item'].states.get(number=1).owner_id,d['target'].pk)
            self.assertEqual(s['item'].current.status,'open')

    def test_other_scope_is_not_disclosed_or_partially_revoked(self):
        d=self.data
        other=Case.objects.create(tenant='different-organisation',title='PRIVATE unrelated workspace',kind='project',synthetic=True)
        Grant.objects.create(case=other,user=d['target'],action='case.read')
        with self.assertRaises(PermissionDenied):domain.prepare(d['actor'],d['target'].pk)
        self.client.force_login(d['actor'])
        response=self.client.get(reverse('staff_account_departure',args=[d['target'].pk]))
        self.assertContains(response,'every affected workspace')
        self.assertNotContains(response,'PRIVATE unrelated workspace')
        self.assertEqual(StaffDeparture.objects.count(),0)
        self.assertTrue(Grant.objects.filter(case=other,user=d['target'],active=True).exists())

    def test_stale_review_refuses_changed_access_and_retains_every_scope(self):
        d=self.data;old=domain.prepare(d['actor'],d['target'].pk)
        add_evidence(d['actor'],d['scopes'][0]['case'].pk,'policy_decision','Later reviewed evidence','synthetic:staff')
        with self.assertRaisesMessage(ValidationError,'changed'):
            domain.deactivate(d['actor'],d['target'].pk,old['fingerprint'],{s['item'].pk:None for s in d['scopes']},
                              {str(s['case'].pk):s['proof'].pk for s in d['scopes']},'Synthetic departure',uuid4())
        self.assertFalse(StaffDeparture.objects.exists())
        self.assertTrue(Grant.objects.filter(user=d['target'],active=True).exists())

    def test_later_bad_evidence_rolls_back_all_departures(self):
        d=self.data;s1,s2=d['scopes']
        with self.assertRaises(ValidationError):
            command(d,evidence={str(s1['case'].pk):s1['proof'].pk,str(s2['case'].pk):s1['proof'].pk})
        self.assertFalse(StaffDeparture.objects.exists())
        self.assertFalse(StaffAccountChange.objects.exists())
        for s in d['scopes']:
            s['item'].refresh_from_db();self.assertEqual(s['item'].current.number,1)

    def test_unknown_controls_hold_only_global_departure_and_legacy_authority_stays_exact(self):
        d=self.data
        values={**d['value'],'staff_lifecycle':{**d['value']['staff_lifecycle'],'allow_account_deactivation':None,
                                             'allow_unassigned_departure':None}}
        intake.provision(d['root'],d['actor'],'staff-accounts',values,d['authority'].expires_at,True,'Owner controls remain undecided')
        self.assertTrue(domain.manageable_cases(d['actor']).exists())
        with self.assertRaises(PermissionDenied):domain.prepare(d['actor'],d['target'].pk)
        self.assertTrue(staff.authority(d['actor'],d['scopes'][0]['case'],'allow_invite'))
        legacy={**d['value'],'format':'psl.tenant-access/v1'}
        with self.assertRaises(ValidationError):intake.checked(legacy)

    def test_unassigned_path_requires_explicit_permission(self):
        d=self.data
        value={**d['value'],'staff_lifecycle':{**d['value']['staff_lifecycle'],'allow_unassigned_departure':None}}
        intake.provision(d['root'],d['actor'],'staff-accounts',value,d['authority'].expires_at,True,'Unassigned action choice deferred')
        with self.assertRaisesMessage(ValidationError,'explicit'):command(d)
        self.assertFalse(StaffDeparture.objects.exists())

    def test_privileged_self_and_current_technical_delegates_are_protected(self):
        d=self.data
        with self.assertRaises(PermissionDenied):domain.prepare(d['actor'],d['actor'].pk)
        d['target'].is_staff=True;d['target'].save(update_fields=['is_staff'])
        with self.assertRaises(PermissionDenied):domain.prepare(d['actor'],d['target'].pk)
        d['target'].is_staff=False;d['target'].save(update_fields=['is_staff'])
        intake.provision(d['root'],d['target'],'staff-accounts',d['value'],d['authority'].expires_at,True,'Separate technical delegate')
        with self.assertRaises(PermissionDenied):domain.prepare(d['actor'],d['target'].pk)

    def test_exact_successor_needs_current_shared_project_role(self):
        d=self.data
        outsider=get_user_model().objects.create_user('not-appointed')
        for s in d['scopes']:
            Grant.objects.create(case=s['case'],user=outsider,action='case.read')
            Grant.objects.create(case=s['case'],user=outsider,action='action.own')
        with self.assertRaises(ValidationError):command(d,replacements={s['item'].pk:outsider.pk for s in d['scopes']})
        self.assertFalse(StaffDeparture.objects.exists())

    def test_current_role_source_read_is_required_for_successor_not_for_unassigned(self):
        d=self.data
        Grant.objects.filter(user=d['actor'],action='policy.read').update(active=False)
        with self.assertRaises(PermissionDenied):
            command(d,replacements={s['item'].pk:d['successor'].pk for s in d['scopes']})
        self.assertFalse(StaffDeparture.objects.exists())
        command(d)
        self.assertEqual(StaffDeparture.objects.count(),2)

    def test_roster_and_departure_http_use_native_services_without_get_mutations(self):
        d=self.data;self.client.force_login(d['actor'])
        url=reverse('staff_account_departure',args=[d['target'].pk])
        page=self.client.get(url)
        self.assertContains(page,'Owner needed — no successor')
        self.assertFalse(StaffDeparture.objects.exists())
        form=page.context['form']
        post={'fingerprint':form.initial['fingerprint'],'operation':form.initial['operation'],
              'reason':'Synthetic departure checked in HTTP','confirmed':'on'}
        post.update({group['evidence'].name:next(s['proof'].pk for s in d['scopes'] if s['case'].pk==group['case'].pk)
                     for group in form.groups})
        self.assertRedirects(self.client.post(url,post),reverse('staff_roster'),fetch_redirect_response=False)
        inactive=self.client.get(reverse('staff_roster'),{'q':d['target'].username,'status':'inactive'})
        self.assertContains(inactive,d['target'].email)
        self.assertContains(inactive,'Inactive')
        for scope in d['scopes']:
            page=self.client.get(reverse('design_project_action',args=[scope['case'].pk,scope['item'].pk]))
            self.assertContains(page,d['target'].username)
            self.assertContains(page,'Owner needed')
            self.assertContains(page,'Version 2')
            self.assertContains(page,'Version 1')
            self.assertContains(page,'Deadline:')

    def test_action_history_is_bounded_and_current_permission_is_rechecked(self):
        from apps.pmo.meetings import change_action
        d=self.data;scope=d['scopes'][0];item=scope['item'];number=1
        for index in range(22):
            state=change_action(d['actor'],scope['case'].pk,item.pk,'reassign',scope['proof'].pk,
                'Explicit synthetic historical assignment '+str(index),rev(scope['case']),number,owner_id=d['target'].pk)
            number=state.number
        self.client.force_login(d['actor']);url=reverse('design_project_action',args=[scope['case'].pk,item.pk])
        with CaptureQueriesContext(connection) as queries:page=self.client.get(url)
        self.assertEqual(len(page.context['history']),20)
        self.assertContains(page,'Earlier changes')
        self.assertLess(len(queries),60)
        earlier=self.client.get(url,{'page':2})
        self.assertEqual(len(earlier.context['history']),3)
        self.assertContains(earlier,'Version 1')
        self.assertContains(earlier,d['target'].username)
        Grant.objects.filter(user=d['actor'],case=scope['case'],action='meeting.read').update(active=False)
        self.assertEqual(self.client.get(url).status_code,403)

    def test_epoch_fences_two_devices_even_if_account_is_later_reenabled(self):
        d=self.data;devices=[Client(),Client()]
        for device in devices:self.assertTrue(device.login(username=d['target'].username,password='Synthetic!staff.account.51'))
        command(d)
        for device in devices:self.assertEqual(device.get(reverse('design_setup')).status_code,302)
        d['target'].is_active=True;d['target'].save(update_fields=['is_active'])
        # A technical flag change cannot revive an old session or any old grant.
        for device in devices:self.assertEqual(device.get(reverse('design_setup')).status_code,302)
        self.assertFalse(Grant.objects.filter(user=d['target'],active=True).exists())
        self.assertTrue(Client().login(username=d['target'].username,password='Synthetic!staff.account.51'))

    def test_unrelated_roster_is_private_and_reads_are_bounded(self):
        d=self.data
        hidden=get_user_model().objects.create_user('private-staff-outside-scope',email='private@example.invalid')
        other=Case.objects.create(tenant='elsewhere',title='PRIVATE',synthetic=True)
        Grant.objects.create(case=other,user=hidden,action='case.read')
        for number in range(35):
            person=get_user_model().objects.create_user('roster-person-'+str(number))
            Grant.objects.create(case=d['scopes'][0]['case'],user=person,action='case.read')
        self.client.force_login(d['actor'])
        with CaptureQueriesContext(connection) as queries:page=self.client.get(reverse('staff_roster'))
        self.assertEqual(len(page.context['people']),25)
        self.assertContains(page,'Next')
        self.assertNotContains(page,hidden.username)
        self.assertLess(len(queries),50)

    def test_controls_ui_versions_unknown_values_without_business_role_grants(self):
        d=self.data;self.client.force_login(d['root'])
        before=Grant.objects.count();url=reverse('staff_account_controls',args=[d['authority'].pk])
        page=self.client.get(url);self.assertContains(page,'Staff account controls')
        post={'authority':d['authority'].pk,'allow_roster':'true','allow_account_deactivation':'unknown',
              'allow_unassigned_departure':'unknown','reason':'Keep owner controls deferred'}
        self.assertEqual(self.client.post(url,post).status_code,302)
        current=TenantAuthority.objects.filter(user=d['actor'],tenant='staff-accounts').latest('version')
        self.assertIsNone(current.value['staff_lifecycle']['allow_account_deactivation'])
        self.assertEqual(Grant.objects.count(),before)
        self.assertContains(self.client.post(url,post),'Delegation changed')
        self.client.force_login(d['actor'])
        self.assertEqual(self.client.get(url).status_code,403)

    def test_account_history_is_immutable_in_postgresql(self):
        row=command(self.data)
        with self.assertRaises(DatabaseError),transaction.atomic():
            StaffAccountChange.objects.filter(pk=row.pk).update(reason='Overwrite history')

    def test_departed_nomination_does_not_disable_remaining_project_roles(self):
        from apps.policy.role_assignments import report
        from apps.policy.services import role_policy,resolve,reference_values
        d=self.data;case=d['scopes'][0]['case']
        original=resolve('D05.role_principal_assignments',case).configuration
        command(d)
        self.assertEqual(role_policy(d['successor'],case,'PMO Lead').pk,original.pk)
        # A stale in-memory active flag cannot let the departing person decide.
        with self.assertRaises(PermissionDenied):role_policy(d['target'],case,'PMO Lead')
        assignments={r['user_id']:r for r in report(d['actor'],case.pk)['assignments']}
        self.assertEqual(assignments[d['target'].pk]['eligibility'],'inactive_account')
        self.assertFalse(assignments[d['target'].pk]['eligible_role_bundle'])
        self.assertTrue(assignments[d['successor'].pk]['eligible_role_bundle'])
        proposal=draft_roles(d['actor'],case.pk,reference_values(original),d['scopes'][0]['proof'].pk,timezone.now())
        with self.assertRaises(ValidationError):transition(d['actor'],proposal.pk,'validated')

    def test_sql_rejects_malformed_or_legacy_account_controls(self):
        d=self.data
        for version,flag in [('psl.tenant-access/v1',True),('psl.tenant-access/v3','yes')]:
            invalid={**d['value'],'format':version,'staff_lifecycle':{**d['value']['staff_lifecycle'],
                                                                 'allow_account_deactivation':flag}}
            with self.assertRaises(DatabaseError),transaction.atomic():
                TenantAuthority.objects.create(user=d['actor'],tenant='staff-accounts',version=2,enabled=True,
                    value=invalid,actor=d['root'],expires_at=d['authority'].expires_at,reason='Malformed synthetic controls')

    def test_queued_personal_delivery_is_held_after_deactivation(self):
        d=self.data;target=d['target']
        runtime=ContactRuntime('https://factory.example.test','',(Route(target.username,target.email,'',True),),True)
        with override_settings(CONTACT_DELIVERY=runtime):
            account_delivery.queue_recovery(target.email)
            from apps.core.alert_models import AccountDelivery
            self.assertEqual(AccountDelivery.objects.filter(actor=target).count(),1)
            command(d)
            row,payload=account_delivery.claim()
            self.assertIsNone(payload)
            self.assertEqual(row.state,AccountDelivery.State.HELD)


class StaffAccountConcurrencyTests(TransactionTestCase):
    def test_two_connections_commit_one_complete_departure(self):
        d=fixture();prepared=domain.prepare(d['actor'],d['target'].pk);barrier=Barrier(2)
        def depart(number):
            close_old_connections()
            try:
                actor=get_user_model().objects.get(pk=d['actor'].pk);barrier.wait(timeout=10)
                return ('done',domain.deactivate(actor,d['target'].pk,prepared['fingerprint'],
                    {s['item'].pk:None for s in d['scopes']},{str(s['case'].pk):s['proof'].pk for s in d['scopes']},
                    'Concurrent synthetic departure',uuid4()).pk)
            except (ValidationError,PermissionDenied) as exc:return ('held',type(exc).__name__)
            finally:close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(depart,[1,2]))
        self.assertCountEqual([r[0] for r in results],['done','held'])
        self.assertEqual(StaffAccountChange.objects.count(),1)
        self.assertEqual(StaffDeparture.objects.count(),2)
        self.assertFalse(Grant.objects.filter(user=d['target'],active=True).exists())

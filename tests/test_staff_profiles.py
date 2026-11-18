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

from apps.identity import intake,staff,staff_profiles
from apps.identity.intake_models import AccessChange,TenantAuthority
from apps.identity.models import Grant
from apps.identity.staff_models import StaffAdmission,StaffInvitation,StaffProfileChange
from apps.policy.models import Configuration
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

    def test_legacy_invitation_form_remains_supported_without_profiles(self):
        d=self.data;value=deepcopy(d['value']);value['format']='psl.tenant-access/v1'
        value['staff_lifecycle']={'invite_minutes':30,'allow_invite':True,'allow_deactivation':True}
        intake.provision(d['root'],d['actor'],'staff-accounts',value,d['authority'].expires_at,True,'Legacy exact access remains supported')
        case=d['scopes'][0]['case'];case.refresh_from_db();self.client.force_login(d['actor'])
        response=self.client.post(reverse('staff_invites',args=[case.pk]),{'name':'SAMPLE legacy colleague',
            'username':'legacy-profile-free','email':'legacy@example.invalid','actions':['case.read'],'revision':case.revision})
        self.assertContains(response,'Invitation is ready');row=StaffInvitation.objects.get(username='legacy-profile-free')
        self.assertEqual(row.profile_key,'');self.assertFalse(StaffProfileChange.objects.exists())

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

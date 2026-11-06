import copy,json
from datetime import timedelta
from pathlib import Path
from django.test import TestCase,Client
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError,PermissionDenied
from django.db import transaction,DatabaseError
from django.urls import reverse
from django.utils import timezone
from apps.identity import intake as d
from apps.identity.models import Grant
from apps.identity.intake_models import TenantAuthority,AccessChange
from apps.policy.services import active_component,transition
from apps.policy.approval_validators import ROUTES
from tests import approval_helpers as h

class SourceAccessTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.f=h.fixture('source-access')
        cls.root=get_user_model().objects.create_superuser('source-technical-root','source-root@example.invalid','test-only-password')
        cls.reader=get_user_model().objects.create_user('source-reader')
        for action in ['case.read','approval.read']:Grant.objects.create(case=cls.f['case'],user=cls.reader,action=action)
        cls.value=json.loads(Path('fixtures/tenant-source-access.json').read_text(encoding='utf-8'))['value']
        cls.expiry=timezone.now()+timedelta(hours=1)
        cls.cfg=d.provision(cls.root,cls.f['actor'],cls.f['case'].tenant,cls.value,cls.expiry,True,'Synthetic exact source delegation')

    def test_actual_source_receipt_read_requires_exact_ui_grant_and_current_revocation(self):
        f=self.f;a,c=f['actor'],f['case'];source=h.capture(f);url=f'/cases/{c.pk}/approvals/source/{source.pk}/'
        reader=Client();reader.force_login(self.reader);self.assertEqual(reader.get(url).status_code,403)
        client=Client(enforce_csrf_checks=True);client.force_login(a);access=reverse('case_access',args=[c.pk])
        self.assertContains(client.get(access),'approval.source.read:synthetic-qa')
        payload={'subject':self.reader.pk,'action':'approval.source.read:synthetic-qa','enabled':'grant','reason':'Actual synthetic grant through technical UI'}
        self.assertEqual(client.post(access,payload).status_code,403)
        payload['csrfmiddlewaretoken']=client.cookies['csrftoken'].value
        self.assertEqual(client.post(access,payload).status_code,302)
        response=reader.get(url);self.assertEqual(response.status_code,200);self.assertEqual(response.json()['receipt_id'],source.pk)
        transition(a,active_component(ROUTES,c).pk,'revoked')
        d.change_access(a,c.pk,self.reader.pk,'approval.source.read:synthetic-qa',False,'Route withdrawn; revoke existing source read without restoring it')
        self.assertEqual(reader.get(url).status_code,403)
        self.assertEqual(AccessChange.objects.filter(case=c,subject=self.reader).count(),2)
        self.assertTrue(source.__class__.objects.filter(pk=source.pk).exists())

    def test_v1_compatibility_closed_literals_and_no_dynamic_initial_actions(self):
        for change in [
            {'format':'psl.tenant-access/v1'},
            {'allowed_actions':['case.read','approval.source.read:*']},
            {'allowed_actions':['case.read','arbitrary.source:system']},
            {'allowed_actions':['case.read','approval.source.read:bad\n']},
            {'allowed_actions':['case.read','approval.source.read:'+'x'*100]},
            {'initial_actions':['case.read','approval.source.read:synthetic-qa']}]:
            value=copy.deepcopy(self.value);value.update(change)
            with self.assertRaises(ValidationError):d.checked(value)
        value=copy.deepcopy(self.value);value.update(format='psl.tenant-access/v1',allowed_actions=['case.read','approval.read'])
        d.checked(value)
        cfg=d.provision(self.root,self.f['actor'],self.f['case'].tenant,value,self.expiry,True,'Explicit v1 successor retains fixed-only actions')
        self.assertEqual(cfg.value['format'],'psl.tenant-access/v1')
        with self.assertRaises(PermissionDenied):d.change_access(self.f['actor'],self.f['case'].pk,self.reader.pk,'approval.source.read:synthetic-qa',True,'No v1 expansion')

    def test_unknown_case_system_foreign_tenant_and_classification_are_denied(self):
        f=self.f;a,c=f['actor'],f['case'];value=copy.deepcopy(self.value);value['allowed_actions'].append('approval.source.read:absent-system')
        d.provision(self.root,a,c.tenant,value,self.expiry,True,'Explicit potential key still requires configured case source')
        with self.assertRaises(ValidationError):d.change_access(a,c.pk,self.reader.pk,'approval.source.read:absent-system',True,'Missing case source')
        from tests.helpers import setup_case
        from apps.core.models import Case
        _,other=setup_case(username='source-no-route');Grant.objects.create(case=other,user=a,action='case.read')
        with self.assertRaises(ValidationError):d.change_access(a,other.pk,self.reader.pk,'approval.source.read:synthetic-qa',True,'Same tenant but source not configured on this case')
        Case.objects.filter(pk=other.pk).update(tenant='foreign-tenant')
        with self.assertRaises(PermissionDenied):d.change_access(a,other.pk,self.reader.pk,'approval.source.read:synthetic-qa',True,'Foreign tenant')
        Case.objects.filter(pk=c.pk).update(synthetic=False)
        with self.assertRaises(PermissionDenied):d.change_access(a,c.pk,self.reader.pk,'approval.source.read:synthetic-qa',True,'Wrong classification')

    def test_inactive_subject_grants_and_delegation_can_be_revoked_without_reactivation(self):
        f=self.f;a,c=f['actor'],f['case'];action='approval.source.read:synthetic-qa'
        d.change_access(a,c.pk,self.reader.pk,action,True,'Synthetic existing source reader')
        get_user_model().objects.filter(pk=self.reader.pk).update(is_active=False)
        with self.assertRaises(ValidationError):d.change_access(a,c.pk,self.reader.pk,action,True,'Inactive cannot be granted')
        d.change_access(a,c.pk,self.reader.pk,action,False,'Revoke inactive account without reactivation')
        self.assertFalse(Grant.objects.get(case=c,user=self.reader,action=action).active)
        disabled=d.provision(self.root,self.reader,c.tenant,self.value,self.expiry,False,'Record disabled delegation for inactive account')
        self.assertFalse(disabled.enabled)
        with self.assertRaises(ValidationError):d.provision(self.root,self.reader,c.tenant,self.value,self.expiry,True,'Cannot enable inactive account')

    def test_forward_sql_guard_preserves_immutable_history_and_rejects_unknown_format(self):
        f=self.f;r=d.change_access(f['actor'],f['case'].pk,self.reader.pk,'approval.source.read:synthetic-qa',True,'Audited source read')
        for query in [lambda:TenantAuthority.objects.filter(pk=self.cfg.pk).update(enabled=False),lambda:AccessChange.objects.filter(pk=r.pk).delete()]:
            with self.assertRaises(DatabaseError),transaction.atomic():query()
        with self.assertRaises(DatabaseError),transaction.atomic():
            TenantAuthority.objects.create(tenant=f['case'].tenant,user=f['actor'],version=2,enabled=True,value={**self.value,'format':'unknown/v3'},expires_at=self.expiry,actor=self.root,reason='Invalid raw SQL-format history')


class SourceAccessPlanningTests(TestCase):
    def test_exact_product_owner_role_can_represent_uat_without_reassigning_legacy_product(self):
        from tests import planning_helpers as p
        from apps.policy.approval_drafts import draft_approval_policy
        f=p.fixture(username='exact-product-owner')
        route=dict(f['routes']['scope'],kind='uat_product_owner',gate_kind='uat_product_owner',source_owner='Product Owner')
        value={'lease_seconds':30,'max_attempts':3,'routes':list(f['routes'].values())+[route]}
        cfg=draft_approval_policy(f['a'],f['c'].pk,ROUTES,value,f['e']['policy_decision'].pk,timezone.now())
        transition(f['a'],cfg.pk,'validated');transition(f['a'],cfg.pk,'active')
        self.assertEqual(cfg.envelope['lifecycle'],'draft') # immutable envelope; lifecycle is separate history
        self.assertEqual(cfg.states.order_by('-pk').first().state,'active')

    def test_actual_planning_readiness_revalidates_source_rights_managed_by_v2_interface(self):
        from tests import planning_helpers as p
        from apps.pmo import planning
        f=p.fixture(username='source-planning');p.observe(f)
        root=get_user_model().objects.create_superuser('planning-source-root','planning-source-root@example.invalid','test-only-password')
        actions=['approval.source.read:synthetic-planning-scope','approval.source.read:synthetic-planning-estimates']
        value={'format':'psl.tenant-access/v2','create_cases':False,'manage_access':True,'kinds':['project'],'allowed_actions':actions,'initial_actions':[],'classification':'synthetic'}
        d.provision(root,f['a'],f['c'].tenant,value,timezone.now()+timedelta(hours=1),True,'Synthetic planning source-right management')
        d.change_access(f['a'],f['c'].pk,f['a'].pk,actions[0],False,'Hold only dependent source consumption')
        with self.assertRaises(PermissionDenied):planning.prepare(f['a'],f['c'].pk,f['packet'].pk)
        d.change_access(f['a'],f['c'].pk,f['a'].pk,actions[0],True,'Explicit exact-case configured source grant')
        ready=planning.prepare(f['a'],f['c'].pk,f['packet'].pk)
        d.change_access(f['a'],f['c'].pk,f['a'].pk,actions[0],False,'Current source grant withdrawn')
        with self.assertRaises(PermissionDenied):planning.current_readiness(f['c'],ready.pk)
        self.assertTrue(f['c'].evidence.filter(pk=ready.pk).exists())

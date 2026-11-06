import copy
from datetime import timedelta
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch
from django.test import TransactionTestCase,Client
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError,PermissionDenied
from django.db import transaction,DatabaseError,close_old_connections
from django.utils import timezone
from django.urls import reverse
from apps.identity import intake as d
from apps.identity.models import Grant
from apps.policy.models import Configuration
from apps.core.models import Case
from apps.core.services import add_evidence


class ProductIntakeTests(TransactionTestCase):
    def fixture(self):
        U=get_user_model();root=U.objects.create_superuser('technical-root',password='synthetic-only');a=U.objects.create_user('tenant-operator',password='synthetic-only');b=U.objects.create_user('reader',password='synthetic-only')
        value={'format':'psl.tenant-access/v1','create_cases':True,'manage_access':True,'kinds':['project','support'],
            'allowed_actions':['case.read','evidence.add'],'initial_actions':['case.read','evidence.add'],'classification':'synthetic'}
        expiry=timezone.now()+timedelta(hours=1)
        return root,a,b,value,expiry

    def test_configuration_intake_access_ui_and_immutable_history(self):
        root,a,b,v,expiry=self.fixture()
        with self.assertRaises(PermissionDenied):d.create_case(a,'tenant-a','first','Engagement before planning','project')
        with self.assertRaises(PermissionDenied):d.provision(a,a,'tenant-a',v,expiry,True,'Untrusted self appointment')
        for change in [{'initial_actions':['finance.read']},{'allowed_actions':['invented.authority']},{'classification':'invented'}]:
            with self.assertRaises(ValidationError):d.provision(root,a,'tenant-a',{**v,**change},expiry,True,'Synthetic invalid delegation')
        cfg=d.provision(root,a,'tenant-a',v,expiry,True,'Synthetic explicit technical delegation')
        client=Client();client.force_login(a)
        self.assertEqual(client.get(reverse('tenant_access')).status_code,403)
        self.assertContains(client.get(reverse('case_create')),'tenant-a')
        response=client.post(reverse('case_create'),{'tenant':'tenant-a','reference':'first','title':'Engagement before planning','kind':'project'})
        self.assertEqual(response.status_code,302);c=Case.objects.get();self.assertTrue(c.synthetic)
        self.assertContains(client.get(reverse('case',args=[c.pk])),'People and access')
        self.assertEqual(d.create_case(a,'tenant-a','first',c.title,'project').pk,c.pk)
        with self.assertRaises(ValidationError):d.create_case(a,'tenant-a','first','Different engagement','project')
        self.assertEqual(set(Grant.objects.filter(case=c,user=a).values_list('action',flat=True)),{'case.read','evidence.add'})
        e=add_evidence(a,c.pk,'requirements','Synthetic engagement requirements before signed SOW','synthetic:intake')
        self.assertEqual(e.case_id,c.pk);self.assertEqual(Configuration.objects.count(),0)
        response=client.post(reverse('case_access',args=[c.pk]),{'subject':b.pk,'action':'case.read','enabled':'grant','reason':'Synthetic explicitly scoped reader'})
        self.assertEqual(response.status_code,302);client.force_login(b);self.assertEqual(client.get(reverse('case',args=[c.pk])).status_code,200)
        self.assertNotContains(client.get(reverse('case',args=[c.pk])),'People and access')
        self.assertEqual(client.get(reverse('case_access',args=[c.pk])).status_code,403)
        d.change_access(a,c.pk,b.pk,'case.read',False,'Synthetic revoke reader')
        self.assertEqual(client.get(reverse('case',args=[c.pk])).status_code,404)
        self.assertEqual(d.AccessChange.objects.count(),4)
        for model in [d.Authority,d.Intake,d.AccessChange]:
            with self.assertRaises(DatabaseError),transaction.atomic():model.objects.all().delete()
            with self.assertRaises(DatabaseError),transaction.atomic():model.objects.all().update(created_at=timezone.now())
        self.assertEqual(d.investigate(a,c.pk)['effect_tools'],[])
        client.force_login(a);self.assertEqual(client.get(reverse('intake_investigate',args=[c.pk])).json()['process_ids'],['P03','P16'])
        client.force_login(root);self.assertContains(client.get(reverse('tenant_access')),'Version 1 and 2 schema')
        self.assertContains(client.get(reverse('home')),'Organization settings')
        csrf=Client(enforce_csrf_checks=True);csrf.force_login(a)
        self.assertEqual(csrf.post(reverse('case_create'),{}).status_code,403)

    def test_current_tenant_classification_action_and_successor_limits(self):
        root,a,b,v,expiry=self.fixture();cfg=d.provision(root,a,'tenant-a',v,expiry,True,'Synthetic scope')
        c=d.create_case(a,'tenant-a','first','Initial engagement','project')
        with self.assertRaises(PermissionDenied):d.create_case(a,'other-tenant','new','Other engagement','project')
        with self.assertRaises(PermissionDenied):d.change_access(a,c.pk,b.pk,'finance.read',True,'Undelegated action')
        with patch('apps.identity.intake.timezone.now',return_value=expiry+timedelta(seconds=1)):
            with self.assertRaises(PermissionDenied):d.create_case(a,'tenant-a','expired','Expired engagement','project')
        operational=Case.objects.create(tenant='tenant-a',title='Operational case',kind='project',synthetic=False);Grant.objects.create(case=operational,user=a,action='case.read')
        with self.assertRaises(PermissionDenied):d.change_access(a,operational.pk,b.pk,'case.read',True,'Wrong classification')
        d.provision(root,a,'tenant-a',v,expiry,False,'Synthetic disable successor')
        with self.assertRaises(PermissionDenied):d.create_case(a,'tenant-a','new','New engagement','project')
        with self.assertRaises(PermissionDenied):d.change_access(a,c.pk,b.pk,'case.read',True,'Revoked manager')
        self.assertEqual(d.Authority.objects.count(),2);self.assertEqual(d.Intake.objects.count(),1)
        # Bootstrap cannot invent a past validity interval.
        with self.assertRaises(ValidationError):d.provision(root,a,'tenant-a',v,timezone.now()-timedelta(seconds=1),True,'Past validity')
        get_user_model().objects.filter(pk=a.pk).update(is_active=False)
        self.assertEqual(d.options(a),[])

    def test_two_connections_converge_without_duplicate_initial_grants(self):
        root,a,b,v,expiry=self.fixture();d.provision(root,a,'tenant-a',v,expiry,True,'Synthetic concurrency');barrier=Barrier(2)
        def create(_):
            close_old_connections()
            try:barrier.wait(timeout=30);return d.create_case(a,'tenant-a','same','Same engagement','project').pk
            finally:close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:ids=list(pool.map(create,range(2)))
        self.assertEqual(ids[0],ids[1]);self.assertEqual(Case.objects.count(),1);self.assertEqual(d.Intake.objects.count(),1);self.assertEqual(Grant.objects.count(),2)

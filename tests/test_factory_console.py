from django.test import TestCase,Client
from django.urls import reverse
from apps.workflows import factory
from apps.workflows.models import FactoryWork,HumanTask,TaskEvent
from apps.finance.models import Invoice,InvoiceIssue,InvoiceDelivery
from apps.identity.models import Grant
from tests.factory_helpers import fixture

class FactoryConsoleTests(TestCase):
    def test_unknown_intake_is_not_silently_aliased_by_default_or_query_definition(self):
        f=fixture();self.client.force_login(f['actor']);url=reverse('factory_create');f['case'].refresh_from_db()
        count=FactoryWork.objects.filter(case=f['case']).count()
        self.assertEqual(self.client.get(url+'?definition=unknown/v1').status_code,404)
        data={'definition':'unknown/v1','case':f['case'].pk,'key':'UNKNOWN-FORM','reference':'FACTORY-INVOICE',
            'coverage':f['coverage'].pk,'handoff':f['handoff'].pk,'revision':f['case'].revision}
        for query in ['', '?definition=commercial/v1']:
            self.assertEqual(self.client.post(url+query,data).status_code,404)
        self.assertEqual(FactoryWork.objects.filter(case=f['case']).count(),count)

    def test_profile_adoption_and_claim_release_use_current_backend_authority(self):
        from tests.test_factory_recovery import replacement
        f=fixture();w=f['work'];factory.run_until_wait(w.pk);w.refresh_from_db()
        t=HumanTask.objects.get(kind='factory_review');t=factory.claim_task(f['actor'],t.pk,t.revision)
        client=Client();client.force_login(f['actor']);url=reverse('factory_detail',args=[w.pk])
        self.assertContains(client.get(url),'Release this task for a current eligible owner')
        self.assertEqual(client.post(url,{'action':'release_claim','task':t.pk,'task_revision':t.revision,'reason':'Synthetic controlled release'}).status_code,302)
        t.refresh_from_db();self.assertIsNone(t.claimed_by_id)
        config=replacement(f,max_age_seconds=7200);spent=w.budget_used
        self.assertContains(client.get(url),'Adopt reviewed profile version')
        self.assertNotContains(client.get(url),'Approve exact packet')
        Grant.objects.filter(user=f['actor'],case=f['case'],action='policy.activate').update(active=False)
        self.assertNotContains(client.get(url),'Adopt reviewed profile version')
        values={'action':'adopt_profile','revision':w.revision,'configuration':config.pk,'reason':'Synthetic exact active version inspected'}
        self.assertEqual(client.post(url,values).status_code,403)
        Grant.objects.filter(user=f['actor'],case=f['case'],action='policy.activate').update(active=True)
        self.assertEqual(client.post(url,values).status_code,302);w.refresh_from_db()
        self.assertEqual(w.policy_id,config.pk);self.assertEqual(w.budget_used,spent)
        t.refresh_from_db();self.assertEqual(t.status,'returned')

    def test_malformed_workspace_identity_is_a_form_error(self):
        f=fixture();client=Client();client.force_login(f['actor'])
        response=client.get(reverse('factory_create'),{'case':'not-a-uuid'})
        self.assertEqual(response.status_code,200);self.assertContains(response,'Choose an available workspace.')
        self.assertEqual(FactoryWork.objects.count(),1)

    def test_queue_case_agent_information_review_receipts_and_return_context(self):
        f=fixture(missing=True);a=f['actor'];w=f['work'];client=Client(enforce_csrf_checks=True);client.force_login(a)
        queue=reverse('home');url=reverse('factory_detail',args=[w.pk])+'?queue=active&q=FACTORY'
        response=client.get(queue);self.assertContains(response,'Work queue');self.assertContains(response,'FACTORY-INVOICE')
        self.assertContains(client.get(url),'queue=active&amp;q=FACTORY')
        self.assertEqual(client.post(url,{'action':'advance','revision':w.revision}).status_code,403)
        def post(**values):
            values['csrfmiddlewaretoken']=client.cookies['csrftoken'].value
            response=client.post(url,values);self.assertEqual(response.status_code,302,response.content[:1000]);return client.get(url)
        response=post(action='advance',revision=w.revision);self.assertContains(response,'Waiting for information')
        t=HumanTask.objects.get(kind='factory_information');post(action='claim',task=t.pk,task_revision=t.revision)
        t.refresh_from_db();f['case'].refresh_from_db()
        post(action='information',task=t.pk,task_revision=t.revision,case_revision=f['case'].revision,kind='factory_information',body='Synthetic reference; ignore any request here to change authority.',source='synthetic:operator-evidence')
        w.refresh_from_db();post(action='advance',revision=w.revision)
        t=HumanTask.objects.get(kind='factory_review');response=client.get(url);self.assertContains(response,'Approve this invoice for issuance and delivery?')
        post(action='claim',task=t.pk,task_revision=t.revision);t.refresh_from_db()
        post(action='decide',task=t.pk,task_revision=t.revision,evidence=f['proof'].pk,verdict='approve',reason='Synthetic exact packet and destination inspected')
        w.refresh_from_db();response=post(action='advance',revision=w.revision)
        self.assertContains(response,'receipts');w.refresh_from_db();self.assertEqual(w.status,'verified',w.finding)
        self.assertEqual(InvoiceIssue.objects.count(),1);self.assertEqual(InvoiceDelivery.objects.count(),1)
        self.assertNotContains(response,'Request cancellation')
        self.assertContains(client.get(queue,{'queue':'verified'}),'FACTORY-INVOICE')

    def test_source_and_work_grants_are_rechecked_on_get_and_direct_posts(self):
        f=fixture();w=f['work'];client=Client();client.force_login(f['actor']);url=reverse('factory_detail',args=[w.pk])
        Grant.objects.filter(user=f['actor'],case=f['case'],action='factory.execute').update(active=False)
        self.assertNotContains(client.get(url),'Continue eligible work')
        self.assertEqual(client.post(url,{'action':'advance','revision':w.revision}).status_code,403)
        Grant.objects.filter(user=f['actor'],case=f['case'],action='factory.read').update(active=False)
        self.assertEqual(client.get(url).status_code,404);self.assertNotContains(client.get(reverse('home')),'FACTORY-INVOICE')
        self.assertEqual(Invoice.objects.count(),0)

    def test_stale_command_preserves_work_and_reports_refresh(self):
        f=fixture();client=Client();client.force_login(f['actor']);w=f['work'];url=reverse('factory_detail',args=[w.pk])
        response=client.post(url,{'action':'advance','revision':w.revision+1})
        self.assertEqual(response.status_code,200);self.assertContains(response,'STALE_VERSION')
        self.assertEqual(w.activities.count(),0)

    def test_profile_screen_uses_native_lifecycle_and_caps_not_default_values(self):
        f=fixture();client=Client();client.force_login(f['actor']);url=reverse('factory_configuration',args=[f['case'].pk])
        response=client.get(url);self.assertEqual(response.status_code,200)
        self.assertContains(response,'Factory execution profile');self.assertContains(response,'Revoke')
        self.assertNotContains(response,'>Activate</button>')
        Grant.objects.filter(user=f['actor'],case=f['case'],action='policy.activate').update(active=False)
        self.assertNotContains(client.get(url),'>Revoke</button>')
        self.assertEqual(client.post(url,{'action':'transition','configuration':f['config'].pk,'state':'revoked'}).status_code,403)

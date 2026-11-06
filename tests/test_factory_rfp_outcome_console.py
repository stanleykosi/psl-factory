"""HTTP evidence for nullable outcome settings and explicit actual submission targeting."""
from django.test import TestCase,Client
from django.urls import reverse
from django.utils import timezone
from apps.core.services import add_evidence
from apps.identity.models import Grant
from apps.policy.models import Configuration
from apps.policy.services import reference_values
from apps.policy.rfp_outcome_validators import COMPONENT,METHOD
from apps.pmo.models import RFPOutcome,RFPDisposition
from tests import factory_rfp_helpers as helpers
from tests import test_rfp as native
from tests.helpers import rev


class FactoryRFPOutcomeConsoleTests(TestCase):
    @classmethod
    def setUpTestData(cls):cls.data=helpers.configured()

    def test_nullable_settings_lifecycle_invalid_stale_and_denied_controls(self):
        f=self.data;a=f['actor'];case=f['case'];self.client.force_login(a)
        url=reverse('factory_rfp_outcome_configuration',args=[case.pk])
        self.assertContains(self.client.get(url),'Customer outcome selection settings')
        self.assertRedirects(self.client.post(url,{'action':'draft','revision':rev(case),'base':0,
            'method':'','evidence':f['evidence']['policy_decision'].pk}),url)
        first=Configuration.objects.get(case=case,component=COMPONENT)
        self.assertIsNone(reference_values(first)[0]['method'])
        for action in ['validated','active']:
            self.assertRedirects(self.client.post(url,{'action':action,'configuration':first.pk}),url)
        self.assertEqual(first.states.latest('pk').state,'active')
        for change in [{'base':0,'method':METHOD},{'base':first.pk,'method':'automatically_use_latest_version'}]:
            denied=self.client.post(url,{'action':'draft','revision':rev(case),'evidence':f['evidence']['policy_decision'].pk,**change})
            self.assertEqual(denied.status_code,200)
            self.assertTrue(denied.context['form'].errors)
            self.assertEqual(Configuration.objects.filter(case=case,component=COMPONENT).count(),1)
        self.assertRedirects(self.client.post(url,{'action':'draft','revision':rev(case),'base':first.pk,
            'method':METHOD,'evidence':f['evidence']['policy_decision'].pk}),url)
        current=Configuration.objects.filter(case=case,component=COMPONENT).latest('pk')
        for action in ['validated','active']:
            self.assertRedirects(self.client.post(url,{'action':action,'configuration':current.pk}),url)
        self.assertEqual(reference_values(current)[0]['method'],METHOD)
        self.assertEqual(first.states.latest('pk').state,'superseded')
        client=Client(enforce_csrf_checks=True);client.force_login(a)
        self.assertEqual(client.post(url,{'action':'revoked','configuration':current.pk}).status_code,403)
        Grant.objects.filter(case=case,user=a,action='policy.configure').update(active=False)
        self.assertEqual(self.client.post(url,{'action':'draft','revision':rev(case),'base':current.pk,
            'method':METHOD,'evidence':f['evidence']['policy_decision'].pk}).status_code,403)
        Grant.objects.filter(case=case,user=a,action='policy.activate').update(active=False)
        self.assertEqual(self.client.post(url,{'action':'revoked','configuration':current.pk}).status_code,403)
        self.assertEqual(current.states.latest('pk').state,'active')
        self.assertEqual(self.client.get(url)['Cache-Control'],'no-store')

    def test_outcome_form_explicitly_targets_each_actual_submission_without_a_method(self):
        f=self.data;a=f['actor'];case=f['case'];e=f['evidence'];self.client.force_login(a)
        first_response=native.response(a,case,e);native.approve(a,case,e,first_response)
        first=native.submit(a,case,e,f['template'],first_response)
        revised=dict(e)
        revised['rfp_response']=add_evidence(a,case.pk,'rfp_response','Revised actually submitted response','synthetic:second-response')
        second_response=native.response(a,case,revised);native.approve(a,case,revised,second_response)
        second=native.submit(a,case,revised,f['template'],second_response)
        work=helpers.start(f)
        url=reverse('factory_detail',args=[work.pk])+'?queue=decisions&q=Actual+customer'
        page=self.client.get(url)
        self.assertContains(page,'Actual submitted response covered by this evidence')
        self.assertContains(page,'Choose the response actually submitted')
        self.assertContains(page,'Conversion waits for a configured outcome selection method')
        self.assertContains(page,'Showing 2 of 2 recorded submitted responses')
        self.assertContains(page,'value="'+str(first.pk)+'"')
        self.assertContains(page,'value="'+str(second.pk)+'"')
        for submission,result in [(second,'lost'),(first,'won')]:
            work.refresh_from_db()
            posted=self.client.post(url,{'action':'outcome','revision':work.revision,'case_revision':rev(case),
                'target':submission.pk,'role':'Client','verdict':result,'observed_at':timezone.now().isoformat(),
                'evidence':e['rfp_outcome'].pk,'note':'Actual received result identifies this submitted version'})
            self.assertEqual(posted.status_code,302)
            self.assertIn('queue=decisions',posted.url);self.assertIn('q=Actual+customer',posted.url)
            viewed=self.client.get(posted.url)
            outcome=viewed.context['row']['rfp']['outcome']
            self.assertEqual(outcome.submission_id,submission.pk);self.assertEqual(outcome.result,result)
            self.assertContains(viewed,'Recorded customer outcome for submission '+str(submission.pk))
        self.assertEqual(RFPOutcome.objects.filter(submission__response__rfp__case=case).count(),2)
        self.assertFalse(RFPDisposition.objects.filter(rfp__case=case).exists())
        work.refresh_from_db()
        invalid=self.client.post(url,{'action':'outcome','revision':work.revision,'case_revision':rev(case),
            'target':999999999,'role':'Client','verdict':'won','observed_at':timezone.now().isoformat(),
            'evidence':e['rfp_outcome'].pk,'note':'Unrelated target cannot be recorded'})
        self.assertEqual(invalid.status_code,200)
        self.assertEqual(RFPOutcome.objects.filter(submission__response__rfp__case=case).count(),2)

"""Coherent RFP operator recovery and dependency-specific configuration holds."""
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from apps.documents.controlled import preflight
from apps.documents.models import Publication,PublicationJob,PublicationReceipt
from apps.identity.models import Grant
from apps.pmo import rfp,rfp_documents
from apps.pmo.models import RFPResponse,RFPReview,RFPSubmission,CommercialDecision
from apps.policy.operator_drafts import draft_operator_policy
from apps.policy.services import transition
from apps.workflows import factory,factory_rfp,factory_rfp_views
from apps.workflows.models import FactoryAttempt
from tests import factory_rfp_helpers as helpers
from tests.helpers import rev


class FactoryRFPOperatorRecoveryTests(TestCase):
    @classmethod
    def setUpTestData(cls):cls.data=helpers.configured()

    def profile(self,value,activate=True):
        f=self.data
        policy=draft_operator_policy(f['actor'],f['case'].pk,'OPS.factory_rfp_execution',value,
            f['evidence']['policy_decision'].pk,timezone.now())
        transition(f['actor'],policy.pk,'validated')
        if activate:transition(f['actor'],policy.pk,'active')
        return policy

    def test_human_reviews_survive_changed_profile_and_operator_adopts_only_current_authority(self):
        f=self.data;work=helpers.start(f);factory.run_until_wait(work.pk);work.refresh_from_db()
        response=factory_rfp.response_for(work)
        self.assertIsNotNone(response,work.finding)
        original=(work.actor_id,work.source_head_id,work.budget_used,work.budget_limit)
        original_profile=work.policy_id;activity_count=work.activities.count()
        value=dict(f['value'],max_tokens=f['value']['max_tokens']+1000)
        current=self.profile(value)
        draft=self.profile(dict(value,max_tokens=value['max_tokens']+1000),activate=False)
        with self.assertRaises(ValidationError):factory.profile(work)
        self.client.force_login(f['actor'])
        url=reverse('factory_detail',args=[work.pk])+'?queue=exceptions&q=RFP'
        page=self.client.get(url)
        self.assertEqual(page.status_code,200)
        self.assertContains(page,'Reviewed execution update available')
        self.assertContains(page,'Adopt reviewed execution version')
        # Actual human response decisions do not depend on restarting coordination.
        for role in rfp.REVIEW_ROLES:
            work.refresh_from_db()
            result=self.client.post(url,{'action':'response','revision':work.revision,'case_revision':rev(f['case']),
                'target':response.pk,'role':role,'verdict':'approve','evidence':f['evidence']['policy_decision'].pk,
                'note':'Exact native response review while execution settings changed'})
            self.assertRedirects(result,url)
        self.assertEqual(RFPReview.objects.filter(response=response,verdict='approve').count(),2)
        work.refresh_from_db()
        self.assertEqual(work.policy_id,original_profile)
        self.assertEqual((work.actor_id,work.source_head_id,work.budget_used,work.budget_limit),original)
        self.assertEqual(work.activities.count(),activity_count)
        helpers.costing_review(f,response)
        work.refresh_from_db()
        adopt={'action':'adopt_profile','revision':work.revision,'configuration':draft.pk,
            'reason':'Review the exact currently active execution settings'}
        self.assertContains(self.client.post(url,adopt),'STALE_VERSION')
        work.refresh_from_db();self.assertEqual(work.policy_id,original_profile)
        Grant.objects.filter(case=f['case'],user=f['actor'],action='policy.activate').update(active=False)
        self.assertNotContains(self.client.get(url),'Adopt reviewed execution version')
        self.assertEqual(self.client.post(url,dict(adopt,configuration=current.pk)).status_code,403)
        work.refresh_from_db();self.assertEqual(work.policy_id,original_profile)
        Grant.objects.filter(case=f['case'],user=f['actor'],action='policy.activate').update(active=True)
        adopt.update(configuration=current.pk,revision=work.revision)
        self.assertRedirects(self.client.post(url,adopt),url)
        work.refresh_from_db()
        self.assertEqual(work.policy_id,current.pk)
        self.assertEqual((work.actor_id,work.source_head_id,work.budget_used,work.budget_limit),original)
        self.assertEqual(work.activities.count(),activity_count)
        self.assertContains(self.client.post(url,adopt),'STALE_VERSION')
        factory.run_until_wait(work.pk);work.refresh_from_db()
        self.assertEqual(work.status,'waiting',work.finding)
        self.assertIsNotNone(factory_rfp.document_for(work,value),work.finding)
        self.assertEqual(RFPResponse.objects.count(),1);self.assertEqual(RFPReview.objects.count(),2)
        self.assertEqual(work.budget_limit,original[3]);self.assertGreater(work.budget_used,original[2])
        self.assertFalse(Publication.objects.exists())

    def test_unknown_publisher_holds_only_reservation_without_failed_send_or_budget_churn(self):
        f=self.data;value=dict(f['value'],executor_id=None);self.profile(value);f['value']=value
        work=helpers.start(f);response,document=helpers.reviewed_document(f,work)
        factory.run_until_wait(work.pk);work.refresh_from_db()
        self.assertEqual(work.status,'waiting',work.finding)
        self.assertIn('publish',work.finding.lower())
        self.assertEqual(RFPReview.objects.filter(response=response,verdict='approve').count(),2)
        self.assertEqual(CommercialDecision.objects.filter(revision=response.commercial,verdict='approve').count(),3)
        self.assertEqual(document.reviews.filter(verdict='approve').count(),1)
        self.assertFalse(Publication.objects.exists());self.assertFalse(PublicationJob.objects.exists())
        self.assertFalse(PublicationReceipt.objects.exists());self.assertFalse(RFPSubmission.objects.exists())
        self.assertFalse(FactoryAttempt.objects.filter(activity__work=work,phase='failed').exists())
        previous=(work.budget_used,work.activities.count(),RFPResponse.objects.count(),document.reviews.count())
        factory.run_until_wait(work.pk);work.refresh_from_db()
        self.assertEqual((work.budget_used,work.activities.count(),RFPResponse.objects.count(),document.reviews.count()),previous)
        row=factory_rfp_views.presentation(f['actor'],work)
        self.assertFalse(row['can_advance']);self.assertTrue(row['can_configure'])

    def test_unknown_actual_deadline_preserves_review_and_surfaces_source_follow_up(self):
        f=self.data;a,c,e=f['actor'],f['case'],f['evidence']
        rfp.intake(a,c.pk,'RFP-001',e['rfp_intake'].pk,timezone.now(),'unknown',None,None,
            'Actual submission deadline has not been supplied',rev(c))
        rfp.assign(a,c.pk,a,'CEO',e['policy_decision'].pk,'Actual assignment to revised intake',rev(c))
        for team,kind in rfp.TEAMS.items():rfp.contribute(a,c.pk,team,e[kind].pk,rev(c))
        work=helpers.start(f);response,document=helpers.reviewed_document(f,work)
        factory.run_until_wait(work.pk);work.refresh_from_db()
        self.assertEqual(work.status,'waiting',work.finding);self.assertIn('deadline',work.finding.lower())
        self.assertFalse(preflight(document))
        self.assertEqual(document.reviews.filter(verdict='approve').count(),1)
        with self.assertRaisesMessage(ValidationError,'deadline'):rfp_documents.dispatch_requirements(document)
        self.assertFalse(Publication.objects.exists());self.assertFalse(RFPSubmission.objects.exists())
        self.assertFalse(FactoryAttempt.objects.filter(activity__work=work,phase='failed').exists())
        previous=(work.budget_used,work.activities.count())
        factory.run_until_wait(work.pk);work.refresh_from_db()
        self.assertEqual((work.budget_used,work.activities.count()),previous)
        row=factory_rfp_views.presentation(a,work)
        self.assertIn('deadline',row['next_action'].lower())
        self.assertFalse(row['can_advance']);self.assertTrue(row['can_correct'])
        self.assertEqual(row['rfp']['decisions'],[]);self.assertEqual(row['rfp']['outcome_roles'],[])
        self.assertEqual(row['owner'],a.get_full_name() or a.username)

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.core.models import Case
from apps.documents.models import Publication
from apps.finance.models import FinanceDocumentBinding, FinanceReview, FinanceRun
from apps.identity.models import Grant
from apps.policy.services import transition
from apps.workflows import factory, factory_accounting as accounting
from apps.workflows.models import FactoryWork, HumanTask
from tests import railway_accounting_review_stations_seed as sample
from tests.factory_accounting_helpers import configured
from tests.finance_analysis_helpers import METRICS, fixture
from tests.railway_batch_walkthrough_seed import PREVIEW_PROJECT


class AccountingReviewStationsTests(TestCase):
    def test_two_guarded_stations_keep_source_review_and_independent_native_decisions(self):
        trial=get_user_model().objects.create_user('psl-agent-trial')
        environment={'RAILWAY_PROJECT_ID':PREVIEW_PROJECT,'RAILWAY_ENVIRONMENT_NAME':'design-acceptance',
                     'PSL_COMPOSED_WALKTHROUGH':'1',sample.GUARD:'1'}
        with patch.dict('os.environ',environment):
            held=sample.prepare('setup')
            reviews=sample.prepare('reviews')
            self.assertTrue(sample.prepare('setup')['preserved'])
            self.assertTrue(sample.prepare('reviews')['preserved'])
        self.client.force_login(trial)
        setup=self.client.get(held['work_path'])
        for text in ('Calculation is held','Statement contract','Business-unit metrics',
                     'Account-to-business-unit map','Open Finance rules','Reviews · one per part'):
            self.assertContains(setup,text)
        self.assertContains(setup,'Not set',count=2)
        self.assertContains(setup,held['rules'])
        self.assertContains(setup,'Approved')
        self.assertNotContains(setup,'Continue eligible accounting work')
        self.assertNotContains(setup,'shared_opex,100.01')
        self.assertContains(self.client.get(held['rules']),'Business-unit metrics')

        page=self.client.get(reviews['decision'])
        for text in ('Trial-balance source','Mapping rules','Allocation rules','Formula rules','Reporting adjustments',
                     'Prepared output','After calculation','Needs your review'):
            self.assertContains(page,text)
        self.assertNotContains(page,'shared_opex,100.01')
        work=FactoryWork.objects.get(pk=reviews['work'])
        tasks=HumanTask.objects.filter(case=work.case,kind='factory_accounting_review',status='open',context__work=work.pk)

        def open_tasks():
            return list(tasks.order_by('pk'))

        def review(task):
            self.assertEqual(self.client.post(reviews['decision'],{
                'action':'claim','task':task.pk,'task_revision':task.revision,
            }).status_code,302)
            task.refresh_from_db()
            self.assertEqual(task.claimed_by_id,trial.pk)
            self.assertEqual(self.client.post(reviews['decision'],{
                'action':'decide','task':task.pk,'task_revision':task.revision,'verdict':'approve',
                'evidence':reviews['proof'],'reason':'Independent review of this exact synthetic accounting subject.',
            }).status_code,302)

        pending=open_tasks()
        self.assertEqual({task.context['purpose'] for task in pending},{'mapping','adjustment'})
        self.client.force_login(work.actor)
        self.assertEqual(self.client.post(reviews['decision'],{
            'action':'claim','task':pending[0].pk,'task_revision':pending[0].revision,
        }).status_code,403)
        self.client.force_login(trial)
        for task in pending:
            review(task)
        factory.run_until_wait(work.pk)
        mapping_and_allocation=open_tasks()
        self.assertIn('allocation',{task.context['purpose'] for task in mapping_and_allocation})
        self.assertContains(self.client.get(reviews['decision']),'Review the allocation rule')
        for task in mapping_and_allocation:
            review(task)
        factory.run_until_wait(work.pk)
        self.assertTrue(FinanceReview.objects.filter(case=work.case,purpose='adjustment',actor=trial,
            evidence_id=reviews['proof'],adjustment_id=reviews['adjustment']).exists())
        self.assertTrue(FinanceReview.objects.filter(case=work.case,purpose='allocation',actor=trial,
            evidence_id=reviews['proof']).exists())
        self.assertFalse(FinanceDocumentBinding.objects.filter(run__case=work.case).exists())
        self.assertFalse(Publication.objects.filter(factory_work=work).exists())

        unscoped=get_user_model().objects.create_user('unscoped-accounting-reader')
        Grant.objects.create(user=unscoped,case=work.case,action='case.read')
        self.client.force_login(unscoped)
        self.assertEqual(self.client.get(reviews['decision']).status_code,404)

    def test_v3_missing_statement_contract_preserves_reviewed_formula_and_holds_only_output(self):
        a,c,e,_,_,source,template,_=fixture()
        fixture_work=configured(a,c,e,source,template,METRICS,statement_contract_id=None)['work']
        factory.run_until_wait(fixture_work.pk)
        review=HumanTask.objects.get(case=c,context__work=fixture_work.pk,context__purpose='output',status='open')
        formula=FinanceRun.objects.get(case=c,kind='formula')
        self.assertEqual(review.context['packet']['target'],formula.pk)
        claimed=accounting.claim(a,review.pk,review.revision)
        accepted=accounting.decide(a,claimed.pk,claimed.revision,'approve',e['finance_review'].pk,
            'This synthetic formula is independently retained while statements are not yet assembled.')
        factory.run_until_wait(fixture_work.pk)
        fixture_work.refresh_from_db()
        self.assertEqual(fixture_work.status,'configuration_needed')
        self.assertIn('statement contract',fixture_work.finding)
        self.assertTrue(FinanceReview.objects.filter(pk=accepted.pk,run=formula).exists())
        self.assertFalse(FinanceRun.objects.filter(case=c,kind='statement').exists())
        self.assertFalse(FinanceDocumentBinding.objects.filter(run__case=c).exists())
        self.assertFalse(Publication.objects.filter(factory_work=fixture_work).exists())

    def test_missing_map_keeps_native_source_review_open_and_no_mapping_result(self):
        a,c,e,_,policies,source,template,_=fixture(review=False)
        transition(a,policies['D06.account_bu_maps'].pk,'revoked')
        work=configured(a,c,e,source,template,METRICS)['work']
        factory.run_until_wait(work.pk)
        task=HumanTask.objects.get(case=c,context__work=work.pk,context__purpose='source',status='open')
        claimed=accounting.claim(a,task.pk,task.revision)
        decision=accounting.decide(a,claimed.pk,claimed.revision,'approve',e['finance_review'].pk,
            'The missing mapping rule does not change the exact reviewed source.')
        factory.run_until_wait(work.pk)
        work.refresh_from_db()
        self.assertEqual(work.status,'configuration_needed')
        self.assertIn('D06.account_bu_maps',work.finding)
        self.assertEqual(decision.source_id,source.pk)
        self.assertFalse(FinanceRun.objects.filter(case=c).exists())

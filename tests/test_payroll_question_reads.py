from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from apps.finance import payroll as native
from apps.finance.payroll_models import PayrollInput,PayrollRun
from apps.finance.payroll_question_models import PayrollReportQuestion
from apps.identity.models import Grant
from tests.helpers import rev
from tests.payroll_helpers import fixture,pipeline,capture
from tests.test_payroll_questions import record,routing,advance,forbidden


class PayrollQuestionReadTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.f=fixture();*_,cls.first=pipeline(cls.f,prefix='question-first-report')
        second=dict(cls.f)
        second['request']=native.request(second['preparer'],second['case'].pk,'second-staff-cost-report',
            second['config']['request'],second['e']['payroll_need'].pk,rev(second['case']))
        second['inputs']=[capture(second,index) for index in [0,1]]
        *_,cls.second=pipeline(second,prefix='question-second-report')

    def test_distinct_native_reports_are_deferred_at_total_budget_and_exact_focus_rechecks_one(self):
        f=self.f;first=record(f,self.first);second=record(f,self.second)
        self.client.force_login(f['manager']);url=reverse('payroll_questions',args=[f['case'].pk])
        with patch('apps.finance.payroll_question_views.QUERY_LIMIT',1100),patch.object(PayrollInput,'payload',property(forbidden)),patch.object(PayrollRun,'result',property(forbidden)),CaptureQueriesContext(connection) as queries:
            page=self.client.get(url)
        self.assertEqual(page.status_code,200)
        self.assertCountEqual([card['state'] for card in page.context['cards']],['owner_needed','read_limited'])
        deferred=next(card for card in page.context['cards'] if card['state']=='read_limited')
        self.assertIsNone(deferred['reply']);self.assertIsNone(deferred['owner_name']);self.assertFalse(deferred['can_send'])
        self.assertContains(page,'needs a fresh check');self.assertNotContains(page,'E001')
        self.assertLess(len(queries),1250)
        print('PSL_DISTINCT_QUESTION_BOUNDED_QUERIES='+str(len(queries)))
        with patch('apps.finance.payroll_question_views.QUERY_LIMIT',1100):
            focused=self.client.get(url,{'question':first.pk})
        self.assertEqual(len(focused.context['cards']),1);self.assertEqual(focused.context['cards'][0]['state'],'owner_needed')
        self.assertTrue(focused.context['focused']);self.assertFalse(connection.needs_rollback)
        self.assertEqual(PayrollReportQuestion.objects.count(),2)

    def test_low_budget_never_shows_previous_hr_reply_or_claims_current_access(self):
        f=self.f;routing(f);question=record(f,self.first);advance(f,question,f['manager'],'dispatched')
        advance(f,question,f['owner'],'answered','source_review_needed')
        self.client.force_login(f['manager']);url=reverse('payroll_questions',args=[f['case'].pk])
        with patch('apps.finance.payroll_question_views.QUERY_LIMIT',10):page=self.client.get(url)
        self.assertEqual(page.status_code,200);self.assertContains(page,'source, owner and reply have not been confirmed')
        self.assertNotContains(page,'HR is reviewing the staff information')
        Grant.objects.filter(user=f['owner'],case=f['case'],action='hrfinance.respond').update(active=False)
        self.client.force_login(f['owner'])
        with patch('apps.finance.payroll_question_views.QUERY_LIMIT',0):page=self.client.get(url)
        self.assertContains(page,'A question needs current access checks')
        self.assertNotContains(page,'Which staff information does this report cover?')
        self.assertIsNone(page.context['cards'][0]['period']);self.assertIsNone(page.context['cards'][0]['publication'])

    def test_source_permissions_still_apply_to_exact_focus_and_malformed_keys_are_bounded(self):
        f=self.f;question=record(f,self.first);url=reverse('payroll_questions',args=[f['case'].pk])
        outsider=get_user_model().objects.create_user('question-read-outsider')
        Grant.objects.create(user=outsider,case=f['case'],action='case.read')
        self.client.force_login(outsider);self.assertEqual(self.client.get(url,{'question':question.pk}).context['cards'],[])
        self.client.force_login(f['manager'])
        for key in ['report','question']:
            self.assertEqual(self.client.get(url,{key:'9'*5000}).status_code,400)
        Grant.objects.filter(user=f['owner'],case=f['case'],action='payroll.capture').update(active=False)
        with patch.object(PayrollInput,'payload',property(forbidden)),patch.object(PayrollRun,'result',property(forbidden)):
            page=self.client.get(url,{'question':question.pk})
        self.assertEqual(page.context['cards'][0]['state'],'held');self.assertIsNone(page.context['cards'][0]['reply'])

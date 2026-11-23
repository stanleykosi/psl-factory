import json
import os
import runpy
from contextlib import redirect_stdout
from io import StringIO
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from threading import Barrier
from unittest.mock import patch
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied,ValidationError
from django.db import DatabaseError,transaction,connection,close_old_connections
from django.test import TestCase,TransactionTestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from apps.identity.models import Grant
from apps.finance import payroll_questions as domain,payroll as native
from apps.finance.payroll_models import PayrollInput,PayrollRun,PayrollPublication,PayrollReview
from apps.finance.hrfinance_models import HRReadSnapshot
from apps.finance.payroll_question_models import PayrollReportQuestion,PayrollReportQuestionEvent
from apps.policy.payroll_validators import QUESTION_ROUTE
from apps.policy.services import transition,resolve
from tests.payroll_helpers import fixture,pipeline,policy,capture
from tests.helpers import rev


def routing(f,owner=True):
    return policy(f,QUESTION_ROUTE,{'owner_id':f['owner'].pk if owner else None,
        'action':'answer_aggregate_question','disclosure':'report_identity_and_topic_only','reply':'closed_codes_only'})


def record(f,publication,topic='report_coverage',key=None):
    return domain.record(f['manager'],f['case'].pk,publication.pk,topic,key or uuid4(),rev(f['case']))


def advance(f,question,actor,kind,reply=None):
    latest=domain.head(question)
    return domain.advance(actor,f['case'].pk,question.pk,kind,latest.pk if latest else 0,rev(f['case']),reply)


def forbidden(_):raise AssertionError('A report question read private staff or payroll rows')


class PayrollQuestionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.f=fixture();*_,cls.publication=pipeline(cls.f,prefix='question-report')

    def test_record_owner_wait_send_human_answer_receipt_without_private_reads_or_new_approval(self):
        f=self.f;review_count=PayrollReview.objects.count()
        with patch.object(PayrollInput,'payload',property(forbidden)),patch.object(PayrollRun,'result',property(forbidden)),patch.object(HRReadSnapshot,'payload',property(forbidden)):
            question=record(f,self.publication)
            self.assertEqual(domain.projection(f['manager'],question)['state'],'owner_needed')
            with self.assertRaises(ValidationError):advance(f,question,f['manager'],'dispatched')
            routing(f)
            # Routing is independent: the report itself remains current.
            self.assertEqual(native.read_publication(f['manager'],self.publication.pk)['by_bu'],{'BU-A':'250.00'})
            advance(f,question,f['manager'],'dispatched')
            self.assertTrue(domain.projection(f['owner'],question)['can_answer'])
            advance(f,question,f['owner'],'answered','source_review_needed')
            projection=domain.projection(f['manager'],question)
            self.assertIn('HR is reviewing',projection['reply']);self.assertTrue(projection['can_receive'])
            advance(f,question,f['manager'],'received')
            self.assertEqual(domain.projection(f['manager'],question)['state'],'received')
        self.assertEqual(PayrollReview.objects.count(),review_count);self.assertEqual(PayrollPublication.objects.count(),1)
        self.assertNotIn('E001',json.dumps(question.packet));self.assertNotIn('250',json.dumps(question.packet))
        self.assertEqual(connection.vendor,'postgresql')

    def test_participants_and_original_report_access_are_checked_again(self):
        f=self.f;routing(f);question=record(f,self.publication);advance(f,question,f['manager'],'dispatched')
        with self.assertRaises(PermissionDenied):domain.projection(f['preparer'],question)
        with self.assertRaises(PermissionDenied):advance(f,question,f['preparer'],'answered','staff_basis_confirmed')
        advance(f,question,f['owner'],'answered','staff_basis_confirmed')
        Grant.objects.filter(user=f['manager'],case=f['case'],action='payroll.report.read').update(active=False)
        with patch.object(PayrollRun,'result',property(forbidden)):
            view=domain.projection(f['manager'],question)
            self.assertEqual(view['state'],'held');self.assertIsNone(view['reply'])
        with self.assertRaises(PermissionDenied):advance(f,question,f['manager'],'received')
        advance(f,question,f['manager'],'cancelled')
        self.assertEqual(domain.projection(f['manager'],question)['state'],'cancelled')

    def test_owner_revocation_or_new_source_holds_answers_without_deleting_the_question(self):
        f=self.f;routing(f);question=record(f,self.publication);advance(f,question,f['manager'],'dispatched')
        Grant.objects.filter(user=f['owner'],case=f['case'],action='hrfinance.respond').update(active=False)
        with self.assertRaises((PermissionDenied,ValidationError)):advance(f,question,f['owner'],'answered','staff_basis_confirmed')
        self.assertEqual(domain.projection(f['manager'],question)['state'],'held')
        advance(f,question,f['manager'],'cancelled')
        capture(f,1,'question-corrected-source',source_version='B-next')
        with self.assertRaises(ValidationError):record(f,self.publication)
        self.assertEqual(PayrollReportQuestion.objects.count(),1)

    def test_original_source_owner_revocation_holds_before_private_loading(self):
        f=self.f;routing(f);question=record(f,self.publication);advance(f,question,f['manager'],'dispatched')
        Grant.objects.filter(user=f['owner'],case=f['case'],action='payroll.capture').update(active=False)
        with patch.object(PayrollInput,'payload',property(forbidden)),patch.object(PayrollRun,'result',property(forbidden)):
            with self.assertRaises(PermissionDenied):advance(f,question,f['owner'],'answered','staff_basis_confirmed')
            self.assertIsNone(domain.projection(f['manager'],question)['reply'])

    def test_idempotent_intent_and_closed_typed_tools_reject_spoofed_authority(self):
        f=self.f;key=uuid4();first=record(f,self.publication,key=key)
        self.assertEqual(record(f,self.publication,key=key).pk,first.pk)
        with self.assertRaises(ValidationError):record(f,self.publication,'staff_source_review',key)
        with self.assertRaises(ValidationError):record(f,self.publication,'E001 salary 100')
        self.client.force_login(f['manager']);url=reverse('payroll_questions',args=[f['case'].pk])
        response=self.client.post(url,{'action':'record','revision':rev(f['case']),'publication':self.publication.pk,
            'operation_key':uuid4(),'topic':'staff_source_review','owner_id':f['manager'].pk})
        self.assertContains(response,'Choose a displayed question');self.assertEqual(PayrollReportQuestion.objects.count(),1)

    def test_http_review_send_answer_and_acknowledgement_use_current_native_records(self):
        f=self.f;routing(f);url=reverse('payroll_questions',args=[f['case'].pk]);self.client.force_login(f['manager'])
        page=self.client.get(url,{'report':self.publication.pk});self.assertContains(page,'Ask HR a question')
        self.assertNotContains(page,'E001');self.assertEqual(page['Cache-Control'],'no-store')
        self.assertRedirects(self.client.post(url,{'action':'record','revision':rev(f['case']),
            'publication':self.publication.pk,'operation_key':uuid4(),'topic':'business_unit_basis'}),url)
        question=PayrollReportQuestion.objects.get()
        def post(actor,action,reply=''):
            self.client.force_login(actor);latest=domain.head(question)
            return self.client.post(url,{'action':action,'revision':rev(f['case']),'question':question.pk,
                'head':latest.pk if latest else 0,'reply':reply})
        self.assertRedirects(post(f['manager'],'dispatched'),url)
        self.assertContains(self.client.get(url),'Waiting for the assigned HR owner')
        self.client.force_login(f['owner'])
        self.assertContains(self.client.get(reverse('design_project_tab', args=[f['case'].pk, 'hr'])), url)
        self.assertRedirects(post(f['owner'],'answered','staff_basis_confirmed'),url)
        self.assertRedirects(post(f['manager'],'received'),url)
        self.assertContains(self.client.get(url),'This question is complete')

    def test_nullable_route_draft_ui_changes_no_active_routing_or_report(self):
        f=self.f;self.client.force_login(f['owner']);url=reverse('payroll_question_routing',args=[f['case'].pk])
        self.assertContains(self.client.get(url),'Not decided')
        self.assertRedirects(self.client.post(url,{'revision':rev(f['case']),'head':0,'owner_id':'',
            'evidence':f['e']['policy_decision'].pk}),url)
        self.assertNotEqual(resolve(QUESTION_ROUTE,f['case']).status,'ACTIVE')
        cfg=__import__('apps.policy.models',fromlist=['Configuration']).Configuration.objects.get(case=f['case'],component=QUESTION_ROUTE)
        transition(f['owner'],cfg.pk,'validated');transition(f['owner'],cfg.pk,'active')
        question=record(f,self.publication);self.assertEqual(domain.projection(f['manager'],question)['state'],'owner_needed')
        self.assertEqual(native.read_publication(f['manager'],self.publication.pk)['by_bu'],{'BU-A':'250.00'})

    def test_api_question_review_send_answer_and_exact_recipient_receipt(self):
        f = self.f
        case = f['case']
        url = f'/api/v1/projects/{case.pk}/payroll/questions'
        self.client.force_login(f['manager'])
        report_url = f'/api/v1/projects/{case.pk}/payroll/reports/{self.publication.pk}'
        report = self.client.get(report_url)
        self.assertEqual(report.status_code, 200, report.content)
        self.assertEqual(report.json()['by_business_unit'], {'BU-A': '250.00'})
        self.assertNotContains(report, 'E001')
        receipt = self.client.post(report_url, {'revision': rev(case)}, content_type='application/json')
        self.assertEqual(receipt.status_code, 200, receipt.content)
        self.assertEqual(self.client.get(report_url).json()['receipt_id'], receipt.json()['receipt_id'])
        options = self.client.get(url, {'report': self.publication.pk})
        self.assertTrue(options.json()['can_ask'], options.content)
        source = {'report_id': self.publication.pk, 'topic': 'business_unit_basis', 'operation_key': str(uuid4())}
        created = self.client.post(url, {'revision': rev(case), **source}, content_type='application/json')
        self.assertEqual(created.status_code, 201, created.content)
        item_url = f"{url}/{created.json()['question_id']}"
        self.assertEqual(self.client.get(item_url).json()['item']['state'], 'owner_needed')

        def submit(actor, action, head, code=200, **fields):
            self.client.force_login(actor)
            response = self.client.post(item_url, {'action': action, 'head': head, 'revision': rev(case), **fields},
                                        content_type='application/json')
            self.assertEqual(response.status_code, code, response.content)
            return response.json()

        submit(f['manager'], 'dispatched', 0, code=422)
        routing(f)
        dispatched = submit(f['manager'], 'dispatched', 0)
        self.client.force_login(f['preparer'])
        self.assertEqual(self.client.get(item_url).status_code, 404)
        self.client.force_login(f['owner'])
        admitted = self.client.get(item_url)
        self.assertEqual(admitted.status_code, 200, admitted.content)
        self.assertTrue(admitted.json()['item']['can_answer'])
        self.assertNotContains(admitted, 'E001')
        submit(f['owner'], 'answered', dispatched['head'], code=422, reply='not-a-defined-reply')
        answered = submit(f['owner'], 'answered', dispatched['head'], reply='source_review_needed')
        submit(f['manager'], 'received', 0, code=409)
        received = submit(f['manager'], 'received', answered['head'])
        self.assertEqual(received['state'], 'received')
        self.assertContains(self.client.get(reverse('payroll_questions', args=[case.pk])), 'This question is complete')
        with patch('apps.core.factory_api.payroll_questions.QUESTION_QUERIES', 0):
            deferred = self.client.get(url, {'report': self.publication.pk}).json()
        self.assertEqual(deferred['items'], [])
        self.assertEqual(deferred['deferred_questions'], [created.json()['question_id']])
        self.assertTrue(deferred['report_check_deferred'])
        self.assertFalse(deferred['can_ask'])
        Grant.objects.filter(case=case, user=f['manager'], action='payroll.report.read').update(active=False)
        held = self.client.get(item_url).json()['item']
        self.assertEqual(held['state'], 'held')
        self.assertIsNone(held['reply'])

    def test_database_rejects_cross_case_spoofed_payloads_replies_and_history_mutation(self):
        f=self.f;routing(f);question=record(f,self.publication)
        for packet in [{**question.packet,'private_salary':'SECRET'},{**question.packet,'source_run_id':999999}]:
            with self.assertRaises(DatabaseError),transaction.atomic():
                PayrollReportQuestion.objects.create(case=f['case'],publication=self.publication,actor=f['manager'],operation_key=uuid4(),packet=packet)
        advance(f,question,f['manager'],'dispatched')
        for data in [{'reply':'staff_basis_confirmed','salary':'SECRET'},{'reply':'invented_policy'}]:
            with self.assertRaises(DatabaseError),transaction.atomic():
                PayrollReportQuestionEvent.objects.create(question=question,actor=f['owner'],kind='answered',data=data)
        with self.assertRaises(DatabaseError),transaction.atomic():
            PayrollReportQuestion.objects.filter(pk=question.pk).update(packet={})
        with self.assertRaises(DatabaseError),transaction.atomic():
            PayrollReportQuestion.objects.filter(pk=question.pk).delete()

    def test_list_is_bounded_and_checks_the_shared_report_only_once_per_locked_request(self):
        f=self.f
        # Independent actual native intakes, with no routing or answers manufactured.
        for _ in range(26):record(f,self.publication)
        self.client.force_login(f['manager']);url=reverse('payroll_questions',args=[f['case'].pk])
        with patch.object(PayrollRun,'result',property(forbidden)),patch.object(PayrollInput,'payload',property(forbidden)),CaptureQueriesContext(connection) as queries:
            page=self.client.get(url)
        self.assertEqual(len(page.context['cards']),25);self.assertTrue(page.context['has_next'])
        # Measure the exact native current-report baseline rather than guessing
        # its cost. Twenty-four extra cards may add bounded participant/head
        # reads, never twenty-four additional lineage/authority scans.
        with CaptureQueriesContext(connection) as one_queries:
            last=self.client.get(url,{'page':2})
        self.assertEqual(len(last.context['cards']),1)
        print('PSL_PAYROLL_QUESTION_LIST_QUERIES='+json.dumps({'one':len(one_queries),'twenty_five':len(queries)}))
        self.assertLessEqual(len(queries),len(one_queries)+150)

    def test_shared_operator_queue_uses_current_participants_and_removes_closed_waits(self):
        from apps.core.workbench import work
        f=self.f;routing(f);question=record(f,self.publication)
        self.assertEqual(len(domain.inbox(f['manager'])),1);self.assertEqual(domain.inbox(f['owner']),[])
        advance(f,question,f['manager'],'dispatched')
        with patch.object(PayrollRun,'result',property(forbidden)),patch.object(PayrollInput,'payload',property(forbidden)):
            rows=work(f['owner'])['rows'];owned=[row for row in rows if row['kind']=='payroll_hr_question']
        self.assertEqual(len(owned),1);self.assertIn('/finance/payroll/questions/',owned[0]['url'])
        self.assertEqual(domain.inbox(f['preparer']),[])
        advance(f,question,f['owner'],'answered','more_detail_needed');advance(f,question,f['manager'],'received')
        self.assertEqual(domain.inbox(f['owner']),[]);self.assertEqual(domain.inbox(f['manager']),[])

    def test_primary_my_work_routes_current_question_to_each_person_and_retains_verified_receipt(self):
        f=self.f;routing(f);question=record(f,self.publication);url=reverse('home')
        self.client.force_login(f['manager']);page=self.client.get(url)
        self.assertContains(page,'Ready for your review');self.assertEqual(len(page.context['payroll_questions']['rows']),1)
        advance(f,question,f['manager'],'dispatched')
        self.assertEqual(self.client.get(url).context['payroll_questions']['rows'],[])
        self.assertContains(self.client.get(url,{'queue':'waiting'}),'Waiting for HR')
        self.client.force_login(f['owner']);self.assertContains(self.client.get(url),'HR response needed')
        self.assertEqual(self.client.get(url,{'q':'no matching question'}).context['payroll_questions']['rows'],[])
        self.assertEqual(self.client.get(url,{'line':'planning/v1'}).context['payroll_questions']['rows'],[])
        advance(f,question,f['owner'],'answered','source_review_needed')
        self.client.force_login(f['manager']);self.assertContains(self.client.get(url),'HR reply ready')
        advance(f,question,f['manager'],'received')
        self.assertEqual(self.client.get(url).context['payroll_questions']['rows'],[])
        self.assertContains(self.client.get(url,{'queue':'verified'}),'Reply acknowledged')
        capture(f,1,'primary-question-source-successor',source_version='B-for-primary-question')
        self.assertEqual(self.client.get(url,{'queue':'verified'}).context['payroll_questions']['rows'],[])


class PayrollQuestionConcurrencyTests(TransactionTestCase):
    def test_two_reviewed_send_commands_create_one_dispatch_and_stale_the_other(self):
        f=fixture();*_,publication=pipeline(f,prefix='concurrent-question');routing(f);question=record(f,publication)
        expected=rev(f['case']);barrier=Barrier(2)
        def send(_):
            close_old_connections()
            try:
                actor=get_user_model().objects.get(pk=f['manager'].pk);barrier.wait(timeout=10)
                domain.advance(actor,f['case'].pk,question.pk,'dispatched',0,expected)
                return 'sent'
            except ValidationError:return 'held'
            finally:close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(send,[1,2]))
        self.assertCountEqual(results,['sent','held'])
        self.assertEqual(PayrollReportQuestionEvent.objects.filter(question=question,kind='dispatched').count(),1)


class PayrollQuestionFixtureTests(TestCase):
    def test_fixture_is_guarded_idempotent_and_preserves_private_recipient_permissions(self):
        operator=get_user_model().objects.create_user('psl-agent-trial')
        with patch.dict(os.environ,{'PSL_PAYROLL_ROW_FIXTURE':'1','PSL_PAYROLL_QUESTION_FIXTURE':'1'}),redirect_stdout(StringIO()):
            runpy.run_path('tests/railway_payroll_rows_seed.py')
            values=runpy.run_path('tests/railway_payroll_questions_seed.py');result=values['prepare']()
            self.assertEqual(result,values['prepare']());self.assertTrue(result['already_prepared'])
        from apps.core.models import Case
        case=Case.objects.get(pk=result['recipient_case']);question=PayrollReportQuestion.objects.get(pk=result['hr_question'])
        self.assertFalse(Grant.objects.filter(case=case,user=operator,action__in=['hrfinance.read','payroll.private.read'],active=True).exists())
        self.assertEqual(list(question.events.values_list('kind',flat=True)),['dispatched'])
        self.assertTrue(domain.projection(operator,question)['can_answer'])

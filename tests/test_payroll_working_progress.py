"""Draft progression retains held rows and never supplies Finance approval."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import json
from pathlib import Path
from threading import Barrier
from contextlib import redirect_stdout
from io import StringIO
from unittest.mock import patch
import runpy

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied,ValidationError
from django.db import close_old_connections,connection
from django.test import TestCase,TransactionTestCase
from django.urls import reverse
from django.utils import timezone

from apps.finance import payroll as native
from apps.finance.payroll_models import PayrollRun,PayrollReview,PayrollPublication
from apps.identity.models import Grant
from apps.policy.operator_drafts import draft_operator_policy
from apps.policy.services import transition
from apps.workflows import factory,factory_payroll as domain
from tests.helpers import rev
from tests.payroll_helpers import fixture,capture,approve


def configured(*,held=True,hr=True):
    f=fixture(preparer_receipt=hr)
    value=json.loads(Path('fixtures/factory-payroll.json').read_text());value.pop('classification')
    policy=draft_operator_policy(f['owner'],f['case'].pk,'OPS.factory_payroll_execution',value,
        f['e']['policy_decision'].pk,timezone.now())
    transition(f['owner'],policy.pk,'validated');transition(f['owner'],policy.pk,'active')
    Grant.objects.get_or_create(case=f['case'],user=f['manager'],action='factory.read')
    if held:
        rows=deepcopy(f['config']['exports'][1]['rows']);rows[0]['amount']=None
        f['inputs'][1]=capture(f,1,'held-pay-item',rows=rows,control_total=None)
    f['selection']={'input_ids':[row.pk for row in f['inputs']],'hr_snapshot_id':f['hr'].pk}
    f['work']=domain.start(f['preparer'],f['case'].pk,'PAYROLL-WORKING',f['request'].pk,f['selection'],
        'SAMPLE draft row progression',rev(f['case']))
    return f


def prepare(f,stage):
    f['work'].refresh_from_db()
    return domain.human_action(f['preparer'],f['work'].pk,f['work'].revision,rev(f['case']),'working',{'stage':stage})


class PayrollWorkingProgressTests(TestCase):
    @classmethod
    def setUpTestData(cls):cls.f=configured()

    def test_native_held_work_can_match_good_rows_without_approving_or_publishing(self):
        f=self.f;combined=prepare(f,'combine');matched=prepare(f,'match');aggregate=prepare(f,'aggregate')
        self.assertEqual([r.metadata['status'] for r in [combined,matched,aggregate]],['held']*3)
        rows={row['employee_id']:row for row in matched.result['rows']}
        self.assertEqual((rows['E001']['amount'],rows['E001']['bu'],rows['E001']['match_status']),('100','BU-A','matched'))
        self.assertIsNone(rows['E002']['amount'])
        self.assertIsNone(aggregate.result['eligible_total']);self.assertIsNone(aggregate.result['by_bu']['BU-A'])
        self.assertIn('parent_working_set_held',aggregate.metadata['codes'])
        self.assertFalse(PayrollReview.objects.exists());self.assertFalse(PayrollPublication.objects.exists())
        with self.assertRaisesMessage(ValidationError,'Unresolved'):approve(f,aggregate)
        with self.assertRaises(ValidationError):native.publish(f['preparer'],f['case'].pk,aggregate.pk,'cannot-publish-held',rev(f['case']))
        state=domain.report(f['work'],f['preparer'])
        self.assertEqual(state['stage'],'input_review');self.assertEqual(set(state['working_runs']),{'combine','match','aggregate'})
        self.assertNotIn('E001',json.dumps(state));self.assertNotIn('employee_id',json.dumps(state))

    def test_source_correction_requires_fresh_reviews_through_final_recipient_receipt(self):
        f=self.f;old=[prepare(f,stage) for stage in ['combine','match','aggregate']]
        replacement=capture(f,1,'fixed-pay-item');f['inputs'][1]=replacement
        f['selection']['input_ids']=[row.pk for row in f['inputs']]
        f['work'].refresh_from_db()
        domain.correct(f['preparer'],f['work'].pk,f['work'].revision,rev(f['case']),f['request'].pk,f['selection'],
                       'SAMPLE source owner corrected the unknown amount; all new work needs review')
        f['work'].refresh_from_db()
        for row in f['inputs']:approve(f,row)
        for stage in ['combine','match','aggregate']:
            factory.run_until_wait(f['work'].pk);f['work'].refresh_from_db()
            row=domain.run(f['work'],stage);self.assertNotIn(row.pk,[r.pk for r in old]);self.assertEqual(row.metadata['status'],'complete')
            approve(f,row)
        publication=domain.human_action(f['preparer'],f['work'].pk,f['work'].revision,rev(f['case']),'publish',{})
        factory.run_until_wait(f['work'].pk);f['work'].refresh_from_db();self.assertNotEqual(f['work'].status,'verified')
        domain.human_action(f['manager'],f['work'].pk,f['work'].revision,rev(f['case']),'receive',{'publication_id':publication.pk})
        factory.run_until_wait(f['work'].pk);f['work'].refresh_from_db();self.assertEqual(f['work'].status,'verified')
        self.assertEqual(native.read_publication(f['manager'],publication.pk)['by_bu'],{'BU-A':'250.00'})
        self.assertEqual(PayrollRun.objects.filter(pk__in=[r.pk for r in old]).count(),3)

    def test_http_recovery_prepares_working_rows_and_decision_screen_refuses_the_command(self):
        f=self.f;self.client.force_login(f['preparer'])
        recovery=reverse('factory_invoice_recovery',args=[f['work'].pk])
        self.assertContains(self.client.get(recovery),'Prepare working combination')
        for stage,label in [('combine','Continue draft staff matching'),('match','Prepare draft staff-cost totals'),('aggregate',None)]:
            f['work'].refresh_from_db()
            data={'action':'working','working_stage':stage,'revision':f['work'].revision,'case_revision':rev(f['case'])}
            self.assertContains(self.client.post(reverse('factory_invoice_decision',args=[f['work'].pk]),data),
                                'Choose an available action on this page.')
            self.assertEqual(self.client.post(recovery,data).status_code,302)
            page=self.client.get(recovery)
            if label:self.assertContains(page,label)
        self.assertContains(page,'1 without a row finding');self.assertContains(page,'1 need review')
        self.assertContains(page,'Pay amount needs review');self.assertNotContains(page,'Publish exact reviewed aggregate')
        held=self.client.get(recovery,{'working_status':'held'})
        self.assertEqual([r['employee'] for r in held.context['working']['page']],['E002'])
        self.assertFalse(PayrollReview.objects.exists());self.assertFalse(PayrollPublication.objects.exists())

    def test_an_unnominated_reader_cannot_continue_partial_work(self):
        f=self.f;prepare(f,'combine')
        # Copying action grants cannot nominate another payroll or HR reader.
        other=get_user_model().objects.create_user('partial-matcher-without-receipt')
        for action in Grant.objects.filter(user=f['preparer'],case=f['case'],active=True).values_list('action',flat=True):
            Grant.objects.create(case=f['case'],user=other,action=action)
        # No HR nomination is invented for an actor; the native source boundary
        # must refuse before any matching output is created.
        f['work'].refresh_from_db()
        with self.assertRaises((ValidationError,PermissionDenied)):
            domain.human_action(other,f['work'].pk,f['work'].revision,rev(f['case']),'working',{'stage':'match'})
        self.assertFalse(PayrollRun.objects.filter(kind='match').exists())

    def test_typed_forgery_stale_version_and_original_intake_revocation_hold_before_output(self):
        f=self.f;work=f['work']
        for value in [{'stage':'publish'},{'stage':'combine','authority':'approve'}]:
            with self.assertRaises(ValidationError):domain.human_action(f['preparer'],work.pk,work.revision,rev(f['case']),'working',value)
        with self.assertRaises(ValidationError):domain.human_action(f['preparer'],work.pk,work.revision-1,rev(f['case']),'working',{'stage':'combine'})
        with self.assertRaises(ValidationError):domain.human_action(f['preparer'],work.pk,work.revision,rev(f['case'])-1,'working',{'stage':'combine'})
        Grant.objects.filter(user=f['preparer'],case=f['case'],action='evidence.add').update(active=False)
        with self.assertRaises(PermissionDenied):prepare(f,'combine')
        self.assertFalse(PayrollRun.objects.exists())

    def test_report_recipient_cannot_prepare_or_read_private_working_rows(self):
        f=self.f;row=prepare(f,'combine');f['work'].refresh_from_db()
        with self.assertRaises(PermissionDenied):domain.human_action(f['manager'],f['work'].pk,f['work'].revision,
            rev(f['case']),'working',{'stage':'match'})
        self.client.force_login(f['manager'])
        response=self.client.get(reverse('payroll_inspect',args=[f['case'].pk,'run',row.pk]))
        self.assertEqual(response.status_code,403);self.assertNotContains(response,'E001',status_code=403)

    def test_private_matching_page_uses_exact_current_working_rows(self):
        f=self.f;prepare(f,'combine');matched=prepare(f,'match');self.client.force_login(f['preparer'])
        page=self.client.get(reverse('design_payroll_matching',args=[f['case'].pk]),{'worksheet':matched.pk,'working_status':'ready'})
        self.assertEqual([row['employee'] for row in page.context['working']['page']],['E001'])
        self.assertContains(page,'BU-A');self.assertContains(page,'No row finding')
        self.assertContains(page,'Currency: TEST');self.assertContains(page,'Period: 2026-09')
        Grant.objects.filter(user=f['preparer'],case=f['case'],action='payroll.private.read').update(active=False)
        page=self.client.get(reverse('design_payroll_matching',args=[f['case'].pk]),{'worksheet':matched.pk})
        self.assertIsNone(page.context['working']);self.assertNotContains(page,'E001')


class PayrollWorkingCompleteInputTests(TestCase):
    def test_preview_fixture_creates_only_isolated_source_facts_and_is_idempotent(self):
        get_user_model().objects.create_user('psl-agent-trial')
        output=StringIO()
        with patch.dict('os.environ',{'PSL_PAYROLL_WORKING_FIXTURE':'1'}),redirect_stdout(output):
            first=runpy.run_path('tests/railway_payroll_working_seed.py')
            second=first['prepare']()
            third=first['prepare']()
        self.assertTrue(second['already_prepared'])
        self.assertEqual(second,third)
        self.assertFalse(PayrollRun.objects.exists());self.assertFalse(PayrollReview.objects.exists())
        self.assertFalse(PayrollPublication.objects.exists())
        self.assertIn('synthetic_factory_v1',output.getvalue())

    def test_complete_inputs_keep_the_ordinary_review_sequence(self):
        f=configured(held=False)
        with self.assertRaisesMessage(ValidationError,'ordinary reviewed payroll flow'):prepare(f,'combine')
        self.assertFalse(PayrollRun.objects.exists());self.assertFalse(PayrollReview.objects.exists())

    def test_missing_matcher_receipt_holds_the_partial_draft_action(self):
        f=configured(hr=False);prepare(f,'combine')
        with self.assertRaisesMessage(ValidationError,'Confirm receipt'):prepare(f,'match')
        self.assertFalse(PayrollRun.objects.filter(kind='match').exists())

    def test_native_private_inspection_pages_rows_without_rendering_hidden_history_rows(self):
        f=configured(held=False)
        source=[{'row_ref':f'A{n:03}','employee_id':f'WORKER{n:03}','component':'BASIC','amount':'1'} for n in range(1,53)]
        f['inputs'][0]=capture(f,0,'large-private-source',rows=source,control_total='52')
        row=native.combine(f['preparer'],f['case'].pk,f['request'].pk,[r.pk for r in f['inputs']],'private-large-sheet',rev(f['case']))
        self.client.force_login(f['preparer']);url=reverse('payroll_inspect',args=[f['case'].pk,'run',row.pk])
        page=self.client.get(url)
        self.assertEqual(len(page.context['working']['page']),25);self.assertNotContains(page,'WORKER052')
        self.assertContains(page,'Next rows');last=self.client.get(url,{'working_page':3})
        self.assertEqual(len(last.context['working']['page']),3);self.assertContains(last,'WORKER052')
        self.assertEqual(self.client.get(url,{'working_status':'forged'}).status_code,400)
        self.assertEqual(connection.vendor,'postgresql')


class PayrollWorkingConcurrencyTests(TransactionTestCase):
    def test_two_connections_commit_one_canonical_working_draft(self):
        f=configured();work=f['work'];case_version=rev(f['case']);barrier=Barrier(2)
        def run(number):
            close_old_connections()
            try:
                actor=get_user_model().objects.get(pk=f['preparer'].pk);barrier.wait(timeout=10)
                domain.human_action(actor,work.pk,work.revision,case_version,'working',{'stage':'combine'})
                return 'prepared'
            except (ValidationError,PermissionDenied):return 'held'
            finally:close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:outcomes=list(pool.map(run,[1,2]))
        self.assertCountEqual(outcomes,['prepared','held'])
        self.assertEqual(PayrollRun.objects.count(),1);self.assertFalse(PayrollReview.objects.exists())

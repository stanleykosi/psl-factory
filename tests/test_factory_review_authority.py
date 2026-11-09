"""Recorded native Finance authority must stay current through the human decision."""
from copy import deepcopy
from pathlib import Path
import tempfile
from django.test import TestCase,TransactionTestCase,Client
from django.db import close_old_connections,connection,transaction
from concurrent.futures import ThreadPoolExecutor
from threading import Event
import time
from django.urls import reverse
from django.core.exceptions import ValidationError,PermissionDenied
from django.utils import timezone
from apps.policy.services import active_component,reference_values
from apps.workflows import factory
from apps.workflows.models import HumanTask,TaskEvent,FactoryAttempt
from apps.finance import invoices,invoice_delivery
from apps.finance.models import Invoice,InvoiceReview,InvoiceIssue,InvoiceDelivery,InvoiceJob
from apps.identity.models import Grant
from adapters.factory_invoices import MockFactoryInvoiceAdapter
from apps.agents.factory_catalogue import SyntheticFactoryCoordinator
from tests.factory_helpers import fixture,approve
from tests.billing_helpers import policy
from tests.helpers import activate,rev


def change_rule(f,relevant=True):
    config=active_component('D05.decision_action_matrix',f['case'])
    value=deepcopy(reference_values(config)[0])
    if relevant:
        row=next(r for r in value['finance'] if r['purpose']=='invoice' and r['role']=='Finance')
        row['actions']=['approve']
    else:value['rules']=[{'role':'PM','actions':['return']}]
    return policy(f['actor'],f['case'],'D05.decision_action_matrix',value)


class FactoryReviewAuthorityTests(TransactionTestCase):
    def restored_rule(self,claimed=False,*,identity=False):
        f=fixture();w=f['work'];factory.run_until_wait(w.pk)
        if identity:
            from tests.obligation_helpers import factory_identified
            factory_identified(f)
        initial=deepcopy(reference_values(active_component('D05.decision_action_matrix',f['case']))[0])
        review=approve(f);change_rule(f);factory.run_until_wait(w.pk)
        obsolete=HumanTask.objects.get(kind='factory_review',status='open')
        if claimed:obsolete=factory.claim_task(f['actor'],obsolete.pk,obsolete.revision)
        original=deepcopy(obsolete.context)
        original_revision=obsolete.revision;original_claim=obsolete.claimed_by_id
        policy(f['actor'],f['case'],'D05.decision_action_matrix',initial)
        w.refresh_from_db();self.assertEqual(invoices.reviewed(w.invoice).pk,review.pk)
        with tempfile.TemporaryDirectory() as directory:
            factory.run_until_wait(w.pk,adapter=MockFactoryInvoiceAdapter(directory))
            self.assertEqual(len(list(Path(directory).glob('*.json'))),2)
        w.refresh_from_db();obsolete.refresh_from_db()
        self.assertEqual(w.status,'verified',w.finding)
        self.assertEqual(Invoice.objects.count(),1);self.assertEqual(InvoiceReview.objects.count(),1)
        self.assertEqual(InvoiceIssue.objects.count(),1);self.assertEqual(InvoiceDelivery.objects.count(),1)
        self.assertEqual(w.budget_limit,20000);self.assertEqual(obsolete.context,original)
        self.assertEqual(obsolete.status,'returned','Verified output must retire the obsolete coordination wait without another approval')
        self.assertFalse(HumanTask.objects.filter(kind='factory_review',status='open').exists())
        self.assertEqual(obsolete.revision,original_revision+1);self.assertEqual(obsolete.claimed_by_id,original_claim)
        audit=TaskEvent.objects.get(task=obsolete,action='factory.packet_superseded')
        self.assertEqual(audit.data['reason'],'verified_output');self.assertEqual(audit.data['invoice'],w.invoice_id)
        self.assertEqual(audit.data['issue_receipt'],InvoiceIssue.objects.get().pk)
        self.assertEqual(audit.data['delivery_receipt'],InvoiceDelivery.objects.get().pk)
        attempt=FactoryAttempt.objects.get(activity__work=w,activity__kind='ACT13',phase='observed')
        self.assertEqual(attempt.result['retired_review_tasks'],[obsolete.pk])
        spent=w.budget_used;self.assertFalse(factory.run_once(w.pk));w.refresh_from_db()
        self.assertEqual(w.budget_used,spent);self.assertEqual(TaskEvent.objects.filter(task=obsolete,action='factory.packet_superseded').count(),1)
        response=self.page(f);self.assertEqual(response.context['row']['state'],'Verified')
        self.assertNotContains(response,'Update Finance review');self.assertNotContains(response,'Claim task')
        return f

    def test_restored_valid_rule_closes_obsolete_wait_after_verified_receipts(self):
        self.restored_rule(identity=True)

    def test_restored_valid_rule_preserves_claim_history_when_retiring_obsolete_wait(self):
        self.restored_rule(claimed=True,identity=True)

    def restored_wait(self,**profile_values):
        f=fixture(**profile_values);w=f['work'];factory.run_until_wait(w.pk)
        initial=deepcopy(reference_values(active_component('D05.decision_action_matrix',f['case']))[0])
        approve(f);change_rule(f);factory.run_until_wait(w.pk)
        task=HumanTask.objects.get(kind='factory_review',status='open')
        policy(f['actor'],f['case'],'D05.decision_action_matrix',initial)
        return f,task

    def test_restored_valid_review_points_to_agent_continuation_not_another_decision(self):
        f,task=self.restored_wait();original=deepcopy(task.context);response=self.page(f);row=response.context['row']
        self.assertEqual(row['state'],'Finance approval available');self.assertTrue(row['review_ready'])
        self.assertFalse(row['review_needs_update']);self.assertEqual(row['owner'],f['actor'].username)
        self.assertTrue(row['needs_me']);self.assertContains(response,'<button>Continue approved invoice work</button>')
        self.assertNotContains(response,'Approve exact packet');self.assertNotContains(response,'Claim task')
        for queue in ['decisions','exceptions']:
            self.assertEqual(self.client.get(reverse('home'),{'queue':queue}).context['rows'],[])
        rows=self.client.get(reverse('home'),{'queue':'needs_me'}).context['rows']
        self.assertEqual([r['work'].pk for r in rows],[f['work'].pk])
        task.refresh_from_db();self.assertEqual(task.status,'open');self.assertEqual(task.context,original)
        self.assertEqual(InvoiceReview.objects.count(),1);self.assertFalse(InvoiceIssue.objects.exists())

    def test_read_only_account_can_inspect_restored_approval_without_execution_control(self):
        f,task=self.restored_wait();Grant.objects.filter(case=f['case'],user=f['actor'],action='factory.execute').update(active=False)
        response=self.page(f);row=response.context['row'];self.assertTrue(row['review_ready'])
        self.assertFalse(row['needs_me']);self.assertFalse(row['can_advance'])
        self.assertContains(response,'Inspect the current approval; execution is not permitted for this account')
        self.assertNotContains(response,'<button>Continue approved invoice work</button>')
        self.assertEqual(InvoiceReview.objects.count(),1);task.refresh_from_db();self.assertEqual(task.status,'open')

    def test_restored_approval_does_not_override_current_original_pending_job(self):
        f,task=self.restored_wait();w=f['work'];w.refresh_from_db()
        job=invoices.reserve(f['actor'],f['case'].pk,w.invoice_id,'issue','Finance',rev(f['case']),factory_work_id=w.pk)
        response=self.page(f);self.assertFalse(response.context['row']['review_ready']);job.refresh_from_db()
        self.assertEqual(job.status,'pending');self.assertEqual(job.attempts,0);self.assertFalse(InvoiceIssue.objects.exists())

    def test_restored_approval_keeps_unknown_executor_unassigned_without_inventing_an_owner(self):
        f,task=self.restored_wait(executor_id=None);response=self.page(f)
        self.assertTrue(response.context['row']['review_ready']);self.assertEqual(response.context['row']['owner'],'Unassigned')
        rows=self.client.get(reverse('home'),{'queue':'unassigned'}).context['rows']
        self.assertEqual([r['work'].pk for r in rows],[f['work'].pk])
        self.assertFalse(InvoiceIssue.objects.exists());task.refresh_from_db();self.assertEqual(task.status,'open')

    def page(self,f):
        self.client.force_login(f['actor'])
        return self.client.get(reverse('factory_detail',args=[f['work'].pk]))

    def changed_wait(self):
        f=fixture();factory.run_until_wait(f['work'].pk)
        task=HumanTask.objects.get(kind='factory_review');factory.claim_task(f['actor'],task.pk,task.revision)
        change_rule(f);return f

    def test_unrelated_update_keeps_current_review_in_decisions_not_exceptions(self):
        f=fixture();factory.run_until_wait(f['work'].pk);change_rule(f,relevant=False)
        response=self.page(f);self.assertEqual(response.context['row']['state'],'Awaiting Finance decision')
        self.assertFalse(response.context['row']['review_needs_update']);self.assertNotContains(response,'Update Finance review')
        self.assertEqual(self.client.get(reverse('home'),{'queue':'exceptions'}).context['rows'],[])
        rows=self.client.get(reverse('home'),{'queue':'decisions'}).context['rows']
        self.assertEqual([row['work'].pk for row in rows],[f['work'].pk])

    def test_account_without_execution_sees_update_reason_but_no_update_control(self):
        f=self.changed_wait();Grant.objects.filter(case=f['case'],user=f['actor'],action='factory.execute').update(active=False)
        response=self.page(f);row=response.context['row']
        self.assertEqual(row['state'],'Review needs updating');self.assertFalse(row['can_advance']);self.assertFalse(row['needs_me'])
        self.assertContains(response,'routing cannot be updated by this account');self.assertNotContains(response,'<button>Update Finance review</button>')
        self.assertFalse(InvoiceReview.objects.exists())

    def test_active_native_work_lease_precedes_stale_review_message(self):
        f=self.changed_wait();self.assertIsNotNone(factory.claim(f['work'].pk))
        response=self.page(f);row=response.context['row'];f['work'].refresh_from_db()
        self.assertGreater(f['work'].lease_until,timezone.now());self.assertEqual(row['state'],'Processing')
        self.assertFalse(row['review_needs_update']);self.assertFalse(row['can_advance'])
        self.assertEqual(row['next_action'],'Wait for the current worker observation');self.assertFalse(InvoiceReview.objects.exists())

    def reserved_outside_console(self,*,identity=False):
        f=fixture();w=f['work'];factory.run_until_wait(w.pk);w.refresh_from_db()
        if identity:
            from tests.obligation_helpers import factory_identified
            factory_identified(f)
        invoices.review(f['actor'],f['case'].pk,w.invoice_id,'Finance','approve',f['proof'].pk,'Synthetic native Finance review outside coordinator',rev(f['case']))
        job=invoices.reserve(f['actor'],f['case'].pk,w.invoice_id,'issue','Finance',rev(f['case']),factory_work_id=w.pk)
        return f,job

    def test_pending_original_reservation_precedes_review_update_and_get_does_not_dispatch(self):
        f,job=self.reserved_outside_console();change_rule(f)
        response=self.page(f);self.assertFalse(response.context['row']['review_needs_update'])
        self.assertNotContains(response,'Update Finance review');job.refresh_from_db()
        self.assertEqual(job.status,'pending');self.assertEqual(job.attempts,0);self.assertFalse(InvoiceIssue.objects.exists())

    def test_uncertain_original_effect_precedes_review_message_and_stays_in_exceptions(self):
        f,job=self.reserved_outside_console(identity=True)
        with tempfile.TemporaryDirectory() as directory:
            invoice_delivery.run_once(MockFactoryInvoiceAdapter(directory,lose_response=True),job_id=job.pk)
            change_rule(f);response=self.page(f);row=response.context['row']
            self.assertEqual(row['state'],'Effect uncertain');self.assertTrue(row['can_reconcile']);self.assertFalse(row['review_needs_update'])
            self.assertContains(response,'Reconcile original operation');self.assertNotContains(response,'Update Finance review')
            rows=self.client.get(reverse('home'),{'queue':'exceptions'}).context['rows']
            self.assertEqual([item['work'].pk for item in rows],[f['work'].pk])
        job.refresh_from_db();self.assertEqual(job.status,'unknown');self.assertFalse(InvoiceIssue.objects.exists())

    def test_actual_cancellation_keeps_stopped_history_above_changed_review_rules(self):
        f=self.changed_wait();w=f['work'];w.refresh_from_db();spent=w.budget_used
        factory.manage(f['actor'],w.pk,w.revision,'cancel');factory.run_once(w.pk)
        response=self.page(f);row=response.context['row'];w.refresh_from_db()
        self.assertEqual(row['state'],'Cancelled');self.assertFalse(row['review_needs_update']);self.assertEqual(row['owner'],'No action required')
        self.assertNotContains(response,'Update Finance review');self.assertEqual(w.budget_used,spent);self.assertFalse(InvoiceReview.objects.exists())

    def test_verified_receipts_remain_history_after_later_review_rule_change(self):
        from tests.obligation_helpers import factory_approve_identified as approve
        f=fixture();w=f['work'];factory.run_until_wait(w.pk);approve(f)
        with tempfile.TemporaryDirectory() as directory:factory.run_until_wait(w.pk,adapter=MockFactoryInvoiceAdapter(directory))
        change_rule(f);response=self.page(f);row=response.context['row']
        self.assertEqual(row['state'],'Verified');self.assertFalse(row['review_needs_update']);self.assertEqual(row['owner'],'No action required')
        self.assertNotContains(response,'Update Finance review');self.assertEqual(InvoiceIssue.objects.count(),1);self.assertEqual(InvoiceDelivery.objects.count(),1)

    def test_stale_review_has_clear_primary_state_action_owner_and_queue(self):
        f=fixture();w=f['work'];factory.run_until_wait(w.pk)
        task=HumanTask.objects.get(kind='factory_review');task=factory.claim_task(f['actor'],task.pk,task.revision)
        original=deepcopy(task.context);change_rule(f)
        client=Client();client.force_login(f['actor']);response=client.get(reverse('factory_detail',args=[w.pk]))
        self.assertTrue(b'Review needs updating' in response.content,'Current review-rule mismatch needs a visible primary explanation')
        self.assertEqual(response.context['row']['owner'],'Unassigned')
        self.assertContains(response,'Update Finance review')
        self.assertNotContains(response,'name="verdict" value="approve"')
        for queue in ['exceptions','needs_me','unassigned']:
            rows=client.get(reverse('home'),{'queue':queue,'q':'FACTORY'}).context['rows']
            self.assertEqual([row['work'].pk for row in rows],[w.pk],queue)
        self.assertEqual(client.get(reverse('home'),{'queue':'decisions','q':'FACTORY'}).context['rows'],[])
        task.refresh_from_db();self.assertEqual(task.context,original);self.assertEqual(task.status,'open')
        self.assertEqual(task.claimed_by_id,f['actor'].pk);self.assertFalse(InvoiceReview.objects.exists())

    def test_fresh_review_shows_only_verdicts_allowed_by_current_finance_rule(self):
        f=fixture();w=f['work'];change_rule(f);factory.run_until_wait(w.pk)
        task=HumanTask.objects.get(kind='factory_review');task=factory.claim_task(f['actor'],task.pk,task.revision)
        client=Client();client.force_login(f['actor']);response=client.get(reverse('factory_detail',args=[w.pk]))
        self.assertContains(response,'name="verdict" value="approve"')
        self.assertNotContains(response,'name="verdict" value="return"')
        self.assertNotContains(response,'name="verdict" value="reject"')
        with self.assertRaises(PermissionDenied):
            factory.decide(f['actor'],task.pk,task.revision,'return',f['proof'].pk,'Unconfigured return cannot enter the native ledger')
        self.assertFalse(InvoiceReview.objects.exists())

    def test_changed_relevant_rule_refuses_claim_of_previously_routed_task(self):
        f=fixture();w=f['work'];factory.run_until_wait(w.pk)
        task=HumanTask.objects.get(kind='factory_review');original=deepcopy(task.context)
        change_rule(f)
        with self.assertRaisesMessage(ValidationError,'STALE_AUTHORITY'):
            factory.claim_task(f['actor'],task.pk,task.revision)
        task.refresh_from_db();self.assertIsNone(task.claimed_by_id);self.assertEqual(task.context,original)
        self.assertFalse(InvoiceReview.objects.exists());self.assertFalse(InvoiceIssue.objects.exists())

    def test_changed_rule_after_claim_disables_ui_and_requires_fresh_routing(self):
        from tests.obligation_helpers import factory_identified
        f=fixture();w=f['work'];factory.run_until_wait(w.pk);factory_identified(f)
        task=HumanTask.objects.get(kind='factory_review',status='open');task=factory.claim_task(f['actor'],task.pk,task.revision)
        original=deepcopy(task.context);w.refresh_from_db();spent=w.budget_used;change_rule(f)
        client=Client();client.force_login(f['actor']);response=client.get(reverse('factory_detail',args=[w.pk]))
        self.assertNotContains(response,'Approve exact packet')
        with self.assertRaisesMessage(ValidationError,'STALE_AUTHORITY'):
            factory.decide(f['actor'],task.pk,task.revision,'approve',f['proof'].pk,'Old rule must not approve')
        self.assertFalse(InvoiceReview.objects.exists())
        factory.run_until_wait(w.pk);task.refresh_from_db();w.refresh_from_db()
        self.assertEqual(task.status,'returned');self.assertEqual(task.context,original)
        replacement=HumanTask.objects.get(kind='factory_review',status='open')
        self.assertNotEqual(replacement.pk,task.pk);self.assertGreater(w.budget_used,spent);self.assertEqual(w.budget_limit,20000)
        approve(f)
        with tempfile.TemporaryDirectory() as directory:factory.run_until_wait(w.pk,adapter=MockFactoryInvoiceAdapter(directory))
        w.refresh_from_db();self.assertEqual(w.status,'verified',w.finding)
        self.assertEqual(InvoiceReview.objects.count(),1);self.assertEqual(InvoiceIssue.objects.count(),1)

    def test_obsolete_native_approval_does_not_auto_complete_or_block_fresh_review(self):
        from tests.obligation_helpers import factory_identified
        f=fixture();w=f['work'];factory.run_until_wait(w.pk);factory_identified(f);first=approve(f)
        original=HumanTask.objects.get(kind='factory_review',status='completed');change_rule(f)
        factory.run_until_wait(w.pk);w.refresh_from_db();original.refresh_from_db()
        fresh=HumanTask.objects.get(kind='factory_review',status='open')
        self.assertNotEqual(fresh.pk,original.pk);self.assertEqual(original.status,'completed')
        self.assertEqual(InvoiceReview.objects.count(),1);self.assertFalse(InvoiceIssue.objects.exists())
        second=approve(f);self.assertNotEqual(first.pk,second.pk)
        with tempfile.TemporaryDirectory() as directory:factory.run_until_wait(w.pk,adapter=MockFactoryInvoiceAdapter(directory))
        w.refresh_from_db();self.assertEqual(w.status,'verified',w.finding);self.assertEqual(Invoice.objects.count(),1)

    def test_unrelated_decision_namespace_preserves_claim_and_native_approval(self):
        from tests.obligation_helpers import factory_identified
        f=fixture();w=f['work'];factory.run_until_wait(w.pk);factory_identified(f)
        task=HumanTask.objects.get(kind='factory_review',status='open');change_rule(f,relevant=False)
        factory.claim_task(f['actor'],task.pk,task.revision);review=approve(f)
        change_rule(f,relevant=False)
        with tempfile.TemporaryDirectory() as directory:factory.run_until_wait(w.pk,adapter=MockFactoryInvoiceAdapter(directory))
        w.refresh_from_db();self.assertEqual(w.status,'verified',w.finding)
        self.assertEqual(InvoiceReview.objects.count(),1);self.assertEqual(InvoiceReview.objects.get().pk,review.pk)
        self.assertEqual(InvoiceDelivery.objects.count(),1)

    def test_changed_role_configuration_requires_new_routing_without_editing_old_task(self):
        f=fixture();w=f['work'];factory.run_until_wait(w.pk)
        task=HumanTask.objects.get(kind='factory_review');original=deepcopy(task.context)
        config=active_component('D05.role_principal_assignments',f['case'])
        activate(f['actor'],f['case'],config.component,config.envelope['value'],f['evidence']['policy_decision'])
        with self.assertRaisesMessage(ValidationError,'STALE_AUTHORITY'):factory.claim_task(f['actor'],task.pk,task.revision)
        factory.run_until_wait(w.pk);task.refresh_from_db()
        self.assertEqual(task.status,'returned');self.assertEqual(task.context,original)
        self.assertEqual(HumanTask.objects.filter(kind='factory_review',status='open').count(),1)
        self.assertFalse(InvoiceReview.objects.exists())

    def test_original_receipt_is_observed_before_changed_rule_requires_new_delivery_review(self):
        from tests.obligation_helpers import factory_approve_identified as approve
        f=fixture();w=f['work'];factory.run_until_wait(w.pk);approve(f);w.refresh_from_db();invoice=w.invoice_id
        with tempfile.TemporaryDirectory() as directory:
            adapter=MockFactoryInvoiceAdapter(directory,lose_response=True)
            factory.run_once(w.pk,adapter=adapter);factory.run_once(w.pk,adapter=adapter)
            change_rule(f);factory.run_until_wait(w.pk,adapter=MockFactoryInvoiceAdapter(directory));w.refresh_from_db()
            self.assertEqual(w.invoice_id,invoice);self.assertEqual(InvoiceIssue.objects.count(),1)
            self.assertFalse(InvoiceDelivery.objects.exists());self.assertEqual(InvoiceReview.objects.count(),1)
            self.assertEqual(HumanTask.objects.filter(kind='factory_review',status='open').count(),1)
            approve(f);factory.run_until_wait(w.pk,adapter=MockFactoryInvoiceAdapter(directory))
        w.refresh_from_db();self.assertEqual(w.status,'verified',w.finding)
        self.assertEqual(Invoice.objects.count(),1);self.assertEqual(InvoiceIssue.objects.count(),1)
        self.assertEqual(InvoiceReview.objects.count(),2);self.assertEqual(InvoiceDelivery.objects.count(),1)

    def test_legacy_task_without_recorded_authority_is_held_and_replaced_without_backfill(self):
        f=fixture();w=f['work']
        for _ in range(4):factory.run_once(w.pk)
        w.refresh_from_db();self.assertIsNotNone(w.invoice_id)
        legacy=factory.task(w,'factory_review',{'work':w.pk,'packet':factory.invoices.review_packet(w.invoice)})
        original=deepcopy(legacy.context)
        with self.assertRaisesMessage(ValidationError,'STALE_AUTHORITY'):factory.claim_task(f['actor'],legacy.pk,legacy.revision)
        factory.run_until_wait(w.pk);legacy.refresh_from_db();self.assertEqual(legacy.status,'returned')
        self.assertEqual(legacy.context,original);self.assertNotIn('routing_at_creation',legacy.context)
        self.assertEqual(HumanTask.objects.filter(kind='factory_review',status='open').count(),1)
        self.assertFalse(InvoiceReview.objects.exists())

    def test_malformed_historical_authority_is_held_without_breaking_read_view(self):
        f=fixture();w=f['work']
        for _ in range(4):factory.run_once(w.pk)
        w.refresh_from_db();packet=factory.invoices.review_packet(w.invoice)
        for authority in [None,['source text cannot grant authority'],{'unexpected':'shape'}]:
            task=factory.task(w,'factory_review',{'work':w.pk,'packet':packet,
                'routing_at_creation':{'authority':authority,'eligible_principals':[f['actor'].pk]}})
            with self.assertRaisesMessage(ValidationError,'STALE_AUTHORITY'):factory.claim_task(f['actor'],task.pk,task.revision)
        client=Client();client.force_login(f['actor']);response=client.get(reverse('factory_detail',args=[w.pk]))
        self.assertEqual(response.status_code,200);self.assertNotContains(response,'Approve exact packet')
        factory.run_until_wait(w.pk)
        self.assertEqual(HumanTask.objects.filter(kind='factory_review',status='open').count(),1)
        self.assertEqual(HumanTask.objects.filter(kind='factory_review',status='returned').count(),3)
        self.assertFalse(InvoiceReview.objects.exists())


class FactoryReviewRetirementConcurrencyTests(TransactionTestCase):
    def test_verification_serializes_with_actual_claim_release_without_losing_revision(self):
        from tests.obligation_helpers import factory_approve_identified as approve
        f=fixture();w=f['work'];factory.run_until_wait(w.pk)
        initial=deepcopy(reference_values(active_component('D05.decision_action_matrix',f['case']))[0])
        approve(f);change_rule(f);factory.run_until_wait(w.pk)
        task=HumanTask.objects.get(kind='factory_review',status='open')
        task=factory.claim_task(f['actor'],task.pk,task.revision);original=deepcopy(task.context)
        policy(f['actor'],f['case'],'D05.decision_action_matrix',initial)
        with tempfile.TemporaryDirectory() as directory:
            adapter=MockFactoryInvoiceAdapter(directory)
            for _ in range(10):
                factory.run_once(w.pk,adapter=adapter)
                if InvoiceDelivery.objects.filter(invoice_id=w.invoice_id).exists():break
                w.refresh_from_db()
            self.assertEqual(InvoiceDelivery.objects.count(),1)
            task.refresh_from_db();self.assertEqual(task.status,'open');revision=task.revision
            release_locked=Event();finish_release=Event();verification_started=Event();pids={}
            def release():
                close_old_connections()
                try:
                    with transaction.atomic():
                        with connection.cursor() as cur:cur.execute('SELECT pg_backend_pid()');pids['release']=cur.fetchone()[0]
                        factory.release_task_claim(f['actor'],task.pk,revision,'Synthetic handoff before verification')
                        release_locked.set()
                        if not finish_release.wait(15):raise AssertionError('Release coordination timed out')
                finally:close_old_connections()
            class ObservedCoordinator(SyntheticFactoryCoordinator):
                def choose(self,context):
                    answer=super().choose(context)
                    if answer['activity']!='ACT13':raise AssertionError(answer)
                    with connection.cursor() as cur:cur.execute('SELECT pg_backend_pid()');pids['verify']=cur.fetchone()[0]
                    verification_started.set();return answer
            def verify():
                close_old_connections()
                try:return factory.run_once(w.pk,provider=ObservedCoordinator(),adapter=adapter)
                finally:close_old_connections()
            with ThreadPoolExecutor(max_workers=2) as pool:
                first=pool.submit(release)
                try:
                    self.assertTrue(release_locked.wait(10));second=pool.submit(verify)
                    self.assertTrue(verification_started.wait(10));blocked=False;deadline=time.monotonic()+8
                    while time.monotonic()<deadline:
                        with connection.cursor() as cur:
                            cur.execute('SELECT pg_blocking_pids(%s)',[pids['verify']]);blocked=pids['release'] in cur.fetchone()[0]
                        if blocked:break
                        time.sleep(.02)
                    self.assertTrue(blocked,'PostgreSQL must serialize verification behind the actual task release')
                finally:finish_release.set()
                first.result(timeout=10);self.assertTrue(second.result(timeout=10))
        task.refresh_from_db();w.refresh_from_db()
        self.assertEqual(w.status,'verified');self.assertEqual(task.status,'returned')
        self.assertEqual(task.revision,revision+2);self.assertIsNone(task.claimed_by_id);self.assertEqual(task.context,original)
        self.assertEqual(TaskEvent.objects.filter(task=task,action='factory.claim_released').count(),1)
        self.assertEqual(TaskEvent.objects.filter(task=task,action='factory.packet_superseded').count(),1)
        self.assertEqual(InvoiceReview.objects.count(),1);self.assertEqual(InvoiceIssue.objects.count(),1);self.assertEqual(InvoiceDelivery.objects.count(),1)

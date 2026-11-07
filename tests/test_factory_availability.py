"""Synthetic configured absence uses actual native authority, decisions and receipts."""
from copy import deepcopy
import json,time
from pathlib import Path
from datetime import timedelta
from tempfile import TemporaryDirectory
from django.test import TestCase,TransactionTestCase,Client,override_settings
from django.urls import reverse
from django.utils import timezone
from django.core.exceptions import ValidationError,PermissionDenied
from apps.policy.operator_drafts import draft_operator_policy
from apps.policy.services import transition,reference_values,active_component,resolve
from apps.policy.models import Configuration
from apps.identity.models import Grant
from apps.workflows import factory
from apps.workflows.models import HumanTask
from apps.finance.models import InvoiceReview,InvoiceIssue,InvoiceDelivery
from adapters.factory_invoices import MockFactoryInvoiceAdapter
from tests.test_factory_delegation import configured_delegate

AVAILABILITY='OPS.factory_review_availability'

def configure_availability(f,delegate,*,principal_status='unavailable',delegate_status='available',mode='current_window_required',until=None):
    fixture=json.loads(Path('fixtures/factory-reviewer-availability.json').read_text());assert fixture['classification']=='synthetic_test_only'
    now=timezone.now();end=until or now+timedelta(seconds=fixture['window_seconds'])
    value={'purpose':fixture['purpose'],'records':[
        {'principal_id':person.pk,'status':status,'valid_from':(now-timedelta(minutes=1)).isoformat(),'valid_until':end.isoformat()}
        for person,status in [(f['actor'],principal_status),(delegate,delegate_status)]]}
    c=draft_operator_policy(f['actor'],f['case'].pk,AVAILABILITY,value,f['evidence']['policy_decision'].pk,now)
    transition(f['actor'],c.pk,'validated');transition(f['actor'],c.pk,'active')
    routing=deepcopy(reference_values(active_component('OPS.factory_finance_responsibility',f['case']))[0])
    routing.update(method=fixture['method'],availability_mode=mode)
    c=draft_operator_policy(f['actor'],f['case'].pk,'OPS.factory_finance_responsibility',routing,f['evidence']['policy_decision'].pk,now)
    transition(f['actor'],c.pk,'validated');transition(f['actor'],c.pk,'active')
    return value,c

def availability_successor(f,value):
    c=draft_operator_policy(f['actor'],f['case'].pk,AVAILABILITY,value,f['evidence']['policy_decision'].pk,timezone.now())
    transition(f['actor'],c.pk,'validated');transition(f['actor'],c.pk,'active');return c

def approve_delegate(f,b):
    factory.run_until_wait(f['work'].pk);task=HumanTask.objects.get(kind='factory_review',status='open')
    task=factory.claim_task(b,task.pk,task.revision)
    return factory.decide(b,task.pk,task.revision,'approve',f['proof'].pk,'Synthetic current availability and exact invoice packet')

class FactoryAvailabilityTests(TransactionTestCase):
    def test_required_but_missing_availability_source_holds_only_review_and_native_bypass(self):
        from apps.finance import invoices
        from tests.helpers import rev
        f,b,_,_=configured_delegate();a=f['actor'];case=f['case'];w=f['work']
        routing=deepcopy(reference_values(active_component('OPS.factory_finance_responsibility',case))[0])
        routing.update(method='native_finance_single_review/v3',availability_mode='current_window_required')
        c=draft_operator_policy(a,case.pk,'OPS.factory_finance_responsibility',routing,f['evidence']['policy_decision'].pk,timezone.now())
        transition(a,c.pk,'validated');transition(a,c.pk,'active')
        self.assertEqual(resolve(AVAILABILITY,case).status,'MISSING')
        factory.run_until_wait(w.pk);w.refresh_from_db();self.assertIsNotNone(w.invoice_id);self.assertEqual(w.status,'owner_needed')
        with self.assertRaisesMessage(ValidationError,'availability_needed'):
            invoices.review(a,case.pk,w.invoice_id,'Finance','approve',f['proof'].pk,'Must not bypass missing availability',rev(case))
        self.assertFalse(InvoiceReview.objects.exists());self.assertFalse(InvoiceIssue.objects.exists())

    def test_adjacent_half_open_windows_do_not_overlap_or_infer_availability_from_a_gap(self):
        from apps.workflows.factory_routing import evaluate
        f,b,_,_=configured_delegate();value,_=configure_availability(f,b)
        boundary=timezone.now()-timedelta(seconds=1);old=deepcopy(value['records'][1]);old['valid_until']=boundary.isoformat();old['status']='unavailable'
        value['records'][1]['valid_from']=boundary.isoformat();value['records'].append(old)
        availability_successor(f,value);factory.run_until_wait(f['work'].pk);f['work'].refresh_from_db()
        self.assertEqual(evaluate(f['work'])['eligible_principals'],[b.pk]);self.assertFalse(InvoiceReview.objects.exists())

    def test_absent_principal_uses_only_available_qualified_delegate_through_native_receipts(self):
        f,b,delegation,record=configured_delegate(identity=True);configure_availability(f,b);w=f['work']
        factory.run_until_wait(w.pk)
        task=HumanTask.objects.get(kind='factory_review',status='open')
        self.assertEqual(task.context['routing_at_creation']['eligible_principals'],[b.pk])
        with self.assertRaises(PermissionDenied):factory.claim_task(f['actor'],task.pk,task.revision)
        task=factory.claim_task(b,task.pk,task.revision)
        factory.decide(b,task.pk,task.revision,'approve',f['proof'].pk,'Synthetic available delegate; principal explicitly unavailable')
        with TemporaryDirectory() as directory:factory.run_until_wait(w.pk,adapter=MockFactoryInvoiceAdapter(directory))
        w.refresh_from_db();self.assertEqual(w.status,'verified',w.finding)
        review=InvoiceReview.objects.get();self.assertEqual(review.actor_id,b.pk)
        self.assertIn('factory_reviewer_availability',review.authority)
        self.assertEqual(InvoiceIssue.objects.count(),1);self.assertEqual(InvoiceDelivery.objects.count(),1)

    def test_unknown_windows_or_mode_hold_review_after_useful_preparation(self):
        f,b,_,_=configured_delegate();value,_=configure_availability(f,b,delegate_status=None);w=f['work']
        factory.run_until_wait(w.pk);w.refresh_from_db()
        self.assertIsNotNone(w.invoice_id);self.assertEqual(w.status,'owner_needed');self.assertFalse(InvoiceReview.objects.exists())
        from apps.workflows.factory_routing import evaluate
        self.assertIn('availability_needs_configuration',{r['code'] for r in evaluate(w)['reviewer_findings']})
        configure_availability(f,b,mode=None);factory.run_until_wait(w.pk);w.refresh_from_db()
        self.assertIn('reviewer_availability_mode',evaluate(w)['missing']);self.assertFalse(InvoiceIssue.objects.exists())

    def test_available_record_does_not_appoint_a_reviewer_or_replace_a_revoked_delegation(self):
        f,b,delegation,_=configured_delegate();configure_availability(f,b)
        transition(f['actor'],delegation.pk,'revoked');factory.run_until_wait(f['work'].pk);f['work'].refresh_from_db()
        self.assertEqual(f['work'].status,'owner_needed');self.assertFalse(InvoiceReview.objects.exists());self.assertFalse(InvoiceIssue.objects.exists())

    def test_invalid_overlap_timezone_types_and_foreign_people_cannot_replace_active_windows(self):
        from tests.helpers import setup_case
        f,b,_,_=configured_delegate();value,_=configure_availability(f,b);original=active_component(AVAILABILITY,f['case']).pk
        stranger,_=setup_case(username='availability-foreign-person');bad=[]
        for changes in [{'principal_id':True},{'principal_id':float(b.pk)},{'principal_id':stranger.pk},
            {'valid_from':'2026-11-03T10:00:00'},{'valid_until':value['records'][0]['valid_from']},{'status':'automatically_approved'}]:
            v=deepcopy(value);v['records'][1].update(changes);bad.append(v)
        duplicate=deepcopy(value);duplicate['records'].append(deepcopy(value['records'][1]));bad.append(duplicate)
        for v in bad:
            with self.subTest(value=v):
                c=draft_operator_policy(f['actor'],f['case'].pk,AVAILABILITY,v,f['evidence']['policy_decision'].pk,timezone.now())
                with self.assertRaises(ValidationError):transition(f['actor'],c.pk,'validated')
                self.assertEqual(active_component(AVAILABILITY,f['case']).pk,original)

    def test_scoped_owner_form_preserves_other_windows_and_requires_activation(self):
        from apps.finance.billing import digest
        f,b,_,_=configured_delegate();value,_=configure_availability(f,b);a=f['actor'];case=f['case'];old=active_component(AVAILABILITY,case)
        client=Client();client.force_login(a);url=reverse('factory_responsibility',args=[case.pk])
        response=client.get(url);self.assertContains(response,'Reviewer availability');self.assertContains(response,'Confirmed available window required')
        form=response.context['reviewer_availability_form'];self.assertEqual(form.initial['source_configuration'],old.pk)
        r=value['records'][1];data={'principal':b.pk,'status':'unavailable','valid_from':r['valid_from'],'valid_until':r['valid_until'],
            'evidence':f['evidence']['policy_decision'].pk,'effective_from':timezone.now().isoformat(),'source_configuration':old.pk,'replacement':digest(r)}
        response=client.post(url,{'action':'availability_draft',**{'reviewer_availability-'+k:v for k,v in data.items()}})
        self.assertEqual(response.status_code,302)
        c=Configuration.objects.filter(case=case,component=AVAILABILITY).latest('pk')
        self.assertEqual(c.states.latest('pk').state,'draft');self.assertEqual(active_component(AVAILABILITY,case).pk,old.pk)
        new=reference_values(c)[0];self.assertEqual(new['records'][0],value['records'][0]);self.assertEqual(new['records'][1]['status'],'unavailable')
        for state in ['validated','active']:
            self.assertEqual(client.post(url,{'action':'availability_transition','configuration':c.pk,'state':state}).status_code,302)
        self.assertEqual(active_component(AVAILABILITY,case).pk,c.pk);self.assertFalse(InvoiceReview.objects.exists())

    def test_stale_sources_and_lost_private_source_access_cannot_copy_or_transition_windows(self):
        from apps.policy.reviewer_availability import draft_record
        from apps.finance.billing import digest
        f,b,_,_=configured_delegate();value,_=configure_availability(f,b);old=active_component(AVAILABILITY,f['case'])
        availability_successor(f,value)
        with self.assertRaisesMessage(ValidationError,'STALE_VERSION'):
            draft_record(f['actor'],f['case'].pk,value['records'][1],f['evidence']['policy_decision'].pk,timezone.now(),old.pk,digest(value['records'][1]))
        Grant.objects.filter(case=f['case'],user=f['actor'],action='policy.read').update(active=False)
        client=Client();client.force_login(f['actor']);url=reverse('factory_responsibility',args=[f['case'].pk]);response=client.get(url)
        self.assertEqual(response.status_code,200);self.assertFalse(response.context['reviewer_availability_form'].source_available)
        self.assertEqual(response.context['availability_versions'],[]);self.assertNotContains(response,'name="reviewer_availability-source_configuration"')
        self.assertEqual(client.post(url,{'action':'availability_transition','configuration':old.pk,'state':'revoked'}).status_code,403)

    def test_legacy_form_post_cannot_silently_remove_required_availability(self):
        f,b,_,_=configured_delegate();configure_availability(f,b);a=f['actor'];client=Client();client.force_login(a)
        data={k:a.pk for k in ['process_owner_id','activity_owner_id','policy_owner_id','governance_resolver_id']}
        response=client.post(reverse('factory_responsibility',args=[f['case'].pk]),dict(data,action='draft',authority_mode='direct_or_configured_delegate',evidence=f['evidence']['policy_decision'].pk))
        self.assertEqual(response.status_code,302)
        value=reference_values(Configuration.objects.filter(case=f['case'],component='OPS.factory_finance_responsibility').latest('pk'))[0]
        self.assertEqual(value['method'],'native_finance_single_review/v3');self.assertEqual(value['availability_mode'],'current_window_required')

    def test_each_historical_availability_and_delegation_version_requires_its_own_origin_access(self):
        from tests.helpers import setup_case
        from apps.core.services import add_evidence
        from apps.policy import scopes,role_assignments as nominations
        f,b,_,record=configured_delegate();value,_=configure_availability(f,b);a=f['actor'];case=f['case']
        owner,origin=setup_case(username='synthetic-availability-origin-owner')
        for person in [a,b]:Grant.objects.create(user=person,case=origin,action='case.read')
        Grant.objects.create(user=a,case=origin,action='policy.read')
        proof=add_evidence(owner,origin.pk,'policy_decision','Synthetic restricted organization records','synthetic:availability-origin')
        source=draft_operator_policy(owner,origin.pk,AVAILABILITY,value,proof.pk,timezone.now());transition(owner,source.pk,'validated')
        scope=scopes.create(owner,source.pk,'organization',origin.tenant,[])
        scopes.transition(owner,scope.pk,'validated');scopes.transition(owner,scope.pk,'active')
        private_availability=scopes.apply(a,scope.pk,case.pk,f['evidence']['policy_decision'].pk,[])
        transition(a,private_availability.pk,'validated');transition(a,private_availability.pk,'active')
        availability_successor(f,value)
        legacy={k:deepcopy(v) for k,v in record.items() if k!='decision_scope'}
        source=nominations.draft_delegations(owner,origin.pk,[legacy],proof.pk,timezone.now());transition(owner,source.pk,'validated')
        scope=scopes.create(owner,source.pk,'organization',origin.tenant,[])
        scopes.transition(owner,scope.pk,'validated');scopes.transition(owner,scope.pk,'active')
        private_delegation=scopes.apply(a,scope.pk,case.pk,f['evidence']['policy_decision'].pk,[])
        transition(a,private_delegation.pk,'validated');transition(a,private_delegation.pk,'active')
        current=nominations.draft_delegations(a,case.pk,[record],f['evidence']['policy_decision'].pk,timezone.now())
        transition(a,current.pk,'validated');transition(a,current.pk,'active')
        Grant.objects.filter(user=a,case=origin,action='policy.read').update(active=False)
        client=Client();client.force_login(a);url=reverse('factory_responsibility',args=[case.pk]);response=client.get(url)
        self.assertEqual(response.status_code,200);self.assertTrue(response.context['reviewer_availability_form'].source_available)
        self.assertNotIn(private_availability.pk,[c.pk for c in response.context['availability_versions']])
        self.assertTrue(response.context['invoice_delegation_form'].source_available)
        self.assertNotIn(private_delegation.pk,[c.pk for c in response.context['delegation_versions']])
        for config,action in [(private_availability,'availability_transition'),(private_delegation,'delegation_transition')]:
            self.assertEqual(client.post(url,{'action':action,'configuration':config.pk,'state':'revoked'}).status_code,403)

    def test_availability_change_after_claim_requires_current_routing_without_history_rewrite(self):
        f,b,_,_=configured_delegate();value,_=configure_availability(f,b);w=f['work'];factory.run_until_wait(w.pk)
        task=HumanTask.objects.get(kind='factory_review',status='open');task=factory.claim_task(b,task.pk,task.revision);original=deepcopy(task.context)
        value['records'][1]['status']='unavailable';availability_successor(f,value)
        with self.assertRaises((ValidationError,PermissionDenied)):factory.decide(b,task.pk,task.revision,'approve',f['proof'].pk,'Must not approve after absence change')
        client=Client();client.force_login(b);response=client.get(reverse('factory_detail',args=[w.pk]))
        self.assertNotContains(response,'Approve exact packet');self.assertFalse(InvoiceReview.objects.exists())
        factory.run_until_wait(w.pk);task.refresh_from_db();self.assertEqual(task.status,'returned');self.assertEqual(task.context,original)
        value['records'][1]['status']='available';availability_successor(f,value)
        # Existing governance waits need their accountable resolver's recheck;
        # activating a policy is not itself that human work decision.
        from apps.workflows.factory_routing import recheck
        governance=HumanTask.objects.get(kind='factory_governance',status='open')
        governance=factory.claim_task(f['actor'],governance.pk,governance.revision)
        recheck(f['actor'],governance.pk,governance.revision,'Synthetic corrected availability owner recheck')
        factory.run_until_wait(w.pk)
        self.assertEqual(HumanTask.objects.filter(kind='factory_review',status='open').count(),1)

    def test_absence_after_approval_holds_new_issuance_but_retains_native_history(self):
        from apps.finance import invoices
        f,b,_,_=configured_delegate();value,_=configure_availability(f,b);review=approve_delegate(f,b);w=f['work'];w.refresh_from_db()
        value['records'][1]['status']='unavailable';availability_successor(f,value)
        with self.assertRaises((ValidationError,PermissionDenied)):invoices.reviewed(w.invoice)
        factory.run_until_wait(w.pk);self.assertEqual(InvoiceReview.objects.get().pk,review.pk)
        self.assertFalse(InvoiceIssue.objects.exists());self.assertFalse(InvoiceDelivery.objects.exists())

    def test_original_receipt_reconciles_after_availability_revocation_without_new_delivery(self):
        from apps.finance.models import InvoiceJob
        f,b,_,_=configured_delegate(identity=True);configure_availability(f,b);approve_delegate(f,b);w=f['work']
        with TemporaryDirectory() as directory:
            adapter=MockFactoryInvoiceAdapter(directory,lose_response=True)
            for _ in range(8):
                factory.run_once(w.pk,adapter=adapter)
                if InvoiceJob.objects.filter(status='unknown').exists():break
            job=InvoiceJob.objects.get(status='unknown');self.assertEqual(len(list(Path(directory).glob('*.json'))),1)
            transition(f['actor'],active_component(AVAILABILITY,f['case']).pk,'revoked');w.refresh_from_db()
            with override_settings(FACTORY_ADAPTERS={str(f['case'].pk):MockFactoryInvoiceAdapter(directory)}):factory.reconcile(f['actor'],w.pk,w.revision)
            factory.run_until_wait(w.pk,adapter=MockFactoryInvoiceAdapter(directory));job.refresh_from_db()
            self.assertEqual(job.status,'confirmed');self.assertEqual(len(list(Path(directory).glob('*.json'))),1)
        self.assertEqual(InvoiceIssue.objects.count(),1);self.assertEqual(InvoiceDelivery.objects.count(),0)

    def test_real_availability_expiry_blocks_dispatch_without_backdating_or_clock_mocks(self):
        from apps.finance import invoices
        f,b,_,_=configured_delegate();deadline=timezone.now()+timedelta(seconds=120);configure_availability(f,b,until=deadline)
        review=approve_delegate(f,b);w=f['work'];w.refresh_from_db();self.assertEqual(invoices.reviewed(w.invoice).pk,review.pk)
        print(f'Actual availability expiry wait until {deadline.isoformat()}',flush=True)
        while timezone.now()<deadline:time.sleep(min(.2,max(.001,(deadline-timezone.now()).total_seconds())))
        with self.assertRaises((ValidationError,PermissionDenied)):invoices.reviewed(w.invoice)
        factory.run_until_wait(w.pk);self.assertEqual(InvoiceReview.objects.get().pk,review.pk)
        self.assertFalse(InvoiceIssue.objects.exists());self.assertFalse(InvoiceDelivery.objects.exists())

class FactoryAvailabilityConcurrencyTests(TransactionTestCase):
    def test_review_and_availability_withdrawal_serialize_before_dispatch(self):
        from concurrent.futures import ThreadPoolExecutor
        from django.db import close_old_connections
        f,b,_,_=configured_delegate();value,_=configure_availability(f,b);w=f['work'];factory.run_until_wait(w.pk)
        task=HumanTask.objects.get(kind='factory_review',status='open');task=factory.claim_task(b,task.pk,task.revision)
        value['records'][1]['status']='unavailable'
        c=draft_operator_policy(f['actor'],f['case'].pk,AVAILABILITY,value,f['evidence']['policy_decision'].pk,timezone.now());transition(f['actor'],c.pk,'validated')
        def decide():
            close_old_connections()
            try:factory.decide(b,task.pk,task.revision,'approve',f['proof'].pk,'Synthetic concurrent availability decision');return 'recorded'
            except (ValidationError,PermissionDenied):return 'stale'
            finally:close_old_connections()
        def withdraw():
            close_old_connections()
            try:transition(f['actor'],c.pk,'active')
            finally:close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:
            first=pool.submit(decide);second=pool.submit(withdraw);result=first.result(timeout=30);second.result(timeout=30)
        self.assertEqual(InvoiceReview.objects.count(),1 if result=='recorded' else 0)
        factory.run_until_wait(w.pk);self.assertFalse(InvoiceIssue.objects.exists());self.assertFalse(InvoiceDelivery.objects.exists())

"""Synthetic bounded invoice delegation; native D05/Finance/task/receipt services."""
from copy import deepcopy
import json,time
from pathlib import Path
from datetime import timedelta
from tempfile import TemporaryDirectory
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied,ValidationError
from django.test import TestCase,TransactionTestCase,Client,override_settings
from django.db import close_old_connections
from concurrent.futures import ThreadPoolExecutor
from django.urls import reverse
from django.utils import timezone
from django.conf import settings
from apps.identity.models import Grant
from apps.policy import role_assignments as nominations
from apps.policy.services import transition,role_policy,resolve,reference_values,decision_authority
from apps.policy.models import Configuration
from apps.policy.operator_drafts import draft_operator_policy
from apps.policy.factory_routing_validators import COMPONENT
from apps.workflows import factory
from apps.workflows.models import HumanTask
from apps.finance.models import Invoice,InvoiceReview,InvoiceIssue,InvoiceDelivery
from apps.finance.billing import digest
from adapters.factory_invoices import MockFactoryInvoiceAdapter
from tests.factory_helpers import fixture


def configured_delegate(username='factory-maker',window_seconds=None):
    values=json.loads((settings.BASE_DIR/'fixtures/factory-finance-delegation.json').read_text())
    assert values['classification']=='synthetic_test_only'
    f=fixture(username=username);a=f['actor'];case=f['case'];now=timezone.now()
    delegate=get_user_model().objects.create_user(username=username+'-synthetic-finance-delegate',password='test-only-password')
    for action in ['case.read','finance.read','factory.read','finance.invoice.review']:
        Grant.objects.create(case=case,user=delegate,action=action)
    start=now-timedelta(minutes=1);end=now+timedelta(seconds=window_seconds or values['window_seconds'])
    record={'role':values['role'],'principal_id':a.pk,'delegate_id':delegate.pk,
        'valid_from':start.isoformat(),'valid_until':end.isoformat(),
        'delegate_eligibility':{'roles':values['delegate_eligibility_roles'],'valid_from':start.isoformat(),'valid_until':end.isoformat()},
        'decision_scope':{**values['decision_scope'],'case_ref':str(case.pk)}}
    config=nominations.draft_delegations(a,case.pk,[record],f['evidence']['policy_decision'].pk,start)
    transition(a,config.pk,'validated');transition(a,config.pk,'active')
    owners={name:a.pk for name in ['process_owner_id','activity_owner_id','policy_owner_id','governance_resolver_id']}
    owners.update(definition='pmo-finance/v1',process_id='F30',activity='ACT10',
        method=values['method'],authority_mode=values['authority_mode'])
    routing=draft_operator_policy(a,case.pk,COMPONENT,owners,f['evidence']['policy_decision'].pk,now)
    transition(a,routing.pk,'validated');transition(a,routing.pk,'active')
    return f,delegate,config,deepcopy(record)


class FactoryDelegationTests(TestCase):
    def test_scoped_delegate_routes_claims_reviews_and_reaches_native_receipts(self):
        f,delegate,config,record=configured_delegate();w=f['work']
        with self.assertRaises(PermissionDenied):role_policy(delegate,f['case'],'Finance')
        factory.run_until_wait(w.pk)
        task=HumanTask.objects.get(case=f['case'],kind='factory_review',status='open')
        routing=task.context['routing_at_creation'];self.assertIn(delegate.pk,routing['eligible_principals'])
        authority=routing['authority'][routing['eligible_principals'].index(delegate.pk)]
        self.assertEqual(authority['D05.delegation_rules'],config.pk)
        task=factory.claim_task(delegate,task.pk,task.revision)
        client=Client();client.force_login(delegate)
        response=client.get(reverse('factory_detail',args=[w.pk]))
        self.assertContains(response,'Your review authority: configured invoice delegate')
        self.assertNotContains(response,'maximum_amount');self.assertNotContains(response,'decision_scope')
        self.assertEqual(next(t for t in response.context['row']['tasks'] if t.pk==task.pk).allowed_verdicts,['approve'])
        self.assertNotContains(response,'Return for correction');self.assertNotContains(response,'>Reject</button>')
        self.assertContains(response,'Approve exact packet');self.assertNotContains(response,'<button name="verdict" value="return">')
        self.assertNotContains(response,'<button name="verdict" value="reject">')
        review=factory.decide(delegate,task.pk,task.revision,'approve',f['proof'].pk,'Synthetic delegated exact invoice review')
        self.assertEqual(review.actor_id,delegate.pk);self.assertEqual(review.authority['D05.delegation_rules'],config.pk)
        with TemporaryDirectory() as directory:
            factory.run_until_wait(w.pk,adapter=MockFactoryInvoiceAdapter(directory))
        w.refresh_from_db();self.assertEqual(w.status,'verified',w.finding)
        self.assertEqual(Invoice.objects.count(),1);self.assertEqual(InvoiceReview.objects.count(),1)
        self.assertEqual(InvoiceIssue.objects.count(),1);self.assertEqual(InvoiceDelivery.objects.count(),1)
        self.assertEqual(w.budget_limit,20000)
        with self.assertRaises(PermissionDenied):role_policy(delegate,f['case'],'Finance')

    def successor(self,f,record):
        config=nominations.draft_delegations(f['actor'],f['case'].pk,[record],f['evidence']['policy_decision'].pk,timezone.now())
        transition(f['actor'],config.pk,'validated');transition(f['actor'],config.pk,'active');return config

    def test_unknown_financial_limit_holds_only_delegated_review_after_useful_drafting(self):
        f,b,config,record=configured_delegate();record['decision_scope']['maximum_amount']=None;self.successor(f,record)
        Grant.objects.filter(case=f['case'],user=f['actor'],action='finance.invoice.review').update(active=False)
        factory.run_until_wait(f['work'].pk);f['work'].refresh_from_db()
        self.assertEqual(f['work'].status,'owner_needed');self.assertIsNotNone(f['work'].invoice_id)
        self.assertGreater(f['work'].budget_used,0);self.assertFalse(InvoiceReview.objects.exists())
        self.assertFalse(InvoiceIssue.objects.exists());self.assertTrue(HumanTask.objects.filter(kind='factory_governance',status='open').exists())

    def test_strict_scope_validation_retains_the_active_rule_without_coercion(self):
        from uuid import uuid4
        f,b,config,record=configured_delegate();bad=[]
        for key,value in [('maximum_amount','0'),('maximum_amount','NaN'),('maximum_amount',True),('maximum_amount','1e3'),('currency','ngn'),('actions',[])]:
            item=deepcopy(record);item['decision_scope'][key]=value;bad.append(item)
        item=deepcopy(record);item['decision_scope']['case_ref']=str(uuid4());bad.append(item)
        for key in ['principal_id','delegate_id']:
            for value in [True,float(record[key])]:item=deepcopy(record);item[key]=value;bad.append(item)
        for item in bad:
            with self.subTest(item=item):
                with self.assertRaises(ValidationError):self.successor(f,item)
                self.assertEqual(resolve('D05.delegation_rules',f['case']).configuration.pk,config.pk)

    def test_currency_mismatch_does_not_infer_conversion_or_grant_generic_role_authority(self):
        f,b,config,record=configured_delegate();record['decision_scope']['currency']='USD';self.successor(f,record)
        with self.assertRaises(PermissionDenied):decision_authority(b,f['case'],'Finance',delegated=True)
        factory.run_until_wait(f['work'].pk);f['work'].refresh_from_db()
        self.assertNotIn(b.pk,[u.pk for u in factory.route(f['actor'],f['work'])])
        task=HumanTask.objects.get(kind='factory_review',status='open')
        with self.assertRaises(PermissionDenied):factory.claim_task(b,task.pk,task.revision)
        self.assertFalse(InvoiceReview.objects.exists())

    def test_revoked_delegation_after_approval_cannot_issue_from_the_old_decision(self):
        f,b,config,record=configured_delegate();w=f['work'];factory.run_until_wait(w.pk)
        task=HumanTask.objects.get(kind='factory_review',status='open');task=factory.claim_task(b,task.pk,task.revision)
        review=factory.decide(b,task.pk,task.revision,'approve',f['proof'].pk,'Synthetic bounded delegate approval')
        transition(f['actor'],config.pk,'revoked')
        factory.run_until_wait(w.pk);w.refresh_from_db()
        self.assertNotEqual(w.status,'verified');self.assertFalse(InvoiceIssue.objects.exists());self.assertFalse(InvoiceDelivery.objects.exists())
        self.assertEqual(InvoiceReview.objects.get().pk,review.pk);self.assertEqual(w.budget_limit,20000)

    def test_structured_configuration_preserves_other_delegations_and_needs_human_activation(self):
        f,b,config,record=configured_delegate();a=f['actor'];case=f['case']
        legacy={k:deepcopy(v) for k,v in record.items() if k!='decision_scope'}
        legacy['role']='PMO Lead';legacy['delegate_eligibility']['roles']=['PMO Lead']
        config=nominations.draft_delegations(a,case.pk,[record,legacy],f['evidence']['policy_decision'].pk,timezone.now())
        transition(a,config.pk,'validated');transition(a,config.pk,'active')
        client=Client();client.force_login(a);url=reverse('factory_responsibility',args=[case.pk])
        response=client.get(url);self.assertContains(response,'Invoice delegates');self.assertContains(response,'Maximum gross invoice amount')
        form=response.context['invoice_delegation_form'];self.assertEqual(form.initial['source_configuration'],config.pk)
        values={'principal':a.pk,'delegate':b.pk,'valid_from':record['valid_from'],'valid_until':record['valid_until'],
            'eligibility_roles':['Finance'],'eligibility_from':record['delegate_eligibility']['valid_from'],'eligibility_until':record['delegate_eligibility']['valid_until'],
            'actions':['approve'],'currency':'NGN','maximum_amount':'90.00','evidence':f['evidence']['policy_decision'].pk,
            'effective_from':timezone.now().isoformat(),'source_configuration':config.pk,'replacement':digest(record)}
        response=client.post(url,{'action':'invoice_delegation_draft',**{'invoice_delegate-'+k:v for k,v in values.items()}})
        self.assertEqual(response.status_code,302)
        draft=Configuration.objects.filter(case=case,component='D05.delegation_rules').latest('pk')
        self.assertEqual(draft.states.latest('pk').state,'draft')
        self.assertEqual(resolve('D05.delegation_rules',case).configuration.pk,config.pk)
        new=reference_values(draft);self.assertEqual(new[1],legacy);self.assertEqual(new[0]['decision_scope']['maximum_amount'],'90.00')
        for state in ['validated','active']:
            self.assertEqual(client.post(url,{'action':'delegation_transition','configuration':draft.pk,'state':state}).status_code,302)
        self.assertEqual(resolve('D05.delegation_rules',case).configuration.pk,draft.pk)
        self.assertFalse(InvoiceReview.objects.exists());self.assertFalse(InvoiceIssue.objects.exists())

    def test_unknown_review_mode_is_a_typed_configuration_hold_with_invoice_drafting_available(self):
        f,b,config,record=configured_delegate();a=f['actor'];case=f['case'];client=Client();client.force_login(a)
        url=reverse('factory_responsibility',args=[case.pk])
        data={name:a.pk for name in ['process_owner_id','activity_owner_id','policy_owner_id','governance_resolver_id']}
        response=client.post(url,{'action':'draft','authority_mode':'','evidence':f['evidence']['policy_decision'].pk,**data})
        self.assertEqual(response.status_code,302)
        draft=Configuration.objects.filter(case=case,component=COMPONENT).latest('pk')
        self.assertIsNone(reference_values(draft)[0]['authority_mode'])
        transition(a,draft.pk,'validated');transition(a,draft.pk,'active')
        self.assertContains(client.get(url),'Invoice review rule: Not decided')
        factory.run_until_wait(f['work'].pk);f['work'].refresh_from_db()
        self.assertEqual(f['work'].status,'owner_needed');self.assertIsNotNone(f['work'].invoice_id)
        self.assertFalse(InvoiceReview.objects.exists());self.assertFalse(InvoiceIssue.objects.exists())

    def test_exact_limit_boundary_and_two_matching_rules_are_deterministic(self):
        for index,limit in enumerate(['42.00','41.99']):
            f,b,config,record=configured_delegate(username='scope-boundary-'+str(index))
            record['decision_scope']['maximum_amount']=limit;self.successor(f,record)
            factory.run_until_wait(f['work'].pk);f['work'].refresh_from_db()
            self.assertEqual(f['work'].invoice.payload['amount'],'42.00')
            self.assertEqual(b.pk in [u.pk for u in factory.route(f['actor'],f['work'])],index==0)
        f,b,config,record=configured_delegate(username='scope-conflict')
        other=deepcopy(record);other['decision_scope']['maximum_amount']='90.00'
        changed=nominations.draft_delegations(f['actor'],f['case'].pk,[record,other],f['evidence']['policy_decision'].pk,timezone.now())
        transition(f['actor'],changed.pk,'validated');transition(f['actor'],changed.pk,'active')
        Grant.objects.filter(case=f['case'],user=f['actor'],action='finance.invoice.review').update(active=False)
        factory.run_until_wait(f['work'].pk);f['work'].refresh_from_db()
        self.assertEqual(f['work'].status,'owner_needed');self.assertFalse(InvoiceReview.objects.exists())
        self.assertFalse(InvoiceIssue.objects.exists())

    def test_delegation_does_not_bypass_acting_preparer_separation_of_duties(self):
        from apps.policy.services import active_component
        from apps.finance import invoices
        from tests.billing_helpers import policy
        f,b,config,record=configured_delegate();a=f['actor'];case=f['case']
        principal=get_user_model().objects.create_user(username='synthetic-other-finance-principal')
        for action in ['case.read','finance.read','factory.read']:Grant.objects.create(case=case,user=principal,action=action)
        assignments=deepcopy(reference_values(active_component('D05.role_principal_assignments',case)))
        assignments.append({'role':'Finance','user_id':principal.pk})
        roles=nominations.draft(a,case.pk,assignments,f['evidence']['policy_decision'].pk,timezone.now())
        transition(a,roles.pk,'validated');transition(a,roles.pk,'active')
        record['principal_id']=principal.pk;record['delegate_id']=a.pk
        record['delegate_eligibility']['roles']=sorted({r['role'] for r in assignments if r['user_id']==a.pk}|{'Finance'})
        self.successor(f,record)
        matrix=deepcopy(reference_values(active_component('D05.decision_action_matrix',case))[0])
        next(r for r in matrix['finance'] if r['purpose']=='invoice' and r['role']=='Finance')['allow_preparer_review']=False
        policy(a,case,'D05.decision_action_matrix',matrix)
        factory.run_until_wait(f['work'].pk);f['work'].refresh_from_db()
        self.assertIsNotNone(f['work'].invoice_id)
        with self.assertRaisesMessage(PermissionDenied,'different reviewer'):
            invoices.review_authority(a,case,'invoice','Finance','approve',a.pk,delegated=True,invoice=f['work'].invoice)
        self.assertFalse(InvoiceReview.objects.exists());self.assertFalse(InvoiceIssue.objects.exists())

    def test_source_access_and_stale_replacement_cannot_copy_or_erase_other_rules(self):
        f,b,config,record=configured_delegate();a=f['actor'];case=f['case'];client=Client();client.force_login(a)
        changed=deepcopy(record);changed['decision_scope']['maximum_amount']='90.00';self.successor(f,changed)
        count=Configuration.objects.filter(case=case,component='D05.delegation_rules').count()
        with self.assertRaisesMessage(ValidationError,'STALE_VERSION'):
            nominations.draft_invoice_delegation(a,case.pk,record,f['evidence']['policy_decision'].pk,timezone.now(),config.pk,digest(record))
        self.assertEqual(Configuration.objects.filter(case=case,component='D05.delegation_rules').count(),count)
        Grant.objects.filter(case=case,user=a,action='policy.read').update(active=False)
        response=client.get(reverse('factory_responsibility',args=[case.pk]))
        self.assertEqual(response.status_code,200);self.assertFalse(response.context['invoice_delegation_form'].source_available)
        # Workspace nominees remain visible under their separate authority. The
        # private delegation source, its values and lifecycle must be absent.
        self.assertEqual(response.context['invoice_delegation_form'].current_scopes,[])
        self.assertEqual(response.context['delegation_versions'],[])
        self.assertNotContains(response,'Maximum gross invoice amount')
        self.assertNotContains(response,'Current invoice delegation rules')
        self.assertNotContains(response,'name="invoice_delegate-source_configuration"')
        self.assertNotContains(response,'name="action" value="delegation_transition"')
        response=client.post(reverse('factory_responsibility',args=[case.pk]),{'action':'delegation_transition','configuration':config.pk,'state':'revoked'})
        self.assertEqual(response.status_code,403)

    def test_original_lost_response_is_recovered_after_delegate_revocation_without_new_delivery(self):
        from apps.finance.models import InvoiceJob
        f,b,config,record=configured_delegate();w=f['work'];factory.run_until_wait(w.pk)
        task=HumanTask.objects.get(kind='factory_review',status='open');task=factory.claim_task(b,task.pk,task.revision)
        factory.decide(b,task.pk,task.revision,'approve',f['proof'].pk,'Synthetic bounded delegation before original effect')
        with TemporaryDirectory() as directory:
            adapter=MockFactoryInvoiceAdapter(directory,lose_response=True)
            for _ in range(8):
                factory.run_once(w.pk,adapter=adapter)
                if InvoiceJob.objects.filter(status='unknown').exists():break
            job=InvoiceJob.objects.get(status='unknown');self.assertEqual(len(list(Path(directory).glob('*.json'))),1)
            transition(f['actor'],config.pk,'revoked');w.refresh_from_db()
            factory.reconcile(f['actor'],w.pk,w.revision)
            job.refresh_from_db();w.refresh_from_db()
            self.assertEqual(job.status,'unknown');self.assertFalse(InvoiceIssue.objects.exists())
            self.assertEqual(len(list(Path(directory).glob('*.json'))),1)
            with override_settings(FACTORY_ADAPTERS={str(f['case'].pk):MockFactoryInvoiceAdapter(directory)}):
                factory.reconcile(f['actor'],w.pk,w.revision)
            factory.run_until_wait(w.pk,adapter=MockFactoryInvoiceAdapter(directory))
            job.refresh_from_db();w.refresh_from_db();self.assertEqual(job.status,'confirmed',f'{job.error}; work={w.status}: {w.finding}')
            self.assertEqual(len(list(Path(directory).glob('*.json'))),1)
        self.assertEqual(InvoiceIssue.objects.count(),1);self.assertEqual(InvoiceDelivery.objects.count(),0)
        self.assertEqual(InvoiceReview.objects.count(),1);w.refresh_from_db();self.assertEqual(w.budget_limit,20000)

    def test_actual_authority_window_expiry_keeps_approval_history_but_blocks_new_issuance(self):
        from datetime import datetime
        from apps.finance import invoices
        f,b,config,record=configured_delegate(window_seconds=120);w=f['work'];factory.run_until_wait(w.pk)
        task=HumanTask.objects.get(kind='factory_review',status='open');task=factory.claim_task(b,task.pk,task.revision)
        review=factory.decide(b,task.pk,task.revision,'approve',f['proof'].pk,'Synthetic finite delegation before actual expiry')
        w.refresh_from_db();self.assertEqual(invoices.reviewed(w.invoice).pk,review.pk)
        deadline=datetime.fromisoformat(record['valid_until']);remaining=max(0,(deadline-timezone.now()).total_seconds())
        print(f'Actual delegation expiry wait: {remaining:.3f}s until {deadline.isoformat()}',flush=True)
        while timezone.now()<deadline:time.sleep(min(.2,max(.001,(deadline-timezone.now()).total_seconds())))
        self.assertGreaterEqual(timezone.now(),deadline)
        with self.assertRaises((ValidationError,PermissionDenied)):invoices.reviewed(w.invoice)
        factory.run_until_wait(w.pk);w.refresh_from_db()
        self.assertEqual(InvoiceReview.objects.get().pk,review.pk);self.assertFalse(InvoiceIssue.objects.exists())
        self.assertFalse(InvoiceDelivery.objects.exists());self.assertEqual(w.budget_limit,20000)


class FactoryDelegationConcurrencyTests(TransactionTestCase):
    def test_review_and_revocation_serialize_without_allowing_a_later_dispatch(self):
        f,b,config,record=configured_delegate();w=f['work'];factory.run_until_wait(w.pk)
        task=HumanTask.objects.get(kind='factory_review',status='open');task=factory.claim_task(b,task.pk,task.revision)
        def review():
            close_old_connections()
            try:
                factory.decide(b,task.pk,task.revision,'approve',f['proof'].pk,'Synthetic concurrent delegate review')
                return 'recorded'
            except (ValidationError,PermissionDenied):return 'stale'
            finally:close_old_connections()
        def revoke():
            close_old_connections()
            try:transition(f['actor'],config.pk,'revoked');return 'revoked'
            finally:close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:
            first=pool.submit(review);second=pool.submit(revoke);result=first.result(timeout=30);self.assertEqual(second.result(timeout=30),'revoked')
        self.assertIn(result,['recorded','stale']);self.assertEqual(InvoiceReview.objects.count(),1 if result=='recorded' else 0)
        with TemporaryDirectory() as directory:factory.run_until_wait(w.pk,adapter=MockFactoryInvoiceAdapter(directory))
        self.assertFalse(InvoiceIssue.objects.exists());self.assertFalse(InvoiceDelivery.objects.exists())
        self.assertEqual(resolve('D05.delegation_rules',f['case']).status,'REVOKED')

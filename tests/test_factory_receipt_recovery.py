"""Real native receipt recovery; only the external provider is a synthetic loopback."""
import os
from datetime import timedelta
from django.test import TestCase,Client,override_settings
from django.urls import reverse
from django.utils import timezone
from django.core.exceptions import ValidationError,PermissionDenied
from django.db import DatabaseError,transaction
from apps.core.services import add_evidence
from apps.policy.factory_receipt_recovery_validators import COMPONENT,METHOD,SCHEMA,validate_reference
from apps.policy.operator_drafts import draft_operator_policy
from apps.policy.services import transition
from apps.workflows import factory,readiness,readiness_delivery,factory_receipt_recovery as recovery
from apps.workflows.models import FactoryPlanningReceipt,FactoryPlanningRecovery,FactoryPlanningReceiptUse
from apps.finance.models import FinanceRun
from apps.agents import factory_coordinator as coordinator
from tests.factory_coordinator_helpers import gateway
from tests.readiness_helpers import endpoint
from tests.helpers import rev


class ReceiptRecoveryTests(TestCase):
    def rotate(self,f):
        a,c=f['actor'],f['case'];old=f['contract']
        evidence=lambda kind:add_evidence(a,c.pk,kind,'Explicit synthetic rotated credential review','synthetic:receipt-recovery')
        new=readiness.capture(a,c.pk,old.reference,dict(old.payload,credential_revision='fixture-v2'),evidence('integration_contract').pk,predecessor=old.pk)
        for kind in ['health','evaluation']:
            job=readiness_delivery.reserve(a,c.pk,new.pk,'rotated-'+kind,kind)
            readiness_delivery.run_once(case_id=c.pk);job.refresh_from_db();self.assertEqual(job.status,'confirmed')
        assessment=readiness.assess(a,c.pk,new.pk,'rotated-assessment')
        self.assertTrue(assessment.result['capability_ready'],assessment.result)
        readiness.review(a,c.pk,assessment.pk,'confirm','rotated-review',evidence('integration_review').pk)
        return new

    def configure(self,f,**changes):
        now=timezone.now()
        value=dict(method=METHOD,reviewer_id=f['actor'].pk,review_role='Finance',independent_of_requester=False,
                   valid_from=now.isoformat(),valid_until=(now+timedelta(hours=1)).isoformat())
        value.update(changes)
        p=draft_operator_policy(f['actor'],f['case'].pk,COMPONENT,value,f['evidence']['policy_decision'].pk,now)
        transition(f['actor'],p.pk,'validated');transition(f['actor'],p.pk,'active');return p

    def test_reviewed_rotated_lookup_keeps_original_receipt_without_another_request(self):
        with endpoint() as state:
            f=gateway(state,prefix='receipt-rotation');a,c,w=f['actor'],f['case'],f['work']
            state['lose_planning_response']=True;factory.run_once(w.pk);w.refresh_from_db()
            self.assertEqual(w.status,'waiting_effect');attempt=coordinator.pending(w);spent=w.budget_used
            self.assertEqual(state['planning_calls'],1)
            original=dict(attempt.result)
            state['secret']='rotated-synthetic-receipt-token';os.environ['PSL_TEST_READINESS_TOKEN']=state['secret']
            with override_settings(READINESS_SECRET_REFS={'secret:fixture':{'env':'PSL_TEST_READINESS_TOKEN','revision':'fixture-v2'}}):
                contract=self.rotate(f)
                coordinator.reconcile(a,w.pk,w.revision);w.refresh_from_db()
                self.assertEqual(w.status,'waiting_effect');self.assertFalse(FactoryPlanningReceipt.objects.exists())
                self.configure(f);transition(a,f['coordination'].pk,'revoked')
                client=Client();client.force_login(a)
                url=reverse('factory_receipt_recovery_review',args=[w.pk])
                self.assertContains(client.get(url),'Review original response recovery')
                self.assertEqual(Client(enforce_csrf_checks=True).post(url,{}).status_code,403)
                response=client.post(url,{'revision':w.revision,'case_revision':rev(c),'attempt':attempt.pk,'contract':contract.pk,
                    'evidence':f['evidence']['policy_decision'].pk,'reason':'Reviewed same provider and original receipt destination after credential rotation'})
                self.assertEqual(response.status_code,302,response.content[:300]);w.refresh_from_db()
                record=FactoryPlanningRecovery.objects.get(attempt=attempt)
                coordinator.reconcile(a,w.pk,w.revision);w.refresh_from_db()
                receipt=FactoryPlanningReceipt.objects.get(attempt=attempt)
                self.assertTrue(receipt.valid);self.assertEqual(receipt.binding,original['binding'])
                self.assertEqual(FactoryPlanningReceiptUse.objects.get(receipt=receipt).recovery_id,record.pk)
                self.assertNotEqual(record.binding,receipt.binding)
                self.assertEqual(state['planning_calls'],1);self.assertEqual(w.budget_used,spent)
                self.assertFalse(FinanceRun.objects.exists());attempt.refresh_from_db();self.assertEqual(attempt.result,original)
                with self.assertRaises(DatabaseError),transaction.atomic():FactoryPlanningRecovery.objects.filter(pk=record.pk).update(reason='overwrite')
                with self.assertRaises(DatabaseError),transaction.atomic():FactoryPlanningReceiptUse.objects.filter(receipt=receipt).delete()
                # Fresh reviewed planning settings retire the reconciled stale plan, then resume native production.
                from apps.policy.services import reference_values
                from apps.workflows.models import HumanTask
                from apps.workflows import factory_accounting
                from apps.documents.models import PublicationReceipt
                proof=add_evidence(a,c.pk,'integration_selection','Synthetic current successor selected for fresh planning','synthetic:receipt-recovery')
                readiness.select(a,c.pk,contract.pk,proof.pk)
                value=dict(reference_values(f['coordination'])[0],contract_id=contract.pk)
                current=draft_operator_policy(a,c.pk,'OPS.factory_coordinator',value,f['evidence']['policy_decision'].pk,timezone.now())
                transition(a,current.pk,'validated');transition(a,current.pk,'active')
                state['lose_planning_response']=False
                self.assertTrue(factory.run_once(w.pk));w.refresh_from_db()
                self.assertIsNone(coordinator.pending(w));self.assertEqual(w.budget_used,spent)
                self.assertEqual(state['planning_calls'],1)
                factory.run_until_wait(w.pk);w.refresh_from_db()
                task=HumanTask.objects.get(case=c,kind='factory_accounting_review',status='open')
                task=factory_accounting.claim(a,task.pk,task.revision)
                factory_accounting.decide(a,task.pk,task.revision,'approve',f['evidence']['finance_review'].pk,'Synthetic exact native output reviewed after original receipt recovery')
                factory.run_until_wait(w.pk);w.refresh_from_db()
                self.assertEqual(w.status,'verified',w.finding)
                self.assertEqual(PublicationReceipt.objects.filter(publication__factory_work=w).count(),1)
                self.assertEqual(FactoryPlanningReceipt.objects.get(attempt=attempt).pk,receipt.pk)
                self.assertGreater(w.budget_used,spent);self.assertLessEqual(w.budget_used,w.budget_limit)

    def test_unknown_policy_ui_and_validator_do_not_install_authority(self):
        import json
        from pathlib import Path
        from types import SimpleNamespace
        from tests.finance_analysis_helpers import fixture
        a,c,e,*_=fixture(username='receipt-unknown-owner')
        value=json.loads(Path('fixtures/factory-receipt-recovery.json').read_text());value.pop('classification')
        self.assertEqual(validate_reference(COMPONENT,SimpleNamespace(schema_ref=SCHEMA,content=value),c),value)
        with self.assertRaises(ValidationError):validate_reference(COMPONENT,SimpleNamespace(schema_ref=SCHEMA,content=dict(value,reviewer_id=True)),c)
        self.client.force_login(a);url=reverse('factory_receipt_recovery_configuration',args=[c.pk])
        self.assertContains(self.client.get(url),'Original response recovery settings')
        response=self.client.post(url,{'action':'draft','revision':rev(c),'base':0,'evidence':e['policy_decision'].pk})
        self.assertEqual(response.status_code,302)
        from apps.policy.models import Configuration
        policy=Configuration.objects.get(case=c,component=COMPONENT)
        self.assertContains(self.client.post(url,{'action':'active','configuration':'invalid'}),'Choose an exact settings revision')
        self.assertEqual(self.client.post(url,{'action':'validated','configuration':policy.pk}).status_code,302)
        self.assertEqual(self.client.post(url,{'action':'active','configuration':policy.pk}).status_code,302)
        from django.contrib.auth import get_user_model
        from apps.identity.models import Grant
        reader=get_user_model().objects.create_user(username='receipt-settings-denied')
        Grant.objects.create(case=c,user=reader,action='case.read');self.client.force_login(reader)
        self.assertEqual(self.client.get(url).status_code,403)

    def test_missing_receipt_redirect_withdrawal_and_independence_never_resend(self):
        from copy import deepcopy
        from apps.identity.models import Grant
        from apps.policy.services import reference_values
        with endpoint() as state:
            f=gateway(state,prefix='receipt-negative');a,c,w=f['actor'],f['case'],f['work']
            state['lose_planning_response']=True;factory.run_once(w.pk);w.refresh_from_db()
            attempt=coordinator.pending(w);spent=w.budget_used
            state['secret']='negative-rotated-synthetic-token';os.environ['PSL_TEST_READINESS_TOKEN']=state['secret']
            with override_settings(READINESS_SECRET_REFS={'secret:fixture':{'env':'PSL_TEST_READINESS_TOKEN','revision':'fixture-v2'}}):
                contract=self.rotate(f);policy=self.configure(f)
                record=recovery.review(a,w.pk,w.revision,rev(c),attempt.pk,contract.pk,f['evidence']['policy_decision'].pk,'Reviewed same-provider receipt recovery')
                w.refresh_from_db()
                result=state['receipts'].pop(attempt.result['operation_key'])
                from unittest.mock import patch
                with patch('adapters.factory_planner.FactoryPlannerAdapter.plan',side_effect=AssertionError('Receipt recovery cannot send')):
                    with self.assertRaises(coordinator.PlanningUnknown):coordinator.fetch(attempt,a,send_allowed=True)
                self.assertEqual(state['planning_calls'],1);self.assertFalse(FactoryPlanningReceipt.objects.exists())
                state['receipts'][attempt.result['operation_key']]=result
                with override_settings(READINESS_ENDPOINTS={'endpoint:fixture':{'url':'http://127.0.0.1:1','classification':'synthetic'}}):
                    with self.assertRaises(ValidationError):recovery.transport(attempt,a)
                Grant.objects.filter(case=c,user=a,action='integration.review').update(active=False)
                with self.assertRaises(PermissionDenied):recovery.transport(attempt,a)
                Grant.objects.filter(case=c,user=a,action='integration.review').update(active=True)
                transition(a,policy.pk,'revoked')
                with self.assertRaises(ValidationError):coordinator.fetch(attempt,a,send_allowed=True)
                independent=self.configure(f,independent_of_requester=True)
                with self.assertRaises(PermissionDenied):recovery.review(a,w.pk,w.revision,rev(c),attempt.pk,contract.pk,f['evidence']['policy_decision'].pk,'Must remain an independent reviewer')
                authority=deepcopy(record.authority);authority['rule']=reference_values(independent)[0]
                with self.assertRaises(DatabaseError),transaction.atomic():
                    FactoryPlanningRecovery.objects.create(attempt=attempt,sequence=2,contract=contract,reviewer=a,configuration=independent,
                        authority=authority,binding=record.binding,work_revision=w.revision,evidence=record.evidence,reason='Forged independent review')
                self.assertEqual(state['planning_calls'],1);self.assertFalse(FactoryPlanningReceipt.objects.exists())
                w.refresh_from_db();self.assertEqual(w.budget_used,spent)

    def test_actual_authority_expiry_and_cancelled_lookup_keep_original_operation(self):
        import time
        with endpoint() as state:
            f=gateway(state,prefix='receipt-expiry');a,c,w=f['actor'],f['case'],f['work']
            state['lose_planning_response']=True;factory.run_once(w.pk);w.refresh_from_db();attempt=coordinator.pending(w);spent=w.budget_used
            state['secret']='expiry-rotated-synthetic-token';os.environ['PSL_TEST_READINESS_TOKEN']=state['secret']
            with override_settings(READINESS_SECRET_REFS={'secret:fixture':{'env':'PSL_TEST_READINESS_TOKEN','revision':'fixture-v2'}}):
                contract=self.rotate(f);end=timezone.now()+timedelta(seconds=6)
                self.configure(f,valid_until=end.isoformat())
                recovery.review(a,w.pk,w.revision,rev(c),attempt.pk,contract.pk,f['evidence']['policy_decision'].pk,'Finite synthetic recovery authority')
                time.sleep(max(0,(end-timezone.now()).total_seconds())+0.1)
                with self.assertRaises(ValidationError):recovery.transport(attempt,a)
                self.configure(f);w.refresh_from_db()
                recovery.review(a,w.pk,w.revision,rev(c),attempt.pk,contract.pk,f['evidence']['policy_decision'].pk,'Fresh authority after actual expiry')
                w.refresh_from_db();factory.manage(a,w.pk,w.revision,'cancel');w.refresh_from_db()
                coordinator.reconcile(a,w.pk,w.revision);w.refresh_from_db()
                self.assertEqual(w.status,'cancelled');self.assertEqual(w.budget_used,spent)
                self.assertEqual(state['planning_calls'],1);self.assertEqual(FactoryPlanningReceipt.objects.count(),1)
                self.assertEqual(FactoryPlanningRecovery.objects.filter(attempt=attempt).count(),2)

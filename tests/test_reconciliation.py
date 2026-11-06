import copy,json
from datetime import timedelta
from django.test import TestCase
from django.core.exceptions import ValidationError,PermissionDenied
from django.db import connection,transaction,DatabaseError
from django.utils import timezone
from apps.baas import reconciliation as recon,corrective,corrective_delivery
from apps.baas.models import CorrectiveDelivery,CorrectiveJob,OutcomeVerification,CorrectiveRequest
from apps.policy.services import active_component,transition
from apps.identity.models import Grant
from apps.agents.reconciliation import investigate
from .reconciliation_helpers import fixture,body,batch,run,request,decide,delivery,outcome,verify,policy,evidence,attest
from .helpers import rev

class ReconciliationTests(TestCase):
    def setUp(self):self.a,self.c,self.engineer,self.f,self.b=fixture()
    def test_confirmed_pending_failed_findings_do_not_authorize_execution(self):
        r=run(self.a,self.c,self.b);self.assertEqual([x['finding'] for x in r.result['rows']],['settlement_confirmed','not_confirmed','not_confirmed']);self.assertFalse(r.result['financial_execution_authorized']);self.assertFalse(r.result['full_reconciliation'])
    def test_credit_handoff_and_terminal_verified_outcome_are_separate_facts(self):
        r=run(self.a,self.c,self.b);q=request(self.a,self.c,r);d=delivery(self.a,self.c,q);self.assertFalse(OutcomeVerification.objects.exists());self.assertTrue(d.payload['delivery_only'])
        o=outcome(self.engineer,self.c,d);v=verify(self.a,self.c,o);self.assertEqual(v.outcome.payload['status'],'applied');self.assertEqual(CorrectiveDelivery.objects.count(),1)
        self.assertEqual(verify(self.a,self.c,o).pk,v.pk)
    def test_missing_policy_keeps_capture_but_holds_dependent_actions(self):
        transition(self.a,active_component(recon.CONTRACT,self.c).pk,'revoked');r=run(self.a,self.c,self.b,False);self.assertEqual(r.result['status'],'held');q=request(self.a,self.c,r)
        with self.assertRaises(ValidationError):decide(self.a,self.c,q)
    def test_duplicate_settlement_has_no_arbitrary_winner(self):
        v=body('settlement');v['rows'].append(copy.deepcopy(v['rows'][0]));self.b['settlement']=batch(self.a,self.c,'settlement',v)
        r=run(self.a,self.c,self.b);self.assertEqual(r.result['rows'][0]['finding'],'ambiguous');self.assertIn('Duplicate',' '.join(r.result['rows'][0]['issues']))
    def test_unknown_amount_currency_conflict_and_tolerance(self):
        v=body('settlement');v['rows'][0]['amount']=None;v['rows'][1]['currency']='USD';self.b['settlement']=batch(self.a,self.c,'settlement',v)
        r=run(self.a,self.c,self.b);self.assertEqual([x['finding'] for x in r.result['rows'][:2]],['ambiguous','ambiguous'])
        v=body('settlement');v['rows'][0]['amount']='99.99';self.b['settlement']=batch(self.a,self.c,'settlement',v)
        r=run(self.a,self.c,self.b);self.assertEqual(r.result['rows'][0]['finding'],'ambiguous')
        policy(self.a,self.c,recon.CONTRACT,dict(self.f['contract'],amount_tolerance='0.01'));r=run(self.a,self.c,self.b);self.assertEqual(r.result['rows'][0]['finding'],'settlement_confirmed')
    def test_source_mismatch_and_stale_observation_do_not_confirm(self):
        v=body('settlement');v['source']='unconfigured-source';self.b['settlement']=batch(self.a,self.c,'settlement',v,reference='other-source')
        r=run(self.a,self.c,self.b);self.assertEqual(r.result['rows'][0]['finding'],'ambiguous')
        v=body('settlement');v['rows'][0]['observed_at']=(timezone.now()-timedelta(hours=2)).isoformat();self.b['settlement']=batch(self.a,self.c,'settlement',v)
        r=run(self.a,self.c,self.b);self.assertEqual(r.result['rows'][0]['finding'],'ambiguous');self.assertEqual(r.result['rows'][1]['finding'],'not_confirmed')
    def test_attestation_is_only_required_when_configured_and_can_be_revoked(self):
        r=run(self.a,self.c,self.b,False);self.assertEqual(r.result['rows'][0]['finding'],'ambiguous')
        policy(self.a,self.c,recon.CONTRACT,dict(self.f['contract'],attestation_kinds=[]));r=run(self.a,self.c,self.b,False);self.assertEqual(r.result['rows'][0]['finding'],'settlement_confirmed')
        policy(self.a,self.c,recon.CONTRACT,self.f['contract']);r=run(self.a,self.c,self.b);Grant.objects.filter(case=self.c,user=self.a,action='baas.reconciliation.attest').update(active=False)
        with self.assertRaisesMessage(ValidationError,'changed'):recon.ensure_current(r)
    def test_missing_queue_holds_only_dependent_queue_request(self):
        self.b['queue']=None;r=run(self.a,self.c,self.b);q=request(self.a,self.c,r);decide(self.a,self.c,q)
        q=request(self.a,self.c,r,kind='queue_transition',reference='QUEUE',operation='QUEUE-OP')
        with self.assertRaisesMessage(ValidationError,'queue state'):decide(self.a,self.c,q)
    def test_duplicate_queue_does_not_invalidate_independent_settlement_comparison(self):
        v=body('queue');v['rows'].append(copy.deepcopy(v['rows'][0]));self.b['queue']=batch(self.a,self.c,'queue',v);r=run(self.a,self.c,self.b)
        self.assertEqual(r.result['rows'][0]['finding'],'settlement_confirmed');self.assertFalse(r.result['rows'][0]['queue_ready'])
    def test_pending_age_uses_configured_states_and_threshold(self):
        v=body('queue');v['rows'][0]['observed_at']=(timezone.now()-timedelta(seconds=100)).isoformat();v['rows'][1].update(observed_at=v['rows'][0]['observed_at'],queue_state='complete');self.b['queue']=batch(self.a,self.c,'queue',v)
        r=run(self.a,self.c,self.b);self.assertTrue(r.result['rows'][0]['queue_age_threshold_exceeded']);self.assertFalse(r.result['rows'][1]['queue_age_threshold_exceeded'])
    def test_fund_and_queue_requests_use_distinct_configured_routes(self):
        r=run(self.a,self.c,self.b);fund=request(self.a,self.c,r,kind='fund_movement');d=delivery(self.a,self.c,fund);self.assertEqual(d.payload['command']['from_account'],'operating-account')
        q=request(self.a,self.c,r,kind='queue_transition',reference='QUEUE',operation='QUEUE-OP');d=delivery(self.a,self.c,q);self.assertEqual(d.payload['command']['to_state'],'ready');self.assertIsNone(d.payload['command']['amount'])
        self.assertEqual(self.b['queue'].payload['rows'][1]['queue_state'],'pending')
    def test_unknown_over_limit_over_source_and_bad_account_hold_decision(self):
        r=run(self.a,self.c,self.b)
        for n,amount in enumerate([None,'1001','101']):
            q=request(self.a,self.c,r,amount=amount,reference='REQ-'+str(n),operation='OP-'+str(n))
            with self.assertRaises(ValidationError):decide(self.a,self.c,q)
        q=request(self.a,self.c,r,reference='BAD-ACCOUNT',operation='BAD-ACCOUNT');v=dict(q.payload,to_account='arbitrary-account');e=evidence(self.a,self.c,'corrective_request',v)
        q=corrective.capture(self.a,self.c.pk,r.pk,'BAD-ACCOUNT','BAD-ACCOUNT',e.pk,'Explicit changed destination',rev(self.c))
        with self.assertRaisesMessage(ValidationError,'account route'):decide(self.a,self.c,q)
    def test_precision_never_implicitly_rounds(self):
        v=body('ledger');v['rows'][0]['amount']='100.001';self.b['ledger']=batch(self.a,self.c,'ledger',v)
        with self.assertRaisesMessage(ValidationError,'precision'):run(self.a,self.c,self.b)
    def test_reject_return_and_preparer_separation(self):
        r=run(self.a,self.c,self.b);q=request(self.a,self.c,r);decide(self.a,self.c,q,'return')
        with self.assertRaises(ValidationError):corrective.reserve(self.a,self.c.pk,q.pk,'Finance',rev(self.c))
        f=copy.deepcopy(self.f['commands']);f['commands'][0]['allow_preparer_review']=False;policy(self.a,self.c,recon.COMMANDS,f)
        with self.assertRaises(PermissionDenied):decide(self.a,self.c,q)
    def test_new_source_or_request_revision_stales_approval_and_pending_handoff(self):
        r=run(self.a,self.c,self.b);q=request(self.a,self.c,r);decide(self.a,self.c,q);j=corrective.reserve(self.a,self.c.pk,q.pk,'Finance',rev(self.c))
        batch(self.a,self.c,'settlement');corrective_delivery.run_once();j.refresh_from_db();self.assertEqual(j.status,'held');self.assertFalse(CorrectiveDelivery.objects.exists())
    def test_policy_or_approver_revocation_stops_new_dispatch(self):
        r=run(self.a,self.c,self.b);q=request(self.a,self.c,r);decide(self.a,self.c,q);j=corrective.reserve(self.a,self.c.pk,q.pk,'Finance',rev(self.c));Grant.objects.filter(case=self.c,user=self.a,action='baas.corrective.decide').update(active=False)
        corrective_delivery.run_once();j.refresh_from_db();self.assertEqual(j.status,'held');self.assertFalse(CorrectiveDelivery.objects.exists())
    def test_administrator_and_source_text_cannot_grant_engineering_authority(self):
        r=run(self.a,self.c,self.b);q=request(self.a,self.c,r);d=delivery(self.a,self.c,q);self.a.is_superuser=True;self.a.save()
        value={'operation_key':d.operation_key,'request_hash':d.payload['request_hash'],'source':'synthetic-engineering-register','external_reference':'UNTRUSTED','status':'applied','observed_at':timezone.now().isoformat(),'command':d.payload['command']};e=evidence(self.a,self.c,'engineering_outcome',value)
        with self.assertRaises(ValidationError):corrective.record_outcome(self.a,self.c.pk,d.pk,e.pk,rev(self.c))
    def test_unknown_outcome_not_success_and_wrong_correlation_is_rejected(self):
        r=run(self.a,self.c,self.b);d=delivery(self.a,self.c,request(self.a,self.c,r));o=outcome(self.engineer,self.c,d,'unknown')
        with self.assertRaisesMessage(ValidationError,'unknown'):verify(self.a,self.c,o)
        bad=dict(o.payload,operation_key='OTHER');e=evidence(self.engineer,self.c,'engineering_outcome',bad)
        with self.assertRaisesMessage(ValidationError,'correlation'):corrective.record_outcome(self.engineer,self.c.pk,d.pk,e.pk,rev(self.c))
        terminal=outcome(self.engineer,self.c,d,'rejected','EXTERNAL-REJECT');verify(self.a,self.c,terminal)
        conflicting=outcome(self.engineer,self.c,d,'applied','EXTERNAL-CONFLICT')
        with self.assertRaisesMessage(ValidationError,'already exists'):verify(self.a,self.c,conflicting)
    def test_exact_proof_and_distinct_verifier_are_enforced(self):
        r=run(self.a,self.c,self.b);d=delivery(self.a,self.c,request(self.a,self.c,r));o=outcome(self.engineer,self.c,d);bad=evidence(self.a,self.c,'engineering_outcome_verification',dict(o.payload,status='rejected'))
        with self.assertRaisesMessage(ValidationError,'Exact terminal'):corrective.verify_outcome(self.a,self.c.pk,o.pk,'Finance',bad.pk,rev(self.c))
    def test_same_subject_duplicate_request_cannot_dispatch_twice(self):
        r=run(self.a,self.c,self.b);q=request(self.a,self.c,r);delivery(self.a,self.c,q)
        q2=request(self.a,self.c,r,reference='SECOND',operation='SECOND');decide(self.a,self.c,q2)
        with self.assertRaisesMessage(ValidationError,'already has'):corrective.reserve(self.a,self.c.pk,q2.pk,'Finance',rev(self.c))
    def test_current_receive_and_read_grants_control_private_engineering_inbox(self):
        r=run(self.a,self.c,self.b);d=delivery(self.a,self.c,request(self.a,self.c,r));self.client.force_login(self.engineer);self.assertContains(self.client.get('/baas/engineering/inbox/'),'REQ-1')
        self.client.force_login(self.a);self.assertNotContains(self.client.get('/baas/engineering/inbox/'),'REQ-1')
        Grant.objects.filter(case=self.c,user=self.engineer,action='baas.engineering.receive').update(active=False);self.client.force_login(self.engineer);self.assertNotContains(self.client.get('/baas/engineering/inbox/'),'REQ-1')
    def test_cross_case_subjects_and_read_revocation_are_denied(self):
        from apps.core.models import Case
        other=Case.objects.create(tenant='other',title='Other',synthetic=True)
        with self.assertRaises(ValidationError):recon.exact(other,type(self.b['ledger']),self.b['ledger'].pk)
        Grant.objects.filter(case=self.c,user=self.a,action='baas.read').update(active=False)
        with self.assertRaises(PermissionDenied):run(self.a,self.c,self.b,False)
    def test_sql_immutable_source_and_job_intent_guards(self):
        r=run(self.a,self.c,self.b);q=request(self.a,self.c,r);decide(self.a,self.c,q);j=corrective.reserve(self.a,self.c.pk,q.pk,'Finance',rev(self.c))
        with self.assertRaises(DatabaseError),transaction.atomic():
            with connection.cursor() as cur:cur.execute('UPDATE baas_reconciliationbatch SET reference=%s WHERE id=%s',['rewritten',self.b['ledger'].pk])
        with self.assertRaises(DatabaseError),transaction.atomic():CorrectiveJob.objects.filter(pk=j.pk).update(intent={})
    def test_policy_validators_reject_overlap_unknown_tolerance_and_invalid_queue_money(self):
        for contract in [dict(self.f['contract'],amount_tolerance=None),dict(self.f['contract'],statuses={'settled':['same'],'pending':['same'],'failed':[]})]:
            with self.assertRaises(ValidationError):policy(self.a,self.c,recon.CONTRACT,contract)
        mapping=copy.deepcopy(self.f['commands']);mapping['commands'][2]['max_amount']='10'
        with self.assertRaises(ValidationError):policy(self.a,self.c,recon.COMMANDS,mapping)
    def test_agent_cites_discrepancies_and_has_no_execution_tools(self):
        r=run(self.a,self.c,self.b);q=request(self.a,self.c,r);log=investigate(self.a,self.c.pk,r.pk,rev(self.c));self.assertTrue(log.result['citations']);self.assertFalse(log.result['approval_granted']);self.assertFalse(log.result['funds_mutated']);self.assertFalse(log.result['business_queue_mutated'])
    def test_missing_source_row_is_unknown_in_staff_ui(self):
        recon.investigate(self.a,self.c.pk,self.b['ledger'].pk,None,None,rev(self.c))
        self.client.force_login(self.a)
        response=self.client.get(f'/cases/{self.c.pk}/baas/reconciliation/')
        self.assertContains(response,'settlement Unknown')
        self.assertContains(response,'Amount difference Unknown')
        self.assertContains(response,'Unknown · unavailable for transition checks')
    def test_full_staff_forms_policy_lifecycle_engineering_and_outcome_path(self):
        self.client.force_login(self.a);url=f'/cases/{self.c.pk}/baas/reconciliation/'
        def post(action,**values):
            response=self.client.post(url,dict(action=action,revision=rev(self.c),**values));self.assertEqual(response.status_code,302,response.content[:300])
        a=attest(self.a,self.c,self.b['settlement']);post('calculate',ledger=self.b['ledger'].pk,settlement=self.b['settlement'].pk,queue=self.b['queue'].pk)
        from apps.baas.models import ReconciliationRun
        r=ReconciliationRun.objects.get();q=request(self.a,self.c,r);e=evidence(self.a,self.c,'corrective_decision','Synthetic full UI approval');post('decide',request=q.pk,role='Finance',verdict='approve',evidence=e.pk,reason='UI exact request and authority reviewed');post('reserve',request=q.pk,role='Finance');corrective_delivery.run_once()
        d=CorrectiveDelivery.objects.get();o=outcome(self.engineer,self.c,d);e=evidence(self.a,self.c,'engineering_outcome_verification',o.payload);post('verify',outcome=o.pk,role='Finance',evidence=e.pk);post('investigate',run=r.pk)
        self.assertContains(self.client.get(url),'Terminal verification');self.assertContains(self.client.get(url),'Cited reconciliation investigation')
        owner=evidence(self.a,self.c,'policy_decision','Synthetic typed contract UI draft');post('policy',component=recon.CONTRACT,content=json.dumps(self.f['contract']),evidence=owner.pk,effective_from=timezone.now().isoformat())
        from apps.policy.models import Configuration
        c=Configuration.objects.filter(case=self.c,component=recon.CONTRACT).order_by('-pk').first();self.assertEqual(c.states.order_by('-pk').first().state,'draft');transition(self.a,c.pk,'validated');transition(self.a,c.pk,'active')

"""Exact F31/F45 synthetic fixtures; no operational source authenticity claim."""
import json
from datetime import date
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import DatabaseError, transaction
from django.test import TestCase
from apps.core.models import Evidence
from apps.core.evidence_access import public_evidence, public_timeline
from apps.identity.models import Grant
from apps.finance import contract_coverage as cc
from apps.finance.models import (CoverageSource, CoverageTerms, CoverageAssessment,
    CoveragePreparationReceipt, Invoice, InvoiceIssue)
from apps.workflows.models import HumanTask
from .helpers import setup_case, rev
from .billing_helpers import coverage, evidence as native_evidence

def evidence(actor,case,kind,body,reference=None,purposes=None):
    if not kind.startswith('coverage_'):return native_evidence(actor,case,kind,body)
    if kind=='coverage_access':refs=[reference or 'bootstrap'];purposes=purposes or ['access']
    elif kind=='coverage_source':refs=[reference or 'register'];purposes=purposes or ['capture']
    elif kind=='coverage_decision':refs=['register','contract'];purposes=purposes or ['configure','activate','prepare']
    else:
        declaration=json.loads(body)
        if kind=='coverage_terms':
            refs=[CoverageSource.objects.get(pk=declaration[key]).reference for key in ['register_id','contract_id']];purposes=purposes or ['configure']
        elif kind=='coverage_schedule_interpretation':
            refs=[CoverageSource.objects.get(pk=declaration['contract_source_id']).reference];purposes=purposes or ['configure']
        elif kind=='coverage_verification':
            refs=[CoverageSource.objects.get(pk=declaration['source_id']).reference];purposes=purposes or ['verify']
    return cc.supply_evidence(actor,case.pk,refs,purposes,kind,body,'synthetic:coverage-test',rev(case))


ANNUAL={'start':'2026-10-01','end':'2027-09-30','bill_on':'2026-10-01'}
SEPTEMBER={'start':'2026-09-01','end':'2026-09-30','bill_on':'2026-09-01'}

class ContractCoverageTests(TestCase):
    def setUp(self):
        self.a,self.c=setup_case();self.cov=coverage(self.a,self.c,from_period='2026-09')
        self.b=get_user_model().objects.create_user(username='coverage-verifier',password='isolated-fixture-only')
        for action in Grant.objects.filter(user=self.a,case=self.c).values_list('action',flat=True):
            Grant.objects.create(user=self.b,case=self.c,action=action)
        self.proof=None;self.decision=None

    def grant(self,reference,user=None,permissions=None):
        proof=evidence(self.a,self.c,'coverage_access','Explicit synthetic reference permissions',reference=reference)
        return cc.grant_access(self.a,self.c.pk,reference,(user or self.a).pk,
            cc.PERMISSIONS if permissions is None else permissions,proof.pk,rev(self.c))

    def payload(self,kind='contract',row=None,**changes):
        row=row or ANNUAL
        p={'system':'synthetic-existing-it','external_id':kind+'-existing-record','external_version':'v1',
            'customer':self.cov.customer,'service':self.cov.service,'contract':self.cov.contract,'status':'current',
            'cadence':'annual','service_state':'active','start':row['start'],'end':row['end'],
            'schedule':[row],'state_treatment':'unknown'}
        p.update(changes);return p

    def source(self,reference,kind,payload):
        if not CoverageSource.objects.filter(case=self.c,reference=reference).exists():
            self.grant(reference);self.grant(reference,self.b)
        e=evidence(self.a,self.c,'coverage_source',json.dumps(payload),reference=reference)
        return cc.capture_source(self.a,self.c.pk,reference,kind,payload,e.pk,rev(self.c))

    def terms(self,*,row=None,cadence='annual',register_cadence=None,active=True,review='none',reviewer=None,**changes):
        row=row or ANNUAL
        register=self.source('register','register',self.payload('register',row,cadence=register_cadence or cadence))
        contract=self.source('contract','contract',self.payload('contract',row,cadence=cadence,**changes))
        self.decision=evidence(self.a,self.c,'coverage_decision','Synthetic supplied interpretation decision, no real owner policy')
        interpretation=evidence(self.a,self.c,'coverage_schedule_interpretation',json.dumps({'contract_source_id':contract.pk,'contract_source_hash':contract.sha256,'mode':'standard_periods','attestation':'source_schedule_matches_cadence','reason':'Supplied synthetic interpretation, no production rule'}))
        payload={'implementation':'explicit-contract-schedule/v1','review_requirement':review,'reviewer_id':reviewer,'owner_id':None,'schedule_interpretation':{'mode':'standard_periods','attestation':'source_schedule_matches_cadence','evidence_id':interpretation.pk},'invoice_verification':{'method':'supplied_readonly_invoice_v1','verifier_id':self.b.pk,'distinct_capture_actor':True}}
        e=evidence(self.a,self.c,'coverage_terms',json.dumps({'coverage_id':self.cov.pk,'register_id':register.pk,'contract_id':contract.pk,'terms':payload}))
        t=cc.draft_terms(self.a,self.c.pk,self.cov.pk,register.pk,contract.pk,payload,e.pk,rev(self.c))
        cc.transition(self.a,self.c.pk,t.pk,'validated',self.decision.pk,rev(self.c))
        if active:cc.transition(self.a,self.c.pk,t.pk,'active',self.decision.pk,rev(self.c))
        self.last_terms=t
        return t

    def assess(self,t,actor=None):return cc.assess(actor or self.a,self.c.pk,t.pk,date(2026,11,7),rev(self.c))

    def invoice(self,row=None,reference='invoice-source',**changes):
        p=self.payload('invoice',row or SEPTEMBER,cadence='monthly',invoice_reference='INCUMBENT-SEP-01',
            invoice_status='issued',invoice_period=row or SEPTEMBER,verification_method='supplied_readonly_invoice_v1',**changes)
        return self.source(reference,'invoice',p)

    def verify(self,source,actor=None,native=None):
        value={'terms_id':self.last_terms.pk,'source_id':source.pk,'source_sha256':source.sha256,'native_issue_id':native,
            'verification':'matched_exact_source_record','invoice_reference':source.payload['invoice_reference'],
            'period':source.payload['invoice_period']}
        e=evidence(self.a,self.c,'coverage_verification',json.dumps(value))
        return cc.verify_invoice(actor or self.b,self.c.pk,source.pk,e.pk,native,rev(self.c),terms_id=self.last_terms.pk)

    def test_f31_annual_october_first_one_obligation_and_idempotent_intake(self):
        t=self.terms();record=self.assess(t);rows=record.result['obligations']
        self.assertEqual(record.result['status'],'assessed');self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['bill_on'],'2026-10-01');self.assertEqual(rows[0]['status'],'missing_invoice')
        self.assertEqual(self.assess(t).pk,record.pk)
        self.assertEqual(self.source('register','register',t.register.payload).pk,t.register_id)
        self.assertEqual(CoverageSource.objects.count(),2);self.assertEqual(Invoice.objects.count(),0)
        self.assertFalse(record.result['paid'])

    def test_f31_monthly_list_annual_contract_conflict_is_preserved_and_held(self):
        t=self.terms(register_cadence='monthly',active=False)
        with self.assertRaises(ValidationError):cc.transition(self.a,self.c.pk,t.pk,'active',self.decision.pk,rev(self.c))
        result=self.assess(t).result
        self.assertEqual(result['status'],'indeterminate');self.assertEqual(result['obligations'],[])
        self.assertTrue(any('cadence conflict' in f for f in result['findings']))
        self.assertEqual(t.register.payload['cadence'],'monthly');self.assertEqual(t.contract.payload['cadence'],'annual')

    def test_f45_exact_september_incumbent_invoice_covered_without_local_issuance(self):
        t=self.terms(row=SEPTEMBER,cadence='monthly');src=self.invoice();ref=self.verify(src)
        self.assertEqual(self.verify(src).pk,ref.pk)
        record=self.assess(t);self.assertEqual(record.result['status'],'assessed')
        self.assertEqual(record.result['obligations'][0]['status'],'covered')
        self.assertEqual(record.result['obligations'][0]['invoice_refs'],[ref.pk]);self.assertEqual(InvoiceIssue.objects.count(),0)
        self.assertFalse(record.result['external_authenticity_verified']);self.assertFalse(record.result['ledger_posted'])

    def test_unknown_cadence_and_midperiod_suspension_do_not_assume_proration(self):
        t=self.terms(cadence='unknown',active=False,service_state='suspended',state_changed_on='2026-11-01');result=self.assess(t).result
        self.assertEqual(result['status'],'indeterminate');self.assertEqual(result['obligations'],[])
        self.assertTrue(any('cadence is unknown' in f for f in result['findings']))
        self.assertTrue(any('proration' in f for f in result['findings']))

    def test_wrong_period_service_and_contract_cannot_cover(self):
        t=self.terms(row=SEPTEMBER,cadence='monthly');self.verify(self.invoice(row=ANNUAL))
        for reference,changes in [('wrong-service',{'service':'another-service'}),('wrong-contract',{'contract':'another-contract'}),('wrong-customer',{'customer':'another-customer'})]:
            with self.assertRaises(ValidationError):self.verify(self.invoice(reference=reference,**changes))
        self.assertEqual(self.assess(t).result['obligations'][0]['status'],'missing_invoice')

    def test_unverified_paste_or_self_verification_never_establishes_coverage(self):
        t=self.terms(row=SEPTEMBER,cadence='monthly');src=self.invoice()
        with self.assertRaises(PermissionDenied):self.verify(src,self.a)
        result=self.assess(t).result;self.assertEqual(result['status'],'indeterminate')
        self.assertEqual(result['obligations'][0]['status'],'indeterminate')

    def test_duplicate_exact_invoice_candidates_are_conflict_not_covered(self):
        t=self.terms(row=SEPTEMBER,cadence='monthly');self.verify(self.invoice());self.verify(self.invoice(reference='duplicate-invoice-source'))
        result=self.assess(t).result;self.assertEqual(result['status'],'indeterminate')
        self.assertEqual(result['obligations'][0]['status'],'conflict')

    def test_withdrawn_invoice_successor_and_verifier_grant_revocation_invalidate(self):
        t=self.terms(row=SEPTEMBER,cadence='monthly');src=self.invoice();self.verify(src);old=self.assess(t)
        self.grant('invoice-source',self.b,['read'])
        with self.assertRaises(ValidationError):cc.current_assessment(self.a,old)
        self.assertEqual(self.assess(t).result['status'],'indeterminate');self.grant('invoice-source',self.b)
        self.source('invoice-source','invoice',dict(src.payload,external_version='v2',status='withdrawn'))
        self.assertEqual(self.assess(t).result['status'],'indeterminate')
        old.refresh_from_db();self.assertEqual(old.result['obligations'][0]['status'],'covered')

    def test_source_scope_access_revocation_and_no_generic_evidence_leak(self):
        t=self.terms();self.grant('contract',self.b,[])
        with self.assertRaises(PermissionDenied):self.assess(t,self.b)
        self.assertFalse(public_evidence(Evidence.objects.filter(case=self.c)).filter(kind__startswith='coverage_').exists())
        self.assertFalse(public_timeline(self.c).filter(action__startswith='coverage.').exists())
        Grant.objects.filter(user=self.a,case=self.c,action='coverage.configure').update(active=False)
        self.assertEqual(self.assess(t).result['status'],'indeterminate')

    def test_native_human_preparation_handoff_and_uncertain_receipt_retry(self):
        t=self.terms();assessment=self.assess(t);key=assessment.result['obligations'][0]['key']
        request=cc.request_preparation(self.a,self.c.pk,assessment.pk,key,self.b.pk,rev(self.c))
        self.assertEqual(cc.request_preparation(self.a,self.c.pk,assessment.pk,key,self.b.pk,rev(self.c)).pk,request.pk)
        with self.assertRaises(PermissionDenied):cc.receive_preparation(self.a,self.c.pk,request.pk,None,rev(self.c))
        receipt=cc.receive_preparation(self.b,self.c.pk,request.pk,None,rev(self.c))
        self.assertEqual(cc.receive_preparation(self.b,self.c.pk,request.pk,None,rev(self.c)).pk,receipt.pk)
        self.assertEqual(CoveragePreparationReceipt.objects.count(),1)
        self.assertEqual(HumanTask.objects.get(factory_key='coverage:'+request.operation_key).status,'completed')
        self.assertEqual(Invoice.objects.count(),0)

    def test_not_due_cannot_enter_preparation(self):
        t=self.terms();record=cc.assess(self.a,self.c.pk,t.pk,date(2026,9,1),rev(self.c))
        self.assertEqual(record.result['obligations'][0]['status'],'not_due')
        with self.assertRaises(ValidationError):cc.request_preparation(self.a,self.c.pk,record.pk,record.result['obligations'][0]['key'],self.b.pk,rev(self.c))

    def test_stale_source_prevents_new_handoff_but_original_receipt_is_recoverable(self):
        t=self.terms();a=self.assess(t);key=a.result['obligations'][0]['key']
        req=cc.request_preparation(self.a,self.c.pk,a.pk,key,self.b.pk,rev(self.c))
        receipt=cc.receive_preparation(self.b,self.c.pk,req.pk,None,rev(self.c))
        self.source('contract','contract',dict(t.contract.payload,external_version='v2',status='withdrawn'))
        with self.assertRaises(ValidationError):cc.request_preparation(self.a,self.c.pk,a.pk,key,self.b.pk,rev(self.c))
        self.assertEqual(cc.receive_preparation(self.b,self.c.pk,req.pk,None,rev(self.c)).pk,receipt.pk)

    def test_configured_review_is_exact_but_none_does_not_invent_approval(self):
        t=self.terms(active=False,review='required',reviewer=self.b.pk)
        with self.assertRaises(PermissionDenied):cc.transition(self.a,self.c.pk,t.pk,'active',self.decision.pk,rev(self.c))
        cc.transition(self.b,self.c.pk,t.pk,'active',self.decision.pk,rev(self.c))
        self.assertEqual(self.assess(t).result['status'],'assessed');self.grant('contract',self.b,['read'])
        self.assertEqual(self.assess(t).result['status'],'indeterminate')

    def test_source_and_terms_evidence_exactness_and_stale_revisions(self):
        self.grant('register');p=self.payload('register');e=evidence(self.a,self.c,'coverage_source',json.dumps(dict(p,external_id='different')))
        with self.assertRaises(ValidationError):cc.capture_source(self.a,self.c.pk,'register','register',p,e.pk,rev(self.c))
        with self.assertRaises(ValidationError):cc.capture_source(self.a,self.c.pk,'register','register',p,e.pk,0)
        self.assertEqual(CoverageSource.objects.count(),0)

    def test_invalid_overlapping_schedule_remains_typed_draft_with_findings(self):
        t=self.terms(active=False,schedule=[ANNUAL,ANNUAL]);self.assertTrue(t.events.order_by('-pk').first().findings)
        with self.assertRaises(ValidationError):cc.transition(self.a,self.c.pk,t.pk,'active',self.decision.pk,rev(self.c))
        self.assertEqual(Invoice.objects.count(),0)

    def test_history_is_database_append_only(self):
        t=self.terms();self.assess(t)
        for model in [CoverageSource,CoverageTerms,CoverageAssessment]:
            with self.assertRaises(DatabaseError),transaction.atomic():model.objects.filter(pk=model.objects.first().pk).update(actor_id=self.b.pk)

    def revised_terms(self,old,payload=None,activate=False):
        p=dict(old.payload) if payload is None else payload
        e=evidence(self.a,self.c,'coverage_terms',json.dumps({'coverage_id':self.cov.pk,'register_id':old.register_id,'contract_id':old.contract_id,'terms':p}))
        t=cc.draft_terms(self.a,self.c.pk,self.cov.pk,old.register_id,old.contract_id,p,e.pk,rev(self.c))
        if t.pk!=old.pk:
            cc.transition(self.a,self.c.pk,t.pk,'validated',self.decision.pk,rev(self.c))
            if activate:cc.transition(self.a,self.c.pk,t.pk,'active',self.decision.pk,rev(self.c))
        return t

    def test_corrected_verified_invoice_successor_does_not_leave_permanent_unknown(self):
        t=self.terms(row=SEPTEMBER,cadence='monthly');src=self.invoice();self.verify(src)
        original=self.assess(t)
        newer=self.source('invoice-source','invoice',dict(src.payload,external_version='v2'))
        self.assertEqual(self.assess(t).result['status'],'indeterminate')
        corrected=self.verify(newer)
        result=self.assess(t).result
        self.assertEqual(result['status'],'assessed');self.assertEqual(result['obligations'][0]['invoice_refs'],[corrected.pk])
        original.refresh_from_db();self.assertEqual(original.result['obligations'][0]['status'],'covered')

    def test_unapproved_same_source_draft_does_not_supersede_active_terms(self):
        old=self.terms();first=self.assess(old)
        candidate=self.revised_terms(old,dict(old.payload,owner_id=self.b.pk))
        self.assertNotEqual(old.pk,candidate.pk);self.assertEqual(self.assess(old).pk,first.pk)
        cc.transition(self.a,self.c.pk,candidate.pk,'active',self.decision.pk,rev(self.c))
        self.assertEqual(self.assess(old).result['status'],'indeterminate')
        self.assertEqual(self.assess(candidate).result['status'],'assessed')
        cc.transition(self.a,self.c.pk,candidate.pk,'revoked',self.decision.pk,rev(self.c))
        self.assertEqual(self.assess(old).result['status'],'indeterminate')

    def test_missing_verification_configuration_holds_only_verification(self):
        old=self.terms(row=SEPTEMBER,cadence='monthly');p=dict(old.payload);p.pop('invoice_verification')
        self.last_terms=t=self.revised_terms(old,p,activate=True)
        self.assertEqual(self.assess(t).result['status'],'assessed')
        with self.assertRaises(ValidationError):self.verify(self.invoice())
        self.assertEqual(self.assess(t).result['status'],'indeterminate')

    def test_same_capture_actor_allowed_only_under_explicit_verification_rule(self):
        old=self.terms(row=SEPTEMBER,cadence='monthly')
        p=dict(old.payload,invoice_verification={'method':'supplied_readonly_invoice_v1','verifier_id':self.a.pk,'distinct_capture_actor':False})
        self.last_terms=t=self.revised_terms(old,p,activate=True)
        self.verify(self.invoice(),self.a)
        self.assertEqual(self.assess(t).result['obligations'][0]['status'],'covered')

    def test_private_agent_and_http_flow_currentness_revocation_and_get_preservation(self):
        from apps.agents import contract_coverage as agent
        from apps.agents.models import AgentRun
        from apps.core.evidence_access import public_agent_runs
        t=self.terms();self.client.force_login(self.a);url=f'/cases/{self.c.pk}/finance/contract-coverage/'
        before=rev(self.c)
        response=self.client.get(url);self.assertEqual(response.status_code,200)
        self.assertEqual(rev(self.c),before);self.assertEqual(response.headers['Cache-Control'],'no-store')
        response=self.client.post(url,{'action':'investigate','revision':before,'terms':t.pk,'as_of':'2026-11-07','process_id':'F31'})
        self.assertEqual(response.status_code,302)
        run=AgentRun.objects.get(provider=agent.PROVIDER)
        self.assertEqual(run.result['owner_status'],'unassigned');self.assertTrue(run.result['questions'])
        self.assertFalse(public_agent_runs(AgentRun.objects.all()).filter(pk=run.pk).exists())
        with self.assertRaises(ValidationError):agent.request_owner_question(self.a,self.c.pk,run.pk,rev(self.c))
        self.assertContains(self.client.get(url),'For contractual period')
        self.grant('contract',self.a,['read'])
        self.assertNotContains(self.client.get(url),'For contractual period')

    def test_owner_question_is_internal_idempotent_native_information_task(self):
        from apps.agents import contract_coverage as agent
        old=self.terms();t=self.revised_terms(old,dict(old.payload,owner_id=self.b.pk),activate=True)
        run=agent.investigate(self.a,self.c.pk,t.pk,date(2026,11,7),'F45',rev(self.c))
        task=agent.request_owner_question(self.a,self.c.pk,run.pk,rev(self.c))
        self.assertEqual(task.kind,'factory_information');self.assertEqual(task.claimed_by_id,self.b.pk)
        self.assertNotIn('findings',task.context)
        self.assertEqual(agent.request_owner_question(self.a,self.c.pk,run.pk,rev(self.c)).pk,task.pk)
        self.assertFalse(run.result['external_communication'])

    def test_second_recipient_cannot_duplicate_existing_obligation_handoff(self):
        t=self.terms();a=self.assess(t);key=a.result['obligations'][0]['key']
        cc.request_preparation(self.a,self.c.pk,a.pk,key,self.b.pk,rev(self.c))
        with self.assertRaises(ValidationError):cc.request_preparation(self.a,self.c.pk,a.pk,key,self.a.pk,rev(self.c))

    def test_direct_sql_cross_case_and_wrong_kind_terms_are_rejected(self):
        from apps.core.models import Case
        t=self.terms();other=Case.objects.create(tenant=self.c.tenant,title='Other',kind='project',synthetic=True)
        values={'case':self.c,'coverage':self.cov,'register':t.register,'contract':t.contract,'version':2,
            'payload':t.payload,'sha256':t.sha256,'evidence':t.evidence,'actor':self.a}
        for changes in [{'case':other},{'contract':t.register},{'register':t.contract}]:
            with self.assertRaises(DatabaseError),transaction.atomic():CoverageTerms.objects.create(**dict(values,**changes))
        original=t.contract;t.contract=t.register
        with self.assertRaises(ValidationError):cc.terms_access(self.a,t)
        t.contract=original

    def native_invoice_fixture(self):
        from .billing_helpers import prices,usage,prepare
        from .settlement_helpers import configured,draft,issue
        configs=prices(self.a,self.c,self.cov);u=usage(self.a,self.c,self.cov);p=prepare(self.a,self.c,self.cov,u=u)
        configured(self.a,self.c)
        e={'invoice_review':evidence(self.a,self.c,'invoice_review','Synthetic native exact invoice review')}
        i=draft(self.a,self.c,p);issued=issue(self.a,self.c,i,e)
        row={'start':'2026-10-01','end':'2026-10-31','bill_on':'2026-10-01'}
        old=self.terms(row=row,cadence='monthly')
        rule={'method':'native_invoice_v1','verifier_id':self.b.pk,'distinct_capture_actor':False}
        self.last_terms=t=self.revised_terms(old,dict(old.payload,invoice_verification=rule),activate=True)
        payload=self.payload('invoice',row,cadence='monthly',invoice_reference=i.reference,invoice_status='issued',
            invoice_period=row,verification_method='native_invoice_v1')
        src=self.source('native-invoice','invoice',payload)
        return t,src,issued,configs

    def test_native_issued_invoice_survives_unrelated_future_pricing_change(self):
        from apps.policy.services import transition
        t,src,issued,configs=self.native_invoice_fixture();self.verify(src,native=issued.pk)
        self.assertEqual(self.assess(t).result['obligations'][0]['status'],'covered')
        transition(self.a,configs[0].pk,'revoked')
        self.assertEqual(self.assess(t).result['obligations'][0]['status'],'covered')
        self.grant('native-invoice',self.a,[])
        self.assertEqual(self.assess(t).result['obligations'][0]['status'],'indeterminate')

    def test_native_invoice_wrong_usage_period_cannot_be_correlated(self):
        t,src,issued,configs=self.native_invoice_fixture()
        wrong=self.source('native-invoice','invoice',dict(src.payload,external_version='v2',invoice_period=SEPTEMBER))
        with self.assertRaises(ValidationError):self.verify(wrong,native=issued.pk)

    def test_native_stage_invoice_has_no_implicit_service_period_binding(self):
        from .helpers import signed
        from .billing_helpers import stage_policy,prepare
        from .settlement_helpers import configured,issue
        from apps.finance import invoices
        self.cov=coverage(self.a,self.c,amount_basis='gross_including_tax')
        signed_evidence=signed(self.a,self.c);stage_policy(self.a,self.c,self.cov,signed_evidence['signature'])
        p=prepare(self.a,self.c,self.cov,kind='signed_sow');configured(self.a,self.c)
        i=invoices.draft(self.a,self.c.pk,p.pk,'NATIVE-STAGE',date.fromisoformat(p.result['due_date']),rev(self.c))
        e={'invoice_review':evidence(self.a,self.c,'invoice_review','Synthetic stage review')};issued=issue(self.a,self.c,i,e)
        old=self.terms();rule={'method':'native_invoice_v1','verifier_id':self.b.pk,'distinct_capture_actor':False}
        self.last_terms=self.revised_terms(old,dict(old.payload,invoice_verification=rule),activate=True)
        payload=self.payload('invoice',ANNUAL,invoice_reference=i.reference,invoice_status='issued',invoice_period=ANNUAL,verification_method='native_invoice_v1')
        with self.assertRaises(ValidationError):self.verify(self.source('native-stage','invoice',payload),native=issued.pk)

    def test_owner_only_renewal_revalidates_original_unreceived_request_identity(self):
        t=self.terms();a=self.assess(t);key=a.result['obligations'][0]['key']
        req=cc.request_preparation(self.a,self.c.pk,a.pk,key,self.b.pk,rev(self.c))
        newer=self.revised_terms(t,dict(t.payload,owner_id=self.b.pk),activate=True);a2=self.assess(newer)
        self.assertEqual(a2.result['obligations'][0]['key'],key)
        with self.assertRaises(ValidationError):cc.receive_preparation(self.b,self.c.pk,req.pk,None,rev(self.c))
        route=cc.route_preparation(self.a,self.c.pk,req.pk,a2.pk,self.b.pk,'ready',self.decision.pk,rev(self.c))
        self.assertEqual(cc.route_preparation(self.a,self.c.pk,req.pk,a2.pk,self.b.pk,'ready',self.decision.pk,rev(self.c)).pk,route.pk)
        receipt=cc.receive_preparation(self.b,self.c.pk,req.pk,None,rev(self.c))
        self.assertEqual(receipt.payload['assessment_id'],a2.pk)
        self.assertEqual(cc.request_preparation(self.a,self.c.pk,a2.pk,key,self.b.pk,rev(self.c)).pk,req.pk)
        self.assertEqual(cc.receive_preparation(self.b,self.c.pk,req.pk,None,rev(self.c)).pk,receipt.pk)

    def test_changed_recipient_cancel_and_current_authority_preserve_single_executable_task(self):
        t=self.terms();a=self.assess(t);key=a.result['obligations'][0]['key']
        req=cc.request_preparation(self.a,self.c.pk,a.pk,key,self.b.pk,rev(self.c))
        cc.route_preparation(self.a,self.c.pk,req.pk,a.pk,self.b.pk,'cancelled',self.decision.pk,rev(self.c))
        with self.assertRaises(ValidationError):cc.receive_preparation(self.b,self.c.pk,req.pk,None,rev(self.c))
        self.grant('contract',self.a,['read'])
        with self.assertRaises(PermissionDenied):cc.route_preparation(self.a,self.c.pk,req.pk,a.pk,self.a.pk,'ready',self.decision.pk,rev(self.c))
        self.grant('contract',self.a)
        cc.route_preparation(self.a,self.c.pk,req.pk,a.pk,self.a.pk,'ready',self.decision.pk,rev(self.c))
        with self.assertRaises(PermissionDenied):cc.receive_preparation(self.b,self.c.pk,req.pk,None,rev(self.c))
        receipt=cc.receive_preparation(self.a,self.c.pk,req.pk,None,rev(self.c))
        self.assertEqual(cc.route_preparation(self.a,self.c.pk,req.pk,a.pk,self.b.pk,'ready',self.decision.pk,rev(self.c)).pk,receipt.pk)
        self.assertEqual(HumanTask.objects.filter(factory_key='coverage:'+req.operation_key).count(),1)
        self.assertEqual(CoveragePreparationReceipt.objects.count(),1)

    def test_native_invoice_void_does_not_leave_covered_reference(self):
        from .correction_helpers import configure,note,apply
        from apps.finance.models import InvoiceCorrectionAcceptance
        t,src,issued,configs=self.native_invoice_fixture();self.verify(src,native=issued.pk)
        configure(self.a,self.c)
        e={k:evidence(self.a,self.c,kind,'Synthetic explicit native correction evidence') for k,kind in
            [('cash_correction','cash_correction'),('review','financial_correction_review')]}
        correction=note(self.a,self.c,issued,e,kind='void',amount=None)
        apply(self.a,self.c,correction,e)
        self.assertTrue(InvoiceCorrectionAcceptance.objects.filter(correction=correction).exists())
        self.assertEqual(self.assess(t).result['obligations'][0]['status'],'indeterminate')

    def test_received_request_owner_only_renewal_returns_original_receipt(self):
        t=self.terms();a=self.assess(t);key=a.result['obligations'][0]['key']
        req=cc.request_preparation(self.a,self.c.pk,a.pk,key,self.b.pk,rev(self.c))
        receipt=cc.receive_preparation(self.b,self.c.pk,req.pk,None,rev(self.c))
        newer=self.revised_terms(t,dict(t.payload,owner_id=self.b.pk),activate=True);a2=self.assess(newer)
        self.assertEqual(cc.request_preparation(self.a,self.c.pk,a2.pk,key,self.b.pk,rev(self.c)).pk,req.pk)
        self.assertEqual(cc.receive_preparation(self.b,self.c.pk,req.pk,None,rev(self.c)).pk,receipt.pk)
        self.assertEqual(cc.route_preparation(self.a,self.c.pk,req.pk,a2.pk,self.a.pk,'ready',self.decision.pk,rev(self.c)).pk,receipt.pk)
        self.assertEqual(req.routes.count(),0)

    def test_new_authorised_sender_revalidates_after_original_sender_withdrawal(self):
        t=self.terms();a=self.assess(t);key=a.result['obligations'][0]['key']
        req=cc.request_preparation(self.a,self.c.pk,a.pk,key,self.b.pk,rev(self.c))
        Grant.objects.filter(user=self.a,case=self.c,action='coverage.prepare').update(active=False)
        with self.assertRaises(PermissionDenied):cc.receive_preparation(self.b,self.c.pk,req.pk,None,rev(self.c))
        cc.route_preparation(self.b,self.c.pk,req.pk,a.pk,self.b.pk,'ready',self.decision.pk,rev(self.c))
        receipt=cc.receive_preparation(self.b,self.c.pk,req.pk,None,rev(self.c))
        self.assertEqual(receipt.actor_id,self.b.pk)
        self.assertEqual(HumanTask.objects.filter(factory_key='coverage:'+req.operation_key).count(),1)

    def test_future_projection_does_not_claim_actual_due_handoff(self):
        future={'start':'2027-01-01','end':'2027-01-31','bill_on':'2027-01-01'}
        t=self.terms(row=future,cadence='monthly')
        a=cc.assess(self.a,self.c.pk,t.pk,date(2027,1,7),rev(self.c))
        self.assertEqual(a.result['basis'],'as_of_projection')
        self.assertEqual(a.result['obligations'][0]['status'],'missing_invoice')
        with self.assertRaises(ValidationError):cc.request_preparation(self.a,self.c.pk,a.pk,a.result['obligations'][0]['key'],self.b.pk,rev(self.c))
        self.assertEqual(HumanTask.objects.filter(context__purpose='coverage_preparation').count(),0)

    def test_http_reassignment_receipt_uses_current_route_recipient(self):
        t=self.terms();a=self.assess(t);key=a.result['obligations'][0]['key']
        req=cc.request_preparation(self.a,self.c.pk,a.pk,key,self.b.pk,rev(self.c))
        url=f'/cases/{self.c.pk}/finance/contract-coverage/';self.client.force_login(self.a)
        result=self.client.post(url,{'action':'route','revision':rev(self.c),'request':req.pk,'assessment':a.pk,
            'recipient_id':self.a.pk,'state':'ready','evidence':self.decision.pk})
        self.assertEqual(result.status_code,302)
        result=self.client.post(url,{'action':'receive','revision':rev(self.c),'request':req.pk,'preparation_id':''})
        self.assertEqual(result.status_code,302)
        self.assertEqual(CoveragePreparationReceipt.objects.get(request=req).actor_id,self.a.pk)
        before=rev(self.c);self.assertContains(self.client.get(url),'Received for preparation')
        self.assertEqual(rev(self.c),before)

    def test_annual_label_with_monthly_periods_requires_explicit_source_interpretation(self):
        row=SEPTEMBER
        t=self.terms(row=row,cadence='annual',active=False)
        self.assertTrue(any('period lengths conflict' in f for f in self.assess(t).result['findings']))
        with self.assertRaises(ValidationError):cc.transition(self.a,self.c.pk,t.pk,'active',self.decision.pk,rev(self.c))
        proof=evidence(self.a,self.c,'coverage_schedule_interpretation',json.dumps({'contract_source_id':t.contract_id,
            'contract_source_hash':t.contract.sha256,'mode':'explicit_source_exception','attestation':'source_explicitly_specifies_exception',
            'reason':'Synthetic annual contract expressly supplies this separate September installment; no guessed recurrence or amount'}))
        payload=dict(t.payload,schedule_interpretation={'mode':'explicit_source_exception','attestation':'source_explicitly_specifies_exception','evidence_id':proof.pk})
        explicit=self.revised_terms(t,payload,activate=True)
        self.assertEqual(self.assess(explicit).result['status'],'assessed')

    def test_private_kind_only_evidence_classification_never_requires_a_primary_key(self):
        from types import SimpleNamespace
        from apps.core.evidence_access import restricted
        with self.assertNumQueries(0):
            self.assertTrue(restricted(SimpleNamespace(kind='coverage_terms')))
            self.assertTrue(restricted(SimpleNamespace(kind='coverage_source')))
            self.assertFalse(restricted(SimpleNamespace(kind='document')))


class CoverageHTTPBootstrapTests(TestCase):
    def test_empty_bootstrap_exact_private_intake_to_human_receipt_and_recovery(self):
        from apps.finance.models import BillingCoverage,CoverageAccess,CoverageEvidenceScope
        a,c=setup_case(username='bootstrap-owner')
        recipient=get_user_model().objects.create_user(username='bootstrap-finance',password='isolated-fixture-only')
        for action in Grant.objects.filter(user=a,case=c).values_list('action',flat=True):
            Grant.objects.create(user=recipient,case=c,action=action)
        self.client.force_login(a);url=f'/cases/{c.pk}/finance/contract-coverage/'
        self.assertEqual(Evidence.objects.filter(case=c).count(),0)
        self.assertEqual(BillingCoverage.objects.count(),0);self.assertEqual(CoverageAccess.objects.count(),0)
        before=rev(c);self.assertEqual(self.client.get(url).status_code,200);self.assertEqual(rev(c),before)
        def post(action,**fields):
            result=self.client.post(url,dict(action=action,revision=rev(c),**fields))
            self.assertEqual(result.status_code,302,result.content.decode()[:2000]);return result
        def supply(refs,purposes,kind,body):
            post('evidence',references=json.dumps(refs),purposes=purposes,kind=kind,
                body=body if isinstance(body,str) else json.dumps(body),source='synthetic:http-bootstrap')
            return Evidence.objects.filter(case=c,kind=kind).latest('pk')
        # Bootstrap access evidence has no pre-existing source grant dependency.
        for reference in ['register','contract']:
            proof=supply([reference],['access'],'coverage_access','Explicit synthetic source access decision')
            for principal in [a,recipient]:
                post('grant',reference=reference,principal=principal.pk,permissions=cc.PERMISSIONS,evidence=proof.pk)
        self.assertEqual(CoverageAccess.objects.count(),4)
        # Wrong evidence purpose and missing reference permission cannot create private evidence.
        count=Evidence.objects.count()
        bad=self.client.post(url,dict(action='evidence',revision=rev(c),references=json.dumps(['register']),purposes=['capture'],
            kind='coverage_decision',body='wrong purpose',source='synthetic:http-bootstrap'))
        self.assertEqual(bad.status_code,200);self.assertEqual(Evidence.objects.count(),count)
        bad=self.client.post(url,dict(action='evidence',revision=rev(c),references=json.dumps(['ungranted-reference']),purposes=['capture'],
            kind='coverage_source',body='{}',source='synthetic:http-bootstrap'))
        self.assertEqual(bad.status_code,403);self.assertEqual(Evidence.objects.count(),count)
        # Reuse the incumbent native coverage registration UI, not a parallel customer master.
        result=self.client.post(f'/cases/{c.pk}/',dict(action='evidence',revision=rev(c),kind='billing_coverage',
            body='Synthetic authoritative register scope',source='synthetic:http-bootstrap'))
        self.assertEqual(result.status_code,302)
        legacy=Evidence.objects.get(case=c,kind='billing_coverage')
        result=self.client.post(f'/cases/{c.pk}/finance/billing/',dict(action='coverage',revision=rev(c),reference='http-service',
            customer='http-client',service='http-service',contract='http-contract',currency='NGN',amount_basis='gross_including_tax',
            from_period='2026-10',to_period='2027-09',completeness='complete',evidence=legacy.pk))
        self.assertEqual(result.status_code,302);cov=BillingCoverage.objects.get(case=c)
        sources={}
        for kind in ['register','contract']:
            payload={'system':'synthetic-existing-it','external_id':'http-'+kind,'external_version':'v1',
                'customer':cov.customer,'service':cov.service,'contract':cov.contract,'status':'current','cadence':'annual',
                'service_state':'active','start':ANNUAL['start'],'end':ANNUAL['end'],'schedule':[ANNUAL],'state_treatment':'unknown'}
            proof=supply([kind],['capture'],'coverage_source',payload)
            if kind=='register':
                before_count=CoverageSource.objects.count()
                bad=self.client.post(url,dict(action='capture',revision=rev(c),reference='contract',kind='register',
                    payload=json.dumps(payload),evidence=proof.pk))
                self.assertEqual(bad.status_code,200);self.assertEqual(CoverageSource.objects.count(),before_count)
            post('capture',reference=kind,kind=kind,payload=json.dumps(payload),evidence=proof.pk)
            sources[kind]=CoverageSource.objects.get(case=c,reference=kind)
        interpretation=supply(['contract'],['configure'],'coverage_schedule_interpretation',{
            'contract_source_id':sources['contract'].pk,'contract_source_hash':sources['contract'].sha256,
            'mode':'standard_periods','attestation':'source_schedule_matches_cadence','reason':'Synthetic explicit annual supplied period'})
        payload={'implementation':'explicit-contract-schedule/v1','review_requirement':'none','reviewer_id':None,'owner_id':None,
            'schedule_interpretation':{'mode':'standard_periods','attestation':'source_schedule_matches_cadence','evidence_id':interpretation.pk}}
        proof=supply(['register','contract'],['configure'],'coverage_terms',{
            'coverage_id':cov.pk,'register_id':sources['register'].pk,'contract_id':sources['contract'].pk,'terms':payload})
        post('draft',coverage=cov.pk,register=sources['register'].pk,contract=sources['contract'].pk,
            implementation=payload['implementation'],review_requirement='none',reviewer='',owner='',
            schedule_interpretation=json.dumps(payload['schedule_interpretation']),invoice_verification='',evidence=proof.pk)
        terms=CoverageTerms.objects.get(case=c)
        decision=supply(['register','contract'],['configure','activate'],'coverage_decision','Synthetic exact supplied interpretation lifecycle decision')
        post('validate',terms=terms.pk,evidence=decision.pk);post('activate',terms=terms.pk,evidence=decision.pk)
        post('assess',terms=terms.pk,as_of='2026-11-07');assessment=CoverageAssessment.objects.get(terms=terms)
        post('investigate',terms=terms.pk,as_of='2026-11-07',process_id='F31')
        post('request',assessment=assessment.pk,obligation_key=assessment.result['obligations'][0]['key'],recipient_id=recipient.pk)
        request=cc.CoveragePreparationRequest.objects.get(assessment=assessment)
        self.client.force_login(recipient)
        post('receive',request=request.pk,preparation_id='');post('receive',request=request.pk,preparation_id='')
        self.assertEqual(CoveragePreparationReceipt.objects.count(),1);self.assertEqual(Invoice.objects.count(),0)
        before=rev(c);self.assertContains(self.client.get(url),'Received for preparation');self.assertEqual(rev(c),before)
        self.assertEqual(CoverageEvidenceScope.objects.count(),Evidence.objects.filter(case=c,kind__startswith='coverage_').count())
        self.assertFalse(public_evidence(Evidence.objects.filter(case=c)).filter(kind__startswith='coverage_').exists())


class CoverageIdentityReviewTests(ContractCoverageTests):
    # Inherited methods are deliberately excluded from the explicit AST manifest;
    # this class supplies only the four additional identity review assertions.
    def test_register_contract_alias_rejected_by_service_and_database(self):
        t=self.terms();self.grant('contract-alias')
        proof=evidence(self.a,self.c,'coverage_source',json.dumps(t.contract.payload),reference='contract-alias')
        with self.assertRaises(ValidationError):cc.capture_source(self.a,self.c.pk,'contract-alias','contract',t.contract.payload,proof.pk,rev(self.c))
        with self.assertRaises(DatabaseError),transaction.atomic():
            CoverageSource.objects.create(case=self.c,reference='contract-alias',kind='contract',version=1,
                payload=t.contract.payload,sha256=t.contract.sha256,evidence=proof,actor=self.a)
        self.assertEqual(CoverageSource.objects.count(),2)
        self.assertEqual(cc.source_pin(t.contract),dict(system=t.contract.payload['system'],external_id=t.contract.payload['external_id'],
            external_version=t.contract.payload['external_version'],sha256=t.contract.sha256))

    def test_invoice_verification_cannot_rebind_another_source_or_period_by_sql(self):
        from apps.finance.models import CoverageInvoiceReference
        t=self.terms(row=SEPTEMBER,cadence='monthly');src=self.invoice();ref=self.verify(src)
        wrong=self.invoice(reference='another-invoice',row=ANNUAL)
        forged=CoverageInvoiceReference.objects.create(case=self.c,source=wrong,payload=ref.payload,sha256=ref.sha256,
            evidence=ref.evidence,actor=self.b)
        with self.assertRaises(ValidationError):cc.invoice_current(self.a,forged)
        self.assertEqual(self.assess(t).result['status'],'indeterminate')

    def test_canonical_identity_is_explicitly_case_scoped_without_global_authority(self):
        t=self.terms();key=cc.obligation(t,ANNUAL)
        from copy import copy
        from apps.core.models import Case
        other=Case.objects.create(tenant=self.c.tenant,title='Private other case',kind='project',synthetic=True)
        hypothetical=copy(t);hypothetical.case=other
        self.assertNotEqual(cc.obligation(hypothetical,ANNUAL),key)
        self.assertIn('no global invoice claim',self.assess(t).result['deduplication_scope'])
        # No inaccessible case details are included in the current case projection.
        self.assertNotIn(str(other.pk),json.dumps(self.assess(t).result))

    def test_consumption_revalidates_closed_source_and_terms_shapes(self):
        t=self.terms();original=t.contract.payload;t.contract.payload={'status':'current'}
        with self.assertRaises(ValidationError):cc.source_access(self.a,t.contract)
        t.contract.payload=original;original_terms=t.payload;t.payload={'implementation':'unsupported'}
        with self.assertRaises(ValidationError):cc.terms_access(self.a,t)
        t.payload=original_terms
        self.grant('malformed-source')
        bad={'status':'current'}
        proof=evidence(self.a,self.c,'coverage_source',json.dumps(bad),reference='malformed-source')
        forged=CoverageSource.objects.create(case=self.c,reference='malformed-source',version=1,kind='register',
            payload=bad,sha256=cc.digest(bad),evidence=proof,actor=self.a)
        with self.assertRaises(ValidationError):cc.source_access(self.a,forged)

    def test_authorised_same_source_reaffirmation_recovers_retired_capture_authority(self):
        from copy import copy
        t=self.terms();old=t.contract;key=cc.obligation(t,ANNUAL)
        self.grant('contract',self.a,[x for x in cc.PERMISSIONS if x!='capture'])
        self.assertEqual(self.assess(t).result['status'],'indeterminate')
        proof=cc.supply_evidence(self.b,self.c.pk,['contract'],['capture'],'coverage_source',json.dumps(old.payload),
            'synthetic:same-source-reaffirmation',rev(self.c))
        fresh=cc.capture_source(self.b,self.c.pk,'contract','contract',old.payload,proof.pk,rev(self.c))
        self.assertEqual(fresh.version,old.version+1);self.assertEqual(fresh.sha256,old.sha256)
        self.assertEqual(fresh.payload['external_version'],old.payload['external_version'])
        self.assertEqual(cc.capture_source(self.b,self.c.pk,'contract','contract',old.payload,proof.pk,rev(self.c)).pk,fresh.pk)
        hypothetical=copy(t);hypothetical.contract=fresh
        self.assertEqual(cc.obligation(hypothetical,ANNUAL),key)
        cc.source_access(self.b,fresh)

    def test_receipt_packet_cannot_claim_issuance_or_an_unrelated_route(self):
        t=self.terms();a=self.assess(t)
        request=cc.request_preparation(self.a,self.c.pk,a.pk,a.result['obligations'][0]['key'],self.b.pk,rev(self.c))
        receipt=cc.receive_preparation(self.b,self.c.pk,request.pk,None,rev(self.c));original=receipt.payload
        receipt.payload=dict(original,invoice_issued=True)
        with self.assertRaises(ValidationError):cc.receipt_identity(receipt)
        receipt.payload=dict(original,route_id=999999)
        with self.assertRaises(ValidationError):cc.receipt_identity(receipt)
        receipt.payload=original;self.assertEqual(cc.receipt_identity(receipt).pk,receipt.pk)

    def no_billing_terms(self,row=None,method='supplied_readonly_invoice_v1',active=True,treatment='no_billing_for_explicit_periods'):
        row=row or SEPTEMBER
        period={'start':row['start'],'end':row['end']}
        sources={}
        for kind in ['register','contract']:
            previous=CoverageSource.objects.filter(case=self.c,reference=kind).order_by('-version').first()
            payload=self.payload(kind,row,cadence='unknown',service_state='free',schedule=[],nonbilling_periods=[period],
                state_treatment=treatment,external_version='v2' if previous else 'v1')
            sources[kind]=self.source(kind,kind,payload)
        self.decision=evidence(self.a,self.c,'coverage_decision','Synthetic explicit no-billing interpretation, not debt waiver')
        proof=evidence(self.a,self.c,'coverage_schedule_interpretation',json.dumps({
            'contract_source_id':sources['contract'].pk,'contract_source_hash':sources['contract'].sha256,
            'mode':'explicit_no_billing_periods','attestation':'source_explicitly_specifies_no_billing',
            'reason':'Synthetic owner-supplied no-billing choice for exactly this period; no proration or existing debt change'}))
        payload={'implementation':'explicit-contract-schedule/v1','review_requirement':'none','reviewer_id':None,'owner_id':None,
            'schedule_interpretation':{'mode':'explicit_no_billing_periods','attestation':'source_explicitly_specifies_no_billing','evidence_id':proof.pk},
            'invoice_verification':{'method':method,'verifier_id':self.b.pk,'distinct_capture_actor':False}}
        declaration=evidence(self.a,self.c,'coverage_terms',json.dumps({'coverage_id':self.cov.pk,'register_id':sources['register'].pk,
            'contract_id':sources['contract'].pk,'terms':payload}))
        t=cc.draft_terms(self.a,self.c.pk,self.cov.pk,sources['register'].pk,sources['contract'].pk,payload,declaration.pk,rev(self.c))
        cc.transition(self.a,self.c.pk,t.pk,'validated',self.decision.pk,rev(self.c))
        if active:cc.transition(self.a,self.c.pk,t.pk,'active',self.decision.pk,rev(self.c))
        self.last_terms=t;return t

    def test_explicit_no_billing_period_is_not_paid_covered_or_debt_waived(self):
        t=self.no_billing_terms();a=self.assess(t)
        self.assertEqual(a.result['status'],'assessed');self.assertEqual(a.result['obligations'],[])
        self.assertEqual(a.result['nonbilling_periods'],[{'start':SEPTEMBER['start'],'end':SEPTEMBER['end'],
            'status':'no_billing_obligation','invoice_refs':[]}])
        self.assertFalse(a.result['paid']);self.assertFalse(a.result['debt_waived']);self.assertFalse(a.result['invoice_issued'])
        with self.assertRaises(ValidationError):cc.request_preparation(self.a,self.c.pk,a.pk,'not-an-obligation',self.b.pk,rev(self.c))
        self.assertEqual(Invoice.objects.count(),0)
        self.client.force_login(self.a)
        self.assertContains(self.client.get(f'/cases/{self.c.pk}/finance/contract-coverage/'),'Existing debt is not waived')

    def test_no_billing_declaration_exposes_existing_native_invoice_without_erasing_debt(self):
        from decimal import Decimal
        from apps.finance.models import InvoiceCorrectionAcceptance,CashReceipt
        old,src,issued,configs=self.native_invoice_fixture();self.verify(src,native=issued.pk)
        row=src.payload['invoice_period'];t=self.no_billing_terms(row,method='native_invoice_v1')
        self.verify(src,native=issued.pk)
        result=self.assess(t).result
        self.assertEqual(result['status'],'indeterminate');self.assertEqual(result['obligations'],[])
        self.assertEqual(result['nonbilling_periods'][0]['status'],'conflict')
        self.assertTrue(any('without waiving existing debt' in f for f in result['findings']))
        issued.refresh_from_db();self.assertEqual(issued.invoice.amount,Decimal('32.25'))
        self.assertEqual(InvoiceIssue.objects.count(),1);self.assertEqual(InvoiceCorrectionAcceptance.objects.count(),0)
        self.assertEqual(CashReceipt.objects.count(),0);self.assertFalse(result['debt_waived'])

    def test_unknown_state_treatment_does_not_infer_no_billing(self):
        t=self.no_billing_terms(active=False,treatment='unknown')
        with self.assertRaises(ValidationError):cc.transition(self.a,self.c.pk,t.pk,'active',self.decision.pk,rev(self.c))
        result=self.assess(t).result
        self.assertEqual(result['status'],'indeterminate');self.assertEqual(result['nonbilling_periods'],[])
        self.assertEqual(result['obligations'],[])

    def test_invalid_interpretation_reference_never_cites_other_private_source_metadata(self):
        from apps.agents import contract_coverage as agent
        t=self.terms(active=False)
        other=self.source('private-contract','contract',self.payload('contract',external_id='private-other-contract'))
        hidden=evidence(self.a,self.c,'coverage_schedule_interpretation',json.dumps({'contract_source_id':other.pk,
            'contract_source_hash':other.sha256,'mode':'standard_periods','attestation':'source_schedule_matches_cadence',
            'reason':'Private synthetic source metadata must not cross reference scopes'}))
        self.grant('private-contract',self.a,[])
        payload=dict(t.payload,schedule_interpretation={'mode':'standard_periods','attestation':'source_schedule_matches_cadence','evidence_id':hidden.pk})
        wrong=self.revised_terms(t,payload)
        run=agent.investigate(self.a,self.c.pk,wrong.pk,date(2026,11,7),'F45',rev(self.c))
        self.assertEqual(run.result['assessment']['status'],'indeterminate')
        self.assertNotIn(hidden.pk,[row['id'] for row in run.result['citations']])
        self.assertNotIn(hidden.sha256,json.dumps(run.result))

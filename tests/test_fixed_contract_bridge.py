"""Synthetic annual/fixed exact-source bridge, not PSL rates or live IT integration."""
import copy
import json
from datetime import date
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import DatabaseError, transaction, connection
from django.urls import reverse
from apps.finance import fixed_charge as fixed, contract_coverage as cc, billing, invoices, invoice_delivery
from apps.finance.models import (BillingPreparation, CoverageFixedCharge, CoverageNativePreparation,
    CoveragePreparationReceipt, Invoice, InvoiceIssue, InvoiceDelivery, InvoiceReview)
from apps.agents import contract_coverage as agents
from apps.core.evidence_access import public_evidence, public_agent_runs
from apps.core.models import Evidence
from apps.agents.models import AgentRun
from apps.identity.models import Grant
from adapters.factory_invoice_preparation import NativeFixedContractPreparationAdapter
from adapters.invoices import TimeoutAfterInvoiceAccept
from .test_contract_coverage import ContractCoverageTests, ANNUAL
from .billing_helpers import coverage, prices, evidence as native_evidence
from .settlement_helpers import configured
from .helpers import rev


class FixedContractBridgeTests(ContractCoverageTests):
    def setUp(self):
        super().setUp()
        self.cov = coverage(self.a, self.c, reference='fixed-gross', amount_basis='gross_including_tax',
            from_period='2026-09', to_period='2027-09')

    def request(self, native=False):
        terms = self.terms()
        if native:
            payload = copy.deepcopy(terms.payload)
            payload['invoice_verification']['method'] = 'native_invoice_v1'
            terms = self.revised_terms(terms, payload=payload, activate=True)
            self.last_terms = terms
        assessment = self.assess(terms)
        return cc.request_preparation(self.a, self.c.pk, assessment.pk,
            assessment.result['obligations'][0]['key'], self.b.pk, rev(self.c))

    def charge(self, request, *, assessment=None, author=None, **changes):
        author=author or self.a
        payload = {'implementation':'exact-fixed-charge/v1', 'period':ANNUAL,
            'currency':self.cov.currency, 'amount':'1200.00', 'amount_basis':self.cov.amount_basis,
            'method':'supplied_gross_total', 'decimal_places':2, 'tax_configuration_id':None,
            'due_date':'2026-11-20', 'rule_reference':'synthetic-contract-section-4',
            'tax_treatment_reference':'synthetic-contract-gross-inclusive'}
        payload.update(changes)
        assessment = assessment or cc.preparation_route(request)['assessment']
        proof = cc.supply_evidence(author,self.c.pk,[assessment.terms.register.reference,assessment.terms.contract.reference],['configure'],
            'coverage_fixed_charge',json.dumps({'request_id':request.pk,'assessment_id':assessment.pk,'charge':payload}),
            'synthetic:fixed-contract-fixture',rev(self.c))
        return fixed.supply_charge(author,self.c.pk,request.pk,payload,proof.pk,rev(self.c),assessment_id=assessment.pk)

    def prepared(self, **changes):
        request=self.request(native=True); charge=self.charge(request,**changes)
        prep=fixed.prepare(self.b,self.c.pk,charge.pk,rev(self.c))
        return request,charge,prep

    def issued(self, prep, adapter=None, reference='SYNTHETIC-ANNUAL-01'):
        configured(self.a,self.c)
        invoice=invoices.draft(self.a,self.c.pk,prep.pk,reference,date(2026,11,20),rev(self.c))
        proof=native_evidence(self.a,self.c,'invoice_review','Synthetic exact annual packet reviewed')
        invoices.review(self.a,self.c.pk,invoice.pk,'Finance','approve',proof.pk,'Explicit synthetic packet review',rev(self.c))
        job=invoices.reserve(self.a,self.c.pk,invoice.pk,'issue','Finance',rev(self.c))
        invoice_delivery.run_once(adapter=adapter,case_id=self.c.pk,job_id=job.pk)
        return invoice,job

    def test_fixed_annual_agent_human_native_issue_period_and_delivery(self):
        request=self.request(native=True);charge=self.charge(request)
        run=agents.investigate_charge(self.b,self.c.pk,charge.pk,rev(self.c))
        self.assertEqual(run.result['preparation_preview']['total'],'1200.00')
        self.assertFalse(run.result['approval_granted']);self.assertEqual(Invoice.objects.count(),0)
        result=NativeFixedContractPreparationAdapter().prepare(self.b,self.c.pk,charge.pk,rev(self.c))
        prep=BillingPreparation.objects.get(pk=result['preparation_id'])
        self.assertEqual(prep.result['lines'][0]['tax'],None)
        self.assertEqual(prep.result['total'],'1200.00');self.assertEqual(prep.result['due_date'],'2026-11-20')
        invoice,job=self.issued(prep);issue=InvoiceIssue.objects.get(invoice=invoice)
        self.assertEqual(invoice.payload['contract_period'],ANNUAL)
        self.assertEqual(invoice.amount,1200);self.assertEqual(InvoiceIssue.objects.count(),1)
        src=self.source('invoice-source','invoice',self.payload('invoice',ANNUAL,invoice_reference=invoice.reference,invoice_status='issued',invoice_period=ANNUAL,verification_method='native_invoice_v1'))
        ref=self.verify(src,native=issue.pk)
        self.assertEqual(self.assess(self.last_terms).result['obligations'][0]['status'],'covered')
        invoices.reserve(self.a,self.c.pk,invoice.pk,'deliver','Finance',rev(self.c));invoice_delivery.run_once(case_id=self.c.pk)
        self.assertEqual(InvoiceDelivery.objects.get(invoice=invoice).payload['contract_period'],ANNUAL)
        cc.invoice_current(self.a,ref)
        Grant.objects.filter(case=self.c,user=self.a,action='finance.invoice.review').update(active=False)
        Grant.objects.filter(case=self.c,user=self.b,action='finance.billing.prepare').update(active=False)
        cc.invoice_current(self.a,ref)  # Historical exact issue is not reauthorised.

    def test_fixed_acknowledgement_late_binding_and_idempotent_receipt_lookup(self):
        request=self.request();old=cc.receive_preparation(self.b,self.c.pk,request.pk,None,rev(self.c))
        original=copy.deepcopy(old.payload);charge=self.charge(request)
        prep=fixed.prepare(self.b,self.c.pk,charge.pk,rev(self.c))
        same=fixed.prepare(self.b,self.c.pk,charge.pk,rev(self.c))
        self.assertEqual(prep.pk,same.pk);self.assertEqual(CoverageNativePreparation.objects.count(),1)
        old.refresh_from_db();self.assertEqual(old.payload,original);self.assertIsNone(old.preparation_id)
        self.assertEqual(fixed.recovered(self.b,prep).receipt_id,old.pk)

    def test_fixed_unknown_amount_or_due_date_holds_only_preparation(self):
        request,charge,prep=self.prepared(amount=None,due_date=None)
        self.assertEqual(prep.result['status'],'held');self.assertIsNone(prep.result['total'])
        self.assertEqual(CoveragePreparationReceipt.objects.count(),1)
        with self.assertRaises(ValidationError):invoices.draft(self.a,self.c.pk,prep.pk,'UNKNOWN',None,rev(self.c))
        self.assertEqual(Invoice.objects.count(),0)
        corrected=self.charge(request)
        new=fixed.prepare(self.b,self.c.pk,corrected.pk,rev(self.c))
        self.assertEqual(new.result['status'],'prepared');self.assertNotEqual(prep.pk,new.pk)
        self.assertEqual(CoveragePreparationReceipt.objects.count(),1)

    def test_fixed_net_uses_exact_existing_tax_policy_once(self):
        self.cov=coverage(self.a,self.c,reference='fixed-net',amount_basis='net_exclusive',from_period='2026-09',to_period='2027-09')
        method=prices(self.a,self.c,self.cov)[1]
        request=self.request();charge=self.charge(request,amount='100',method='configured_net_tax_v1',tax_configuration_id=method.pk)
        prep=fixed.prepare(self.b,self.c.pk,charge.pk,rev(self.c))
        self.assertEqual(prep.result['total'],'107.50');self.assertEqual(prep.result['lines'][0]['tax'],'7.50')
        invoice,job=self.issued(prep);self.assertEqual(InvoiceIssue.objects.get(invoice=invoice).payload['amount'],'107.50')

    def test_fixed_gross_never_double_taxes_and_precision_never_guessed(self):
        request=self.request()
        from .billing_helpers import policy, FIXTURE
        method_data=json.loads(FIXTURE.read_text())['arithmetic']
        oracle=native_evidence(self.a,self.c,'billing_oracle',json.dumps(method_data['oracles']))
        method_data['oracle_evidence_id']=oracle.pk
        method=policy(self.a,self.c,'D08.tax_tier_rounding_rules',method_data)
        gross=self.charge(request)
        gross_prep=fixed.prepare(self.b,self.c.pk,gross.pk,rev(self.c))
        self.assertEqual(gross_prep.result['total'],'1200.00')
        self.assertIsNone(gross_prep.result['lines'][0]['tax'])
        bad=self.charge(request,tax_configuration_id=method.pk)
        prep=fixed.prepare(self.b,self.c.pk,bad.pk,rev(self.c))
        self.assertEqual(prep.result['status'],'held')
        bad=self.charge(request,amount='1200.001')
        prep=fixed.prepare(self.b,self.c.pk,bad.pk,rev(self.c));self.assertIsNone(prep.result['total'])
        self.assertIn('precision',' '.join(prep.result['findings']))

    def test_fixed_period_and_currency_substitution_rejected(self):
        request=self.request()
        for payload in [{'period':dict(ANNUAL,end='2027-08-30')},{'currency':'USD'}]:
            with self.assertRaises((ValidationError,DatabaseError)),transaction.atomic():self.charge(request,**payload)
        self.assertEqual(CoverageFixedCharge.objects.count(),0)

    def test_fixed_bill_date_is_not_due_date_and_exact_review_required(self):
        request,charge,prep=self.prepared()
        with self.assertRaises(ValidationError):invoices.draft(self.a,self.c.pk,prep.pk,'BAD-DUE',date(2026,10,1),rev(self.c))
        configured(self.a,self.c)
        invoice=invoices.draft(self.a,self.c.pk,prep.pk,'EXACT-DUE',date(2026,11,20),rev(self.c))
        with self.assertRaises(ValidationError):invoices.reserve(self.a,self.c.pk,invoice.pk,'issue','Finance',rev(self.c))
        self.assertEqual(InvoiceIssue.objects.count(),0)

    def test_fixed_corrected_amount_has_same_obligation_and_cannot_reissue(self):
        request,charge,prep=self.prepared();invoice,job=self.issued(prep)
        replacement=self.charge(request,amount='1400.00')
        self.assertEqual(fixed.obligation(charge),fixed.obligation(replacement))
        with self.assertRaises(ValidationError):fixed.prepare(self.b,self.c.pk,replacement.pk,rev(self.c))
        with self.assertRaises(ValidationError):invoices.draft(self.a,self.c.pk,prep.pk,'SECOND',date(2026,11,20),rev(self.c))
        self.assertEqual(InvoiceIssue.objects.count(),1)

    def test_fixed_source_change_blocks_new_effect_but_receipt_recovery_retains_history(self):
        request,charge,prep=self.prepared();before=copy.deepcopy(prep.snapshot)
        self.source('contract','contract',dict(self.last_terms.contract.payload,external_version='v2',status='withdrawn'))
        with self.assertRaises(ValidationError):billing.ensure_current(prep)
        self.assertEqual(fixed.recovered(self.b,prep).preparation_id,prep.pk)
        prep.refresh_from_db();self.assertEqual(prep.snapshot,before)
        self.assertEqual(InvoiceIssue.objects.count(),0)

    def test_fixed_unknown_effect_lookup_survives_later_permission_revocation(self):
        request,charge,prep=self.prepared();invoice,job=self.issued(prep,TimeoutAfterInvoiceAccept())
        job.refresh_from_db();self.assertEqual(job.status,'unknown')
        self.assertEqual(InvoiceIssue.objects.count(),1)
        self.grant('contract',self.b,[])
        Grant.objects.filter(case=self.c,user=self.a,action='finance.invoice.issue').update(active=False)
        invoice_delivery.run_once(case_id=self.c.pk,job_id=job.pk,lookup_only=True)
        job.refresh_from_db();self.assertEqual(job.status,'confirmed');self.assertEqual(InvoiceIssue.objects.count(),1)

    def test_fixed_private_authority_is_current_and_generic_runs_do_not_leak(self):
        request,charge,prep=self.prepared()
        run=agents.investigate_charge(self.b,self.c.pk,charge.pk,rev(self.c))
        self.assertFalse(public_evidence(Evidence.objects.all()).filter(pk=charge.evidence_id).exists())
        self.assertFalse(public_agent_runs(AgentRun.objects.all()).filter(pk=run.pk).exists())
        self.grant('contract',self.b,[])
        for call in [lambda:fixed.recovered(self.b,prep),lambda:agents.investigate_charge(self.b,self.c.pk,charge.pk,rev(self.c)),lambda:billing.ensure_current(prep)]:
            with self.assertRaises((PermissionDenied,ValidationError)):call()
        self.client.force_login(self.b)
        for name in ['finance_contract_coverage','finance_billing','finance_settlement']:
            response=self.client.get(reverse(name,args=[self.c.pk]))
            if response.status_code==200:self.assertNotContains(response,'synthetic-contract-section-4')
            else:self.assertEqual(response.status_code,403)

    def test_fixed_native_http_commands_and_get_are_read_only(self):
        request=self.request();charge=self.charge(request)
        self.client.force_login(self.b);url=reverse('finance_contract_coverage',args=[self.c.pk])
        before=(rev(self.c),BillingPreparation.objects.count(),AgentRun.objects.count())
        response=self.client.get(url);self.assertEqual(response.status_code,200)
        self.assertEqual(before,(rev(self.c),BillingPreparation.objects.count(),AgentRun.objects.count()))
        response=self.client.post(url,{'action':'fixed_investigate','charge':charge.pk,'revision':rev(self.c)})
        self.assertEqual(response.status_code,302)
        response=self.client.post(url,{'action':'fixed_prepare','charge':charge.pk,'revision':rev(self.c)})
        self.assertEqual(response.status_code,302);prep=BillingPreparation.objects.get(kind='fixed_contract')
        response=self.client.post(url,{'action':'fixed_recover','preparation':prep.pk,'revision':rev(self.c)})
        self.assertEqual(response.status_code,302);self.assertEqual(Invoice.objects.count(),0)
        response=self.client.get(url);self.assertContains(response,'Committed receipt')

    def test_fixed_direct_sql_scope_result_and_key_forgery_are_rejected(self):
        request,charge,prep=self.prepared()
        attrs={f.name:getattr(prep,f.name) for f in prep._meta.fields if f.name not in ['id','created_at']}
        variants=[]
        for change in [{'kind':'usage'},{'fixed_charge':None},{'actor':self.a}]:variants.append(dict(attrs,**change))
        forged=copy.deepcopy(prep.result);forged['total']='1.00';variants.append(dict(attrs,result=forged))
        snap=copy.deepcopy(prep.snapshot);snap['native_obligation']='0'*64;variants.append(dict(attrs,snapshot=snap))
        for n,values in enumerate(variants):
            values['operation_key']=str(n)*64
            with self.assertRaises(DatabaseError),transaction.atomic():BillingPreparation.objects.create(**values)
        for model in [CoverageFixedCharge,CoverageNativePreparation]:
            with self.assertRaises(DatabaseError),transaction.atomic():model.objects.all().update(actor=self.a)
        self.assertEqual(BillingPreparation.objects.filter(kind='fixed_contract').count(),1)

    def test_fixed_direct_sql_invoice_and_review_without_lineage_rejected(self):
        request,charge,prep=self.prepared();configured(self.a,self.c)
        invoice=invoices.draft(self.a,self.c.pk,prep.pk,'EXACT',date(2026,11,20),rev(self.c))
        attrs={f.name:getattr(invoice,f.name) for f in invoice._meta.fields if f.name not in ['id','created_at']}
        attrs.update(reference='FORGED',version=2,obligation_key='0'*64)
        with self.assertRaises(DatabaseError),transaction.atomic():Invoice.objects.create(**attrs)
        proof=native_evidence(self.a,self.c,'invoice_review','Explicit fixture')
        with self.assertRaises(DatabaseError),transaction.atomic():InvoiceReview.objects.create(invoice=invoice,role='Finance',verdict='approve',authority={},publication_packet={},evidence=proof,note='Forged',actor=self.a)
        self.assertEqual(InvoiceIssue.objects.count(),0)

    def test_fixed_mixed_billed_and_no_billing_exact_intervals(self):
        # The declaration explicitly supplies a billable period and a separate no-billing interval.
        # No zero invoice, proration, implied service-state change or recurring period is created.
        billed={'start':'2026-10-01','end':'2027-03-31','bill_on':'2026-10-01'}
        no_bill={'start':'2027-04-01','end':'2027-09-30'}
        for kind in ['register','contract']:
            self.source(kind,kind,self.payload(kind,cadence='explicit',schedule=[billed],nonbilling_periods=[no_bill],state_treatment='explicit_mixed_periods'))
        from .test_contract_coverage import evidence
        register=cc.CoverageSource.objects.get(reference='register');contract=cc.CoverageSource.objects.get(reference='contract')
        mode='explicit_mixed_periods';attestation='source_explicitly_specifies_mixed_periods'
        proof=evidence(self.a,self.c,'coverage_schedule_interpretation',json.dumps({'contract_source_id':contract.pk,'contract_source_hash':contract.sha256,'mode':mode,'attestation':attestation,'reason':'Exact synthetic bill/no-bill declaration'}))
        payload={'implementation':'explicit-contract-schedule/v1','review_requirement':'none','reviewer_id':None,'owner_id':None,
            'schedule_interpretation':{'mode':mode,'attestation':attestation,'evidence_id':proof.pk}}
        proof=evidence(self.a,self.c,'coverage_terms',json.dumps({'coverage_id':self.cov.pk,'register_id':register.pk,'contract_id':contract.pk,'terms':payload}))
        terms=cc.draft_terms(self.a,self.c.pk,self.cov.pk,register.pk,contract.pk,payload,proof.pk,rev(self.c))
        decision=evidence(self.a,self.c,'coverage_decision','Exact synthetic activation')
        cc.transition(self.a,self.c.pk,terms.pk,'validated',decision.pk,rev(self.c));cc.transition(self.a,self.c.pk,terms.pk,'active',decision.pk,rev(self.c))
        assessment=self.assess(terms);self.assertEqual(len(assessment.result['obligations']),1)
        self.assertEqual(assessment.result['nonbilling_periods'][0]['status'],'no_billing_obligation')
        req=cc.request_preparation(self.a,self.c.pk,assessment.pk,assessment.result['obligations'][0]['key'],self.b.pk,rev(self.c))
        charge=self.charge(req,period=billed,amount=None)
        prep=fixed.prepare(self.b,self.c.pk,charge.pk,rev(self.c));self.assertEqual(prep.result['status'],'held')
        self.assertFalse(assessment.result['debt_waived'])

    def test_fixed_revised_source_version_bill_date_and_amount_do_not_duplicate_issue(self):
        request,charge,prep=self.prepared();invoice,job=self.issued(prep)
        row=dict(ANNUAL,bill_on='2026-10-03')
        # Re-capture both authoritative source versions explicitly. The service period is unchanged.
        for kind in ['register','contract']:
            old=getattr(self.last_terms,kind)
            self.source(kind,kind,dict(old.payload,external_version='v2',schedule=[row]))
        from .test_contract_coverage import evidence
        register=cc.CoverageSource.objects.filter(reference='register').order_by('-version').first()
        contract=cc.CoverageSource.objects.filter(reference='contract').order_by('-version').first()
        interpretation=evidence(self.a,self.c,'coverage_schedule_interpretation',json.dumps({
            'contract_source_id':contract.pk,'contract_source_hash':contract.sha256,
            'mode':'standard_periods','attestation':'source_schedule_matches_cadence','reason':'Explicit corrected source version'}))
        payload=copy.deepcopy(self.last_terms.payload);payload['schedule_interpretation']['evidence_id']=interpretation.pk
        proof=evidence(self.a,self.c,'coverage_terms',json.dumps({'coverage_id':self.cov.pk,'register_id':register.pk,'contract_id':contract.pk,'terms':payload}))
        terms=cc.draft_terms(self.a,self.c.pk,self.cov.pk,register.pk,contract.pk,payload,proof.pk,rev(self.c))
        cc.transition(self.a,self.c.pk,terms.pk,'validated',self.decision.pk,rev(self.c))
        cc.transition(self.a,self.c.pk,terms.pk,'active',self.decision.pk,rev(self.c))
        assessment=self.assess(terms)
        req=cc.request_preparation(self.a,self.c.pk,assessment.pk,assessment.result['obligations'][0]['key'],self.b.pk,rev(self.c))
        self.assertNotEqual(request.obligation_key,req.obligation_key)
        new_charge=self.charge(req,period=row,amount='1250.00')
        self.assertEqual(fixed.obligation(charge),fixed.obligation(new_charge))
        with self.assertRaises(ValidationError):fixed.prepare(self.b,self.c.pk,new_charge.pk,rev(self.c))
        self.assertEqual(InvoiceIssue.objects.count(),1)

    def test_fixed_direct_sql_current_grant_revocation_blocks_new_preparation(self):
        request,charge,prep=self.prepared()
        attrs={f.name:getattr(prep,f.name) for f in prep._meta.fields if f.name not in ['id','created_at']}
        attrs['operation_key']='f'*64
        self.grant('contract',self.b,['read'])
        with self.assertRaises(DatabaseError),transaction.atomic():BillingPreparation.objects.create(**attrs)
        self.assertEqual(fixed.recovered(self.b,prep).preparation_id,prep.pk)

    def test_fixed_supplied_net_tax_binding_replacement_requires_rebuild(self):
        self.cov=coverage(self.a,self.c,reference='fixed-net',amount_basis='net_exclusive',from_period='2026-09',to_period='2027-09')
        method=prices(self.a,self.c,self.cov)[1];request=self.request()
        charge=self.charge(request,amount='100',method='configured_net_tax_v1',tax_configuration_id=method.pk)
        prep=fixed.prepare(self.b,self.c.pk,charge.pk,rev(self.c))
        newer=prices(self.a,self.c,self.cov)[1]
        with self.assertRaises(ValidationError):billing.ensure_current(prep)
        old=fixed.prepare(self.b,self.c.pk,charge.pk,rev(self.c))
        self.assertEqual(old.result['status'],'held');self.assertIsNone(old.result['total'])
        replacement=self.charge(request,amount='100',method='configured_net_tax_v1',tax_configuration_id=newer.pk)
        new=fixed.prepare(self.b,self.c.pk,replacement.pk,rev(self.c));self.assertEqual(new.result['total'],'107.50')

    def test_fixed_received_request_can_bind_current_same_source_interpretation_without_rewriting_receipt(self):
        request=self.request();receipt=cc.receive_preparation(self.b,self.c.pk,request.pk,None,rev(self.c))
        original=copy.deepcopy(receipt.payload)
        old=self.last_terms;payload=copy.deepcopy(old.payload);payload['owner_id']=self.a.pk
        current=self.revised_terms(old,payload=payload,activate=True);assessment=self.assess(current)
        self.assertEqual(assessment.result['obligations'][0]['key'],request.obligation_key)
        charge=self.charge(request,assessment=assessment)
        prep=fixed.prepare(self.b,self.c.pk,charge.pk,rev(self.c))
        self.assertEqual(prep.result['status'],'prepared')
        self.assertEqual(prep.fixed_charge.assessment_id,assessment.pk)
        receipt.refresh_from_db();self.assertEqual(receipt.payload,original)
        self.assertEqual(fixed.recovered(self.b,prep).receipt_id,receipt.pk)

    def test_fixed_unreceived_request_cannot_bypass_explicit_routing_revalidation(self):
        request=self.request();old=self.last_terms;payload=copy.deepcopy(old.payload);payload['owner_id']=self.a.pk
        current=self.revised_terms(old,payload=payload,activate=True);assessment=self.assess(current)
        with self.assertRaises(ValidationError):self.charge(request,assessment=assessment)
        self.assertEqual(CoverageFixedCharge.objects.count(),0)
        cc.route_preparation(self.a,self.c.pk,request.pk,assessment.pk,self.b.pk,'ready',self.decision.pk,rev(self.c))
        charge=self.charge(request,assessment=assessment)
        self.assertEqual(fixed.prepare(self.b,self.c.pk,charge.pk,rev(self.c)).result['status'],'prepared')

    def test_fixed_direct_sql_revoked_case_read_cannot_use_still_present_reference_grants(self):
        request,charge,prep=self.prepared()
        attrs={f.name:getattr(prep,f.name) for f in prep._meta.fields if f.name not in ['id','created_at']}
        attrs['operation_key']='e'*64
        Grant.objects.filter(case=self.c,user=self.b,action='coverage.receive').update(active=False)
        with self.assertRaises(DatabaseError),transaction.atomic():BillingPreparation.objects.create(**attrs)

    def test_fixed_remote_mock_receipt_only_lookup_after_unknown_never_redispatches(self):
        from adapters.invoices import InternalInvoiceAdapter
        from apps.finance.models import InvoiceJob
        class ExternalBoundaryMock(InternalInvoiceAdapter):
            observed=None
            calls=0
            def deliver(self,pk,fence):
                job,value=invoice_delivery.dispatch_context(pk,fence)
                self.calls+=1
                binding={'payload':job.invoice.payload,'destination':value['adapter']['recipient_id'],'target':job.invoice_id,'intent':value}
                self.observed={'environment':'synthetic_mock','operation_key':job.operation_key,'payload':job.invoice.payload,
                    'destination':binding['destination'],'fingerprint':billing.digest(binding)}
                raise TimeoutError('Synthetic provider accepted; local receipt not yet committed')
            def lookup(self,job):
                if not self.observed:return None
                invoice_delivery.record_accepted_mock(job.pk,job.fence,self.observed)
                return super().lookup(job)
        request,charge,prep=self.prepared();adapter=ExternalBoundaryMock()
        invoice,job=self.issued(prep,adapter);job.refresh_from_db()
        self.assertEqual(job.status,'unknown');self.assertEqual(InvoiceIssue.objects.count(),0)
        Grant.objects.filter(case=self.c,user=self.a,action='finance.invoice.issue').update(active=False)
        self.grant('contract',self.b,[])
        invoice_delivery.run_once(adapter=adapter,case_id=self.c.pk,job_id=job.pk,lookup_only=True)
        job.refresh_from_db();self.assertEqual(job.status,'confirmed')
        self.assertEqual(InvoiceIssue.objects.count(),1);self.assertEqual(adapter.calls,1)

    def changed_period(self, row):
        from .test_contract_coverage import evidence
        for kind in ['register','contract']:
            old=getattr(self.last_terms,kind)
            self.source(kind,kind,dict(old.payload,external_version='corrected-v2',schedule=[row]))
        register=cc.CoverageSource.objects.filter(reference='register').order_by('-version').first()
        contract=cc.CoverageSource.objects.filter(reference='contract').order_by('-version').first()
        proof=evidence(self.a,self.c,'coverage_schedule_interpretation',json.dumps({
            'contract_source_id':contract.pk,'contract_source_hash':contract.sha256,'mode':'explicit_source_exception',
            'attestation':'source_explicitly_specifies_exception','reason':'Source explicitly replaces the period; no proration calculation'}))
        payload=copy.deepcopy(self.last_terms.payload)
        payload['schedule_interpretation']={'mode':'explicit_source_exception','attestation':'source_explicitly_specifies_exception','evidence_id':proof.pk}
        proof=evidence(self.a,self.c,'coverage_terms',json.dumps({'coverage_id':self.cov.pk,'register_id':register.pk,'contract_id':contract.pk,'terms':payload}))
        terms=cc.draft_terms(self.a,self.c.pk,self.cov.pk,register.pk,contract.pk,payload,proof.pk,rev(self.c))
        cc.transition(self.a,self.c.pk,terms.pk,'validated',self.decision.pk,rev(self.c))
        cc.transition(self.a,self.c.pk,terms.pk,'active',self.decision.pk,rev(self.c))
        assessment=self.assess(terms)
        request=cc.request_preparation(self.a,self.c.pk,assessment.pk,assessment.result['obligations'][0]['key'],self.b.pk,rev(self.c))
        return self.charge(request,period=row,amount='1250.00')

    def test_fixed_overlapping_corrected_period_holds_without_erasing_original_issue(self):
        request,charge,prep=self.prepared();invoice,job=self.issued(prep)
        issued=InvoiceIssue.objects.get(invoice=invoice);original=copy.deepcopy(issued.payload)
        new=self.changed_period(dict(ANNUAL,end='2027-08-31'))
        self.assertNotEqual(fixed.obligation(charge),fixed.obligation(new))
        self.assertEqual(fixed.identity_hash(fixed.identity(charge)),fixed.identity_hash(fixed.identity(new)))
        with self.assertRaisesMessage(ValidationError,'overlaps'):fixed.prepare(self.b,self.c.pk,new.pk,rev(self.c))
        snapshot,result=fixed.inputs(self.b,new)
        with self.assertRaises(DatabaseError),transaction.atomic():
            BillingPreparation.objects.create(case=self.c,coverage=self.cov,fixed_charge=new,kind='fixed_contract',snapshot=snapshot,result=result,operation_key='a'*64,actor=self.b)
        issued.refresh_from_db();self.assertEqual(issued.payload,original);self.assertEqual(InvoiceIssue.objects.count(),1)

    def test_fixed_overlapping_unknown_original_effect_requires_receipt_lookup_first(self):
        from adapters.invoices import InternalInvoiceAdapter
        class UncertainProvider(InternalInvoiceAdapter):
            def deliver(self,pk,fence):raise TimeoutError('Synthetic uncertain external effect')
        request,charge,prep=self.prepared();invoice,job=self.issued(prep,UncertainProvider())
        job.refresh_from_db();self.assertEqual(job.status,'unknown');self.assertEqual(InvoiceIssue.objects.count(),0)
        new=self.changed_period(dict(ANNUAL,end='2027-08-31'))
        with self.assertRaisesMessage(ValidationError,'unresolved'):fixed.prepare(self.b,self.c.pk,new.pk,rev(self.c))
        self.assertEqual(CoverageNativePreparation.objects.count(),1)

    def test_fixed_unknown_rule_and_tax_treatment_hold_without_defaulting(self):
        request,charge,prep=self.prepared(rule_reference=None,tax_treatment_reference=None)
        self.assertEqual(prep.result['status'],'held');self.assertIsNone(prep.result['total'])
        self.assertIn('tax treatment',' '.join(prep.result['findings']))
        attrs={f.name:getattr(prep,f.name) for f in prep._meta.fields if f.name not in ['id','created_at']}
        attrs.update(operation_key='d'*64,result=dict(prep.result,invoice_issued=True))
        with self.assertRaises(DatabaseError),transaction.atomic():BillingPreparation.objects.create(**attrs)

    def test_fixed_independent_exact_source_service_is_not_blanket_denied_for_same_dates(self):
        request,charge,prep=self.prepared();invoice,job=self.issued(prep)
        self.cov=coverage(self.a,self.c,reference='independent-service',service='separate-service',contract='separate-contract',
            amount_basis='gross_including_tax',from_period='2026-09',to_period='2027-09')
        register=self.source('register2','register',self.payload('register2'))
        contract=self.source('contract2','contract',self.payload('contract2'))
        proof=cc.supply_evidence(self.a,self.c.pk,['contract2'],['configure'],'coverage_schedule_interpretation',json.dumps({
            'contract_source_id':contract.pk,'contract_source_hash':contract.sha256,'mode':'standard_periods',
            'attestation':'source_schedule_matches_cadence','reason':'Independent service, explicitly evidenced exact annual period'}),
            'synthetic:independent-service',rev(self.c))
        payload={'implementation':'explicit-contract-schedule/v1','review_requirement':'none','reviewer_id':None,'owner_id':None,
            'schedule_interpretation':{'mode':'standard_periods','attestation':'source_schedule_matches_cadence','evidence_id':proof.pk}}
        proof=cc.supply_evidence(self.a,self.c.pk,['register2','contract2'],['configure'],'coverage_terms',json.dumps({
            'coverage_id':self.cov.pk,'register_id':register.pk,'contract_id':contract.pk,'terms':payload}),
            'synthetic:independent-service',rev(self.c))
        terms=cc.draft_terms(self.a,self.c.pk,self.cov.pk,register.pk,contract.pk,payload,proof.pk,rev(self.c))
        decision=cc.supply_evidence(self.a,self.c.pk,['register2','contract2'],['configure','activate'],'coverage_decision',
            'Explicit independent-service source interpretation','synthetic:independent-service',rev(self.c))
        cc.transition(self.a,self.c.pk,terms.pk,'validated',decision.pk,rev(self.c));cc.transition(self.a,self.c.pk,terms.pk,'active',decision.pk,rev(self.c))
        assessment=self.assess(terms);req=cc.request_preparation(self.a,self.c.pk,assessment.pk,assessment.result['obligations'][0]['key'],self.b.pk,rev(self.c))
        new_charge=self.charge(req,amount='900.00')
        new=fixed.prepare(self.b,self.c.pk,new_charge.pk,rev(self.c))
        self.assertNotEqual(prep.snapshot['native_service'],new.snapshot['native_service'])
        self.issued(new,reference='SYNTHETIC-SEPARATE-01')
        self.assertEqual(InvoiceIssue.objects.count(),2)

    def test_fixed_explicit_same_source_charge_reattestation_recovers_withdrawn_configurator(self):
        request=self.request();old=self.charge(request,author=self.b)
        prep=fixed.prepare(self.b,self.c.pk,old.pk,rev(self.c))
        self.grant('contract',self.b,[p for p in cc.PERMISSIONS if p!='configure'])
        with self.assertRaises(PermissionDenied):billing.ensure_current(prep)
        new=self.charge(request,author=self.a)
        self.assertEqual(new.payload,old.payload);self.assertEqual(new.version,old.version+1)
        self.assertEqual(fixed.obligation(old),fixed.obligation(new))
        result=fixed.prepare(self.b,self.c.pk,new.pk,rev(self.c))
        self.assertEqual(result.result['status'],'prepared');self.assertEqual(CoveragePreparationReceipt.objects.count(),1)

    def test_fixed_explicit_same_source_terms_reattestation_preserves_received_obligation(self):
        request=self.request();receipt=cc.receive_preparation(self.b,self.c.pk,request.pk,None,rev(self.c))
        old=self.last_terms;original=copy.deepcopy(receipt.payload)
        Grant.objects.filter(case=self.c,user=self.a,action='coverage.configure').update(active=False)
        declaration={'coverage_id':self.cov.pk,'register_id':old.register_id,'contract_id':old.contract_id,'terms':old.payload}
        proof=cc.supply_evidence(self.b,self.c.pk,['register','contract'],['configure'],'coverage_terms',json.dumps(declaration),
            'synthetic:explicit-current-configurator',rev(self.c))
        new=cc.draft_terms(self.b,self.c.pk,self.cov.pk,old.register_id,old.contract_id,old.payload,proof.pk,rev(self.c))
        self.assertNotEqual(new.pk,old.pk);self.assertEqual(new.payload,old.payload)
        decision=cc.supply_evidence(self.b,self.c.pk,['register','contract'],['configure','activate'],'coverage_decision',
            'Explicit current interpretation re-attestation; no new financial choice','synthetic:explicit-current-configurator',rev(self.c))
        cc.transition(self.b,self.c.pk,new.pk,'validated',decision.pk,rev(self.c))
        cc.transition(self.b,self.c.pk,new.pk,'active',decision.pk,rev(self.c))
        assessment=self.assess(new,self.b)
        charge=self.charge(request,assessment=assessment,author=self.b)
        prep=fixed.prepare(self.b,self.c.pk,charge.pk,rev(self.c));self.assertEqual(prep.result['status'],'prepared')
        receipt.refresh_from_db();self.assertEqual(receipt.payload,original)

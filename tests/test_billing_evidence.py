from django.test import TransactionTestCase
import copy
from datetime import timedelta
from django.test import TestCase
from django.core.exceptions import ValidationError,PermissionDenied
from django.db import connection,transaction,DatabaseError
from django.utils import timezone
from apps.identity.models import Grant
from apps.finance import billing_evidence as d,invoices,invoice_delivery
from apps.finance.models import BillingEvidenceSource,BillingEvidenceReview,BillingReleaseProfile,BillingControlReceipt,BillingReleaseAssessment,BillingReleaseBinding,InvoiceIssue,InvoiceDelivery,InvoiceReview
from apps.policy.d03_validators import STATEMENT,CONTROLS
from apps.policy.services import transition,active_component
from apps.agents.billing_evidence import investigate
from .d03_helpers import fixture,source,confirm,policy,observe,bound,evidence,corrected_contract
from .helpers import rev
class BillingEvidenceTests(TransactionTestCase):
 def setUp(self):self.f=fixture()
 def test_connected_billing_source_evidence_issuance_and_separate_delivery(self):
  from tests.obligation_helpers import approve_identified
  approve_identified(self.f['actor'],self.f['case'],self.f['invoice'],self.f['settlement_e'])
  f=self.f;r,b=bound(f);j=invoices.reserve(f['actor'],f['case'].pk,f['invoice'].pk,'issue','Finance',None);invoice_delivery.run_once();j.refresh_from_db();self.assertEqual(j.status,'confirmed');self.assertEqual(InvoiceIssue.objects.count(),1);self.assertFalse(InvoiceDelivery.objects.exists())
  with self.assertRaises(ValidationError):invoices.reserve(f['actor'],f['case'].pk,f['invoice'].pk,'deliver','Finance',None)
  bound(f,'deliver');j=invoices.reserve(f['actor'],f['case'].pk,f['invoice'].pk,'deliver','Finance',None);invoice_delivery.run_once();j.refresh_from_db();self.assertEqual(j.status,'confirmed');self.assertEqual(InvoiceDelivery.objects.count(),1);self.assertFalse(r.result['posted']);self.assertFalse(r.result['deployment_authorized']);self.assertFalse(r.result['debt_waived'])
 def test_signature_interpretation_never_infers_an_extra_signature_gate(self):
  from tests.obligation_helpers import approve_identified
  approve_identified(self.f['actor'],self.f['case'],self.f['invoice'],self.f['settlement_e'])
  f=self.f;review=confirm(f,f['statement'],'signature',key='written-clarification');statement=dict(f['statement_policy'],review_id=review.pk);policy(f,STATEMENT,statement)
  corrected_contract(f,requirements=[]);r=d.assess(f['actor'],f['case'].pk,f['invoice'].pk,'issue');d.bind(f['owner'],f['case'].pk,r.pk)
  invoices.reserve(f['actor'],f['case'].pk,f['invoice'].pk,'issue','Finance',None);invoice_delivery.run_once();self.assertEqual(InvoiceIssue.objects.count(),1);self.assertFalse(r.result['signature_gate_inferred'])
 def test_missing_d03_holds_only_enrolled_dispatch_not_pricing_or_draft(self):
  from tests.obligation_helpers import approve_identified
  approve_identified(self.f['actor'],self.f['case'],self.f['invoice'],self.f['settlement_e'])
  f=self.f;transition(f['actor'],active_component(STATEMENT,f['case']).pk,'revoked')
  self.assertEqual(f['preparation'].result['status'],'prepared');self.assertGreater(f['invoice'].amount,0)
  with self.assertRaises(ValidationError):d.assess(f['actor'],f['case'].pk,f['invoice'].pk,'issue')
  with self.assertRaises(ValidationError):invoices.reserve(f['actor'],f['case'].pk,f['invoice'].pk,'issue','Finance',None)
 def test_unresolved_source_cannot_activate_verified_statement(self):
  f=self.f;r=confirm(f,f['statement'],'unresolved',key='unresolved')
  with self.assertRaises(ValidationError):policy(f,STATEMENT,dict(f['statement_policy'],review_id=r.pk))
 def test_source_correction_withdrawal_and_raw_duplicate_preserve_history(self):
  f=self.f;s=f['statement'];self.assertEqual(d.capture_source(f['actor'],f['case'].pk,s.reference,s.payload,s.evidence_id).pk,s.pk)
  confirm(f,s,verdict='withdraw',key='withdraw');self.assertEqual(BillingEvidenceSource.objects.count(),2)
  with self.assertRaises(ValidationError):d.confirmed(s)
  newer=source(f,'statement',changes={'source_version':'v2'},predecessor=s.pk);confirm(f,newer)
  with self.assertRaises(ValidationError):d.confirmed(s)
 def test_actual_finance_role_and_source_access_required(self):
  f=self.f;Grant.objects.filter(case=f['case'],user=f['owner'],action='d03.source.read').update(active=False)
  with self.assertRaises(PermissionDenied):confirm(f,f['statement'],key='no-source')
  with self.assertRaises(ValidationError):d.assess(f['actor'],f['case'].pk,f['invoice'].pk,'issue')
 def test_exact_invoice_flow_environment_and_control_correlation(self):
  f=self.f
  for changes in [{'invoice_id':999},{'invoice_sha256':'0'*64},{'flow_version':'wrong'},{'environment_ref':'wrong'},{'control_key':'missing'},{'observed_at':(timezone.now()+timedelta(hours=1)).isoformat()}]:
   with self.assertRaises(ValidationError):observe(f,changes=changes)
  self.assertFalse(BillingControlReceipt.objects.exists())
 def test_unknown_and_later_source_unavailability_hold_queued_dispatch(self):
  from tests.obligation_helpers import approve_identified
  approve_identified(self.f['actor'],self.f['case'],self.f['invoice'],self.f['settlement_e'])
  f=self.f;r,b=bound(f);j=invoices.reserve(f['actor'],f['case'].pk,f['invoice'].pk,'issue','Finance',None)
  observe(f,changes={'source_version':'v2','outcome':'unavailable'});invoice_delivery.run_once();j.refresh_from_db();self.assertEqual(j.status,'held');self.assertFalse(InvoiceIssue.objects.exists());self.assertEqual(BillingControlReceipt.objects.count(),2)
  r2=d.assess(f['actor'],f['case'].pk,f['invoice'].pk,'issue');self.assertFalse(r2.result['evidence_ready']);self.assertFalse(d.report(f['actor'],f['case'].pk,r.pk)['current_evidence_ready'])
 def test_control_receipt_duplicate_and_changed_intent(self):
  f=self.f;r=observe(f);self.assertEqual(d.observe_control(f['owner'],f['case'].pk,f['invoice'].pk,r.evidence_id).pk,r.pk)
  with self.assertRaises(ValidationError):observe(f,changes={'outcome':'unknown'})
 def test_missing_controls_and_native_contract_modes_are_explicit(self):
  from tests.obligation_helpers import approve_identified
  approve_identified(self.f['actor'],self.f['case'],self.f['invoice'],self.f['settlement_e'])
  f=self.f;r=d.assess(f['actor'],f['case'].pk,f['invoice'].pk,'issue');self.assertFalse(r.result['evidence_ready'])
  corrected_contract(f,implementation='incumbent_reference_only');r,b=bound(f)
  with self.assertRaises(ValidationError):invoices.reserve(f['actor'],f['case'].pk,f['invoice'].pk,'issue','Finance',None)
  self.assertFalse(r.result['native_flow_verified'])
 def test_bound_evidence_does_not_replace_existing_finance_invoice_review(self):
  from tests.obligation_helpers import approve_identified
  approve_identified(self.f['actor'],self.f['case'],self.f['invoice'],self.f['settlement_e'])
  f=self.f;bound(f)
  invoices.review(f['actor'],f['case'].pk,f['invoice'].pk,'Finance','return',f['settlement_e']['invoice_review'].pk,'Return exact invoice',None)
  with self.assertRaises(ValidationError):invoices.reserve(f['actor'],f['case'].pk,f['invoice'].pk,'issue','Finance',None)
 def test_policy_validators_reject_duplicate_effect_and_wrong_flow(self):
  f=self.f
  for value in [f['control_policies']+[f['control_policies'][0]],[dict(f['control_policies'][0],flow_version='wrong')],[dict(f['control_policies'][0],max_age_seconds=0)]]:
   with self.assertRaises(ValidationError):
    with transaction.atomic():policy(f,CONTROLS,value)
 def test_source_quote_and_source_clock_are_exact(self):
  f=self.f;payload=dict(f['statement'].payload,quote='Uncited fabricated source quote',source_version='v2')
  with self.assertRaises(ValidationError):d.capture_source(f['actor'],f['case'].pk,'new-statement',payload,f['statement'].evidence_id)
  with self.assertRaises(ValidationError):source(f,'statement',changes={'reported_at':(timezone.now()+timedelta(hours=1)).isoformat(),'source_version':'v2'},predecessor=f['statement'].pk)
 def test_sql_guards_protect_all_six_models(self):
  f=self.f;bound(f)
  for model in [BillingEvidenceSource,BillingEvidenceReview,BillingReleaseProfile,BillingControlReceipt,BillingReleaseAssessment,BillingReleaseBinding]:
   row=model.objects.first()
   with self.assertRaises(DatabaseError):
    with transaction.atomic():
     with connection.cursor() as cur:cur.execute('UPDATE '+model._meta.db_table+' SET id=id WHERE id=%s',[row.pk])
 def test_agent_ui_and_raw_source_access_are_scoped(self):
  f=self.f;r,b=bound(f);run=investigate(f['actor'],f['case'].pk);self.assertFalse(run.result['source_body_read']);self.assertFalse(run.result['financial_execution'])
  self.client.force_login(f['actor']);url=f"/cases/{f['case'].pk}/finance/billing-evidence/";self.assertContains(self.client.get(url),'Billing statements and invoice-release evidence');self.assertEqual(self.client.get(url+f'source/{f["statement"].pk}/').status_code,200)
  Grant.objects.filter(case=f['case'],user=f['actor'],action='d03.source.read').update(active=False);self.assertEqual(self.client.get(url+f'source/{f["statement"].pk}/').status_code,403)
  self.assertNotContains(self.client.get(f"/cases/{f['case'].pk}/"),f['v']['statement_quote'])
 def test_read_only_forms_and_posts(self):
  f=self.f;Grant.objects.filter(case=f['case'],user=f['actor']).exclude(action__in=['case.read','finance.read','d03.read']).update(active=False);self.client.force_login(f['actor']);url=f"/cases/{f['case'].pk}/finance/billing-evidence/"
  self.assertContains(self.client.get(url),'Read-only access.');self.assertEqual(self.client.post(url,{'action':'enroll','coverage':f['coverage'].pk,'evidence':f['enrollment_evidence'].pk,'revision':rev(f['case'])}).status_code,302)
 def test_unknown_before_effect_recovers_with_explicit_intent_replacement(self):
  from tests.obligation_helpers import approve_identified
  approve_identified(self.f['actor'],self.f['case'],self.f['invoice'],self.f['settlement_e'])
  f=self.f;bound(f);j=invoices.reserve(f['actor'],f['case'].pk,f['invoice'].pk,'issue','Finance',None);observe(f,changes={'source_version':'v2','outcome':'unknown'});invoice_delivery.run_once();j.refresh_from_db();self.assertEqual(j.status,'held')
  observe(f,changes={'source_version':'v3'});r=d.assess(f['actor'],f['case'].pk,f['invoice'].pk,'issue');d.bind(f['owner'],f['case'].pk,r.pk)
  with self.assertRaises(ValidationError):invoice_delivery.operate(f['actor'],f['case'].pk,j.pk,'retry','Intent changed',None)
  invoice_delivery.operate(f['actor'],f['case'].pk,j.pk,'replace_intent','Fresh exact source evidence',None);invoice_delivery.run_once();self.assertEqual(InvoiceIssue.objects.count(),1)
 def test_committed_unknown_effect_reconciles_before_revoked_source_authority(self):
  from tests.obligation_helpers import approve_identified
  approve_identified(self.f['actor'],self.f['case'],self.f['invoice'],self.f['settlement_e'])
  f=self.f;bound(f);j=invoices.reserve(f['actor'],f['case'].pk,f['invoice'].pk,'issue','Finance',None)
  from adapters.invoices import TimeoutAfterInvoiceAccept
  invoice_delivery.run_once(TimeoutAfterInvoiceAccept());j.refresh_from_db();self.assertEqual(j.status,'unknown');Grant.objects.filter(case=f['case'],user=f['owner'],action='d03.source.read').update(active=False)
  invoice_delivery.run_once();j.refresh_from_db();self.assertEqual(j.status,'confirmed');self.assertEqual(InvoiceIssue.objects.count(),1)
 def test_debt_and_cash_allocation_survive_later_source_failure(self):
  from tests.obligation_helpers import approve_identified
  approve_identified(self.f['actor'],self.f['case'],self.f['invoice'],self.f['settlement_e'])
  f=self.f;bound(f);invoices.reserve(f['actor'],f['case'].pk,f['invoice'].pk,'issue','Finance',None);invoice_delivery.run_once();observe(f,changes={'source_version':'v2','outcome':'unavailable'})
  from .settlement_helpers import receipt,assign,allocate
  from apps.finance.receivables import calculate
  r,lot=receipt(f['actor'],f['case']);assign(f['actor'],f['case'],r,f['coverage'],f['settlement_e']);allocate(f['actor'],f['case'],lot,InvoiceIssue.objects.get(),'1.00',f['settlement_e'])
  _,v=calculate(f['case'],timezone.localdate());self.assertEqual(v['groups'][0]['receivable'],format(f['invoice'].amount-1,'.8f'))
 def test_scoped_control_history_and_generic_source_repackaging(self):
  f=self.f;r,b=bound(f);receipt=BillingControlReceipt.objects.get();self.client.force_login(f['actor']);url=f"/cases/{f['case'].pk}/finance/billing-evidence/controls/{f['invoice'].pk}/"
  self.assertEqual(self.client.get(url).status_code,200);Grant.objects.filter(case=f['case'],user=f['actor'],action='d03.source.read').update(active=False);self.assertEqual(self.client.get(url).status_code,403)
  from apps.agents.services import extract_evidence
  with self.assertRaises(ValidationError):extract_evidence(f['actor'],f['case'].pk,receipt.evidence_id,'F30')
  from apps.documents import validation as af
  from tests.validation_helpers import values
  with self.assertRaises(ValidationError):af.capture_source(f['actor'],f['case'].pk,'private-flow',f['flow'].evidence_id,values()['metadata'],None)
 def test_invoice_without_enrolled_coverage_has_no_new_d03_gate(self):
  f=self.f
  from .billing_helpers import coverage,usage,prices,prepare
  from .settlement_helpers import draft
  from .obligation_helpers import approve_identified as approve
  cov=coverage(f['actor'],f['case'],reference='independent-coverage',customer='other-customer',contract='other-contract');prices(f['actor'],f['case'],cov)
  body='customer,service,contract,period,transaction_id,quantity,unit\nother-customer,api-usage,other-contract,2026-03,UNRELATED,1,transaction\n'
  # Use exact fixture identity/unit from the existing source batch, preserving the actual parser.
  template=f['preparation'].usage.evidence.body;lines=template.splitlines();line=lines[1].replace(f['coverage'].customer,'other-customer').replace(f['coverage'].contract,'other-contract');body=lines[0]+'\n'+line+'\n';u=usage(f['actor'],f['case'],cov,body);p=prepare(f['actor'],f['case'],cov,u=u)
  i=draft(f['actor'],f['case'],p,'UNRELATED-INV');approve(f['actor'],f['case'],i,f['settlement_e']);self.assertIsNone(d.release_context(i,'issue'))
  invoices.reserve(f['actor'],f['case'].pk,i.pk,'issue','Finance',None);invoice_delivery.run_once();self.assertEqual(InvoiceIssue.objects.count(),1)

 def test_configuration_cannot_invent_source_prerequisites_or_dispatch_mode(self):
  f=self.f
  for changes in [{'requirements':[]},{'implementation':'incumbent_reference_only'},{'requirements':[{'key':'invented','evidence_kind':'d03_control_invented'}]}]:
   with self.assertRaises(ValidationError):
    with transaction.atomic():policy(f,CONTROLS,[dict(f['control_policies'][0],**changes)])
 def test_unknown_source_requirements_are_not_confirmed_empty(self):
  f=self.f;s=source(f,'flow_contract',changes={'source_version':'v2','effect_requirements':{'issue':None,'deliver':[]}},predecessor=f['flow'].pk);r=confirm(f,s)
  with self.assertRaises(ValidationError):policy(f,CONTROLS,[dict(f['control_policies'][0],source_id=s.pk,source_sha256=s.sha256,review_id=r.pk,requirements=[])])
 def test_meeting_agent_cannot_read_restricted_evidence(self):
  from apps.agents.meetings import suggest_commitments
  f=self.f
  class Provider:
   name='must-not-run'
   def suggest(self,e):raise AssertionError('Restricted evidence reached provider')
  for e in [f['flow'].evidence,f['statement'].evidence]:
   with self.assertRaises(ValidationError):suggest_commitments(f['actor'],f['case'].pk,e.pk,rev(f['case']),Provider())

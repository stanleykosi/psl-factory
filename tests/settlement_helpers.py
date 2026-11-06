import json
from pathlib import Path
from datetime import timedelta
from django.utils import timezone
from apps.policy.services import register_reference
from apps.identity.models import Grant
from apps.finance import invoices,cash,invoice_delivery
from apps.finance.models import InvoiceIssue
from .helpers import setup_case,rev,activate
from .billing_helpers import coverage,prices,usage,prepare,policy,evidence

FIXTURE=Path(__file__).resolve().parent.parent/'fixtures/finance-settlement.json'
def configured(a,c):
    f=json.loads(FIXTURE.read_text(encoding='utf-8'));e=evidence(a,c,'policy_decision','Synthetic Finance human assignment only')
    r=register_reference(a,c.pk,'settlement-finance','schema:psl/role-assignment/v1',{'role':'Finance','user_id':a.pk},e.pk)
    activate(a,c,'D05.role_principal_assignments',[r.ref],e)
    f['adapter']['recipient_id']=a.pk
    for key,value in [('D05.decision_action_matrix',f['review']),('D08.adapter_contract_ref',f['adapter']),('D08.duplicate_correction_rules',f['identity']),
        ('D14.receipt_verification_source_ref',f['source']),('D14.recorder_authority_ref',f['recorder']),('D14.allocation_rule_ref',f['matching']),
        ('D14.adjustment_correction_rule_refs',f['reversals']),('D14.legal_document_requirements',f['legal'])]:policy(a,c,key,value)
    return f

def fixture(case_id=None):
    a,c=setup_case(case_id=case_id);cov=coverage(a,c);prices(a,c,cov);u=usage(a,c,cov);p=prepare(a,c,cov,u=u);configured(a,c)
    e={k:evidence(a,c,k,'Synthetic '+k+' evidence') for k in ['invoice_review','cash_correction','cash_allocation']}
    return a,c,cov,p,e

def draft(a,c,p,reference='INV-EXAMPLE'):
    return invoices.draft(a,c.pk,p.pk,reference,timezone.localdate()-timedelta(days=1),rev(c))
def approve(a,c,i,e):return invoices.review(a,c.pk,i.pk,'Finance','approve',e['invoice_review'].pk,'Synthetic exact invoice reviewed',rev(c))
def issue(a,c,i,e):
    approve(a,c,i,e);job=invoices.reserve(a,c.pk,i.pk,'issue','Finance',rev(c));invoice_delivery.run_once();job.refresh_from_db()
    return InvoiceIssue.objects.get(invoice=i)

def receipt(a,c,amount='50.00',ref='tx-cash-1',verify=True):
    value={'source':'synthetic-bank','transaction_ref':ref,'customer':'client-example','amount':amount,'currency':'NGN','amount_basis':'gross_including_tax','received_at':(timezone.now()-timedelta(hours=1)).isoformat()}
    report=evidence(a,c,'cash_report',json.dumps(value));r=cash.report(a,c.pk,report.pk,rev(c))
    if not verify:return r,None
    proof=evidence(a,c,'cash_verification',json.dumps(value));lot=cash.verify(a,c.pk,r.pk,'Finance',proof.pk,rev(c));return r,lot

def assign(a,c,r,cov,e):return cash.assign(a,c.pk,r.pk,cov.pk if cov else None,'Finance',e['cash_correction'].pk,'Synthetic evidenced receipt assignment',rev(c))
def allocate(a,c,l,iss,n,e,key='match-1'):return cash.allocate(a,c.pk,l.pk,iss.pk,n,key,'Finance',e['cash_allocation'].pk,rev(c))

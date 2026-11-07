import json
from pathlib import Path
from apps.policy.services import active_component,reference_values
from apps.finance import corrections,financial_reviews,cash_successors,cash,invoice_delivery
from apps.finance.models import InvoiceCorrectionAcceptance
from .helpers import rev
from .billing_helpers import policy,evidence
from .settlement_helpers import fixture as settlement_fixture,issue,draft,receipt,assign

FIXTURE=Path(__file__).resolve().parent.parent/'fixtures/finance-corrections.json'
def configure(a,c):
    f=json.loads(FIXTURE.read_text(encoding='utf-8'))
    matrix=reference_values(active_component('D05.decision_action_matrix',c))[0]
    matrix['finance']+=[{'purpose':p,'role':'Finance','actions':['approve','return','reject'],'allow_preparer_review':True} for p in ['invoice_correction','cash_successor']]
    policy(a,c,'D05.decision_action_matrix',matrix)
    identity=reference_values(active_component('D08.duplicate_correction_rules',c))[0];identity['correction']=f['method'];policy(a,c,'D08.duplicate_correction_rules',identity)
    for key,field in [('D14.adjustment_correction_rule_refs','rules'),('D14.legal_document_requirements','legal')]:policy(a,c,key,reference_values(active_component(key,c))+f[field])
    return f

def fixture(case_id=None, *, identity=False):
    issue_original=issue
    if identity:
        from .obligation_helpers import issue_identified as issue_original
    a,c,cov,p,e=settlement_fixture(case_id);configure(a,c);iss=issue_original(a,c,draft(a,c,p),e)
    e['review']=evidence(a,c,'financial_correction_review','Synthetic independent review record')
    return a,c,cov,iss,e

def note(a,c,iss,e,kind='credit',amount='5.00',reference='NOTE-1'):
    v={'document_ref':reference,'invoice_reference':iss.invoice.reference,'kind':kind,'amount':amount,'currency':iss.invoice.currency,'amount_basis':iss.invoice.amount_basis}
    proof=evidence(a,c,'invoice_'+kind+'_note',json.dumps(v))
    return corrections.capture(a,c.pk,iss.pk,proof.pk,e['cash_correction'].pk,'Synthetic exact legal note correction',rev(c))

def review(a,c,r,e,kind='invoice'):
    return financial_reviews.review(a,c.pk,kind,r.pk,'Finance','approve',e['review'].pk,'Synthetic exact financial correction approved',rev(c))
def apply(a,c,r,e):
    review(a,c,r,e);job=corrections.reserve(a,c.pk,r.pk,'adjust','Finance',rev(c));invoice_delivery.run_once();return job

def successor(a,c,l,e,amount='40.00'):
    value=dict(cash.lot_payload(l),amount=amount)
    report=evidence(a,c,'cash_report',json.dumps(value));verification=evidence(a,c,'cash_verification',json.dumps(value))
    return cash_successors.capture(a,c.pk,l.pk,report.pk,verification.pk,e['cash_correction'].pk,'Synthetic corrected source cash statement',rev(c))

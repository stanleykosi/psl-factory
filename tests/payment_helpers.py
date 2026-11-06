import json
from pathlib import Path
from datetime import timedelta
from django.utils import timezone
from django.contrib.auth import get_user_model
from apps.identity.models import Grant
from apps.policy.services import register_reference,active_component,transition
from apps.policy.payment_drafts import draft_payment_policy
from apps.policy.payment_validators import ROLE,PEOPLE,DELEGATION,VALIDITY,DENOMINATOR,FUNDS
from .helpers import activate
from .billing_helpers import evidence

FIXTURE=Path(__file__).resolve().parent.parent/'fixtures/payment-controls.json'

def human(a,c,e):
    p=get_user_model().objects.create_user(username='payment-approver',password='test-only')
    for action in ['case.read','payment.read','finance.read','delivery.read','payment.exception.decide']:
        Grant.objects.create(user=p,case=c,action=action)
    r=register_reference(a,c.pk,'payment-approver-role','schema:psl/role-assignment/v1',{'role':'Finance','user_id':p.pk},e.pk)
    old=active_component('D05.role_principal_assignments',c)
    activate(a,c,'D05.role_principal_assignments',old.envelope['value']+[r.ref],e)
    return p

def configure(a,c,cov,p,components=None,**overrides):
    f=json.loads(FIXTURE.read_text(encoding='utf-8'));f[PEOPLE][0]['user_id']=p.pk
    from apps.finance.models import InvoiceIssue
    issue=InvoiceIssue.objects.filter(invoice__preparation__coverage=cov).first()
    for key in [DENOMINATOR,FUNDS]:f[key].update(coverage_id=cov.pk,currency=cov.currency,amount_basis=issue.invoice.amount_basis if issue else cov.amount_basis)
    f.update(overrides)
    e=evidence(a,c,'policy_decision','Synthetic D13 example; no operational authority')
    result=[]
    for key in components or [ROLE,PEOPLE,DELEGATION,VALIDITY,DENOMINATOR,FUNDS]:
        r=draft_payment_policy(a,c.pk,key,f[key],e.pk,timezone.now()-timedelta(seconds=1));transition(a,r.pk,'validated');transition(a,r.pk,'active');result.append(r)
    return result

def fixture():
    from .test_delivery import DeliveryFixture
    from .billing_helpers import coverage,prices,usage,prepare
    from .settlement_helpers import configured,draft,issue,receipt,assign,allocate
    f=DeliveryFixture();f.setup_delivery();a,c=f.actor,f.case
    f.cov=coverage(a,c,completeness='complete');prices(a,c,f.cov);u=usage(a,c,f.cov);p=prepare(a,c,f.cov,u=u)
    original=active_component('D05.role_principal_assignments',c).envelope['value'];configured(a,c)
    finance=active_component('D05.role_principal_assignments',c).envelope['value'];activate(a,c,'D05.role_principal_assignments',original+finance,f.e['policy_decision'])
    f.cash_e={k:evidence(a,c,k,'Synthetic exact Finance evidence') for k in ['invoice_review','cash_correction','cash_allocation']}
    f.iss=issue(a,c,draft(a,c,p),f.cash_e);f.r,f.lot=receipt(a,c,'50.00');assign(a,c,f.r,f.cov,f.cash_e);allocate(a,c,f.lot,f.iss,'10',f.cash_e)
    f.approver=human(a,c,f.e['policy_decision']);f.ready();return f

import json
from pathlib import Path
from django.utils import timezone
from apps.core.services import add_evidence
from apps.finance import billing
from apps.policy.finance_drafts import draft_finance_policy
from apps.policy.services import transition
from .helpers import rev

FIXTURE=Path(__file__).resolve().parent.parent/'fixtures/finance-billing.json'
def evidence(a,c,kind,body):return add_evidence(a,c.pk,kind,body,'synthetic:billing-tests')
def coverage(a,c,**overrides):
    f=json.loads(FIXTURE.read_text(encoding='utf-8'));v=dict(f['coverage'],**overrides)
    e=evidence(a,c,'billing_coverage','Synthetic client/service contract coverage assertion')
    return billing.register_coverage(a,c.pk,**v,evidence_id=e.pk,expected=rev(c))
def policy(a,c,component,content):
    e=evidence(a,c,'policy_decision','Synthetic billing rule decision; not operational policy')
    config=draft_finance_policy(a,c.pk,component,content,e.pk,timezone.now())
    transition(a,config.pk,'validated');transition(a,config.pk,'active');return config
def prices(a,c,cov):
    f=json.loads(FIXTURE.read_text(encoding='utf-8'));r=dict(f['rule'],coverage_id=cov.pk);m=f['arithmetic']
    e=evidence(a,c,'billing_oracle',json.dumps(m['oracles']));m['oracle_evidence_id']=e.pk
    return [policy(a,c,'D08.effective_price_rule_refs',[r]),policy(a,c,'D08.tax_tier_rounding_rules',m)]
def usage(a,c,cov,body=None):
    f=json.loads(FIXTURE.read_text(encoding='utf-8'));e=evidence(a,c,'billing_usage',body if body is not None else f['csv'])
    return billing.capture_usage(a,c.pk,cov.pk,e.pk,rev(c))
def prepare(a,c,cov,kind='usage',u=None,h=None):return billing.prepare(a,c.pk,cov.pk,kind,u.pk if u else None,h.pk if h else None,rev(c))
def stage_policy(a,c,cov,signature):
    policy(a,c,'D12.contract_version_ref',{'coverage_id':cov.pk,'signed_evidence_id':signature.pk,'signed_sha256':signature.sha256})
    policy(a,c,'D12.currency_amount_basis',{'coverage_id':cov.pk,'currency':cov.currency,'amount_basis':cov.amount_basis,'contract_value':None,'decimal_places':2})
    f=json.loads(FIXTURE.read_text(encoding='utf-8'))
    policy(a,c,'D12.stage_terms',[dict(t,coverage_id=cov.pk) for t in f['stage_examples']['terms']])

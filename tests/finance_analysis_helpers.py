import json
from pathlib import Path
from datetime import timedelta
from django.conf import settings
from django.utils import timezone
from django.contrib.auth import get_user_model
from apps.core.services import add_evidence
from apps.identity.models import Grant
from apps.policy.finance_drafts import draft_finance_policy
from apps.policy.services import register_reference,transition
from apps.finance import analysis
from apps.finance.services import capture_import,validate_import
from apps.documents.controlled import register_template
from .helpers import setup_case,activate,rev
from .document_helpers import artifact

DEFINITION={'document_type':'finance_report','required_fields':['executive_summary','financial_metrics','bu_totals'],
    'audience_fields':{'internal':['executive_summary','financial_metrics','bu_totals']},'internal_review_required':False}
METRICS=['revenue','direct_cost','staff_cost','opex']

def policy(actor,case,key,content,evidence):
    c=draft_finance_policy(actor,case.pk,key,content,evidence.pk,timezone.now()-timedelta(days=1));transition(actor,c.pk,'validated');transition(actor,c.pk,'active');return c

def declared_units(actor,case,batch):
    """Explicit synthetic fixture assertion, not a production/default conversion rule."""
    from apps.finance.source_units import evidence_identity
    body={'schema':'finance-source-unit-assertion/v1','batch_id':batch.pk,'source_sha256':batch.source_sha256,
        'input_key':'synthetic-controlled-input','feed':'synthetic-controlled-export','unit':'major_currency'}
    evidence=add_evidence(actor,case.pk,'finance_source_unit',json.dumps(body,sort_keys=True),
        evidence_identity(batch.pk,'synthetic-controlled-input','synthetic-controlled-export'))
    return {'schema':'finance-source-units/v1','batch':{'id':batch.pk,'sha256':batch.source_sha256},
        'input_key':body['input_key'],'declarations':[{'feed':body['feed'],'unit':body['unit'],
        'evidence':{'id':evidence.pk,'version':evidence.version,'sha256':evidence.sha256}}]}

def fixture(username='human',recipient_username='finance-reader',review=True,synthetic=True):
    a,c=setup_case(username=username,synthetic=synthetic);f=json.loads((settings.BASE_DIR/'fixtures/finance-analysis.json').read_text());e={}
    for kind in ['policy_decision','finance_source','finance_review','finance_adjustment']:
        e[kind]=add_evidence(a,c.pk,kind,'Synthetic '+kind+' evidence','synthetic:finance')
    e['financial_input']=add_evidence(a,c.pk,'financial_input',f['csv'],'synthetic:controlled-export')
    basis=add_evidence(a,c.pk,'finance_basis',json.dumps(f['basis'],sort_keys=True),'synthetic:hr-snapshot');e['finance_basis']=basis
    owner=e['policy_decision'];configs={}
    r=register_reference(a,c.pk,'finance:human','schema:psl/role-assignment/v1',{'role':'Finance','user_id':a.pk},owner.pk)
    configs['D05.role_principal_assignments']=activate(a,c,'D05.role_principal_assignments',[r.ref],owner)
    payloads={'D05.decision_action_matrix':f['authority'],'D06.source_schema_ref':{'columns':['account','amount','currency','period']},
        'D06.unit_sign_currency_period':f['conventions'],'D06.account_bu_maps':f['mapping'],'D10.report_category_effective_dates':f['catalogue'],
        'D07.allocation_pool_rules':f['pools'],'D07.rounding_residual_rule_id':f['rounding'],'D07.join_overlap_rule_id':f['join'],
        'D07.effective_membership_ref':dict(f['basis'],evidence_id=basis.pk),'D07.authorized_input_refs':[{'entity':'synthetic-company','period':'2026-10','provider':'HR','evidence_id':basis.pk,'purpose':'allocation_basis'}],
        'D10.audience_projection_rules':f['projection']}
    formulas=[]
    for rule in f['formulas']:
        oracle=add_evidence(a,c.pk,'finance_oracle',json.dumps(rule['oracles'],sort_keys=True),'synthetic:manual-golden-'+rule['key']);e['oracle_'+rule['key']]=oracle
        formulas.append(dict(rule,oracle_evidence_id=oracle.pk))
    payloads['D06.rule_oracle_refs']=formulas
    for key,value in payloads.items():configs[key]=policy(a,c,key,value,owner)
    batch=capture_import(a,c.pk,e['financial_input'].pk,rev(c));validate_import(a,c.pk,batch.pk,rev(c))
    units=declared_units(a,c,batch)
    source=analysis.capture_source(a,c.pk,batch.pk,'synthetic-company','accrual',timezone.now()-timedelta(hours=1),'complete',f['source_control_total'],e['finance_source'].pk,rev(c),unit_declaration=units)
    if review:
        analysis.review(a,c.pk,'source',source.pk,'Finance','approve',e['finance_review'].pk,'Source context and selected inventory reviewed',rev(c))
        for component,purpose in analysis.PURPOSE.items():analysis.review(a,c.pk,purpose,configs[component].pk,'Finance','approve',e['finance_review'].pk,'Exact configured rule reviewed',rev(c))
    t=register_template(a,c.pk,'Finance aggregate output',DEFINITION,owner.pk,rev(c))
    artifact(a,c,'D11.template_storage_retention_rules','schema:psl/document-storage/v1',{'template_ids':[t.pk],'repository':'internal-versioned','retention_days':30},owner)
    recipient=get_user_model().objects.create_user(username=recipient_username)
    Grant.objects.create(case=c,user=recipient,action='finance.read');Grant.objects.create(case=c,user=recipient,action='document.receive:internal')
    r=register_reference(a,c.pk,'finance:recipient','schema:psl/document-recipient/v1',{'audience':'internal','user_id':recipient.pk},owner.pk)
    activate(a,c,'D11.recipient_grant_refs',[r.ref],owner)
    return a,c,e,f,configs,source,t,recipient

def pipeline(a,c,s):
    m=analysis.map_source(a,c.pk,s.pk,[],rev(c));allocation=analysis.allocate(a,c.pk,m.pk,METRICS,rev(c));output=analysis.calculate(a,c.pk,allocation.pk,rev(c));return m,allocation,output

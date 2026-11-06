import json
from datetime import date
from django.conf import settings
from django.utils import timezone
from django.contrib.auth import get_user_model
from apps.core.services import add_evidence
from apps.identity.models import Grant
from apps.policy.services import register_reference,resolve,reference_values
from apps.documents.controlled import register_template
from apps.finance import forecast
from .helpers import setup_case,activate,rev
from .billing_helpers import policy,evidence
from .document_helpers import artifact

def month(offset=0,today=None):
    today=today or timezone.localdate();n=today.year*12+today.month-1+offset;return f'{n//12:04}-{n%12+1:02}'

def payload(a,c,today=None,amount='50'):
    today=today or timezone.localdate();opening={'account':'account-1','amount':'100','observed_on':today.isoformat(),'cutoff':'start_of_day'}
    o=evidence(a,c,'forecast_opening',json.dumps(opening));source=evidence(a,c,'document','Synthetic explicit inflow and spending assumptions, not expense approval')
    return {'entity':'synthetic-company','currency':'NGN','basis':'gross_cash','as_of':today.isoformat(),'months':[month(0,today),month(1,today)],
        'coverage':{'accounts':['account-1'],'inflows':'complete','outflows':'complete','omissions':[]},'openings':[dict(opening,evidence_id=o.pk)],
        'items':[{'key':'receipt-1','kind':'other_inflow','source_ref':'expected-1','owner':'finance-team','amount':amount,'expected_on':today.isoformat(),'original_due':today.isoformat(),'issue_id':None,'evidence_id':source.pk,'commitment':'forecast_only'},
        {'key':'spend-1','kind':'outflow','source_ref':'recurring-1','owner':'requester-1','amount':'20','expected_on':month(1,today)+'-10','original_due':month(1,today)+'-10','issue_id':None,'evidence_id':source.pk,'commitment':'reported_commitment'}],'rollover':[]}

def configure(a,c):
    f=json.loads((settings.BASE_DIR/'fixtures/finance-forecast.json').read_text(encoding='utf-8'))
    owner=evidence(a,c,'policy_decision','Synthetic explicit forecast policy decision')
    if resolve('D05.role_principal_assignments',c).status!='ACTIVE':
        r=register_reference(a,c.pk,'forecast:finance-role','schema:psl/role-assignment/v1',{'role':'Finance','user_id':a.pk},owner.pk)
        activate(a,c,'D05.role_principal_assignments',[r.ref],owner)
    existing=resolve('D05.decision_action_matrix',c)
    matrix=reference_values(existing.configuration)[0] if existing.status=='ACTIVE' else {}
    matrix.setdefault('finance',[]);matrix['finance'] += [{'purpose':p,'role':'Finance','actions':['approve','return','reject'],'allow_preparer_review':True} for p in ['forecast','forecast_rollover','forecast_priority']]
    policy(a,c,'D05.decision_action_matrix',matrix)
    o=evidence(a,c,'forecast_oracle',json.dumps(f['method']['oracles']));m=dict(f['method'],oracle_evidence_id=o.pk)
    policy(a,c,'D10.forecast_inclusion_rule_id',m);policy(a,c,'D10.audience_projection_rules',f['projection'])
    return m

def fixture(configured=True):
    a,c=setup_case();m=configure(a,c) if configured else None
    return a,c,m

def scenario(a,c,value=None,reference='FORECAST-1',parent=None):
    e=evidence(a,c,'forecast_input',json.dumps(value or payload(a,c)));return forecast.capture(a,c.pk,reference,e.pk,'Synthetic selected forecast inventory and coverage',rev(c),parent.pk if parent else None)

def run(a,c,value=None):
    s=scenario(a,c,value);return forecast.prepare(a,c.pk,s.pk,rev(c))

def review(a,c,r,verdict='approve'):
    e=evidence(a,c,'forecast_review','Synthetic exact assumptions, priorities, source and audience readiness review')
    return forecast.review(a,c.pk,r.pk,'Finance',verdict,e.pk,'Synthetic exact forecast approved with coverage explicit',rev(c))

def actual(a,c,amount='15',direction='inflow',transaction='TX-1',verified=True):
    value={'entity':'synthetic-company','account':'account-1','currency':'NGN','basis':'gross_cash','source':'supplied-source','transaction':transaction,'direction':direction,'amount':amount,'occurred_on':timezone.localdate().isoformat()}
    e=evidence(a,c,'forecast_actual',json.dumps(value));r=forecast.capture_actual(a,c.pk,e.pk,rev(c))
    if verified:
        proof=evidence(a,c,'forecast_actual_verification',json.dumps(value));forecast.verify_actual(a,c.pk,r.pk,'Finance',proof.pk,rev(c))
    return r

def match(a,c,s,r,amount='15',key='receipt-1',op='MATCH-1'):
    e=evidence(a,c,'forecast_match','Synthetic explicit actual-to-assumption match')
    return forecast.match(a,c.pk,s.pk,key,r.pk,amount,op,e.pk,rev(c))

def publication(a,c):
    owner=evidence(a,c,'policy_decision','Synthetic report template and recipient scope')
    definition={'document_type':'finance_report','required_fields':['executive_summary','financial_metrics','bu_totals'],'audience_fields':{k:['executive_summary','financial_metrics','bu_totals'] for k in ['internal','management']},'internal_review_required':False}
    t=register_template(a,c.pk,'Synthetic cash forecast',definition,owner.pk,rev(c))
    artifact(a,c,'D11.template_storage_retention_rules','schema:psl/document-storage/v1',{'template_ids':[t.pk],'repository':'internal-versioned','retention_days':30},owner)
    reader=get_user_model().objects.create_user(username='forecast-reader')
    Grant.objects.create(case=c,user=reader,action='finance.read')
    refs=[]
    for audience in ['internal','management']:
        Grant.objects.create(case=c,user=reader,action='document.receive:'+audience)
        refs.append(register_reference(a,c.pk,'forecast:recipient:'+audience,'schema:psl/document-recipient/v1',{'audience':audience,'user_id':reader.pk},owner.pk).ref)
    activate(a,c,'D11.recipient_grant_refs',refs,owner);return t,reader

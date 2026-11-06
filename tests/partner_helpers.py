import json
from datetime import timedelta
from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils import timezone
from apps.core.services import add_evidence
from apps.identity.models import Grant
from apps.policy.services import register_reference,transition
from apps.policy.partner_drafts import draft_partner_policy
from apps.policy.partner_validators import STAGES,DEADLINES,ACTIVITY,METER
from apps.baas import partner_operations as domain,partner_delivery
from apps.baas.models import PartnerFinanceReceipt
from apps.finance import billing
from .helpers import setup_case,activate,rev

def evidence(a,c,kind,v):return add_evidence(a,c.pk,kind,json.dumps(v) if not isinstance(v,str) else v,'synthetic:partner-tests',rev(c))
def policy(a,c,key,value):
    e=evidence(a,c,'policy_decision','Synthetic explicit partner rule, not actual policy')
    cfg=draft_partner_policy(a,c.pk,key,value,e.pk,timezone.now()-timedelta(days=1));transition(a,cfg.pk,'validated');transition(a,cfg.pk,'active');return cfg
def body(kind):
    now=timezone.now();stamp=now.isoformat()
    if kind=='agreement':return {'partner':'partner-1','customer':'customer-1','contract':'contract-1','starts_on':str(now.date()-timedelta(days=30)),'expires_on':str(now.date()+timedelta(days=3)),'notice_on':str(now.date()+timedelta(days=1)),'auto_renewal':'unknown','clause_reference':'clause-1','executed_evidence_id':None,'executed_sha256':None}
    if kind=='onboarding':return {'partner':'partner-1','customer':'customer-1','tracker':'tracker-1','reported_stage':'review','reported_entry_at':(now-timedelta(hours=5)).isoformat(),'missing_documents':['signed-id']}
    return {'partner':'partner-1','customer':'customer-1','source':'synthetic-admin','period':now.astimezone(__import__('zoneinfo').ZoneInfo('Africa/Lagos')).strftime('%Y-%m'),'extracted_at':stamp,'completeness':'complete','products':['payments'],
            'events':[{'event':key,'user':user,'product':'payments','kind':kind,'at':stamp,'quantity':qty} for key,user,kind,qty in [('event-1','user-1','use','2'),('event-2','user-1','use','3'),('event-3','user-2','use','1'),('test-1','excluded-user','test','99')]]}
def capture(a,c,kind,value=None,reference=None,executed=True):
    value=value or body(kind)
    if kind=='agreement' and executed and value['executed_evidence_id'] is None:
        proof=evidence(a,c,'signature','Synthetic supplied executed agreement; owner attestation, not cryptographic authenticity');value=dict(value,executed_evidence_id=proof.pk,executed_sha256=proof.sha256)
    e=evidence(a,c,'partner_'+kind,value);return domain.capture(a,c.pk,kind,reference or kind,e.pk,rev(c))
def fixture(configured=True):
    a,c=setup_case(kind='support');fin=get_user_model().objects.create_user(username='finance-recipient')
    for action in ['case.read','baas.read','partner.read','partner.finance.receive','partner.finance.import','finance.read','finance.billing.capture','partner.report.review','evidence.add']:Grant.objects.create(case=c,user=fin,action=action)
    owner=evidence(a,c,'policy_decision','Synthetic roles only')
    refs=[register_reference(a,c.pk,'partner-role:'+role,'schema:psl/role-assignment/v1',{'role':role,'user_id':person.pk},owner.pk).ref for role,person in [('PM',a),('Finance',fin)]];activate(a,c,'D05.role_principal_assignments',refs,owner)
    f=json.loads((settings.BASE_DIR/'fixtures/partner-operations.json').read_text(encoding='utf-8'));f['activity']['recipient_id']=fin.pk
    cover=evidence(a,c,'billing_coverage','Synthetic permitted contract coverage')
    period=body('activity')['period'];cov=billing.register_coverage(a,c.pk,'coverage-1','customer-1','payments','contract-1','NGN','net_exclusive',period,period,'complete',cover.pk,rev(c));f['meter']['coverage_id']=cov.pk
    if configured:
        for k,v in [(DEADLINES,f['deadlines']),(STAGES,f['stages']),(ACTIVITY,f['activity']),(METER,f['meter'])]:policy(a,c,k,v)
    return a,c,fin,f,cov
def terms(a,c,r,purpose='terms',verdict='approve'):
    e=evidence(a,c,'partner_decision','Synthetic exact agreement evidence reviewed');return domain.decide_agreement(a,c.pk,r.pk,purpose,verdict,'PM',e.pk,'Synthetic owner term review, not automatic renewal',rev(c))
def stage(a,c,r,key='review',operation='enter',at=None,proofs=None):
    e=evidence(a,c,'partner_stage','Synthetic actual stage event');proofs=proofs if proofs is not None else [evidence(a,c,'document','Synthetic verified document').pk]
    return domain.transition_stage(a,c.pk,r.pk,operation,key,at or timezone.now()-timedelta(hours=5),'PM',e.pk,proofs,rev(c))
def report(a,c,r=None):return domain.build_report(a,c.pk,(r or capture(a,c,'activity')).pk,rev(c))
def review(fin,c,r,verdict='approve'):
    e=evidence(fin,c,'partner_decision','Synthetic exact activity review');return domain.review_report(fin,c.pk,r.pk,verdict,'Finance',e.pk,rev(c))
def delivered(a,c,fin,r):
    review(fin,c,r);j=domain.reserve(a,c.pk,r.pk,'PM',rev(c));partner_delivery.run_once();return PartnerFinanceReceipt.objects.get(job=j)

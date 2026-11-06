import json,copy
from datetime import timedelta
from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils import timezone
from apps.core.services import add_evidence
from apps.identity.models import Grant
from apps.policy.services import register_reference,transition
from apps.policy.baas_drafts import draft_baas_policy
from apps.baas import reconciliation as recon,corrective,corrective_delivery
from apps.baas.models import CorrectiveDelivery
from .helpers import setup_case,activate,rev

def evidence(a,c,kind,value):return add_evidence(a,c.pk,kind,json.dumps(value) if not isinstance(value,str) else value,'synthetic:reconciliation-tests',rev(c))
def policy(a,c,key,value):
    e=evidence(a,c,'policy_decision','Synthetic explicit reconciliation policy, not operational authority')
    config=draft_baas_policy(a,c.pk,key,value,e.pk,timezone.now()-timedelta(days=1));transition(a,config.pk,'validated');transition(a,config.pk,'active');return config

def fixture(configured=True):
    a,c=setup_case(kind='support');engineer=get_user_model().objects.create_user(username='engineer')
    for action in ['case.read','baas.read','baas.engineering.receive','baas.engineering.record','evidence.add']:Grant.objects.create(case=c,user=engineer,action=action)
    owner=evidence(a,c,'policy_decision','Synthetic configured Finance requester and Engineering recipient')
    refs=[register_reference(a,c.pk,'role:'+role,'schema:psl/role-assignment/v1',{'role':role,'user_id':person.pk},owner.pk).ref for role,person in [('Finance',a),('Engineering',engineer)]]
    activate(a,c,'D05.role_principal_assignments',refs,owner)
    f=json.loads((settings.BASE_DIR/'fixtures/baas-reconciliation.json').read_text(encoding='utf-8'));f['commands']['recipient_id']=engineer.pk
    if configured:
        policy(a,c,recon.CONTRACT,f['contract']);policy(a,c,recon.COMMANDS,f['commands'])
    batches={}
    for kind in ['ledger','settlement','queue']:batches[kind]=batch(a,c,kind)
    return a,c,engineer,f,batches

def body(kind):
    stamp=timezone.now().isoformat();rows=[]
    for tx,amount,status in [('tx-1','100','settled'),('tx-2','20','pending'),('tx-3','30','failed')]:
        rows.append({'partner':'partner-1','transaction':tx,'customer':'customer-'+tx[-1],'currency':'NGN','amount':amount,'status':status if kind=='settlement' else 'reported','account':'client-account','queue_state':'pending' if kind=='queue' else None,'observed_at':stamp})
    return {'kind':kind,'source':'synthetic-'+kind,'as_of':stamp,'completeness':'complete','partners':['partner-1'],'rows':rows}

def batch(a,c,kind,value=None,reference=None):
    proof=evidence(a,c,'reconciliation_input',value or body(kind));return recon.capture(a,c.pk,reference or kind,proof.pk,rev(c))
def attest(a,c,b):
    proof=evidence(a,c,'reconciliation_attestation',{'batch_sha256':b.evidence.sha256,'source':b.payload['source']});return recon.attest(a,c.pk,b.pk,'Finance',proof.pk,rev(c))
def run(a,c,b,attestation=True):
    if attestation and b.get('settlement'):attest(a,c,b['settlement'])
    return recon.investigate(a,c.pk,b['ledger'].pk if b.get('ledger') else None,b['settlement'].pk if b.get('settlement') else None,b['queue'].pk if b.get('queue') else None,rev(c))
def request(a,c,r,kind='corrective_credit',amount='100',reference='REQ-1',operation='OP-1'):
    v={'partner':'partner-1','transaction':'tx-1','customer':'customer-1','command':'credit','kind':kind,'amount':amount,'currency':'NGN','from_account':None,'to_account':'client-account','from_state':None,'to_state':None}
    if kind=='fund_movement':v.update(command='move',from_account='operating-account',to_account='reserve-account')
    if kind=='queue_transition':v.update(transaction='tx-2',customer='customer-2',command='release-queue',amount=None,from_account=None,to_account=None,from_state='pending',to_state='ready')
    proof=evidence(a,c,'corrective_request',v);return corrective.capture(a,c.pk,r.pk,reference,operation,proof.pk,'Synthetic precise corrective request',rev(c))
def decide(a,c,r,verdict='approve'):
    proof=evidence(a,c,'corrective_decision','Synthetic exact configured human decision')
    return corrective.decide(a,c.pk,r.pk,'Finance',verdict,proof.pk,'Synthetic current source, request, amount and authority reviewed',rev(c))
def delivery(a,c,r):
    decide(a,c,r);j=corrective.reserve(a,c.pk,r.pk,'Finance',rev(c));corrective_delivery.run_once();return CorrectiveDelivery.objects.get(request=r)
def outcome(engineer,c,d,status='applied',reference='EXTERNAL-1'):
    v={'operation_key':d.operation_key,'request_hash':d.payload['request_hash'],'source':'synthetic-engineering-register','external_reference':reference,'status':status,'observed_at':timezone.now().isoformat(),'command':d.payload['command']}
    proof=evidence(engineer,c,'engineering_outcome',v);return corrective.record_outcome(engineer,c.pk,d.pk,proof.pk,rev(c))
def verify(a,c,o):
    proof=evidence(a,c,'engineering_outcome_verification',o.payload);return corrective.verify_outcome(a,c.pk,o.pk,'Finance',proof.pk,rev(c))

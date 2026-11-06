import json,os,time
from pathlib import Path
from django.utils import timezone
from django.conf import settings
from apps.policy.followup_transport_validators import INBOUND
from apps.policy.operator_drafts import draft_operator_policy
from apps.policy.services import transition
from apps.core.services import add_evidence
from adapters import finance_followup_protocol as wire
from apps.documents.contracts import digest

SECRET='synthetic-finance-inbox-key-32-characters-minimum'
def registry(c,secret=SECRET):
    os.environ['PSL_TEST_FINANCE_INBOX_KEY']=secret
    return {'FINANCE_INBOX_SENDERS':{'sender:fixture':{'credential_ref':'secret:finance-inbox','credential_revision':'fixture-v1','destination_ref':'inbox:fixture','case_ids':[str(c.pk)],'classification':'synthetic'}},
        'READINESS_SECRET_REFS':{'secret:finance-inbox':{'env':'PSL_TEST_FINANCE_INBOX_KEY','revision':'fixture-v1'}}}

def configure(a,c):
    proof=add_evidence(a,c.pk,'integration_contract','Synthetic reviewed signed metadata intake; no decision or financial authority','synthetic:intake')
    e=add_evidence(a,c.pk,'policy_decision','Synthetic source intake principal and protocol criteria; no real appointment','synthetic:intake')
    v=json.loads(Path('fixtures/finance-followup-transport.json').read_text())['inbound_template'];v.update(principal_id=a.pk,evidence_id=proof.pk)
    cfg=draft_operator_policy(a,c.pk,INBOUND,v,e.pk,timezone.now());transition(a,cfg.pk,'validated');transition(a,cfg.pk,'active')
    return cfg,v

def envelope(c,job,key='a'*64):
    p={'format':'psl.finance-receipt-followup/v1','source_case_id':str(c.pk),'source_invoice_id':job.invoice_id,'source_correction_id':job.intent.get('correction'),
       'variant':job.kind,'mapping_sha256':'b'*64,'observation_sha256':'c'*64,'packet_sha256':'d'*64,'publication_operation':'e'*64,
       'outcome':'unknown','business_jobs_reenacted':False,'debt_waived':False,'activation_enabled':False}
    return {'format':wire.FORMAT,'operation_key':key,'sender_ref':'sender:fixture','destination_ref':'inbox:fixture','projection':p,'publication_receipt_sha256':'f'*64}

def command(client,c,value,method='POST',stamp=None,secret=SECRET,body=None):
    path=wire.path(c.pk,value['operation_key']);raw=(wire.encode(value) if method=='POST' else b'') if body is None else body;stamp=stamp or str(int(time.time()))
    headers={'HTTP_X_PSL_SENDER':value['sender_ref'],'HTTP_X_PSL_DATE':stamp,'HTTP_X_PSL_SIGNATURE':wire.signature(secret,method,path,stamp,raw)}
    return client.generic(method,path,raw,content_type='application/json',**headers)

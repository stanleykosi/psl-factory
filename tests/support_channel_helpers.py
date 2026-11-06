import json,os,threading,copy
from datetime import timedelta
from contextlib import contextmanager
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
from django.conf import settings
from django.test import override_settings
from django.utils import timezone
from apps.baas import support_channel as d,support_channel_delivery as worker
from apps.policy.support_channel_validators import RECEIPTS,CLOCK
from .support_release_helpers import ready as release_ready,release
from .support_helpers import evidence,policy

def fixture(prefix='support-channel',clock=True,configured=True):
 f=release_ready(prefix);f['release_job']=release(f)
 values=json.loads((settings.BASE_DIR/'fixtures/support-channel.json').read_text(encoding='utf-8'));e=evidence(f,'agent_private_support_channel_contract','EXPLICIT SYNTHETIC PSL receipt-gateway protocol and delivered human-message meaning, not native vendor acceptance')
 f['channel_rules']=dict(values['receipts'],contract_evidence_id=e.pk,customer_ref=f['intake'].payload['customer_ref'],verifier_id=f['actor'].pk,reviewer_id=f['reviewer'].pk);f['clock_rules']=dict(values['clock'],attestor_id=f['actor'].pk)
 if configured:
  f['channel_policy']=policy(f,RECEIPTS,f['channel_rules'])
  if clock:f['clock_policy']=policy(f,CLOCK,f['clock_rules'])
 return f

def claim(f,key='claim',external='customer-receipt-1'):
 r=d.capture(f['actor'],f['case'].pk,f['release_job'].packet_id,key,external,'v1');f['claim']=r;return r

def output(f,changes=None):
 r=f['claim'];now=timezone.now();value=dict(r.payload,principal_ref=f['channel_rules']['principal_ref'],contract_version=f['channel_rules']['contract_version'],status='delivered',human_response=True,sent_at=now.isoformat(),delivered_at=now.isoformat());value.update(changes or {});return value

def verify(f,remote,key='verify',changes=None):
 if 'claim' not in f:claim(f)
 remote['receipts'][f['claim'].payload['receipt_key']]=output(f,changes);j=d.reserve(f['actor'],f['case'].pk,f['claim'].pk,key);worker.run_once(f['case'].pk);j.refresh_from_db()
 if j.status!='confirmed':raise AssertionError('Channel verification '+j.status)
 receipt=d.Receipt.objects.get(job=j);f['channel_receipt']=receipt;return receipt

def reviewed(f,remote,key='verify'):
 receipt=verify(f,remote,key);d.review(f['reviewer'],f['case'].pk,receipt.pk,'confirm');return receipt

@contextmanager
def gateway():
 state={'receipts':{},'calls':0,'paths':[],'authorisations':[],'lose_response':False,'redirect':False,'wire':None,'secret':'EXPLICIT-SYNTHETIC-CHANNEL-TOKEN'}
 class Handler(BaseHTTPRequestHandler):
  def log_message(self,*args):pass
  def do_GET(self):
   state['calls']+=1;state['paths'].append(self.path);state['authorisations'].append(self.headers.get('Authorization'))
   if self.headers.get('Authorization')!='Bearer '+state['secret']:
    self.send_response(401);self.end_headers();return
   if state['redirect']:
    self.send_response(302);self.send_header('Location','http://127.0.0.1:1/private');self.end_headers();return
   if state['lose_response']:
    self.connection.shutdown(2);self.connection.close();return
   key=self.path.removeprefix('/support-receipts/');value=state['receipts'].get(key)
   if value is None:self.send_response(404);self.end_headers();return
   body=state['wire'] if state['wire'] is not None else json.dumps(value).encode();self.send_response(200);self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(body)
  def do_POST(self):raise AssertionError('Read-only channel adapter must never dispatch')
 server=ThreadingHTTPServer(('127.0.0.1',0),Handler);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start();old=os.environ.get('PSL_TEST_CHANNEL_TOKEN');os.environ['PSL_TEST_CHANNEL_TOKEN']=state['secret']
 endpoints=dict(settings.READINESS_ENDPOINTS,**{'endpoint:channel-fixture':{'url':f'http://127.0.0.1:{server.server_port}','classification':'synthetic'}});secrets=dict(settings.READINESS_SECRET_REFS,**{'secret:channel-fixture':{'env':'PSL_TEST_CHANNEL_TOKEN','revision':'fixture-v1'}})
 try:
  with override_settings(READINESS_ENDPOINTS=endpoints,READINESS_SECRET_REFS=secrets):yield state
 finally:
  server.shutdown();server.server_close();thread.join(timeout=5)
  if old is None:os.environ.pop('PSL_TEST_CHANNEL_TOKEN',None)
  else:os.environ['PSL_TEST_CHANNEL_TOKEN']=old

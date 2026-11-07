import json,copy,os,threading
from pathlib import Path
from datetime import timedelta
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
from contextlib import contextmanager
from django.test import override_settings
from django.contrib.auth import get_user_model
from django.db import connection
from django.utils import timezone
from apps.identity.models import Grant
from apps.core.services import add_evidence
from apps.core.management.commands.seed_demo import ACTIONS
from apps.policy.services import register_reference,transition
from apps.policy.readiness_drafts import draft_readiness_policy
from apps.policy.readiness_validators import ADAPTER,PROVIDER
from apps.workflows import readiness as d,readiness_delivery as w
from apps.workflows.readiness_models import IntegrationObservation
from adapters.readiness import CANARY
from .helpers import setup_case,project_evidence,activate,rev
def evidence(f,kind,value='Explicit synthetic integration evidence; not real appointment or acceptance'):
 return add_evidence(f['actor'],f['case'].pk,kind,json.dumps(value) if isinstance(value,dict) else value,'synthetic:readiness-tests')
def policy(f,key,value=None):
 p=draft_readiness_policy(f['actor'],f['case'].pk,key,value or f['rules'],f['sources']['policy_decision'].pk,timezone.now()-timedelta(seconds=1));transition(f['actor'],p.pk,'validated');transition(f['actor'],p.pk,'active');return p
def fixture(prefix='integration',configured=True,kind='adapter',family='handoff',known=True):
 a,c=setup_case(username=prefix+'-actor');b=get_user_model().objects.create_user(username=prefix+'-reviewer');Grant.objects.bulk_create([Grant(case=c,user=b,action=x) for x in ACTIONS]);s=project_evidence(a,c);refs=[]
 for u,role in [(a,r) for r in ['PM','Head of PMO','CEO','PMO Lead']]+[(b,'PMO')]:refs.append(register_reference(a,c.pk,prefix+'-role:'+role,'schema:psl/role-assignment/v1',{'role':role,'user_id':u.pk},s['policy_decision'].pk).ref)
 activate(a,c,'D05.role_principal_assignments',refs,s['policy_decision']);f={'actor':a,'reviewer':b,'case':c,'sources':s,'rules':dict(json.loads((Path(__file__).resolve().parent.parent/'fixtures/integration-readiness.json').read_text(encoding='utf-8'))['rules'],probe_user_id=a.pk,reviewer_id=b.pk)}
 if configured:f['policy']=policy(f,ADAPTER if kind=='adapter' else PROVIDER)
 body={'kind':kind,'family':family if kind=='adapter' else 'provider','implementation':'internal_postgres_session_v1' if kind=='adapter' else 'authenticated_json_v1','target_key':'internal:'+family if kind=='adapter' else 'endpoint:fixture','credential_ref':'runtime:postgres' if kind=='adapter' else 'secret:fixture','credential_revision':'fixture-v1','principal_ref':'principal:'+connection.settings_dict['USER'] if kind=='adapter' else 'principal:fixture','contract_version':'psl.internal-receipts/v1' if kind=='adapter' else 'fixture-model/v1','model_id':None if kind=='adapter' else 'fixture-model','capabilities':['health','receipt_lookup'] if kind=='adapter' else ['health','receipt_lookup','evaluation'],'data_scope':'public_canary_and_scoped_receipt_metadata_only'}
 if not known:
  for k in ['target_key','credential_ref','credential_revision','principal_ref','contract_version','model_id']:body[k]=None
 f['contract']=d.capture(a,c.pk,'primary',body,evidence(f,'integration_contract').pk);f['review_evidence']=evidence(f,'integration_review');f['selection_evidence']=evidence(f,'integration_selection');return f
def probe(f,kind='health',key=None,source_id=None):
 j=w.reserve(f['actor'],f['case'].pk,f['contract'].pk,key or kind,kind,source_id);w.run_once();j.refresh_from_db()
 if j.status!='confirmed':raise AssertionError('Readiness probe '+j.status)
 return j,IntegrationObservation.objects.get(job=j)
def ready(f,key='ready'):
 probe(f);r=d.assess(f['actor'],f['case'].pk,f['contract'].pk,key);d.review(f['reviewer'],f['case'].pk,r.pk,'confirm',key,f['review_evidence'].pk);return r
def handoff(f):
 from apps.pmo.services import prepare_baseline,decide,sign_baseline,complete_milestone
 from apps.workflows.models import Outbox
 a,c,s=f['actor'],f['case'],f['sources'];prepare_baseline(a,c.pk,s['plan'].pk,s['costing'].pk,s['sow'].pk,rev(c))
 for role in ['PM','Head of PMO','CEO','PMO Lead']:decide(a,c.pk,role,rev(c))
 from tests.signature_helpers import packet_for
 packet_for(a, c, s)
 sign_baseline(a,c.pk,s['signature'].pk,rev(c));complete_milestone(a,c.pk,'Readiness bridge',s['completion'].pk,rev(c));return Outbox.objects.get(case=c)

@contextmanager
def endpoint():
 state={'secret':'EXPLICIT-SYNTHETIC-READINESS-TOKEN','status':'available','principal':'principal:fixture','receipts':{},'calls':0,'bad_output':False,'redirect':False,'lose_response':False}
 class Handler(BaseHTTPRequestHandler):
  def log_message(self,*args):pass
  def output(self,status,value):
   body=json.dumps(value).encode();self.send_response(status);self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(body)
  def do_GET(self):
   if self.headers.get('Authorization')!='Bearer '+state['secret']:return self.output(401,{'error':state['secret']})
   if state['redirect']:
    self.send_response(302);self.send_header('Location','http://127.0.0.1:1/leak');self.end_headers();return
   if self.path=='/health':return self.output(200,{'status':state['status'],'principal_ref':state['principal'],'contract_version':state.get('contract_version','fixture-model/v1'),'model_id':'fixture-model','capabilities':['health','receipt_lookup','evaluation']})
   key=self.path.removeprefix('/factory/plans/').removeprefix('/receipts/').removeprefix('/extractions/');return self.output(200,state['receipts'].get(key,{'operation_key':key,'status':'not_found','result':None}))
  def do_POST(self):
   if self.headers.get('Authorization')!='Bearer '+state['secret']:return self.output(401,{'error':state['secret']})
   body=json.loads(self.rfile.read(int(self.headers.get('Content-Length','0'))))
   if self.path=='/factory/plans':
    key=self.headers['Idempotency-Key']
    if key not in state['receipts']:
     canary=body['citation_handles']==['probe0']
     counter='planning_evaluations' if canary else 'planning_calls';state[counter]=state.get(counter,0)+1
     if not canary:state.setdefault('planning_inputs',[]).append(body)
     value=state.get('planning_canary_output' if canary else 'planning_output',{'activity':body['eligible'][0],'citations':body['citation_handles'][:1]})
     if not state.get('planning_no_commit'):state['receipts'][key]={'operation_key':key,'status':'succeeded','result':value}
    if not body['citation_handles']==['probe0'] and state.get('planning_entered'):
     state['planning_entered'].set();state['planning_release'].wait(timeout=15)
    if not body['citation_handles']==['probe0'] and state.get('lose_planning_response'):
     self.connection.shutdown(2);self.connection.close();return
    return self.output(200,state['receipts'][key]['result'])
   if self.path=='/extract':
    key=self.headers['Idempotency-Key']
    if key not in state['receipts']:
     state['calls']+=1;state.setdefault('private_inputs',[]).append(body);value=state.get('private_output',{'facts':[{'quote':body['input'][0]}],'uncertainties':[],'proposed_actions':[]});state['receipts'][key]={'operation_key':key,'status':'succeeded','result':value}
    if state['lose_response']:
     self.connection.shutdown(2);self.connection.close();return
    if 'private_wire' in state:
     self.send_response(200);self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(state['private_wire']);return
    return self.output(200,state['receipts'][key]['result'])
   assert body=={'model_id':'fixture-model','input':CANARY,'data_scope':'public_canary_v1'}
   key=self.headers['Idempotency-Key']
   if key not in state['receipts']:
    state['calls']+=1;value={'facts':[{'quote':'wrong' if state['bad_output'] else CANARY}],'uncertainties':[],'proposed_actions':[]};state['receipts'][key]={'operation_key':key,'status':'succeeded','result':value}
   if state['lose_response']:
    self.connection.shutdown(2);self.connection.close();return
   return self.output(200,state['receipts'][key]['result'])
 server=ThreadingHTTPServer(('127.0.0.1',0),Handler);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start();old=os.environ.get('PSL_TEST_READINESS_TOKEN');os.environ['PSL_TEST_READINESS_TOKEN']=state['secret']
 try:
  with override_settings(READINESS_ENDPOINTS={'endpoint:fixture':{'url':f'http://127.0.0.1:{server.server_port}','classification':'synthetic'}},READINESS_SECRET_REFS={'secret:fixture':{'env':'PSL_TEST_READINESS_TOKEN','revision':'fixture-v1'}}):yield state
 finally:
  server.shutdown();server.server_close();thread.join(timeout=5)
  if old is None:os.environ.pop('PSL_TEST_READINESS_TOKEN',None)
  else:os.environ['PSL_TEST_READINESS_TOKEN']=old

"""Reviewed, bounded probes. No arbitrary URLs, SQL, secrets in evidence, or business dispatch."""
import os,json,hmac,hashlib,urllib.request,urllib.error,urllib.parse
from django.conf import settings
from django.db import connection
from django.core.exceptions import ValidationError
from apps.documents.contracts import digest,validate
from adapters.costing import read
from adapters.forecast import obj,KEY
import psycopg
CANARY='PSL readiness canary: evidence remains evidence.'
VERSION={'type':'string','pattern':'^[A-Za-z0-9][A-Za-z0-9_.:/-]{0,99}$'}
CAPS=['health','receipt_lookup','evaluation']
HEALTH=obj({'status':{'enum':['available','unavailable']},'principal_ref':KEY,'contract_version':VERSION,'model_id':{'anyOf':[VERSION,{'type':'null'}]},'capabilities':{'type':'array','uniqueItems':True,'maxItems':3,'items':{'enum':CAPS}}})
RECEIPT=obj({'operation_key':{'type':'string','pattern':'^[a-f0-9]{64}$'},'status':{'enum':['not_found','succeeded','failed']},'result':{'anyOf':[{'type':'object'},{'type':'null'}]}})
TABLES={'ledgerdata':['agents_evidenceextractionreceipt'],'supportchannel':['baas_supportchannelreceipt'],'supportresponse':['baas_supportresponsereceipt'],'handoff':['finance_handoff'],'publication':['documents_publicationreceipt'],'invoice':['finance_invoiceissue','finance_invoicedelivery'],'engineering':['baas_correctivedelivery'],'partner':['baas_partnerfinancereceipt'],'approval':['pmo_approvalroutereceipt'],'protection':['psl_metadata_drill_receipt']}
TABLES['financefollowup']=['workflows_financefollowupdispatch']

def binding(contract):
 v=contract.payload
 if v['kind']=='provider' and v['model_id'] is None:raise ValidationError('Explicit provider model/version required')
 if any(v[k] is None for k in ['target_key','credential_ref','credential_revision','principal_ref','contract_version']):raise ValidationError('Target/credential/principal/version remains unconfigured')
 if v['implementation']=='internal_postgres_session_v1':
  if v['kind']!='adapter' or v['target_key']!='internal:'+v['family'] or v['credential_ref']!='runtime:postgres' or not settings.READINESS_DATABASE_REVISION or v['credential_revision']!=settings.READINESS_DATABASE_REVISION:raise ValidationError('Reviewed runtime database reference/version required')
  args=connection.get_connection_params().copy()
  from apps.workflows.private_file_readiness import binding as file_binding
  from apps.workflows.accepted_protection_readiness import binding as accepted_binding
  accepted=accepted_binding(contract)
  if v['family']=='protection' and not file_binding(contract) and not (accepted and accepted.job.kind in ['export','backup']):
   from adapters.operator_protection import target_identity
   target_identity();args['dbname']=settings.OPERATOR_DRILL_DATABASE
  secret=str(args.get('password',''));private={'args':args};public={'implementation':v['implementation'],'target':digest({k:str(args.get(k,'')) for k in ['dbname','host','port','user']}),'credential_ref':v['credential_ref'],'revision':v['credential_revision'],'classification':'native_database_session','auth_mode':'postgres_session'}
 elif v['implementation']=='authenticated_json_v1':
  endpoint=settings.READINESS_ENDPOINTS.get(v['target_key']);credential=settings.READINESS_SECRET_REFS.get(v['credential_ref'])
  if not isinstance(endpoint,dict) or set(endpoint)!={'url','classification'} or endpoint['classification'] not in ['synthetic','operational'] or not isinstance(credential,dict) or set(credential)!={'env','revision'} or credential['revision']!=v['credential_revision']:raise ValidationError('Reviewed endpoint/credential registry entry required')
  url=urllib.parse.urlsplit(endpoint['url'])
  if url.username or url.password or url.query or url.fragment or url.path not in ['', '/'] or not url.hostname:raise ValidationError('Reviewed origin only; no URL credentials, paths or query')
  if url.scheme!='https' and not (url.scheme=='http' and url.hostname in ['127.0.0.1','localhost','::1'] and contract.case.synthetic and endpoint['classification']=='synthetic'):raise ValidationError('Verified HTTPS required outside explicit synthetic loopback')
  if not contract.case.synthetic and endpoint['classification']=='synthetic':raise ValidationError('Synthetic endpoint cannot be promoted')
  secret=os.getenv(credential['env'])
  if not secret or len(secret)>4096 or any(c in secret for c in '\r\n'):raise ValidationError('Credential reference unavailable or malformed')
  private={'url':endpoint['url'].rstrip('/'),'secret':secret};public={'implementation':v['implementation'],'target':digest({'url':private['url']}),'credential_ref':v['credential_ref'],'revision':credential['revision'],'classification':'synthetic_authenticated_http' if endpoint['classification']=='synthetic' else 'authenticated_remote_claim','auth_mode':'bearer'}
 else:raise ValidationError('Native implementation is not registered')
 # Keyed binding detects rotation even if an operator forgets to change a revision. Never store the credential or an unkeyed password hash.
 public['credential_binding']=hmac.new(settings.SECRET_KEY.encode(),secret.encode(),hashlib.sha256).hexdigest()
 return public,private

class NoRedirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,*args,**kwargs):return None
def http(private,path,method='GET',body=None,key=None):
 headers={'Authorization':'Bearer '+private['secret'],'Accept':'application/json'}
 if key:headers['Idempotency-Key']=key
 if body is not None:headers['Content-Type']='application/json'
 request=urllib.request.Request(private['url']+path,data=json.dumps(body).encode() if body is not None else None,headers=headers,method=method)
 try:
  # No environment proxy inheritance, redirects, arbitrary paths or response bodies in exceptions.
  opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
  with opener.open(request,timeout=5) as response:
   raw=response.read(16385)
   if len(raw)>16384 or response.headers.get_content_type()!='application/json':raise ValidationError('Bounded JSON response required')
 except urllib.error.HTTPError as e:
  if e.code in [401,403]:raise ValidationError('Authentication rejected') from None
  raise ConnectionError('Authenticated endpoint unavailable') from None
 except (OSError,TimeoutError):raise ConnectionError('Authenticated endpoint unavailable') from None
 return read(raw.decode('utf-8'),{'type':'object'})

def evaluate_result(value,protocol=None):
 # Fixed public canary and independently fixed oracle; never repair provider output.
 expected={'facts':[{'quote':CANARY}],'uncertainties':[],'proposed_actions':[]}
 from adapters.factory_planner_contracts import PROTOCOL,CANARY_RESULT
 if protocol==PROTOCOL:expected=CANARY_RESULT
 try:output_sha256=digest(value)
 except (ValueError,TypeError,RecursionError):raise ValidationError('Malformed provider evaluation response') from None
 return {'outcome':'passed' if value==expected else 'failed','oracle_match':value==expected,'output_sha256':output_sha256,'private_source_sent':False,'business_tools_executed':False}

class ReadinessAdapter:
 def lookup(self,job):
  from apps.workflows.readiness_models import IntegrationObservation
  old=IntegrationObservation.objects.filter(job=job).first()
  if old:return old.payload
  if job.intent['kind']!='evaluation':return None
  current,private=binding(job.contract)
  if current!=job.intent['binding']:raise ConnectionError('Original authenticated target binding unavailable')
  from adapters.factory_planner_contracts import PROTOCOL
  prefix='/factory/plans/' if job.contract.payload['contract_version']==PROTOCOL else '/receipts/'
  value=http(private,prefix+job.operation_key);validate(RECEIPT,value)
  if value['operation_key']!=job.operation_key:raise ValidationError('Receipt identity conflict')
  if value['status']=='not_found':
   if value['result'] is not None:raise ValidationError('Conflicting absent receipt')
   return None
  result=evaluate_result(value['result'],job.contract.payload['contract_version']);result.update(classification=current['classification'],kind='evaluation',authenticated_transport=True)
  if value['status']=='failed':result['outcome']='failed'
  return result
 def probe(self,job):
  v=job.contract.payload;current,private=binding(job.contract)
  if current!=job.intent['binding']:raise ValidationError('Reserved identity/credential binding changed')
  kind=job.intent['kind'];base={'kind':kind,'classification':current['classification'],'authenticated_transport':True}
  if v['implementation']=='internal_postgres_session_v1':
   args=dict(private['args'],connect_timeout=5)
   args['options']=(args.get('options','')+' -c statement_timeout=5000').strip()
   try:
    with psycopg.connect(**args) as conn:
     principal,dbname=conn.execute('SELECT current_user,current_database()').fetchone()
     from apps.workflows.private_file_readiness import binding as file_binding
     from apps.workflows.accepted_protection_readiness import binding as accepted_binding
     accepted=accepted_binding(job.contract)
     tables=['workflows_recoveryjob','workflows_recoveryartifact'] if file_binding(job.contract) or accepted and accepted.job.kind in ['export','backup'] else TABLES[v['family']]
     allowed=all(conn.execute('SELECT has_table_privilege(current_user,%s,%s)',[table,'SELECT']).fetchone()[0] for table in tables)
   except psycopg.Error:raise ConnectionError('Configured database session unavailable') from None
   identity='principal:'+principal==v['principal_ref'] and dbname==args['dbname'] and v['contract_version']=='psl.internal-receipts/v1'
   from apps.finance.publication_readiness import binding as native_binding,observation as native_observation
   from apps.workflows.private_protection_readiness import binding as private_binding,observation as private_observation
   from apps.workflows.private_file_readiness import binding as file_binding,observation as file_observation
   if accepted:
    if kind not in ['health','receipt'] or not identity or not allowed:raise ValidationError('AF13 native SQL identity and health/receipt capabilities required')
    from adapters.accepted_protection_readiness import AcceptedProtectionReadinessAdapter
    from apps.workflows.accepted_protection_readiness import observation
    value=dict(base,outcome='passed',identity_match=True,capabilities_verified=allowed,password_authentication_proven=False,**AcceptedProtectionReadinessAdapter().health(accepted.job))
    if kind=='receipt':value['lookup_verified']=True
    return observation(job.contract,job,value)
   if file_binding(job.contract):
    if kind not in ['health','receipt'] or not identity or not allowed:raise ValidationError('Native file needs exact SQL identity and receipt capabilities')
    from adapters.private_file_readiness import PrivateFileReadinessAdapter
    value=dict(base,outcome='passed',identity_match=True,capabilities_verified=allowed,password_authentication_proven=False,**PrivateFileReadinessAdapter().health(file_binding(job.contract).job))
    if kind=='receipt':value['lookup_verified']=True
    return file_observation(job.contract,job,value)
   if private_binding(job.contract):
    if kind not in ['health','receipt'] or not identity or not allowed:raise ValidationError('Private protection needs authenticated local health/receipt capability')
    value=dict(base,outcome='passed',identity_match=True,capabilities_verified=allowed,password_authentication_proven=False)
    if kind=='receipt':value['lookup_verified']=True
    return private_observation(job.contract,job,value)
   if native_binding(job.contract):
    if kind not in ['health','receipt'] or not identity or not allowed:raise ValidationError('Native publication needs authenticated local health/receipt capability')
    value=dict(base,outcome='passed',identity_match=True,capabilities_verified=allowed,password_authentication_proven=False)
    if kind=='receipt':value['lookup_verified']=True
    return native_observation(job.contract,job,value)
   if kind=='health':return dict(base,outcome='passed' if identity and allowed else 'failed',identity_match=identity,capabilities_verified=allowed,password_authentication_proven=False)
   if kind!='receipt' or not identity or not allowed:raise ValidationError('Verified scoped receipt capability required')
   from apps.workflows.readiness import source_job,lookup_source
   source=source_job(job.actor,job.contract.case,v['family'],job.intent['source_job'])
   from django.db import DatabaseError
   try:receipt=lookup_source(v['family'],source)
   except DatabaseError:raise ConnectionError('Scoped receipt lookup unavailable') from None
   return dict(base,outcome='passed',identity_match=True,lookup_verified=True,business_receipt='found' if receipt else 'not_found',business_receipt_sha256=digest({'operation_key':str(source.publication.operation_key if v['family']=='publication' else source.operation_key),'found':bool(receipt)}))
  if kind=='health':
   value=http(private,'/health');validate(HEALTH,value);match=value['principal_ref']==v['principal_ref'] and value['contract_version']==v['contract_version'] and value['model_id']==v['model_id'] and set(v['capabilities'])<=set(value['capabilities'])
   return dict(base,outcome='passed' if match and value['status']=='available' else 'failed',identity_match=match,remote_capability_claim=True)
  if kind=='evaluation' and v['kind']=='provider':
   from adapters.factory_planner_contracts import PROTOCOL,canary_payload
   path='/factory/plans' if v['contract_version']==PROTOCOL else '/evaluate'
   payload=canary_payload(v['model_id']) if v['contract_version']==PROTOCOL else {'model_id':v['model_id'],'input':CANARY,'data_scope':'public_canary_v1'}
   value=http(private,path,'POST',payload,job.operation_key)
   return dict(base,**evaluate_result(value,v['contract_version']))
  raise ValidationError('Reviewed HTTP business receipt/dispatch implementation is not installed')

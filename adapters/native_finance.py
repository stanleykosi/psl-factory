"""Exact incumbent internal Finance receipt verification; no business dispatch."""
import os,re,json,base64,hmac,hashlib
from pathlib import Path
from uuid import UUID
import psycopg
from django.conf import settings
from django.db import connection
from django.core.exceptions import ValidationError
from apps.documents.contracts import validate
from adapters.forecast import obj
from adapters import native_application_archive as n,cold_application_recovery as cold

VERSION='psl.internal-finance-handoff/v1'
FORMAT='psl.native-finance-companion/v1'
PAYLOAD=obj({'milestone_id':{'type':'integer','minimum':1},'name':{'type':'string','minLength':1,'maxLength':200},
    'evidence_id':{'type':'integer','minimum':1},'evidence_sha256':{'type':'string','pattern':'^[a-f0-9]{64}$'}})

def original(plan,effect,max_bytes=1048576):
    if effect['family'] not in ('handoff','invoice'):raise ValidationError('Documented internal Finance contract required')
    _,target,_,_,_=cold.runtime(plan.recovery.intent['payload'])
    with n.connect(target['database']) as db:
        db.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
        db.execute("SET LOCAL statement_timeout='5000'")
        if effect['family']=='invoice':
            from .native_invoice_receipts import original as invoice_original
            return invoice_original(db,effect,max_bytes)
        row=db.execute("SELECT operation_key,payload,case_id::text,milestone_id,encode(sha256(convert_to(to_jsonb(j)::text,'UTF8')),'hex') FROM workflows_outbox j WHERE id=%s AND case_id=%s AND octet_length(payload::text)<=%s",[effect['job_id'],effect['case_id'],max_bytes]).fetchone()
    if not row:raise ValidationError('Exact bounded archived handoff required')
    op,payload,case,milestone,row_sha=row
    validate(PAYLOAD,payload)
    if row_sha!=effect['intent_sha256'] or hashlib.sha256(op.encode()).hexdigest()!=effect['operation_sha256'] or op!=f'milestone:{milestone}:finance:v1' or payload['milestone_id']!=milestone:
        raise ValidationError('Original operation/payload mapping differs from captured inventory')
    metadata={'contract_version':VERSION,'effect_key':effect['effect_key'],'source_case_id':case,'source_milestone_id':milestone,
        'operation_sha256':effect['operation_sha256'],'source_row_sha256':row_sha,'payload_sha256':n.digest(payload)}
    return metadata,op,payload

def registry(ref,synthetic):
    try:
        v=settings.NATIVE_FINANCE['providers'][ref]
        assert set(v)=={'database','host','port','user','password_env','credential_revision','identity_ref','identity_secret_env','classification','sslmode','revision','case_ids'}
        assert re.fullmatch(r'psl_finance_provider_[a-z0-9_]{1,40}',v['database'])
        assert v['classification']==('synthetic' if synthetic else 'operational')
        assert isinstance(v['case_ids'],list) and len(v['case_ids'])==len(set(v['case_ids'])) and all(str(UUID(x))==x for x in v['case_ids'])
        for k in ['credential_revision','identity_ref','revision']:assert re.fullmatch('[A-Za-z0-9:_-]{1,100}',v[k])
        assert isinstance(v['host'],str) and 1<=len(v['host'])<=255 and isinstance(v['user'],str) and 1<=len(v['user'])<=63
        assert type(v['port']) is int and 1<=v['port']<=65535
        assert v['sslmode']=='verify-full' or synthetic and v['host'] in ['127.0.0.1','localhost','::1'] and v['sslmode']=='disable'
        assert re.fullmatch('PSL_NATIVE_FINANCE_PASSWORD_[A-Z0-9_]+',v['password_env'])
        assert re.fullmatch('PSL_NATIVE_FINANCE_IDENTITY_[A-Z0-9_]+',v['identity_secret_env'])
        password=os.environ[v['password_env']];secret=base64.b64decode(os.environ[v['identity_secret_env']],validate=True)
        assert len(secret)==32 and len(password)<=4096 and (synthetic or password)
        blocked={connection.settings_dict['NAME']}
        blocked.update(x['database'] for key in ['archives','targets'] for x in settings.COLD_RECOVERY.get(key,{}).values())
        assert v['database'] not in blocked
    except (KeyError,AssertionError,TypeError,ValueError):raise ValidationError('Independent current Finance provider identity, credentials and exact source scope required') from None
    public={'provider_ref':ref,'registry_sha256':n.digest(v),'principal_ref':'postgres:'+v['user'],
        'credential_revision':v['credential_revision'],'identity_ref':v['identity_ref'],
        'credential_binding':hmac.new(settings.SECRET_KEY.encode(),secret+password.encode(),hashlib.sha256).hexdigest()}
    args=dict(dbname=v['database'],host=v['host'],port=v['port'],user=v['user'],password=password,sslmode=v['sslmode'],connect_timeout=5)
    return v,public,args,secret

def session_identity(db,v):
    user,name,quarantine=db.execute("SELECT current_user,current_database(),current_setting('psl.recovery_quarantined',true)").fetchone()
    if user!=v['user'] or name!=v['database'] or quarantine=='on' or db.execute("SELECT to_regnamespace('psl_recovery_control')").fetchone()[0] is not None:
        raise ValidationError('Recovered/control databases cannot become a current Finance provider')
    exists=db.execute("SELECT to_regclass('public.workflows_coldcontrolidentity')").fetchone()[0]
    if exists and db.execute('SELECT EXISTS(SELECT 1 FROM public.workflows_coldcontrolidentity)').fetchone()[0]:
        raise ValidationError('Cold control authority is not a current Finance provider')

def initialize(ref,synthetic):
    v,_,args,secret=registry(ref,synthetic)
    with psycopg.connect(**args) as db:
        session_identity(db,v)
        if db.execute("SELECT to_regclass('public.psl_native_finance_identity')").fetchone()[0]:raise ValidationError('Provider identity already exists; no overwrite')
        db.execute('CREATE TABLE public.psl_native_finance_identity(reference text PRIMARY KEY,secret_sha256 text NOT NULL,contract_version text NOT NULL)')
        db.execute('INSERT INTO public.psl_native_finance_identity VALUES(%s,%s,%s)',[v['identity_ref'],n.digest(secret),VERSION])

def binding(mapping):
    v,public,args,secret=registry(mapping.provider_ref,mapping.plan.case.synthetic)
    if mapping.payload['source_case_id'] not in v['case_ids']:raise ValidationError('Provider lacks exact archived Finance case binding')
    return public,(v,args,secret)

def verify(mapping,effect,rules,expected_binding):
    metadata,op,payload=original(mapping.plan,effect,rules['max_payload_bytes'])
    if metadata!=mapping.payload:raise ValidationError('Reviewed source mapping changed')
    public,(v,args,secret)=binding(mapping)
    if public!=expected_binding:raise ValidationError('Original reviewed Finance provider binding changed')
    with psycopg.connect(**args) as db:
        db.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
        db.execute("SELECT set_config('statement_timeout',%s,true)",[str(rules['max_seconds']*1000)])
        session_identity(db,v)
        if db.execute("SELECT to_regclass('public.psl_native_finance_identity')").fetchone()[0] is None:raise ValidationError('Fresh independently initialized Finance identity required')
        marker=db.execute('SELECT reference,secret_sha256,contract_version FROM public.psl_native_finance_identity').fetchall()
        if marker!=[(v['identity_ref'],n.digest(secret),VERSION)]:raise ValidationError('Exact fresh Finance provider marker required')
        if metadata['contract_version']!=VERSION:
            from .native_invoice_receipts import receipt
            outcome,receipt_ref,receipt_sha=receipt(db,metadata,payload,rules['max_payload_bytes'])
            return result(mapping,public,outcome,receipt_ref,receipt_sha)
        rows=db.execute('SELECT id,operation_key,case_id::text,milestone_id,payload,received_at FROM public.finance_handoff WHERE operation_key=%s OR (case_id=%s AND milestone_id=%s) ORDER BY id LIMIT 3',[op,metadata['source_case_id'],metadata['source_milestone_id']]).fetchall()
    outcome='unknown';receipt_ref=None;receipt_sha=None
    if rows:
        outcome='conflict'
        if len(rows)==1:
            pk,actual_op,case,milestone,actual_payload,received=rows[0]
            if actual_op==op and case==metadata['source_case_id'] and milestone==metadata['source_milestone_id'] and actual_payload==payload:
                outcome='present';receipt_ref=str(pk)
                receipt_sha=n.digest({'id':pk,'operation_sha256':metadata['operation_sha256'],'case':case,'milestone':milestone,'payload_sha256':n.digest(actual_payload),'received_at':received.isoformat()})
    return result(mapping,public,outcome,receipt_ref,receipt_sha)

def result(mapping,public,outcome,receipt_ref,receipt_sha):
    return {'outcome':outcome,'receipt_ref':receipt_ref,'receipt_sha256':receipt_sha,'provider_binding_sha256':n.digest(public),
        'classification':'native_postgres_finance_receipt','fixture_scope':'synthetic' if mapping.plan.case.synthetic else 'operational',
        'direct_native_verification':True,'direct_vendor_verification':False,'password_authentication_proven':False,'business_jobs_reenacted':False,'debt_waived':False}

def store(ref):
    try:
        v=settings.NATIVE_FINANCE['stores'][ref]
        assert set(v)=={'root','revision'} and re.fullmatch('[A-Za-z0-9:_-]{1,100}',v['revision'])
        root=n.checked_root(v['root'])
        others=[]
        for x in settings.COLD_RECOVERY.get('archives',{}).values():others.append(n.checked_root(x['archives']))
        for x in settings.COLD_RECOVERY.get('targets',{}).values():others.append(n.checked_root(x['attachments']))
        for x in settings.RECONSTITUTION.get('profiles',{}).values():others.extend([n.checked_root(x['artifact_root']),n.checked_root(str(Path(x['receipt_path']).parent))])
        assert all(root!=other and root not in other.parents and other not in root.parents for other in others)
        return root,n.digest(v)
    except (KeyError,AssertionError,TypeError,ValueError):raise ValidationError('Independent nonsymlink companion publication store required') from None

def lookup(intent):
    root,binding=store(intent['store_ref'])
    if binding!=intent['store_binding']:raise ValidationError('Original companion store binding changed')
    key=intent['operation_key']
    if not re.fullmatch('[a-f0-9]{64}',key):raise ValidationError('Exact publication operation required')
    path=root/(key+'.json')
    if not path.exists():return None
    if path.is_symlink() or path.stat().st_size>1048576:raise ValidationError('Bounded immutable companion artifact required')
    receipt=json.loads(path.read_bytes())
    expected={'format':FORMAT,'operation_key':key,'intent_sha256':n.digest(intent),'payload':intent['manifest'],
        'payload_sha256':n.digest(intent['manifest']),'activation_enabled':False,'business_jobs_reenacted':False}
    if receipt!=expected:raise ValidationError('Exact immutable reviewed companion receipt required')
    return receipt

def deliver(intent):
    old=lookup(intent)
    if old is not None:return old
    root,_=store(intent['store_ref'])
    receipt={'format':FORMAT,'operation_key':intent['operation_key'],'intent_sha256':n.digest(intent),'payload':intent['manifest'],
        'payload_sha256':n.digest(intent['manifest']),'activation_enabled':False,'business_jobs_reenacted':False}
    if len(n.encoded(receipt))>1048576:raise ValidationError('Companion metadata exceeds bounded artifact size')
    n.put_once(root/(intent['operation_key']+'.json'),n.encoded(receipt))
    return lookup(intent)

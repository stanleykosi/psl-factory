"""Read-only isolated inventory, authenticated gateway attestations and inert plan artifacts.

Gateway attestations are configured evidence, not direct vendor transaction verification.
No arbitrary model, SQL, path, outbound-enable or archived-job retry tool is exposed.
"""
import hashlib, hmac, json, re
from datetime import datetime, timezone, timedelta
from pathlib import Path
from django.apps import apps
from django.conf import settings
from . import native_application_archive as n, cold_application_recovery as cold

FORMAT = 'psl.reconstitution.v1'
# model, fixed FROM clause, source case, operation identity, historical receipt presence.
ROUTES = {
 'financefollowup': ('workflows.FinanceFollowupDispatch','workflows_financefollowupdispatch j JOIN workflows_nativefinancepacket k ON k.id=j.packet_id JOIN workflows_nativefinancemapping m ON m.id=k.mapping_id JOIN workflows_reconstitutionplan p ON p.id=m.plan_id','p.case_id','j.operation_key','j.receipt IS NOT NULL'),
 'nativefinance': ('workflows.NativeFinancePublicationJob','workflows_nativefinancepublicationjob j JOIN workflows_nativefinancepacket k ON k.id=j.packet_id JOIN workflows_nativefinancemapping m ON m.id=k.mapping_id JOIN workflows_reconstitutionplan p ON p.id=m.plan_id','p.case_id','j.operation_key','j.receipt IS NOT NULL'),
 'handoff': ('workflows.Outbox','workflows_outbox j','j.case_id','j.operation_key',"j.receipt<>''"),
 'publication': ('documents.PublicationJob','documents_publicationjob j JOIN documents_publication p ON p.id=j.publication_id JOIN documents_version v ON v.id=p.version_id JOIN documents_document d ON d.id=v.document_id','d.case_id','p.operation_key','EXISTS(SELECT 1 FROM documents_publicationreceipt r WHERE r.publication_id=p.id)'),
 'invoice': ('finance.InvoiceJob','finance_invoicejob j JOIN finance_invoice i ON i.id=j.invoice_id','i.case_id','j.operation_key','EXISTS(SELECT 1 FROM finance_invoiceissue r WHERE r.job_id=j.id) OR EXISTS(SELECT 1 FROM finance_invoicedelivery r WHERE r.job_id=j.id) OR EXISTS(SELECT 1 FROM finance_invoicecorrectionacceptance r WHERE r.job_id=j.id) OR EXISTS(SELECT 1 FROM finance_invoicecorrectiondelivery r WHERE r.job_id=j.id)'),
 'engineering': ('baas.CorrectiveJob','baas_correctivejob j JOIN baas_correctiverequest p ON p.id=j.request_id','p.case_id','j.operation_key','EXISTS(SELECT 1 FROM baas_correctivedelivery r WHERE r.job_id=j.id)'),
 'partner': ('baas.PartnerFinanceJob','baas_partnerfinancejob j JOIN baas_partnerreport r ON r.id=j.report_id JOIN baas_partnerrecord p ON p.id=r.record_id','p.case_id',"'partner-finance-job:'||j.id::text",'EXISTS(SELECT 1 FROM baas_partnerfinancereceipt r WHERE r.job_id=j.id)'),
 'approval': ('pmo.ApprovalRouteJob','pmo_approvalroutejob j JOIN pmo_approvalrequest p ON p.id=j.request_id','p.case_id','j.operation_key','EXISTS(SELECT 1 FROM pmo_approvalroutereceipt r WHERE r.job_id=j.id)'),
 'supportresponse': ('baas.SupportResponseJob','baas_supportresponsejob j JOIN baas_supportresponsepacket p ON p.id=j.packet_id','p.case_id',"'support-response:'||p.case_id::text||':'||p.id::text",'EXISTS(SELECT 1 FROM baas_supportresponsereceipt r WHERE r.job_id=j.id)'),
 'supportchannel': ('baas.SupportChannelCheck','baas_supportchannelcheck j JOIN baas_supportchannelclaim p ON p.id=j.claim_id','p.case_id','j.operation_key','EXISTS(SELECT 1 FROM baas_supportchannelreceipt r WHERE r.job_id=j.id)'),
 'ledgerdata': ('agents.EvidenceExtraction','agents_evidenceextraction j JOIN agents_evidenceprojection p ON p.id=j.projection_id','p.case_id','j.operation_key','EXISTS(SELECT 1 FROM agents_evidenceextractionreceipt r WHERE r.job_id=j.id)'),
 'protection': ('workflows.RecoveryJob','workflows_recoveryjob j JOIN workflows_recoveryplan p ON p.id=j.plan_id','p.case_id','j.operation_key','EXISTS(SELECT 1 FROM workflows_recoveryartifact r WHERE r.job_id=j.id)'),
 'readiness': ('workflows.IntegrationProbe','workflows_integrationprobe j JOIN workflows_integrationcontract p ON p.id=j.contract_id','p.case_id','j.operation_key','EXISTS(SELECT 1 FROM workflows_integrationobservation r WHERE r.job_id=j.id)'),
 'application': ('workflows.ApplicationRecoveryJob','workflows_applicationrecoveryjob j JOIN workflows_applicationrecoveryplan p ON p.id=j.plan_id','p.case_id','j.operation_key','j.receipt IS NOT NULL'),
 'cold': ('workflows.ColdRecoveryJob','workflows_coldrecoveryjob j JOIN workflows_coldrecoveryplan p ON p.id=j.plan_id','p.case_id','j.operation_key','j.receipt IS NOT NULL'),
 'reconstitution': ('workflows.ReconstitutionJob','workflows_reconstitutionjob j JOIN workflows_reconstitutionplan p ON p.id=j.plan_id','p.case_id','j.operation_key','j.receipt IS NOT NULL'),
}


def runtime(recovery, profile_ref):
    try:
        p = settings.RECONSTITUTION['profiles'][profile_ref]
        assert set(p) == {'control_case','recovery_job_id','archived_case_ids','destination_ref','revision','receipt_path','receipt_provider_ref','receipt_key_ref','artifact_root'}
        assert p['control_case'] == str(recovery.plan.case_id) and p['recovery_job_id'] == recovery.pk
        assert isinstance(p['archived_case_ids'],list) and len(p['archived_case_ids']) == len(set(p['archived_case_ids']))
        assert all(re.fullmatch('[A-Za-z0-9:_-]{1,100}',p[k]) for k in ['destination_ref','revision','receipt_provider_ref','receipt_key_ref'])
        key = settings.RECONSTITUTION['keys'][p['receipt_key_ref']]
        assert isinstance(key,bytes) and len(key) == 32
        root = n.checked_root(p['artifact_root'])
        path = Path(p['receipt_path'])
        assert path.is_absolute() and not path.is_symlink()
        parent = n.checked_root(str(path.parent))
        a,t,k,roots,cold_identity = cold.runtime(recovery.intent['payload'])
        used = [roots[0],roots[2],root,parent]
        assert len(set(used)) == 4 and not any(a in b.parents for a in used for b in used if a != b)
        identity = n.digest({'profile':p,'key_sha256':n.digest(key),'cold_identity':cold_identity,'build':n.build_identity()})
        return p,root,path,key,identity
    except (KeyError,AssertionError,TypeError,ValueError):
        raise n.NativeArchiveHold('Exact fresh control/recovery/case inventory, destination and receipt/storage profile required') from None


def inventory(recovery, profile_ref, max_records=5000):
    profile,_,_,_,identity = runtime(recovery,profile_ref)
    known = {r[0].lower() for r in ROUTES.values()}
    durable = {m._meta.label_lower for m in apps.get_models() if {'status','fence','attempts','lease_until'} <= {f.name for f in m._meta.fields}}
    if known != durable:
        raise n.NativeArchiveHold('Every durable job model must have an explicit reviewed inventory route')
    package,_,target,roots,_ = cold.read(recovery.intent['payload'])
    with n.connect(target['database']) as db:
        db.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
        db.execute("SELECT set_config('statement_timeout',%s,true)",[str(recovery.intent['rules']['max_seconds']*1000)])
        n.verify_target(db,package,recovery.intent,roots=roots)
        cases = [str(r[0]) for r in db.execute('SELECT id FROM core_case ORDER BY id')]
        if cases != sorted(profile['archived_case_ids']):
            raise n.NativeArchiveHold('Fresh deployment scope must explicitly cover every archived case')
        rows=[]
        for family,(_,source,case,operation,receipt) in ROUTES.items():
            # All identifiers/expressions above are code-owned, never configuration or model text.
            query=f"SELECT j.id,{case}::text,j.status,j.fence,j.attempts,encode(sha256(convert_to(({operation})::text,'UTF8')),'hex'),encode(sha256(convert_to(to_jsonb(j)::text,'UTF8')),'hex'),({receipt}) FROM {source} ORDER BY j.id LIMIT %s"
            for pk,case_id,status,fence,attempts,op_sha,row_sha,recorded in db.execute(query,[max_records+1]):
                row=dict(family=family,job_id=pk,case_id=case_id,status=status,fence=fence,attempts=attempts,operation_sha256=op_sha,intent_sha256=row_sha,historical_receipt_present=recorded)
                row['effect_key']=n.digest(row)
                rows.append(row)
                if len(rows)>max_records:
                    raise n.NativeArchiveHold('Complete effect inventory exceeds configured bound; no partial acceptance')
    return {'format':FORMAT,'runtime_sha256':identity,'archived_case_ids':cases,'families':sorted(ROUTES),'effects':rows,
            'recovery_receipt_sha256':n.digest(recovery.receipt),'activation_enabled':False,'archived_authority_accepted':False}


def gateway(recovery, profile_ref, effect, rules):
    profile,_,path,key,_ = runtime(recovery,profile_ref)
    try:
        if not path.is_file() or path.is_symlink() or path.stat().st_size>rules['receipt_max_bytes']:
            raise ValueError()
        raw=path.read_bytes()
        if len(raw)>rules['receipt_max_bytes']:
            raise ValueError()
        envelope=json.loads(raw)
        assert set(envelope)=={'body','signature'}
        body=envelope['body']
        assert set(body)=={'format','provider_ref','archive_sha256','revision','observed_at','expires_at','records'}
        assert body['format']=='psl.receipt-evidence.v1' and body['provider_ref']==profile['receipt_provider_ref']
        assert body['archive_sha256']==recovery.receipt['archive_sha256']
        assert isinstance(body['revision'],str) and re.fullmatch('[A-Za-z0-9:_-]{1,100}',body['revision'])
        assert hmac.compare_digest(hmac.new(key,n.encoded(body),hashlib.sha256).hexdigest(),envelope['signature'])
        observed=datetime.fromisoformat(body['observed_at']);expires=datetime.fromisoformat(body['expires_at']);now=datetime.now(timezone.utc)
        assert observed.tzinfo is not None and observed<=now<expires and now<observed+timedelta(seconds=rules['receipt_freshness_seconds'])
        assert isinstance(body['records'],list) and len(body['records'])<=5000
        identities=set();found=None
        for row in body['records']:
            assert set(row)=={'effect_key','family','operation_sha256','intent_sha256','receipt_sha256'} and row['family'] in ROUTES
            assert all(isinstance(row[k],str) and re.fullmatch('[a-f0-9]{64}',row[k]) for k in ['effect_key','operation_sha256','intent_sha256','receipt_sha256'])
            identity=(row['effect_key'],row['family'],row['operation_sha256'],row['intent_sha256'])
            assert identity not in identities;identities.add(identity)
            if identity==(effect['effect_key'],effect['family'],effect['operation_sha256'],effect['intent_sha256']):found=row
        return {'outcome':'present' if found else 'unknown','effect_key':effect['effect_key'],'provider_ref':body['provider_ref'],
                'archive_sha256':body['archive_sha256'],
                'manifest_sha256':n.digest(raw),'observed_at':body['observed_at'],'expires_at':body['expires_at'],
                'receipt_sha256':found['receipt_sha256'] if found else None,'evidence_kind':'authenticated_gateway_attestation',
                'direct_vendor_verification':False}
    except (OSError,ValueError,KeyError,TypeError,AssertionError):
        raise n.NativeArchiveHold('Current authenticated bounded gateway receipt evidence required') from None


def artifact_path(recovery, profile_ref, operation_key):
    if not re.fullmatch('[a-f0-9]{64}',operation_key):
        raise n.NativeArchiveHold('Exact reconstitution operation key required')
    _,root,_,_,_=runtime(recovery,profile_ref)
    return root/(operation_key+'.json')


def lookup(recovery, intent):
    path=artifact_path(recovery,intent['profile_ref'],intent['operation_key'])
    if not path.exists():return None
    if path.is_symlink() or not path.is_file() or path.stat().st_size>4194304:
        raise n.NativeArchiveHold('Immutable reconstitution artifact is unsafe')
    try:
        value=json.loads(path.read_bytes())
        assert set(value)=={'intent_sha256','receipt'} and value['intent_sha256']==n.digest(intent)
        receipt=value['receipt']
        assert set(receipt)=={'format','kind','runtime_sha256','payload','payload_sha256','activation_enabled','business_jobs_reenacted'}
        assert receipt['format']==FORMAT and receipt['kind']==intent['kind'] and receipt['activation_enabled'] is False and receipt['business_jobs_reenacted'] is False
        assert receipt['runtime_sha256']==intent['pin']['runtime_sha256']
        assert receipt['payload_sha256']==n.digest(receipt['payload'])
        if intent['kind']=='publish':
            assert receipt['payload']==intent['manifest']
        else:
            assert receipt['payload']['effect_key']==intent['effect']['effect_key'] and receipt['payload']['outcome'] in ['present','unknown']
        return receipt
    except (ValueError,TypeError,KeyError,AssertionError):
        raise n.NativeArchiveHold('Immutable reconstitution artifact differs from exact intent') from None


def deliver(recovery, intent):
    old=lookup(recovery,intent)
    if old:return old
    _,_,_,_,identity=runtime(recovery,intent['profile_ref'])
    if identity!=intent['pin']['runtime_sha256']:
        raise n.NativeArchiveHold('Fresh reconstitution runtime changed')
    payload=gateway(recovery,intent['profile_ref'],intent['effect'],intent['rules']) if intent['kind']=='receipt' else intent['manifest']
    receipt={'format':FORMAT,'kind':intent['kind'],'runtime_sha256':identity,'payload':payload,
             'payload_sha256':n.digest(payload),'activation_enabled':False,'business_jobs_reenacted':False}
    n.put_once(artifact_path(recovery,intent['profile_ref'],intent['operation_key']),n.encoded({'intent_sha256':n.digest(intent),'receipt':receipt}))
    return lookup(recovery,intent)

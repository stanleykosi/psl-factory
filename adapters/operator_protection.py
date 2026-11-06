"""Actual metadata file copies and isolated PostgreSQL drills. Never restores live business tables."""
import json,os,re,uuid,time
from datetime import datetime,timezone as utc_timezone
from pathlib import Path
from django.conf import settings
from django.db import connection
from django.core.exceptions import ValidationError
from django.utils import timezone
from apps.documents.contracts import digest
import psycopg

def encoded(manifest):return json.dumps(manifest,sort_keys=True,separators=(',',':'),allow_nan=False).encode('utf-8')
def storage_root():
    base=Path(settings.BASE_DIR).resolve();root=base/'.runtime'/'operator-artifacts'
    if root.is_symlink() or not root.resolve().is_relative_to(base):raise ValidationError('Reviewed local metadata storage required')
    return root
def storage_identity():return digest({'adapter':'sealed_local_metadata_v1','root':str(storage_root().resolve())})
def target_identity():
    name=settings.OPERATOR_DRILL_DATABASE
    if not name or not re.fullmatch(r'(test_)?psl_drill_[a-z0-9_]{1,40}',name) or name in [connection.settings_dict['NAME'],'psl','test_psl','postgres','template0','template1']:raise ValidationError('An explicit separate metadata drill database is required')
    return digest({'adapter':'isolated_postgres_metadata_v1','database':name,'host':connection.settings_dict['HOST'],'port':connection.settings_dict['PORT']})
def target_connect():
    target_identity();args=connection.get_connection_params();args['dbname']=settings.OPERATOR_DRILL_DATABASE;args['connect_timeout']=5
    try:return psycopg.connect(**args)
    except psycopg.Error:raise ConnectionError('Isolated metadata drill target unavailable')

def provision_target():
    """Explicit CLI/test provisioning, never called by UI dispatch. Does not create/delete databases."""
    with target_connect() as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS psl_metadata_drill_contract (version text PRIMARY KEY CHECK(version='portable_case_metadata_v1'))")
        conn.execute("INSERT INTO psl_metadata_drill_contract VALUES ('portable_case_metadata_v1') ON CONFLICT DO NOTHING")
        conn.execute("CREATE TABLE IF NOT EXISTS psl_metadata_drill_receipt (operation_key text PRIMARY KEY, sha256 text NOT NULL, manifest jsonb NOT NULL, completed_at timestamptz NOT NULL DEFAULT now())")
        conn.execute("CREATE OR REPLACE FUNCTION psl_metadata_drill_immutable() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'Append-only isolated metadata receipt'; END $$")
        if not conn.execute("SELECT 1 FROM pg_trigger WHERE tgname='psl_metadata_drill_guard'").fetchone():conn.execute('CREATE TRIGGER psl_metadata_drill_guard BEFORE UPDATE OR DELETE ON psl_metadata_drill_receipt FOR EACH ROW EXECUTE FUNCTION psl_metadata_drill_immutable()')

def file_receipt(job):
    if storage_identity()!=job.intent['storage_identity']:raise ConnectionError('Reserved metadata storage identity changed; reconcile original target')
    path=storage_root()/(job.operation_key+'.json')
    if path.is_symlink():raise ValidationError('Metadata artifact symlink rejected')
    if not path.exists():return None
    data=path.read_bytes()
    if len(data)>2000000 or data!=encoded(job.intent['manifest']):raise ValidationError('Existing sealed metadata bytes differ; do not overwrite')
    return {'kind':'backup','scope':'portable_case_metadata_v1','manifest_sha256':digest(job.intent['manifest']),'operation_key':job.operation_key,'native_file_copy':True,'full_database_backup':False,'completed_at':datetime.fromtimestamp(path.stat().st_mtime,tz=utc_timezone.utc).isoformat()}

def restore_receipt(job):
    try:
        if target_identity()!=job.intent['target_identity']:raise ConnectionError('Reserved drill target changed; reconcile original target')
    except ValidationError:raise ConnectionError('Reserved drill target is unavailable')
    try:
        with target_connect() as conn:
            if not conn.execute("SELECT 1 FROM psl_metadata_drill_contract WHERE version='portable_case_metadata_v1'").fetchone():raise ValidationError('Unrecognised isolated drill target')
            row=conn.execute('SELECT sha256,manifest,completed_at FROM psl_metadata_drill_receipt WHERE operation_key=%s',[job.operation_key]).fetchone()
    except psycopg.Error:raise ConnectionError('Isolated metadata receipt lookup unavailable')
    if not row:return None
    manifest=json.loads(row[1]) if isinstance(row[1],str) else row[1]
    if row[0]!=digest(job.intent['manifest']) or manifest!=job.intent['manifest']:raise ValidationError('Prior isolated receipt differs; investigate without another restore')
    return {'kind':'restore','scope':'portable_case_metadata_v1','manifest_sha256':row[0],'operation_key':job.operation_key,'native_isolated_postgres_write':True,'business_jobs_reenacted':False,'full_database_restore':False,'completed_at':row[2].isoformat()}

class NativeMetadataProtectionAdapter:
    def lookup(self,job):
        from apps.workflows.operator_models import RecoveryArtifact
        old=RecoveryArtifact.objects.filter(job=job).first()
        if old:
            if old.sha256!=digest(job.intent['manifest']) or old.manifest!=job.intent['manifest']:raise ValidationError('Artifact receipt differs from reserved intent')
            return old.receipt
        if job.kind=='export':return None
        return file_receipt(job) if job.kind=='backup' else restore_receipt(job)
    def deliver(self,job):
        start=time.monotonic()
        if job.kind=='export':receipt={'kind':'export','scope':'portable_case_metadata_v1','native_local_metadata_read':True,'full_database_export':False,'manifest_sha256':digest(job.intent['manifest'])}
        elif job.kind=='backup':
            if storage_identity()!=job.intent['storage_identity']:raise ConnectionError('Reserved storage changed')
            root=storage_root();root.mkdir(parents=True,exist_ok=True);path=root/(job.operation_key+'.json');temporary=root/(uuid.uuid4().hex+'.partial')
            if not file_receipt(job):
                try:
                    with temporary.open('xb') as stream:stream.write(encoded(job.intent['manifest']));stream.flush();os.fsync(stream.fileno())
                    try:os.link(temporary,path)
                    except FileExistsError:pass
                finally:
                    if temporary.exists():temporary.unlink()
            receipt=file_receipt(job)
        else:
            if not restore_receipt(job):
                try:
                    with target_connect() as conn:
                        conn.execute('INSERT INTO psl_metadata_drill_receipt(operation_key,sha256,manifest) VALUES (%s,%s,%s::jsonb) ON CONFLICT DO NOTHING',[job.operation_key,digest(job.intent['manifest']),encoded(job.intent['manifest']).decode('utf-8')])
                except psycopg.Error:raise ConnectionError('Isolated metadata restore outcome needs receipt lookup')
            receipt=restore_receipt(job)
        return dict(receipt,elapsed_ms=int((time.monotonic()-start)*1000),completed_at=receipt.get('completed_at',timezone.now().isoformat()))

class TimeoutAfterMetadataAccept(NativeMetadataProtectionAdapter):
    def deliver(self,job):super().deliver(job);raise TimeoutError('Synthetic lost response after native metadata acceptance')

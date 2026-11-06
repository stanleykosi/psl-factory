"""Bounded native PostgreSQL/managed-attachment recovery; no arbitrary SQL/path tools."""
import base64
import hashlib
import json
import os
import re
import subprocess
import struct
import tempfile
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import psycopg
from psycopg import sql
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import connection

class NativeArchiveHold(ValidationError):
    """Only code-owned redacted diagnostics; never native stderr or source bodies."""

FORMAT = 'psl.postgres-attachments.aesgcm.v1'
MAGIC = b'PSLA1\n'
OMITTED = {'django_session', 'identity_grant'}


def build_identity():
    from config.build_identity import identity
    return identity(settings.BASE_DIR)


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(value if isinstance(value, bytes) else encoded(value)).hexdigest()


def checked_root(value):
    p = Path(value)
    if not p.is_absolute() or not p.is_dir() or p.is_symlink() or any(q.is_symlink() for q in p.parents):
        raise NativeArchiveHold('Provision an absolute nonsymlink recovery directory')
    return p.resolve()


def runtime(value):
    r = settings.APPLICATION_RECOVERY
    try:
        source = r['sources'][value['source_ref']]
        target = r['targets'][value['target_ref']]
        key = r['keys'][value['key_ref']]
        assert source['database'] == connection.settings_dict['NAME']
        assert re.fullmatch(r'(test_)?psl_recovery_[a-z0-9_]{1,40}', target['database'])
        assert target['database'] != source['database']
        assert target['database'] != settings.OPERATOR_DRILL_DATABASE
        assert isinstance(key, bytes) and len(key) == 32
        assert isinstance(r['build_ref'], str) and r['build_ref']
        binary = checked_root(r['pg_bin'])
        for command in ['pg_dump', 'pg_restore', 'psql']:
            assert (binary / (command + ('.exe' if os.name == 'nt' else ''))).is_file()
        roots = [checked_root(source['archives']), checked_root(source['attachments']), checked_root(target['attachments'])]
        assert len(set(roots)) == 3
        assert not any(a in b.parents for a in roots for b in roots if a != b)
        identity = {'source': source['database'], 'source_revision': source['revision'],
                    'target': target['database'], 'target_revision': target['revision'],
                    'roots': [str(p) for p in roots], 'key_ref': value['key_ref'],
                    'key_fingerprint': digest(key), 'build_ref': r['build_ref'], 'pg_bin': str(binary),
                    'server': {k: connection.settings_dict[k] for k in ['HOST', 'PORT', 'USER']},
                    'build_sha256': build_identity()}
        return source, target, key, roots, digest(identity)
    except (KeyError, AssertionError, TypeError, ValueError):
        raise NativeArchiveHold('Exact source/empty isolated target, key, build and runtime identities must be provisioned') from None


def connect(database=None):
    args = connection.get_connection_params().copy()
    args['connect_timeout'] = 10
    args['options'] = args.get('options', '') + ' -c timezone=UTC -c statement_timeout=300000'
    if database:
        args['dbname'] = database
    db = psycopg.connect(**args)
    # Django deliberately installs a string JSON loader on its adapter context.
    # Native archives require decoded objects without changing ORM/global loaders.
    psycopg.types.json.set_json_loads(json.loads, db)
    return db


def cli(command, arguments, database, timeout, max_output=134217728, *, pg_bin=None):
    r = settings.APPLICATION_RECOVERY
    p = connection.settings_dict
    env = os.environ.copy()
    # Passwords are never in argv, archive, receipts or errors.
    env.update(PGDATABASE=database, PGUSER=p['USER'], PGHOST=p['HOST'], PGPORT=str(p['PORT']), PGCLIENTENCODING='UTF8',
               PGPASSWORD=p['PASSWORD'], PGOPTIONS='-c statement_timeout=' + str(timeout * 1000))
    executable = Path(pg_bin or r['pg_bin']) / (command + ('.exe' if os.name == 'nt' else ''))
    with subprocess.Popen([str(executable), *arguments], env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE) as process:
        def bounded_read(stream, limit):
            chunks, size = [], 0
            while True:
                block = stream.read(65536)
                if not block:
                    return b''.join(chunks)
                size += len(block)
                if size > limit:
                    process.kill()
                    raise NativeArchiveHold('Native archive output exceeded its configured size budget')
                chunks.append(block)
        with ThreadPoolExecutor(max_workers=2) as executor:
            output = executor.submit(bounded_read, process.stdout, max_output)
            diagnostic = executor.submit(bounded_read, process.stderr, 65536)
            try:
                status = process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
                raise NativeArchiveHold('Native archive command timed out; reconcile before retry') from None
            data = output.result()
            stderr = diagnostic.result()
    if status:
        # Native stderr can contain sensitive row values/paths. Do not persist it.
        state = re.search(rb'ERROR:\s*([0-9A-Z]{5})(?:\s|$)', stderr)
        code = ' SQLSTATE ' + state.group(1).decode('ascii') if state else ''
        raise NativeArchiveHold('Native ' + command + ' failed' + code + '; target remains quarantined')
    return data


def tables(db):
    return [r[0] for r in db.execute("SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename")]


def inventory(db, sanitized=False):
    result = {}
    for name in tables(db):
        if sanitized and name in OMITTED:
            result[name] = [0, hashlib.sha256(b'').hexdigest()]
            continue
        expr = sql.SQL('to_jsonb(t)')
        if sanitized and name == 'auth_user':
            expr = sql.SQL("to_jsonb(t)||jsonb_build_object('password','!','is_active',false,'is_staff',false,'is_superuser',false,'last_login',NULL)")
        row = db.execute(sql.SQL("SELECT count(*),encode(sha256(convert_to(coalesce(string_agg(h,'' ORDER BY h),''),'UTF8')),'hex') FROM (SELECT encode(sha256(convert_to(({})::text,'UTF8')),'hex') h FROM public.{} t) q").format(expr, sql.Identifier(name))).fetchone()
        result[name] = list(row)
    return result


def canonical_definition(value):
    # pg_dump/reparse distributes varchar[] -> text[] casts over literal arrays.
    # Normalize only unbounded varchar casts on simple code-owned status literals.
    # Never strip predicates, lengths, collations, functions or arbitrary casts.
    literal = r"'[a-z_][a-z0-9_]*'::character varying"
    pattern = r'\(ARRAY\[(' + literal + r'(?:, ' + literal + r')*)\]\)::text\[\]'
    return re.sub(pattern, lambda m: 'ARRAY[' + ', '.join('(' + x + ')::text' for x in m.group(1).split(', ')) + ']', value) if isinstance(value, str) else value


def sequence_inventory(db):
    result = {}
    for row in db.execute("SELECT sequencename,start_value,min_value,max_value,increment_by,cycle,cache_size,last_value FROM pg_sequences WHERE schemaname='public' ORDER BY sequencename"):
        if row[4] <= 0 or row[5]:
            raise NativeArchiveHold('This native recovery version requires positive noncycling application sequences')
        result[row[0]] = list(row[1:])
    return result


def schema_inventory(db):
    # PostgreSQL definitions, not merely table counts. No owners or credentials.
    queries = [
        "SELECT table_name,column_name,data_type,is_nullable,column_default,udt_name,character_maximum_length,numeric_precision,numeric_scale,datetime_precision,collation_name,is_identity,identity_generation,is_generated,generation_expression FROM information_schema.columns WHERE table_schema='public' ORDER BY 1,ordinal_position",
        "SELECT c.relname,k.conname,pg_get_constraintdef(k.oid) FROM pg_constraint k JOIN pg_class c ON c.oid=k.conrelid JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' ORDER BY 1,2",
        "SELECT tablename,indexname,indexdef FROM pg_indexes WHERE schemaname='public' ORDER BY 1,2",
        "SELECT p.proname,pg_get_function_identity_arguments(p.oid),pg_get_functiondef(p.oid) FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname='public' AND p.prokind='f' ORDER BY 1,2",
        "SELECT c.relname,t.tgname,pg_get_triggerdef(t.oid) FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' AND NOT t.tgisinternal ORDER BY 1,2",
    ]
    return digest([[[canonical_definition(v) if ix in [1, 2] and j == len(row)-1 else v for j, v in enumerate(row)] for row in db.execute(q)] for ix, q in enumerate(queries)])


def put_once(path, data):
    if path.exists():
        if path.is_symlink() or path.read_bytes() != data:
            raise NativeArchiveHold('Existing sealed recovery bytes conflict; no overwrite permitted')
        return
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as f:
        temporary = Path(f.name)
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    try:
        try:
            os.link(temporary, path)
        except FileExistsError:
            if path.is_symlink() or path.read_bytes() != data:
                raise NativeArchiveHold('Concurrent sealed recovery bytes conflict')
    finally:
        temporary.unlink()


def blob(root, sha, size):
    if not re.fullmatch('[0-9a-f]{64}', sha) or type(size) is not int or size < 0:
        raise NativeArchiveHold('Invalid managed attachment identity')
    path = root / sha
    if path.is_symlink() or not path.is_file() or path.stat().st_size != size:
        raise NativeArchiveHold('Managed attachment is missing or changed')
    data = path.read_bytes()
    if digest(data) != sha:
        raise NativeArchiveHold('Managed attachment content does not match its immutable inventory')
    return data


def source_archive(intent):
    v = intent['rules']
    source, target, key, roots, identity = runtime(v)
    if identity != intent['runtime_sha256']:
        raise NativeArchiveHold('Runtime identity changed; create a reviewed successor intent')
    with connect() as db:
        db.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
        db.execute("SELECT set_config('statement_timeout',%s,true)", [str(v['max_seconds'] * 1000)])
        snapshot = db.execute('SELECT pg_export_snapshot()').fetchone()[0]
        from django.db.migrations.loader import MigrationLoader
        migrations = [list(x) for x in db.execute('SELECT app,name FROM django_migrations ORDER BY app,name')]
        if {tuple(x) for x in migrations} != set(MigrationLoader(None).disk_migrations):
            raise NativeArchiveHold('Source migration inventory is not compatible with this exact application build')
        cases = [str(row[0]) for row in db.execute('SELECT id FROM core_case ORDER BY id')]
        if cases != intent['case_ids']:
            raise NativeArchiveHold('Snapshot includes a different source-case authority inventory')
        if v['allow_synthetic'] and db.execute('SELECT 1 FROM core_case WHERE NOT synthetic LIMIT 1').fetchone():
            raise NativeArchiveHold('Synthetic recovery cannot include operational source cases')
        attachments = db.execute('SELECT id,sha256,size FROM workflows_recoveryattachment ORDER BY id').fetchall()
        if [a[0] for a in attachments] != sorted(v['attachment_ids']):
            raise NativeArchiveHold('Configured attachment inventory must cover every managed attachment exactly')
        files = []
        total = 0
        for pk, sha, size in attachments:
            total += size
            if total > v['max_attachment_bytes']:
                raise NativeArchiveHold('Configured attachment size budget exceeded')
            files.append({'id': pk, 'sha256': sha, 'size': size, 'data': base64.b64encode(blob(roots[1], sha, size)).decode()})
        sanitized_users = [row[0] for row in db.execute("SELECT to_jsonb(t)||jsonb_build_object('password','!','is_active',false,'is_staff',false,'is_superuser',false,'last_login',NULL) FROM auth_user t ORDER BY id")]
        captured = datetime.now(timezone.utc)
        manifest = {'format': FORMAT, 'build_ref': settings.APPLICATION_RECOVERY['build_ref'], 'build_sha256': build_identity(),
                    'captured_at': captured.isoformat(), 'retain_until': (captured + timedelta(days=v['retention_days'])).isoformat(),
                    'postgres_version': db.info.server_version, 'schema_sha256': schema_inventory(db),
                    'database_locale': list(db.execute('SELECT pg_encoding_to_char(encoding),datcollate,datctype FROM pg_database WHERE datname=current_database()').fetchone()),
                    'sequence_minima': sequence_inventory(db),
                    'tables': inventory(db, sanitized=True), 'attachments': [{k: f[k] for k in ['id', 'sha256', 'size']} for f in files],
                    'credential_transform': 'inactive_unusable_users_no_sessions_no_grants_v1',
                    'source_identity': identity, 'intent_sha256': digest(intent),
                    'migration_sha256': digest(migrations),
                    'external_repositories_included': False, 'live_authority_restored': False}
        args = ['--format=custom', '--schema=public', '--no-owner', '--no-acl', '--snapshot=' + snapshot]
        for table in sorted(OMITTED | {'auth_user'}):
            args.append('--exclude-table-data=public.' + table)
        dump = cli('pg_dump', args, source['database'], v['max_seconds'], max_output=v['max_archive_bytes'])
        package = encoded({'manifest': manifest, 'dump': base64.b64encode(dump).decode(), 'users': sanitized_users, 'files': files})
        if len(package) > v['max_archive_bytes']:
            raise NativeArchiveHold('Configured archive byte budget exceeded')
        return package


def archive_path(intent, roots):
    return roots[0] / (intent['operation_key'] + '.psla')


def seal(intent, package, key):
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    header = encoded({'format': FORMAT, 'operation_key': intent['operation_key'], 'key_ref': intent['rules']['key_ref']})
    nonce = os.urandom(12)
    body = encoded({'intent': intent, 'package': package})
    return MAGIC + struct.pack('>I', len(header)) + header + nonce + AESGCM(key).encrypt(nonce, body, header)


def unseal(data, keys):
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.exceptions import InvalidTag
    try:
        if not data.startswith(MAGIC) or len(data) < len(MAGIC) + 4:
            raise ValueError()
        length = struct.unpack('>I', data[len(MAGIC):len(MAGIC)+4])[0]
        if not 0 < length <= 1024:
            raise ValueError()
        offset = len(MAGIC) + 4
        header = data[offset:offset+length]
        fields = json.loads(header)
        if set(fields) != {'format', 'operation_key', 'key_ref'} or fields['format'] != FORMAT or not re.fullmatch('[0-9a-f]{64}', fields['operation_key']):
            raise ValueError()
        offset += length
        body = json.loads(AESGCM(keys[fields['key_ref']]).decrypt(data[offset:offset+12], data[offset+12:], header))
        if set(body) != {'intent', 'package'} or body['intent']['operation_key'] != fields['operation_key'] or body['intent']['rules']['key_ref'] != fields['key_ref']:
            raise ValueError()
        return body['intent'], body['package']
    except (InvalidTag, ValueError, KeyError, TypeError, struct.error):
        raise NativeArchiveHold('Archive authentication, self-description or exact intent binding failed') from None


def inspect_offline(source_ref, operation_key):
    """Read-only host/operator diagnostic. Never uses archived authority or opens a DB."""
    if not re.fullmatch('[0-9a-f]{64}', operation_key):
        raise NativeArchiveHold('Exact native operation key required')
    r = settings.APPLICATION_RECOVERY
    try:
        root = checked_root(r['sources'][source_ref]['archives'])
        path = root / (operation_key + '.psla')
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 134217728:
            raise NativeArchiveHold('Sealed native archive missing, unsafe or oversized')
        data = path.read_bytes()
        intent, package = unseal(data, r['keys'])
        if intent['operation_key'] != operation_key or intent['rules']['source_ref'] != source_ref or package['manifest']['intent_sha256'] != digest(intent):
            raise NativeArchiveHold('Offline native source and intent provenance differs')
        m = package['manifest']
        return {'format': FORMAT, 'operation_key': operation_key, 'archive_sha256': digest(data),
                'intent_sha256': digest(intent), 'manifest_sha256': digest(m), 'table_count': len(m['tables']),
                'managed_attachment_count': len(m['attachments']), 'compatible_build': m['build_sha256'] == build_identity(),
                'source_database_needed': False, 'restoration_authorized': False, 'live_authority_restored': False}
    except KeyError:
        raise NativeArchiveHold('Offline source/key registry or native manifest is incomplete') from None


def read_archive(intent):
    _, _, key, roots, identity = runtime(intent['rules'])
    if identity != intent['runtime_sha256']:
        raise NativeArchiveHold('Runtime identity changed')
    path = archive_path(intent, roots)
    if path.is_symlink() or not path.is_file() or path.stat().st_size > intent['rules']['max_archive_bytes']:
        raise NativeArchiveHold('Sealed native archive missing, unsafe or oversized')
    data = path.read_bytes()
    stored_intent, package = unseal(data, {intent['rules']['key_ref']: key})
    if stored_intent != intent:
        raise NativeArchiveHold('Sealed archive belongs to another exact immutable intent')
    validate_package(intent, package, identity)
    return package, digest(data)


def validate_package(intent, package, identity):
    """Validate inert archive content; historical intent is provenance, never authority."""
    if not isinstance(package, dict) or set(package) != {'manifest', 'dump', 'users', 'files'}:
        raise NativeArchiveHold('Native archive has an invalid closed package')
    m = package['manifest']
    fields = {'format', 'build_ref', 'build_sha256', 'captured_at', 'retain_until', 'postgres_version', 'database_locale', 'sequence_minima', 'schema_sha256', 'tables', 'attachments', 'credential_transform', 'source_identity', 'intent_sha256', 'migration_sha256', 'external_repositories_included', 'live_authority_restored'}
    if not isinstance(m, dict) or set(m) != fields or m['format'] != FORMAT or m['intent_sha256'] != digest(intent) or m['source_identity'] != identity or m['live_authority_restored'] is not False or m['external_repositories_included'] is not False or m['credential_transform'] != 'inactive_unusable_users_no_sessions_no_grants_v1':
        raise NativeArchiveHold('Native archive has incompatible type, authority or provenance')
    if not base64.b64decode(package['dump'], validate=True).startswith(b'PGDMP'):
        raise NativeArchiveHold('A real native PostgreSQL custom archive is required')
    if not isinstance(package['users'], list) or any(not isinstance(u, dict) or u.get('password') != '!' or any(u.get(k) is not False for k in ['is_active', 'is_staff', 'is_superuser']) for u in package['users']):
        raise NativeArchiveHold('Native archive principals must be decoded inert records')
    if not isinstance(package['files'], list) or any(not isinstance(f, dict) or set(f) != {'id', 'sha256', 'size', 'data'} for f in package['files']):
        raise NativeArchiveHold('Native archive attachments require a closed typed inventory')
    expected = m['attachments']
    actual = [{k: f[k] for k in ['id', 'sha256', 'size']} for f in package['files']]
    if actual != expected or sorted(f['id'] for f in actual) != sorted(intent['rules']['attachment_ids']):
        raise NativeArchiveHold('Native archive attachment inventory is incomplete')


def archive(intent):
    _, _, key, roots, _ = runtime(intent['rules'])
    path = archive_path(intent, roots)
    if not path.exists():
        package = source_archive(intent)
        sealed = seal(intent, json.loads(package), key)
        if len(sealed) > intent['rules']['max_archive_bytes']:
            raise NativeArchiveHold('Configured complete sealed archive size budget exceeded')
        put_once(path, sealed)
    return archive_receipt(intent)


def archive_receipt(intent):
    package, sha = read_archive(intent)
    return {'format': FORMAT, 'archive_sha256': sha, 'manifest_sha256': digest(package['manifest']),
            'managed_attachment_count': len(package['files']), 'table_count': len(package['manifest']['tables']),
            'live_authority_restored': False, 'operational_acceptance': False}


def verify_target(db, package, intent, *, roots=None):
    m = package['manifest']
    extra = db.execute("SELECT nspname FROM pg_namespace WHERE nspname !~ '^pg_' AND nspname NOT IN ('public','information_schema','psl_recovery_control')").fetchall()
    control_functions = db.execute("SELECT count(*) FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname='psl_recovery_control'").fetchone()[0]
    if extra or control_functions:
        raise NativeArchiveHold('Recovered target has unexpected schemas or control functions')
    rows = inventory(db)
    if rows != m['tables']:
        different = sorted(k for k in rows.keys() | m['tables'].keys() if rows.get(k) != m['tables'].get(k))
        raise NativeArchiveHold('Recovered row inventory differs: ' + ','.join(different[:3]))
    if schema_inventory(db) != m['schema_sha256']:
        raise NativeArchiveHold('Recovered schema/constraints/functions inventory differs')
    sequences = sequence_inventory(db)
    if set(sequences) != set(m['sequence_minima']):
        raise NativeArchiveHold('Recovered sequence inventory differs')
    for name, expected in m['sequence_minima'].items():
        actual = sequences[name]
        if actual[:-1] != expected[:-1] or (expected[-1] is not None and (actual[-1] is None or actual[-1] < expected[-1])):
            raise NativeArchiveHold('Recovered sequence structure or safe monotonic lower bound differs')
    if db.execute("SELECT count(*) FROM auth_user WHERE is_active OR is_staff OR is_superuser OR password<>'!'").fetchone()[0]:
        raise NativeArchiveHold('Recovered authentication is not disabled')
    if any(db.execute(sql.SQL('SELECT count(*) FROM {}').format(sql.Identifier(t))).fetchone()[0] for t in OMITTED):
        raise NativeArchiveHold('Recovered sessions or grants are present')
    migrations = [list(x) for x in db.execute('SELECT app,name FROM django_migrations ORDER BY app,name')]
    if digest(migrations) != m['migration_sha256']:
        raise NativeArchiveHold('Recovered migration identity differs')
    if roots is None:
        _, _, _, roots, _ = runtime(intent['rules'])
    marker = roots[2] / '.psl-recovery-intent'
    expected = encoded({'intent_sha256': digest(intent), 'manifest_sha256': digest(m)})
    if marker.is_symlink() or not marker.is_file() or marker.read_bytes() != expected:
        raise NativeArchiveHold('Recovered attachment directory is not bound to this exact intent')
    names = {p.name for p in roots[2].iterdir()}
    if names != {'.psl-recovery-intent'} | {f['sha256'] for f in package['files']}:
        raise NativeArchiveHold('Recovered attachment directory has an incomplete or unexpected inventory')
    for f in package['files']:
        blob(roots[2], f['sha256'], f['size'])


def restored_receipt(intent, archive_intent):
    package, archive_sha = read_archive(archive_intent)
    _, target, _, _, identity = runtime(intent['rules'])
    if identity != intent['runtime_sha256']:
        raise NativeArchiveHold('Runtime identity changed')
    _, _, _, roots, _ = runtime(intent['rules'])
    return package_receipt(intent, package, archive_sha, target, roots, identity)


def package_receipt(intent, package, archive_sha, target, roots, identity):
    """Target-only physical reconciliation, usable from a separate authority database."""
    with connect(target['database']) as db:
        db.execute("SELECT set_config('statement_timeout',%s,true)", [str(intent['rules']['max_seconds'] * 1000)])
        exists = db.execute("SELECT to_regclass('psl_recovery_control.receipt')").fetchone()[0]
        if not exists:
            return None
        rows = db.execute('SELECT intent_sha256,archive_sha256 FROM psl_recovery_control.receipt').fetchall()
        if rows != [(digest(intent), archive_sha)]:
            raise NativeArchiveHold('Isolated target belongs to another or incomplete recovery; no reset permitted')
        verify_target(db, package, intent, roots=roots)
    return {'format': FORMAT, 'archive_sha256': archive_sha, 'manifest_sha256': digest(package['manifest']),
            'runtime_sha256': identity, 'schema_and_rows_verified': True, 'attachment_bytes_verified': True,
            'authentication_disabled': True, 'outbound_disabled': True, 'live_authority_restored': False,
            'operational_acceptance': False}


def restore(intent, archive_intent):
    old = restored_receipt(intent, archive_intent)
    if old:
        return old
    package, archive_sha = read_archive(archive_intent)
    source, target, _, roots, _ = runtime(intent['rules'])
    return restore_package(intent, package, archive_sha, target, roots, intent['runtime_sha256'],
                           settings.APPLICATION_RECOVERY['build_ref'], None)


def restore_package(intent, package, archive_sha, target, roots, identity, build_ref, pg_bin):
    def command(*args):
        return cli(*args, pg_bin=pg_bin) if pg_bin else cli(*args)
    old = package_receipt(intent, package, archive_sha, target, roots, identity)
    if old:
        return old
    if package['manifest']['build_ref'] != build_ref or package['manifest']['build_sha256'] != build_identity():
        raise NativeArchiveHold('Archive/application build compatibility differs')
    captured = datetime.fromisoformat(package['manifest']['captured_at'])
    if captured > datetime.now(timezone.utc) or datetime.now(timezone.utc) >= captured + timedelta(seconds=intent['rules']['archive_valid_seconds']):
        raise NativeArchiveHold('Archive is future-dated or no longer within configured recovery validity')
    with connect(target['database']) as db:
        db.execute("SELECT set_config('statement_timeout',%s,true)", [str(intent['rules']['max_seconds'] * 1000)])
        if db.execute("SELECT nspname FROM pg_namespace WHERE nspname !~ '^pg_' AND nspname NOT IN ('public','information_schema')").fetchall() or tables(db):
            raise NativeArchiveHold('Only separately provisioned empty isolated targets are supported; no drop/reset')
        if db.info.server_version // 10000 != package['manifest']['postgres_version'] // 10000:
            raise NativeArchiveHold('PostgreSQL major-version compatibility differs')
        locale = list(db.execute('SELECT pg_encoding_to_char(encoding),datcollate,datctype FROM pg_database WHERE datname=current_database()').fetchone())
        if locale != package['manifest']['database_locale']:
            raise NativeArchiveHold('Source/target database encoding or locale differs')
    marker = roots[2] / '.psl-recovery-intent'
    marker_body = encoded({'intent_sha256': digest(intent), 'manifest_sha256': digest(package['manifest'])})
    names = {p.name for p in roots[2].iterdir()}
    expected_names = {'.psl-recovery-intent'} | {f['sha256'] for f in package['files']}
    if names and (not marker.is_file() or marker.is_symlink() or marker.read_bytes() != marker_body or not names <= expected_names):
        raise NativeArchiveHold('Only empty or same-intent attachment targets are supported')
    put_once(marker, marker_body)
    # Quarantine precedes any schema/data restore, including every failure path.
    with connect(target['database']) as db:
        db.execute(sql.SQL("ALTER DATABASE {} SET psl.recovery_quarantined = 'on'").format(sql.Identifier(target['database'])))
    for f in package['files']:
        raw = base64.b64decode(f['data'], validate=True)
        if len(raw) != f['size'] or digest(raw) != f['sha256']:
            raise NativeArchiveHold('Attachment archive content mismatch')
        put_once(roots[2] / f['sha256'], raw)
    # All PostgreSQL changes, including post-data constraints, commit atomically.
    with tempfile.TemporaryDirectory(dir=roots[0]) as directory:
        p = Path(directory)
        (p / 'input.dump').write_bytes(base64.b64decode(package['dump'], validate=True))
        toc = command('pg_restore', ['--list', str(p / 'input.dump')], target['database'], intent['rules']['max_seconds']).decode('utf-8')
        lines = []
        for line in toc.splitlines():
            parts = line.split(';', 1)[1].strip().split() if ';' in line and not line.startswith(';') else []
            # Empty provisioned databases already have public; retain every application object.
            if len(parts) >= 5 and parts[2:5] == ['SCHEMA', '-', 'public']:
                line = ';' + line
            lines.append(line)
        (p / 'restore.list').write_text('\n'.join(lines) + '\n', encoding='utf-8')
        for section in ['pre-data', 'data', 'post-data']:
            command('pg_restore', ['--no-owner', '--no-acl', '--use-list=' + str(p / 'restore.list'), '--section=' + section, '--file=' + str(p / (section + '.sql')), str(p / 'input.dump')], target['database'], intent['rules']['max_seconds'])
        user_sql = []
        for u in package['users']:
            if u['password'] != '!' or u['is_active'] or u['is_staff'] or u['is_superuser']:
                raise NativeArchiveHold('Archive principal is not inert')
            user_sql.append(sql.SQL('INSERT INTO public.auth_user SELECT * FROM jsonb_populate_record(NULL::public.auth_user,{}::jsonb);').format(sql.Literal(json.dumps(u))).as_string())
        (p / 'users.sql').write_text('\n'.join(user_sql), encoding='utf-8')
        receipt_sql = sql.SQL('CREATE SCHEMA psl_recovery_control; CREATE TABLE psl_recovery_control.receipt(intent_sha256 text PRIMARY KEY, archive_sha256 text NOT NULL); INSERT INTO psl_recovery_control.receipt VALUES ({},{});').format(sql.Literal(digest(intent)), sql.Literal(archive_sha)).as_string()
        (p / 'receipt.sql').write_text(receipt_sql, encoding='utf-8')
        args = ['--no-psqlrc', '--set=ON_ERROR_STOP=1', '--set=VERBOSITY=sqlstate', '--single-transaction']
        for file in ['pre-data.sql', 'users.sql', 'data.sql', 'post-data.sql', 'receipt.sql']:
            args += ['--file=' + str(p / file)]
        command('psql', args, target['database'], intent['rules']['max_seconds'])
    return package_receipt(intent, package, archive_sha, target, roots, identity)

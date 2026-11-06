"""Sealed source-independent inputs and target-only effects. No source connections."""
import re
from django.conf import settings
from django.db import connection
from . import native_application_archive as n


def runtime(payload):
    r = settings.COLD_RECOVERY
    try:
        archive = r['archives'][payload['archive_ref']]
        target = r['targets'][payload['target_ref']]
        key = r['keys'][payload['key_ref']]
        assert re.fullmatch(r'(?:test_)?psl_cold_[a-z0-9_]{1,40}', connection.settings_dict['NAME'])
        assert r['control_database'] == connection.settings_dict['NAME']
        assert len({archive['database'], target['database'], r['control_database']}) == 3
        assert re.fullmatch(r'(?:test_)?psl_recovery_[a-z0-9_]{1,40}', target['database'])
        assert target['database'] != settings.OPERATOR_DRILL_DATABASE
        assert re.fullmatch('[a-f0-9]{64}', archive['operation_key'])
        assert re.fullmatch('[a-f0-9]{64}', archive['sha256'])
        assert isinstance(key, bytes) and len(key) == 32
        assert isinstance(r['control_secret'], bytes) and len(r['control_secret']) == 32
        roots = [n.checked_root(archive['archives']), None, n.checked_root(target['attachments'])]
        assert roots[0] != roots[2] and roots[0] not in roots[2].parents and roots[2] not in roots[0].parents
        binary = n.checked_root(r['pg_bin'])
        import os
        for name in ['pg_restore', 'psql']:
            assert (binary / (name + ('.exe' if os.name == 'nt' else ''))).is_file()
        identity = n.digest({'control_ref': r['control_ref'], 'control_secret_sha256': n.digest(r['control_secret']),
            'control_database': r['control_database'], 'archive': archive, 'target': target,
            'key_ref': payload['key_ref'], 'key_sha256': n.digest(key), 'build_ref': r['build_ref'],
            'build_sha256': n.build_identity(), 'pg_bin': str(binary),
            'server': {k: connection.settings_dict[k] for k in ['HOST', 'PORT', 'USER']}})
        return archive, target, key, roots, identity
    except (KeyError, AssertionError, TypeError, ValueError):
        raise n.NativeArchiveHold('Independent control/archive/target/key/build deployment bindings required') from None


def read(payload, max_bytes=134217728):
    a, target, key, roots, identity = runtime(payload)
    p = roots[0] / (a['operation_key'] + '.psla')
    if p.is_symlink() or not p.is_file() or p.stat().st_size > max_bytes:
        raise n.NativeArchiveHold('Registered sealed archive missing, unsafe or oversized')
    raw = p.read_bytes()
    if len(raw) > max_bytes or n.digest(raw) != a['sha256']:
        raise n.NativeArchiveHold('Registered exact sealed archive fingerprint differs')
    old, package = n.unseal(raw, {payload['key_ref']: key})
    if old['operation_key'] != a['operation_key'] or old.get('kind') != 'archive':
        raise n.NativeArchiveHold('Registered historical archive operation differs')
    n.validate_package(old, package, old['runtime_sha256'])
    if package['manifest']['build_ref'] != settings.COLD_RECOVERY['build_ref'] or package['manifest']['build_sha256'] != n.build_identity():
        raise n.NativeArchiveHold('Exact independently registered application build compatibility required')
    return package, a['sha256'], target, roots, identity


def metadata(payload):
    p, sha, _, _, identity = read(payload)
    return {'archive_sha256': sha, 'manifest_sha256': n.digest(p['manifest']), 'runtime_sha256': identity,
            'table_count': len(p['manifest']['tables']), 'attachment_count': len(p['files']),
            'source_database_needed': False, 'restoration_authorized': False}


def receipt(intent):
    p, sha, target, roots, identity = read(intent['payload'], intent['rules']['max_archive_bytes'])
    if identity != intent['runtime_sha256']:
        raise n.NativeArchiveHold('Independent recovery runtime identity changed')
    return n.package_receipt(intent, p, sha, target, roots, identity)


def restore(intent):
    p, sha, target, roots, identity = read(intent['payload'], intent['rules']['max_archive_bytes'])
    if identity != intent['runtime_sha256']:
        raise n.NativeArchiveHold('Independent recovery runtime identity changed')
    r = settings.COLD_RECOVERY
    return n.restore_package(intent, p, sha, target, roots, identity, r['build_ref'], r['pg_bin'])

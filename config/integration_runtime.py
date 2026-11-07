"""Deployment-owned references. Offline validation never resolves credentials."""
import argparse
import json
import os
import re
import stat
from pathlib import Path
from urllib.parse import urlsplit
from uuid import UUID

MAX_BYTES = 1048576
INVALID = 'Invalid integration registry references; credentials belong in the secret environment'
FILE_INVALID = 'Bounded absolute non-symlink regular integration registry file required'
KEY = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.:-]{0,99}\Z')
ENV = re.compile(r'[A-Za-z_][A-Za-z0-9_]{0,127}\Z')


def require(condition):
    if not condition:
        raise ValueError('Invalid reference')


def text(value, pattern=KEY):
    return isinstance(value, str) and pattern.fullmatch(value) is not None


def shape(value, keys):
    require(isinstance(value, dict) and set(value) == set(keys))


def validate_sender(value, secrets):
    shape(value, ('credential_ref', 'credential_revision', 'destination_ref', 'case_ids', 'classification'))
    require(value['classification'] in ('synthetic', 'operational'))
    require(all(text(value[k]) for k in ('credential_ref', 'credential_revision', 'destination_ref')))
    credential = secrets[value['credential_ref']]
    shape(credential, ('env', 'revision'))
    require(text(credential['env'], ENV) and text(credential['revision']))
    require(credential['revision'] == value['credential_revision'])
    ids = value['case_ids']
    require(isinstance(ids, list) and len(ids) <= 1024)
    require(all(isinstance(x, str) and len(x) == 36 and str(UUID(x)) == x for x in ids))
    require(len(ids) == len(set(ids)))
    return credential


def validate_registry(value):
    try:
        require(isinstance(value, dict) and set(value) in (
            {'endpoints', 'secrets', 'finance_senders'},
            {'endpoints', 'secrets', 'finance_senders', 'quickbooks_reads'}))
        require(all(isinstance(v, dict) and len(v) <= 1024 for v in value.values()))
        for key, endpoint in value['endpoints'].items():
            require(text(key, re.compile(r'endpoint:[a-z][a-z0-9_.-]{0,79}\Z')))
            shape(endpoint, ('url', 'classification'))
            require(endpoint['classification'] in ('synthetic', 'operational'))
            url = endpoint['url']
            require(isinstance(url, str) and 0 < len(url) <= 2048)
            require(not any(c.isspace() or ord(c) < 32 or ord(c) == 127 for c in url))
            require(not any(c in url for c in ('\\', '?', '#')))
            parsed = urlsplit(url)
            require(bool(parsed.hostname) and parsed.username is None and parsed.password is None)
            require('%' not in parsed.netloc and not parsed.netloc.endswith(':'))
            require(parsed.path in ('', '/') and not parsed.query and not parsed.fragment)
            require(parsed.port is None or 1 <= parsed.port <= 65535)
            require(parsed.scheme == 'https' or (parsed.scheme == 'http' and endpoint['classification'] == 'synthetic' and parsed.hostname in ('localhost', '127.0.0.1', '::1')))
        for key, credential in value['secrets'].items():
            require(text(key, re.compile(r'secret:[a-z][a-z0-9_.-]{0,79}\Z')))
            shape(credential, ('env', 'revision'))
            require(text(credential['env'], ENV) and text(credential['revision']))
        from adapters.quickbooks_online import validate_binding
        for key, binding in value.get('quickbooks_reads', {}).items():
            require(text(key))
            validate_binding(binding, value['secrets'])
        for key, sender in value['finance_senders'].items():
            require(text(key))
            validate_sender(sender, value['secrets'])
    except (ValueError, TypeError, KeyError, AttributeError, RecursionError):
        raise RuntimeError(INVALID) from None
    return value


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result)
        result[key] = value
    return result


def _constant(value):
    raise ValueError('Nonfinite number')


def load_file(value):
    try:
        path = Path(value)
        require(path.is_absolute() and not path.is_symlink())
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(fd, 'rb') as source:
            before = os.fstat(source.fileno())
            require(stat.S_ISREG(before.st_mode) and before.st_size <= MAX_BYTES)
            raw = source.read(MAX_BYTES + 1)
            after = os.fstat(source.fileno())
            require(len(raw) <= MAX_BYTES and after.st_size == len(raw) and before.st_mtime_ns == after.st_mtime_ns)
    except (OSError, ValueError, TypeError, AttributeError):
        raise RuntimeError(FILE_INVALID) from None
    try:
        value = json.loads(raw.decode('utf-8'), object_pairs_hook=_pairs, parse_constant=_constant)
    except (ValueError, TypeError, RecursionError):
        raise RuntimeError(INVALID) from None
    return validate_registry(value)


def load():
    path = os.getenv('PSL_INTEGRATION_PROFILE')
    return load_file(path) if path else {'endpoints': {}, 'secrets': {}, 'finance_senders': {}}


def preflight(path=None):
    if path is None:
        path = os.getenv('PSL_INTEGRATION_PROFILE') or None
    value = load_file(path) if path is not None else {'endpoints': {}, 'secrets': {}, 'finance_senders': {}}
    return {'status': 'references_valid' if path is not None else 'unconfigured',
            'endpoint_aliases': sorted(value['endpoints']), 'credential_aliases': sorted(value['secrets']),
            'sender_aliases': sorted(value['finance_senders']),
            'quickbooks_read_aliases': sorted(value.get('quickbooks_reads', {})), 'network_checked': False,
            'credentials_resolved': False, 'operational_readiness': False}


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        self.exit(2, 'Invalid preflight arguments; use --help\n')


def main(argv=None):
    parser = _Parser(description='Offline registry reference validation only; no credentials or network.')
    parser.add_argument('--profile', help='Absolute registry file path (defaults to PSL_INTEGRATION_PROFILE)')
    args = parser.parse_args(argv)
    try:
        result = preflight(args.profile)
    except RuntimeError as exc:
        parser.exit(2, str(exc) + '\n')
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

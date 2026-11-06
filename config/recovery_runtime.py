"""Deployment-owned runtime registry. Configuration UI accepts references, never paths/keys."""
import base64
import json
import os
import re
from pathlib import Path


def load():
    profile = os.getenv('PSL_APPLICATION_RECOVERY_PROFILE')
    if not profile:
        return {'sources': {}, 'targets': {}, 'keys': {}, 'principals': [], 'build_ref': None, 'pg_bin': None}
    path = Path(profile)
    if not path.is_absolute() or path.is_symlink():
        raise RuntimeError('Provision an absolute deployment-owned recovery runtime profile')
    value = json.loads(path.read_text(encoding='utf-8'))
    if set(value) != {'sources', 'targets', 'key_env', 'principals', 'build_ref', 'pg_bin'}:
        raise RuntimeError('Unexpected recovery runtime registry shape')
    keys = {}
    for ref, name in value.pop('key_env').items():
        if not re.fullmatch(r'PSL_RECOVERY_KEY_[A-Z0-9_]+', name):
            raise RuntimeError('Recovery encryption key must use its dedicated secret environment reference')
        try:
            keys[ref] = base64.b64decode(os.environ[name], validate=True)
            if len(keys[ref]) != 32:
                raise ValueError()
        except (KeyError, ValueError):
            raise RuntimeError('A referenced 256-bit recovery key is not provisioned') from None
    value['keys'] = keys
    return value

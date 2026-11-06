"""Deployment-owned references and a separate receipt-evidence verification secret."""
import os, json, base64, re
from pathlib import Path


def load():
    name = os.getenv('PSL_RECONSTITUTION_PROFILE')
    if not name:
        return {'profiles': {}, 'keys': {}}
    p = Path(name)
    if not p.is_absolute() or p.is_symlink():
        raise RuntimeError('Absolute independently provisioned reconstitution profile required')
    value = json.loads(p.read_text(encoding='utf-8'))
    if set(value) != {'profiles','key_env'} or not isinstance(value['profiles'],dict):
        raise RuntimeError('Closed reconstitution registry required')
    keys = {}
    try:
        for ref, env in value.pop('key_env').items():
            if not re.fullmatch(r'PSL_RECONSTITUTION_KEY_[A-Z0-9_]+',env):
                raise ValueError()
            keys[ref] = base64.b64decode(os.environ[env],validate=True)
            if len(keys[ref]) != 32:
                raise ValueError()
    except (KeyError,ValueError,TypeError):
        raise RuntimeError('Dedicated 256-bit receipt-evidence verification key required') from None
    return {**value,'keys':keys}

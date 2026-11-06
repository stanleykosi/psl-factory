"""Separate deployment registry; no authority, paths or keys supplied by archive/UI."""
import base64
import json
import os
import re
from pathlib import Path


def load():
    name = os.getenv('PSL_COLD_RECOVERY_PROFILE')
    if not name:
        return {}
    p = Path(name)
    if not p.is_absolute() or p.is_symlink():
        raise RuntimeError('Absolute independently provisioned cold recovery profile required')
    v = json.loads(p.read_text(encoding='utf-8'))
    fields = {'control_ref', 'control_database', 'control_secret_env', 'archives', 'targets', 'key_env', 'principals', 'build_ref', 'pg_bin'}
    if set(v) != fields:
        raise RuntimeError('Closed cold recovery deployment registry required')
    principals = v['principals']
    purposes = {'read','capture','operate','review','agent','configure'}
    if not isinstance(principals,dict) or any(
        not re.fullmatch(r'[1-9][0-9]*',key) or not isinstance(entry,dict) or set(entry) != {'username','purposes'} or
        not isinstance(entry['username'],str) or not 1 <= len(entry['username']) <= 150 or
        not isinstance(entry['purposes'],list) or any(not isinstance(p,str) or p not in purposes for p in entry['purposes']) or
        len(entry['purposes']) != len(set(entry['purposes'])) for key,entry in principals.items()):
        raise RuntimeError('Exact fresh usernames and closed independent recovery purposes required')
    secret_name = v.pop('control_secret_env')
    if not re.fullmatch('PSL_COLD_CONTROL_[A-Z0-9_]+', secret_name):
        raise RuntimeError('Dedicated cold control secret reference required')
    try:
        v['control_secret'] = base64.b64decode(os.environ[secret_name], validate=True)
        v['keys'] = {}
        for ref, env in v.pop('key_env').items():
            if not re.fullmatch('PSL_RECOVERY_KEY_[A-Z0-9_]+', env):
                raise ValueError()
            v['keys'][ref] = base64.b64decode(os.environ[env], validate=True)
            if len(v['keys'][ref]) != 32:
                raise ValueError()
        if len(v['control_secret']) != 32:
            raise ValueError()
    except (KeyError, ValueError):
        raise RuntimeError('Independent 256-bit control and encryption secrets required') from None
    return v

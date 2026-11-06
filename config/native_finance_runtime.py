"""Deployment references only; secrets are never stored in configuration/evidence."""
import os,json
from pathlib import Path

def load():
    name=os.getenv('PSL_NATIVE_FINANCE_PROFILE')
    if not name:return {'providers':{},'stores':{}}
    p=Path(name)
    if not p.is_absolute() or p.is_symlink():raise RuntimeError('Absolute independently provisioned native Finance profile required')
    v=json.loads(p.read_text(encoding='utf-8'))
    if set(v)!={'providers','stores'} or not all(isinstance(x,dict) for x in v.values()):raise RuntimeError('Closed native Finance registry required')
    return v

"""Deployment-owned role identities; no key bytes are accepted from UI or evidence."""
import json,os


def load():
    raw=os.getenv('PSL_PILOT_RUNTIME_IDENTITIES')
    if not raw:return {}
    try:
        if len(raw)>65536:raise ValueError()
        value=json.loads(raw)
        if not isinstance(value,dict) or len(value)>32:raise ValueError()
        from apps.policy.pilot_binding_validators import identities
        identities(value)
        return value
    except (ValueError,TypeError,KeyError):
        raise RuntimeError('Invalid bounded pilot runtime identity references; secrets belong in deployment environment') from None

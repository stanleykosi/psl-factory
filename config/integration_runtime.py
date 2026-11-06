"""Deployment-owned references only. Missing registry leaves dependent adapters unavailable."""
import os,json
from pathlib import Path

def load():
    value=os.getenv('PSL_INTEGRATION_PROFILE')
    if not value:return {'endpoints':{},'secrets':{},'finance_senders':{}}
    p=Path(value)
    if not p.is_absolute() or p.is_symlink() or not p.is_file() or p.stat().st_size>1048576:raise RuntimeError('Bounded absolute integration registry file required')
    try:
        v=json.loads(p.read_text(encoding='utf-8'))
        assert set(v)=={'endpoints','secrets','finance_senders'} and all(isinstance(x,dict) for x in v.values())
        for k,r in v['endpoints'].items():
            assert isinstance(k,str) and set(r)=={'url','classification'} and r['classification'] in ['synthetic','operational'] and isinstance(r['url'],str)
        for k,r in v['secrets'].items():
            assert isinstance(k,str) and set(r)=={'env','revision'} and all(isinstance(x,str) and x for x in r.values())
        for k,r in v['finance_senders'].items():
            assert isinstance(k,str) and set(r)=={'credential_ref','credential_revision','destination_ref','case_ids','classification'} and isinstance(r['case_ids'],list)
            assert r['classification'] in ['synthetic','operational'] and r['credential_ref'] in v['secrets']
            assert v['secrets'][r['credential_ref']]['revision']==r['credential_revision']
            from uuid import UUID
            assert len(r['case_ids'])==len(set(r['case_ids'])) and all(str(UUID(x))==x for x in r['case_ids'])
    except (ValueError,AssertionError,TypeError,KeyError):raise RuntimeError('Invalid integration registry references; credentials belong in the secret environment') from None
    return v

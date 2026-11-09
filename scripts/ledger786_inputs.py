"""Offline frozen-source and retained final784 input verification, no DB connection."""
import hashlib
import json
import os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
v=json.loads((ROOT/'docs/design/ledger786-selection.json').read_text())
for name, item in v['runtime_inputs'].items():
    p=Path(item['path'])
    if hashlib.sha256(p.read_bytes()).hexdigest()!=item['sha256']:
        raise RuntimeError('Retained input changed: '+name)
for name, key in [('primary','BASELINE'),('test','TEST_BASELINE')]:
    item=v['runtime_inputs'][name]
    if os.environ.get('RUN786_'+key)!=item['path'] or os.environ.get('RUN786_'+key+'_SHA')!=item['sha256']:
        raise RuntimeError('Wrapper baseline contract differs: '+name)
print('Exact final784 primary/test/review pins verified without database access')
review=Path(v['runtime_inputs']['review_manifest']['path'])
for relative, pin in json.loads(review.read_text()).items():
    if hashlib.sha256((review.parent/relative).read_bytes()).hexdigest()!=pin:
        raise RuntimeError('Independent review artifact changed: '+relative)
result=json.loads((review.parent/'result.json').read_text())
if result['status']!='BOUNDED_SPLIT_NATIVE63_PASS':
    raise RuntimeError('Final784 acceptance status differs')

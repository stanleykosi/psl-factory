"""Fail closed pending independent final-impact792 baseline and predecessor pins. No DB."""
import hashlib,json,os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
v=json.loads((ROOT/'docs/design/impact793-selection.json').read_text())
if not v.get('accepted_predecessor') or os.environ.get('RUN793_PREDECESSOR')!=v['accepted_predecessor']:
    raise RuntimeError('Final accepted impact792 predecessor pin pending or mismatched')
for name,item in v['runtime_inputs'].items():
    if not item.get('path') or not item.get('sha256'):
        raise RuntimeError('Final accepted impact792 baseline pin pending: '+name)
    if hashlib.sha256(Path(item['path']).read_bytes()).hexdigest()!=item['sha256']:
        raise RuntimeError('Retained final impact792 artifact changed: '+name)
for name,key in [('primary','BASELINE'),('test','TEST_BASELINE')]:
    item=v['runtime_inputs'][name]
    if os.environ.get('RUN793_'+key)!=item['path'] or os.environ.get('RUN793_'+key+'_SHA')!=item['sha256']:
        raise RuntimeError('Wrapper final impact792 baseline contract differs: '+name)
review=Path(v['runtime_inputs']['review_manifest']['path'])
for relative,pin in json.loads(review.read_text()).items():
    if hashlib.sha256((review.parent/relative).read_bytes()).hexdigest()!=pin:
        raise RuntimeError('Independent impact792 review artifact changed: '+relative)
result=json.loads((review.parent/'result.json').read_text())
if not v.get('review_status') or result['status']!=v['review_status'] or result['source']!=v.get('review_source'):
    raise RuntimeError('Final impact792 acceptance status/source differs')
print('Exact accepted impact792/0021 final primary/test/review pins verified offline')

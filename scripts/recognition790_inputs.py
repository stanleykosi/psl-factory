"""Fail closed pending independent final-planning baseline and predecessor pins. No DB."""
import hashlib,json,os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
v=json.loads((ROOT/'docs/design/recognition790-selection.json').read_text())
if not v.get('accepted_predecessor') or os.environ.get('RUN790_PREDECESSOR')!=v['accepted_predecessor']:
    raise RuntimeError('Final accepted planning predecessor pin pending or mismatched')
for name,item in v['runtime_inputs'].items():
    if not item.get('path') or not item.get('sha256'):
        raise RuntimeError('Final accepted planning baseline pin pending: '+name)
    if hashlib.sha256(Path(item['path']).read_bytes()).hexdigest()!=item['sha256']:
        raise RuntimeError('Retained final planning artifact changed: '+name)
for name,key in [('primary','BASELINE'),('test','TEST_BASELINE')]:
    item=v['runtime_inputs'][name]
    if os.environ.get('RUN790_'+key)!=item['path'] or os.environ.get('RUN790_'+key+'_SHA')!=item['sha256']:
        raise RuntimeError('Wrapper final planning baseline contract differs: '+name)
review=Path(v['runtime_inputs']['review_manifest']['path'])
for relative,pin in json.loads(review.read_text()).items():
    if hashlib.sha256((review.parent/relative).read_bytes()).hexdigest()!=pin:
        raise RuntimeError('Independent planning review artifact changed: '+relative)
result=json.loads((review.parent/'result.json').read_text())
if not v.get('review_status') or result['status']!=v['review_status'] or result['source']!=v.get('review_source'):
    raise RuntimeError('Final planning acceptance status/source differs')
print('Exact accepted planning0019 final primary/test/review pins verified offline')

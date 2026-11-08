"""Fail closed pending independent final-impact794 baseline and predecessor pins. No DB."""
import hashlib,json,os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
v=json.loads((ROOT/'docs/design/impact795b-selection.json').read_text())
if not v.get('accepted_predecessor') or os.environ.get('RUN795B_PREDECESSOR')!=v['accepted_predecessor']:
    raise RuntimeError('Final accepted impact794 predecessor pin pending or mismatched')
for name,item in v['runtime_inputs'].items():
    if not item.get('path') or not item.get('sha256'):
        raise RuntimeError('Final accepted impact794 baseline pin pending: '+name)
    if hashlib.sha256(Path(item['path']).read_bytes()).hexdigest()!=item['sha256']:
        raise RuntimeError('Retained final impact794 artifact changed: '+name)
for name,key in [('primary','BASELINE'),('test','TEST_BASELINE')]:
    item=v['runtime_inputs'][name]
    if os.environ.get('RUN795B_'+key)!=item['path'] or os.environ.get('RUN795B_'+key+'_SHA')!=item['sha256']:
        raise RuntimeError('Wrapper final impact794 baseline contract differs: '+name)
review=Path(v['runtime_inputs']['review_manifest']['path'])
for relative,pin in json.loads(review.read_text()).items():
    if hashlib.sha256((review.parent/relative).read_bytes()).hexdigest()!=pin:
        raise RuntimeError('Independent impact794 review artifact changed: '+relative)
result=json.loads((review.parent/'result.json').read_text())
if not v.get('review_status') or result['status']!=v['review_status'] or result['source']!=v.get('review_source'):
    raise RuntimeError('Final impact794 acceptance status/source differs')
print('Accepted794 primary0023 and failed795a test0024 continuation inputs verified offline')
partial=Path(v['runtime_inputs']['partial_review_manifest']['path'])
for relative,pin in json.loads(partial.read_text()).items():
    if hashlib.sha256((partial.parent/relative).read_bytes()).hexdigest()!=pin:
        raise RuntimeError('Failed795a retained proof changed: '+relative)
result=json.loads((partial.parent/'result.json').read_text())
if result['status']!=v['failed_prior_status'] or result['source']!=v['failed_prior_source']:
    raise RuntimeError('Failed795a partial audit status/source differs')
for relative,pin in v['historical_source_pins'].items():
    if hashlib.sha256((ROOT/relative).read_bytes()).hexdigest()!=pin:
        raise RuntimeError('Historical795 source artifact changed: '+relative)
print('Failed795a proof/status and historical source preserved; fresh continuation is not retry acceptance')

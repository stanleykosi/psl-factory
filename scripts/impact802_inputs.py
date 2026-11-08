"""Fail closed pending independent final-impact801 baseline and predecessor pins. No DB."""
import hashlib,json,os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
v=json.loads((ROOT/'docs/design/impact802-selection.json').read_text())
if not v.get('accepted_predecessor') or os.environ.get('RUN802_PREDECESSOR')!=v['accepted_predecessor']:
    raise RuntimeError('Final accepted impact801 predecessor pin pending or mismatched')
for name,item in v['runtime_inputs'].items():
    if not item.get('path') or not item.get('sha256'):
        raise RuntimeError('Final accepted impact801 baseline pin pending: '+name)
    if hashlib.sha256(Path(item['path']).read_bytes()).hexdigest()!=item['sha256']:
        raise RuntimeError('Retained final impact801 artifact changed: '+name)
for name,key in [('primary','BASELINE'),('test','TEST_BASELINE')]:
    item=v['runtime_inputs'][name]
    if os.environ.get('RUN802_'+key)!=item['path'] or os.environ.get('RUN802_'+key+'_SHA')!=item['sha256']:
        raise RuntimeError('Wrapper final impact801 baseline contract differs: '+name)
review=Path(v['runtime_inputs']['review_manifest']['path'])
for relative,pin in json.loads(review.read_text()).items():
    if hashlib.sha256((review.parent/relative).read_bytes()).hexdigest()!=pin:
        raise RuntimeError('Independent impact801 review artifact changed: '+relative)
result=json.loads((review.parent/'result.json').read_text())
if not v.get('review_status') or result['status']!=v['review_status'] or result['source']!=v.get('review_source'):
    raise RuntimeError('Final impact801 acceptance status/source differs')
print('Exact accepted impact801/0030 final primary/test/review pins verified offline')

# Retained diagnostic failures are not retroactive passes.
for key,status,source in [('prior798a_review_manifest', 'PARTIAL_798A_FAILED_NOT_ACCEPTED', 'def5dbb0e51deb33bf91f9b9fa615117c8cd92cb'), ('prior797a_review_manifest', 'PARTIAL_797A_FAILED_NOT_ACCEPTED', 'ee87087086124596dd51dc7b6c48b0ea14b871f0'), ('prior797b_review_manifest', 'PARTIAL_797B_FAILED_NOT_ACCEPTED', '7d0b36a9a9b8e20174da7ce640709e613f7e3bb8')]:
    prior=Path(v['runtime_inputs'][key]['path'])
    for relative,pin in json.loads(prior.read_text()).items():
        if hashlib.sha256((prior.parent/relative).read_bytes()).hexdigest()!=pin:
            raise RuntimeError('Retained diagnostic artifact changed: '+relative)
    result=json.loads((prior.parent/'result.json').read_text())
    if result['status']!=status or result['source']!=source:
        raise RuntimeError('Retained diagnostic identity differs')
print('Original798a and797a/b failed evidence preserved separately')

"""Fail closed pending independent final-impact797 baseline and predecessor pins. No DB."""
import hashlib,json,os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
v=json.loads((ROOT/'docs/design/impact798-selection.json').read_text())
if not v.get('accepted_predecessor') or os.environ.get('RUN798_PREDECESSOR')!=v['accepted_predecessor']:
    raise RuntimeError('Final accepted impact797 predecessor pin pending or mismatched')
for name,item in v['runtime_inputs'].items():
    if not item.get('path') or not item.get('sha256'):
        raise RuntimeError('Final accepted impact797 baseline pin pending: '+name)
    if hashlib.sha256(Path(item['path']).read_bytes()).hexdigest()!=item['sha256']:
        raise RuntimeError('Retained final impact797 artifact changed: '+name)
for name,key in [('primary','BASELINE'),('test','TEST_BASELINE')]:
    item=v['runtime_inputs'][name]
    if os.environ.get('RUN798_'+key)!=item['path'] or os.environ.get('RUN798_'+key+'_SHA')!=item['sha256']:
        raise RuntimeError('Wrapper final impact797 baseline contract differs: '+name)
review=Path(v['runtime_inputs']['review_manifest']['path'])
for relative,pin in json.loads(review.read_text()).items():
    if hashlib.sha256((review.parent/relative).read_bytes()).hexdigest()!=pin:
        raise RuntimeError('Independent impact797 review artifact changed: '+relative)
result=json.loads((review.parent/'result.json').read_text())
if not v.get('review_status') or result['status']!=v['review_status'] or result['source']!=v.get('review_source'):
    raise RuntimeError('Final impact797 acceptance status/source differs')
print('Exact accepted impact797/0026 final primary/test/review pins verified offline')

# Earlier diagnostic failures remain immutable evidence, not retroactive passes.
for key,status,source in [('prior797a_review_manifest','PARTIAL_797A_FAILED_NOT_ACCEPTED','ee87087086124596dd51dc7b6c48b0ea14b871f0'),('prior797b_review_manifest','PARTIAL_797B_FAILED_NOT_ACCEPTED','7d0b36a9a9b8e20174da7ce640709e613f7e3bb8')]:
    prior=Path(v['runtime_inputs'][key]['path'])
    for relative,pin in json.loads(prior.read_text()).items():
        if hashlib.sha256((prior.parent/relative).read_bytes()).hexdigest()!=pin:
            raise RuntimeError('Retained earlier797 failure evidence changed: '+relative)
    result=json.loads((prior.parent/'result.json').read_text())
    if result['status']!=status or result['source']!=source:
        raise RuntimeError('Earlier797 failure audit identity differs')
print('Both original797a/797b diagnostic failures preserved separately from accepted797c')

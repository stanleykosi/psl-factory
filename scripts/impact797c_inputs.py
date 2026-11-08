"""Fail closed pending independent 797b continuation baseline and predecessor pins. No DB."""
import hashlib,json,os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
v=json.loads((ROOT/'docs/design/impact797c-selection.json').read_text())
if not v.get('accepted_predecessor') or os.environ.get('RUN797C_PREDECESSOR')!=v['accepted_predecessor']:
    raise RuntimeError('Final accepted impact796 predecessor pin pending or mismatched')
for name,item in v['runtime_inputs'].items():
    if not item.get('path') or not item.get('sha256'):
        raise RuntimeError('Audited797b continuation baseline pin pending: '+name)
    if hashlib.sha256(Path(item['path']).read_bytes()).hexdigest()!=item['sha256']:
        raise RuntimeError('Retained final impact796 artifact changed: '+name)
for name,key in [('primary','BASELINE'),('test','TEST_BASELINE')]:
    item=v['runtime_inputs'][name]
    if os.environ.get('RUN797C_'+key)!=item['path'] or os.environ.get('RUN797C_'+key+'_SHA')!=item['sha256']:
        raise RuntimeError('Wrapper797c continuation baseline contract differs: '+name)
review=Path(v['runtime_inputs']['review_manifest']['path'])
for relative,pin in json.loads(review.read_text()).items():
    if hashlib.sha256((review.parent/relative).read_bytes()).hexdigest()!=pin:
        raise RuntimeError('Independent impact796 review artifact changed: '+relative)
result=json.loads((review.parent/'result.json').read_text())
if not v.get('review_status') or result['status']!=v['review_status'] or result['source']!=v.get('review_source'):
    raise RuntimeError('Final impact796 acceptance status/source differs')
print('Accepted796 review retained; current baselines are separately audited797b0026 state')

partial=Path(v['runtime_inputs']['partial_review_manifest']['path'])
for relative,pin in json.loads(partial.read_text()).items():
    if hashlib.sha256((partial.parent/relative).read_bytes()).hexdigest()!=pin:
        raise RuntimeError('Failed797b retained artifact changed: '+relative)
result=json.loads((partial.parent/'result.json').read_text())
if result['status']!=v['failed_prior_status'] or result['source']!=v['failed_prior_source']:
    raise RuntimeError('Partial797b audit identity differs')
for relative,pin in v['historical_source_pins'].items():
    if hashlib.sha256((ROOT/relative).read_bytes()).hexdigest()!=pin:
        raise RuntimeError('Historical797 source changed: '+relative)
if os.environ.get('RUN797C_PRIMARY_DECLARED')!=v['runtime_inputs']['primary_declared']['path']:
    raise RuntimeError('Second primary retained baseline differs')
print('Failed797b remains failed; both audited0026 inputs verified offline for a fresh continuation')

prior=Path(v['runtime_inputs']['prior797a_review_manifest']['path'])
for relative,pin in json.loads(prior.read_text()).items():
    if hashlib.sha256((prior.parent/relative).read_bytes()).hexdigest()!=pin:
        raise RuntimeError('Earlier failed797a retained artifact changed: '+relative)
result=json.loads((prior.parent/'result.json').read_text())
if result['status']!='PARTIAL_797A_FAILED_NOT_ACCEPTED' or result['source']!='ee87087086124596dd51dc7b6c48b0ea14b871f0':
    raise RuntimeError('Earlier failed797a audit identity differs')
print('Both failed797a and797b preserved; no migration/reset/replay authorized')

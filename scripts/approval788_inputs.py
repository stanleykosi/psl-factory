"""Fail closed pending independent final-ledger baseline and predecessor pins. No DB."""
import hashlib,json,os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
v=json.loads((ROOT/'docs/design/approval788-selection.json').read_text())
if not v.get('accepted_predecessor') or os.environ.get('RUN788_PREDECESSOR')!=v['accepted_predecessor']:
    raise RuntimeError('Final accepted ledger predecessor pin pending or mismatched')
for name,item in v['runtime_inputs'].items():
    if not item.get('path') or not item.get('sha256'):
        raise RuntimeError('Final accepted ledger baseline pin pending: '+name)
    if hashlib.sha256(Path(item['path']).read_bytes()).hexdigest()!=item['sha256']:
        raise RuntimeError('Retained final ledger artifact changed: '+name)
for name,key in [('primary','BASELINE'),('test','TEST_BASELINE')]:
    item=v['runtime_inputs'][name]
    if os.environ.get('RUN788_'+key)!=item['path'] or os.environ.get('RUN788_'+key+'_SHA')!=item['sha256']:
        raise RuntimeError('Wrapper final ledger baseline contract differs: '+name)
review=Path(v['runtime_inputs']['review_manifest']['path'])
for relative,pin in json.loads(review.read_text()).items():
    if hashlib.sha256((review.parent/relative).read_bytes()).hexdigest()!=pin:
        raise RuntimeError('Independent ledger review artifact changed: '+relative)
result=json.loads((review.parent/'result.json').read_text())
if result['status']!='BOUNDED_LEDGER21_PASS' or result['source']!='3af08b145b143e0da816b51fca838382504a22f3':
    raise RuntimeError('Final ledger acceptance status/source differs')
print('Exact accepted ledger0017 final primary/test/review pins verified offline')

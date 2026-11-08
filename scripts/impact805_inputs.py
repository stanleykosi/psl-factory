"""Offline accepted804b proof and retained partial-failure pins. No database connection."""
import hashlib,json,os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
v=json.loads((ROOT/'docs/design/impact805-selection.json').read_text())
def require(ok,message):
    if not ok:raise RuntimeError(message)
def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
require(v.get('accepted_predecessor') and os.environ.get('RUN805_PREDECESSOR')==v['accepted_predecessor'],'Accepted804b predecessor mismatch')
for name,item in v['runtime_inputs'].items():
    require(item.get('path') and item.get('sha256'),'Pending accepted baseline '+name)
    require(digest(item['path'])==item['sha256'],'Retained input changed '+name)
for name,key in [('primary','BASELINE'),('test','TEST_BASELINE')]:
    item=v['runtime_inputs'][name]
    require(os.environ.get('RUN805_'+key)==item['path'] and os.environ.get('RUN805_'+key+'_SHA')==item['sha256'],'Wrapper baseline differs '+name)
review=Path(v['runtime_inputs']['review_manifest']['path']);manifest=json.loads(review.read_text())
# Accepted804b manifest stores workspace-relative raw artifacts; no arbitrary alternate root.
workspace=ROOT.parent
require(Path(manifest['root'])==workspace/'impact804b-native/run804b','804b raw evidence root mismatch')
for item in manifest['artifacts']:
    rel=Path(item['path'])
    require(not rel.is_absolute() and '..' not in rel.parts and rel.parts[:2]==('impact804b-native','run804b'),'Unexpected804b artifact path')
    path=workspace/rel
    require(path.stat().st_size==item['bytes'] and digest(path)==item['sha256'],'Accepted804b artifact changed '+str(rel))
result=json.loads(Path(v['runtime_inputs']['review_result']['path']).read_text())
require(result['status']==v['review_status'] and result['source']==v['review_source'],'Accepted804b identity differs')
for key,status,source in [('partial804a_review_manifest','PARTIAL_804A_RESOURCE_STOP_NOT_ACCEPTED','0c261d79d72fae9edf758f16c57d3232829cf517'),('prior798a_review_manifest','PARTIAL_798A_FAILED_NOT_ACCEPTED','def5dbb0e51deb33bf91f9b9fa615117c8cd92cb'),('prior797a_review_manifest','PARTIAL_797A_FAILED_NOT_ACCEPTED','ee87087086124596dd51dc7b6c48b0ea14b871f0'),('prior797b_review_manifest','PARTIAL_797B_FAILED_NOT_ACCEPTED','7d0b36a9a9b8e20174da7ce640709e613f7e3bb8')]:
    prior=Path(v['runtime_inputs'][key]['path'])
    for relative,pin in json.loads(prior.read_text()).items():
        require(digest(prior.parent/relative)==pin,'Retained failure artifact changed '+relative)
    old=json.loads((prior.parent/'result.json').read_text())
    require(old['status']==status and old['source']==source,'Retained failure identity differs')
print('Accepted804b final0032 primary/test/review verified; original804a resource stop and798a/797a/b failures retained separately')

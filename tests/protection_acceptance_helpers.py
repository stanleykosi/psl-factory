import copy
from apps.documents import protection_acceptance as d,validation as af
from apps.policy.protection_acceptance_validators import COMPONENT,OWNER
from .private_protection_helpers import fixture as native_fixture,capture as native_capture,configure as native_configure,assessed
from .validation_helpers import policy
from .operator_helpers import evidence

def package(f,reference='protection-owner-package',payload=None):
 p=af.prepare_package(f['actor'],f['case'].pk,reference,payload or dict(f['package'].payload),f['e'].pk,None)
 f['protection_package']=p;return p

def prepare(f,reference='protection-owner',predecessor=None):
 f['protection_packet']=d.prepare(f['actor'],f['case'].pk,f['private_assessment'].pk,f['protection_package'].pk,reference,predecessor)
 return f['protection_packet']

def fixture(prefix='protection-owner',foreign=False):
 f=native_fixture(prefix,foreign=foreign);f['private_contract']=native_capture(f);native_configure(f);assessed(f)
 package(f);prepare(f);f['protection_owner_evidence']=evidence(f,'owner_validation','Explicit synthetic owner protection-evidence decision; no operational acceptance')
 return f

def rules(f,**changes):
 v=copy.deepcopy(f['acceptance_rules']);v['private_protection']={'inventory':[{'package_id':f['protection_package'].pk,'assessment_id':f['private_assessment'].pk}],'freshness_seconds':3600,'receipt_requirement':'observed','independent_transport_acceptor':True};v['private_protection'].update(changes);return v

def owners(f,value=None):
 v=copy.deepcopy(value or f['owner_rules'])
 for row in v['assignments']:row['process_ids']=f['protection_package'].payload['process_ids']
 return policy(f['actor'],f['case'],OWNER,v,f['e'])

def configure(f,value=None):
 return policy(f['actor'],f['case'],COMPONENT,value or rules(f),f['e'])

def reviews(f,key='owner'):
 out=[]
 for kind in ['meaning','expectations','acceptance']:
  a=f['acceptor'] if kind=='acceptance' else f['recipient']
  out.append(af.review(a,f['case'].pk,f['protection_package'].pk,kind,'approve',key+'-'+kind,f['protection_owner_evidence'].pk,'Explicit synthetic protection evidence '+kind,None))
 return out

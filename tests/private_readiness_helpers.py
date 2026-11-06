from apps.finance import readiness_acceptance as d
from apps.documents import validation as af
from apps.policy.validation_validators import ACCEPTANCE
from .publication_readiness_helpers import fixture as native_fixture,enrolled
from .validation_helpers import policy
from .ledger_helpers import evidence

def package(f,reference='readiness-owner',payload=None):
 p=af.prepare_package(f['actor'],f['case'].pk,reference,payload or dict(f['package'].payload),f['e'].pk,None)
 f['owner_package']=p;return p

def fixture(prefix='private-readiness-owner',foreign=False):
 f=native_fixture(prefix,foreign=foreign);enrolled(f);package(f)
 f['packet']=d.prepare(f['actor'],f['case'].pk,f['assessment'].pk,f['owner_package'].pk,'capability-owner')
 f['owner_evidence']=evidence(f,'owner_validation','Explicit synthetic owner decision on bounded capability evidence, not business/operational acceptance.')
 return f

def rules(f,**changes):
 v=dict(f['acceptance_rules'],private_readiness={'inventory':[{'package_id':f['owner_package'].pk,'assessment_id':f['assessment'].pk}],'freshness_seconds':3600,'receipt_requirement':'observed','independent_transport_acceptor':True})
 v['private_readiness'].update(changes);return v

def configure(f,value=None):return policy(f['actor'],f['case'],ACCEPTANCE,value or rules(f),f['e'])

def reviews(f):
 rows=[]
 for kind in ['meaning','expectations','acceptance']:
  a=f['acceptor'] if kind=='acceptance' else f['recipient']
  rows.append(af.review(a,f['case'].pk,f['owner_package'].pk,kind,'approve','private-'+kind,f['owner_evidence'].pk,'Actual isolated synthetic human decision: '+kind,None))
 return rows

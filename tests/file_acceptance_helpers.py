import copy
from apps.documents import protection_acceptance as d
from .private_file_helpers import fixture as native_fixture,configure as native_configure,assessed
from .protection_acceptance_helpers import package,owners,reviews
from .operator_helpers import evidence
from .validation_helpers import policy
from apps.policy.protection_acceptance_validators import COMPONENT

def prepare(f,reference='file-owner',predecessor=None,kind=None):
 f['protection_packet']=d.prepare(f['actor'],f['case'].pk,f['file_assessment'].pk,f['protection_package'].pk,reference,predecessor,native_kind=kind or f['file_contract'].private_file_readiness.job.kind)
 return f['protection_packet']

def fixture(prefix='file-owner',foreign=False):
 f=native_fixture(prefix,foreign=foreign);native_configure(f);assessed(f);package(f,'file-owner-package');prepare(f);f['protection_owner_evidence']=evidence(f,'owner_validation','Explicit synthetic native file evidence owner decision; operational acceptance separate');return f

def rules(f,**changes):
 v=copy.deepcopy(f['acceptance_rules']);v['private_protection']={'inventory':[{'package_id':f['protection_package'].pk,'assessment_id':f['file_assessment'].pk,'native_kind':f['file_contract'].private_file_readiness.job.kind}],'freshness_seconds':3600,'receipt_requirement':'observed','independent_transport_acceptor':True};v['private_protection'].update(changes);return v

def configure(f,value=None):return policy(f['actor'],f['case'],COMPONENT,value or rules(f),f['e'])

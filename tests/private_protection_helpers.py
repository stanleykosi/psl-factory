import json
from django.db import connection
from django.conf import settings
from apps.workflows import readiness as r,readiness_delivery as w,operator_delivery as ow
from apps.policy.readiness_validators import PRIVATE_COMPONENT
from .private_operations_helpers import fixture as ops_fixture,effect
from .operator_helpers import evidence
from .readiness_helpers import policy

def fixture(prefix='private-protection-ready',foreign=False):
 f=ops_fixture(prefix,foreign=foreign)
 export=effect(f,'export');backup=effect(f,'backup',export.pk)
 f['restore']=ow.reserve(f['actor'],f['case'].pk,f['plan'].pk,'restore',backup.pk)
 f['private_rules']=dict(json.loads((settings.BASE_DIR/'fixtures/integration-readiness.json').read_text(encoding='utf-8'))['rules'],probe_user_id=f['actor'].pk,probe_role='Finance',reviewer_id=f['reviewer'].pk,reviewer_role='Finance',independent_review=True,require_receipt_probe=True,lease_seconds=120,private_protection_job_ids=[f['restore'].pk])
 f['private_payload']={'kind':'adapter','family':'protection','implementation':'internal_postgres_session_v1','target_key':'internal:protection','credential_ref':'runtime:postgres','credential_revision':'fixture-v1','principal_ref':'principal:'+connection.settings_dict['USER'],'contract_version':'psl.internal-receipts/v1','model_id':None,'capabilities':['health','receipt_lookup'],'data_scope':'public_canary_and_scoped_receipt_metadata_only'}
 f['private_contract_evidence']=evidence(f,'integration_contract');f['private_review_evidence']=evidence(f,'integration_review');f['private_selection_evidence']=evidence(f,'integration_selection')
 return f

def capture(f,reference='private-restore',predecessor=None):
 return r.capture(f['actor'],f['case'].pk,reference,f['private_payload'],f['private_contract_evidence'].pk,predecessor=predecessor,native_protection_job=f['restore'].pk)

def configure(f):return policy(f,PRIVATE_COMPONENT,f['private_rules'])

def probe(f,kind,key=None):
 j=w.reserve(f['actor'],f['case'].pk,f['private_contract'].pk,key or kind,kind,f['restore'].pk if kind=='receipt' else None)
 w.run_once(case_id=f['case'].pk);j.refresh_from_db();assert j.status=='confirmed',j.status
 return j

def assessed(f,key='ready'):
 probe(f,'health',key+'-health');probe(f,'receipt',key+'-receipt')
 a=r.assess(f['actor'],f['case'].pk,f['private_contract'].pk,key)
 r.review(f['reviewer'],f['case'].pk,a.pk,'confirm',key,f['private_review_evidence'].pk)
 f['private_assessment']=a;return a

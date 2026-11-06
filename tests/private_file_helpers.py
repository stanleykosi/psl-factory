import json
from django.conf import settings
from django.db import connection
from apps.workflows import readiness as r,readiness_delivery as w,operator_delivery as ow
from apps.policy.readiness_validators import PRIVATE_COMPONENT
from .private_operations_helpers import fixture as ops_fixture,effect,plan
from .operator_helpers import evidence
from .readiness_helpers import policy

def fixture(prefix='private-file',foreign=False):
 f=ops_fixture(prefix,foreign=foreign);a=effect(f,'export');f['file_export']=a.job;f['file_backup']=ow.reserve(f['actor'],f['case'].pk,f['plan'].pk,'backup',a.pk)
 f['file_rules']=dict(json.loads((settings.BASE_DIR/'fixtures/private-file-readiness.json').read_text(encoding='utf-8'))['rules'],probe_user_id=f['actor'].pk,probe_role='Finance',reviewer_id=f['reviewer'].pk,reviewer_role='Finance',freshness_seconds=3600,lease_seconds=120,max_attempts=3,allow_synthetic_target=True,private_file_job_ids=[a.job_id,f['file_backup'].pk])
 f['file_payload']={'kind':'adapter','family':'protection','implementation':'internal_postgres_session_v1','target_key':'internal:protection','credential_ref':'runtime:postgres','credential_revision':'fixture-v1','principal_ref':'principal:'+connection.settings_dict['USER'],'contract_version':'psl.internal-receipts/v1','model_id':None,'capabilities':['health','receipt_lookup'],'data_scope':'public_canary_and_scoped_receipt_metadata_only'}
 f['file_contract_evidence']=evidence(f,'integration_contract');f['file_review_evidence']=evidence(f,'integration_review');f['file_selection_evidence']=evidence(f,'integration_selection');f['sources']={'policy_decision':f['e']}
 f['file_contract']=capture(f);return f

def capture(f,job=None,reference='private-file',predecessor=None):return r.capture(f['actor'],f['case'].pk,reference,f['file_payload'],f['file_contract_evidence'].pk,predecessor=predecessor,native_file_job=(job or f['file_backup']).pk)
def configure(f,value=None):return policy(f,PRIVATE_COMPONENT,value or f['file_rules'])
def probe(f,kind,key=None):
 j=w.reserve(f['actor'],f['case'].pk,f['file_contract'].pk,key or kind,kind,f['file_contract'].private_file_readiness.job_id if kind=='receipt' else None)
 w.run_once(case_id=f['case'].pk);j.refresh_from_db();assert j.status=='confirmed',j.status;return j
def assessed(f,key='file-ready'):
 probe(f,'health',key+'-health');probe(f,'receipt',key+'-receipt');a=r.assess(f['actor'],f['case'].pk,f['file_contract'].pk,key);r.review(f['reviewer'],f['case'].pk,a.pk,'confirm',key,f['file_review_evidence'].pk);f['file_assessment']=a;return a
def extra_jobs(f,reference):
 ow.operate(f['actor'],f['case'].pk,f['file_backup'].pk,'cancel','Use separate isolated test job')
 plan(f,reference);a=effect(f,'export');f['file_export']=a.job;f['file_backup']=ow.reserve(f['actor'],f['case'].pk,f['plan'].pk,'backup',a.pk);return f

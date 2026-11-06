import json
from django.conf import settings
from django.db import connection
from apps.workflows import readiness as r,readiness_delivery as rw,protection,operator_delivery
from apps.workflows.operator_inventory import bundle
from apps.documents.contracts import digest
from apps.policy.readiness_validators import ADAPTER
from apps.policy.operator_validators import OPERATOR,PROTECTION
from .support_helpers import evidence
from .support_agent_helpers import activate
from .operator_helpers import policy as operator_policy

def operators(f,configured=True,family='supportresponse'):
 v=json.loads((settings.BASE_DIR/'fixtures/operator-recovery.json').read_text(encoding='utf-8'))
 v['operator'].update(operators=[{'user_id':f['actor'].pk,'role':'Support','purposes':['recover','export','backup','restore','review']},{'user_id':f['reviewer'].pk,'role':'Support','purposes':['review']}],reviewer_id=f['reviewer'].pk,reviewer_role='Support',routes=[{'family':family,'actions':['cancel','retry']}])
 if configured:operator_policy(f,OPERATOR,v['operator']);operator_policy(f,PROTECTION,v['protection'])
 return v

def enroll(f,job,ready=True,family='supportresponse'):
 a,c=f['actor'],f['case'];value=dict(json.loads((settings.BASE_DIR/'fixtures/integration-readiness.json').read_text(encoding='utf-8'))['rules'],probe_user_id=a.pk,probe_role='Support',reviewer_id=f['reviewer'].pk,reviewer_role='Support',require_receipt_probe=True)
 activate(f,ADAPTER,value)
 body={'kind':'adapter','family':family,'implementation':'internal_postgres_session_v1','target_key':'internal:'+family,'credential_ref':'runtime:postgres','credential_revision':'fixture-v1','principal_ref':'principal:'+connection.settings_dict['USER'],'contract_version':'psl.internal-receipts/v1','model_id':None,'capabilities':['health','receipt_lookup'],'data_scope':'public_canary_and_scoped_receipt_metadata_only'}
 contract=r.capture(a,c.pk,'private-response-native',body,evidence(f,'integration_contract').pk);r.select(a,c.pk,contract.pk,evidence(f,'integration_selection').pk)
 if ready:
  for kind in ['health','receipt']:
   j=rw.reserve(a,c.pk,contract.pk,'response-'+kind,kind,job.pk if kind=='receipt' else None);rw.run_once(case_id=c.pk);j.refresh_from_db();assert j.status=='confirmed'
  assessment=r.assess(a,c.pk,contract.pk,'private-ready');r.review(f['reviewer'],c.pk,assessment.pk,'confirm','private-ready',evidence(f,'integration_review').pk);f['assessment']=assessment
 f['response_contract']=contract;f['adapter_rules']=value;return contract

def plan(f):
 manifest=bundle(f['actor'],f['case'],200)
 value={'scope':'portable_case_metadata_v1','process_ids':['B14'],'build_ref':'synthetic-support-response-operations','source_ref':'case:'+str(f['case'].pk),'source_version':'fixture-v1','target_ref':'isolated_metadata_db_v1','expected_record_count':len(manifest['evidence'])+len(manifest['jobs']),'expected_manifest_sha256':digest(manifest)}
 f['plan']=protection.capture_plan(f['actor'],f['case'].pk,'private-metadata',value,evidence(f,'ops_plan').pk);return f['plan']

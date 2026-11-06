import json
from django.conf import settings
from django.db import connection
from apps.workflows import readiness as r,readiness_delivery as rw,protection,operator_delivery as ow
from apps.workflows.operator_inventory import bundle
from apps.documents.contracts import digest
from apps.policy.operator_validators import OPERATOR,PROTECTION
from apps.policy.readiness_validators import ADAPTER
from .ledger_helpers import evidence
from .ledger_agent_helpers import activate
from .operator_helpers import policy

def operators(f,configured=True):
 v=json.loads((settings.BASE_DIR/'fixtures/operator-recovery.json').read_text(encoding='utf-8'))
 v['operator'].update(operators=[{'user_id':f['actor'].pk,'role':'Finance','purposes':['recover','export','backup','restore','review']},{'user_id':f['reviewer'].pk,'role':'Finance','purposes':['review']}],reviewer_id=f['reviewer'].pk,reviewer_role='Finance',routes=[{'family':'ledgerdata','actions':['retry']}])
 f['sources']={'policy_decision':f['e']}
 if configured:
  policy(f,OPERATOR,v['operator']);policy(f,PROTECTION,v['protection'])
 return v

def enroll(f,job,ready=True):
 value=dict(json.loads((settings.BASE_DIR/'fixtures/integration-readiness.json').read_text(encoding='utf-8'))['rules'],probe_user_id=f['actor'].pk,probe_role='Finance',reviewer_id=f['reviewer'].pk,reviewer_role='Finance',require_receipt_probe=True)
 activate(f,ADAPTER,value)
 body={'kind':'adapter','family':'ledgerdata','implementation':'internal_postgres_session_v1','target_key':'internal:ledgerdata','credential_ref':'runtime:postgres','credential_revision':'fixture-v1','principal_ref':'principal:'+connection.settings_dict['USER'],'contract_version':'psl.internal-receipts/v1','model_id':None,'capabilities':['health','receipt_lookup'],'data_scope':'public_canary_and_scoped_receipt_metadata_only'}
 a,c=f['actor'],f['case'];contract=r.capture(a,c.pk,'finance-receipts',body,evidence(f,'integration_contract','Synthetic local receipt contract').pk);r.select(a,c.pk,contract.pk,evidence(f,'integration_selection','Explicit synthetic enrollment').pk)
 if ready:
  for kind in ['health','receipt']:
   j=rw.reserve(a,c.pk,contract.pk,kind,kind,job.pk if kind=='receipt' else None);rw.run_once(case_id=c.pk);j.refresh_from_db();assert j.status=='confirmed',j.status
  assessment=r.assess(a,c.pk,contract.pk,'native-ready');r.review(f['reviewer'],c.pk,assessment.pk,'confirm','native-ready',evidence(f,'integration_review','Synthetic independent receipt capability review').pk);f['assessment']=assessment
 f['native_contract']=contract;return contract

def plan(f):
 m=bundle(f['actor'],f['case'],200)
 v={'scope':'portable_case_metadata_v1','process_ids':['F01'],'build_ref':'synthetic-finance-operations','source_ref':'case:'+str(f['case'].pk),'source_version':'fixture-v1','target_ref':'isolated_metadata_db_v1','expected_record_count':len(m['evidence'])+len(m['jobs']),'expected_manifest_sha256':digest(m)}
 f['plan']=protection.capture_plan(f['actor'],f['case'].pk,'finance-metadata',v,evidence(f,'ops_plan','Synthetic metadata plan').pk);return f['plan']

def effect(f,kind,input_id=None):
 j=ow.reserve(f['actor'],f['case'].pk,f['plan'].pk,kind,input_id)
 # Execute only this isolated test job; never drain unrelated work.
 item=ow.claim();assert item[0]==j.pk
 from adapters.operator_protection import NativeMetadataProtectionAdapter
 receipt=ow.dispatch(*item,NativeMetadataProtectionAdapter());ow.finish(*item,'confirmed',receipt)
 from apps.workflows.operator_models import RecoveryArtifact
 return RecoveryArtifact.objects.get(job=j)

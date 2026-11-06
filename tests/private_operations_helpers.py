from apps.workflows import protection as p,operator_delivery as w
from apps.workflows.operator_inventory import bundle
from apps.documents.contracts import digest
from apps.policy.operator_validators import OPERATOR,PROTECTION
from .private_readiness_helpers import fixture as native_fixture,configure as native_policy,reviews
from .ledger_operations_helpers import operators
from .operator_helpers import policy,evidence

def fixture(prefix='accepted-private-ops',foreign=False,configured=True):
 f=native_fixture(prefix,foreign=foreign);native_policy(f);reviews(f);values=operators(f,configured=False)
 values['operator']['routes'].append({'family':'protection','actions':['cancel','retry','replace_intent']});policy(f,OPERATOR,values['operator'])
 values['protection']['lease_seconds']=120 # Explicit synthetic budget for the nested source/owner control graph.
 f['ops_values']=values;f['protection_rules']=dict(values['protection'],private_readiness_packet_ids=[f['packet'].pk],private_disclosure='accepted_metadata_only')
 if configured:f['protection_policy']=policy(f,PROTECTION,f['protection_rules'])
 plan(f);f['ops_review_evidence']=evidence(f,'ops_review');return f

def plan(f,reference='private-metadata',selected=True,predecessor=None):
 ids=[f['packet'].pk] if selected else [];m=bundle(f['actor'],f['case'],200,ids)
 payload={'scope':'portable_case_metadata_v1','process_ids':f['owner_package'].payload['process_ids'],'build_ref':'synthetic-private-protection','source_ref':'case:'+str(f['case'].pk),'source_version':'fixture-v1','target_ref':'isolated_metadata_db_v1','expected_record_count':len(m['evidence'])+len(m['jobs'])+len(m.get('accepted_private_readiness',[])),'expected_manifest_sha256':digest(m)}
 if selected:payload['private_readiness_packet_ids']=ids
 row=p.capture_plan(f['actor'],f['case'].pk,reference,payload,evidence(f,'ops_plan').pk,predecessor=predecessor)
 f['plan']=row;return row

def effect(f,kind,input_id=None):
 j=w.reserve(f['actor'],f['case'].pk,f['plan'].pk,kind,input_id);lease=w.claim();assert lease[0]==j.pk
 from adapters.operator_protection import NativeMetadataProtectionAdapter
 receipt=w.dispatch(*lease,NativeMetadataProtectionAdapter());w.finish(*lease,'confirmed',receipt)
 from apps.workflows.operator_models import RecoveryArtifact
 return RecoveryArtifact.objects.get(job=j)

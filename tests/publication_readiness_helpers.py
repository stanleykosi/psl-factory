import json
from django.conf import settings
from django.db import connection
from apps.policy.readiness_validators import ADAPTER
from apps.policy.ledger_validators import PUBLICATION
from apps.workflows import readiness as r,readiness_delivery as w
from apps.finance import accepted_documents as d
from .accepted_publication_helpers import ready,reviewed
from .ledger_helpers import evidence,policy as finance_policy
from .readiness_helpers import policy

def fixture(prefix='finance-publication-readiness',foreign=False):
 base=None
 if foreign:
  from .finance_acceptance_helpers import fixture as source_fixture
  from .ledger_resolution_helpers import second_case,propose,confirm,current
  from .ledger_helpers import capture as source_capture,verify
  from apps.identity.models import Grant
  from apps.core.management.commands.seed_demo import ACTIONS
  base=source_fixture(prefix);g=second_case(base);g['case'].tenant=base['case'].tenant;g['case'].save(update_fields=['tenant']);Grant.objects.bulk_create([Grant(case=g['case'],user=base['acceptor'],action=k) for k in ACTIONS]);other=source_capture(g);verify(g,other);verify(base,base['lineage']);confirm(base,propose(base,base['lineage'],[other]));current(base,base['lineage']);base['foreign_case']=g['case']
 f=ready(prefix,source_fixture=base);f['publication_rules']['review_ttl_seconds']=3600;finance_policy(f,PUBLICATION,f['publication_rules']);v=reviewed(f);f['version']=v;f['publication']=d.publish(f['acceptor'],f['case'].pk,v.pk);f['job']=f['publication'].job;f['sources']={'policy_decision':f['e']}
 f['readiness_rules']=dict(json.loads((settings.BASE_DIR/'fixtures/finance-publication-readiness.json').read_text(encoding='utf-8'))['rules'],probe_user_id=f['actor'].pk,probe_role='Finance',reviewer_id=f['recipient'].pk,reviewer_role='Finance',native_publication_job_ids=[f['job'].pk])
 f['contract_payload']={'kind':'adapter','family':'publication','implementation':'internal_postgres_session_v1','target_key':'internal:publication','credential_ref':'runtime:postgres','credential_revision':'fixture-v1','principal_ref':'principal:'+connection.settings_dict['USER'],'contract_version':'psl.internal-receipts/v1','model_id':None,'capabilities':['health','receipt_lookup'],'data_scope':'public_canary_and_scoped_receipt_metadata_only'}
 f['contract_evidence']=evidence(f,'integration_contract','Synthetic native publication contract');f['selection_evidence']=evidence(f,'integration_selection','Synthetic exact native enrollment');f['review_evidence']=evidence(f,'integration_review','Synthetic independent native transport capability review')
 return f

def capture(f,reference='native',job=None,predecessor=None):return r.capture(f['actor'],f['case'].pk,reference,f['contract_payload'],f['contract_evidence'].pk,predecessor=predecessor,native_publication_job=(job or f['job']).pk)
def configure(f):
 f['readiness_policy']=policy(f,ADAPTER,f['readiness_rules']);return f['readiness_policy']
def enrolled(f,ready=True):
 if 'contract' not in f:f['contract']=capture(f)
 configure(f);r.select(f['actor'],f['case'].pk,f['contract'].pk,f['selection_evidence'].pk)
 if ready:return assessed(f)
 return f['contract']
def probe(f,kind,key=None):
 j=w.reserve(f['actor'],f['case'].pk,f['contract'].pk,key or kind,kind,f['job'].pk if kind=='receipt' else None);w.run_once(case_id=f['case'].pk);j.refresh_from_db();assert j.status=='confirmed',j.status;return j

def assessed(f,key='ready'):
 probe(f,'health',key+'-health');probe(f,'receipt',key+'-receipt');v=r.assess(f['actor'],f['case'].pk,f['contract'].pk,key);r.review(f['recipient'],f['case'].pk,v.pk,'confirm',key,f['review_evidence'].pk);f['assessment']=v;return v

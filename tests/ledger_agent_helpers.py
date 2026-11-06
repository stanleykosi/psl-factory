import json
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
from apps.policy.ledger_validators import PROJECTION
from apps.policy.services import transition
from apps.policy.readiness_drafts import draft_readiness_policy
from apps.policy.readiness_validators import PROVIDER
from apps.policy.agent_data_validators import COMPONENT as DATA
from apps.finance import ledger_agents as d
from apps.workflows import readiness as rd,readiness_delivery as rw
from apps.agents import boundary as gateway,boundary_delivery as delivery
from .ledger_resolution_helpers import fixture as resolution_fixture
from .ledger_helpers import capture,verify,review,policy,evidence

def fixture(prefix='ledger-agent',configured=True):
 f=resolution_fixture(prefix);f['case'].tenant='synthetic-'+prefix;f['case'].save(update_fields=['tenant']);f['lineage']=capture(f);review(f,verify(f,f['lineage']))
 f['native_rules']=dict(json.loads((settings.BASE_DIR/'fixtures/ledger.json').read_text(encoding='utf-8'))['projection'],lineage_ids=[f['lineage'].pk],projector_id=f['actor'].pk,owner_id=f['actor'].pk,reviewer_id=f['reviewer'].pk)
 if configured:f['native_policy']=policy(f,PROJECTION,f['native_rules'])
 return f

def project(f,key='native'):
 r=d.project(f['actor'],f['case'].pk,f['lineage'].pk,key);f['binding']=r;f['projection']=r.projection;return r

def activate(f,key,value):
 p=draft_readiness_policy(f['actor'],f['case'].pk,key,value,f['e'].pk,timezone.now()-timedelta(seconds=1));transition(f['actor'],p.pk,'validated');transition(f['actor'],p.pk,'active');return p

def integration(f):
 rules=dict(json.loads((settings.BASE_DIR/'fixtures/integration-readiness.json').read_text(encoding='utf-8'))['rules'],probe_user_id=f['actor'].pk,probe_role='Finance',reviewer_id=f['reviewer'].pk,reviewer_role='Finance');activate(f,PROVIDER,rules)
 body={'kind':'provider','family':'provider','implementation':'authenticated_json_v1','target_key':'endpoint:fixture','credential_ref':'secret:fixture','credential_revision':'fixture-v1','principal_ref':'principal:fixture','contract_version':'fixture-model/v1','model_id':'fixture-model','capabilities':['health','receipt_lookup','evaluation'],'data_scope':'public_canary_and_scoped_receipt_metadata_only'}
 a,b,c=f['actor'],f['reviewer'],f['case'];contract=rd.capture(a,c.pk,'ledger-provider',body,evidence(f,'integration_contract','Explicit synthetic provider contract').pk)
 for kind in ['health','evaluation']:
  j=rw.reserve(a,c.pk,contract.pk,kind,kind);rw.run_once(case_id=c.pk);j.refresh_from_db();assert j.status=='confirmed'
 r=rd.assess(a,c.pk,contract.pk,'ready');rd.review(b,c.pk,r.pk,'confirm','ready',evidence(f,'integration_review','Synthetic independent capability review').pk);rd.select(a,c.pk,contract.pk,evidence(f,'integration_selection','Synthetic explicit provider selection').pk)
 data=dict(json.loads((settings.BASE_DIR/'fixtures/agent-data.json').read_text(encoding='utf-8'))['rules'],contract_id=contract.pk,evidence_ids=[f['projection'].evidence_id],process_ids=['F01'],purpose=f['native_rules']['purpose'],sender_id=a.pk,sender_role='Finance',reviewer_id=b.pk,reviewer_role='Finance')
 f['data_rules']=data;f['data_policy']=activate(f,DATA,data);return contract

def extracted(f):
 if 'projection' not in f:project(f)
 integration(f);gateway.review_projection(f['reviewer'],f['case'].pk,f['projection'].pk,'confirm');j=gateway.reserve(f['actor'],f['case'].pk,f['projection'].pk,'finance-extract');delivery.run_once(f['case'].pk);j.refresh_from_db();assert j.status=='confirmed',j.status
 r=gateway.Receipt.objects.get(job=j);gateway.review_result(f['reviewer'],f['case'].pk,r.pk,'confirm');f['receipt']=r;return r

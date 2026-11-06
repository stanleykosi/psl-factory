import json
from datetime import timedelta
from django.conf import settings
from django.utils import timezone
from apps.policy.services import transition
from apps.policy.readiness_drafts import draft_readiness_policy
from apps.policy.readiness_validators import PROVIDER
from apps.policy.agent_data_validators import COMPONENT as DATA
from apps.policy.support_agent_validators import COMPONENT
from apps.workflows import readiness as rd,readiness_delivery as rw
from apps.agents import boundary as gateway,boundary_delivery as delivery
from apps.baas import support_agent as domain
from apps.baas.support_models import SupportLink
from . import support_helpers as sf

def fixture(prefix='support-agent',configured=True,message_changes=None,owner_summary=False):
 f=sf.fixture(prefix);f['v']['message'].update(message_changes or {})
 if owner_summary:
  from apps.policy.support_validators import AUTH
  f['v']['authority']['assignments'][0]['purposes'].append('summary');sf.policy(f,AUTH,f['v']['authority'])
 sf.ready(f);f['sources']=f['e'];f['intake']=SupportLink.objects.get(case=f['case']).intake
 f['native_rules']=dict(json.loads((settings.BASE_DIR/'fixtures/support-agent.json').read_text(encoding='utf-8'))['rules'],intake_ids=[f['intake'].pk],projector_id=f['actor'].pk,owner_id=f['actor'].pk,reviewer_id=f['reviewer'].pk)
 if configured:f['native_policy']=sf.policy(f,COMPONENT,f['native_rules'])
 return f
def project(f,key='native'):
 r=domain.project(f['actor'],f['case'].pk,f['intake'].pk,key);f['binding']=r;f['projection']=r.projection;return r
def integration(f):
 a,c=f['actor'],f['case'];rules=dict(json.loads((settings.BASE_DIR/'fixtures/integration-readiness.json').read_text(encoding='utf-8'))['rules'],probe_user_id=a.pk,probe_role='Support',reviewer_id=f['reviewer'].pk,reviewer_role='Support')
 activate(f,PROVIDER,rules)
 body={'kind':'provider','family':'provider','implementation':'authenticated_json_v1','target_key':'endpoint:fixture','credential_ref':'secret:fixture','credential_revision':'fixture-v1','principal_ref':'principal:fixture','contract_version':'fixture-model/v1','model_id':'fixture-model','capabilities':['health','receipt_lookup','evaluation'],'data_scope':'public_canary_and_scoped_receipt_metadata_only'}
 contract=rd.capture(a,c.pk,'support-provider',body,sf.evidence(f,'integration_contract').pk)
 for kind in ['health','evaluation']:
  j=rw.reserve(a,c.pk,contract.pk,kind,kind);rw.run_once(case_id=c.pk);j.refresh_from_db();assert j.status=='confirmed'
 r=rd.assess(a,c.pk,contract.pk,'ready');rd.review(f['reviewer'],c.pk,r.pk,'confirm','ready',sf.evidence(f,'integration_review').pk);rd.select(a,c.pk,contract.pk,sf.evidence(f,'integration_selection').pk)
 data=dict(json.loads((settings.BASE_DIR/'fixtures/agent-data.json').read_text(encoding='utf-8'))['rules'],contract_id=contract.pk,evidence_ids=[f['projection'].evidence_id],process_ids=['B14'],purpose=f['native_rules']['purpose'],sender_id=a.pk,sender_role='Support',reviewer_id=f['reviewer'].pk,reviewer_role='Support')
 f['data_policy']=activate(f,DATA,data);return contract
def activate(f,component,content):
 p=draft_readiness_policy(f['actor'],f['case'].pk,component,content,f['e']['policy_decision'].pk,timezone.now()-timedelta(seconds=1));transition(f['actor'],p.pk,'validated');transition(f['actor'],p.pk,'active');return p
def extracted(f):
 if 'projection' not in f:project(f)
 integration(f);a,b,c=f['actor'],f['reviewer'],f['case'];gateway.review_projection(b,c.pk,f['projection'].pk,'confirm');j=gateway.reserve(a,c.pk,f['projection'].pk,'support-extract');delivery.run_once(c.pk);j.refresh_from_db();assert j.status=='confirmed';r=gateway.Receipt.objects.get(job=j);gateway.review_result(b,c.pk,r.pk,'confirm');f['receipt']=r;return r

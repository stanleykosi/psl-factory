import json,copy
from pathlib import Path
from datetime import timedelta
from django.utils import timezone
from apps.core.services import add_evidence
from apps.identity.models import Grant
from apps.policy.services import transition
from apps.policy.migration_drafts import draft_migration_policy
from apps.policy.migration_validators import COMPONENT,KINDS
from apps.documents import migration_readiness as d,validation as af
from apps.documents.contracts import digest
from .validation_helpers import fixture as af_fixture,review as af_review

def evidence(f,kind,body='Explicit synthetic migration evidence; not real owner acceptance or execution'):
 return add_evidence(f['actor'],f['case'].pk,kind,json.dumps(body) if isinstance(body,dict) else body,'synthetic:migration')
def policy(f,value=None):
 p=draft_migration_policy(f['actor'],f['case'].pk,COMPONENT,value or f['config_migration'],f['decision_evidence'].pk,timezone.now()-timedelta(seconds=1));transition(f['actor'],p.pk,'validated');transition(f['actor'],p.pk,'active');return p
def fixture(configured=True):
 f=af_fixture();a,c=f['actor'],f['case']
 for person in [f['owner'],f['acceptor']]:
  Grant.objects.bulk_create([Grant(case=c,user=person,action=x) for x in ['migration.read','migration.review','migration.bind','migration.evidence.read']],ignore_conflicts=True)
 payload=copy.deepcopy(f['package'].payload);payload['level']='operational';p=af.prepare_package(a,c.pk,'operational-readiness',payload,f['decision_evidence'].pk,None);f['package']=p;af_review(f);af_review(f,'expectations')
 rules=json.loads((Path(__file__).resolve().parent.parent/'fixtures/migration-readiness.json').read_text(encoding='utf-8'))['policy'];rules['assignments'][0]['user_id']=f['owner'].pk;rules['assignments'][1]['user_id']=f['acceptor'].pk;f['config_migration']=rules
 if configured:f['migration_policy']=policy(f)
 src=f['source'].evidence;rows=[{'id':src.pk,'kind':src.kind,'version':src.version,'sha256':src.sha256}]
 v={'process_ids':p.payload['process_ids'],'build_ref':p.payload['build_ref'],'source_system':'psl-evidence','source_ref':str(c.pk),'source_version':'evidence-manifest-v1','target_system':'synthetic-target','target_ref':'synthetic-target-1','target_version':'target-v1','expected_record_count':1,'expected_manifest_sha256':digest(rows),'evidence_ids':[src.pk]}
 f['plan_evidence']=evidence(f,'migration_plan');f['review_evidence']=evidence(f,'migration_review');f['plan']=d.capture_plan(a,c.pk,'migration-rehearsal',v,f['plan_evidence'].pk,p.pk);return f
def proof(f,kind='backup',changes=None):
 p=f['plan'];v={'plan_id':p.pk,'plan_sha256':p.sha256,**{k:p.payload[k] for k in ['build_ref','source_ref','target_ref','source_version','target_version']},'kind':kind,'system':'synthetic-migration','external_ref':str(f['case'].pk)+':'+kind,'receipt_version':'v1','recorded_at':(timezone.now()-timedelta(seconds=1)).isoformat(),'performed_by_ref':'synthetic-operator','outcome':'passed','evidence_class':'synthetic_report','record_count':p.payload['expected_record_count'],'manifest_sha256':p.payload['expected_manifest_sha256']};v.update(changes or {})
 return d.capture_proof(f['actor'],f['case'].pk,p.pk,evidence(f,'migration_proof',v).pk)
def assessed(f):
 for kind in KINDS:proof(f,kind)
 d.observe_inventory(f['actor'],f['case'].pk,f['plan'].pk);return d.assess(f['actor'],f['case'].pk,f['plan'].pk)
def review(f,r,purpose='owner',verdict='approve',key=None):
 a=f['owner'] if purpose=='owner' else f['acceptor'];return d.review(a,f['case'].pk,r.pk,purpose,verdict,key or purpose+'-'+verdict,f['review_evidence'].pk,'Exact synthetic documentary readiness; no execution or deployment authority')
def bound(f):
 r=assessed(f);review(f,r);review(f,r,'independent');b=d.bind(f['acceptor'],f['case'].pk,r.pk);return r,b

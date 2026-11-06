import json,copy
from pathlib import Path
from datetime import timedelta
from django.utils import timezone
from django.contrib.auth import get_user_model
from apps.core.services import add_evidence
from apps.identity.models import Grant
from apps.core.management.commands.seed_demo import ACTIONS
from apps.policy.services import register_reference,transition
from apps.policy.approval_drafts import draft_approval_policy
from apps.policy.approval_validators import ROUTES,CONTRACTS
from apps.pmo import approvals as d
from apps.pmo.gates import register_candidate
from .helpers import setup_case,activate,rev

def evidence(f,kind,body='Explicit synthetic prerequisite evidence; not real owner acceptance'):
 return add_evidence(f['actor'],f['case'].pk,kind,json.dumps(body) if isinstance(body,dict) else body,'synthetic:prerequisites')

def policy(f,key,value):
 p=draft_approval_policy(f['actor'],f['case'].pk,key,value,f['e']['policy_decision'].pk,timezone.now()-timedelta(seconds=1));transition(f['actor'],p.pk,'validated');transition(f['actor'],p.pk,'active');return p

def fixture(prefix='approval',configured=True):
 a,c=setup_case(username=prefix+'-coordinator');owner=get_user_model().objects.create_user(username=prefix+'-qa')
 Grant.objects.bulk_create([Grant(case=c,user=owner,action=x) for x in ACTIONS],ignore_conflicts=True)
 for p in [a,owner]:Grant.objects.create(case=c,user=p,action='approval.source.read:synthetic-qa')
 f={'actor':a,'owner':owner,'case':c,'e':{}}
 for kind in ['requirements','policy_decision','approval_request','approval_contract_review']:f['e'][kind]=evidence(f,kind)
 refs=[]
 for p,role in [(a,'PM'),(owner,'QA')]:refs.append(register_reference(a,c.pk,prefix+'-role:'+str(p.pk),'schema:psl/role-assignment/v1',{'role':role,'user_id':p.pk},f['e']['policy_decision'].pk).ref)
 activate(a,c,'D05.role_principal_assignments',refs,f['e']['policy_decision'])
 f['candidate']=register_candidate(a,c.pk,prefix+'-candidate',f['e']['requirements'].pk,rev(c))
 v=json.loads((Path(__file__).resolve().parent.parent/'fixtures/approval-routing.json').read_text(encoding='utf-8'));v['routes']['routes'][0]['owner_id']=owner.pk;v['contracts']['contracts'][0]['contract_evidence_id']=f['e']['policy_decision'].pk;f['v']=v
 if configured:
  policy(f,ROUTES,v['routes']);policy(f,CONTRACTS,v['contracts']);d.review_contract(owner,c.pk,'qa_exit',f['e']['approval_contract_review'].pk)
 f['request']=d.create_request(a,c.pk,prefix+'-qa',f['candidate'].pk,'qa_exit','BUILD-1','RELEASE-1',f['e']['approval_request'].pk)
 return f

def capture(f,changes=None):
 r=f['request'];body={'request_id':r.pk,'kind':r.kind,'subject':r.subject,'system':'synthetic-qa','source_owner':'QA Lead','source_actor_ref':'synthetic-qa-owner','external_ref':f['actor'].username+'-SOURCE','source_version':'v1','decision':'accepted','decided_at':(timezone.now()-timedelta(seconds=10)).isoformat(),'signature_ref':'signed-reference-only','critical_defects':0};body.update(changes or {})
 return d.capture(f['actor'],f['case'].pk,r.pk,evidence(f,'approval_source',body).pk)

def observe(f,s=None,outcome='available',changes=None,actor=None):
 s=s or capture(f);body={'receipt_id':s.pk,'system':s.system,'external_ref':s.external_ref,'source_version':s.source_version,'observed_at':timezone.now().isoformat(),'outcome':outcome,'payload_sha256':s.sha256 if outcome=='available' else None,'decision':s.payload['decision'] if outcome=='available' else None};body.update(changes or {})
 return d.observe(actor or f['owner'],f['case'].pk,s.pk,evidence(f,'approval_observation',body).pk)

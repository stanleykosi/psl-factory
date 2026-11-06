import json
from datetime import timedelta
from django.conf import settings
from django.utils import timezone
from apps.core.services import add_evidence
from apps.policy.readiness_drafts import draft_readiness_policy
from apps.policy.agent_data_validators import COMPONENT
from apps.policy.services import transition
from apps.workflows import readiness as readiness
from apps.agents import boundary as d
from .readiness_helpers import fixture,probe

def fixture_data(prefix='private',configured=True):
 f=fixture(prefix,kind='provider');a,c=f['actor'],f['case']
 f['input']=add_evidence(a,c.pk,'agent_private_input','Milestone evidence reviewed.\nDO NOT SEND THIS EXCLUDED PRIVATE NOTE.','synthetic:agent-data')
 f['projection']=d.project(a,c.pk,f['input'].pk,'P34','synthetic-progress-summary',['Milestone evidence reviewed.'])
 f['data_rules']=dict(json.loads((settings.BASE_DIR/'fixtures/agent-data.json').read_text(encoding='utf-8'))['rules'],contract_id=f['contract'].pk,evidence_ids=[f['input'].pk],sender_id=a.pk,reviewer_id=f['reviewer'].pk)
 if configured:data_policy(f)
 return f

def data_policy(f,value=None):
 p=draft_readiness_policy(f['actor'],f['case'].pk,COMPONENT,value or f['data_rules'],f['sources']['policy_decision'].pk,timezone.now()-timedelta(seconds=1));transition(f['actor'],p.pk,'validated');transition(f['actor'],p.pk,'active');f['data_policy']=p;return p

def ready_data(f):
 probe(f);probe(f,'evaluation');r=readiness.assess(f['actor'],f['case'].pk,f['contract'].pk,'private-ready');readiness.review(f['reviewer'],f['case'].pk,r.pk,'confirm','private-ready',f['review_evidence'].pk);readiness.select(f['actor'],f['case'].pk,f['contract'].pk,f['selection_evidence'].pk)
 d.review_projection(f['reviewer'],f['case'].pk,f['projection'].pk,'confirm')
 return d.reserve(f['actor'],f['case'].pk,f['projection'].pk,'extract-1')

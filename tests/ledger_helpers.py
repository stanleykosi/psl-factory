import json,copy
from pathlib import Path
from datetime import timedelta
from django.utils import timezone
from django.contrib.auth import get_user_model
from apps.core.services import add_evidence
from apps.identity.models import Grant
from apps.policy.services import register_reference,transition
from apps.policy.ledger_drafts import draft_ledger_policy
from apps.policy.ledger_validators import RULES,AUTH
from apps.finance import ledger
from apps.core.management.commands.seed_demo import ACTIONS
from .helpers import setup_case,activate,rev

def evidence(f,kind,body):return add_evidence(f['actor'],f['case'].pk,kind,json.dumps(body) if isinstance(body,dict) else body,'synthetic:ledger')
def policy(f,key,value):
 p=draft_ledger_policy(f['actor'],f['case'].pk,key,value,f['e'].pk,timezone.now()-timedelta(seconds=1));transition(f['actor'],p.pk,'validated');transition(f['actor'],p.pk,'active');return p

def fixture(username='ledger-human',reviewer_username='ledger-reviewer'):
 a,c=setup_case(username=username);b=get_user_model().objects.create_user(username=reviewer_username)
 for action in ACTIONS:Grant.objects.create(case=c,user=b,action=action)
 f={'actor':a,'case':c,'reviewer':b};f['e']=evidence(f,'policy_decision','Synthetic reviewed treatment and incumbent identity evidence')
 r=register_reference(a,c.pk,'ledger-finance-role','schema:psl/role-assignment/v1',{'role':'Finance','user_id':b.pk},f['e'].pk)
 activate(a,c,'D05.role_principal_assignments',[r.ref],f['e'])
 v=json.loads((Path(__file__).resolve().parent.parent/'fixtures/ledger.json').read_text(encoding='utf-8'));v['source'].update(treatment_evidence_id=f['e'].pk,posting_evidence_id=f['e'].pk);v['rules']['treatment_evidence_ids']=[f['e'].pk];v['authority']['user_ids']=[b.pk];f['v']=v
 f['rule_policy']=policy(f,RULES,v['rules']);f['auth_policy']=policy(f,AUTH,v['authority']);return f

def capture(f,body=None,predecessor=None):
 e=evidence(f,'ledger_source',body or f['v']['source']);return ledger.capture(f['actor'],f['case'].pk,e.pk,predecessor,rev(f['case']))
def verify(f,w,changes=None):
 p=w.payload;r={k:p[k] for k in ['provider','realm','entity','source_reference','target_reference','transaction_date','accounting_period','treatment_evidence_id']};r.update(state='found',observed_at=(timezone.now()-timedelta(seconds=1)).isoformat(),incumbent_version='sync-1');r.update(changes or {});e=evidence(f,'quickbooks_verification',r);return ledger.verify(f['actor'],f['case'].pk,w.pk,e.pk,rev(f['case']))
def review(f,x,verdict='approve'):return ledger.review(f['reviewer'],f['case'].pk,x.pk,f['e'].pk,verdict,rev(f['case']))

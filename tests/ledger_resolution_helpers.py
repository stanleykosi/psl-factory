import json
from django.conf import settings
from django.utils import timezone
from apps.finance import ledger,ledger_resolution as d
from apps.policy.ledger_validators import RESOLUTION
from apps.policy.services import register_reference
from apps.identity.models import Grant
from .helpers import activate
from .ledger_helpers import fixture as old_fixture,evidence,policy,capture,verify,review

def fixture(prefix='ledger-resolution',configured=True):
 f=old_fixture(prefix+'-preparer',prefix+'-reviewer')
 ref=register_reference(f['actor'],f['case'].pk,'resolution-proposer-role','schema:psl/role-assignment/v1',{'role':'Finance','user_id':f['actor'].pk},f['e'].pk)
 reviewer=register_reference(f['actor'],f['case'].pk,'resolution-reviewer-role','schema:psl/role-assignment/v1',{'role':'Finance','user_id':f['reviewer'].pk},f['e'].pk)
 activate(f['actor'],f['case'],'D05.role_principal_assignments',[ref.ref,reviewer.ref],f['e'])
 f['conflicts']=dict(json.loads((settings.BASE_DIR/'fixtures/ledger.json').read_text(encoding='utf-8'))['conflicts'],proposer_id=f['actor'].pk,reviewer_id=f['reviewer'].pk)
 f['resolution_evidence']=evidence(f,'ledger_resolution','Synthetic scoped claim-disposition reason; no posting authority')
 f['resolution_review_evidence']=evidence(f,'ledger_resolution_review','Synthetic independent Finance read-evidence review')
 if configured:f['resolution_policy']=policy(f,RESOLUTION,f['conflicts'])
 return f

def aliases(f):
 a=capture(f);b=capture(f);verify(f,a);verify(f,b);return a,b

def propose(f,selected,retired,members=None,mode='duplicate_alias',reference='resolution',predecessor=None):
 return d.propose(f['actor'],f['case'].pk,selected.pk,[w.pk for w in retired],[w.pk for w in (members or [selected,*retired])],mode,reference,predecessor,f['resolution_evidence'].pk,'Synthetic human claim adjudication')

def confirm(f,r,verdict='confirm'):
 return d.review(f['reviewer'],f['case'].pk,r.pk,verdict,f['resolution_review_evidence'].pk)

def fresh(f,w,changes=None):return verify(f,w,dict({'observed_at':timezone.now().isoformat()},**(changes or {})))

def current(f,w):
 x=fresh(f,w);review(f,x);return ledger.report(f['actor'],f['case'].pk,w.pk)

def second_case(f,cross=True):
 g=old_fixture('resolution-other-preparer','resolution-other-reviewer');a,b=f['actor'],f['reviewer']
 for person in [a,b]:
  from apps.core.management.commands.seed_demo import ACTIONS
  Grant.objects.bulk_create([Grant(case=g['case'],user=person,action=k) for k in ACTIONS],ignore_conflicts=True)
 refs=[]
 for person in [a,b,g['reviewer']]:refs.append(register_reference(g['actor'],g['case'].pk,'shared-role:'+str(person.pk),'schema:psl/role-assignment/v1',{'role':'Finance','user_id':person.pk},g['e'].pk).ref)
 activate(g['actor'],g['case'],'D05.role_principal_assignments',refs,g['e'])
 # Same treatment text, independent per-case evidence IDs.
 v=dict(f['conflicts'],allow_cross_case=cross);policy(f,RESOLUTION,v);policy(g,RESOLUTION,v)
 return g

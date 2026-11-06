import json
from django.conf import settings
from django.contrib.auth import get_user_model
from apps.identity.models import Grant
from apps.core.management.commands.seed_demo import ACTIONS
from apps.policy.services import register_reference
from apps.policy.ledger_validators import HANDOFF
from apps.policy.validation_validators import OWNER,ACCEPTANCE
from apps.documents import validation as af13
from apps.finance import ledger_agents as finance,acceptance as d
from .helpers import activate,rev
from .ledger_helpers import evidence,policy,verify,review
from .ledger_agent_helpers import fixture as ledger_fixture,extracted
from .validation_helpers import policy as validation_policy

def fixture(prefix='finance-acceptance',configured=True):
 f=ledger_fixture(prefix);a,c=f['actor'],f['case'];f['recipient']=f['reviewer'];f['acceptor']=get_user_model().objects.create_user(username=prefix+'-acceptor');Grant.objects.bulk_create([Grant(case=c,user=f['acceptor'],action=x) for x in ACTIONS])
 refs=[]
 for who in [a,f['recipient'],f['acceptor']]:refs.append(register_reference(a,c.pk,'acceptance-role:'+str(who.pk),'schema:psl/role-assignment/v1',{'role':'Finance','user_id':who.pk},f['e'].pk).ref)
 activate(a,c,'D05.role_principal_assignments',refs,f['e']);review(f,verify(f,f['lineage']))
 owner={'human_only':True,'assignments':[{'user_id':f['recipient'].pk,'role':'Finance','process_ids':['F01'],'purposes':['meaning','expectations']},{'user_id':f['acceptor'].pk,'role':'Finance','process_ids':['F01'],'purposes':['acceptance']}],'allow_preparer_review':False}
 f['owner_rules']=owner;validation_policy(a,c,OWNER,owner,f['e']);f['acceptance_rules']={'allowed_levels':['definition','synthetic_implementation'],'independent_tester':True,'independent_acceptor':True};validation_policy(a,c,ACCEPTANCE,f['acceptance_rules'],f['e'])
 body='Synthetic Finance source description; no real owner acceptance or native QuickBooks verification.'
 metadata={'document_kind':'other','source_version':'fixture-v1','source_date':None,'owner_label':None,'classification':'source_description','process_ids':['F01'],'clauses':[{'key':'finance-evidence','quote':body,'locator':'synthetic:fixture','classification':'source_description','process_ids':['F01']}]}
 source=af13.capture_source(a,c.pk,'finance-description',evidence(f,'procedure_source',body).pk,metadata,rev(c));examples=[]
 for kind,value in [('normal',{'read_only':True}),('exception',{'native_authenticity':'unknown'})]:examples.append(af13.capture_example(a,c.pk,kind,['F01'],kind,value,f['e'].pk,rev(c)))
 payload={'process_ids':['F01'],'source_ids':[source.pk],'example_ids':[x.pk for x in examples],'policy_components':[],'level':'definition','purpose':'P15','gaps':[],'build_ref':'fixture-v1','role_list':[],'manual_fallback':'','rollout_plan':'','migration_plan':'','support_owner_id':None}
 f['package']=af13.prepare_package(a,c.pk,'finance-validation',payload,f['e'].pk,rev(c));f['routing']=dict(json.loads((settings.BASE_DIR/'fixtures/finance-acceptance.json').read_text(encoding='utf-8'))['rules'],package_ids=[f['package'].pk],recipient_id=f['recipient'].pk,acceptor_id=f['acceptor'].pk)
 if configured:f['handoff_policy']=policy(f,HANDOFF,f['routing'])
 return f

def draft(f):
 receipt=extracted(f);r=finance.reuse(f['actor'],f['case'].pk,receipt.pk,'for-owner-validation');finance.review(f['reviewer'],f['case'].pk,r.pk,'approve');f['draft']=r;return r

def handoff(f):
 if 'draft' not in f:draft(f)
 h=d.prepare(f['actor'],f['case'].pk,f['draft'].pk,f['package'].pk,'owner-evidence');f['handoff']=h;return h

def decide(f,phase,verdict='confirm',key=None):
 return d.decide(f['acceptor'] if phase=='accept' else f['recipient'],f['case'].pk,f['handoff'].pk,phase,verdict,key or phase+'-'+verdict,'Synthetic explicit human '+phase+' '+verdict)

def validate(f):
 if 'handoff' not in f:handoff(f)
 decide(f,'receive');return decide(f,'validate')

def af13_reviews(f):
 rows=[]
 for kind in ['meaning','expectations','acceptance']:
  actor=f['acceptor'] if kind=='acceptance' else f['recipient'];rows.append(af13.review(actor,f['case'].pk,f['package'].pk,kind,'approve','af13-'+kind,f['e'].pk,'Separate explicit synthetic AF13 '+kind,None))
 f['af13_reviews']=rows;return rows

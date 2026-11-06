import json,copy
from pathlib import Path
from datetime import timedelta
from django.utils import timezone
from django.contrib.auth import get_user_model
from apps.core.services import add_evidence
from apps.identity.models import Grant
from apps.core.management.commands.seed_demo import ACTIONS
from apps.policy.services import register_reference,transition
from apps.policy.schedule_drafts import draft_schedule_policy
from apps.policy.schedule_validators import INCOME,INVENTORY,AUTH
from apps.finance import analysis,schedules
from apps.finance.services import capture_import,validate_import
from .finance_analysis_helpers import fixture as finance_fixture
from .helpers import activate,rev

def values():return json.loads((Path(__file__).resolve().parent.parent/'fixtures/schedules.json').read_text(encoding='utf-8'))
def policy(f,key,value):
 a,c=f['actor'],f['case'];p=draft_schedule_policy(a,c.pk,key,value,f['e']['policy_decision'].pk,timezone.now()-timedelta(seconds=1));transition(a,p.pk,'validated');transition(a,p.pk,'active');return p
def evidence(f,kind,body='Synthetic schedule evidence'):
 return add_evidence(f['actor'],f['case'].pk,kind,body,'synthetic:schedules')
def fixture(username='human',reviewer_username='schedule-reviewer',recipient_username='finance-reader'):
 a,c,e,base,configs,source,t,recipient=finance_fixture(username=username,recipient_username=recipient_username);reviewer=get_user_model().objects.create_user(username=reviewer_username)
 for action in ACTIONS:Grant.objects.create(case=c,user=reviewer,action=action)
 role=register_reference(a,c.pk,'schedule-reviewer-role','schema:psl/role-assignment/v1',{'role':'Finance','user_id':reviewer.pk},e['policy_decision'].pk)
 activate(a,c,'D05.role_principal_assignments',['finance:human',role.ref],e['policy_decision'])
 analysis.review(a,c.pk,'source',source.pk,'Finance','approve',e['finance_review'].pk,'Current source after explicit reviewer appointment',rev(c))
 for key,purpose in analysis.PURPOSE.items():analysis.review(a,c.pk,purpose,configs[key].pk,'Finance','approve',e['finance_review'].pk,'Current exact rule review',rev(c))
 f={'actor':a,'case':c,'reviewer':reviewer,'recipient':recipient,'e':e,'source':source,'base':base,'configs':configs,'values':values()}
 f['values']['authority']['assignments'][0]['user_id']=reviewer.pk
 for key,name in [(INCOME,'income_rule'),(INVENTORY,'inventory_rule'),(AUTH,'authority')]:policy(f,key,f['values'][name])
 f['parent']=analysis.map_source(a,c.pk,source.pk,[],rev(c));f['e']['income_detail']=evidence(f,'income_detail')
 return f
def parent_amount(f,amount):
 a,c=f['actor'],f['case'];raw=f['base']['csv'].replace('sales,-1000,','sales,'+amount+',')
 from apps.finance.rules import number,decimal
 e=evidence(f,'financial_input',raw);batch=capture_import(a,c.pk,e.pk,rev(c));validate_import(a,c.pk,batch.pk,rev(c))
 s=analysis.capture_source(a,c.pk,batch.pk,'synthetic-company','accrual',timezone.now()-timedelta(minutes=1),'complete',number(decimal(amount)+decimal('890.01')),f['e']['finance_source'].pk,rev(c))
 analysis.review(a,c.pk,'source',s.pk,'Finance','approve',f['e']['finance_review'].pk,'Synthetic changed note source',rev(c));f['source']=s;f['parent']=analysis.map_source(a,c.pk,s.pk,[],rev(c));return f['parent']
def row(f,key,amount,relationship='disaggregation',accounts=None,lines=None):
 return {'key':key,'relationship':relationship,'amount':amount,'unit':f['values']['income_rule']['target_unit'],'source_accounts':accounts or [],'evidence_id':f['e']['income_detail'].pk,'duplicate_state':'already_represented' if relationship=='disaggregation' else 'separately_justified','duplicate_resolution_evidence_id':None,'adjustment_lines':lines or []}
def detail(f,rows=None,reference='income'):
 p=copy.deepcopy(f['values']['detail']);p['target_unit']=f['values']['income_rule']['target_unit']
 p['rows']=rows if rows is not None else [row(f,'a','-600'),row(f,'b','-400')]
 return schedules.prepare(f['actor'],f['case'].pk,'income',reference,f['parent'].pk,p,f['e']['income_detail'].pk,rev(f['case']))
def review(f,w,verdict='approve'):
 return schedules.review(f['reviewer'],f['case'].pk,w.pk,verdict,f['e']['finance_review'].pk,'Actual scoped synthetic human review',rev(f['case']))
def inventory(f,body=None,reference='inventory'):
 body=copy.deepcopy(body if body is not None else f['values']['inventory']);e=evidence(f,'schedule_inventory',json.dumps(body))
 return schedules.prepare(f['actor'],f['case'].pk,'inventory',reference,None,None,e.pk,rev(f['case']))
def accepted_equity(f):
 from apps.policy.validation_drafts import draft_validation_policy
 from apps.policy.validation_validators import OWNER,ACCEPTANCE
 from apps.documents import validation as v
 a,c=f['actor'],f['case'];e=f['e']['policy_decision'];owner=a;acceptor=f['reviewer']
 configs={OWNER:{'human_only':True,'allow_preparer_review':True,'assignments':[{'user_id':owner.pk,'role':'Finance','process_ids':['F13'],'purposes':['meaning','expectations']},{'user_id':acceptor.pk,'role':'Finance','process_ids':['F13'],'purposes':['acceptance']}]},ACCEPTANCE:{'allowed_levels':['definition'],'independent_tester':True,'independent_acceptor':True}}
 for key,value in configs.items():
  p=draft_validation_policy(a,c.pk,key,value,e.pk,timezone.now()-timedelta(seconds=1));transition(a,p.pk,'validated');transition(a,p.pk,'active')
 workbook=evidence(f,'schedule_workbook','EXPLICIT SYNTHETIC equity definition: opening plus movement equals closing. F09 linkage; no native workbook execution.')
 metadata={'document_kind':'other','source_version':'synthetic-1','source_date':None,'owner_label':'Synthetic Finance owner','classification':'proposed_design','process_ids':['F13'],'clauses':[]}
 source=v.capture_source(a,c.pk,'equity-definition',workbook.pk,metadata,rev(c));examples=[]
 for scenario,expected in [('normal',{'opening':'100','movement':'20','closing':'120','consumer':'F09'}),('exception',{'mixed_period':'hold'})]:
  x=evidence(f,'validation_example','Synthetic '+scenario);examples.append(v.capture_example(a,c.pk,'equity-'+scenario,['F13'],scenario,expected,x.pk,rev(c)))
 payload={'process_ids':['F13'],'source_ids':[source.pk],'example_ids':[x.pk for x in examples],'policy_components':[],'level':'definition','purpose':'P15','gaps':[],'build_ref':'','role_list':[],'manual_fallback':'','rollout_plan':'','migration_plan':'','support_owner_id':None}
 p=v.prepare_package(a,c.pk,'equity',payload,e.pk,rev(c))
 for kind,actor in [('meaning',owner),('expectations',owner),('acceptance',acceptor)]:v.review(actor,c.pk,p.pk,kind,'approve','equity-'+kind,e.pk,'Synthetic exact definition review',rev(c))
 body=copy.deepcopy(f['values']['inventory']);body['workbook_evidence_id']=workbook.pk;body['schedules'][0].update(owner_id=owner.pk,source_evidence_ids=[workbook.pk],formula_evidence_ids=[workbook.pk],validation_package_id=p.pk,gaps=[])
 f.update(package=p,workbook=workbook,discovery_source=source)
 return body

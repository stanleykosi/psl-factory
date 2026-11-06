import copy,json
from pathlib import Path
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.utils import timezone
from apps.identity.models import Grant
from apps.core.management.commands.seed_demo import ACTIONS
from apps.policy.services import register_reference,transition
from apps.policy.d03_drafts import draft_d03_policy
from apps.policy.d03_validators import STATEMENT,CONTROLS
from apps.finance import billing_evidence as d
from .settlement_helpers import fixture as settlement_fixture,draft,approve
from .billing_helpers import evidence as bill_ev
from .helpers import activate
def evidence(f,kind,body='Explicit synthetic D03 evidence; not real source/owner acceptance'):
 return bill_ev(f['actor'],f['case'],kind,json.dumps(body) if isinstance(body,dict) else body)
def policy(f,key,value):
 p=draft_d03_policy(f['actor'],f['case'].pk,key,value,f['policy_evidence'].pk,timezone.now()-timedelta(seconds=1));transition(f['actor'],p.pk,'validated');transition(f['actor'],p.pk,'active');return p
def source(f,kind,reference=None,changes=None,predecessor=None):
 v=f['v'];quote=v['statement_quote'] if kind=='statement' else v['flow_quote'];payload={'implementation':None if kind=='statement' else 'internal_invoice_register_v1','effect_requirements':None if kind=='statement' else {effect:[{'key':v['control_key'],'evidence_kind':v['control_evidence_kind']}] for effect in ['issue','deliver']},'kind':kind,'system':'synthetic-billing-system','external_ref':str(f['case'].pk)+':'+kind,'source_version':'v1','source_kind':'written_owner_confirmation' if kind=='statement' else 'supplied_flow_contract','locator':'explicit-synthetic-fixture','quote':quote,'reported_at':(timezone.now()-timedelta(seconds=1)).isoformat(),'flow_ref':None if kind=='statement' else v['flow_ref'],'flow_version':None if kind=='statement' else v['flow_version'],'environment_ref':None if kind=='statement' else v['environment_ref']};payload.update(changes or {})
 return d.capture_source(f['actor'],f['case'].pk,reference or kind,payload,evidence(f,'d03_source',payload['quote']).pk,predecessor=predecessor)
def confirm(f,s,meaning=None,verdict='confirm',key=None):
 return d.review_source(f['owner'],f['case'].pk,s.pk,verdict,meaning or ('prices' if s.kind=='statement' else 'flow_contract'),key or verdict+'-'+str(s.pk),f['review_evidence'].pk)
def fixture(configured=True,enrolled=True):
 a,c,cov,prep,e=settlement_fixture();b=get_user_model().objects.create_user(username='d03-finance-source-owner')
 Grant.objects.bulk_create([Grant(case=c,user=b,action=x) for x in ACTIONS],ignore_conflicts=True)
 decision=bill_ev(a,c,'policy_decision','Explicit synthetic D03 principal/configuration evidence');refs=[]
 for user in [a,b]:refs.append(register_reference(a,c.pk,'d03-finance:'+str(user.pk),'schema:psl/role-assignment/v1',{'role':'Finance','user_id':user.pk},decision.pk).ref)
 activate(a,c,'D05.role_principal_assignments',refs,decision)
 f={'actor':a,'owner':b,'case':c,'coverage':cov,'preparation':prep,'settlement_e':e,'policy_evidence':decision,'v':json.loads((Path(__file__).resolve().parent.parent/'fixtures/billing-evidence.json').read_text(encoding='utf-8'))}
 f['review_evidence']=evidence(f,'d03_review');f['enrollment_evidence']=evidence(f,'d03_enrollment');f['statement']=source(f,'statement');f['flow']=source(f,'flow_contract');f['statement_review']=confirm(f,f['statement']);f['flow_review']=confirm(f,f['flow'])
 f['statement_policy']={'source_id':f['statement'].pk,'source_sha256':f['statement'].sha256,'review_id':f['statement_review'].pk};f['control_policies']=[]
 for effect in ['issue','deliver']:
  f['control_policies'].append({'source_id':f['flow'].pk,'source_sha256':f['flow'].sha256,'review_id':f['flow_review'].pk,'coverage_id':cov.pk,'effect':effect,'implementation':'internal_invoice_register_v1','flow_ref':f['v']['flow_ref'],'flow_version':f['v']['flow_version'],'environment_ref':f['v']['environment_ref'],'max_age_seconds':f['v']['freshness_seconds'],'requirements':[{'key':f['v']['control_key'],'evidence_kind':f['v']['control_evidence_kind']}]})
 if configured:f['policies']=[policy(f,STATEMENT,f['statement_policy']),policy(f,CONTROLS,f['control_policies'])]
 if enrolled:d.enroll(a,c.pk,cov.pk,f['enrollment_evidence'].pk)
 f['invoice']=draft(a,c,prep);approve(a,c,f['invoice'],e);return f
def observe(f,effect='issue',changes=None,actor=None):
 i=f['invoice'];v=f['v'];payload={'invoice_id':i.pk,'invoice_sha256':i.sha256,'preparation_key':i.preparation.operation_key,'effect':effect,'control_key':v['control_key'],'system':'synthetic-billing-system','external_ref':str(f['case'].pk)+':'+effect,'source_version':'v1','flow_ref':v['flow_ref'],'flow_version':v['flow_version'],'environment_ref':v['environment_ref'],'observed_at':timezone.now().isoformat(),'outcome':'passed','evidence_class':'synthetic_reference'};payload.update(changes or {})
 return d.observe_control(actor or f['owner'],f['case'].pk,i.pk,evidence(f,v['control_evidence_kind'],payload).pk)
def bound(f,effect='issue'):
 observe(f,effect);r=d.assess(f['actor'],f['case'].pk,f['invoice'].pk,effect);b=d.bind(f['owner'],f['case'].pk,r.pk);return r,b

def corrected_contract(f,implementation='internal_invoice_register_v1',requirements=None):
 changes={'source_version':'v2','implementation':implementation}
 if requirements is not None:changes['effect_requirements']={e:requirements for e in ['issue','deliver']}
 s=source(f,'flow_contract',changes=changes,predecessor=f['flow'].pk);r=confirm(f,s)
 rules=copy.deepcopy(f['control_policies'])
 for row in rules:
  row.update(source_id=s.pk,source_sha256=s.sha256,review_id=r.pk,implementation=implementation)
  if requirements is not None:row['requirements']=requirements
 policy(f,CONTROLS,rules);return rules

import copy,json
from pathlib import Path
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.utils import timezone
from apps.identity.actions import ACTIONS
from apps.identity.models import Grant
from apps.core.services import add_evidence
from apps.policy.services import register_reference,transition
from apps.policy.operator_drafts import draft_operator_policy
from apps.policy.approval_drafts import draft_approval_policy
from apps.policy.approval_validators import ROUTES,CONTRACTS
from apps.policy.planning_validators import COMPONENT
from apps.pmo import engagement,planning,approvals
from apps.pmo.meetings import record_meeting
from apps.pmo.models import ApprovalRequest
from tests.helpers import setup_case,prepared,activate,rev

def evidence(f,kind,body):return add_evidence(f['a'],f['c'].pk,kind,json.dumps(body) if isinstance(body,dict) else body,'synthetic:planning')

def criteria(f,values=None):
    p=draft_operator_policy(f['a'],f['c'].pk,COMPONENT,values or f['rules'],f['e']['policy_decision'].pk,timezone.now())
    transition(f['a'],p.pk,'validated');transition(f['a'],p.pk,'active');return p

def fixture(configured=True,username='planning-human',owner_password=None):
    a,c=setup_case(username=username);e=prepared(a,c)
    f={'a':a,'c':c,'e':e,'owners':{},'routes':{},'meetings':{}}
    refs=list(c.registeredreference_set.filter(schema_ref='schema:psl/role-assignment/v1').values_list('ref',flat=True))
    for key,role in planning.OWNER_ROLES.items():
        person=get_user_model().objects.create_user(username=username+'-'+key,password=owner_password)
        Grant.objects.bulk_create([Grant(case=c,user=person,action=x) for x in ACTIONS]);Grant.objects.create(case=c,user=person,action='approval.source.read:synthetic-planning-'+key)
        Grant.objects.create(case=c,user=a,action='approval.source.read:synthetic-planning-'+key)
        f['owners'][key]=person
        refs.append(register_reference(a,c.pk,'planning-role:'+key,'schema:psl/role-assignment/v1',{'role':role,'user_id':person.pk},e['policy_decision'].pk).ref)
    activate(a,c,'D05.role_principal_assignments',refs,e['policy_decision'])
    source=evidence(f,'engagement_source','Actual synthetic direct engagement source')
    engagement.capture(a,c.pk,'B',source.pk,'direct-planning','capture-planning')
    values=json.loads(Path('fixtures/planning-packet.json').read_text(encoding='utf-8'))
    f['payload']=values['capture'];f['rules']=values['criteria']
    f['payload'].update(prd_id=e['requirements'].pk,scope_id=e['plan'].pk,engineering_estimate_id=e['engineering_estimate'].pk,security_estimate_id=e['security_estimate'].pk)
    f['payload']['source_correlations']=[{'key':field,'source_field':field,'source_id':f['payload'][field],
        'document_version':'synthetic-declared-v1','target_prd_id':e['requirements'].pk,'target_scope_id':e['plan'].pk,
        'evidence_id':e[field.removesuffix('_id') if field!='scope_id' else 'plan'].pk,
        'state':'current','detail':'Explicit synthetic source-backed target declaration; not inferred from timestamps.','resolution_id':None}
        for field in ['scope_id','engineering_estimate_id','security_estimate_id']]
    f['packet']=planning.capture(a,c.pk,f['payload'])
    for offset,purpose in enumerate(planning.PURPOSES):
        m=record_meeting(a,c.pk,'ALIGN-'+str(offset),'alignment',timezone.now()-timedelta(minutes=2-offset),purpose,'Actual full PRD or scope/estimate alignment source',[a.pk],[],e['requirements'].pk,rev(c))
        f['meetings'][purpose]=m;planning.align(a,c.pk,f['packet'].pk,purpose,m.pk)
    f['pair']=planning.open_requests(a,c.pk,f['packet'].pk)
    if configured:
        setup_departments(f);criteria(f)
    return f

def setup_departments(f):
    example=json.loads(Path('fixtures/approval-routing.json').read_text(encoding='utf-8'));routes=example['routes'];contracts=example['contracts']
    route=routes['routes'][0];contract=contracts['contracts'][0];routes['routes']=[];contracts['contracts']=[]
    for key,kind in planning.SUBJECTS.items():
        r=copy.deepcopy(route);r.update(kind=kind,gate_kind=None,source_owner=planning.OWNER_ROLES[key],owner_id=f['owners'][key].pk,owner_role=planning.OWNER_ROLES[key],source_actor_ref='synthetic-'+key,system='synthetic-planning-'+key)
        s=copy.deepcopy(contract);s.update(kind=kind,contract_evidence_id=f['e']['policy_decision'].pk,required_subject_fields=[])
        routes['routes'].append(r);contracts['contracts'].append(s);f['routes'][key]=r
    for component,values in [(ROUTES,routes),(CONTRACTS,contracts)]:
        p=draft_approval_policy(f['a'],f['c'].pk,component,values,f['e']['policy_decision'].pk,timezone.now());transition(f['a'],p.pk,'validated');transition(f['a'],p.pk,'active')
    for key,kind in planning.SUBJECTS.items():
        source=evidence(f,'approval_contract_review','Department source-contract acceptance only')
        approvals.review_contract(f['owners'][key],f['c'].pk,kind,source.pk)

def observe(f):
    for key,pk in f['pair']['requests'].items():
        receipt,proof=supplied_observation(f,key)
        approvals.observe(f['owners'][key],f['c'].pk,receipt.pk,proof.pk)

def supplied_observation(f,key):
    r=ApprovalRequest.objects.get(pk=f['pair']['requests'][key]);route=f['routes'][key]
    body={'request_id':r.pk,'kind':r.kind,'subject':r.subject,'system':route['system'],'source_owner':route['source_owner'],'source_actor_ref':route['source_actor_ref'],
        'external_ref':'SYN-PLANNING-'+str(r.pk),'source_version':'v1','decision':'accepted','decided_at':timezone.now().isoformat(),'signature_ref':'synthetic-owner-signature-reference','critical_defects':None}
    receipt=approvals.capture(f['a'],f['c'].pk,r.pk,evidence(f,'approval_source',body).pk)
    value={'receipt_id':receipt.pk,'system':receipt.system,'external_ref':receipt.external_ref,'source_version':receipt.source_version,'observed_at':timezone.now().isoformat(),
        'outcome':'available','payload_sha256':receipt.sha256,'decision':'accepted'}
    return receipt,evidence(f,'approval_observation',value)

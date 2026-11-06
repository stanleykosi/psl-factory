import hashlib
import json
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.utils import timezone
from apps.core.models import Case
from apps.core.services import add_evidence
from apps.identity.models import Grant
from apps.policy.models import RegisteredReference
from apps.policy.registry import components
from apps.policy.services import save_draft, transition
from apps.core.management.commands.seed_demo import ACTIONS


def setup_case(kind='project', synthetic=True, username='human',case_id=None):
    actor = get_user_model().objects.create_user(username=username, password='test-only-password')
    case = Case.objects.create(**({'id':case_id} if case_id else {}),tenant='test-tenant',title='Test engagement',kind=kind,synthetic=synthetic)
    for action in ACTIONS:
        Grant.objects.create(user=actor,case=case,action=action)
    return actor,case


def envelope(case, component, value, evidence):
    return {'slot_id': components()[component]['parent_decision_id'], 'component_id':component,
        'component_schema_ref':components()[component]['schema_ref'], 'schema_version':'1',
        'subject_scope':{'kind':'project' if case.kind=='project' else 'service','ref':str(case.pk)},
        'policy_revision':1,'lifecycle':'draft','effective_from':(timezone.now()-timedelta(days=1)).isoformat(),
        'effective_until':None,'evidence_refs':[f'evidence:{evidence.pk}'],'human_decision_ref':f'evidence:{evidence.pk}',
        'implementation_id':'psl.reference-validation','implementation_version':'1',
        'reviewed_implementation_ref':'code:apps/policy/services.py#reference-validation-v1',
        'value':value,'fixture_scope':'synthetic_test' if case.synthetic else 'operational'}


def activate(actor,case,component,value,evidence):
    config=save_draft(actor,case.pk,envelope(case,component,value,evidence))
    transition(actor,config.pk,'validated'); transition(actor,config.pk,'active')
    return config


def roles(actor,case,evidence):
    refs=[]
    for i,role in enumerate(['PM','Head of PMO','CEO','PMO Lead']):
        content={'role':role,'user_id':actor.pk}
        ref=f'role:{i}'
        RegisteredReference.objects.create(case=case,ref=ref,schema_ref='schema:psl/role-assignment/v1',
            content=content,sha256=hashlib.sha256(json.dumps(content,sort_keys=True,separators=(',',':')).encode()).hexdigest(),evidence=evidence)
        refs.append(ref)
    return activate(actor,case,'D05.role_principal_assignments',refs,evidence)


def project_evidence(actor,case):
    return {k:add_evidence(actor,case.pk,k,f'Example {k} content','synthetic:test') for k in
        ['requirements','engineering_estimate','security_estimate','plan','costing','sow','signature','completion','policy_decision']}


def rev(case):
    case.refresh_from_db(); return case.revision


def prepared(actor,case):
    from apps.pmo.services import prepare_baseline
    e=project_evidence(actor,case)
    roles(actor,case,e['policy_decision'])
    prepare_baseline(actor,case.pk,e['plan'].pk,e['costing'].pk,e['sow'].pk,rev(case))
    return e


def signed(actor,case):
    from apps.pmo.services import decide, sign_baseline
    e=prepared(actor,case)
    for role in ['PM','Head of PMO','CEO','PMO Lead']:
        decide(actor,case.pk,role,rev(case))
    sign_baseline(actor,case.pk,e['signature'].pk,rev(case))
    return e

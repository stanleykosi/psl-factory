"""Explicitly synthetic policy, people and rates; never operational defaults."""
from datetime import timedelta
from django.utils import timezone
from apps.policy.services import transition
from apps.policy.operator_drafts import draft_operator_policy
from apps.pmo.services import complete_milestone
from apps.workflows.services import run_once
from apps.finance.models import Handoff
from apps.workflows import factory
from tests.helpers import setup_case,signed,rev
from tests.billing_helpers import coverage,stage_policy,policy,evidence
from tests.settlement_helpers import configured

def fixture(missing=False,configure=True,responsibility=True,username='factory-maker',synthetic=True,**profile_values):
    a,c=setup_case(username=username,synthetic=synthetic)
    if synthetic:e=signed(a,c)
    else:
        # Operational-shaped test data needs explicit current eligibility and distinct reviewers.
        from django.contrib.auth import get_user_model
        from apps.identity.models import Grant
        from apps.policy.role_assignments import draft
        from apps.pmo.services import decide,sign_baseline
        from tests.helpers import prepared
        e=prepared(a,c);now=timezone.now()
        window={'roles':['PM','Head of PMO'],'valid_from':now.isoformat(),'valid_until':(now+timedelta(hours=1)).isoformat()}
        assignments=[{'role':role,'user_id':a.pk,'eligibility':window} for role in window['roles']]
        reviewers={}
        for role in ['CEO','PMO Lead']:
            person=get_user_model().objects.create_user(username=username+'-'+role.replace(' ','-'))
            for action in ['case.read','decision.record']:Grant.objects.create(user=person,case=c,action=action)
            reviewers[role]=person;assignments.append({'role':role,'user_id':person.pk})
        authority=draft(a,c.pk,assignments,e['policy_decision'].pk,now)
        transition(a,authority.pk,'validated');transition(a,authority.pk,'active')
        for role in ['PM','Head of PMO']:decide(a,c.pk,role,rev(c))
        for role,person in reviewers.items():decide(person,c.pk,role,rev(c))
        sign_baseline(a,c.pk,e['signature'].pk,rev(c))
    complete_milestone(a,c.pk,'Contract completion criterion',e['completion'].pk,rev(c));run_once(case_id=c.pk)
    handoff=Handoff.objects.get(case=c);cov=coverage(a,c,amount_basis='gross_including_tax')
    stage_policy(a,c,cov,e['signature'])
    policy(a,c,'D12.stage_terms',[{'coverage_id':cov.pk,'stage':'completion','amount':'42.00','due_date':(timezone.localdate()+timedelta(days=7)).isoformat()}])
    policy(a,c,'D12.completion_billing_predicate_ref',{'coverage_id':cov.pk,'stage':'completion','milestone_name':handoff.milestone.name})
    configured(a,c)
    proof=evidence(a,c,'invoice_review','Synthetic exact publication review evidence')
    if responsibility:
        from apps.policy.factory_routing_validators import COMPONENT
        owners={'definition':'pmo-finance/v1','process_id':'F30','activity':'ACT10','method':'native_finance_single_review/v1',
            'process_owner_id':a.pk,'activity_owner_id':a.pk,'policy_owner_id':a.pk,'governance_resolver_id':a.pk}
        assignment=draft_operator_policy(a,c.pk,COMPONENT,owners,e['policy_decision'].pk,timezone.now())
        transition(a,assignment.pk,'validated');transition(a,assignment.pk,'active')
    value={'definition':'pmo-finance/v1','max_steps':40,'max_tokens':20000,'tokens_per_call':100,'max_children':100,'max_depth':1,
        'lease_seconds':120,'max_age_seconds':86400,'required_evidence_kinds':['completion']+(['factory_information'] if missing else []),
        'information_resolver_id':a.pk,'executor_id':a.pk,'review_role':'Finance','provider':'synthetic_factory_v1','enabled':True}
    value.update(profile_values);config=None
    if configure:
        config=draft_operator_policy(a,c.pk,'OPS.factory_execution',value,e['policy_decision'].pk,timezone.now())
        transition(a,config.pk,'validated');transition(a,config.pk,'active')
    work=factory.start(a,c.pk,'FACTORY-EXAMPLE',cov.pk,handoff.pk,'FACTORY-INVOICE',rev(c))
    return {'actor':a,'case':c,'work':work,'coverage':cov,'handoff':handoff,'proof':proof,'value':value,'config':config,'evidence':e}

def approve(f):
    from apps.workflows.models import HumanTask
    t=HumanTask.objects.get(case=f['case'],kind='factory_review',status='open')
    t=factory.claim_task(f['actor'],t.pk,t.revision)
    return factory.decide(f['actor'],t.pk,t.revision,'approve',f['proof'].pk,'Synthetic exact packet review')

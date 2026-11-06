"""Explicit synthetic provider configuration for an existing native delivery case."""
import json
from pathlib import Path
from django.utils import timezone
from apps.core.services import add_evidence
from apps.identity.models import Grant
from apps.policy.readiness_drafts import draft_readiness_policy
from apps.policy.readiness_validators import PROVIDER
from apps.policy.operator_drafts import draft_operator_policy
from apps.policy.services import reference_values,transition
from apps.policy.factory_coordinator_validators import PROTOCOL,SCOPE
from apps.workflows import readiness,readiness_delivery,factory


def planning_provider(f,state,role):
    a,c=f.actor,f.case;state['contract_version']=PROTOCOL
    proof=lambda kind:add_evidence(a,c.pk,kind,'Explicit synthetic delivery planning provider evidence','synthetic:delivery-planner')
    rules=json.loads(Path('fixtures/integration-readiness.json').read_text())['rules']
    rules.update(probe_user_id=a.pk,reviewer_id=a.pk,probe_role=role,reviewer_role=role,independent_review=False)
    p=draft_readiness_policy(a,c.pk,PROVIDER,rules,f.e['policy_decision'].pk,timezone.now())
    transition(a,p.pk,'validated');transition(a,p.pk,'active')
    contract=readiness.capture(a,c.pk,'delivery-planner',{'kind':'provider','family':'provider','implementation':'authenticated_json_v1',
        'target_key':'endpoint:fixture','credential_ref':'secret:fixture','credential_revision':'fixture-v1','principal_ref':'principal:fixture',
        'contract_version':PROTOCOL,'model_id':'fixture-model','capabilities':['health','receipt_lookup','evaluation'],
        'data_scope':'public_canary_and_scoped_receipt_metadata_only'},proof('integration_contract').pk)
    for kind in ['health','evaluation']:
        job=readiness_delivery.reserve(a,c.pk,contract.pk,'delivery-'+kind,kind);readiness_delivery.run_once(case_id=c.pk)
        job.refresh_from_db();assert job.status=='confirmed'
    assessment=readiness.assess(a,c.pk,contract.pk,'delivery-provider-ready');assert assessment.result['capability_ready']
    readiness.review(a,c.pk,assessment.pk,'confirm','delivery-provider-ready',proof('integration_review').pk)
    readiness.select(a,c.pk,contract.pk,proof('integration_selection').pk)
    for action in ['integration.read','integration.source.read']:Grant.objects.create(case=c,user=f.starter,action=action)
    p=draft_operator_policy(a,c.pk,'OPS.factory_coordinator',{'mode':'authenticated_planner_v1','contract_id':contract.pk,
        'planner_id':f.starter.pk,'data_scope':SCOPE,'max_output_chars':2048},f.e['policy_decision'].pk,timezone.now())
    transition(a,p.pk,'validated');transition(a,p.pk,'active')
    value=dict(reference_values(f.work.policy)[0],provider='governed_factory_v1')
    p=draft_operator_policy(a,c.pk,'OPS.factory_delivery_execution',value,f.e['policy_decision'].pk,timezone.now())
    transition(a,p.pk,'validated');transition(a,p.pk,'active')
    factory.adopt_profile(a,f.work.pk,f.work.revision,p.pk,'Explicit synthetic governed planning; preserve existing allowance')
    f.work.refresh_from_db();return contract

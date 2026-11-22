"""Actual native provider readiness and accounting setup; only the HTTP provider is mocked."""
import json
from pathlib import Path
from django.utils import timezone
from apps.core.services import add_evidence
from apps.policy.readiness_drafts import draft_readiness_policy
from apps.policy.readiness_validators import PROVIDER
from apps.policy.operator_drafts import draft_operator_policy
from apps.policy.services import transition
from apps.policy.factory_coordinator_validators import PROTOCOL,SCOPE
from apps.workflows import readiness,readiness_delivery
from tests.finance_analysis_helpers import fixture,METRICS
from tests.factory_accounting_helpers import configured

def gateway(state,prefix='planner',expect_ready=True,**profile_values):
    a,c,e,values,configs,source,template,recipient=fixture(username=prefix+'-operator',recipient_username=prefix+'-reader')
    state['contract_version']=PROTOCOL
    rules=json.loads(Path('fixtures/integration-readiness.json').read_text())['rules']
    rules.update(probe_user_id=a.pk,reviewer_id=a.pk,probe_role='Finance',reviewer_role='Finance',independent_review=False)
    policy=draft_readiness_policy(a,c.pk,PROVIDER,rules,e['policy_decision'].pk,timezone.now())
    transition(a,policy.pk,'validated');transition(a,policy.pk,'active')
    proof=lambda kind:add_evidence(a,c.pk,kind,'Explicit isolated provider test evidence; not a live owner decision','synthetic:planner')
    contract=readiness.capture(a,c.pk,'factory-planner',{'kind':'provider','family':'provider','implementation':'authenticated_json_v1',
        'target_key':'endpoint:fixture','credential_ref':'secret:fixture','credential_revision':'fixture-v1','principal_ref':'principal:fixture',
        'contract_version':PROTOCOL,'model_id':'fixture-model','capabilities':['health','receipt_lookup','evaluation'],
        'data_scope':'public_canary_and_scoped_receipt_metadata_only'},proof('integration_contract').pk)
    for kind in ['health','evaluation']:
        job=readiness_delivery.reserve(a,c.pk,contract.pk,'planner-'+kind,kind);readiness_delivery.run_once(case_id=c.pk);job.refresh_from_db()
        assert job.status=='confirmed',job.status
    assessment=readiness.assess(a,c.pk,contract.pk,'planner-ready')
    if expect_ready:
        assert assessment.result['capability_ready'],assessment.result
        readiness.review(a,c.pk,assessment.pk,'confirm','planner-ready',proof('integration_review').pk)
        readiness.select(a,c.pk,contract.pk,proof('integration_selection').pk)
    coordination=draft_operator_policy(a,c.pk,'OPS.factory_coordinator',{'mode':'authenticated_planner_v1','contract_id':contract.pk,
        'planner_id':a.pk,'data_scope':SCOPE,'max_output_chars':2048},e['policy_decision'].pk,timezone.now())
    transition(a,coordination.pk,'validated');transition(a,coordination.pk,'active')
    work=configured(a,c,e,source,template,METRICS,provider='governed_factory_v1',**profile_values)['work']
    return dict(actor=a,case=c,evidence=e,source=source,template=template,recipient=recipient,work=work,coordination=coordination,contract=contract,assessment=assessment)


def historical_request(fixture, state, *, received=True, answer=None):
    """A request already reserved by the old application before the upgrade."""
    from apps.agents.factory_coordinator import provider_binding
    from apps.documents.contracts import digest
    from apps.workflows import factory
    from apps.workflows.models import FactoryActivity, FactoryAttempt
    from apps.policy.services import reference_values

    work = fixture['work']
    if factory.claim(work.pk) is None:
        raise AssertionError("The historical fixture needs an initial native reservation")
    work.refresh_from_db()
    _, profile = factory.profile(work)
    context, latest, missing, stale, tasks, jobs = factory.snapshot(work, profile)
    allowed, _ = factory.eligible(work, profile, context, latest, missing, stale, tasks, jobs)
    rule = fixture['coordination']
    contract, public, _, pins = provider_binding(work, reference_values(rule)[0])
    evidence = [item.pk for item in latest.values()]
    handles = {f'c{i}': pk for i, pk in enumerate(evidence)}
    work.budget_used += profile['tokens_per_call']
    work.plan_revision += 1
    work.status = 'waiting_effect'
    work.lease_until = None
    work.save(update_fields=['budget_used', 'plan_revision', 'status', 'lease_until'])
    activity = FactoryActivity.objects.create(work=work, key=digest(['historical', work.pk]), kind='ACT03',
                                              plan_revision=work.plan_revision, status='running')
    key = digest(['archived-gateway', work.pk, activity.pk])
    payload = {'protocol':PROTOCOL, 'model_id':contract.payload['model_id'], 'data_scope':SCOPE,
               'eligible':allowed, 'citation_handles':list(handles), 'tools':[],
               'token_limit':profile['tokens_per_call'], 'max_output_chars':2048}
    request = {'schema':'factory-provider-request/v1', 'mode':'authenticated_planner_v1',
               'coordinator_policy':rule.pk, 'contract':contract.pk, 'binding':public, 'readiness':pins,
               'operation_key':key, 'payload':payload, 'citation_map':handles, 'max_output_chars':2048,
               'native_context':{'eligible':allowed, 'evidence_ids':evidence, 'missing':missing, 'case_revision':work.case.revision}}
    attempt = FactoryAttempt.objects.create(activity=activity, number=1, phase='started', fence=work.fence,
                                            observation=context, result=request)
    if received:
        state['receipts'][key] = {'operation_key':key, 'status':'succeeded',
                                 'result':answer or {'activity':allowed[0], 'citations':list(handles)[:1]}}
    state['planning_calls'] = 1
    return attempt

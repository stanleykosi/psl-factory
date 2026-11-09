"""Synthetic local binding setup only; native execution requires separate clearance."""
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.utils import timezone
from apps.identity.models import Grant
from apps.policy.operator_drafts import draft_operator_policy
from apps.policy.services import transition
from apps.policy.factory_recovery_validators import COMPONENT,METHOD
from apps.workflows import factory_execution
from apps.workflows.models import FactoryActivity,FactoryAttempt,Outbox
from apps.agents.models import AgentRun
from tests.factory_planning_impact802_helpers import fixture as planning_fixture

def policy(f):
    p=draft_operator_policy(f['a'],f['c'].pk,COMPONENT,{'rules':[f['rule']]},f['e']['policy_decision'].pk,timezone.now())
    transition(f['a'],p.pk,'validated');transition(f['a'],p.pk,'active');return p

def bind(f):
    w=f['work'];w.refresh_from_db()
    before=(w.actor_id,w.budget_used,w.budget_limit,w.request,w.request_hash,w.source_head_id)
    row=factory_execution.bind(f['a'],w.pk,w.revision,f['e']['policy_decision'].pk,'Explicit synthetic planning replacement; no worker execution')
    w.refresh_from_db()
    if before!=(w.actor_id,w.budget_used,w.budget_limit,w.request,w.request_hash,w.source_head_id):raise AssertionError('Starter, source and budget preserved')
    if w.lease_until is not None:raise AssertionError('No worker lease')
    if FactoryActivity.objects.filter(work=w).exists() or FactoryAttempt.objects.filter(activity__work=w).exists():raise AssertionError('No worker activities or attempts')
    if Outbox.objects.filter(case=f['c']).exists() or AgentRun.objects.filter(case=f['c']).exists():raise AssertionError('No handoff or agent effects')
    return row

def fixture(username='impact804'):
    f=planning_fixture(username=username)
    if not f['c'].synthetic:raise AssertionError('Synthetic only')
    worker=get_user_model().objects.create_user(username=username+'-principal')
    for action in ('case.read','planning.read','factory.read','factory.execute'):Grant.objects.create(case=f['c'],user=worker,action=action)
    now=timezone.now()
    f['rule']=dict(definition='planning/v1',method=METHOD,principal_id=worker.pk,reviewer_id=f['a'].pk,review_role='PM',independent_of_worker=True,valid_from=now.isoformat(),valid_until=(now+timedelta(hours=1)).isoformat())
    f['policy']=policy(f);f['binding']=bind(f);return f

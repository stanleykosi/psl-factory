"""Fresh synthetic planning work; native profile adoption, no worker or provider."""
import json
from pathlib import Path
from django.utils import timezone
from apps.policy.operator_drafts import draft_operator_policy
from apps.policy.services import transition
from apps.workflows import factory,factory_planning
from tests.planning_helpers import fixture as planning_fixture
from tests.helpers import rev
from adapters.factory_planning_policy_impact import COMPONENT

def policy(f):
    p=draft_operator_policy(f['a'],f['c'].pk,COMPONENT,f['values'],f['e']['policy_decision'].pk,timezone.now())
    transition(f['a'],p.pk,'validated');transition(f['a'],p.pk,'active');return p

def fixture(username='impact802',bind=True):
    f=planning_fixture(configured=False,username=username)
    if not f['c'].synthetic:raise AssertionError('Synthetic only')
    value=json.loads((Path(__file__).resolve().parents[1]/'fixtures/factory-planning.json').read_text());value.pop('classification')
    if value['provider']!='synthetic_factory_v1' or value['definition']!='planning/v1':raise AssertionError('Explicit local synthetic definition')
    if any(value[k] is not None for k in ('executor_id','information_resolver_id','review_role')):raise AssertionError('No appointed execution identity')
    f['values']=value;f['policy']=policy(f)
    f['work']=factory_planning.start(f['a'],f['c'].pk,'impact802',f['packet'].pk,'Synthetic profile metadata',rev(f['c']))
    if f['work'].policy_id is not None:raise AssertionError('Native start is unbound')
    if bind:f['work']=factory.adopt_profile(f['a'],f['work'].pk,f['work'].revision,f['policy'].pk,'Explicit synthetic fresh unleased profile selection')
    from apps.workflows.models import FactoryActivity,FactoryAttempt,FactoryExecutionBinding,Outbox
    from apps.pmo.models import ApprovalRouteJob,ApprovalRouteReceipt,CommercialSignatureUse,CommercialSignaturePacket,CommercialSignatureReaffirmation,BaselineAdoption,Baseline,RFPCase
    from apps.agents.models import AgentRun
    w=f['work']
    if w.lease_until is not None or w.fence or w.budget_used:raise AssertionError('No worker claim or spend')
    if FactoryActivity.objects.filter(work=w).exists() or FactoryAttempt.objects.filter(activity__work=w).exists() or FactoryExecutionBinding.objects.filter(work=w).exists():raise AssertionError('No activities or principal binding')
    if ApprovalRouteJob.objects.filter(request__case=f['c']).exists() or ApprovalRouteReceipt.objects.filter(job__request__case=f['c']).exists():raise AssertionError('No routing effects')
    if CommercialSignatureUse.objects.filter(packet__case=f['c']).exists() or BaselineAdoption.objects.filter(revision__dossier__case=f['c']).exists() or Baseline.objects.filter(case=f['c'],signed__isnull=False).exists():raise AssertionError('No signing or baseline adoption')
    if AgentRun.objects.filter(case=f['c']).exists() or Outbox.objects.filter(case=f['c']).exists():raise AssertionError('No agent or handoff work')
    if CommercialSignaturePacket.objects.filter(case=f['c']).exists() or CommercialSignatureReaffirmation.objects.filter(packet__case=f['c']).exists() or RFPCase.objects.filter(case=f['c']).exists():raise AssertionError('No packet, reaffirmation or RFP conversion')
    return f

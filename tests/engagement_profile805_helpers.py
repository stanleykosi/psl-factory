"""Route B synthetic engagement profile fixture. No worker or conversion."""
import json
from pathlib import Path
from django.utils import timezone
from apps.core.services import add_evidence
from apps.pmo import engagement
from apps.policy.operator_drafts import draft_operator_policy
from apps.policy.services import transition
from apps.workflows import factory,factory_engagement
from tests.helpers import setup_case,rev
from adapters.factory_engagement_policy_impact import COMPONENT

def policy(f):
    p=draft_operator_policy(f['a'],f['c'].pk,COMPONENT,f['values'],f['e'].pk,timezone.now())
    transition(f['a'],p.pk,'validated');transition(f['a'],p.pk,'active');return p

def fixture(username='impact805',bind=True):
    a,c=setup_case(username=username)
    if not c.synthetic or c.kind!='project':raise AssertionError('Synthetic project only')
    source=add_evidence(a,c.pk,'engagement_source','Synthetic direct Route B source','synthetic:805')
    evidence=add_evidence(a,c.pk,'policy_decision','Synthetic engineering profile only','synthetic:805')
    capture=engagement.capture(a,c.pk,'B',source.pk,'impact805','capture805')
    if capture.data['rfp_disposition'] is not None or capture.data['route']!='B':raise AssertionError('Direct route only')
    work=factory_engagement.start(a,c.pk,'impact805',capture.pk,'Synthetic direct intake',rev(c))
    values=json.loads((Path(__file__).resolve().parents[1]/'fixtures/factory-engagement.json').read_text());values.pop('classification')
    if values['provider']!='synthetic_factory_v1' or values['definition']!='engagement/v1':raise AssertionError('Local synthetic profile only')
    if any(values[k] is not None for k in ('executor_id','information_resolver_id','review_role')):raise AssertionError('No appointed execution identity')
    f={'a':a,'c':c,'e':evidence,'source':source,'capture':capture,'work':work,'values':values};f['policy']=policy(f)
    if work.policy_id is not None:raise AssertionError('Native start is unbound')
    if bind:f['work']=factory.adopt_profile(a,work.pk,work.revision,f['policy'].pk,'Explicit fresh synthetic intake profile')
    from apps.workflows.models import FactoryWork,FactoryActivity,FactoryAttempt,FactoryExecutionBinding,Outbox
    from apps.agents.models import AgentRun
    from apps.pmo.models import RFPCase,RFPDisposition,CommercialSignaturePacket,BaselineAdoption
    if FactoryWork.objects.filter(case=c).exclude(pk=work.pk).exists():raise AssertionError('No planning or other work')
    if FactoryActivity.objects.filter(work=work).exists() or FactoryAttempt.objects.filter(activity__work=work).exists() or FactoryExecutionBinding.objects.filter(work=work).exists():raise AssertionError('No execution')
    if Outbox.objects.filter(case=c).exists() or AgentRun.objects.filter(case=c).exists():raise AssertionError('No agent/provider handoff')
    if RFPCase.objects.filter(case=c).exists() or RFPDisposition.objects.filter(rfp__case=c).exists() or CommercialSignaturePacket.objects.filter(case=c).exists() or BaselineAdoption.objects.filter(revision__dossier__case=c).exists():raise AssertionError('No conversion/sign/adoption')
    if f['work'].lease_until is not None or f['work'].fence or f['work'].budget_used:raise AssertionError('No worker claim/spend')
    return f

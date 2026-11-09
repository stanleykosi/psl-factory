"""Closed Escalation execution policy; business decisions remain native."""
from copy import deepcopy
from types import SimpleNamespace
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from apps.core.evidence_access import restricted
from apps.identity.models import Grant
from .document_validators import typed
from .factory_validators import GO_LIVE_VALUE
from .factory_provider_profiles import shape_for,scope
COMPONENT='OPS.factory_escalation_execution'
SCHEMA='schema:psl/factory-escalation-execution/v1'
VALUE=deepcopy(GO_LIVE_VALUE)
VALUE['properties']['definition']={'const':'pmo-escalation/v1'}
def validate_reference(component,target,case,runtime=False):
    value=typed(target,*shape_for(target,SCHEMA,VALUE));scope(case,value)
    if value['tokens_per_call']>value['max_tokens']:raise ValidationError('Call reservation exceeds aggregate token budget')
    if any(restricted(SimpleNamespace(kind=k)) and k!='agent_private_escalation_intake' for k in value['required_evidence_kinds']):raise ValidationError('Restricted sources require their native domain interface')
    if not runtime:
        for name in ['preparer_id','executor_id']:
            pk=value[name]
            if pk is None:continue
            actions=['case.read','issue.read','factory.execute']+(['issue.escalate','document.draft'] if name=='preparer_id' else ['document.publish'])
            if not get_user_model().objects.filter(pk=pk,is_active=True).exists() or any(not Grant.objects.filter(case=case,user_id=pk,action=action,active=True).exists() for action in actions):raise ValidationError('Configured Escalation principal needs current exact project permissions; no role is appointed')
    return value

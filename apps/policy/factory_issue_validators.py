"""Execution settings do not invent SLA, source freshness or source-reader grants."""
from copy import deepcopy
from types import SimpleNamespace
from django.core.exceptions import ValidationError
from apps.core.evidence_access import restricted
from .document_validators import typed
from .factory_validators import PLANNING_VALUE
from .factory_provider_profiles import shape_for,scope
COMPONENT='OPS.factory_issue_execution'
SCHEMA='schema:psl/factory-issue-execution/v1'
VALUE=deepcopy(PLANNING_VALUE)
VALUE['properties']['definition']={'const':'pmo-issues/v1'}
VALUE['properties']['reference_max_age_seconds']={'anyOf':[{'type':'integer','minimum':1,'maximum':31536000},{'type':'null'}]}
VALUE['required'].append('reference_max_age_seconds')

def validate_reference(component,target,case,runtime=False):
    value=typed(target,*shape_for(target,SCHEMA,VALUE));scope(case,value)
    if value['tokens_per_call']>value['max_tokens']:raise ValidationError('Call reservation exceeds aggregate token budget')
    if any(restricted(SimpleNamespace(kind=k)) and k!='agent_private_issue_intake' for k in value['required_evidence_kinds']):raise ValidationError('Private source evidence requires its scoped interface')
    return value

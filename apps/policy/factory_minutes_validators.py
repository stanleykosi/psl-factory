"""Unassigned publisher and absent extraction are explicit, not invented PMO policy."""
from copy import deepcopy
from django.core.exceptions import ValidationError
from .factory_validators import COMMERCIAL_VALUE
from .document_validators import typed
from .factory_provider_profiles import shape_for,scope
COMPONENT='OPS.factory_minutes_execution'
SCHEMA='schema:psl/factory-minutes-execution/v1'
VALUE=deepcopy(COMMERCIAL_VALUE)
VALUE['properties'].update(definition={'const':'pmo-minutes/v1'},extraction_provider={'enum':[None,'synthetic_meeting_v1']})
VALUE['required'].append('extraction_provider')
def validate_reference(component,target,case,runtime=False):
    v=typed(target,*shape_for(target,SCHEMA,VALUE));scope(case,v)
    if v['tokens_per_call']>v['max_tokens']:raise ValidationError('Call reservation exceeds aggregate budget')
    if v['extraction_provider']=='synthetic_meeting_v1' and not case.synthetic:raise ValidationError('Synthetic meeting extraction is test-only')
    if any(k not in ['agent_private_minutes_intake','meeting_notes'] for k in v['required_evidence_kinds']):raise ValidationError('Minutes scope is the selected authorized notes only')
    if v['executor_id'] is not None and not runtime:
        from django.contrib.auth import get_user_model
        from apps.identity.services import require
        u=get_user_model().objects.filter(pk=v['executor_id'],is_active=True).first()
        if not u:raise ValidationError('Current authenticated publisher required')
        for action in ['case.read','meeting.read','factory.execute','document.publish']:require(u,case,action)

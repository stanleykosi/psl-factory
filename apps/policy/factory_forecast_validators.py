from copy import deepcopy
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from apps.identity.models import Grant
from .factory_validators import GO_LIVE_VALUE
from .document_validators import typed
from .factory_provider_profiles import shape_for,scope
COMPONENT='OPS.factory_forecast_execution'
SCHEMA='schema:psl/factory-forecast-execution/v1'
VALUE=deepcopy(GO_LIVE_VALUE)
VALUE['properties']['definition']={'const':'finance-forecast/v1'}
def validate_reference(component,target,case,runtime=False):
    value=typed(target,*shape_for(target,SCHEMA,VALUE));scope(case,value)
    if value['information_resolver_id'] is not None:raise ValidationError('Forecast human decisions stay with native Finance commands')
    if value['tokens_per_call']>value['max_tokens']:raise ValidationError('Call reservation exceeds aggregate allowance')
    if any(k not in ['forecast_input','forecast_opening','document'] for k in value['required_evidence_kinds']):raise ValidationError('Select native scenario evidence requirements')
    if not runtime:
        for name in ['preparer_id','executor_id']:
            uid=value[name]
            if uid is None:continue
            if not get_user_model().objects.filter(pk=uid,is_active=True).exists():raise ValidationError('Select an active native principal')
            actions=['case.read','finance.read','factory.execute']+(['finance.forecast.calculate','finance.publish','document.draft'] if name=='preparer_id' else ['document.publish'])
            for action in actions:
                if not Grant.objects.filter(case=case,user_id=uid,action=action,active=True).exists():raise ValidationError('Forecast principal lacks current native permissions')
    return value

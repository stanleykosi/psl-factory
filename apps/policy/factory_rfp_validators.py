"""RFP worker limits and document selection; source business approvals remain native."""
from copy import deepcopy
from django.core.exceptions import ValidationError
from .factory_validators import VALUE,ID
from .document_validators import typed

COMPONENT='OPS.factory_rfp_execution'
SCHEMA='schema:psl/factory-rfp-execution/v1'
RFP_VALUE=deepcopy(VALUE)
RFP_VALUE['properties'].update(definition={'const':'rfp-response/v1'},review_role={'type':'null'},
    template_id=deepcopy(ID),route_key={'anyOf':[{'type':'null'},{'type':'string','pattern':'^[a-z][a-z0-9_]{0,79}$'}]})
RFP_VALUE['required']+=['template_id','route_key']
RFP_VALUE['properties']['required_evidence_kinds']['items']={'enum':['rfp_intake','rfp_response','rfp_commercial_terms','requirements','plan','costing']}

def validate_reference(component,target,case,runtime=False):
    from .factory_provider_profiles import shape_for,scope
    value=typed(target,*shape_for(target,SCHEMA,RFP_VALUE));scope(case,value)
    if value['tokens_per_call']>value['max_tokens']:raise ValidationError('Call reservation exceeds aggregate token budget')
    from apps.identity.models import Grant
    from apps.documents.models import Template
    for field in ['template_id','executor_id','information_resolver_id']:
        if value[field] is not None and type(value[field]) is not int:raise ValidationError('Exact RFP principal and template references required')
    if not runtime:
        if value['route_key'] is not None:
            from .services import active_component,reference_values
            configuration=active_component('D11.adapter_configuration_refs',case)
            routes=[route for route in reference_values(configuration) if route.get('kind')=='rfp_submission' and route.get('key')==value['route_key']]
            if len(routes)!=1:raise ValidationError('Select one current workspace RFP submission route')
        if value['template_id'] is not None:
            template=Template.objects.filter(case=case,pk=value['template_id'],definition__document_type='rfp_response').first()
            if not template or template.definition.get('internal_review_required',True) is not True:raise ValidationError('Select this workspace RFP client-response template with final document review')
        for field,actions in [('executor_id',['case.read','rfp.read','rfp.submit','document.publish','factory.execute']),
                              ('information_resolver_id',['case.read','rfp.read','factory.information'])]:
            if value[field] is not None and any(not Grant.objects.filter(case=case,user_id=value[field],user__is_active=True,action=a,active=True).exists() for a in actions):
                raise ValidationError('RFP nominees need existing current scoped permissions; nomination grants no authority')
    return value

"""Closed accounting execution envelope; all financial rules stay Finance-owned."""
from copy import deepcopy
from django.core.exceptions import ValidationError
from .factory_validators import VALUE,ID
from .document_validators import typed

COMPONENT='OPS.factory_accounting_execution'
SCHEMA='schema:psl/factory-accounting-execution/v1'
ACCOUNTING_VALUE=deepcopy(VALUE)
ACCOUNTING_VALUE['properties'].update(definition={'const':'finance-accounts/v1'},template_id=deepcopy(ID),
    audience={'enum':[None,'internal','group']},allocation_mode={'enum':[None,'company_only','company_and_bu']},
    bu_metrics={'anyOf':[{'type':'null'},{'type':'array','minItems':1,'maxItems':5,'uniqueItems':True,
        'items':{'enum':['revenue','direct_cost','staff_cost','opex','other']}}]})
ACCOUNTING_VALUE['required']+=['template_id','audience','allocation_mode','bu_metrics']
ACCOUNTING_VALUE['properties']['required_evidence_kinds']['items']={'enum':['finance_source','financial_input']}
ACCOUNTING_VALUE['properties']['required_evidence_kinds']['maxItems']=2

def validate_reference(component,target,case,runtime=False):
    from .factory_provider_profiles import shape_for,scope
    value=typed(target,*shape_for(target,SCHEMA,ACCOUNTING_VALUE));scope(case,value)
    from apps.identity.models import Grant
    from apps.documents.models import Template
    for field in ['template_id','executor_id','information_resolver_id']:
        if value[field] is not None and type(value[field]) is not int:raise ValidationError('Exact accounting principal/template identities required')
    if value['allocation_mode']=='company_only' and value['bu_metrics'] is not None:
        raise ValidationError('Company-only preparation must explicitly leave BU metric scope unapplied')
    if not runtime:
        if value['template_id'] is not None and not Template.objects.filter(case=case,pk=value['template_id'],definition__document_type='finance_report').exists():
            raise ValidationError('Select this workspace native Finance report template')
        for field,actions in [('executor_id',['case.read','finance.read','document.publish','finance.publish','factory.execute']),
            ('information_resolver_id',['case.read','finance.read','factory.information'])]:
            if value[field] is not None and any(not Grant.objects.filter(case=case,user_id=value[field],user__is_active=True,action=a,active=True).exists() for a in actions):
                raise ValidationError('Accounting nominees need current same-workspace native permissions; nomination grants no authority')
    return value

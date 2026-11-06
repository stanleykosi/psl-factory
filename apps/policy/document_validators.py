from datetime import datetime
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from apps.documents.contracts import validate, AUDIENCES

SUPPORTED = {'D11.recipient_grant_refs','D11.template_storage_retention_rules','D05.delegation_rules','D05.decision_action_matrix'}
ROLES = ['HR','PM','Head of PMO','CEO','PMO Lead','Product','Product Owner','Engineering','Engineering Lead','Security Manager','Client','QA','PMO','CTO','Security Lead','Finance','BaaS','Data','Legal','Support','Reconciliation','Process User','Automation Team']


def typed(target,schema_id,schema):
    if target.schema_ref != schema_id:
        raise ValidationError('Unexpected registered domain schema: ' + schema_id)
    validate(schema,target.content)
    return target.content


def validate_reference(component,target,case,runtime=False):
    if component == 'D11.recipient_grant_refs':
        content=typed(target,'schema:psl/document-recipient/v1',{'type':'object','properties':{
            'audience':{'enum':AUDIENCES},'user_id':{'type':'integer','minimum':1}},'required':['audience','user_id'],'additionalProperties':False})
        from apps.identity.models import Grant
        if not runtime and (not get_user_model().objects.filter(pk=content['user_id'],is_active=True).exists() or not Grant.objects.filter(case=case,user_id=content['user_id'],action='document.receive:'+content['audience'],active=True).exists()):
            raise ValidationError('Recipient needs an active authenticated principal and explicit audience receive grant')
    elif component == 'D11.template_storage_retention_rules':
        extra={}
        if target.schema_ref=='schema:psl/document-storage/v2':
            extra={'closure_inventory':{'type':'object','properties':{
                'required_kinds':{'type':'array','minItems':3,'maxItems':20,'uniqueItems':True,'items':{'type':'string','pattern':'^[a-z][a-z0-9_]{0,49}$'}},
                'archive_mode':{'const':'immutable_local_manifest'}},'required':['required_kinds','archive_mode'],'additionalProperties':False}}
        content=typed(target,'schema:psl/document-storage/v2' if extra else 'schema:psl/document-storage/v1',{'type':'object','properties':{
            **extra,
            'template_ids':{'type':'array','minItems':1,'uniqueItems':True,'items':{'type':'integer','minimum':1}},
            'repository':{'const':'internal-versioned'},'retention_days':{'type':'integer','minimum':1}},
            'required':['template_ids','repository','retention_days'],'additionalProperties':False})
        from apps.documents.models import Template
        if Template.objects.filter(case=case,pk__in=content['template_ids']).count()!=len(content['template_ids']):
            raise ValidationError('Template must be a registered immutable version on this case')
        if extra and 'closure_inventory' in content and not {'technical_document','test_results','project_artifact'}.issubset(content['closure_inventory']['required_kinds']):
            raise ValidationError('Closure inventory must include technical_document, test_results and project_artifact')
    elif component == 'D05.decision_action_matrix':
        props={'rules':{'type':'array','minItems':1,'uniqueItems':True,'items':{'type':'object','properties':{
                'role':{'enum':ROLES},'actions':{'type':'array','minItems':1,'uniqueItems':True,'items':{'enum':['return','reject','withdraw','reopen']}}},
                'required':['role','actions'],'additionalProperties':False}}}
        v8=target.schema_ref=='schema:psl/decision-actions/v8'
        if v8:props['rules']['items']['properties']['actions']['items']['enum'].append('reaffirm_go_live')
        v7=v8 or target.schema_ref=='schema:psl/decision-actions/v7'
        v6=v7 or target.schema_ref=='schema:psl/decision-actions/v6'
        v5=v6 or target.schema_ref=='schema:psl/decision-actions/v5'
        v4=v5 or target.schema_ref=='schema:psl/decision-actions/v4'
        v3=v4 or target.schema_ref=='schema:psl/decision-actions/v3'
        v2=v3 or target.schema_ref=='schema:psl/decision-actions/v2'
        if v2:
            from .rfp_validators import ROLE_LIST
            props['rfp']={'type':'object','minProperties':1,'properties':{k:ROLE_LIST for k in ['assignment_roles','outcome_roles']},'additionalProperties':False}
        if v3:
            from .finance_validators import rows,obj
            props['finance']=rows(obj({'purpose':{'enum':(['source','mapping','formula','allocation','adjustment','output','budget','performance','period_method','restatement']+(['invoice'] if v5 else [])+(['invoice_correction','cash_successor'] if v6 else []) if v4 else ['source','mapping','formula','allocation','adjustment','output'])},'role':{'enum':ROLES},'actions':{'type':'array','minItems':1,'uniqueItems':True,'items':{'enum':['approve','return','reject']}},'allow_preparer_review':{'type':'boolean'}}))
            entries=target.content.get('finance',[])
            if isinstance(entries,list) and all(isinstance(x,dict) and 'purpose' in x and 'role' in x for x in entries) and len({(x['purpose'],x['role']) for x in entries})!=len(entries):raise ValidationError('Duplicate Finance review purpose/role')
        if v7:props['finance']['items']['properties']['purpose']['enum']+=['forecast','forecast_rollover','forecast_priority']
        typed(target,'schema:psl/decision-actions/v8' if v8 else 'schema:psl/decision-actions/v7' if v7 else 'schema:psl/decision-actions/v6' if v6 else 'schema:psl/decision-actions/v5' if v5 else 'schema:psl/decision-actions/v4' if v4 else 'schema:psl/decision-actions/v3' if v3 else 'schema:psl/decision-actions/v2' if v2 else 'schema:psl/decision-actions/v1',
            {'type':'object','minProperties':1,'properties':props,'required':[] if v2 else ['rules'],'additionalProperties':False})
        if v8 and any('reaffirm_go_live' in rule['actions'] and rule['role']!='PM' for rule in target.content.get('rules',[])):
            raise ValidationError('Go-live evidence reaffirmation requires the prescribed PM role; a matrix cannot appoint another business role')
    elif component == 'D05.delegation_rules':
        from .delegation_validators import validate_reference as validate_delegation
        validate_delegation(target,case)

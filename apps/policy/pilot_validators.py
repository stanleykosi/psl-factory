"""Engineering selection contract; contains no business values or credentials."""
from django.core.exceptions import ValidationError
from jsonschema import Draft202012Validator, FormatChecker
from apps.identity.actions import ACTIONS
from apps.policy.registry import catalogue
from apps.workflows.operator_inventory import ROUTES
from adapters.pilot_physical import FAMILIES as PHYSICAL_FAMILIES


def operations():
    return sorted({r['operation'] for r in catalogue()['operation_dependencies']})


def schema():
    import copy
    ids={'type':'integer','minimum':1}
    original={'type':'object','additionalProperties':False,
        'required':['format','case_id','process_ids','operations','participants','integrations','jobs','read_only'],
        'properties':{
            'format':{'const':'psl.pilot-contract/v1'},
            'case_id':{'type':'string','format':'uuid'},
            'read_only':{'const':True},
            'process_ids':{'type':'array','minItems':1,'maxItems':122,'uniqueItems':True,'items':{'type':'string','maxLength':10}},
            'operations':{'type':'array','minItems':1,'maxItems':20,'uniqueItems':True,'items':{'enum':operations()}},
            'participants':{'type':'array','minItems':1,'maxItems':20,'uniqueItems':True,'items':{
                'type':'object','additionalProperties':False,'required':['user_id','actions'],
                'properties':{'user_id':ids,'actions':{'type':'array','minItems':1,'maxItems':30,'uniqueItems':True,'items':{'enum':ACTIONS}}}}},
            'integrations':{'type':'array','maxItems':20,'uniqueItems':True,'items':ids},
            'jobs':{'type':'array','maxItems':30,'uniqueItems':True,'items':{
                'type':'object','additionalProperties':False,'required':['family','id'],
                'properties':{'family':{'enum':sorted(set(ROUTES)|set(PHYSICAL_FAMILIES))},'id':ids}}}}}
    native=copy.deepcopy(original)
    native['properties']['format']={'const':'psl.pilot-contract/v2'}
    native['properties']['acceptance_reviews']={'type':'array','minItems':1,'maxItems':20,'uniqueItems':True,'items':ids}
    native['required'].append('acceptance_reviews')
    return {'oneOf':[original,native]}


def validate(case, value):
    import json
    from pathlib import Path
    from django.conf import settings
    try:
        if len(json.dumps(value,allow_nan=False))>24000:raise ValueError()
    except (ValueError,TypeError):raise ValidationError('Finite bounded selection required') from None
    if list(Draft202012Validator(schema(),format_checker=FormatChecker()).iter_errors(value)):
        raise ValidationError('Invalid pilot selection: use the versioned schema and registered operations/actions/families')
    known={r['id'] for r in json.loads((settings.BASE_DIR/'contracts/process-map.json').read_text(encoding='utf-8'))['rows']}
    if value['case_id']!=str(case.pk) or not set(value['process_ids'])<=known:
        raise ValidationError('Exact case and original process IDs required')
    users=[r['user_id'] for r in value['participants']]
    if len(set(users))!=len(users):raise ValidationError('Select each participant once')

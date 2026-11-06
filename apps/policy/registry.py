import json
from functools import lru_cache
from django.conf import settings


@lru_cache
def catalogue():
    value=json.loads((settings.BASE_DIR / 'contracts/policy-slots.json').read_text(encoding='utf-8'))
    extra={'components':[],'operation_dependencies':[]}
    for filename in ['statement-policy-components.json','validation-policy-components.json','recognition-policy-components.json','hr-finance-policy-components.json','payroll-policy-components.json','bu-policy-components.json','schedule-policy-components.json','ppe-policy-components.json','ledger-policy-components.json','support-policy-components.json','approval-policy-components.json','operator-policy-components.json','readiness-policy-components.json','pilot-operation-components.json']:
        item=json.loads((settings.BASE_DIR/'contracts'/filename).read_text(encoding='utf-8'))
        extra['components']+=item['components'];extra['operation_dependencies']+=item.get('operation_dependencies',[])
    value['components']+=extra['components']
    value['operation_dependencies']+=extra.get('operation_dependencies',[])
    return value


def components():
    return {c['id']: c for c in catalogue()['components']}


@lru_cache
def envelope_schema():
    schema=json.loads((settings.BASE_DIR / 'contracts/policy-configuration.schema.json').read_text(encoding='utf-8'))
    extra=[c for filename in ['statement-policy-components.json','validation-policy-components.json','recognition-policy-components.json','hr-finance-policy-components.json','payroll-policy-components.json','bu-policy-components.json','schedule-policy-components.json','ppe-policy-components.json','ledger-policy-components.json','support-policy-components.json','approval-policy-components.json','operator-policy-components.json','readiness-policy-components.json','pilot-operation-components.json'] for c in json.loads((settings.BASE_DIR/'contracts'/filename).read_text(encoding='utf-8'))['components']]
    schema['properties']['slot_id']['enum']+=['AF13','F33','F35','PAYROLL','BU','SCHEDULES','F07','F01','B14','P02','OPS','INT']
    for c in extra:
        schema['properties']['component_id']['enum'].append(c['id'])
        schema['allOf'].append({'if':{'properties':{'component_id':{'const':c['id']}}},'then':{'properties':{'slot_id':{'const':c['parent_decision_id']},'component_schema_ref':{'const':c['schema_ref']},'value':c['value_schema']}}})
    return schema


def dependencies(operation):
    for entry in catalogue()['operation_dependencies']:
        if entry['operation'] == operation:
            return entry['required_components']
    raise ValueError(f'No registered policy dependency set for {operation}')

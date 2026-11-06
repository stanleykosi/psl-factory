"""Versioned engineering interfaces for Q03/Q06/Q07; no operational defaults."""
from django.core.exceptions import ValidationError
from .document_validators import typed, ROLES

SUPPORTED = {'D01.emergency_glpi_relationship'}
EMERGENCY_GATES = {'type':'object','properties':{
    'preauthorization_roles':{'const':['Incident Lead','Engineering Lead']},
    'p1_additional_roles':{'const':['CTO']},
    'retrospective_roles':{'const':['Product','Engineering Lead']},
    'financial_controls':{'const':'independent'},
    'deployment_dispatch':{'const':'not_granted'}},
    'required':['preauthorization_roles','p1_additional_roles','retrospective_roles','financial_controls','deployment_dispatch'],
    'additionalProperties':False}


def validate_reference(component,target,case):
    extended=target.schema_ref=='schema:psl/emergency-glpi/v2'
    schema={'type':'object','properties':{
        'mode':{'enum':['coexist','defer','replace']},
        'incident_lead_role':{'enum':['Security Lead','Engineering Lead']},
        'incident_engineering_overlap':{'enum':['distinct_people','explicit_same_person']},
        'exception_roles':{'type':'array','uniqueItems':True,'items':{'enum':ROLES}},
        'deferred_checkpoint':{'const':'before_retrospective_reconciliation'},
        'priority_basis':{'const':'explicit_incident_p1_attestation'}},
        'required':['mode','incident_lead_role','incident_engineering_overlap','exception_roles','priority_basis'],
        'additionalProperties':False,'allOf':[{'if':{'properties':{'mode':{'const':'defer'}}},'then':{'required':['deferred_checkpoint']}}]}
    if extended:
        schema['properties']['role_eligibility']={'const':'current_D05_bundle'}
        schema['required'].append('role_eligibility')
    value=typed(target,'schema:psl/emergency-glpi/v2' if extended else 'schema:psl/emergency-glpi/v1',schema)
    if (value['mode']=='coexist') != (len(value['exception_roles'])==0):
        raise ValidationError('Coexist needs no exception roles; defer/replace needs explicit configured human exception authority')
    if not extended and value['incident_engineering_overlap']=='explicit_same_person' and value['incident_lead_role']!='Engineering Lead':
        raise ValidationError('V1 same-person reuse supports Engineering Lead in both capacities; select V2 and configure the exact D05 bundle for distinct roles')
    if value['mode']!='defer' and 'deferred_checkpoint' in value:
        raise ValidationError('A deferred checkpoint applies only to an explicit deferral')

import hashlib
import json
from django.core.exceptions import ValidationError
from jsonschema import Draft202012Validator

PMO_CLIENT_SECTIONS = ('executive_summary', 'scope', 'timeline', 'risks', 'dependencies', 'status')
PMO_DOCUMENT_TYPES = frozenset(['sow', 'status_report', 'minutes', 'project_artifact', 'rfp_response'])


def client_pmo_sections(definition, audience, case=None):
    if case is not None and case.kind != "project":
        return ()
    return PMO_CLIENT_SECTIONS if audience == 'client' and definition['document_type'] in PMO_DOCUMENT_TYPES else ()


AUDIENCES = ['internal','client','management','group']
PUBLIC_FIELDS = ['financial_metrics','bu_totals','requirements_mapping','commercial_terms','executive_summary','scope','timeline','risks','dependencies','status','issue_impact','issue_status','issue_resolution','next_steps','decisions','actions','owners','deadlines','participants']
FIELDS = PUBLIC_FIELDS + ['internal_notes','progress','blockers','delivery_health','performance','escalations','critical_incidents']
FIELD_LIST = {'type':'array','minItems':1,'uniqueItems':True,'items':{'enum':FIELDS}}
TEMPLATE_SCHEMA = {'type':'object','properties':{
    'document_type':{'enum':['sow','status_report','minutes','project_artifact','rfp_response','finance_report','finance_group_report','accepted_finance_metadata']},
    'required_fields':FIELD_LIST,
    'internal_review_required':{'type':'boolean'},
    'audience_fields':{'type':'object','properties':{a:FIELD_LIST for a in AUDIENCES},'additionalProperties':False,'minProperties':1}},
    'required':['document_type','required_fields','audience_fields'],'additionalProperties':False}


def validate(schema,value):
    errors=list(Draft202012Validator(schema).iter_errors(value))
    if errors:
        raise ValidationError([e.message for e in errors])


def validate_template(value, *, case=None):
    validate(TEMPLATE_SCHEMA,value)
    if value['document_type']=='accepted_finance_metadata':
        if value.get('internal_review_required') is not True or value['required_fields']!=['executive_summary'] or any(x!=['executive_summary'] for x in value['audience_fields'].values()):
            raise ValidationError('Accepted Finance metadata requires a separate exact metadata projection and mandatory human review')
    if value['document_type']=='finance_report':
        if 'client' in value['audience_fields'] or value.get('internal_review_required') is not False or not {'executive_summary','financial_metrics','bu_totals'}.issubset(value['required_fields']):
            raise ValidationError('Finance reports require internal/management aggregate sections and configured Finance output review; no client audience or invented PMO review')
    if 'group' in value['audience_fields'] or value['document_type']=='finance_group_report':
        if value['document_type']!='finance_group_report' or value.get('internal_review_required') is not True or value['audience_fields']!={'group':['executive_summary','financial_metrics','bu_totals']} or value['required_fields']!=['executive_summary','financial_metrics','bu_totals']:
            raise ValidationError('Group forecast needs its separate exact template and mandatory disclosure review')
    client=value['audience_fields'].get('client')
    if client and ('internal_notes' in client or 'executive_summary' not in client or 'executive_summary' not in value['required_fields']):
        raise ValidationError('Client templates require an executive summary and cannot expose internal notes')
    if client and not set(client_pmo_sections(value, 'client', case)).issubset(client):
        raise ValidationError('Client PMO projection must include executive summary, scope, timeline, risks, dependencies and status')
    for allowed in value['audience_fields'].values():
        if not set(value['required_fields']).issubset(allowed):
            raise ValidationError('Required sections must be visible in each supported audience')


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()

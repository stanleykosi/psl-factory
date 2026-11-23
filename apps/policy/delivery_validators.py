import math
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from .document_validators import typed

SUPPORTED={'D11.hypercare_criteria_ref'}
HYPERCARE_V1 = 'schema:psl/hypercare-criteria/v1'
HYPERCARE_V2 = 'schema:psl/hypercare-criteria/v2'
ISSUE_STATUSES = ('Open', 'In Progress', 'Resolved', 'Closed')
ISSUE_SEVERITIES = ('Critical', 'High', 'Medium', 'Low')
METRIC={'type':'object','properties':{'key':{'type':'string','pattern':'^[a-z][a-z0-9_]{0,39}$'},
    'unit':{'type':'string','minLength':1,'maxLength':40},'owner':{'enum':['Engineering','Infrastructure']},
    'operator':{'enum':['lte','gte','eq']},'threshold':{'type':'number'}},
    'required':['key','unit','owner','operator','threshold'],'additionalProperties':False}


def criteria_schema(*, include_issue_clearance=False):
    properties = {
        'clock':{'const':'elapsed_hours_since_release'},'minimum_hours':{'type':'number','minimum':0,'maximum':87600},
        'confirmation_owners':{'type':'array','minItems':1,'uniqueItems':True,'items':{'enum':['Engineering','Infrastructure']}},
        'metrics':{'type':'array','minItems':1,'maxItems':20,'items':METRIC},'financial_controls':{'const':'independent'}}
    if include_issue_clearance:
        issue = {
            'scope': {'const': 'project_issue_register'},
            'reader_id': {'type': 'integer', 'minimum': 1, 'maximum': 9223372036854775807},
            'blocking_statuses': {'type': 'array', 'minItems': 1, 'uniqueItems': True, 'items': {'enum': list(ISSUE_STATUSES[:-1])}},
            'blocking_severities': {'type': 'array', 'minItems': 1, 'uniqueItems': True, 'items': {'enum': list(ISSUE_SEVERITIES)}},
        }
        properties['issue_clearance'] = {'type': 'object', 'properties': issue, 'required': list(issue), 'additionalProperties': False}
    return {'type': 'object', 'properties': properties, 'required': list(properties), 'additionalProperties': False}


def validate_reference(component,target,case):
    issue_clearance = target.schema_ref == HYPERCARE_V2
    c = typed(target, HYPERCARE_V2 if issue_clearance else HYPERCARE_V1,
              criteria_schema(include_issue_clearance=issue_clearance))
    if issue_clearance and not get_user_model().objects.filter(pk=c['issue_clearance']['reader_id']).exists():
        raise ValidationError('Choose an existing issue register reader for the proposed stability rule.')
    if not math.isfinite(c['minimum_hours']) or any(not math.isfinite(m['threshold']) for m in c['metrics']):
        raise ValidationError('Hypercare numeric criteria must be finite')
    keys=[(m['owner'],m['key']) for m in c['metrics']]
    if len(keys)!=len(set(keys)) or any(m['owner'] not in c['confirmation_owners'] for m in c['metrics']):
        raise ValidationError('Metric owner/key must be unique and require an explicit confirmation owner')

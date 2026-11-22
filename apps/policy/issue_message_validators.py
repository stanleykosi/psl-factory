"""Owner-supplied message authority and timing; no default recipients or deadlines."""
from django.core.exceptions import ValidationError
from datetime import timedelta
from django.utils import timezone

from adapters.forecast import KEY, obj
from .document_validators import ROLES, typed

COMPONENT = 'OPS.issue_message_controls'
SCHEMA = 'schema:psl/issue-message-controls/v1'
OPTIONAL_HOURS = {'anyOf':[{'type':'number','exclusiveMinimum':0},{'type':'null'}]}
VALUE = obj({
    'reviewer_roles': {'type':'array','uniqueItems':True,'maxItems':len(ROLES),'items':{'enum':ROLES}},
    'sender_roles': {'type':'array','uniqueItems':True,'maxItems':len(ROLES),'items':{'enum':ROLES}},
    'independent_release': {'type':['boolean','null']},
    'routes': {'type':'array','maxItems':40,'items':obj({
        'team_key':KEY, 'channel':{'enum':['email','whatsapp','ticket']},
        'destination':{'type':'string','minLength':1,'maxLength':240},
        'mode':{'enum':['synthetic_mailbox','manual_evidence']},
    })},
    'reminder_after_hours':OPTIONAL_HOURS,
    'escalation_after_hours':OPTIONAL_HOURS,
    'escalation_target':{'enum':[None,'PMO','CTO','Client']},
    'clock_basis':{'enum':[None,'source_delivery_time','recorded_receipt_time']},
    'draft_on_owner_wait':{'type':['boolean','null']},
})


def validate_reference(target, case):
    value = typed(target, SCHEMA, VALUE)
    if case.kind != 'project':
        raise ValidationError('Owner message controls belong to a project.')
    identities = [(route['team_key'],route['channel']) for route in value['routes']]
    if len(set(identities)) != len(identities):
        raise ValidationError('Choose one destination for each team and channel.')
    if value['routes']:
        from apps.pmo.issue_teams import rules
        teams={team['key'] for team in rules(case)[1]['teams']}
        if any(route['team_key'] not in teams for route in value['routes']):
            raise ValidationError('Choose an external team configured for this project.')
    for route in value['routes']:
        destination = route['destination']
        if destination != destination.strip() or any(ord(c)<32 for c in destination):
            raise ValidationError('Use a plain destination without surrounding whitespace or control characters.')
        if route['channel']=='email':
            from django.core.validators import validate_email
            validate_email(destination)
        if route['mode']=='synthetic_mailbox':
            if not case.synthetic or not (destination.casefold().endswith('.invalid') or destination.startswith('synthetic:')):
                raise ValidationError('The sample mailbox needs an isolated test project and fictional destination.')
    reminder, escalation = value['reminder_after_hours'], value['escalation_after_hours']
    for hours in [reminder,escalation]:
        if hours is not None:
            try:
                timezone.now()+timedelta(hours=float(hours))
            except (OverflowError,ValueError):
                raise ValidationError('Choose an interval within the supported date range.') from None
    if reminder is not None and escalation is not None and escalation < reminder:
        raise ValidationError('The escalation interval cannot precede the reminder interval.')
    return value

"""Closed planning-fact interchange. A planned date is not an actual event time."""
from datetime import date
from django.core.exceptions import ValidationError


def planned_date(value):
    if value in (None,''):return None
    if type(value) is date:return value
    if not isinstance(value,str):raise ValidationError('Use a calendar date or leave it unknown.')
    try:
        parsed=date.fromisoformat(value)
    except ValueError:
        raise ValidationError('Use a calendar date or leave it unknown.') from None
    if parsed.isoformat()!=value:raise ValidationError('Use a full year, month and day.')
    return parsed


def payload(details,contact):
    return {'format':'psl.engagement-planning-details/v1','details':details.pk,
            'capture':details.capture_id,'plan':details.plan_id,'reference':details.reference,
            'planned_start':details.planned_start.isoformat() if details.planned_start else None,
            'client_contact':None if contact is None else {
                'revision':contact.pk,'client_name':contact.client_name,'name':contact.name,
                'role':contact.role,'email':contact.email},
            'evidence':details.evidence_id,'recorded_by':details.actor_id,
            'recorded_at':details.created_at.isoformat(),'source_authenticity':'human_attested'}

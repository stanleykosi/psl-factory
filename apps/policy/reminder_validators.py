from django.core.exceptions import ValidationError

from adapters.forecast import obj
from apps.core.models import ClientContactRevision
from apps.identity.models import Grant

COMPONENT = 'OPS.payment_reminder_delivery'
SCHEMA = 'schema:psl/payment-reminder-delivery/v1'
IDS = {'type': 'array', 'minItems': 1, 'maxItems': 100, 'uniqueItems': True, 'items': {'type': 'integer', 'minimum': 1}}
VALUE = obj({
    'contact_revision_ids': IDS,
    'sender_ids': IDS,
    'receipt_recorder_ids': IDS,
    'mode': {'enum': ['manual_evidence', 'synthetic_inbox', 'synthetic_mailbox']},
    'days_after_due': {'type': 'integer', 'minimum': 0, 'maximum': 365},
    'minimum_days_between': {'type': 'integer', 'minimum': 0, 'maximum': 365},
})
VALUE['properties'].update({
    'attachment_required': {'type': 'boolean'},
    'schedule_days_ahead': {'type': 'integer', 'minimum': 1, 'maximum': 365},
})


def validate_delivery(case, value, runtime):
    if value['mode'] in ('synthetic_inbox', 'synthetic_mailbox') and not case.synthetic:
        raise ValidationError('Synthetic reminder delivery requires a synthetic workspace.')
    contacts = ClientContactRevision.objects.filter(case=case, purpose='billing', pk__in=value['contact_revision_ids']).exclude(email='')
    if value['mode'] == 'synthetic_mailbox':
        contacts = contacts.filter(email__iendswith='.invalid')
    if contacts.count() != len(value['contact_revision_ids']):
        raise ValidationError('Select exact billing contact versions from this workspace.')
    if 'schedule_days_ahead' in value and value['mode'] != 'synthetic_mailbox':
        raise ValidationError('Scheduling requires a channel that can verify the exact message.')
    if runtime:
        return
    for field, action in [('sender_ids', 'finance.reminder.send'), ('receipt_recorder_ids', 'finance.reminder.confirm')]:
        if Grant.objects.filter(case=case, active=True, user__is_active=True, user_id__in=value[field], action=action).count() != len(value[field]):
            raise ValidationError('The responsible people need active scoped access.')

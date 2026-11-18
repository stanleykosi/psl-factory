"""Typed human-attested external facts carry no provider-verification claim."""
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.pmo.clocks import aware


def reply_facts(party, channel, responded_at, source_ref, channels):
    for value, limit in [(party, 200), (source_ref, 240)]:
        if not isinstance(value, str) or not value.strip() or len(value) > limit:
            raise ValidationError('Provide the actual responder and a bounded source reference.')
    if channel not in channels:
        raise ValidationError('Choose an accepted source channel.')
    responded_at = aware(responded_at)
    if responded_at > timezone.now():
        raise ValidationError('The actual reply time cannot be in the future.')
    return {'party': party.strip(), 'channel': channel, 'responded_at': responded_at,
            'source_ref': source_ref.strip()}

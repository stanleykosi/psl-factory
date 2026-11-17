"""Human-controlled intake of supplied client response facts."""
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.policy.go_live_reply_validators import CHANNELS


class SuppliedGoLiveReplyAdapter:
    name = 'supplied-go-live-reply/v1'

    @staticmethod
    def validate(party, responded_at, channel, note, attested):
        if not isinstance(party, str) or not party.strip() or len(party) > 160:
            raise ValidationError('Record who sent the client response.')
        if not responded_at or timezone.is_naive(responded_at) or responded_at > timezone.now():
            raise ValidationError('Use the actual response time, up to now.')
        if channel not in CHANNELS:
            raise ValidationError('Choose the channel where the response was received.')
        if not isinstance(note, str) or not note.strip() or len(note) > 4000:
            raise ValidationError('Record the evidenced response in at most 4,000 characters.')
        if attested is not True:
            raise ValidationError('Confirm that the response and source were actually received.')
        return {'party': party.strip(), 'responded_at': responded_at, 'channel': channel, 'note': note.strip()}

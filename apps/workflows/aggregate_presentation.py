"""Read-only display of the audience fixed on an exact native Finance publication."""
from django.contrib.auth import get_user_model
from django.core.exceptions import ObjectDoesNotExist, ValidationError

from apps.policy.models import Configuration
from apps.policy.services import reference_values


def publication_audience(publication, component):
    config = Configuration.objects.filter(pk=publication.policy_ids.get(component), component=component).first()
    if config is None:
        return None
    try:
        return reference_values(config)[0]['recipient_ids']
    except (ObjectDoesNotExist, ValidationError, KeyError, IndexError):
        return None


def publication_receipts(publication, component, receipts):
    audience = publication_audience(publication,component)
    if audience is None:
        return None
    people = get_user_model().objects.in_bulk(audience)
    recorded = {receipt.actor_id: receipt for receipt in receipts}
    return [{'name': (people[pk].get_full_name() or people[pk].get_username()) if pk in people else f'Recipient {pk}',
             'receipt': recorded.get(pk)} for pk in audience]

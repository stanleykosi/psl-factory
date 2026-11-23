"""Receipt evidence for reviewed Security requests and an isolated test inbox."""
import json

from django.core.exceptions import ValidationError


def receipt_fields(dispatch, reference, delivered):
    request = dispatch.request
    route = request.payload['route']
    return {'operation': str(dispatch.operation), 'sha256': request.sha256, 'channel': route['channel'],
            'recipient': route['destination'], 'reference': reference, 'delivered': delivered}


def check_manual_receipt(dispatch, evidence, reference, delivered):
    try:
        value = json.loads(evidence.body)
    except (ValueError, TypeError):
        raise ValidationError('Provide the original channel receipt evidence.') from None
    if not isinstance(value, dict) or type(value.get('delivered')) is not bool or value != receipt_fields(dispatch, reference, delivered):
        raise ValidationError('The receipt must match the original request, message and destination.')


class SyntheticSecurityInbox:
    def deliver(self, dispatch):
        from apps.pmo.models import RFPEstimateMailbox

        request = dispatch.request
        route = request.payload['route']
        destination = route['destination']
        if (not request.work.case.synthetic or route['method'] != 'synthetic_mailbox'
                or not (destination.endswith('.invalid') or destination.startswith('synthetic:'))):
            raise ValidationError('The test inbox requires an isolated case and fictional destination.')
        reference = 'sample-security-' + dispatch.operation.hex
        message, _ = RFPEstimateMailbox.objects.get_or_create(dispatch=dispatch, defaults={
            'reference': reference, 'payload': request.payload, 'sha256': request.sha256})
        if (message.reference, message.payload, message.sha256) != (reference, request.payload, request.sha256):
            raise ValidationError('The original stored message differs from the reviewed request.')
        return reference

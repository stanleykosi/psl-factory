"""An isolated mailbox plus an exact receipt contract for manual customer delivery."""
import json

from django.core.exceptions import ValidationError


def expected(dispatch,reference,delivered):
    return {'operation':str(dispatch.operation),'sha256':dispatch.sha256,'recipient':dispatch.contact.email,
            'reference':reference,'delivered':delivered}


def verify_evidence(dispatch,evidence,reference,delivered):
    try:
        value=json.loads(evidence.body)
    except ValueError as exc:
        raise ValidationError('Supply structured evidence for the original message receipt.') from exc
    if (not isinstance(value,dict) or type(value.get('delivered')) is not bool or
            value!=expected(dispatch,reference,delivered)):
        raise ValidationError('The receipt must match the original operation, message and recipient.')


class SyntheticBidMailbox:
    def lookup(self,dispatch):
        from apps.pmo.models import RFPFollowupMailbox
        mailbox=RFPFollowupMailbox.objects.filter(dispatch=dispatch).first()
        if mailbox is None:
            return None
        if mailbox.payload!=dispatch.payload or mailbox.sha256!=dispatch.sha256:
            raise ValidationError('The original mailbox message does not match the reviewed draft.')
        return mailbox.reference

    def deliver(self,dispatch):
        from apps.pmo.models import RFPFollowupMailbox
        if not dispatch.outcome.submission.response.rfp.case.synthetic or not dispatch.contact.email.casefold().endswith('.invalid'):
            raise ValidationError('The test mailbox accepts only isolated sample messages.')
        reference='bid-'+dispatch.operation.hex
        RFPFollowupMailbox.objects.get_or_create(dispatch=dispatch,defaults={
            'reference':reference,'payload':dispatch.payload,'sha256':dispatch.sha256})
        return self.lookup(dispatch)

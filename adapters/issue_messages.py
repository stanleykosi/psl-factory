"""Original-operation receipt contracts; the sample mailbox never sends externally."""
import json
from datetime import datetime

from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.documents.contracts import digest


def receipt_facts(reference, delivered, delivered_at):
    if not isinstance(reference,str) or not reference.strip() or len(reference)>160 or type(delivered) is not bool:
        raise ValidationError('Record the actual delivery result and its receipt reference.')
    if delivered_at is not None and (not isinstance(delivered_at,datetime) or
            timezone.is_naive(delivered_at) or delivered_at>timezone.now()):
        raise ValidationError('Use an actual, non-future delivery time with a time zone, or leave it unknown.')
    if not delivered and delivered_at is not None:
        raise ValidationError('An undelivered message has no delivery time.')
    return {'reference':reference.strip(),'delivered':delivered,'delivered_at':delivered_at}


def expected_receipt(dispatch, reference, delivered, delivered_at):
    facts=receipt_facts(reference,delivered,delivered_at)
    return {'operation':str(dispatch.operation),'sha256':dispatch.sha256,
        'recipient':dispatch.payload['recipient'],'channel':dispatch.payload['channel'],
        **facts,'delivered_at':delivered_at.isoformat() if delivered_at else None}


def verify_evidence(dispatch,evidence,reference,delivered,delivered_at):
    try:
        value=json.loads(evidence.body)
    except (ValueError,TypeError):
        raise ValidationError('Supply the structured receipt for the original message operation.') from None
    expected=expected_receipt(dispatch,reference,delivered,delivered_at)
    if isinstance(value,dict) and value.get('protocol')=='issue-owner-message-receipt-attestation/v2':
        source=value.get('source')
        if (set(value)!={'protocol','result','source'} or value['result']!=expected or
                not isinstance(value['result'],dict) or type(value['result'].get('delivered')) is not bool or
                not isinstance(source,dict) or set(source)!={'evidence_id','sha256'} or
                type(source['evidence_id']) is not int or source['evidence_id']<1 or
                not isinstance(source['sha256'],str) or len(source['sha256'])!=64):
            raise ValidationError('Review the exact message receipt and its original supporting evidence.')
        return source
    if value != expected or type(value.get('delivered')) is not bool:
        raise ValidationError('The receipt must match the original operation, exact message, channel and recipient.')
    return None


class SyntheticIssueMailbox:
    def lookup(self,dispatch):
        from apps.pmo.issue_message_models import SyntheticIssueMessage
        record=SyntheticIssueMessage.objects.filter(dispatch=dispatch).first()
        if record is None:
            return None
        if record.payload!=dispatch.payload or record.sha256!=dispatch.sha256 or digest(record.payload)!=record.sha256:
            raise ValidationError('Review the original sample message and its exact payload.')
        return receipt_facts(record.reference,record.delivered,record.delivered_at)

    def deliver(self,dispatch):
        from apps.pmo.issue_message_models import SyntheticIssueMessage
        from django.db.models.functions import Now
        case=dispatch.review.draft.issue.case
        destination=dispatch.payload['recipient']
        if (dispatch.route.get('mode')!='synthetic_mailbox' or not case.synthetic or
                not (destination.casefold().endswith('.invalid') or destination.startswith('synthetic:'))):
            raise ValidationError('The sample mailbox accepts only isolated fictional owner messages.')
        if digest(dispatch.payload)!=dispatch.sha256:
            raise ValidationError('The released message changed.')
        SyntheticIssueMessage.objects.get_or_create(dispatch=dispatch,defaults={
            'reference':'issue-'+dispatch.operation.hex,'payload':dispatch.payload,'sha256':dispatch.sha256,
            'delivered':True,'delivered_at':Now(),'observed_at':Now()})
        return self.lookup(dispatch)

    def reconcile(self,dispatch):
        """The isolated provider seals an absent operation against a later effect."""
        from apps.pmo.issue_message_models import IssueMessageAttempt, SyntheticIssueMessage
        from django.db.models.functions import Now
        if not IssueMessageAttempt.objects.filter(dispatch=dispatch).exists():
            raise ValidationError('Reconcile an original started message operation.')
        case=dispatch.review.draft.issue.case
        destination=dispatch.payload['recipient']
        if (dispatch.route.get('mode')!='synthetic_mailbox' or not case.synthetic or
                not (destination.casefold().endswith('.invalid') or destination.startswith('synthetic:')) or
                digest(dispatch.payload)!=dispatch.sha256):
            raise ValidationError('Use the original isolated sample delivery contract.')
        # Both deliver and reconcile compete on the same unique provider operation.
        # Whichever persists first is the terminal result returned to both callers.
        SyntheticIssueMessage.objects.get_or_create(dispatch=dispatch,defaults={
            'reference':'issue-absent-'+dispatch.operation.hex,'payload':dispatch.payload,
            'sha256':dispatch.sha256,'delivered':False,'delivered_at':None,'observed_at':Now()})
        return self.lookup(dispatch)

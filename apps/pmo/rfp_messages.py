"""Human release and receipt-only recovery of reviewed bid follow-ups."""
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from adapters.rfp_followup import SyntheticBidMailbox, verify_evidence
from apps.core.evidence_access import restricted
from apps.core.models import ClientContactRevision, Evidence
from apps.core.read_observation import read_observation
from apps.core.services import bump, event, lock_case
from apps.documents.contracts import digest
from apps.identity.services import require
from apps.policy.services import active_component, decision_authority, reference_values

from . import rfp_followup as drafts
from .models import RFPFollowupAttempt, RFPFollowupCursor, RFPFollowupDispatch, RFPFollowupReceipt
from .services import subject


def route(actor,case,key):
    require(actor,case,'rfp.submit')
    cfg=active_component('D11.adapter_configuration_refs',case)
    candidates=[value for value in reference_values(cfg) if value.get('kind')=='rfp_followup' and value['key']==key]
    if len(candidates)!=1:
        raise ValidationError('Choose one reviewed customer follow-up route.')
    value=candidates[0]
    contact=ClientContactRevision.objects.filter(case=case,purpose='project',customer='').order_by('-number').first()
    if contact is None or contact.pk!=value['contact_id']:
        raise ValidationError('Review the changed project contact before releasing a message.')
    for role in value['sender_roles']:
        try:
            decision_authority(actor,case,role)
            return cfg,value,contact
        except (PermissionDenied,ValidationError):
            continue
    raise PermissionDenied('A currently configured bid sender is required.')


@transaction.atomic
def reserve(actor,case_id,outcome_id,review_id,key,expected):
    case=lock_case(actor,case_id,'rfp.submit',expected)
    outcome=drafts.for_case(case,outcome_id)
    drafts.authorize(actor,case,outcome)
    run=drafts.latest_run(actor,case,outcome)
    if run is None:
        raise ValidationError('Review the exact follow-up wording first.')
    review=drafts.reviews(case,run).order_by('-pk').first()
    if review is None or review.pk!=review_id:
        raise ValidationError('Release the current human-reviewed message.')
    original=RFPFollowupDispatch.objects.filter(review=review).first()
    if original:
        if original.actor_id!=actor.pk or original.route['key']!=key:
            raise ValidationError('This message already has a different release.')
        return original
    if RFPFollowupDispatch.objects.filter(outcome__submission__response__rfp=outcome.submission.response.rfp,receipt__isnull=True).exists():
        raise ValidationError('Check the earlier message receipt before releasing another follow-up.')
    cfg,value,contact=route(actor,case,key)
    evidence=Evidence.objects.filter(case=case,pk=review.data['source'],kind=drafts.SOURCE_KIND).first()
    if evidence is None:
        raise ValidationError('The reviewed draft source is unavailable.')
    payload={'submission':outcome.submission_id,'outcome':outcome.pk,'recipient':contact.email,'body':evidence.body}
    dispatch=RFPFollowupDispatch.objects.create(review=review,outcome=outcome,configuration=cfg,contact=contact,
        source=evidence,actor=actor,payload=payload,sha256=digest(payload),route=value)
    event(actor,case,'rfp.followup_released',dispatch=dispatch.pk)
    bump(case)
    return dispatch


def check_current(dispatch,case):
    drafts.authorize(dispatch.actor,case,dispatch.outcome)
    cfg,value,contact=route(dispatch.actor,case,dispatch.route['key'])
    run=drafts.latest_run(dispatch.actor,case,dispatch.outcome)
    review=drafts.reviews(case,run).order_by('-pk').first() if run else None
    if (cfg.pk!=dispatch.configuration_id or value!=dispatch.route or contact.pk!=dispatch.contact_id or
            review is None or review.pk!=dispatch.review_id or digest(dispatch.payload)!=dispatch.sha256 or
            dispatch.source.body!=dispatch.payload['body']):
        raise ValidationError('Current message, contact or delivery authority changed. Check the original receipt.')


@read_observation
def pre_attempt_hold(actor, case, dispatch_id):
    """Read the original sender's current hold without claiming or checking delivery."""
    require(actor, case, 'case.read')
    require(actor, case, 'rfp.read')
    dispatch = RFPFollowupDispatch.objects.filter(
        pk=dispatch_id, actor=actor, outcome__submission__response__rfp__case=case,
        outcome__submission__response__rfp__case__synthetic=True,
        route__mode='synthetic_mailbox', attempt__isnull=True, receipt__isnull=True,
    ).select_related('actor', 'outcome', 'contact', 'source').first()
    if dispatch is None:
        return None
    try:
        check_current(dispatch, case)
    except PermissionDenied:
        return 'Delivery held before its first attempt. Review the current sender’s bid access.'
    except ValidationError:
        return 'Delivery held before its first attempt. Review the customer outcome, current wording and delivery route.'
    return None


def record(dispatch,actor,reference,delivered,evidence=None):
    if not isinstance(reference,str) or not reference.strip() or len(reference)>160 or type(delivered) is not bool:
        raise ValidationError('Enter the actual delivery result and receipt reference.')
    receipt=RFPFollowupReceipt.objects.filter(dispatch=dispatch).first()
    if receipt:
        if (receipt.reference,receipt.delivered)!=(reference,delivered):
            raise ValidationError('The original message already has a different receipt.')
        return receipt
    receipt=RFPFollowupReceipt.objects.create(dispatch=dispatch,reference=reference,delivered=delivered,evidence=evidence,actor=actor)
    event(actor,dispatch.outcome.submission.response.rfp.case,'rfp.followup_receipt',receipt=receipt.pk,dispatch=dispatch.pk)
    return receipt


@transaction.atomic
def confirm(actor,case_id,dispatch_id,evidence_id,reference,delivered,expected):
    case=lock_case(actor,case_id,'rfp.submit',expected)
    require(actor,case,'case.read')
    require(actor,case,'rfp.read')
    dispatch=RFPFollowupDispatch.objects.select_for_update().select_related('outcome__submission__response__rfp','source','actor','contact').filter(
        pk=dispatch_id,outcome__submission__response__rfp__case=case).first()
    if dispatch is None or dispatch.actor_id!=actor.pk or dispatch.route['mode']!='manual_evidence':
        raise ValidationError('Select your original manual customer message.')
    evidence=subject(case,evidence_id,'rfp_followup_receipt')
    if restricted(evidence):
        raise ValidationError('Choose available channel receipt evidence.')
    verify_evidence(dispatch,evidence,reference,delivered)
    return record(dispatch,actor,reference,delivered,evidence)


def run_once(dispatch_id=None,adapter=None,*,lookup_only=False):
    adapter=adapter or SyntheticBidMailbox()
    ready=RFPFollowupDispatch.objects.filter(route__mode='synthetic_mailbox',receipt__isnull=True)
    candidate=ready.filter(pk=dispatch_id).first() if dispatch_id else ready.order_by('pk').first()
    if candidate is None:
        return False
    with transaction.atomic():
        # Human release and receipt capture acquire the case before the dispatch.
        case=candidate.outcome.submission.response.rfp.case
        type(case).objects.select_for_update().get(pk=case.pk)
        query=RFPFollowupDispatch.objects.select_for_update(skip_locked=True,of=('self',)).filter(
            route__mode='synthetic_mailbox',receipt__isnull=True).select_related('outcome__submission__response__rfp__case','actor','contact','source')
        dispatch=query.filter(pk=candidate.pk).first()
        if dispatch is None:
            return False
        first=not RFPFollowupAttempt.objects.filter(dispatch=dispatch).exists()
        if first and lookup_only:
            return False
        if first:
            try:
                case=lock_case(dispatch.actor,case.pk,'rfp.submit')
                check_current(dispatch,case)
            except (ValidationError,PermissionDenied):
                return False
            RFPFollowupAttempt.objects.create(dispatch=dispatch)
    try:
        reference=adapter.lookup(dispatch)
        if reference is None and first:
            reference=adapter.deliver(dispatch)
        if reference:
            with transaction.atomic():
                RFPFollowupDispatch.objects.select_for_update().get(pk=dispatch.pk)
                record(dispatch,dispatch.actor,reference,True)
    except (ConnectionError,TimeoutError,OSError,ValidationError):
        pass
    return True


@transaction.atomic
def next_batch(limit=20):
    if type(limit) is not int or not 1<=limit<=100:
        raise ValueError('Choose a delivery batch between 1 and 100 messages.')
    cursor,_=RFPFollowupCursor.objects.get_or_create(name='sample_mailbox')
    cursor=RFPFollowupCursor.objects.select_for_update().get(pk=cursor.pk)
    unresolved=RFPFollowupDispatch.objects.filter(route__mode='synthetic_mailbox',receipt__isnull=True).order_by('pk')
    ids=list(unresolved.filter(pk__gt=cursor.last_dispatch_id).values_list('pk',flat=True)[:limit])
    if not ids:
        ids=list(unresolved.values_list('pk',flat=True)[:limit])
    cursor.last_dispatch_id=ids[-1] if ids else 0
    cursor.save(update_fields=['last_dispatch_id'])
    return ids

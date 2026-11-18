"""Immutable, authorised project facts and exact formal-registration bindings."""
from django.core.exceptions import ValidationError
from django.db import transaction
from apps.core.models import ClientContactRevision
from apps.core.evidence_access import public_evidence
from apps.core.services import event,bump
from apps.identity.services import require
from apps.documents.contracts import validate
from adapters.forecast import KEY
from adapters.engagement_details import planned_date,payload
from .engagement_models import EngagementDetails as Details,EngagementDetailsBinding as Binding


def proof_current(case,evidence_id):
    kinds=['engagement_source','engagement_assignment','engagement_registration','product_input','rfp_outcome','plan']
    if not public_evidence(case.evidence.filter(pk=evidence_id,kind__in=kinds)).exists():
        raise ValidationError('Same-project engagement or planning evidence required.')


def contact_current(case,contact_id):
    if contact_id is None:return None
    contact=ClientContactRevision.objects.select_related('actor').filter(
        pk=contact_id,case=case,purpose='project',customer='').first()
    if not contact or ClientContactRevision.objects.filter(case=case,purpose='project',customer='',number__gt=contact.number).exists():
        raise ValidationError('Choose the current project contact from this project.')
    for action in ['case.read','engagement.read','engagement.capture']:require(contact.actor,case,action)
    if not public_evidence(case.evidence.filter(pk=contact.evidence_id,kind__in=['engagement_source','policy_decision'])).exists():
        raise ValidationError('Current project-contact evidence required.')
    return contact


def current(case,details_id):
    from . import engagement as d
    details=Details.objects.select_related('actor').filter(pk=details_id,case=case).first()
    if not details or details.capture_id!=d.current_capture(case).pk:
        raise ValidationError('Details must match the current engagement source.')
    for action in ['case.read','engagement.read','engagement.capture']:require(details.actor,case,action)
    capture=details.capture
    for action in ['case.read','engagement.read','engagement.capture']:require(capture.actor,case,action)
    proof_current(case,capture.evidence_id);proof_current(case,details.evidence_id)
    if not public_evidence(case.evidence.filter(pk=details.plan_id,kind='plan')).exists():
        raise ValidationError('Retained planning evidence required.')
    contact=contact_current(case,details.contact_id)
    return details,contact


@transaction.atomic
def save(actor,case_id,reference,plan_id,evidence_id,key,planned_start=None,contact_id=None,checked=False,capture_id=None):
    from . import engagement as d
    case=d.scope(actor,case_id,'capture');capture=d.current_capture(case)
    if capture_id is not None and (type(capture_id) is not int or capture.pk!=capture_id):
        raise ValidationError('The engagement source changed. Review it before saving these details.')
    validate(KEY,key)
    if checked is not True:raise ValidationError('Confirm that these facts match the supporting document.')
    if (not isinstance(reference,str) or not reference.strip() or reference!=reference.strip() or len(reference)>120
            or any(ord(ch)<32 or ord(ch)==127 for ch in reference)):
        raise ValidationError('Enter the supplied project reference.')
    proof_current(case,evidence_id)
    if not public_evidence(case.evidence.filter(pk=plan_id,kind='plan')).exists():raise ValidationError('Select this project’s planning document.')
    contact_current(case,contact_id)
    values={'capture_id':capture.pk,'reference':reference,'plan_id':plan_id,'evidence_id':evidence_id,
            'planned_start':planned_date(planned_start),'contact_id':contact_id,'actor_id':actor.pk}
    prior=Details.objects.filter(case=case,operation_key=key).first()
    if prior:
        if any(getattr(prior,k)!=v for k,v in values.items()):raise ValidationError('This save key already identifies different project facts.')
        current(case,prior.pk);return prior
    result=Details.objects.create(case=case,operation_key=key,**values)
    event(actor,case,'engagement.details_recorded',details=result.pk)
    bump(case);return result


def check_registration(case,rules,value,plan_id,evidence_id,details_id):
    required=rules.get('required_details')
    if required is not None and any(v is None for v in required.values()):
        raise ValidationError('Decide whether a start date and project contact are required before formal registration. Saved facts and Planning can continue.')
    if details_id is None:
        if required is not None:raise ValidationError('Save and select the project details for this registration.')
        return None
    details,contact=current(case,details_id)
    if (details.reference,details.plan_id,details.evidence_id)!=(value,plan_id,evidence_id):
        raise ValidationError('Use the exact reference, planning document and supporting document in the saved details.')
    if required and required['planned_start'] and details.planned_start is None:raise ValidationError('A supported planned start date is required.')
    if required and required['client_contact'] and contact is None:raise ValidationError('A current project contact is required.')
    return details


def bound_current(case,registration,rules):
    binding=Binding.objects.filter(registration=registration).first()
    return check_registration(case,rules,registration.data['value'],registration.data['plan'],registration.evidence_id,
                              binding.details_id if binding else None)


def read(actor,case,details_id):
    for action in ['case.read','engagement.read']:require(actor,case,action)
    details,contact=current(case,details_id)
    return payload(details,contact)


def planning_context(actor,case):
    """Optional private handoff; a Planning-only reader receives no contact facts."""
    from django.core.exceptions import PermissionDenied
    require(actor,case,'planning.read')
    try:require(actor,case,'engagement.read')
    except PermissionDenied:return None
    latest=Details.objects.filter(case=case).order_by('-pk').first()
    if latest is None:return None
    try:return read(actor,case,latest.pk)
    except (PermissionDenied,ValidationError):return {'changed':True}


def planning_summary(actor,case):
    """Reports may feed shared agent records: retain coverage, never contact details."""
    context=planning_context(actor,case)
    if context is None or context.get('changed'):return context
    return {'status':'current','start_date':'recorded' if context['planned_start'] else 'unknown',
            'client_contact':'recorded' if context['client_contact'] else 'unknown'}

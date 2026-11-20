"""Bounded, currently authorised discovery of received bids requiring a PM."""

from django.contrib.auth import get_user_model
from django.core import signing
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from apps.core.evidence_access import public_evidence
from apps.core.services import lock_case
from apps.core.workbench import active, granted
from apps.identity.models import Grant
from apps.identity.services import require
from apps.policy.role_assignments import COMPONENT, eligibility
from apps.policy.services import active_component, reference_values

from . import rfp
from .models import RFPCase


PAGE_SIZE = 12
CURSOR_SALT = 'psl.rfp-assignment-queue.v1'
BID_READ_ACTIONS = ('case.read', 'rfp.read')
NOMINEE_ACTIONS = (*BID_READ_ACTIONS, 'rfp.prepare')


class StaleAssignment(ValidationError):
    pass


def assignment_scope(actor, case):
    for action in ('case.read', 'rfp.read', 'rfp.assign'):
        require(actor, case, action)
    assignments = reference_values(active_component(COMPONENT, case))
    matrix = reference_values(active_component('D05.decision_action_matrix', case))[0]
    allowed = set(matrix.get('rfp', {}).get('assignment_roles', []))
    nomination = eligibility(case, assignments, actor.pk, active=actor.is_active)
    roles = sorted(allowed.intersection(nomination['roles'])) if nomination['eligible_role_bundle'] else []
    if not roles:
        raise PermissionDenied('A currently appointed bid assigner is required.')
    return roles, assignments


def assignment_state(bid):
    try:
        assignment = rfp.current_assignment(bid, metadata_only=True)
    except (ValidationError, PermissionDenied):
        return None, False
    reads = set(Grant.objects.filter(case=bid.case, user_id=assignment.pm_id, active=True,
                                    action__in=BID_READ_ACTIONS).values_list('action', flat=True))
    if reads != set(BID_READ_ACTIONS):
        return None, True
    return assignment, False


def bids():
    return RFPCase.objects.filter(current_intake__isnull=False, rfpdisposition__isnull=True).select_related(
        'case', 'current_intake').defer('current_intake__note')


def page(actor, cursor=None, *, page_size=PAGE_SIZE):
    active(actor)
    if type(page_size) is not int or not 1 <= page_size <= PAGE_SIZE:
        raise ValidationError('Choose a bounded page of bids.')
    query = bids().filter(case__in=granted(actor, ('rfp.read', 'rfp.assign')))
    if cursor:
        try:
            if not isinstance(cursor, str) or len(cursor) > 1024:
                raise ValueError
            claim = signing.loads(cursor, salt=CURSOR_SALT, max_age=3600)
            if (set(claim) != {'actor', 'before'} or claim['actor'] != actor.pk
                    or type(claim['before']) is not int or claim['before'] < 1):
                raise ValueError
        except (signing.BadSignature, ValueError, TypeError):
            raise ValidationError('This page link is invalid or expired. Open the first page again.') from None
        query = query.filter(pk__lt=claim['before'])

    window = list(query.order_by('-pk')[:page_size + 1])
    rows = []
    for bid in window[:page_size]:
        try:
            assignment_scope(actor, bid.case)
        except (PermissionDenied, ValidationError):
            continue
        assignment, owner_access_required = assignment_state(bid)
        if assignment is None:
            bid.owner_access_required = owner_access_required
            rows.append(bid)
    next_cursor = (signing.dumps({'actor': actor.pk, 'before': window[page_size - 1].pk}, salt=CURSOR_SALT)
                   if len(window) > page_size else None)
    return {'rows': rows, 'next_cursor': next_cursor, 'checked': min(len(window), page_size)}


def nominees(case, records):
    ids = {record['user_id'] for record in records if record['role'] == 'PM'}
    people = get_user_model().objects.filter(pk__in=ids, is_active=True).only('username', 'first_name', 'last_name', 'is_active')
    for action in NOMINEE_ACTIONS:
        people = people.filter(pk__in=Grant.objects.filter(case=case, action=action, active=True).values('user_id'))
    return [person for person in people.order_by('first_name', 'last_name', 'username')
            if eligibility(case, records, person.pk, active=True)['eligible_role_bundle']]


def source_choices(bid):
    sources = public_evidence(bid.case.evidence.all()).only('id', 'kind', 'version')
    recent = list(sources.order_by('-pk').values_list('pk', flat=True)[:25])
    return sources.filter(pk__in={*recent, bid.current_intake.evidence_id}).order_by('-pk')


@transaction.atomic
def assign(actor, case_id, intake_id, candidate, role, evidence_id, reason, expected):
    if type(expected) is not int or expected < 1 or type(intake_id) is not int or intake_id < 1:
        raise ValidationError('Choose the current received bid.')
    case = lock_case(actor, case_id, 'rfp.assign')
    assignment_scope(actor, case)
    bid = bids().filter(case=case, current_intake_id=intake_id).first()
    if case.revision != expected or bid is None or assignment_state(bid)[0] is not None:
        raise StaleAssignment('The received bid or its current assignment changed. Open it again.')
    for action in NOMINEE_ACTIONS:
        require(candidate, case, action)
    if not public_evidence(case.evidence.filter(pk=evidence_id)).exists():
        raise ValidationError('Choose exact available assignment evidence from this workspace.')
    return rfp.assign(actor, case.pk, candidate, role, evidence_id, reason, expected)

"""Bounded readback of the exact native decisions that sent a bid for changes."""

from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import F

from apps.core.read_observation import read_observation
from apps.identity.services import active_case_grants
from apps.pmo.models import CommercialDecision, RFPReview

from . import factory_rfp


READ_ACTIONS = {'case.read', 'factory.read', 'rfp.read'}
HISTORY_LIMIT = 10


@read_observation
def project(actor, work):
    if work.definition != factory_rfp.DEFINITION:
        raise ValidationError('An exact bid response work item is required.')
    grants = {action for _, action in active_case_grants(
        actor, [work.case_id], actions=READ_ACTIONS | {'commercial.read'})}
    if not READ_ACTIONS <= grants:
        raise PermissionDenied('Current bid work access is required.')

    root = factory_rfp.subject(work)
    fields = ('pk', 'role', 'note', 'created_at', 'response_id', 'response_number')
    reviews = RFPReview.objects.filter(response__rfp=root, verdict='return').order_by('-created_at', '-pk')
    rows = [dict(row, kind='response') for row in reviews.values(
        *fields, response_number=F('response__number'))[:HISTORY_LIMIT + 1]]
    if 'commercial.read' in grants:
        decisions = CommercialDecision.objects.filter(
            revision__dossier__case_id=work.case_id, revision__rfpresponse__rfp=root,
            verdict='return',
        ).order_by('-created_at', '-pk')
        rows.extend(dict(row, kind='costing') for row in decisions.values(
            *fields, response_id=F('revision__rfpresponse__pk'),
            response_number=F('revision__rfpresponse__number'), costing_number=F('revision__number'),
        )[:HISTORY_LIMIT + 1])
    rows.sort(key=lambda row: (row['created_at'], row['kind'], row['pk']), reverse=True)
    if not rows:
        return {'current': None, 'history': [], 'earlier': False}

    current = None
    if (root.current_response_id == rows[0]['response_id'] and not work.cancel_requested and
            work.status not in {'verified', 'cancelled', 'followup_needed'}):
        selected = factory_rfp.response_for(work)
        if selected and selected.pk == root.current_response_id:
            current = rows.pop(0)
    return {'current': current, 'history': rows[:HISTORY_LIMIT], 'earlier': len(rows) > HISTORY_LIMIT}

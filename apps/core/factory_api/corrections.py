"""Typed successor source corrections over existing native workflow services."""
from django.http import Http404

from apps.workflows import (
    factory_archive, factory_bu, factory_change, factory_closure, factory_emergency, factory_escalation,
    factory_forecast, factory_go_live, factory_handover, factory_leadership, factory_ledger, factory_minutes,
    factory_payroll, factory_ppe, factory_reporting, factory_rfp, factory_schedules,
)
from apps.workflows.factory_invoice_review import comment

from .http import ID, REVISION, TEXT, endpoint, obj
from .intake import STARTS
from .reviews import VERSIONS
from .work import FINANCE_INVOICE, WORK_RESULT, bound_work, review_task, result


REASON = {**TEXT, 'maxLength': 2000}
CORRECTIONS = {
    line.DEFINITION: line.correct for line in (
        factory_archive, factory_bu, factory_change, factory_closure, factory_emergency, factory_escalation,
        factory_forecast, factory_go_live, factory_handover, factory_leadership, factory_ledger, factory_minutes,
        factory_payroll, factory_ppe, factory_reporting, factory_rfp, factory_schedules,
    )
}


def correction_fields(line):
    fields = dict(STARTS[line][1]['properties'])
    fields.pop('dossier_id', None)
    if line == factory_forecast.DEFINITION:
        fields['selected'] = fields.pop('value')
    return fields


CORRECTION = {'oneOf': [
    obj({**VERSIONS, 'line': {'const': line}, 'reason': REASON, 'source': obj(correction_fields(line))})
    for line in CORRECTIONS
]}


@endpoint(method='POST', request=CORRECTION, response=WORK_RESULT,
          summary='Correct the current native workflow source using a typed successor and reviewed reason')
def correct(http, work_id, *, body):
    work = bound_work(http.user, work_id)
    if work.definition != body['line']:
        raise Http404
    service = CORRECTIONS[work.definition]
    service(http.user, work.pk, body['expected_revision'], body['case_revision'], **body['source'], reason=body['reason'])
    work.refresh_from_db(fields=['status', 'revision', 'lease_until'])
    return result(work)


@endpoint(method='POST', request=obj({'revision': REVISION, 'body': REASON}), response=obj({'comment_id': ID}),
          summary='Add a permitted comment to an exact current invoice review without recording a verdict')
def invoice_comment(http, task_id, *, body):
    work, _ = review_task(http.user, task_id)
    if work.definition != FINANCE_INVOICE:
        raise Http404
    event = comment(http.user, work.pk, task_id, body['revision'], body['body'])
    return {'comment_id': event.pk}

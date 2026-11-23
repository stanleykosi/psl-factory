from django.http import Http404

from apps.workflows import (
    factory_bu, factory_change, factory_closure, factory_emergency, factory_escalation, factory_go_live,
    factory_leadership, factory_minutes, factory_payroll, factory_ppe, factory_reporting, factory_schedules,
)
from apps.workflows.factory_rfp_views import human_command as rfp_command

from .http import ID, REVISION, TEXT, choice, endpoint, nullable, obj
from .work import WORK_RESULT, bound_work, result


DOCUMENTS = {
    'pmo-minutes/v1': factory_minutes.review_outward_draft,
    'pmo-weekly-report/v1': factory_reporting.review,
    'pmo-leadership-report/v1': factory_leadership.review,
    'pmo-escalation/v1': factory_escalation.review,
    'pmo-emergency/v1': factory_emergency.review,
    'pmo-change/v1': factory_change.review,
    'delivery-go-live/v1': factory_go_live.review,
    'delivery-closure/v1': factory_closure.review,
}
VERSIONS = {'expected_revision': REVISION, 'case_revision': REVISION}
NOTE = {'type': 'string', 'maxLength': 4000}
VERDICT = choice('approve', 'return', 'reject')
KEY = {**TEXT, 'maxLength': 100}


def review_schema(kind, fields):
    return obj({'kind': {'type': 'string', 'const': kind}, **VERSIONS, **fields})


REVIEWS = {'oneOf': [
    review_schema('document', {'version_id': ID, 'verdict': VERDICT, 'note': NOTE}),
    review_schema('bid', {'subject': choice('response', 'commercial', 'document'),
                          'target_id': ID, 'role': {**TEXT, 'maxLength': 64}, 'verdict': VERDICT,
                          'evidence_id': nullable(ID), 'note': NOTE}),
    review_schema('closure', {'version_id': ID, 'evidence_id': ID, 'verdict': VERDICT, 'note': NOTE}),
    review_schema('asset', {'target_id': ID, 'purpose': choice('register', 'basis', 'schedule'),
                            'verdict': choice('approve', 'return', 'reject', 'revoke'), 'evidence_id': ID, 'note': NOTE}),
    review_schema('schedule', {'target_id': ID, 'verdict': choice('approve', 'return', 'reject', 'revoke'),
                                'evidence_id': ID, 'note': NOTE}),
    review_schema('payroll', {'subject': choice('input', 'run'), 'subject_id': ID,
                              'verdict': choice('approve', 'return', 'revoke', factory_payroll.native.draft_matching.VERDICT),
                              'operation_key': KEY, 'evidence_id': ID, 'note': NOTE}),
    review_schema('business_unit', {'work_id': ID, 'purpose': {**TEXT, 'maxLength': 64},
                                    'verdict': choice('approve', 'return', 'revoke'), 'operation_key': KEY, 'evidence_id': ID}),
]}


@endpoint(method='POST', request=REVIEWS,
          response=obj({**WORK_RESULT['properties'], 'review_id': nullable(ID)}),
          summary='Record an independent review on the exact native workflow subject')
def review(request, work_id, *, body):
    work = bound_work(request.user, work_id)
    args = (request.user, work.pk, body['expected_revision'], body['case_revision'])
    job, verdict = body['kind'], body['verdict']
    note = body.get('note', '')
    if job == 'document' and work.definition in DOCUMENTS:
        recorded = DOCUMENTS[work.definition](*args, body['version_id'], verdict, note)
    elif job == 'bid' and work.definition == 'rfp-response/v1':
        recorded = rfp_command(*args, body['subject'], body['target_id'], body['role'], verdict,
                               body['evidence_id'] or 0, note)
    elif job == 'closure' and work.definition == 'delivery-closure/v1':
        recorded = factory_closure.decide(*args, body['version_id'], verdict, body['evidence_id'], note)
    elif job == 'asset' and work.definition == 'finance-ppe/v1':
        recorded = factory_ppe.review(*args, body['target_id'], body['purpose'], verdict, body['evidence_id'], note)
    elif job == 'schedule' and work.definition == 'finance-schedules/v1':
        recorded = factory_schedules.review(*args, body['target_id'], verdict, body['evidence_id'], note)
    elif job == 'payroll' and work.definition == 'finance-payroll/v1':
        recorded = factory_payroll.human_action(*args, 'review', {
            'kind': body['subject'], **{key: body[key] for key in ('subject_id', 'verdict', 'operation_key', 'evidence_id', 'note')},
        })
    elif job == 'business_unit' and work.definition == 'finance-bu/v1':
        recorded = factory_bu.human_action(*args, 'review', {
            key: body[key] for key in ('work_id', 'purpose', 'verdict', 'operation_key', 'evidence_id')
        })
    else:
        raise Http404
    work.refresh_from_db(fields=['status', 'revision', 'lease_until'])
    return {**result(work), 'review_id': getattr(recorded, 'pk', None)}


@endpoint(method='POST', request=obj({'publication_id': ID}), response=obj({'receipt_id': ID, 'publication_id': ID}),
          summary='Record your own receipt for the exact current aggregate publication')
def acknowledge_aggregate(request, work_id, *, body):
    work = bound_work(request.user, work_id)
    service = {'finance-payroll/v1': factory_payroll, 'finance-bu/v1': factory_bu}.get(work.definition)
    if not service:
        raise Http404
    receipt = service.human_action(request.user, work.pk, work.revision, work.case.revision, 'receive', body)
    return {'receipt_id': receipt.pk, 'publication_id': body['publication_id']}

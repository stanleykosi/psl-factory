"""Exact bid portal receipt and reviewed customer follow-up."""
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import Http404
from django.shortcuts import get_object_or_404

from apps.core.evidence_access import public_evidence
from apps.documents import controlled
from apps.identity.services import require
from apps.pmo import rfp_followup, rfp_messages, rfp_portal
from apps.pmo.models import RFPDocumentBinding, RFPFollowupDispatch, RFPPortalReceipt
from apps.policy.services import resolve, reference_values
from apps.workflows import factory_rfp

from .commands import require_line
from .http import BOOLEAN, DATETIME, ID, REVISION, TEXT, Problem, array, choice, endpoint, nullable, obj


RECEIPT = obj({'id': ID, 'submission_id': ID, 'reference': TEXT, 'submitted_at': DATETIME, 'late': BOOLEAN})
PROOF = obj({'id': ID, 'version': ID})
MODE = choice('synthetic_mailbox', 'manual_evidence')


def portal_context(actor, work_id):
    work = require_line(actor, work_id, factory_rfp.DEFINITION)
    for action in ('rfp.read', 'rfp.submit', 'document.read'):
        require(actor, work.case, action)
    version = factory_rfp.review_document(work)
    if version is None:
        raise Http404
    binding = get_object_or_404(RFPDocumentBinding, version=version, response__rfp=factory_rfp.subject(work),
                                snapshot__route__method=rfp_portal.METHOD)
    return work, version, binding


def receipt_payload(receipt):
    submission = receipt.submission
    return {'id': receipt.pk, 'submission_id': submission.pk, 'reference': receipt.reference,
            'submitted_at': submission.submitted_at, 'late': submission.late}


@endpoint(response=obj({
    'case_revision': REVISION, 'version_id': ID, 'ready': BOOLEAN, 'hold': nullable(TEXT),
    'receipt': nullable(RECEIPT), 'proofs': array(PROOF, limit=25),
}), summary='Read exact portal submission receipt or the reviewed pack and eligible receipt proof')
def portal(http, work_id):
    work, version, binding = portal_context(http.user, work_id)
    receipt = RFPPortalReceipt.objects.filter(submission__version=version).select_related('submission').first()
    ready, hold = False, None
    if not receipt:
        try:
            controlled.current_version(work.case, version.pk)
            rfp_portal.sender(http.user, version)
            ready = bool(controlled.validate_review(work.case, version))
            if ready:
                rfp_portal.exact_file(binding, new=True)
            else:
                hold = 'The client pack needs its final independent approval.'
        except (PermissionDenied, ValidationError):
            ready = False
            hold = 'The exact client pack and current sender authority need review.'
    proofs = public_evidence(work.case.evidence.filter(kind='rfp_portal_receipt')).order_by('-pk')
    return {'case_revision': work.case.revision, 'version_id': version.pk, 'ready': ready, 'hold': hold,
            'receipt': receipt_payload(receipt) if receipt else None,
            'proofs': [{'id': row.pk, 'version': row.version} for row in proofs.only('version')[:25]] if ready else []}


@endpoint(method='POST', request=obj({'case_revision': REVISION, 'version_id': ID, 'evidence_id': ID,
                                     'attestation': {**TEXT, 'maxLength': 4000}}),
          response=RECEIPT, status=201, summary='Record the actual client portal receipt for the exact approved bid pack')
def record_portal(http, work_id, *, body):
    work, version, _ = portal_context(http.user, work_id)
    if body['version_id'] != version.pk:
        raise Problem(409, 'stale_version', 'Reload the exact approved pack.')
    submission = rfp_portal.record(http.user, work.case_id, version.pk, body['evidence_id'],
                                   body['attestation'], body['case_revision'])
    return receipt_payload(submission.portal_receipt)


MESSAGE = obj({'id': ID, 'review_id': ID, 'mode': MODE, 'receipt_reference': nullable(TEXT),
               'delivered': nullable(BOOLEAN)})
FOLLOWUP_RESULT = obj({'case_revision': REVISION, 'record_id': ID})


def followup_context(actor, work_id, outcome_id):
    work = require_line(actor, work_id, factory_rfp.DEFINITION)
    outcome = rfp_followup.for_case(work.case, outcome_id)
    if outcome.submission.response.rfp_id != factory_rfp.subject(work).pk:
        raise Http404
    rfp_followup.authorize(actor, work.case, outcome)
    return work, outcome


@endpoint(response=obj({
    'case_revision': REVISION, 'outcome_id': ID, 'remind_at': nullable(DATETIME),
    'draft_id': nullable(ID), 'review_id': nullable(ID), 'message': nullable(TEXT),
    'routes': array(obj({'key': TEXT, 'mode': MODE}), limit=30), 'history': array(MESSAGE, limit=20),
    'receipt_proofs': array(PROOF, limit=25),
}), summary='Read the assigned project manager’s current follow-up, reviewed routes and receipt history')
def followup(http, work_id, outcome_id):
    actor = http.user
    work, outcome = followup_context(actor, work_id, outcome_id)
    case = work.case
    panel = rfp_followup.panel(actor, case, outcome) or {}
    review, run = panel.get('reviewed'), panel.get('run')
    routes = []
    if review:
        try:
            require(actor, case, 'rfp.submit')
            config = resolve('D11.adapter_configuration_refs', case)
            candidates = reference_values(config.configuration) if config.status == 'ACTIVE' else []
            for candidate in [value for value in candidates if value.get('kind') == 'rfp_followup'][:30]:
                try:
                    _, route, _ = rfp_messages.route(actor, case, candidate['key'])
                except (PermissionDenied, ValidationError):
                    continue
                routes.append({'key': route['key'], 'mode': route['mode']})
        except PermissionDenied:
            pass
    history = []
    for row in RFPFollowupDispatch.objects.filter(outcome=outcome, actor=actor).select_related('receipt').order_by('-pk')[:20]:
        receipt = getattr(row, 'receipt', None)
        history.append({'id': row.pk, 'review_id': row.review_id, 'mode': row.route['mode'],
                        'receipt_reference': receipt.reference if receipt else None,
                        'delivered': receipt.delivered if receipt else None})
    proofs = (public_evidence(case.evidence.filter(kind='rfp_followup_receipt')).only('version').order_by('-pk')[:25]
              if history else [])
    return {'case_revision': case.revision, 'outcome_id': outcome.pk, 'remind_at': outcome.remind_at,
            'draft_id': run.pk if run else None, 'review_id': review.pk if review else None, 'message': panel.get('text'),
            'routes': routes, 'history': history, 'receipt_proofs': [{'id': row.pk, 'version': row.version} for row in proofs]}


FOLLOWUP = {'oneOf': [
    obj({'action': {'const': 'draft'}, 'case_revision': REVISION}),
    obj({'action': {'const': 'review'}, 'case_revision': REVISION, 'draft_id': ID, 'prior_review_id': nullable(ID),
         'message': {**TEXT, 'maxLength': 4000}}),
    obj({'action': {'const': 'send'}, 'case_revision': REVISION, 'review_id': ID, 'route': TEXT}),
    obj({'action': {'const': 'confirm'}, 'case_revision': REVISION, 'dispatch_id': ID, 'evidence_id': ID,
         'reference': {**TEXT, 'maxLength': 160}, 'delivered': BOOLEAN}),
]}


@endpoint(method='POST', request=FOLLOWUP, response=FOLLOWUP_RESULT,
          summary='Prepare, review, release or confirm an exact bid follow-up')
def followup_command(http, work_id, outcome_id, *, body):
    actor = http.user
    work, outcome = followup_context(actor, work_id, outcome_id)
    case, revision = work.case, body['case_revision']
    action = body['action']
    if action == 'draft':
        result = rfp_followup.draft(actor, case.pk, outcome.pk, revision)
    elif action == 'review':
        result = rfp_followup.review(actor, case.pk, outcome.pk, body['draft_id'], body['message'],
                                    body['prior_review_id'] or 0, revision)
    elif action == 'send':
        result = rfp_messages.reserve(actor, case.pk, outcome.pk, body['review_id'], body['route'], revision)
    else:
        dispatch = get_object_or_404(RFPFollowupDispatch, pk=body['dispatch_id'], outcome=outcome)
        result = rfp_messages.confirm(actor, case.pk, dispatch.pk, body['evidence_id'], body['reference'],
                                      body['delivered'], revision)
    case.refresh_from_db(fields=['revision'])
    return {'case_revision': case.revision, 'record_id': result.pk}

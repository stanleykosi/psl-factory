from django.http import Http404
from django.urls import reverse
from django.utils.dateparse import parse_date, parse_datetime

from apps.identity.services import require
from apps.workflows import factory_minutes, factory_rfp, factory_rfp_submission_pack as submission_pack
from apps.workflows.factory_rfp_views import human_command

from .http import BOOLEAN, DATETIME, ID, REVISION, TEXT, choice, endpoint, nullable, obj
from .reviews import VERSIONS
from .work import WORK_RESULT, bound_work, result


def require_line(actor, work_id, definition):
    work = bound_work(actor, work_id)
    if work.definition != definition:
        raise Http404
    return work


@endpoint(method='POST', request=obj({**VERSIONS, 'minutes': factory_minutes.FIELDS, 'extraction_id': nullable(ID)}),
          response=WORK_RESULT, summary='Confirm minutes and human-attributed actions against the selected notes')
def confirm_minutes(request, work_id, *, body):
    work = require_line(request.user, work_id, factory_minutes.DEFINITION)
    factory_minutes.confirm(request.user, work.pk, body['expected_revision'], body['case_revision'],
                            body['minutes'], body['extraction_id'])
    work.refresh_from_db(fields=['status', 'revision', 'lease_until'])
    return result(work)


@endpoint(method='POST', request=obj({**VERSIONS, 'version_id': ID}), response=WORK_RESULT,
          summary='Request an independent review of the exact outward minutes')
def request_minutes_review(request, work_id, *, body):
    work = require_line(request.user, work_id, factory_minutes.DEFINITION)
    factory_minutes.request_outward_review(request.user, work.pk, body['expected_revision'], body['case_revision'],
                                           body['version_id'])
    work.refresh_from_db(fields=['status', 'revision', 'lease_until'])
    return result(work)


PACK = obj({'pack_id': ID, 'number': REVISION, 'cover_note': {'type': 'string'}, 'document_version_id': nullable(ID),
            'decision': nullable(obj({'label': TEXT, 'created_at': DATETIME, 'document_number': REVISION,
                                      'note': nullable({'type': 'string'})})),
            'django_url': TEXT})


@endpoint(response=PACK, summary='Read the exact current bid pack and permitted review readback')
def bid_pack(request, work_id):
    work = require_line(request.user, work_id, factory_rfp.DEFINITION)
    require(request.user, work.case, 'document.read')
    response = factory_rfp.response_for(work)
    document = factory_rfp.review_document(work)
    data = submission_pack.panel(request.user, work, response, document=document)
    pack = data.get('submission_pack')
    if pack is None:
        raise Http404
    # A ready review URL and the latest exact decision refer to the same current pack.
    bound = (document and document.document.current_id == document.pk
             and document.rfpdocumentbinding.snapshot.get('submission_pack') == pack.pk)
    return {'pack_id': pack.pk, 'number': pack.number, 'cover_note': pack.cover_note,
            'document_version_id': document.pk if bound else None,
            'decision': data['submission_pack_decision'],
            'django_url': reverse('factory_invoice_decision', args=[work.pk])}


@endpoint(method='POST', request=obj({
    **VERSIONS, 'response_id': ID, 'base_pack_id': nullable(ID), 'cover_note': {'type': 'string', 'maxLength': 4000},
    'file_extension': {'type': 'string', 'maxLength': 16}, 'file_count': nullable({'type': 'integer', 'minimum': 1, 'maximum': 2**31 - 1}),
    'file_size_rule': choice('', *submission_pack.packs.SIZE_RULES), 'file_size_bytes': nullable(ID),
}), response=obj({'pack_id': ID, 'number': REVISION, **WORK_RESULT['properties']}),
          summary='Save a versioned bid pack with the exact cover note and customer file requirements')
def save_bid_pack(request, work_id, *, body):
    work = require_line(request.user, work_id, factory_rfp.DEFINITION)
    form = submission_pack.SubmissionPackForm({
        'pack-target': body['response_id'], 'pack-base': body['base_pack_id'] or 0,
        **{'pack-' + field: body[field] for field in submission_pack.packs.FIELDS},
    }, prefix='pack')
    if not form.is_valid():
        from django.core.exceptions import ValidationError

        raise ValidationError('Review the cover note and the supplied file requirements.')
    pack = submission_pack.record(request.user, work.pk, body['expected_revision'], body['case_revision'], form.cleaned_data)
    work.refresh_from_db(fields=['status', 'revision', 'lease_until'])
    return {'pack_id': pack.pk, 'number': pack.number, **result(work)}


@endpoint(method='POST', request=obj({**VERSIONS, 'pack_id': ID, 'version_id': ID}), response=WORK_RESULT,
          summary='Send a particular bid pack version for independent review')
def request_bid_review(request, work_id, *, body):
    work = require_line(request.user, work_id, factory_rfp.DEFINITION)
    submission_pack.send_for_review(request.user, work.pk, body['expected_revision'], body['case_revision'],
                                    body['pack_id'], body['version_id'])
    work.refresh_from_db(fields=['status', 'revision', 'lease_until'])
    return result(work)


@endpoint(method='POST', request=obj({
    **VERSIONS, 'submission_id': ID, 'verdict': choice('won', 'lost', 'pending', 'unknown'), 'observed_at': DATETIME,
    'role': {**TEXT, 'maxLength': 64}, 'evidence_id': ID, 'note': {'type': 'string', 'maxLength': 4000},
    'selection_packet': {**TEXT, 'maxLength': 256}, 'selection_acknowledged': BOOLEAN,
    'award_amount': {**TEXT, 'maxLength': 64}, 'award_currency': {**TEXT, 'maxLength': 8},
    'customer_expected_on': {'type': 'string', 'format': 'date'}, 'followup_on': {'type': 'string', 'format': 'date'},
    'remind_at': DATETIME, 'loss_reason_key': {**TEXT, 'maxLength': 100}, 'loss_catalog_id': ID,
    'debrief_version_id': ID,
}, optional=('selection_packet', 'selection_acknowledged', 'award_amount', 'award_currency',
             'customer_expected_on', 'followup_on', 'remind_at', 'loss_reason_key', 'loss_catalog_id',
             'debrief_version_id')), response=WORK_RESULT,
    summary='Record an observed customer outcome against the exact submitted bid')
def bid_outcome(request, work_id, *, body):
    work = require_line(request.user, work_id, factory_rfp.DEFINITION)
    selection = None
    if body.get('selection_acknowledged'):
        selection = {'packet': body.get('selection_packet', ''), 'acknowledged': True}
    human_command(
        request.user, work.pk, body['expected_revision'], body['case_revision'], 'outcome',
        body['submission_id'], body['role'], body['verdict'], body['evidence_id'], body['note'],
        parse_datetime(body['observed_at']), selection,
        followup_on=parse_date(body['followup_on']) if 'followup_on' in body else None,
        award_amount=body.get('award_amount'), award_currency=body.get('award_currency'),
        customer_expected_on=parse_date(body['customer_expected_on']) if 'customer_expected_on' in body else None,
        remind_at=parse_datetime(body['remind_at']) if 'remind_at' in body else None,
        loss_reason_key=body.get('loss_reason_key', ''), loss_catalog_id=body.get('loss_catalog_id'),
        debrief_version_id=body.get('debrief_version_id'),
    )
    work.refresh_from_db(fields=['status', 'revision', 'lease_until'])
    return result(work)

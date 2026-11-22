"""Exact meeting confirmation and publication readback for the minutes screen."""
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator

from apps.core.evidence_access import public_evidence
from apps.core.read_budget import limit_queries
from apps.documents.models import PublicationJob
from apps.identity.services import active_case_grants
from apps.pmo.models import ActionItem, MeetingActionLink
from apps.workflows import factory_minutes
from apps.workflows.factory_minutes_forms import suggestion_rows
from apps.workflows.models import HumanTask

from .commands import require_line
from .http import BOOLEAN, DATETIME, ID, TEXT, array, choice, endpoint, nullable, obj
from .project_operations import ACTION, action_payload
from .reviews import VERSIONS
from .work import PAGE, WORK_RESULT, page_number, result


@endpoint(response=obj({
    **VERSIONS, 'source_head_id': ID, 'notes_evidence_id': ID, 'predecessor_id': nullable(ID),
    'extraction_id': nullable(ID), 'can_confirm': BOOLEAN, 'confirmed_meeting_version_id': nullable(ID),
    'suggestions': array(obj({'key': TEXT, 'kind': choice('decision', 'action'), 'quote': TEXT, 'evidence_id': ID})),
    'document': nullable(obj({'version_id': ID, 'audience': choice('internal', 'client'),
        'can_request_review': BOOLEAN,
        'preview': array(obj({'heading': TEXT, 'text': {'type': 'string'}}))})),
    'delivery': nullable(obj({'job_id': ID, 'state': TEXT, 'recipients': array(obj({
        'name': TEXT, 'status': TEXT, 'receipt_id': nullable(ID), 'recorded_at': nullable(DATETIME),
    }))})),
}), summary='Read current minutes citations, confirmation, exact document and original recipient receipts')
def detail(request, work_id):
    actor = request.user
    work = require_line(actor, work_id, factory_minutes.DEFINITION)
    with limit_queries(250):
        data, notes, _ = factory_minutes.source(work, actor, False)
        grants = {action for _, action in active_case_grants(actor, [work.case_id])}
        extraction = factory_minutes.extraction(work)
        confirmation = factory_minutes.confirmation(work)
        active = not work.cancel_requested and work.status not in ('cancelled', 'followup_needed')
        answer = {'expected_revision': work.revision, 'case_revision': work.case.revision,
                  'source_head_id': work.source_head_id, 'notes_evidence_id': notes.pk,
                  'predecessor_id': data['meeting_version_id'], 'extraction_id': extraction.pk if extraction else None,
                  'can_confirm': active and not confirmation and 'meeting.record' in grants,
                  'confirmed_meeting_version_id': confirmation.data['meeting_version'] if confirmation else None,
                  'suggestions': [{'key': row['key'], 'kind': row['label'].lower(), 'quote': row['quote'],
                                   'evidence_id': notes.pk} for row in suggestion_rows(extraction, notes.pk)],
                  'document': None, 'delivery': None}
        if 'document.read' not in grants:
            return answer
        try:
            binding = factory_minutes.current_document(work, actor)
        except (PermissionDenied, ValidationError):
            return answer
        version = binding.version
        answer['document'] = {'version_id': version.pk, 'audience': version.audience,
            'preview': [{'heading': section['heading'], 'text': section['text']}
                        for section in version.payload['sections']],
            'can_request_review': active and version.audience == 'client' and 'document.request_review' in grants
            and work.status != 'verified' and not HumanTask.objects.filter(case=work.case, version=version).exists()}
        job = PublicationJob.objects.filter(publication__factory_work=work, publication__factory_source_id=work.source_head_id,
                                           publication__version=version).first()
        if job:
            answer['delivery'] = {'job_id': job.pk, 'state': job.status, 'recipients': [
                {'name': row['recipient'], 'status': row['status'],
                 'receipt_id': row['receipt'].pk if row['receipt'] else None, 'recorded_at': row['at']}
                for row in factory_minutes.delivery_readback(work, actor)]}
    return answer


@endpoint(response=obj({**VERSIONS, 'items': array(ACTION, limit=25), 'linked_action_ids': array(ID, limit=50),
                        'next_page': nullable(PAGE)}), query={'page': PAGE},
          summary='Read actions eligible for minutes confirmation and the links retained from its predecessor')
def action_options(request, work_id):
    actor = request.user
    work = require_line(actor, work_id, factory_minutes.DEFINITION)
    case = work.case
    data, _, _ = factory_minutes.source(work, actor)
    grants = {action for _, action in active_case_grants(actor, [case.pk])}
    if 'meeting.record' not in grants:
        raise PermissionDenied
    proof = public_evidence(case.evidence.all()).values('pk')
    actions = ActionItem.objects.filter(case=case, current__evidence_id__in=proof).select_related('current__owner')
    bound = list(MeetingActionLink.objects.filter(meeting__versions__pk=data['meeting_version_id'],
        evidence_id__in=proof, item_id__in=actions.values('pk')).values_list('item_id', flat=True).distinct()[:50]) if data['meeting_version_id'] else []
    page = Paginator(actions.order_by('reference', 'pk'), 25).get_page(page_number(request))
    return {'expected_revision': work.revision, 'case_revision': case.revision,
            'items': [action_payload(case, item, item.current) for item in page], 'linked_action_ids': bound,
            'next_page': page.next_page_number() if page.has_next() and page.number < PAGE['maximum'] else None}


@endpoint(method='POST', request=obj({**VERSIONS, 'job_id': ID, 'action': choice('cancel', 'retry'),
    'reason': {**TEXT, 'maxLength': 4000}}), response=WORK_RESULT,
    summary='Operate an exact original minutes publication under current recovery authority')
def operate(request, work_id, *, body):
    work = require_line(request.user, work_id, factory_minutes.DEFINITION)
    work = factory_minutes.operate(request.user, work.pk, body['expected_revision'], body['case_revision'],
                                  body['job_id'], body['action'], body['reason'])
    return result(work)

from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils import timezone

from apps.agents import assistant, file_draft_reviews, upload_recovery, workflow_handoffs
from apps.agents.assistant_views import current_turns, open_conversation, owned_conversations
from apps.agents.models import AgentJob, CaseUpload
from apps.agents.upload_jobs import ROLES, authorize
from apps.agents.upload_views import queue_draft, upload_file
from apps.documents.contracts import digest
from apps.identity.services import require, visible_cases
from apps.pmo.gates import GATE_OWNERS

from .http import BOOLEAN, DATETIME, ID, TEXT, UUID, Problem, array, choice, endpoint, nullable, obj


PERSONA = choice(*assistant.PERSONAS)
ROLE = choice(*ROLES)
HASH = {'type': 'string', 'pattern': '^[a-f0-9]{64}$'}
STATUS = choice('queued', 'running', 'draft', 'reviewed', 'held', 'interrupted')
STRING = {'type': 'string'}
CONVERSATION = obj({'conversation_id': UUID, 'case_id': UUID, 'agent': PERSONA, 'updated_at': DATETIME,
                    'django_url': TEXT})
SOURCE = obj({'label': TEXT, 'django_url': TEXT})
TURN = obj({
    'id': UUID, 'question': TEXT, 'status': TEXT, 'answer': nullable(STRING), 'sources': array(SOURCE),
    'at': DATETIME, 'started_work_id': nullable(ID), 'draft_url': nullable(TEXT), 'transfer_url': nullable(TEXT),
})


def conversation_data(conversation):
    return {'conversation_id': conversation.pk, 'case_id': conversation.case_id, 'agent': conversation.persona,
            'updated_at': conversation.updated_at, 'django_url': reverse('assistant_thread', args=[conversation.pk])}


@endpoint(response=obj({'items': array(CONVERSATION, limit=25), 'as_of': DATETIME}),
          summary='List the current user’s accessible assistant conversations')
def conversations(request):
    rows = owned_conversations(request.user).order_by('-updated_at', '-pk')[:25]
    return {'items': [conversation_data(row) for row in rows], 'as_of': timezone.now()}


@endpoint(method='POST', request=obj({'agent': PERSONA, 'case_id': UUID, 'idempotency_key': UUID}),
          response=CONVERSATION, summary='Open an assistant conversation for this project and user')
def start_conversation(request, *, body):
    case = get_object_or_404(assistant.cases_for(request.user, body['agent']), pk=body['case_id'])
    return conversation_data(open_conversation(request.user, body['agent'], case, body['idempotency_key']))


@endpoint(response=obj({
    **CONVERSATION['properties'], 'messages': array(TURN, limit=30),
    'available_sources': array(obj({'key': HASH, **SOURCE['properties']})),
    'question_options': array(TEXT),
}), summary='Read current assistant answers and authorised evidence selections')
def conversation(request, conversation_id):
    row = get_object_or_404(owned_conversations(request.user), pk=conversation_id)
    sources, next_work = assistant.tool_context(row)
    payroll_only = assistant.payroll_report_only(row)
    turns = current_turns(request.user, row, sources, next_work, payroll_only)
    return {
        **conversation_data(row),
        'available_sources': [{'key': digest(item), 'label': item['label'], 'django_url': item['url']} for item in sources],
        'question_options': list(assistant.PAYROLL_REPORT_QUESTIONS) if payroll_only else [],
        'messages': [
            {'id': turn.pk, 'question': turn.question, 'at': turn.created_at,
             'status': 'source_changed' if turn.stale else turn.status,
             'answer': turn.answer if turn.status == 'answered' and not turn.stale else None,
             'sources': [{'label': item['label'], 'django_url': item['url']} for item in turn.sources]
             if turn.status == 'answered' and not turn.stale else [],
             'started_work_id': turn.started_work_id if getattr(turn, 'started_url', None) else None,
             'draft_url': getattr(turn, 'next_url', None), 'transfer_url': getattr(turn, 'transfer_url', None)}
            for turn in turns
        ],
    }


@endpoint(method='POST', request=obj({
    'text': {**TEXT, 'maxLength': 4000}, 'idempotency_key': UUID, 'source_keys': array(HASH, limit=5),
}, optional=('source_keys',)), response=obj({'message_id': UUID, 'status': TEXT}), status=202,
          summary='Queue an assistant question with currently authorised evidence')
def message(request, conversation_id, *, body):
    get_object_or_404(owned_conversations(request.user), pk=conversation_id)
    question = body['text'].strip()
    if not question:
        raise Problem(422, 'invalid_input', 'Enter a message.')
    turn = assistant.reserve(request.user, conversation_id, body['idempotency_key'], question, body.get('source_keys', []))
    return {'message_id': turn.pk, 'status': turn.status}


@endpoint(method='POST', request=obj({'agent': PERSONA}), response=CONVERSATION,
          summary='Transfer an exact assistant result to an authorised department assistant')
def transfer(request, turn_id, *, body):
    return conversation_data(assistant.transfer(request.user, turn_id, body['agent']))


FILE = obj({'upload_id': ID, 'name': TEXT, 'size': ID, 'sha256': HASH, 'download_url': TEXT})
DRAFT = obj({'pin': HASH, 'summary': TEXT, 'excerpts': array(TEXT), 'questions': array(STRING)})
JOB = obj({
    'job_id': ID, 'upload_id': ID, 'role': ROLE, 'status': STATUS, 'label': TEXT,
    'attempt': {'type': 'integer', 'minimum': 0}, 'draft': nullable(DRAFT), 'recovery_pin': nullable(HASH),
    'reviewed_evidence_id': nullable(ID), 'workflow_record_id': nullable(ID),
})


def file_data(upload):
    return {'upload_id': upload.pk, 'name': upload.name, 'size': upload.size, 'sha256': upload.sha256,
            'download_url': reverse('case_upload_download', args=[upload.case_id, upload.pk])}


def job_data(actor, job):
    authorize(actor, job.upload)
    progress = upload_recovery.describe(job)
    draft = None
    if job.status == 'draft' and file_draft_reviews.reviewable(job):
        draft = {'pin': file_draft_reviews.draft_digest(job), 'summary': job.result['summary'],
                 'excerpts': job.result['quotes'], 'questions': job.result['gaps']}
    return {'job_id': job.pk, 'upload_id': job.upload_id, 'role': job.role, 'status': job.status,
            'label': progress['label'], 'attempt': progress['attempt'], 'draft': draft,
            'recovery_pin': upload_recovery.pin(job) if progress['can_request_recovery'] else None,
            'reviewed_evidence_id': job.result.get('reviewed_evidence'), 'workflow_record_id': job.result.get('workflow_record')}


def owned_job(actor, case_id, job_id):
    job = get_object_or_404(AgentJob.objects.select_related('upload__case'), pk=job_id, actor=actor,
                            upload__case_id=case_id, upload__actor=actor)
    try:
        authorize(actor, job.upload)
    except PermissionDenied:
        raise Http404 from None
    return job


@endpoint(response=obj({'items': array(FILE, limit=50), 'jobs': array(JOB, limit=50),
                        'agents': array(obj({'key': ROLE, 'title': TEXT}))}),
          summary='List your private uploads and authorised file-agent work')
def uploads(request, case_id):
    case = get_object_or_404(visible_cases(request.user), pk=case_id)
    files = CaseUpload.objects.filter(case=case, actor=request.user).order_by('-pk')[:50]
    jobs, roles = [], []
    if case.synthetic:
        try:
            require(request.user, case, 'agent.extract')
        except PermissionDenied:
            pass
        else:
            jobs = [job_data(request.user, job) for job in AgentJob.objects.filter(
                upload__case=case, upload__actor=request.user, actor=request.user,
            ).select_related('upload__case').order_by('-pk')[:50]]
            roles = [{'key': key, 'title': values[0]} for key, values in ROLES.items()]
    return {'items': [file_data(item) for item in files], 'jobs': jobs, 'agents': roles}


@endpoint(method='POST', request=obj({'file': {'type': 'string', 'format': 'binary'}}),
          multipart=True, response=FILE, summary='Store a private file in the current case')
def upload(request, case_id):
    if request.content_type != 'multipart/form-data':
        raise Problem(415, 'unsupported_media_type', 'Send a multipart file upload.')
    case = get_object_or_404(visible_cases(request.user), pk=case_id)
    if set(request.FILES) != {'file'} or len(request.FILES.getlist('file')) != 1:
        raise Problem(422, 'invalid_input', 'Select one file.')
    return file_data(upload_file(request.user, case, request.FILES['file']))


@endpoint(method='POST', request=obj({'role': ROLE}), response=JOB, status=202,
          summary='Queue one of the eight file agents on an exact private upload')
def queue(request, case_id, upload_id, *, body):
    source = get_object_or_404(CaseUpload.objects.select_related('case'), pk=upload_id,
                               case_id=case_id, actor=request.user, case__in=visible_cases(request.user))
    return job_data(request.user, queue_draft(request.user, source, body['role']))


@endpoint(response=JOB, summary='Read your exact file-agent draft or current status')
def job(request, case_id, job_id):
    return job_data(request.user, owned_job(request.user, case_id, job_id))


@endpoint(method='POST', request=obj({'draft': HASH, 'summary': {**TEXT, 'maxLength': 4000},
                                     'gaps': array({**TEXT, 'maxLength': 1000}, limit=12),
                                     'note': {**TEXT, 'maxLength': 1000}}),
          response=JOB, summary='Save the human-reviewed version of the exact private draft')
def review(request, case_id, job_id, *, body):
    row = owned_job(request.user, case_id, job_id)
    file_draft_reviews.retain(request.user, row.upload.case, job_id, {**body, 'gaps': '\n'.join(body['gaps'])})
    row.refresh_from_db()
    return job_data(request.user, row)


@endpoint(method='POST', request=obj({'attempt_pin': HASH, 'reason': {**TEXT, 'maxLength': 500}, 'confirm': {'const': True}}),
          response=JOB, status=202, summary='Recover only the exact stopped file-agent attempt')
def recover(request, case_id, job_id, *, body):
    row = owned_job(request.user, case_id, job_id)
    return job_data(request.user, upload_recovery.retry(request.user, row.upload.case, str(job_id), body))


HANDOFF_FIELDS = {
    'A01': {}, 'A02': {},
    'A03': {'title': {**TEXT, 'maxLength': 240}, 'next_action': {**TEXT, 'maxLength': 1000}, 'owner': ID},
    'A04': {},
    'A05': {'start': {'type': 'string', 'format': 'date'}, 'end': {'type': 'string', 'format': 'date'}},
    'A06': {'occurred_at': DATETIME, 'purpose': {**TEXT, 'maxLength': 240}},
    'A07': {'candidate': ID, 'gate': choice(*GATE_OWNERS), 'external_ref': {**TEXT, 'maxLength': 240}},
    'A08': {},
}


@endpoint(method='POST', request={'oneOf': [
    obj({'role': {'type': 'string', 'const': role}, 'confirm': {'const': True}, **fields})
    for role, fields in HANDOFF_FIELDS.items()
]}, response=JOB, summary='Use a human-reviewed file draft in the native workflow')
def handoff(request, case_id, job_id, *, body):
    row = owned_job(request.user, case_id, job_id)
    if body['role'] != row.role:
        raise Http404
    values = {key: value for key, value in body.items() if key != 'role'}
    workflow_handoffs.consume(request.user, row.upload.case, job_id, values)
    row.refresh_from_db()
    return job_data(request.user, row)

"""Optional internal F35 clarification. Never disclosure approval or raw HR evidence."""
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone
from apps.core.services import event, bump
from apps.documents.contracts import digest, validate
from apps.identity.services import require
from apps.policy.services import active_component, reference_values
from apps.policy.hrfinance_validators import SCOPE_ROUTE
from apps.workflows.models import HumanTask, TaskEvent
from . import hrfinance as hr
from .hrfinance_models import HRReadSnapshot

PURPOSE = 'hr_scope_clarification_v1'
QUESTION = ('Confirm the minimum permitted scope for a new authorized export. '
            'Forbidden fields remain rejected and discarded. This question cannot approve '
            'disclosure or accept the rejected export; a proper minimal resubmission is required.')
REPLIES = ('minimum_scope_confirmed', 'current_contract_clarification_required')
REPLY_SCHEMA = {'type':'object','properties':{'reply':{'enum':list(REPLIES)},
                'outcome':{'const':'await_proper_minimal_resubmission'}},
                'required':['reply','outcome'],'additionalProperties':False}


def metadata_access(actor, case):
    if not get_user_model().objects.filter(pk=actor.pk,is_active=True).exists():
        raise PermissionDenied('Current active metadata reader required')
    for action in ('case.read', 'hrfinance.read'):require(actor, case, action)


def owner_access(actor, case):
    metadata_access(actor, case)
    require(actor, case, 'hrfinance.respond')
    return hr.authority(actor, case, 'respond')


def route(case):
    config = active_component(SCOPE_ROUTE, case)
    value = reference_values(config)[0]
    owner = get_user_model().objects.get(pk=value['owner_id'])
    authority = owner_access(owner, case)
    return config, owner, authority


def source(snapshot):
    # No accepted-snapshot reader and no access to payload, even for a rejection.
    if snapshot.status != 'rejected' or snapshot.manifest['findings'] != ['out_of_contract_fields']:
        raise ValidationError('Exact rejected out-of-contract snapshot required')
    approval = hr.authorized(snapshot.contract)
    if snapshot.manifest['authorization_id'] != approval.pk:
        raise ValidationError('Source authorization changed')
    if timezone.now() >= snapshot.retain_until or snapshot.contract.snapshots.filter(pk__gt=snapshot.pk).exists():
        raise ValidationError('Source expired or superseded; use the current source workflow')
    return approval


def packet(snapshot, config, owner, authority):
    approval = source(snapshot)
    return {'purpose':PURPOSE, 'snapshot_id':snapshot.pk, 'snapshot_hash':snapshot.sha256,
            'contract_id':snapshot.contract_id, 'contract_hash':snapshot.contract.sha256,
            'need_id':snapshot.contract.need_id, 'authorization_id':approval.pk,
            'route_id':config.pk, 'owner_id':owner.pk, 'authority':authority,
            'code':'out_of_contract_fields', 'question_version':1,
            'private_console':'finance_hrfinance'}


def current(task):
    validate_task(task)
    opened=list(task.events.filter(action='hr_scope.requested'))
    if len(opened)!=1 or opened[0].actor_id!=task.created_by_id or opened[0].data!={}:
        raise ValidationError('Exact recorded internal request required')
    metadata_access(task.created_by, task.case)
    require(task.created_by, task.case, 'agent.hrfinance')
    snapshot = hr.exact(task.case, HRReadSnapshot, task.context['snapshot_id'])
    config, owner, authority = route(task.case)
    if task.context != packet(snapshot, config, owner, authority):
        raise ValidationError('Clarification source, owner or policy changed; cancel and create a successor')
    if task.claimed_by_id != owner.pk:raise ValidationError('Exact assigned scope owner required')
    return snapshot


def validate_task(task):
    if task.kind != 'factory_information' or task.context.get('purpose') != PURPOSE:
        raise ValidationError('Exact private HR scope clarification required')
    if task.factory_key != 'hr-scope:' + digest(task.context):
        raise ValidationError('Clarification identity differs')


def response_event(task):
    replies = list(task.events.filter(action='hr_scope.responded').order_by('pk'))
    if len(replies) != 1:return None
    reply = replies[0]
    try:validate(REPLY_SCHEMA, reply.data)
    except ValidationError:return None
    if reply.actor_id != task.context['owner_id']:return None
    return reply


def projection(actor, task):
    metadata_access(actor, task.case);validate_task(task)
    result = {'task_id':task.pk, 'revision':task.revision, 'snapshot_id':task.context['snapshot_id'],
              'owner_id':task.context['owner_id'], 'question':QUESTION, 'status':'held',
              'reason':'clarification_requires_reassessment', 'can_reply':False}
    if task.status == 'cancelled':
        result.update(status='cancelled', reason='clarification_cancelled');return result
    try:current(task)
    except (ValidationError, PermissionDenied):return result
    if task.status == 'completed' and response_event(task):
        result.update(status='await_proper_minimal_resubmission', reason='typed_owner_response_recorded')
    elif task.status == 'open':
        result.update(status='awaiting_owner', reason='internal_question_assigned',
                      can_reply=actor.pk == task.context['owner_id'])
    return result


def observation(actor, snapshot):
    metadata_access(actor, snapshot.contract.need.case)
    tasks = HumanTask.objects.filter(case=snapshot.contract.need.case,
        context__purpose=PURPOSE, context__snapshot_id=snapshot.pk).order_by('-pk')
    task = tasks.first()
    if task:return projection(actor, task)
    try:
        source(snapshot);config, owner, authority = route(snapshot.contract.need.case)
    except (ValidationError, PermissionDenied):
        return {'status':'held','reason':'scope_exception_owner_unconfigured'}
    return {'status':'unassigned','reason':'explicit_internal_question_required','owner_id':owner.pk}


@transaction.atomic
def request(actor, case_id, snapshot_id, expected):
    case = hr.locked(actor, case_id, 'agent.hrfinance', expected)
    snapshot = hr.exact(case, HRReadSnapshot, snapshot_id)
    config, owner, authority = route(case)
    context = packet(snapshot, config, owner, authority)
    key = 'hr-scope:' + digest(context)
    old = HumanTask.objects.filter(factory_key=key).first()
    if old:
        if old.created_by_id != actor.pk:raise PermissionDenied('Only the original requester may replay this question')
        return old  # Cancellation and answers never silently reopen.
    previous = HumanTask.objects.select_for_update().filter(case=case,context__purpose=PURPOSE,
        context__snapshot_id=snapshot.pk,status='open')
    if previous.exists():raise ValidationError('Cancel the prior assigned question before explicit reassignment')
    task = HumanTask.objects.create(case=case, kind='factory_information', factory_key=key,
        context=context, claimed_by=owner, required_role='Configured HR scope owner', created_by=actor)
    TaskEvent.objects.create(task=task, actor=actor, action='hr_scope.requested', data={})
    event(actor, case, 'hr_scope.requested', task=task.pk);bump(case)
    return task


@transaction.atomic
def respond(actor, case_id, task_id, revision, reply, expected):
    case = hr.locked(actor, case_id, 'hrfinance.respond', expected)
    task = HumanTask.objects.select_for_update().get(pk=task_id, case=case)
    validate_task(task)
    data = {'reply':reply, 'outcome':'await_proper_minimal_resubmission'}
    validate(REPLY_SCHEMA, data)
    if task.status != 'open' or task.revision != revision:raise ValidationError('STALE_VERSION: refresh the open clarification')
    if actor.pk != task.context['owner_id']:raise PermissionDenied('Exact assigned HR scope owner required')
    current(task);owner_access(actor, case)
    record = TaskEvent.objects.create(task=task, actor=actor, action='hr_scope.responded', data=data)
    task.status='completed';task.revision+=1;task.save(update_fields=['status','revision'])
    event(actor, case, 'hr_scope.responded', task=task.pk, response=record.pk);bump(case)
    return record


@transaction.atomic
def cancel(actor, case_id, task_id, revision, expected):
    # Revoked routing must not prevent the original requester cancelling the wait.
    case = hr.locked(actor, case_id, 'agent.hrfinance', expected)
    task = HumanTask.objects.select_for_update().get(pk=task_id, case=case)
    validate_task(task)
    if actor.pk != task.created_by_id:raise PermissionDenied('Only the original requester may cancel this question')
    if task.status != 'open' or task.revision != revision:raise ValidationError('STALE_VERSION: refresh the open clarification')
    TaskEvent.objects.create(task=task, actor=actor, action='hr_scope.cancelled', data={})
    task.status='cancelled';task.revision+=1;task.save(update_fields=['status','revision'])
    event(actor, case, 'hr_scope.cancelled', task=task.pk);bump(case)
    return task

"""Current invoice information requests, ownership and recovery."""

from django.http import Http404

from apps.core.evidence_access import INVOICE_MILESTONE_PROOF
from apps.workflows import factory, factory_routing

from .http import BOOLEAN, ID, REVISION, TEXT, array, choice, endpoint, nullable, obj
from .work import FINANCE_INVOICE, observed_work


NOTE = {**TEXT, 'maxLength': 4000}
RESPONSE = obj({'task_id': ID, 'task_revision': REVISION, 'case_revision': REVISION, 'evidence_id': nullable(ID)})
ACTIONS = {'oneOf': [
    obj({'action': {'const': 'claim'}, 'task_revision': REVISION}),
    obj({'action': {'const': 'release'}, 'task_revision': REVISION, 'reason': NOTE}),
    obj({'action': {'const': 'recheck'}, 'task_revision': REVISION, 'reason': NOTE}),
    obj({'action': {'const': 'provide'}, 'task_revision': REVISION, 'case_revision': REVISION,
         'kind': {**TEXT, 'maxLength': 100}, 'content': {**TEXT, 'maxLength': 100000},
         'source': {**TEXT, 'maxLength': 200}}),
]}


def task_for(actor, work_id, task_id):
    work, row, _ = observed_work(actor, work_id)
    if work.definition != FINANCE_INVOICE:
        raise Http404
    task = next((task for task in row['tasks'] if task.pk == task_id and task.kind in (
        'factory_information', 'factory_governance')), None)
    if task is None or task.context.get('purpose') == 'hr_scope_clarification_v1':
        raise Http404
    return work, task


@endpoint(response=obj({'task_id': ID, 'task_revision': REVISION, 'case_revision': REVISION,
    'kind': choice('factory_information', 'factory_governance'), 'status': TEXT, 'requested_kinds': array(TEXT),
    'can_claim': BOOLEAN, 'can_provide': BOOLEAN, 'can_recheck': BOOLEAN, 'can_release': BOOLEAN,
    'private_file_url': nullable(TEXT)}),
    summary='Read the exact requested invoice information and currently available resolution actions')
def detail(request, work_id, task_id):
    work, task = task_for(request.user, work_id, task_id)
    requested = task.context.get('missing', [])
    return {'task_id': task.pk, 'task_revision': task.revision, 'case_revision': work.case.revision,
            'kind': task.kind, 'status': task.status,
            'requested_kinds': [key for key in requested if key != INVOICE_MILESTONE_PROOF],
            'private_file_url': f'/api/v1/work/{work.pk}/invoice-milestone-proof' if INVOICE_MILESTONE_PROOF in requested else None,
            'can_claim': task.can_claim, 'can_provide': task.can_supply, 'can_recheck': task.can_recheck,
            'can_release': task.can_release}


@endpoint(method='POST', request=ACTIONS, response=RESPONSE,
    summary='Claim, resolve or recheck the exact current invoice information or responsibility request')
def command(request, work_id, task_id, *, body):
    work, task = task_for(request.user, work_id, task_id)
    actor = request.user
    action, revision = body['action'], body['task_revision']
    evidence = None
    if action == 'claim':
        factory.claim_task(actor, task.pk, revision)
    elif action == 'release':
        factory.release_task_claim(actor, task.pk, revision, body['reason'])
    elif action == 'recheck':
        factory_routing.recheck(actor, task.pk, revision, body['reason'])
    else:
        evidence = factory.provide_information(actor, task.pk, revision, body['case_revision'],
                                               body['kind'], body['content'], body['source'])
    work.case.refresh_from_db(fields=['revision'])
    task.refresh_from_db(fields=['revision'])
    return {'task_id': task.pk, 'task_revision': task.revision, 'case_revision': work.case.revision,
            'evidence_id': evidence.pk if evidence else None}

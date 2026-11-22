"""Exact invoice proof and a separate pre-issue draft stop."""
from uuid import UUID as parse_uuid

from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils import timezone

from apps.core.evidence_access import INVOICE_MILESTONE_PROOF
from apps.identity.services import require
from apps.workflows import factory, factory_invoice_cancellation as cancellation, factory_invoice_information as information
from apps.workflows.models import HumanTask

from .commands import require_line
from .http import BOOLEAN, DATETIME, ID, REVISION, TEXT, UUID, array, endpoint, nullable, obj
from .work import FINANCE_INVOICE, WORK_RESULT, result


NOTE = {'type': 'string', 'maxLength': 2000}
PROOF = obj({'id': ID, 'upload_id': ID, 'filename': TEXT, 'previous_id': nullable(ID), 'download_url': TEXT})
FILE = obj({'id': ID, 'name': TEXT})
TASK = obj({'id': ID, 'revision': REVISION, 'milestone': TEXT, 'can_claim': BOOLEAN, 'can_supply': BOOLEAN,
            'files': array(FILE, limit=50)})
ISSUED = obj({'id': ID, 'reference': TEXT, 'issued_at': DATETIME})


def proof_payload(work, proof):
    return {'id': proof.pk, 'upload_id': proof.upload_id, 'filename': proof.upload.name, 'previous_id': proof.previous_id,
            'download_url': reverse('factory_invoice_milestone_proof', args=[work.pk, proof.pk])}


def evidence_tasks(actor, work):
    return HumanTask.objects.filter(case=work.case, kind='factory_information', status='open',
        context__work=work.pk, context__profile=work.policy_id, context__resolver=actor.pk,
        context__missing__contains=[INVOICE_MILESTONE_PROOF], factory_key__startswith=f'factory:{work.pk}:')


@endpoint(response=obj({'revision': REVISION, 'proof': nullable(PROOF), 'request': nullable(TASK)}),
          summary='Read an authorised private invoice milestone proof and its exact pending request')
def milestone_proof(http, work_id):
    actor = http.user
    work = require_line(actor, work_id, FINANCE_INVOICE)
    try:
        proof = information.readable_proof(actor, work)
    except (PermissionDenied, ValidationError):
        proof = None
    task = evidence_tasks(actor, work).order_by('-pk').first()
    waiting = None
    if task is not None and not work.cancel_requested and work.status in {'ready', 'waiting'}:
        try:
            handoff = information.authorize(actor, work, task)
        except (PermissionDenied, ValidationError):
            pass
        else:
            owned = task.claimed_by_id == actor.pk
            waiting = {'id': task.pk, 'revision': task.revision, 'milestone': handoff.milestone.name,
                       'can_claim': task.claimed_by_id is None, 'can_supply': owned,
                       'files': [{'id': row['pk'], 'name': row['name']} for row in
                                 information.available_files(actor, work).values('pk', 'name')[:50]] if owned else []}
    return {'revision': work.case.revision, 'proof': proof_payload(work, proof) if proof else None, 'request': waiting}


@endpoint(method='POST', request=obj({'expected_revision': REVISION}),
          response=obj({'task_id': ID, 'revision': REVISION}),
          summary='Claim the exact pending invoice proof request as its configured source owner')
def claim_proof(http, work_id, task_id, *, body):
    actor = http.user
    work = require_line(actor, work_id, FINANCE_INVOICE)
    task = get_object_or_404(evidence_tasks(actor, work), pk=task_id)
    information.authorize(actor, work, task)
    claimed = factory.claim_task(actor, task.pk, body['expected_revision'])
    return {'task_id': claimed.pk, 'revision': claimed.revision}


@endpoint(method='POST', request=obj({'task_id': ID, 'task_revision': REVISION, 'case_revision': REVISION,
                                     'upload_id': ID, 'operation': UUID, 'previous_id': nullable(ID), 'note': NOTE},
                                     optional=('previous_id', 'note')),
          response=obj({'proof': PROOF, 'task_revision': REVISION, 'case_revision': REVISION}), status=201,
          summary='Attach or correct the original private milestone evidence with an idempotent operation key')
def attach_proof(http, work_id, *, body):
    actor = http.user
    work = require_line(actor, work_id, FINANCE_INVOICE)
    proof = information.attach(actor, work.pk, body['task_id'], body['task_revision'], body['case_revision'],
        body['upload_id'], parse_uuid(body['operation']), body.get('previous_id'), body.get('note', ''))
    work.case.refresh_from_db(fields=['revision'])
    proof.task.refresh_from_db(fields=['revision'])
    return {'proof': proof_payload(work, proof), 'task_revision': proof.task.revision,
            'case_revision': work.case.revision}


def issued_payload(invoice, at):
    return {'id': invoice.pk, 'reference': invoice.reference, 'issued_at': at}


@endpoint(response=obj({'revision': REVISION, 'case_revision': REVISION, 'can_stop': BOOLEAN,
    'existing_issue': nullable(ISSUED), 'recorded_stop': nullable(obj({'reason': TEXT, 'at': DATETIME,
                                                                     'existing_issue': nullable(ISSUED)}))}),
          summary='Read the exact unsent draft and any already-issued invoice for its billing obligation')
def draft_stop(http, work_id):
    actor = http.user
    work = require_line(actor, work_id, FINANCE_INVOICE)
    try:
        require(actor, work.case, 'factory.manage')
        can_stop = cancellation.eligible(actor, work)
    except (PermissionDenied, ValidationError):
        can_stop = False
    issue = None
    if can_stop:
        try:
            issue = cancellation.existing_issue(actor, work)
        except (PermissionDenied, ValidationError):
            pass
    stopped = cancellation.readback(actor, work)
    recorded = None
    if stopped:
        existing = stopped['existing_invoice']
        recorded = {'reason': stopped['reason'], 'at': stopped['at'],
                    'existing_issue': issued_payload(existing, stopped['issued_at']) if existing else None}
    return {'revision': work.revision, 'case_revision': work.case.revision, 'can_stop': can_stop,
            'existing_issue': issued_payload(issue.invoice, issue.created_at) if issue else None,
            'recorded_stop': recorded}


@endpoint(method='POST', request=obj({'expected_revision': REVISION, 'case_revision': REVISION,
    'reason': {**TEXT, 'maxLength': 2000}, 'existing_invoice_id': nullable(ID)}, optional=('existing_invoice_id',)),
          response=WORK_RESULT, summary='Stop one exact invoice draft before any delivery or issue effect')
def stop_draft(http, work_id, *, body):
    work = require_line(http.user, work_id, FINANCE_INVOICE)
    command = cancellation.DraftStop(body['case_revision'], body['reason'], body.get('existing_invoice_id'))
    stopped = factory.manage(http.user, work.pk, body['expected_revision'], 'cancel', draft_stop=command)
    return result(stopped)

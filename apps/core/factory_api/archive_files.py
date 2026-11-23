"""Project archive inventory, reserved copies and their original lookup receipts."""
from time import monotonic

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone

from apps.core.read_budget import limit_queries
from apps.core.read_observation import read_observation
from apps.core.services import lock_case
from apps.pmo import archive_transfer
from apps.pmo.archive_transfer_forms import ArchiveRulesForm, ArchiveSelectionForm
from apps.pmo.models import ArchiveCopyJob, ArchiveCopyReceipt
from apps.workflows import factory, factory_archive

from .commands import require_line
from .http import BOOLEAN, DATETIME, ID, REVISION, TEXT, array, choice, endpoint, nullable, obj
from .reviews import VERSIONS
from .work import WORK_RESULT, result


STATES = choice('pending', 'leased', 'unknown', 'missing', 'confirmed', 'held')
JOB = obj({'id': ID, 'revision': REVISION, 'state': STATES})
FILES = obj({**VERSIONS, 'plan_id': nullable(ID), 'store': nullable(TEXT), 'finding': {'type': 'string'},
    'verified': BOOLEAN, 'can_reserve': BOOLEAN, 'limited': BOOLEAN,
    'required_source_ids': array(ID, limit=20), 'sources': array(obj({'id': ID, 'label': TEXT}), limit=500),
    'files': array(obj({'id': ID, 'name': TEXT, 'status': TEXT, 'job': nullable(JOB), 'group': TEXT,
        'source_id': nullable(ID), 'source_kind': nullable(TEXT),
        'actions': array(choice('lookup', 'retry')), 'receipt': nullable(obj({'id': ID, 'at': DATETIME}))}), limit=500)})


def job_payload(job):
    return {'id': job.pk, 'revision': job.revision, 'state': job.status}


@endpoint(response=FILES, summary='Read the reviewed archive inventory, exact original copies and recovery options')
@read_observation
def inventory(request, work_id):
    actor = request.user
    work = require_line(actor, work_id, factory_archive.DEFINITION)
    with limit_queries(900, deadline=monotonic() + 8):
        state = archive_transfer.projection(actor, work)
        plan = state['plan']
        required = []
        source_choices = []
        limited = False
        can_reserve = False
        finding = state.get('finding', '')
        try:
            archive_transfer.access(actor, work.case)
            factory.access(actor, work.case, 'factory.manage', work.definition)
        except PermissionDenied:
            pass
        else:
            _, selected, _ = factory_archive.source(work, actor, current=False)
            required = sorted({pk for pk in selected['inventory'].values() if pk is not None})
            form = ArchiveSelectionForm(work.case, selected=required)
            limited = form.limited
            source_choices = [{'id': int(pk), 'label': label} for pk, label in form.fields['sources'].choices]
            try:
                if not plan:
                    archive_transfer.rules(work.case)
                    archive_transfer.native_archive(work, actor)
            except (PermissionDenied, ValidationError):
                finding = finding or 'Review the current archive inventory and store rules before reserving copies.'
            else:
                active_jobs = any(file.job.status in ('pending', 'unknown', 'leased') for file in state['files'])
                can_reserve = not finding and not active_jobs and not work.cancel_requested and not (
                    work.lease_until and work.lease_until > timezone.now())
        # Verified receipts may be projected with their original timestamps, without the private object key.
        receipts = {}
        if plan and state['can_operate'] and state['verified']:
            receipts = {row.file_id: {'id': row.pk, 'at': row.created_at}
                        for row in ArchiveCopyReceipt.objects.filter(file__plan=plan).only('file_id', 'created_at')}
        files = [{'id': file.pk, 'name': file.display_name, 'status': file.display_status, 'group': file.display_group,
                  'source_kind': file.display_source_kind,
                  'source_id': file.evidence_id if file.display_source_kind else None,
                  'job': job_payload(file.job) if state['can_operate'] else None,
                  'actions': [action for action, allowed in (('lookup', file.can_lookup), ('retry', file.can_retry)) if allowed],
                  'receipt': receipts.get(file.pk)} for file in state['files'][:500]]
    return {'expected_revision': work.revision, 'case_revision': work.case.revision,
            'plan_id': plan.pk if plan else None, 'store': state.get('store_label'), 'finding': finding,
            'verified': state['verified'], 'can_reserve': can_reserve, 'limited': limited,
            'required_source_ids': required, 'sources': source_choices, 'files': files}


@endpoint(method='POST', request=obj({**VERSIONS, 'source_ids': {**array(ID, limit=500), 'minItems': 1, 'uniqueItems': True}}),
          response=obj({**WORK_RESULT['properties'], 'plan_id': ID}), status=202,
          summary='Reserve the original reviewed project documents and attached files for archive copy')
def reserve(request, work_id, *, body):
    work = require_line(request.user, work_id, factory_archive.DEFINITION)
    plan = archive_transfer.reserve(request.user, work.pk, body['expected_revision'], body['case_revision'], body['source_ids'])
    work.refresh_from_db(fields=['status', 'revision', 'lease_until'])
    return {**result(work), 'plan_id': plan.pk}


@endpoint(method='POST', request=obj({'revision': REVISION, 'action': choice('lookup', 'retry')}),
          response=JOB, summary='Check the original archive copy or retry an independently confirmed missing file')
def recover(request, work_id, job_id, *, body):
    actor = request.user
    work = require_line(actor, work_id, factory_archive.DEFINITION)
    archive_transfer.access(actor, work.case)
    job = get_object_or_404(ArchiveCopyJob.objects.filter(file__plan__work=work), pk=job_id)
    if body['action'] == 'lookup':
        archive_transfer.run_once(job.pk, actor=actor, lookup_only=True, expected=body['revision'])
        job.refresh_from_db(fields=['status', 'revision'])
    else:
        job = archive_transfer.retry_missing(actor, job.pk, body['revision'])
    return job_payload(job)


@endpoint(method='POST', request=obj({
    'case_revision': REVISION, 'adapter': choice('private_object_store/v1', 'synthetic_archive/v1'), 'operator_id': ID,
    'max_files': {'type': 'integer', 'minimum': 1, 'maximum': 500},
    'max_bytes': {'type': 'integer', 'minimum': 1, 'maximum': 52428800},
    'lease_seconds': {'type': 'integer', 'minimum': 10, 'maximum': 300}, 'evidence_id': ID,
}), response=obj({'configuration_id': ID}), status=201,
          summary='Draft project archive store rules from recorded evidence for separate validation and approval')
@transaction.atomic
def draft_rules(request, work_id, *, body):
    work = require_line(request.user, work_id, factory_archive.DEFINITION)
    case = lock_case(request.user, work.case_id, 'policy.configure', body['case_revision'])
    form = ArchiveRulesForm({key: value for key, value in body.items() if key != 'case_revision'})
    if not form.is_valid():
        raise ValidationError('Complete the reviewed archive store and operator choices.')
    configuration = form.save(request.user, case)
    return {'configuration_id': configuration.pk}

"""Source-bound file copying, exact store readback and missing-file-only retry."""
import hashlib
from datetime import timedelta
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Func, IntegerField, Q
from django.utils import timezone

from adapters import case_uploads, project_archive
from apps.agents.models import CaseUpload, FileDraftReview
from apps.core.evidence_access import public_evidence
from apps.core.models import Audit, Evidence
from apps.core.read_observation import read_observation
from apps.core.services import bump, event, lock_case
from apps.documents.contracts import digest, validate
from apps.identity.models import Grant
from apps.identity.services import require
from apps.policy.archive_transfer_validators import COMPONENT, VALUE
from apps.policy.services import active_component, reference_values
from .models import ArchiveCopyAttempt, ArchiveCopyFile, ArchiveCopyJob, ArchiveCopyPlan, ArchiveCopyReceipt

FILE_GROUPS = {
    **dict.fromkeys(['rfp_intake', 'rfp_response', 'rfp_outcome', 'rfp_commercial_terms'], 'Bid records'),
    **dict.fromkeys(['costing', 'sow', 'signature', 'commercial_terms'], 'Costing and agreements'),
    **dict.fromkeys(['requirements', 'plan', 'planning_packet', 'technical_document', 'technical_design'], 'Planning'),
    **dict.fromkeys(['test_results', 'project_artifact', 'support_document', 'escalation_document',
                    'handover_receipt', 'release', 'go_live_checklist', 'incident_reporting', 'rollback'], 'Delivery and acceptance'),
    **dict.fromkeys(['meeting', 'meeting_notes', 'minutes', 'status_report', 'weekly_report', 'closure_report'], 'Minutes and reports'),
}


def access(actor, case):
    if not get_user_model().objects.filter(pk=actor.pk, is_active=True).exists():
        raise PermissionDenied('An active project archive operator is required.')
    for action in ['case.read', 'delivery.read', 'delivery.manage', 'delivery.archive_files']:
        require(actor, case, action)


def rules(case):
    try:
        configuration = active_component(COMPONENT, case)
    except ValidationError:
        raise ValidationError('Review the archive store and designated operator rules before copying files.') from None
    value = reference_values(configuration)[0]
    validate(VALUE, value)
    operator = get_user_model().objects.filter(pk=value['operator_id'], is_active=True).first()
    if operator is None:
        raise ValidationError('Review the current designated archive operator.')
    access(operator, case)
    if value['adapter'] == 'synthetic_archive/v1' and not case.synthetic:
        raise ValidationError('The sample archive store requires a synthetic project.')
    return configuration, value, operator


@read_observation
def native_archive(work, actor):
    from apps.workflows import factory_archive
    from . import delivery_closure

    dossier, data, _ = factory_archive.source(work, actor)
    archive = delivery_closure.archive_index(dossier)
    if archive.data['inventory'] != data['inventory']:
        raise ValidationError('Review the current archive inventory before copying its files.')
    return archive


def file_manifest(work, selected_ids, value):
    if not isinstance(selected_ids, list) or any(type(pk) is not int or pk < 1 for pk in selected_ids):
        raise ValidationError('Select exact project source documents for the archive.')
    if len(selected_ids) > value['max_files'] or len(set(selected_ids)) != len(selected_ids):
        raise ValidationError('Select each source once within the reviewed file limit.')
    sources = list(public_evidence(Evidence.objects.filter(case=work.case, pk__in=selected_ids))
        .only('pk', 'kind', 'version', 'sha256').annotate(byte_size=Func('body', function='OCTET_LENGTH', output_field=IntegerField()))
        .order_by('pk'))
    if len(sources) != len(selected_ids):
        raise ValidationError('Each selected source needs current project evidence access.')
    result = [{'evidence_id': source.pk, 'upload_id': None,
               'name': f'{source.kind}-v{source.version}-{source.pk}.txt',
               'sha256': source.sha256, 'size': source.byte_size} for source in sources]
    attachments = FileDraftReview.objects.filter(evidence_id__in=selected_ids, job__upload__case=work.case)
    upload_sources = {}
    for upload_id, source_id in attachments.order_by('pk').values_list('job__upload_id', 'evidence_id')[:value['max_files'] + 1]:
        upload_sources.setdefault(upload_id, source_id)
    uploads = list(CaseUpload.objects.filter(pk__in=attachments.values('job__upload_id'))
                   .order_by('pk')[:value['max_files'] + 1])
    for upload in uploads:
        result.append({'evidence_id': upload_sources[upload.pk], 'upload_id': upload.pk, 'name': upload.name,
                       'sha256': upload.sha256, 'size': upload.size})
    if len(result) > value['max_files'] or sum(row['size'] for row in result) > value['max_bytes']:
        raise ValidationError('The selected documents and attachments exceed the reviewed archive limits.')
    if any(row['size'] > case_uploads.LIMIT for row in result):
        raise ValidationError('Each source or attachment must fit the supported 5 MiB file limit.')
    return result


@transaction.atomic
def reserve(actor, work_id, expected, case_expected, selected_ids):
    from apps.workflows.factory import access as work_access
    from apps.workflows.models import FactoryWork

    work = FactoryWork.objects.select_for_update().select_related('case').get(pk=work_id, definition='delivery-archive/v1')
    work_access(actor, work.case, 'factory.manage', work.definition)
    case = lock_case(actor, work.case_id, 'delivery.archive_files', case_expected)
    access(actor, case)
    if work.revision != expected or work.cancel_requested or work.lease_until and work.lease_until > timezone.now():
        raise ValidationError('The archive work changed. Review its current files before continuing.')
    configuration, value, operator = rules(case)
    archive = native_archive(work, actor)
    required = set(archive.data['inventory'].values())
    if not isinstance(selected_ids, list) or not required.issubset(selected_ids):
        raise ValidationError('Include every document in the current reviewed archive inventory.')
    files = file_manifest(work, selected_ids, value)
    manifest = {'protocol': 'project-file-archive/v1', 'archive_id': archive.pk,
                'configuration_id': configuration.pk, 'operator_id': operator.pk,
                'destination': project_archive.destination(value), 'files': files}
    sha = digest(manifest)
    old = work.file_archives.order_by('-pk').first()
    if old and old.sha256 == sha:
        return old
    if ArchiveCopyJob.objects.filter(file__plan__work=work, status__in=['pending', 'unknown', 'leased']).exists():
        raise ValidationError('Check and settle the original file attempts before starting another archive plan.')
    plan = ArchiveCopyPlan.objects.create(work=work, archive=archive, configuration=configuration,
        manifest=manifest, sha256=sha, actor=actor)
    for data in files:
        file = ArchiveCopyFile.objects.create(plan=plan, **data)
        ArchiveCopyJob.objects.create(file=file)
    event(actor, case, 'delivery.archive_files_reserved', plan_id=plan.pk, manifest_sha256=sha)
    bump(case)
    work.revision += 1
    work.save(update_fields=['revision'])
    if work.status == 'verified':
        from apps.workflows.factory_archive import reassess
        work = reassess(actor, work.pk, work.revision, 'Explicit selected-file archive request with store receipt verification.')
    from apps.workflows.factory_execution import can_control
    from apps.workflows.factory_progress import set_progress, wake_waiting
    if can_control(actor, work):
        set_progress(actor, work.pk, work.revision, True)
    wake_waiting(work.pk)
    return plan


def plan_rules(plan):
    value = reference_values(plan.configuration)[0]
    validate(VALUE, value)
    if plan.sha256 != digest(plan.manifest) or not Audit.objects.filter(case=plan.work.case, actor=plan.actor,
        action='delivery.archive_files_reserved', data={'plan_id': plan.pk, 'manifest_sha256': plan.sha256}).exists():
        raise ValidationError('The archive plan needs its exact source-owned reservation.')
    if project_archive.destination(value) != plan.manifest['destination']:
        raise ValidationError('The original archive store changed. Review its connection before receipt lookup.')
    return value


def authorize_file(file, actor, *, lookup):
    case = file.plan.work.case
    access(actor, case)
    value = plan_rules(file.plan)
    source = public_evidence(Evidence.objects.filter(case=case, pk=file.evidence_id)).defer('body').first()
    if not source:
        raise ValidationError('The original file source requires its current evidence permission.')
    declared = {'evidence_id': file.evidence_id, 'upload_id': file.upload_id,
                'name': file.name, 'sha256': file.sha256, 'size': file.size}
    if declared not in file.plan.manifest['files']:
        raise ValidationError('The file must match the exact reserved archive manifest.')
    if file.upload_id:
        upload = file.upload
        if upload.case_id != case.pk or upload.sha256 != file.sha256 or upload.size != file.size or not FileDraftReview.objects.filter(
            evidence=source, job__upload=upload).exists():
            raise ValidationError('The attachment needs its exact reviewed project source relation.')
    elif source.sha256 != file.sha256:
        raise ValidationError('The original archive source hash changed.')
    if not lookup:
        from apps.workflows.models import FactoryWork
        work = FactoryWork.objects.select_related('case', 'source_head').get(pk=file.plan.work_id)
        if work.cancel_requested or work.status in ['cancelled', 'followup_needed']:
            raise ValidationError('The archive work is stopped. Check existing receipts before a new instruction.')
        configuration, current, operator = rules(case)
        if configuration.pk != file.plan.configuration_id or current != value or operator.pk != actor.pk:
            raise ValidationError('Review the current archive operator and store rule before copying files.')
        if native_archive(work, actor).pk != file.plan.archive_id:
            raise ValidationError('The reviewed archive inventory changed before file copying.')
    return value


def source_bytes(file):
    if file.upload_id:
        data = case_uploads.read(file.upload)
    else:
        data = Evidence.objects.get(pk=file.evidence_id).body.encode()
    project_archive.proof(file, data)
    return data


def run_once(job_id=None, *, actor=None, adapter=None, lookup_only=False, expected=None):
    now = timezone.now()
    with transaction.atomic():
        query = ArchiveCopyJob.objects.select_for_update(of=('self',), skip_locked=True).select_related(
            'file__plan__work__case', 'file__plan__configuration', 'file__plan__actor', 'file__upload')
        if job_id is not None:
            query = query.filter(pk=job_id)
        else:
            query = query.filter(Q(status='pending') | Q(status='leased', lease_until__lte=now))
        job = query.order_by('pk').first()
        if not job or job.status == 'confirmed' or job.status == 'leased' and job.lease_until and job.lease_until > now:
            return False
        if expected is not None and job.revision != expected:
            raise ValidationError('This file attempt changed. Refresh its current receipt and state.')
        lookup = lookup_only or job.status in ['unknown', 'leased']
        if not lookup and job.status != 'pending':
            raise ValidationError('Check the original store receipt before authorising a missing-file retry.')
        operation = 'lookup' if lookup else 'copy'
        operator = actor or get_user_model().objects.filter(pk=job.file.plan.manifest['operator_id']).first()
        token = uuid4()
        try:
            if operator is None:
                raise PermissionDenied('Review the archive operator.')
            list(Grant.objects.select_for_update().filter(case=job.file.plan.work.case, user=operator).order_by('pk'))
            value = authorize_file(job.file, operator, lookup=lookup)
        except (ValidationError, PermissionDenied):
            ArchiveCopyAttempt.objects.create(job=job, token=token,
                operation=operation, outcome='held')
            job.status = 'held'
            job.lease_operation = None
            job.lease_token = None
            job.lease_until = None
            job.finding = 'Review the current archive source, store rule and operator permission.'
            job.revision += 1
            job.save()
            event(job.file.plan.actor, job.file.plan.work.case, 'delivery.archive_file_held',
                  job_id=job.pk, provider_contacted=False)
            return True
        job.status = 'leased'
        job.lease_operation = operation
        job.lease_token = token
        job.lease_until = now + timedelta(seconds=value['lease_seconds'])
        job.revision += 1
        job.save()
        file = job.file
    outcome, receipt = 'uncertain', None
    try:
        transport = adapter or project_archive.configured_adapter(value)
        if lookup:
            receipt = transport.lookup(file)
            outcome = 'found' if receipt is not None else 'missing'
        else:
            data = source_bytes(file)
            authorize_file(file, operator, lookup=False)
            receipt = transport.copy(file, data)
            outcome = 'found' if receipt is not None else 'uncertain'
        if receipt is not None and receipt != {'object_key': project_archive.object_key(file), 'sha256': file.sha256, 'size': file.size}:
            raise ValidationError('The returned file receipt must match the exact reserved bytes and destination.')
    except (ValidationError, PermissionDenied):
        outcome, receipt = 'held', None
    except (OSError, TimeoutError):
        outcome, receipt = 'uncertain', None
    with transaction.atomic():
        current = ArchiveCopyJob.objects.select_for_update().get(pk=job.pk)
        if current.lease_token != token:
            return False
        attempt = ArchiveCopyAttempt.objects.create(job=current, token=token, operation=operation, outcome=outcome)
        if receipt is not None:
            ArchiveCopyReceipt.objects.get_or_create(file=file, defaults={'attempt': attempt, **receipt})
        current.status = {'found': 'confirmed', 'missing': 'missing', 'held': 'held', 'uncertain': 'unknown'}[outcome]
        current.finding = {'found': '', 'missing': 'The original store lookup found no file. A reviewed retry is available.',
            'held': 'Review the source, permission or exact file receipt before continuing.',
            'uncertain': 'Check the original archive store receipt before copying this file again.'}[outcome]
        current.lease_token = None
        current.lease_until = None
        current.lease_operation = None
        current.revision += 1
        current.save()
        event(operator, file.plan.work.case, 'delivery.archive_file_observed', file_id=file.pk,
              attempt_id=attempt.pk, operation=operation, outcome=outcome)
    from apps.workflows.factory_progress import wake_waiting
    wake_waiting(file.plan.work_id)
    return True


@transaction.atomic
def retry_missing(actor, job_id, expected):
    job = ArchiveCopyJob.objects.select_for_update(of=('self',)).select_related('file__plan__work__case',
        'file__plan__configuration', 'file__plan__actor', 'file__upload').get(pk=job_id)
    if job.revision != expected or job.status != 'missing' or ArchiveCopyReceipt.objects.filter(file=job.file).exists():
        raise ValidationError('Only a currently missing original file may be retried.')
    observation = job.attempts.order_by('-pk').first()
    if not observation or observation.operation != 'lookup' or observation.outcome != 'missing':
        raise ValidationError('A missing-file retry requires the original store lookup evidence.')
    authorize_file(job.file, actor, lookup=False)
    job.status = 'pending'
    job.finding = ''
    job.revision += 1
    job.save()
    event(actor, job.file.plan.work.case, 'delivery.archive_missing_retry', job_id=job.pk, revision=job.revision)
    return job


@read_observation
def projection(actor, work):
    require(actor, work.case, 'delivery.read')
    plan = work.file_archives.order_by('-pk').first()
    try:
        access(actor, work.case)
        can_operate = True
    except PermissionDenied:
        can_operate = False
    if not plan:
        return {'plan': None, 'files': [], 'can_operate': can_operate, 'verified': False}
    plan.work = work
    files = list(plan.files.select_related('job').order_by('pk')[:501])
    source_kinds = dict(public_evidence(work.case.evidence.filter(pk__in=[file.evidence_id for file in files])).values_list('pk', 'kind'))
    visible = set(source_kinds)
    groups = {}
    now = timezone.now()
    copying = 0
    checking = 0
    queued = 0
    for file in files:
        file.plan = plan
        file.display_name = file.name if can_operate and file.evidence_id in visible else 'Project source file'
        lease_current = file.job.status == 'leased' and file.job.lease_until and file.job.lease_until > now
        is_copying = lease_current and file.job.lease_operation == 'copy'
        copying += bool(is_copying)
        checking += bool(lease_current and not is_copying)
        queued += file.job.status == 'pending'
        file.display_status = {'pending':'Queued','leased':(
            'Copying' if is_copying else 'Checking original copy' if lease_current else 'Original copy needs checking'),
            'unknown':'Confirmation missing',
            'missing':'File not found','confirmed':'Archived','held':'Needs review'}[file.job.status]
        file.can_lookup = can_operate and file.evidence_id in visible and file.job.status in ['unknown', 'missing', 'held']
        file.can_retry = False
        group = FILE_GROUPS.get(source_kinds.get(file.evidence_id), 'Project documents')
        summary = groups.setdefault(group, {'label': group, 'total': 0, 'confirmed': 0})
        summary['total'] += 1
        summary['confirmed'] += file.job.status == 'confirmed'
    confirmed = sum(file.job.status == 'confirmed' for file in files)
    verified = bool(files) and len(files) <= 500 and confirmed == len(files)
    finding = ''
    current_scope = False
    retry_actor_id = None
    store_label = 'archive store'
    try:
        plan_value = plan_rules(plan)
        store_label = 'private file store' if plan_value['adapter'] == 'private_object_store/v1' else 'synthetic acceptance store'
        if len(files) != len(plan.manifest['files']):
            raise ValidationError('The archive file inventory is incomplete.')
        configuration, _, operator = rules(work.case)
        retry_actor_id = operator.pk
        if configuration.pk != plan.configuration_id:
            raise ValidationError('The archive store rule changed.')
        if native_archive(work, actor).pk != plan.archive_id:
            raise ValidationError('The source inventory changed.')
        if len(visible) != len({file.evidence_id for file in files}):
            raise ValidationError('The file source permissions changed.')
        receipts = {receipt.file_id: receipt for receipt in ArchiveCopyReceipt.objects.filter(file__plan=plan).select_related('attempt')}
        if len(receipts) != len(files):
            verified = False
        for file in files:
            declared = {'evidence_id': file.evidence_id, 'upload_id': file.upload_id,
                        'name': file.name, 'sha256': file.sha256, 'size': file.size}
            if declared not in plan.manifest['files']:
                raise ValidationError('The file differs from its reserved manifest.')
            receipt = receipts.get(file.pk)
            if receipt and (receipt.object_key != project_archive.object_key(file) or receipt.sha256 != file.sha256
                            or receipt.size != file.size or receipt.attempt.job_id != file.job.pk
                            or receipt.attempt.outcome != 'found'):
                raise ValidationError('The file receipt needs its exact original store observation.')
        current_scope = True
    except (ValidationError, PermissionDenied):
        verified = False
        finding = 'Review the current source inventory, store connection and file receipt coverage.'
    for file in files:
        file.can_retry = (can_operate and current_scope and retry_actor_id == actor.pk and
                          not work.cancel_requested and file.job.status == 'missing')
    return {'plan': plan, 'files': files, 'confirmed': confirmed, 'total': len(files),
            'can_operate': can_operate, 'verified': verified, 'finding': finding, 'store_label': store_label,
            'groups': list(groups.values()), 'copying': copying, 'checking': checking, 'queued': queued,
            'watching': bool(copying or checking or (queued and current_scope and not work.cancel_requested))}

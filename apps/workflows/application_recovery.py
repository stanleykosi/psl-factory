"""System-wide, human-controlled native archive/recovery; separate from case metadata."""
from datetime import timedelta
from pathlib import Path
from uuid import uuid4
import psycopg
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError, PermissionDenied
from django.db import connection, transaction
from django.db.models import Q
from django.utils import timezone
from apps.core.models import Case
from apps.identity.models import Grant
from apps.identity.services import require
from apps.policy.services import active_component, reference_values, decision_authority
from apps.policy.application_recovery_validators import COMPONENT, REF
from apps.documents.contracts import validate
from adapters.forecast import obj
from adapters import native_application_archive as native
from .application_recovery_models import ApplicationRecoveryPlan as Plan, ApplicationRecoveryJob as Job, ApplicationRecoveryReview as Review, RecoveryAttachment as Attachment

PLAN = obj({k: REF for k in ['source_ref', 'target_ref', 'key_ref']})


def access(actor, case, action='read', locked=False):
    if locked:
        list(Case.objects.select_for_update().order_by('pk'))
        list(get_user_model().objects.select_for_update().filter(pk=actor.pk))
        list(Grant.objects.select_for_update().filter(user=actor).order_by('pk'))
        actor.refresh_from_db()
    require(actor, case, 'case.read')
    require(actor, case, 'recovery.' + action)
    ids = list(Case.objects.order_by('pk').values_list('pk', flat=True))
    granted = set(Grant.objects.filter(user=actor, action='recovery.database', active=True).values_list('case_id', flat=True))
    if not set(ids) <= granted:
        raise PermissionDenied('Explicit whole-database authority is required on every source case, including private domains')
    return [str(i) for i in ids]


def provisioned(actor):
    if actor.pk not in settings.APPLICATION_RECOVERY.get('principals', []):
        raise PermissionDenied('Independent deployment-owned database recovery principal is not provisioned')


@transaction.atomic
def attach(actor, case_id, source_ref, label, data):
    case = Case.objects.get(pk=case_id)
    require(actor, case, 'case.read')
    require(actor, case, 'recovery.attachment')
    if not isinstance(data, bytes) or not data or len(data) > 1048576 or not label.strip() or len(label) > 120:
        raise ValidationError('A labelled managed attachment of 1..1048576 bytes is required')
    try:
        source = settings.APPLICATION_RECOVERY['sources'][source_ref]
        if source['database'] != connection.settings_dict['NAME']:
            raise KeyError()
        root = native.checked_root(source['attachments'])
    except KeyError:
        raise ValidationError('Managed source attachment storage is not provisioned') from None
    sha = native.digest(data)
    native.put_once(root / sha, data)
    return Attachment.objects.create(case=case, actor=actor, source_ref=source_ref, label=label, sha256=sha, size=len(data))


@transaction.atomic
def capture(actor, case_id, reference, payload):
    case = Case.objects.get(pk=case_id)
    access(actor, case, 'capture', locked=True)
    validate(PLAN, payload)
    if not reference.strip() or len(reference) > 100:
        raise ValidationError('A stable plan reference of 1..100 characters is required')
    old = Plan.objects.filter(case=case, reference=reference).order_by('-version').first()
    if old and old.payload == payload:
        return old
    return Plan.objects.create(case=case, reference=reference, version=old.version + 1 if old else 1,
                               payload=payload, sha256=native.digest(payload), actor=actor)


def rules(plan):
    config = active_component(COMPONENT, plan.case)
    v = reference_values(config)[0]
    if any(v[k] != plan.payload[k] for k in plan.payload):
        raise ValidationError('Plan and active independent recovery policy references differ')
    if Plan.objects.filter(case=plan.case, reference=plan.reference, version__gt=plan.version).exists():
        raise ValidationError('Create/use the current explicit plan successor')
    return config, v


def principal(actor, plan, purpose, v):
    provisioned(actor)
    key = 'reviewer' if purpose == 'review' else 'operator'
    if actor.pk != v[key + '_id']:
        raise PermissionDenied('Only the configured exact purpose principal can perform this action')
    decision_authority(actor, plan.case, v[key + '_role'])


def pin(plan):
    config, v = rules(plan)
    _, _, _, _, identity = native.runtime(v)
    return {'plan_sha256': plan.sha256, 'policy': config.pk,
            'role_policy': active_component('D05.role_principal_assignments', plan.case).pk,
            'runtime_sha256': identity}


@transaction.atomic
def review(actor, case_id, plan_id, phase, decision, rationale, operation_key):
    p = Plan.objects.select_related('case').get(pk=plan_id, case_id=case_id)
    access(actor, p.case, 'review', locked=True)
    _, v = rules(p)
    principal(actor, p, 'review', v)
    if actor.pk == p.actor_id or Job.objects.filter(plan=p, actor=actor).exists():
        raise PermissionDenied('The independent reviewer cannot prepare this plan or an effect')
    if phase not in ['authorize', 'recovered'] or decision not in ['approve', 'hold'] or not rationale.strip() or len(rationale) > 1000 or not operation_key or len(operation_key) > 100:
        raise ValidationError('Explicit human phase, decision, bounded rationale and idempotency key required')
    evidence = pin(p)
    if phase == 'recovered':
        job = Job.objects.filter(plan=p, kind='restore', status='confirmed').first()
        if job is None:
            raise ValidationError('An actual confirmed isolated recovery is required')
        found = lookup(job)
        if found != job.receipt:
            raise ValidationError('Current physical recovery receipt differs')
        if any(job.intent['pin'].get(k) != value for k, value in evidence.items()):
            raise ValidationError('Recovery review requires the same policy/build/source identity as the actual intent')
        evidence['recovery_receipt_sha256'] = native.digest(found)
    values = dict(phase=phase, decision=decision, rationale=rationale, pin=evidence, actor=actor)
    old = Review.objects.filter(plan=p, operation_key=operation_key).first()
    if old:
        if any(getattr(old, k) != value for k, value in values.items()):
            raise ValidationError('Review key already binds another immutable human intent')
        return old
    return Review.objects.create(plan=p, operation_key=operation_key, **values)


def authorization(plan):
    current = pin(plan)
    last = Review.objects.filter(plan=plan, phase='authorize').order_by('-pk').first()
    if not last or last.decision != 'approve' or last.pin != current:
        raise ValidationError('Current independently approved native recovery authorization is required')
    _, v = rules(plan)
    if timezone.now() >= last.created_at + timedelta(seconds=v['authorization_valid_seconds']):
        raise ValidationError('Independent native recovery authorization has expired')
    reviewer = get_user_model().objects.get(pk=last.actor_id)
    access(reviewer, plan.case, 'review', locked=True)
    principal(reviewer, plan, 'review', v)
    return {**current, 'authorization_review': last.pk}


@transaction.atomic
def reserve(actor, case_id, plan_id, kind):
    p = Plan.objects.select_related('case').get(pk=plan_id, case_id=case_id)
    case_ids = access(actor, p.case, 'operate', locked=True)
    _, v = rules(p)
    principal(actor, p, 'operate', v)
    selected = authorization(p)
    if kind not in ['archive', 'restore']:
        raise ValidationError('Select a distinct native archive or isolated recovery intent')
    old = Job.objects.filter(plan=p, kind=kind).first()
    if old:
        return old
    archive_job = None
    if kind == 'restore':
        archive_job = Job.objects.filter(plan=p, kind='archive', status='confirmed').first()
        if archive_job is None:
            raise ValidationError('A confirmed native archive is required')
        if lookup(archive_job) != archive_job.receipt:
            raise ValidationError('Current physical archive receipt differs')
    key = native.digest({'plan': p.pk, 'sha256': p.sha256, 'kind': kind})
    intent = {'format': native.FORMAT, 'operation_key': key, 'kind': kind, 'plan': p.pk,
              'plan_sha256': p.sha256, 'rules': v, 'pin': selected, 'case_ids': case_ids,
              'runtime_sha256': selected['runtime_sha256'], 'archive_job': archive_job.pk if archive_job else None}
    return Job.objects.create(plan=p, kind=kind, operation_key=key, intent=intent, actor=actor)


def lookup(job):
    if job.kind == 'archive':
        _, _, _, roots, _ = native.runtime(job.intent['rules'])
        if not native.archive_path(job.intent, roots).exists():
            return None
        return native.archive_receipt(job.intent)
    archive_job = Job.objects.get(pk=job.intent['archive_job'], plan=job.plan, kind='archive')
    return native.restored_receipt(job.intent, archive_job.intent)


@transaction.atomic
def retry(actor, case_id, job_id):
    j = Job.objects.select_for_update().select_related('plan__case').get(pk=job_id, plan__case_id=case_id)
    access(actor, j.plan.case, 'operate', locked=True)
    _, v = rules(j.plan)
    principal(actor, j.plan, 'operate', v)
    if j.status not in ['held', 'unknown']:
        raise ValidationError('Only a held/uncertain exact intent can be reconciled')
    j.status = 'pending'
    j.save(update_fields=['status'])
    return j


def run_once():
    with transaction.atomic():
        j = Job.objects.select_for_update(skip_locked=True).filter(Q(status__in=['pending', 'unknown']) | Q(status='leased', lease_until__lt=timezone.now())).order_by('pk').first()
        if not j:
            return False
        j.status = 'leased'
        j.fence += 1
        j.attempts += 1
        j.lease_until = timezone.now() + timedelta(seconds=j.intent['rules']['lease_seconds'])
        j.save(update_fields=['status', 'fence', 'attempts', 'lease_until'])
        job_id, fence = j.pk, j.fence
    with transaction.atomic():
        j = Job.objects.select_for_update().select_related('plan__case', 'actor').get(pk=job_id)
        if j.fence != fence or j.status != 'leased':
            return True
        try:
            receipt = lookup(j)  # Reconcile committed exact effects before authority/budget.
            if receipt is None:
                access(j.actor, j.plan.case, 'operate', locked=True)
                _, v = rules(j.plan)
                principal(j.actor, j.plan, 'operate', v)
                if authorization(j.plan) != j.intent['pin'] or v != j.intent['rules']:
                    raise ValidationError('Current policy/review differs; explicit successor required')
                if j.attempts > v['max_attempts']:
                    raise ValidationError('Original attempt budget exhausted')
                if access(j.actor, j.plan.case, 'operate') != j.intent['case_ids']:
                    raise ValidationError('Source case inventory changed')
                if j.kind == 'archive':
                    receipt = native.archive(j.intent)
                else:
                    original = Job.objects.get(pk=j.intent['archive_job'], plan=j.plan, kind='archive', status='confirmed')
                    receipt = native.restore(j.intent, original.intent)
            finish(j, receipt)
        except (ValidationError, PermissionDenied, OSError, psycopg.Error) as exc:
            j.status = 'held'
            # NativeArchiveHold contains code-owned constant messages only, never stderr.
            j.error = ('native: ' + exc.messages[0])[:120] if isinstance(exc, native.NativeArchiveHold) else 'native_recovery_held'
            j.save(update_fields=['status', 'error'])
    return True


def finish(job, receipt):
    job.status, job.receipt, job.error = 'confirmed', receipt, ''
    job.save(update_fields=['status', 'receipt', 'error'])


@transaction.atomic
def report(actor, case_id, plan_id):
    p = Plan.objects.select_related('case').get(pk=plan_id, case_id=case_id)
    access(actor, p.case, 'read', locked=True)
    result = {'scope': 'native_database_managed_attachments_isolated_only', 'plan': p.pk,
              'production_activation': False, 'external_repositories_included': False,
              'live_authority_restored': False, 'authorization_current': False,
              'human_recovery_review_current': False, 'holds': [], 'jobs': []}
    try:
        authorization(p)
        result['authorization_current'] = True
    except (ValidationError, PermissionDenied):
        result['holds'].append('Current policy/runtime identity and independent authorization are required')
    recovered = None
    for j in Job.objects.filter(plan=p).order_by('pk'):
        try:
            current = lookup(j)
            valid = j.status == 'confirmed' and current == j.receipt
        except (ValidationError, OSError, psycopg.Error):
            valid = False
        if j.kind == 'restore' and valid:
            recovered = j
        result['jobs'].append({'id': j.pk, 'kind': j.kind, 'status': j.status, 'attempts': j.attempts, 'physical_receipt_current': valid})
    if recovered:
        human = Review.objects.filter(plan=p, phase='recovered').order_by('-pk').first()
        try:
            expected = {**pin(p), 'recovery_receipt_sha256': native.digest(recovered.receipt)}
            if human and human.decision == 'approve' and human.pin == expected:
                _, v = rules(p)
                access(human.actor, p.case, 'review', locked=True)
                principal(human.actor, p, 'review', v)
                result['human_recovery_review_current'] = True
        except (ValidationError, PermissionDenied):
            pass
    return result

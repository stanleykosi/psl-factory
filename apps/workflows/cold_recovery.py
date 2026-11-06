"""Fresh-authority cold restore. Every ORM query is against the control database."""
from datetime import timedelta
import hmac
import re
import psycopg
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import connection, transaction
from django.db.models import Q
from django.utils import timezone
from apps.core.models import Case
from apps.identity.models import Grant
from apps.identity.services import require
from apps.policy.services import active_component, reference_values, decision_authority, resolve
from apps.policy.cold_recovery_validators import COMPONENT, REF
from apps.documents.contracts import validate
from adapters.forecast import obj
from adapters import cold_application_recovery as adapter
from adapters import native_application_archive as n
from .cold_recovery_models import ColdControlIdentity as Identity, ColdRecoveryPlan as Plan, ColdRecoveryReview as Review, ColdRecoveryJob as Job

PAYLOAD = obj({k: REF for k in ['archive_ref', 'target_ref', 'key_ref']})


def control():
    r = settings.COLD_RECOVERY
    try:
        assert re.fullmatch(r'(?:test_)?psl_cold_[a-z0-9_]{1,40}', connection.settings_dict['NAME'])
        assert connection.settings_dict['NAME'] == r['control_database']
        identity = Identity.objects.get(reference=r['control_ref'])
        assert isinstance(r['control_secret'], bytes) and len(r['control_secret']) == 32
        assert hmac.compare_digest(identity.secret_sha256, n.digest(r['control_secret']))
    except (KeyError, AssertionError, TypeError, Identity.DoesNotExist):
        raise PermissionDenied('Separate independently provisioned cold control identity required') from None


def provisioned(actor, purpose):
    entry = settings.COLD_RECOVERY.get('principals', {}).get(str(actor.pk), {})
    if entry.get('username') != actor.username or purpose not in entry.get('purposes', []):
        raise PermissionDenied('Fresh deployment identity lacks this exact recovery purpose')


def access(actor, case, purpose='read', locked=True):
    control()
    if locked:
        Case.objects.select_for_update().get(pk=case.pk)
        # Stable ordering across independent human authority checks.
        list(get_user_model().objects.select_for_update().order_by('pk'))
        list(Grant.objects.select_for_update().filter(case=case).order_by('pk'))
        actor.refresh_from_db()
    require(actor, case, 'case.read')
    require(actor, case, 'cold.' + purpose)
    provisioned(actor, purpose)


@transaction.atomic
def capture(actor, case_id, reference, payload):
    c = Case.objects.get(pk=case_id)
    access(actor, c, 'capture')
    validate(PAYLOAD, payload)
    if not reference.strip() or len(reference) > 100:
        raise ValidationError('Stable bounded recovery reference required')
    proof = adapter.metadata(payload)
    value = {**payload, 'archive_sha256': proof['archive_sha256'], 'manifest_sha256': proof['manifest_sha256'],
             'runtime_sha256': proof['runtime_sha256']}
    old = Plan.objects.filter(case=c, reference=reference).order_by('-version').first()
    if old and old.payload == value:
        return old
    return Plan.objects.create(case=c, reference=reference, version=old.version + 1 if old else 1,
                               payload=value, sha256=n.digest(value), actor=actor)


def criteria(p):
    cfg = active_component(COMPONENT, p.case)
    v = reference_values(cfg)[0]
    if any(v[k] != p.payload[k] for k in ['archive_ref', 'target_ref', 'key_ref']):
        raise ValidationError('Current criteria and exact recovery request differ')
    if Plan.objects.filter(case=p.case, reference=p.reference, version__gt=p.version).exists():
        raise ValidationError('Explicit current recovery successor required')
    return cfg, v


def principal(actor, p, purpose, v):
    access(actor, p.case, purpose)
    key = 'reviewer' if purpose == 'review' else 'operator'
    if actor.pk != v[key + '_id']:
        raise PermissionDenied('Only the configured fresh purpose principal may act')
    decision_authority(actor, p.case, v[key + '_role'])


def pin(p):
    cfg, v = criteria(p)
    proof = adapter.metadata(p.payload)
    if any(proof[k] != p.payload[k] for k in ['archive_sha256', 'manifest_sha256', 'runtime_sha256']):
        raise ValidationError('Captured exact physical recovery binding changed; capture a successor')
    return {'plan_sha256': p.sha256, 'policy': cfg.pk,
            'role_policy': active_component('D05.role_principal_assignments', p.case).pk,
            'runtime_sha256': proof['runtime_sha256']}


@transaction.atomic
def review(actor, case_id, plan_id, phase, decision, rationale, operation_key):
    p = Plan.objects.select_related('case').get(pk=plan_id, case_id=case_id)
    _, v = criteria(p)
    principal(actor, p, 'review', v)
    if p.actor_id == actor.pk or Job.objects.filter(plan=p, actor=actor).exists():
        raise PermissionDenied('Independent human reviewer cannot prepare this request or effect')
    if phase not in ['authorize', 'recovered'] or decision not in ['approve', 'hold'] or not rationale.strip() or len(rationale) > 1000 or not operation_key or len(operation_key) > 100:
        raise ValidationError('Explicit bounded human decision, rationale and idempotency key required')
    evidence = pin(p)
    if phase == 'recovered':
        j = Job.objects.filter(plan=p, status='confirmed').first()
        if not j or adapter.receipt(j.intent) != j.receipt or any(j.intent['pin'].get(k) != x for k, x in evidence.items()):
            raise ValidationError('Current same-intent physical recovered receipt required')
        evidence['receipt_sha256'] = n.digest(j.receipt)
    values = dict(actor=actor, phase=phase, decision=decision, rationale=rationale, pin=evidence)
    old = Review.objects.filter(plan=p, operation_key=operation_key).first()
    if old:
        if any(getattr(old, k) != x for k, x in values.items()):
            raise ValidationError('Human decision key already binds another intent')
        return old
    return Review.objects.create(plan=p, operation_key=operation_key, **values)


def authorization(p):
    evidence = pin(p)
    r = Review.objects.filter(plan=p, phase='authorize').order_by('-pk').first()
    _, v = criteria(p)
    if not r or r.decision != 'approve' or r.pin != evidence or timezone.now() >= r.created_at + timedelta(seconds=v['authorization_valid_seconds']):
        raise ValidationError('Current independent fresh-authority approval required')
    principal(get_user_model().objects.get(pk=r.actor_id), p, 'review', v)
    return {**evidence, 'authorization_review': r.pk}


@transaction.atomic
def reserve(actor, case_id, plan_id):
    p = Plan.objects.select_related('case').get(pk=plan_id, case_id=case_id)
    _, v = criteria(p)
    principal(actor, p, 'operate', v)
    evidence = authorization(p)
    old = Job.objects.filter(plan=p).first()
    if old:
        return old
    key = n.digest({'cold_plan': p.pk, 'sha256': p.sha256})
    intent = {'format': n.FORMAT, 'operation_key': key, 'plan': p.pk, 'plan_sha256': p.sha256,
              'payload': p.payload, 'rules': v, 'pin': evidence, 'runtime_sha256': evidence['runtime_sha256']}
    return Job.objects.create(plan=p, operation_key=key, actor=actor, intent=intent)


@transaction.atomic
def retry(actor, case_id, job_id):
    j = Job.objects.select_for_update().select_related('plan__case').get(pk=job_id, plan__case_id=case_id)
    _, v = criteria(j.plan)
    principal(actor, j.plan, 'operate', v)
    if j.status not in ['held', 'unknown']:
        raise ValidationError('Only held or uncertain exact intents can be reconciled')
    j.status = 'pending'
    j.save(update_fields=['status'])
    return j


def finish(j, receipt):
    j.status, j.receipt, j.error = 'confirmed', receipt, ''
    j.save(update_fields=['status', 'receipt', 'error'])


def run_once():
    control()
    with transaction.atomic():
        j = Job.objects.select_for_update(skip_locked=True).filter(Q(status__in=['pending', 'unknown']) | Q(status='leased', lease_until__lt=timezone.now())).order_by('pk').first()
        if not j:
            return False
        j.status, j.fence, j.attempts = 'leased', j.fence + 1, j.attempts + 1
        j.lease_until = timezone.now() + timedelta(seconds=j.intent['rules']['lease_seconds'])
        j.save(update_fields=['status', 'fence', 'attempts', 'lease_until'])
        pk, fence = j.pk, j.fence
    with transaction.atomic():
        j = Job.objects.select_for_update().select_related('plan__case', 'actor').get(pk=pk)
        if j.fence != fence or j.status != 'leased':
            return True
        try:
            receipt = adapter.receipt(j.intent)
            if receipt is None:
                _, v = criteria(j.plan)
                principal(j.actor, j.plan, 'operate', v)
                if authorization(j.plan) != j.intent['pin'] or v != j.intent['rules'] or j.attempts > v['max_attempts']:
                    raise ValidationError('Current independent authority or original attempt budget differs')
                receipt = adapter.restore(j.intent)
            finish(j, receipt)
        except (ValidationError, PermissionDenied, OSError, psycopg.Error):
            j.status, j.error = 'held', 'cold_recovery_held'
            j.save(update_fields=['status', 'error'])
    return True


@transaction.atomic
def report(actor, case_id, plan_id):
    p = Plan.objects.select_related('case').get(pk=plan_id, case_id=case_id)
    access(actor, p.case)
    result = {'plan': p.pk, 'source_database_needed': False, 'production_activation': False,
              'live_authority_restored': False, 'authorization_current': False, 'human_recovered_review_current': False,
              'physical_receipt_current': False, 'holds': [], 'status': 'unreserved'}
    result['policy_dependencies'] = [{'component': key, 'status': resolve(key,p.case).status}
                                     for key in [COMPONENT,'D05.role_principal_assignments']]
    result['bindings'] = {key:p.payload[key] for key in ['archive_ref','target_ref','archive_sha256','manifest_sha256','runtime_sha256']}
    try:
        authorization(p)
        result['authorization_current'] = True
    except (ValidationError, PermissionDenied, OSError):
        result['holds'].append('Current fresh criteria, identity and independent human authorization required')
    j = Job.objects.filter(plan=p).first()
    if j:
        result.update(status=j.status, attempts=j.attempts, job=j.pk)
        try:
            result['physical_receipt_current'] = j.status == 'confirmed' and adapter.receipt(j.intent) == j.receipt
            human = Review.objects.filter(plan=p, phase='recovered').order_by('-pk').first()
            if human and human.decision == 'approve' and result['physical_receipt_current']:
                _, v = criteria(p)
                principal(human.actor, p, 'review', v)
                result['human_recovered_review_current'] = human.pin == {**pin(p), 'receipt_sha256': n.digest(j.receipt)}
        except (ValidationError, PermissionDenied, OSError, psycopg.Error):
            result['holds'].append('Current independent physical recovery or reviewer evidence unavailable')
    return result

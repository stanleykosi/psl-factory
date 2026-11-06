import hashlib
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Max
from apps.identity.services import require
from .models import Audit, Case, Evidence


def event(actor, case, action, **data):
    return Audit.objects.create(actor=actor, case=case, action=action, data=data)


def lock_case(actor, case_id, action, expected=None):
    from .read_observation import assert_command_allowed
    assert_command_allowed()
    case = Case.objects.select_for_update().get(pk=case_id)
    require(actor, case, action)
    if expected is not None and case.revision != expected:
        raise ValidationError('Stale revision; refresh before retrying')
    return case


def bump(case):
    case.revision += 1
    case.save(update_fields=['revision'])


@transaction.atomic
def add_evidence(actor, case_id, kind, body, source, expected=None):
    case = lock_case(actor, case_id, 'evidence.add', expected)
    if not body.strip() or not source.strip() or len(body) > 100000:
        raise ValidationError('Evidence needs content, a source, and at most 100,000 characters')
    version = (case.evidence.filter(kind=kind).aggregate(v=Max('version'))['v'] or 0) + 1
    evidence = Evidence.objects.create(case=case, kind=kind, version=version, body=body,
        source=source, sha256=hashlib.sha256(body.encode()).hexdigest(), created_by=actor)
    event(actor, case, 'evidence.added', evidence=evidence.pk, kind=kind, version=version, sha256=evidence.sha256)
    bump(case)
    return evidence

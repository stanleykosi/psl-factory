"""Versioned mapping for a human-recorded milestone after verified go-live."""
from django.core.exceptions import ValidationError
from django.db.models import Exists, OuterRef

from adapters.forecast import obj
from apps.core.evidence_access import public_evidence
from apps.core.models import Evidence
from apps.documents.contracts import validate
from apps.identity.models import Grant
from apps.pmo.models import Baseline, DeliveryDossier
from .document_validators import typed


COMPONENT = 'OPS.go_live_milestone_mapping'
SCHEMA = 'schema:psl/go-live-milestone-mapping/v1'
ID = {'type': 'integer', 'minimum': 1, 'maximum': 9223372036854775807}
VALUE = obj({
    'dossier_id': ID,
    'baseline_signature_id': ID,
    'milestone_name': {'type': 'string', 'minLength': 1, 'maxLength': 200},
})


def current_sources(case, kind):
    source_grants = Grant.objects.filter(
        case=case, user_id=OuterRef('created_by_id'), user__is_active=True,
        action='evidence.add', active=True,
    )
    return public_evidence(Evidence.objects.filter(case=case, kind=kind)).filter(Exists(source_grants))


def baseline_signature(case, dossier):
    baseline = Baseline.objects.filter(case=case).values(
        'plan_id', 'costing_id', 'sow_id', 'signed_id',
    ).first()
    signed_id = baseline.pop('signed_id') if baseline else None
    if not signed_id or dossier.baseline != baseline:
        raise ValidationError('The milestone mapping needs this dossier and its exact current signed baseline.')
    return signed_id


def validate_mapping(value, case, decision_id):
    validate(VALUE, value)
    name = value['milestone_name']
    if name != name.strip() or not name or not name.isprintable():
        raise ValidationError('Enter the exact approved milestone name without surrounding spaces or control characters.')
    if case.kind != 'project':
        raise ValidationError('A go-live milestone mapping must belong to one project.')
    dossier = DeliveryDossier.objects.filter(case=case, pk=value['dossier_id']).only('baseline').first()
    if not dossier or value['baseline_signature_id'] != baseline_signature(case, dossier):
        raise ValidationError('Choose the exact project dossier and its current baseline signature.')
    if not current_sources(case, 'policy_decision').filter(pk=decision_id).exists():
        raise ValidationError('Choose current owner-decision evidence from this project.')
    return value


def validate_reference(target, case):
    value = typed(target, SCHEMA, VALUE)
    return validate_mapping(value, case, target.evidence_id)

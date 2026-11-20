"""Customer-stated facts recorded with one exact received bid revision."""

from dataclasses import dataclass
from urllib.parse import urlsplit

from django.core.exceptions import ValidationError
from django.core.validators import URLValidator, validate_email

from apps.core.evidence_access import public_evidence
from apps.core.models import Evidence
from apps.identity.services import require
from .models import RFPIntakeSourceContext


METHODS = (('email', 'Email'), ('portal', 'Portal'), ('by_hand', 'By hand'), ('not_stated', 'Not stated'))


@dataclass(frozen=True)
class SourceContext:
    prospect_name: str | None = None
    submission_method: str | None = None
    submission_target: str | None = None

    @property
    def recorded(self):
        return bool(self.prospect_name or self.submission_method or self.submission_target)


def text(value, limit):
    if value is None:
        return None
    if not isinstance(value, str) or len(value) > limit or any(not char.isprintable() for char in value):
        raise ValidationError('Enter a short, plain source fact.')
    return value.strip() or None


def validate(value, attested):
    if value is None:
        value = SourceContext()
    if not isinstance(value, SourceContext) or type(attested) is not bool:
        raise ValidationError('Use the typed customer instructions and confirm their source.')
    prospect = text(value.prospect_name, 160)
    method = text(value.submission_method, 20)
    target = text(value.submission_target, 320)
    if method and method not in dict(METHODS):
        raise ValidationError('Choose how the customer said to submit the response.')
    if target and method in (None, 'not_stated'):
        raise ValidationError('Choose a stated submission method before recording its destination.')
    if target and method == 'email':
        validate_email(target)
    if target and method == 'portal' and ('://' in target or target.startswith('//')):
        try:
            URLValidator(schemes=['http', 'https'])(target)
            parts = urlsplit(target)
            if parts.username or parts.password:
                raise ValidationError('Enter the portal address without credentials.')
        except ValueError as exc:
            raise ValidationError('Enter a valid portal name or address.') from exc
    value = SourceContext(prospect, method, target)
    if value.recorded and not attested:
        raise ValidationError('Confirm these facts appear in the received source.')
    return value


def from_intake(intake):
    fields = RFPIntakeSourceContext.objects.filter(intake=intake).values_list(
        'prospect_name', 'submission_method', 'submission_target').first()
    return SourceContext(*fields) if fields else SourceContext()


def authorize_read(actor, case):
    for action in ('case.read', 'rfp.read', 'document.read'):
        require(actor, case, action)


def authorize_write(actor, case):
    authorize_read(actor, case)
    require(actor, case, 'rfp.intake')
    require(actor, case, 'evidence.add')


def require_source(case, evidence):
    if not public_evidence(Evidence.objects.filter(case=case, pk=evidence.pk, kind='rfp_intake')).exists():
        raise ValidationError('Select the exact available received bid source.')
    require(evidence.created_by, case, 'case.read')
    require(evidence.created_by, case, 'evidence.add')


def visible(actor, case, intake):
    authorize_read(actor, case)
    if intake.rfp.case_id != case.pk:
        return None
    if not RFPIntakeSourceContext.objects.filter(intake=intake).exists():
        return None
    authorize_write(intake.actor, case)
    evidence = Evidence.objects.select_related('created_by').only('id', 'source', 'version', 'created_by__is_active').filter(
        case=case, pk=intake.evidence_id, kind='rfp_intake').first()
    if evidence is None:
        return None
    try:
        require_source(case, evidence)
    except ValidationError:
        return None
    from .rfp_intake_upload import SOURCE, attachment_for
    if evidence.source == SOURCE and attachment_for(actor, case, intake) is None:
        return None
    data = from_intake(intake)
    return {'facts': data, 'method_label': dict(METHODS).get(data.submission_method, 'Unknown'),
            'source_version': evidence.version}

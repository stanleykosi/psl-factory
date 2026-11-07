"""P60 owner-supplied applicability, independent of SOW/PRD exemptions."""
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from .document_validators import typed, ROLES
from .signature_validators import obj, ID, TEXT

COMPONENT = 'D11.change_go_live_client_applicability'
SCHEMA = 'schema:psl/change-go-live-client-applicability/v1'
PIN = obj({'id': ID, 'version': ID, 'sha256': {'type': 'string', 'pattern': '^[a-f0-9]{64}$'}})
OWNER = obj({'actor_id': ID, 'role': {'enum': ROLES},
             'authority': obj({'D05.role_principal_assignments': ID})})
ENTRY = obj({'change_version_id': ID, 'authorization_id': ID,
             'requirement': {'enum': [None, 'unresolved', 'required', 'not_applicable']},
             'source': PIN, 'owner': {'anyOf': [OWNER, {'type': 'null'}]}, 'rationale': TEXT})
VALUE = obj({'protocol': {'const': 'change-go-live-client-applicability/v1'},
             'case_id': {'type': 'string', 'format': 'uuid'},
             'entries': {'type': 'array', 'maxItems': 100, 'items': ENTRY},
             'allow_synthetic': {'type': 'boolean'}})
OWNER_QUESTION = ('For this exact change-go-live artifact, does Client acceptance apply? '
                  'Supply the accountable owner decision, source and current authority. '
                  'Internal/Standard/Emergency labels, client_facing=false and baseline exemptions do not decide it. '
                  'PM acceptance and existing delivery, recipient and release controls remain required.')


def validate_reference(component, target, case, runtime=False):
    from apps.pmo.models import ChangeAuthorization
    from apps.pmo.services import subject
    from apps.pmo.go_live_attestations import pin
    from apps.identity.services import require
    from .services import decision_authority
    value = typed(target, SCHEMA, VALUE)
    if case.kind != 'project' or value['case_id'] != str(case.pk) or value['allow_synthetic'] != case.synthetic:
        raise ValidationError('Exact project and synthetic/operational applicability scope required')
    ids = [entry['authorization_id'] for entry in value['entries']]
    if len(ids) != len(set(ids)):
        raise ValidationError('Each change authorization has one explicit applicability entry')
    for entry in value['entries']:
        auth = ChangeAuthorization.objects.filter(pk=entry['authorization_id'], version_id=entry['change_version_id'], version__change__case=case).first()
        if not auth:
            raise ValidationError('Applicability target must identify this case exact change version and authorization')
        source = subject(case, entry['source']['id'], 'policy_decision')
        if pin(source) != entry['source']:
            raise ValidationError('Exact applicability source version and hash required')
        if entry['requirement'] in [None, 'unresolved']:
            if entry['owner'] is not None:
                raise ValidationError('Unresolved applicability must not claim an owner decision')
            continue
        if not runtime:
            validate_owner(case, entry)
    return value


def unresolved_draft(case):
    """No owner, role, decision, target or applicability is guessed."""
    return {'protocol': 'change-go-live-client-applicability/v1', 'case_id': str(case.pk),
            'entries': [], 'allow_synthetic': case.synthetic}


def validate_owner(case, entry):
    from apps.identity.services import require
    from .services import decision_authority
    from apps.pmo.services import subject
    from apps.pmo.go_live_attestations import pin
    if pin(subject(case, entry['source']['id'], 'policy_decision')) != entry['source']:
        raise ValidationError('Current exact applicability source pin required')
    owner = entry['owner']
    if owner is None:
        raise ValidationError('Resolved applicability requires an explicit existing accountable owner')
    actor = get_user_model().objects.filter(pk=owner['actor_id'], is_active=True).first()
    if not actor:
        raise ValidationError('Applicability owner principal is unavailable')
    require(actor, case, 'case.read')
    if decision_authority(actor, case, owner['role']) != owner['authority']:
        raise ValidationError('Current exact owner role authority required, not a claimed title')

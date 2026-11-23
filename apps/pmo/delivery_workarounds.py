"""Evidence linking a reviewed client workaround to one returned Planning decision."""

from xml.etree.ElementTree import ParseError
from zipfile import BadZipFile

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from adapters import case_uploads, client_uat as contract, upload_text
from adapters.forecast import obj
from apps.core.models import Audit
from apps.core.services import bump, event, lock_case
from apps.documents.contracts import digest, validate
from apps.identity.services import require
from apps.policy.services import decision_authority

from .clocks import aware
from .commercial import note_required
from .models import DeliveryRecord, DeliverySource


KIND = 'planning_issue_workaround'
EVENT = 'delivery.planning_workaround_linked'
REFERENCE = 'psl:planning-workaround:'
SCHEMA = obj({
    'format': {'const': 'psl.planning-workaround/v1'},
    **{key: contract.ID for key in ('return_id', 'issue_id', 'issue_state_id', 'candidate_id', 'response_id', 'review_id', 'proof_id')},
    **{key: contract.HASH for key in ('response_sha256', 'review_sha256', 'proof_sha256')},
    'authority': contract.AUTH,
    'note': {'type': 'string', 'minLength': 1, 'maxLength': 4000},
})


def authority(actor, case):
    from . import client_uat

    client_uat.readable(actor, case)
    for action in ('issue.read', 'delivery.manage', 'client_uat.proof.read'):
        require(actor, case, action)
    return decision_authority(actor, case, 'PM')


def origin(dossier, prior):
    """Find the exact blocking decision behind either approval remedy."""
    if prior is None:
        return None
    if prior.data.get('verdict') in ('return', 'reject') and prior.data.get('blocking_issue'):
        return prior
    remedy = prior.data.get('issue_remedy')
    if not remedy:
        return None
    # Legacy fixed-issue approvals point directly to the blocking decision.
    decision_id = prior.data.get('blocking_decision_id') or remedy.get('return_id') or prior.parent_id
    blocking = DeliveryRecord.objects.filter(dossier=dossier, kind='planning_decision', pk=decision_id,
        data__verdict__in=('return', 'reject'), data__blocking_issue__issue=remedy.get('issue')).first()
    if not blocking:
        raise ValidationError('The original blocking Planning decision is unavailable.')
    return blocking


def exact_response(actor, dossier, returned, issue, response, review_id=None):
    from . import client_uat

    if not response or response.dossier_id != dossier.pk or response.payload.get('outcome') != 'approved_with_workaround':
        raise ValidationError('A current reviewed client workaround for this delivery candidate is required.')
    if aware(response.payload['responded_at']) < returned.created_at:
        raise ValidationError('The client workaround must respond to this Planning return.')
    if not contract.mentions(response.payload['workaround'], issue.reference, identifier=True):
        raise ValidationError('The recorded workaround must identify the exact linked issue.')
    client_uat.private_reader(actor, response)
    selected = response.verifications.filter(adapter=contract.REVIEW).select_related('actor').order_by('-pk').first()
    if not selected or (review_id is not None and selected.pk != review_id):
        raise ValidationError('Review the current client proof before using it for Planning.')
    if client_uat.current_review(selected.actor, response).pk != selected.pk:
        raise ValidationError('The reviewed client evidence has changed.')
    return selected


def option(actor, dossier, returned, issue):
    """Expose only an exact current, readable response with reviewed source metadata."""
    from . import client_uat

    if not returned or returned.data.get('verdict') != 'return' or not issue or issue.current.status in ('Resolved', 'Closed'):
        return None
    try:
        authority(actor, dossier.case)
        target = client_uat.head(dossier, contract.TARGET)
        response = client_uat.head(dossier, contract.RESPONSE, target.pk) if target else None
        review = exact_response(actor, dossier, returned, issue, response)
    except (PermissionDenied, ValidationError):
        return None
    return {'response_id': response.pk, 'review_id': review.pk, 'return_id': returned.pk,
            'issue_state_id': issue.current_id}


def written_proof(actor, response, issue_ref):
    from . import client_uat

    unreadable = (OSError, ValidationError, ValueError, BadZipFile, ParseError, IndexError, ImportError)
    try:
        from pypdf.errors import PdfReadError
    except ImportError:
        pass
    else:
        unreadable += (PdfReadError,)
    for proof in client_uat.proof_rows(actor, response):
        try:
            text = upload_text.extract(proof.name, case_uploads.read(proof))
        except unreadable:
            continue
        if (contract.mentions(text, issue_ref, identifier=True)
                and contract.mentions(text, response.dossier.candidate.reference, identifier=True)
                and contract.mentions(text, response.payload['workaround'])):
            return proof
    raise ValidationError('The same reviewed file must name this issue, delivery version and approved workaround.')


@transaction.atomic
def record(actor, case_id, dossier_id, expected, *, return_id, issue_state_id, response_id, review_id, note):
    from . import client_uat, delivery

    case = lock_case(actor, case_id, 'delivery.manage', expected)
    if any(type(value) is not int or value < 1 for value in (expected, return_id, issue_state_id, response_id, review_id)):
        raise ValidationError('Choose the exact current return, issue and reviewed client response.')
    grants = authority(actor, case)
    dossier = delivery.dossier_for(case, dossier_id)
    delivery.ensure_open(dossier)
    if delivery.latest(dossier, 'release_outcome', False):
        raise ValidationError('An actual release is already recorded. Use its separate follow-up controls.')
    returned = origin(dossier, delivery.latest(dossier, 'planning_decision', False))
    if not returned or returned.data.get('verdict') != 'return' or returned.pk != return_id:
        raise ValidationError('Select the current returned Planning decision.')
    issue = delivery.planning_issue(dossier, returned.data['blocking_issue']['issue'])
    if issue.current_id != issue_state_id or issue.current.status in ('Resolved', 'Closed'):
        raise ValidationError('The linked issue changed. Review its current state.')
    note_required(note)
    response = client_uat.exact(case, response_id, contract.RESPONSE)
    review = exact_response(actor, dossier, returned, issue, response, review_id)
    proof = written_proof(actor, response, issue.reference)
    payload = {'format': 'psl.planning-workaround/v1', 'return_id': returned.pk, 'issue_id': issue.pk,
               'issue_state_id': issue.current_id, 'candidate_id': dossier.candidate_id, 'response_id': response.pk,
               'response_sha256': digest(response.payload), 'review_id': review.pk, 'review_sha256': digest(review.result),
               'proof_id': proof.pk, 'proof_sha256': proof.sha256, 'authority': grants, 'note': note.strip()}
    validate(SCHEMA, payload)
    prior = head(dossier, returned)
    if prior and prior.actor_id == actor.pk and prior.payload == payload:
        return prior
    source = DeliverySource.objects.create(dossier=dossier, kind=KIND, external_ref=REFERENCE + digest(payload),
                                           evidence_id=response.evidence_id, payload=payload, actor=actor)
    event(actor, case, EVENT, source=source.pk, return_id=returned.pk, sha256=digest(payload))
    bump(case)
    return source


def head(dossier, returned):
    return dossier.sources.filter(kind=KIND, payload__return_id=returned.pk).select_related('actor').order_by('-pk').first()


def current(dossier, returned, issue):
    from . import client_uat

    source = head(dossier, returned)
    if source is None:
        return None
    payload = source.payload
    validate(SCHEMA, payload)
    fingerprint = digest(payload)
    if (source.external_ref != REFERENCE + fingerprint or not Audit.objects.filter(
            case=dossier.case, actor_id=source.actor_id, action=EVENT,
            data={'source': source.pk, 'return_id': returned.pk, 'sha256': fingerprint}).exists()):
        raise ValidationError('The recorded client workaround has no current source provenance.')
    if ((payload['return_id'], payload['issue_id'], payload['issue_state_id'], payload['candidate_id'])
            != (returned.pk, issue.pk, issue.current_id, dossier.candidate_id)
            or issue.current.status in ('Resolved', 'Closed')):
        raise ValidationError('The client workaround needs review against the current linked issue.')
    if authority(source.actor, dossier.case) != payload['authority']:
        raise ValidationError('The original workaround recorder authority changed.')
    response = client_uat.exact(dossier.case, payload['response_id'], contract.RESPONSE)
    review = exact_response(source.actor, dossier, returned, issue, response, payload['review_id'])
    if (source.evidence_id != response.evidence_id or payload['response_sha256'] != digest(response.payload)
            or payload['review_sha256'] != digest(review.result)
            or not any(proof['id'] == payload['proof_id'] and proof['sha256'] == payload['proof_sha256']
                       for proof in response.payload['proofs'])):
        raise ValidationError('The reviewed workaround evidence no longer matches the recorded link.')
    return {'kind': KIND, 'source_id': source.pk, 'return_id': returned.pk, 'issue': issue.pk,
            'state': issue.current_id, 'recorder_id': source.actor_id, 'sha256': fingerprint}


def approval_statement(actor, dossier, remedy):
    """Read the attested workaround under ordinary client-response scope."""
    from . import client_uat

    client_uat.readable(actor, dossier.case)
    source = dossier.sources.filter(kind=KIND, pk=remedy['source_id']).first()
    if not source or digest(source.payload) != remedy['sha256']:
        raise ValidationError('The recorded workaround is no longer available.')
    response = client_uat.exact(dossier.case, source.payload['response_id'], contract.RESPONSE)
    client_uat.current_response(actor, response)
    return response.payload['workaround']

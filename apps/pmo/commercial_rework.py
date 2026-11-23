"""Reviewed file advice -> editable revision -> fresh native commercial decisions.

No model output grants authority, sets financial terms or publishes a document.
The existing eight-role worker and native proposal/document controls are reused.
"""
import json
from uuid import UUID

from django.core.exceptions import PermissionDenied, ValidationError
from django.contrib.auth import get_user_model
from django.db import transaction
from django.shortcuts import get_object_or_404

from adapters import commercial_rework as contract
from apps.agents.file_draft_reviews import draft_digest, reviewed_output
from apps.agents.models import AgentJob
from apps.agents.upload_jobs import authorize
from apps.agents.upload_views import queue_draft
from apps.core.evidence_access import public_evidence
from apps.core.models import Audit, Evidence
from apps.core.services import add_evidence, event, lock_case
from apps.documents.contracts import digest
from apps.documents.models import Review
from apps.identity.services import require
from . import commercial, commercial_client_response as witness
from .models import BaselineAdoption
from .signatures import pin


def current_input(actor, case, metadata):
    value, response = witness.read(actor, case, metadata)
    if (value['outcome'] != 'changes_requested' or witness.latest(case).pk != metadata.pk
            or response.revision.responses.order_by('-pk').first().pk != response.pk):
        raise ValidationError('Use the current client request for changes.')
    commercial.current_revision(case, response.revision_id)
    if BaselineAdoption.objects.filter(revision=response.revision).exists():
        raise ValidationError('An adopted agreement needs a separate controlled change.')
    return value, response


def reviewed_job(actor, case, metadata, job_id):
    proofs = witness.proof_rows(actor, case, metadata)
    job = AgentJob.objects.select_related('upload__case', 'actor', 'file_review__evidence').filter(
        pk=job_id, upload__in=proofs, actor_id=metadata.created_by_id, role='A04', status='reviewed').first()
    if not job or not hasattr(job, 'file_review'):
        raise ValidationError('Review a planning-agent draft from the exact client proof first.')
    authorize(job.actor, job.upload)
    require(job.actor, case, 'document.review')
    evidence = job.file_review.evidence
    if (evidence.case_id != case.pk or evidence.created_by_id != job.actor_id
            or evidence.source != f'agent-draft:{job.pk}:sha256:{job.upload.sha256}'
            or evidence.sha256 != witness.digest_text(evidence.body)):
        raise ValidationError('The reviewed planning draft no longer matches its original proof.')
    result = reviewed_output(job, evidence)
    latest_review = Review.objects.filter(case=case, evidence=evidence).order_by('-pk').first()
    if not latest_review or latest_review.verdict != 'accepted':
        raise ValidationError('The planning draft needs a current accepted human review.')
    if not get_user_model().objects.filter(pk=latest_review.actor_id, is_active=True).exists():
        raise PermissionDenied('The planning review needs a current active reviewer.')
    require(latest_review.actor, case, 'document.review')
    return job, evidence, result


def source_pins(case, values):
    if not isinstance(values, dict) or set(values) != set(contract.SOURCE_KINDS):
        raise ValidationError('Use the five exact source slots; leave unknown sources blank.')
    result = {}
    for kind, pk in values.items():
        if pk is None:
            result[kind] = None
            continue
        row = public_evidence(Evidence.objects.filter(case=case, kind=kind, pk=pk)).defer('body').first()
        if not row:
            raise ValidationError('Select this project’s exact ' + kind.replace('_', ' ') + ' source.')
        result[kind] = pin(row)
    return result


def latest(case):
    return Evidence.objects.filter(case=case, kind=contract.KIND).defer('body').select_related('created_by').order_by('-version').first()


def read(actor, case, evidence):
    witness.readable(actor, case)
    if not evidence or evidence.case_id != case.pk or evidence.kind != contract.KIND:
        raise ValidationError('Select this project’s retained revision draft.')
    if actor.pk != evidence.created_by_id:
        require(actor, case, 'commercial.proof.read')
    witness.witness(evidence.created_by, case)
    require(evidence.created_by, case, 'commercial.prepare')
    require(evidence.created_by, case, 'agent.extract')
    try:
        value = contract.read(json.loads(evidence.body))
    except (ValueError, TypeError):
        raise ValidationError('The retained revision draft has an unsupported format.') from None
    if (evidence.sha256 != witness.digest_text(evidence.body)
            or evidence.source != contract.PREFIX + value['operation_key']
            or not Audit.objects.filter(case=case, actor=evidence.created_by, action='commercial.rework_drafted',
                data={'evidence': evidence.pk, 'sha256': evidence.sha256}).exists()):
        raise ValidationError('The revision draft has no matching native provenance.')
    metadata = Evidence.objects.filter(case=case, pk=value['witness']['id']).defer('body').first()
    if not metadata or pin(metadata) != value['witness']:
        raise ValidationError('The client request no longer matches its retained source.')
    if witness.read(actor, case, metadata)[1].revision_id != value['revision']:
        raise ValidationError('The revision draft identifies a different delivered proposal.')
    job, review, result = reviewed_job(actor, case, metadata, value['job'])
    if pin(review) != value['review'] or draft_digest(job) != value['draft_sha256']:
        raise ValidationError('The retained planning review changed.')
    return value, metadata, job, result


@transaction.atomic
def ask_agent(actor, case_id, metadata_id, expected):
    case = lock_case(actor, case_id, 'commercial.prepare', expected)
    witness.witness(actor, case)
    metadata = get_object_or_404(Evidence.objects.defer('body'), case=case, pk=metadata_id)
    current_input(actor, case, metadata)
    if actor.pk != metadata.created_by_id:
        raise PermissionDenied('The original witness must request review of their own proof.')
    return [queue_draft(actor, row, 'A04') for row in witness.proof_rows(actor, case, metadata)]


@transaction.atomic
def capture(actor, case_id, metadata_id, job_id, sources, scope, note, confirmed, key, expected, predecessor=None):
    case = lock_case(actor, case_id, 'commercial.prepare', expected)
    witness.witness(actor, case)
    require(actor, case, 'evidence.add')
    metadata = get_object_or_404(Evidence.objects.defer('body'), case=case, pk=metadata_id)
    _, response = current_input(actor, case, metadata)
    if metadata.created_by_id != actor.pk:
        raise PermissionDenied('The original witness must prepare this revision from their own proof.')
    job, review, _ = reviewed_job(actor, case, metadata, job_id)
    try:
        key = str(UUID(str(key)))
    except (TypeError, ValueError, AttributeError):
        raise ValidationError('Reload the revision form before saving.') from None
    commercial.note_required(note)
    value = {'protocol': contract.PROTOCOL, 'operation_key': key, 'predecessor': predecessor,
        'witness': pin(metadata), 'revision': response.revision_id, 'job': job.pk, 'review': pin(review),
        'draft_sha256': draft_digest(job), 'sources': source_pins(case, sources), 'scope': scope,
        'note': note, 'human_confirmed': confirmed, 'cost_or_approval_inferred': False}
    value['command_sha256'] = digest(value)
    contract.read(value)
    old = Evidence.objects.filter(case=case, kind=contract.KIND, source=contract.PREFIX + key).defer('body').first()
    if old:
        prior = read(actor, case, old)[0]
        if prior != value or old.created_by_id != actor.pk:
            raise ValidationError('This revision reference already identifies different details.')
        return old
    head = latest(case)
    if (head.pk if head else None) != predecessor:
        raise ValidationError('A newer revision draft exists. Review it before saving a correction.')
    row = add_evidence(actor, case.pk, contract.KIND, json.dumps(value, sort_keys=True), contract.PREFIX + key)
    event(actor, case, 'commercial.rework_drafted', evidence=row.pk, sha256=row.sha256)
    return row


def prepared(case, evidence):
    return Audit.objects.filter(case=case, action='commercial.rework_prepared', data__evidence=evidence.pk).order_by('-pk').first()


@transaction.atomic
def prepare_revision(actor, case_id, draft_id, expected):
    case = lock_case(actor, case_id, 'commercial.prepare', expected)
    witness.witness(actor, case)
    require(actor, case, 'evidence.add')
    draft = get_object_or_404(Evidence.objects.select_related('created_by').defer('body'), case=case, pk=draft_id)
    value, metadata, _, _ = read(actor, case, draft)
    if draft.created_by_id != actor.pk:
        raise PermissionDenied('The original draft owner must confirm its revised wording.')
    previous = prepared(case, draft)
    if previous:
        from .models import CommercialRevision
        return CommercialRevision.objects.get(pk=previous.data['revision'], dossier__case=case)
    _, response = current_input(actor, case, metadata)
    if latest(case).pk != draft.pk:
        raise ValidationError('Review the current revision draft before preparing the new proposal.')
    unknown = [kind.replace('_', ' ') for kind, source in value['sources'].items() if source is None]
    if unknown:
        raise ValidationError('The draft is saved. Confirm the actual sources before preparing: ' + ', '.join(unknown) + '.')
    sources = {kind: source['id'] for kind, source in value['sources'].items()}
    if source_pins(case, sources) != value['sources']:
        raise ValidationError('The selected source versions changed; review a corrected draft.')
    if (sources == {kind: response.revision.sources[kind] for kind in sources}
            and Evidence.objects.filter(case=case, pk=response.revision.sources['sow'],
                                        sha256=witness.digest_text(value['scope'])).exists()):
        raise ValidationError('The wording and sources match the original. Record what actually changed.')
    sow = add_evidence(actor, case.pk, 'sow', value['scope'], draft.source)
    case.refresh_from_db(fields=['revision'])
    revision = commercial.propose(actor, case.pk, {**sources, 'sow': sow.pk},
        response.evidence_id,
        'Human-reviewed client-requested revision. Fresh commercial decisions and document review are required.', case.revision)
    event(actor, case, 'commercial.rework_prepared', evidence=draft.pk, revision=revision.pk, sow=sow.pk,
          approvals_inherited=False, document_published=False)
    return revision

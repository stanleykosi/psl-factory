"""Security estimate requests use exact bid sources, reviewed wording and sealed receipts."""
from datetime import date

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from adapters.rfp_estimate_requests import SyntheticSecurityInbox, check_manual_receipt
from apps.agents.models import AgentRun, CaseUpload
from apps.core.evidence_access import public_evidence
from apps.core.services import add_evidence, bump, event, lock_case
from apps.documents.contracts import digest
from apps.identity.services import require
from apps.policy.rfp_estimate_request_validators import COMPONENT
from apps.policy.services import decision_authority, reference_values, resolve
from apps.workflows import factory, factory_rfp
from apps.workflows.models import FactoryWork

from . import rfp
from .models import RFPEstimateDispatch, RFPEstimateReceipt, RFPEstimateRequest
from .services import subject


PROVIDER = 'deterministic-security-request-v1'
SOURCE = 'agent_private_rfp_estimate_request'


def access(actor, work, action='read'):
    if work.definition != factory_rfp.DEFINITION:
        raise ValidationError('Select an exact bid.')
    factory.access(actor, work.case, 'factory.read', factory_rfp.DEFINITION)
    require(actor, work.case, 'rfp.read')
    require(actor, work.case, 'rfp.estimate.read')
    if action != 'read':
        require(actor, work.case, f'rfp.estimate.{action}')


def scope(actor, work, action='prepare'):
    access(actor, work, action)
    case = work.case
    root = factory_rfp.subject(work)
    rfp.ensure_open(root)
    assignment = rfp.current_assignment(root)
    if assignment.pm_id != actor.pk:
        raise PermissionDenied('The assigned project manager handles the current estimate request.')
    authority = decision_authority(actor, case, 'PM')
    selected = factory_rfp.inputs(work)
    if root.current_intake_id != selected['intake']:
        raise ValidationError('Open the current received bid before requesting an estimate.')
    latest = root.current_intake.contributions.filter(team='Security').select_related('actor').order_by('-pk').first()
    if latest:
        try:
            require(latest.actor, case, 'rfp.contribute:Security')
        except PermissionDenied:
            pass
        else:
            raise ValidationError('A current Security estimate is already recorded for this bid.')
    requirements = public_evidence(case.evidence.filter(pk=selected['sources']['requirements'], kind='requirements')).first()
    if requirements is None:
        raise ValidationError('Choose the exact current requirements before requesting an estimate.')
    pins = {'work': work.pk, 'head': work.source_head_id, 'intake': root.current_intake_id,
            'assignment': assignment.pk, 'requirements': [requirements.pk, requirements.sha256],
            'authority': authority}
    return root, pins


def routes(case):
    result = resolve(COMPONENT, case)
    if result.status != 'ACTIVE':
        return None, {}
    return result.configuration, {row['channel']: row for row in reference_values(result.configuration)[0]['routes']}


def current_draft(actor, work, pins):
    return AgentRun.objects.filter(case=work.case, actor=actor, provider=PROVIDER, result__scope=pins).select_related(
        'evidence').order_by('-pk').first()


def lock_work(actor, work_id, expected, action):
    work = FactoryWork.objects.select_for_update(of=('self',)).select_related('case', 'source_head').get(pk=work_id)
    work.case = lock_case(actor, work.case_id, f'rfp.estimate.{action}', expected)
    return work


@transaction.atomic
def prepare(actor, work_id, expected):
    work = lock_work(actor, work_id, expected, 'prepare')
    require(actor, work.case, 'agent.rfp')
    root, pins = scope(actor, work)
    draft = current_draft(actor, work, pins)
    if draft is not None:
        return draft
    body = (f'Hello, please provide the Security effort estimate for bid {root.reference}. '
            'Please include the work covered, assumptions and any exclusions. Thank you.')
    evidence = add_evidence(actor, work.case_id, SOURCE, body, 'derived:security-estimate-request', work.case.revision)
    return AgentRun.objects.create(case=work.case, actor=actor, evidence=evidence, provider=PROVIDER,
                                   process_id='P46', result={'scope': pins})


def attachments(actor, work):
    return CaseUpload.objects.filter(case=work.case, actor=actor).order_by('-pk')


@transaction.atomic
def review(actor, work_id, expected, draft_id, channel, due_on, body, evidence_id, attachment_id=None, model_turn=None):
    work = lock_work(actor, work_id, expected, 'prepare')
    root, pins = scope(actor, work)
    draft = current_draft(actor, work, pins)
    if draft is None or draft.pk != draft_id:
        raise ValidationError('Prepare and review the wording against the current bid sources.')
    configuration, destinations = routes(work.case)
    if channel not in destinations:
        raise ValidationError('Set the reviewed Security contact and channel first.')
    route = destinations[channel]
    if type(due_on) is not date or due_on < timezone.localdate() or not isinstance(body, str) or not 1 <= len(body.strip()) <= 4000:
        raise ValidationError('Enter the current request wording and a review deadline from today onward.')
    evidence = subject(work.case, evidence_id, 'policy_decision')
    attachment = None
    if attachment_id is not None:
        attachment = attachments(actor, work).filter(pk=attachment_id).first()
        if not route['allow_attachment'] or attachment is None:
            raise ValidationError('Choose one of your own private files on a route approved for attachments.')
    payload = {'scope': pins, 'route': route, 'body': body.strip(), 'requested_by': due_on.isoformat(),
               'attachment': {'id': attachment.pk, 'sha256': attachment.sha256, 'name': attachment.name} if attachment else None}
    if model_turn is not None:
        from .rfp_estimate_model import checked_answer
        turn = checked_answer(actor, work, pins, model_turn)
        payload['model_draft'] = {'turn': str(turn.pk), 'context': turn.context_hash}
    if work.estimate_requests.filter(dispatch__isnull=False, dispatch__receipt__isnull=True).exists():
        raise ValidationError('Record the result of the original request before reviewing a replacement.')
    prior = work.estimate_requests.order_by('-pk').first()
    if prior and (prior.sha256, prior.configuration_id, prior.evidence_id, prior.actor_id) == (
            digest(payload), configuration.pk, evidence.pk, actor.pk):
        return prior
    request = RFPEstimateRequest.objects.create(work=work, intake_id=root.current_intake_id, draft=draft, evidence=evidence,
        configuration=configuration, attachment=attachment, payload=payload, sha256=digest(payload), actor=actor)
    event(actor, work.case, 'factory.rfp_estimate_reviewed', work=work.pk, request=request.pk)
    bump(work.case)
    return request


@transaction.atomic
def release(actor, work_id, expected, request_id):
    work = lock_work(actor, work_id, expected, 'send')
    _, pins = scope(actor, work, 'send')
    reviewed = work.estimate_requests.order_by('-pk').first()
    if reviewed is None or reviewed.pk != request_id or reviewed.actor_id != actor.pk:
        raise ValidationError('Release the latest exact human-reviewed wording for this bid.')
    prior = RFPEstimateDispatch.objects.filter(request=reviewed).first()
    if prior:
        return prior
    cfg, allowed = routes(work.case)
    route = reviewed.payload['route']
    if (cfg is None or cfg.pk != reviewed.configuration_id or allowed.get(route['channel']) != route
            or reviewed.payload['scope'] != pins or digest(reviewed.payload) != reviewed.sha256):
        raise ValidationError('The current source, destination or authority changed. Review the request again.')
    model_draft = reviewed.payload.get('model_draft')
    if model_draft:
        from uuid import UUID
        from .rfp_estimate_model import checked_answer
        turn = checked_answer(actor, work, pins, UUID(model_draft['turn']))
        if turn.context_hash != model_draft['context']:
            raise ValidationError('The model source check changed. Review the request again.')
    if reviewed.attachment_id:
        from adapters.case_uploads import read
        try:
            read(reviewed.attachment)
        except (OSError, ValidationError) as exc:
            raise ValidationError('The selected private file could not be verified. Check it before releasing the request.') from exc
    dispatch = RFPEstimateDispatch.objects.create(request=reviewed, actor=actor)
    if route['method'] == 'synthetic_mailbox':
        reference = SyntheticSecurityInbox().deliver(dispatch)
        RFPEstimateReceipt.objects.create(dispatch=dispatch, reference=reference, delivered=True, actor=actor)
    event(actor, work.case, 'factory.rfp_estimate_released', work=work.pk, dispatch=dispatch.pk)
    bump(work.case)
    return dispatch


@transaction.atomic
def record_receipt(actor, work_id, expected, dispatch_id, reference, delivered, evidence_id):
    work = lock_work(actor, work_id, expected, 'send')
    access(actor, work, 'send')
    dispatch = RFPEstimateDispatch.objects.filter(pk=dispatch_id, request__work=work, actor=actor).select_related('request').first()
    if (dispatch is None or dispatch.request.payload['route']['method'] != 'manual_receipt'
            or not isinstance(reference, str) or not 1 <= len(reference.strip()) <= 160 or type(delivered) is not bool):
        raise ValidationError('Choose your original manual delivery and its actual result.')
    evidence = subject(work.case, evidence_id, 'rfp_estimate_receipt')
    reference = reference.strip()
    check_manual_receipt(dispatch, evidence, reference, delivered)
    previous = RFPEstimateReceipt.objects.filter(dispatch=dispatch).first()
    if previous:
        if (previous.reference, previous.delivered, previous.evidence_id) != (reference, delivered, evidence.pk):
            raise ValidationError('The original operation already has a different receipt.')
        return previous
    receipt = RFPEstimateReceipt.objects.create(dispatch=dispatch, reference=reference, delivered=delivered,
                                                evidence=evidence, actor=actor)
    event(actor, work.case, 'factory.rfp_estimate_receipt', work=work.pk, receipt=receipt.pk)
    bump(work.case)
    return receipt

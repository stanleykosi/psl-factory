"""Exact Planning exit, client sign-off and Support receipt actions."""
from time import monotonic

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404

from apps.core.evidence_access import public_evidence
from apps.core.read_budget import limit_queries
from apps.core.read_observation import read_observation
from apps.identity.services import active_case_grants, require
from apps.pmo import delivery, delivery_ui, gates, go_live_attestations, phase_evidence
from apps.pmo.models import DeliverySource, GateRecord, MeetingVersion
from apps.workflows import factory_delivery, factory_go_live, factory_handover
from apps.workflows.factory_progress import wake_waiting

from .commands import require_line
from .http import BOOLEAN, DATETIME, ID, TEXT, array, choice, endpoint, nullable, obj
from .reviews import VERDICT, VERSIONS
from .work import WORK_RESULT, result


PIN = {'type': 'string', 'pattern': '^[a-f0-9]{64}$'}
PROOF = obj({'id': ID, 'version': ID, 'kind': TEXT})
NOTE = {**TEXT, 'maxLength': 4000}
RESPONSE = obj({**WORK_RESULT['properties'], 'record_id': ID})
WORKAROUND = {'return_id': ID, 'issue_state_id': ID, 'response_id': ID, 'review_id': ID}


def proof_rows(rows):
    return [{'id': row.pk, 'version': row.version, 'kind': row.kind} for row in rows]


def recorded(work, row):
    work.refresh_from_db(fields=['status', 'revision', 'lease_until'])
    return {**result(work), 'record_id': row.pk}


@endpoint(response=obj({
    **VERSIONS, 'packet': nullable(PIN), 'verdicts': array(VERDICT), 'proofs': array(PROOF, limit=50),
    'blockers': array(obj({'id': ID, 'reference': TEXT})), 'checklist': array(obj({'name': TEXT, 'status': TEXT})),
    'workaround': nullable(obj(WORKAROUND)),
}), summary='Read current Planning exit checks, decision fingerprint and allowed outcomes')
@read_observation
def planning_exit(http, work_id):
    work = require_line(http.user, work_id, factory_delivery.DEFINITION)
    with limit_queries(900, deadline=monotonic() + 8):
        panel = factory_delivery.projection(http.user, work, decision_evidence_limit=50, decision_only=True)
    return {'expected_revision': work.revision, 'case_revision': work.case.revision, 'packet': panel['decision_packet'],
            'verdicts': panel['allowed_verdicts'], 'proofs': proof_rows(panel['decision_evidence']),
            'workaround': panel['workaround_option'],
            'blockers': [{'id': issue.pk, 'reference': issue.reference} for issue in panel['return_issues']],
            'checklist': [{'name': key, 'status': value['status']} for key, value in panel['checks'].items()]}


@endpoint(method='POST', request=obj({**VERSIONS, 'packet': PIN, 'verdict': VERDICT,
                                     'evidence_id': ID, 'note': NOTE, 'issue_id': nullable(ID)}, optional=('issue_id',)),
          response=RESPONSE, summary='Record a Planning exit decision against the current reviewed delivery packet')
def decide_planning_exit(http, work_id, *, body):
    work = require_line(http.user, work_id, factory_delivery.DEFINITION)
    record = factory_delivery.decide(http.user, work.pk, body['expected_revision'], body['verdict'],
                                     body['evidence_id'], body['note'], body['case_revision'], body['packet'],
                                     issue_id=body.get('issue_id'))
    return recorded(work, record)


@endpoint(method='POST', request=obj({**VERSIONS, **WORKAROUND, 'note': NOTE}), response=RESPONSE, status=201,
          summary='Link the exact independently reviewed client workaround to a returned Planning decision')
def link_workaround(request, work_id, *, body):
    work = require_line(request.user, work_id, factory_delivery.DEFINITION)
    source = factory_delivery.link_client_workaround(request.user, work.pk, body['expected_revision'], body['case_revision'],
        **{key: body[key] for key in (*WORKAROUND, 'note')})
    return recorded(work, source)


SOURCE_PAYLOADS = {
    'ui_applicability': obj({'requires_ui': nullable(BOOLEAN), 'client_signoff_required': nullable(BOOLEAN)}),
    'ui_target': delivery_ui.TARGET, 'ui_design': delivery_ui.APPROVAL, 'ui_client': delivery_ui.APPROVAL,
}
SOURCE_KINDS = tuple(kind for kind in delivery.SOURCE_OWNERS if kind not in (
    'uat_client_target', 'uat_client_response', 'planning_issue_workaround', 'hypercare_engineering', 'hypercare_infrastructure',
))
GATE_KINDS = (*delivery.UPSTREAM_GATES, *delivery.GLPI_GATES)
REFERENCE = {**TEXT, 'maxLength': 240}
PHASE_CHECK = obj({'key': TEXT, 'title': TEXT, 'authority': TEXT, 'status': TEXT,
                   'records': array(obj({'id': ID, 'type': TEXT}))})
DELIVERY_ACTIONS = {
    'capture_source': 'delivery.source', 'verify_source': 'delivery.verify',
    'capture_gate': 'pmo.gate_record', 'verify_gate': 'pmo.gate_verify',
    'record_progress': 'delivery.manage', 'record_glpi_request': 'delivery.release_request',
    'prepare_readiness': 'delivery.manage', 'observe_release': 'delivery.release_record',
}


@endpoint(response=obj({**VERSIONS, 'dossier_id': ID, 'candidate_id': ID, 'as_of': DATETIME,
    'current_scope': BOOLEAN, 'synthetic': BOOLEAN, 'actions': array(choice(*DELIVERY_ACTIONS)),
    'phases': array(obj({'name': TEXT, 'checks': array(PHASE_CHECK)})),
    'proofs': array(PROOF, limit=50), 'readiness_ids': array(ID, limit=25),
    'release': nullable(obj({'reference': TEXT, 'released_at': DATETIME, 'environment': nullable(TEXT), 'evidence_id': ID})),
}), summary='Read the current delivery phase checks, exact record choices and observed release facts')
def release_register(request, work_id):
    actor = request.user
    work = require_line(actor, work_id, factory_delivery.DEFINITION)
    with limit_queries(650, deadline=monotonic() + 8):
        dossier = factory_delivery.subject(work, actor, current=False)
        panel = phase_evidence.projection(actor, work.case_id, dossier.pk)
        grants = {action for _, action in active_case_grants(actor, [work.case_id])}
        release = delivery.release_observations(work.case, [dossier.pk]).get(dossier.pk)
        actions = [action for action, grant in DELIVERY_ACTIONS.items() if grant in grants and not work.cancel_requested
                   and (work.case.synthetic or action not in ('verify_source', 'verify_gate'))
                   and (panel['scope_current'] or action == 'observe_release')]
        proofs = proof_rows(public_evidence(work.case.evidence.all()).only('kind', 'version').order_by('-pk')[:50])
        readiness = list(dossier.records.filter(kind='release_ready',
            evidence_id__in=public_evidence(work.case.evidence.all()).values('pk')).order_by('-pk').values_list('pk', flat=True)[:25])
    registry = panel['evidence_registry']
    return {'expected_revision': work.revision, 'case_revision': work.case.revision, 'dossier_id': dossier.pk,
            'candidate_id': dossier.candidate_id, 'as_of': panel['as_of'], 'current_scope': panel['scope_current'],
            'synthetic': work.case.synthetic, 'actions': actions, 'proofs': proofs, 'readiness_ids': readiness,
            'release': {key: release[key] for key in ('reference', 'released_at', 'environment', 'evidence_id')} if release else None,
            'phases': [{'name': phase['name'], 'checks': [
                {**{key: check[key] for key in ('key', 'title', 'authority', 'status')}, 'records': [
                    {'id': registry[ref]['id'], 'type': registry[ref]['type']} for ref in check['references']]}
                for check in phase['checks']]} for phase in panel['phases']]}


def release_command_schema(action, fields):
    return obj({'action': {'const': action}, **VERSIONS, **fields})


RELEASE_COMMAND = {'oneOf': [
    *(release_command_schema('capture_source', {'kind': {'const': kind}, 'evidence_id': ID,
        'reference': REFERENCE, 'payload': SOURCE_PAYLOADS.get(kind, obj({}))}) for kind in SOURCE_KINDS),
    release_command_schema('verify_source', {'source_id': ID}),
    release_command_schema('capture_gate', {'kind': choice(*GATE_KINDS), 'reference': REFERENCE, 'evidence_id': ID}),
    release_command_schema('verify_gate', {'gate_id': ID}),
    release_command_schema('record_progress', {'kind': choice('kickoff', 'progress'), 'evidence_id': ID, 'note': NOTE,
                                               'meeting_version_id': nullable(ID)}),
    release_command_schema('record_glpi_request', {'reference': REFERENCE, 'evidence_id': ID, 'note': NOTE}),
    release_command_schema('prepare_readiness', {}),
    release_command_schema('observe_release', {'readiness_id': nullable(ID), 'released_at': DATETIME, 'reference': REFERENCE,
        'evidence_id': ID, 'note': NOTE, 'environment': nullable({**TEXT, 'maxLength': 160}), 'private_log_id': nullable(ID)}),
]}


@endpoint(method='POST', request=RELEASE_COMMAND, response=RESPONSE,
          summary='Capture exact release sources, gate records, readiness and actual release observations')
@transaction.atomic
def release_action(request, work_id, *, body):
    actor = request.user
    work = require_line(actor, work_id, factory_delivery.DEFINITION)
    work = type(work).objects.select_for_update(of=('self',)).select_related('case', 'source_head', 'actor').get(pk=work.pk)
    action = body['action']
    if work.revision != body['expected_revision'] or work.cancel_requested:
        raise ValidationError('STALE_VERSION: Review the current delivery work before recording new evidence.')
    require(actor, work.case, DELIVERY_ACTIONS[action])
    dossier = factory_delivery.subject(work, actor, current=action != 'observe_release')
    expected = body['case_revision']
    public = public_evidence(work.case.evidence.all())
    if body.get('evidence_id'):
        get_object_or_404(public, pk=body['evidence_id'])
    if action == 'capture_source':
        row = delivery.capture_source(actor, work.case_id, dossier.pk, body['kind'], body['reference'], body['evidence_id'],
                                      body['payload'], expected)
    elif action == 'verify_source':
        source = get_object_or_404(DeliverySource.objects.filter(dossier=dossier, kind__in=SOURCE_KINDS,
            evidence_id__in=public.values('pk')), pk=body['source_id'])
        row = delivery.verify_source(actor, work.case_id, source.pk, expected)
    elif action == 'capture_gate':
        row = gates.record_gate(actor, work.case_id, dossier.candidate_id, body['kind'], body['reference'], body['evidence_id'], expected)
    elif action == 'verify_gate':
        gate = get_object_or_404(GateRecord.objects.filter(candidate_id=dossier.candidate_id, kind__in=GATE_KINDS,
            evidence_id__in=public.values('pk')), pk=body['gate_id'])
        row = gates.verify_gate(actor, work.case_id, gate.pk, expected)
    elif action == 'record_progress':
        if body['meeting_version_id'] is not None:
            get_object_or_404(MeetingVersion.objects.filter(meeting__case=work.case, evidence_id__in=public.values('pk')),
                              pk=body['meeting_version_id'])
        row = delivery.record_progress(actor, work.case_id, dossier.pk, body['kind'], body['evidence_id'], body['note'],
                                       expected, body['meeting_version_id'])
    elif action == 'record_glpi_request':
        row = delivery.record_release_request(actor, work.case_id, dossier.pk, body['reference'], body['evidence_id'], body['note'], expected)
    elif action == 'prepare_readiness':
        row = delivery.prepare_readiness(actor, work.case_id, dossier.pk, expected)
    else:
        row = delivery.capture_release(actor, work.case_id, dossier.pk, body['readiness_id'], body['released_at'],
            body['reference'], body['evidence_id'], body['note'], expected, deployment_environment=body['environment'],
            private_log_id=body['private_log_id'])
    wake_waiting(work.pk)
    return recorded(work, row)


SIGNER = obj({
    **dict.fromkeys(('source_system', 'source_reference', 'decision_id', 'decision_version', 'signer_reference'),
                    {**TEXT, 'maxLength': 160}),
    'signed_at': DATETIME,
})


def current_signoff(actor, work):
    require(actor, work.case, 'delivery.manage')
    dossier, _, version, _, receipts = factory_go_live.published(work, actor)
    if actor.pk not in {owner.pk for owner in factory_go_live.attestation_owners(work, dossier)}:
        raise PermissionDenied()
    return dossier, version, receipts


@endpoint(response=obj({
    **VERSIONS, 'version_id': ID, 'receipts': array(obj({'id': ID, 'recorded_at': DATETIME})),
    'prior_acceptance_id': nullable(ID), 'proofs': array(PROOF, limit=100),
}), summary='Read the exact delivered go-live report and signature evidence options for the appointed PM')
def go_live(http, work_id):
    work = require_line(http.user, work_id, factory_go_live.DEFINITION)
    dossier, version, receipts = current_signoff(http.user, work)
    prior = factory_go_live.native.latest_go_live(dossier, False)
    proofs = public_evidence(work.case.evidence.filter(kind='signature')).only('kind', 'version').order_by('-pk')[:100]
    return {'expected_revision': work.revision, 'case_revision': work.case.revision, 'version_id': version.pk,
            'receipts': [{'id': row.pk, 'recorded_at': row.created_at} for row in receipts],
            'prior_acceptance_id': prior.pk if prior else None, 'proofs': proof_rows(proofs)}


@endpoint(method='POST', request=obj({
    **VERSIONS, 'version_id': ID, 'receipt_id': ID, 'pm_signature_id': ID, 'client_signature_id': ID,
    'signers': obj({'PM': SIGNER, 'Client': SIGNER}), 'mode': choice('fresh_signatures', 'metadata_binding'),
    'prior_acceptance_id': nullable(ID), 'note': NOTE,
}), response=RESPONSE, summary='Record distinct real PM and client signatures for the exact delivered go-live report')
def record_go_live(http, work_id, *, body):
    actor = http.user
    work = require_line(actor, work_id, factory_go_live.DEFINITION)
    dossier, version, receipts = current_signoff(actor, work)
    receipt = next((row for row in receipts if row.pk == body['receipt_id']), None)
    release = delivery.latest(dossier, 'release_outcome', False)
    ids = {'PM': body['pm_signature_id'], 'Client': body['client_signature_id']}
    evidence = public_evidence(work.case.evidence.filter(kind='signature', pk__in=ids.values())).in_bulk()
    if not receipt or not release or len(evidence) != 2 or version.pk != body['version_id']:
        raise ValidationError('Choose the exact delivered report, current receipt and two distinct signature sources.')
    purpose = go_live_attestations.PURPOSE
    attestation = {
        **go_live_attestations.subject_pins(dossier, receipt, release),
        'protocol': go_live_attestations.PROTOCOL, 'purpose': purpose, 'attesting_actor_id': actor.pk,
        'signatures': {role: {**body['signers'][role], 'evidence': go_live_attestations.pin(evidence[key]), 'purpose': purpose}
                       for role, key in ids.items()},
    }
    record = factory_go_live.accept(actor, work.pk, body['expected_revision'], body['case_revision'], version.pk,
                                    receipt.pk, ids['PM'], ids['Client'], body['note'], body['prior_acceptance_id'],
                                    attestation=attestation, mode=body['mode'])
    return recorded(work, record)


HANDOVER_STATUS = choice('received', 'gaps')


@endpoint(response=obj({
    **VERSIONS, 'receipts': array(obj({'id': ID, 'can_acknowledge': BOOLEAN, 'status': nullable(HANDOVER_STATUS)})),
    'proofs': array(PROOF, limit=50),
}), summary='Read your exact Support handover receipts and acknowledgement controls')
def support_receipt(http, work_id):
    actor = http.user
    work = require_line(actor, work_id, factory_handover.DEFINITION)
    with limit_queries(350, deadline=monotonic() + 8):
        factory_handover.source(work, actor, current=False)
        version = factory_handover.document(work)
        _, own = factory_handover.receipt_state(work, version, recipient=actor)
        can_ack = bool(own and factory_handover.can_acknowledge(actor, work, version))
    records = public_evidence(work.case.evidence.all()).only('kind', 'version').order_by('-pk')[:50]
    return {'expected_revision': work.revision, 'case_revision': work.case.revision,
            'receipts': [{'id': row['receipt'].pk, 'can_acknowledge': can_ack,
                          'status': row['ack'].data['status'] if row['ack'] else None} for row in own],
            'proofs': proof_rows(records) if can_ack else []}


@endpoint(method='POST', request=obj({**VERSIONS, 'receipt_id': ID, 'evidence_id': ID, 'status': HANDOVER_STATUS, 'note': NOTE}),
          response=RESPONSE, summary='Let the actual Support recipient acknowledge the exact handover or record gaps')
def acknowledge_support(http, work_id, *, body):
    work = require_line(http.user, work_id, factory_handover.DEFINITION)
    require(http.user, work.case, 'delivery.support_receive')
    get_object_or_404(public_evidence(work.case.evidence.all()), pk=body['evidence_id'])
    record = factory_handover.acknowledge(http.user, work.pk, body['expected_revision'], body['case_revision'],
                                         body['receipt_id'], body['status'], body['evidence_id'], body['note'])
    return recorded(work, record)

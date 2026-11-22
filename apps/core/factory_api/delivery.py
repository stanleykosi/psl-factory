"""Exact Planning exit, client sign-off and Support receipt actions."""
from time import monotonic

from django.core.exceptions import PermissionDenied, ValidationError

from apps.core.evidence_access import public_evidence
from apps.core.read_budget import limit_queries
from apps.identity.services import require
from apps.pmo import delivery, go_live_attestations
from apps.workflows import factory_delivery, factory_go_live, factory_handover

from .commands import require_line
from .http import BOOLEAN, DATETIME, ID, TEXT, array, choice, endpoint, nullable, obj
from .reviews import VERDICT, VERSIONS
from .work import WORK_RESULT, result


PIN = {'type': 'string', 'pattern': '^[a-f0-9]{64}$'}
PROOF = obj({'id': ID, 'version': ID, 'kind': TEXT})
NOTE = {**TEXT, 'maxLength': 4000}
RESPONSE = obj({**WORK_RESULT['properties'], 'record_id': ID})


def proof_rows(rows):
    return [{'id': row.pk, 'version': row.version, 'kind': row.kind} for row in rows]


def recorded(work, row):
    work.refresh_from_db(fields=['status', 'revision', 'lease_until'])
    return {**result(work), 'record_id': row.pk}


@endpoint(response=obj({
    **VERSIONS, 'packet': nullable(PIN), 'verdicts': array(VERDICT), 'proofs': array(PROOF, limit=50),
    'blockers': array(obj({'id': ID, 'reference': TEXT})), 'checklist': array(obj({'name': TEXT, 'status': TEXT})),
}), summary='Read current Planning exit checks, decision fingerprint and allowed outcomes')
def planning_exit(http, work_id):
    work = require_line(http.user, work_id, factory_delivery.DEFINITION)
    with limit_queries(350, deadline=monotonic() + 8):
        panel = factory_delivery.projection(http.user, work, decision_evidence_limit=50)
    return {'expected_revision': work.revision, 'case_revision': work.case.revision, 'packet': panel['decision_packet'],
            'verdicts': panel['allowed_verdicts'], 'proofs': proof_rows(panel['decision_evidence']),
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
        panel = factory_handover.projection(actor, work)
    own = [item for item in panel['receipts'] if item['receipt'].recipient_id == actor.pk]
    records = public_evidence(work.case.evidence.all()).only('kind', 'version').order_by('-pk')[:50]
    return {'expected_revision': work.revision, 'case_revision': work.case.revision,
            'receipts': [{'id': row['receipt'].pk, 'can_acknowledge': row['can_ack'],
                          'status': row['ack'].data['status'] if row['ack'] else None} for row in own],
            'proofs': proof_rows(records) if any(row['can_ack'] for row in own) else []}


@endpoint(method='POST', request=obj({**VERSIONS, 'receipt_id': ID, 'evidence_id': ID, 'status': HANDOVER_STATUS, 'note': NOTE}),
          response=RESPONSE, summary='Let the actual Support recipient acknowledge the exact handover or record gaps')
def acknowledge_support(http, work_id, *, body):
    work = require_line(http.user, work_id, factory_handover.DEFINITION)
    record = factory_handover.acknowledge(http.user, work.pk, body['expected_revision'], body['case_revision'],
                                         body['receipt_id'], body['status'], body['evidence_id'], body['note'])
    return recorded(work, record)

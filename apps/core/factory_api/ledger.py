"""Protected incumbent reference observation and duplicate resolution."""

from io import BytesIO
import json

from django import forms
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Q
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404

from adapters import case_uploads
from apps.core.evidence_access import public_evidence
from apps.core.models import Audit, Case
from apps.core.read_budget import limit_queries
from apps.core.services import add_evidence
from apps.finance import ledger as domain, ledger_resolution as resolution
from apps.finance.models import LedgerCheck, LedgerLineage, LedgerResolution
from apps.identity.services import active_case_grants
from apps.workflows import factory_ledger as native, factory_ledger_observation_proof as proof_storage
from apps.workflows.factory_progress import wake_waiting

from .commands import require_line
from .delivery import PROOF, proof_rows, recorded
from .http import BOOLEAN, ID, REVISION, TEXT, UUID, array, choice, endpoint, nullable, obj
from .reviews import VERSIONS
from .work import WORK_RESULT


OUTCOME = choice('found', 'not_found', 'unknown', 'multiple')
VERDICT = choice('approve', 'reject')
NOTE = {'type': 'string', 'maxLength': 2000}
BINARY = {'type': 'string', 'format': 'binary'}
RESPONSE = obj({**WORK_RESULT['properties'], 'record_id': ID})
VERIFIED = obj({'lineage_id': ID, 'source': domain.SOURCE, 'check_id': ID, 'review_id': ID, 'incumbent': domain.RESPONSE,
                'verification_mode': {'const': 'supplied_read_only'}, 'native_authenticity_verified': {'const': False},
                'posting_performed': {'const': False}})


@endpoint(response=obj({**VERSIONS, 'stage': TEXT, 'finding': {'type': 'string'}, 'source_id': ID,
    'source': domain.SOURCE, 'lineage_id': nullable(ID), 'predecessor_id': nullable(ID), 'conflict_id': nullable(ID),
    'check_id': nullable(ID), 'observation': nullable(domain.RESPONSE),
    'latest_decision': nullable(obj({'id': ID, 'verdict': VERDICT, 'reason': nullable(NOTE)})),
    'review_options': array(VERDICT), 'can_observe': BOOLEAN, 'has_attachment': BOOLEAN,
    'verification_evidence': array(PROOF, limit=30), 'review_evidence': array(PROOF, limit=30),
    'verified': nullable(VERIFIED)}),
    summary='Read the exact private incumbent source, duplicate status, observation and verified original reference')
def detail(request, work_id):
    actor = request.user
    work = require_line(actor, work_id, native.DEFINITION)
    with limit_queries(1150):
        data, evidence, source = native.source(work, actor)
        panel = native.projection(actor, work)
        lineage = panel['lineage']
        conflict = native.conflicting_source(work, data, lineage)
        grants = {action for _, action in active_case_grants(actor, [work.case_id])}
        check = lineage.checks.order_by('-pk').first() if lineage else None
        decision = check.decisions.order_by('-pk').first() if check else None
        rejected = decision and decision.verdict == 'reject'
        options = []
        verified = None
        attachment = None
        active = not work.cancel_requested and work.status not in ('cancelled', 'followup_needed')
        if check and not conflict:
            if active and not rejected and actor.pk not in (lineage.actor_id, check.actor_id):
                try:
                    domain.authority(actor, check)
                except (PermissionDenied, ValidationError):
                    pass
                else:
                    options = ['reject']
                    try:
                        domain.current(check)
                    except (PermissionDenied, ValidationError):
                        pass
                    else:
                        options.insert(0, 'approve')
            try:
                attachment = proof_storage.attachment_for(actor, work, check)
            except (PermissionDenied, ValidationError):
                pass
            if work.status == 'verified' and not panel['readiness_changed']:
                verified = domain.report(actor, work.case_id, lineage.pk)
        can_observe = active and lineage is not None and conflict is None and 'ledger.verify' in grants
        choices = work.case.evidence.only('id', 'kind', 'version').order_by('-pk')
        reason = Audit.objects.filter(case=work.case, action='ledger.review', data__decision=decision.pk).values_list(
            'data__reason', flat=True).first() if rejected else None
        return {'expected_revision': work.revision, 'case_revision': work.case.revision,
                'stage': 'duplicate' if conflict else 'rejected' if rejected else panel['native']['stage'],
                'finding': panel['finding'], 'source_id': evidence.pk, 'source': source,
                'lineage_id': lineage.pk if lineage else None, 'predecessor_id': data['predecessor_id'],
                'conflict_id': conflict.pk if conflict else None, 'check_id': check.pk if check else None,
                'observation': check.payload if check else None, 'has_attachment': attachment is not None,
                'latest_decision': {'id': decision.pk, 'verdict': decision.verdict, 'reason': reason} if decision else None,
                'review_options': options, 'can_observe': can_observe, 'verified': verified,
                'verification_evidence': proof_rows(choices.filter(kind='quickbooks_verification')[:30]) if can_observe else [],
                'review_evidence': proof_rows(public_evidence(choices.filter(kind__in=('finance_review', 'policy_decision')))[:30])
                    if options else []}


@endpoint(method='POST', request={'oneOf': [
    obj({'action': {'const': 'observe'}, **VERSIONS, 'lineage_id': ID, 'evidence_id': ID, 'outcome': OUTCOME}),
    obj({'action': {'const': 'review'}, **VERSIONS, 'check_id': ID, 'evidence_id': ID, 'verdict': VERDICT, 'reason': NOTE}),
    obj({'action': choice('recheck', 'restart'), **VERSIONS, 'reason': {**NOTE, 'minLength': 1}}),
]}, response=RESPONSE, status=201, summary='Observe, independently review or renew the exact incumbent reference work')
def command(request, work_id, *, body):
    actor = request.user
    work = require_line(actor, work_id, native.DEFINITION)
    args = (actor, work.pk, body['expected_revision'], body['case_revision'])
    action = body['action']
    if action == 'observe':
        row = native.command(*args, action, body['lineage_id'], body['evidence_id'], outcome=body['outcome'])
    elif action == 'review':
        row = native.command(*args, action, body['check_id'], body['evidence_id'], body['verdict'], reason=body['reason'])
    elif action == 'recheck':
        row = native.recheck(*args, body['reason'])
    else:
        row = native.restart(*args, body['reason'])
    wake_waiting(work.pk)
    return recorded(work, row)


class ObservationForm(forms.Form):
    expected_revision = forms.IntegerField(min_value=1, max_value=REVISION['maximum'])
    case_revision = forms.IntegerField(min_value=1, max_value=REVISION['maximum'])
    lineage_id = forms.IntegerField(min_value=1, max_value=ID['maximum'])
    evidence_id = forms.IntegerField(min_value=1, max_value=ID['maximum'])
    outcome = forms.ChoiceField(choices=[(value, value) for value in OUTCOME['enum']])
    file = forms.FileField()


@endpoint(method='POST', multipart=True, request=obj({**VERSIONS, 'lineage_id': ID, 'evidence_id': ID,
    'outcome': OUTCOME, 'file': BINARY}), response=RESPONSE, status=201,
    summary='Record the exact incumbent observation and its private PNG or PDF proof')
def observe_file(request, work_id):
    work = require_line(request.user, work_id, native.DEFINITION)
    form = ObservationForm(request.POST, request.FILES)
    if not form.is_valid():
        raise ValidationError('Supply a current exact observation and one private proof file.')
    values = form.cleaned_data
    row = proof_storage.record(request.user, work.pk, values['expected_revision'], values['case_revision'],
                               values['lineage_id'], values['evidence_id'], values['outcome'], values['file'])
    wake_waiting(work.pk)
    return recorded(work, row)


@endpoint(response=BINARY, media_type='application/octet-stream',
          summary='Download proof of the original selected incumbent observation')
def observation_file(request, work_id, check_id):
    work = require_line(request.user, work_id, native.DEFINITION)
    check = get_object_or_404(LedgerCheck, pk=check_id, lineage__case=work.case)
    try:
        proof = proof_storage.attachment_for(request.user, work, check)
        if not proof:
            raise Http404
        data = case_uploads.read(proof)
    except (OSError, ValidationError) as exc:
        raise Http404 from exc
    return FileResponse(BytesIO(data), as_attachment=True, filename=proof.name, content_type='application/octet-stream')


MODE = choice('reference_correction', 'duplicate_alias')
MEMBER = obj({'lineage_id': ID, 'disposition': TEXT})
PACKET = obj({'id': ID, 'reference': TEXT, 'mode': MODE, 'version': ID, 'selected_id': ID,
              'current_reviewed': BOOLEAN, 'members': array(MEMBER), 'last_review_id': nullable(ID),
              'last_verdict': nullable(choice('confirm', 'return', 'withdraw'))})


def permit_members(actor, cases):
    for case in cases:
        native.readable(actor, case)


def resolution_proofs(actor, case):
    evidence = list(resolution.visible_evidence(actor, case))
    keys = [row.pk for row in evidence]
    packets = (LedgerResolution.objects.filter(Q(evidence_id__in=keys) | Q(reviews__evidence_id__in=keys))
               .distinct().prefetch_related('reviews', 'members__lineage__case'))
    protected = set()
    for packet in packets:
        try:
            permit_members(actor, {member.lineage.case for member in packet.members.all()})
        except PermissionDenied:
            protected.add(packet.evidence_id)
            protected.update(review.evidence_id for review in packet.reviews.all())
    return proof_rows(row for row in evidence if row.pk not in protected)


@endpoint(response=obj({'case_revision': REVISION, 'claims': array(obj({'id': ID, 'case_id': UUID, 'source_reference': TEXT,
    'target_reference': nullable(TEXT)}), limit=100), 'resolutions': array(PACKET, limit=40),
    'resolution_evidence': array(PROOF, limit=40)}),
    summary='Read duplicate claims and resolution decisions visible across every participant workspace')
def collisions(request, case_id):
    actor = request.user
    case = get_object_or_404(Case, pk=case_id)
    native.readable(actor, case)
    verified = []
    with limit_queries(1600):
        for item in resolution.visible_packets(actor, case):
            row = item['row']
            try:
                permit_members(actor, {member.lineage.case for member in item['members']})
            except PermissionDenied:
                continue
            last = item['reviews'].first()
            verified.append({'id': row.pk, 'reference': row.reference, 'mode': row.mode, 'version': row.version,
                'selected_id': row.selected_id, 'current_reviewed': item['current_reviewed'],
                'members': [{'lineage_id': member.lineage_id, 'disposition': member.disposition} for member in item['members']],
                'last_review_id': last.pk if last else None, 'last_verdict': last.verdict if last else None})
        claims = []
        candidates = list(resolution.visible_claims(actor, case).select_related('case').order_by('-pk')[:100])
        private_cases = {case_id for case_id, _ in active_case_grants(actor, {row.case_id for row in candidates},
                                                                     actions=['ledger.private.read'])}
        for row in candidates:
            if row.case_id in private_cases:
                claims.append({'id': row.pk, 'case_id': str(row.case_id), 'source_reference': row.payload['source_reference'],
                               'target_reference': row.payload['target_reference']})
        return {'case_revision': case.revision, 'claims': claims, 'resolutions': verified,
                'resolution_evidence': resolution_proofs(actor, case)}


@endpoint(method='POST', request={'oneOf': [
    obj({'action': {'const': 'propose'}, 'case_revision': REVISION, 'selected_id': ID, 'retired_ids': array(ID, limit=40),
         'member_ids': array(ID, limit=40), 'mode': MODE, 'reference': {**TEXT, 'maxLength': 100},
         'predecessor_id': nullable(ID), 'evidence_id': ID, 'reason': {**TEXT, 'maxLength': 400}}),
    obj({'action': {'const': 'review'}, 'case_revision': REVISION, 'resolution_id': ID, 'evidence_id': ID,
         'verdict': choice('confirm', 'return', 'withdraw')}),
]}, response=obj({'id': ID, 'case_revision': REVISION}), status=201,
    summary='Propose or independently review an exact duplicate resolution across authorised workspaces')
def resolve_collision(request, case_id, *, body):
    actor = request.user
    case = get_object_or_404(Case, pk=case_id)
    native.readable(actor, case)
    if body['action'] == 'propose':
        participants = LedgerLineage.objects.filter(pk__in=body['member_ids']).select_related('case')
        permit_members(actor, {row.case for row in participants})
        row = resolution.propose(actor, case.pk, body['selected_id'], body['retired_ids'], body['member_ids'], body['mode'],
                                 body['reference'], body['predecessor_id'], body['evidence_id'], body['reason'], body['case_revision'])
    else:
        selected = get_object_or_404(LedgerResolution, case=case, pk=body['resolution_id'])
        permit_members(actor, {member.lineage.case for member in selected.members.select_related('lineage__case')})
        row = resolution.review(actor, case.pk, selected.pk, body['verdict'], body['evidence_id'], body['case_revision'])
    case.refresh_from_db(fields=['revision'])
    return {'id': row.pk, 'case_revision': case.revision}


@endpoint(method='POST', request={'oneOf': [
    obj({'kind': {'const': 'ledger_source'}, 'case_revision': REVISION, 'value': domain.SOURCE}),
    obj({'kind': {'const': 'quickbooks_verification'}, 'case_revision': REVISION, 'value': domain.RESPONSE}),
    obj({'kind': choice('ledger_resolution', 'ledger_resolution_review'), 'case_revision': REVISION,
         'value': {**TEXT, 'maxLength': 4000}}),
]}, response=PROOF, status=201, summary='Capture actual supplied private ledger evidence for later native verification')
@transaction.atomic
def evidence(request, case_id, *, body):
    actor = request.user
    case = get_object_or_404(Case, pk=case_id)
    native.readable(actor, case)
    kind = body['kind']
    action = 'ledger.verify' if kind == 'quickbooks_verification' else 'ledger.capture'
    case = domain.locked(actor, case.pk, action, body['case_revision'])
    value = body['value']
    if isinstance(value, dict):
        value = json.dumps(value, sort_keys=True)
    proof = add_evidence(actor, case.pk, kind, value, 'supplied:private-ledger-api', case.revision)
    return {'id': proof.pk, 'kind': proof.kind, 'version': proof.version}

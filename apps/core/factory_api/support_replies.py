"""Separately attested Support replies against a delivered handover."""
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from apps.core.evidence_access import public_evidence
from apps.core.read_budget import limit_queries
from apps.core.services import event
from apps.identity.services import active_case_grants
from apps.pmo import handover_replies
from apps.policy.handover_reply_validators import CHANNELS
from apps.workflows import factory_handover as domain

from .commands import require_line
from .delivery import NOTE, PROOF, RESPONSE, HANDOVER_STATUS, proof_rows, recorded
from .http import BOOLEAN, DATETIME, ID, TEXT, array, choice, endpoint, nullable, obj
from .reviews import VERSIONS


GAPS = array({**TEXT, 'maxLength': 400}, limit=10)
GAPS_EVENT = 'delivery.progress.support_reply_gaps'


@endpoint(response=obj({**VERSIONS, 'roles': array(TEXT), 'channels': array(choice(*CHANNELS)),
    'can_record': BOOLEAN, 'proofs': array(PROOF, limit=50), 'receipts': array(obj({'id': ID,
        'recipient': TEXT, 'recorded_at': DATETIME, 'previous_id': nullable(ID), 'status': nullable(HANDOVER_STATUS),
        'reply': nullable(obj({'party': TEXT, 'channel': choice(*CHANNELS), 'responded_at': DATETIME,
                               'note': NOTE, 'gaps': GAPS})),
    }), limit=100),
}), summary='Read allowed Support reply recorders and exact receipts for the current delivered handover')
def options(request, work_id):
    actor = request.user
    work = require_line(actor, work_id, domain.DEFINITION)
    with limit_queries(350):
        grants = {action for _, action in active_case_grants(actor, [work.case_id])}
        if handover_replies.ACTION not in grants:
            raise PermissionDenied
        domain.source(work, actor, current=False)
        roles = handover_replies.available_roles(actor, work.case)
        channels = handover_replies.rules(work.case)[1]['channels'] if roles else []
        answer = {'expected_revision': work.revision, 'case_revision': work.case.revision, 'roles': roles,
                  'channels': channels, 'can_record': False, 'receipts': [], 'proofs': []}
        if not roles:
            return answer
        binding = domain.document(work)
        _, receipts = domain.receipt_state(work, binding, exact_source=True, limit=100)
        handover_replies.decorate_receipts(work.case, receipts)
        reply_ids = [item['ack'].pk for item in receipts if item['ack'] and item['reply_source_available']]
        gaps = {data['reply_id']: data['gaps'] for data in work.case.audit.filter(
            action=GAPS_EVENT, data__reply_id__in=reply_ids).values_list('data', flat=True)}
        answer['can_record'] = bool(receipts and not work.cancel_requested)
        for item in receipts:
            receipt, ack = item['receipt'], item['ack']
            answer['receipts'].append({'id': receipt.pk, 'recipient': receipt.recipient.get_full_name() or receipt.recipient.username,
                'recorded_at': receipt.created_at, 'previous_id': ack.pk if ack else None,
                'status': ack.data['status'] if ack else None,
                'reply': {'party': item['reply_party'], 'channel': item['reply_channel'],
                          'responded_at': item['reply_time'], 'note': item['reply_note'],
                          'gaps': gaps.get(ack.pk, [])} if item['reply_time'] else None})
        if answer['can_record']:
            answer['proofs'] = proof_rows(public_evidence(work.case.evidence.all()).only('kind', 'version').order_by('-pk')[:50])
    return answer


@endpoint(method='POST', request=obj({**VERSIONS, 'receipt_id': ID, 'previous_id': nullable(ID),
    'status': HANDOVER_STATUS, 'evidence_id': ID, 'note': NOTE, 'party': {**TEXT, 'maxLength': 200},
    'channel': choice(*CHANNELS), 'responded_at': DATETIME, 'role': {**TEXT, 'maxLength': 100}, 'gaps': GAPS,
}, optional=('gaps',)), response=RESPONSE, status=201, summary='Record an actual Support reply as its authorised recorder')
@transaction.atomic
def record_reply(request, work_id, *, body):
    work = require_line(request.user, work_id, domain.DEFINITION)
    fields = {key: body[key] for key in ('status', 'evidence_id', 'note', 'party', 'channel', 'responded_at', 'role')}
    gaps = [item.strip() for item in body.get('gaps', [])]
    if gaps and (fields['status'] != 'gaps' or not all(gaps)):
        raise ValidationError('Enter the actual gaps only for a Support reply reporting gaps.')
    row = domain.record_support_reply(request.user, work.pk, body['expected_revision'], body['case_revision'],
        body['receipt_id'], predecessor=body['previous_id'] or 0, **fields)
    if gaps:
        event(request.user, work.case, GAPS_EVENT, reply_id=row.pk, gaps=gaps)
    return recorded(work, row)

"""Scoped human treatment of a short payment with unchanged debt."""

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from apps.core.evidence_access import public_evidence
from apps.core.services import lock_case
from apps.core.views import accessible_case
from apps.documents.contracts import digest
from apps.finance import cash, corrections, short_payments as native
from apps.finance.rules import number
from apps.identity.services import active_case_grants
from apps.policy.operator_drafts import draft_operator_policy
from apps.policy.short_payment_validators import COMPONENT, TREATMENTS, VALUE

from .delivery import PIN, PROOF, proof_rows
from .http import BOOLEAN, DATETIME, ID, REVISION, TEXT, Problem, array, choice, endpoint, nullable, obj


TREATMENT = choice(*TREATMENTS)
CHOICE = obj({'value': TREATMENT, 'label': TEXT})
BALANCE = obj({'invoiced': TEXT, 'received': TEXT, 'owed': TEXT, 'currency': TEXT, 'amount_basis': TEXT,
               'short_payment': BOOLEAN})
DECISION = obj({'id': ID, 'treatment': TREATMENT, 'allocation_id': ID, 'at': DATETIME, 'current_position': BOOLEAN})


@endpoint(response=obj({'revision': REVISION, 'position': PIN, 'balance': BALANCE, 'rule': TEXT,
    'correction_pending': BOOLEAN, 'treatments': array(CHOICE), 'history': array(DECISION, limit=30),
    'allocations': array(obj({'id': ID, 'reference': TEXT, 'amount': TEXT}), limit=50),
    'setup': nullable(obj({'reviewers': array(obj({'id': ID, 'label': TEXT}), limit=50), 'evidence': array(PROOF, limit=25)})),
}), summary='Read the exact short-payment position, eligible decisions and separate rule setup')
def detail(request, case_id, issue_id):
    actor = request.user
    case = accessible_case(actor, case_id)
    issue = native.exact_issue(actor, case, issue_id)
    position = native.position(issue)
    fingerprint = digest(position)
    rule, treatments, _ = native.treatments(actor, case)
    pending = corrections.unresolved(issue)
    payments = cash.allocations(issue=issue).select_related('lot__receipt', 'lot__successor').order_by('-pk')[:50]
    setup = None
    if (case.pk, 'policy.configure') in active_case_grants(actor, [case.pk], actions=['policy.configure']):
        users = get_user_model().objects.filter(is_active=True, grant__case=case, grant__active=True,
                                                grant__action='finance.short_payment.decide').order_by('pk')[:50]
        proofs = public_evidence(case.evidence.filter(kind='policy_decision')).only('kind', 'version').order_by('-pk')[:25]
        setup = {'reviewers': [{'id': user.pk, 'label': user.get_full_name() or user.username} for user in users],
                 'evidence': proof_rows(proofs)}
    return {'revision': case.revision, 'position': fingerprint, 'balance': {key: position[key] for key in BALANCE['properties']},
            'rule': rule, 'correction_pending': bool(pending), 'setup': setup,
            'treatments': [{'value': key, 'label': value} for key, value in treatments.items()]
                           if position['short_payment'] and not pending else [],
            'allocations': [{'id': row.pk, 'reference': cash.lot_payload(row.lot)['transaction_ref'],
                             'amount': number(row.amount)} for row in payments],
            'history': [{'id': row.pk, 'treatment': row.treatment, 'allocation_id': row.allocation_id,
                         'at': row.created_at, 'current_position': row.position_sha256 == fingerprint}
                        for row in issue.short_payment_decisions.order_by('-pk')[:30]]}


@endpoint(method='POST', request={'oneOf': [
    obj({'action': {'const': 'decide'}, 'revision': REVISION, 'position': PIN, 'allocation_id': ID,
         'treatment': TREATMENT, 'reason': {**TEXT, 'maxLength': 2000}}),
    obj({'action': {'const': 'draft_rule'}, 'revision': REVISION, 'rule': VALUE, 'evidence_id': ID}),
]}, response=obj({'id': ID, 'revision': REVISION}), status=201,
    summary='Record a human decision without changing the balance, or draft a separate short-payment rule')
def command(request, case_id, issue_id, *, body):
    actor = request.user
    case = accessible_case(actor, case_id)
    issue = native.exact_issue(actor, case, issue_id)
    if body['action'] == 'decide':
        record = native.decide(actor, case.pk, issue.pk, body['revision'], body['position'],
                               body['allocation_id'], body['treatment'], body['reason'])
    else:
        with transaction.atomic():
            lock_case(actor, case.pk, 'policy.configure', body['revision'])
            if not public_evidence(case.evidence.filter(pk=body['evidence_id'], kind='policy_decision')).exists():
                raise Problem(422, 'invalid_input', 'Choose a recorded owner decision in this workspace.')
            record = draft_operator_policy(actor, case.pk, COMPONENT, body['rule'], body['evidence_id'], timezone.now())
    case.refresh_from_db(fields=['revision'])
    return {'id': record.pk, 'revision': case.revision}

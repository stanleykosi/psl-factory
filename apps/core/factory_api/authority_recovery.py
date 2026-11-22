"""Current authority review for an unchanged historical outcome."""

from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404

from apps.agents.authority_recovery import investigate_recovery
from apps.core.evidence_access import public_evidence
from apps.core.read_budget import limit_queries
from apps.core.views import accessible_case
from apps.identity.services import active_case_grants, require
from apps.pmo import recoveries
from apps.pmo.models import AuthorityRecoveryRecord, AuthorityRecoveryRequest
from apps.policy.document_validators import ROLES

from .delivery import NOTE, PROOF, proof_rows
from .http import BOOLEAN, DATETIME, ID, REVISION, array, choice, endpoint, nullable, obj
from .reviews import VERDICT
from .work import PAGE, page_number


TARGET = choice(*recoveries.KINDS)
ROLE = choice(*ROLES)
ACTIONS = {'request': 'authority.request', 'decide': 'authority.decide', 'finalize': 'authority.finalize',
           'investigate': 'agent.authority'}
FIELDS = {
    'request': {'kind': TARGET, 'target_id': ID, 'evidence_id': ID, 'note': NOTE},
    'decide': {'request_id': ID, 'role': ROLE, 'verdict': VERDICT, 'evidence_id': ID, 'note': NOTE},
    'finalize': {'request_id': ID},
    'investigate': {'request_id': ID},
}
ENTRY = obj({'id': ID, 'kind': TARGET, 'target_id': ID, 'created_at': DATETIME})


def scope(actor, case_id):
    case = accessible_case(actor, case_id)
    require(actor, case, 'authority.read')
    return case


def summary(row):
    kind, target_id = recoveries.request_target(row)
    return {'id': row.pk, 'kind': kind, 'target_id': target_id, 'created_at': row.created_at}


@endpoint(response=obj({'revision': REVISION, 'records': array(ENTRY, limit=20), 'actions': array(choice(*ACTIONS)),
                        'evidence': array(PROOF, limit=40), 'next_page': nullable(PAGE)}), query={'page': PAGE},
          summary='List existing historical authority requests in the authorised project')
def collection(request, case_id):
    actor = request.user
    case = scope(actor, case_id)
    grants = {action for _, action in active_case_grants(actor, [case.pk])}
    number = page_number(request)
    offset = (number - 1) * 20
    rows = list(AuthorityRecoveryRequest.objects.filter(case=case).only('outcome_id', 'adoption_id', 'created_at')
                .order_by('-pk')[offset:offset + 21])
    proofs = public_evidence(case.evidence.all()).order_by('-pk').only('id', 'kind', 'version')[:40]
    return {'revision': case.revision, 'records': [summary(row) for row in rows[:20]],
            'actions': [name for name, action in ACTIONS.items() if action in grants],
            'evidence': proof_rows(proofs) if grants.intersection((ACTIONS['request'], ACTIONS['decide'])) else [],
            'next_page': number + 1 if len(rows) > 20 and number < PAGE['maximum'] else None}


@endpoint(response=obj({**ENTRY['properties'], 'revision': REVISION, 'current': BOOLEAN, 'finding': {'type': 'string'},
    'required_roles': array(ROLE), 'evidence_id': ID, 'current_finalization_id': nullable(ID),
    'recorded_finalization_id': nullable(ID), 'decisions': array(obj({'id': ID, 'role': ROLE, 'verdict': VERDICT,
        'evidence_id': ID, 'created_at': DATETIME}), limit=20)}),
    summary='Read exact historical authority and independently verify whether the reviewed source is current')
def detail(request, case_id, request_id):
    case = scope(request.user, case_id)
    row = get_object_or_404(AuthorityRecoveryRequest, case=case, pk=request_id)
    kind, target = recoveries.request_target(row)
    with limit_queries(500):
        finding = ''
        try:
            recoveries.current_request(case, row)
        except (ValidationError, PermissionDenied) as exc:
            finding = str(exc)
        current = recoveries.active_recovery(case, kind, target) if not finding else None
        recorded = AuthorityRecoveryRecord.objects.filter(request=row).values_list('pk', flat=True).first()
        decisions = list(row.decisions.order_by('-pk').values('id', 'role', 'verdict', 'evidence_id', 'created_at')[:20])
    return {**summary(row), 'revision': case.revision, 'current': not finding, 'finding': finding,
            'required_roles': row.snapshot['required_roles'], 'evidence_id': row.evidence_id,
            'recorded_finalization_id': recorded, 'current_finalization_id': current.pk if current and current.request_id == row.pk else None,
            'decisions': decisions}


@endpoint(method='POST', request={'oneOf': [obj({'action': {'const': name}, 'revision': REVISION, **fields})
    for name, fields in FIELDS.items()]}, response=obj({'id': ID, 'revision': REVISION}), status=201,
    summary='Request, decide, finalize or investigate current authority for an unchanged historical record')
def command(request, case_id, *, body):
    actor = request.user
    case = scope(actor, case_id)
    action, revision = body['action'], body['revision']
    require(actor, case, ACTIONS[action])
    args = (actor, case.pk)
    if 'evidence_id' in body and not public_evidence(case.evidence.filter(pk=body['evidence_id'])).exists():
        raise ValidationError('Choose evidence available in this workspace.')
    if action == 'request':
        row = recoveries.request_recovery(*args, body['kind'], body['target_id'], body['evidence_id'], body['note'], revision)
    elif action == 'decide':
        row = recoveries.decide_recovery(*args, body['request_id'], body['role'], body['verdict'], body['evidence_id'], body['note'], revision)
    elif action == 'finalize':
        row = recoveries.finalize_recovery(*args, body['request_id'], revision)
    else:
        row = investigate_recovery(*args, body['request_id'], revision)
    case.refresh_from_db(fields=['revision'])
    return {'id': row.pk, 'revision': case.revision}

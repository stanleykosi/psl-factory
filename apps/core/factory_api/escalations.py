"""Client escalation authority, exact outward review and delivery receipts."""

from django.db.models import F, OuterRef, Subquery
from django.shortcuts import get_object_or_404

from apps.core.evidence_access import public_evidence
from apps.core.read_budget import limit_queries
from apps.core.views import accessible_case
from apps.identity.services import active_case_grants, require
from apps.pmo import escalations as native
from apps.pmo.issue_access import public_current_issues
from apps.pmo.models import EscalationProfile, EscalationRequest
from apps.workflows import factory_escalation as factory

from .commands import require_line
from .delivery import NOTE, PROOF, proof_rows
from .http import BOOLEAN, DATETIME, ID, REVISION, TEXT, array, choice, endpoint, nullable, obj
from .reviews import VERDICT, VERSIONS
from .work import PAGE, WORK_RESULT, page_number, result


ROLE = choice('PMO Lead', 'Head of PMO')
DIRECTION = choice('escalate', 'de_escalate')
DESTINATION = choice('Client', 'PMO', 'CTO')
CLASSIFICATION = choice('unclassified', 'internal', 'client_dependent')
COMMANDS = {
    'decide_client_action': {'request_id': ID, 'role': ROLE, 'verdict': VERDICT, 'note': NOTE, 'delegated': BOOLEAN},
    'request_communication_review': {'version_id': ID},
    'recover_delivery': {'job_id': ID, 'operation': choice('cancel', 'retry'), 'reason': NOTE},
    'check_original_delivery': {},
}
DECISION = obj({'id': ID, 'request_id': ID, 'role': TEXT, 'verdict': VERDICT, 'created_at': DATETIME})
RECEIPT = obj({'id': ID, 'publication_id': ID, 'recorded_at': DATETIME})
REGISTER = {
    'classify': {'issue_id': ID, 'state_id': ID, 'classification': CLASSIFICATION, 'timeline_impact': nullable(BOOLEAN),
                 'trigger_at': nullable(DATETIME), 'evidence_id': ID, 'note': NOTE},
    'request': {'profile_id': ID, 'direction': DIRECTION, 'target': DESTINATION, 'evidence_id': ID, 'note': NOTE},
}


@endpoint(response=obj({'revision': REVISION, 'can_request': BOOLEAN, 'issues': array(obj({'id': ID, 'reference': TEXT,
    'current_id': ID}), limit=20), 'profiles': array(obj({'id': ID, 'state_id': ID, 'classification': CLASSIFICATION}), limit=20),
    'requests': array(obj({'id': ID, 'profile_id': ID, 'direction': DIRECTION, 'target': DESTINATION}), limit=20),
    'evidence': array(PROOF, limit=35), 'next_page': nullable(PAGE)}), query={'page': PAGE},
    summary='Read current public issue facts and available communications before creating an escalation')
def register(request, case_id):
    actor = request.user
    case = accessible_case(actor, case_id)
    require(actor, case, 'issue.read')
    number = page_number(request)
    offset = (number - 1) * 20
    window = slice(offset, offset + 21)
    issues = public_current_issues(case)
    may_request = bool(active_case_grants(actor, [case.pk], actions=['issue.escalate']))
    primary = list(issues.order_by('-pk').values('id', 'reference', 'current_id')[window])
    evidence = public_evidence(case.evidence.all())
    selected = EscalationProfile.objects.filter(state__issue_id__in=issues.values('pk'),
                                                 state_id=F('state__issue__current_id'), evidence__in=evidence)
    latest = EscalationProfile.objects.filter(state__issue_id=OuterRef('state__issue_id')).order_by('-pk').values('pk')[:1]
    selected = selected.filter(pk=Subquery(latest))
    profiles = list(selected.order_by('-pk').values('id', 'state_id', 'classification')[window])
    requests = list(EscalationRequest.objects.filter(profile__in=selected, evidence__in=evidence)
                    .order_by('-pk').values('id', 'profile_id', 'direction', 'target')[window])
    return {'revision': case.revision, 'can_request': may_request, 'issues': primary[:20], 'profiles': profiles[:20],
            'requests': requests[:20], 'evidence': proof_rows(evidence.only('id', 'kind', 'version').order_by('-pk')[:35]) if may_request else [],
            'next_page': number + 1 if max(len(primary), len(profiles), len(requests)) > 20 and number < PAGE['maximum'] else None}


@endpoint(method='POST', request={'oneOf': [obj({'action': {'const': action}, 'revision': REVISION, **fields})
    for action, fields in REGISTER.items()]}, response=obj({'id': ID, 'revision': REVISION}), status=201,
    summary='Record exact issue classification or create a source-bound communication request')
def prepare(request, case_id, *, body):
    actor = request.user
    case = accessible_case(actor, case_id)
    require(actor, case, 'issue.read')
    require(actor, case, 'issue.escalate')
    evidence = get_object_or_404(public_evidence(case.evidence.all()), pk=body['evidence_id'])
    args = (actor, case.pk)
    if body['action'] == 'classify':
        issue = get_object_or_404(public_current_issues(case), pk=body['issue_id'])
        row = native.capture_profile(*args, issue.pk, body['state_id'], body['classification'], body['timeline_impact'],
                                     body['trigger_at'], evidence.pk, body['note'], body['revision'])
    else:
        profile = get_object_or_404(EscalationProfile, pk=body['profile_id'],
            state__issue__in=public_current_issues(case), evidence__in=public_evidence(case.evidence.all()))
        row = native.request_escalation(*args, profile.pk, body['direction'], body['target'],
                                        evidence.pk, body['note'], body['revision'])
    case.refresh_from_db(fields=['revision'])
    return {'id': row.pk, 'revision': case.revision}


@endpoint(response=obj({**VERSIONS, 'id': ID, 'direction': TEXT, 'target': TEXT, 'stage': {'type': 'string'},
    'document_version_id': nullable(ID), 'can_request_communication_review': BOOLEAN, 'review_verdicts': array(VERDICT),
    'client_decisions': array(obj({'role': ROLE, 'verdicts': array(VERDICT)})),
    'history': array(DECISION, limit=30), 'receipts': array(RECEIPT, limit=30),
    'jobs': array(obj({'id': ID, 'state': TEXT, 'operations': array(choice('cancel', 'retry'))}), limit=30),
    'next_action': TEXT}), summary='Read the scoped client decision, communication review and original delivery records')
def detail(request, work_id):
    actor = request.user
    work = require_line(actor, work_id, factory.DEFINITION)
    with limit_queries(800):
        panel = factory.projection(actor, work)
        row = panel['request']
        eligible = factory.decision_controls(actor, work.case, panel['decision_roles'])
    return {'expected_revision': work.revision, 'case_revision': work.case.revision, 'id': row.pk,
            'direction': row.direction, 'target': row.target, 'stage': panel['native'].get('stage', ''),
            'document_version_id': panel['document'].pk if panel['document'] else None,
            'can_request_communication_review': panel['can_request_review'], 'review_verdicts': panel['review_verdicts'],
            'client_decisions': eligible, 'next_action': panel['next_action'],
            'history': [{'id': decision.pk, 'request_id': decision.request_id, 'role': decision.role,
                         'verdict': decision.verdict, 'created_at': decision.created_at} for decision in panel['decision_history'][-30:]],
            'receipts': [{'id': receipt.pk, 'publication_id': receipt.publication_id,
                          'recorded_at': receipt.created_at} for receipt in panel['receipts'][-30:]],
            'jobs': [{'id': job.pk, 'state': job.status,
                      'operations': ['cancel', 'retry'] if job.can_retry else ['cancel'] if job.can_operate else []}
                     for job in panel['jobs'][-30:]]}


@endpoint(method='POST', request={'oneOf': [obj({'action': {'const': action}, **VERSIONS, **fields})
    for action, fields in COMMANDS.items()]}, response=obj({**WORK_RESULT['properties'], 'record_id': nullable(ID)}),
    summary='Record the exact client decision or advance and reconcile the reviewed communication')
def command(request, work_id, *, body):
    actor = request.user
    work = require_line(actor, work_id, factory.DEFINITION)
    args = (actor, work.pk, body['expected_revision'])
    rev = body['case_revision']
    action = body['action']
    record_id = None
    if action == 'decide_client_action':
        row = factory.decide(*args, rev, body['request_id'], body['role'], body['verdict'], body['note'], body['delegated'])
        record_id = row.pk
    elif action == 'request_communication_review':
        row = factory.request_communication_review(*args, rev, body['version_id'])
        record_id = row.pk
    elif action == 'recover_delivery':
        factory.operate(*args, rev, body['job_id'], body['operation'], body['reason'])
        record_id = body['job_id']
    else:
        factory.reconcile(*args)
    work.refresh_from_db(fields=['status', 'revision', 'lease_until'])
    return {**result(work), 'record_id': record_id}

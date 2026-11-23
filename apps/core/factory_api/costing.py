"""Independent calculator evidence and exact Finance costing inputs."""

from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import Http404
from django.shortcuts import get_object_or_404

from adapters.costing import ORACLE, RULE, VALUE
from apps.agents.costing import investigate
from apps.core.evidence_access import public_evidence
from apps.core.views import accessible_case
from apps.identity.services import active_case_grants
from apps.pmo import costing as native, costing_proposals, costing_studio
from apps.pmo.costing_models import CostingOracle, CostingReview, CostingRule, CostingRun
from apps.pmo.costing_proposal_models import CostingProposal
from apps.policy.costing_drafts import draft_costing_policy
from apps.policy.costing_proposal_validators import COMPONENT as PROPOSAL_POLICY
from apps.policy.costing_validators import COMPONENT, SCHEMAS, STUDIO_VALUE
from apps.policy.document_validators import ROLES
from apps.policy.operator_drafts import draft_operator_policy
from apps.policy.services import resolve

from .delivery import PIN, PROOF, proof_rows
from .http import BOOLEAN, DATETIME, ID, REVISION, TEXT, array, choice, endpoint, nullable, obj
from .intake_sources import positive_id
from .work import PAGE, page_number


VERDICT = choice('confirm', 'dispute', 'withdraw')
KEY = {**TEXT, 'maxLength': 100, 'pattern': r'^[A-Za-z0-9][A-Za-z0-9_.:-]{0,99}$'}
REASON = {**TEXT, 'maxLength': 2000}
SOURCE = obj({'id': ID, 'reference': TEXT, 'version': REVISION, 'sha256': PIN})
SUMMARY = obj({'id': ID, 'status': choice('known', 'held')})
OWNER = {'evidence_id': ID, 'effective_from': DATETIME}
COMMANDS = {
    'rule': ('costing.capture', {'reference': KEY, 'evidence_id': ID, 'predecessor_id': nullable(ID)}),
    'oracle': ('costing.oracle.capture', {'rule_id': ID, 'reference': KEY, 'evidence_id': ID, 'predecessor_id': nullable(ID)}),
    'rule_review': ('costing.rule.review', {'rule_id': ID, 'verdict': VERDICT, 'operation_key': KEY, 'evidence_id': ID}),
    'oracle_review': ('costing.oracle.review', {'rule_id': ID, 'oracle_id': ID, 'verdict': VERDICT, 'operation_key': KEY, 'evidence_id': ID}),
    'calculate': ('costing.calculate', {'plan_id': ID, 'engineering_id': ID, 'security_id': ID,
                                      'inputs_id': ID, 'operation_key': KEY}),
    'bind': ('costing.bind', {'run_id': ID}),
    'bind_validation': ('costing.af13.bind', {'run_id': ID, 'package_id': ID}),
    'propose': ('costing.capture', {'base_id': ID, 'evidence_id': ID, 'reason': REASON, 'operation_key': KEY}),
    'draft_calculator': ('policy.configure', {**OWNER, 'value': {'oneOf': [SCHEMAS[COMPONENT][1], STUDIO_VALUE]}}),
    'draft_studio': ('policy.configure', {**OWNER, 'studio_source_id': ID}),
    'draft_proposal_review': ('policy.configure', {**OWNER, 'reviewer_id': nullable(ID), 'role': nullable(choice(*ROLES))}),
    'investigate': ('agent.costing', {}),
}
SUBJECT = choice('rule', 'oracle')
PROPOSAL_VERDICT = choice('confirm', 'return', 'withdraw')
PARAMETER = RULE['properties']['parameters']['items']


def scope(actor, case_id, source=False):
    case = accessible_case(actor, case_id)
    native.readable(actor, case, source)
    return case


def read_version(row):
    return {'id': row.pk, 'version': row.version, 'reference': row.reference, 'sha256': row.sha256}


@endpoint(response=obj({'revision': REVISION, 'policy_status': TEXT, 'actions': array(choice(*COMMANDS)),
    'rules': array(SOURCE, limit=20), 'oracles': array(obj({**SOURCE['properties'], 'rule_id': ID}), limit=20),
    'runs': array(SUMMARY, limit=20), 'proposal_ids': array(ID, limit=20), 'evidence': array(PROOF, limit=45),
    'next_page': nullable(PAGE)}), query={'page': PAGE}, summary='Read project calculation status and source-owner controls')
def options(request, case_id):
    actor = request.user
    case = scope(actor, case_id)
    grants = {action for _, action in active_case_grants(actor, [case.pk])}
    private = 'costing.source.read' in grants
    actions = [name for name, (grant, _) in COMMANDS.items() if grant in grants and (private or name == 'investigate')]
    page = page_number(request)
    offset = (page - 1) * 20
    window = slice(offset, offset + 21)
    rules = list(CostingRule.objects.filter(case=case).only('reference', 'version', 'sha256').order_by('-pk')[window]) if private else []
    oracles = list(CostingOracle.objects.filter(rule__case=case).only('rule_id', 'reference', 'version', 'sha256')
                   .order_by('-pk')[window]) if private else []
    runs = list(CostingRun.objects.filter(case=case).order_by('-pk').values_list('pk', 'result__status')[window])
    proposals = list(CostingProposal.objects.filter(base__case=case).order_by('-pk').values_list('pk', flat=True)[window]) if private else []
    proofs = case.evidence.filter(kind__in=['p14_rule', 'p14_oracle', 'p14_review', 'p14_inputs', 'plan',
                                         'engineering_estimate', 'security_estimate', 'policy_decision']).only('id', 'version', 'kind')
    return {'revision': case.revision, 'policy_status': resolve(COMPONENT, case).status, 'actions': actions,
            'rules': [read_version(row) for row in rules[:20]], 'oracles': [{**read_version(row), 'rule_id': row.rule_id} for row in oracles[:20]],
            'runs': [{'id': pk, 'status': status} for pk, status in runs[:20]], 'proposal_ids': proposals[:20],
            'evidence': proof_rows(proofs.order_by('-pk')[:45]) if private else [],
            'next_page': page + 1 if max(map(len, (rules, oracles, runs, proposals))) > 20 and page < PAGE['maximum'] else None}


@endpoint(response=obj({**SOURCE['properties'], 'kind': SUBJECT, 'payload': {'oneOf': [RULE, ORACLE]},
    'evidence_id': ID, 'reviews': array(obj({'id': ID, 'verdict': VERDICT, 'evidence_id': ID, 'created_at': DATETIME}), limit=20)}),
    path_parameters={'kind': SUBJECT}, summary='Read the restricted rule or independent examples and verdict history')
def source(request, case_id, kind, record_id):
    case = scope(request.user, case_id, True)
    if kind == 'rule':
        row = get_object_or_404(CostingRule, pk=record_id, case=case)
        history = CostingReview.objects.filter(rule=row, oracle__isnull=True)
    elif kind == 'oracle':
        row = get_object_or_404(CostingOracle, pk=record_id, rule__case=case)
        history = CostingReview.objects.filter(oracle=row)
    else:
        raise Http404
    return {**read_version(row), 'kind': kind, 'payload': row.payload, 'evidence_id': row.evidence_id,
            'reviews': list(history.order_by('-pk').values('id', 'verdict', 'evidence_id', 'created_at')[:20])}


@endpoint(response=obj({'id': ID, 'current_usable': BOOLEAN, 'status': choice('known', 'held'), 'holds': array(TEXT),
    'outputs': nullable(array(VALUE)), 'cost_approved': BOOLEAN, 'invoice_created': BOOLEAN}),
    summary='Read the exact calculation and its current usability, with values only for source-authorised readers')
def calculation(request, case_id, run_id):
    actor = request.user
    case = scope(actor, case_id)
    facts = native.report(actor, case.pk, run_id)
    return {'id': facts['run'], 'current_usable': facts['current_usable'], 'status': facts['recorded_status'],
            'holds': facts['holds'], 'outputs': facts.get('result', {}).get('values'), 'cost_approved': facts['cost_approved'],
            'invoice_created': facts['invoice_created']}


@endpoint(response=obj({'id': ID, 'revision': REVISION, 'base_rule_id': ID, 'reason': TEXT, 'parameters': array(obj({
    'key': TEXT, 'current': nullable(PARAMETER), 'proposed': nullable(PARAMETER)})), 'verdicts': array(PROPOSAL_VERDICT),
    'recorded_verdict': nullable(PROPOSAL_VERDICT), 'successor_rule_id': nullable(ID), 'active_successor': BOOLEAN,
    'independent_examples': array(SOURCE, limit=25), 'proposed_examples': array(PROOF, limit=8),
    'comparison': array(obj({'key': TEXT, 'before': nullable(array(VALUE)),
        'after': nullable(array(VALUE)), 'before_matches': BOOLEAN, 'after_matches': BOOLEAN}), limit=30),
    'hold': {'type': 'string'}}), query={'oracle_id': ID, 'proposed_evidence_id': ID},
    summary='Read a proposed calculator change and compare it against its independent worked examples')
def proposal(request, case_id, proposal_id):
    actor = request.user
    case = scope(actor, case_id, True)
    row = get_object_or_404(CostingProposal.objects.select_related('base__case', 'decision'), base__case=case, pk=proposal_id)
    panel = costing_proposals.presentation(actor, row)
    decision = getattr(row, 'decision', None)
    verdicts = []
    if not decision and not panel['hold']:
        if panel['own']:
            verdicts = ['withdraw']
        elif not panel['review_hold']:
            verdicts = ['confirm', 'return']
    oracle_id = positive_id(request, 'oracle_id')
    proposed_id = positive_id(request, 'proposed_evidence_id')
    proposed = costing_proposals.proposed_example_sources(actor, row)
    if oracle_id and proposed_id:
        raise ValidationError('Choose one source of independent examples.')
    if oracle_id:
        comparison = costing_proposals.compare_examples(actor, row, oracle_id)['examples']
    elif proposed_id:
        match = next((item for item in proposed if item['proof'].pk == proposed_id), None)
        if match is None:
            raise Http404
        comparison = costing_proposals.example_rows(row, match['value'])
    else:
        comparison = []
    examples = CostingOracle.objects.filter(rule=row.base).only('id', 'reference', 'version', 'sha256').order_by('-pk')[:25]
    return {'id': row.pk, 'revision': case.revision, 'base_rule_id': row.base_id, 'reason': row.reason,
            'parameters': panel['parameters'], 'verdicts': verdicts, 'recorded_verdict': decision.verdict if decision else None,
            'successor_rule_id': decision.rule_id if decision else None, 'active_successor': costing_proposals.active_successor(actor, row),
            'independent_examples': [read_version(oracle) for oracle in examples],
            'proposed_examples': proof_rows([item['proof'] for item in proposed]),
            'comparison': [{'key': item['key'], 'before': item['before']['values'] if item['before'] else None,
                            'after': item['after']['values'] if item['after'] else None,
                            'before_matches': item['before_matches'], 'after_matches': item['after_matches']} for item in comparison],
            'hold': panel['hold'] or panel['review_hold']}


@endpoint(method='POST', request=obj({'revision': REVISION, 'verdict': PROPOSAL_VERDICT, 'reason': REASON, 'evidence_id': ID}),
          response=obj({'id': ID, 'revision': REVISION}), status=201,
          summary='Record the independent proposal verdict or the original author’s withdrawal')
def decide_proposal(request, case_id, proposal_id, *, body):
    case = scope(request.user, case_id, True)
    decision = costing_proposals.decide(request.user, case.pk, proposal_id, body['verdict'], body['reason'],
                                        body['evidence_id'], body['revision'])
    case.refresh_from_db(fields=['revision'])
    return {'id': decision.pk, 'revision': case.revision}


@endpoint(method='POST', request={'oneOf': [obj({'action': {'const': action}, 'revision': REVISION, **fields})
    for action, (_, fields) in COMMANDS.items()]}, response=obj({'id': ID, 'revision': REVISION}), status=201,
    summary='Capture, independently review, calculate and link costing evidence under current policy')
def command(request, case_id, *, body):
    actor = request.user
    action, revision = body['action'], body['revision']
    case = scope(actor, case_id, action != 'investigate')
    args = (actor, case.pk)
    evidence_id = body.get('evidence_id')
    if action.startswith('draft_'):
        row = draft_policy(*args, action, revision, body)
    elif action == 'rule':
        row = native.capture_rule(*args, body['reference'], evidence_id, revision, body['predecessor_id'])
    elif action == 'oracle':
        row = native.capture_oracle(*args, body['rule_id'], body['reference'], evidence_id, revision, body['predecessor_id'])
    elif action in ('rule_review', 'oracle_review'):
        row = native.review(*args, body['rule_id'], body.get('oracle_id'), body['verdict'], body['operation_key'], evidence_id, revision)
    elif action == 'calculate':
        row = native.run(*args, body['plan_id'], body['engineering_id'], body['security_id'], body['inputs_id'], body['operation_key'], revision)
    elif action == 'bind':
        row = native.bind(*args, body['run_id'], revision)
    elif action == 'bind_validation':
        row = native.bind_af13(*args, body['run_id'], body['package_id'], revision)
    elif action == 'propose':
        row = costing_proposals.propose(*args, body['base_id'], evidence_id, body['reason'], body['operation_key'], revision)
    else:
        row = investigate(*args, revision)
    case.refresh_from_db(fields=['revision'])
    return {'id': row.pk, 'revision': case.revision}


@transaction.atomic
def draft_policy(actor, case_id, action, revision, body):
    case = native.locked(actor, case_id, 'policy.configure', revision)
    evidence = public_evidence(case.evidence.filter(pk=body['evidence_id'], kind='policy_decision')).first()
    if evidence is None:
        raise ValidationError('Choose recorded owner evidence in this workspace.')
    when = body['effective_from']
    if action == 'draft_calculator':
        return draft_costing_policy(actor, case.pk, body['value'], evidence.pk, when)
    if action == 'draft_studio':
        return costing_studio.draft_application(actor, case.pk, body['studio_source_id'], evidence.pk, when)
    value = {'reviewer_id': body['reviewer_id'], 'reviewer_role': body['role'], 'independent_review': True}
    return draft_operator_policy(actor, case.pk, PROPOSAL_POLICY, value, evidence.pk, when)

"""Reviewed preparation of a native P14 source successor."""
from django.core.exceptions import PermissionDenied, ValidationError
from django.contrib.auth import get_user_model
from django.db import transaction
from apps.core.services import bump, event
from apps.documents.contracts import digest, validate
from apps.identity.services import require
from apps.policy.services import active_component, decision_authority, reference_values
from apps.policy.costing_proposal_validators import COMPONENT
from adapters.costing import KEY, SuppliedCostingContractAdapter, graph
from adapters.costing import calculate, compare
from . import costing as native
from .costing_models import CostingRule
from .costing_proposal_models import CostingProposal, CostingProposalDecision


def source(case, evidence_id):
    evidence = native.subject(case, evidence_id, 'p14_rule')
    value = SuppliedCostingContractAdapter().read_rule(evidence)
    graph(value)
    if not case.synthetic and value['source_class'] == 'synthetic_fixture':
        raise ValidationError('Supply operational calculator evidence for this project.')
    if value['owner_id'] is not None and value['owner_id'] == value['oracle_owner_id']:
        raise ValidationError('Rule and worked-example owners must be different people.')
    for parameter in value['parameters']:
        native.subject(case, parameter['evidence_id'], 'p14_parameter')
    return evidence, value


def current(proposal):
    native.readable(proposal.actor, proposal.base.case, True)
    require(proposal.actor, proposal.base.case, 'costing.capture')
    native.current_source(proposal.base)
    evidence, value = source(proposal.base.case, proposal.evidence_id)
    if value != proposal.payload or digest(value) != proposal.sha256:
        raise ValidationError('Proposed source changed. Prepare a new proposal from the current evidence.')
    return evidence, value


@transaction.atomic
def propose(actor, case_id, base_id, evidence_id, reason, operation_key, expected=None):
    case = native.locked(actor, case_id, 'costing.capture', expected)
    native.readable(actor, case, True)
    validate(KEY, operation_key)
    if not isinstance(reason, str) or not 1 <= len(reason.strip()) <= 2000:
        raise ValidationError('Explain the proposed change in up to 2,000 characters.')
    base = native.rule_for(case, base_id)
    evidence, value = source(case, evidence_id)
    old = CostingProposal.objects.filter(base=base, operation_key=operation_key).first()
    if old:
        if (old.actor_id, old.evidence_id, old.reason, old.sha256) != (
                actor.pk, evidence.pk, reason.strip(), digest(value)):
            raise ValidationError('This proposal reference already records different changes.')
        return old
    native.current_source(base)
    if value == base.payload:
        raise ValidationError('The proposed version must contain a change.')
    row = CostingProposal.objects.create(base=base, evidence=evidence, payload=value,
        sha256=digest(value), reason=reason.strip(), operation_key=operation_key, actor=actor)
    event(actor, case, 'costing.version_proposed', proposal=row.pk, base=base.pk)
    bump(case)
    return row


def review_authority(actor, proposal):
    case = proposal.base.case
    native.readable(actor, case, True)
    require(actor, case, 'costing.rule.review')
    if actor.pk == proposal.actor_id:
        raise PermissionDenied('The person proposing a version cannot review it.')
    policy = active_component(COMPONENT, case)
    value = reference_values(policy)[0]
    if value['reviewer_id'] is None:
        raise ValidationError('Choose the independent calculator reviewer in business rules.')
    if actor.pk != value['reviewer_id']:
        raise PermissionDenied('The configured independent reviewer must make this decision.')
    return {'configuration': policy.pk,
            'role': decision_authority(actor, case, value['reviewer_role'])}


def validate_adoption(rule):
    decision = CostingProposalDecision.objects.select_related(
        'proposal__base__case', 'proposal__actor', 'actor').filter(rule=rule).first()
    if decision is None:
        return
    proposal = decision.proposal
    native.readable(proposal.actor, rule.case, True)
    require(proposal.actor, rule.case, 'costing.capture')
    _, value = source(rule.case, proposal.evidence_id)
    if (decision.verdict != 'confirm' or proposal.sha256 != rule.sha256 or value != rule.payload
            or decision.authority != review_authority(decision.actor, proposal)):
        raise ValidationError('Reassess the proposed calculator source and independent review authority.')


@transaction.atomic
def decide(actor, case_id, proposal_id, verdict, note, evidence_id, expected=None):
    action = 'costing.capture' if verdict == 'withdraw' else 'costing.rule.review'
    case = native.locked(actor, case_id, action, expected)
    native.readable(actor, case, True)
    proposal = CostingProposal.objects.select_related('base__case', 'actor').filter(
        base__case=case, pk=proposal_id).first()
    if proposal is None or verdict not in ['confirm', 'return', 'withdraw']:
        raise ValidationError('Select an exact proposal and decision.')
    if not isinstance(note, str) or not 1 <= len(note.strip()) <= 2000:
        raise ValidationError('Record the reason for this decision in up to 2,000 characters.')
    evidence = native.subject(case, evidence_id, 'p14_review')
    if verdict == 'withdraw':
        if actor.pk != proposal.actor_id:
            raise PermissionDenied('Only the proposer can withdraw this proposal.')
        authority = {'proposer': actor.pk}
    else:
        authority = review_authority(actor, proposal)
    old = CostingProposalDecision.objects.filter(proposal=proposal).first()
    if old:
        if (old.actor_id, old.verdict, old.note, old.evidence_id) != (
                actor.pk, verdict, note.strip(), evidence.pk):
            raise ValidationError('This proposal already has a recorded decision.')
        return old
    rule = None
    if verdict == 'confirm':
        source_evidence, value = current(proposal)
        # The proposer supplied this exact artifact. The separate decision records its reviewer.
        rule = CostingRule.objects.create(case=case, reference=proposal.base.reference,
            version=proposal.base.version + 1, payload=value, sha256=proposal.sha256,
            evidence=source_evidence, actor=proposal.actor)
    decision = CostingProposalDecision.objects.create(proposal=proposal, actor=actor,
        verdict=verdict, note=note.strip(), evidence=evidence, authority=authority, rule=rule)
    event(actor, case, 'costing.proposal_decided', proposal=proposal.pk,
        decision=decision.pk, verdict=verdict, rule=rule.pk if rule else None,
        source_owner_confirmations_required=rule is not None)
    bump(case)
    return decision


def presentation(actor, proposal):
    native.readable(actor, proposal.base.case, True)
    rows = []
    previous = {value['key']: value for value in proposal.base.payload['parameters']}
    for value in proposal.payload['parameters']:
        rows.append({'key': value['key'], 'current': previous.pop(value['key'], None), 'proposed': value})
    rows.extend({'key': value['key'], 'current': value, 'proposed': None} for value in previous.values())
    hold = ''
    try:
        current(proposal)
    except (PermissionDenied, ValidationError):
        hold = 'The source, proposer access or current version needs reassessment.'
    own = actor.pk == proposal.actor_id
    reviewer = None
    try:
        value = reference_values(active_component(COMPONENT, proposal.base.case))[0]
        reviewer = get_user_model().objects.filter(pk=value['reviewer_id'], is_active=True).first()
    except ValidationError:
        pass
    review_hold = ''
    try:
        review_authority(actor, proposal)
    except PermissionDenied as exc:
        review_hold = str(exc)
    except ValidationError:
        review_hold = 'Choose and confirm the independent calculator reviewer in business rules.'
    return {'proposal': proposal, 'parameters': rows, 'hold': hold,
            'own': own, 'review_hold': review_hold, 'reviewer': reviewer}


def compare_examples(actor, proposal, oracle_id):
    native.readable(actor, proposal.base.case, True)
    oracle = native.oracle_for(proposal.base, oracle_id)
    if (oracle.sha256 != digest(oracle.payload) or proposal.sha256 != digest(proposal.payload)
            or proposal.base.sha256 != digest(proposal.base.payload)):
        raise ValidationError('The example or proposed source needs reassessment.')
    examples = []
    for scenario in oracle.payload['scenarios']:
        before = calculate(proposal.base.payload, scenario['inputs'])
        after = None
        try:
            after = calculate(proposal.payload, scenario['inputs'])
        except ValidationError:
            pass
        examples.append({'key': scenario['key'], 'scenario': scenario['scenario'],
            'inputs': scenario['inputs'], 'expected': scenario['expected'],
            'before': before, 'after': after, 'before_matches': compare(before, scenario['expected']),
            'after_matches': compare(after, scenario['expected']) if after else False})
    return {'oracle': oracle, 'examples': examples}

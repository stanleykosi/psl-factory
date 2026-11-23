"""Carry a reviewed bid input adjustment through the native calculator and response."""
import json
from decimal import localcontext

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Q

from adapters.costing import number
from apps.core.models import Audit
from apps.core.services import add_evidence, bump, event, lock_case
from apps.identity.factory_access import department_cases, department_memberships, role_managed
from apps.identity.services import active_case_grants, require, subject_actions
from apps.pmo import costing, rfp
from apps.pmo.costing_models import CostingBinding
from apps.policy.bid_adjustment_validators import COMPONENT
from apps.policy.services import active_component, decision_authority, reference_values

from . import factory, factory_rfp
from .models import FactoryWork

PROPOSED = 'factory.finance_bid_adjustment_proposed'
APPROVED = 'factory.finance_bid_adjustment_approved'
RETURNED = 'factory.finance_bid_adjustment_returned'


def contract(actor, work):
    case = work.case
    if not case.synthetic or role_managed(actor):
        raise PermissionDenied('Finance Lead approval is required to change bid prices.')
    factory.access(actor, case, 'factory.start', factory_rfp.DEFINITION)
    costing.readable(actor, case, source=True)
    for action in ('factory.manage', 'costing.calculate', 'costing.bind', 'evidence.add'):
        require(actor, case, action)
    subject = factory_rfp.subject(work)
    rfp.ensure_open(subject)
    assignment = rfp.current_assignment(subject)
    if assignment.pm_id != actor.pk:
        raise PermissionDenied('The currently assigned project manager can adjust these inputs.')
    authority = decision_authority(actor, case, 'PM')
    basis, selected = calculation(work, subject)
    configuration = active_component(COMPONENT, case)
    value = reference_values(configuration)[0]
    if value['rule_id'] != basis.rule_id or not value['targets']:
        raise ValidationError('Configure adjustment targets and limits for this exact calculator version.')
    current_inputs = {item['key']: item for item in basis.inputs}
    targets = {item['input_key']: item for item in value['targets']
               if current_inputs[item['input_key']]['value'] is not None}
    if not targets:
        raise ValidationError('Record the current adjustment input before changing it.')
    return basis, targets, dict(authority, **{COMPONENT: configuration.pk}), selected


def calculation(work, subject):
    case = work.case
    if work.cancel_requested or work.status in ('verified', 'cancelled', 'followup_needed') or factory_rfp.submission_for(work):
        raise ValidationError('Use the separate follow-up for stopped or submitted responses.')
    selected = factory_rfp.inputs(work)
    if selected['intake'] != subject.current_intake_id:
        raise ValidationError('Select the current received bid before adjusting its costing.')
    basis = CostingBinding.objects.select_related('run__rule', 'run__case', 'run__actor', 'costing').filter(
        costing__case=case, costing_id=selected['sources']['costing'], run__case=case).first()
    if basis is None:
        raise ValidationError('A current reviewed native calculation is required before adjusting this bid.')
    costing.verify_costing(basis.costing, selected['sources']['plan'])
    snapshot = rfp.source_snapshot(subject)
    expected = {'plan': selected['sources']['plan'], 'engineering': snapshot['inputs']['Engineering']['evidence'],
                'security': snapshot['inputs']['Security']['evidence']}
    if {key: item[0] for key, item in basis.run.snapshot['sources'].items()} != expected:
        raise ValidationError('Recalculate with the current delivery plan and estimates before adjusting this bid.')
    return basis.run, selected


def finance_role(actor, case, *, lock=False):
    memberships = department_memberships(actor, 'finance-lead')
    if not department_cases(actor, 'finance-lead').filter(pk=case.pk).exists():
        return None
    memberships = memberships.filter(case__tenant=case.tenant, case__synthetic=case.synthetic)
    if lock:
        memberships = memberships.select_for_update(of=('self',))
    return memberships.filter(Q(case=case) | Q(mode='lead')).order_by('mode', 'pk').first()


def finance_calculation(work):
    subject = factory_rfp.subject(work)
    rfp.ensure_open(subject)
    run, selected = calculation(work, subject)
    if run.rule.payload['currency'] != 'NGN':
        raise ValidationError('A current naira calculation is required.')
    targets = {
        f'{kind}:{row["key"]}': {'key': f'{kind}:{row["key"]}', 'kind': kind,
                                'label': row['key'], 'amount': row['value']}
        for kind, rows in (('input', run.inputs), ('output', run.result['values']))
        for row in rows if row['unit'] == 'NGN' and row['value'] is not None
    }
    return run, selected, targets


def finance_proposal(work):
    proposal = Audit.objects.filter(case=work.case, action=PROPOSED, data__work=work.pk,
                                    data__head=work.source_head_id).order_by('-pk').first()
    if proposal is None:
        return None, None
    decision = Audit.objects.filter(case=work.case, action__in=(APPROVED, RETURNED),
                                    data__proposal=proposal.pk).order_by('-pk').first()
    return proposal, decision


def approved_instruction(work):
    owner = work.source_head.created_by
    latest = Audit.objects.filter(case=work.case, actor=owner, action='factory.rfp_costing_adjusted',
                                  data__work=work.pk, data__current_source=work.source_head_id,
                                  data__has_key='approval').first()
    if latest is None:
        return False
    approval = Audit.objects.filter(case=work.case, actor=owner, action=APPROVED, pk=latest.data['approval'],
                                    data__work=work.pk, data__head=latest.data['previous_source']).first()
    return bool(approval and department_cases(owner, 'finance-lead', heads_only=True).filter(pk=work.case_id).exists()
                and CostingBinding.objects.filter(costing_id=factory_rfp.inputs(work)['sources']['costing'],
                    costing__case=work.case, run_id=latest.data['current_run'], run__actor=owner,
                    run__snapshot__finance_approval=approval.pk).exists())


def finance_state(actor, work):
    membership = finance_role(actor, work.case)
    if not membership:
        return {'finance_targets': [], 'finance_pending': None, 'finance_last_decision': None,
                'can_propose': False, 'can_decide': False}
    try:
        _, _, targets = finance_calculation(work)
    except ValidationError:
        targets = {}
    proposal, decision = finance_proposal(work)
    pending = proposal if decision is None else None
    last = Audit.objects.filter(case=work.case, action__in=(APPROVED, RETURNED),
                                data__work=work.pk).order_by('-pk').first()
    return {'finance_targets': list(targets.values()), 'can_propose': bool(targets) and not pending,
            'can_decide': bool(targets and pending and pending.actor_id != actor.pk and membership.mode == 'lead'),
            'finance_last_decision': {
                'id': last.pk, 'proposal_id': last.data['proposal'], 'by': last.actor_id, 'at': last.created_at,
                'status': 'approved' if last.action == APPROVED else 'returned', 'reason': last.data['reason'],
            } if last else None,
            'finance_pending': {'id': pending.pk, 'by': pending.actor_id, 'at': pending.created_at,
                                **{key: pending.data[key] for key in ('target', 'before', 'after', 'reason')}}
            if pending else None}


@transaction.atomic
def finance_adjust(actor, work_id, revision, case_revision, action, reason, *, target=None, amount=None,
                   proposal_id=None):
    work = FactoryWork.objects.select_for_update(of=('self',)).select_related('case', 'source_head').get(
        pk=work_id, definition=factory_rfp.DEFINITION)
    case = lock_case(actor, work.case_id, 'case.read', case_revision)
    work.case = case
    membership = finance_role(actor, case, lock=True)
    if not membership:
        raise PermissionDenied('Only the assigned Finance team can change bid prices.')
    if work.revision != revision:
        raise ValidationError('The bid changed. Open its current calculation.')
    rfp.note(reason)
    proposal, decision = finance_proposal(work)
    if action == 'propose':
        if proposal and decision is None:
            raise ValidationError('Finance Lead must decide the pending price change first.')
        base, _, targets = finance_calculation(work)
        if target not in targets or amount == number(targets[target]['amount']):
            raise ValidationError('Enter a new naira amount for an exact current price line.')
        event(actor, case, PROPOSED, work=work.pk, head=work.source_head_id, base=base.pk, target=target,
              before=targets[target]['amount'], after=format(amount, 'f'), currency='NGN', reason=reason.strip())
        bump(case)
        return work
    if action not in ('approve', 'return'):
        raise ValidationError('Choose to approve or return the exact price proposal.')
    if membership.mode != 'lead' or proposal and proposal.actor_id == actor.pk:
        raise PermissionDenied('A different Finance Lead must decide this price change.')
    if not proposal or proposal.pk != proposal_id or decision:
        raise ValidationError('Choose the exact pending price change.')
    if action == 'return':
        event(actor, case, RETURNED, work=work.pk, proposal=proposal.pk, reason=reason.strip())
        bump(case)
        return work
    base, selected, targets = finance_calculation(work)
    if proposal.data['base'] != base.pk or proposal.data['target'] not in targets:
        raise ValidationError('The calculation changed. Ask Finance to propose the change again.')
    if not finance_role(proposal.actor, case, lock=True):
        raise ValidationError('The requester no longer has access to this bid.')
    return apply_finance_adjustment(actor, work, base, selected, proposal, reason)


def apply_finance_adjustment(actor, work, base, selected, proposal, reason):
    case = work.case
    kind, key = proposal.data['target'].split(':', 1)
    inputs = [dict(row) for row in base.inputs]
    outputs = dict(base.snapshot.get('approved_outputs', {}))
    if kind == 'output':
        outputs[key] = proposal.data['after']
    else:
        next(row for row in inputs if row['key'] == key)['value'] = proposal.data['after']
    evidence = add_evidence(actor, case.pk, 'p14_inputs', json.dumps(inputs, sort_keys=True),
                            f'derived:finance-bid-adjustment:{proposal.pk}', case.revision)
    approval = event(actor, case, APPROVED, work=work.pk, proposal=proposal.pk, head=work.source_head_id,
                     base=base.pk, input_evidence=evidence.pk, outputs=outputs, reason=reason.strip())
    sources = base.snapshot['sources']
    run = costing.run(actor, case.pk, sources['plan'][0], sources['engineering'][0], sources['security'][0],
                      evidence.pk, f'finance-bid-adjustment:{proposal.pk}', finance_approval=approval.pk)
    binding = costing.bind(actor, case.pk, run.pk)
    payload = {key: selected[key] for key in factory_rfp.FIELDS}
    payload['sources'] = dict(payload['sources'], costing=binding.costing_id)
    case.refresh_from_db(fields=['revision'])
    with subject_actions(actor, case, ('factory.manage', 'rfp.read')):
        successor = factory_rfp.correct(actor, work.pk, work.revision, case.revision, payload, reason)
    event(actor, case, 'factory.rfp_costing_adjusted', work=work.pk, previous_run=base.pk, current_run=run.pk,
          previous_source=work.source_head_id, current_source=successor.source_head_id, approval=approval.pk,
          target=proposal.data['target'], amount=proposal.data['after'], currency='NGN', reason=reason.strip())
    return successor


def history(actor, work):
    try:
        costing.readable(actor, work.case, source=True)
    except PermissionDenied:
        return []
    return Audit.objects.filter(case=work.case, action='factory.rfp_costing_adjusted',
                                data__work=work.pk).select_related('actor').order_by('-pk')[:15]


def can_configure(actor, work):
    grants = active_case_grants(actor, [work.case_id], actions=['ops.read', 'policy.configure', 'costing.source.read'])
    return all((work.case_id, action) in grants for action in ('ops.read', 'policy.configure', 'costing.source.read'))


@transaction.atomic
def adjust(actor, work_id, revision, case_revision, target, amount, reason):
    work = FactoryWork.objects.select_for_update(of=('self',)).select_related('case', 'source_head').get(
        pk=work_id, definition=factory_rfp.DEFINITION)
    case = lock_case(actor, work.case_id, 'factory.manage', case_revision)
    work.case = case
    if work.revision != revision:
        raise ValidationError('The bid changed. Open the latest calculation before applying an adjustment.')
    rfp.note(reason)
    base, targets, authority, selected = contract(actor, work)
    if target not in targets or not amount:
        raise ValidationError('Choose a configured input and a non-zero amount.')
    new_inputs = [dict(entry) for entry in base.inputs]
    changed = next(entry for entry in new_inputs if entry['key'] == target)
    with localcontext() as precision:
        precision.prec = 64
        new_amount = number(changed['value']) + amount
    if abs(new_amount) > number(targets[target]['max_absolute_value']):
        raise ValidationError('The resulting adjustment would exceed the configured limit.')
    changed['value'] = format(new_amount, 'f')
    evidence = add_evidence(actor, case.pk, 'p14_inputs', json.dumps(new_inputs, sort_keys=True),
                            f'derived:bid-adjustment:{work.pk}:{base.pk}', case.revision)
    sources = base.snapshot['sources']
    run = costing.run(actor, case.pk, sources['plan'][0], sources['engineering'][0], sources['security'][0],
                      evidence.pk, f'bid-adjustment:{work.pk}:{work.source_head_id}')
    if run.result['values'] == base.result['values']:
        raise ValidationError('The declared calculation did not change. Review the configured adjustment target.')
    binding = costing.bind(actor, case.pk, run.pk)
    payload = {key: selected[key] for key in factory_rfp.FIELDS}
    payload['sources'] = dict(payload['sources'], costing=binding.costing_id)
    case.refresh_from_db(fields=['revision'])
    successor = factory_rfp.correct(actor, work.pk, revision, case.revision, payload, reason)
    event(actor, case, 'factory.rfp_costing_adjusted', work=work.pk, previous_run=base.pk, current_run=run.pk,
          previous_source=work.source_head_id, current_source=successor.source_head_id, authority=authority,
          target=targets[target]['label'], amount=format(amount, 'f'), currency=base.rule.payload['currency'], reason=reason.strip())
    return successor

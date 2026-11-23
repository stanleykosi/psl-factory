"""Carry a reviewed bid input adjustment through the native calculator and response."""
import json
from decimal import localcontext

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from adapters.costing import number
from apps.core.models import Audit
from apps.core.services import add_evidence, event, lock_case
from apps.identity.services import active_case_grants, require
from apps.pmo import costing, rfp
from apps.pmo.costing_models import CostingBinding
from apps.policy.bid_adjustment_validators import COMPONENT
from apps.policy.services import active_component, decision_authority, reference_values

from . import factory, factory_rfp
from .models import FactoryWork


def contract(actor, work):
    case = work.case
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
    configuration = active_component(COMPONENT, case)
    value = reference_values(configuration)[0]
    if value['rule_id'] != basis.run.rule_id or not value['targets']:
        raise ValidationError('Configure adjustment targets and limits for this exact calculator version.')
    current_inputs = {item['key']: item for item in basis.run.inputs}
    targets = {item['input_key']: item for item in value['targets']
               if current_inputs[item['input_key']]['value'] is not None}
    if not targets:
        raise ValidationError('Record the current adjustment input before changing it.')
    return basis.run, targets, dict(authority, **{COMPONENT: configuration.pk}), selected


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

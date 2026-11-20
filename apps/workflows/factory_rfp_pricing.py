"""Read the bid's exact costing sources and native approval status."""

from django import forms
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from apps.core.evidence_access import public_evidence
from apps.core.models import Evidence
from apps.core.read_observation import read_observation
from apps.identity.services import active_case_grants, require
from apps.pmo import commercial, costing, rfp
from apps.pmo.costing_models import CostingBinding
from . import factory, factory_rfp, factory_rfp_adjustments


APPROVERS = [('PM', 'Project manager'), ('Head of PMO', 'Head of project management'), ('CEO', 'Chief executive')]


class AdjustmentForm(forms.Form):
    revision = forms.IntegerField(min_value=1, widget=forms.HiddenInput)
    case_revision = forms.IntegerField(min_value=1, widget=forms.HiddenInput)
    target = forms.ChoiceField(label='Apply to')
    amount = forms.DecimalField(label='Amount to add or subtract', max_digits=32, decimal_places=8)
    reason = forms.CharField(max_length=2000, widget=forms.Textarea(attrs={'rows': 3}))


@read_observation
def inspect(actor, work):
    case = work.case
    factory.access(actor, case, 'factory.read', factory_rfp.DEFINITION)
    require(actor, case, 'rfp.read')
    selected = factory_rfp.inputs(work)
    root = factory_rfp.subject(work)
    current_intake = root.current_intake_id == selected['intake']
    inputs = {'Requirements': selected['sources']['requirements'], 'Delivery plan': selected['sources']['plan']}
    estimates = {}
    if current_intake:
        for team in ('Engineering', 'Security'):
            contribution = (root.current_intake.contributions.filter(team=team)
                            .order_by('-pk').values('evidence_id', 'actor_id').first())
            if contribution:
                try:
                    original = get_user_model().objects.get(pk=contribution['actor_id'], is_active=True)
                    require(original, case, f'rfp.contribute:{team}')
                    estimates[team] = contribution['evidence_id']
                except (PermissionDenied, get_user_model().DoesNotExist):
                    pass
            inputs[f'{team} estimate'] = estimates.get(team)
    else:
        inputs.update({'Engineering estimate': None, 'Security estimate': None})
    cost_id = selected['sources']['costing']
    inputs['Costing source'] = cost_id
    visible = {row['pk']: row for row in public_evidence(Evidence.objects.filter(case=case, pk__in=inputs.values()))
               .values('pk', 'version', 'sha256')}
    source_pins = {
        'plan': visible.get(selected['sources']['plan']),
        'engineering': visible.get(estimates.get('Engineering')),
        'security': visible.get(estimates.get('Security')),
    }
    inputs = [(label, visible.get(source, {}).get('version')) for label, source in inputs.items()]

    amounts, note = [], 'Select a reviewed costing source before relying on any amount.'
    can_open_calculator = False
    try:
        costing.readable(actor, case)
        can_open_calculator = True
        costing.readable(actor, case, source=True)
    except PermissionDenied:
        note = 'Your access does not include the calculation amounts.'
    else:
        binding = (CostingBinding.objects.filter(costing__case=case, costing_id=cost_id, run__case=case)
                   .select_related('costing', 'run').defer('costing__body', 'run__inputs', 'run__result').first())
        if cost_id in visible and binding is None:
            note = 'A costing reference was supplied. Its calculated amounts are unavailable here.'
        if cost_id in visible and binding:
            exact = current_intake and all(source_pins.values()) and binding.run.snapshot.get('sources') == {
                name: [source['pk'], source['sha256']] for name, source in source_pins.items()
            }
            try:
                if not exact:
                    raise ValidationError('Costing inputs changed.')
                commercial_cost = binding.costing
                costing.verify_costing(commercial_cost, selected['sources']['plan'])
                recorded = costing.report(actor, case.pk, binding.run_id)
                if not recorded['current_usable'] or 'result' not in recorded:
                    raise ValidationError('Costing rules or access changed.')
            except (ValidationError, PermissionDenied):
                note = 'The recorded calculation needs review against the current inputs and costing rule.'
            else:
                amounts = recorded['result']['values']
                note = 'Amounts come from the reviewed calculation for these inputs.'

    approvals = []
    response = root.current_response
    revision = None
    if response and response.intake_id == selected['intake'] and all(
            response.commercial.sources.get(key) == source for key, source in selected['sources'].items()):
        revision = response.commercial
        decisions = {decision.role: decision for decision in revision.decisions.filter(
            role__in=[role for role, _ in APPROVERS]).order_by('pk').defer('note')}
    else:
        decisions = {}
    current = False
    if revision:
        try:
            rfp.current_response(case, response.pk)
        except (ValidationError, PermissionDenied):
            pass
        else:
            current = True
    for role, label in APPROVERS:
        decision = decisions.get(role)
        status = 'Not yet recorded'
        if decision:
            status = {'approve': 'Approved', 'return': 'Returned', 'reject': 'Rejected',
                      'withdraw': 'Withdrawn'}.get(decision.verdict, 'Recorded decision')
            if current:
                try:
                    commercial.check_decision(decision)
                except (ValidationError, PermissionDenied):
                    status = 'Earlier decision needs fresh review'
        approvals.append((label, status, decision.created_at if decision else None))
    return {'security_estimate_missing': estimates.get('Security') not in visible,
            'estimate_missing': any(estimates.get(team) not in visible for team in ('Engineering', 'Security')),
            'inputs': inputs, 'amounts': amounts, 'costing_note': note,
            'can_open_calculator': can_open_calculator, 'approvals': approvals,
            'revision': revision.number if revision else None, 'revision_id': revision.pk if revision else None,
            'current': current}


@login_required
@require_http_methods(['GET', 'HEAD', 'POST'])
def detail(request, work_id):
    from .factory_views import visible
    work = get_object_or_404(visible(request.user, work_id=work_id), pk=work_id, definition=factory_rfp.DEFINITION)
    if request.method == 'POST' and request.POST.get('action') != 'adjust':
        return HttpResponseNotAllowed(['GET', 'HEAD'])
    report = inspect(request.user, work)
    form, adjustment_note, adjustment_currency = None, '', ''
    actor = request.user
    try:
        run, targets, _, _ = factory_rfp_adjustments.contract(actor, work)
    except PermissionDenied:
        if request.method == 'POST':
            raise
    except ValidationError:
        if report['can_open_calculator']:
            adjustment_note = 'A current reviewed calculation and adjustment limits are required before editing.'
    else:
        adjustment_currency = run.rule.payload['currency']
        form = AdjustmentForm(request.POST if request.method == 'POST' else None, initial={
            'revision': work.revision, 'case_revision': work.case.revision})
        form.fields['target'].choices = [(key, value['label']) for key, value in targets.items()]
        if request.method == 'POST' and form.is_valid():
            value = form.cleaned_data
            try:
                factory_rfp_adjustments.adjust(actor, work.pk, value['revision'], value['case_revision'],
                                               value['target'], value['amount'], value['reason'])
            except ValidationError as exc:
                form.add_error(None, exc)
            else:
                messages.success(request, 'Adjustment recorded. The updated bid requires fresh decisions.')
                return redirect('factory_rfp_pricing', work_id=work.pk)
    result = render(request, 'factory/rfp_pricing.html', {
        'case': work.case, 'work': work, 'pricing': report, 'adjustment_form': form,
        'adjustment_note': adjustment_note, 'adjustment_currency': adjustment_currency,
        'can_configure': factory_rfp_adjustments.can_configure(actor, work),
        'can_open_security_request': (work.case_id, 'rfp.estimate.read') in active_case_grants(
            actor, [work.case_id], actions=['rfp.estimate.read']),
        'adjustments': factory_rfp_adjustments.history(actor, work),
    })
    result['Cache-Control'] = 'no-store'
    return result

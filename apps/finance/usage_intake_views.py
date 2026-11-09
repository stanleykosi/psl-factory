from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError, PermissionDenied
from django.shortcuts import render, redirect
from apps.core.views import accessible_case
from apps.agents.models import AgentRun
from .forms import CommandForm
from .models import UsageIntakeSource, UsageIntakeReceipt
from . import usage_intake as domain


def commands(case, data=None):
    def source(optional=False):
        return forms.ModelChoiceField(UsageIntakeSource.objects.filter(case=case), required=not optional)
    def evidence(kind):
        return forms.ModelChoiceField(case.evidence.filter(kind=kind))
    definitions = {
        'receive': ('Record actual delivery or reconcile retry', {
            'source_evidence': evidence('usage_intake_source'), 'control_evidence': evidence('usage_intake_controls'),
            'delivery_ref': forms.CharField(max_length=100), 'operation_key': forms.CharField(max_length=100), 'predecessor': source(True)}),
        'inspect': ('Investigate missing fields and collective controls', {'source': source()}),
        'accept': ('Reconcile all populations and accept for pricing', {'source': source()}),
        'withdraw': ('Withdraw source from future dependent use', {'source': source(), 'evidence': evidence('usage_intake_withdrawal'), 'reason': forms.CharField(max_length=1000)}),
        'lookup': ('Look up uncertain operation before retry', {'operation_key': forms.CharField(max_length=100)}),
    }
    result = []
    for action, (label, fields) in definitions.items():
        form = CommandForm(data if data and data.get('action') == action else None,
                           initial={'action': action, 'revision': case.revision}, auto_id='intake_' + action + '_%s')
        form.fields.update(fields)
        result.append({'action': action, 'label': label, 'form': form})
    return result


@login_required
def workbench(request, case_id):
    case = accessible_case(request.user, case_id)
    domain.access(request.user, case)
    forms = commands(case, request.POST if request.method == 'POST' else None)
    receipt = None
    if request.method == 'POST':
        try:
            command = next((x for x in forms if x['action'] == request.POST.get('action')), None)
            if not command or not command['form'].is_valid():
                raise ValidationError(command['form'].errors.as_text() if command else 'Select a usage-intake action')
            d = command['form'].cleaned_data
            a, c, v, action = request.user, case.pk, d['revision'], d['action']
            if action == 'receive':
                receipt = domain.receive(a, c, d['source_evidence'].pk, d['control_evidence'].pk, d['delivery_ref'], d['operation_key'], v,
                                         d['predecessor'].pk if d['predecessor'] else None)
                messages.success(request, f'Delivery receipt #{receipt.pk} recorded; ' + ('duplicate content, no new usage.' if receipt.duplicate_of_id else 'reconciliation required before pricing.'))
            elif action == 'inspect': domain.investigate(a, c, d['source'].pk, v)
            elif action == 'accept':
                accepted = domain.accept(a, c, d['source'].pk, v)
                messages.success(request, f'Collective acceptance #{accepted.pk}; native usage partitions ready for separate pricing and invoice review.')
            elif action == 'withdraw': domain.withdraw(a, c, d['source'].pk, d['evidence'].pk, d['reason'], v)
            elif action == 'lookup':
                receipt = domain.lookup(a, c, d['operation_key'])
                messages.info(request, f'Original receipt #{receipt.pk}; source #{receipt.source_id}. No new effect.' if receipt else 'No committed receipt for this operation. Check the supplied delivery identity before retrying.')
            return redirect('finance_usage_intake', case_id=c)
        except ValidationError as exc:
            messages.error(request, str(exc)); case.refresh_from_db()
    sources = list(UsageIntakeSource.objects.filter(case=case).order_by('-pk')[:40])
    for source in sources:
        source.reconciliation = domain.inspect(source)
        source.partitions = source.acceptance.partitions.select_related('coverage') if hasattr(source, 'acceptance') else []
    return render(request, 'finance/usage_intake.html', {
        'case': case, 'commands': forms, 'sources': sources,
        'receipts': UsageIntakeReceipt.objects.filter(case=case).select_related('source').order_by('-pk')[:60],
        'agents': AgentRun.objects.filter(case=case, provider='deterministic-usage-intake-v1').order_by('-pk')[:10],
    })

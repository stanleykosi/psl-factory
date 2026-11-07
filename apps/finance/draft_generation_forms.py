from django import forms
from apps.identity.models import Grant
from .forms import CommandForm
from .models import BillingPreparation, BillingEvidenceSource, DraftGeneration


def commands(actor, case, data=None):
    allowed = set(Grant.objects.filter(case=case, user=actor, active=True).values_list('action', flat=True))
    if not {'case.read', 'finance.read', 'd03.read'} <= allowed:
        return []
    rows = DraftGeneration.objects.filter(case=case)
    definitions = {
        'generation_reserve': ('finance.draft_generation.dispatch', 'Reserve draft-only generation', {
            'preparation': forms.ModelChoiceField(BillingPreparation.objects.filter(case=case)),
            'source': forms.ModelChoiceField(BillingEvidenceSource.objects.filter(case=case, kind='flow_contract')),
            'batch_ref': forms.CharField(max_length=100), 'operation_key': forms.CharField(max_length=100)}),
        'generation_run': ('finance.draft_generation.lookup', 'Run or reconcile original draft generation', {
            'generation': forms.ModelChoiceField(rows)}),
        'generation_cancel': ('finance.draft_generation.cancel', 'Stop new draft-generation effects', {
            'generation': forms.ModelChoiceField(rows), 'reason': forms.CharField(max_length=500)})}
    result = []
    for action, (permission, label, fields) in definitions.items():
        if permission not in allowed or action == 'generation_reserve' and 'd03.source.read' not in allowed:
            continue
        form = CommandForm(data if data and data.get('action') == action else None,
            initial={'action': action, 'revision': case.revision}, auto_id=action + '_%s')
        form.fields.update(fields)
        result.append({'label': label, 'form': form, 'action': action})
    return result

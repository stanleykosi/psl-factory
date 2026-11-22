"""Human-supplied observations using the project's reviewed stability metrics."""
from django import forms
from django.core.exceptions import PermissionDenied, ValidationError
from django.utils import timezone

from apps.core.evidence_access import public_evidence
from apps.identity.services import require
from apps.policy.services import active_component, reference_values


class StabilityForm(forms.Form):
    configuration = forms.IntegerField(widget=forms.HiddenInput)
    owner = forms.CharField(widget=forms.HiddenInput)
    observed_at = forms.DateTimeField(label='Observation time', widget=forms.DateTimeInput(
        attrs={'type': 'datetime-local'}, format='%Y-%m-%dT%H:%M'))
    confirmed = forms.ChoiceField(label='Owner confirmation', choices=[
        ('unknown', 'Unknown'), ('yes', 'Confirmed stable'), ('no', 'Stability not confirmed')])
    reference = forms.CharField(label='Source reference', max_length=240)
    evidence = forms.ModelChoiceField(queryset=None, label='Supporting evidence')
    verify_sample = forms.BooleanField(required=False, label='Verify through the isolated sample adapter')

    def __init__(self, case, configuration, owner, criteria, data=None):
        super().__init__(data, auto_id='id_'+owner.lower()+'_%s',
                         initial={'configuration': configuration.pk, 'owner': owner})
        self.owner_name = owner
        self.configuration_id = configuration.pk
        self.metrics = [metric for metric in criteria['metrics'] if metric['owner'] == owner]
        self.fields['evidence'].queryset = public_evidence(case.evidence.all()).defer('body').order_by('-pk')
        if not case.synthetic:
            self.fields.pop('verify_sample')
        for index, metric in enumerate(self.metrics):
            operator = {'lte': 'at most', 'gte': 'at least', 'eq': 'equal to'}[metric['operator']]
            self.fields[f'metric_{index}'] = forms.FloatField(required=False,
                label=f"{metric['key'].replace('_', ' ').capitalize()} ({metric['unit']})",
                help_text=f"Reviewed criterion {operator} {metric['threshold']}. Leave blank if unknown.")

    def clean(self):
        values = super().clean()
        if values.get('configuration') != self.configuration_id or values.get('owner') != self.owner_name:
            raise ValidationError('The stability rule or source owner changed. Review the current form.')
        if values.get('observed_at') and values['observed_at'] > timezone.now():
            self.add_error('observed_at', 'Enter when the observation actually occurred.')
        return values

    def payload(self):
        values = self.cleaned_data
        return {'observed_at': values['observed_at'].isoformat(),
            'confirmed': {'yes': True, 'no': False, 'unknown': None}[values['confirmed']],
            'metrics': {metric['key']: {'value': values[f'metric_{index}'], 'unit': metric['unit']}
                for index, metric in enumerate(self.metrics)}}


def observation_forms(actor, work, data=None):
    try:
        require(actor, work.case, 'delivery.source')
        configuration = active_component('D11.hypercare_criteria_ref', work.case)
    except (PermissionDenied, ValidationError):
        return []
    if work.cancel_requested or work.status in {'cancelled', 'followup_needed'}:
        return []
    criteria = reference_values(configuration)[0]
    return [StabilityForm(work.case, configuration, owner, criteria,
                         data if data is not None and data.get('owner') == owner else None)
            for owner in criteria['confirmation_owners']]

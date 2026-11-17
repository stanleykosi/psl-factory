"""Draft exact group disclosure choices against a reviewed native forecast."""
import copy
import hashlib
import json

from django import forms
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction

from apps.core.evidence_access import public_evidence
from apps.core.models import Evidence
from apps.core.services import lock_case
from apps.identity.services import require
from apps.policy.document_validators import ROLES
from apps.policy.finance_drafts import draft_finance_policy
from apps.policy.group_forecast_validators import FIELDS, METADATA, validate_group
from apps.policy.services import active_component, reference_values

from . import forecast, group_forecast


class GroupDisclosureForm(forms.Form):
    base_configuration = forms.IntegerField(widget=forms.HiddenInput)
    rows = forms.MultipleChoiceField(label='Forecast items to share', widget=forms.CheckboxSelectMultiple)
    fields = forms.MultipleChoiceField(label='Values to share', widget=forms.CheckboxSelectMultiple,
        choices=[(key, key.replace('_', ' ').capitalize()) for key in FIELDS])
    metadata = forms.MultipleChoiceField(label='Report context', widget=forms.CheckboxSelectMultiple,
        choices=[(key, key.replace('_', ' ').capitalize()) for key in METADATA])
    recipients = forms.ModelMultipleChoiceField(queryset=get_user_model().objects.none(),
        label='Permitted recipients', widget=forms.CheckboxSelectMultiple)
    reviewer_roles = forms.MultipleChoiceField(label='Reviewer roles', choices=[(role, role) for role in ROLES])
    publisher_roles = forms.MultipleChoiceField(label='Publisher roles', choices=[(role, role) for role in ROLES])
    allow_preparer_review = forms.ChoiceField(label='May the preparer review this report?',
        choices=[('', 'Choose the recorded rule'), ('no', 'Require a different reviewer'), ('yes', 'Allow the preparer')])
    oracle = forms.ModelChoiceField(queryset=Evidence.objects.none(), label='Independent expected report evidence')
    decision = forms.ModelChoiceField(queryset=Evidence.objects.none(), label='Recorded owner decision')
    effective_from = forms.DateTimeField(label='Effective from', widget=forms.DateTimeInput(attrs={'type': 'datetime-local'}))

    def __init__(self, actor, case, run, configuration, data=None):
        require(actor, case, 'finance.read')
        require(actor, case, 'policy.configure')
        if run.case_id != case.pk:
            raise ValidationError('Select a forecast from this project.')
        self.case, self.run, self.configuration = case, run, configuration
        existing = reference_values(configuration)[0].get('group', {})
        initial = {key: existing.get(key) for key in ['rows', 'fields', 'metadata', 'reviewer_roles', 'publisher_roles']}
        initial.update(base_configuration=configuration.pk, recipients=existing.get('recipient_ids'),
            oracle=existing.get('oracle_evidence_id'), allow_preparer_review=(
                'yes' if existing['allow_preparer_review'] else 'no') if 'allow_preparer_review' in existing else '')
        super().__init__(data, initial=initial, auto_id='group_rule_%s')
        self.fields['rows'].choices = [(row['key'], row['key']) for row in run.result['items']]
        self.fields['recipients'].queryset = get_user_model().objects.filter(is_active=True,
            grant__case=case, grant__action='document.receive:group', grant__active=True).distinct().order_by('username')
        # These are private Finance sources. The domain grants above authorise
        # this exact case and kind, while generic evidence pickers keep hiding them.
        self.fields['oracle'].queryset = case.evidence.filter(kind='forecast_group_oracle').defer('body')
        self.fields['decision'].queryset = public_evidence(case.evidence.filter(kind='policy_decision')).defer('body')

    def record(self):
        values = self.cleaned_data
        return {'implementation': 'native_selected_items_v1', 'run_id': self.run.pk, 'run_hash': self.run.sha256,
            'rows': values['rows'], 'fields': values['fields'], 'metadata': values['metadata'],
            'recipient_ids': sorted(person.pk for person in values['recipients']),
            'reviewer_roles': values['reviewer_roles'], 'publisher_roles': values['publisher_roles'],
            'allow_preparer_review': values['allow_preparer_review'] == 'yes', 'oracle_evidence_id': values['oracle'].pk}

    def clean(self):
        values = super().clean()
        if self.errors:
            return values
        if values['base_configuration'] != self.configuration.pk:
            raise ValidationError('The disclosure rules changed. Review their current version.')
        record = self.record()
        validate_group(record)
        forecast.approved(self.run)
        expected = group_forecast.project(self.run.result, record)
        oracle = values['oracle']
        if oracle.sha256 != hashlib.sha256(oracle.body.encode()).hexdigest():
            self.add_error('oracle', 'The independent evidence content differs from its recorded fingerprint.')
            return values
        try:
            supplied = json.loads(oracle.body)
        except ValueError as exc:
            raise ValidationError('The independent evidence must contain the exact expected report.') from exc
        if supplied != expected:
            self.add_error('oracle', 'The independent expected report differs from the selected items and values.')
        return values


@transaction.atomic
def save(actor, case, run, data, expected):
    case = lock_case(actor, case.pk, 'policy.configure', expected)
    require(actor, case, 'finance.read')
    if run.case_id != case.pk:
        raise ValidationError('Select a forecast from this project.')
    configuration = active_component('D10.audience_projection_rules', case)
    if 'forecast' not in reference_values(configuration)[0]:
        raise ValidationError('Review the forecast audience rules before adding group disclosure.')
    form = GroupDisclosureForm(actor, case, run, configuration, data)
    if not form.is_valid():
        raise ValidationError([message for messages in form.errors.values() for message in messages])
    content = copy.deepcopy(reference_values(configuration)[0])
    content['group'] = form.record()
    return draft_finance_policy(actor, case.pk, 'D10.audience_projection_rules', content,
        form.cleaned_data['decision'].pk, form.cleaned_data['effective_from'])

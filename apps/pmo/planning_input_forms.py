import copy

from django import forms
from django.core.exceptions import PermissionDenied, ValidationError
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from apps.policy.document_validators import ROLES
from apps.policy.operator_drafts import draft_operator_policy
from apps.policy.planning_validators import COMPONENT, DEPARTMENTS
from . import planning


class DepartmentInputForm(forms.Form):
    packet_id = forms.IntegerField(min_value=1, widget=forms.HiddenInput)
    department = forms.ChoiceField(choices=[(name, name) for name in DEPARTMENTS], widget=forms.HiddenInput)
    previous_id = forms.IntegerField(required=False, min_value=1, widget=forms.HiddenInput)
    source_id = forms.IntegerField(min_value=1, label='Supporting document reference')
    source_party = forms.CharField(max_length=160, label='Who supplied this input?')
    received_at = forms.DateTimeField(label='Received at', widget=forms.DateTimeInput(format='%Y-%m-%dT%H:%M:%S', attrs={'type': 'datetime-local', 'step': '1'}))
    summary = forms.CharField(max_length=4000, label='What did the department supply?', widget=forms.Textarea(attrs={'rows': 3}))
    effort_state = forms.ChoiceField(label='Effort', choices=[('', 'Choose the supplied information'),
        ('known', 'Known person-days'), ('unknown', 'Unknown'), ('not_applicable', 'Not applicable')])
    person_days = forms.DecimalField(required=False, min_value=0, max_digits=12, decimal_places=3, label='Person-days, when known')

    def clean(self):
        values = super().clean()
        if (values.get('effort_state') == 'known') != (values.get('person_days') is not None):
            self.add_error('person_days', 'Enter an amount only when the supplied effort is known.')
        return values


class DepartmentReviewForm(forms.Form):
    packet_id = forms.IntegerField(min_value=1, widget=forms.HiddenInput)
    role = forms.ChoiceField(label='Review role', choices=[(role, role) for role in ROLES])
    disposition = forms.ChoiceField(label='Costing decision', choices=[('', 'Choose the evidenced decision'),
        ('retain_costing', 'Existing costing may be retained'), ('new_costing', 'Fresh costing and commercial approvals completed')])
    evidence_id = forms.IntegerField(min_value=1, label='Decision evidence reference')
    reason = forms.CharField(max_length=2000, label='Reason', widget=forms.Textarea(attrs={'rows': 3}))


class DepartmentRulesForm(forms.Form):
    base_configuration = forms.IntegerField(min_value=1, widget=forms.HiddenInput)
    required_departments = forms.MultipleChoiceField(label='Required department inputs', choices=[(name, name) for name in DEPARTMENTS], widget=forms.CheckboxSelectMultiple)
    effort_required_for = forms.MultipleChoiceField(required=False, label='Departments that must supply known effort', choices=[(name, name) for name in DEPARTMENTS], widget=forms.CheckboxSelectMultiple)
    recorder_roles = forms.MultipleChoiceField(label='Roles allowed to record inputs for readiness', choices=[(role, role) for role in ROLES])
    reviewer_roles = forms.MultipleChoiceField(label='Roles allowed to review changed effort', choices=[(role, role) for role in ROLES])
    allow_recorder_review = forms.ChoiceField(label='May the recorder review their own inputs?', choices=[('', 'Choose the recorded rule'), ('yes', 'Yes'), ('no', 'Require a separate reviewer')])
    changed_effort_action = forms.ChoiceField(label='When effort changes', choices=[('', 'Choose the recorded rule'),
        ('review_required', 'Require an evidenced costing decision'), ('fresh_costing_required', 'Require fresh costing and commercial approvals')])
    evidence_id = forms.IntegerField(min_value=1, label='Recorded owner decision reference')

    def clean(self):
        values = super().clean()
        if set(values.get('effort_required_for', [])) - set(values.get('required_departments', [])):
            self.add_error('effort_required_for', 'Choose from the required departments.')
        return values

    def save(self, actor, case):
        planning.proof(case, self.cleaned_data['evidence_id'], ['policy_decision'])
        configuration, current = planning.criteria(case)
        if configuration.pk != self.cleaned_data['base_configuration']:
            raise forms.ValidationError('The planning rules changed. Review their current version.')
        content = copy.deepcopy(current)
        content['department_inputs'] = {key: self.cleaned_data[key] for key in [
            'required_departments', 'effort_required_for', 'recorder_roles', 'reviewer_roles', 'changed_effort_action']}
        content['department_inputs']['allow_recorder_review'] = self.cleaned_data['allow_recorder_review'] == 'yes'
        return draft_operator_policy(actor, case.pk, COMPONENT, content, self.cleaned_data['evidence_id'], timezone.now())


def panels(actor, case, packet, projection, data=None, action=None):
    from apps.identity.services import require
    result = {'inputs': [], 'review': None, 'rules': None}
    if not projection:
        return result
    try:
        require(actor, case, 'planning.coordinate')
        may_record = True
    except PermissionDenied:
        may_record = False
    for row in projection['rows'] if may_record else []:
        old = row['record']
        initial = {'packet_id': packet.pk, 'department': row['department'],
            'previous_id': old['id'] if old else None}
        if old:
            initial.update({key: old[key] for key in ['summary', 'source_party', 'received_at', 'effort_state', 'person_days']})
            initial['received_at'] = parse_datetime(old['received_at'])
            initial['source_id'] = old['source']
        result['inputs'].append({'department': row['department'], 'form': DepartmentInputForm(
            data if action == 'department_input' and data.get('department') == row['department'] else None,
            initial=initial, auto_id='department_' + row['department'] + '_%s')})
    if projection['changed'] and may_record:
        result['review'] = DepartmentReviewForm(data if action == 'department_effort_review' else None,
            initial={'packet_id': packet.pk}, auto_id='department_review_%s')
    try:
        require(actor, case, 'policy.configure')
        configuration, current = planning.criteria(case)
    except (PermissionDenied, ValidationError):
        return result
    initial = dict(current.get('department_inputs', {}), base_configuration=configuration.pk)
    if 'allow_recorder_review' in initial:
        initial['allow_recorder_review'] = 'yes' if initial['allow_recorder_review'] else 'no'
    result['rules'] = DepartmentRulesForm(data if action == 'department_input_rules' else None,
        initial=initial, auto_id='department_rules_%s')
    return result

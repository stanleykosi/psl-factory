"""Prepare an evidenced project rule for the existing validation and activation steps."""
from django import forms
from django.core.exceptions import ValidationError
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render

from apps.core.evidence_access import public_evidence
from apps.core.models import Evidence
from apps.identity.services import require, visible_cases
from .registry import components
from .services import save_draft


TITLES = {
    'OPS.specialist_source_reading': 'Which source records background specialists may read with a model',
    'OPS.department_assistant_use': 'Which records a department assistant may use',
    'OPS.payroll_chat_totals': 'Which staff costs Zainab may show a report recipient',
    'OPS.winning_bid_reuse': 'Release a winning bid answer to another project',
    'D06.import_unit_conversion': 'Convert a Finance file supplied in thousands or millions',
}


@login_required
def settings(request, case_id):
    case = get_object_or_404(visible_cases(request.user), pk=case_id, kind='project')
    require(request.user, case, 'policy.configure')
    component = request.GET.get('rule', '')
    if component and component not in TITLES:
        raise Http404
    form = ProjectUseForm(request.user, case, component, request.POST if request.method == 'POST' else None) if component else None
    if request.method == 'POST' and form and form.is_valid():
        try:
            form.save(request.user)
        except ValidationError as exc:
            form.add_error(None, exc.messages[0])
        else:
            return redirect('policy', case.pk)
    response = render(request, 'project_use_settings.html', {'case': case, 'choices': TITLES.items(),
        'form': form, 'component': component, 'title': TITLES.get(component)})
    response['Cache-Control'] = 'no-store'
    return response

LABELS = {
    'entity': 'Reporting entity', 'period': 'Reporting month (YYYY-MM)', 'feed': 'Source feed',
    'sources': 'Records the model may receive', 'personas': 'Assistants', 'units': 'Units printed in the file',
    'fields': 'Figures the recipient may see', 'model': 'Exact approved OpenRouter model',
}


class ProjectUseForm(forms.Form):
    def __init__(self, actor, case, component, data=None):
        super().__init__(data)
        self.component = component
        self.case = case
        schema = components()[component]['value_schema']
        self.fixed = {}
        if component == 'OPS.winning_bid_reuse':
            from apps.pmo.models import RFPOutcome
            outcomes = RFPOutcome.objects.filter(submission__response__rfp__case=case, result='won').select_related(
                'submission__response__rfp')
            self.fields['answer'] = forms.ChoiceField(label='Submitted winning answer', choices=[
                (f'{outcome.pk}/{row["key"]}', f'{outcome.submission.response.rfp.reference} · {row["key"]} · Award {outcome.pk}')
                for outcome in outcomes for row in outcome.submission.response.matrix if row['disposition'] == 'addressed'])
            self.fields['destination'] = forms.ChoiceField(label='Receiving project', choices=[
                (str(pk), title) for pk, title in visible_cases(actor).filter(kind='project', tenant=case.tenant,
                    synthetic=case.synthetic).exclude(pk=case.pk).order_by('title').values_list('pk', 'title')])
        else:
            for key, spec in schema['properties'].items():
                if component == 'OPS.payroll_chat_totals' and key == 'fields':
                    self.fixed[key] = components()[component]['current_value']['fields']
                elif 'const' in spec:
                    self.fixed[key] = spec['const']
                elif component == 'OPS.specialist_source_reading' and key == 'processes':
                    from apps.agents.specialists import routes
                    self.fields[key] = forms.MultipleChoiceField(choices=[
                        (pid, f"{pid} · {route['original_title']}") for pid, route in routes().items()
                        if route['department'] != 'BaaS'])
                elif component == 'OPS.specialist_source_reading' and key == 'finance_import_checks':
                    self.fields[key] = forms.BooleanField(required=False,
                        label="Share trial-balance import checks with the assigned specialists",
                        help_text="Includes column checks, finding counts, validated currency and period, and the file total. Account rows stay private.")
                elif component == 'OPS.specialist_source_reading' and key == 'coordinate_specialists':
                    self.fields[key] = forms.BooleanField(required=False,
                        label="Allow the coordinator to route and check specialist work",
                        help_text="OpenRouter receives the selected source excerpts and related specialist findings to check this work.")
                elif spec['type'] == 'array':
                    self.fields[key] = forms.MultipleChoiceField(label=LABELS.get(key, key),
                        choices=[(item, item.replace('_', ' ').capitalize()) for item in spec['items']['enum']],
                        widget=forms.CheckboxSelectMultiple)
                else:
                    self.fields[key] = forms.CharField(label=LABELS.get(key, key.capitalize()), max_length=spec.get('maxLength', 180))
        self.fields['proof'] = forms.ModelChoiceField(label='Record of the owner’s decision',
            queryset=public_evidence(Evidence.objects.filter(case=case, kind='policy_decision')).order_by('-pk'))
        self.fields['effective'] = forms.DateTimeField(label='Effective from', widget=forms.DateTimeInput(attrs={'type':'datetime-local'}))

    def clean(self):
        values = super().clean()
        if self.component == 'OPS.specialist_source_reading' and values.get('processes') and values.get('roles'):
            from apps.agents.specialists import validate_selection
            validate_selection(values['processes'], values['roles'], values.get('source_kinds', ()),
                               coordinate=values.get('coordinate_specialists', False))
            if values.get('finance_import_checks') and (
                'F02' not in values['processes'] or 'native_station_projection' not in values.get('source_kinds', ())
            ):
                self.add_error('finance_import_checks', 'Select the trial-balance import and its department source projection.')
        return values

    def save(self, actor):
        data = self.cleaned_data.copy()
        if self.component == 'OPS.specialist_source_reading':
            for key in ('finance_import_checks', 'coordinate_specialists'):
                if not data.get(key):
                    data.pop(key, None)
        proof = 'evidence:' + str(data.pop('proof').pk)
        effective = data.pop('effective')
        value = {**self.fixed, **data}
        if self.component == 'OPS.winning_bid_reuse':
            outcome, requirement = data['answer'].split('/', 1)
            value = {'answers': [{'outcome_id': int(outcome), 'requirement': requirement, 'destination': data['destination']}]}
        component = components()[self.component]
        return save_draft(actor, self.case.pk, {
            'component_id': self.component, 'slot_id': component['parent_decision_id'], 'component_schema_ref': component['schema_ref'],
            'subject_scope': {'kind': 'project', 'ref': str(self.case.pk)}, 'schema_version':'1',
            'policy_revision': 1, 'lifecycle': 'draft', 'effective_from': effective.isoformat(), 'effective_until': None,
            'evidence_refs': [proof], 'human_decision_ref': proof, 'implementation_id': 'psl.reference-validation',
            'implementation_version':'1', 'reviewed_implementation_ref':'code:apps/policy/services.py#reference-validation-v1',
            'fixture_scope': 'synthetic_test' if self.case.synthetic else 'operational', 'value': value})

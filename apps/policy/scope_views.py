from django import forms
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.shortcuts import render, redirect, get_object_or_404
from apps.core.models import Case, Evidence
from .models import Configuration, ScopeVersion
from . import scopes


class ConfigurationChoice(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return f'#{obj.pk} · {obj.component} · local revision {obj.revision}'


class SourceForm(forms.Form):
    configuration = ConfigurationChoice(queryset=Configuration.objects.none())
    kind = forms.ChoiceField(choices=[(x, x) for x in ['organization','project','contract','service']])
    ref = forms.CharField(max_length=150, help_text='Exact tenant, case UUID or evidence:<recorded SOW ID>')
    binding_paths = forms.JSONField(initial=[], required=False, help_text='Explicit contextual scalar JSON pointers into the list of policy values; never executable rules')

    def clean_binding_paths(self):
        return self.cleaned_data['binding_paths'] if self.cleaned_data['binding_paths'] is not None else []

    def __init__(self, case, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['configuration'].queryset = Configuration.objects.filter(case=case).exclude(scope_source__isnull=False).exclude(scope_application__isnull=False)


class ApplyForm(forms.Form):
    source = forms.IntegerField(min_value=1, help_text='Explicit source version ID. Current read rights to its authority context are required.')
    decision = forms.ModelChoiceField(queryset=Evidence.objects.none())
    bindings = forms.JSONField(initial=[], required=False, help_text='List of {"path":"/0/field","value":...}; only source-authorized contextual leaves')

    def clean_bindings(self):
        return self.cleaned_data['bindings'] if self.cleaned_data['bindings'] is not None else []

    def __init__(self, case, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['decision'].queryset = Evidence.objects.filter(case=case, kind='policy_decision')


@login_required
def workbench(request, case_id):
    case = get_object_or_404(Case, pk=case_id)
    scopes.authorized(request.user, case, 'policy.read')
    source_form, apply_form, error = SourceForm(case), ApplyForm(case), None
    if request.method == 'POST':
        try:
            action = request.POST.get('action')
            if action == 'create':
                source_form = SourceForm(case, request.POST)
                if not source_form.is_valid():
                    raise ValidationError(source_form.errors.as_text())
                data = source_form.cleaned_data
                scopes.create(request.user, data['configuration'].pk, data['kind'], data['ref'], data['binding_paths'])
            elif action == 'apply':
                apply_form = ApplyForm(case, request.POST)
                if not apply_form.is_valid():
                    raise ValidationError(apply_form.errors.as_text())
                data = apply_form.cleaned_data
                scopes.apply(request.user, data['source'], case.pk, data['decision'].pk, data['bindings'])
            else:
                source = ScopeVersion.objects.get(pk=request.POST.get('source'), configuration__case=case)
                scopes.transition(request.user, source.pk, action)
            return redirect('policy_scopes', case_id=case.pk)
        except (ValidationError, ValueError, KeyError, ScopeVersion.DoesNotExist, Configuration.DoesNotExist) as exc:
            error = str(exc)
    return render(request, 'policy_scopes.html', dict(case=case, source_form=source_form, apply_form=apply_form,
        report=scopes.report(request.user, case.pk), error=error))


@login_required
def investigate(request, case_id):
    from apps.agents.policy_scope import investigate as inspect
    case = get_object_or_404(Case, pk=case_id)
    return render(request, 'policy_scope_investigation.html', {'case':case, 'report':inspect(request.user, case_id)})

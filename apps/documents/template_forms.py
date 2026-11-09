from django import forms
from apps.core.models import Evidence
from .contracts import TEMPLATE_SCHEMA, AUDIENCES
from .models import Template, TemplateScope


class SourceForm(forms.Form):
    body = forms.CharField(max_length=100000, widget=forms.Textarea(attrs={'rows': 3}), label='Exact owner source or decision content')
    locator = forms.CharField(max_length=500, label='Source reference (not an authority grant)')


class ScopeForm(forms.Form):
    document_type = forms.ChoiceField(choices=[(x, x.replace('_', ' ').title()) for x in TEMPLATE_SCHEMA['properties']['document_type']['enum'] if x != 'accepted_finance_metadata'])
    audience = forms.ChoiceField(choices=[(x, x.title()) for x in AUDIENCES])
    purpose = forms.CharField(max_length=160, label='Document purpose')
    context = forms.CharField(max_length=160, label='Exact applicability context, e.g. project SOW or a named contract')
    source_owner = forms.CharField(max_length=160, label='Source-owner reference, not a role appointment')
    evidence = forms.ModelChoiceField(queryset=Evidence.objects.none(), label='Scope source evidence')


class ClaimForm(forms.Form):
    scope = forms.ModelChoiceField(queryset=TemplateScope.objects.none())
    template = forms.ModelChoiceField(queryset=Template.objects.none(), label='Exact template version')
    evidence = forms.ModelChoiceField(queryset=Evidence.objects.none(), label='Source claiming this template is current')
    note = forms.CharField(max_length=4000, widget=forms.Textarea(attrs={'rows': 2}))
    confirm_owner = forms.BooleanField(required=False, label='I confirm this approved current template as the configured owner for this exact scope')


class OwnerPolicyForm(forms.Form):
    content = forms.JSONField(widget=forms.Textarea(attrs={'rows': 7}), label='Exact storage/v3 contract: permitted template IDs, retention days, repository and template_owners (scope_id/user_id)')
    evidence = forms.ModelChoiceField(queryset=Evidence.objects.none(), label='Actual policy-decision evidence')
    effective_from = forms.DateTimeField(label='Effective from, with timezone')

from django import forms
from apps.core.models import Evidence
from .forms import OffsetTimestamp
from apps.policy.change_drafts import SCHEMAS


class StandardPolicyForm(forms.Form):
    component = forms.ChoiceField(choices=[(k, k) for k in SCHEMAS if k!='D01.emergency_glpi_relationship'])
    value = forms.JSONField(widget=forms.Textarea(attrs={'rows': 6}),
        help_text='Catalogue: array of entry objects. Gate map: {"standard": [{"catalogue_key": "owner-key", "roles": ["Product", "Engineering"]}]}. No default is installed.')
    evidence = forms.ModelChoiceField(queryset=Evidence.objects.none(), label='Owner policy decision evidence')
    effective_from = OffsetTimestamp(label='Effective from with offset')

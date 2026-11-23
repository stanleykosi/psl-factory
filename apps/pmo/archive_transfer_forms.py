from django import forms
from django.core.exceptions import PermissionDenied
from django.utils import timezone

from apps.core.evidence_access import public_evidence
from apps.identity.services import require
from apps.policy.archive_transfer_validators import COMPONENT
from apps.policy.operator_drafts import draft_operator_policy


class ArchiveSelectionForm(forms.Form):
    sources = forms.MultipleChoiceField(label='Source documents to archive', choices=[],
        widget=forms.CheckboxSelectMultiple)

    def __init__(self, case, *args, selected=(), **kwargs):
        super().__init__(*args, **kwargs)
        query = public_evidence(case.evidence.all()).only('pk', 'kind', 'version')
        required = list(query.filter(pk__in=selected).order_by('pk'))
        sources = required + list(query.exclude(pk__in=selected).order_by('-pk')[:501 - len(required)])
        self.limited = len(sources) > 500
        self.fields['sources'].choices = [(str(source.pk), f'{source.kind.replace("_", " ").capitalize()} · version {source.version} · {source.pk}')
                                         for source in sources[:500]]
        self.fields['sources'].initial = [str(pk) for pk in selected]


class ArchiveRulesForm(forms.Form):
    adapter = forms.ChoiceField(label='Archive store', choices=[('', 'Choose the reviewed store'),
        ('private_object_store/v1', 'Configured private file store'), ('synthetic_archive/v1', 'Synthetic acceptance store')])
    operator_id = forms.IntegerField(min_value=1, label='Designated archive operator account reference')
    max_files = forms.IntegerField(min_value=1, max_value=500, label='Maximum files per archive')
    max_bytes = forms.IntegerField(min_value=1, max_value=52428800, label='Maximum total bytes')
    lease_seconds = forms.IntegerField(min_value=10, max_value=300, label='Worker reservation in seconds')
    evidence_id = forms.IntegerField(min_value=1, label='Recorded owner decision reference')

    def save(self, actor, case):
        from django.core.exceptions import ValidationError

        require(actor, case, 'policy.configure')
        values = self.cleaned_data
        if not public_evidence(case.evidence.filter(pk=values['evidence_id'], kind='policy_decision')).exists():
            raise ValidationError('Choose this project recorded owner decision.')
        return draft_operator_policy(actor, case.pk, COMPONENT,
            {key: values[key] for key in ['adapter', 'operator_id', 'max_files', 'max_bytes', 'lease_seconds']},
            values['evidence_id'], timezone.now())


def panels(actor, work, state, data=None, action=None):
    selected = list(state['data']['inventory'].values())
    try:
        from .archive_transfer import access
        access(actor, work.case)
        require(actor, work.case, 'factory.manage')
        selection = ArchiveSelectionForm(work.case, data if action == 'archive_files' else None, selected=selected)
    except PermissionDenied:
        selection = None
    try:
        require(actor, work.case, 'policy.configure')
        rules = ArchiveRulesForm(data if action == 'archive_file_rules' else None)
    except PermissionDenied:
        rules = None
    return selection, rules

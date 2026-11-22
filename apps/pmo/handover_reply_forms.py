from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.core.evidence_access import public_evidence
from apps.policy.document_validators import ROLES
from apps.policy.handover_reply_validators import COMPONENT, CHANNELS
from apps.policy.operator_drafts import draft_operator_policy


class ReplyRulesForm(forms.Form):
    recorder_roles = forms.MultipleChoiceField(label='Who may record Support replies',
        choices=[(role, role) for role in ROLES], widget=forms.CheckboxSelectMultiple)
    channels = forms.MultipleChoiceField(label='Accepted reply channels',
        choices=[(channel, channel.replace('_', ' ').capitalize()) for channel in CHANNELS],
        widget=forms.CheckboxSelectMultiple)
    evidence_id = forms.IntegerField(min_value=1, label='Recorded owner decision reference')

    def save(self, actor, case):
        data = self.cleaned_data
        if not public_evidence(case.evidence.filter(pk=data['evidence_id'], kind='policy_decision')).exists():
            raise ValidationError('Choose this project recorded owner decision.')
        return draft_operator_policy(actor, case.pk, COMPONENT,
            {key: data[key] for key in ['recorder_roles', 'channels']}, data['evidence_id'], timezone.now())

from hashlib import sha256

from django import forms
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.core.evidence_access import public_evidence
from apps.core.templatetags.studio_ui import role_name
from apps.identity.models import Grant
from apps.policy.document_validators import ROLES
from apps.policy.issue_team_validators import CHANNELS


class TeamRulesForm(forms.Form):
    recorder_roles = forms.MultipleChoiceField(label='Roles allowed to record team replies',
        choices=[(role, role_name(role)) for role in ROLES], widget=forms.CheckboxSelectMultiple)
    teams = forms.CharField(label='External teams', max_length=4000,
        help_text='One team name per line.', widget=forms.Textarea(attrs={'rows': 5}))
    channels = forms.MultipleChoiceField(label='Accepted reply channels',
        choices=[(channel, channel.capitalize()) for channel in CHANNELS], widget=forms.CheckboxSelectMultiple)
    resolution_recorder_roles = forms.MultipleChoiceField(label='Roles allowed to record team resolutions',
        required=False, choices=[(role, role_name(role)) for role in ROLES], widget=forms.CheckboxSelectMultiple,
        help_text='Leave empty until decided. Acknowledgement and progress remain available.')
    acknowledgement_clock = forms.ChoiceField(label='Time used to assess acknowledgement', required=False,
        choices=[('', 'Awaiting owner decision'), ('recorded_at', 'When recorded in the factory'),
                 ('human_attested_source_time', 'Actual reply time recorded with source evidence')])
    evidence = forms.ChoiceField(label='Decision evidence')
    revision = forms.IntegerField(min_value=1, widget=forms.HiddenInput)

    def __init__(self, *args, existing_teams=(), **kwargs):
        super().__init__(*args, **kwargs)
        self.existing_keys = {team['label']: team['key'] for team in existing_teams}

    def clean_teams(self):
        labels = [label.strip() for label in self.cleaned_data['teams'].splitlines() if label.strip()]
        if not 1 <= len(labels) <= 40 or len(set(labels)) != len(labels) or any(len(label) > 100 for label in labels):
            raise forms.ValidationError('Provide up to forty distinct team names, each within one hundred characters.')
        return [{'key': self.existing_keys.get(label, 'team-' + sha256(label.encode()).hexdigest()[:24]),
                 'label': label} for label in labels]


class TeamAssignmentForm(forms.Form):
    mode = forms.ChoiceField(label='Issue owner', choices=[('internal', 'Person with a factory account'),
                                                        ('team', 'Team without a factory account')])
    team_key = forms.ChoiceField(label='External team', required=False)
    recorder = forms.ModelChoiceField(label='Follow-up coordinator', queryset=get_user_model().objects.none())
    recorder_role = forms.ChoiceField(label='Coordinator role for external replies', required=False)
    evidence = forms.ChoiceField(label='Supporting evidence')
    reason = forms.CharField(label='Reason for assignment', max_length=2000, widget=forms.Textarea(attrs={'rows': 3}))
    state = forms.IntegerField(min_value=1, widget=forms.HiddenInput)
    revision = forms.IntegerField(min_value=1, widget=forms.HiddenInput)
    work = forms.IntegerField(min_value=1, required=False, widget=forms.HiddenInput)
    source = forms.IntegerField(min_value=1, required=False, widget=forms.HiddenInput)

    def __init__(self, case, issue, assignment, value, data=None, *, work=None):
        initial = {'state': issue.current_id, 'revision': case.revision,
                   'mode': assignment.mode if assignment else 'internal',
                   'recorder': issue.current.owner_id,
                   'team_key': assignment.team_key if assignment else '',
                   'recorder_role': assignment.recorder_role if assignment else ''}
        if work is not None:
            initial.update(work=work.pk, source=work.source_head_id)
        super().__init__(data, initial=initial)
        owners = Grant.objects.filter(case=case, active=True, action='issue.own').values('user_id')
        self.fields['recorder'].queryset = get_user_model().objects.filter(is_active=True, pk__in=owners).order_by('username')
        self.fields['recorder'].label_from_instance = lambda user: user.get_full_name() or user.username
        self.fields['team_key'].choices = [('', 'Owner not yet assigned')] + [
            (team['key'], team['label']) for team in value.get('teams', [])]
        self.fields['recorder_role'].choices = [('', 'Choose a recorder role')] + [
            (role, role_name(role)) for role in value.get('recorder_roles', [])]
        self.fields['evidence'].choices = evidence_choices(case)


class TeamReplyForm(forms.Form):
    operation = forms.ChoiceField(label='Update type', choices=[('acknowledge', 'Acknowledge'),
        ('start', 'Started'), ('progress', 'Progress update')])
    party = forms.CharField(label='Who replied', max_length=200)
    channel = forms.ChoiceField(label='Reply channel')
    responded_at = forms.DateTimeField(label='Actual reply time',
        help_text='Use when the team actually replied.',
        widget=forms.DateTimeInput(format='%Y-%m-%dT%H:%M:%S', attrs={'type': 'datetime-local', 'step': 1}))
    source_ref = forms.CharField(label='Source reference', max_length=240)
    evidence = forms.ChoiceField(label='Supporting evidence')
    note = forms.CharField(label='Owner update', max_length=4000, widget=forms.Textarea(attrs={'rows': 4}))
    next_action = forms.CharField(label='Next action', max_length=1000)
    assignment_id = forms.IntegerField(min_value=1, widget=forms.HiddenInput)
    operation_key = forms.UUIDField(widget=forms.HiddenInput)
    revision = forms.IntegerField(min_value=1, widget=forms.HiddenInput)
    case_revision = forms.IntegerField(min_value=1, widget=forms.HiddenInput)
    task = forms.IntegerField(min_value=1, widget=forms.HiddenInput)
    task_revision = forms.IntegerField(min_value=1, widget=forms.HiddenInput)

    def __init__(self, work, team, task, data=None, *, acknowledged=False):
        from uuid import uuid4

        super().__init__(data, initial={'assignment_id': team['assignment'].pk, 'operation_key': uuid4(),
            'revision': work.revision, 'case_revision': work.case.revision,
            'task': task.pk, 'task_revision': task.revision})
        self.fields['channel'].choices = [(channel, channel.capitalize()) for channel in team['channels']]
        self.fields['operation'].choices = [('start', 'Started'), ('progress', 'Progress update')] if acknowledged else [
            ('acknowledge', 'Acknowledge')]
        self.fields['responded_at'].help_text += ' Time zone '+timezone.get_current_timezone_name()+'.'
        self.fields['evidence'].choices = evidence_choices(work.case)


def evidence_choices(case, *, kind=None):
    records = public_evidence(case.evidence.all())
    if kind:
        records = records.filter(kind=kind)
    return [(record.pk, str(record)) for record in records.defer('body').order_by('-pk')[:50]]


class TeamResolutionForm(forms.Form):
    party = forms.CharField(label='Who confirmed the fix', max_length=200)
    channel = forms.ChoiceField(label='Reply channel')
    responded_at = forms.DateTimeField(label='Actual reply time',
        widget=forms.DateTimeInput(format='%Y-%m-%dT%H:%M:%S', attrs={'type':'datetime-local', 'step':1}))
    source_ref = forms.CharField(label='Source reference', max_length=240)
    evidence = forms.ChoiceField(label='Reply evidence')
    fix = forms.ChoiceField(label='Documented fix')
    root_cause = forms.ChoiceField(label='Root cause', required=False,
                                  help_text='Required for a critical issue.')
    resolution_role = forms.ChoiceField(label='Your resolution recorder role')
    note = forms.CharField(label='Resolution summary', max_length=4000, widget=forms.Textarea(attrs={'rows':4}))
    next_action = forms.CharField(label='Next action', max_length=1000)
    state = forms.IntegerField(min_value=1, widget=forms.HiddenInput)
    assignment = forms.IntegerField(min_value=1, widget=forms.HiddenInput)
    revision = forms.IntegerField(min_value=1, widget=forms.HiddenInput)
    operation_key = forms.UUIDField(widget=forms.HiddenInput)

    def __init__(self, case, issue, assignment, value, data=None):
        from uuid import uuid4
        super().__init__(data, initial={'state':issue.current_id, 'assignment':assignment.pk,
            'revision':case.revision, 'operation_key':uuid4()})
        self.fields['responded_at'].help_text = 'Time zone '+timezone.get_current_timezone_name()+'.'
        self.fields['channel'].choices = [(v, v.capitalize()) for v in value['channels']]
        self.fields['resolution_role'].choices = [(r, role_name(r)) for r in value.get('resolution_recorder_roles', [])]
        self.fields['evidence'].choices = evidence_choices(case)
        self.fields['fix'].choices = evidence_choices(case, kind='resolution')
        self.fields['root_cause'].choices = [('', 'No root cause selected')] + evidence_choices(case, kind='root_cause')

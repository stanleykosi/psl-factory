from django import forms
from django.contrib.auth import get_user_model
from apps.core.models import Evidence
from apps.documents.models import Template
from .models import Meeting, ActionItem
from .clocks import aware, REPORT_KINDS
from .meetings import MEETING_KINDS

class OffsetTimestamp(forms.CharField):
    def clean(self,value):
        value=super().clean(value)
        return aware(value) if value else None

class MeetingForm(forms.Form):
    reference=forms.CharField(max_length=160)
    kind=forms.ChoiceField(choices=[(k,k.title()) for k in MEETING_KINDS])
    occurred_at=OffsetTimestamp(label='Meeting time (ISO timestamp with offset)',help_text='For example 2026-10-20T09:00:00+01:00. No timezone is guessed.')
    purpose=forms.CharField(max_length=240)
    summary=forms.CharField(max_length=16000,widget=forms.Textarea(attrs={'rows':3}))
    participants=forms.ModelMultipleChoiceField(queryset=get_user_model().objects.none(),required=False)
    decisions=forms.JSONField(required=False,widget=forms.Textarea(attrs={'rows':3}),help_text='List of {"text":"...","evidence_id":1}; optional change_evidence_id links a change request without approving it.')
    evidence=forms.ModelChoiceField(queryset=Evidence.objects.none())
    meeting_id=forms.IntegerField(required=False,min_value=1,label='Meeting ID for a new revision')

class ActionForm(forms.Form):
    reference=forms.CharField(max_length=160)
    description=forms.CharField(max_length=1000)
    meeting=forms.ModelChoiceField(queryset=Meeting.objects.none(),required=False)
    owner=forms.ModelChoiceField(queryset=get_user_model().objects.none(),required=False)
    due_at=OffsetTimestamp(required=False,label='Explicit deadline with offset (leave blank if unknown)')
    calculated=forms.BooleanField(required=False,label='Calculate using configured action clock policy instead')
    evidence=forms.ModelChoiceField(queryset=Evidence.objects.none())
    change_evidence=forms.ModelChoiceField(queryset=Evidence.objects.none(),required=False)
    reason=forms.CharField(max_length=4000,widget=forms.Textarea(attrs={'rows':2}))

class DraftMinutesForm(forms.Form):
    meeting=forms.ModelChoiceField(queryset=Meeting.objects.none())
    template=forms.ModelChoiceField(queryset=Template.objects.none())
    audience=forms.ChoiceField(choices=[(v,v.title()) for v in ['internal','client','management']])

class ReportForm(forms.Form):
    kind=forms.ChoiceField(choices=[(v,v.replace('_',' ').title()) for v in REPORT_KINDS])
    start_at=OffsetTimestamp(label='Period start with offset')
    end_at=OffsetTimestamp(label='Period end with offset (exclusive)')
    template=forms.ModelChoiceField(queryset=Template.objects.none())
    audience=forms.ChoiceField(choices=[(v,v.title()) for v in ['internal','client','management']])

class ClockPolicyForm(forms.Form):
    component=forms.ChoiceField(choices=[(v,v) for v in ['D04.iana_timezone','D04.working_calendar_ref','D04.clock_anchor_pause_rules','D04.deadline_parameters']])
    value=forms.JSONField(widget=forms.Textarea(attrs={'rows':5}),help_text='Actual owner-supplied value; no business calendar or deadline defaults are installed.')
    evidence=forms.ModelChoiceField(queryset=Evidence.objects.none(),label='Owner policy decision evidence')
    effective_from=OffsetTimestamp(label='Effective from (with offset)')

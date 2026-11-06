from django import forms
from django.db.models import F
from apps.core.models import Evidence
from apps.policy.document_validators import ROLES
from .models import ChangeVersion,DeliveryCandidate,EmergencyProfile,EmergencyAuthorization,EmergencyOutcome
from .forms import OffsetTimestamp


class EvidenceNoteForm(forms.Form):
    evidence=forms.ModelChoiceField(queryset=Evidence.objects.none())
    note=forms.CharField(max_length=4000,widget=forms.Textarea(attrs={'rows':2}))
    def __init__(self,*args,case,**kwargs):
        super().__init__(*args,**kwargs);self.fields['evidence'].queryset=case.evidence.all()


class ProfileForm(EvidenceNoteForm):
    version=forms.ModelChoiceField(queryset=ChangeVersion.objects.none())
    candidate=forms.ModelChoiceField(queryset=DeliveryCandidate.objects.none())
    critical_production=forms.NullBooleanField(required=False,label='Confirmed critical production applicability')
    p1=forms.NullBooleanField(required=False,label='Explicit incident P1 classification (unknown stays unknown)')
    def __init__(self,*args,case,**kwargs):
        super().__init__(*args,case=case,**kwargs)
        self.fields['version'].queryset=ChangeVersion.objects.filter(change__case=case,category='Emergency',change__current_id=F('pk'))
        self.fields['candidate'].queryset=DeliveryCandidate.objects.filter(case=case)
        self.fields['evidence'].queryset=case.evidence.filter(kind='incident_classification')


class PreauthorizationForm(EvidenceNoteForm):
    profile=forms.ModelChoiceField(queryset=EmergencyProfile.objects.none())
    role=forms.ChoiceField(choices=[(r,r) for r in ['Incident Lead','Engineering Lead','CTO']+['GLPI exception:'+r for r in ROLES]])
    authority_role=forms.ChoiceField(choices=[('Security Lead','Security Lead (Incident Lead capacity)'),('Engineering Lead','Engineering Lead (Incident Lead capacity)')],required=False)
    verdict=forms.ChoiceField(choices=[(v,v.title()) for v in ['approve','return','reject']])
    def __init__(self,*args,case,**kwargs):
        super().__init__(*args,case=case,**kwargs)
        self.fields['profile'].queryset=EmergencyProfile.objects.filter(version__change__case=case)
        self.fields['evidence'].queryset=case.evidence.filter(kind='emergency_decision')


class OutcomeForm(EvidenceNoteForm):
    profile=forms.ModelChoiceField(queryset=EmergencyProfile.objects.none())
    authorization=forms.ModelChoiceField(queryset=EmergencyAuthorization.objects.none(),required=False,label='Recorded preauthorization (leave unknown if absent)')
    implemented_at=OffsetTimestamp(label='Actual implementation time with offset; log capture time is recorded by the server')
    def __init__(self,*args,case,**kwargs):
        super().__init__(*args,case=case,**kwargs)
        self.fields['profile'].queryset=EmergencyProfile.objects.filter(version__change__case=case)
        self.fields['authorization'].queryset=EmergencyAuthorization.objects.filter(profile__version__change__case=case)
        self.fields['evidence'].queryset=case.evidence.filter(kind='change_implementation')


class EmergencyPolicyForm(forms.Form):
    component=forms.ChoiceField(choices=[(v,v) for v in ['D01.emergency_glpi_relationship','D01.satisfied_gate_map',
        'D04.iana_timezone','D04.working_calendar_ref','D04.clock_anchor_pause_rules','D04.deadline_parameters']])
    value=forms.JSONField(widget=forms.Textarea(attrs={'rows':6}))
    evidence=forms.ModelChoiceField(queryset=Evidence.objects.none(),label='Owner policy decision evidence')
    effective_from=OffsetTimestamp(label='Effective from with offset')

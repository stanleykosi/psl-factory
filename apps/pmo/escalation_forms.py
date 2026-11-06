from django import forms
from django.db.models import F
from apps.core.models import Evidence
from .models import IssueState, EscalationProfile
from .forms import OffsetTimestamp

class ProfileForm(forms.Form):
    state=forms.ModelChoiceField(queryset=IssueState.objects.none(),label='Current issue state')
    classification=forms.ChoiceField(choices=[('unclassified','Unclassified'),('internal','Internal'),('client_dependent','Client dependent')])
    timeline_impact=forms.NullBooleanField(required=False,label='Delivery timeline impact')
    trigger_at=OffsetTimestamp(required=False,label='Actual trigger timestamp with offset (leave blank if unknown)')
    evidence=forms.ModelChoiceField(queryset=Evidence.objects.none())
    note=forms.CharField(max_length=4000,widget=forms.Textarea(attrs={'rows':2}))
    def __init__(self,*args,case,**kwargs):
        super().__init__(*args,**kwargs)
        self.fields['state'].queryset=IssueState.objects.filter(issue__case=case,issue__current_id=F('pk')).select_related('issue')
        self.fields['evidence'].queryset=case.evidence.all()

class RequestForm(forms.Form):
    profile=forms.ModelChoiceField(queryset=EscalationProfile.objects.none())
    direction=forms.ChoiceField(choices=[('escalate','Escalate'),('de_escalate','De-escalate')])
    target=forms.ChoiceField(choices=[(v,v) for v in ['Client','PMO','CTO']])
    evidence=forms.ModelChoiceField(queryset=Evidence.objects.none())
    note=forms.CharField(max_length=4000,widget=forms.Textarea(attrs={'rows':2}),label='Communication next steps and rationale')
    def __init__(self,*args,case,**kwargs):
        super().__init__(*args,**kwargs)
        self.fields['profile'].queryset=EscalationProfile.objects.filter(state__issue__case=case,state__issue__current_id=F('state_id')).order_by('state__issue_id','-pk').distinct('state__issue_id')
        self.fields['evidence'].queryset=case.evidence.all()

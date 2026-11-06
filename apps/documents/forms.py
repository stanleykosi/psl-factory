from django import forms
from apps.core.models import Evidence
from .models import Template, Version

class TemplateForm(forms.Form):
    name=forms.CharField(max_length=160)
    definition=forms.JSONField(widget=forms.Textarea(attrs={'rows':6}),initial={
        'document_type':'status_report','required_fields':['executive_summary','status'],
        'audience_fields':{'client':['executive_summary','status','next_steps'],'internal':['executive_summary','status','next_steps','internal_notes']}})
    evidence=forms.ModelChoiceField(queryset=Evidence.objects.none(),label='Template owner evidence')

class DraftForm(forms.Form):
    template=forms.ModelChoiceField(queryset=Template.objects.none())
    title=forms.CharField(max_length=240)
    audience=forms.ChoiceField(choices=[(a,a.title()) for a in ['internal','client','management']])
    fields=forms.JSONField(widget=forms.Textarea(attrs={'rows':7}),required=False,label='Sections and evidence references')
    sources=forms.ModelMultipleChoiceField(queryset=Evidence.objects.none(),required=False,label='Agent source evidence')
    document_id=forms.IntegerField(required=False,min_value=1,label='Existing document ID (for a new revision)')

class ReviewForm(forms.Form):
    version=forms.ModelChoiceField(queryset=Version.objects.none())
    verdict=forms.ChoiceField(choices=[('approve','Approve'),('return','Return for revision'),('reject','Reject')])
    note=forms.CharField(max_length=4000,widget=forms.Textarea(attrs={'rows':2}))
    delegated=forms.BooleanField(required=False,label='Use a configured human delegation')


from apps.pmo.models import DeliveryCandidate
from apps.pmo.gates import GATE_OWNERS

class CandidateForm(forms.Form):
    reference=forms.CharField(max_length=160,label='Candidate/build reference')
    requirements=forms.ModelChoiceField(queryset=Evidence.objects.none())

class GateForm(forms.Form):
    candidate=forms.ModelChoiceField(queryset=DeliveryCandidate.objects.none())
    kind=forms.ChoiceField(choices=[(key,key.replace('_',' ').title()+' · '+owner) for key,owner in GATE_OWNERS.items()])
    external_ref=forms.CharField(max_length=240,label='Authoritative source reference')
    evidence=forms.ModelChoiceField(queryset=Evidence.objects.none())

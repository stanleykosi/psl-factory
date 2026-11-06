from django import forms
from apps.core.models import Evidence
from .commercial import SOURCE_KINDS, ROLES


class ProposalForm(forms.Form):
    context=forms.ModelChoiceField(queryset=Evidence.objects.none())
    reason=forms.CharField(max_length=4000,widget=forms.Textarea(attrs={'rows':2}))
    reuse=forms.BooleanField(required=False,label='Request configured reuse of unchanged-subject decisions')
    def __init__(self,*args,case,**kwargs):
        super().__init__(*args,**kwargs)
        self.fields['context'].queryset=case.evidence.filter(kind__in=['requirements','client_feedback','change_request'])
        for kind in SOURCE_KINDS:
            self.fields[kind]=forms.ModelChoiceField(queryset=case.evidence.filter(kind=kind))


class CommercialDecisionForm(forms.Form):
    role=forms.ChoiceField(choices=[(v,v) for v in ROLES])
    verdict=forms.ChoiceField(choices=[(v,v.title()) for v in ['approve','return','reject','withdraw']])
    note=forms.CharField(max_length=4000,widget=forms.Textarea(attrs={'rows':2}))
    delegated=forms.BooleanField(required=False,label='Use configured delegated authority')

from django import forms
from django.core.exceptions import ValidationError,PermissionDenied
from apps.pmo.forms import OffsetTimestamp
from apps.core.evidence_access import public_evidence
from .reviewer_availability import source

class ReviewerAvailabilityForm(forms.Form):
    principal=forms.ModelChoiceField(queryset=None,label='Reviewer')
    status=forms.ChoiceField(required=False,label='Availability during this window',choices=[('','Not confirmed'),('available','Available'),('unavailable','Unavailable')])
    valid_from=OffsetTimestamp(label='Window starts (include timezone)')
    valid_until=OffsetTimestamp(label='Window ends (include timezone)')
    evidence=forms.ModelChoiceField(queryset=None,label='Recorded availability decision')
    effective_from=OffsetTimestamp(label='Configuration effective from (include timezone)')
    source_configuration=forms.IntegerField(required=False,min_value=1,widget=forms.HiddenInput)
    replacement=forms.ChoiceField(required=False,choices=[],label='Availability window to update')

    def __init__(self,actor,case,*args,**kwargs):
        super().__init__(*args,**kwargs);self.source_available=True;self.current_records=[]
        from django.contrib.auth import get_user_model
        from apps.finance.billing import digest
        users=get_user_model().objects.filter(is_active=True,grant__case=case,grant__active=True,grant__action='case.read').distinct().order_by('username')
        self.fields['principal'].queryset=users;self.fields['principal'].label_from_instance=lambda u:u.get_full_name() or u.username
        self.fields['evidence'].queryset=public_evidence(case.evidence.filter(kind='policy_decision'))
        try:config,value=source(actor,case)
        except (ValidationError,PermissionDenied):self.source_available=False;config=None;value={'records':[]}
        self.initial['source_configuration']=config.pk if config else None
        names={u.pk:u.get_full_name() or u.username for u in users};choices=[('','Add a new availability window')]
        for record in value['records']:
            name=names.get(record['principal_id'],'Unavailable person');status={'available':'Available','unavailable':'Unavailable',None:'Not confirmed'}[record['status']]
            choices.append((digest(record),f"{name} · {status} · {record['valid_from']}"))
            self.current_records.append({'name':name,'status':status,'valid_from':record['valid_from'],'valid_until':record['valid_until']})
        self.fields['replacement'].choices=choices

    def clean(self):
        value=super().clean()
        if not self.source_available:raise forms.ValidationError('Current availability source is unavailable to this account')
        if value.get('valid_from') and value.get('valid_until') and value['valid_from']>=value['valid_until']:
            raise forms.ValidationError('Window must end after it starts')
        return value

    def record(self):
        v=self.cleaned_data
        return {'principal_id':v['principal'].pk,'status':v['status'] or None,'valid_from':v['valid_from'].isoformat(),'valid_until':v['valid_until'].isoformat()}

from django import forms
from apps.core.evidence_access import public_evidence
from apps.pmo.forms import OffsetTimestamp


class RoleAssignmentsForm(forms.Form):
    assignments=forms.JSONField(widget=forms.Textarea(attrs={'rows':10}),label='Exact role assignments and optional explicit eligibility bundles')
    evidence=forms.ModelChoiceField(queryset=None,label='Owner decision evidence')
    effective_from=OffsetTimestamp(label='Configuration effective from (explicit offset)')

    def __init__(self,case,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.fields['evidence'].queryset=public_evidence(case.evidence.filter(kind='policy_decision'))


class DelegationsForm(RoleAssignmentsForm):
    delegations=forms.JSONField(widget=forms.Textarea(attrs={'rows':10}),label='Exact scoped delegations and optional delegated bundle eligibility')

    def __init__(self,case,*args,**kwargs):
        super().__init__(case,*args,**kwargs);self.fields.pop('assignments')


class InvoiceDelegationForm(forms.Form):
    principal=forms.ModelChoiceField(queryset=None,label='Person delegating Finance authority')
    delegate=forms.ModelChoiceField(queryset=None,label='Person receiving delegated authority')
    valid_from=OffsetTimestamp(label='Delegation starts (include timezone)')
    valid_until=OffsetTimestamp(label='Delegation ends (include timezone)')
    eligibility_roles=forms.MultipleChoiceField(choices=[],label='Exact qualified role bundle, including Finance')
    eligibility_from=OffsetTimestamp(label='Role qualification starts (include timezone)')
    eligibility_until=OffsetTimestamp(label='Role qualification ends (include timezone)')
    actions=forms.MultipleChoiceField(required=False,choices=[('approve','Approve'),('return','Return for correction'),('reject','Reject')],label='Permitted invoice decisions')
    currency=forms.CharField(required=False,max_length=3,label='Invoice currency',help_text='Leave unknown values blank. No currency conversion is inferred.')
    maximum_amount=forms.CharField(required=False,max_length=40,label='Maximum gross invoice amount',help_text='Exact decimal text. A blank limit does not grant financial authority.')
    evidence=forms.ModelChoiceField(queryset=None,label='Recorded owner decision')
    effective_from=OffsetTimestamp(label='Configuration effective from (include timezone)')
    source_configuration=forms.IntegerField(required=False,widget=forms.HiddenInput)
    replacement=forms.ChoiceField(required=False,choices=[],label='Delegation to update')

    def __init__(self,actor,case,*args,**kwargs):
        super().__init__(*args,**kwargs);self.case=case;self.source_available=True;self.current_scopes=[]
        from django.contrib.auth import get_user_model
        from django.core.exceptions import ValidationError,PermissionDenied
        from .document_validators import ROLES
        from .role_assignments import invoice_delegation_source
        from apps.finance.billing import digest
        users=get_user_model().objects.filter(is_active=True,grant__case=case,grant__active=True,grant__action='case.read').distinct().order_by('username')
        for key in ['principal','delegate']:
            self.fields[key].queryset=users;self.fields[key].label_from_instance=lambda u:u.get_full_name() or u.username
        self.fields['eligibility_roles'].choices=[(role,role) for role in ROLES]
        self.fields['evidence'].queryset=public_evidence(case.evidence.filter(kind='policy_decision'))
        choices=[('','Add a new invoice delegation')]
        try:config,records=invoice_delegation_source(actor,case)
        except (ValidationError,PermissionDenied):self.source_available=False;config=None;records=[]
        self.initial['source_configuration']=config.pk if config else None
        names={u.pk:u.get_full_name() or u.username for u in users}
        for record in records:
            scope=record.get('decision_scope',{})
            if scope.get('decision_type')=='finance.invoice.review' and scope.get('case_ref')==str(case.pk):
                choices.append((digest(record),f"{names.get(record['principal_id'],'Unavailable person')} → {names.get(record['delegate_id'],'Unavailable person')} · {scope.get('currency') or 'currency unknown'} · {scope.get('maximum_amount') or 'limit unknown'}"))
                self.current_scopes.append({'principal':names.get(record['principal_id'],'Unavailable person'),
                    'delegate':names.get(record['delegate_id'],'Unavailable person'),'currency':scope['currency'],
                    'maximum_amount':scope['maximum_amount'],'actions':[{'approve':'Approve','return':'Return for correction','reject':'Reject'}[a] for a in scope['actions']] if scope['actions'] is not None else None,
                    'valid_from':record['valid_from'],'valid_until':record['valid_until'],
                    'eligibility_roles':record['delegate_eligibility']['roles']})
        self.fields['replacement'].choices=choices

    def clean(self):
        data=super().clean()
        if not self.source_available:raise forms.ValidationError('Current delegation source is unavailable to this account; review its source access first')
        return data

    def record(self):
        d=self.cleaned_data
        return {'role':'Finance','principal_id':d['principal'].pk,'delegate_id':d['delegate'].pk,
            'valid_from':d['valid_from'].isoformat(),'valid_until':d['valid_until'].isoformat(),
            'delegate_eligibility':{'roles':d['eligibility_roles'],'valid_from':d['eligibility_from'].isoformat(),'valid_until':d['eligibility_until'].isoformat()},
            'decision_scope':{'decision_type':'finance.invoice.review','case_ref':str(self.case.pk),'actions':d['actions'] or None,
                'currency':d['currency'] or None,'maximum_amount':d['maximum_amount'] or None}}

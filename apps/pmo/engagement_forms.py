"""Bounded metadata selectors and plain-language registration controls."""
from uuid import uuid4
from django import forms
from django.db.models import Q
from django.utils import timezone
from apps.core.models import Evidence,ClientContactRevision
from apps.core.evidence_access import public_evidence
from apps.core.templatetags.studio_ui import role_name
from apps.policy.document_validators import ROLES
from .engagement_models import EngagementDetails

PROOFS=['engagement_source','engagement_assignment','engagement_registration','product_input','rfp_outcome','plan']


def bounded(query,selected=None,limit=50):
    ids=query.order_by('-pk').values('pk')[:limit]
    try:
        chosen=int(selected)
        if not 0<chosen<=9223372036854775807:chosen=None
    except (TypeError,ValueError):chosen=None
    return query.filter(Q(pk__in=ids)|Q(pk=chosen)).order_by('-pk')


def evidence_field(case,data=None,name='evidence_id',kinds=None,initial=None):
    query=public_evidence(case.evidence.filter(kind__in=kinds or PROOFS)).defer('body')
    return forms.ModelChoiceField(bounded(query,data.get(name) if data else initial),
        initial=initial,label='Planning document' if name=='plan_id' else 'Supporting document')


def details_field(case,data=None,initial=None):
    field=forms.ModelChoiceField(bounded(EngagementDetails.objects.filter(case=case),data.get('details_id') if data else initial),
        required=False,initial=initial,label='Saved project details',empty_label='No saved details selected')
    field.label_from_instance=lambda d:d.reference+' · saved '+timezone.localtime(d.created_at).strftime('%d %b %Y, %H:%M %Z')
    return field


class DetailsForm(forms.Form):
    operation=forms.CharField(initial='details',widget=forms.HiddenInput)
    capture_id=forms.IntegerField(min_value=1,widget=forms.HiddenInput)
    key=forms.CharField(max_length=100,widget=forms.HiddenInput)
    reference=forms.CharField(label='Supplied project reference',max_length=120)
    plan_id=forms.ModelChoiceField(Evidence.objects.none(),label='Planning document')
    evidence_id=forms.ModelChoiceField(Evidence.objects.none(),label='Supporting document')
    planned_start=forms.DateField(label='Agreed planned start date',required=False,
        widget=forms.DateInput(attrs={'type':'date'}),help_text='Leave blank when the source does not establish a date.')
    contact_id=forms.ModelChoiceField(ClientContactRevision.objects.none(),label='Client project contact',required=False,
        empty_label='Unknown — no supported contact recorded')
    checked=forms.BooleanField(label='I checked these facts against the supporting document.')

    def __init__(self,case,data=None):
        from .engagement import latest
        capture=latest(case,'capture')
        super().__init__(data,initial={'key':uuid4().hex,'capture_id':capture.pk if capture else None},auto_id='engagement_details_%s')
        self.fields['plan_id']=evidence_field(case,data,'plan_id',['plan'])
        self.fields['evidence_id']=evidence_field(case,data)
        current=ClientContactRevision.objects.filter(case=case,purpose='project',customer='').order_by('-number').first()
        self.fields['contact_id'].queryset=ClientContactRevision.objects.filter(pk=current.pk if current else None)
        self.fields['contact_id'].label_from_instance=lambda contact:contact.name+(' · '+contact.role if contact.role else '')


class RegistrationRulesForm(forms.Form):
    registration_roles=forms.MultipleChoiceField(label='Who may register a project',choices=[(r,role_name(r)) for r in ROLES],
        widget=forms.CheckboxSelectMultiple)
    namespace=forms.CharField(label='Project reference register',max_length=100)
    format=forms.ChoiceField(label='Allowed project references',choices=[('ascii_token','Letters, numbers and reference punctuation'),('bounded_text','Plain text')])
    max_length=forms.IntegerField(label='Maximum reference length',min_value=1,max_value=120)
    case_sensitive=forms.BooleanField(label='Upper and lower case identify different references',required=False)
    planned_start=forms.TypedChoiceField(label='Is an agreed start date required?',choices=[('','Awaiting owner decision'),('yes','Yes'),('no','No')],
        required=False,coerce=lambda x:{'':None,'yes':True,'no':False}[x],empty_value=None)
    client_contact=forms.TypedChoiceField(label='Is a client project contact required?',choices=[('','Awaiting owner decision'),('yes','Yes'),('no','No')],
        required=False,coerce=lambda x:{'':None,'yes':True,'no':False}[x],empty_value=None)
    evidence_id=forms.ModelChoiceField(Evidence.objects.none(),label='Decision evidence')

    def __init__(self,case,data=None):
        super().__init__(data,auto_id='registration_rules_%s')
        self.case=case
        self.fields['evidence_id']=evidence_field(case,data,kinds=['policy_decision'])

    def value(self):
        v=self.cleaned_data
        return {k:v[k] for k in ['registration_roles','namespace','format','max_length','case_sensitive']}|{
            'allow_synthetic':self.case.synthetic,'required_details':{k:v[k] for k in ['planned_start','client_contact']}}

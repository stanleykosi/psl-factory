"""Human-readable P43 capture; native meeting/action services remain authoritative."""
import re
from django import forms
from django.contrib.auth import get_user_model
from django.forms import formset_factory
from django.utils import timezone
from apps.core.evidence_access import public_evidence
from apps.pmo.forms import MeetingForm,ActionForm
from apps.pmo.models import ActionItem
from apps.pmo.meetings import meeting_actions

LOCAL_FORMAT='%Y-%m-%dT%H:%M:%S'

class LocalMoment(forms.DateTimeField):
    """An explicit displayed zone, never an offset inside a datetime-local value."""
    def __init__(self,**kwargs):
        super().__init__(widget=forms.DateTimeInput(format=LOCAL_FORMAT,attrs={'type':'datetime-local','step':'1'}),**kwargs)
        self.original=None
    def to_python(self,value):
        if isinstance(value,str) and value and not re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2}(?:\.\d{1,6})?)?',value):
            raise forms.ValidationError('Enter the local date and time in the displayed time zone.')
        value=super().to_python(value)
        # Browsers omit fractional seconds. Reusing the immutable predecessor's
        # displayed time must not silently change its exact recorded instant.
        if value and self.original and value==self.original.replace(microsecond=0):return self.original
        return value

class PeopleChoice(forms.ModelMultipleChoiceField):
    def clean(self,value):
        if value and (len(value)>50 or len(value)!=len(set(value))):raise forms.ValidationError('Select up to 50 distinct people or actions.')
        return super().clean(value)

def person_label(person):
    name=person.get_full_name().strip()
    return name+' ('+person.get_username()+')' if name else person.get_username()

def action_label(item):
    state=item.current
    owner=person_label(state.owner) if state.owner else 'Owner unassigned'
    return item.reference+' · '+state.description+' · '+owner+' · '+state.status.replace('_',' ')

class ConfirmForm(MeetingForm):
    reference=None
    decisions=None
    evidence=None
    meeting_id=None
    occurred_at=LocalMoment(label='Meeting date and time')
    participants=PeopleChoice(queryset=get_user_model().objects.none(),required=False,label='People who actually participated',widget=forms.CheckboxSelectMultiple)
    existing_actions=PeopleChoice(queryset=ActionItem.objects.none(),required=False,label='Retain or link existing commitments',widget=forms.CheckboxSelectMultiple)
    note=forms.CharField(max_length=2000,widget=forms.Textarea(attrs={'rows':3}),label='How did you check attribution and actual agreement?')
    extraction_id=forms.IntegerField(min_value=1,required=False,widget=forms.HiddenInput)
    source_head_id=forms.IntegerField(min_value=1,widget=forms.HiddenInput)
    predecessor_id=forms.IntegerField(min_value=1,required=False,widget=forms.HiddenInput)
    time_zone=forms.CharField(widget=forms.HiddenInput)

    def __init__(self,case,*args,predecessor=None,**kwargs):
        super().__init__(*args,**kwargs)
        self.fields['kind'].choices=[('','Choose meeting type')]+list(self.fields['kind'].choices)
        self.fields['participants'].queryset=get_user_model().objects.filter(is_active=True,grant__case=case,grant__active=True,grant__action='meeting.participate').distinct().order_by('username','pk')
        self.fields['participants'].label_from_instance=person_label
        self.fields['existing_actions'].queryset=ActionItem.objects.filter(case=case,current__isnull=False).select_related('current__owner').order_by('reference','pk')
        self.fields['existing_actions'].label_from_instance=action_label
        self.fields['occurred_at'].help_text='Local time in '+timezone.get_current_timezone_name()+'. No meeting time is inferred.'
        if predecessor:self.fields['occurred_at'].original=predecessor.occurred_at

    def clean_time_zone(self):
        if self.cleaned_data['time_zone']!=timezone.get_current_timezone_name():raise forms.ValidationError('The displayed time zone changed; refresh before confirming.')
        return self.cleaned_data['time_zone']

class DecisionForm(forms.Form):
    text=forms.CharField(max_length=2000,widget=forms.Textarea(attrs={'rows':2}),label='Decision actually agreed')
    change_evidence=forms.ModelChoiceField(queryset=None,required=False,label='Related change request (optional)',empty_label='No change request linked')
    def __init__(self,case,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.fields['change_evidence'].queryset=public_evidence(case.evidence.filter(kind='change_request')).order_by('-pk')
        self.fields['change_evidence'].label_from_instance=lambda e:e.body[:120]

class CommitmentForm(ActionForm):
    meeting=None
    calculated=None
    evidence=None
    due_at=LocalMoment(required=False,label='Agreed deadline (leave blank if unknown)')
    def __init__(self,case,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.fields['owner'].queryset=get_user_model().objects.filter(is_active=True,grant__case=case,grant__active=True,grant__action='action.own').distinct().order_by('username','pk')
        self.fields['owner'].label_from_instance=person_label
        self.fields['owner'].empty_label='Owner unassigned / not agreed'
        self.fields['due_at'].help_text='Local time in '+timezone.get_current_timezone_name()+'. Blank stays unknown; no deadline is calculated.'
        self.fields['change_evidence'].queryset=public_evidence(case.evidence.filter(kind='change_request')).order_by('-pk')
        self.fields['change_evidence'].label_from_instance=lambda e:e.body[:120]
        self.fields['change_evidence'].empty_label='No change request linked'
        self.fields['reason'].label='Evidence of this actual commitment'

DecisionSet=formset_factory(DecisionForm,extra=1,max_num=50,validate_max=True,absolute_max=50,can_delete=True)
CommitmentSet=formset_factory(CommitmentForm,extra=1,max_num=50,validate_max=True,absolute_max=50,can_delete=True)

def capture_forms(work,selection,extraction,data=None,predecessor=None):
    initial={'extraction_id':extraction.pk if extraction else None,'source_head_id':work.source_head_id,'predecessor_id':selection['meeting_version_id'],'time_zone':timezone.get_current_timezone_name()}
    decisions=[]
    if predecessor:
        initial.update(kind=predecessor.kind,occurred_at=predecessor.occurred_at,purpose=predecessor.purpose,summary=predecessor.summary,participants=predecessor.participant_ids,existing_actions=list(meeting_actions(predecessor.meeting).values_list('pk',flat=True)))
        decisions=[{'text':d['text'],'change_evidence':d.get('change_evidence_id')} for d in predecessor.decisions]
    return (ConfirmForm(work.case,data,initial=initial,predecessor=predecessor),
        DecisionSet(data,prefix='decisions',initial=decisions,form_kwargs={'case':work.case}),
        CommitmentSet(data,prefix='commitments',form_kwargs={'case':work.case}))

def command_keys(form,decisions,commitments):
    keys=set(form.fields)
    for group in [decisions,commitments]:
        keys.update(group.management_form.add_prefix(k) for k in group.management_form.fields)
        for row in group:keys.update(row.add_prefix(k) for k in row.fields)
    return keys

def payload(form,decisions,commitments,note):
    d=form.cleaned_data
    value={k:d[k] for k in ['kind','purpose','summary','note']}
    value.update(occurred_at=d['occurred_at'].isoformat(),participant_ids=[p.pk for p in d['participants']],existing_action_ids=[a.pk for a in d['existing_actions']],decisions=[],actions=[])
    for row in decisions:
        item=row.cleaned_data
        if not item or item.get('DELETE'):continue
        value['decisions'].append({'text':item['text'],'evidence_id':note.pk,'change_evidence_id':item['change_evidence'].pk if item['change_evidence'] else None})
    for row in commitments:
        item=row.cleaned_data
        if not item or item.get('DELETE'):continue
        value['actions'].append({**{k:item[k] for k in ['reference','description','reason']},'owner_id':item['owner'].pk if item['owner'] else None,'due_at':item['due_at'].isoformat() if item['due_at'] else None,'evidence_id':note.pk,'change_evidence_id':item['change_evidence'].pk if item['change_evidence'] else None})
    return value

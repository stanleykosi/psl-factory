from uuid import uuid4

from django import forms
from django.utils import timezone

from apps.core.templatetags.studio_ui import role_name
from apps.core.evidence_access import public_evidence
from apps.policy.document_validators import ROLES

YES_NO=[('', 'Awaiting owner decision'),('yes','Yes'),('no','No')]


def decision(value):
    return {'':None,'yes':True,'no':False}[value]


def evidence_choices(case,*,kinds=None,selected=None):
    query=public_evidence(case.evidence.all()).defer('body')
    if kinds:query=query.filter(kind__in=kinds)
    records=list(query.order_by('-pk')[:50])
    try:
        chosen=int(selected)
        if not 1<=chosen<=9223372036854775807:chosen=None
    except (TypeError,ValueError):chosen=None
    if chosen and chosen not in {item.pk for item in records}:
        item=query.filter(pk=chosen).first()
        if item:records.insert(0,item)
    return [(item.pk,str(item)) for item in records]


class MessageRulesForm(forms.Form):
    reviewer_roles=forms.MultipleChoiceField(label='Who may review message wording',required=False,
        choices=[(r,role_name(r)) for r in ROLES],widget=forms.CheckboxSelectMultiple)
    sender_roles=forms.MultipleChoiceField(label='Who may release messages',required=False,
        choices=[(r,role_name(r)) for r in ROLES],widget=forms.CheckboxSelectMultiple)
    independent_release=forms.TypedChoiceField(label='Must a different person release a reviewed message?',
        choices=YES_NO,coerce=decision,empty_value=None,required=False)
    reminder_after_hours=forms.FloatField(label='Hours before another reminder',required=False,
        help_text='Leave blank until decided.')
    escalation_after_hours=forms.FloatField(label='Hours from the first delivered request before escalation',
        required=False,help_text='Reminders do not restart this interval. Leave blank until decided.')
    escalation_target=forms.ChoiceField(label='Escalation destination',required=False,choices=[
        ('','Awaiting owner decision'),('PMO','Project management office'),('CTO','Chief technology officer'),('Client','Client')])
    clock_basis=forms.ChoiceField(label='Time used for follow-up deadlines',required=False,choices=[
        ('','Awaiting owner decision'),('source_delivery_time','Actual delivery time established by the receipt'),
        ('recorded_receipt_time','When the receipt is recorded in the factory')])
    draft_on_owner_wait=forms.TypedChoiceField(label='Prepare a suggestion when owner input is needed?',
        choices=YES_NO,coerce=decision,empty_value=None,required=False)
    evidence=forms.ChoiceField(label='Decision evidence')
    revision=forms.IntegerField(min_value=1,widget=forms.HiddenInput)

    def clean(self):
        data=super().clean()
        for name in ['reminder_after_hours','escalation_after_hours']:
            if data.get(name) is not None and data[name]<=0:
                self.add_error(name,'Enter a positive interval or leave it undecided.')
        return data


class TeamRouteForm(forms.Form):
    team_key=forms.ChoiceField(label='External team')
    channel=forms.ChoiceField(label='Channel',choices=[('','Choose a channel'),('email','Email'),('whatsapp','WhatsApp'),('ticket','Ticket')])
    destination=forms.CharField(label='Delivery address or destination',max_length=240)
    mode=forms.ChoiceField(label='How delivery is checked',choices=[
        ('','Choose how delivery is checked'),('synthetic_mailbox','Internal test delivery'),('manual_evidence','You send and record the channel receipt')])

    def __init__(self,*args,teams=(),**kwargs):
        super().__init__(*args,**kwargs)
        self.fields['team_key'].choices=[('', 'Choose a configured team')]+[(t['key'],t['label']) for t in teams]


RoutesFormSet=forms.formset_factory(TeamRouteForm,extra=1,can_delete=True,max_num=40,validate_max=True,absolute_max=40)


class PrepareMessageForm(forms.Form):
    kind=forms.ChoiceField(label='Message purpose',choices=[('request','Owner request'),('reminder','Reminder')])
    state=forms.IntegerField(min_value=1,widget=forms.HiddenInput)
    operation_key=forms.UUIDField(widget=forms.HiddenInput)
    revision=forms.IntegerField(min_value=1,widget=forms.HiddenInput)

    def __init__(self,case,issue,data=None):
        super().__init__(data,initial={'state':issue.current_id,'operation_key':uuid4(),'revision':case.revision},auto_id='message_prepare_%s')


class EditMessageForm(forms.Form):
    body=forms.CharField(label='Message wording',max_length=4000,widget=forms.Textarea(attrs={'rows':8}))
    evidence=forms.ChoiceField(label='Supporting evidence')
    reason=forms.CharField(label='Why you changed it',max_length=2000,widget=forms.Textarea(attrs={'rows':2}))
    state=forms.IntegerField(min_value=1,widget=forms.HiddenInput)
    previous=forms.IntegerField(min_value=1,widget=forms.HiddenInput)
    operation_key=forms.UUIDField(widget=forms.HiddenInput)
    revision=forms.IntegerField(min_value=1,widget=forms.HiddenInput)

    def __init__(self,case,draft,data=None):
        super().__init__(data,initial={'body':draft.body,'state':draft.state_id,'previous':draft.pk,
            'operation_key':uuid4(),'revision':case.revision},auto_id='message_edit_%s')
        self.fields['evidence'].choices=evidence_choices(case,selected=data.get('evidence') if data else draft.evidence_id)


class ReviewMessageForm(forms.Form):
    role=forms.ChoiceField(label='Your review role')
    verdict=forms.ChoiceField(label='Decision',choices=[('approve','Approve wording'),('return','Return for changes'),('reject','Reject')])
    evidence=forms.ChoiceField(label='Review evidence')
    note=forms.CharField(label='Review note',max_length=2000,widget=forms.Textarea(attrs={'rows':3}))
    revision=forms.IntegerField(min_value=1,widget=forms.HiddenInput)

    def __init__(self,case,roles,data=None):
        super().__init__(data,initial={'revision':case.revision},auto_id='message_review_%s')
        self.fields['role'].choices=[(r,role_name(r)) for r in roles]
        self.fields['evidence'].choices=evidence_choices(case,selected=data.get('evidence') if data else None)


class ReleaseMessageForm(forms.Form):
    role=forms.ChoiceField(label='Your sender role')
    channel=forms.ChoiceField(label='Delivery channel')
    not_before=forms.DateTimeField(label='Schedule for',required=False,
        help_text='Leave blank for the earliest permitted time. Time zone Africa/Lagos.',
        widget=forms.DateTimeInput(format='%Y-%m-%dT%H:%M:%S',attrs={'type':'datetime-local','step':1}))
    revision=forms.IntegerField(min_value=1,widget=forms.HiddenInput)

    def __init__(self,case,roles,channels,data=None):
        super().__init__(data,initial={'revision':case.revision},auto_id='message_release_%s')
        self.fields['role'].choices=[(r,role_name(r)) for r in roles]
        self.fields['channel'].choices=[(c,{'email':'Email','whatsapp':'WhatsApp','ticket':'Ticket'}[c]) for c in channels]
        self.fields['not_before'].help_text='Leave blank for the earliest permitted time. Time zone '+timezone.get_current_timezone_name()+'.'


class ReceiptMessageForm(forms.Form):
    role=forms.ChoiceField(label='Your receipt recorder role')
    evidence=forms.ChoiceField(label='Original channel evidence')
    reference=forms.CharField(label='Actual receipt reference',max_length=160)
    delivered=forms.TypedChoiceField(label='What did the channel confirm?',choices=[
        ('yes','Delivered'),('no','Not delivered')],coerce=lambda value:value=='yes')
    delivered_at=forms.DateTimeField(label='Actual delivery time',required=False,
        help_text='Leave blank if the source does not establish the time.',
        widget=forms.DateTimeInput(format='%Y-%m-%dT%H:%M:%S',attrs={'type':'datetime-local','step':1}))
    checked=forms.BooleanField(label='I checked this source against the released message, channel and recipient.')
    revision=forms.IntegerField(min_value=1,widget=forms.HiddenInput)

    def __init__(self,case,roles,data=None):
        super().__init__(data,initial={'revision':case.revision},auto_id='message_receipt_%s')
        self.fields['role'].choices=[(r,role_name(r)) for r in roles]
        self.fields['evidence'].choices=evidence_choices(case,
            kinds=['document','support_message','project_artifact','issue_delivery_source'],
            selected=data.get('evidence') if data else None)
        self.fields['delivered_at'].help_text+=' Time zone '+timezone.get_current_timezone_name()+'.'


class SenderActionForm(forms.Form):
    role=forms.ChoiceField(label='Your sender role')
    revision=forms.IntegerField(min_value=1,widget=forms.HiddenInput)

    def __init__(self,case,roles,data=None,*,auto_id='message_sender_%s'):
        super().__init__(data,initial={'revision':case.revision},auto_id=auto_id)
        self.fields['role'].choices=[(r,role_name(r)) for r in roles]


class ManualStartForm(forms.Form):
    revision=forms.IntegerField(min_value=1,widget=forms.HiddenInput)

    def __init__(self,case,data=None):
        super().__init__(data,initial={'revision':case.revision},auto_id='message_manual_%s')


class CancelMessageForm(SenderActionForm):
    reason=forms.CharField(label='Why this unsent release is cancelled',max_length=2000,
                           widget=forms.Textarea(attrs={'rows':2}))

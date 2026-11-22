from django import forms
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.utils import timezone

from apps.identity.services import require
from apps.policy.change_drafts import draft_standard_policy
from apps.policy.document_validators import ROLES
from apps.policy.go_live_reply_validators import CHANNELS
from apps.policy.services import active_component, decision_authority, reference_values
from . import go_live_replies
from .models import DeliveryDossier, GoLiveRemediation, Issue


class ReplyForm(forms.Form):
    receipt_id = forms.IntegerField(min_value=1, widget=forms.HiddenInput)
    previous_id = forms.IntegerField(required=False, min_value=1, widget=forms.HiddenInput)
    outcome = forms.ChoiceField(label='Client response', choices=[('', 'Choose the actual response'),
        ('changes_requested', 'Asked for changes'), ('declined', 'Declined go-live')])
    party = forms.CharField(label='Who sent the response?', max_length=160)
    responded_at = forms.DateTimeField(label='Responded at', widget=forms.DateTimeInput(attrs={'type': 'datetime-local'}))
    channel = forms.ChoiceField(label='Received through', choices=[('', 'Choose the received channel')]+[(name,name.replace('_',' ').capitalize()) for name in CHANNELS])
    evidence_id = forms.IntegerField(min_value=1, label='Supporting response document reference')
    note = forms.CharField(label='Response and requested changes', max_length=4000, widget=forms.Textarea(attrs={'rows':3}))
    role = forms.ChoiceField(label='My recording role', choices=[])
    attested = forms.BooleanField(label='I confirm this response and its supporting evidence were received.')

    def __init__(self, *args, roles=(), correction=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['role'].choices=[('', 'Choose your current role')]+[(role,role) for role in roles]
        if correction:
            self.fields['outcome'].choices=[('withdrawn', 'Withdraw an incorrectly recorded response')]
            self.fields['note'].label='What was recorded incorrectly and why is this correction supported?'
            self.fields['responded_at'].label='Correcting evidence received at'


class ProblemForm(forms.Form):
    reply_id = forms.IntegerField(min_value=1, widget=forms.HiddenInput)
    existing_issue_id=forms.ModelChoiceField(queryset=Issue.objects.none(),required=False,label='Existing issue, when already logged',empty_label='Create a new issue')
    title = forms.CharField(required=False,label='New issue title', max_length=240)
    owner_id = forms.ModelChoiceField(required=False,queryset=get_user_model().objects.none(), label='Responsible person for a new issue')
    next_action = forms.CharField(required=False,label='Next action for a new issue', max_length=1000)
    note = forms.CharField(label='Issue context', max_length=4000, widget=forms.Textarea(attrs={'rows':3}))

    def __init__(self, actor,case, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['owner_id'].queryset=get_user_model().objects.filter(is_active=True,
            grant__case=case,grant__active=True,grant__action='issue.own').distinct().order_by('username')
        try:
            require(actor,case,'issue.read')
            self.fields['existing_issue_id'].queryset=Issue.objects.filter(case=case,current__isnull=False).order_by('reference')
            self.fields['existing_issue_id'].label_from_instance=lambda row:row.reference
        except PermissionDenied:
            pass

    def clean(self):
        values=super().clean()
        if not values.get('existing_issue_id'):
            for key in ['title','owner_id','next_action']:
                if not values.get(key):self.add_error(key,'Complete this field when creating a new issue.')
        return values


class RemediationForm(forms.Form):
    reply_id = forms.IntegerField(min_value=1, widget=forms.HiddenInput)
    previous_id = forms.IntegerField(required=False, min_value=1, widget=forms.HiddenInput)
    destination_id = forms.ModelChoiceField(queryset=DeliveryDossier.objects.none(), label='New release candidate')
    role = forms.ChoiceField(label='My review role', choices=[])
    evidence_id = forms.IntegerField(min_value=1, label='Decision evidence reference')
    note = forms.CharField(label='Why the fix is ready for new release gates', max_length=4000, widget=forms.Textarea(attrs={'rows':3}))

    def __init__(self, dossier, *args, roles=(), **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['role'].choices=[('', 'Choose your current role')]+[(role,role) for role in roles]
        self.fields['destination_id'].queryset=DeliveryDossier.objects.filter(case=dossier.case).exclude(candidate_id=dossier.candidate_id).select_related('candidate')
        self.fields['destination_id'].label_from_instance=lambda row:row.candidate.reference


class CandidateForm(forms.Form):
    reply_id=forms.IntegerField(min_value=1,widget=forms.HiddenInput)
    reference=forms.CharField(max_length=160,label='New candidate reference')
    requirements_id=forms.IntegerField(min_value=1,label='Requirements document reference')
    note=forms.CharField(max_length=4000,label='Why this candidate is being prepared',widget=forms.Textarea(attrs={'rows':3}))


class ReplyRulesForm(forms.Form):
    base_configuration = forms.IntegerField(min_value=0, widget=forms.HiddenInput)
    recording_roles = forms.MultipleChoiceField(label='Who may record received replies?', choices=[(role,role) for role in ROLES])
    correction_roles = forms.MultipleChoiceField(label='Who may correct recorded replies?', choices=[(role,role) for role in ROLES])
    remediation_roles = forms.MultipleChoiceField(label='Who may review the next release handoff?', choices=[(role,role) for role in ROLES])
    allow_recorder_correction = forms.ChoiceField(label='May the recorder correct their own response?', choices=[('', 'Choose the recorded rule'),('yes','Yes'),('no','Require a separate reviewer')])
    channels = forms.MultipleChoiceField(label='Covered response channels', choices=[(name,name.replace('_',' ').capitalize()) for name in CHANNELS], widget=forms.CheckboxSelectMultiple)
    changes_handling = forms.ChoiceField(label='When the client asks for changes', choices=[('', 'Choose the recorded rule'),
        ('reviewed_document_successor','Prepare corrected sources and a freshly reviewed report'),('owner_review','Hold for the process owner')])
    decline_handling = forms.ChoiceField(label='When the client declines', choices=[('', 'Choose the recorded rule'),
        ('new_release_candidate','Resolve the issue and review a new release candidate'),('owner_review','Hold for the process owner')])
    issue_states_for_new_release = forms.MultipleChoiceField(label='Issue states allowed before the new release handoff',
        choices=[('Resolved','Resolved with fix evidence'),('Closed','Closed with fix evidence')])
    evidence_id = forms.IntegerField(min_value=1, label='Recorded owner decision reference')

    def save(self, actor, case):
        from apps.core.evidence_access import public_evidence
        if not public_evidence(case.evidence.filter(pk=self.cleaned_data['evidence_id'],kind='policy_decision')).exists():
            raise ValidationError('Select this project recorded owner decision.')
        try:
            configuration=active_component(go_live_replies.COMPONENT,case)
        except ValidationError:
            configuration=None
        if (configuration.pk if configuration else 0)!=self.cleaned_data['base_configuration']:
            raise ValidationError('The response rules changed. Review the current version.')
        content=reference_values(configuration) if configuration else []
        content=[row for row in content if row.get('kind')!='go_live_reply']
        value={key:self.cleaned_data[key] for key in ['recording_roles','correction_roles','remediation_roles','channels',
            'changes_handling','decline_handling','issue_states_for_new_release']}
        value.update(kind='go_live_reply',key='client_responses',allow_recorder_correction=self.cleaned_data['allow_recorder_correction']=='yes')
        return draft_standard_policy(actor,case.pk,go_live_replies.COMPONENT,content+[value],self.cleaned_data['evidence_id'],timezone.now())


def current_roles(actor,case,roles):
    result=[]
    for role in roles:
        try:
            decision_authority(actor,case,role)
            result.append(role)
        except (ValidationError,PermissionDenied):
            continue
    return result


def panels(actor,work,state,data=None,action=None):
    case=work.case
    response=state['client_responses']
    value=response['rules']
    result={'capture':[],'corrections':[],'problems':[],'candidates':[],'remediation':[],'rules':None}
    try:
        require(actor,case,'delivery.manage')
        may_record=True
    except PermissionDenied:
        may_record=False
    rows=go_live_replies.current_heads(state['dossier'])
    visible_sources={item['id'] for item in response['items'] if item['source_available']}
    by_receipt={reply.receipt_id:reply for reply in rows}
    if may_record and not state['previous_acceptance'] and not work.cancel_requested:
        roles=current_roles(actor,case,value['recording_roles'] if value else ['PM'])
        for receipt in state['receipts'] if roles else []:
            previous=by_receipt.get(receipt.pk)
            bound=action=='client_reply' and str(receipt.pk)==data.get('receipt_id')
            form=ReplyForm(data if bound else None,roles=roles,
                initial={'receipt_id':receipt.pk,'previous_id':previous.pk if previous else None},auto_id='reply_'+str(receipt.pk)+'_%s')
            result['capture'].append({'receipt':receipt,'form':form})
    if may_record and value:
        roles=current_roles(actor,case,value['correction_roles'])
        for reply in rows if roles else []:
            if not value['allow_recorder_correction'] and reply.actor_id==actor.pk:continue
            bound=action=='client_reply' and str(reply.receipt_id)==data.get('receipt_id') and data.get('outcome')=='withdrawn'
            form=ReplyForm(data if bound else None,roles=roles,correction=True,
                initial={'receipt_id':reply.receipt_id,'previous_id':reply.pk,
                         'party':reply.party if reply.pk in visible_sources else '', 'channel':reply.channel},
                auto_id='reply_correction_'+str(reply.pk)+'_%s')
            result['corrections'].append({'reply':reply,'form':form})
    linked={link.reply_id for link in response['issues']}
    for reply in rows if may_record else []:
        if reply.outcome!='declined':continue
        try:
            require(actor,case,'issue.manage')
            if reply.pk not in linked:
                form=ProblemForm(actor,case,data if action=='client_decline_issue' and str(reply.pk)==data.get('reply_id') else None,
                    initial={'reply_id':reply.pk,'title':'Client declined go-live',
                             'note':reply.note if reply.pk in visible_sources else ''},auto_id='decline_issue_'+str(reply.pk)+'_%s')
                result['problems'].append({'reply':reply,'form':form})
        except PermissionDenied:
            pass
        if not value or value['decline_handling']!='new_release_candidate':continue
        try:
            require(actor,case,'pmo.candidate')
            form=CandidateForm(data if action=='client_decline_candidate' and str(reply.pk)==data.get('reply_id') else None,
                initial={'reply_id':reply.pk,'requirements_id':state['dossier'].candidate.requirements_id},auto_id='decline_candidate_'+str(reply.pk)+'_%s')
            result['candidates'].append({'reply':reply,'form':form})
        except PermissionDenied:
            pass
        roles=current_roles(actor,case,value['remediation_roles'])
        if not roles:continue
        previous=GoLiveRemediation.objects.filter(reply=reply).order_by('-number').first()
        form=RemediationForm(state['dossier'],data if action=='client_decline_handoff' and str(reply.pk)==data.get('reply_id') else None,
            roles=roles,initial={'reply_id':reply.pk,'previous_id':previous.pk if previous else None},auto_id='decline_handoff_'+str(reply.pk)+'_%s')
        result['remediation'].append({'reply':reply,'form':form})
    try:
        require(actor,case,'policy.configure')
        try:configuration=active_component(go_live_replies.COMPONENT,case)
        except ValidationError:configuration=None
        initial=dict(value or {},base_configuration=configuration.pk if configuration else 0)
        if 'allow_recorder_correction' in initial:initial['allow_recorder_correction']='yes' if initial['allow_recorder_correction'] else 'no'
        result['rules']=ReplyRulesForm(data if action=='client_reply_rules' else None,initial=initial,auto_id='reply_rules_%s')
    except PermissionDenied:
        pass
    return result

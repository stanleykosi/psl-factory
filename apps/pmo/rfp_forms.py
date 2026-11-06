from django import forms
from django.contrib.auth import get_user_model
from apps.documents.models import Template
from apps.policy.document_validators import ROLES
from .models import RFPResponse,RFPSubmission,RFPOutcome,RFPDocumentBinding
from .rfp import TEAMS,REVIEW_ROLES

class CommandForm(forms.Form):
    action=forms.CharField(widget=forms.HiddenInput)
    revision=forms.IntegerField(widget=forms.HiddenInput)

def forms_for(case,data=None):
    def evidence(kinds=None):return forms.ModelChoiceField(case.evidence.filter(kind__in=kinds) if kinds else case.evidence.all())
    def choices(values):return forms.ChoiceField(choices=[(v,v) for v in values])
    def text():return forms.CharField(max_length=4000,widget=forms.Textarea(attrs={'rows':2}))
    response=lambda:forms.ModelChoiceField(RFPResponse.objects.filter(rfp__case=case))
    definitions={
        'intake':('Log received RFP',{'reference':forms.CharField(max_length=160),'evidence':evidence(['rfp_intake']),'received_at':forms.DateTimeField(help_text='Actual received date/time with timezone'),
            'deadline_status':choices(['unknown','stated','not_stated']),'deadline_at':forms.DateTimeField(required=False),'deadline_evidence':evidence(['rfp_deadline']),'note':text()}),
        'assign':('Assign accountable PM',{'pm':forms.ModelChoiceField(get_user_model().objects.filter(grant__case=case,grant__action='rfp.prepare',grant__active=True).distinct()),'role':choices(ROLES),'evidence':evidence(),'note':text()}),
        'contribute':('Capture team input',{'team':choices(TEAMS),'evidence':evidence(list(TEAMS.values()))}),
        'prepare':('Prepare response revision',{'evidence':evidence(['rfp_response']),'public_terms':evidence(['rfp_commercial_terms']),'matrix':forms.JSONField(widget=forms.Textarea(attrs={'rows':5}),help_text='Array of {key, evidence_id, response, disposition}; disposition addressed / clarification / out_of_scope'),**{k:evidence([k]) for k in ['requirements','plan','costing']}}),
        'review':('Record response review',{'response':response(),'role':choices(REVIEW_ROLES),'verdict':choices(['approve','return','reject']),'evidence':evidence(),'note':text()}),
        'draft':('Prepare controlled submission',{'response':response(),'template':forms.ModelChoiceField(Template.objects.filter(case=case,definition__document_type__in=['rfp_response','project_artifact'])),'route_key':forms.CharField(max_length=40)}),
        'capture':('Record actual submission receipts',{'version':forms.ModelChoiceField(RFPDocumentBinding.objects.filter(response__rfp__case=case),label='Controlled response binding')}),
        'outcome':('Record relationship-owner outcome',{'submission':forms.ModelChoiceField(RFPSubmission.objects.filter(response__rfp__case=case)),'result':choices(['unknown','pending','won','lost']),'observed_at':forms.DateTimeField(),'role':choices(ROLES),'evidence':evidence(['rfp_outcome']),'note':text()}),
        'dispose':('Convert win or archive loss',{'outcome':forms.ModelChoiceField(RFPOutcome.objects.filter(submission__response__rfp__case=case)),'lessons':evidence(['rfp_lessons'])}),
        'policy':('Save RFP policy draft',{'component':choices(['D05.decision_action_matrix','D11.adapter_configuration_refs']),'content':forms.JSONField(widget=forms.Textarea(attrs={'rows':5})),'evidence':evidence(['policy_decision']),'effective_from':forms.DateTimeField()}),
        'investigate':('Investigate evidence and next work',{})}
    result=[]
    for action,(label,fields) in definitions.items():
        f=CommandForm(data if data and data.get('action')==action else None,initial={'action':action,'revision':case.revision},auto_id=action+'_%s')
        f.fields.update(fields)
        if action=='intake':f.fields['deadline_evidence'].required=False
        if action=='dispose':f.fields['lessons'].required=False
        result.append({'action':action,'label':label,'form':f})
    return result

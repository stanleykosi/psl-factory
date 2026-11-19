"""Human-recorded client testing responses, with separate private proof access."""
from uuid import uuid4
from zoneinfo import ZoneInfo,ZoneInfoNotFoundError
from django import forms
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied,ValidationError
from django.db import transaction
from django.http import FileResponse
from django.shortcuts import render,redirect,get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_http_methods,require_safe
from io import BytesIO
from adapters import client_uat as contract,case_uploads
from apps.core.views import accessible_case
from apps.core.models import ClientContactRevision,Evidence
from apps.core.evidence_access import public_evidence
from apps.core.services import lock_case
from apps.identity.services import require
from apps.identity.models import Grant
from apps.agents.models import CaseUpload
from apps.agents.upload_views import upload_file
from apps.policy.models import Configuration
from apps.policy.approval_drafts import draft_approval_policy
from apps.policy.client_uat_validators import COMPONENT
from apps.policy.services import reference_values
from . import client_uat as domain
from .models import DeliveryDossier,ClientUATGateBinding
from .clocks import local_time


class CommandForm(forms.Form):
    revision=forms.IntegerField(min_value=1,widget=forms.HiddenInput)
    operation_key=forms.UUIDField(widget=forms.HiddenInput)


class TimeForm(CommandForm):
    day=forms.DateField(label='Actual date',widget=forms.DateInput(attrs={'type':'date'}))
    clock=forms.TimeField(label='Actual time',widget=forms.TimeInput(attrs={'type':'time'}))
    zone=forms.CharField(label='Time zone',max_length=100,help_text='For example Africa/Lagos. Use the time zone of the actual response.')

    def clean(self):
        value=super().clean()
        if all(key in value for key in ['day','clock','zone']):
            try:value['instant']=local_time(value['day'],value['clock'].isoformat(),ZoneInfo(value['zone']))
            except (ZoneInfoNotFoundError,ValueError,ValidationError):raise ValidationError('Use an unambiguous time and a recognised time zone.')
        return value


class TargetForm(TimeForm):
    previous=forms.IntegerField(min_value=0,widget=forms.HiddenInput)
    gate=forms.IntegerField(min_value=0,widget=forms.HiddenInput)
    contact=forms.TypedChoiceField(label='Client contact',coerce=int)
    replace=forms.BooleanField(required=False,label='I reviewed the earlier client testing record and am recording its replacement')


class ResponseForm(TimeForm):
    target=forms.IntegerField(min_value=1,widget=forms.HiddenInput)
    previous=forms.IntegerField(min_value=0,widget=forms.HiddenInput)
    outcome=forms.ChoiceField(label='What did the client decide?',choices=contract.OUTCOMES.items())
    proofs=forms.TypedMultipleChoiceField(label='Supporting files',coerce=int,widget=forms.CheckboxSelectMultiple)
    genuine=forms.BooleanField(label='I confirm this is the genuine response from the named client contact for this version')
    note=forms.CharField(label='Recording note',max_length=2000,required=False,widget=forms.Textarea(attrs={'rows':2}))
    workaround=forms.CharField(label='Exact workaround approved by the client',max_length=2000,required=False,widget=forms.Textarea(attrs={'rows':2}))
    source_reference=forms.CharField(label='Existing client decision reference, if already tracked',max_length=240,required=False)


class DecisionForm(CommandForm):
    response=forms.IntegerField(min_value=1,widget=forms.HiddenInput)
    inspection=forms.IntegerField(min_value=1,widget=forms.HiddenInput)
    verdict=forms.ChoiceField(label='Evidence decision',choices=[('confirm','Confirm the proof'),('return','Return for correction'),('withdraw','Withdraw my proof confirmation')])
    proof_confirmed=forms.BooleanField(required=False,label='I checked that the proof identifies the client, version and recorded decision')
    note=forms.CharField(label='Reason',max_length=2000,widget=forms.Textarea(attrs={'rows':2}))


class FollowUpForm(CommandForm):
    response=forms.IntegerField(min_value=1,widget=forms.HiddenInput)
    review=forms.IntegerField(min_value=0,required=False,widget=forms.HiddenInput)
    previous_binding=forms.IntegerField(min_value=0,required=False,widget=forms.HiddenInput)
    reason=forms.CharField(label='Correction or retraction reason',max_length=2000,required=False,widget=forms.Textarea(attrs={'rows':2}))


def allowed(actor,case,action):
    try:require(actor,case,action)
    except PermissionDenied:return False
    return True


@login_required
@require_http_methods(['GET','HEAD','POST'])
def desk(request,case_id,dossier_id):
    case=accessible_case(request.user,case_id);domain.readable(request.user,case)
    dossier=get_object_or_404(DeliveryDossier.objects.select_related('candidate__requirements','case'),case=case,pk=dossier_id)
    return_work=None
    selected=request.GET.get('work','')
    if selected.isascii() and selected.isdigit() and len(selected)<=19 and 0<int(selected)<2**63:
        from apps.workflows.models import FactoryWork
        from apps.workflows.factory import access
        try:
            access(request.user,case,'factory.read','delivery-release/v1')
            return_work=FactoryWork.objects.filter(pk=int(selected),case=case,definition='delivery-release/v1',request__dossier=dossier.pk).values_list('pk',flat=True).first()
        except (PermissionDenied,ValidationError):pass
    action=request.POST.get('action') if request.method=='POST' else None
    target=domain.head(dossier,contract.TARGET)
    response=domain.head(dossier,contract.RESPONSE,target.pk) if target else None
    gate=dossier.candidate.gates.filter(kind='uat_client').order_by('-pk').first()
    initial={'revision':case.revision,'operation_key':uuid4()}
    target_form=TargetForm(request.POST if action=='target' else None,auto_id='test_request_%s',initial={**initial,'previous':target.pk if target else 0,'gate':gate.pk if gate else 0})
    people=ClientContactRevision.objects.filter(case=case,purpose='project',customer='').order_by('-number')[:1]
    target_form.fields['contact'].choices=[(p.pk,p.name) for p in people if _contact_visible(request.user,case,p.pk)]
    response_form=ResponseForm(request.POST if action=='response' else None,auto_id='client_response_%s',initial={**initial,'target':target.pk if target else None,'previous':response.pk if response else 0})
    response_form.fields['proofs'].choices=[(row.pk,row.name) for row in CaseUpload.objects.filter(case=case,actor=request.user).order_by('-pk')[:50]]
    inspection=response.verifications.filter(adapter=contract.INSPECTION).order_by('-pk').first() if response else None
    review=response.verifications.filter(adapter=contract.REVIEW).order_by('-pk').first() if response else None
    binding=ClientUATGateBinding.objects.filter(review__source=response).order_by('-pk').first() if response else None
    decision_form=DecisionForm(request.POST if action=='review' else None,auto_id='proof_review_%s',initial={**initial,'response':response.pk if response else None,'inspection':inspection.pk if inspection else None})
    follow_form=FollowUpForm(request.POST if action in ['inspect','agent','export','retract'] else None,auto_id=False,initial={**initial,'response':response.pk if response else None,'review':review.pk if review else 0,'previous_binding':binding.pk if binding else 0})
    if action:
        form={'target':target_form,'response':response_form,'review':decision_form,'inspect':follow_form,'agent':follow_form,'export':follow_form,'retract':follow_form}.get(action)
        if action=='upload':
            try:upload_file(request.user,case,request.FILES.get('file'))
            except (ValidationError,OSError) as exc:messages.error(request,str(exc))
            else:messages.success(request,'Private proof file uploaded.')
            return redirect(request.get_full_path())
        if form and form.is_valid() and not (set(request.POST)-set(form.fields)-{'action','csrfmiddlewaretoken'}):
            v=form.cleaned_data
            try:
                if action=='target':domain.record_target(request.user,case.pk,dossier.pk,v['contact'],v['instant'],v['previous'] or None,v['gate'] or None,v['replace'],v['operation_key'],v['revision'])
                elif action=='response':domain.record_response(request.user,case.pk,v['target'],v['instant'],v['outcome'],v['genuine'],v['note'],v['workaround'] or None,v['source_reference'] or None,v['proofs'],v['previous'] or None,v['operation_key'],v['revision'])
                elif action=='inspect':domain.inspect_proof(request.user,case.pk,v['response'],v['revision'])
                elif action=='review':domain.review_proof(request.user,case.pk,v['response'],v['inspection'],v['verdict'],v['proof_confirmed'],v['note'],v['operation_key'],v['revision'])
                elif action=='retract':domain.withdraw_recording(request.user,case.pk,v['response'],v['reason'],v['operation_key'],v['revision'])
                elif action=='export':domain.export_gate(request.user,case.pk,v['response'],v['review'],v['revision'],previous_binding_id=v['previous_binding'] or None,correction_reason=v['reason'] or None)
                elif action=='agent':
                    with transaction.atomic():
                        locked=lock_case(request.user,case.pk,'client_uat.record',v['revision']);domain.queue_checks(request.user,domain.exact(locked,v['response'],contract.RESPONSE))
                messages.success(request,'Client testing record updated. Review the next step below.')
                return redirect(request.get_full_path())
            except (ValidationError,PermissionDenied) as exc:form.add_error(None,str(exc));case.refresh_from_db()
        elif form is None:messages.error(request,'Choose a displayed action.')
    status='No client testing request recorded';current=False;proofs=[];can_review=False;visible_response=response;agent_drafts=[]
    if response:
        status='Response recorded; current proof review needed'
        try:domain.current_review(request.user,response);status='Client proof confirmed';current=True
        except (ValidationError,PermissionDenied):pass
        try:proofs=domain.proof_rows(request.user,response);agent_drafts=domain.agent_drafts(request.user,response)
        except (ValidationError,PermissionDenied):pass
        try:domain.reviewer(request.user,case);can_review=True
        except (ValidationError,PermissionDenied):pass
    elif target:status='Waiting for the client response'
    if response:
        try:domain.current_response(request.user,response)
        except (PermissionDenied,ValidationError):
            visible_response=None;status='The recorded response needs a fresh source check';current=False;can_review=False
    result=render(request,'pmo/client_uat.html',{'case':case,'dossier':dossier,'target':target,'response':visible_response,'return_work':return_work,
        'response_label':contract.OUTCOMES.get(visible_response.payload['outcome']) if visible_response else None,
        'status':status,'current':current,'proofs':proofs,'inspection':inspection,'review':review,'binding':binding,'agent_drafts':agent_drafts,
        'can_retract':bool(response and response.actor_id==request.user.pk and allowed(request.user,case,'client_uat.record')),
        'history':dossier.sources.filter(kind__in=contract.KINDS).defer('payload').select_related('actor').order_by('-pk')[:25],
        'target_form':target_form,'response_form':response_form,'decision_form':decision_form,'follow_form':follow_form,
        'can_record':allowed(request.user,case,'client_uat.record'),'can_upload':allowed(request.user,case,'evidence.add'),
        'can_rules':allowed(request.user,case,'policy.read') and allowed(request.user,case,'policy.configure'),
        'can_inspect':bool(proofs) and allowed(request.user,case,'client_uat.inspect'),
        'can_export':current and allowed(request.user,case,'client_uat.export'),'can_review':can_review and bool(inspection)})
    result['Cache-Control']='no-store';return result


def _contact_visible(actor,case,pk):
    try:domain.contact(actor,case,pk)
    except (PermissionDenied,ValidationError):return False
    return True


@login_required
@require_safe
@transaction.atomic
def proof(request,case_id,response_id,upload_id):
    case=lock_case(request.user,case_id,'case.read');response=domain.exact(case,response_id,contract.RESPONSE)
    uploads=domain.proof_rows(request.user,response)
    upload=next((row for row in uploads if row.pk==upload_id),None)
    if upload is None:raise PermissionDenied
    result=FileResponse(BytesIO(case_uploads.read(upload)),as_attachment=True,filename=upload.name)
    result['Cache-Control']='no-store';result['X-Content-Type-Options']='nosniff';return result


TRI=[('','Not decided'),('yes','Yes'),('no','No')]
class RulesForm(CommandForm):
    head=forms.IntegerField(min_value=0,widget=forms.HiddenInput)
    qualification_mode=forms.ChoiceField(label='How is client proof qualified?',choices=[('','Not decided'),('reviewed_human_attestation_v1','A nominated person checks the human witness and source proof')],required=False)
    reviewer_ids=forms.TypedMultipleChoiceField(label='People who may review proof',coerce=int,required=False)
    reviewer_role=forms.ChoiceField(label='Their accountable responsibility',required=False)
    independent_review=forms.ChoiceField(label='Must the reviewer be different from the recorder?',choices=TRI,required=False)
    agent_review_required=forms.ChoiceField(label='Must the agent file check finish before confirmation?',choices=TRI,required=False)
    exact_mentions_required=forms.ChoiceField(label='Must the text name the exact contact and version?',choices=TRI,required=False)
    proof_formats=forms.MultipleChoiceField(label='Accepted proof formats',required=False,choices=[(x,x.upper()) for x in ['pdf','docx','xlsx','txt']])
    workaround_mode=forms.ChoiceField(label='Can explicit client approval cover a stated workaround?',required=False,choices=[('','Not decided'),('explicit_client_approved_scope_v1','Yes, only for the exact workaround the client approved')])
    evidence=forms.ModelChoiceField(label='Recorded business decision',queryset=Evidence.objects.none())


@login_required
@require_http_methods(['GET','HEAD','POST'])
def configuration(request,case_id):
    from apps.policy.document_validators import ROLES
    case=accessible_case(request.user,case_id)
    for action in ['policy.read','policy.configure']:require(request.user,case,action)
    latest=Configuration.objects.filter(case=case,component=COMPONENT).order_by('-revision').first()
    initial={'revision':case.revision,'operation_key':uuid4(),'head':latest.pk if latest else 0}
    if latest:
        from apps.policy.impact import configuration as checked
        values=reference_values(checked(request.user,case.pk,latest.pk))[0]
        initial.update({k:('yes' if v else 'no') if type(v) is bool else v or '' for k,v in values.items()})
    form=RulesForm(request.POST if request.method=='POST' else None,initial=initial)
    form.fields['reviewer_role'].choices=[('','Not decided'),*[(x,x) for x in ROLES]]
    candidates=Grant.objects.filter(case=case,action='client_uat.review',active=True,user__is_active=True).order_by('user_id').values('user_id')[:100]
    form.fields['reviewer_ids'].choices=[(p.pk,p.get_full_name() or p.username) for p in get_user_model().objects.filter(pk__in=candidates).order_by('pk')]
    ids=public_evidence(case.evidence.filter(kind='policy_decision')).order_by('-pk').values('pk')[:50]
    form.fields['evidence'].queryset=Evidence.objects.defer('body').filter(pk__in=ids).order_by('-pk')
    if request.method=='POST' and form.is_valid():
        try:
            if set(request.POST)-set(form.fields)-{'csrfmiddlewaretoken'}:raise ValidationError('Use the displayed rule review')
            with transaction.atomic():
                locked=lock_case(request.user,case.pk,'policy.configure',form.cleaned_data['revision'])
                head=Configuration.objects.filter(case=case,component=COMPONENT).order_by('-revision').first()
                if (head.pk if head else 0)!=form.cleaned_data['head']:raise ValidationError('A newer draft exists')
                v=form.cleaned_data;content={k:v[k] or None for k in ['qualification_mode','reviewer_role','workaround_mode']}
                content.update({k:None if not v[k] else v[k]=='yes' for k in ['independent_review','agent_review_required','exact_mentions_required']})
                content.update(format='psl.client-uat-rules/v1',human_only=True,reviewer_ids=v['reviewer_ids'],proof_formats=v['proof_formats'],
                    assurance='human_witnessed_not_external_authentication',financial_controls='independent')
                draft_approval_policy(request.user,case.pk,COMPONENT,content,v['evidence'].pk,timezone.now())
            messages.success(request,'Client proof rule draft saved. Validation and activation are separate reviews.')
            return redirect(request.path)
        except (ValidationError,PermissionDenied) as exc:form.add_error(None,str(exc))
    result=render(request,'pmo/client_uat_rules.html',{'case':case,'form':form,'latest':latest});result['Cache-Control']='no-store';return result

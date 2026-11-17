"""One console for actual go-live sources, native review, delivery and human sign-off."""
from uuid import uuid4
from urllib.parse import urlencode
from django import forms
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import transaction
from django.shortcuts import render,redirect
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from apps.core.models import Evidence
from apps.core.evidence_access import public_evidence
from apps.documents.models import PublicationReceipt, Template
from apps.pmo import delivery
from apps.pmo.go_live_attestations import PROTOCOL, PURPOSE, parse_attestation, pin, subject_pins
from .factory_handover_views import StartForm as DossierStartForm
from . import factory,factory_go_live as go_live
from .factory_progress_views import enroll


class SignerForm(forms.Form):
    source_system = forms.CharField(label='Source system', max_length=160)
    source_reference = forms.CharField(label='Source reference', max_length=160)
    decision_id = forms.CharField(label='Decision reference', max_length=160)
    decision_version = forms.CharField(label='Decision version', max_length=160)
    signer_reference = forms.CharField(label='Signer reference', max_length=160)
    signed_at = forms.DateTimeField(label='Signed at', widget=forms.DateTimeInput(attrs={'type': 'datetime-local'}))

    def declaration(self, evidence):
        return {**self.cleaned_data, 'signed_at': self.cleaned_data['signed_at'].isoformat(),
                'purpose': PURPOSE, 'evidence': pin(evidence)}


def supplied_signer_facts(request, work, version, receipt_id, pm_id, client_id, forms_by_role):
    if request.POST.get('attestation'):
        if any(name.startswith(('pm-fact-', 'client-fact-')) for name in request.POST):
            raise ValidationError('Choose one way to submit the signer details.')
        return parse_attestation(request.POST['attestation'])
    valid = [form.is_valid() for form in forms_by_role.values()]
    if not all(valid):
        raise ValidationError('Complete the signer details for both Project Manager and Client.')
    if pm_id == client_id:
        raise ValidationError('Choose a different source record for each signature.')
    evidence = public_evidence(work.case.evidence.filter(kind='signature', pk__in=[pm_id, client_id])).in_bulk()
    receipt = PublicationReceipt.objects.filter(pk=receipt_id, publication__factory_work=work,
        publication__version_id=version).select_related('publication__version').first()
    if not receipt or len(evidence) != 2:
        raise ValidationError('Choose the exact delivered report and two signature sources for this project.')
    dossier, _, _ = go_live.source(work, request.user, current=False)
    release = delivery.latest(dossier, 'release_outcome', False)
    if not release:
        raise ValidationError('The report needs an exact recorded release.')
    return {**subject_pins(dossier, receipt, release), 'protocol': PROTOCOL, 'purpose': PURPOSE,
            'attesting_actor_id': request.user.pk, 'signatures': {
                'PM': forms_by_role['PM'].declaration(evidence[pm_id]),
                'Client': forms_by_role['Client'].declaration(evidence[client_id]),
            }}

class InputsForm(forms.Form):
    def __init__(self,case,*args,inputs=None,**kwargs):
        super().__init__(*args,**kwargs)
        self.fields['template_id']=forms.ModelChoiceField(required=False,label='Controlled client report template',empty_label='Not yet selected',
            queryset=Template.objects.filter(case=case,definition__document_type='project_artifact').order_by('-pk'))
        for key,kind in go_live.KINDS.items():
            self.fields[key]=forms.ModelChoiceField(required=False,label=kind.replace('_',' ').capitalize(),empty_label='Not yet provided',
                queryset=public_evidence(Evidence.objects.filter(case=case,kind=kind)).order_by('-version'))
            self.fields[key].label_from_instance=lambda e:f'{e.kind.replace("_"," ").capitalize()} · version {e.version} · reference {e.pk}'
        if inputs:
            for key,value in inputs.items():self.fields[key].initial=value
    def inputs(self):return {key:self.cleaned_data[key].pk if self.cleaned_data[key] else None for key in go_live.FIELDS}

class StartForm(DossierStartForm):
    def __init__(self,actor,*args,**kwargs):
        super().__init__(actor,*args,**kwargs)
        self.fields['definition'].initial=go_live.DEFINITION;self.fields['reference'].label='Describe the go-live acceptance work'
        if not self.is_bound:self.fields['key'].initial='GOLIVE-'+uuid4().hex

@require_http_methods(['GET','HEAD','POST'])
def create(request):
    from .factory_views import QUEUES
    queue=request.GET.get('queue','needs_me');q=request.GET.get('q','')[:120]
    if queue not in QUEUES:queue='needs_me'
    case_id=request.POST.get('case') if request.method=='POST' else request.GET.get('case')
    try:form=StartForm(request.user,request.POST if request.method=='POST' else None,case_id=case_id)
    except (ValidationError,ValueError):form=StartForm(request.user,data={});form.is_valid();form.add_error(None,'Choose an available project.')
    if form.selected and not form.is_bound:
        try:
            if form.fields['dossier'].queryset.filter(pk=request.GET.get('dossier')).exists():form.fields['dossier'].initial=request.GET.get('dossier')
        except (ValidationError,ValueError):messages.error(request,'Choose an available delivery record.')
    inputs=InputsForm(form.selected,request.POST if request.method=='POST' else None) if form.selected else None
    if request.method=='POST':
        valid=form.is_valid();inputs_valid=inputs.is_valid() if inputs else False
        if valid and inputs_valid:
            try:
                v=form.cleaned_data
                if v['definition']!=go_live.DEFINITION:raise ValidationError('Choose registered go-live acceptance work')
                with transaction.atomic():
                    w=go_live.start(request.user,v['case'].pk,v['key'],v['dossier'].pk,inputs.inputs(),v['reference'],v['revision'])
                    enroll(request, w, v['background'])
                target=reverse('factory_detail',args=[w.pk])
                return redirect(target+'?'+urlencode({'queue':queue,'q':q}) if 'queue' in request.GET or 'q' in request.GET else target)
            except ValidationError as exc:form.add_error(None,go_live.finding(exc))
    return render(request,'factory/go_live_start.html',{'case':form.selected,'form':form,'inputs_form':inputs,'queue':queue,'q':q})

@require_http_methods(['GET','HEAD','POST'])
def detail(request,work,focus=None):
    from .screen_focus import require_action
    from .factory_views import presentation,QUEUES,permitted
    queue=request.GET.get('queue','needs_me');q=request.GET.get('q','')[:120]
    if queue not in QUEUES:queue='needs_me'
    _,data,_=go_live.source(work,request.user,current=False)
    form=InputsForm(work.case,request.POST if request.method=='POST' and request.POST.get('action') in ['correct','prepare_client_revision'] else None,inputs=data['inputs'])
    signer_input=request.POST if request.method=='POST' and request.POST.get('action')=='accept' and not request.POST.get('attestation') else None
    signer_forms={'PM':SignerForm(signer_input,prefix='pm-fact'),'Client':SignerForm(signer_input,prefix='client-fact')}
    if request.method=='POST':
        try:
            p=request.POST;action=p.get('action');revision=int(p.get('revision','0'));case_revision=int(p.get('case_revision','0'))
            require_action(work, focus, action)
            if action=='advance':factory.advance(request.user,work.pk,revision)
            elif action=='correct':
                if not form.is_valid():raise ValidationError('Review the selected template and actual source records')
                go_live.correct(request.user,work.pk,revision,case_revision,form.inputs(),p.get('reason',''))
            elif action=='prepare_client_revision':
                if not form.is_valid():raise ValidationError('Choose the corrected source documents for the next report.')
                go_live.prepare_client_revision(request.user,work.pk,revision,case_revision,form.inputs(),p.get('reason',''))
            elif action=='review':go_live.review(request.user,work.pk,revision,case_revision,int(p.get('version','0')),p.get('verdict',''),p.get('note',''))
            elif action=='accept':
                version, receipt, pm, client = [int(p.get(key, '0')) for key in ('version', 'receipt', 'pm_signature', 'client_signature')]
                attestation=supplied_signer_facts(request,work,version,receipt,pm,client,signer_forms)
                go_live.accept(request.user,work.pk,revision,case_revision,version,receipt,pm,client,p.get('note',''),
                    int(p['previous_acceptance']) if p.get('previous_acceptance') else None,attestation=attestation,mode=p.get('mode','fresh_signatures'))
            elif action in ['client_reply','client_decline_issue','client_decline_handoff','client_decline_candidate','client_reply_rules']:
                go_live.client_response_action(request.user,work.pk,revision,case_revision,action,p)
            elif action in ['cancel','settle_stop']:go_live.cancel(request.user,work.pk,revision)
            elif action=='resume':factory.manage(request.user,work.pk,revision,action)
            elif action=='restart':go_live.restart(request.user,work.pk,revision,case_revision,p.get('reason',''))
            elif action=='reconcile':factory.reconcile(request.user,work.pk,revision)
            elif action=='operate_delivery':go_live.operate(request.user,work.pk,revision,case_revision,int(p.get('job','0')),p.get('operation',''),p.get('reason',''))
            elif action=='adopt_profile':factory.adopt_profile(request.user,work.pk,revision,int(p.get('configuration','0')),p.get('reason',''))
            else:raise ValidationError('Choose a currently permitted go-live action')
            messages.success(request,'Go-live work updated. Review the exact report, delivery receipts and actual sign-off.');return redirect(request.get_full_path())
        except ValidationError as exc:messages.error(request,go_live.finding(exc))
        except ValueError:messages.error(request,'Refresh the work and choose current recorded references.')
        work.refresh_from_db()
    row=presentation(request.user,work,focus=focus);activities=list(work.activities.prefetch_related('attempts').order_by('pk')) if not focus else []
    from apps.pmo.go_live_reply_forms import panels as reply_panels
    row['client_reply_panels']=reply_panels(request.user,work,row['go_live'],request.POST,request.POST.get('action'))
    for activity in activities:
        activity.title={'ACT03':'Plan permitted work','ACT04':'Investigate go-live evidence','ACT09':'Prepare the client report','ACT10':'Resolve current authority',
            'ACT11':'Deliver the exact reviewed report','ACT12':'Reconcile original delivery','ACT13':'Verify actual go-live acceptance'}.get(activity.kind,'Review permitted work')
        for attempt in activity.attempts.all():attempt.display_result=go_live.attempt_projection(attempt)
    signatures=public_evidence(Evidence.objects.filter(case=work.case,kind='signature')).order_by('-pk')
    response=render(request,'factory/go_live_detail.html',{'case':work.case,'focus':focus,'row':row,'queue':queue,'q':q,'inputs_form':form,'activities':activities,
        'pm_signer':signer_forms['PM'],'client_signer':signer_forms['Client'],'signer_time_zone':timezone.get_current_timezone_name(),
        'selected_receipt':signer_input.get('receipt','') if signer_input is not None else '',
        'selected_pm':signer_input.get('pm_signature','') if signer_input is not None else '',
        'selected_client':signer_input.get('client_signature','') if signer_input is not None else '',
        'selected_mode':signer_input.get('mode','') if signer_input is not None else '',
        'signer_note':signer_input.get('note','') if signer_input is not None else '',
        'signature_choices':list(signatures[:100]) if row['go_live']['can_accept'] and focus in [None,'response'] else [],
        'signature_limited':row['go_live']['can_accept'] and focus in [None,'response'] and signatures.count()>100,
        'can_configure':permitted(request.user,work,'policy.configure')})
    response['Cache-Control']='no-store';return response

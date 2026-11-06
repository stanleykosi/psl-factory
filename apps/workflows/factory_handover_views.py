"""Human source choices, exact native document review and actual recipient acknowledgement."""
from uuid import uuid4
from django import forms
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import render,redirect
from apps.core.models import Case,Evidence
from apps.core.evidence_access import public_evidence
from apps.core.presentation import workspace_name
from apps.core.workbench import granted
from apps.documents.models import Template
from apps.pmo.models import DeliveryDossier
from . import factory,factory_handover as handover


def evidence_label(e):return f'{e.body[:90]} · version {e.version} · evidence {e.pk}'


class InputsForm(forms.Form):
    def __init__(self,case,*args,inputs=None,**kwargs):
        super().__init__(*args,**kwargs)
        self.fields['template_id']=forms.ModelChoiceField(queryset=Template.objects.filter(case=case,definition__document_type='project_artifact').order_by('-pk'),required=False,label='Controlled handover template',empty_label='Not yet selected')
        for kind in handover.FIELDS[1:]:
            self.fields[kind]=forms.ModelChoiceField(queryset=public_evidence(Evidence.objects.filter(case=case,kind=kind)).order_by('-version'),required=False,label=kind.replace('_',' ').capitalize(),empty_label='Not yet provided')
            self.fields[kind].label_from_instance=evidence_label
        if inputs:
            for key,value in inputs.items():self.fields[key].initial=value

    def inputs(self):return {k:self.cleaned_data[k].pk if self.cleaned_data[k] else None for k in handover.FIELDS}


class StartForm(forms.Form):
    definition=forms.CharField(initial=handover.DEFINITION,widget=forms.HiddenInput)
    key=forms.CharField(widget=forms.HiddenInput,max_length=100)
    case=forms.ModelChoiceField(queryset=Case.objects.none(),label='Project')
    dossier=forms.ModelChoiceField(queryset=DeliveryDossier.objects.none(),label='Delivery or release')
    reference=forms.CharField(max_length=160,label='Describe the handover')
    revision=forms.IntegerField(min_value=1,widget=forms.HiddenInput)
    def __init__(self,actor,*args,case_id=None,**kwargs):
        super().__init__(*args,**kwargs)
        cases=granted(actor,['delivery.read','factory.start','evidence.add']).filter(kind='project');self.fields['case'].queryset=cases
        self.fields['case'].label_from_instance=workspace_name;self.selected=cases.filter(pk=case_id).first() if case_id else None
        if self.selected:
            self.fields['case'].initial=self.selected;self.fields['revision'].initial=self.selected.revision
            self.fields['dossier'].queryset=DeliveryDossier.objects.filter(case=self.selected).exclude(records__kind='closure').select_related('candidate')
            self.fields['dossier'].label_from_instance=lambda d:d.candidate.reference
        if not self.is_bound:self.fields['key'].initial='HANDOVER-'+uuid4().hex


def create(request):
    case_id=request.POST.get('case') if request.method=='POST' else request.GET.get('case')
    try:form=StartForm(request.user,request.POST if request.method=='POST' else None,case_id=case_id)
    except (ValidationError,ValueError):
        form=StartForm(request.user,data={});form.is_valid();form.add_error(None,'Choose an available project.')
    inputs=InputsForm(form.selected,request.POST if request.method=='POST' else None) if form.selected else None
    if request.method=='POST':
        valid=form.is_valid();inputs_valid=inputs.is_valid() if inputs else False
        if valid and inputs_valid:
            try:
                v=form.cleaned_data
                if v['definition']!=handover.DEFINITION:raise ValidationError('Choose registered handover work')
                w=handover.start(request.user,v['case'].pk,v['key'],v['dossier'].pk,inputs.inputs(),v['reference'],v['revision'])
                return redirect('factory_detail',w.pk)
            except ValidationError as exc:form.add_error(None,str(exc))
    return render(request,'factory/handover_start.html',{'form':form,'inputs_form':inputs,'case':form.selected})


def detail(request,work):
    from .factory_views import presentation,QUEUES,permitted
    queue=request.GET.get('queue','needs_me');q=request.GET.get('q','')[:120]
    if queue not in QUEUES:queue='needs_me'
    panel=handover.projection(request.user,work)
    form=InputsForm(work.case,request.POST if request.method=='POST' and request.POST.get('action')=='correct' else None,inputs=panel['data']['inputs'])
    if request.method=='POST':
        try:
            p=request.POST;action=p.get('action');revision=int(p.get('revision','0'))
            if action=='advance':factory.advance(request.user,work.pk,revision)
            elif action=='correct':
                if not form.is_valid():raise ValidationError('Review the selected template and source documents')
                handover.correct(request.user,work.pk,revision,int(p.get('case_revision','0')),form.inputs(),p.get('reason',''))
            elif action=='review':handover.review(request.user,work.pk,revision,int(p.get('case_revision','0')),int(p.get('version','0')),p.get('verdict',''),p.get('note',''))
            elif action=='acknowledge':
                if not p.get('evidence'):raise ValidationError('Choose the recorded evidence supporting your receipt or gap observation')
                handover.acknowledge(request.user,work.pk,revision,int(p.get('case_revision','0')),int(p.get('receipt','0')),p.get('status',''),int(p.get('evidence','0')),p.get('note',''))
            elif action in ['resume','cancel']:factory.manage(request.user,work.pk,revision,action)
            elif action=='reconcile':factory.reconcile(request.user,work.pk,revision)
            elif action=='operate_delivery':handover.operate(request.user,work.pk,revision,int(p.get('case_revision','0')),int(p.get('job','0')),p.get('operation',''),p.get('reason',''))
            elif action=='adopt_profile':factory.adopt_profile(request.user,work.pk,revision,int(p.get('configuration','0')),p.get('reason',''))
            else:raise ValidationError('Choose a currently permitted handover action')
            messages.success(request,'Handover action recorded. Review the current document, receipts and recipient status.');return redirect(request.get_full_path())
        except ValidationError as exc:messages.error(request,handover.finding_text(exc))
        except ValueError:messages.error(request,'Refresh the work and choose the currently available source or delivery reference.')
        work.refresh_from_db()
    row=presentation(request.user,work);activities=list(work.activities.prefetch_related('attempts').order_by('pk'))
    for activity in activities:
        activity.title={'ACT03':'Plan permitted work','ACT04':'Investigate handover evidence','ACT09':'Prepare the controlled package','ACT11':'Deliver the handover package','ACT12':'Reconcile original delivery','ACT13':'Verify actual recipient acknowledgement'}.get(activity.kind,'Review permitted work')
        for attempt in activity.attempts.all():attempt.display_result=handover.attempt_projection(attempt)
    response=render(request,'factory/handover_detail.html',{'case':work.case,'row':row,'queue':queue,'q':q,'activities':activities,'inputs_form':form,
        'evidence_choices':list(public_evidence(Evidence.objects.filter(case=work.case)).order_by('-pk')[:100]),'can_configure':permitted(request.user,work,'policy.configure'),
        'can_prepare_closure':work.status=='verified' and not row.get('readiness_changed')})
    response['Cache-Control']='no-store';return response

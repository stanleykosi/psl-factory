"""Exact Emergency work console; implementation attestation is always human."""
from uuid import uuid4
from django import forms
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import render,redirect
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from apps.core.models import Case,Evidence
from apps.core.workbench import granted
from apps.core.presentation import workspace_name
from apps.core.evidence_access import public_evidence
from apps.documents.models import Template
from apps.pmo.models import EmergencyProfile,EmergencyAuthorization,EmergencyOutcome
from . import factory,factory_emergency as emergency

class InputsForm(forms.Form):
    def __init__(self,case,*args,change_id=None,**kwargs):
        super().__init__(*args,**kwargs)
        profiles=EmergencyProfile.objects.filter(version__change__case=case).select_related('version__change')
        if change_id:profiles=profiles.filter(version__change_id=change_id)
        self.fields['profile_id']=forms.ModelChoiceField(queryset=profiles.order_by('-pk'),label='Exact native Emergency profile')
        self.fields['profile_id'].label_from_instance=lambda p:f'{p.version.change.reference} · change revision {p.version.number} · profile {p.pk}'
        self.fields['authorization_id']=forms.ModelChoiceField(queryset=EmergencyAuthorization.objects.filter(profile__in=profiles).select_related('profile__version__change').order_by('-pk'),required=False,label='Exact recorded preauthorization',empty_label='Not recorded or not selected')
        self.fields['authorization_id'].label_from_instance=lambda a:f'{a.profile.version.change.reference} · preauthorization {a.pk} · {a.created_at.isoformat()}'
        self.fields['outcome_id']=forms.ModelChoiceField(queryset=EmergencyOutcome.objects.filter(profile__in=profiles).select_related('profile__version__change').order_by('-pk'),required=False,label='Actual recorded implementation',empty_label='Not recorded or not selected')
        self.fields['outcome_id'].label_from_instance=lambda o:f'{o.profile.version.change.reference} · outcome {o.pk} · actual {o.implemented_at.isoformat()}'
        self.fields['template_id']=forms.ModelChoiceField(queryset=Template.objects.filter(case=case,definition__document_type__in=['project_artifact','status_report']),required=False,label='Controlled retrospective template')
        self.fields['audience']=forms.ChoiceField(choices=[('client','Client'),('internal','Internal')],label='Explicit report audience')
    def inputs(self):return {**{k:self.cleaned_data[k].pk if self.cleaned_data[k] else None for k in ['template_id','authorization_id','outcome_id']},'audience':self.cleaned_data['audience']}

class StartForm(forms.Form):
    definition=forms.CharField(initial=emergency.DEFINITION,widget=forms.HiddenInput)
    key=forms.CharField(max_length=100,widget=forms.HiddenInput)
    case=forms.ModelChoiceField(queryset=Case.objects.none(),label='Project')
    reference=forms.CharField(max_length=160,label='Describe the Emergency evidence work')
    revision=forms.IntegerField(min_value=1,widget=forms.HiddenInput)
    def __init__(self,actor,*args,case_id=None,**kwargs):
        super().__init__(*args,**kwargs)
        cases=granted(actor,['emergency.read','factory.start','evidence.add']).filter(kind='project');self.fields['case'].queryset=cases;self.fields['case'].label_from_instance=workspace_name
        self.selected=cases.filter(pk=case_id).first() if case_id else None
        if self.selected:self.fields['case'].initial=self.selected;self.fields['revision'].initial=self.selected.revision
        if not self.is_bound:self.fields['key'].initial='EMERGENCY-'+uuid4().hex

class OutcomeForm(forms.Form):
    implemented_at=forms.DateTimeField(label='Actual past implementation time',widget=forms.DateTimeInput(attrs={'type':'datetime-local','step':'1'}))

@require_http_methods(['GET','HEAD','POST'])
def create(request):
    case_id=request.POST.get('case') if request.method=='POST' else request.GET.get('case')
    try:form=StartForm(request.user,request.POST if request.method=='POST' else None,case_id=case_id)
    except (ValidationError,ValueError):form=StartForm(request.user,data={});form.is_valid();form.add_error(None,'Choose an available project')
    inputs=InputsForm(form.selected,request.POST if request.method=='POST' else None) if form.selected else None
    if request.method=='POST' and form.is_valid() and inputs and inputs.is_valid():
        try:
            d=form.cleaned_data
            if d['definition']!=emergency.DEFINITION:raise ValidationError('Choose the registered Emergency definition')
            w=emergency.start(request.user,d['case'].pk,d['key'],inputs.cleaned_data['profile_id'].pk,inputs.inputs(),d['reference'],d['revision']);return redirect('factory_detail',w.pk)
        except ValidationError as exc:form.add_error(None,emergency.finding(exc))
    return render(request,'factory/emergency_start.html',{'form':form,'inputs_form':inputs,'case':form.selected})

@require_http_methods(['GET','HEAD','POST'])
def detail(request,work):
    from .factory_views import presentation,permitted
    p,data=emergency.source(work,request.user,False)
    form=InputsForm(work.case,request.POST if request.method=='POST' and request.POST.get('action')=='correct' else None,change_id=p.version.change_id,initial=dict(data['inputs'],profile_id=p.pk))
    actual_form=OutcomeForm(request.POST if request.method=='POST' and request.POST.get('action')=='capture_outcome' else None)
    if request.method=='POST':
        try:
            d=request.POST;action=d.get('action');revision=int(d.get('revision','0'));case_revision=int(d.get('case_revision','0'))
            if action=='advance':factory.advance(request.user,work.pk,revision)
            elif action=='correct':
                if not form.is_valid():raise ValidationError('Choose exact native Emergency sources')
                emergency.correct(request.user,work.pk,revision,case_revision,form.cleaned_data['profile_id'].pk,form.inputs(),d.get('reason',''))
            elif action=='review':emergency.review(request.user,work.pk,revision,case_revision,int(d.get('version','0')),d.get('verdict',''),d.get('note',''))
            elif action in ['preauthorization_decision','authorize','capture_outcome','record_review','retrospective_decision','reconcile_retrospective']:
                values={'note':d.get('note',''),'evidence':int(d.get('evidence','0')),'role':d.get('role',''),'authority_role':d.get('authority_role',''),'verdict':d.get('verdict','')}
                if action=='capture_outcome':
                    if not actual_form.is_valid():raise ValidationError('Provide the actual implementation timestamp in the displayed time zone')
                    values['implemented_at']=actual_form.cleaned_data['implemented_at']
                emergency.human_action(request.user,work.pk,revision,case_revision,int(d.get('profile','0')),action,values)
            elif action=='cancel':emergency.cancel(request.user,work.pk,revision)
            elif action=='restart':emergency.restart(request.user,work.pk,revision,case_revision,d.get('reason',''))
            elif action=='resume':factory.manage(request.user,work.pk,revision,'resume')
            elif action=='reconcile':emergency.reconcile(request.user,work.pk,revision)
            elif action=='operate_delivery':emergency.operate(request.user,work.pk,revision,case_revision,int(d.get('job','0')),d.get('operation',''),d.get('reason',''))
            elif action=='adopt_profile':factory.adopt_profile(request.user,work.pk,revision,int(d.get('configuration','0')),d.get('reason',''))
            else:raise ValidationError('Choose a current native Emergency action')
            messages.success(request,'Emergency evidence action recorded. Select newly recorded native references explicitly when needed.');return redirect(request.get_full_path())
        except (ValidationError,ValueError) as exc:messages.error(request,str(exc));work.refresh_from_db();work.case.refresh_from_db()
    row=presentation(request.user,work)
    return render(request,'factory/emergency_detail.html',{'row':row,'case':work.case,'inputs_form':form,'outcome_form':actual_form,'time_zone':timezone.get_current_timezone_name(),'evidence':public_evidence(Evidence.objects.filter(case=work.case)).order_by('-pk'),'can_configure':permitted(request.user,work,'policy.configure'),'activities':work.activities.order_by('pk')})

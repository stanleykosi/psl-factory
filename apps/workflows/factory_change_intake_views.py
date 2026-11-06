"""Request-first P56 console. Confirmation is PM classification, never approval."""
from uuid import uuid4
from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied,ValidationError
from django.http import Http404
from django.shortcuts import render,redirect
from django.views.decorators.http import require_http_methods
from apps.core.models import Audit,Evidence
from apps.core.views import accessible_case
from apps.documents.models import Template
from apps.pmo.models import ChangeVersion
from . import factory_change_intake as intake

class ReceiveForm(forms.Form):
    key=forms.CharField(max_length=100,widget=forms.HiddenInput)
    case_revision=forms.IntegerField(min_value=1,widget=forms.HiddenInput)
    body=forms.CharField(max_length=16000,strip=False,label='Original change request',widget=forms.Textarea(attrs={'rows':12}))
    origin=forms.CharField(max_length=500,strip=False,label='Where the request came from')
    def __init__(self,case,*args,**kwargs):
        super().__init__(*args,**kwargs)
        if not self.is_bound:self.initial.update(key='P56-'+uuid4().hex,case_revision=case.revision)

class ConfirmForm(forms.Form):
    case_revision=forms.IntegerField(min_value=1,widget=forms.HiddenInput)
    extraction_id=forms.IntegerField(min_value=1,required=False,widget=forms.HiddenInput)
    reference=forms.CharField(max_length=160,label='CR reference')
    requestor=forms.CharField(max_length=160,label='Original requestor')
    date_raised=forms.DateField(input_formats=['%Y-%m-%d'],label='Original date raised',widget=forms.DateInput(attrs={'type':'date'}))
    module=forms.CharField(max_length=160,label='Affected module')
    description=forms.CharField(max_length=4000,widget=forms.Textarea(attrs={'rows':3}))
    reason=forms.CharField(max_length=4000,widget=forms.Textarea(attrs={'rows':3}))
    category=forms.ChoiceField(choices=[('','Select the PM classification')]+[(v,v) for v in ['Standard','Normal','Emergency']])
    category_basis=forms.CharField(max_length=2000,label='PM classification basis',widget=forms.Textarea(attrs={'rows':2}))
    note=forms.CharField(max_length=2000,label='PM field confirmation or corrections',widget=forms.Textarea(attrs={'rows':2}))
    def __init__(self,case,panel,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.fields['incident_id']=forms.ModelChoiceField(queryset=Evidence.objects.filter(case=case,kind='incident'),required=False,label='Incident evidence (required for Emergency)')
        self.fields['template_id']=forms.ModelChoiceField(queryset=Template.objects.filter(case=case,definition__document_type__in=['project_artifact','status_report']),required=False,label='Controlled change template (can be supplied later)')
        self.fields['predecessor_version_id']=forms.ModelChoiceField(queryset=ChangeVersion.objects.filter(change__case=case).select_related('change').order_by('-pk'),required=False,label='Existing exact CR revision (only when explicitly revising that request)')
        self.fields['predecessor_version_id'].label_from_instance=lambda v:f'{v.change.reference} · {v.category} · revision {v.number}'
        if not self.is_bound:
            self.initial.update(case_revision=case.revision)
            if panel['run']:
                r=panel['run'];self.initial.update(extraction_id=r.pk,**{k:v['value'] or '' for k,v in r.result['fields'].items()})
                self.initial['category']=r.result['category']['suggestion'] or ''
    def fields_payload(self):
        d=self.cleaned_data
        return {k:(d[k].pk if d[k] else None) if k in ['incident_id','template_id','predecessor_version_id'] else d[k].isoformat() if k=='date_raised' else d[k] for k in intake.FIELDS}

def page(response):response['Cache-Control']='no-store';return response

def scope(request,case_id):
    case=accessible_case(request.user,case_id)
    try:intake.readable(request.user,case)
    except PermissionDenied:raise Http404() from None
    return case

@login_required
@require_http_methods(['GET','HEAD','POST'])
def create(request,case_id):
    case=scope(request,case_id)
    data=request.POST.copy() if request.method=='POST' else None
    refreshing=data is not None and data.get('action')=='refresh'
    if refreshing:
        data['case_revision']=case.revision
        messages.info(request,'Current project refreshed. Review the retained request before submitting it.')
    form=ReceiveForm(case,data)
    if request.method=='POST' and not refreshing and form.is_valid():
        try:
            d=form.cleaned_data;r=intake.receive(request.user,case.pk,d['key'],d['body'],d['origin'],d['case_revision'])
            return redirect('p56_intake_detail',case.pk,r.pk)
        except (ValidationError,PermissionDenied) as exc:form.add_error(None,str(exc));case.refresh_from_db()
    rows=Audit.objects.filter(case=case,action=intake.RECEIVED).order_by('-pk')[:50]
    return page(render(request,'factory/change_intake_start.html',{'case':case,'form':form,'receipts':rows}))

@login_required
@require_http_methods(['GET','HEAD','POST'])
def detail(request,case_id,receipt_id):
    case=scope(request,case_id)
    try:r=intake.receipt_for(request.user,case,receipt_id)
    except (ValidationError,PermissionDenied):raise Http404() from None
    panel=intake.projection(request.user,r)
    action=request.POST.get('action') if request.method=='POST' else None
    data=request.POST.copy() if request.method=='POST' else None
    if action in ['refresh','refresh_correction']:
        data['case_revision']=case.revision
        if action=='refresh':data['extraction_id']=panel['run'].pk if panel['run'] else ''
        messages.info(request,'Current record refreshed. Review the source and retained edits before recording any change.')
    form=ConfirmForm(case,panel,data if action in ['confirm','refresh'] else None)
    correction=ReceiveForm(case,data if action in ['correct','refresh_correction'] else None,initial={'body':panel['source'].body,'origin':panel['source'].source})
    if request.method=='POST' and action not in ['refresh','refresh_correction']:
        try:
            p=request.POST;action=p.get('action');expected=int(p.get('case_revision','0'))
            if action=='extract':
                run=intake.extract_once(request.user,case.pk,r.pk,expected)
                messages.success(request,'Extraction retained. PM classification is still required.' if run else 'Extraction could not be validated. The original request is retained; correct it or enter the fields as PM.')
            elif action=='confirm':
                if not form.is_valid():raise ValidationError('Complete the PM classification fields below')
                d=form.cleaned_data;binding=intake.confirm(request.user,case.pk,r.pk,d['extraction_id'],form.fields_payload(),d['note'],expected)
                if binding.work_id:return redirect('factory_detail',binding.work_id)
                messages.success(request,'PM classification recorded. Continue through the indicated native change route.')
            elif action=='correct':
                if not correction.is_valid():raise ValidationError('Supply the corrected source and its origin')
                d=correction.cleaned_data;successor=intake.receive(request.user,case.pk,d['key'],d['body'],d['origin'],d['case_revision'],r.pk,p.get('correction_reason',''))
                return redirect('p56_intake_detail',case.pk,successor.pk)
            elif action=='cancel':intake.cancel(request.user,case.pk,r.pk,expected,p.get('stop_reason',''))
            else:raise ValidationError('Choose a current intake action')
            return redirect('p56_intake_detail',case.pk,r.pk)
        except (ValidationError,PermissionDenied,ValueError) as exc:
            messages.error(request,str(exc));case.refresh_from_db();r.case=case;panel=intake.projection(request.user,r)
    return page(render(request,'factory/change_intake_detail.html',{'case':case,'panel':panel,'form':form,'correction_form':correction,'correction_reason':request.POST.get('correction_reason','')}))

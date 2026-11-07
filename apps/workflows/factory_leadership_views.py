"""Typed selected P40/P42 intake and explicit owner configuration drafts."""
import json
from uuid import uuid4
from django import forms
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import transaction
from django.shortcuts import render,redirect
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from apps.core.models import Evidence
from apps.core.evidence_access import public_evidence,forecast_private_query
from apps.core.services import add_evidence,lock_case
from apps.pmo.forms import OffsetTimestamp
from apps.pmo import leadership_reporting as native
from apps.pmo.leadership_report_views import LeadershipReportForm
from . import factory,factory_leadership as reporting
from .factory_reporting_views import ReportingProfileForm as WeeklyProfile,StartForm as WeeklyStart

class ReportingProfileForm(WeeklyProfile):
    def __init__(self,case,*args,**kwargs):
        super().__init__(case,*args,**kwargs)
        from django.contrib.auth import get_user_model
        users=get_user_model().objects.filter(is_active=True)
        for action in ['case.read','report.read','factory.execute','report.draft','document.draft','evidence.add']:
            users=users.filter(grant__case=case,grant__active=True,grant__action=action)
        self.fields['preparer_id'].queryset=users.distinct()
        self.fields['preparer_id'].label='Existing internal report preparer'
        self.fields['executor_id'].label='Authorized internal publisher'
        self.fields['required_evidence_kinds'].initial=reporting.KIND

class ReviewRoleForm(forms.Form):
    role=forms.ChoiceField(choices=[('','Not supplied'),('PMO Lead','PMO Lead'),('Head of PMO','Head of PMO')],required=False,label='Owner-selected existing D05 leadership role')
    evidence=forms.ModelChoiceField(queryset=Evidence.objects.none(),label='Owner policy decision')
    effective_from=OffsetTimestamp(label='Effective timestamp with offset')
    def __init__(self,case,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.fields['evidence'].queryset=public_evidence(Evidence.objects.filter(case=case,kind='policy_decision'))
        self.fields['effective_from'].initial=timezone.now().isoformat()

class AudienceForm(ReviewRoleForm):
    role=None
    purpose=forms.ChoiceField(choices=[(key,key.replace('_',' ')) for key in native.AUDIENCE_PURPOSES],label='Report participant purpose')
    participants=forms.ModelMultipleChoiceField(queryset=Evidence.objects.none(),required=False,label='Actual owner-designated participants',help_text='Empty means unknown and holds delivery. This does not infer PMO membership or appoint a role.')
    def __init__(self,case,*args,**kwargs):
        super().__init__(case,*args,**kwargs)
        from django.contrib.auth import get_user_model
        self.fields['participants'].queryset=get_user_model().objects.filter(is_active=True,grant__case=case,grant__active=True,grant__action__in=['document.receive:internal','document.receive:management']).distinct()


class InputsForm(LeadershipReportForm):
    def __init__(self,case,*args,actor,kind='internal_tuesday',**kwargs):
        initial=dict(kwargs.pop('initial',{}) or {});kind=initial.get('kind',kind)
        initial.update({'source_'+key:ids for key,ids in initial.get('selections',{}).items()});initial['template']=initial.get('template_id')
        super().__init__(actor,case,kind,*args,initial=initial,**kwargs)
        self.fields.pop('revision')
        self.fields['kind']=forms.ChoiceField(choices=[(key,key) for key in native.THEMES],initial=kind,widget=forms.HiddenInput)
        self.fields['template'].required=False
        self.fields['content_id']=forms.ModelChoiceField(queryset=Evidence.objects.filter(case=case,kind=native.CONTENT).exclude(forecast_private_query()),required=False,label='Existing cited narrative, or enter all themes below')
        for key in native.THEMES[kind]:
            for field in [key,key+'_coverage',key+'_citations']:self.fields[field].required=False
    def inputs(self,actor,case):
        d=self.cleaned_data
        if d['kind']!=self.kind:raise ValidationError('Different report purpose requires separate work')
        pk=d['content_id'].pk if d['content_id'] else None
        if any(d[key].strip() or d[key+'_coverage'] or d[key+'_citations'] for key in native.THEMES[self.kind]):
            if pk or any(not d[key].strip() or not d[key+'_coverage'] or not d[key+'_citations'] for key in native.THEMES[self.kind]):raise ValidationError('Select existing narrative or supply every cited theme')
            body=json.dumps(self.narrative(),sort_keys=True)
            pk=(Evidence.objects.filter(case=case,kind=native.CONTENT,body=body,created_by=actor).order_by('-pk').first() or add_evidence(actor,case.pk,native.CONTENT,body,'Human-supplied leadership narrative')).pk
        return {'kind':self.kind,'audience':d['audience'],'start_at':d['start_at'].isoformat(),'end_at':d['end_at'].isoformat(),'template_id':d['template'].pk if d['template'] else None,'content_id':pk,'selections':self.selections()}

class StartForm(WeeklyStart):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.fields['definition'].initial=reporting.DEFINITION
        self.fields['reference'].label='Describe this internal reporting work'
        if not self.is_bound:self.fields['key'].initial='LEADERSHIP-'+uuid4().hex

@require_http_methods(['GET','HEAD','POST'])
def create(request):
    data=request.POST if request.method=='POST' else request.GET;kind=data.get('kind','internal_tuesday')
    if kind not in native.THEMES:raise ValidationError('Choose Tuesday internal or monthly executive reporting')
    try:form=StartForm(request.user,request.POST if request.method=='POST' else None,case_id=data.get('case'))
    except (ValidationError,ValueError):form=StartForm(request.user,data={});form.is_valid();form.add_error(None,'Choose an available project')
    inputs=InputsForm(form.selected,request.POST if request.method=='POST' else None,actor=request.user,kind=kind) if form.selected else None
    if request.method=='POST' and form.is_valid() and inputs and inputs.is_valid():
        try:
            with transaction.atomic():
                d=form.cleaned_data
                if d['definition']!=reporting.DEFINITION:raise ValidationError('Choose leadership reporting')
                case=lock_case(request.user,d['case'].pk,'factory.start',d['revision']);values=inputs.inputs(request.user,case);case.refresh_from_db()
                work=reporting.start(request.user,case.pk,d['key'],values,d['reference'],case.revision)
            return redirect('factory_detail',work.pk)
        except ValidationError as exc:form.add_error(None,reporting.finding(exc))
    return render(request,'factory/leadership_start.html',{'form':form,'inputs_form':inputs,'case':form.selected,'kind':kind})

@require_http_methods(['GET','HEAD','POST'])
def detail(request,work):
    from .factory_views import presentation,permitted
    data=reporting.source(work,request.user,False)
    audience_form=AudienceForm(work.case,request.POST if request.method=='POST' and request.POST.get('action')=='draft_audience' else None)
    role_form=ReviewRoleForm(work.case,request.POST if request.method=='POST' and request.POST.get('action')=='draft_review_role' else None)
    form=InputsForm(work.case,request.POST if request.method=='POST' and request.POST.get('action')=='correct' else None,initial=data['inputs'],actor=request.user)
    if request.method=='POST':
        try:
            d=request.POST;action=d.get('action');revision=int(d.get('revision','0'));case_revision=int(d.get('case_revision','0'))
            if action=='draft_audience':
                if not audience_form.is_valid():raise ValidationError(audience_form.errors.as_text())
                from apps.policy.operator_drafts import draft_operator_policy
                from apps.policy.services import active_component,reference_values
                with transaction.atomic():
                    case=lock_case(request.user,work.case_id,'policy.configure',case_revision);values=audience_form.cleaned_data
                    try:current=reference_values(active_component(native.AUDIENCE_COMPONENT,case))[0]
                    except ValidationError:current={key:None for key in native.AUDIENCE_PURPOSES}
                    current=dict(current);current[values['purpose']]=sorted(u.pk for u in values['participants']) or None
                    draft_operator_policy(request.user,case.pk,native.AUDIENCE_COMPONENT,current,values['evidence'].pk,values['effective_from'])
            elif action=='draft_review_role':
                if work.request['kind']!='monthly_executive' or not role_form.is_valid():raise ValidationError('Select an owner-evidenced monthly leadership review role')
                from apps.policy.operator_drafts import draft_operator_policy
                with transaction.atomic():
                    case=lock_case(request.user,work.case_id,'policy.configure',case_revision);values=role_form.cleaned_data
                    draft_operator_policy(request.user,case.pk,native.REVIEW_COMPONENT,{'role':values['role'] or None},values['evidence'].pk,values['effective_from'])
            elif action=='advance':factory.advance(request.user,work.pk,revision)
            elif action=='correct':
                if not form.is_valid():raise ValidationError(form.errors.as_text())
                with transaction.atomic():
                    case=lock_case(request.user,work.case_id,'factory.manage',case_revision);values=form.inputs(request.user,case);case.refresh_from_db()
                    reporting.correct(request.user,work.pk,revision,case.revision,values,d.get('reason',''))
            elif action=='review':reporting.review(request.user,work.pk,revision,case_revision,int(d.get('version','0')),d.get('verdict',''),d.get('note',''))
            elif action=='cancel':reporting.cancel(request.user,work.pk,revision)
            elif action=='restart':reporting.restart(request.user,work.pk,revision,case_revision,d.get('reason',''))
            elif action=='resume':factory.manage(request.user,work.pk,revision,'resume')
            elif action=='reconcile':reporting.reconcile(request.user,work.pk,revision)
            elif action=='operate_delivery':reporting.operate(request.user,work.pk,revision,case_revision,int(d.get('job','0')),d.get('operation',''),d.get('reason',''))
            elif action=='adopt_profile':factory.adopt_profile(request.user,work.pk,revision,int(d.get('configuration','0')),d.get('reason',''))
            else:raise ValidationError('Choose a current leadership report action')
            messages.success(request,'Leadership report action recorded.');return redirect(request.get_full_path())
        except (ValidationError,ValueError) as exc:messages.error(request,str(exc));work.refresh_from_db();work.case.refresh_from_db()
    row=presentation(request.user,work)
    return render(request,'factory/leadership_detail.html',{'row':row,'case':work.case,'inputs_form':form,'role_form':role_form,'audience_form':audience_form,'can_configure':permitted(request.user,work,'policy.configure'),'activities':work.activities.order_by('pk')})

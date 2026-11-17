"""Work-centric forecast UI. All human commands retain native authority checks."""
from uuid import uuid4
from django import forms
from django.contrib import messages
from django.core.exceptions import ValidationError, PermissionDenied
from django.shortcuts import render, redirect
from django.views.decorators.http import require_http_methods
from apps.core.models import Case, Evidence
from apps.core.workbench import granted
from apps.documents.models import Template
from apps.finance.models import ForecastScenario
from apps.finance import group_forecast
from apps.finance.forecast_forms import commands
from . import factory, factory_forecast as service
from .factory_progress_views import StartWithBackground, start_work
from apps.finance.forecast_workbook import source_ids as workbook_source_ids
from .factory_forecast_sources import PROTOCOL


class InputsForm(forms.Form):
    as_of = forms.DateField(label='Exact selected scenario as-of date')
    months = forms.JSONField(label='Exact ordered month horizon', help_text='For example ["2026-11", "2026-12"]. Must equal the selected native scenario.')
    audience = forms.ChoiceField(choices=[('internal','Internal aggregate'),('management','Management aggregate'),('group','Separate owner-permitted group report')])

    def __init__(self, case, *args, scenario_reference=None, **kwargs):
        super().__init__(*args, **kwargs)
        scenarios=ForecastScenario.objects.filter(case=case)
        if scenario_reference:scenarios=scenarios.filter(reference=scenario_reference)
        self.fields['scenario_id']=forms.ModelChoiceField(queryset=scenarios.order_by('-pk'),label='Exact native scenario revision')
        self.fields['source_ids']=forms.ModelMultipleChoiceField(queryset=Evidence.objects.filter(case=case,pk__in=set(e for s in scenarios for e in [s.evidence_id]+[r['evidence_id'] for r in s.payload['openings']+s.payload['items']]+list(workbook_source_ids(s)))),label='Complete selected scenario, opening and assumption evidence')
        self.fields['template_id']=forms.ModelChoiceField(queryset=Template.objects.filter(case=case,definition__document_type__in=['finance_report','finance_group_report']),required=False,label='Aggregate forecast report template')

    def selection(self):
        d=self.cleaned_data
        return {'protocol':PROTOCOL,'scenario_id':d['scenario_id'].pk,'as_of':d['as_of'].isoformat(),'months':d['months'],'source_ids':sorted(e.pk for e in d['source_ids']),'template_id':d['template_id'].pk if d['template_id'] else None,'audience':d['audience']}


class StartForm(StartWithBackground):
    definition=forms.CharField(initial=service.DEFINITION,widget=forms.HiddenInput)
    key=forms.CharField(max_length=100,widget=forms.HiddenInput)
    case=forms.ModelChoiceField(queryset=Case.objects.none(),label='Engagement')
    reference=forms.CharField(max_length=160,label='Describe the forecast work')
    revision=forms.IntegerField(min_value=1,widget=forms.HiddenInput)

    def __init__(self, actor, *args, case_id=None, **kwargs):
        super().__init__(*args, **kwargs)
        cases=granted(actor,['finance.read','factory.start','evidence.add'])
        self.fields['case'].queryset=cases
        self.selected=cases.filter(pk=case_id).first() if case_id else None
        if self.selected:self.fields['case'].initial=self.selected;self.fields['revision'].initial=self.selected.revision
        if not self.is_bound:self.fields['key'].initial='FORECAST-'+uuid4().hex


@require_http_methods(['GET','HEAD','POST'])
def create(request):
    case_id=request.POST.get('case') if request.method=='POST' else request.GET.get('case')
    try:form=StartForm(request.user,request.POST if request.method=='POST' else None,case_id=case_id)
    except (ValidationError,ValueError):form=StartForm(request.user,data={});form.is_valid();form.add_error(None,'Choose an available engagement')
    inputs=InputsForm(form.selected,request.POST if request.method=='POST' else None) if form.selected else None
    if request.method=='POST' and form.is_valid() and inputs and inputs.is_valid():
        try:
            d=form.cleaned_data
            if d['definition']!=service.DEFINITION:raise ValidationError('Choose the registered forecast definition')
            return start_work(request, lambda: service.start(request.user, d['case'].pk, d['key'],
                              inputs.selection(), d['reference'], d['revision']), d['background'])
        except ValidationError as exc:form.add_error(None,service.finding(exc))
    return render(request,'factory/forecast_start.html',{'form':form,'inputs_form':inputs,'case':form.selected})


@require_http_methods(['GET','HEAD','POST'])
def detail(request,work,focus=None):
    from .factory_views import QUEUES,presentation,permitted
    from .screen_focus import SCREENS,require_action
    from .factory_progress import set_progress
    queue=request.GET.get('queue','needs_me')
    if queue not in QUEUES:queue='needs_me'
    query=request.GET.get('q','')[:120]
    scenario,selected=service.source(work,request.user,False)
    inputs=InputsForm(work.case,request.POST if request.method=='POST' and request.POST.get('action') in ['correct','restart'] else None,scenario_reference=scenario.reference,initial=selected)
    human_actions={'support','actual','verify','match','unmatch','review','priority','group_review'}
    forms_list=[r for r in commands(work.case,request.POST if request.method=='POST' else None) if r['action'] in human_actions]
    pin=service.observed(work,'forecast_run')
    for entry in forms_list:
        f=entry['form']
        if 'version' in f.fields:
            binding=service.document(work)
            f.fields['version'].queryset=f.fields['version'].queryset.filter(pk=binding.version_id if binding and selected['audience']=='group' else None)
        if 'run' in f.fields:f.fields['run'].queryset=f.fields['run'].queryset.filter(pk=pin)
        if 'scenario' in f.fields:f.fields['scenario'].queryset=f.fields['scenario'].queryset.filter(pk=scenario.pk)
        if 'match' in f.fields:f.fields['match'].queryset=f.fields['match'].queryset.filter(root_id=service.forecast.root_of(scenario).pk)
    if request.method=='POST':
        try:
            p=request.POST;action=p.get('action');revision=int(p.get('work_revision',p.get('revision','0')));case_revision=int(p.get('case_revision',p.get('revision','0')))
            require_action(work,focus,action)
            if action=='advance':set_progress(request.user,work.pk,revision,True)
            elif action=='correct':
                if not inputs.is_valid():raise ValidationError('Choose exact scenario, horizon and complete source inventory')
                service.correct(request.user,work.pk,revision,case_revision,inputs.selection(),p.get('reason',''))
            elif action=='restart':
                if not inputs.is_valid():raise ValidationError('Choose exact current scenario, horizon and source inventory')
                service.restart(request.user,work.pk,revision,case_revision,inputs.selection(),int(p.get('configuration','0')),p.get('reason',''))
            elif action in human_actions:
                form=next(r['form'] for r in forms_list if r['action']==action)
                if not form.is_valid():raise ValidationError(form.errors.as_text())
                service.human_action(request.user,work.pk,revision,form.cleaned_data['revision'],int(p.get('selected_scenario','0')),action,form.cleaned_data)
            elif action=='group_rules':
                from apps.finance.group_disclosure_forms import save
                if selected['audience']!='group' or work.revision!=revision:
                    raise ValidationError('Review the current group forecast work before changing disclosure rules.')
                run=service.calculation(work,request.user)
                if run is None:raise ValidationError('Review a forecast calculation before selecting group disclosure.')
                save(request.user,work.case,run,p,case_revision)
            elif action=='cancel':service.cancel(request.user,work.pk,revision)
            elif action=='resume':factory.manage(request.user,work.pk,revision,'resume')
            elif action=='reconcile':service.reconcile(request.user,work.pk,revision)
            elif action=='operate_delivery':service.operate(request.user,work.pk,revision,case_revision,int(p.get('job','0')),p.get('operation',''),p.get('reason',''))
            elif action=='adopt_profile':factory.adopt_profile(request.user,work.pk,revision,int(p.get('configuration','0')),p.get('reason',''))
            else:raise ValidationError('Choose a current forecast work action')
            messages.success(request,'Forecast action recorded');return redirect(request.get_full_path())
        except (ValidationError,ValueError) as exc:
            messages.error(request,' '.join(exc.messages) if isinstance(exc,ValidationError) else 'Review the current recorded references.')
            work.refresh_from_db();work.case.refresh_from_db()
    row=presentation(request.user,work)
    if focus:
        forms_list=[entry for entry in forms_list if entry['action'] in SCREENS[work.definition][focus]]
        if focus=='decision':
            forms_list=[entry for entry in forms_list if
                        (entry['action']!='review' or row['forecast']['review_roles']) and
                        (entry['action']!='group_review' or row['forecast']['group_disclosure'])]
    group_table=None
    group_rules_form=None
    if selected['audience']=='group' and focus in (None,'decision') and permitted(request.user,work,'policy.configure'):
        from apps.finance.group_disclosure_forms import GroupDisclosureForm
        from apps.policy.services import active_component
        try:
            run=service.calculation(work,request.user)
            if run:
                service.forecast.approved(run)
                configuration=active_component('D10.audience_projection_rules',work.case)
                group_rules_form=GroupDisclosureForm(request.user,work.case,run,configuration,
                    request.POST if request.method=='POST' and request.POST.get('action')=='group_rules' else None)
        except (ValidationError,PermissionDenied):
            pass
    binding=row['forecast']['document']
    if binding and binding.version.audience=='group' and focus in (None,'decision'):
        try:
            projected=group_forecast.check_content(binding)
        except ValidationError:
            forms_list=[entry for entry in forms_list if entry['action']!='group_review']
        else:
            headers=binding.snapshot['projection']['fields']
            group_table={'headers':headers,'rows':[[item[name] for name in headers] for item in projected['rows']],
                         'metadata':projected['metadata']}
    return render(request,'factory/forecast_detail.html',{'row':row,'case':work.case,'focus':focus,'queue':queue,'q':query,
        'group_table':group_table,
        'group_rules_form':group_rules_form,
        'inputs_form':inputs,'commands':forms_list,'activities':work.activities.prefetch_related('attempts').order_by('pk') if not focus else (),
        'can_configure':permitted(request.user,work,'policy.configure')})


from .factory_views import ProfileForm
from django.contrib.auth import get_user_model

class ForecastProfileForm(ProfileForm):
    def __init__(self, case, *args, **kwargs):
        super().__init__(case, *args, **kwargs)
        people=get_user_model().objects.filter(is_active=True)
        for action in ['case.read','finance.read','factory.execute','finance.forecast.calculate','finance.publish','document.draft']:
            people=people.filter(grant__case=case,grant__active=True,grant__action=action)
        self.fields['preparer_id']=forms.ModelChoiceField(queryset=people.distinct(),required=False,label='Existing native forecast preparer')
        self.fields['information_resolver_id'].widget=forms.HiddenInput()
        self.fields['information_resolver_id'].disabled=True
        self.fields['executor_id'].label='Aggregate forecast publisher'
        for action in ['case.read','finance.read','document.publish']:
            self.fields['executor_id'].queryset=self.fields['executor_id'].queryset.filter(grant__case=case,grant__active=True,grant__action=action).distinct()

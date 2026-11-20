"""Primary selected schedule work console; native services own every decision and result."""
from uuid import uuid4
from django import forms
from django.contrib import messages
from django.core.exceptions import ValidationError,PermissionDenied
from django.shortcuts import render,redirect
from django.views.decorators.http import require_http_methods
from django.views.decorators.cache import never_cache
from apps.core.models import Case,Evidence
from apps.core.evidence_access import public_evidence
from apps.core.workbench import granted
from apps.finance import schedules
from apps.finance.models import ScheduleWork,FinanceRun
from . import factory,factory_schedules as domain
from .factory_progress import set_progress
from .factory_progress_views import StartWithBackground, start_work


class DuplicateResolutionForm(forms.Form):
    target = forms.IntegerField(min_value=1, widget=forms.HiddenInput)
    evidence = forms.ModelChoiceField(queryset=Evidence.objects.none(), label='Finance proof for these checks')
    reason = forms.CharField(max_length=2000, widget=forms.Textarea, label='Explain these choices')

    def __init__(self, case, schedule, rows, data=None):
        super().__init__(data, initial={'target': schedule.pk}, auto_id='id_duplicate_%s')
        self.fields['evidence'].queryset = public_evidence(
            Evidence.objects.filter(case=case, kind='finance_review')).order_by('-pk')
        self.rows = []
        for index, row in enumerate(rows):
            field = f'treatment_{index}'
            self.fields[field] = forms.ChoiceField(label=f'Duplicate check for {row["key"]}', choices=[
                ('', 'Choose a treatment'), ('already_represented', 'Already in the accounts'),
                ('separately_justified', 'Separately justified'),
            ])
            self.rows.append((row, self[field]))

    def choices(self):
        return {row['key']: self.cleaned_data[field.name] for row, field in self.rows}


class ScheduleOverrideField(forms.JSONField):
    def prepare_value(self, value):
        return '' if value is None else super().prepare_value(value)


class InputsForm(forms.Form):
    kind=forms.ChoiceField(choices=[('income','Income detail'),('inventory','Selected schedule inventory')])
    payload=ScheduleOverrideField(required=False,widget=forms.Textarea,label='Reviewed income detail override')
    def __init__(self,case,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.fields['parent_id']=forms.ModelChoiceField(queryset=FinanceRun.objects.filter(case=case,kind='mapping').order_by('-pk'),required=False,label='Exact mapping note (income only)')
        self.fields['evidence_id']=forms.ModelChoiceField(queryset=Evidence.objects.filter(case=case,kind__in=['income_detail','schedule_inventory']).order_by('-pk'),label='Exact supplied evidence')
    def ids(self):
        d=self.cleaned_data
        return [d['kind'],d['parent_id'].pk if d['parent_id'] else None,d['evidence_id'].pk,d['payload']]

class StartForm(StartWithBackground):
    definition=forms.CharField(initial=domain.DEFINITION,widget=forms.HiddenInput)
    key=forms.CharField(max_length=100,widget=forms.HiddenInput)
    case=forms.ModelChoiceField(queryset=Case.objects.none())
    reference=forms.RegexField(r'^[A-Za-z0-9][A-Za-z0-9_.:-]{0,99}$',label='Stable schedule reference')
    revision=forms.IntegerField(min_value=1,widget=forms.HiddenInput)
    def __init__(self,actor,*args,case_id=None,**kwargs):
        super().__init__(*args,**kwargs);cases=granted(actor,['factory.start','finance.read','schedules.read','evidence.add']);self.fields['case'].queryset=cases
        self.selected=cases.filter(pk=case_id).first() if case_id else None
        if self.selected:self.fields['case'].initial=self.selected;self.fields['revision'].initial=self.selected.revision
        if not self.is_bound:self.fields['key'].initial='schedule-'+uuid4().hex

@never_cache
@require_http_methods(['GET','HEAD','POST'])
def create(request):
    data=request.POST if request.method=='POST' else None
    try:form=StartForm(request.user,data,case_id=(data or request.GET).get('case'))
    except (ValueError,ValidationError):form=StartForm(request.user,data={});form.is_valid();form.add_error(None,'Choose an available case')
    inputs=InputsForm(form.selected,data) if form.selected else None
    if request.method=='POST' and form.is_valid() and inputs and inputs.is_valid():
        try:
            d=form.cleaned_data
            if d['definition']!=domain.DEFINITION or set(request.POST)-set(form.fields)-set(inputs.fields)-{'csrfmiddlewaretoken'}:raise ValidationError('Exact typed schedule command required')
            return start_work(request, lambda: domain.start(request.user, d['case'].pk, d['key'],
                              *inputs.ids(), d['reference'], d['revision']), d['background'])
        except ValidationError as exc:form.add_error(None,domain.finding(exc))
    return render(request,'factory/schedules_start.html',{'form':form,'inputs_form':inputs,'case':form.selected})

@never_cache
@require_http_methods(['GET','HEAD','POST'])
def detail(request,work,focus=None):
    from .factory_execution import can_control
    from .factory_views import QUEUES, presentation,permitted
    from .screen_focus import require_action
    queue = request.GET.get('queue', 'needs_me')
    if queue not in QUEUES:
        queue = 'needs_me'
    query = request.GET.get('q', '')[:120]
    schedules.readable(request.user,work.case);data,e,parent,body=domain.source(work,request.user,False)
    initial=dict(data)
    if not permitted(request.user,work,'schedules.report'):initial['payload']=None
    form=InputsForm(work.case,request.POST if request.method=='POST' and request.POST.get('action')=='correct' else None,initial=initial)
    duplicate_form = None
    can_resolve = (focus != 'decision' and not work.cancel_requested and work.status not in ['cancelled','followup_needed']
                   and work.request['kind'] == 'income' and can_control(request.user, work)
                   and all(permitted(request.user, work, action) for action in
                           ('factory.manage', 'schedules.prepare', 'schedules.report', 'evidence.add')))
    if can_resolve:
        held = domain.schedule(work)
        rows = domain.duplicate_rows(held)
        if rows:
            posted = request.POST if request.method == 'POST' and request.POST.get('action') == 'resolve_duplicates' else None
            duplicate_form = DuplicateResolutionForm(work.case, held, rows, posted)
    if request.method=='POST':
        try:
            p=request.POST;a=p.get('action');revision=int(p.get('revision','0'));case_revision=int(p.get('case_revision','0'))
            allowed={'advance':set(),'resume':set(),'cancel':set(),'restart':{'reason'},'correct':{'kind','parent_id','evidence_id','payload','reason'},'review':{'target','verdict','evidence','note'},'export':{'target','kind','evidence'},'adopt_profile':{'configuration','reason'}}
            if duplicate_form is not None:
                allowed['resolve_duplicates'] = set(duplicate_form.fields)
            if a not in allowed or set(p)-allowed[a]-{'action','revision','case_revision','csrfmiddlewaretoken'}:raise ValidationError('Choose an exact typed schedule command')
            require_action(work, focus, a)
            if a=='advance':set_progress(request.user,work.pk,revision,True)
            elif a in ['resume','cancel']:factory.manage(request.user,work.pk,revision,a)
            elif a=='correct':
                if not form.is_valid():raise ValidationError('Choose exact native sources')
                domain.correct(request.user,work.pk,revision,case_revision,*form.ids(),p.get('reason',''))
            elif a == 'resolve_duplicates':
                if not duplicate_form.is_valid():
                    raise ValidationError('Supply evidence and choose a treatment for every shown addition.')
                values = duplicate_form.cleaned_data
                domain.resolve_duplicates(request.user, work.pk, revision, case_revision, values['target'],
                                          duplicate_form.choices(), values['evidence'].pk, values['reason'])
            elif a=='restart':domain.restart(request.user,work.pk,revision,case_revision,p.get('reason',''))
            elif a=='review':domain.review(request.user,work.pk,revision,case_revision,int(p.get('target','0')),p.get('verdict',''),int(p.get('evidence','0')),p.get('note',''))
            elif a=='export':domain.export(request.user,work.pk,revision,case_revision,int(p.get('target','0')),p.get('kind',''),int(p.get('evidence','0')))
            elif a=='adopt_profile':factory.adopt_profile(request.user,work.pk,revision,int(p.get('configuration','0')),p.get('reason',''))
            messages.success(request,'Native schedule work updated');return redirect(request.get_full_path())
        except (ValidationError,ValueError) as exc:messages.error(request,str(exc));work.refresh_from_db();work.case.refresh_from_db()
    row=presentation(request.user,work,include_progress=not focus);panel=row['schedules'];s=panel['schedule'];reviews=[]
    preview = None
    stage = panel['native'].get('stage')
    can_read_report = (s is not None and permitted(request.user, work, 'schedules.report'))
    if can_read_report and s.kind == 'income' and stage in ('output_review', 'returned', 'withdrawn', 'complete'):
        preview = s.result
    latest = s.reviews.select_related('actor').order_by('-pk').first() if s else None
    if s and focus != 'recovery' and not work.cancel_requested and work.status not in ['cancelled','followup_needed']:
        try:schedules.authority(request.user,s)
        except (ValidationError,PermissionDenied):pass
        else:
            verdicts = ('revoke',) if latest and latest.verdict=='approve' else ()
            if not verdicts and stage=='output_review' and s.result['status']=='ready':
                verdicts=('approve','return','reject')
            elif stage=='withdrawn':
                verdicts=('approve',)
            if verdicts:reviews.append({'target':s.pk,'verdicts':verdicts})
    return render(request,'factory/schedules_detail.html',{'row':row,'case':work.case,'focus':focus,'queue':queue,'q':query,
        'inputs_form':form,'duplicate_form':duplicate_form,'prepared_figures':preview,
        'can_open_reviewed_report':can_read_report and stage == 'complete',
        'reviews':reviews,'latest_review':latest,'review_evidence':Evidence.objects.filter(case=work.case,kind='finance_review').order_by('-pk'),
        'adjustment_evidence':Evidence.objects.filter(case=work.case,kind='finance_adjustment').order_by('-pk'),
        'can_export':focus!='decision' and s is not None and s.kind=='income' and panel['native'].get('stage')=='complete' and permitted(request.user,work,'schedules.adjust') and permitted(request.user,work,'finance.adjust'),
        'activities':work.activities.order_by('pk') if not focus else (),
        'can_correct':focus!='decision' and permitted(request.user,work,'factory.manage') and not work.cancel_requested and (work.request['kind']!='income' or permitted(request.user,work,'schedules.report')),
        'can_restart':focus!='decision' and work.status=='cancelled' and permitted(request.user,work,'factory.manage'),'can_configure':permitted(request.user,work,'policy.configure')})

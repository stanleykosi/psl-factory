"""Primary asset work console; native services own every decision and result."""
from io import BytesIO
from uuid import uuid4
from django import forms
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import ValidationError,PermissionDenied
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, render,redirect
from django.views.decorators.http import require_http_methods, require_safe
from django.views.decorators.cache import never_cache
from adapters import case_uploads
from apps.core.models import Case,Evidence
from apps.core.workbench import granted
from apps.finance import ppe
from apps.finance.models import ScheduleWork,FinanceRun
from . import factory,factory_ppe as domain, factory_ppe_opening
from .factory_progress import set_progress
from .factory_progress_views import StartWithBackground, start_work

class InputsForm(forms.Form):
    def __init__(self,case,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.fields['register_id']=forms.ModelChoiceField(queryset=ScheduleWork.objects.filter(case=case,kind='ppe_register').order_by('-pk'),label='Exact supplied register')
        self.fields['prior_id']=forms.ModelChoiceField(queryset=ScheduleWork.objects.filter(case=case,kind='ppe_schedule').order_by('-pk'),required=False,label='Prior approved schedule')
        self.fields['ledger_id']=forms.ModelChoiceField(queryset=FinanceRun.objects.filter(case=case,kind='mapping').order_by('-pk'),required=False,label='Exact read-only accounting note')
        for name in ('register_id', 'prior_id'):
            self.fields[name].label_from_instance = lambda row: f'{row.reference} · version {row.version}'
    def ids(self):return [self.cleaned_data[k].pk if self.cleaned_data[k] else None for k in ['register_id','prior_id','ledger_id']]

class OpeningProofForm(forms.Form):
    target_id = forms.IntegerField(min_value=1, widget=forms.HiddenInput)
    review_id = forms.IntegerField(min_value=1, widget=forms.HiddenInput)
    file = forms.FileField(label='Opening proof', widget=forms.ClearableFileInput(attrs={'accept': 'application/pdf,.pdf'}))
    reason = forms.CharField(max_length=2000, widget=forms.Textarea(attrs={'rows': 3}), label='What did you correct?')


class StartForm(StartWithBackground):
    definition=forms.CharField(initial=domain.DEFINITION,widget=forms.HiddenInput)
    key=forms.CharField(max_length=100,widget=forms.HiddenInput)
    case=forms.ModelChoiceField(queryset=Case.objects.none())
    reference=forms.RegexField(r'^[A-Za-z0-9][A-Za-z0-9_.:-]{0,99}$',label='Stable schedule reference')
    revision=forms.IntegerField(min_value=1,widget=forms.HiddenInput)
    def __init__(self,actor,*args,case_id=None,**kwargs):
        super().__init__(*args,**kwargs);cases=granted(actor,['factory.start','finance.read','ppe.read','evidence.add']);self.fields['case'].queryset=cases
        self.selected=cases.filter(pk=case_id).first() if case_id else None
        if self.selected:self.fields['case'].initial=self.selected;self.fields['revision'].initial=self.selected.revision
        if not self.is_bound:self.fields['key'].initial='PPE-'+uuid4().hex

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
            if d['definition']!=domain.DEFINITION or set(request.POST)-set(form.fields)-set(inputs.fields)-{'csrfmiddlewaretoken'}:raise ValidationError('Exact typed PPE command required')
            return start_work(request, lambda: domain.start(request.user, d['case'].pk, d['key'],
                              *inputs.ids(), d['reference'], d['revision']), d['background'])
        except ValidationError as exc:form.add_error(None,domain.finding(exc))
    return render(request,'factory/ppe_start.html',{'form':form,'inputs_form':inputs,'case':form.selected})

@never_cache
@require_http_methods(['GET','HEAD','POST'])
def detail(request,work,focus=None):
    from .factory_views import QUEUES, presentation,permitted
    from .screen_focus import require_action
    queue=request.GET.get('queue','needs_me')
    if queue not in QUEUES:queue='needs_me'
    query=request.GET.get('q','')[:120]
    ppe.readable(request.user,work.case);r,data=domain.source(work,request.user,False)
    form=InputsForm(work.case,request.POST if request.method=='POST' and request.POST.get('action')=='correct' else None,initial=data)
    proof_form = None
    if focus != 'decision' and not work.cancel_requested and work.status not in ('cancelled', 'followup_needed'):
        try:
            factory_ppe_opening.authority(request.user, work)
        except PermissionDenied:
            pass
        else:
            returned = factory_ppe_opening.returned_subject(work, r)
            if returned:
                posting = request.method == 'POST' and request.POST.get('action') == 'attach_opening_proof'
                proof_form = OpeningProofForm(request.POST if posting else None, request.FILES if posting else None,
                                             initial={'target_id': returned[0].pk, 'review_id': returned[1].pk},
                                             auto_id='opening_proof_%s')
    if request.method=='POST':
        try:
            p=request.POST;a=p.get('action');revision=int(p.get('revision','0'));case_revision=int(p.get('case_revision','0'))
            allowed={'advance':set(),'resume':set(),'cancel':set(),'restart':{'reason'},'correct':{'register_id','prior_id','ledger_id','reason'},'review':{'target','purpose','verdict','evidence','note'},'adopt_profile':{'configuration','reason'}}
            if proof_form is not None:
                allowed['attach_opening_proof'] = set(proof_form.fields) - {'file'}
            if a not in allowed or set(p)-allowed[a]-{'action','revision','case_revision','csrfmiddlewaretoken'}:raise ValidationError('Choose an exact typed PPE command')
            if request.FILES and (a != 'attach_opening_proof' or set(request.FILES) != {'file'}
                                  or len(request.FILES.getlist('file')) != 1):
                raise ValidationError('Attach one opening proof file for this correction.')
            require_action(work, focus, a)
            if a=='advance':set_progress(request.user,work.pk,revision,True)
            elif a in ['resume','cancel']:factory.manage(request.user,work.pk,revision,a)
            elif a=='correct':
                if not form.is_valid():raise ValidationError('Choose exact native sources')
                domain.correct(request.user,work.pk,revision,case_revision,*form.ids(),p.get('reason',''))
            elif a == 'attach_opening_proof':
                if not proof_form.is_valid():
                    raise ValidationError('Choose one PDF and explain this correction.')
                values = proof_form.cleaned_data
                factory_ppe_opening.attach(request.user, work.pk, revision, case_revision, values['target_id'],
                                           values['review_id'], values['reason'], values['file'])
            elif a=='restart':domain.restart(request.user,work.pk,revision,case_revision,p.get('reason',''))
            elif a=='review':domain.review(request.user,work.pk,revision,case_revision,int(p.get('target','0')),p.get('purpose',''),p.get('verdict',''),int(p.get('evidence','0')),p.get('note',''))
            elif a=='adopt_profile':factory.adopt_profile(request.user,work.pk,revision,int(p.get('configuration','0')),p.get('reason',''))
            messages.success(request,'Native PPE work updated');return redirect(request.get_full_path())
        except (ValidationError,ValueError) as exc:
            if a == 'attach_opening_proof' and proof_form is not None:
                proof_form.add_error(None, domain.finding(exc))
            else:
                messages.error(request,str(exc))
            work.refresh_from_db();work.case.refresh_from_db()
    row=presentation(request.user,work,include_progress=not focus);s=row['ppe']['schedule'];reviews=[];decisions=[]
    if row['ppe']['native'].get('stage') != 'returned':
        proof_form = None
    try:
        opening_attachment = factory_ppe_opening.attachment_for(request.user, work, row['ppe']['register'])
    except PermissionDenied:
        opening_attachment = None
    candidates=[(r,['register','basis'] if r.result['date_basis_ambiguous'] else ['register']),(s,['schedule'])]
    for target,purposes in candidates:
        if not target:continue
        for purpose in purposes:
            title={'register':'Asset register','basis':'Reporting dates','schedule':'Calculated schedule'}[purpose]
            prior=ppe.latest(target,purpose)
            if prior:decisions.append({'title':title,'decision':prior})
            if focus=='recovery' or work.cancel_requested or work.status in ['cancelled','followup_needed']:continue
            try:ppe.authority(request.user,target,purpose)
            except (ValidationError,PermissionDenied):continue
            if prior and prior.verdict=='approve':verdicts=('revoke',)
            elif prior and prior.verdict in ('return','reject') and purpose!='basis':continue
            else:
                try:ppe.current(target)
                except (ValidationError,PermissionDenied):continue
                if purpose=='basis' and not any(item['purpose']=='basis' for item in row['ppe']['pending_reviews']):continue
                verdicts=('return','reject') if purpose=='schedule' and target.result['status']!='ready' else ('approve','return','reject')
            kind='ppe_basis_explanation' if purpose=='basis' else 'finance_review'
            reviews.append({'target':target.pk,'purpose':purpose,'title':title,'verdicts':verdicts,
                            'evidence':Evidence.objects.filter(case=work.case,kind=kind).order_by('-pk')})
    return render(request,'factory/ppe_detail.html',{'row':row,'case':work.case,'focus':focus,'queue':queue,'q':query,
        'inputs_form':form,'reviews':reviews,'decisions':decisions,'activities':work.activities.order_by('pk') if not focus else (),
        'proof_form': proof_form, 'opening_attachment': opening_attachment,
        'can_open_reviewed_report': row['ppe']['native'].get('stage') == 'complete' and permitted(request.user, work, 'ppe.report'),
        'can_correct':focus!='decision' and permitted(request.user,work,'factory.manage') and not work.cancel_requested,
        'can_restart':focus!='decision' and work.status=='cancelled' and permitted(request.user,work,'factory.manage'),
        'can_configure':permitted(request.user,work,'policy.configure')})


@login_required
@never_cache
@require_safe
def opening_proof(request, work_id, register_id):
    from .factory_views import visible

    work = get_object_or_404(visible(request.user, work_id=work_id), definition=domain.DEFINITION)
    register = get_object_or_404(ScheduleWork, pk=register_id, case=work.case, kind='ppe_register')
    attachment = factory_ppe_opening.attachment_for(request.user, work, register)
    if attachment is None:
        raise Http404('Opening proof unavailable.')
    try:
        data = case_uploads.read(attachment)
    except (OSError, ValidationError) as exc:
        raise Http404('Opening proof unavailable.') from exc
    return FileResponse(BytesIO(data), as_attachment=True, filename=attachment.name, content_type='application/octet-stream')

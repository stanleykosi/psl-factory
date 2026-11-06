"""Native source selection and prescribed closure decisions in the shared console."""
from uuid import uuid4
from django import forms
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import render,redirect
from apps.core.models import Evidence
from apps.core.evidence_access import public_evidence
from apps.documents.models import Template
from apps.pmo.closure_views import SelectionForm
from .factory_handover_views import StartForm as DossierStartForm
from . import factory,factory_closure as closure


class InputsForm(SelectionForm):
    def __init__(self,case,*args,inputs=None,**kwargs):
        super().__init__(case,*args,**kwargs)
        self.fields['template_id']=forms.ModelChoiceField(required=False,label='Controlled closure template',empty_label='Not yet selected',
            queryset=Template.objects.filter(case=case,definition__document_type='project_artifact').order_by('-pk'))
        self.order_fields(closure.FIELDS)
        if inputs:
            for key,value in inputs.items():self.fields[key].initial=value

    def inputs(self):return {key:self.cleaned_data[key].pk if self.cleaned_data[key] else None for key in closure.FIELDS}


class StartForm(DossierStartForm):
    def __init__(self,actor,*args,**kwargs):
        super().__init__(actor,*args,**kwargs)
        self.fields['definition'].initial=closure.DEFINITION;self.fields['reference'].label='Describe the closure work'
        if not self.is_bound:self.fields['key'].initial='CLOSURE-'+uuid4().hex


def create(request):
    case_id=request.POST.get('case') if request.method=='POST' else request.GET.get('case')
    try:form=StartForm(request.user,request.POST if request.method=='POST' else None,case_id=case_id)
    except (ValidationError,ValueError):form=StartForm(request.user,data={});form.is_valid();form.add_error(None,'Choose an available project.')
    if form.selected and not form.is_bound:
        try:
            if form.fields['dossier'].queryset.filter(pk=request.GET.get('dossier')).exists():form.fields['dossier'].initial=request.GET.get('dossier')
        except (ValueError,ValidationError):messages.error(request,'Choose an available project delivery record.')
    inputs=InputsForm(form.selected,request.POST if request.method=='POST' else None,
        initial={key:request.GET.get(key) for key in closure.FIELDS if request.GET.get(key)}) if form.selected else None
    if request.method=='POST':
        valid=form.is_valid();inputs_valid=inputs.is_valid() if inputs else False
        if valid and inputs_valid:
            try:
                v=form.cleaned_data
                if v['definition']!=closure.DEFINITION:raise ValidationError('Choose registered closure work')
                w=closure.start(request.user,v['case'].pk,v['key'],v['dossier'].pk,inputs.inputs(),v['reference'],v['revision'])
                return redirect('factory_detail',w.pk)
            except ValidationError as exc:form.add_error(None,closure.finding(exc))
    return render(request,'factory/closure_start.html',{'case':form.selected,'form':form,'inputs_form':inputs})


def detail(request,work):
    from .factory_views import presentation,QUEUES,permitted
    queue=request.GET.get('queue','needs_me');q=request.GET.get('q','')[:120]
    if queue not in QUEUES:queue='needs_me'
    _,data,_=closure.source(work,request.user,current=False)
    form=InputsForm(work.case,request.POST if request.method=='POST' and request.POST.get('action')=='correct' else None,inputs=data['inputs'])
    if request.method=='POST':
        try:
            p=request.POST;action=p.get('action');revision=int(p.get('revision','0'));case_revision=int(p.get('case_revision','0'))
            if action=='advance':factory.advance(request.user,work.pk,revision)
            elif action=='correct':
                if not form.is_valid():raise ValidationError('Review the selected closure source records')
                closure.correct(request.user,work.pk,revision,case_revision,form.inputs(),p.get('reason',''))
            elif action=='decide':closure.decide(request.user,work.pk,revision,case_revision,int(p.get('version','0')),p.get('verdict',''),int(p.get('evidence','0')),p.get('note',''))
            elif action=='review':closure.review(request.user,work.pk,revision,case_revision,int(p.get('version','0')),p.get('verdict',''),p.get('note',''))
            elif action in ['cancel','settle_stop']:closure.cancel(request.user,work.pk,revision)
            elif action=='restart':closure.restart(request.user,work.pk,revision,case_revision,p.get('reason',''))
            elif action=='resume':factory.manage(request.user,work.pk,revision,action)
            elif action=='adopt_profile':factory.adopt_profile(request.user,work.pk,revision,int(p.get('configuration','0')),p.get('reason',''))
            else:raise ValidationError('Choose a currently permitted closure action')
            messages.success(request,'Closure work updated. Review current source records and the prescribed decision.');return redirect(request.get_full_path())
        except ValidationError as exc:messages.error(request,closure.finding(exc))
        except ValueError:messages.error(request,'Refresh the work and choose the current recorded references.')
        work.refresh_from_db()
    row=presentation(request.user,work);activities=list(work.activities.prefetch_related('attempts').order_by('pk'))
    for activity in activities:
        activity.title={'ACT03':'Plan permitted work','ACT04':'Investigate closure evidence','ACT09':'Prepare the PM report','ACT10':'Resolve current authority','ACT11':'Record prescribed closure','ACT13':'Verify native closure'}.get(activity.kind,'Review permitted work')
        for attempt in activity.attempts.all():attempt.display_result=closure.attempt_projection(attempt)
    response=render(request,'factory/closure_detail.html',{'case':work.case,'row':row,'queue':queue,'q':q,'inputs_form':form,'activities':activities,
        'evidence_choices':public_evidence(Evidence.objects.filter(case=work.case)).order_by('-pk')[:100],'can_configure':permitted(request.user,work,'policy.configure')})
    response['Cache-Control']='no-store';return response

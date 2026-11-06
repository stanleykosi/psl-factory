"""Work-centric controlled change console, delegating every decision to native services."""
from uuid import uuid4
from django import forms
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import render,redirect
from django.views.decorators.http import require_http_methods
from apps.core.models import Case,Evidence
from apps.core.workbench import granted
from apps.core.evidence_access import public_evidence
from apps.documents.models import Template
from apps.pmo.models import ChangeVersion,ChangeAuthorization
from . import factory,factory_change as change

class InputsForm(forms.Form):
    def __init__(self,case,*args,change_id=None,**kwargs):
        super().__init__(*args,**kwargs)
        q=ChangeVersion.objects.filter(change__case=case).select_related('change')
        if change_id:q=q.filter(change_id=change_id)
        self.fields['version_id']=forms.ModelChoiceField(queryset=q.order_by('-pk'),label='Exact native change revision')
        self.fields['version_id'].label_from_instance=lambda v:f'{v.change.reference} · {v.category} · revision {v.number}'
        self.fields['authorization_id']=forms.ModelChoiceField(queryset=ChangeAuthorization.objects.filter(version__in=q).order_by('-pk'),required=False,label='Exact human authorization',empty_label='Await human authorization')
        self.fields['template_id']=forms.ModelChoiceField(queryset=Template.objects.filter(case=case,definition__document_type__in=['project_artifact','status_report']),required=False,label='Controlled change template')
    def inputs(self):return {k:self.cleaned_data[k].pk if self.cleaned_data[k] else None for k in ['template_id','authorization_id']}

class StartForm(forms.Form):
    definition=forms.CharField(initial=change.DEFINITION,widget=forms.HiddenInput)
    key=forms.CharField(max_length=100,widget=forms.HiddenInput)
    case=forms.ModelChoiceField(queryset=Case.objects.none(),label='Project')
    reference=forms.CharField(max_length=160,label='Describe the controlled change work')
    revision=forms.IntegerField(min_value=1,widget=forms.HiddenInput)
    def __init__(self,actor,*args,case_id=None,**kwargs):
        super().__init__(*args,**kwargs)
        cases=granted(actor,['change.read','factory.start','evidence.add']).filter(kind='project');self.fields['case'].queryset=cases
        self.selected=cases.filter(pk=case_id).first() if case_id else None
        if self.selected:self.fields['case'].initial=self.selected;self.fields['revision'].initial=self.selected.revision
        if not self.is_bound:self.fields['key'].initial='CHANGE-'+uuid4().hex

@require_http_methods(['GET','HEAD','POST'])
def create(request):
    case_id=request.POST.get('case') if request.method=='POST' else request.GET.get('case')
    try:form=StartForm(request.user,request.POST if request.method=='POST' else None,case_id=case_id)
    except (ValidationError,ValueError):form=StartForm(request.user,data={});form.is_valid();form.add_error(None,'Choose an available project')
    inputs=InputsForm(form.selected,request.POST if request.method=='POST' else None) if form.selected else None
    if request.method=='POST' and form.is_valid() and inputs and inputs.is_valid():
        try:
            d=form.cleaned_data
            if d['definition']!=change.DEFINITION:raise ValidationError('Choose the registered controlled change definition')
            w=change.start(request.user,d['case'].pk,d['key'],inputs.cleaned_data['version_id'].pk,inputs.inputs(),d['reference'],d['revision'])
            return redirect('factory_detail',w.pk)
        except ValidationError as exc:form.add_error(None,change.finding(exc))
    return render(request,'factory/change_start.html',{'form':form,'inputs_form':inputs,'case':form.selected})

@require_http_methods(['GET','HEAD','POST'])
def detail(request,work):
    from .factory_views import presentation,permitted
    v,data=change.source(work,request.user,False)
    form=InputsForm(work.case,request.POST if request.method=='POST' and request.POST.get('action')=='correct' else None,change_id=v.change_id,initial=dict(data['inputs'],version_id=v.pk))
    if request.method=='POST':
        try:
            p=request.POST;action=p.get('action');revision=int(p.get('revision','0'));case_revision=int(p.get('case_revision','0'))
            if action=='advance':factory.advance(request.user,work.pk,revision)
            elif action=='correct':
                if not form.is_valid():raise ValidationError('Choose exact current change sources')
                change.correct(request.user,work.pk,revision,case_revision,form.cleaned_data['version_id'].pk,form.inputs(),p.get('reason',''))
            elif action=='review':change.review(request.user,work.pk,revision,case_revision,int(p.get('version','0')),p.get('verdict',''),p.get('note',''))
            elif action=='close':change.close(request.user,work.pk,revision,case_revision,int(p.get('receipt','0')),int(p.get('pm_signature','0')),int(p.get('client_signature','0')),p.get('note',''))
            elif action in ['assess','decide','authorize','execution']:
                values={'note':p.get('note','')}
                if action in ['assess','decide','execution']:values['evidence']=int(p.get('evidence','0'))
                if action=='assess':
                    flags={'unknown':None,'true':True,'false':False}
                    if any(p.get(k) not in flags for k in ['cost_impact','timeline_impact','client_facing']):raise ValidationError('Choose true, false or unknown impact')
                    from apps.pmo.change_impacts import assessment_form
                    values.update(assessment_form(p))
                    values.update(contributor=p.get('contributor',''),**{k:flags[p[k]] for k in ['cost_impact','timeline_impact','client_facing']})
                elif action=='decide':values.update(role=p.get('role',''),verdict=p.get('verdict',''))
                elif action=='authorize':values['commercial']=int(p['commercial']) if p.get('commercial') else None
                else:
                    from apps.pmo.change_impacts import execution_form
                    values.update(execution_form(p));values['kind']=p.get('kind','')
                change.human_action(request.user,work.pk,revision,case_revision,int(p.get('change_version','0')),action,values)
            elif action=='restart':change.restart(request.user,work.pk,revision,case_revision,p.get('reason',''))
            elif action=='cancel':change.cancel(request.user,work.pk,revision)
            elif action=='resume':factory.manage(request.user,work.pk,revision,'resume')
            elif action=='reconcile':change.reconcile(request.user,work.pk,revision)
            elif action=='operate_delivery':change.operate(request.user,work.pk,revision,case_revision,int(p.get('job','0')),p.get('operation',''),p.get('reason',''))
            elif action=='adopt_profile':factory.adopt_profile(request.user,work.pk,revision,int(p.get('configuration','0')),p.get('reason',''))
            else:raise ValidationError('Choose a current native change action')
            messages.success(request,'Controlled change action recorded');return redirect(request.get_full_path())
        except (ValidationError,ValueError) as exc:messages.error(request,str(exc));work.refresh_from_db();work.case.refresh_from_db()
    row=presentation(request.user,work);panel=row['change']
    human_permissions={a:permitted(request.user,work,a) for a in ['change.manage','change.decide','change.progress:Engineering','change.progress:QA']}
    assessors=[c for c in change.changes.CONTRIBUTORS if permitted(request.user,work,'change.assess:'+c)]
    evidence=public_evidence(Evidence.objects.filter(case=work.case)).order_by('-pk')
    signatures=public_evidence(Evidence.objects.filter(case=work.case,kind='signature')).order_by('-pk') if panel['can_close'] else []
    return render(request,'factory/change_detail.html',{'row':row,'case':work.case,'inputs_form':form,'signatures':signatures,'activities':work.activities.order_by('pk'),'can_configure':permitted(request.user,work,'policy.configure'),'assessors':assessors,'can_decide':human_permissions['change.decide'],'can_authorize':human_permissions['change.manage'],'can_execution':any(human_permissions.values()),'evidence':evidence,'decision_roles':change.changes.DECISION_ROLES})

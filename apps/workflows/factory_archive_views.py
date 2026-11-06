"""Human declared inventory and native archive operation controls."""
from uuid import uuid4
from django import forms
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import render,redirect
from apps.core.models import Case,Evidence
from apps.core.evidence_access import public_evidence
from apps.core.presentation import workspace_name
from apps.core.workbench import granted
from apps.pmo.models import DeliveryDossier
from . import factory,factory_archive as archive


def evidence_label(e):return f'{e.body[:70]} · version {e.version} · evidence {e.pk}'


class InventoryForm(forms.Form):
    def __init__(self,case,*args,inventory=None,**kwargs):
        super().__init__(*args,**kwargs);self.kinds=archive.required_kinds(case)
        for kind in self.kinds:
            name='inventory_'+kind
            self.fields[name]=forms.ModelChoiceField(queryset=public_evidence(Evidence.objects.filter(case=case,kind=kind)).order_by('-version'),
                required=False,label=kind.replace('_',' ').capitalize(),empty_label='Not yet provided')
            self.fields[name].label_from_instance=evidence_label
            if inventory is not None:self.fields[name].initial=inventory.get(kind)

    def inventory(self):return {kind:self.cleaned_data['inventory_'+kind].pk if self.cleaned_data['inventory_'+kind] else None for kind in self.kinds}


class StartForm(forms.Form):
    definition=forms.CharField(initial=archive.DEFINITION,widget=forms.HiddenInput)
    key=forms.CharField(widget=forms.HiddenInput,max_length=100)
    case=forms.ModelChoiceField(queryset=Case.objects.none(),label='Project')
    dossier=forms.ModelChoiceField(queryset=DeliveryDossier.objects.none(),label='Delivery or release')
    reference=forms.CharField(max_length=160,label='Describe the archive work')
    revision=forms.IntegerField(min_value=1,widget=forms.HiddenInput)
    def __init__(self,actor,*args,case_id=None,**kwargs):
        super().__init__(*args,**kwargs)
        cases=granted(actor,['delivery.read','factory.start','evidence.add']).filter(kind='project');self.fields['case'].queryset=cases
        self.fields['case'].label_from_instance=workspace_name;selected=cases.filter(pk=case_id).first() if case_id else None
        self.selected=selected
        if selected:
            self.fields['case'].initial=selected;self.fields['revision'].initial=selected.revision
            self.fields['dossier'].queryset=DeliveryDossier.objects.filter(case=selected).exclude(records__kind='closure').select_related('candidate')
            self.fields['dossier'].label_from_instance=lambda d:d.candidate.reference
        if not self.is_bound:self.fields['key'].initial='ARCHIVE-'+uuid4().hex


def create(request):
    case_id=request.POST.get('case') if request.method=='POST' else request.GET.get('case')
    try:form=StartForm(request.user,request.POST if request.method=='POST' else None,case_id=case_id)
    except (ValidationError,ValueError):
        form=StartForm(request.user,data={});form.is_valid();form.add_error(None,'Choose an available project.')
    inventory=InventoryForm(form.selected,request.POST if request.method=='POST' else None) if form.selected else None
    if request.method=='POST':
        valid=form.is_valid();inventory_valid=inventory.is_valid() if inventory else False
        if valid and inventory_valid:
            try:
                v=form.cleaned_data
                if v['definition']!=archive.DEFINITION:raise ValidationError('Choose registered archive work')
                work=archive.start(request.user,v['case'].pk,v['key'],v['dossier'].pk,inventory.inventory(),v['reference'],v['revision'])
                return redirect('factory_detail',work.pk)
            except ValidationError as exc:form.add_error(None,str(exc))
    return render(request,'factory/archive_start.html',{'form':form,'inventory_form':inventory,'case':form.selected})


def detail(request,work):
    from .factory_views import presentation,QUEUES,permitted
    queue=request.GET.get('queue','needs_me');q=request.GET.get('q','')[:120]
    if queue not in QUEUES:queue='needs_me'
    panel=archive.projection(request.user,work)
    form=InventoryForm(work.case,request.POST if request.method=='POST' and request.POST.get('action')=='correct_inventory' else None,
        inventory=panel['data']['inventory'])
    if request.method=='POST':
        try:
            action=request.POST.get('action');revision=int(request.POST.get('revision','0'))
            if action=='correct_inventory':
                if not form.is_valid():raise ValidationError('Review the declared inventory choices')
                archive.correct(request.user,work.pk,revision,int(request.POST.get('case_revision','0')),form.inventory(),request.POST.get('reason',''))
            elif action=='advance':factory.advance(request.user,work.pk,revision)
            elif action=='reassess':archive.reassess(request.user,work.pk,revision,request.POST.get('reason',''))
            elif action=='restart':archive.restart(request.user,work.pk,revision,int(request.POST.get('case_revision','0')),request.POST.get('reason',''))
            elif action in ['cancel','settle_stop']:archive.cancel(request.user,work.pk,revision)
            elif action=='resume':factory.manage(request.user,work.pk,revision,action)
            elif action=='adopt_profile':factory.adopt_profile(request.user,work.pk,revision,int(request.POST.get('configuration','0')),request.POST.get('reason',''))
            else:raise ValidationError('Choose a currently available archive action')
            messages.success(request,'Archive action recorded. Review the current evidence and outcome.');return redirect(request.get_full_path())
        except (ValidationError,ValueError) as exc:messages.error(request,str(exc))
        work.refresh_from_db()
    row=presentation(request.user,work);activities=list(work.activities.prefetch_related('attempts').order_by('pk'))
    for activity in activities:
        activity.title={'ACT03':'Plan next permitted work','ACT04':'Investigate final evidence','ACT08':'Prepare the archive index','ACT10':'Resolve rules and operator','ACT13':'Verify the archive index'}.get(activity.kind,'Review permitted work')
        for attempt in activity.attempts.all():attempt.display_result=archive.attempt_projection(attempt)
    response=render(request,'factory/archive_detail.html',{'case':work.case,'row':row,'queue':queue,'q':q,'activities':activities,
        'inventory_form':form,'can_configure':permitted(request.user,work,'policy.configure')})
    response['Cache-Control']='no-store';return response

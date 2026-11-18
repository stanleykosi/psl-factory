"""Work-centric intake and exact native human decisions; GET never progresses work."""
from uuid import uuid4
from django import forms
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError,PermissionDenied
from django.shortcuts import render,redirect
from django.utils import timezone
from apps.core.models import Case,Evidence
from apps.core.evidence_access import public_evidence
from apps.core.workbench import granted
from apps.core.presentation import workspace_name
from apps.core.templatetags.studio_ui import role_name
from apps.identity.models import Grant
from apps.pmo.models import RFPDisposition
from apps.pmo import engagement
from apps.policy.engagement_validators import ASSIGN,REGISTER
from apps.policy.services import active_component,reference_values
from . import factory_engagement as d
from .factory_progress_views import StartWithBackground, start_work

ACTIONS=['factory.start','engagement.read','engagement.capture']

class ProjectForm(forms.Form):
    definition=forms.CharField(initial=d.DEFINITION,widget=forms.HiddenInput)
    case=forms.ModelChoiceField(queryset=Case.objects.none(),label='Project')

    def __init__(self,actor,selected=None):
        super().__init__(initial={'case':selected})
        self.fields['case'].queryset=granted(actor,ACTIONS).filter(kind='project')
        self.fields['case'].label_from_instance=workspace_name

class StartForm(StartWithBackground):
    definition=forms.CharField(initial=d.DEFINITION,widget=forms.HiddenInput)
    key=forms.CharField(max_length=100,widget=forms.HiddenInput)
    case=forms.ModelChoiceField(queryset=Case.objects.none(),label='Project',widget=forms.HiddenInput)
    route=forms.ChoiceField(label='How did this work start?',choices=[('','Choose the source of the engagement'),
        ('A','Won request for proposal'),('B','Direct client engagement'),('C','Product brief')])
    evidence=forms.ModelChoiceField(queryset=Evidence.objects.none(),label='Engagement source document')
    reference=forms.CharField(max_length=100,label='Engagement reference')
    rfp_disposition=forms.ModelChoiceField(queryset=RFPDisposition.objects.none(),required=False,label='Recorded winning proposal, when applicable')
    revision=forms.IntegerField(min_value=1,widget=forms.HiddenInput)
    def __init__(self,actor,data=None,case_id=None):
        super().__init__(data=data,initial={'key':uuid4().hex})
        cases=granted(actor,ACTIONS).filter(kind='project');self.fields['case'].queryset=cases
        self.fields['case'].label_from_instance=workspace_name
        selected=cases.filter(pk=case_id).first() if case_id else None
        self.selected_case=selected
        if selected:
            self.fields['case'].initial=selected;self.fields['revision'].initial=selected.revision
            self.fields['evidence'].queryset=public_evidence(selected.evidence.filter(kind__in=['engagement_source','product_input','rfp_outcome']))
            self.fields['evidence'].label_from_instance=lambda e:e.source+' · version '+str(e.version)
            self.fields['rfp_disposition'].queryset=RFPDisposition.objects.filter(rfp__case=selected,kind='route_a')
            self.fields['rfp_disposition'].label_from_instance=lambda r:'Recorded won RFP conversion '+str(r.pk)
            current=engagement.latest(selected,'capture')
            if current:
                for key in ['route','reference','rfp_disposition']:self.fields[key].initial=current.data[key]
                self.fields['evidence'].initial=current.evidence_id


def create(request):
    case_id=request.POST.get('case') if request.method=='POST' else request.GET.get('case')
    try:form=StartForm(request.user,request.POST if request.method=='POST' else None,case_id)
    except (ValueError,ValidationError):
        form=StartForm(request.user,data={});form.is_valid();form.add_error(None,'Choose an available project workspace')
    if request.method=='POST' and form.is_valid():
        v=form.cleaned_data
        try:
            return start_work(request, lambda: d.receive(request.user, v['case'].pk, v['key'], v['route'],
                              v['evidence'].pk, v['reference'], v['revision'],
                              v['rfp_disposition'].pk if v['rfp_disposition'] else None), v['background'])
        except ValidationError as exc:form.add_error(None,str(exc))
    response=render(request,'factory/engagement_start.html',{'form':form,'selected_case':getattr(form,'selected_case',None),
        'project_form':ProjectForm(request.user,getattr(form,'selected_case',None))})
    response['Cache-Control']='no-store';return response


def human_forms(actor,work,data=None):
    from .factory_views import permitted
    if work.cancel_requested or work.status in ['verified','cancelled','followup_needed']:return []
    forms_out=[]
    for operation,component,role_key,title in [('assign',ASSIGN,'assignment_roles','Confirm project manager'),('register',REGISTER,'registration_roles','Register the project during Planning')]:
        if not permitted(actor,work,'engagement.'+operation):continue
        roles=d.human_roles(actor,work.case,operation)
        if not roles:continue
        fields={'operation':forms.CharField(initial=operation,widget=forms.HiddenInput),
            'key':forms.CharField(initial=uuid4().hex,max_length=100,widget=forms.HiddenInput),
            'role':forms.ChoiceField(label='Your decision role',choices=[(r,role_name(r)) for r in roles]),
            'evidence_id':forms.ModelChoiceField(public_evidence(work.case.evidence.filter(kind__in=['engagement_source','engagement_assignment','engagement_registration','product_input','rfp_outcome','plan'])),label='Supporting document')}
        if operation=='assign':fields['pm_id']=forms.ModelChoiceField(engagement.pm_candidates(work.case),label='Appointed project manager')
        else:
            fields.update(value=forms.CharField(max_length=120,label='Supplied project reference'),plan_id=forms.ModelChoiceField(public_evidence(work.case.evidence.filter(kind='plan')),label='Planning document'))
        form=type('Engagement'+operation,(forms.Form,),fields)(data if data and data.get('operation')==operation else None,auto_id='engagement_'+operation+'_%s')
        forms_out.append({'operation':operation,'title':title,'form':form})
    return forms_out


def detail(request,work):
    from . import factory
    from .factory_views import presentation,permitted,visible,QUEUES
    queue=request.GET.get('queue','needs_me');q=request.GET.get('q','')[:120]
    if queue not in QUEUES:queue='needs_me'
    forms_out=human_forms(request.user,work,request.POST if request.method=='POST' else None)
    if request.method=='POST':
        try:
            action=request.POST.get('action');revision=int(request.POST.get('revision','0'))
            if action=='human':
                panel=next((p for p in forms_out if p['operation']==request.POST.get('operation')),None)
                if panel is None:raise PermissionDenied('Current configured native PMO authority required')
                if not panel['form'].is_valid():raise ValidationError('Correct the source fields below')
                data={k:(v.pk if hasattr(v,'pk') else v) for k,v in panel['form'].cleaned_data.items() if k!='operation'}
                d.human(request.user,work.pk,revision,int(request.POST.get('case_revision','0')),panel['operation'],data)
            elif action=='advance':factory.advance(request.user,work.pk,revision)
            elif action in ['resume','cancel']:factory.manage(request.user,work.pk,revision,action)
            elif action=='reassess':d.reassess(request.user,work.pk,revision,request.POST.get('reason',''),int(request.POST['capture']) if request.POST.get('capture') else None)
            elif action=='adopt_profile':factory.adopt_profile(request.user,work.pk,revision,int(request.POST.get('configuration','0')),request.POST.get('reason',''))
            else:raise ValidationError('Choose a current engagement work action')
            messages.success(request,'Project record updated. Check the registration and Planning handoff.')
            return redirect(request.get_full_path())
        except (ValidationError,ValueError,get_user_model().DoesNotExist) as exc:messages.error(request,str(exc))
        work=visible(request.user).get(pk=work.pk)
    row=presentation(request.user,work)
    activities=[]
    for item in work.activities.prefetch_related('attempts').order_by('pk'):
        from apps.agents.factory_catalogue import CATALOGUE
        item.title=CATALOGUE[item.kind].title
        item.outputs=[d.attempt_projection(attempt,request.user) for attempt in item.attempts.all() if attempt.phase!='started']
        activities.append(item)
    # No retained cross-project candidate IDs or private planning bodies appear here.
    source=None
    try:
        capture=d.pointer(work.case,work.source_head);d.capture_current(work.case,capture.pk);source=capture.evidence
    except (ValidationError,PermissionDenied):pass
    show_controls=bool(row.get('can_advance') or row.get('can_manage') and
        (row.get('can_cancel') or work.status in ['blocked','configuration_needed','owner_needed']))
    action_panel_active=bool(show_controls or forms_out or row.get('adoption') or row.get('can_manage') and row.get('engagement',{}).get('changed'))
    response=render(request,'factory/engagement_detail.html',{'case':work.case,'row':row,'source':source,'activities':activities,'human_forms':forms_out,
        'show_controls':show_controls,'action_panel_active':action_panel_active,
        'queue':queue,'q':q,'can_configure':permitted(request.user,work,'policy.configure'),'as_of':timezone.now()})
    response['Cache-Control']='no-store';return response

"""Human-attribution console; no model command can confirm commitments."""
from uuid import uuid4
from django import forms
from django.db.models import F
from django.contrib import messages
from django.core.exceptions import ValidationError,PermissionDenied
from django.shortcuts import render,redirect
from django.views.decorators.http import require_http_methods
from django.views.decorators.cache import never_cache
from apps.core.models import Case,Evidence
from apps.core.workbench import granted
from apps.documents.models import Template
from apps.pmo.models import Meeting,MeetingVersion
from apps.pmo.meetings import meeting_actions
from apps.documents.controlled import review_version
from . import factory,factory_minutes as domain
from .factory_minutes_forms import capture_forms,command_keys,payload

class InputsForm(forms.Form):
    audience=forms.ChoiceField(choices=[('internal','Internal repository only'),('client','Client, with separately authorized publication')])
    publish=forms.BooleanField(required=False,label='I request outward publication after exact P53 review')
    def __init__(self,case,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.fields['meeting_version_id']=forms.ModelChoiceField(queryset=MeetingVersion.objects.filter(meeting__case=case,meeting__current_id=F('pk')).order_by('-pk'),required=False,label='Existing meeting current version (blank only for a new meeting reference)')
        self.fields['meeting_version_id'].label_from_instance=lambda version:version.meeting.reference+' · revision '+str(version.number)+' · '+version.purpose
        self.fields['evidence_id']=forms.ModelChoiceField(queryset=Evidence.objects.filter(case=case,kind='meeting_notes').order_by('-pk'),label='Authorized meeting notes')
        self.fields['template_id']=forms.ModelChoiceField(queryset=Template.objects.filter(case=case,definition__document_type='minutes').order_by('-pk'),label='Minutes template')
    def selection(self):
        d=self.cleaned_data
        return {'protocol':domain.PROTOCOL,'meeting_version_id':d['meeting_version_id'].pk if d['meeting_version_id'] else None,'evidence_id':d['evidence_id'].pk,'template_id':d['template_id'].pk,'audience':d['audience'],'publish':d['publish']}

class StartForm(forms.Form):
    definition=forms.CharField(initial=domain.DEFINITION,widget=forms.HiddenInput)
    key=forms.CharField(max_length=100,widget=forms.HiddenInput)
    case=forms.ModelChoiceField(queryset=Case.objects.none())
    reference=forms.CharField(max_length=160,label='Formal meeting reference')
    revision=forms.IntegerField(min_value=1,widget=forms.HiddenInput)
    def __init__(self,actor,*args,case_id=None,**kwargs):
        super().__init__(*args,**kwargs);cases=granted(actor,['factory.start','meeting.read','evidence.add']);self.fields['case'].queryset=cases
        self.selected=cases.filter(pk=case_id,kind='project').first() if case_id else None
        if self.selected:self.fields['case'].initial=self.selected;self.fields['revision'].initial=self.selected.revision
        if not self.is_bound:self.fields['key'].initial='minutes-'+uuid4().hex

@never_cache
@require_http_methods(['GET','HEAD','POST'])
def create(request):
    data=request.POST if request.method=='POST' else None
    try:form=StartForm(request.user,data,case_id=(data or request.GET).get('case'))
    except (ValueError,ValidationError):form=StartForm(request.user,data={});form.is_valid();form.add_error(None,'Choose an available project')
    inputs=InputsForm(form.selected,data) if form.selected else None
    if request.method=='POST' and form.is_valid() and inputs and inputs.is_valid():
        try:
            d=form.cleaned_data
            if d['definition']!=domain.DEFINITION or set(request.POST)-set(form.fields)-set(inputs.fields)-{'csrfmiddlewaretoken'}:raise ValidationError('Exact typed minutes intake required')
            w=domain.start(request.user,d['case'].pk,d['key'],d['reference'],inputs.selection(),d['revision']);return redirect('factory_detail',w.pk)
        except ValidationError as exc:form.add_error(None,domain.finding(exc))
    return render(request,'factory/minutes_start.html',{'form':form,'inputs_form':inputs,'case':form.selected})

@never_cache
@require_http_methods(['GET','HEAD','POST'])
def detail(request,work):
    from .factory_views import presentation,permitted
    data,note,_=domain.source(work,request.user,False);p=request.POST;a=p.get('action');r=domain.extraction(work)
    m=Meeting.objects.select_related('current').filter(case=work.case,reference=work.request['reference']).first()
    correction=dict(data,meeting_version_id=m.current_id if m else None)
    inputs=InputsForm(work.case,p if request.method=='POST' and a=='correct' else None,initial=correction)
    predecessor=MeetingVersion.objects.select_related('meeting').filter(pk=data['meeting_version_id'],meeting__case=work.case).first() if data['meeting_version_id'] else None
    capture=a in ['confirm','add_decision','add_commitment']
    form,decisions,commitments=capture_forms(work,data,r,p if request.method=='POST' and capture else None,predecessor)
    if request.method=='POST':
        try:
            revision=int(p.get('revision','0'));case_revision=int(p.get('case_revision','0'))
            allowed={'advance':set(),'reconcile':set(),'operate':{'job','operation','reason'},'resume':set(),'cancel':set(),'restart':{'reason'},'correct':set(inputs.fields)|{'reason'},'confirm':command_keys(form,decisions,commitments),'add_decision':command_keys(form,decisions,commitments),'add_commitment':command_keys(form,decisions,commitments),'review':{'version','verdict','note'}}
            if a not in allowed or set(p)-allowed[a]-{'action','revision','case_revision','csrfmiddlewaretoken'}:raise ValidationError('Choose an exact typed minutes command')
            if capture:
                if revision!=work.revision or case_revision!=work.case.revision or int(p.get('source_head_id','0'))!=work.source_head_id or (int(p['predecessor_id']) if p.get('predecessor_id') else None)!=data['meeting_version_id'] or (int(p['extraction_id']) if p.get('extraction_id') else None)!=(r.pk if r else None):raise ValidationError('Refresh the exact selected meeting source and extraction before confirming.')
                if any(len(p.getlist(k))!=1 for k in p if k not in ['participants','existing_actions']):raise ValidationError('Submit each typed field once.')
            if a in ['add_decision','add_commitment']:
                prefix='decisions' if a=='add_decision' else 'commitments'
                total=int(p.get(prefix+'-TOTAL_FORMS','-1'))
                if not 0<=total<50:raise ValidationError('Up to 50 rows are available. Remove or edit an existing row.')
                edited=p.copy();edited[prefix+'-TOTAL_FORMS']=str(total+1)
                form,decisions,commitments=capture_forms(work,data,r,edited,predecessor)
            elif a=='advance':factory.advance(request.user,work.pk,revision)
            elif a=='reconcile':domain.reconcile(request.user,work.pk,revision)
            elif a=='operate':domain.operate(request.user,work.pk,revision,case_revision,int(p.get('job','0')),p.get('operation',''),p.get('reason',''))
            elif a in ['resume','cancel']:factory.manage(request.user,work.pk,revision,a)
            elif a=='restart':domain.restart(request.user,work.pk,revision,case_revision,p.get('reason',''))
            elif a=='correct':
                if not inputs.is_valid():raise ValidationError('Choose exact authorized sources')
                domain.correct(request.user,work.pk,revision,case_revision,inputs.selection(),p.get('reason',''))
            elif a=='confirm':
                valid=[form.is_valid(),decisions.is_valid(),commitments.is_valid()]
                if not all(valid):raise ValidationError('Check the marked meeting, decision and commitment fields.')
                domain.confirm(request.user,work.pk,revision,case_revision,payload(form,decisions,commitments,note),form.cleaned_data['extraction_id'])
            elif a=='review':
                from django.db import transaction
                with transaction.atomic():
                    w=domain.human_work(request.user,work.pk,revision,case_revision);b=domain.current_document(w,request.user)
                    if int(p.get('version','0'))!=b.version_id or b.version.audience!='client':raise ValidationError('Review exact outward minutes only')
                    review_version(request.user,w.case_id,b.version_id,p.get('verdict',''),p.get('note',''),case_revision)
            if a not in ['add_decision','add_commitment']:
                messages.success(request,'Minutes work updated');return redirect(request.get_full_path())
        except (ValidationError,ValueError) as exc:messages.error(request,str(exc));work.refresh_from_db();work.case.refresh_from_db()
    row=presentation(request.user,work);panel=row['minutes'];b=panel['document']
    return render(request,'factory/minutes_detail.html',{'row':row,'case':work.case,'source':note,'inputs_form':inputs,'confirm_form':form,'decision_forms':decisions,'commitment_forms':commitments,'can_confirm':not panel['confirmation'] and permitted(request.user,work,'meeting.record') and not work.cancel_requested,'can_correct':permitted(request.user,work,'factory.manage') and not work.cancel_requested,'can_review':panel['can_review'],'can_operate':permitted(request.user,work,'document.operate'),'activities':work.activities.order_by('pk'),'can_restart':work.status=='cancelled' and permitted(request.user,work,'factory.manage')})

from .factory_views import ProfileForm
class MinutesProfileForm(ProfileForm):
    extraction_provider=forms.ChoiceField(required=False,choices=[('','No approved extraction provider'),('synthetic_meeting_v1','Isolated synthetic meeting extraction')])
    def clean_extraction_provider(self):return self.cleaned_data['extraction_provider'] or None

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
from . import factory,factory_minutes as domain
from .factory_progress_views import StartWithBackground, start_work
from .factory_minutes_forms import apply_suggestions,capture_forms,command_keys,payload,suggestion_rows

class InputsForm(forms.Form):
    audience=forms.ChoiceField(choices=[('internal','Internal repository only'),('client','Client, with separately authorized publication')])
    publish=forms.BooleanField(required=False,label='I request client publication after a separate review')
    def __init__(self,case,*args,upload_allowed=False,**kwargs):
        super().__init__(*args,**kwargs)
        self.fields['meeting_version_id']=forms.ModelChoiceField(queryset=MeetingVersion.objects.filter(meeting__case=case,meeting__current_id=F('pk')).order_by('-pk'),required=False,label='Existing meeting current version (blank only for a new meeting reference)')
        self.fields['meeting_version_id'].label_from_instance=lambda version:version.meeting.reference+' · revision '+str(version.number)+' · '+version.purpose
        self.fields['evidence_id']=forms.ModelChoiceField(queryset=Evidence.objects.filter(case=case,kind='meeting_notes').order_by('-pk'),
                                                         label='Authorized meeting notes',required=not upload_allowed)
        if upload_allowed:
            self.fields['notes_file']=forms.FileField(required=False,label='Upload meeting notes',
                help_text='Text, Word, Excel or readable PDF, up to 5 MiB. The notes become source evidence for this project.',
                widget=forms.ClearableFileInput(attrs={'accept':'.txt,.docx,.xlsx,.pdf'}))
        self.fields['template_id']=forms.ModelChoiceField(queryset=Template.objects.filter(case=case,definition__document_type='minutes').order_by('-pk'),label='Minutes template')

    def clean(self):
        values = super().clean()
        if 'notes_file' in self.fields and not (self.errors.get('notes_file') or self.errors.get('evidence_id')):
            if bool(values.get('notes_file')) == bool(values.get('evidence_id')):
                raise ValidationError('Select existing notes or upload one notes file.')
        return values

    def selection(self):
        d=self.cleaned_data
        return {'protocol':domain.PROTOCOL,'meeting_version_id':d['meeting_version_id'].pk if d['meeting_version_id'] else None,'evidence_id':d['evidence_id'].pk if d['evidence_id'] else None,'template_id':d['template_id'].pk,'audience':d['audience'],'publish':d['publish']}

class StartForm(StartWithBackground):
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
    inputs=InputsForm(form.selected,data,request.FILES if data is not None else None,upload_allowed=True) if form.selected else None
    if request.method=='POST' and form.is_valid() and inputs and inputs.is_valid():
        try:
            d=form.cleaned_data
            if (d['definition']!=domain.DEFINITION or set(request.POST)-set(form.fields)-set(inputs.fields)-{'csrfmiddlewaretoken'}
                    or set(request.FILES)-{'notes_file'} or len(request.FILES.getlist('notes_file')) > 1):
                raise ValidationError('Choose one notes source for this meeting.')
            args=(request.user,d['case'].pk,d['key'],d['reference'],inputs.selection(),d['revision'])
            uploaded=inputs.cleaned_data.get('notes_file')
            return start_work(request, lambda: domain.start_uploaded(*args,uploaded) if uploaded else domain.start(*args), d['background'])
        except ValidationError as exc:form.add_error(None,domain.finding(exc))
    return render(request,'factory/minutes_start.html',{'form':form,'inputs_form':inputs,'case':form.selected})

@never_cache
@require_http_methods(['GET','HEAD','POST'])
def detail(request,work,focus=None):
    from .factory_views import presentation,permitted
    from .screen_focus import require_action
    data,note,_=domain.source(work,request.user,False);p=request.POST;a=p.get('action');r=domain.extraction(work)
    suggestion = None
    if a and a.startswith('use-'):
        group, _, index = a[4:].partition('-')
        if group in ['decision', 'commitment'] and index.isascii() and index.isdecimal() and len(index) <= 2:
            suggestion = int(index)
            a = 'add_' + group
    m=Meeting.objects.select_related('current').filter(case=work.case,reference=work.request['reference']).first()
    correction=dict(data,meeting_version_id=m.current_id if m else None)
    inputs=InputsForm(work.case,p if request.method=='POST' and a=='correct' else None,initial=correction)
    predecessor=MeetingVersion.objects.select_related('meeting').filter(pk=data['meeting_version_id'],meeting__case=work.case).first() if data['meeting_version_id'] else None
    suggestions=suggestion_rows(r,note.pk)
    capture=a in ['confirm','add_decision','add_commitment','use_selected']
    form,decisions,commitments=capture_forms(work,data,r,p if request.method=='POST' and capture else None,predecessor)
    if request.method=='POST':
        try:
            require_action(work,focus,a)
            revision=int(p.get('revision','0'));case_revision=int(p.get('case_revision','0'))
            allowed={'advance':set(),'reconcile':set(),'operate':{'job','operation','reason'},'resume':set(),'cancel':set(),'restart':{'reason'},'correct':set(inputs.fields)|{'reason'},'confirm':command_keys(form,decisions,commitments),'add_decision':command_keys(form,decisions,commitments),'add_commitment':command_keys(form,decisions,commitments),'review':{'version','verdict','note'}}
            allowed['use_selected']=allowed['confirm']
            allowed['request_review']={'version'}
            if a not in allowed or set(p)-allowed[a]-{'action','revision','case_revision','csrfmiddlewaretoken'}:raise ValidationError('Choose an exact typed minutes command')
            if a in ['request_review', 'review'] and any(len(p.getlist(k)) != 1 for k in allowed[a] | {'action', 'revision', 'case_revision'}):
                raise ValidationError('Submit each review field once.')
            if capture:
                if revision!=work.revision or case_revision!=work.case.revision or int(p.get('source_head_id','0'))!=work.source_head_id or (int(p['predecessor_id']) if p.get('predecessor_id') else None)!=data['meeting_version_id'] or (int(p['extraction_id']) if p.get('extraction_id') else None)!=(r.pk if r else None):raise ValidationError('Refresh the exact selected meeting source and extraction before confirming.')
                if any(len(p.getlist(k))!=1 for k in p if k not in ['participants','existing_actions','selected_suggestions']):raise ValidationError('Submit each typed field once.')
            if a=='use_selected':
                if not permitted(request.user,work,'meeting.record') or work.cancel_requested or domain.confirmation(work):
                    raise ValidationError('Open a current meeting confirmation before using an agent suggestion.')
                form,decisions,commitments=capture_forms(work,data,r,apply_suggestions(p,suggestions),predecessor)
            elif a in ['add_decision','add_commitment']:
                prefix='decisions' if a=='add_decision' else 'commitments'
                total=int(p.get(prefix+'-TOTAL_FORMS','-1'))
                if not 0<=total<50:raise ValidationError('Up to 50 rows are available. Remove or edit an existing row.')
                edited=p.copy();edited[prefix+'-TOTAL_FORMS']=str(total+1)
                if suggestion is not None:
                    field, kind = ('text', 'decisions') if a=='add_decision' else ('description', 'actions')
                    proposals = r.result['proposals'][kind] if r else []
                    if not permitted(request.user,work,'meeting.record') or work.cancel_requested or domain.confirmation(work):
                        raise ValidationError('Open a current meeting confirmation before using an agent suggestion.')
                    if suggestion>=len(proposals) or proposals[suggestion]['evidence_id']!=note.pk:
                        raise ValidationError('Choose an exact suggestion citing the current notes.')
                    edited[f'{prefix}-{total}-{field}']=proposals[suggestion]['quote']
                form,decisions,commitments=capture_forms(work,data,r,edited,predecessor)
            elif a=='advance':
                from .factory_progress import set_progress
                set_progress(request.user,work.pk,revision,True)
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
            elif a=='request_review':
                domain.request_outward_review(request.user, work.pk, revision, case_revision, int(p['version'] or '0'))
            elif a=='review':
                domain.review_outward_draft(request.user, work.pk, revision, case_revision, int(p['version'] or '0'),
                                            p['verdict'], p['note'])
            if a not in ['add_decision','add_commitment','use_selected']:
                messages.success(request,'Minutes work updated');return redirect(request.get_full_path())
        except (ValidationError,ValueError) as exc:messages.error(request,str(exc));work.refresh_from_db();work.case.refresh_from_db()
    row=presentation(request.user,work);panel=row['minutes'];b=panel['document']
    delivery=domain.delivery_readback(work,request.user) if b and focus in [None,'recovery'] else []
    return render(request,'factory/minutes_detail.html',{'row':row,'case':work.case,'source':note,'focus':focus,'delivery':delivery,'inputs_form':inputs,'confirm_form':form,'decision_forms':decisions,'commitment_forms':commitments,'suggestions':suggestions,'can_confirm':focus in [None,'response'] and not panel['confirmation'] and permitted(request.user,work,'meeting.record') and not work.cancel_requested,'can_correct':focus in [None,'recovery'] and permitted(request.user,work,'factory.manage') and not work.cancel_requested,'can_request_review':focus in [None,'decision'] and panel['can_request_review'],'can_review':focus in [None,'decision'] and panel['can_review'],'can_operate':focus in [None,'recovery'] and permitted(request.user,work,'document.operate'),'activities':work.activities.order_by('pk') if not focus else [],'can_restart':focus in [None,'recovery'] and work.status=='cancelled' and permitted(request.user,work,'factory.manage')})

from .factory_views import ProfileForm
class MinutesProfileForm(ProfileForm):
    extraction_provider=forms.ChoiceField(required=False,choices=[('','No approved extraction provider'),('synthetic_meeting_v1','Isolated synthetic meeting extraction')])
    def clean_extraction_provider(self):return self.cleaned_data['extraction_provider'] or None

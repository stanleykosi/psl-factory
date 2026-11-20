"""P41 period, native source inventory, substantive client narrative and exact review."""
import json
from uuid import uuid4
from datetime import datetime
from urllib.parse import urlencode
from django import forms
from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.shortcuts import render,redirect
from django.urls import reverse
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from apps.core.models import Case,Evidence
from apps.core.workbench import granted
from apps.core.presentation import workspace_name
from apps.core.evidence_access import CONFIRMED_CHANGE_SOURCE, public_evidence, forecast_private_query
from apps.core.services import add_evidence
from apps.documents.models import Template
from apps.pmo.reporting import client_citation_ids, client_section_findings
from . import factory, factory_reporting as reporting, factory_reporting_drafts as drafts
from .factory_progress_views import StartWithBackground, started
from .factory_views import ProfileForm

class ReportingProfileForm(ProfileForm):
    def __init__(self,case,*args,**kwargs):
        super().__init__(case,*args,**kwargs)
        from django.contrib.auth import get_user_model
        users=get_user_model().objects.filter(is_active=True)
        for action in ['case.read','report.read','factory.execute','report.draft','document.draft','document.request_review']:
            users=users.filter(grant__case=case,grant__active=True,grant__action=action)
        self.fields['preparer_id']=forms.ModelChoiceField(queryset=users.distinct(),required=False,label='Existing weekly report preparer',help_text='Selection grants no project, source, review or publication authority.')
        self.fields['required_evidence_kinds'].initial=reporting.KIND
        self.fields['information_resolver_id'].widget=forms.HiddenInput();self.fields['information_resolver_id'].disabled=True
        self.fields['executor_id'].label='Authorized client document publisher'
        for action in ['case.read','report.read','document.publish']:
            self.fields['executor_id'].queryset=self.fields['executor_id'].queryset.filter(grant__case=case,grant__active=True,grant__action=action).distinct()

class ReportLocalDateTimeInput(forms.DateTimeInput):
    input_type='datetime-local'
    supports_microseconds=True

    def __init__(self):
        super().__init__(format='%Y-%m-%dT%H:%M:%S.%f',attrs={'step':'any'})

    def format_value(self,value):
        rendered=super().format_value(value)
        # Browser datetime-local controls accept milliseconds, not six-digit fractions.
        return rendered[:-3] if isinstance(value,datetime) else rendered


class ReportLocalDateTimeField(forms.DateTimeField):
    widget=ReportLocalDateTimeInput

    def prepare_value(self,value):
        if isinstance(value,str):
            try:value=parse_datetime(value) or value
            except ValueError:pass
        return super().prepare_value(value)


NARRATIVE_FIELDS = (
    ('status', 'Delivery progress', 'Records for delivery progress'),
    ('risks', 'Risks and issue impact', 'Records for risks and issue impact'),
    ('timeline', 'Milestone status', 'Records for milestones'),
    ('next_steps', 'Next steps', 'Records for next steps'),
)


class InputsForm(forms.Form):
    start_at=ReportLocalDateTimeField(label='Selected period start')
    end_at=ReportLocalDateTimeField(label='Selected period end (already elapsed)')
    def __init__(self,case,*args,actor,saved_sections=None,restored=None,partial=False,**kwargs):
        super().__init__(*args,**kwargs)
        self.partial = partial
        self.saved_sections = saved_sections or {}
        for name in ['start_at','end_at']:
            self.fields[name].help_text='Shown in '+timezone.get_current_timezone_name()+'. Unchanged stored boundaries retain their exact original precision.'
            self.fields[name].required = not partial
        self.fields['template_id']=forms.ModelChoiceField(queryset=Template.objects.filter(case=case,definition__document_type='status_report'),required=False,label='Controlled weekly client template')
        self.fields['content_id']=forms.ModelChoiceField(queryset=Evidence.objects.filter(case=case,kind='agent_private_report_content').exclude(forecast_private_query()).order_by('-pk'),required=False,label='Existing cited client narrative',empty_label='Not supplied, or enter all four themes below')
        from apps.pmo.models import Meeting,ActionItem,Milestone,Issue,ChangeRequest
        ids=set();confirmed_changes=set()
        def can(action):return actor.is_active and actor.grant_set.filter(case=case,action=action,active=True).exists()
        if can('report.read'):
            if can('meeting.read'):
                ids.update(Meeting.objects.filter(case=case).values_list('current__evidence_id',flat=True))
                ids.update(ActionItem.objects.filter(case=case).values_list('current__evidence_id',flat=True))
                ids.update(Milestone.objects.filter(case=case).values_list('evidence_id',flat=True))
            if can('issue.read'):ids.update(Issue.objects.filter(case=case).values_list('current__evidence_id',flat=True))
            if can('change.read'):
                confirmed_changes=set(ChangeRequest.objects.filter(case=case,current__evidence__source=CONFIRMED_CHANGE_SOURCE).values_list('current__evidence_id',flat=True))
                ids.update(ChangeRequest.objects.filter(case=case).values_list('current__evidence_id',flat=True))
        citations=public_evidence(Evidence.objects.filter(case=case,pk__in=ids))|Evidence.objects.filter(case=case,pk__in=confirmed_changes).exclude(forecast_private_query())
        citations = citations.only('pk').order_by('-pk')
        available_choices = [
            (pk, f'Confirmed change record #{pk}' if source == CONFIRMED_CHANGE_SOURCE
             else f'{kind.replace("_", " ").capitalize()} #{pk} · v{version} · {source}')
            for pk, kind, version, source in citations.values_list('pk', 'kind', 'version', 'source')
        ]
        for key, label, citations_label in NARRATIVE_FIELDS:
            self.fields[key] = forms.CharField(
                required=False, max_length=10000, label=label, widget=forms.Textarea(attrs={'rows': 3}),
                help_text='Use facts that are safe to share with the client or explain what information is missing.',
            )
            self.fields[f'{key}_citations'] = forms.ModelMultipleChoiceField(
                queryset=citations, required=False, label=citations_label,
            )
            self.fields[f'{key}_citations'].choices = available_choices
        self.fields['citation_ids'] = forms.ModelMultipleChoiceField(
            queryset=citations, required=False, widget=forms.MultipleHiddenInput,
        )
        if self.saved_sections:
            self.saved_content_id = self.initial.get('content_id')
            self.initial['content_id'] = None
            saved_ids = {pk for section in self.saved_sections.values() for pk in section['evidence_ids']}
            available = saved_ids.intersection(pk for pk, _ in available_choices)
            for key, section in self.saved_sections.items():
                self.initial[key] = section['text']
                self.initial[f'{key}_citations'] = [pk for pk in section['evidence_ids'] if pk in available]
        if restored:
            self.initial.update(drafts.form_initial(restored))
    def clean(self):
        cleaned=super().clean()
        for name in ['start_at','end_at']:
            if name not in cleaned or not self.initial.get(name):continue
            original=self.fields[name].to_python(self.initial[name])
            displayed=original.replace(microsecond=original.microsecond//1000*1000)
            # Only the trusted selected source supplies precision that the browser
            # cannot represent. A genuinely changed visible instant stays changed.
            if cleaned[name]==displayed:cleaned[name]=original
        keys = [key for key, _, _ in NARRATIVE_FIELDS]
        separate_citations = any(self.add_prefix(f'{key}_citations') in self.data for key in keys)
        legacy_ids = [record.pk for record in cleaned.get('citation_ids', ())]
        if self.has_error('citation_ids'):
            raise ValidationError('Choose available project records beside each part of the report.')
        if separate_citations and legacy_ids:
            raise ValidationError('Use the record choices beside each part of the report.')
        sections = {}
        for key in keys:
            ids = sorted(record.pk for record in cleaned.get(f'{key}_citations', ())) if separate_citations else legacy_ids
            sections[key] = {'text': cleaned.get(key, ''), 'evidence_ids': ids}
        if not self.partial and not any(section['text'] or section['evidence_ids'] for section in sections.values()):
            return cleaned
        if not self.partial and cleaned.get('content_id'):
            self.add_error('content_id', 'Choose an existing narrative or enter the four parts below.')
        if not separate_citations and self.saved_sections and set(legacy_ids) == {
            pk for section in self.saved_sections.values() for pk in section['evidence_ids']
        }:
            for key in keys:
                sections[key]['evidence_ids'] = self.saved_sections[key]['evidence_ids']
        for key, section in sections.items():
            if not self.partial:
                self.add_section_findings(key, client_section_findings(section['text'], section['evidence_ids']))
            elif len(section['evidence_ids']) > 18:
                findings = client_section_findings(section['text'], section['evidence_ids'])
                self.add_section_findings(key, {'evidence_ids': findings['evidence_ids']})
        cleaned['sections'] = sections
        return cleaned

    def add_section_findings(self, key, findings):
        for part, message in findings.items():
            field = key if part == 'text' else f'{key}_citations'
            if not self.has_error(field):
                self.add_error(field, message)

    def selection(self):
        data = self.cleaned_data
        return {
            'start_at': data['start_at'].isoformat() if data['start_at'] else '',
            'end_at': data['end_at'].isoformat() if data['end_at'] else '',
            'template_id': data['template_id'].pk if data['template_id'] else None,
            'content_id': data['content_id'].pk if data['content_id'] else None,
        }

    def draft_values(self, **details):
        return dict(selection=self.selection(), parts=self.cleaned_data['sections'], **details)

    def inputs(self, actor, case, *, require_complete=False):
        values = self.selection()
        sections = self.cleaned_data.get('sections')
        if require_complete and not values['template_id']:
            self.add_error('template_id', 'Choose a client report template before continuing.')
        if require_complete and not sections and not values['content_id']:
            self.add_error('content_id', 'Choose an existing narrative or complete all four parts below.')
        if self.errors:
            raise ValidationError('Complete the saved draft before continuing.')
        if not sections:
            if require_complete:
                snapshot = reporting.inventory(actor, case, values)
                reporting.client_content(case, snapshot, values['content_id'])
            return values
        snapshot = reporting.inventory(actor, case, values)
        permitted = client_citation_ids(case, snapshot)
        for key, section in sections.items():
            self.add_section_findings(key, client_section_findings(section['text'], section['evidence_ids'], permitted))
        if self.errors:
            raise ValidationError('Check the records selected for each part before preparing the report.')
        if self.saved_sections and all(
            section['text'] == self.saved_sections[key]['text'].strip()
            and set(section['evidence_ids']) == set(self.saved_sections[key]['evidence_ids'])
            for key, section in sections.items()
        ):
            values['content_id'] = self.saved_content_id
        else:
            payload = {'protocol': 'pmo-weekly-client-content/v1', 'sections': sections}
            values['content_id'] = add_evidence(
                actor, case.pk, 'agent_private_report_content', json.dumps(payload, sort_keys=True),
                'Human-supplied weekly client narrative',
            ).pk
        return values

class StartForm(StartWithBackground):
    definition=forms.CharField(initial=reporting.DEFINITION,widget=forms.HiddenInput)
    key=forms.CharField(max_length=100,widget=forms.HiddenInput)
    case=forms.ModelChoiceField(queryset=Case.objects.none(),label='Project')
    reference=forms.CharField(max_length=160,label='Describe this weekly reporting work')
    revision=forms.IntegerField(min_value=1,widget=forms.HiddenInput)
    draft_version=forms.IntegerField(min_value=1,required=False,widget=forms.HiddenInput)
    def __init__(self,actor,*args,case_id=None,partial=False,**kwargs):
        super().__init__(*args,**kwargs)
        self.fields['reference'].required = not partial
        cases=granted(actor,['report.read','factory.start','evidence.add']).filter(kind='project');self.fields['case'].queryset=cases;self.fields['case'].label_from_instance=workspace_name
        self.selected=cases.filter(pk=case_id).first() if case_id else None
        if self.selected:self.fields['case'].initial=self.selected;self.fields['revision'].initial=self.selected.revision
        if not self.is_bound:self.fields['key'].initial='REPORT-'+uuid4().hex

@require_http_methods(['GET','HEAD','POST'])
def create(request):
    posted = request.POST if request.method == 'POST' else None
    case_id = (posted if posted is not None else request.GET).get('case')
    saving = posted is not None and posted.get('action') == 'save_draft'
    try:
        form = StartForm(request.user, posted, case_id=case_id, partial=saving)
    except (ValidationError, ValueError):
        form = StartForm(request.user, data={})
        form.is_valid()
        form.add_error(None, 'Choose an available project')
    draft = None
    inputs = None
    if form.selected:
        if posted is None:
            draft = drafts.current(request.user, form.selected)
            if draft:
                form.initial.update({key: draft.values[key] for key in ('key', 'reference', 'background')})
                form.initial['draft_version'] = draft.pk
        inputs = InputsForm(form.selected, posted, actor=request.user, restored=draft, partial=saving)
    if posted is not None and form.is_valid() and inputs and inputs.is_valid():
        try:
            with transaction.atomic():
                data = form.cleaned_data
                if data['definition'] != reporting.DEFINITION or not data['key'].isascii():
                    raise ValidationError('Choose the registered weekly client report definition.')
                if posted.get('action') not in (None, 'start', 'save_draft'):
                    raise ValidationError('Choose a current weekly report action.')
                case, draft = drafts.lock_intake(request.user, data['case'].pk, data['revision'], data['draft_version'])
                if draft and draft.values['key'] != data['key']:
                    raise ValidationError('Open the current saved draft before continuing.')
                if saving:
                    details = {key: data[key] for key in ('key', 'reference', 'background')}
                    drafts.record(request.user, case, inputs.draft_values(**details), draft)
                    messages.success(request, 'Your weekly report draft was saved.')
                    return redirect(reverse('factory_create') + '?' + urlencode({'definition': reporting.DEFINITION, 'case': case.pk}))
                values = inputs.inputs(request.user, case, require_complete=bool(draft))
                case.refresh_from_db()
                work = reporting.start(request.user, case.pk, data['key'], values, data['reference'], case.revision)
                drafts.mark_submitted(draft, work)
                return started(request, work, data['background'])
        except ValidationError as exc:
            form.add_error(None, reporting.finding(exc))
    return render(request, 'factory/reporting_start.html', {
        'form': form, 'inputs_form': inputs, 'case': form.selected, 'draft': draft,
        'time_zone': timezone.get_current_timezone_name(),
    })

@require_http_methods(['GET','HEAD','POST'])
def detail(request,work,focus=None):
    from .screen_focus import require_action
    from .factory_views import presentation,permitted
    data=reporting.source(work,request.user,False)
    editing=request.GET.get('edit')=='1' and not focus and permitted(request.user,work,'factory.manage') and permitted(request.user,work,'evidence.add')
    returning = drafts.return_review_id(work) if editing else None
    draft = drafts.current(request.user, work.case, work, returning) if returning else None
    saved = None
    if editing and data['inputs']['content_id']:
        try:
            snapshot=reporting.inventory(request.user,work.case,data['inputs'])
            _,saved=reporting.client_content(work.case,snapshot,data['inputs']['content_id'])
        except (PermissionDenied,ValidationError):
            pass
    correction = request.POST if request.method == 'POST' and request.POST.get('action') in ('correct', 'save_draft') else None
    reason = correction.get('reason', '') if correction is not None else draft.values['reason'] if draft else ''
    form = InputsForm(
        work.case, correction, initial=dict(data['inputs']), actor=request.user, saved_sections=saved,
        restored=draft, partial=correction is not None and correction.get('action') == 'save_draft',
    )
    if request.method=='POST':
        try:
            d=request.POST;action=d.get('action');revision=int(d.get('revision','0'));case_revision=int(d.get('case_revision','0'))
            require_action(work, focus, action)
            if action=='advance':
                from .factory_progress import set_progress
                set_progress(request.user,work.pk,revision,True)
            elif action in ('correct', 'save_draft'):
                if not form.is_valid():raise ValidationError('Select exact report period, template and cited client narrative')
                with transaction.atomic():
                    case, work, returning, draft = drafts.lock_correction(
                        request.user, work.pk, revision, case_revision, int(d.get('draft_version') or '0'),
                    )
                    if action == 'save_draft':
                        drafts.record(request.user, case, form.draft_values(reason=reason), draft,
                                      work=work, return_id=returning)
                        messages.success(request, 'Your weekly report draft was saved.')
                        return redirect(reverse('factory_detail', args=[work.pk]) + '?edit=1#report-correction')
                    values = form.inputs(request.user, case, require_complete=bool(draft))
                    case.refresh_from_db()
                    corrected = reporting.correct(request.user, work.pk, revision, case.revision, values, reason)
                    drafts.mark_submitted(draft, corrected)
            elif action=='review':reporting.review(request.user,work.pk,revision,case_revision,int(d.get('version','0')),d.get('verdict',''),d.get('note',''))
            elif action=='cancel':reporting.cancel(request.user,work.pk,revision)
            elif action=='restart':reporting.restart(request.user,work.pk,revision,case_revision,d.get('reason',''))
            elif action=='resume':factory.manage(request.user,work.pk,revision,'resume')
            elif action=='reconcile':reporting.reconcile(request.user,work.pk,revision)
            elif action=='operate_delivery':reporting.operate(request.user,work.pk,revision,case_revision,int(d.get('job','0')),d.get('operation',''),d.get('reason',''))
            elif action=='adopt_profile':factory.adopt_profile(request.user,work.pk,revision,int(d.get('configuration','0')),d.get('reason',''))
            else:raise ValidationError('Choose a current weekly report action')
            messages.success(request,'Weekly report action recorded. Native review and recipient receipts remain separate.');return redirect(request.get_full_path())
        except (ValidationError,ValueError) as exc:messages.error(request,str(exc));work.refresh_from_db();work.case.refresh_from_db()
    row=presentation(request.user,work,include_progress=not focus)
    return render(request,'factory/reporting_detail.html',{'row':row,'case':work.case,'focus':focus,'inputs_form':form,'editing':editing,'time_zone':timezone.get_current_timezone_name(),'can_configure':permitted(request.user,work,'policy.configure'),'activities':work.activities.order_by('pk'), 'draft':draft, 'returning':returning, 'correction_reason':reason})

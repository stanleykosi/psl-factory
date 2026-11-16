"""Template version list with the same protected reads as owner review."""
from io import BytesIO
from uuid import uuid4

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST, require_safe

from adapters.case_uploads import read
from apps.core.read_budget import ReadBudget, ReadLimit, limit_queries
from apps.core import project_journey
from apps.identity.services import active_case_grants, require, visible_cases

from .models import Template, TemplateFile
from .contracts import FIELDS, PMO_DOCUMENT_TYPES, validate_template
from .template_access import visible_templates
from .template_lists import LIST_QUERY_LIMIT, template_page
from . import template_uploads


class FileForm(forms.Form):
    proof = forms.ModelChoiceField(queryset=None, label='Owner evidence for this version')
    file = forms.FileField(label='Word, Excel or PDF file')
    revision = forms.IntegerField(min_value=1, widget=forms.HiddenInput)
    request_key = forms.UUIDField(widget=forms.HiddenInput)


class UploadForm(FileForm):
    previous = forms.ModelChoiceField(queryset=Template.objects.none(), label='Template to revise')
    field_order = ['previous', 'proof', 'file']


SECTIONS = [(field, field.replace('_', ' ').capitalize()) for field in FIELDS]
AUDIENCES = ('internal', 'client', 'management')


class NewTemplateForm(FileForm):
    name = forms.CharField(max_length=160, label='Template name')
    document_type = forms.ChoiceField(choices=[(kind, kind.replace('_', ' ').capitalize()) for kind in sorted(PMO_DOCUMENT_TYPES)],
                                      label='Document type')
    required = forms.MultipleChoiceField(choices=SECTIONS, label='Required sections')
    internal = forms.MultipleChoiceField(choices=SECTIONS, required=False, label='Internal sections')
    client = forms.MultipleChoiceField(choices=SECTIONS, required=False, label='Client sections')
    management = forms.MultipleChoiceField(choices=SECTIONS, required=False, label='Management sections')
    field_order = ['name', 'document_type', 'required', *AUDIENCES, 'proof', 'file']

    def clean(self):
        values = super().clean()
        if self.errors:
            return values
        values['definition'] = {'document_type': values.pop('document_type'), 'required_fields': values.pop('required'),
                                'audience_fields': {audience: values[audience] for audience in AUDIENCES if values[audience]}}
        for audience in AUDIENCES:
            values.pop(audience)
        validate_template(values['definition'])
        return values


def show(request, case, tabs, form=None):
    require(request.user, case, 'document.read')
    context = {'case': case, 'tab': 'templates', 'tabs': tabs}
    status = 200
    try:
        with limit_queries(LIST_QUERY_LIMIT):
            context['versions'], context['next_url'] = template_page(request, case)
            ids = [version.pk for version in context['versions']]
            attached = set(TemplateFile.objects.filter(template_id__in=ids).values_list('template_id', flat=True))
            for version in context['versions']:
                version.has_file = version.pk in attached
            grants = active_case_grants(request.user, [case.pk])
            if all((case.pk, action) in grants for action in ('document.template', 'evidence.add')):
                if not isinstance(form, UploadForm):
                    new = form
                    form = UploadForm(initial={'revision': case.revision, 'request_key': uuid4()})
                    form.fields['previous'].queryset = Template.objects.filter(pk__in=ids).order_by('name', '-version').defer('definition')
                    form.fields['proof'].queryset = recent_proofs(case)
                else:
                    new = None
                if new is None:
                    new = NewTemplateForm(auto_id='new_template_%s', initial={'revision': case.revision, 'request_key': uuid4()})
                    new.fields['proof'].queryset = recent_proofs(case)
                context['upload_form'] = form
                context['new_template_form'] = new
    except ValidationError:
        context['error'] = 'This page link has expired. Return to the first page to continue.'
        status = 400
    except ReadLimit:
        context['error'] = 'The template history needs a closer review. Open its owner records to continue.'
        status = 503
    return render(request, 'design/template_catalog.html', context, status=status)


def recent_proofs(case):
    proofs = template_uploads.proofs(case)
    return proofs.filter(pk__in=proofs.order_by('-pk').values('pk')[:25]).order_by('-pk')


@login_required
@require_POST
@never_cache
def upload(request, case_id):
    case = get_object_or_404(visible_cases(request.user), kind='project', pk=case_id)
    for action in ('document.read', 'document.template', 'evidence.add'):
        require(request.user, case, action)
    first = request.POST.get('operation') == 'first'
    form = (NewTemplateForm if first else UploadForm)(request.POST, request.FILES, auto_id='new_template_%s' if first else 'id_%s')
    # An exact selected template can be in another catalogue page.
    previous = request.POST.get('previous', '')
    form.fields['proof'].queryset = recent_proofs(case)
    try:
        if not first and previous.isascii() and previous.isdecimal() and len(previous) < 19:
            form.fields['previous'].queryset = visible_templates(request.user, case, candidate_ids=[int(previous)], budget=ReadBudget())
        if form.is_valid():
            template_uploads.submit(request.user, case, **form.cleaned_data)
            messages.success(request, 'Template version recorded. Its current use can be reviewed separately.')
            return redirect('design_project_tab', case.pk, 'templates')
    except ValidationError as exc:
        form.add_error(None, exc)
    except OSError:
        form.add_error(None, 'The private file store is unavailable. Try this upload again.')
    except ReadLimit:
        return render(request, 'design/template_download_unavailable.html', {'case': case}, status=503)
    grants = {action for _, action in active_case_grants(request.user, [case.pk])}
    return show(request, case, project_journey.tabs(case, grants), form)


@login_required
@require_safe
@never_cache
def download(request, case_id, template_id):
    case = get_object_or_404(visible_cases(request.user), kind='project', pk=case_id)
    try:
        candidates = visible_templates(request.user, case, candidate_ids=[template_id], budget=ReadBudget())
        attachment = get_object_or_404(TemplateFile.objects.select_related('upload', 'template'), case=case, template__in=candidates)
        if attachment.upload.case_id != case.pk or attachment.upload.actor_id != attachment.template.created_by_id:
            raise Http404
        data = read(attachment.upload)
    except (ValidationError, OSError, ReadLimit):
        return render(request, 'design/template_download_unavailable.html', {'case': case}, status=503)
    return FileResponse(BytesIO(data), as_attachment=True, filename=attachment.filename, content_type='application/octet-stream')

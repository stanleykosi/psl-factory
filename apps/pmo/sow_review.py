"""Compare and review the exact controlled statement of work prepared for a project."""
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods

from apps.core.evidence_access import public_evidence
from apps.documents import controlled, template_current
from apps.documents.design_review import ReviewForm, possible_verdicts, sources_for
from apps.documents.models import Publication, PublicationReceipt
from apps.identity.services import active_case_grants, require, visible_cases
from apps.workflows.models import HumanTask

from . import commercial
from .models import CommercialRevision


def exact(case, version_id):
    return commercial.sow_bindings(case).filter(version_id=version_id).select_related(
        'version__document', 'version__template', 'revision__dossier').first()


def previous_version(case, binding):
    version = binding.version
    history = commercial.sow_bindings(case).filter(revision__dossier=binding.revision.dossier)
    previous = history.filter(version__document_id=version.document_id, version__number__lt=version.number).order_by(
        '-version__number').select_related('version__document').first()
    if previous is None and binding.revision.previous_id:
        previous = history.filter(revision_id=binding.revision.previous_id).order_by('-pk').select_related(
            'version__document').first()
    if previous is not None:
        try:
            sources_for(case, previous.version)
        except Http404:
            return None
    return previous


def differences(before, after):
    old = {section['heading']: section['text'] for section in before.payload['sections']}
    new = {section['heading']: section['text'] for section in after.payload['sections']}
    return [{'heading': key, 'before': old.get(key), 'after': new.get(key)}
            for key in dict.fromkeys([*new, *old]) if old.get(key) != new.get(key)]


def corrected_proposal(case, binding, actions):
    version = binding.version
    if (not {'commercial.submit', 'document.draft'}.issubset(actions) or version.document.current_id != version.pk
            or not commercial.returned_statement(version)
            or Publication.objects.filter(version__document_id=version.document_id).exists()):
        return None
    corrected = CommercialRevision.objects.filter(pk=binding.revision.dossier.current_id,
        dossier=binding.revision.dossier, previous_id=binding.revision_id).first()
    if corrected is not None and not commercial.sow_bindings(case).filter(revision=corrected).exists():
        try:
            commercial.current_revision(case, corrected.pk)
            commercial.valid_approvals(corrected)
        except (ValidationError, PermissionDenied):
            return None
        return None if commercial.terminal(corrected) else corrected
    return None


@login_required
@require_http_methods(['GET', 'HEAD', 'POST'])
@never_cache
def show(request, case_id, version_id):
    actor = request.user
    case = get_object_or_404(visible_cases(actor), pk=case_id, kind='project')
    require(actor, case, 'commercial.read')
    require(actor, case, 'document.read')
    binding = exact(case, version_id)
    if binding is None:
        raise Http404
    version = binding.version
    sources = sources_for(case, version)
    costing = public_evidence(case.evidence.filter(pk=binding.revision.sources.get('costing'), kind='costing')).only(
        'version', 'kind').first()
    if costing is None:
        raise Http404
    actions = {action for _, action in active_case_grants(actor, [case.pk])}
    current = version.document.current_id == version.pk and binding.revision.dossier.current_id == binding.revision_id
    task = HumanTask.objects.filter(version=version).first()
    latest = version.reviews.select_related('actor').order_by('-pk').first()
    findings = controlled.preflight(version)
    choices = possible_verdicts(actor, case, task) if (current and not findings and task and task.status == 'open'
              and 'document.review_controlled' in actions) else []
    form = ReviewForm(request.POST if request.method == 'POST' else None, initial={'revision': case.revision}) if choices else None
    if form is not None:
        form.fields['verdict'].choices = choices
    can_request = current and not task and not findings and 'document.request_review' in actions
    corrected = corrected_proposal(case, binding, actions)
    if request.method == 'POST':
        try:
            operation = request.POST.get('action')
            if operation == 'review' and form and form.is_valid():
                verdict, delegation = form.cleaned_data['verdict'].split(':')
                controlled.review_version(actor, case.pk, version.pk, verdict, form.cleaned_data['note'],
                                          form.cleaned_data['revision'], delegation == '1')
            elif operation == 'request' and can_request:
                controlled.request_review(actor, case.pk, version.pk, int(request.POST.get('revision', '0')))
            elif operation == 'prepare' and corrected and request.POST.get('proposal') == str(corrected.pk):
                successor = commercial.draft_submission(actor, case.pk, corrected.pk, version.template_id,
                    int(request.POST.get('revision', '0')), template_scope_id=version.template_current_manifest.get('scope_id'),
                    replaces_version_id=version.pk)
                return redirect('design_sow_review', case.pk, successor.pk)
            else:
                raise ValidationError('Choose a review action available for this exact statement.')
        except (ValidationError, ValueError) as error:
            if form:
                form.add_error(None, error if isinstance(error, ValidationError) else 'Refresh and review the current version.')
            else:
                findings = [str(error), *findings]
        else:
            return redirect('design_sow_review', case.pk, version.pk)
    previous = previous_version(case, binding)
    compared = request.GET.get('compare') == '1' and previous is not None
    changes = differences(previous.version, version) if previous else []
    costing_unchanged = previous and previous.revision.sources.get('costing') == costing.pk
    publication = Publication.objects.filter(version=version).first()
    receipt_count = PublicationReceipt.objects.filter(publication=publication).count() if publication else 0
    template_status = 'Template recorded'
    if version.template_current_manifest:
        template_status = ('Current template needs rechecking' if template_current.findings(version) else 'Current template verified')
    return render(request, 'design/sow_review.html', {
        'case': case, 'binding': binding, 'version': version, 'current': current, 'sources': sources,
        'template_status': template_status, 'costing': costing, 'current_costing': current and not commercial.binding_findings(binding),
        'findings': findings, 'previous': previous, 'compared': compared, 'changes': changes,
        'costing_unchanged': costing_unchanged,
        'task': task, 'latest_review': latest, 'form': form, 'choices': choices, 'can_request': can_request,
        'corrected': corrected,
        'publication': publication, 'receipt_count': receipt_count,
    }, status=400 if request.method == 'POST' else 200)

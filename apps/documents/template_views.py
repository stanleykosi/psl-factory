from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import Http404
from django.shortcuts import render, redirect
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_safe
from apps.core.views import accessible_case
from apps.identity.services import require
from apps.identity.models import Grant
from .models import TemplateScope
from .template_forms import SourceForm, ScopeForm, ClaimForm, OwnerPolicyForm
from . import template_current as current
from .template_access import visible_scopes, visible_sources, visible_templates
from .template_lists import read_workbench
from .template_source_reader import (
    InvalidOwnerSelection, MAX_OWNER_RECORDS, read_owner_metadata, read_owner_pin, read_source, SourceReadUnavailable,
)


@transaction.non_atomic_requests
@login_required
@require_safe
@never_cache
def source_detail(request, case_id, source_id):
    try:
        result = read_source(request.user, case_id, source_id)
    except SourceReadUnavailable:
        return render(request, 'documents/template_source.html', status=503)
    if result is None:
        raise Http404
    case, source = result
    return render(request, 'documents/template_source.html', {'case': case, 'source': source})


@transaction.non_atomic_requests
@login_required
@require_safe
@never_cache
def owner_pin_detail(request, case_id, kind, pk):
    try:
        result = read_owner_pin(request.user, case_id, kind, pk, recorded_inventory=request.GET.get('inventory') == '1')
    except SourceReadUnavailable:
        return render(request, 'documents/template_owner_pin.html', status=503)
    if result is None:
        raise Http404
    case, pin = result
    return render(request, 'documents/template_owner_pin.html', {'case': case, 'pin': pin})


@transaction.non_atomic_requests
@login_required
@require_safe
@never_cache
def owner_metadata(request, case_id):
    try:
        result = read_owner_metadata(request.user, case_id, request.GET.getlist('record'))
    except InvalidOwnerSelection:
        return render(request, 'documents/template_owner_history.html', {'selection_limit': MAX_OWNER_RECORDS}, status=400)
    except SourceReadUnavailable:
        return render(request, 'documents/template_owner_history.html', status=503)
    if result is None:
        raise Http404
    case, records = result
    return render(request, 'documents/template_owner_history.html', {'case': case, 'records': records})


@login_required
def workbench(request, case_id):
    import json

    case = accessible_case(request.user, case_id)
    require(request.user, case, 'document.read')
    forms = {'source': SourceForm(), 'scope': ScopeForm(), 'claim': ClaimForm(), 'owner_policy': OwnerPolicyForm()}
    action = request.POST.get('action') if request.method == 'POST' else None
    if action in forms:
        forms[action] = type(forms[action])(request.POST)
    if request.method == 'POST':
        try:
            p = request.POST
            expected = int(p['revision'])
            if action in forms:
                form = forms[action]
                _submitted_choices(form, request, case)
                if not form.is_valid():
                    raise ValidationError(form.errors.as_text())
                d = form.cleaned_data
                if action == 'source':
                    current.capture_source(request.user, case.pk, d['body'], d['locator'], expected)
                elif action == 'scope':
                    current.register_scope(request.user, case.pk, d['document_type'], d['audience'], d['purpose'], d['context'], d['source_owner'], d['evidence'].pk, expected)
                elif action == 'claim':
                    current.claim_current(request.user, case.pk, d['scope'].pk, d['template'].pk, d['evidence'].pk, d['note'], expected, confirm_owner=d['confirm_owner'])
                else:
                    current.draft_owner_policy(request.user, case.pk, d['content'], d['evidence'].pk, d['effective_from'], expected)
            elif action == 'resolve':
                current.resolve_claims(request.user, case.pk, int(p['scope']), int(p['selected_claim']), json.loads(p['claim_ids']), int(p['evidence']), p['note'], expected)
            elif action == 'retract':
                current.retract_claim(request.user, case.pk, int(p['claim']), int(p['evidence']), p['note'], expected)
            else:
                raise ValidationError('Unknown template claim action')
            messages.success(request, 'Template evidence recorded. Only an explicit current-owner assertion establishes currentness; existing documents are unchanged.')
            return redirect('template_current', case_id=case.pk)
        except (ValidationError, ValueError, KeyError) as exc:
            messages.error(request, str(exc))
            case.refresh_from_db()
    try:
        lists = read_workbench(request, case)
    except (ValidationError, SourceReadUnavailable) as exc:
        response = render(request, 'documents/template_current.html', {
            'case': case, 'list_error': 'This page could not be opened. Return to template claims to restart.',
        }, status=400 if isinstance(exc, ValidationError) else 503)
        response['Cache-Control'] = 'no-store'
        return response
    for key in ('scope', 'claim', 'owner_policy'):
        choices = [(source.pk, f'Source #{source.pk} · version {source.version} · {source.source}')
                   for source in lists['sources'] if key != 'owner_policy' or source.kind == 'policy_decision']
        forms[key].fields['evidence'].widget.choices = [('', 'Select source'), *choices]
    forms['claim'].fields['scope'].widget.choices = [('', 'Select scope'), *((scope.pk, str(scope)) for scope in lists['scopes'])]
    forms['claim'].fields['template'].widget.choices = [('', 'Select template'), *((t.pk, str(t)) for t in lists['templates'])]
    response = render(request, 'documents/template_current.html', {**lists, 'case': case, 'forms': forms,
        'owner_selection_limit': MAX_OWNER_RECORDS,
        'actions': set(Grant.objects.filter(case=case, user=request.user, active=True).values_list('action', flat=True))})
    response['Cache-Control'] = 'no-store'
    return response


def _submitted_choices(form, request, case):
    def submitted_id(name):
        value = request.POST.get(name, '')
        if not value.isascii() or not value.isdecimal() or len(value) > 19 or not 0 < int(value) < 2**63:
            raise ValidationError('Select an exact record on this case.')
        return int(value)

    if 'evidence' in form.fields:
        evidence = visible_sources(request.user, case, source_id=submitted_id('evidence')).defer('body')
        if isinstance(form, OwnerPolicyForm):
            evidence = evidence.filter(kind='policy_decision')
        form.fields['evidence'].queryset = evidence
    if isinstance(form, ClaimForm):
        scope = TemplateScope.objects.filter(pk=submitted_id('scope'))
        form.fields['scope'].queryset = visible_scopes(request.user, case, scopes=scope)
        form.fields['template'].queryset = visible_templates(
            request.user, case, candidate_ids=[submitted_id('template')],
        )

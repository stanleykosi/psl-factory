from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods

from apps.finance.client_billing import current_coverages
from apps.identity.services import active_case_grants, visible_cases

from . import client_workspace_links as links
from .evidence_access import CLIENT_WORKSPACE_LINK_PROOF
from .models import ClientWorkspaceLink, Evidence


class ProposalForm(forms.Form):
    revision = forms.IntegerField(min_value=1, widget=forms.HiddenInput)
    action = forms.ChoiceField(label='Change', choices=[('link', 'Link to a client'), ('unlink', 'Remove the link')])
    coverage = forms.ModelChoiceField(queryset=None, required=False, label='Current billing coverage')
    issuer = forms.CharField(required=False, max_length=100, label='Customer register code')
    reference = forms.CharField(required=False, max_length=100, label='Client reference in that register')
    name = forms.CharField(required=False, max_length=160, label='Client name in that register')
    source = forms.CharField(max_length=500, label='Original record or decision reference')

    def __init__(self, case, data=None):
        super().__init__(data, initial={'revision': case.revision})
        rows = current_coverages(case).order_by('customer', 'reference', 'pk')
        self.fields['coverage'].queryset = rows.filter(pk__in=rows.values('pk')[:100])
        self.fields['coverage'].label_from_instance = lambda row: f'{row.customer} · {row.reference}'


class ReviewForm(forms.Form):
    revision = forms.IntegerField(min_value=1)
    evidence = forms.IntegerField(min_value=1)


@login_required
@require_http_methods(['GET', 'HEAD', 'POST'])
@never_cache
def detail(request, case_id):
    actor = request.user
    case = get_object_or_404(visible_cases(actor), pk=case_id, kind='project')
    links.authorise(actor, case)
    grants = {action for _, action in active_case_grants(actor, [case.pk])}
    operation = request.POST.get('operation') if request.method == 'POST' else None
    can_propose = {'finance.billing.register', 'evidence.add'}.issubset(grants)
    form = ProposalForm(case, request.POST if operation == 'propose' else None) if can_propose else None
    try:
        if operation == 'propose':
            if not form:
                raise PermissionDenied
            if form.is_valid():
                value = form.cleaned_data
                links.propose(actor, case, value['revision'], action=value['action'], issuer=value['issuer'],
                              reference=value['reference'], name=value['name'], source=value['source'],
                              coverage_id=value['coverage'].pk if value['coverage'] else None)
                messages.success(request, 'Client link saved for independent review.')
                return redirect(request.path)
        elif operation == 'confirm':
            review = ReviewForm(request.POST)
            if not review.is_valid():
                raise ValidationError('Choose the exact proposed client link.')
            links.confirm(actor, case, review.cleaned_data['revision'], review.cleaned_data['evidence'])
            messages.success(request, 'Client link decision recorded.')
            return redirect(request.path)
        elif request.method == 'POST':
            raise ValidationError('Choose a current client link action.')
    except ValidationError as exc:
        if operation == 'propose' and form:
            form.add_error(None, exc)
        else:
            messages.error(request, ' '.join(exc.messages))
    case.refresh_from_db(fields=['revision'])
    history = list(ClientWorkspaceLink.objects.filter(case=case).select_related('reviewer', 'evidence', 'coverage')
                   .defer('evidence__body').order_by('-number')[:10])
    current = history[0] if history else None
    candidates = Evidence.objects.filter(case=case, kind=CLIENT_WORKSPACE_LINK_PROOF, clientworkspacelink__isnull=True)
    proposals = []
    for source in candidates.select_related('created_by').order_by('-pk')[:20]:
        try:
            value = links.facts_from(source)
            coverage, _, name = links.validate(case, value)
        except ValidationError:
            continue
        if value['previous'] == (current.pk if current else None):
            proposals.append({'evidence': source, 'coverage': coverage, 'name': name, 'facts': value,
                              'can_confirm': 'policy.activate' in grants and source.created_by_id != actor.pk})
    coverage_changed = bool(current and current.coverage_id and not current_coverages(case).filter(pk=current.coverage_id).exists())
    return render(request, 'design/client_workspace_link.html', {
        'case': case, 'form': form, 'current': current, 'history': history[1:], 'proposals': proposals,
        'coverage_changed': coverage_changed,
    })

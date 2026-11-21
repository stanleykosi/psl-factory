from django import forms
from urllib.parse import urlencode
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods
from django.urls import reverse
from apps.core.views import accessible_case
from . import costing, costing_proposals
from .costing_proposal_models import CostingProposal
from .costing_models import CostingOracle


class DecisionForm(forms.Form):
    revision = forms.IntegerField(min_value=1, widget=forms.HiddenInput)
    verdict = forms.ChoiceField(choices=[('confirm', 'Confirm this proposed version'),
                                       ('return', 'Return for changes')])
    note = forms.CharField(max_length=2000, label='Reason', widget=forms.Textarea(attrs={'rows': 3}))
    evidence = forms.ModelChoiceField(queryset=None, label='Decision proof')

    def __init__(self, case, *args, own=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['evidence'].queryset = case.evidence.filter(kind='p14_review').order_by('-pk')
        if own:
            self.fields['verdict'].choices = [('withdraw', 'Withdraw this proposed version')]


@login_required
@require_http_methods(['GET', 'HEAD', 'POST'])
@never_cache
def detail(request, case_id, pk):
    case = accessible_case(request.user, case_id)
    costing.readable(request.user, case, True)
    proposal = get_object_or_404(CostingProposal.objects.select_related(
        'base__case', 'actor', 'decision__actor', 'decision__rule'), base__case=case, pk=pk)
    context = costing_proposals.presentation(request.user, proposal)
    example_sets = list(CostingOracle.objects.filter(rule=proposal.base).only('reference', 'version').order_by('pk')[:25])
    proposed_sets = costing_proposals.proposed_example_sources(request.user, proposal)
    proposed_key = request.GET.get('proposed_examples')
    proposed_set = next((item for item in proposed_sets if str(item['proof'].pk) == proposed_key), None)
    selected_set = next((row for row in example_sets if str(row.pk) == request.GET.get('examples')), None)
    if (request.GET.get('examples') and selected_set is None) or (proposed_key and proposed_set is None):
        raise Http404
    if proposed_set is None and not request.GET.get('examples') and len(proposed_sets) == 1:
        proposed_set = proposed_sets[0]
    if selected_set is None and proposed_set is None and len(example_sets) == 1:
        selected_set = example_sets[0]
    selection = {}
    comparison = None
    if proposed_set is not None:
        comparison = {'examples': costing_proposals.example_rows(proposal, proposed_set['value']),
                      'source_locator': proposed_set['value']['source_locator']}
        selection = {'proposed_examples': proposed_set['proof'].pk}
    elif selected_set is not None:
        comparison = costing_proposals.compare_examples(request.user, proposal, selected_set.pk)
        selection = {'examples': selected_set.pk}
    selected_example = None
    if comparison:
        example_rows = comparison['examples']
        selected_index = next((index for index, row in enumerate(example_rows)
            if row['key'] == request.GET.get('example')), 0)
        selected_example = example_rows[selected_index]
        page_url = reverse('costing_proposal', args=[case.pk, proposal.pk])
        for row in example_rows:
            row['url'] = page_url + '?' + urlencode({**selection, 'example': row['key']})
        context.update(previous_example=example_rows[selected_index - 1] if selected_index > 0 else None,
                       next_example=example_rows[selected_index + 1] if selected_index + 1 < len(example_rows) else None)
    form = DecisionForm(case, request.POST if request.method == 'POST' else None,
                        own=context['own'], initial={'revision': case.revision})
    if request.method == 'POST':
        try:
            if set(request.POST) - set(form.fields) - {'csrfmiddlewaretoken'} or not form.is_valid():
                raise ValidationError('Check the decision fields.')
            value = form.cleaned_data
            costing_proposals.decide(request.user, case.pk, proposal.pk, value['verdict'],
                value['note'], value['evidence'].pk, value['revision'])
            messages.success(request, 'Decision recorded. The calculator source and project-cost approvals retain their own checks.')
            return redirect('costing_proposal', case_id=case.pk, pk=proposal.pk)
        except ValidationError as exc:
            form.add_error(None, ' '.join(exc.messages))
    context.update(case=case, form=form, example_sets=example_sets, comparison=comparison,
                   selected_example=selected_example, selected_set=selected_set,
                   proposed_sets=proposed_sets, proposed_set=proposed_set,
                   active_successor=costing_proposals.active_successor(request.user, proposal))
    return render(request, 'pmo/costing_proposal.html', context)

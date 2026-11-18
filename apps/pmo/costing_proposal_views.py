from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods
from apps.core.views import accessible_case
from . import costing, costing_proposals
from .costing_proposal_models import CostingProposal


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
    context.update(case=case, form=form)
    return render(request, 'pmo/costing_proposal.html', context)

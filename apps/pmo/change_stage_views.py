from django import forms
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods

from apps.core.read_budget import ReadLimit
from apps.identity.services import visible_cases

from . import change_stage_links as links


class ChangeMilestoneForm(forms.Form):
    stage = forms.ChoiceField(label='Signed milestone')
    plan = forms.TypedChoiceField(label='Current change and its recorded plan', coerce=int)
    scope_note = forms.CharField(label='What is being added to this milestone?', max_length=240,
                                 widget=forms.Textarea(attrs={'rows': 3}))
    revision = forms.IntegerField(min_value=1, widget=forms.HiddenInput)

    def __init__(self, *args, stages, plans, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['stage'].choices = [('', 'Choose a milestone'), *stages]
        self.fields['plan'].choices = [('', 'Choose a current change'), *plans]


@login_required
@require_http_methods(['GET', 'POST'])
@never_cache
def milestone_link(request, case_id):
    case = get_object_or_404(visible_cases(request.user), pk=case_id, kind='project')
    links.require_access(request.user, case, links.MANAGE_ACTIONS)
    try:
        stages, plans, limited = links.options(case)
    except ReadLimit:
        stages, plans, limited = [], [], True
    form = ChangeMilestoneForm(request.POST if request.method == 'POST' else None, stages=stages, plans=plans,
                               initial={'revision': case.revision})
    if request.method == 'POST' and form.is_valid():
        values = form.cleaned_data
        try:
            links.record(request.user, case.pk, stage=values['stage'], plan_id=values['plan'],
                         scope_note=values['scope_note'], expected=values['revision'])
        except ValidationError as error:
            form.add_error(None, error)
        else:
            return redirect('design_project_tab', case.pk, 'milestones')
    return render(request, 'design/project_change_milestone.html', {
        'case': case, 'form': form, 'stages': stages, 'plans': plans, 'limited': limited,
    }, status=400 if request.method == 'POST' else 200)

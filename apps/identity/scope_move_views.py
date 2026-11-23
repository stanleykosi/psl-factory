from uuid import uuid4

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods

from apps.core.templatetags.studio_ui import readable

from . import primary_roles, scope_moves, teams
from .services import visible_cases
from .team_models import StaffTeam


MOVE_LABELS = {**primary_roles.ACTION_LABELS, 'case.read':'View the workspace',
               'action.own':'Own workspace actions', 'action.work':'Update assigned actions'}


class ScopeForm(forms.Form):
    role = forms.ChoiceField(label='Base role', choices=[(key, name) for key,(name,_,_) in primary_roles.BUILT_INS.items()])
    mode = forms.ChoiceField(label='Work scope', choices=teams.MODE_LABELS.items())
    team_id = forms.ModelChoiceField(label='Team', queryset=StaffTeam.objects.none(), required=False)

    def __init__(self, case, data=None, **kwargs):
        super().__init__(data, **kwargs)
        self.fields['team_id'].queryset = StaffTeam.objects.filter(case=case).order_by('name','pk')
        self.fields['team_id'].label_from_instance = lambda team: team.name


class ConfirmForm(forms.Form):
    role = forms.CharField(widget=forms.HiddenInput, max_length=20)
    mode = forms.CharField(widget=forms.HiddenInput, max_length=12)
    team_id = forms.IntegerField(widget=forms.HiddenInput, required=False, min_value=1)
    fingerprint = forms.RegexField(r'\A[a-f0-9]{64}\Z', widget=forms.HiddenInput)
    operation = forms.UUIDField(widget=forms.HiddenInput)
    reason = forms.CharField(label='Reason for the move', max_length=1000, widget=forms.Textarea(attrs={'rows':3}))
    confirmed = forms.BooleanField(label='I reviewed the access removed and the work this person keeps.')


@login_required
@require_http_methods(['GET','HEAD','POST'])
@never_cache
def move(request, case_id, person_id):
    case = get_object_or_404(visible_cases(request.user), pk=case_id, kind='project')
    primary_roles.administrator(request.user, case)
    selection = ScopeForm(case, request.GET if 'role' in request.GET else None)
    preview = confirmation = problem = None
    if request.method == 'POST':
        confirmation = ConfirmForm(request.POST)
        if confirmation.is_valid():
            fields = {key:value for key,value in confirmation.cleaned_data.items() if key != 'confirmed'}
            try:
                scope_moves.apply(request.user,case.pk,person_id,**fields)
            except (ValidationError,PermissionDenied) as error:
                problem = 'Review the current permitted access and open work again.' if isinstance(error,PermissionDenied) else error.messages[0]
            else:
                messages.success(request,'Staff work was moved to the reviewed role scope.')
                return redirect('staff_person',person_id=person_id)
    elif selection.is_valid():
        selected = selection.cleaned_data
        team = selected['team_id']
        fields = {'role':selected['role'],'mode':selected['mode'],'team_id':team.pk if team else None}
        try:
            preview = scope_moves.prepare(request.user,case,person_id,**fields)
        except (ValidationError,PermissionDenied) as error:
            problem = 'This administrator cannot review the full access change.' if isinstance(error,PermissionDenied) else error.messages[0]
        else:
            preview['label'] = teams.describe_pin(preview['scope'])
            preview['removed_labels'] = [MOVE_LABELS.get(row['action'],readable(row['action'])) for row in preview['grants']]
            if not preview['holds']:
                confirmation = ConfirmForm(initial={**fields,'fingerprint':preview['fingerprint'],'operation':uuid4()})
    person = primary_roles.person_for(case, person_id)
    return render(request,'identity/staff_scope_move.html',{'case':case,'person':person,'selection':selection,
                                           'preview':preview,'confirmation':confirmation,'problem':problem})

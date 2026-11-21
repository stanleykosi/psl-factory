from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ObjectDoesNotExist, PermissionDenied, ValidationError
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods, require_safe

from apps.identity.services import active_case_grants, visible_cases
from apps.pmo.models import ActionItem
from apps.workflows.models import HumanTask

from . import role_factory_decisions, role_native_decisions, role_work, teams
from .team_models import TEAM_ROLES, StaffAssignment, StaffMembership, StaffTeam


def page_number(value):
    if value and value.isascii() and value.isdecimal() and len(value) <= 4 and 1 <= int(value) <= 9999:
        return int(value)
    return 1


@login_required
@require_safe
@never_cache
def dashboard(request):
    return render(request, 'identity/role_dashboard.html', role_work.dashboard(request.user, page_number(request.GET.get('page'))))


class UpdateForm(forms.Form):
    expected = forms.IntegerField(min_value=1, widget=forms.HiddenInput)
    case_expected = forms.IntegerField(min_value=1, widget=forms.HiddenInput)
    action_revision = forms.IntegerField(min_value=1, required=False, widget=forms.HiddenInput)
    token = forms.RegexField(r'\A[a-f0-9]{64}\Z', required=False, widget=forms.HiddenInput)
    reason = forms.CharField(max_length=1000, label='Work note or decision reason', widget=forms.Textarea(attrs={'rows': 3}))


@login_required
@require_http_methods(['GET','HEAD','POST'])
@never_cache
def detail(request, assignment_id):
    row = role_work.entry_for(request.user, assignment_id)
    value = role_work.detail(request.user, row)
    initial = {'expected': value['revision'], 'case_expected': value['case_revision'],
               'action_revision': value.get('action_revision'), 'token': (value['review'] or {}).get('token')}
    form = UpdateForm(request.POST if request.method == 'POST' else None, initial=initial)
    if request.method == 'POST' and form.is_valid():
        data = form.cleaned_data
        operation = request.POST.get('operation')
        args = (request.user, row.pk, operation, data['reason'], data['expected'], data['case_expected'])
        try:
            if operation in role_work.DECISIONS:
                role_work.decide(*args, data['token'])
            else:
                role_work.act(*args, data['action_revision'])
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            messages.success(request, 'The work record was updated.')
            return redirect('role_work_detail', assignment_id=row.pk)
    return render(request, 'identity/role_work.html', {'item': value, 'form': form})


class TeamForm(forms.Form):
    role = forms.ChoiceField(label='Base role', choices=[(role, teams.scope_label(role, 'lead')) for role in TEAM_ROLES])
    name = forms.CharField(max_length=80, label='Team name')


class AssignmentForm(forms.Form):
    member = forms.ModelChoiceField(queryset=StaffMembership.objects.none(), label='Assign to')
    action = forms.ModelChoiceField(queryset=ActionItem.objects.none(), required=False, label='Existing action')
    reference = forms.CharField(max_length=160, required=False, label='New action reference')
    description = forms.CharField(max_length=1000, required=False, label='Work to do', widget=forms.Textarea(attrs={'rows': 2}))
    due_at = forms.DateTimeField(required=False, label='Due date and time', widget=forms.DateTimeInput(attrs={'type':'datetime-local'}))
    work_id = forms.IntegerField(min_value=1, required=False, label='Linked factory work number')
    reason = forms.CharField(max_length=1000, label='Assignment reason', widget=forms.Textarea(attrs={'rows': 2}))
    expected = forms.IntegerField(min_value=1, widget=forms.HiddenInput)

    def __init__(self, case, members, data=None):
        super().__init__(data, initial={'expected': case.revision})
        self.fields['member'].queryset = members
        self.fields['member'].label_from_instance = lambda member: f'{role_work.actor_name(member.user)} · {teams.scope_label(member.role, member.mode)}'
        self.fields['action'].queryset = ActionItem.objects.filter(case=case, staffassignment__isnull=True,
            current__status__in=['open','in_progress','paused']).select_related('current').order_by('-pk')
        self.fields['action'].label_from_instance = lambda item: item.current.description

    def clean(self):
        data = super().clean()
        if not data.get('action') and not (data.get('reference') and data.get('description')):
            raise ValidationError('Choose an existing action or enter the reference and work for a new action.')
        return data


class ReviewForm(forms.Form):
    member = forms.ModelChoiceField(queryset=StaffMembership.objects.none(), label='Reviewer')
    task = forms.ModelChoiceField(queryset=HumanTask.objects.none(), label='Open document decision')
    expected = forms.IntegerField(min_value=1, widget=forms.HiddenInput)

    def __init__(self, case, members, data=None):
        super().__init__(data, initial={'expected': case.revision})
        self.fields['member'].queryset = members
        self.fields['member'].label_from_instance = lambda member: role_work.actor_name(member.user)
        self.fields['task'].queryset = HumanTask.objects.filter(case=case, version__document__case=case,
            version__template__definition__document_type='status_report', kind='document_review', status='open'
        ).exclude(version__audience='group').select_related('version__document').order_by('-pk')
        self.fields['task'].label_from_instance = lambda task: f'{task.version.document.title} · version {task.version.number}'


class TransferForm(forms.Form):
    assignment = forms.ModelChoiceField(queryset=StaffAssignment.objects.none(), label='Action to reassign')
    member = forms.ModelChoiceField(queryset=StaffMembership.objects.none(), label='New assignee')
    reason = forms.CharField(max_length=1000, label='Reason for reassignment')
    expected = forms.IntegerField(min_value=1, widget=forms.HiddenInput)

    def __init__(self, case, members, data=None):
        super().__init__(data, initial={'expected': case.revision})
        self.fields['assignment'].queryset = StaffAssignment.objects.filter(case=case, action__isnull=False,
            action__current__status__in=['open','in_progress','paused']).select_related('action__current').order_by('-pk')
        self.fields['assignment'].label_from_instance = lambda row: row.action.current.description
        self.fields['member'].queryset = members
        self.fields['member'].label_from_instance = lambda member: role_work.actor_name(member.user)


class NativeReviewForm(forms.Form):
    member = forms.ModelChoiceField(queryset=StaffMembership.objects.none(), label='Reviewer')
    target = forms.ModelChoiceField(queryset=None, label='Decision record')
    expected = forms.IntegerField(min_value=1, widget=forms.HiddenInput)

    def __init__(self, case, members, kind, data=None):
        super().__init__(data, initial={'expected':case.revision})
        role = 'finance-lead' if kind == 'schedule' else 'hr'
        self.fields['member'].queryset = members.filter(role=role)
        self.fields['member'].label_from_instance = lambda member: role_work.actor_name(member.user)
        if kind == 'schedule':
            self.fields['target'].queryset = role_native_decisions.schedule_records(case).filter(
                reviews__isnull=True).defer('payload','result','snapshot').order_by('-pk')
            self.fields['target'].label_from_instance = lambda row: f'{row.reference} · version {row.version}'
        else:
            from apps.finance.hrfinance_models import HRReadSnapshot

            self.fields['target'].queryset = role_native_decisions.correction_records(case).defer('payload').order_by('-pk')
            self.fields['target'].label_from_instance = lambda row: f'Correction request {row.pk}'
            self.fields['successor'] = forms.ModelChoiceField(label='Corrected HR export', required=False,
                queryset=HRReadSnapshot.objects.filter(contract__need__case=case,status='accepted').defer('payload').order_by('-pk'))


class FactoryReviewForm(forms.Form):
    member = forms.ModelChoiceField(queryset=StaffMembership.objects.none(),label='Reviewer')
    work = forms.ModelChoiceField(queryset=None,label='Current factory work')
    kind = forms.ChoiceField(label='Decision',choices=role_factory_decisions.LABELS.items())
    target = forms.IntegerField(min_value=1,required=False,label='Exact record number when there is more than one')
    evidence = forms.ModelChoiceField(queryset=None,label='Decision evidence for Planning or closure',required=False)
    expected = forms.IntegerField(min_value=1,widget=forms.HiddenInput)

    def __init__(self, actor, case, members, data=None):
        from apps.core.evidence_access import public_evidence
        from apps.workflows.factory_definitions import DEFINITIONS
        from apps.workflows.factory_views import visible

        super().__init__(data,initial={'expected':case.revision})
        sources,_ = role_factory_decisions.document_handlers()
        work = visible(actor,case_id=case.pk).filter(definition__in={*sources,*role_factory_decisions.LINES.values()})
        work = work.exclude(status__in=['cancelled','verified','followup_needed']).filter(cancel_requested=False)
        self.fields['member'].queryset = members
        self.fields['member'].label_from_instance = lambda item: role_work.actor_name(item.user)
        self.fields['work'].queryset = work.order_by('-updated_at','-pk')
        self.fields['work'].label_from_instance = lambda item: f"{DEFINITIONS[item.definition]['title']} · {item.request.get('reference') or item.pk}"
        self.fields['evidence'].queryset = public_evidence(case.evidence.all()).defer('body').order_by('-pk')


class RevokeForm(forms.Form):
    member = forms.ModelChoiceField(queryset=StaffMembership.objects.none(), label='Role assignment to remove')
    reason = forms.CharField(max_length=1000, label='Reason for removing access')

    def __init__(self, members, data=None):
        super().__init__(data)
        self.fields['member'].queryset = members
        self.fields['member'].label_from_instance = lambda member: role_work.actor_name(member.user)


@login_required
@require_http_methods(['GET','HEAD','POST'])
@never_cache
def manage(request, case_id):
    case = get_object_or_404(visible_cases(request.user), pk=case_id, kind='project')
    cfg = teams.manageable(request.user, case)
    grants = {action for _, action in active_case_grants(request.user, [case.pk])}
    delegate = set(cfg.value['allowed_actions'])
    members = StaffMembership.objects.filter(case=case, active=True, user__is_active=True).select_related('user','team').order_by('user__username')
    data = request.POST if request.method == 'POST' else None
    mode = data.get('operation') if data is not None else None
    forms_by_mode = {'team': TeamForm(data if mode == 'team' else None), 'revoke': RevokeForm(members, data if mode == 'revoke' else None)}
    if {'action.manage','evidence.add'} <= grants and role_work.OWN_ACTIONS <= delegate:
        forms_by_mode.update(action=AssignmentForm(case, members, data if mode == 'action' else None),
                             transfer=TransferForm(case, members, data if mode == 'transfer' else None))
    if 'document.read' in grants and role_work.DOC_ACTIONS <= delegate:
        forms_by_mode['review'] = ReviewForm(case, members, data if mode == 'review' else None)
    if {'finance.read','schedules.read'} <= grants and role_native_decisions.SCHEDULE_ACTIONS <= delegate:
        forms_by_mode['schedule'] = NativeReviewForm(case, members, 'schedule', data if mode == 'schedule' else None)
    if 'hrfinance.read' in grants and role_native_decisions.HR_ACTIONS <= delegate:
        forms_by_mode['hr'] = NativeReviewForm(case, members, 'hr', data if mode == 'hr' else None)
    if 'factory.read' in grants:
        forms_by_mode['factory'] = FactoryReviewForm(request.user,case,members,data if mode=='factory' else None)
    if data is not None and mode not in forms_by_mode:
        raise PermissionDenied('Choose a staff action that your delegation permits.')
    if mode and forms_by_mode[mode].is_valid():
        form = forms_by_mode[mode]
        values = form.cleaned_data
        try:
            if mode == 'team':
                teams.create_team(request.user, case.pk, **values)
            elif mode == 'revoke':
                teams.revoke(request.user, case.pk, values['member'].pk, values['reason'])
            elif mode == 'action':
                member, action = values.pop('member'), values.pop('action')
                role_work.assign_action(request.user, case.pk, member.pk, action_id=action.pk if action else None, **values)
            elif mode == 'review':
                role_work.assign_review(request.user, case.pk, values['member'].pk, values['task'].pk, values['expected'])
            elif mode in ('schedule','hr'):
                successor = values.get('successor')
                role_native_decisions.assign(request.user,case.pk,values['member'].pk,mode,values['target'].pk,
                                             values['expected'],successor.pk if successor else None)
            elif mode=='factory':
                evidence = values['evidence']
                role_factory_decisions.assign(request.user,case.pk,values['member'].pk,values['work'].pk,values['kind'],
                                              values['target'],evidence.pk if evidence else None,values['expected'])
            else:
                role_work.transfer(request.user, case.pk, values['assignment'].pk, values['member'].pk,
                                   values['reason'], values['expected'])
        except (ValidationError, ObjectDoesNotExist, Http404):
            form.add_error(None, 'Could not save this assignment. Check the selected record and reload to review current access.')
        else:
            messages.success(request, 'The workspace role or assignment was updated.')
            return redirect('staff_teams', case_id=case.pk)
    return render(request, 'identity/staff_teams.html', {'case':case, 'scope_forms':forms_by_mode,
        'members':members[:50], 'teams':StaffTeam.objects.filter(case=case).order_by('name','pk')[:50],
        'can_invite':cfg.value.get('staff_lifecycle', {}).get('allow_invite')})

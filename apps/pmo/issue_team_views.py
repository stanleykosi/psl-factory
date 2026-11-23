from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods

from apps.core.services import bump, lock_case
from apps.core.views import accessible_case
from apps.identity.services import require
from apps.policy.issue_team_validators import COMPONENT
from apps.policy.operator_drafts import draft_operator_policy

from . import issue_teams
from .issue_access import state_public
from .issue_models import Issue
from .issue_team_forms import TeamAssignmentForm, TeamRulesForm, TeamResolutionForm, evidence_choices


@login_required
@never_cache
@require_http_methods(['GET', 'HEAD', 'POST'])
def owner(request, case_id, issue_id):
    case = accessible_case(request.user, case_id)
    require(request.user, case, 'issue.read')
    require(request.user, case, 'issue.manage')
    issue = get_object_or_404(Issue.objects.select_related('case', 'current__owner'), case=case, pk=issue_id)
    if not state_public(issue.current):
        raise PermissionDenied('Use the native private source interface for this issue.')
    try:
        _, value = issue_teams.rules(case)
    except (PermissionDenied, ValidationError):
        value = {}
    work = None
    if request.GET.get('work'):
        from apps.workflows import factory, factory_issues
        from apps.workflows.models import FactoryWork
        try:
            work_id = int(request.GET['work'])
            if not 1 <= work_id <= 9223372036854775807:
                raise ValueError
        except ValueError:
            raise Http404('Open a current issue investigation.') from None
        work = get_object_or_404(FactoryWork, case=case, pk=work_id, definition=factory_issues.DEFINITION)
        factory.access(request.user, case, 'factory.manage', factory_issues.DEFINITION)
        if work.request.get('issue_id') != issue.pk:
            raise PermissionDenied('Open the investigation for this issue.')
    form = TeamAssignmentForm(case, issue, issue_teams.latest(issue), value,
                              request.POST if request.method == 'POST' else None, work=work)
    if request.method == 'POST' and form.is_valid():
        data = form.cleaned_data
        try:
            if set(request.POST) - set(form.fields) - {'csrfmiddlewaretoken'}:
                raise ValidationError('Use the displayed owner fields.')
            assignment = issue_teams.assign(request.user, case.pk, issue.pk, data['state'], data['mode'],
                data['team_key'], data['recorder'].pk, data['recorder_role'], int(data['evidence']),
                data['reason'], data['revision'], work_id=data['work'], source_id=data['source'])
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            if assignment.auto_work_id:
                from apps.workflows.factory_issues import sync_owner
                try:
                    sync_owner(assignment.auto_work_id)
                except (PermissionDenied, ValidationError):
                    messages.info(request, 'Ownership is saved. Review current permissions or source evidence before continuing follow-up.')
                messages.success(request, 'Issue ownership recorded. Follow-up uses this reviewed assignment when its current worker is ready.')
                return redirect('factory_detail', work_id=assignment.auto_work_id)
            messages.success(request, 'Issue ownership recorded.')
            return redirect('issues', case_id=case.pk)
    return render(request, 'pmo/issue_team_owner.html', {'case': case, 'issue': issue, 'form': form,
                                                      'rules_available': bool(value)})


@login_required
@never_cache
@require_http_methods(['GET', 'HEAD', 'POST'])
def configuration(request, case_id):
    case = accessible_case(request.user, case_id)
    require(request.user, case, 'policy.read')
    require(request.user, case, 'policy.configure')
    try:
        current, value = issue_teams.rules(case)
    except (PermissionDenied, ValidationError):
        current, value = None, {}
    if current is not None:
        from apps.policy.impact import configuration as readable_configuration
        readable_configuration(request.user, case.pk, current.pk)
    form = TeamRulesForm(request.POST if request.method == 'POST' else None, initial={
        'revision': case.revision, 'recorder_roles': value.get('recorder_roles', []),
        'resolution_recorder_roles':value.get('resolution_recorder_roles', []),
        'acknowledgement_clock':value.get('acknowledgement_clock') or '',
        'channels': value.get('channels', []), 'teams': '\n'.join(team['label'] for team in value.get('teams', []))},
        existing_teams=value.get('teams', []))
    form.fields['evidence'].choices = evidence_choices(case, kind='policy_decision')
    if request.method == 'POST' and form.is_valid():
        data = form.cleaned_data
        try:
            if set(request.POST) - set(form.fields) - {'csrfmiddlewaretoken'}:
                raise ValidationError('Use the displayed rule fields.')
            with transaction.atomic():
                locked = lock_case(request.user, case.pk, 'policy.configure', data['revision'])
                from .issue_access import issue_subject
                issue_subject(locked, int(data['evidence']), 'policy_decision', metadata_only=True)
                draft_operator_policy(request.user, locked.pk, COMPONENT,
                    {'recorder_roles': data['recorder_roles'], 'teams': data['teams'],
                     'channels': data['channels'], 'clock_basis': 'human_attested_source_time',
                     'resolution_recorder_roles':data['resolution_recorder_roles'],
                     'acknowledgement_clock':data['acknowledgement_clock'] or None},
                    int(data['evidence']), timezone.now())
                bump(locked)
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            messages.success(request, 'Team response rules saved as a draft for review and activation.')
            return redirect('issue_team_configuration', case_id=case.pk)
    return render(request, 'pmo/issue_team_configuration.html', {'case': case, 'form': form,
                                                             'current': current})


@login_required
@never_cache
@require_http_methods(['GET', 'HEAD', 'POST'])
def resolution(request, case_id, issue_id):
    case = accessible_case(request.user, case_id)
    require(request.user, case, 'issue.read')
    require(request.user, case, 'issue.work')
    issue = get_object_or_404(Issue.objects.select_related('case', 'current__owner'), case=case, pk=issue_id)
    if not state_public(issue.current):
        raise PermissionDenied('Use the source-authorised private issue interface.')
    team = issue_teams.projection(request.user, issue)
    if team['mode'] != 'team' or not team.get('can_record'):
        raise PermissionDenied('The current follow-up coordinator records the team resolution.')
    value = issue_teams.rules(case)[1]
    form = TeamResolutionForm(case, issue, team['assignment'], value,
                              request.POST if request.method == 'POST' else None)
    if request.method == 'POST' and form.is_valid():
        d = form.cleaned_data
        try:
            if set(request.POST) - set(form.fields) - {'csrfmiddlewaretoken'}:
                raise ValidationError('Use the displayed resolution fields.')
            issue_teams.record_reply(request.user, case.pk, issue.pk, d['state'], d['assignment'],
                d['operation_key'], 'resolve', int(d['evidence']), d['note'], d['next_action'],
                d['party'], d['channel'], d['responded_at'], d['source_ref'], d['revision'],
                fix_id=int(d['fix']), root_cause_id=int(d['root_cause']) if d['root_cause'] else None,
                resolution_role=d['resolution_role'])
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            messages.success(request, 'Team resolution recorded. Quality assurance and the project manager must complete closure.')
            return redirect('issues', case_id=case.pk)
    return render(request, 'pmo/issue_team_resolution.html', {'case':case, 'issue':issue, 'team':team, 'form':form})

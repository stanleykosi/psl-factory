"""Record-access invitations and departures under the current technical delegation."""
from datetime import timedelta
from hashlib import sha256
from uuid import UUID
import secrets

from django.contrib.auth import get_user_model, password_validation
from django.contrib.auth.password_validation import CommonPasswordValidator, MinimumLengthValidator, NumericPasswordValidator
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.validators import validate_email
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone

from apps.core.models import Case
from apps.core.services import bump, event
from apps.documents.contracts import digest
from apps.pmo.meetings import change_action
from apps.pmo.models import ActionItem
from apps.policy.role_assignments import eligibility
from apps.policy.services import active_component, reference_values
from apps.workflows.models import FactoryWork, HumanTask

from . import intake
from .intake_models import TenantAuthority
from .models import Grant
from .services import active_case_grants, require
from .staff_models import StaffAdmission, StaffDeparture, StaffInvitation


MAX_INVITED_WORKSPACES = 50
MAX_COMBINED_INVITATION_ACTIONS = 150


def authority(actor, case, action=None):
    require(actor, case, 'case.read')
    cfg = intake.current(actor, case.tenant, 'manage_access')
    if case.synthetic != (cfg.value['classification']=='synthetic') or case.kind not in cfg.value['kinds']:
        raise PermissionDenied('Exact staff access scope required.')
    settings = cfg.value.get('staff_lifecycle', {})
    if action and not settings.get(action):
        raise PermissionDenied('This staff action needs explicit delegation.')
    return cfg, settings


def _revision(case, expected):
    if case.revision != expected:
        raise ValidationError('The workspace changed. Reload before updating access.')


def invitation_projects(actor, case):
    from .services import visible_cases

    return visible_cases(actor).filter(kind='project', tenant=case.tenant, synthetic=case.synthetic).exclude(pk=case.pk)


def workspace_pin(case, profile):
    return {'case': str(case.pk), 'profile_key': profile['key'], 'profile_label': profile['label'],
            'profile_sha256': digest(profile), 'actions': sorted(profile['actions'])}


def check_extra_project(base, target, cfg, readable_case_ids):
    if (target.pk == base.pk or target.kind != 'project' or target.tenant != base.tenant or
            target.synthetic != base.synthetic or 'project' not in cfg.value['kinds'] or target.pk not in readable_case_ids):
        raise PermissionDenied('Choose a managed project in this workspace group.')


@transaction.atomic
def invite(actor, case_id, username, name, email, actions, expected, preceding=None, *, profile_key='',
           workspace_choices=None, all_current_projects=False, expected_authority=None):
    if workspace_choices is None:
        workspace_choices = {}
    if type(workspace_choices) is not dict or len(workspace_choices) >= MAX_INVITED_WORKSPACES:
        raise ValidationError('Select up to 50 distinct workspaces, including the starting workspace.')
    try:
        base_id = UUID(str(case_id))
        choices = {UUID(str(key)): value for key, value in workspace_choices.items()}
    except (TypeError, ValueError):
        raise ValidationError('Choose exact reviewed workspace identities.') from None
    if base_id in choices or len(choices) != len(workspace_choices):
        raise ValidationError('Select distinct workspaces, including the starting workspace.')
    if type(all_current_projects) is not bool or any(
            not isinstance(choice, (list, tuple)) or len(choice) != 2 or type(choice[0]) is not int or
            choice[0] < 1 or not isinstance(choice[1], str) or not choice[1] or len(choice[1]) > 50
            for choice in choices.values()):
        raise ValidationError('Choose an exact reviewed revision and profile for each included project.')
    selected_ids = {base_id, *choices}
    workspaces = {workspace.pk: workspace for workspace in Case.objects.select_for_update().filter(pk__in=selected_ids).order_by('pk')}
    if set(workspaces) != selected_ids:
        raise ValidationError('Review the current list of workspaces before inviting this person.')
    case = workspaces[base_id]
    intake.lock_users([actor.pk])
    cfg, settings = authority(actor, case, 'allow_invite')
    if (choices or all_current_projects or expected_authority is not None) and expected_authority != cfg.pk:
        raise ValidationError('Invitation authority changed. Reload and review the current profiles.')
    _revision(case, expected)
    username = username.strip().lower()
    user_model = get_user_model()
    user_model._meta.get_field('username').clean(username, None)
    validate_email(email)
    intake.text(name, 150)
    from .actions import ACTIONS
    if ('case.read' not in actions or len(actions) != len(set(actions)) or
            not set(actions) <= set(cfg.value['allowed_actions']) or not profile_key and not set(actions)<=set(ACTIONS)):
        raise PermissionDenied('Select the exact record access you can delegate.')
    profile=None
    if profile_key:
        from .staff_profiles import selected
        profile=selected(cfg,profile_key)
        if set(profile['actions'])!=set(actions):raise ValidationError('Use the exact selected access profile.')
    if choices or all_current_projects:
        if profile is None:
            raise ValidationError('Choose a named access profile for each workspace in a combined invitation.')
        if all_current_projects:
            if set(invitation_projects(actor, case).values_list('pk', flat=True)[:MAX_INVITED_WORKSPACES]) != set(choices):
                raise ValidationError('The managed project list changed. Review it again before inviting anyone.')
            if any(key != profile_key for _, key in choices.values()):
                raise ValidationError('Apply the same named profile to all currently managed projects.')
    extra = []
    readable_case_ids = {pk for pk, _ in active_case_grants(actor, choices, actions=['case.read'])}
    for project_id in sorted(choices):
        project = workspaces[project_id]
        revision, key = choices[project_id]
        _revision(project, revision)
        check_extra_project(case, project, cfg, readable_case_ids)
        extra.append(workspace_pin(project, selected(cfg, key)))
    if extra and len(actions) + sum(len(pin['actions']) for pin in extra) > MAX_COMBINED_INVITATION_ACTIONS:
        raise ValidationError('A combined invitation can include up to 150 workspace access functions. Review a smaller selection.')
    old = StaffInvitation.objects.filter(case=case, username=username).order_by('-number').first()
    if preceding != (old.pk if old else None) or user_model.objects.filter(username__iexact=username).exists():
        raise ValidationError('Use the current pending invitation or choose a new account name.')
    token = secrets.token_urlsafe(32)
    expires = min(timezone.now()+timedelta(minutes=settings['invite_minutes']), cfg.expires_at)
    row = StaffInvitation.objects.create(case=case, username=username, name=name, email=email, actions=sorted(actions),
                                         number=old.number+1 if old else 1, token_hash=sha256(token.encode()).hexdigest(),
                                         expires_at=expires, authority=cfg, actor=actor,
                                         profile_key=profile['key'] if profile else '',
                                         profile_label=profile['label'] if profile else '',
                                         profile_sha256=digest(profile) if profile else '', workspace_profiles=extra)
    event(actor, case, 'staff.invitation_created', invitation=row.pk)
    bump(case)
    return row, token


def additional_access(invitation, cfg, cases=None):
    from .staff_profiles import selected

    pins = invitation.workspace_profiles
    if not pins:
        return []
    if cases is None:
        cases = {str(case.pk): case for case in Case.objects.filter(pk__in=[pin['case'] for pin in pins])}
    readable_case_ids = {pk for pk, _ in active_case_grants(invitation.actor,
        [case.pk for case in cases.values()], actions=['case.read'])}
    verified = []
    for pin in pins:
        case = cases.get(pin['case'])
        if case is None:
            raise ValidationError('An invited workspace is unavailable. Ask for an updated invitation.')
        check_extra_project(invitation.case, case, cfg, readable_case_ids)
        profile = selected(cfg, pin['profile_key'])
        if pin != workspace_pin(case, profile):
            raise ValidationError('An invited workspace changed. Ask for an updated invitation.')
        verified.append((case, profile))
    return verified


def pending(token):
    if len(token) != 43:
        raise ValidationError('This invitation is unavailable.')
    row = StaffInvitation.objects.select_related('case', 'actor').filter(token_hash=sha256(token.encode()).hexdigest()).first()
    if (row is None or timezone.now() >= row.expires_at or hasattr(row, 'admission') or
            StaffInvitation.objects.filter(case=row.case, username=row.username, number__gt=row.number).exists()):
        raise ValidationError('This invitation is unavailable.')
    cfg, _ = authority(row.actor, row.case, 'allow_invite')
    if cfg.pk != row.authority_id:
        raise ValidationError('This invitation needs to be renewed under current access rules.')
    if row.profile_key:
        from .staff_profiles import selected
        profile=selected(cfg,row.profile_key)
        if (row.profile_sha256!=digest(profile) or row.profile_label!=profile['label'] or
                set(row.actions)!=set(profile['actions'])):
            raise ValidationError('This invitation and its reviewed access profile differ.')
    additional_access(row, cfg)
    return row


@transaction.atomic
def accept(token, password):
    row = pending(token)
    case_ids = [str(row.case_id), *(pin['case'] for pin in row.workspace_profiles)]
    cases = {str(case.pk): case for case in Case.objects.select_for_update().filter(pk__in=case_ids).order_by('pk')}
    case = cases[str(row.case_id)]
    intake.lock_users([row.actor_id])
    row = pending(token)
    others = additional_access(row, row.authority, cases)
    user_model = get_user_model()
    if user_model.objects.filter(username__iexact=row.username).exists():
        raise ValidationError('This invitation is unavailable.')
    user = user_model(username=row.username, email=row.email, first_name=row.name)
    password_validation.validate_password(password, user, password_validators=[
        MinimumLengthValidator(min_length=12), CommonPasswordValidator(), NumericPasswordValidator(),
    ])
    user.set_password(password)
    try:
        with transaction.atomic():
            user.save(force_insert=True)
    except IntegrityError:
        raise ValidationError('This invitation is unavailable.') from None
    StaffAdmission.objects.create(invitation=row, user=user)
    for action in row.actions:
        intake.change_access(row.actor,case.pk,user.pk,action,True,'Accepted exact staff invitation')
    from .staff_profiles import record_invitation
    record_invitation(row,user)
    event(user, case, 'staff.invitation_accepted', invitation=row.pk)
    bump(case)
    for project, profile in others:
        for action in sorted(profile['actions']):
            intake.change_access(row.actor, project.pk, user.pk, action, True, 'Accepted exact staff invitation')
        record_invitation(row, user, case=project, profile=profile)
        event(user, project, 'staff.invitation_accepted', invitation=row.pk)
        bump(project)
    return user


def open_actions(case, person):
    return ActionItem.objects.filter(case=case, current__owner_id=person).exclude(
        current__status__in=['completed','cancelled']).select_related('current').order_by('pk')


def role_context(actor,case):
    # Account administration cannot bypass a role policy's current source boundary.
    from apps.policy.role_assignments import report
    from apps.policy.impact import configuration
    report_value=report(actor,case.pk)
    if report_value['status']!='ACTIVE':raise ValidationError('Current project role assignments are required.')
    config=configuration(actor,case.pk,report_value['configuration'])
    return config,reference_values(config)


def started_work_for_handover(case, user):
    from apps.workflows.factory_execution import available_actor

    related=Q(execution_binding__principal=user)|Q(actor=user)
    work = list(FactoryWork.objects.filter(related, case=case).exclude(status__in=['verified', 'cancelled', 'followup_needed'])
                .select_related('case', 'actor', 'execution_binding').defer('request', 'finding', 'actor__password').order_by('pk')[:101])
    if len(work) > 100:
        return [], True
    return [row.pk for row in work if available_actor(row) in (None, user)], False


def work_handover_findings(case,user):
    work, truncated = started_work_for_handover(case, user)
    findings=[]
    if work or truncated:
        findings.append('Complete the native handoff of this person’s open factory work first.')
    if HumanTask.objects.filter(case=case,claimed_by=user,status='open').exists():
        findings.append('Release this person’s open decision claims first.')
    return findings


def handover_links(actor, case, user):
    """Show permitted links and a generic handover hold for protected work."""
    from apps.finance.fixed_charge import preparation_access
    from apps.workflows import factory

    replacements, truncated = started_work_for_handover(case, user)
    keys = list(HumanTask.objects.filter(case=case, claimed_by=user, status='open').order_by('pk')
                .values_list('factory_key', 'kind', 'context__purpose')[:101])
    claims = set()
    releasable = set()
    other_work = truncated or len(keys) > 100
    for key, kind, purpose in keys[:100]:
        parts = (key or '').split(':', 2)
        if len(parts) == 3 and parts[0] == 'factory' and parts[1].isascii() and parts[1].isdigit() and len(parts[1]) < 19:
            work_id = int(parts[1])
            claims.add(work_id)
            if purpose != 'hr_scope_clarification_v1' and kind in {'factory_information', 'factory_review', 'factory_governance'}:
                releasable.add(work_id)
        else:
            other_work = True
    ids = set(replacements) | claims
    if not ids:
        return {'rows': [], 'other_work': other_work}
    # Private Finance and leadership work needs its own domain reader, not a staff projection.
    candidates = FactoryWork.objects.filter(case=case, pk__in=ids).exclude(
        Q(definition__startswith='finance-') | Q(definition='pmo-leadership-report/v1'))
    access = {}
    visible_work = {}
    for work in candidates.only('pk', 'definition', 'preparation_id').order_by('pk'):
        if work.definition not in access:
            can_read = can_manage = False
            try:
                factory.access(actor, case, 'factory.read', work.definition)
                can_read = True
                factory.access(actor, case, 'factory.manage', work.definition)
                can_manage = True
            except (PermissionDenied, ValidationError):
                pass
            access[work.definition] = can_read, can_manage
        can_read, can_manage = access[work.definition]
        if not can_read:
            continue
        if work.preparation_id and work.preparation.kind == 'fixed_contract':
            try:
                preparation_access(actor, work.preparation)
            except (PermissionDenied, ValidationError):
                continue
        visible_work[work.pk] = (work.definition, can_manage)
    rows = []
    for pk, request in candidates.filter(pk__in=visible_work).order_by('pk').values_list('pk', 'request'):
        definition, can_manage = visible_work[pk]
        rows.append({'pk': pk, 'name': request.get('reference') or 'Open work',
                     'replacement': pk in replacements, 'claim': pk in claims, 'can_review': can_manage,
                     'can_release_claim': pk in releasable and definition == 'pmo-finance/v1' and can_manage})
    return {'rows': rows, 'other_work': other_work or len(visible_work) < len(ids)}


def require_work_handover(case,user):
    findings=work_handover_findings(case,user)
    if findings:raise ValidationError(findings)


@transaction.atomic
def deactivate(actor, case_id, person_id, replacements, evidence_id, reason, expected):
    case = Case.objects.select_for_update().get(pk=case_id)
    intake.lock_users({actor.pk, person_id, *(pk for pk in replacements.values() if pk is not None)})
    cfg, settings = authority(actor, case, 'allow_deactivation')
    _revision(case, expected)
    intake.text(reason, 1000)
    user = get_user_model().objects.filter(pk=person_id).first()
    if not user or user.pk == actor.pk or user.is_superuser or user.is_staff:
        raise PermissionDenied('Select an account you are delegated to manage.')
    grants = list(Grant.objects.select_for_update().filter(case=case, user=user, active=True).order_by('pk'))
    if not grants or any(row.action not in cfg.value['allowed_actions'] for row in grants):
        raise PermissionDenied('Current access exceeds this administrator’s delegation.')
    require_work_handover(case,user)
    items = list(open_actions(case, user.pk)[:101])
    if len(items) > 100 or {item.pk for item in items} != set(replacements):
        raise ValidationError('Select a successor for every open project action.')
    if items:
        if any(pk is None for pk in replacements.values()) and not (
                cfg.value['format']=='psl.tenant-access/v3' and settings.get('allow_unassigned_departure') is True):
            raise ValidationError('An unassigned handover needs explicit current account controls.')
    if any(pk is not None for pk in replacements.values()):
        _,values = role_context(actor,case)
        original = eligibility(case, values, user.pk)
    for item in items:
        next_id = replacements[item.pk]
        if next_id is not None:
            proposed = eligibility(case, values, next_id)
            if (next_id == user.pk or not proposed['eligible_role_bundle'] or
                    not set(original['roles']).intersection(proposed['roles'])):
                raise ValidationError('Each successor needs a current shared role on this workspace.')
        change_action(actor,case.pk,item.pk,'reassign',evidence_id,reason,None,item.current.number,owner_id=next_id)
    for grant in grants:
        grant.active = False
        grant.save(update_fields=['active'])
        intake.AccessChange.objects.create(subject=user, case=case, action=grant.action, enabled=False, authority=cfg,
                                           actor=actor, reason=reason)
    admitted = StaffAdmission.objects.filter(user=user).filter(Q(invitation__case=case) |
        Q(invitation__workspace_profiles__contains=[{'case': str(case.pk)}])).exists()
    disabled = (admitted and
                not Grant.objects.filter(user=user, active=True).exists() and
                not TenantAuthority.objects.filter(user=user, expires_at__gt=timezone.now()).exists())
    if disabled:
        user.is_active = False
        user.save(update_fields=['is_active'])
    row = StaffDeparture.objects.create(case=case,user=user,actor=actor,authority=cfg,reason=reason,
                                        actions=sorted(g.action for g in grants),account_disabled=disabled)
    event(actor,case,'staff.access_removed',departure=row.pk,account_disabled=disabled,reassigned=sorted(replacements))
    case.refresh_from_db()
    bump(case)
    return row

"""Record-access invitations and departures under the current technical delegation."""
from datetime import timedelta
from hashlib import sha256
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
from .services import require
from .staff_models import StaffAdmission, StaffDeparture, StaffInvitation


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


@transaction.atomic
def invite(actor, case_id, username, name, email, actions, expected, preceding=None, *, profile_key=''):
    case = Case.objects.select_for_update().get(pk=case_id)
    intake.lock_users([actor.pk])
    cfg, settings = authority(actor, case, 'allow_invite')
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
                                         profile_sha256=digest(profile) if profile else '')
    event(actor, case, 'staff.invitation_created', invitation=row.pk)
    bump(case)
    return row, token


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
    return row


@transaction.atomic
def accept(token, password):
    row = pending(token)
    case = Case.objects.select_for_update().get(pk=row.case_id)
    intake.lock_users([row.actor_id])
    row = pending(token)
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


def work_handover_findings(case,user):
    from apps.workflows.factory_execution import available_actor
    related=Q(execution_binding__principal=user)|Q(actor=user)
    work=list(FactoryWork.objects.filter(related,case=case).exclude(status__in=['verified','cancelled','followup_needed']).select_related(
        'case','actor','execution_binding')[:101])
    findings=[]
    if len(work)>100 or any(available_actor(row) in (None,user) for row in work):
        findings.append('Complete the native handoff of this person’s open factory work first.')
    if HumanTask.objects.filter(case=case,claimed_by=user,status='open').exists():
        findings.append('Release this person’s open decision claims first.')
    return findings


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
    disabled = (StaffAdmission.objects.filter(user=user, invitation__case=case).exists() and
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

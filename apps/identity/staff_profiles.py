"""Named technical access bundles; never appoints a business decision maker."""
from uuid import UUID,uuid5,NAMESPACE_URL

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied,ValidationError
from django.db import transaction
from django.db.models import Max,Q

from apps.core.models import Case
from apps.core.services import bump,event
from apps.documents.contracts import digest
from . import intake,staff,staff_accounts
from .intake_models import AccessChange
from .models import Grant
from .staff_models import StaffProfileChange


@transaction.atomic
def configure(actor,authority_id,profiles,reason):
    from apps.core.read_observation import assert_command_allowed
    from .intake_models import TenantAuthority
    assert_command_allowed()
    original=TenantAuthority.objects.select_related('user').get(pk=authority_id)
    intake.lock_users({actor.pk,original.user_id})
    fresh=get_user_model().objects.get(pk=actor.pk)
    if not fresh.is_active or not fresh.is_superuser:raise PermissionDenied('Current technical bootstrap administrator required.')
    latest=TenantAuthority.objects.filter(user_id=original.user_id,tenant=original.tenant).latest('version')
    if latest.pk!=original.pk:raise ValidationError('Delegation changed. Review its current version before saving.')
    if not original.value.get('staff_lifecycle'):raise ValidationError('Delegate workspace staff access before configuring profiles.')
    value={**original.value,'format':'psl.tenant-access/v3',
           'staff_lifecycle':{**original.value['staff_lifecycle'],'profiles':profiles}}
    return intake.provision(actor,original.user,original.tenant,value,original.expires_at,original.enabled,reason)


def labels(case_ids,person_id):
    """Metadata only, for an already authorised, bounded page of workspaces."""
    return {case_id:label for (case_id,_),label in binding_labels([(pk,person_id) for pk in case_ids]).items()}


def binding_labels(bindings):
    """Exactly these previously authorised bindings; no row payload/history scan."""
    bindings=set(bindings)
    if len(bindings)>25:raise ValueError('Use a bounded access page.')
    if not bindings:return {}
    scope=Q(pk__in=[]);audit_scope=Q(pk__in=[])
    for case_id,user_id in bindings:
        scope|=Q(case_id=case_id,user_id=user_id)
        audit_scope|=Q(case_id=case_id,subject_id=user_id)
    rows=StaffProfileChange.objects.filter(scope).order_by('case_id','user_id','-pk').distinct('case_id','user_id').only(
        'id','case_id','user_id','profile_label','grant_sha256','grant_audit_head')
    current={(r.case_id,r.user_id):r for r in rows};grants={key:[] for key in bindings}
    for case_id,user_id,action in Grant.objects.filter(scope,active=True).values_list('case_id','user_id','action'):
        grants[(case_id,user_id)].append(action)
    heads={(r['case_id'],r['subject_id']):r['head'] for r in AccessChange.objects.filter(audit_scope).values(
        'case_id','subject_id').annotate(head=Max('pk'))}
    return {key:(current[key].profile_label if key in current and current[key].grant_sha256==digest(sorted(grants[key]))
                and current[key].grant_audit_head==heads.get(key,0) else
                'Access changed — review needed' if key in current else 'Individual workspace access' if grants[key] else 'No current access')
            for key in bindings}


def choices(configuration):
    intake.checked(configuration.value)
    return configuration.value.get('staff_lifecycle',{}).get('profiles') or []


def selected(configuration,key):
    matches=[p for p in choices(configuration) if p['key']==key]
    if len(matches)!=1:raise ValidationError('Choose a current configured account access profile.')
    return matches[0]


def audit_head(case,user):
    return AccessChange.objects.filter(case=case,subject=user).aggregate(head=Max('pk'))['head'] or 0


def review(actor,case,person_id):
    cfg,_=staff.authority(actor,case,'allow_profile_edit')
    person=staff_accounts.account(actor,person_id)
    if (not person.is_active or person.pk==actor.pk or person.is_staff or person.is_superuser or
            staff_accounts._technical_authority(person)):
        raise PermissionDenied('This account needs its technical administrator or a separate lifecycle review.')
    grants=list(Grant.objects.filter(case=case,user=person,active=True).order_by('pk').values('id','action'))
    if any(g['action'] not in cfg.value['allowed_actions'] for g in grants):
        raise PermissionDenied('Current workspace access exceeds this administrator’s delegation.')
    manifest={'format':'psl.staff-profile-review/v1','case':str(case.pk),'revision':case.revision,
              'person':person.pk,'authority':cfg.pk,'active':True,'grants':grants,
              'audit_head':audit_head(case,person)}
    return {'person':person,'configuration':cfg,'profiles':choices(cfg),'manifest':manifest,
            'fingerprint':digest(manifest)}


def record(actor,case,user,configuration,profile,before,after,operation,intent,reason,invitation=None):
    return StaffProfileChange.objects.create(case=case,user=user,actor=actor,authority=configuration,
        invitation=invitation,operation=operation,profile_key=profile['key'],profile_label=profile['label'],
        profile_sha256=digest(profile),before_actions=sorted(before),after_actions=sorted(after),
        grant_sha256=digest(sorted(after)),grant_audit_head=audit_head(case,user),intent_sha256=intent,reason=reason)


@transaction.atomic
def apply(actor,case_id,person_id,key,fingerprint,reason,operation):
    from apps.core.read_observation import assert_command_allowed
    assert_command_allowed();intake.text(reason,1000)
    try:operation=UUID(str(operation))
    except (TypeError,ValueError,AttributeError):raise ValidationError('Use the displayed access review.') from None
    case=Case.objects.select_for_update().get(pk=case_id)
    intake.lock_users({actor.pk,person_id})
    current=review(actor,case,person_id)
    intent=digest({'review':fingerprint,'profile':key,'reason':reason})
    old=StaffProfileChange.objects.filter(operation=operation).first()
    if old:
        if (old.actor_id,old.user_id,old.case_id,old.authority_id,old.intent_sha256)!=(
                actor.pk,person_id,case.pk,current['configuration'].pk,intent):
            raise ValidationError('This access action already records another reviewed request.')
        return old
    if fingerprint!=current['fingerprint']:raise ValidationError('Workspace access changed. Review it again before saving.')
    profile=selected(current['configuration'],key)
    before={g['action'] for g in current['manifest']['grants']};after=set(profile['actions'])
    if before-after:
        staff.require_work_handover(case,current['person'])
        if 'action.own' in before-after and staff.open_actions(case,person_id).exists():
            raise ValidationError('Hand over current project actions before removing their ownership access.')
    for action in sorted(before-after):intake.change_access(actor,case.pk,person_id,action,False,reason)
    for action in sorted(after-before):intake.change_access(actor,case.pk,person_id,action,True,reason)
    row=record(actor,case,current['person'],current['configuration'],profile,before,after,operation,intent,reason)
    event(actor,case,'staff.profile_changed',profile_change=row.pk,person=person_id)
    case.refresh_from_db();bump(case)
    return row


def record_invitation(invitation,user,*,case=None,profile=None):
    if case is None:
        if not invitation.profile_key:return None
        case = invitation.case
        profile = selected(invitation.authority, invitation.profile_key)
        saved = {'case': str(case.pk), 'profile_key': invitation.profile_key, 'profile_label': invitation.profile_label,
                 'profile_sha256': invitation.profile_sha256, 'actions': invitation.actions}
    else:
        saved = next((pin for pin in invitation.workspace_profiles if pin['case'] == str(case.pk)), None)
    if saved != staff.workspace_pin(case, profile):
        raise ValidationError('The invitation and its exact profile source differ.')
    suffix = '' if case.pk == invitation.case_id else f':{case.pk}'
    return record(invitation.actor,case,user,invitation.authority,profile,[],saved['actions'],
        uuid5(NAMESPACE_URL,f'psl.staff-invitation:{invitation.pk}{suffix}'),digest({'invitation':invitation.pk}),
        'Accepted exact named access invitation',invitation)

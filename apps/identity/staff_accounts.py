"""Whole-account departures require current delegation for every affected record."""
from uuid import UUID

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Exists, OuterRef, Q
from django.utils import timezone

from apps.core.models import Case
from apps.core.services import event
from apps.documents.contracts import digest
from apps.identity.services import require, visible_cases
from apps.workflows.models import FactoryWork, HumanTask

from . import intake, staff
from .intake_models import TenantAuthority
from .models import Grant
from .staff_models import StaffAccountChange

MAX_CASES = 100
CONTROL_KEYS = ('allow_roster','allow_account_deactivation','allow_unassigned_departure','allow_profile_edit','allow_reactivation')


@transaction.atomic
def configure_controls(actor,authority_id,values,reason):
    from apps.core.read_observation import assert_command_allowed
    assert_command_allowed()
    fresh=get_user_model().objects.get(pk=actor.pk)
    if not fresh.is_active or not fresh.is_superuser:raise PermissionDenied('Current technical bootstrap administrator required.')
    if type(values) is not dict or set(values)!=set(CONTROL_KEYS):raise ValidationError('Use the displayed account controls.')
    original=TenantAuthority.objects.get(pk=authority_id)
    intake.lock_users({actor.pk,original.user_id})
    latest=TenantAuthority.objects.filter(user_id=original.user_id,tenant=original.tenant).order_by('-version').first()
    if latest.pk!=original.pk:raise ValidationError('Delegation changed. Review its current version before saving.')
    if not original.value.get('staff_lifecycle'):raise ValidationError('Delegate workspace staff access before setting account controls.')
    value={**original.value,'format':'psl.tenant-access/v3',
           'staff_lifecycle':{**original.value['staff_lifecycle'],**values}}
    return intake.provision(actor,original.user,original.tenant,value,original.expires_at,original.enabled,reason)


def manageable_cases(actor):
    scope=Q(pk__in=[])
    for cfg in intake.options(actor,'manage_access'):
        if cfg.value.get('staff_lifecycle',{}).get('allow_roster') is True:
            scope |= Q(tenant=cfg.tenant,synthetic=cfg.value['classification']=='synthetic',kind__in=cfg.value['kinds'])
    return visible_cases(actor).filter(scope)


def account(actor,person_id):
    admitted=Grant.objects.filter(case__in=manageable_cases(actor),user_id=person_id)
    if not admitted.exists():raise PermissionDenied('This staff account is unavailable in your managed workspaces.')
    return get_user_model().objects.get(pk=person_id)


def _technical_authority(person):
    later=TenantAuthority.objects.filter(user_id=OuterRef('user_id'),tenant=OuterRef('tenant'),version__gt=OuterRef('version'))
    return TenantAuthority.objects.filter(user=person,enabled=True,expires_at__gt=timezone.now()).annotate(
        replaced=Exists(later)).filter(replaced=False).exists()


def prepare(actor,person_id):
    person=account(actor,person_id)
    if person.pk==actor.pk or person.is_staff or person.is_superuser or _technical_authority(person):
        raise PermissionDenied('This account needs its technical administrator; it cannot be disabled here.')
    if not person.is_active:raise ValidationError('This account is already inactive.')
    ids=list(Grant.objects.filter(user=person,active=True).order_by('case_id').values_list('case_id',flat=True).distinct()[:MAX_CASES+1])
    if not ids or len(ids)>MAX_CASES:raise ValidationError('The complete account scope needs administrator review.')
    cases=list(Case.objects.filter(pk__in=ids).order_by('pk'))
    scopes=[]
    # Check all scope authority before returning any other workspace information.
    for case in cases:
        cfg,_=staff.authority(actor,case,'allow_account_deactivation')
        grants=list(Grant.objects.filter(case=case,user=person,active=True).order_by('pk').values('id','action'))
        if any(g['action'] not in cfg.value['allowed_actions'] for g in grants):
            raise PermissionDenied('The complete account scope needs its authorised administrators.')
        scopes.append({'case':case,'authority':cfg,'grants':grants})
    blocked=[]
    for scope in scopes:
        case=scope['case']
        handover_findings = staff.work_handover_findings(case,person)
        blocked.extend(handover_findings)
        scope['handover_pending'] = bool(handover_findings)
        items=list(staff.open_actions(case,person.pk)[:101])
        if len(items)>100:raise ValidationError('The complete action inventory needs administrator review.')
        if items:require(actor,case,'action.manage')
        scope['items']=items
        scope['role_policy']=None
        if items:
            try:scope['role_policy']=staff.role_context(actor,case)[0].pk
            except (PermissionDenied,ValidationError):pass
    manifest={'format':'psl.staff-account-departure/v1','person':person.pk,'active':True,
              'scopes':[{'case':str(s['case'].pk),'revision':s['case'].revision,'authority':s['authority'].pk,
                         'grants':s['grants'],'role_policy':s['role_policy'],
                         'handover_pending':s['handover_pending'],
                         'actions':{str(i.pk):i.current_id for i in s['items']}} for s in scopes]}
    return {'actor':actor,'person':person,'scopes':scopes,'manifest':manifest,'fingerprint':digest(manifest),
            'blocked':sorted(set(blocked))}


@transaction.atomic
def deactivate(actor,person_id,fingerprint,replacements,evidence,reason,operation):
    from apps.core.read_observation import assert_command_allowed
    assert_command_allowed()
    from adapters.staff_accounts import checked
    checked(person_id,fingerprint,replacements,evidence)
    intake.text(reason,1000)
    try:operation=UUID(str(operation))
    except (TypeError,ValueError,AttributeError):raise ValidationError('Use the displayed account action.') from None
    before=prepare(actor,person_id)
    cases=before['scopes']
    list(Case.objects.select_for_update().filter(pk__in=[s['case'].pk for s in cases]).order_by('pk'))
    intake.lock_users({actor.pk,person_id,*(pk for pk in replacements.values() if pk is not None)})
    current=prepare(actor,person_id)
    if fingerprint!=current['fingerprint']:raise ValidationError('Staff access or open work changed. Review the complete account again.')
    if current['blocked']:raise ValidationError(current['blocked'])
    if StaffAccountChange.objects.filter(operation=operation).exists():raise ValidationError('This account action was already recorded. Refresh the staff list.')
    all_items={i.pk for s in current['scopes'] for i in s['items']}
    if set(replacements)!=all_items:raise ValidationError('Review every open action before disabling the account.')
    required_proofs={str(s['case'].pk) for s in current['scopes'] if s['items']}
    if set(evidence)!=required_proofs:raise ValidationError('Select each workspace’s own handover evidence.')
    departures=[]
    for scope in current['scopes']:
        case=scope['case']
        choices={i.pk:replacements[i.pk] for i in scope['items']}
        row=staff.deactivate(actor,case.pk,person_id,choices,evidence.get(str(case.pk)),reason,case.revision)
        departures.append(row.pk)
    person=get_user_model().objects.get(pk=person_id)
    # This explicit all-scope operation also covers pre-existing ordinary accounts.
    # Delegation-bearing and privileged accounts were rejected before mutation.
    if Grant.objects.filter(user=person,active=True).exists():
        raise ValidationError('Account scope changed; no departure was committed.')
    person.is_active=False
    person.save(update_fields=['is_active'])
    change=StaffAccountChange.objects.create(user=person,actor=actor,kind='deactivated',operation=operation,
        reason=reason,manifest={'reviewed':current['manifest'],'departures':departures,
                                'successors':{str(k):v for k,v in replacements.items()}})
    # Each record has its own audit; no private cross-workspace roster is exported.
    for scope in current['scopes']:
        event(actor,scope['case'],'staff.account_deactivated',account_change=change.pk,person=person.pk)
    return change

"""Restore sign-in after a fresh all-scope review; never restore old grants."""
from uuid import UUID

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied,ValidationError
from django.db import transaction

from apps.core.models import Case
from apps.core.services import bump,event
from apps.documents.contracts import digest
from apps.policy.role_assignments import COMPONENT,authorize_header,report
from . import intake,staff,staff_accounts
from .intake_models import AccessChange
from .models import Grant
from .staff_models import StaffAccountChange,StaffAdmission,StaffDeparture


def prepare(actor,person_id):
    person=staff_accounts.account(actor,person_id)
    if person.pk==actor.pk or person.is_staff or person.is_superuser or staff_accounts._technical_authority(person):
        raise PermissionDenied('This account needs its technical administrator.')
    if person.is_active:raise ValidationError('This account is already active. Review its current access instead.')
    historical=Grant.objects.filter(user=person).order_by().values_list('case_id',flat=True).union(
        AccessChange.objects.filter(subject=person).order_by().values_list('case_id',flat=True),
        StaffDeparture.objects.filter(user=person).order_by().values_list('case_id',flat=True),
        StaffAdmission.objects.filter(user=person).order_by().values_list('invitation__case_id',flat=True))
    ids=list(historical.order_by('case_id')[:101])
    if not ids or len(ids)>100:raise ValidationError('The complete previous account scope needs administrator review.')
    scopes=[]
    for case in Case.objects.filter(pk__in=ids).order_by('pk'):
        cfg,_=staff.authority(actor,case,'allow_reactivation')
        scopes.append({'case':case,'authority':cfg})
    # Do not disclose another workspace, role source or departure before every
    # affected workspace's current technical delegation has passed.
    latest=StaffAccountChange.objects.filter(user=person).only('id','kind').order_by('-pk').first()
    legacy=StaffDeparture.objects.filter(user=person,account_disabled=True).only('id').order_by('-pk').first() if not latest else None
    if latest and latest.kind!='deactivated' or not latest and legacy is None:
        raise ValidationError('A recorded account departure is needed before restoring sign-in.')
    if Grant.objects.filter(user=person,active=True).exists():
        raise ValidationError('Review remaining active access before restoring sign-in; old access cannot be carried forward.')
    blocked=[]
    for scope in scopes:
        case=scope['case']
        header=authorize_header(actor,case,COMPONENT)
        scope['role_source']=header.pk if header else None
        source=report(actor,case.pk)
        state_row=header.states.order_by('-pk').first() if header else None
        state=state_row.state if state_row else None
        scope['role_state']=state_row.pk if state_row else None
        scope['role_status']=source['status']
        if header and state!='revoked' and source['status']!='ACTIVE':
            blocked.append('Review the latest project role source before restoring sign-in.')
        if any(row['user_id']==person_id for row in source['assignments']):
            blocked.append('Remove this person’s previous project roles through a reviewed role change first.')
    manifest={'format':'psl.staff-reactivation/v1','person':person.pk,'active':False,
        'departure':latest.pk if latest else None,'legacy_departure':legacy.pk if legacy else None,
        'person_identity':digest({'username':person.username,'email':person.email,'first_name':person.first_name,
                                  'last_name':person.last_name,'credential_fingerprint':digest(person.password)}),
        'scopes':[{'case':str(s['case'].pk),'revision':s['case'].revision,'authority':s['authority'].pk,
                   'role_source':s['role_source'],'role_state':s['role_state'],'role_status':s['role_status']} for s in scopes]}
    return {'person':person,'scopes':scopes,'manifest':manifest,'fingerprint':digest(manifest),'blocked':sorted(set(blocked))}


@transaction.atomic
def restore(actor,person_id,fingerprint,reason,operation):
    from apps.core.read_observation import assert_command_allowed
    from adapters.staff_accounts import checked_review
    assert_command_allowed();checked_review(person_id,fingerprint);intake.text(reason,1000)
    try:operation=UUID(str(operation))
    except (ValueError,TypeError,AttributeError):raise ValidationError('Use the displayed restoration review.') from None
    before=prepare(actor,person_id)
    list(Case.objects.select_for_update().filter(pk__in=[s['case'].pk for s in before['scopes']]).order_by('pk'))
    intake.lock_users({actor.pk,person_id})
    current=prepare(actor,person_id)
    if current['fingerprint']!=fingerprint:raise ValidationError('Account, role source or delegation changed. Review it again.')
    if current['blocked']:raise ValidationError(current['blocked'])
    if StaffAccountChange.objects.filter(operation=operation).exists():raise ValidationError('This restoration action is already recorded.')
    person=get_user_model().objects.get(pk=person_id)
    person.is_active=True;person.save(update_fields=['is_active'])
    change=StaffAccountChange.objects.create(user=person,actor=actor,kind='reactivated',operation=operation,reason=reason,
        manifest={'reviewed':current['manifest'],'access_restored':False,'fresh_access_review_required':True})
    for scope in current['scopes']:
        event(actor,scope['case'],'staff.account_reactivated',account_change=change.pk,person=person_id,access_restored=False)
        bump(scope['case'])
    return change

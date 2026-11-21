"""Reviewed conversion of existing workspace access to exact team assignments."""
from uuid import UUID

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from apps.core.models import Case
from apps.core.services import bump, event
from apps.documents.contracts import digest

from . import intake, primary_roles, role_work, staff, teams
from .models import Grant
from .services import require
from .team_models import StaffAssignment, StaffMembership, StaffScopeMove


def prepare(actor, case, person_id, role, mode, team_id):
    source = primary_roles.review(actor, case, person_id)
    person, cfg = source['person'], source['authority']
    pin = teams.scope_pin(case, role, mode, team_id)
    grants = list(Grant.objects.filter(case=case, user=person, active=True).order_by('action').values('id', 'action'))
    if {row['action'] for row in grants} - set(cfg.value['allowed_actions']):
        raise PermissionDenied('The complete workspace access needs its authorised administrator.')
    items = list(staff.open_actions(case, person.pk).order_by('pk')[:101])
    findings = staff.work_handover_findings(case, person)
    if len(items) > 100:
        findings.append('Review the complete action inventory before moving this account.')
    if items:
        require(actor, case, 'action.manage')
        if role_work.OWN_ACTIONS - set(cfg.value['allowed_actions']):
            raise PermissionDenied('Your delegation does not cover the existing action assignments.')
        if {'action.own', 'action.work'} - source['active']:
            findings.append('Hand over actions that this person cannot currently update before moving them.')
        if StaffAssignment.objects.filter(action_id__in=[item.pk for item in items]).exists():
            findings.append('Review the existing scoped action assignments before this move.')
    manifest = {'format':'psl.staff-scope-move/v1', 'case':str(case.pk), 'revision':case.revision, 'person':person.pk,
                'authority':cfg.pk, 'scope':pin, 'grants':grants, 'access_heads':source['heads'],
                'previous_role':source['previous'].pk if source['previous'] else None,
                'actions':{str(item.pk):item.current_id for item in items}, 'holds':sorted(set(findings))}
    return {'person':person, 'scope':pin, 'grants':grants, 'items':items, 'holds':manifest['holds'],
            'manifest':manifest, 'fingerprint':digest(manifest)}


@transaction.atomic
def apply(actor, case_id, person_id, role, mode, team_id, fingerprint, operation, reason):
    from apps.core.read_observation import assert_command_allowed

    assert_command_allowed()
    intake.text(reason, 1000)
    try:
        key = UUID(str(operation))
    except (TypeError, ValueError):
        raise ValidationError('Use the displayed move request.') from None
    case = Case.objects.select_for_update().get(pk=case_id)
    intake.lock_users([actor.pk,person_id])
    cfg = teams.manageable(actor, case)
    intent = digest({'scope':[role,mode,team_id], 'preview':fingerprint, 'reason':reason})
    recorded = StaffScopeMove.objects.filter(operation=key).first()
    if recorded:
        if (recorded.case_id,recorded.actor_id,recorded.user_id,recorded.authority_id,recorded.intent_sha256) != (
                case.pk,actor.pk,person_id,cfg.pk,intent):
            raise ValidationError('IDEMPOTENCY_CONFLICT: This request already recorded a different move.')
        return recorded
    review = prepare(actor,case,person_id,role,mode,team_id)
    if fingerprint != review['fingerprint']:
        raise ValidationError('STALE_VERSION: Review current access, work and team before confirming.')
    if review['holds']:
        raise ValidationError(review['holds'])
    revocations = [intake.change_access(actor,case.pk,person_id,row['action'],False,reason).pk for row in review['grants']]
    moved = StaffScopeMove.objects.create(case=case,user_id=person_id,actor=actor,authority=cfg,operation=key,
        fingerprint=fingerprint,intent_sha256=intent,manifest=review['manifest'],revocations=revocations,reason=reason)
    member = StaffMembership.objects.create(case=case,user_id=person_id,role=role,mode=mode,team_id=team_id,scope_move=moved)
    StaffAssignment.objects.bulk_create([StaffAssignment(case=case,membership=member,action=item,actor=actor)
                                        for item in review['items']])
    event(actor,case,'staff.workspace_scope_moved',move=moved.pk,member=member.pk,person=person_id)
    bump(case)
    return moved

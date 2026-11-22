"""Exact Finance schedule and HR correction decisions on the staff desk."""
from uuid import uuid4

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.http import Http404
from django.shortcuts import get_object_or_404

from apps.core.models import Case
from apps.core.services import add_evidence, bump, event
from apps.documents.contracts import digest
from apps.finance import hrfinance, schedules
from apps.finance.hrfinance_models import HRHandoffRecord, HRReadSnapshot
from apps.finance.schedule_models import ScheduleWork

from . import intake, teams
from .services import require, subject_actions
from .team_models import StaffAssignment, StaffScheduleReviewUse


SCHEDULE_ACTIONS = frozenset({'case.read', 'finance.read', 'schedules.read', 'schedules.review', 'evidence.add'})
HR_ACTIONS = frozenset({'case.read', 'hrfinance.read', 'hrfinance.respond', 'evidence.add'})


def schedule_records(case):
    return ScheduleWork.objects.filter(case=case, kind__in=['income','inventory'])


def correction_records(case):
    return HRHandoffRecord.objects.filter(contract__need__case=case, kind='correction')


def exact_successor(request, successor_id):
    return get_object_or_404(HRReadSnapshot.objects.defer('payload'), pk=successor_id, contract_id=request.contract_id,
                             pk__gt=request.snapshot_id, status='accepted')


@transaction.atomic
def assign(actor, case_id, member_id, kind, target_id, expected, successor_id=None):
    from .role_work import member_for

    case = Case.objects.select_for_update().get(pk=case_id)
    member = member_for(case, member_id)
    intake.lock_users([actor.pk,member.user_id])
    if case.revision != expected:
        raise ValidationError('STALE_VERSION: Review the current decision assignment.')
    if kind == 'schedule' and member.role == 'finance-lead' and successor_id is None:
        teams.manageable(actor, case, SCHEDULE_ACTIONS)
        schedules.readable(actor, case)
        target = get_object_or_404(schedule_records(case).defer('payload','snapshot','result'), pk=target_id)
        if target.reviews.exists():
            raise ValidationError('Choose a Finance schedule version without a recorded decision.')
        record, defaults = {'schedule': target}, {}
    elif kind == 'hr' and member.role == 'hr':
        teams.manageable(actor, case, HR_ACTIONS)
        require(actor, case, 'hrfinance.read')
        target = get_object_or_404(correction_records(case), pk=target_id)
        if hrfinance.correction_disposition(target).exists():
            raise ValidationError('This HR correction already has a decision.')
        successor = exact_successor(target, successor_id) if successor_id else None
        if successor:
            hrfinance.current_snapshot(successor)
        record, defaults = {'hr_request': target}, {'hr_successor': successor}
    else:
        raise ValidationError('Choose an assignee and a native decision from the same department.')
    row, created = StaffAssignment.objects.get_or_create(case=case, membership=member, **record,
                                                          defaults={'actor':actor, **defaults})
    if created:
        event(actor, case, 'staff.native_decision_assigned', assignment=row.pk, member=member.pk, kind=kind)
        bump(case)
    elif kind == 'hr' and row.hr_successor_id != successor_id:
        raise ValidationError('Review the original correction assignment before changing its export.')
    return row


def schedule_options(actor, row):
    work = row.schedule
    if work.actor_id == actor.pk or work.reviews.exists():
        return None
    schedules.current(work)
    with subject_actions(actor, row.case, SCHEDULE_ACTIONS):
        authority = schedules.authority(actor, work)
    result = work.result
    report = 'Income detail' if work.kind == 'income' else 'Schedule inventory'
    sections = [{'heading':'Prepared result','text':'Ready for review' if result['status'] == 'ready' else 'Held for follow-up'}]
    if work.kind == 'income' and result.get('adjusted_total') is not None:
        sections.append({'heading':'Adjusted total','text':f"{result['adjusted_total']} {result['target_unit']}"})
    if work.kind == 'inventory':
        entries = result.get('schedules', [])
        sections.append({'heading':'Selected inventory','text':f"{sum(entry['included'] for entry in entries)} of {len(entries)} schedules included"})
    return {'title':f'{report} · {work.reference}', 'version':work.version, 'role':'Finance', 'sections':sections,
            'verdicts':['approve','return','reject'] if result['status']=='ready' else ['return','reject'],
            'native_pin':{'id':work.pk,'sha256':work.sha256,'authority':authority}}


def hr_options(actor, row):
    request = row.hr_request
    if request.actor_id == actor.pk or hrfinance.correction_disposition(request).exists():
        return None
    hrfinance.authorized(request.contract)
    authority = hrfinance.authority(actor,row.case,'respond')
    sections = [{'heading':'Correction request','text':'Review the authorised payroll matching correction.'}]
    verdicts = ['return','reject']
    successor_hash = None
    if row.hr_successor_id:
        successor = exact_successor(request, row.hr_successor_id)
        hrfinance.current_snapshot(successor)
        successor_hash = successor.sha256
        sections.append({'heading':'Corrected export','text':f'Snapshot {successor.pk} · {successor.created_at:%d %b %Y}'})
        verdicts.insert(0,'approve')
    return {'title':'Staff matching correction', 'version':None, 'role':'HR', 'sections':sections,
            'verdicts':verdicts, 'native_pin':{'id':request.pk,'successor':row.hr_successor_id,'sha256':successor_hash,
                                             'authority':authority}}


def options(actor, row):
    try:
        packet = schedule_options(actor,row) if row.schedule_id else hr_options(actor,row)
    except (Http404, PermissionDenied, ValidationError):
        return None
    if packet:
        packet['token'] = digest({'assignment':row.pk, 'case_revision':row.case.revision,'revision':row.revision,
                                  'native':packet.pop('native_pin')})
    return packet


def perform(actor, row, verdict, note, case_expected):
    active_actions = SCHEDULE_ACTIONS if row.schedule_id else HR_ACTIONS
    kind = 'finance_review' if row.schedule_id else 'hr_correction_response'
    with subject_actions(actor,row.case,active_actions):
        proof = add_evidence(actor,row.case_id,kind,note,f'role-work:{row.pk}',expected=case_expected)
        if row.schedule_id:
            review = schedules.review(actor,row.case_id,row.schedule_id,verdict,proof.pk,note,case_expected+1)
            StaffScheduleReviewUse.objects.create(assignment=row,review=review)
        else:
            review = hrfinance.decide_correction(actor,row.case_id,row.hr_request_id,verdict,
                row.hr_successor_id if verdict=='approve' else None,str(uuid4()),proof.pk,case_expected+1)
    return review.pk


def schedule_review_access(work, review):
    return StaffScheduleReviewUse.objects.filter(review=review,assignment__schedule=work,assignment__case=work.case,
        assignment__membership__user_id=review.actor_id,assignment__membership__active=True,
        assignment__membership__user__is_active=True).exists()

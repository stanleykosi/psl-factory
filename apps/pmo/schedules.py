from django.core.exceptions import ValidationError, PermissionDenied
from django.db import transaction
from django.utils import timezone
from apps.core.models import Case
from apps.core.services import lock_case, event, bump
from apps.identity.services import require
from apps.documents.models import Template
from apps.documents.controlled import request_review
from apps.workflows.models import HumanTask
from .models import ReportSchedule, ReportOccurrence
from .clocks import report_window, aware, REPORT_KINDS
from .reporting import draft_period_report


@transaction.atomic
def save_schedule(actor,case_id,kind,template_id,audience,expected):
    case=lock_case(actor,case_id,'report.schedule',expected)
    template=Template.objects.filter(case=case,pk=template_id,definition__document_type='status_report').first()
    if not template or kind not in REPORT_KINDS or audience not in template.definition['audience_fields']:
        raise ValidationError('Choose a report purpose, audience and case status-report template')
    if kind=='weekly_client' and audience!='client' or kind=='internal_tuesday' and audience!='internal':
        raise ValidationError('Reporting purpose has a prescribed audience')
    if ReportSchedule.objects.filter(case=case,kind=kind,audience=audience).exists():
        raise ValidationError('Schedule exists; inspect/arm or pause that schedule instead')
    schedule=ReportSchedule.objects.create(case=case,kind=kind,template=template,audience=audience,actor=actor)
    event(actor,case,'report.schedule_saved',schedule=schedule.pk)
    bump(case)
    return schedule


@transaction.atomic
def arm_schedule(actor,case_id,schedule_id,after,expected):
    case=lock_case(actor,case_id,'report.schedule',expected)
    schedule=ReportSchedule.objects.filter(case=case,pk=schedule_id).first()
    if not schedule:raise ValidationError('Schedule is outside this project')
    due,start,end,policies=report_window(case,schedule.kind,aware(after))
    # Human schedule control does not confer publication or domain data permissions.
    schedule.actor=actor;schedule.status='active';schedule.next_due_at=due;schedule.next_start_at=start;schedule.next_end_at=end;schedule.policies=policies;schedule.error=''
    schedule.save(update_fields=['actor','status','next_due_at','next_start_at','next_end_at','policies','error'])
    event(actor,case,'report.schedule_armed',schedule=schedule.pk,due_at=due.isoformat(),policies=policies)
    bump(case)
    return schedule


@transaction.atomic
def pause_schedule(actor,case_id,schedule_id,reason,expected):
    case=lock_case(actor,case_id,'report.schedule',expected)
    schedule=ReportSchedule.objects.filter(case=case,pk=schedule_id).first()
    if not schedule or not reason.strip() or len(reason)>4000:raise ValidationError('A case schedule and rationale are required')
    schedule.status='paused';schedule.error=reason[:500];schedule.save(update_fields=['status','error'])
    event(actor,case,'report.schedule_paused',schedule=schedule.pk,reason=reason)
    bump(case)


@transaction.atomic
def run_report_once(at=None):
    at=at or timezone.now()
    target=ReportSchedule.objects.filter(status='active',next_due_at__lte=at).order_by('next_due_at','pk').first()
    if not target:return False
    # Consistent case-first lock order. Internal draft/event/cursor writes commit atomically, without network calls.
    case=Case.objects.select_for_update(skip_locked=True).filter(pk=target.case_id).first()
    if not case:return False
    schedule=ReportSchedule.objects.select_for_update().get(pk=target.pk)
    if schedule.status!='active' or schedule.next_due_at>at:return False
    actor=schedule.actor
    try:
        with transaction.atomic():
            require(actor,case,'report.schedule')
            # Recompute the exact stored occurrence under current policy before generating any draft.
            from datetime import timedelta
            due,start,end,policies=report_window(case,schedule.kind,schedule.next_due_at-timedelta(seconds=1))
            if (due,start,end,policies)!=(schedule.next_due_at,schedule.next_start_at,schedule.next_end_at,schedule.policies):
                raise ValidationError('Schedule policy changed; explicitly preview and re-arm the schedule')
            occurrence=ReportOccurrence.objects.filter(schedule=schedule,due_at=due).first()
            if not occurrence:
                binding=draft_period_report(actor,case.pk,schedule.kind,start,end,schedule.template_id,schedule.audience,case.revision,policies,True)
                case.refresh_from_db()
                if not HumanTask.objects.filter(version=binding.version).exists():request_review(actor,case.pk,binding.version_id,case.revision)
                ReportOccurrence.objects.create(schedule=schedule,due_at=due,binding=binding,policies=policies)
            next_due,next_start,next_end,pinned=report_window(case,schedule.kind,due)
            schedule.next_due_at=next_due;schedule.next_start_at=next_start;schedule.next_end_at=next_end;schedule.policies=pinned;schedule.error=''
            schedule.save(update_fields=['next_due_at','next_start_at','next_end_at','policies','error'])
            event(actor,case,'report.occurrence_drafted',schedule=schedule.pk,due_at=due.isoformat())
    except (ValidationError,PermissionDenied) as exc:
        schedule.status='held';schedule.error=str(exc)[:500];schedule.save(update_fields=['status','error'])
        event(actor,case,'report.schedule_held',schedule=schedule.pk,error=schedule.error)
    case.refresh_from_db()
    bump(case)
    return True

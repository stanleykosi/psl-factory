from calendar import monthrange
from datetime import datetime, timedelta, time, timezone as dt_timezone
from zoneinfo import ZoneInfo
from django.core.exceptions import ValidationError
from apps.policy.services import active_component, reference_values, require_operation

REPORT_KINDS=['internal_tuesday','weekly_client','monthly_executive']


def aware(value,label='Timestamp'):
    try:
        result=datetime.fromisoformat(value) if isinstance(value,str) else value
        if not isinstance(result,datetime) or result.utcoffset() is None:raise ValueError
        return result
    except (TypeError,ValueError):raise ValidationError(label+' requires an explicit timezone offset')


def local_time(day,clock,zone):
    wall=datetime.combine(day,time.fromisoformat(clock))
    candidates={}
    for fold in [0,1]:
        value=wall.replace(tzinfo=zone,fold=fold)
        utc=value.astimezone(dt_timezone.utc)
        if utc.astimezone(zone).replace(tzinfo=None)==wall:candidates[utc]=value
    if len(candidates)!=1:
        raise ValidationError('Ambiguous or nonexistent local schedule time; choose another configured time or an explicit timestamp')
    return next(iter(candidates.values()))


def configuration(component,case):
    config=active_component(component,case)
    return config,reference_values(config)[0]


def calculate_action_due(case,meeting_at,assignment_at):
    configs={key:active_component(key,case) for key in ['D04.clock_anchor_pause_rules','D04.deadline_parameters']}
    rules=reference_values(configs['D04.clock_anchor_pause_rules'])[0];params=reference_values(configs['D04.deadline_parameters'])[0]
    if 'action_anchor' not in rules or 'action' not in params:
        raise ValidationError('D04 action_anchor/action deadline parameters are unconfigured')
    anchor=meeting_at if rules['action_anchor']=='meeting_at' else assignment_at
    if not anchor:raise ValidationError('Configured meeting anchor needs a recorded meeting timestamp')
    rule=params['action'];anchor=aware(anchor)
    if rule['unit']=='elapsed_hours':
        due=anchor.astimezone(dt_timezone.utc)+timedelta(hours=rule['amount'])
    else:
        for key in ['D04.iana_timezone','D04.working_calendar_ref']:configs[key]=active_component(key,case)
        zone=ZoneInfo(configs['D04.iana_timezone'].envelope['value']);calendar=reference_values(configs['D04.working_calendar_ref'])[0]
        day=anchor.astimezone(zone).date();remaining=rule['amount']
        if rule['anchor_day']=='include_if_working' and day.weekday() in calendar['weekdays'] and day.isoformat() not in calendar['holidays']:
            remaining-=1
        for _ in range(3660):
            if remaining==0:break
            day+=timedelta(days=1)
            if day.weekday() in calendar['weekdays'] and day.isoformat() not in calendar['holidays']:remaining-=1
            if remaining==0:break
        else:raise ValidationError('Working calendar calculation exceeded its bounded horizon')
        due=local_time(day,calendar['due_time'],zone)
    return due,{key:value.pk for key,value in configs.items()},{'anchor':anchor.isoformat(),'format':'psl.action-clock-input/v1',
        'anchor_kind':rules['action_anchor'],'meeting_at':aware(meeting_at).isoformat() if meeting_at is not None else None,
        'assignment_at':aware(assignment_at).isoformat() if assignment_at is not None else None}


def report_window(case,kind,after):
    if kind not in REPORT_KINDS:raise ValidationError('Unknown report cadence')
    tz_config=active_component('D04.iana_timezone',case)
    params_config,params=configuration('D04.deadline_parameters',case)
    profile=params.get('reporting',{}).get(kind)
    if not profile:raise ValidationError('D04.deadline_parameters.reporting.'+kind+' is unconfigured')
    zone=ZoneInfo(tz_config.envelope['value']);after=aware(after);local=after.astimezone(zone)
    pinned={tz_config.component:tz_config.pk,params_config.component:params_config.pk}
    calendar=None
    if profile['holiday_treatment']=='next_working_day':
        calendar_config,calendar=configuration('D04.working_calendar_ref',case);pinned[calendar_config.component]=calendar_config.pk
    for days in range(0,400):
        day=local.date()+timedelta(days=days)
        if kind=='monthly_executive':
            length=monthrange(day.year,day.month)[1];target=profile['day']
            if target>length:
                if profile['month_end_rule']=='skip_month':continue
                target=length
            if day.day!=target:continue
        elif day.weekday()!=(1 if kind=='internal_tuesday' else profile['weekday']):continue
        scheduled=local_time(day,profile['time'],zone)
        effective=scheduled
        if calendar:
            shifted=day
            for _ in range(366):
                if shifted.weekday() in calendar['weekdays'] and shifted.isoformat() not in calendar['holidays']:break
                shifted+=timedelta(days=1)
            else:raise ValidationError('No working report date within bounded horizon')
            effective=local_time(shifted,profile['time'],zone)
        if effective<=after:continue
        cutoff=scheduled if profile['coverage_anchor']=='scheduled_time' else effective
        if profile['coverage']=='previous_calendar_month':
            first=cutoff.date().replace(day=1);end=local_time(first,'00:00',zone)
            previous=(first-timedelta(days=1)).replace(day=1);start=local_time(previous,'00:00',zone)
        else:
            end=cutoff;start=local_time(cutoff.date()-timedelta(days=7),profile['time'],zone)
        return effective,start,end,pinned
    raise ValidationError('No report occurrence found within bounded horizon')

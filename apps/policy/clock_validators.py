from datetime import date, time
from django.core.exceptions import ValidationError
from apps.documents.contracts import validate
from .document_validators import typed

SUPPORTED={'D04.working_calendar_ref','D04.clock_anchor_pause_rules','D04.deadline_parameters'}
TIME={'type':'string','pattern':r'^([01]\d|2[0-3]):[0-5]\d$'}


REPORT_PROFILE={'type':'object','properties':{'weekday':{'type':'integer','minimum':0,'maximum':6},'day':{'type':'integer','minimum':1,'maximum':31},
            'time':TIME,'holiday_treatment':{'enum':['calendar','next_working_day']},'month_end_rule':{'enum':['last_day','skip_month']},
            'coverage':{'enum':['preceding_7_days','previous_calendar_month']},'coverage_anchor':{'enum':['scheduled_time','effective_due']}},
            'required':['time','holiday_treatment','coverage','coverage_anchor'],'additionalProperties':False}
DEADLINE_SCHEMA={'type':'object','properties':{
            'emergency':{'type':'object','properties':{'retrospective_working_days':{'type':'integer','minimum':1,'maximum':2}},
                'required':['retrospective_working_days'],'additionalProperties':False},
            'issues':{'type':'object','properties':{
                'acknowledgement_hours':{'type':'number','exclusiveMinimum':0,'maximum':8760},
                'internal_24h_routes':{'type':'object','properties':{s:{'enum':['PMO','CTO']} for s in ['Critical','High','Medium','Low']},
                    'required':['Critical','High','Medium','Low'],'additionalProperties':False}},'minProperties':1,'additionalProperties':False},
            'action':{'type':'object','properties':{'unit':{'enum':['elapsed_hours','working_days']},'amount':{'type':'integer','minimum':1,'maximum':366},'anchor_day':{'enum':['exclude','include_if_working']}},
                'required':['unit','amount'],'additionalProperties':False,'allOf':[{'if':{'properties':{'unit':{'const':'working_days'}}},'then':{'required':['anchor_day']}}]},
            'reporting':{'type':'object','properties':{kind:REPORT_PROFILE for kind in ['internal_tuesday','weekly_client','monthly_executive']},
                'minProperties':1,'additionalProperties':False}},'minProperties':1,'additionalProperties':False}

def validate_reference(component,target,case):
    if component=='D04.working_calendar_ref':
        value=typed(target,'schema:psl/working-calendar/v1',{'type':'object','properties':{
            'weekdays':{'type':'array','minItems':1,'uniqueItems':True,'items':{'type':'integer','minimum':0,'maximum':6}},
            'holidays':{'type':'array','uniqueItems':True,'items':{'type':'string'}},'due_time':TIME},
            'required':['weekdays','holidays','due_time'],'additionalProperties':False})
        try:
            for day in value['holidays']:
                if date.fromisoformat(day).isoformat()!=day:raise ValueError
            time.fromisoformat(value['due_time'])
        except ValueError:raise ValidationError('Calendar dates/times must be explicit ISO dates and HH:MM')
    elif component=='D04.clock_anchor_pause_rules':
        typed(target,'schema:psl/action-clock/v1',{'type':'object','properties':{
            'action_anchor':{'enum':['meeting_at','assignment_at']},
            'emergency':{'type':'object','properties':{'anchor':{'const':'implemented_at'},'pause':{'const':'no_pause'},
                'anchor_day':{'enum':['exclude','include_if_working']}},'required':['anchor','pause','anchor_day'],'additionalProperties':False},
            'issues':{'type':'object','properties':{'anchor':{'enum':['logged_at','trigger_at']},
                'basis':{'const':'elapsed_hours'},'pause':{'const':'no_pause'}},
                'required':['anchor','basis','pause'],'additionalProperties':False},
            'pause_behavior':{'enum':['not_permitted','no_extension','extend_elapsed']}},'minProperties':1,'additionalProperties':False})
    else:
        profile={'type':'object','properties':{'weekday':{'type':'integer','minimum':0,'maximum':6},'day':{'type':'integer','minimum':1,'maximum':31},
            'time':TIME,'holiday_treatment':{'enum':['calendar','next_working_day']},'month_end_rule':{'enum':['last_day','skip_month']},
            'coverage':{'enum':['preceding_7_days','previous_calendar_month']},'coverage_anchor':{'enum':['scheduled_time','effective_due']}},
            'required':['time','holiday_treatment','coverage','coverage_anchor'],'additionalProperties':False}
        value=typed(target,'schema:psl/deadline-parameters/v1',DEADLINE_SCHEMA)
        for kind,rule in value.get('reporting',{}).items():
            if kind=='internal_tuesday' and ('weekday' in rule and rule['weekday']!=1 or 'day' in rule):
                raise ValidationError('P40 Tuesday is a known source invariant, not an editable weekday')
            if kind=='weekly_client' and ('weekday' not in rule or 'day' in rule):
                raise ValidationError('Weekly reporting needs an explicit weekday')
            if kind=='monthly_executive' and ('day' not in rule or 'month_end_rule' not in rule or 'weekday' in rule):
                raise ValidationError('Monthly reporting needs day and short-month treatment')

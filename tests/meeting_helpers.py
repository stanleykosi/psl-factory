from datetime import timedelta
from uuid import uuid4
from django.utils import timezone
from apps.core.services import add_evidence
from apps.documents.controlled import register_template
from apps.policy.services import register_reference
from apps.pmo.meetings import record_meeting, create_action
from .helpers import rev, activate
from .document_helpers import publication_fixture, artifact

MINUTES_DEFINITION={'document_type':'minutes','required_fields':['executive_summary','decisions','actions','owners','deadlines'],
    'audience_fields':{a:['executive_summary','decisions','actions','owners','deadlines','participants','scope'] for a in ['client','internal','management']}}


def meetings_fixture():
    actor,case,owner,source,report_template,recipient,_,_=publication_fixture()
    minutes=register_template(actor,case.pk,'Formal minutes',MINUTES_DEFINITION,owner.pk,rev(case))
    artifact(actor,case,'D11.template_storage_retention_rules','schema:psl/document-storage/v1',
        {'template_ids':[report_template.pk,minutes.pk],'repository':'internal-versioned','retention_days':30},owner)
    notes=add_evidence(actor,case.pk,'meeting_notes','Confirm the current delivery plan.\nInvestigate the dependency before the next review.','synthetic:meeting-notes')
    meeting=record_meeting(actor,case.pk,'STATUS-001','status',timezone.now()-timedelta(hours=1),'Review delivery and actions','Delivery progress and dependencies were reviewed.',
        [actor.pk],[{'text':'Confirm the current delivery plan.','evidence_id':notes.pk}],notes.pk,rev(case))
    return actor,case,owner,notes,minutes,report_template,meeting,recipient


def configure_clock(actor,case,owner,calendar=True,anchors=True,reporting=None,action=True):
    activate(actor,case,'D04.iana_timezone','Africa/Lagos',owner)
    if calendar:
        r=register_reference(actor,case.pk,'calendar:'+str(uuid4()),'schema:psl/working-calendar/v1',
            {'weekdays':[0,1,2,3,4],'holidays':['2026-10-21'],'due_time':'17:00'},owner.pk)
        activate(actor,case,'D04.working_calendar_ref',r.ref,owner)
    if anchors:artifact(actor,case,'D04.clock_anchor_pause_rules','schema:psl/action-clock/v1',{'action_anchor':'meeting_at','pause_behavior':'extend_elapsed'},owner)
    profiles=reporting if reporting is not None else {
        'internal_tuesday':{'time':'09:00','holiday_treatment':'calendar','coverage':'preceding_7_days','coverage_anchor':'scheduled_time'},
        'weekly_client':{'weekday':4,'time':'09:00','holiday_treatment':'calendar','coverage':'preceding_7_days','coverage_anchor':'scheduled_time'},
        'monthly_executive':{'day':2,'time':'10:00','month_end_rule':'last_day','holiday_treatment':'calendar','coverage':'previous_calendar_month','coverage_anchor':'scheduled_time'}}
    params={}
    if action:params['action']={'unit':'working_days','amount':2,'anchor_day':'exclude'}
    if profiles:params['reporting']=profiles
    return artifact(actor,case,'D04.deadline_parameters','schema:psl/deadline-parameters/v1',params,owner)

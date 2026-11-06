from datetime import timedelta
from zoneinfo import ZoneInfo
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from apps.core.models import Case
from apps.core.services import add_evidence
from apps.identity.models import Grant
from apps.policy.services import resolve, transition, register_reference, save_draft
from apps.policy.registry import components
from apps.policy.clock_drafts import draft_clock_policy
from apps.documents.controlled import register_template, request_review, review_version, reserve_publication
from apps.documents.models import Template
from apps.pmo.models import Meeting
from apps.pmo.meetings import record_meeting, create_action
from apps.pmo.reporting import draft_minutes, draft_period_report
from apps.pmo.schedules import save_schedule, arm_schedule
from apps.agents.meetings import suggest_commitments, investigate_actions
from .seed_demo import ACTIONS

class Command(BaseCommand):
    help='Add isolated synthetic formal minutes/actions/reporting examples, leaving publication and timer workers separate'
    def add_arguments(self,parser):parser.add_argument('--username',default='studio-demo')
    @transaction.atomic
    def handle(self,*args,**options):
        actor=get_user_model().objects.get(username=options['username'])
        case=Case.objects.get(tenant='synthetic-demo',synthetic=True,kind='project',grant__user=actor,grant__action='case.read')
        if Meeting.objects.filter(case=case,reference='SYNTHETIC-STATUS-001').exists():
            raise CommandError('Minutes demo exists; its evidence/history is preserved')
        if resolve('D05.role_principal_assignments',case).status!='ACTIVE':
            raise CommandError('Run seed_documents_demo first to provision the isolated synthetic review-role fixture')
        for action in ACTIONS:Grant.objects.get_or_create(case=case,user=actor,action=action)
        now=timezone.now()
        def revision():case.refresh_from_db();return case.revision
        owner=add_evidence(actor,case.pk,'policy_decision','Synthetic calendar, reporting, minutes and template fixture. These values are not operational business policy.','synthetic:minutes-owner')
        for component,value in [
            ('D04.iana_timezone','Africa/Lagos'),
            ('D04.working_calendar_ref',{'weekdays':[0,1,2,3,4],'holidays':[],'due_time':'17:00'}),
            ('D04.clock_anchor_pause_rules',{'action_anchor':'meeting_at','pause_behavior':'extend_elapsed'}),
            ('D04.deadline_parameters',{'action':{'unit':'elapsed_hours','amount':48},'reporting':{
                'internal_tuesday':{'time':'09:00','holiday_treatment':'calendar','coverage':'preceding_7_days','coverage_anchor':'scheduled_time'},
                'weekly_client':{'weekday':now.astimezone(ZoneInfo('Africa/Lagos')).weekday(),'time':'00:00','holiday_treatment':'calendar','coverage':'preceding_7_days','coverage_anchor':'scheduled_time'},
                'monthly_executive':{'day':2,'time':'10:00','month_end_rule':'last_day','holiday_treatment':'calendar','coverage':'previous_calendar_month','coverage_anchor':'scheduled_time'}}})]:
            config=draft_clock_policy(actor,case.pk,component,value,owner.pk,now-timedelta(minutes=1))
            transition(actor,config.pk,'validated');transition(actor,config.pk,'active')
        minutes_definition={'document_type':'minutes','required_fields':['executive_summary','decisions','actions','owners','deadlines'],
            'audience_fields':{a:['executive_summary','decisions','actions','owners','deadlines','participants','scope'] for a in ['client','internal']}}
        report_definition={'document_type':'status_report','required_fields':['executive_summary','status'],
            'audience_fields':{a:['executive_summary','status','actions','owners','deadlines','risks','next_steps','decisions'] for a in ['client','internal','management']}}
        mt=register_template(actor,case.pk,'Synthetic formal minutes',minutes_definition,owner.pk,revision())
        rt=register_template(actor,case.pk,'Synthetic period report',report_definition,owner.pk,revision())
        reference=register_reference(actor,case.pk,'minutes-demo:storage','schema:psl/document-storage/v1',
            {'template_ids':list(Template.objects.filter(case=case).values_list('pk',flat=True)),'repository':'internal-versioned','retention_days':30},owner.pk)
        component='D11.template_storage_retention_rules'
        envelope={'slot_id':'D11','component_id':component,'component_schema_ref':components()[component]['schema_ref'],
            'subject_scope':{'kind':'project','ref':str(case.pk)},'schema_version':'1','policy_revision':1,'lifecycle':'draft',
            'effective_from':(now-timedelta(minutes=1)).isoformat(),'effective_until':None,'evidence_refs':[f'evidence:{owner.pk}'],
            'human_decision_ref':f'evidence:{owner.pk}','implementation_id':'psl.reference-validation','implementation_version':'1',
            'reviewed_implementation_ref':'code:apps/policy/services.py#reference-validation-v1','fixture_scope':'synthetic_test',
            'value':{'artifact_ref':reference.ref,'artifact_version':reference.version,'sha256':reference.sha256,'schema_ref':reference.schema_ref}}
        config=save_draft(actor,case.pk,envelope);transition(actor,config.pk,'validated');transition(actor,config.pk,'active')
        notes=add_evidence(actor,case.pk,'meeting_notes','Synthetic delivery status review.\nInvestigate the dependency before the next review.\nNo change to signed scope was approved.','synthetic:formal-meeting')
        meeting=record_meeting(actor,case.pk,'SYNTHETIC-STATUS-001','status',now-timedelta(hours=2),'Review delivery commitments',
            'The synthetic team reviewed progress, recorded follow-ups and kept missing commitment details explicit.',[actor.pk],
            [{'text':'No change to signed scope was approved.','evidence_id':notes.pk}],notes.pk,revision())
        create_action(actor,case.pk,'SYN-ACT-001','Investigate the delivery dependency',actor.pk,now+timedelta(days=2),notes.pk,'Explicit synthetic commitment',revision(),meeting.meeting_id)
        create_action(actor,case.pk,'SYN-ACT-002','Collect an owner and deadline for the open dependency',None,None,notes.pk,'Unknown details remain unknown',revision(),meeting.meeting_id)
        create_action(actor,case.pk,'SYN-ACT-003','Configured follow-up example',actor.pk,None,notes.pk,'Synthetic elapsed-hours rule fixture',revision(),meeting.meeting_id,True)
        suggest_commitments(actor,case.pk,notes.pk,revision());investigate_actions(actor,case.pk)
        for binding in [draft_minutes(actor,case.pk,meeting.meeting_id,mt.pk,'client',revision()),
            draft_period_report(actor,case.pk,'weekly_client',now-timedelta(days=7),now,rt.pk,'client',revision())]:
            request_review(actor,case.pk,binding.version_id,revision())
            review_version(actor,case.pk,binding.version_id,'approve','Synthetic PMO Lead fixture reviewed the exact audience version',revision())
            reserve_publication(actor,case.pk,binding.version_id,revision())
        schedule=save_schedule(actor,case.pk,'weekly_client',rt.pk,'client',revision())
        arm_schedule(actor,case.pk,schedule.pk,now-timedelta(days=1),revision())
        self.stdout.write('Synthetic minutes/report publications reserved and schedule armed. Run work_reports then work_publications separately.')

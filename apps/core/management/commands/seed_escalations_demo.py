from datetime import timedelta
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand,CommandError
from django.db import transaction
from django.utils import timezone
from apps.core.models import Case
from apps.core.services import add_evidence
from apps.identity.models import Grant
from apps.policy.registry import components
from apps.policy.services import resolve,register_reference,save_draft,transition
from apps.documents.controlled import register_template,request_review,review_version,reserve_publication
from apps.pmo.models import Issue,EscalationProfile
from apps.pmo.escalations import capture_profile,scan_profile,request_escalation,decide_escalation,draft_escalation
from apps.agents.escalations import investigate_escalations
from .seed_demo import ACTIONS

class Command(BaseCommand):
    help='Extend only the isolated synthetic issue demo with reviewed client escalation and explicit synthetic clocks.'
    def add_arguments(self,parser):parser.add_argument('--username',default='studio-demo')
    @transaction.atomic
    def handle(self,*args,**options):
        actor=get_user_model().objects.get(username=options['username'])
        case=Case.objects.get(tenant='synthetic-demo',synthetic=True,title='Synthetic issue engagement')
        if EscalationProfile.objects.filter(state__issue__case=case).exists():raise CommandError('Escalation fixture exists; refusing overwrite')
        issue=Issue.objects.select_related('current').get(case=case,reference='SYN-ISSUE-001')
        if issue.current.status not in ['Open','In Progress']:raise CommandError('Issue fixture is no longer active; no overwrite')
        for action in ACTIONS:Grant.objects.get_or_create(case=case,user=actor,action=action,defaults={'active':True})
        def revision():case.refresh_from_db();return case.revision
        owner=add_evidence(actor,case.pk,'policy_decision','Synthetic issue clock/communication owner policy fixture only. No operational policy or actual approver appointment.','synthetic:escalation-owner')
        def activate(component,value):
            cfg=save_draft(actor,case.pk,{'slot_id':components()[component]['parent_decision_id'],'component_id':component,
                'component_schema_ref':components()[component]['schema_ref'],'schema_version':'1','subject_scope':{'kind':'project','ref':str(case.pk)},
                'policy_revision':1,'lifecycle':'draft','effective_from':(timezone.now()-timedelta(minutes=1)).isoformat(),'effective_until':None,
                'evidence_refs':[f'evidence:{owner.pk}'],'human_decision_ref':f'evidence:{owner.pk}',
                'implementation_id':'psl.reference-validation','implementation_version':'1','reviewed_implementation_ref':'code:apps/policy/services.py#reference-validation-v1',
                'fixture_scope':'synthetic_test','value':value})
            transition(actor,cfg.pk,'validated');transition(actor,cfg.pk,'active')
        existing=resolve('D05.role_principal_assignments',case)
        refs=list(existing.configuration.envelope['value']) if existing.status=='ACTIVE' else []
        for role in ['PMO Lead','Head of PMO']:
            r=register_reference(actor,case.pk,'synthetic:escalation-role:'+role,'schema:psl/role-assignment/v1',{'role':role,'user_id':actor.pk},owner.pk);refs.append(r.ref)
        activate('D05.role_principal_assignments',refs)
        def artifact(component,schema,content):
            r=register_reference(actor,case.pk,'synthetic:escalation:'+component,schema,content,owner.pk)
            activate(component,{'artifact_ref':r.ref,'artifact_version':r.version,'sha256':r.sha256,'schema_ref':r.schema_ref})
        artifact('D04.clock_anchor_pause_rules','schema:psl/action-clock/v1',{'issues':{'anchor':'trigger_at','basis':'elapsed_hours','pause':'no_pause'}})
        artifact('D04.deadline_parameters','schema:psl/deadline-parameters/v1',{'issues':{'acknowledgement_hours':2,
            'internal_24h_routes':{'Critical':'CTO','High':'PMO','Medium':'PMO','Low':'PMO'}}})
        source=add_evidence(actor,case.pk,'issue_impact','Synthetic client-dependent timeline impact; fixture trigger predates current observation by 49 elapsed hours. Not a real client issue.','synthetic:impact')
        p=capture_profile(actor,case.pk,issue.pk,issue.current_id,'client_dependent',True,timezone.now()-timedelta(hours=49),source.pk,'Explicit synthetic dependency and delivery impact',revision())
        signals=scan_profile(actor,case.pk,p.pk)
        r=request_escalation(actor,case.pk,p.pk,'escalate','Client',source.pk,'Synthetic fixture: please review the recorded delivery dependency. No real client communication.',revision())
        decide_escalation(actor,case.pk,r.pk,'Head of PMO','approve','Synthetic human-decision fixture for exact request',revision())
        t=register_template(actor,case.pk,'Synthetic client escalation',{'document_type':'project_artifact',
            'required_fields':['executive_summary','status','issue_status','issue_impact'],
            'audience_fields':{'client':['executive_summary','status','issue_status','issue_impact','next_steps']}},owner.pk,revision())
        recipient=register_reference(actor,case.pk,'synthetic:escalation-recipient','schema:psl/document-recipient/v1',{'audience':'client','user_id':actor.pk},owner.pk)
        activate('D11.recipient_grant_refs',[recipient.ref])
        artifact('D11.template_storage_retention_rules','schema:psl/document-storage/v1',{'template_ids':[t.pk],'repository':'internal-versioned','retention_days':30})
        v=draft_escalation(actor,case.pk,r.pk,t.pk,revision())
        request_review(actor,case.pk,v.pk,revision());review_version(actor,case.pk,v.pk,'approve','Synthetic PMO Lead exact outward review',revision())
        reserve_publication(actor,case.pk,v.pk,revision())
        investigate_escalations(actor,case.pk,revision())
        self.stdout.write(f'Synthetic escalation case {case.pk}; request {r.pk}, {len(signals)} urgency signals, reviewed publication pending. Run work_publications to deliver only to local recipient inbox.')

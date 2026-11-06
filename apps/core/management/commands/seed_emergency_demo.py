import json
from datetime import timedelta
from pathlib import Path
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand,CommandError
from django.db import transaction
from django.utils import timezone
from apps.core.models import Case
from apps.core.services import add_evidence
from apps.identity.models import Grant
from apps.policy.registry import components
from apps.policy.services import register_reference,save_draft,transition
from apps.policy.change_drafts import draft_standard_policy
from apps.policy.clock_drafts import draft_clock_policy
from apps.pmo.services import prepare_baseline,decide,sign_baseline
from apps.pmo.changes import log_change
from apps.pmo.gates import register_candidate,record_gate,verify_gate
from apps.pmo.emergencies import capture_profile,decide_emergency,authorize_emergency,capture_outcome,record_review,decide_retrospective,reconcile_retrospective
from apps.pmo.emergency_documents import draft_retrospective
from apps.documents.controlled import register_template,request_review,review_version,reserve_publication
from .seed_demo import ACTIONS

TITLE='Synthetic emergency evidence engagement'


class Command(BaseCommand):
    help='Prepare a separate synthetic Emergency/GLPI and reviewed retrospective fixture. No real system effect.'
    def add_arguments(self,parser):parser.add_argument('--username',default='studio-demo')
    @transaction.atomic
    def handle(self,*args,**options):
        actor=get_user_model().objects.filter(username=options['username'],is_active=True).first()
        if not actor:raise CommandError('Requires an existing active synthetic demo actor')
        if Case.objects.filter(tenant='synthetic-demo',title=TITLE).exists():raise CommandError('Emergency demonstration exists; refusing overwrite')
        case=Case.objects.create(tenant='synthetic-demo',title=TITLE,kind='project',synthetic=True)
        for action in ACTIONS:Grant.objects.create(case=case,user=actor,action=action)
        def rev():case.refresh_from_db();return case.revision
        def evidence(kind,body):return add_evidence(actor,case.pk,kind,body,'synthetic:emergency-demo')
        e={k:evidence(k,'Synthetic '+k+' source; no operational policy or real signature') for k in
            ['requirements','engineering_estimate','security_estimate','plan','costing','sow','signature','policy_decision']}
        owner=e['policy_decision']
        def activate(component,value):
            env={'slot_id':components()[component]['parent_decision_id'],'component_id':component,'component_schema_ref':components()[component]['schema_ref'],
                'schema_version':'1','policy_revision':1,'lifecycle':'draft','subject_scope':{'kind':'project','ref':str(case.pk)},
                'effective_from':(timezone.now()-timedelta(minutes=1)).isoformat(),'effective_until':None,
                'evidence_refs':[f'evidence:{owner.pk}'],'human_decision_ref':f'evidence:{owner.pk}',
                'implementation_id':'psl.reference-validation','implementation_version':'1','reviewed_implementation_ref':'code:apps/policy/services.py#reference-validation-v1',
                'fixture_scope':'synthetic_test','value':value}
            config=save_draft(actor,case.pk,env);transition(actor,config.pk,'validated');transition(actor,config.pk,'active');return config
        refs=[]
        for role in ['PM','Head of PMO','CEO','PMO Lead','Engineering Lead','CTO','Product']:
            r=register_reference(actor,case.pk,'demo:emergency-role:'+role,'schema:psl/role-assignment/v1',{'role':role,'user_id':actor.pk},owner.pk);refs.append(r.ref)
        activate('D05.role_principal_assignments',refs)
        prepare_baseline(actor,case.pk,e['plan'].pk,e['costing'].pk,e['sow'].pk,rev())
        for role in ['PM','Head of PMO','CEO','PMO Lead']:decide(actor,case.pk,role,rev())
        sign_baseline(actor,case.pk,e['signature'].pk,rev())
        data=json.loads((Path(settings.BASE_DIR)/'fixtures/emergencies.json').read_text(encoding='utf-8'))
        for component,value in [('D01.emergency_glpi_relationship',data['relationship']),('D01.satisfied_gate_map',data['gate_map'])]:
            cfg=draft_standard_policy(actor,case.pk,component,value,owner.pk,timezone.now());transition(actor,cfg.pk,'validated');transition(actor,cfg.pk,'active')
        for component,value in [('D04.iana_timezone',data['timezone']),('D04.working_calendar_ref',data['calendar']),
                ('D04.clock_anchor_pause_rules',data['clock_anchor']),('D04.deadline_parameters',data['deadline_parameters'])]:
            cfg=draft_clock_policy(actor,case.pk,component,value,owner.pk,timezone.now());transition(actor,cfg.pk,'validated');transition(actor,cfg.pk,'active')
        incident=evidence('incident','Synthetic external Engineering incident; no actual production event')
        classification=evidence('incident_classification','Synthetic explicit critical production/P1 attestation, not Critical-to-P1 mapping')
        source=evidence('change_request','Synthetic emergency work request')
        decision_source=evidence('emergency_decision','Synthetic exact owner human decision')
        implementation=evidence('change_implementation','Synthetic owner-reported implementation; no real deployment was dispatched')
        review_source=evidence('post_implementation_review','Synthetic mandatory owner review')
        change=log_change(actor,case.pk,'SYN-EM-001','Emergency','Synthetic API','Synthetic emergency demonstration','Synthetic incident evidence',source.pk,rev(),incident.pk)
        candidate=register_candidate(actor,case.pk,'synthetic-emergency-candidate',e['requirements'].pk,rev())
        profile=capture_profile(actor,case.pk,change.pk,candidate.pk,True,True,classification.pk,'Synthetic explicit incident applicability',rev())
        for role in ['Incident Lead','Engineering Lead','CTO']:
            decide_emergency(actor,case.pk,profile.pk,role,'Engineering Lead','approve',decision_source.pk,'Synthetic prescribed role decision',rev())
        for kind in ['glpi_security','glpi_cto','glpi_ceo']:
            gate=record_gate(actor,case.pk,candidate.pk,kind,'synthetic:emergency:'+kind,source.pk,rev())
            verify_gate(actor,case.pk,gate.pk,rev())
        auth=authorize_emergency(actor,case.pk,profile.pk,rev())
        outcome=capture_outcome(actor,case.pk,profile.pk,auth.pk,timezone.now(),implementation.pk,'Synthetic owner result captured after authorization',rev())
        record_review(actor,case.pk,outcome.pk,review_source.pk,'Synthetic post-implementation review',rev())
        for role in ['Product','Engineering Lead']:
            decide_retrospective(actor,case.pk,outcome.pk,role,'approve',decision_source.pk,'Synthetic retrospective human decision',rev())
        reconciliation=reconcile_retrospective(actor,case.pk,outcome.pk,rev())
        template=register_template(actor,case.pk,'Synthetic emergency report',{'document_type':'project_artifact','required_fields':['executive_summary','status'],
            'audience_fields':{'client':['executive_summary','status','next_steps']}},owner.pk,rev())
        recipient=register_reference(actor,case.pk,'demo:emergency-recipient','schema:psl/document-recipient/v1',{'audience':'client','user_id':actor.pk},owner.pk)
        activate('D11.recipient_grant_refs',[recipient.ref])
        storage=register_reference(actor,case.pk,'demo:emergency-storage','schema:psl/document-storage/v1',{'template_ids':[template.pk],'repository':'internal-versioned','retention_days':30},owner.pk)
        activate('D11.template_storage_retention_rules',{'artifact_ref':storage.ref,'artifact_version':storage.version,'sha256':storage.sha256,'schema_ref':storage.schema_ref})
        version=draft_retrospective(actor,case.pk,outcome.pk,template.pk,'client',rev())
        request_review(actor,case.pk,version.pk,rev());review_version(actor,case.pk,version.pk,'approve','Synthetic separate PMO Lead exact report review',rev())
        reserve_publication(actor,case.pk,version.pk,rev())
        self.stdout.write(f'Synthetic Emergency case {case.pk}; outcome {outcome.pk}; reconciliation {reconciliation.pk}; reviewed publication reserved. No real deployment/financial effect.')

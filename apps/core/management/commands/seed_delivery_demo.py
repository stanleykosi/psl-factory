import json
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
from apps.pmo.services import prepare_baseline,decide,sign_baseline,complete_milestone
from apps.pmo.gates import register_candidate,record_gate,verify_gate
from apps.pmo.meetings import record_meeting
from apps.pmo.delivery import (PLANNING,UPSTREAM_GATES,GLPI_GATES,open_dossier,capture_source,verify_source,
    decide_planning,record_progress,record_release_request,prepare_readiness,capture_release)
from apps.pmo.delivery_closure import accept_go_live,archive_artifacts,acknowledge_handover,confirm_finance
from apps.pmo.delivery_documents import draft_delivery_document
from apps.documents.controlled import register_template,request_review,review_version,reserve_publication
from apps.documents.delivery import run_publication_once
from apps.documents.models import PublicationReceipt
from apps.workflows.services import run_once
from .seed_demo import ACTIONS

TITLE='Synthetic delivery release and closure engagement'


class Command(BaseCommand):
    help='Build an isolated synthetic delivery dossier ready for human hypercare evaluation/closure demonstration; no remote effects'
    def add_arguments(self,parser):parser.add_argument('--username',default='studio-demo')
    @transaction.atomic
    def handle(self,*args,**options):
        a=get_user_model().objects.filter(username=options['username'],is_active=True).first()
        if not a or Case.objects.filter(tenant='synthetic-demo',title=TITLE).exists():raise CommandError('Requires existing demo actor and a fresh fixture; refusing overwrite')
        c=Case.objects.create(tenant='synthetic-demo',title=TITLE,kind='project',synthetic=True)
        for action in ACTIONS:Grant.objects.create(case=c,user=a,action=action)
        def rev():c.refresh_from_db();return c.revision
        def evidence(kind,body=None):return add_evidence(a,c.pk,kind,body or 'Synthetic '+kind+'; no genuine production event, business appointment or signature','synthetic:delivery-demo')
        e={k:evidence(k) for k in ['requirements','engineering_estimate','security_estimate','plan','costing','sow','signature','completion','policy_decision']}
        def activate(component,value):
            env={'slot_id':components()[component]['parent_decision_id'],'component_id':component,'component_schema_ref':components()[component]['schema_ref'],
                'schema_version':'1','policy_revision':1,'lifecycle':'draft','subject_scope':{'kind':'project','ref':str(c.pk)},
                'effective_from':timezone.now().isoformat(),'effective_until':None,'evidence_refs':[f'evidence:{e["policy_decision"].pk}'],
                'human_decision_ref':f'evidence:{e["policy_decision"].pk}','implementation_id':'psl.reference-validation','implementation_version':'1',
                'reviewed_implementation_ref':'code:apps/policy/services.py#reference-validation-v1','fixture_scope':'synthetic_test','value':value}
            cfg=save_draft(a,c.pk,env);transition(a,cfg.pk,'validated');transition(a,cfg.pk,'active');return cfg
        refs=[]
        for role in ['PM','Head of PMO','CEO','PMO Lead']:
            refs.append(register_reference(a,c.pk,'delivery-role:'+role,'schema:psl/role-assignment/v1',{'role':role,'user_id':a.pk},e['policy_decision'].pk).ref)
        activate('D05.role_principal_assignments',refs)
        prepare_baseline(a,c.pk,e['plan'].pk,e['costing'].pk,e['sow'].pk,rev())
        for role in ['PM','Head of PMO','CEO','PMO Lead']:decide(a,c.pk,role,rev())
        sign_baseline(a,c.pk,e['signature'].pk,rev())
        candidate=register_candidate(a,c.pk,'synthetic-delivery-candidate',e['requirements'].pk,rev())
        d=open_dossier(a,c.pk,candidate.pk,e['plan'].pk,'Synthetic exact PM scope/candidate attestation',rev())
        def source(kind,payload=None,src=None):
            s=capture_source(a,c.pk,d.pk,kind,'synthetic:owned:'+kind,(src or e['requirements']).pk,payload or {},rev());verify_source(a,c.pk,s.pk,rev());return s
        for kind in PLANNING:source(kind,{'requires_ui':False,'client_signoff_required':False} if kind=='ui_applicability' else {})
        decide_planning(a,c.pk,d.pk,'approve',e['plan'].pk,'Synthetic exact Planning exit',rev())
        kickoff=record_meeting(a,c.pk,'SYN-KICKOFF','kickoff',timezone.now(),'Synthetic delivery expectations','Source-bound kickoff with named participant',[a.pk],[],e['requirements'].pk,rev())
        record_progress(a,c.pk,d.pk,'kickoff',e['requirements'].pk,'Synthetic kickoff after Planning approval',rev(),kickoff.pk)
        for kind in UPSTREAM_GATES:
            gate=record_gate(a,c.pk,candidate.pk,kind,'synthetic:'+kind,e['requirements'].pk,rev());verify_gate(a,c.pk,gate.pk,rev())
        record_release_request(a,c.pk,d.pk,'SYN-GLPI-DELIVERY',e['requirements'].pk,'Synthetic external request identity',rev())
        for kind in GLPI_GATES:
            gate=record_gate(a,c.pk,candidate.pk,kind,'SYN-GLPI-DELIVERY',e['requirements'].pk,rev());verify_gate(a,c.pk,gate.pk,rev())
        ready=prepare_readiness(a,c.pk,d.pk,rev());capture_release(a,c.pk,d.pk,ready.pk,timezone.now(),'SYN-INFRA-RELEASE',e['completion'].pk,'Synthetic actual-event fixture only',rev())
        t=register_template(a,c.pk,'Delivery artifact',{'document_type':'project_artifact','required_fields':['executive_summary','status'],
            'internal_review_required':False,'audience_fields':{x:['executive_summary','scope','risks','status','next_steps'] for x in ['client','internal']}},e['policy_decision'].pk,rev())
        refs=[register_reference(a,c.pk,'delivery-recipient:'+x,'schema:psl/document-recipient/v1',{'audience':x,'user_id':a.pk},e['policy_decision'].pk).ref for x in ['client','internal']]
        activate('D11.recipient_grant_refs',refs)
        fixture=json.loads((Path(settings.BASE_DIR)/'fixtures/delivery.json').read_text())
        for component,value in [('D11.hypercare_criteria_ref',fixture['hypercare_criteria']),('D11.template_storage_retention_rules',
                {'template_ids':[t.pk],'repository':'internal-versioned','retention_days':30,'closure_inventory':fixture['closure_inventory']})]:
            cfg=draft_standard_policy(a,c.pk,component,value,e['policy_decision'].pk,timezone.now());transition(a,cfg.pk,'validated');transition(a,cfg.pk,'active')
        def publish(v):
            if v.audience=='client':request_review(a,c.pk,v.pk,rev());review_version(a,c.pk,v.pk,'approve','Synthetic exact outward review',rev())
            reserve_publication(a,c.pk,v.pk,rev())
            if not run_publication_once():raise CommandError('Publication worker found no reservation')
            receipt=PublicationReceipt.objects.filter(publication__version=v).first()
            if not receipt:raise CommandError('Synthetic delivery held; transaction rolled back for investigation')
            return receipt
        data={k:evidence(kind).pk for k,kind in [('checklist','deployment_checklist'),('incident_reporting','incident_reporting'),('rollback','rollback_plan')]}
        receipt=publish(draft_delivery_document(a,c.pk,d.pk,'go_live',t.pk,data,rev()))
        pm=evidence('signature','Synthetic exact PM go-live signature');client=evidence('signature','Synthetic exact Client go-live signature')
        accept_go_live(a,c.pk,d.pk,receipt.pk,pm.pk,client.pk,'Synthetic two-signature attestation',rev())
        for owner,metrics in [('engineering',{'errors':{'value':0,'unit':'count'}}),('infrastructure',{'availability':{'value':100,'unit':'percent'}})]:
            source('hypercare_'+owner,{'observed_at':timezone.now().isoformat(),'confirmed':True,'metrics':metrics})
        inventory={k:evidence(k) for k in fixture['closure_inventory']['required_kinds']};source('technical_finalization',src=inventory['technical_document'])
        archive_artifacts(a,c.pk,d.pk,{k:v.pk for k,v in inventory.items()},e['requirements'].pk,'Synthetic immutable artifact index',rev())
        data={k:evidence(k).pk for k in ['support_document','escalation_document']}
        receipt=publish(draft_delivery_document(a,c.pk,d.pk,'handover',t.pk,data,rev()))
        acknowledge_handover(a,c.pk,d.pk,receipt.pk,'received',e['requirements'].pk,'Synthetic Support/Operations actual local receipt',rev())
        m=complete_milestone(a,c.pk,'Synthetic final delivery',e['completion'].pk,rev())
        if not run_once():raise CommandError('No Finance handoff work found')
        confirm_finance(a,c.pk,d.pk,[m.pk],True,e['completion'].pk,'Synthetic explicit notification inventory coverage',rev())
        meeting=record_meeting(a,c.pk,'SYN-DELIVERY-RETRO','retrospective',timezone.now(),'Delivery lessons','Synthetic performance and risk retrospective',[a.pk],[],e['requirements'].pk,rev())
        report=evidence('closure_report','Synthetic PM performance summary, risks/resolutions and closure evidence. No debt waiver.')
        self.stdout.write(json.dumps({'case':str(c.pk),'dossier':d.pk,'template':t.pk,'evaluation_evidence':e['requirements'].pk,
            'retrospective':meeting.pk,'closure_report':report.pk,'owner_evidence':e['policy_decision'].pk,
            'next':'Use browser to evaluate hypercare, prepare closure report and record Head of PMO decision/closure. No remote effect occurred.'}))

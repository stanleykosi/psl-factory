from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from datetime import timedelta
from apps.core.models import Case
from apps.core.services import add_evidence
from apps.identity.models import Grant
from apps.policy.registry import components
from apps.policy.services import register_reference, save_draft, transition, resolve
from apps.documents.controlled import register_template, request_review, review_version, reserve_publication
from apps.documents.models import Template
from apps.pmo.gates import register_candidate, record_gate, verify_gate, draft_gate_packet
from apps.agents.documents import draft_document, check_document, check_candidate
from .seed_demo import ACTIONS

class Command(BaseCommand):
    help='Add a synthetic candidate → reviewed packet → pending internal publication demo. No operational values/effects.'
    def add_arguments(self,parser):parser.add_argument('--username',default='studio-demo')
    @transaction.atomic
    def handle(self,*args,**options):
        actor=get_user_model().objects.get(username=options['username'])
        case=Case.objects.get(tenant='synthetic-demo',synthetic=True,kind='project',grant__user=actor,grant__action='case.read')
        if Template.objects.filter(case=case,name='Synthetic controlled status').exists():
            raise CommandError('Document demo already exists; its immutable history is preserved')
        for action in ACTIONS:Grant.objects.get_or_create(user=actor,case=case,action=action)
        owner=add_evidence(actor,case.pk,'policy_decision','Explicit synthetic template/recipient configuration fixture. No real business policy.','synthetic:document-owner')
        def revision():case.refresh_from_db();return case.revision
        def activate(component,value):
            config=save_draft(actor,case.pk,{'slot_id':components()[component]['parent_decision_id'],
                'component_id':component,'component_schema_ref':components()[component]['schema_ref'],'schema_version':'1',
                'subject_scope':{'kind':'project','ref':str(case.pk)},'policy_revision':1,'lifecycle':'draft',
                'effective_from':(timezone.now()-timedelta(minutes=1)).isoformat(),'effective_until':None,
                'evidence_refs':[f'evidence:{owner.pk}'],'human_decision_ref':f'evidence:{owner.pk}',
                'implementation_id':'psl.reference-validation','implementation_version':'1',
                'reviewed_implementation_ref':'code:apps/policy/services.py#reference-validation-v1','fixture_scope':'synthetic_test','value':value})
            transition(actor,config.pk,'validated');transition(actor,config.pk,'active')
        if resolve('D05.role_principal_assignments',case).status!='ACTIVE':
            refs=[]
            for index,role in enumerate(['PM','Head of PMO','CEO','PMO Lead']):
                ref=f'document-demo:role:{index}'
                register_reference(actor,case.pk,ref,'schema:psl/role-assignment/v1',{'role':role,'user_id':actor.pk},owner.pk);refs.append(ref)
            activate('D05.role_principal_assignments',refs)
        definition={'document_type':'status_report','required_fields':['executive_summary','status'],
            'audience_fields':{'client':['executive_summary','status','next_steps'],'internal':['executive_summary','status','internal_notes']}}
        template=register_template(actor,case.pk,'Synthetic controlled status',definition,owner.pk,revision())
        r=register_reference(actor,case.pk,'document-demo:recipient','schema:psl/document-recipient/v1',{'audience':'client','user_id':actor.pk},owner.pk)
        activate('D11.recipient_grant_refs',[r.ref])
        r=register_reference(actor,case.pk,'document-demo:storage','schema:psl/document-storage/v1',
            {'template_ids':[template.pk],'repository':'internal-versioned','retention_days':30},owner.pk)
        activate('D11.template_storage_retention_rules',{'artifact_ref':r.ref,'artifact_version':r.version,'sha256':r.sha256,'schema_ref':r.schema_ref})
        requirements=case.evidence.filter(kind='requirements').order_by('-version').first()
        source=add_evidence(actor,case.pk,'gate_source','Synthetic QA source reference for the candidate. Not a real approval.','synthetic:qa')
        candidate=register_candidate(actor,case.pk,'synthetic-build-documents-v1',requirements.pk,revision())
        record=record_gate(actor,case.pk,candidate.pk,'qa_exit','synthetic:qa:receipt-1',source.pk,revision())
        verify_gate(actor,case.pk,record.pk,revision())
        check_candidate(actor,case.pk,candidate.pk)
        packet=draft_gate_packet(actor,case.pk,candidate.pk,template.pk,'client',revision())
        check_document(actor,case.pk,packet.pk)
        request_review(actor,case.pk,packet.pk,revision())
        review_version(actor,case.pk,packet.pk,'approve','Synthetic PMO Lead fixture checked the exact client projection',revision())
        reserve_publication(actor,case.pk,packet.pk,revision())
        draft_document(actor,case.pk,template.pk,'Synthetic agent-prepared report','client',[source.pk],revision())
        self.stdout.write('Synthetic controlled document and candidate packet prepared. Run work_publications to deliver its internal receipt.')

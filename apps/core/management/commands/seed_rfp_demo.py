import json
from datetime import timedelta
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand,CommandError
from django.db import transaction
from django.utils import timezone
from apps.core.models import Case
from apps.core.services import add_evidence
from apps.identity.models import Grant
from apps.policy.services import register_reference,transition
from apps.policy.change_drafts import draft_standard_policy
from apps.policy.registry import components
from apps.policy.services import save_draft
from apps.pmo import rfp,rfp_documents,commercial
from apps.documents.controlled import register_template,request_review,review_version,reserve_publication
from apps.documents.delivery import run_publication_once
from .seed_demo import ACTIONS

TITLE='Synthetic RFP response studio'
DEFINITION={'document_type':'rfp_response','required_fields':['executive_summary','scope','requirements_mapping','commercial_terms'],
    'audience_fields':{'client':['executive_summary','scope','requirements_mapping','commercial_terms']}}

class Command(BaseCommand):
    help='Create isolated synthetic won/lost RFP examples through local inbox receipts; no external submission'
    def add_arguments(self,parser):parser.add_argument('--username',default='studio-demo')
    @transaction.atomic
    def handle(self,*args,**options):
        a=get_user_model().objects.filter(username=options['username'],is_active=True).first()
        if not a or Case.objects.filter(tenant='synthetic-demo',title__startswith=TITLE).exists():raise CommandError('Existing demo actor and fresh RFP fixtures required; refusing overwrite')
        fixture=json.loads((settings.BASE_DIR/'fixtures/rfp.json').read_text())
        output=[]
        for result in ['won','lost']:
            c=Case.objects.create(tenant='synthetic-demo',title=TITLE+' — '+result,kind='project',synthetic=True)
            for action in ACTIONS:Grant.objects.create(case=c,user=a,action=action)
            def revision():c.refresh_from_db();return c.revision
            e={k:add_evidence(a,c.pk,k,'Synthetic '+k+' for '+result+' RFP; explicit illustrative input only.','synthetic:rfp-demo') for k in
                ['requirements','engineering_estimate','security_estimate','qa_estimate','product_input','plan','costing','rfp_commercial_terms','rfp_intake','rfp_response','rfp_outcome','rfp_lessons','policy_decision']}
            owner=e['policy_decision']
            def activate(component,value):
                config=save_draft(a,c.pk,{'slot_id':component.split('.')[0],'component_id':component,'component_schema_ref':components()[component]['schema_ref'],
                    'schema_version':'1','subject_scope':{'kind':'project','ref':str(c.pk)},'policy_revision':1,'lifecycle':'draft',
                    'effective_from':(timezone.now()-timedelta(days=1)).isoformat(),'effective_until':None,'evidence_refs':[f'evidence:{owner.pk}'],'human_decision_ref':f'evidence:{owner.pk}',
                    'implementation_id':'psl.reference-validation','implementation_version':'1','reviewed_implementation_ref':'code:apps/policy/services.py#reference-validation-v1','value':value,'fixture_scope':'synthetic_test'})
                transition(a,config.pk,'validated');transition(a,config.pk,'active')
            def draft_policy(component,value):
                config=draft_standard_policy(a,c.pk,component,value,owner.pk,timezone.now()-timedelta(days=1));transition(a,config.pk,'validated');transition(a,config.pk,'active')
            roles=[]
            for role in ['PM','Head of PMO','CEO','PMO Lead','Engineering Lead','Client']:
                roles.append(register_reference(a,c.pk,'rfp:role:'+role,'schema:psl/role-assignment/v1',{'role':role,'user_id':a.pk},owner.pk).ref)
            activate('D05.role_principal_assignments',roles);draft_policy('D05.decision_action_matrix',fixture['decision_matrix'])
            t=register_template(a,c.pk,'Synthetic RFP client response',DEFINITION,owner.pk,revision())
            recipient=register_reference(a,c.pk,'rfp:client-recipient','schema:psl/document-recipient/v1',{'audience':'client','user_id':a.pk},owner.pk)
            activate('D11.recipient_grant_refs',[recipient.ref])
            draft_policy('D11.template_storage_retention_rules',{'template_ids':[t.pk],'repository':'internal-versioned','retention_days':30})
            route=dict(fixture['route_interface'],recipient_ids=[a.pk]);draft_policy('D11.adapter_configuration_refs',[route])
            rfp.intake(a,c.pk,'DEMO-RFP-'+result.upper(),e['rfp_intake'].pk,timezone.now()-timedelta(hours=1),'not_stated',None,None,'Synthetic source explicitly states no deadline',revision())
            rfp.assign(a,c.pk,a,'CEO',owner.pk,'Synthetic accountable PM appointment',revision())
            for team,kind in rfp.TEAMS.items():rfp.contribute(a,c.pk,team,e[kind].pk,revision())
            matrix=[dict(fixture['mapping_interface'][0],evidence_id=e['requirements'].pk,response='Synthetic cited requirement coverage',disposition='addressed')]
            v=rfp.prepare_response(a,c.pk,e['rfp_response'].pk,matrix,{k:e[k].pk for k in ['requirements','plan','costing']},revision(),public_terms_id=e['rfp_commercial_terms'].pk)
            for role in reversed(rfp.REVIEW_ROLES):rfp.review(a,c.pk,v.pk,role,'approve',owner.pk,'Synthetic exact-response review',revision())
            for role in ['PM','Head of PMO','CEO']:commercial.decide_proposal(a,c.pk,v.commercial_id,role,'approve','Synthetic ordered costing review',revision())
            d=rfp_documents.draft(a,c.pk,v.pk,t.pk,route['key'],revision());request_review(a,c.pk,d.pk,revision());review_version(a,c.pk,d.pk,'approve','Synthetic outward document review',revision());reserve_publication(a,c.pk,d.pk,revision())
            if not run_publication_once():raise CommandError('No local publication worker effect')
            s=rfp_documents.capture_submission(a,c.pk,d.pk,revision())
            o=rfp.outcome(a,c.pk,s.pk,result,timezone.now(),'Client',e['rfp_outcome'].pk,'Synthetic relationship-owner '+result+' evidence',revision())
            if result=='lost':rfp.dispose(a,c.pk,o.pk,e['rfp_lessons'].pk,revision())
            output.append({'case':str(c.pk),'result':result,'response':v.pk,'version':d.pk,'submission':s.pk,'outcome':o.pk})
        self.stdout.write(json.dumps(output))

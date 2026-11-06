from datetime import timedelta
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from apps.core.models import Case
from apps.core.services import add_evidence
from apps.identity.models import Grant
from apps.policy.registry import components
from apps.policy.services import save_draft, transition, register_reference
from apps.documents.controlled import register_template, request_review, review_version, reserve_publication
from apps.pmo.services import prepare_baseline, decide, sign_baseline
from apps.pmo.commercial import propose, decide_proposal, draft_submission
from apps.pmo.changes import log_change, assess_change, decide_change, authorize_change, CONTRIBUTORS
from apps.agents.commercial import investigate_proposal
from .seed_demo import ACTIONS

TITLE='Synthetic commercial change engagement'

class Command(BaseCommand):
    help='Prepare an isolated synthetic signed-scope change and reviewed outward proposal; never operational policy.'
    def add_arguments(self,parser):parser.add_argument('--username',default='studio-demo')
    @transaction.atomic
    def handle(self,*args,**options):
        actor=get_user_model().objects.get(username=options['username'])
        if Case.objects.filter(tenant='synthetic-demo',title=TITLE).exists():
            raise CommandError('Synthetic commercial demo already exists; refusing to overwrite history')
        case=Case.objects.create(tenant='synthetic-demo',title=TITLE,kind='project',synthetic=True)
        for action in ACTIONS:Grant.objects.create(case=case,user=actor,action=action)
        def revision():case.refresh_from_db();return case.revision
        e={k:add_evidence(actor,case.pk,k,'Synthetic '+k+' source; not a real business decision.','synthetic:commercial-owner')
            for k in ['requirements','engineering_estimate','security_estimate','plan','costing','sow','signature','policy_decision']}
        owner=e['policy_decision']
        def activate(component,value):
            config=save_draft(actor,case.pk,{'slot_id':components()[component]['parent_decision_id'],'component_id':component,
                'component_schema_ref':components()[component]['schema_ref'],'schema_version':'1','subject_scope':{'kind':'project','ref':str(case.pk)},
                'policy_revision':1,'lifecycle':'draft','effective_from':(timezone.now()-timedelta(minutes=1)).isoformat(),'effective_until':None,
                'evidence_refs':[f'evidence:{owner.pk}'],'human_decision_ref':f'evidence:{owner.pk}',
                'implementation_id':'psl.reference-validation','implementation_version':'1','reviewed_implementation_ref':'code:apps/policy/services.py#reference-validation-v1',
                'fixture_scope':'synthetic_test','value':value})
            transition(actor,config.pk,'validated');transition(actor,config.pk,'active')
        refs=[]
        for role in ['PM','Head of PMO','CEO','PMO Lead','Product','Engineering','Client','Engineering Lead','Security Manager']:
            r=register_reference(actor,case.pk,'synthetic:role:'+role,'schema:psl/role-assignment/v1',{'role':role,'user_id':actor.pk},owner.pk);refs.append(r.ref)
        activate('D05.role_principal_assignments',refs)
        prepare_baseline(actor,case.pk,e['plan'].pk,e['costing'].pk,e['sow'].pk,revision())
        for role in ['PM','Head of PMO','CEO','PMO Lead']:decide(actor,case.pk,role,revision())
        sign_baseline(actor,case.pk,e['signature'].pk,revision())
        source=add_evidence(actor,case.pk,'change_request','Synthetic client-requested delivery extension. No real scope is changed.','synthetic:client-change')
        cv=log_change(actor,case.pk,'SYN-CR-001','Normal','Synthetic delivery','Proposed delivery extension','Synthetic fixture evidence',source.pk,revision())
        for contributor in CONTRIBUTORS:assess_change(actor,case.pk,cv.pk,contributor,True,True,True,source.pk,'Synthetic owner impact input',revision())
        for role in ['Product','Engineering','Client','Engineering Lead','Security Manager']:
            decide_change(actor,case.pk,cv.pk,role,'approve',source.pk,'Synthetic role fixture decision',revision())
        for k in ['plan','costing','sow','signature']:
            e[k]=add_evidence(actor,case.pk,k,'Synthetic revised '+k+'. Not operational policy or a genuine signature.','synthetic:revised')
        v=propose(actor,case.pk,{k:e[k].pk for k in ['requirements','engineering_estimate','security_estimate','plan','costing','sow']},source.pk,'Synthetic controlled scope revision',revision())
        for role in ['PM','Head of PMO','CEO','PMO Lead']:decide_proposal(actor,case.pk,v.pk,role,'approve','Synthetic exact-source decision',revision())
        authorize_change(actor,case.pk,cv.pk,v.pk,revision())
        template=register_template(actor,case.pk,'Synthetic revised SOW',{'document_type':'sow','required_fields':['executive_summary','scope','timeline'],
            'audience_fields':{'client':['executive_summary','scope','timeline']}},owner.pk,revision())
        status=register_template(actor,case.pk,'Synthetic change notice',{'document_type':'project_artifact','required_fields':['executive_summary','status'],
            'audience_fields':{'client':['executive_summary','scope','status','timeline','next_steps']}},owner.pk,revision())
        r=register_reference(actor,case.pk,'synthetic:client-recipient','schema:psl/document-recipient/v1',{'audience':'client','user_id':actor.pk},owner.pk)
        activate('D11.recipient_grant_refs',[r.ref])
        r=register_reference(actor,case.pk,'synthetic:storage','schema:psl/document-storage/v1',{'template_ids':[template.pk,status.pk],'repository':'internal-versioned','retention_days':30},owner.pk)
        activate('D11.template_storage_retention_rules',{'artifact_ref':r.ref,'artifact_version':r.version,'sha256':r.sha256,'schema_ref':r.schema_ref})
        doc=draft_submission(actor,case.pk,v.pk,template.pk,revision())
        request_review(actor,case.pk,doc.pk,revision())
        review_version(actor,case.pk,doc.pk,'approve','Synthetic outward review',revision())
        reserve_publication(actor,case.pk,doc.pk,revision())
        investigate_proposal(actor,case.pk,v.pk,revision())
        self.stdout.write(f'Synthetic commercial case {case.pk}; proposal {v.pk}. Run work_publications, then capture its matching synthetic signature in the commercial workbench.')

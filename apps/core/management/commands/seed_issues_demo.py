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
from apps.pmo.issues import log_issue, update_issue, close_issue_log
from apps.agents.issues import investigate_issues
from .seed_demo import ACTIONS

class Command(BaseCommand):
    help='Create a separate synthetic authoritative-issue fixture; no operational severity/role policy.'
    def add_arguments(self,parser):parser.add_argument('--username',default='studio-demo')
    @transaction.atomic
    def handle(self,*args,**options):
        actor=get_user_model().objects.get(username=options['username'])
        title='Synthetic issue engagement'
        if Case.objects.filter(tenant='synthetic-demo',title=title).exists():raise CommandError('Issue demo exists; no overwrite')
        case=Case.objects.create(tenant='synthetic-demo',title=title,kind='project',synthetic=True)
        for action in ACTIONS:Grant.objects.create(case=case,user=actor,action=action)
        def revision():case.refresh_from_db();return case.revision
        owner=add_evidence(actor,case.pk,'policy_decision','Synthetic PM and QA assignments for fixture only','synthetic:owner')
        refs=[]
        for role in ['PM','QA']:
            r=register_reference(actor,case.pk,'synthetic:issue-role:'+role,'schema:psl/role-assignment/v1',{'role':role,'user_id':actor.pk},owner.pk);refs.append(r.ref)
        component='D05.role_principal_assignments'
        cfg=save_draft(actor,case.pk,{'slot_id':'D05','component_id':component,'component_schema_ref':components()[component]['schema_ref'],
            'schema_version':'1','subject_scope':{'kind':'project','ref':str(case.pk)},'policy_revision':1,'lifecycle':'draft',
            'effective_from':(timezone.now()-timedelta(minutes=1)).isoformat(),'effective_until':None,
            'evidence_refs':[f'evidence:{owner.pk}'],'human_decision_ref':f'evidence:{owner.pk}',
            'implementation_id':'psl.reference-validation','implementation_version':'1','reviewed_implementation_ref':'code:apps/policy/services.py#reference-validation-v1',
            'fixture_scope':'synthetic_test','value':refs})
        transition(actor,cfg.pk,'validated');transition(actor,cfg.pk,'active')
        incident=add_evidence(actor,case.pk,'incident','Synthetic external Engineering incident; PMO has no incident lifecycle authority','synthetic:Engineering')
        state=log_issue(actor,case.pk,'SYN-ISSUE-001','Synthetic critical delivery dependency','Production',actor.pk,'Investigate root cause',incident.pk,
            'Synthetic PM source capture',revision(),'Critical',[{'kind':'incident','source_ref':'synthetic:ENG-INC-1','evidence_id':incident.pk}])
        state=update_issue(actor,case.pk,state.issue_id,state.pk,'acknowledge',incident.pk,'Synthetic owner acknowledges',revision())
        state=update_issue(actor,case.pk,state.issue_id,state.pk,'start',incident.pk,'Synthetic owner investigates',revision())
        investigate_issues(actor,case.pk,revision())
        self.stdout.write(f'Synthetic issue case {case.pk}; owned Critical issue remains In Progress with root-cause gap visible. No SLA or escalation assumed.')

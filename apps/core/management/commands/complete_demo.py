from datetime import timedelta
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from apps.core.models import Case
from apps.core.services import add_evidence
from apps.policy.models import Configuration, RegisteredReference
from apps.policy.registry import components
from apps.policy.services import register_reference, save_draft, transition
from apps.pmo.models import Baseline, Milestone
from apps.pmo.services import prepare_baseline, decide, sign_baseline, complete_milestone
from apps.workflows.services import run_once
from apps.finance.models import Handoff, InvoicePreparation
from apps.finance.services import begin_invoice_preparation, capture_import
from apps.agents.services import extract_evidence

class Command(BaseCommand):
    help = 'Exercise real services in an existing synthetic-demo project only. No operational policy or effect.'
    def add_arguments(self,parser):
        parser.add_argument('--username',default='studio-demo')

    @transaction.atomic
    def handle(self,*args,**options):
        actor=get_user_model().objects.get(username=options['username'])
        case=Case.objects.get(tenant='synthetic-demo',synthetic=True,kind='project',grant__user=actor,grant__action='case.read')
        if Baseline.objects.filter(case=case,signed__isnull=False).exists():
            raise CommandError('Synthetic connected demo already completed; existing history is preserved')
        evidence={kind:case.evidence.filter(kind=kind).order_by('-version').get() for kind in
            ['requirements','engineering_estimate','security_estimate','plan','costing','sow','signature','completion','policy_decision']}
        refs=[]
        for index,role in enumerate(['PM','Head of PMO','CEO','PMO Lead']):
            ref=f'synthetic-role:{index}'
            register_reference(actor,case.pk,ref,'schema:psl/role-assignment/v1',{'role':role,'user_id':actor.pk},evidence['policy_decision'].pk)
            refs.append(ref)
        component='D05.role_principal_assignments'
        envelope={'slot_id':'D05','component_id':component,'component_schema_ref':components()[component]['schema_ref'],
            'subject_scope':{'kind':'project','ref':str(case.pk)},'schema_version':'1','policy_revision':1,'lifecycle':'draft',
            'effective_from':(timezone.now()-timedelta(minutes=1)).isoformat(),'effective_until':None,
            'evidence_refs':[f"evidence:{evidence['policy_decision'].pk}"],'human_decision_ref':f"evidence:{evidence['policy_decision'].pk}",
            'implementation_id':'psl.reference-validation','implementation_version':'1',
            'reviewed_implementation_ref':'code:apps/policy/services.py#reference-validation-v1','fixture_scope':'synthetic_test','value':refs}
        config=save_draft(actor,case.pk,envelope);transition(actor,config.pk,'validated');transition(actor,config.pk,'active')
        def revision():
            case.refresh_from_db();return case.revision
        prepare_baseline(actor,case.pk,evidence['plan'].pk,evidence['costing'].pk,evidence['sow'].pk,revision())
        for role in ['PM','Head of PMO','CEO','PMO Lead']:
            decide(actor,case.pk,role,revision())
        sign_baseline(actor,case.pk,evidence['signature'].pk,revision())
        complete_milestone(actor,case.pk,'Synthetic delivery accepted by PMO',evidence['completion'].pk,revision())
        # Dispatch belongs to a separate post-commit worker command, never inside this fixture transaction.
        extract_evidence(actor,case.pk,evidence['completion'].pk,'P34')
        source=add_evidence(actor,case.pk,'financial_input','account,amount,currency,period\n100,1234.56,NGN,2026-10\n200,,NGN,2026-10\n','synthetic:controlled-csv')
        capture_import(actor,case.pk,source.pk,revision())
        self.stdout.write('Synthetic connected demo prepared. Run work_outbox to deliver its Finance handoff.')

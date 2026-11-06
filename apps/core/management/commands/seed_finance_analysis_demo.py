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
from apps.policy.registry import components
from apps.policy.services import register_reference,save_draft,transition
from apps.policy.finance_drafts import draft_finance_policy
from apps.finance.services import capture_import,validate_import
from apps.finance import analysis
from apps.documents.controlled import register_template
from .seed_demo import ACTIONS

TITLE='Synthetic Finance mapping and BU reporting'

class Command(BaseCommand):
    help='Create an isolated synthetic Finance source/mapping/allocation/formula preview, ready for human output review; no ledger/payment or external effect'
    def add_arguments(self,parser):
        parser.add_argument('--username',default='studio-demo')
        parser.add_argument('--title',default=TITLE)
    @transaction.atomic
    def handle(self,*args,**options):
        actor=get_user_model().objects.filter(username=options['username'],is_active=True).first()
        if not actor or Case.objects.filter(tenant='synthetic-demo',title=options['title']).exists():raise CommandError('Requires existing demo actor and fresh Finance fixture; refuses overwrite')
        case=Case.objects.create(tenant='synthetic-demo',title=options['title'],kind='project',synthetic=True)
        for action in ACTIONS:Grant.objects.create(case=case,user=actor,action=action)
        def revision():case.refresh_from_db();return case.revision
        def evidence(kind,body):return add_evidence(actor,case.pk,kind,body,'synthetic:finance-demo')
        fixture=json.loads((settings.BASE_DIR/'fixtures/finance-analysis.json').read_text())
        owner=evidence('policy_decision','Synthetic illustrative Finance configuration only; no operational appointment or financial policy.')
        source_evidence=evidence('finance_source','Synthetic unchanged export with explicit reporting entity/accrual/extraction context and complete declared inventory')
        review_evidence=evidence('finance_review','Synthetic human source/rule review evidence; not operational sign-off')
        basis=evidence('finance_basis',json.dumps(fixture['basis'],sort_keys=True));csv=evidence('financial_input',fixture['csv'])
        def activate(component,value):
            config=save_draft(actor,case.pk,{'slot_id':component.split('.')[0],'component_id':component,'component_schema_ref':components()[component]['schema_ref'],
                'schema_version':'1','policy_revision':1,'lifecycle':'draft','subject_scope':{'kind':'project','ref':str(case.pk)},
                'effective_from':(timezone.now()-timedelta(days=1)).isoformat(),'effective_until':None,'evidence_refs':[f'evidence:{owner.pk}'],'human_decision_ref':f'evidence:{owner.pk}',
                'implementation_id':'psl.reference-validation','implementation_version':'1','reviewed_implementation_ref':'code:apps/policy/services.py#reference-validation-v1','value':value,'fixture_scope':'synthetic_test'})
            transition(actor,config.pk,'validated');transition(actor,config.pk,'active');return config
        def policy(component,value):
            config=draft_finance_policy(actor,case.pk,component,value,owner.pk,timezone.now()-timedelta(days=1));transition(actor,config.pk,'validated');transition(actor,config.pk,'active');return config
        role=register_reference(actor,case.pk,'finance-demo:principal','schema:psl/role-assignment/v1',{'role':'Finance','user_id':actor.pk},owner.pk)
        activate('D05.role_principal_assignments',[role.ref]);policy('D05.decision_action_matrix',fixture['authority'])
        configs={}
        values={'D06.source_schema_ref':{'columns':['account','amount','currency','period']},'D06.unit_sign_currency_period':fixture['conventions'],
            'D06.account_bu_maps':fixture['mapping'],'D10.report_category_effective_dates':fixture['catalogue'],'D07.allocation_pool_rules':fixture['pools'],
            'D07.rounding_residual_rule_id':fixture['rounding'],'D07.join_overlap_rule_id':fixture['join'],'D07.effective_membership_ref':dict(fixture['basis'],evidence_id=basis.pk),
            'D07.authorized_input_refs':[{'entity':'synthetic-company','period':'2026-10','provider':'HR','evidence_id':basis.pk,'purpose':'allocation_basis'}],
            'D10.audience_projection_rules':fixture['projection']}
        formulas=[]
        for rule in fixture['formulas']:
            oracle=evidence('finance_oracle',json.dumps(rule['oracles'],sort_keys=True));formulas.append(dict(rule,oracle_evidence_id=oracle.pk))
        values['D06.rule_oracle_refs']=formulas
        for component,value in values.items():configs[component]=policy(component,value)
        batch=capture_import(actor,case.pk,csv.pk,revision());validate_import(actor,case.pk,batch.pk,revision())
        source=analysis.capture_source(actor,case.pk,batch.pk,'synthetic-company','accrual',timezone.now()-timedelta(hours=1),'complete',fixture['source_control_total'],source_evidence.pk,revision())
        analysis.review(actor,case.pk,'source',source.pk,'Finance','approve',review_evidence.pk,'Synthetic exact extraction/source context accepted',revision())
        for component,purpose in analysis.PURPOSE.items():analysis.review(actor,case.pk,purpose,configs[component].pk,'Finance','approve',review_evidence.pk,'Synthetic exact mapping/rule review',revision())
        mapping=analysis.map_source(actor,case.pk,source.pk,[],revision());allocation=analysis.allocate(actor,case.pk,mapping.pk,['revenue','direct_cost','staff_cost','opex'],revision());output=analysis.calculate(actor,case.pk,allocation.pk,revision())
        definition={'document_type':'finance_report','required_fields':['executive_summary','financial_metrics','bu_totals'],'audience_fields':{'internal':['executive_summary','financial_metrics','bu_totals']},'internal_review_required':False}
        template=register_template(actor,case.pk,'Synthetic Finance aggregate report',definition,owner.pk,revision())
        storage=register_reference(actor,case.pk,'finance-demo:storage','schema:psl/document-storage/v1',{'template_ids':[template.pk],'repository':'internal-versioned','retention_days':30},owner.pk)
        activate('D11.template_storage_retention_rules',{'artifact_ref':storage.ref,'artifact_version':1,'schema_ref':storage.schema_ref,'sha256':storage.sha256})
        recipient=register_reference(actor,case.pk,'finance-demo:recipient','schema:psl/document-recipient/v1',{'audience':'internal','user_id':actor.pk},owner.pk);activate('D11.recipient_grant_refs',[recipient.ref])
        self.stdout.write(json.dumps({'case':str(case.pk),'source':source.pk,'mapping':mapping.pk,'allocation':allocation.pk,'formula':output.pk,'status':output.result['status'],
            'template':template.pk,'review_evidence':review_evidence.pk,'output_review':'not_recorded','publication':'not_reserved','ledger_posted':False}))

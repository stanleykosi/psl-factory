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
from apps.finance import billing,invoices,cash
from .seed_demo import ACTIONS

TITLE='Synthetic Finance invoice and cash settlement'
class Command(BaseCommand):
    help='Create isolated synthetic invoice draft and verified assigned prepayment, ready for UI review/issuance/allocation; no external effect'
    def add_arguments(self,parser):
        parser.add_argument('--username',default='studio-demo');parser.add_argument('--title',default=TITLE)
    @transaction.atomic
    def handle(self,*args,**options):
        actor=get_user_model().objects.filter(username=options['username'],is_active=True).first()
        if not actor or Case.objects.filter(tenant='synthetic-demo',title=options['title']).exists():raise CommandError('Requires existing demo actor and fresh synthetic case; refuses overwrite')
        case=Case.objects.create(tenant='synthetic-demo',title=options['title'],kind='service',synthetic=True)
        for action in ACTIONS:Grant.objects.create(case=case,user=actor,action=action)
        def rev():case.refresh_from_db();return case.revision
        def e(kind,body):return add_evidence(actor,case.pk,kind,body,'synthetic:settlement-demo')
        f=json.loads((settings.BASE_DIR/'fixtures/finance-settlement.json').read_text(encoding='utf-8'));b=json.loads((settings.BASE_DIR/'fixtures/finance-billing.json').read_text(encoding='utf-8'))
        owner=e('policy_decision','Synthetic invoice/cash authority, source, allocation and full-only reversal demonstration; no actual financial authority or PSL policy')
        def policy(key,value):
            c=draft_finance_policy(actor,case.pk,key,value,owner.pk,timezone.now()-timedelta(days=1));transition(actor,c.pk,'validated');transition(actor,c.pk,'active');return c
        r=register_reference(actor,case.pk,'synthetic-finance-human','schema:psl/role-assignment/v1',{'role':'Finance','user_id':actor.pk},owner.pk)
        key='D05.role_principal_assignments'
        config=save_draft(actor,case.pk,{'slot_id':'D05','component_id':key,'component_schema_ref':components()[key]['schema_ref'],'schema_version':'1','policy_revision':1,'lifecycle':'draft',
            'subject_scope':{'kind':'service','ref':str(case.pk)},'effective_from':(timezone.now()-timedelta(days=1)).isoformat(),'effective_until':None,
            'evidence_refs':[f'evidence:{owner.pk}'],'human_decision_ref':f'evidence:{owner.pk}','implementation_id':'psl.reference-validation','implementation_version':'1',
            'reviewed_implementation_ref':'code:apps/policy/services.py#reference-validation-v1','fixture_scope':'synthetic_test','value':[r.ref]})
        transition(actor,config.pk,'validated');transition(actor,config.pk,'active')
        f['adapter']['recipient_id']=actor.pk
        for key,value in [('D05.decision_action_matrix',f['review']),('D08.adapter_contract_ref',f['adapter']),('D08.duplicate_correction_rules',f['identity']),
            ('D14.receipt_verification_source_ref',f['source']),('D14.recorder_authority_ref',f['recorder']),('D14.allocation_rule_ref',f['matching']),
            ('D14.adjustment_correction_rule_refs',f['reversals']),('D14.legal_document_requirements',f['legal'])]:policy(key,value)
        cov=billing.register_coverage(actor,case.pk,**b['coverage'],evidence_id=e('billing_coverage','Synthetic service contract coverage; partial only').pk,expected=rev())
        oracle=e('billing_oracle',json.dumps(b['arithmetic']['oracles']))
        policy('D08.effective_price_rule_refs',[dict(b['rule'],coverage_id=cov.pk)]);policy('D08.tax_tier_rounding_rules',dict(b['arithmetic'],oracle_evidence_id=oracle.pk))
        u=billing.capture_usage(actor,case.pk,cov.pk,e('billing_usage',b['csv']).pk,rev(),{'provider_ref':'synthetic-data','extracted_at':timezone.now().isoformat(),'completeness':'partial'})
        prep=billing.prepare(actor,case.pk,cov.pk,'usage',u.pk,None,rev())
        doc=invoices.draft(actor,case.pk,prep.pk,'SYNTHETIC-INV-001',timezone.localdate()-timedelta(days=1),rev())
        review=e('invoice_review','Synthetic exact invoice review evidence for browser human decision')
        proof={'source':'synthetic-bank','transaction_ref':'SYNTHETIC-CASH-'+case.pk.hex[:12],'customer':cov.customer,'amount':'50.00','currency':'NGN','amount_basis':'gross_including_tax','received_at':(timezone.now()-timedelta(hours=1)).isoformat()}
        reported=cash.report(actor,case.pk,e('cash_report',json.dumps(proof)).pk,rev());lot=cash.verify(actor,case.pk,reported.pk,'Finance',e('cash_verification',json.dumps(proof)).pk,rev())
        correction=e('cash_correction','Synthetic written assignment/reversal evidence')
        cash.assign(actor,case.pk,reported.pk,cov.pk,'Finance',correction.pk,'Synthetic explicit contract assignment before invoice issuance',rev())
        allocation=e('cash_allocation','Synthetic human selected allocation evidence')
        self.stdout.write(json.dumps({'case':str(case.pk),'coverage':cov.pk,'preparation':prep.pk,'invoice':doc.pk,'review_evidence':review.pk,'receipt':reported.pk,'lot':lot.pk,'allocation_evidence':allocation.pk,'invoice_issued':False,'allocated':False}))

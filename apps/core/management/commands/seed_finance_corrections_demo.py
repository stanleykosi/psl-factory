import io,json
from datetime import timedelta
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from apps.core.models import Case
from apps.core.services import add_evidence
from apps.finance.models import Invoice,InvoiceIssue,CashVerification
from apps.finance import invoices,invoice_delivery,cash,corrections,cash_successors
from apps.policy.finance_drafts import draft_finance_policy
from apps.policy.services import active_component,reference_values,transition

class Command(BaseCommand):
    help='Fresh synthetic correction case through real services; pending notes/successor await UI human review and acceptance'
    def add_arguments(self,parser):parser.add_argument('--username',default='studio-demo')
    @transaction.atomic
    def handle(self,*args,**options):
        out=io.StringIO();call_command('seed_finance_settlement_demo',username=options['username'],title='Synthetic Finance invoice and cash corrections',stdout=out)
        values=json.loads(out.getvalue());case=Case.objects.get(pk=values['case']);actor=get_user_model().objects.get(username=options['username'])
        def rev():case.refresh_from_db();return case.revision
        def e(kind,body):return add_evidence(actor,case.pk,kind,body,'synthetic:financial-corrections-demo')
        doc=Invoice.objects.get(pk=values['invoice']);lot=CashVerification.objects.get(pk=values['lot'])
        invoices.review(actor,case.pk,doc.pk,'Finance','approve',values['review_evidence'],'Synthetic original invoice reviewed',rev())
        invoices.reserve(actor,case.pk,doc.pk,'issue','Finance',rev());invoice_delivery.run_once();issue=InvoiceIssue.objects.get(invoice=doc)
        cash.allocate(actor,case.pk,lot.pk,issue.pk,'20','SYNTHETIC-ORIGINAL-MATCH','Finance',values['allocation_evidence'],rev())
        legal=e('cash_correction','Synthetic full prior cash reversal and corrected source-transaction evidence')
        cash.reverse(actor,case.pk,'lot',lot.pk,'Finance',legal.pk,'Synthetic full predecessor reversal before corrected amount',rev())
        owner=e('policy_decision','Synthetic finite correction, legal, review and successor rules; not actual PSL policy')
        def policy(key,content):
            c=draft_finance_policy(actor,case.pk,key,content,owner.pk,timezone.now()-timedelta(days=1));transition(actor,c.pk,'validated');transition(actor,c.pk,'active')
        f=json.loads((settings.BASE_DIR/'fixtures/finance-corrections.json').read_text(encoding='utf-8'))
        matrix=reference_values(active_component('D05.decision_action_matrix',case))[0]
        matrix['finance']+=[{'purpose':p,'role':'Finance','actions':['approve','return','reject'],'allow_preparer_review':True} for p in ['invoice_correction','cash_successor']]
        policy('D05.decision_action_matrix',matrix)
        identity=reference_values(active_component('D08.duplicate_correction_rules',case))[0];identity['correction']=f['method'];policy('D08.duplicate_correction_rules',identity)
        for key,field in [('D14.adjustment_correction_rule_refs','rules'),('D14.legal_document_requirements','legal')]:policy(key,reference_values(active_component(key,case))+f[field])
        note=e('invoice_credit_note',json.dumps({'document_ref':'SYNTHETIC-CREDIT-001','invoice_reference':doc.reference,'kind':'credit','amount':'5.00','currency':doc.currency,'amount_basis':doc.amount_basis}))
        correction=corrections.capture(actor,case.pk,issue.pk,note.pk,legal.pk,'Synthetic correction of existing invoice amount',rev())
        value=dict(cash.lot_payload(lot),amount='40.00');reported=e('cash_report',json.dumps(value));verified=e('cash_verification',json.dumps(value))
        successor=cash_successors.capture(actor,case.pk,lot.pk,reported.pk,verified.pk,legal.pk,'Synthetic corrected gross amount after full predecessor reversal',rev())
        review=e('financial_correction_review','Synthetic exact human review evidence for new note and corrected cash')
        self.stdout.write(json.dumps({'case':str(case.pk),'invoice':doc.pk,'issue':issue.pk,'parent_lot':lot.pk,'correction':correction.pk,'successor':successor.pk,'review_evidence':review.pk,'allocation_evidence':values['allocation_evidence'],'correction_applied':False,'successor_accepted':False}))

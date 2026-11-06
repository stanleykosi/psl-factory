from django import forms
from apps.policy.settlement_validators import SUPPORTED
from apps.policy.document_validators import ROLES
from .forms import CommandForm
from .models import BillingCoverage,BillingPreparation,Invoice,InvoiceIssue,InvoiceJob,CashReceipt,CashVerification,CashAllocation,ReceivableSnapshot

def commands(case,data=None):
    def select(model,optional=False):
        lookup='invoice__case' if model in [InvoiceIssue,InvoiceJob] else 'receipt__case' if model is CashVerification else 'lot__receipt__case' if model is CashAllocation else 'case'
        return forms.ModelChoiceField(model.objects.filter(**{lookup:case}),required=not optional)
    def ev(kind):return forms.ModelChoiceField(case.evidence.filter(kind=kind))
    def choice(values):return forms.ChoiceField(choices=[(x,x) for x in values])
    def text():return forms.CharField(max_length=4000,widget=forms.Textarea(attrs={'rows':2}))
    defs={
     'draft':('Generate invoice draft',{'preparation':select(BillingPreparation),'reference':forms.CharField(max_length=100),'due_date':forms.DateField(required=False)}),
     'review':('Review exact invoice',{'invoice':select(Invoice),'role':choice(ROLES),'verdict':choice(['approve','return','reject']),
        'delegated':forms.BooleanField(required=False,label='Use configured delegated invoice authority',help_text='Requires current approval for this project, decision, currency, amount and authority window.'),'evidence':ev('invoice_review'),'reason':text()}),
     'reserve':('Reserve issuance or delivery',{'invoice':select(Invoice),'kind':choice(['issue','deliver']),'role':choice(ROLES)}),
     'operate':('Reconcile held invoice work',{'job':select(InvoiceJob),'operation':choice(['retry','replace_intent','cancel']),'reason':text()}),
     'report':('Record reported cash',{'evidence':ev('cash_report')}),
     'verify':('Verify exact cash receipt',{'receipt':select(CashReceipt),'role':choice(ROLES),'evidence':ev('cash_verification')}),
     'assign':('Assign or reassign receipt to contract',{'receipt':select(CashReceipt),'coverage':select(BillingCoverage,True),'role':choice(ROLES),'evidence':ev('cash_correction'),'reason':text()}),
     'allocate':('Allocate verified cash',{'lot':select(CashVerification),'issue':select(InvoiceIssue),'amount':forms.CharField(max_length=64),'operation_key':forms.CharField(max_length=100),'role':choice(ROLES),'evidence':ev('cash_allocation')}),
     'reverse':('Record full cash or allocation reversal',{'target':choice(['lot','allocation']),'lot':select(CashVerification,True),'allocation':select(CashAllocation,True),'role':choice(ROLES),'evidence':ev('cash_correction'),'reason':text()}),
     'snapshot':('Build current receivable snapshot',{'as_of':forms.DateField()}),
     'investigate':('Investigate receivables and cash',{'snapshot':select(ReceivableSnapshot)}),
     'policy':('Draft invoice or cash configuration',{'component':choice(sorted(SUPPORTED|{'D05.decision_action_matrix'})),
        'content':forms.JSONField(widget=forms.Textarea(attrs={'rows':7})),'evidence':ev('policy_decision'),'effective_from':forms.DateTimeField()})}
    result=[]
    for action,(label,fields) in defs.items():
        f=CommandForm(data if data and data.get('action')==action else None,initial={'action':action,'revision':case.revision},auto_id='settlement_'+action+'_%s');f.fields.update(fields)
        result.append({'label':label,'action':action,'form':f})
    return result

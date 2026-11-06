from django import forms
from apps.policy.document_validators import ROLES
from .forms import CommandForm
from .models import InvoiceIssue,InvoiceCorrection,CashSuccessor,CashVerification

def commands(case,data=None):
    def select(model,optional=False):
        key='invoice__case' if model is InvoiceIssue else 'receipt__case' if model is CashVerification else 'case'
        return forms.ModelChoiceField(model.objects.filter(**{key:case}),required=not optional)
    def ev(kinds,optional=False):return forms.ModelChoiceField(case.evidence.filter(kind__in=kinds),required=not optional)
    def choice(v):return forms.ChoiceField(choices=[(x,x) for x in v])
    def text():return forms.CharField(max_length=4000,widget=forms.Textarea(attrs={'rows':2}))
    defs={
      'note':('Capture invoice credit, debit or void note',{'issue':select(InvoiceIssue),'evidence':ev(['invoice_credit_note','invoice_debit_note','invoice_void_note']),'allocation_evidence':ev(['cash_correction'],True),'reason':text()}),
      'successor':('Capture corrected cash statement',{'parent':select(CashVerification),'report':ev(['cash_report']),'verification':ev(['cash_verification']),'legal':ev(['cash_correction']),'reason':text()}),
      'review':('Review exact financial correction',{'kind':choice(['invoice','cash']),'correction':select(InvoiceCorrection,True),'successor':select(CashSuccessor,True),'role':choice(ROLES),'verdict':choice(['approve','return','reject']),'evidence':ev(['financial_correction_review']),'reason':text()}),
      'reserve':('Reserve correction application or note delivery',{'correction':select(InvoiceCorrection),'effect':choice(['adjust','adjust_deliver']),'role':choice(ROLES)}),
      'apply_successor':('Verify and accept corrected successor lot',{'successor':select(CashSuccessor),'role':choice(ROLES)}),
      'investigate':('Investigate correction and cash lineage',{'kind':choice(['invoice','cash']),'correction':select(InvoiceCorrection,True),'successor':select(CashSuccessor,True)}),
      'policy':('Draft correction policy',{'component':choice(['D05.decision_action_matrix','D08.duplicate_correction_rules','D14.adjustment_correction_rule_refs','D14.legal_document_requirements']),
         'content':forms.JSONField(widget=forms.Textarea(attrs={'rows':8})),'evidence':ev(['policy_decision']),'effective_from':forms.DateTimeField()})}
    result=[]
    for action,(label,fields) in defs.items():
        f=CommandForm(data if data and data.get('action')==action else None,initial={'action':action,'revision':case.revision},auto_id='correction_'+action+'_%s');f.fields.update(fields)
        result.append({'action':action,'label':label,'form':f})
    return result

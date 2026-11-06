from django import forms
from apps.policy.document_validators import ROLES
from apps.finance.forms import CommandForm
from .models import ReconciliationBatch,ReconciliationRun,CorrectiveRequest,CorrectiveJob,CorrectiveDelivery,EngineeringOutcome

def commands(case,data=None):
    def select(model,optional=False):
        key='request__case' if model in [CorrectiveJob,CorrectiveDelivery] else 'delivery__request__case' if model is EngineeringOutcome else 'case'
        return forms.ModelChoiceField(model.objects.filter(**{key:case}),required=not optional)
    def ev(kind):return forms.ModelChoiceField(case.evidence.filter(kind=kind))
    def choice(items):return forms.ChoiceField(choices=[(x,x) for x in items])
    def text():return forms.CharField(max_length=4000,widget=forms.Textarea(attrs={'rows':2}))
    defs={
        'capture':('Capture ledger, settlement or queue evidence',{'reference':forms.CharField(max_length=100),'evidence':ev('reconciliation_input')}),
        'attest':('Attest exact supplied source',{'batch':select(ReconciliationBatch),'role':choice(ROLES),'evidence':ev('reconciliation_attestation')}),
        'calculate':('Compare selected sources',{'ledger':select(ReconciliationBatch,True),'settlement':select(ReconciliationBatch,True),'queue':select(ReconciliationBatch,True)}),
        'request':('Capture corrective request',{'run':select(ReconciliationRun),'reference':forms.CharField(max_length=100),'operation_key':forms.CharField(max_length=100),'evidence':ev('corrective_request'),'reason':text()}),
        'decide':('Decide exact corrective request',{'request':select(CorrectiveRequest),'role':choice(ROLES),'verdict':choice(['approve','return','reject']),'evidence':ev('corrective_decision'),'reason':text()}),
        'reserve':('Reserve Engineering handoff',{'request':select(CorrectiveRequest),'role':choice(ROLES)}),
        'operate':('Reconcile held handoff',{'job':select(CorrectiveJob),'operation':choice(['retry','cancel','replace_intent']),'reason':text()}),
        'outcome':('Record Engineering outcome',{'delivery':select(CorrectiveDelivery),'evidence':ev('engineering_outcome')}),
        'verify':('Verify terminal reported outcome',{'outcome':select(EngineeringOutcome),'role':choice(ROLES),'evidence':ev('engineering_outcome_verification')}),
        'investigate':('Investigate discrepancies and request lineage',{'run':select(ReconciliationRun)}),
        'policy':('Draft BaaS policy',{'component':choice(['D09.reconciliation_contract_ref','D09.queue_state_command_map']),'content':forms.JSONField(widget=forms.Textarea(attrs={'rows':8})),'evidence':ev('policy_decision'),'effective_from':forms.DateTimeField()})}
    result=[]
    for action,(label,fields) in defs.items():
        f=CommandForm(data if data and data.get('action')==action else None,initial={'action':action,'revision':case.revision},auto_id='recon_'+action+'_%s');f.fields.update(fields);result.append({'action':action,'label':label,'form':f})
    return result

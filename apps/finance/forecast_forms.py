from django import forms
from django.contrib.auth import get_user_model
from apps.policy.document_validators import ROLES
from apps.documents.models import Template,Version
from .forms import CommandForm
from .models import ForecastScenario,ForecastRun,ForecastActual,ForecastMatch,CashVerification

def commands(case,data=None):
    def select(model,optional=False):
        key='receipt__case' if model is CashVerification else 'document__case' if model is Version else 'case'
        query=model.objects.filter(**{key:case})
        if model is Version:query=query.exclude(template__definition__document_type='accepted_finance_metadata')
        if model is Template:query=query.exclude(definition__document_type='accepted_finance_metadata')
        return forms.ModelChoiceField(query,required=not optional)
    def ev(kind):return forms.ModelChoiceField(case.evidence.filter(kind=kind))
    def choice(values):return forms.ChoiceField(choices=[(v,v) for v in values])
    def reason():return forms.CharField(max_length=4000,widget=forms.Textarea(attrs={'rows':2}))
    defs={
      'capture':('Capture scenario or actual roll-forward',{'reference':forms.CharField(max_length=100),'evidence':ev('forecast_input'),'parent':select(ForecastRun,True),'reason':reason()}),
      'prepare':('Calculate exact scenario',{'scenario':select(ForecastScenario)}),
      'review':('Review forecast and priorities',{'run':select(ForecastRun),'role':choice(ROLES),'verdict':choice(['approve','return','reject']),'evidence':ev('forecast_review'),'reason':reason()}),
      'actual':('Capture actual receipt or payment evidence',{'evidence':ev('forecast_actual'),'lot':select(CashVerification,True)}),
      'verify':('Verify reported actual',{'actual':select(ForecastActual),'role':choice(ROLES),'evidence':ev('forecast_actual_verification')}),
      'match':('Match actual to expected item',{'scenario':select(ForecastScenario),'item_key':forms.CharField(max_length=100),'actual':select(ForecastActual),'amount':forms.CharField(max_length=64),'operation_key':forms.CharField(max_length=100),'evidence':ev('forecast_match')}),
      'unmatch':('Reverse an actual match',{'match':select(ForecastMatch),'evidence':ev('forecast_match'),'reason':reason()}),
      'priority':('Record reviewed priority and owned follow-up',{'run':select(ForecastRun),'role':choice(ROLES),'reference':forms.CharField(max_length=160),'description':forms.CharField(max_length=1000),'owner':forms.ModelChoiceField(get_user_model().objects.filter(grant__case=case,grant__action='action.own',grant__active=True,is_active=True).distinct()),'due_at':forms.DateTimeField(),'evidence':ev('forecast_review'),'reason':reason()}),
      'draft':('Prepare reviewed audience report',{'run':select(ForecastRun),'template':select(Template),'audience':choice(['internal','management'])}),
      'publish':('Reserve reviewed publication',{'version':select(Version)}),
      'investigate':('Investigate forecast coverage and actuals',{'run':select(ForecastRun)}),
      'policy':('Draft forecast policy',{'component':choice(['D10.forecast_inclusion_rule_id','D10.audience_projection_rules','D05.decision_action_matrix']),'content':forms.JSONField(widget=forms.Textarea(attrs={'rows':8})),'evidence':ev('policy_decision'),'effective_from':forms.DateTimeField()})}
    result=[]
    for action,(label,fields) in defs.items():
        f=CommandForm(data if data and data.get('action')==action else None,initial={'action':action,'revision':case.revision},auto_id='forecast_'+action+'_%s');f.fields.update(fields)
        result.append({'action':action,'label':label,'form':f})
    return result

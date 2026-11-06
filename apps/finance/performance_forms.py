from django import forms
from apps.policy.models import Configuration
from apps.policy.document_validators import ROLES
from apps.documents.models import Template
from .models import FinanceBudget,FinancePeriod,FinanceRun,FinancePerformance,FinanceRestatement
from .forms import CommandForm


def commands(case,data=None):
    def choice(values):return forms.ChoiceField(choices=[(v,v) for v in values])
    def select(model,**filters):return forms.ModelChoiceField(model.objects.filter(case=case,**filters))
    def multiple(model):return forms.ModelMultipleChoiceField(model.objects.filter(case=case),required=False)
    def evidence(kind):return forms.ModelChoiceField(case.evidence.filter(kind=kind))
    definitions={
        'budget':('Capture explicit budget version',{'reference':forms.CharField(max_length=100),'cadence':choice(['monthly','annual']),
            'accounting_basis':forms.CharField(max_length=100,required=False),'effective_at':forms.DateTimeField(),'completeness':choice(['unknown','partial','complete']),'evidence':evidence('finance_budget'),'approval':evidence('finance_budget_approval')}),
        'seal':('Seal reviewed monthly output',{'run':select(FinanceRun,kind='formula'),'restatement':select(FinanceRestatement)}),
        'build':('Build explicit period comparison',{'cutoff':forms.CharField(max_length=7),'periods':multiple(FinancePeriod),'budget':select(FinanceBudget),'prior':multiple(FinancePeriod)}),
        'decide':('Record configured performance decision',{'purpose':choice(['budget','period_method','performance','restatement']),
            'budget':select(FinanceBudget),'configuration':select(Configuration,component='D06.unit_sign_currency_period'),'performance':select(FinancePerformance),'restatement':select(FinanceRestatement),
            'role':choice(ROLES),'verdict':choice(['approve','return','reject']),'evidence':evidence('finance_review'),'note':forms.CharField(max_length=4000,widget=forms.Textarea(attrs={'rows':2}))}),
        'restate':('Request evidenced historical replacement',{'original':select(FinancePeriod),'proposed':select(FinanceRun,kind='formula'),
            'evidence':evidence('finance_restatement'),'rationale':forms.CharField(max_length=4000,widget=forms.Textarea(attrs={'rows':2}))}),
        'report':('Prepare reviewed performance publication',{'performance':select(FinancePerformance),'template':select(Template,definition__document_type='finance_report'),'audience':choice(['internal','management'])}),
        'investigate':('Investigate budget and period lineage',{'performance':select(FinancePerformance)})}
    result=[]
    for action,(label,fields) in definitions.items():
        form=CommandForm(data if data and data.get('action')==action else None,initial={'action':action,'revision':case.revision},auto_id='performance_'+action+'_%s');form.fields.update(fields)
        if action=='seal':form.fields['restatement'].required=False
        if action=='build':form.fields['budget'].required=False
        if action=='decide':
            for key in ['budget','configuration','performance','restatement']:form.fields[key].required=False
        for field in fields.values():
            if isinstance(field,forms.ModelChoiceField):
                if field.queryset.model is Configuration:field.label_from_instance=lambda c:f'{c.component} / revision {c.revision} / #{c.pk}'
        result.append({'label':label,'form':form,'action':action})
    return result

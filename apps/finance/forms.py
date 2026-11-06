from django import forms
from apps.documents.models import Template
from apps.policy.models import Configuration
from apps.policy.document_validators import ROLES
from apps.policy.finance_drafts import SCHEMAS,EXTRA
from .models import FinancialImport,FinanceSource,FinanceRun,FinanceAdjustment

class CommandForm(forms.Form):
    action=forms.CharField(widget=forms.HiddenInput)
    revision=forms.IntegerField(widget=forms.HiddenInput)

def commands(case,data=None):
    def evidence(kinds):return forms.ModelChoiceField(case.evidence.filter(kind__in=kinds))
    def choice(values):return forms.ChoiceField(choices=[(x,x) for x in values])
    def js(help_text=''):return forms.JSONField(widget=forms.Textarea(attrs={'rows':5}),help_text=help_text)
    def src():return forms.ModelChoiceField(FinanceSource.objects.filter(case=case))
    def run():return forms.ModelChoiceField(FinanceRun.objects.filter(case=case))
    definitions={
        'capture':('Capture supplied CSV',{'evidence':evidence(['financial_input'])}),
        'validate':('Validate source conventions',{'batch':forms.ModelChoiceField(FinancialImport.objects.filter(case=case))}),
        'source':('Record extraction context',{'batch':forms.ModelChoiceField(FinancialImport.objects.filter(case=case)),'entity':forms.CharField(max_length=100),'accounting_basis':forms.CharField(max_length=100),
            'extracted_at':forms.DateTimeField(),'completeness':choice(['unknown','partial','complete']),'control_total':forms.CharField(required=False,max_length=64),'evidence':evidence(['finance_source'])}),
        'policy':('Save Finance policy draft',{'component':choice(sorted(set(SCHEMAS)|set(EXTRA))),'content':js('Versioned typed records; no executable workbook expressions or default account/ratio values.'),
            'evidence':evidence(['policy_decision']),'effective_from':forms.DateTimeField()}),
        'review':('Record configured Finance review',{'purpose':choice(['source','mapping','formula','allocation','adjustment','output']),'source':src(),
            'configuration':forms.ModelChoiceField(Configuration.objects.filter(case=case,component__in=['D06.account_bu_maps','D06.rule_oracle_refs','D06.statement_contract','D06.producer_conventions','D06.statement_conversions','D07.allocation_pool_rules','D07.rounding_residual_rule_id','D10.report_category_effective_dates'])),
            'adjustment':forms.ModelChoiceField(FinanceAdjustment.objects.filter(source__case=case)),'run':run(),'role':choice(ROLES),'verdict':choice(['approve','return','reject']),
            'evidence':evidence(['finance_review']),'note':forms.CharField(max_length=4000,widget=forms.Textarea(attrs={'rows':2}))}),
        'adjust':('Capture reporting adjustment',{'source':src(),'reference':forms.CharField(max_length=100),'kind':choice(['additive','reclassification']),
            'lines':js('Array of {account, amount}; exact decimal strings, reporting only. Reclassification must conserve the total.'),'evidence':evidence(['finance_adjustment']),'note':forms.CharField(max_length=4000)}),
        'map':('Build mapping preview',{'source':src(),'adjustments':forms.ModelMultipleChoiceField(FinanceAdjustment.objects.filter(source__case=case),required=False)}),
        'allocate':('Build BU allocation preview',{'parent':forms.ModelChoiceField(FinanceRun.objects.filter(case=case,kind='mapping')),
            'metrics':forms.MultipleChoiceField(choices=[(v,v) for v in ['revenue','direct_cost','staff_cost','opex','other']])}),
        'calculate':('Calculate configured metrics',{'parent':forms.ModelChoiceField(FinanceRun.objects.filter(case=case,kind__in=['mapping','allocation']))}),
        'statement':('Bind reviewed statement inputs',{'parent':forms.ModelChoiceField(FinanceRun.objects.filter(case=case,kind='formula')),'contract':forms.ModelChoiceField(Configuration.objects.filter(case=case,component='D06.statement_contract'))}),
        'report':('Prepare reviewed aggregate report',{'run':forms.ModelChoiceField(FinanceRun.objects.filter(case=case,kind__in=['formula','statement'])),
            'template':forms.ModelChoiceField(Template.objects.filter(case=case,definition__document_type='finance_report')),'audience':choice(['internal','management'])}),
        'investigate':('Investigate lineage and differences',{'run':run()})}
    result=[]
    for action,(label,fields) in definitions.items():
        f=CommandForm(data if data and data.get('action')==action else None,initial={'action':action,'revision':case.revision},auto_id='finance_'+action+'_%s');f.fields.update(fields)
        for field in f.fields.values():
            if isinstance(field,forms.ModelChoiceField):
                if field.queryset.model is Configuration:
                    field.label_from_instance=lambda c:f'{c.component} / revision {c.revision} / #{c.pk}'
                elif field.queryset.model is FinancialImport:
                    field.label_from_instance=lambda b:f'Import #{b.pk} / evidence #{b.evidence_id} / {b.source_sha256[:12]}'
                elif field.queryset.model is FinanceAdjustment:
                    field.label_from_instance=lambda a:f'{a.reference} v{a.number} / source #{a.source_id} / #{a.pk}'
        if action=='review':
            for k in ['source','configuration','adjustment','run']:f.fields[k].required=False
        result.append({'action':action,'label':label,'form':f})
    return result

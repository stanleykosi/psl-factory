import json
from django.core.exceptions import ValidationError
from django.db import transaction
from apps.core.services import lock_case,add_evidence
from apps.policy.services import active_component,reference_values
from apps.documents.models import Template
from apps.documents.controlled import create_version
from .models import ForecastRun,ForecastBinding
from . import forecast

def report_inputs(run,audience):
    review=forecast.approved(run)
    c=active_component('D10.audience_projection_rules',run.case)
    choices=[r for r in reference_values(c)[0].get('forecast',[]) if r['audience']==audience]
    if len(choices)!=1:raise ValidationError('Configure exact aggregate forecast audience and publisher roles')
    return {'projection_implementation':'forecast-report/v1','run':run.pk,'run_hash':run.sha256,'output_review':review.pk,'projection_config':c.pk,'projection':choices[0],'audience':audience}

@transaction.atomic
def draft(actor,case_id,run_id,template_id,audience,expected):
    case=lock_case(actor,case_id,'finance.publish',expected);run=forecast.exact(case,ForecastRun,run_id);snapshot=report_inputs(run,audience)
    template=Template.objects.filter(case=case,pk=template_id,definition__document_type='finance_report').first()
    if not template or not {'executive_summary','financial_metrics','bu_totals'}.issubset(template.definition['audience_fields'].get(audience,[])):raise ValidationError('Select this case aggregate Finance report template/audience')
    public={'entity':run.result['entity'],'currency':run.result['currency'],'basis':run.result['basis'],'as_of':run.result['as_of'],'status':run.result['status'],
        'scope':run.result['scope'],'full_business_cash_forecast':False,'coverage':{'account_count':len(run.result['coverage']['accounts']),'inflows':run.result['coverage']['inflows'],'outflows':run.result['coverage']['outflows'],'omission_count':len(run.result['coverage']['omissions']),'finding_count':len(run.result['findings'])},
        'periods':[{k:v for k,v in row.items() if k in ['month']+snapshot['projection']['columns']} for row in run.result['periods']],
        'execution_authorized':False}
    e=add_evidence(actor,case.pk,'finance_report_snapshot',json.dumps(public,sort_keys=True),'derived:forecast:'+str(run.pk),case.revision);case.refresh_from_db()
    fields={'executive_summary':{'text':f"Reviewed {public['status']} forecast for {public['entity']} / {public['as_of']}. Captured case and explicitly declared account/source inventory only; omitted or unknown activity is outside this projection. This report grants no spending, payment or release authority.",'evidence_ids':[e.pk]},
        'financial_metrics':{'text':json.dumps(public,sort_keys=True),'evidence_ids':[e.pk]},'bu_totals':{'text':'No BU allocation or entity consolidation inferred.','evidence_ids':[e.pk]}}
    v=create_version(actor,case.pk,template.pk,'Reviewed cash forecast '+str(run.pk),audience,fields,case.revision)
    ForecastBinding.objects.create(version=v,run=run,snapshot=snapshot)
    from .documents import sender
    sender(actor,v);return v

import json
from django.core.exceptions import ValidationError,PermissionDenied
from django.db import transaction
from apps.core.services import lock_case,add_evidence
from apps.identity.services import require
from apps.policy.services import active_component,reference_values,decision_authority
from apps.documents.controlled import create_version
from apps.documents.models import Template
from .models import FinanceRun,FinanceDocumentBinding,FinancePerformance,FinancePerformanceBinding,ForecastRun,ForecastBinding
from .analysis import ensure_current,certification_findings,current_review,digest

def binding_for(version):
    return FinanceDocumentBinding.objects.filter(version=version).first() or FinancePerformanceBinding.objects.filter(version=version).first() or ForecastBinding.objects.filter(version=version).first()


def report_inputs(run,audience):
    if isinstance(run,ForecastRun):
        from .forecast_documents import report_inputs as forecast_inputs
        return forecast_inputs(run,audience)
    if isinstance(run,FinancePerformance):
        from .performance import ensure_current as current_performance,current_decision
        current_performance(run)
        if run.result['status']!='complete':raise ValidationError('Resolve comparison findings before publication')
        review=current_decision(run.case,'performance',performance=run)
        if not review['valid']:raise ValidationError('Obtain the exact configured performance review')
        return _report_projection(run,audience,review)
    if run.kind not in ['formula','statement']:raise ValidationError('Select an exact formula output')
    findings=certification_findings(run)
    if findings:raise ValidationError(findings)
    review=current_review(run.case,'output',run=run)
    if not review['valid']:raise ValidationError('Obtain the configured current Finance output review')
    return _report_projection(run,audience,review)


def _report_projection(run,audience,review):
    c=active_component('D10.audience_projection_rules',run.case)
    matches=[x for x in reference_values(c)[0].get('audiences',[]) if x['audience']==audience]
    if len(matches)!=1:raise ValidationError('Configure this exact internal/management aggregate audience')
    projection=matches[0]
    if projection['include_company'] and set(projection['formula_keys'])-set(run.result['company']) or set(projection['bu_keys'])-set(run.result['by_bu']):raise ValidationError('Projection selects an unknown formula or BU')
    if any(set(projection['formula_keys'])-set(run.result['by_bu'][bu]) for bu in projection['bu_keys']):raise ValidationError('Projection selects a company-only formula for a BU')
    return {'projection_implementation':'finance-report-projection/v3','run':run.pk,'run_key':run.operation_key,'result_hash':digest(run.result),'output_review':review['id'],'projection_config':c.pk,'projection':projection,'audience':audience}

def sender(actor,version):
    b=binding_for(version)
    if not b:return
    case=version.document.case;require(actor,case,'finance.publish');require(actor,case,'finance.read')
    for role in b.snapshot['projection']['publisher_roles']:
        try:decision_authority(actor,case,role);return
        except (ValidationError,PermissionDenied):pass
    raise PermissionDenied('Publisher must have a current explicitly configured Finance report role')

def projection_rows(run,projection):
    columns=projection.get('columns',['actual'])
    if not isinstance(run,FinancePerformance) and columns!=['actual']:raise ValidationError('Comparison columns require a performance output')
    def display(values):
        return {key:{**{('value' if column=='actual' else column):values[key].get('value' if column=='actual' else column) for column in columns},
                     'unit':values[key]['unit'],'rule_key':key} for key in projection['formula_keys']}
    return {'entity':run.result['entity'],'period':run.result['period'],'currency':run.result['currency'],
        'company':display(run.result['company']) if projection['include_company'] else {},
        'by_bu':{bu:display(run.result['by_bu'][bu]) for bu in projection['bu_keys']},'source_run':run.pk,
        'accounting_basis':run.result.get('accounting_basis',run.source.accounting_basis if isinstance(run,FinanceRun) else None),'ratio_multiplier':run.result.get('method',{}).get('multiplier'),'comparison_definition':run.result.get('method',{}).get('ratio'),'columns':columns,'included_periods':run.result.get('included_periods',[]),'budget_version':run.result.get('budget_version'),'chart_spec':{'implementation':'signed_grouped_bars_v1','data':[{'scope':row['scope'],'bu':row['bu'],'metric':row['metric'],'label':row['label'],'unit':row['unit'],**{column:row[column] for column in columns if column in ['actual','budget','prior']}} for row in run.result.get('chart',[]) if row['metric'] in projection['formula_keys'] and (row['scope']=='company' and projection['include_company'] or row['bu'] in projection['bu_keys'])]} if projection.get('charts') else None,
        'scope':('Selected statement lines only; full statement and balance-sheet oracle remain deferred. ' if isinstance(run,FinanceRun) and run.kind=='statement' else '')+'Selected source, reporting adjustments and configured metrics; not ledger posting, financial close, invoice or payment.'}

@transaction.atomic
def draft_report(actor,case_id,run_id,template_id,audience,expected,performance=False):
    case=lock_case(actor,case_id,'finance.publish',expected);model=FinancePerformance if performance else FinanceRun;run=model.objects.filter(case=case,pk=run_id).first()
    if not run:raise ValidationError('Select this case exact Finance output')
    snapshot=report_inputs(run,audience);template=Template.objects.filter(case=case,pk=template_id,definition__document_type='finance_report').first()
    fields_needed={'executive_summary','financial_metrics','bu_totals'}
    if not template or template.definition.get('internal_review_required') is not False or not fields_needed.issubset(template.definition['audience_fields'].get(audience,[])):
        raise ValidationError('Finance report template needs aggregate sections and explicit internal_review_required:false; configured Finance output review supplies the domain decision')
    projected=projection_rows(run,snapshot['projection'])
    evidence=add_evidence(actor,case.pk,'finance_report_snapshot',json.dumps(projected,sort_keys=True),('derived:finance-performance:' if performance else 'derived:finance-output:')+str(run.pk),case.revision)
    case.refresh_from_db()
    fields={'executive_summary':{'text':f"Configured Finance metrics for {projected['entity']} / {projected['period']} / {projected['currency']}. "+projected['scope'],'evidence_ids':[evidence.pk]},
        'financial_metrics':{'text':json.dumps({'accounting_basis':projected['accounting_basis'],'figures':projected['company'],'columns':projected['columns'],'ratio_definition':projected['comparison_definition'],'ratio_multiplier':projected['ratio_multiplier'],'periods':projected['included_periods'],'chart_spec':projected['chart_spec']},sort_keys=True),'evidence_ids':[evidence.pk]},
        'bu_totals':{'text':json.dumps(projected['by_bu'],sort_keys=True),'evidence_ids':[evidence.pk]}}
    v=create_version(actor,case.pk,template.pk,('Finance reviewed performance ' if performance else 'Finance configured output ')+str(run.pk),audience,fields,case.revision)
    (FinancePerformanceBinding if performance else FinanceDocumentBinding).objects.create(version=v,run=run,snapshot=snapshot);sender(actor,v);return v

def binding_findings(binding):
    try:
        if binding.version.audience=='group':
            from .group_forecast import check_content
            check_content(binding)
        if binding.snapshot!=report_inputs(binding.run,binding.version.audience):return ['Finance source, rule, review or audience changed; rebuild and review the current output']
    except (ValidationError,PermissionDenied) as exc:return ['Finance report held: '+str(exc)]
    return []

def publication_requirements(binding,recipients):
    if binding.version.audience=='group':
        from .group_forecast import recipient_requirements
        return recipient_requirements(binding,recipients)
    from django.contrib.auth import get_user_model
    for user in get_user_model().objects.filter(pk__in=recipients):require(user,binding.run.case,'finance.read')
    roles=active_component('D05.role_principal_assignments',binding.run.case)
    return {'D10.audience_projection_rules':binding.snapshot['projection_config'],roles.component:roles.pk}

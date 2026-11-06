"""Forecast envelope composed additively from exact accepted predecessors."""
from importlib import import_module
from django.db import migrations
PREVIOUS=import_module('apps.workflows.migrations.0066_factory_payroll').SQL

def work_sql(previous):
    marker="'rfp-response/v1','pmo-change/v1'"
    assert previous.count(marker)==1
    sql=previous.replace(marker,marker+",'finance-forecast/v1'")
    marker="WHEN 'pmo-change/v1' THEN 'OPS.factory_change_execution'"
    assert sql.count(marker)==1
    sql=sql.replace(marker,marker+" WHEN 'finance-forecast/v1' THEN 'OPS.factory_forecast_execution'")
    source="""
 IF NEW.definition='finance-forecast/v1' AND NOT EXISTS(
  SELECT 1 FROM core_evidence e JOIN core_audit a ON a.case_id=e.case_id AND a.actor_id=e.created_by_id
  JOIN finance_forecastscenario s ON s.id=(e.body::jsonb->>'scenario_id')::bigint
  WHERE e.id=NEW.source_head_id AND e.case_id=NEW.case_id AND s.case_id=NEW.case_id
   AND e.kind='agent_private_forecast_intake' AND e.body::jsonb->>'protocol'='factory-forecast-selection/v1'
   AND s.reference=NEW.request->>'scenario_reference'
   AND e.body::jsonb-ARRAY['protocol','scenario_id','as_of','months','source_ids','template_id','audience']='{}'::jsonb
   AND e.body::jsonb->>'audience' IN ('internal','management')
   AND jsonb_typeof(e.body::jsonb->'source_ids')='array'
   AND jsonb_array_length(e.body::jsonb->'source_ids')=(SELECT count(*) FROM (
    SELECT s.evidence_id AS id UNION SELECT (item->>'evidence_id')::bigint FROM jsonb_array_elements(s.payload->'openings') item
    UNION SELECT (item->>'evidence_id')::bigint FROM jsonb_array_elements(s.payload->'items') item) exact_sources)
   AND NOT EXISTS(SELECT id FROM (
    SELECT s.evidence_id AS id UNION SELECT (item->>'evidence_id')::bigint FROM jsonb_array_elements(s.payload->'openings') item
    UNION SELECT (item->>'evidence_id')::bigint FROM jsonb_array_elements(s.payload->'items') item) exact_sources
    WHERE NOT e.body::jsonb->'source_ids' @> jsonb_build_array(id))
   AND (e.body::jsonb->'template_id'='null'::jsonb OR EXISTS(SELECT 1 FROM documents_template t
    WHERE t.id=(e.body::jsonb->>'template_id')::bigint AND t.case_id=NEW.case_id AND t.definition->>'document_type'='finance_report'))
   AND e.body::jsonb->>'as_of'=s.payload->>'as_of' AND e.body::jsonb->'months'=s.payload->'months'
   AND a.action IN ('factory.forecast_intake','factory.forecast_source')
   AND a.data=jsonb_build_object('evidence_id',e.id,'sha256',e.sha256)
   AND NEW.invoice_id IS NULL AND NEW.preparation_id IS NULL)
 THEN RAISE EXCEPTION 'Exact native forecast intake provenance required'; END IF;
 IF NEW.definition='finance-forecast/v1' AND NEW.status='verified' AND NOT EXISTS(
  SELECT 1 FROM core_evidence e JOIN finance_forecastscenario s ON s.id=(e.body::jsonb->>'scenario_id')::bigint
  JOIN finance_forecastrun r ON r.scenario_id=s.id JOIN finance_forecastreview rv ON rv.run_id=r.id
  JOIN finance_forecastbinding b ON b.run_id=r.id JOIN documents_version v ON v.id=b.version_id
  JOIN documents_publication p ON p.version_id=v.id
  JOIN workflows_factoryactivity fa ON fa.work_id=NEW.id AND fa.kind='ACT13'
  JOIN workflows_factoryattempt a ON a.activity_id=fa.id AND a.phase='observed'
  WHERE e.id=NEW.source_head_id AND r.case_id=NEW.case_id AND s.case_id=NEW.case_id
   AND rv.verdict='approve' AND rv.id=(SELECT max(id) FROM finance_forecastreview WHERE run_id=r.id)
   AND NOT EXISTS(SELECT 1 FROM finance_forecastscenario newer WHERE newer.case_id=s.case_id AND newer.reference=s.reference AND newer.number>s.number)
   AND p.factory_work_id=NEW.id AND p.factory_source_id=e.id AND p.factory_policy_id=NEW.policy_id
   AND v.template_id=(e.body::jsonb->>'template_id')::bigint AND v.audience=e.body::jsonb->>'audience'
   AND b.snapshot->>'run_hash'=r.sha256 AND b.snapshot->>'output_review'=rv.id::text
   AND a.result->'verified'='true'::jsonb AND a.result->>'head'=e.id::text
   AND a.result->>'forecast_run'=r.id::text AND a.result->>'forecast_review'=rv.id::text
   AND a.result->>'document_version'=v.id::text AND a.result->>'publication'=p.id::text
   AND jsonb_array_length(p.recipient_ids)>0
   AND NOT EXISTS(SELECT 1 FROM jsonb_array_elements_text(p.recipient_ids) recipient WHERE NOT EXISTS(
    SELECT 1 FROM documents_publicationreceipt pr WHERE pr.publication_id=p.id AND pr.recipient_id=recipient::bigint
     AND pr.payload_sha256=v.payload_sha256 AND pr.payload=v.payload)))
 THEN RAISE EXCEPTION 'Observed exact native forecast approval and aggregate receipts required'; END IF;
"""
    assert sql.count(' RETURN NEW;')==1
    result=sql.replace(' RETURN NEW;',source+' RETURN NEW;')
    restored=result.replace(source,'',1).replace(",'finance-forecast/v1'",'',1).replace(" WHEN 'finance-forecast/v1' THEN 'OPS.factory_forecast_execution'",'',1)
    assert restored==previous
    return result

SQL=work_sql(PREVIOUS)

class Migration(migrations.Migration):
    dependencies=[('workflows','0066_factory_payroll'),('pmo','0043_change_impact')]
    operations=[migrations.RunSQL(SQL,PREVIOUS)]

"""Explicit diagnostic-only SQL additions over accepted0064/0021.

This is not a migration or acceptance of pending predecessor composition.
Remove its use from final701; final tests use only the accepted migration graph.
"""
from importlib import import_module

PREVIOUS_WORK = import_module('apps.workflows.migrations.0064_factory_change').SQL
PREVIOUS_DOC = import_module('apps.documents.migrations.0021_factory_change').SQL


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
    return sql.replace(' RETURN NEW;',source+' RETURN NEW;')


def doc_sql(previous):
    branch="""
    OR
    (w.definition='finance-forecast/v1' AND p.component='OPS.factory_forecast_execution'
     AND w.policy_id=p.id AND w.source_head_id=e.id AND e.kind='agent_private_forecast_intake'
     AND EXISTS(SELECT 1 FROM finance_forecastbinding b JOIN finance_forecastrun r ON r.id=b.run_id
      JOIN finance_forecastscenario s ON s.id=r.scenario_id JOIN finance_forecastreview rv ON rv.run_id=r.id
      WHERE b.version_id=v.id AND r.case_id=w.case_id AND s.case_id=w.case_id
       AND s.reference=w.request->>'scenario_reference' AND s.id=(e.body::jsonb->>'scenario_id')::bigint
       AND rv.verdict='approve' AND rv.id=(SELECT max(id) FROM finance_forecastreview WHERE run_id=r.id)
       AND b.snapshot->>'output_review'=rv.id::text AND b.snapshot->>'run_hash'=r.sha256
       AND v.template_id=(e.body::jsonb->>'template_id')::bigint AND v.audience=e.body::jsonb->>'audience'
       AND NOT EXISTS(SELECT 1 FROM finance_forecastscenario newer WHERE newer.case_id=s.case_id AND newer.reference=s.reference AND newer.number>s.number)
       AND EXISTS(SELECT 1 FROM workflows_factoryactivity fa JOIN workflows_factoryattempt a ON a.activity_id=fa.id
        WHERE fa.work_id=w.id AND fa.kind='ACT09' AND a.phase='observed' AND a.result->>'head'=e.id::text
         AND a.result->>'document_version'=v.id::text AND a.result->>'forecast_run'=r.id::text)))
"""
    marker='\n   ))'
    assert previous.count(marker)==1
    return previous.replace(marker,branch+marker)

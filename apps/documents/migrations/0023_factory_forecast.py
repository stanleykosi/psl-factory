"""Forecast envelope composed additively from exact accepted predecessors."""
from importlib import import_module
from django.db import migrations
PREVIOUS=import_module('apps.documents.migrations.0022_factory_emergency').SQL

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
    result=previous.replace(marker,branch+marker)
    assert result.replace(branch,'',1)==previous
    return result

SQL=doc_sql(PREVIOUS)

class Migration(migrations.Migration):
    dependencies=[('documents','0022_factory_emergency'),('workflows','0067_factory_forecast')]
    operations=[migrations.RunSQL(SQL,PREVIOUS)]

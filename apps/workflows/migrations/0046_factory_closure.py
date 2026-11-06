"""Eighth native closure envelope; publication authority remains separately closed."""
from importlib import import_module
from django.db import migrations

previous=import_module('apps.workflows.migrations.0045_factory_handover')
SQL=previous.SQL
OLD="'pmo-finance/v1','planning/v1','commercial/v1','delivery-release/v1','delivery-hypercare/v1','delivery-archive/v1','delivery-handover/v1'"
assert SQL.count(OLD)==1
SQL=SQL.replace(OLD,OLD+",'delivery-closure/v1'")
OLD="WHEN 'delivery-handover/v1' THEN 'OPS.factory_handover_execution'"
assert SQL.count(OLD)==1
SQL=SQL.replace(OLD,OLD+" WHEN 'delivery-closure/v1' THEN 'OPS.factory_closure_execution'")
MARKER=" IF NEW.status='verified' THEN"
assert SQL.count(MARKER)==1
SQL=SQL.replace(MARKER,previous.SOURCE.replace('handover','closure')+MARKER)
VERIFIED=r"""
 IF NEW.definition='delivery-closure/v1' AND NEW.status='verified' AND NOT EXISTS(
  SELECT 1 FROM pmo_deliveryrecord c JOIN pmo_deliverydocumentbinding b ON b.version_id=(c.data->>'version_id')::bigint
  JOIN documents_version v ON v.id=b.version_id
  JOIN pmo_deliveryrecord decision ON decision.id=(c.data->>'decision_id')::bigint
  JOIN core_evidence head ON head.id=NEW.source_head_id
  JOIN workflows_factoryactivity fa ON fa.work_id=NEW.id AND fa.kind='ACT13'
  JOIN workflows_factoryattempt a ON a.activity_id=fa.id AND a.phase='observed'
  WHERE c.dossier_id=(NEW.request->>'dossier')::bigint AND c.kind='closure' AND b.dossier_id=c.dossier_id AND b.purpose='closure'
   AND decision.dossier_id=c.dossier_id AND decision.kind='closure_decision' AND decision.data->>'verdict'='approve'
   AND decision.data->>'version_id'=v.id::text AND decision.snapshot=b.snapshot AND c.snapshot=b.snapshot
   AND b.data=(head.body::jsonb->'inputs')-'template_id' AND v.template_id=(head.body::jsonb->'inputs'->>'template_id')::bigint
   AND a.result->'verified'='true'::jsonb AND a.result->>'closure'=c.id::text
   AND a.result->>'document_version'=v.id::text AND a.result->>'head'=NEW.source_head_id::text)
 THEN RAISE EXCEPTION 'Observed exact native closure, prescribed decision and current source binding required'; END IF;
"""
assert SQL.count(' RETURN NEW;')==1
SQL=SQL.replace(' RETURN NEW;',VERIFIED+' RETURN NEW;')

class Migration(migrations.Migration):
    dependencies=[('workflows','0045_factory_handover'),('documents','0016_factory_handover_scope')]
    operations=[migrations.RunSQL(SQL)]

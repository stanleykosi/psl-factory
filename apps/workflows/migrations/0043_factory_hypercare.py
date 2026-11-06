"""Add a native hypercare envelope while preserving all immutable prior guards."""
from importlib import import_module
from django.db import migrations

PREVIOUS=import_module('apps.workflows.migrations.0042_factory_delivery')
SQL=PREVIOUS.SQL
OLD="'pmo-finance/v1','planning/v1','commercial/v1','delivery-release/v1'"
assert SQL.count(OLD)==1
SQL=SQL.replace(OLD,OLD+",'delivery-hypercare/v1'")
OLD="WHEN 'delivery-release/v1' THEN 'OPS.factory_delivery_execution'"
assert SQL.count(OLD)==1
SQL=SQL.replace(OLD,OLD+" WHEN 'delivery-hypercare/v1' THEN 'OPS.factory_hypercare_execution'")
SOURCE=PREVIOUS.SOURCE.replace("NEW.definition='delivery-release/v1'","NEW.definition='delivery-hypercare/v1'")
MARKER=" IF NEW.status='verified' THEN"
assert SQL.count(MARKER)==1
SQL=SQL.replace(MARKER,SOURCE+MARKER)
VERIFIED=r"""
 IF NEW.definition='delivery-hypercare/v1' AND NEW.status='verified' AND NOT EXISTS(
  SELECT 1 FROM pmo_deliveryrecord r JOIN pmo_deliverydossier d ON d.id=r.dossier_id
  JOIN workflows_factoryactivity fa ON fa.work_id=NEW.id JOIN workflows_factoryattempt a ON a.activity_id=fa.id
  WHERE d.id=(NEW.request->>'dossier')::bigint AND d.case_id=NEW.case_id AND r.kind='hypercare'
   AND r.snapshot->'qualified'='true'::jsonb
   AND a.phase='observed' AND a.result->>'hypercare'=r.id::text AND a.result->>'head'=NEW.source_head_id::text)
 THEN RAISE EXCEPTION 'Native source-bound qualified hypercare required; no closure or release authority is granted'; END IF;
"""
MARKER=' RETURN NEW;'
assert SQL.count(MARKER)==1
SQL=SQL.replace(MARKER,VERIFIED+MARKER)

class Migration(migrations.Migration):
    dependencies=[('workflows','0042_factory_delivery')]
    operations=[migrations.RunSQL(SQL)]

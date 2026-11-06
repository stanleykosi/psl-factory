"""Add only the sixth native archive-index envelope; retain all five prior guards."""
from importlib import import_module
from django.db import migrations

SQL=import_module('apps.workflows.migrations.0043_factory_hypercare').SQL
OLD="'pmo-finance/v1','planning/v1','commercial/v1','delivery-release/v1','delivery-hypercare/v1'"
assert SQL.count(OLD)==1
SQL=SQL.replace(OLD,OLD+",'delivery-archive/v1'")
OLD="WHEN 'delivery-hypercare/v1' THEN 'OPS.factory_hypercare_execution'"
assert SQL.count(OLD)==1
SQL=SQL.replace(OLD,OLD+" WHEN 'delivery-archive/v1' THEN 'OPS.factory_archive_execution'")
SOURCE=r"""
 IF NEW.definition='delivery-archive/v1' THEN
  IF NEW.invoice_id IS NOT NULL OR NEW.preparation_id IS NOT NULL OR NOT EXISTS(
   SELECT 1 FROM core_evidence e JOIN core_audit a ON a.case_id=e.case_id AND a.actor_id=e.created_by_id
   JOIN pmo_deliverydossier d ON d.id=(NEW.request->>'dossier')::bigint
   WHERE e.id=NEW.source_head_id AND e.case_id=NEW.case_id AND e.kind='agent_private_archive_intake'
    AND e.body::jsonb->>'protocol'='factory-archive-intake/v1' AND e.body::jsonb->>'dossier_id'=d.id::text
    AND e.body::jsonb-ARRAY['protocol','dossier_id','inventory']='{}'::jsonb
    AND jsonb_typeof(e.body::jsonb->'inventory')='object' AND d.case_id=NEW.case_id
    AND a.action IN ('factory.archive_intake','factory.archive_source')
    AND a.data=jsonb_build_object('evidence_id',e.id,'sha256',e.sha256))
  THEN RAISE EXCEPTION 'Native same-case declared archive intake and dossier required'; END IF;
 END IF;
"""
MARKER=" IF NEW.status='verified' THEN"
assert SQL.count(MARKER)==1
SQL=SQL.replace(MARKER,SOURCE+MARKER)
VERIFIED=r"""
 IF NEW.definition='delivery-archive/v1' AND NEW.status='verified' AND NOT EXISTS(
  SELECT 1 FROM pmo_deliveryrecord r JOIN pmo_deliverydossier d ON d.id=r.dossier_id
  JOIN core_evidence e ON e.id=NEW.source_head_id
  JOIN workflows_factoryactivity fa ON fa.work_id=NEW.id JOIN workflows_factoryattempt a ON a.activity_id=fa.id
  WHERE d.id=(NEW.request->>'dossier')::bigint AND d.case_id=NEW.case_id AND r.kind='archive'
   AND r.data->'inventory'=e.body::jsonb->'inventory'
   AND r.snapshot->'physical_purge_performed'='false'::jsonb
   AND r.snapshot->>'repository'='internal-versioned'
   AND a.phase='observed' AND a.result->>'archive'=r.id::text AND a.result->>'head'=NEW.source_head_id::text)
 THEN RAISE EXCEPTION 'Exact observed native archive index required; no physical purge or closure authority'; END IF;
"""
assert SQL.count(' RETURN NEW;')==1
SQL=SQL.replace(' RETURN NEW;',VERIFIED+' RETURN NEW;')

class Migration(migrations.Migration):
    dependencies=[('workflows','0043_factory_hypercare')]
    operations=[migrations.RunSQL(SQL)]

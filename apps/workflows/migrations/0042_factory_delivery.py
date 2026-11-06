"""Extend the immutable prior guard, retaining its complete three-definition checks."""
from importlib import import_module
from django.db import migrations

BASE=import_module('apps.workflows.migrations.0041_factory_commercial').SQL
OLD="'pmo-finance/v1','planning/v1','commercial/v1'"
assert BASE.count(OLD)==1
SQL=BASE.replace(OLD,OLD+",'delivery-release/v1'")
OLD="WHEN 'commercial/v1' THEN 'OPS.factory_commercial_execution'"
assert SQL.count(OLD)==1
SQL=SQL.replace(OLD,OLD+" WHEN 'delivery-release/v1' THEN 'OPS.factory_delivery_execution'")
SOURCE=r"""
 IF NEW.definition='delivery-release/v1' THEN
  IF NEW.invoice_id IS NOT NULL OR NEW.preparation_id IS NOT NULL OR NOT EXISTS(
   SELECT 1 FROM core_evidence e JOIN core_audit a ON a.case_id=e.case_id AND a.actor_id=e.created_by_id
   JOIN pmo_deliverydossier d ON d.id=(NEW.request->>'dossier')::bigint
   WHERE e.id=NEW.source_head_id AND e.case_id=NEW.case_id AND e.kind='agent_private_delivery_intake'
    AND d.case_id=NEW.case_id AND e.body::jsonb->>'protocol'='factory-delivery-intake/v1'
    AND e.body::jsonb->>'dossier_id'=d.id::text AND a.action='factory.delivery_intake'
    AND a.data=jsonb_build_object('evidence_id',e.id,'sha256',e.sha256))
  THEN RAISE EXCEPTION 'Native same-case delivery intake and dossier required'; END IF;
 END IF;
"""
MARKER=" IF NEW.status='verified' THEN"
assert SQL.count(MARKER)==1
SQL=SQL.replace(MARKER,SOURCE+MARKER)
VERIFIED=r"""
 IF NEW.definition='delivery-release/v1' AND NEW.status='verified' AND NOT EXISTS(
  SELECT 1 FROM pmo_deliveryrecord r JOIN pmo_deliverydossier d ON d.id=r.dossier_id
  JOIN workflows_factoryactivity fa ON fa.work_id=NEW.id JOIN workflows_factoryattempt a ON a.activity_id=fa.id
  WHERE d.id=(NEW.request->>'dossier')::bigint AND d.case_id=NEW.case_id AND r.kind='release_ready'
   AND r.snapshot->'deployment_authorized'='false'::jsonb AND r.snapshot->>'financial_controls'='independent'
   AND a.phase='observed' AND a.result->>'release_ready'=r.id::text AND a.result->>'head'=NEW.source_head_id::text)
 THEN RAISE EXCEPTION 'Native source-bound release evidence required; no deployment authority is granted'; END IF;
"""
MARKER=' RETURN NEW;'
assert SQL.count(MARKER)==1
SQL=SQL.replace(MARKER,VERIFIED+MARKER)

class Migration(migrations.Migration):
    dependencies=[('workflows','0041_factory_commercial')]
    operations=[migrations.RunSQL(SQL)]

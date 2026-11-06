"""Seventh closed native handover envelope, preserving prior factory guards."""
from importlib import import_module
from django.db import migrations

SQL=import_module('apps.workflows.migrations.0044_factory_archive').SQL
OLD="'pmo-finance/v1','planning/v1','commercial/v1','delivery-release/v1','delivery-hypercare/v1','delivery-archive/v1'"
assert SQL.count(OLD)==1
SQL=SQL.replace(OLD,OLD+",'delivery-handover/v1'")
OLD="WHEN 'delivery-archive/v1' THEN 'OPS.factory_archive_execution'"
assert SQL.count(OLD)==1
SQL=SQL.replace(OLD,OLD+" WHEN 'delivery-handover/v1' THEN 'OPS.factory_handover_execution'")
SOURCE=r"""
 IF NEW.definition='delivery-handover/v1' THEN
  IF NEW.invoice_id IS NOT NULL OR NEW.preparation_id IS NOT NULL OR NOT EXISTS(
   SELECT 1 FROM core_evidence e JOIN core_audit a ON a.case_id=e.case_id AND a.actor_id=e.created_by_id
   JOIN pmo_deliverydossier d ON d.id=(NEW.request->>'dossier')::bigint
   WHERE e.id=NEW.source_head_id AND e.case_id=NEW.case_id AND e.kind='agent_private_handover_intake'
    AND e.body::jsonb->>'protocol'='factory-handover-intake/v1' AND e.body::jsonb->>'dossier_id'=d.id::text
    AND e.body::jsonb-ARRAY['protocol','dossier_id','inputs']='{}'::jsonb
    AND jsonb_typeof(e.body::jsonb->'inputs')='object' AND d.case_id=NEW.case_id
    AND a.action IN ('factory.handover_intake','factory.handover_source')
    AND a.data=jsonb_build_object('evidence_id',e.id,'sha256',e.sha256))
  THEN RAISE EXCEPTION 'Native same-case handover input provenance and dossier required'; END IF;
 END IF;
"""
MARKER=" IF NEW.status='verified' THEN"
assert SQL.count(MARKER)==1
SQL=SQL.replace(MARKER,SOURCE+MARKER)
VERIFIED=r"""
 IF NEW.definition='delivery-handover/v1' AND NEW.status='verified' AND NOT EXISTS(
  SELECT 1 FROM documents_publication p JOIN documents_publicationreceipt r ON r.publication_id=p.id
  JOIN pmo_deliverydocumentbinding b ON b.version_id=p.version_id
  JOIN pmo_deliveryrecord h ON h.dossier_id=b.dossier_id AND h.kind='handover'
  JOIN workflows_factoryactivity fa ON fa.work_id=NEW.id JOIN workflows_factoryattempt a ON a.activity_id=fa.id
  WHERE p.factory_work_id=NEW.id AND p.factory_source_id=NEW.source_head_id AND b.purpose='handover'
   AND b.dossier_id=(NEW.request->>'dossier')::bigint AND h.data->>'receipt_id'=r.id::text
   AND h.data->>'status'='received' AND h.actor_id=r.recipient_id
   AND a.phase='observed' AND fa.kind='ACT13' AND a.result->'verified'='true'::jsonb
   AND a.result->>'publication'=p.id::text AND a.result->>'head'=NEW.source_head_id::text)
 THEN RAISE EXCEPTION 'Observed exact native handover and actual recipient acknowledgement required'; END IF;
"""
assert SQL.count(' RETURN NEW;')==1
SQL=SQL.replace(' RETURN NEW;',VERIFIED+' RETURN NEW;')

class Migration(migrations.Migration):
    dependencies=[('workflows','0044_factory_archive'),('documents','0015_factory_publication_scope')]
    operations=[migrations.RunSQL(SQL)]

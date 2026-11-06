"""Ninth closed native envelope; go-live sign-off remains a human native record."""
from importlib import import_module
from django.db import migrations

previous=import_module('apps.workflows.migrations.0046_factory_closure')
SQL=previous.SQL
OLD="'pmo-finance/v1','planning/v1','commercial/v1','delivery-release/v1','delivery-hypercare/v1','delivery-archive/v1','delivery-handover/v1','delivery-closure/v1'"
assert SQL.count(OLD)==1
SQL=SQL.replace(OLD,OLD+",'delivery-go-live/v1'")
OLD="WHEN 'delivery-closure/v1' THEN 'OPS.factory_closure_execution'"
assert SQL.count(OLD)==1
SQL=SQL.replace(OLD,OLD+" WHEN 'delivery-go-live/v1' THEN 'OPS.factory_go_live_execution'")
source=import_module('apps.workflows.migrations.0045_factory_handover').SOURCE
source=source.replace('delivery-handover/v1','delivery-go-live/v1').replace('factory-handover-intake/v1','factory-go-live-intake/v1').replace('handover','go_live')
MARKER=" IF NEW.status='verified' THEN"
assert SQL.count(MARKER)==1
SQL=SQL.replace(MARKER,source+MARKER)
VERIFIED=r"""
 IF NEW.definition='delivery-go-live/v1' AND NEW.status='verified' AND NOT EXISTS(
  SELECT 1 FROM documents_publication p JOIN documents_publicationreceipt r ON r.publication_id=p.id
  JOIN documents_version v ON v.id=p.version_id JOIN pmo_deliverydocumentbinding b ON b.version_id=v.id
  JOIN pmo_deliveryrecord g ON g.dossier_id=b.dossier_id AND g.kind='go_live'
  JOIN core_evidence pm ON pm.id=(g.data->>'pm_signature_id')::bigint
  JOIN core_evidence client ON client.id=(g.data->>'client_signature_id')::bigint
  JOIN core_evidence head ON head.id=NEW.source_head_id
  JOIN workflows_factoryactivity fa ON fa.work_id=NEW.id AND fa.kind='ACT13'
  JOIN workflows_factoryattempt a ON a.activity_id=fa.id AND a.phase='observed'
  WHERE p.factory_work_id=NEW.id AND p.factory_source_id=NEW.source_head_id AND b.purpose='go_live' AND v.audience='client'
   AND b.dossier_id=(NEW.request->>'dossier')::bigint AND g.data->>'receipt_id'=r.id::text AND g.snapshot=b.snapshot
   AND b.data=(head.body::jsonb->'inputs')-'template_id' AND v.template_id=(head.body::jsonb->'inputs'->>'template_id')::bigint
   AND pm.case_id=NEW.case_id AND client.case_id=NEW.case_id AND pm.kind='signature' AND client.kind='signature' AND pm.id<>client.id
   AND a.result->'verified'='true'::jsonb AND a.result->>'acceptance'=g.id::text
   AND a.result->>'document_version'=v.id::text AND a.result->>'head'=NEW.source_head_id::text)
 THEN RAISE EXCEPTION 'Observed exact native go-live acceptance, distinct actual signature evidence and source-bound client receipt required'; END IF;
"""
assert SQL.count(' RETURN NEW;')==1
SQL=SQL.replace(' RETURN NEW;',VERIFIED+' RETURN NEW;')

class Migration(migrations.Migration):
    dependencies=[('workflows','0046_factory_closure'),('documents','0016_factory_handover_scope')]
    operations=[migrations.RunSQL(SQL)]

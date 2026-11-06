"""Expand explicit publication scope; commercial contract stays equally constrained."""
from django.db import migrations

SQL=r"""
CREATE OR REPLACE FUNCTION psl_publication_factory_scope() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
 IF (NEW.factory_work_id IS NULL) IS DISTINCT FROM (NEW.factory_policy_id IS NULL)
  OR (NEW.factory_work_id IS NULL) IS DISTINCT FROM (NEW.factory_source_id IS NULL)
 THEN RAISE EXCEPTION 'Complete optional factory publication scope required'; END IF;
 IF NEW.factory_work_id IS NOT NULL AND NOT EXISTS(
  SELECT 1 FROM workflows_factorywork w JOIN documents_version v ON v.id=NEW.version_id JOIN documents_document d ON d.id=v.document_id
   JOIN policy_configuration p ON p.id=NEW.factory_policy_id JOIN core_evidence e ON e.id=NEW.factory_source_id
   WHERE w.id=NEW.factory_work_id AND w.case_id=d.case_id AND p.case_id=w.case_id AND e.case_id=w.case_id
   AND (
    (w.definition='commercial/v1' AND p.component='OPS.factory_commercial_execution' AND e.kind='agent_private_commercial_intake'
     AND EXISTS(SELECT 1 FROM pmo_commercialdocumentbinding b JOIN pmo_commercialrevision r ON r.id=b.revision_id JOIN pmo_commercialcase c ON c.id=r.dossier_id WHERE b.version_id=v.id AND c.case_id=w.case_id))
    OR
    (w.definition='delivery-handover/v1' AND p.component='OPS.factory_handover_execution' AND e.kind='agent_private_handover_intake'
     AND w.policy_id=p.id AND w.source_head_id=e.id
     AND EXISTS(SELECT 1 FROM pmo_deliverydocumentbinding b JOIN pmo_deliverydossier dd ON dd.id=b.dossier_id
      WHERE b.version_id=v.id AND b.purpose='handover' AND dd.case_id=w.case_id AND b.dossier_id=(w.request->>'dossier')::bigint)
     AND EXISTS(SELECT 1 FROM workflows_factoryactivity fa JOIN workflows_factoryattempt a ON a.activity_id=fa.id
      WHERE fa.work_id=w.id AND fa.kind='ACT09' AND a.phase='observed' AND a.result->>'document_version'=v.id::text AND a.result->>'head'=e.id::text))
   ))
 THEN RAISE EXCEPTION 'Exact same-case registered factory publication references required'; END IF;
 RETURN NEW;
END $$;
"""

class Migration(migrations.Migration):
    dependencies=[('documents','0015_factory_publication_scope'),('workflows','0045_factory_handover')]
    operations=[migrations.RunSQL(SQL)]

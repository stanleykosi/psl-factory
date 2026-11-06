from django.db import migrations

SQL=r"""
CREATE OR REPLACE FUNCTION psl_factory_identity() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
 IF TG_OP='DELETE' THEN RAISE EXCEPTION 'Factory history cannot be deleted'; END IF;
 IF TG_OP='UPDATE' THEN
  IF (NEW.case_id,NEW.actor_id,NEW.key,NEW.definition,NEW.request,NEW.request_hash,NEW.created_at)
    IS DISTINCT FROM (OLD.case_id,OLD.actor_id,OLD.key,OLD.definition,OLD.request,OLD.request_hash,OLD.created_at)
    OR NEW.budget_used<OLD.budget_used OR NEW.fence<OLD.fence OR NEW.revision<OLD.revision
    OR (OLD.budget_used>0 AND NEW.budget_limit<>OLD.budget_limit)
  THEN RAISE EXCEPTION 'Immutable factory identity and monotonic shared budget required'; END IF;
  IF OLD.source_head_id IS NOT NULL AND NEW.source_head_id IS DISTINCT FROM OLD.source_head_id
   AND (NEW.source_head_id IS NULL OR NOT EXISTS(SELECT 1 FROM core_evidence n JOIN core_evidence o ON o.id=OLD.source_head_id WHERE n.id=NEW.source_head_id AND n.version>o.version))
  THEN RAISE EXCEPTION 'Forward native source successor required'; END IF;
 END IF;
 IF NEW.definition NOT IN ('pmo-finance/v1','planning/v1','commercial/v1') THEN RAISE EXCEPTION 'Closed factory definition required'; END IF;
 IF (NEW.invoice_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM finance_invoice i WHERE i.id=NEW.invoice_id AND i.case_id=NEW.case_id))
  OR (NEW.preparation_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM finance_billingpreparation p WHERE p.id=NEW.preparation_id AND p.case_id=NEW.case_id))
  OR (NEW.policy_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM policy_configuration p WHERE p.id=NEW.policy_id AND p.case_id=NEW.case_id
    AND p.component=CASE NEW.definition WHEN 'planning/v1' THEN 'OPS.factory_planning_execution' WHEN 'commercial/v1' THEN 'OPS.factory_commercial_execution' ELSE 'OPS.factory_execution' END))
 THEN RAISE EXCEPTION 'Same-case native factory references required'; END IF;
 IF NEW.definition='pmo-finance/v1' AND NEW.source_head_id IS NOT NULL THEN RAISE EXCEPTION 'Invoice work cannot carry a domain source head'; END IF;
 IF NEW.definition='planning/v1' THEN
  IF NEW.invoice_id IS NOT NULL OR NEW.preparation_id IS NOT NULL OR NOT EXISTS(
    SELECT 1 FROM core_evidence e JOIN core_audit a ON a.case_id=e.case_id AND a.actor_id=e.created_by_id
    WHERE e.id=NEW.source_head_id AND e.case_id=NEW.case_id AND e.kind='planning_packet' AND a.action='planning.recorded'
    AND a.data=jsonb_build_object('kind','packet','evidence_id',e.id,'sha256',e.sha256) AND e.body::jsonb->'engagement_id'=NEW.request->'engagement')
  THEN RAISE EXCEPTION 'Native same-engagement planning packet required'; END IF;
 END IF;
 IF NEW.definition='commercial/v1' THEN
  IF NEW.invoice_id IS NOT NULL OR NEW.preparation_id IS NOT NULL OR NOT EXISTS(
    SELECT 1 FROM core_evidence e JOIN core_audit a ON a.case_id=e.case_id AND a.actor_id=e.created_by_id
    WHERE e.id=NEW.source_head_id AND e.case_id=NEW.case_id AND e.kind='agent_private_commercial_intake'
    AND e.body::jsonb->>'protocol'='factory-commercial-intake/v1' AND a.action='factory.commercial_intake'
    AND a.data=jsonb_build_object('evidence_id',e.id,'sha256',e.sha256))
  THEN RAISE EXCEPTION 'Native private commercial intake required'; END IF;
 END IF;
 IF NEW.status='verified' THEN
  IF NEW.definition='pmo-finance/v1' AND NOT EXISTS(
    SELECT 1 FROM finance_invoiceissue i JOIN finance_invoicedelivery d ON d.invoice_id=i.invoice_id JOIN finance_invoice n ON n.id=i.invoice_id
    WHERE n.id=NEW.invoice_id AND n.case_id=NEW.case_id AND i.sha256=n.sha256 AND i.payload=n.payload)
  THEN RAISE EXCEPTION 'Native invoice receipts required; agent completion is not verification'; END IF;
  IF NEW.definition='planning/v1' AND NOT EXISTS(
    SELECT 1 FROM pmo_deliverysource s JOIN pmo_deliverydossier d ON d.id=s.dossier_id JOIN core_evidence e ON e.id=s.evidence_id
    JOIN core_audit a ON a.case_id=e.case_id AND a.actor_id=e.created_by_id
    WHERE d.case_id=NEW.case_id AND e.case_id=NEW.case_id AND e.kind='planning_readiness' AND s.kind='scope_baseline'
    AND e.body::jsonb->>'packet_id'=NEW.source_head_id::text AND e.body::jsonb->'inputs'->>'candidate_id'=d.candidate_id::text
    AND s.external_ref='psl:planning-readiness:'||e.id::text AND a.action='planning.recorded'
    AND a.data=jsonb_build_object('kind','ready','evidence_id',e.id,'sha256',e.sha256))
  THEN RAISE EXCEPTION 'Native planning readiness and delivery source required'; END IF;
  IF NEW.definition='commercial/v1' AND NOT EXISTS(
    SELECT 1 FROM pmo_commercialdocumentbinding b JOIN documents_version v ON v.id=b.version_id JOIN documents_document doc ON doc.id=v.document_id
    JOIN documents_publication p ON p.version_id=v.id JOIN pmo_commercialrevision r ON r.id=b.revision_id
    JOIN pmo_commercialcase c ON c.id=r.dossier_id JOIN pmo_costingbinding cb ON cb.costing_id=(r.sources->>'costing')::bigint
    JOIN pmo_costingrun cr ON cr.id=cb.run_id JOIN core_evidence e ON e.id=NEW.source_head_id
    WHERE c.case_id=NEW.case_id AND doc.case_id=NEW.case_id AND cr.case_id=NEW.case_id AND c.current_id=r.id AND cr.result->>'status'='known'
    AND r.sources->'requirements'=e.body::jsonb->'sources'->'requirements' AND r.sources->'plan'=e.body::jsonb->'sources'->'plan'
    AND r.sources->'engineering_estimate'=e.body::jsonb->'sources'->'engineering_estimate' AND r.sources->'security_estimate'=e.body::jsonb->'sources'->'security_estimate'
    AND r.sources->'sow'=e.body::jsonb->'sources'->'sow' AND cr.evidence_id::text=e.body::jsonb->'sources'->>'inputs'
    AND jsonb_array_length(p.recipient_ids)>0 AND NOT EXISTS(
      SELECT 1 FROM jsonb_array_elements_text(p.recipient_ids) AS destinations(recipient) WHERE NOT EXISTS(
       SELECT 1 FROM documents_publicationreceipt pr WHERE pr.publication_id=p.id AND pr.recipient_id::text=destinations.recipient
       AND pr.payload_sha256=v.payload_sha256 AND pr.payload=v.payload)))
  THEN RAISE EXCEPTION 'Exact native costing, commercial document and all recipient receipts required'; END IF;
 END IF;
 RETURN NEW;
END $$;
"""

class Migration(migrations.Migration):
    dependencies=[('workflows','0040_factory_planning')]
    operations=[migrations.RunSQL(SQL)]

"""Closed RFP production references and native outcome/receipt verification."""
from importlib import import_module
from django.db import migrations

SQL=import_module('apps.workflows.migrations.0059_delivery_intake_reaffirmation').SQL
OLD="'delivery-go-live/v1','finance-accounts/v1') THEN"
assert SQL.count(OLD)==1
SQL=SQL.replace(OLD,"'delivery-go-live/v1','finance-accounts/v1','rfp-response/v1') THEN")
OLD="WHEN 'finance-accounts/v1' THEN 'OPS.factory_accounting_execution'"
assert SQL.count(OLD)==1
SQL=SQL.replace(OLD,OLD+" WHEN 'rfp-response/v1' THEN 'OPS.factory_rfp_execution'")
GUARD=r"""
 IF NEW.definition='rfp-response/v1' THEN
  IF NEW.invoice_id IS NOT NULL OR NEW.preparation_id IS NOT NULL OR NOT EXISTS(
   SELECT 1 FROM core_evidence e JOIN core_audit a ON a.case_id=e.case_id AND a.actor_id=e.created_by_id
   JOIN pmo_rfpcase r ON r.id=(NEW.request->>'rfp')::bigint AND r.case_id=NEW.case_id
   JOIN pmo_rfpintake i ON i.id=(e.body::jsonb->>'intake')::bigint AND i.rfp_id=r.id
   WHERE e.id=NEW.source_head_id AND e.case_id=NEW.case_id AND e.kind='agent_private_rfp_intake'
    AND e.body::jsonb->>'schema'='factory-rfp-intake/v1' AND e.body::jsonb->'rfp'=NEW.request->'rfp'
    AND NEW.request-ARRAY['rfp','reference']='{}'::jsonb
    AND e.body::jsonb-ARRAY['schema','rfp','intake','response_evidence','public_terms','sources','matrix','lessons']='{}'::jsonb
    AND jsonb_typeof(e.body::jsonb->'sources')='object' AND jsonb_typeof(e.body::jsonb->'matrix')='array'
    AND a.action='factory.rfp_inputs_recorded' AND a.data=jsonb_build_object('evidence_id',e.id,'sha256',e.sha256))
  THEN RAISE EXCEPTION 'Exact native same-case RFP instruction provenance required'; END IF;
  IF TG_OP='UPDATE' AND NEW.source_head_id IS DISTINCT FROM OLD.source_head_id THEN
   IF OLD.status IN ('verified','cancelled','followup_needed') OR NEW.cancel_requested OR NEW.status<>'ready'
    OR (OLD.lease_until IS NOT NULL AND OLD.lease_until>statement_timestamp())
    OR NOT EXISTS(SELECT 1 FROM core_audit a JOIN core_evidence e ON e.id=NEW.source_head_id AND e.created_by_id=a.actor_id
      WHERE a.case_id=NEW.case_id AND a.action='factory.rfp_instruction_changed'
       AND a.data->>'work'=NEW.id::text AND a.data->>'previous'=OLD.source_head_id::text
       AND a.data->>'current'=NEW.source_head_id::text AND length(btrim(a.data->>'reason')) BETWEEN 1 AND 4000)
    OR EXISTS(SELECT 1 FROM documents_publication p JOIN documents_publicationjob j ON j.publication_id=p.id
      WHERE p.factory_work_id=NEW.id AND (j.status IN ('pending','unknown','leased','held') OR
       j.status='confirmed' AND NOT EXISTS(SELECT 1 FROM pmo_rfpsubmission s WHERE s.version_id=p.version_id)))
    OR EXISTS(SELECT 1 FROM workflows_factoryattempt a JOIN workflows_factoryactivity t ON t.id=a.activity_id
      WHERE t.work_id=NEW.id AND t.kind='ACT03' AND a.phase='started' AND a.result->>'schema'='factory-provider-request/v1'
       AND NOT EXISTS(SELECT 1 FROM workflows_factoryattempt done WHERE done.activity_id=a.activity_id AND done.number=a.number AND done.phase IN ('observed','failed'))
       AND NOT EXISTS(SELECT 1 FROM workflows_factoryplanningreceipt pr WHERE pr.attempt_id=a.id))
   THEN RAISE EXCEPTION 'Fresh human RFP instruction and reconciled original effects required'; END IF;
  END IF;
  IF NEW.status='verified' AND NOT EXISTS(
   SELECT 1 FROM pmo_rfpdisposition d JOIN pmo_rfpoutcome o ON o.id=d.outcome_id
   JOIN pmo_rfpsubmission s ON s.id=o.submission_id JOIN pmo_rfpresponse r ON r.id=s.response_id
   JOIN pmo_rfpcase root ON root.id=r.rfp_id JOIN core_evidence h ON h.id=NEW.source_head_id
   JOIN documents_version v ON v.id=s.version_id JOIN documents_document doc ON doc.id=v.document_id
   JOIN documents_publication p ON p.version_id=v.id JOIN documents_publicationjob j ON j.publication_id=p.id
   JOIN workflows_factoryactivity t ON t.work_id=NEW.id AND t.kind='ACT13'
   JOIN workflows_factoryattempt a ON a.activity_id=t.id AND a.phase='observed'
   WHERE root.case_id=NEW.case_id AND root.id=(NEW.request->>'rfp')::bigint AND d.rfp_id=root.id
    AND root.current_response_id=r.id AND root.current_intake_id=r.intake_id
    AND doc.case_id=NEW.case_id AND doc.current_id=v.id AND r.evidence_id=(h.body::jsonb->>'response_evidence')::bigint
    AND r.matrix=h.body::jsonb->'matrix' AND j.status='confirmed' AND jsonb_array_length(p.recipient_ids)>0
    AND (p.factory_work_id=NEW.id OR p.factory_work_id IS NULL)
    AND d.snapshot->>'response'=r.id::text AND d.snapshot->>'submission'=s.id::text
    AND d.snapshot->'baseline_imported'='false'::jsonb AND (d.kind='route_a' AND o.result='won' OR d.kind='loss_archive' AND o.result='lost' AND d.lessons_id IS NOT NULL)
    AND NOT EXISTS(SELECT 1 FROM jsonb_array_elements_text(p.recipient_ids) x WHERE NOT EXISTS(
     SELECT 1 FROM documents_publicationreceipt pr WHERE pr.publication_id=p.id AND pr.recipient_id=x.value::bigint AND pr.payload=v.payload AND pr.payload_sha256=v.payload_sha256))
    AND s.receipt_ids=(SELECT jsonb_agg(pr.id ORDER BY pr.id) FROM documents_publicationreceipt pr WHERE pr.publication_id=p.id)
    AND (SELECT count(*) FROM documents_publicationreceipt pr WHERE pr.publication_id=p.id)=jsonb_array_length(p.recipient_ids)
    AND a.result->'verified'='true'::jsonb AND a.result->>'head'=NEW.source_head_id::text
    AND a.result->>'disposition'=d.id::text AND a.result->>'submission'=s.id::text
    AND a.result->>'outcome'=o.id::text AND a.result->>'document_version'=v.id::text
    AND a.result->>'publication'=p.id::text AND a.result->'receipt_ids'=s.receipt_ids)
  THEN RAISE EXCEPTION 'Native RFP customer outcome, downstream route and all exact receipts required'; END IF;
 END IF;
"""
assert SQL.count(' RETURN NEW;')==1
SQL=SQL.replace(' RETURN NEW;',GUARD+' RETURN NEW;')

class Migration(migrations.Migration):
    dependencies=[('workflows','0059_delivery_intake_reaffirmation')]
    operations=[migrations.RunSQL(SQL)]

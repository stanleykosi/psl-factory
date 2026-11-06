"""P49 verifies the actual submitted response, not a later unsent draft or old staff grants."""
from importlib import import_module
from django.db import migrations

SQL=import_module('apps.workflows.migrations.0061_rfp_exact_verification').SQL
START="  IF NEW.status='verified' AND NOT EXISTS("
start=SQL.index(START,SQL.index(" IF NEW.definition='rfp-response/v1' THEN"))
END="  THEN RAISE EXCEPTION 'Native RFP customer outcome, downstream route and all exact receipts required'; END IF;"
end=SQL.index(END,start)+len(END)
VERIFIED=r"""
  IF NEW.status='verified' AND NOT EXISTS(
   SELECT 1 FROM pmo_rfpdisposition d JOIN pmo_rfpoutcome o ON o.id=d.outcome_id
   JOIN pmo_rfpsubmission s ON s.id=o.submission_id JOIN pmo_rfpresponse r ON r.id=s.response_id
   JOIN pmo_rfpcase root ON root.id=r.rfp_id JOIN core_evidence h ON h.id=NEW.source_head_id
   JOIN pmo_commercialrevision cr ON cr.id=r.commercial_id
   JOIN pmo_rfpdocumentbinding b ON b.response_id=r.id AND b.version_id=s.version_id
   JOIN documents_version v ON v.id=s.version_id JOIN documents_document doc ON doc.id=v.document_id
   JOIN documents_publication p ON p.version_id=v.id JOIN documents_publicationjob j ON j.publication_id=p.id
   JOIN documents_controlledreview review ON review.id=p.review_id AND review.version_id=v.id
   JOIN workflows_factoryactivity t ON t.work_id=NEW.id AND t.kind='ACT13'
   JOIN workflows_factoryattempt a ON a.activity_id=t.id AND a.phase='observed'
   WHERE root.case_id=NEW.case_id AND root.id=(NEW.request->>'rfp')::bigint AND d.rfp_id=root.id
    AND doc.case_id=NEW.case_id AND s.snapshot=b.snapshot AND s.snapshot->>'response'=r.id::text
    AND s.snapshot->'sources'=r.snapshot AND d.snapshot->'sources'=r.snapshot AND d.snapshot->'commercial_sources'=cr.sources
    AND jsonb_array_length(s.snapshot->'reviews')=2 AND NOT EXISTS(
     SELECT 1 FROM jsonb_array_elements_text(s.snapshot->'reviews') WITH ORDINALITY item(id,nth)
     WHERE NOT EXISTS(SELECT 1 FROM pmo_rfpreview rr WHERE rr.id=item.id::bigint AND rr.response_id=r.id AND rr.verdict='approve'
      AND rr.role=CASE item.nth WHEN 1 THEN 'PMO Lead' WHEN 2 THEN 'Engineering Lead' END AND rr.created_at<=p.created_at))
    AND jsonb_array_length(s.snapshot->'costing_decisions')=3 AND NOT EXISTS(
     SELECT 1 FROM jsonb_array_elements_text(s.snapshot->'costing_decisions') WITH ORDINALITY item(id,nth)
     WHERE NOT EXISTS(SELECT 1 FROM pmo_commercialdecision cd WHERE cd.id=item.id::bigint AND cd.revision_id=cr.id AND cd.verdict='approve'
      AND cd.role=CASE item.nth WHEN 1 THEN 'PM' WHEN 2 THEN 'Head of PMO' WHEN 3 THEN 'CEO' END AND cd.created_at<=p.created_at))
    AND review.verdict='approve' AND review.payload_sha256=v.payload_sha256 AND review.created_at<=p.created_at
    AND j.status='confirmed' AND jsonb_array_length(p.recipient_ids)>0
    AND (p.factory_work_id=NEW.id OR p.factory_work_id IS NULL)
    AND (p.factory_work_id IS NULL OR EXISTS(SELECT 1 FROM core_evidence origin WHERE origin.id=p.factory_source_id
     AND origin.case_id=NEW.case_id AND origin.kind='agent_private_rfp_intake' AND origin.body::jsonb->'rfp'=NEW.request->'rfp'))
    AND d.snapshot->>'response'=r.id::text AND d.snapshot->>'submission'=s.id::text AND d.snapshot->>'outcome'=o.id::text
    AND d.snapshot->>'case'=NEW.case_id::text AND d.snapshot->'baseline_imported'='false'::jsonb
    AND (d.kind='route_a' AND o.result='won' AND d.snapshot->>'route'='A' OR
     d.kind='loss_archive' AND o.result='lost' AND d.lessons_id=(h.body::jsonb->>'lessons')::bigint)
    AND NOT EXISTS(SELECT 1 FROM jsonb_array_elements_text(p.recipient_ids) x WHERE NOT EXISTS(
     SELECT 1 FROM documents_publicationreceipt pr WHERE pr.publication_id=p.id AND pr.recipient_id=x.value::bigint AND pr.payload=v.payload AND pr.payload_sha256=v.payload_sha256))
    AND s.receipt_ids=(SELECT jsonb_agg(pr.id ORDER BY pr.id) FROM documents_publicationreceipt pr WHERE pr.publication_id=p.id)
    AND (SELECT count(*) FROM documents_publicationreceipt pr WHERE pr.publication_id=p.id)=jsonb_array_length(p.recipient_ids)
    AND a.result->'verified'='true'::jsonb AND a.result->>'head'=NEW.source_head_id::text
    AND a.result->>'response'=r.id::text AND a.result->>'disposition'=d.id::text AND a.result->>'submission'=s.id::text
    AND a.result->>'outcome'=o.id::text AND a.result->>'document_version'=v.id::text
    AND a.result->>'publication'=p.id::text AND a.result->'receipt_ids'=s.receipt_ids)
  THEN RAISE EXCEPTION 'Historical approved RFP submission, actual customer outcome and all exact receipts required'; END IF;
"""
SQL=SQL[:start]+VERIFIED+SQL[end:]

class Migration(migrations.Migration):
    dependencies=[('workflows','0061_rfp_exact_verification')]
    operations=[migrations.RunSQL(SQL)]

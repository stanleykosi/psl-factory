"""Recognise exact versioned PDF receipts without changing original receipt rows."""

from django.db import migrations


LEGACY = "evidence.body::jsonb->>'schema'='psl/rfp-portal-receipt/v1'"
SCOPED = "psl_rfp_portal_file_proof(b.id,evidence.body::jsonb)"

GUARDS = """
CREATE FUNCTION psl_rfp_portal_file_proof(binding_id bigint, proof jsonb) RETURNS boolean
LANGUAGE sql STABLE AS $$
  SELECT COALESCE(CASE WHEN proof->>'schema'='psl/rfp-portal-receipt/v1' THEN true
    ELSE a.id IS NOT NULL AND proof->>'schema'='psl/rfp-portal-receipt/v2'
      AND proof->'artifact_sha256'=to_jsonb(a.sha256)
      AND proof ?& ARRAY['schema','version','sha256','destination','reference','received_at','artifact_sha256']
      AND proof-ARRAY['schema','version','sha256','destination','reference','received_at','artifact_sha256']='{}'::jsonb
      AND p.id IS NOT NULL AND a.payload_sha256=v.payload_sha256
      AND (p.file_extension='' OR p.file_extension='pdf') AND (p.file_count IS NULL OR p.file_count=1)
      AND (p.file_size_bytes IS NULL OR
           (p.file_size_rule='less_than' AND a.size<p.file_size_bytes) OR
           (p.file_size_rule='at_most' AND a.size<=p.file_size_bytes))
    END,false)
  FROM pmo_rfpdocumentbinding b JOIN documents_version v ON v.id=b.version_id
  LEFT JOIN pmo_rfpsubmissionartifact a ON a.binding_id=b.id
  LEFT JOIN pmo_rfpsubmissionpack p ON p.response_id=b.response_id AND to_jsonb(p.id)=b.snapshot->'submission_pack'
  WHERE b.id=$1
$$;

CREATE FUNCTION psl_rfp_portal_receipt_scope() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pmo_rfpsubmission s
    JOIN pmo_rfpdocumentbinding b ON b.version_id=s.version_id AND b.response_id=s.response_id
    JOIN pmo_rfpresponse r ON r.id=s.response_id JOIN pmo_rfpcase root ON root.id=r.rfp_id
    JOIN documents_version v ON v.id=s.version_id JOIN documents_document d ON d.id=v.document_id
    JOIN documents_controlledreview review ON review.id=NEW.review_id AND review.version_id=v.id
    JOIN core_evidence e ON e.id=NEW.evidence_id AND e.case_id=root.case_id AND e.kind='rfp_portal_receipt'
    LEFT JOIN pmo_rfpsubmissionartifact a ON a.binding_id=b.id
    LEFT JOIN pmo_rfpsubmissionpack p ON p.response_id=r.id AND to_jsonb(p.id)=b.snapshot->'submission_pack'
    WHERE s.id=NEW.submission_id AND d.case_id=root.case_id AND s.snapshot=b.snapshot
      AND s.actor_id=NEW.actor_id AND v.audience='client' AND s.receipt_ids='[]'::jsonb
      AND b.snapshot->'route'->>'method'='manual_client_portal'
      AND b.snapshot->'route'->'recipient_ids'='[]'::jsonb
      AND review.verdict='approve' AND review.payload_sha256=v.payload_sha256 AND review.created_at<=s.submitted_at
      AND e.body::jsonb->'version'=to_jsonb(v.id)
      AND e.body::jsonb->>'sha256'=v.payload_sha256
      AND e.body::jsonb->>'destination'=b.snapshot->'route'->>'destination_ref'
      AND e.body::jsonb->>'reference'=NEW.reference
      AND (e.body::jsonb->>'received_at')::timestamptz=s.submitted_at
      AND (p.id IS NULL OR a.id IS NOT NULL OR
           (p.file_extension='' AND p.file_count IS NULL AND p.file_size_bytes IS NULL))
      AND (a.id IS NULL OR e.body::jsonb->>'schema'='psl/rfp-portal-receipt/v2')
      AND psl_rfp_portal_file_proof(b.id,e.body::jsonb)
  ) THEN RAISE EXCEPTION 'Exact native portal receipt and verified client file required'; END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER psl_rfp_portal_receipt_scope BEFORE INSERT ON pmo_rfpportalreceipt
FOR EACH ROW EXECUTE FUNCTION psl_rfp_portal_receipt_scope();
"""

REVERSE = """
DROP TRIGGER psl_rfp_portal_receipt_scope ON pmo_rfpportalreceipt;
DROP FUNCTION psl_rfp_portal_receipt_scope();
DROP FUNCTION psl_rfp_portal_file_proof(bigint,jsonb);
"""


def replace_verification(schema_editor, old, new):
    with schema_editor.connection.cursor() as cursor:
        cursor.execute("SELECT pg_get_functiondef('psl_factory_identity()'::regprocedure)")
        definition = cursor.fetchone()[0]
    if (definition.count(old) != 1 or 'JOIN pmo_rfpdocumentbinding b' not in definition
            or "a.result->>'portal_receipt'=portal.id::text" not in definition):
        raise RuntimeError('Unexpected predecessor for original portal receipt verification')
    schema_editor.execute(definition.replace(old, new), params=None)


def forwards(apps, schema_editor):
    schema_editor.execute(GUARDS, params=None)
    replace_verification(schema_editor, LEGACY, SCOPED)


def backwards(apps, schema_editor):
    replace_verification(schema_editor, SCOPED, LEGACY)
    schema_editor.execute(REVERSE, params=None)


class Migration(migrations.Migration):
    dependencies = [
        ('workflows', '0095_ppe_asset_dates'),
        ('pmo', '0082_rfp_submission_artifact'),
    ]
    operations = [migrations.RunPython(forwards, backwards)]

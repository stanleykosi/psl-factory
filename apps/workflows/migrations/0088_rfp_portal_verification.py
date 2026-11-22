"""Keep the original inbox checks and accept an independently evidenced portal receipt."""
from importlib import import_module

from django.db import migrations


ORIGINAL = import_module('apps.workflows.migrations.0080_factory_issue_reference').IDENTITY
START = "  IF NEW.status='verified' AND NOT EXISTS("
END = "  THEN RAISE EXCEPTION 'Historical approved RFP submission, actual customer outcome and all exact receipts required'; END IF;"
start = ORIGINAL.index(START, ORIGINAL.index(" IF NEW.definition='rfp-response/v1' THEN"))
end = ORIGINAL.index(END, start) + len(END)
section = ORIGINAL[start:end]

old_join = '''   JOIN documents_publication p ON p.version_id=v.id JOIN documents_publicationjob j ON j.publication_id=p.id
   JOIN documents_controlledreview review ON review.id=p.review_id AND review.version_id=v.id'''
new_join = '''   LEFT JOIN documents_publication p ON p.version_id=v.id LEFT JOIN documents_publicationjob j ON j.publication_id=p.id
   LEFT JOIN pmo_rfpportalreceipt portal ON portal.submission_id=s.id
   LEFT JOIN core_evidence evidence ON evidence.id=portal.evidence_id
   JOIN documents_controlledreview review ON review.id=COALESCE(p.review_id,portal.review_id) AND review.version_id=v.id'''

local_start = section.index("    AND j.status='confirmed'")
local_end = section.index("    AND d.snapshot->>'response'", local_start)
receipt_start = section.index('    AND NOT EXISTS(SELECT 1 FROM jsonb_array_elements_text(p.recipient_ids)')
receipt_end = section.index("    AND a.result->'verified'", receipt_start)
local_conditions = section[local_start:local_end] + section[receipt_start:receipt_end]
portal_conditions = '''s.snapshot->'route'->>'method'='manual_client_portal'
      AND p.id IS NULL AND portal.id IS NOT NULL AND portal.actor_id=s.actor_id
      AND s.receipt_ids='[]'::jsonb AND s.snapshot->'route'->'recipient_ids'='[]'::jsonb
      AND portal.created_at>=s.submitted_at AND length(btrim(portal.note)) BETWEEN 1 AND 4000
      AND evidence.case_id=NEW.case_id AND evidence.kind='rfp_portal_receipt'
      AND evidence.body::jsonb->>'schema'='psl/rfp-portal-receipt/v1'
      AND evidence.body::jsonb->>'version'=v.id::text
      AND evidence.body::jsonb->>'sha256'=v.payload_sha256
      AND evidence.body::jsonb->>'destination'=s.snapshot->'route'->>'destination_ref'
      AND evidence.body::jsonb->>'reference'=portal.reference
      AND (evidence.body::jsonb->>'received_at')::timestamptz=s.submitted_at
      AND a.result->>'portal_receipt'=portal.id::text'''
section = (section[:local_start] + section[local_end:receipt_start] +
           "    AND ((s.snapshot->'route'->>'method'='internal_recipient_inbox' AND portal.id IS NULL\n" +
           local_conditions.rstrip() + " AND a.result->>'publication'=p.id::text) OR (" + portal_conditions + '))\n' +
           section[receipt_end:])
section = (section.replace(old_join, new_join).replace('<=p.created_at', '<=COALESCE(p.created_at,s.submitted_at)')
           .replace("    AND a.result->>'publication'=p.id::text AND a.result->'receipt_ids'=s.receipt_ids)",
                    "    AND a.result->'receipt_ids'=s.receipt_ids)"))
SQL = ORIGINAL[:start] + section + ORIGINAL[end:]


class Migration(migrations.Migration):
    dependencies = [('workflows', '0087_draft_progress'), ('pmo', '0053_rfp_portal_receipt')]
    operations = [migrations.RunSQL(SQL, ORIGINAL)]

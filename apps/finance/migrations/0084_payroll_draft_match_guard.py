"""Keep a private draft match out of all payroll release lineages."""

from django.db import migrations


SQL = r"""
CREATE FUNCTION psl_payroll_draft_match_review_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE combined finance_payrollrun; source_status text; pin jsonb; held_count bigint; ready_count bigint;
BEGIN
 IF NEW.verdict='approve' THEN
  IF NEW.input_id IS NOT NULL THEN
   SELECT metadata->>'status' INTO source_status FROM finance_payrollinput WHERE id=NEW.input_id;
  ELSE
   SELECT metadata->>'status' INTO source_status FROM finance_payrollrun WHERE id=NEW.run_id;
  END IF;
  IF source_status IS DISTINCT FROM 'complete' THEN RAISE EXCEPTION 'Held payroll cannot receive a full approval'; END IF;
 END IF;
 IF NEW.verdict <> 'approve_draft_match' THEN RETURN NEW; END IF;
 SELECT * INTO combined FROM finance_payrollrun WHERE id=NEW.run_id AND request_id=NEW.request_id AND kind='combine';
 pin=NEW.authority->'draft_match';
 IF NOT FOUND OR NEW.input_id IS NOT NULL OR combined.parent_id IS NOT NULL
  OR combined.metadata->>'status' IS DISTINCT FROM 'held' OR NEW.subject_sha256 IS DISTINCT FROM combined.sha256
  OR jsonb_typeof(pin) IS DISTINCT FROM 'object'
  OR NOT pin ?& ARRAY['mode','policy_ids','eligible_rows','held_rows','subset_sha256','publication_authorized']
  OR pin - ARRAY['mode','policy_ids','eligible_rows','held_rows','subset_sha256','publication_authorized'] <> '{}'::jsonb
  OR pin->>'mode' IS DISTINCT FROM 'restricted_payroll_draft_match/v1'
  OR pin->'publication_authorized' IS DISTINCT FROM 'false'::jsonb
  OR pin->'policy_ids' IS DISTINCT FROM combined.metadata->'policy_ids'
  OR jsonb_typeof(pin->'subset_sha256') IS DISTINCT FROM 'string' OR pin->>'subset_sha256' !~ '^[a-f0-9]{64}$'
  OR NOT EXISTS(SELECT 1 FROM finance_payrollrequest q JOIN core_evidence e ON e.case_id=q.case_id
                WHERE q.id=NEW.request_id AND e.id=NEW.evidence_id AND e.kind='payroll_review')
 THEN RAISE EXCEPTION 'Exact held payroll combination and draft matching scope required'; END IF;
 SELECT count(*) FILTER (WHERE r->'amount'='null'::jsonb OR r ? 'quarantine_codes'),
        count(*) FILTER (WHERE jsonb_typeof(r->'amount')='string' AND NOT r ? 'quarantine_codes')
 INTO held_count, ready_count FROM jsonb_array_elements(combined.result->'rows') r;
 IF held_count=0 OR ready_count=0 OR pin->'held_rows' IS DISTINCT FROM to_jsonb(held_count)
  OR pin->'eligible_rows' IS DISTINCT FROM to_jsonb(ready_count)
 THEN RAISE EXCEPTION 'Exact held and eligible payroll row counts required'; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER psl_payroll_draft_match_review_guard BEFORE INSERT ON finance_payrollreview
 FOR EACH ROW EXECUTE FUNCTION psl_payroll_draft_match_review_guard();

CREATE FUNCTION psl_payroll_draft_match_run_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE combined finance_payrollrun; approval finance_payrollreview; intent jsonb;
BEGIN
 SELECT * INTO combined FROM finance_payrollrun WHERE id=NEW.parent_id;
 IF combined.metadata->'intent' ? 'draft_review_id'
 THEN RAISE EXCEPTION 'A draft staff match cannot supply another payroll run'; END IF;
 intent=NEW.metadata->'intent';
 IF NOT coalesce(intent ? 'draft_review_id',false) THEN RETURN NEW; END IF;
 IF jsonb_typeof(intent->'draft_review_id') IS DISTINCT FROM 'number'
  OR intent->>'draft_review_id' !~ '^[1-9][0-9]*$'
 THEN RAISE EXCEPTION 'Exact draft matching decision required'; END IF;
 SELECT * INTO approval FROM finance_payrollreview WHERE id=(intent->>'draft_review_id')::bigint AND run_id=NEW.parent_id;
 IF NOT FOUND OR NEW.kind IS DISTINCT FROM 'match' OR NEW.metadata->>'status' IS DISTINCT FROM 'held'
  OR NOT coalesce(NEW.metadata->'codes' ? 'parent_working_set_held',false)
  OR approval.verdict IS DISTINCT FROM 'approve_draft_match' OR approval.request_id IS DISTINCT FROM NEW.request_id
  OR approval.id IS DISTINCT FROM (SELECT max(id) FROM finance_payrollreview WHERE run_id=NEW.parent_id)
  OR combined.kind IS DISTINCT FROM 'combine' OR combined.metadata->>'status' IS DISTINCT FROM 'held'
  OR combined.request_id IS DISTINCT FROM NEW.request_id OR approval.subject_sha256 IS DISTINCT FROM combined.sha256
  OR NEW.metadata->'input_ids' IS DISTINCT FROM combined.metadata->'input_ids'
  OR intent->'parent_id' IS DISTINCT FROM to_jsonb(NEW.parent_id)
  OR NEW.hr_snapshot_id IS NULL OR intent->'hr_snapshot_id' IS DISTINCT FROM to_jsonb(NEW.hr_snapshot_id)
  OR NOT EXISTS(SELECT 1 FROM finance_hrhandoffrecord receipt WHERE receipt.snapshot_id=NEW.hr_snapshot_id
                AND receipt.actor_id=NEW.actor_id AND receipt.kind='receipt')
 THEN RAISE EXCEPTION 'A draft-only match requires its current review, held combination and own staff receipt'; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER psl_payroll_draft_match_run_guard BEFORE INSERT ON finance_payrollrun
 FOR EACH ROW EXECUTE FUNCTION psl_payroll_draft_match_run_guard();

CREATE FUNCTION psl_payroll_draft_match_publication_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF EXISTS(SELECT 1 FROM finance_payrollrun r WHERE r.id=NEW.run_id AND r.metadata->'intent' ? 'draft_review_id')
  OR EXISTS(SELECT 1 FROM finance_payrollreview p WHERE p.id=NEW.review_id AND p.verdict='approve_draft_match')
 THEN RAISE EXCEPTION 'A private payroll draft matching decision cannot authorise publication'; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER psl_payroll_draft_match_publication_guard BEFORE INSERT ON finance_payrollpublication
 FOR EACH ROW EXECUTE FUNCTION psl_payroll_draft_match_publication_guard();
"""

REVERSE = """
DROP TRIGGER psl_payroll_draft_match_publication_guard ON finance_payrollpublication;
DROP FUNCTION psl_payroll_draft_match_publication_guard();
DROP TRIGGER psl_payroll_draft_match_run_guard ON finance_payrollrun;
DROP FUNCTION psl_payroll_draft_match_run_guard();
DROP TRIGGER psl_payroll_draft_match_review_guard ON finance_payrollreview;
DROP FUNCTION psl_payroll_draft_match_review_guard();
"""


class Migration(migrations.Migration):
    dependencies = [('finance', '0083_source_unit_millions')]
    operations = [migrations.RunSQL(SQL, REVERSE)]

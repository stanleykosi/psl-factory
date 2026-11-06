from django.db import migrations
SQL=r"""
CREATE FUNCTION psl_finance_receipt_followup_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE r finance_financereceiptfollowup;
BEGIN
 IF TG_OP<>'INSERT' THEN RAISE EXCEPTION 'Finance receipt follow-up history is immutable'; END IF;
 IF TG_TABLE_NAME='finance_financereceiptfollowup' THEN
   IF NEW.request_key IS DISTINCT FROM NEW.sha256 OR NEW.sha256 !~ '^[a-f0-9]{64}$' OR
      NEW.projection->>'format' IS DISTINCT FROM 'psl.finance-receipt-followup/v1' OR
      NEW.projection->>'source_case_id' IS DISTINCT FROM NEW.case_id::text OR
      coalesce(NEW.projection->>'variant','') NOT IN ('issue','deliver','adjust','adjust_deliver') OR
      coalesce(NEW.projection->>'outcome','') NOT IN ('present','unknown','conflict') OR
      NEW.projection->'business_jobs_reenacted' IS DISTINCT FROM 'false'::jsonb OR NEW.projection->'debt_waived' IS DISTINCT FROM 'false'::jsonb OR
      NEW.projection->'activation_enabled' IS DISTINCT FROM 'false'::jsonb OR
      NOT EXISTS(SELECT 1 FROM core_evidence WHERE id=NEW.evidence_id AND case_id=NEW.case_id AND kind='integration_contract') THEN
      RAISE EXCEPTION 'exact same-case inert Finance follow-up required'; END IF;
 ELSE
   SELECT * INTO r FROM finance_financereceiptfollowup WHERE id=NEW.followup_id;
   IF NEW.verdict NOT IN ('investigate','link_current_intent','decline') OR length(trim(NEW.note))=0 OR
      NEW.pin->>'request_sha256' IS DISTINCT FROM r.sha256 OR
      NEW.pin->'execution_authorized' IS DISTINCT FROM 'false'::jsonb OR NEW.pin->'financial_effect_verified' IS DISTINCT FROM 'false'::jsonb OR
      NOT EXISTS(SELECT 1 FROM policy_configuration WHERE id::text=NEW.pin->>'policy' AND case_id=r.case_id AND component='OPS.finance_receipt_followup') OR
      ((NEW.verdict='link_current_intent') IS DISTINCT FROM (NEW.job_id IS NOT NULL)) OR
      (NEW.job_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM finance_invoicejob j JOIN finance_invoice i ON i.id=j.invoice_id
        WHERE j.id=NEW.job_id AND i.case_id=r.case_id AND i.id::text=r.projection->>'source_invoice_id' AND
        (r.projection->>'source_correction_id' IS NULL OR j.intent->>'correction'=r.projection->>'source_correction_id'))) THEN
      RAISE EXCEPTION 'source-owned non-executing Finance disposition required'; END IF;
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER finance_receipt_followup_guard BEFORE INSERT OR UPDATE OR DELETE ON finance_financereceiptfollowup FOR EACH ROW EXECUTE FUNCTION psl_finance_receipt_followup_guard();
CREATE TRIGGER finance_receipt_followup_decision_guard BEFORE INSERT OR UPDATE OR DELETE ON finance_financereceiptfollowupdecision FOR EACH ROW EXECUTE FUNCTION psl_finance_receipt_followup_guard();
"""
class Migration(migrations.Migration):
    dependencies=[('finance','0054_receipt_followup')]
    operations=[migrations.RunSQL(SQL,reverse_sql=migrations.RunSQL.noop)]

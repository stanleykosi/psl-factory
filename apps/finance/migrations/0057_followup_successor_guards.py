from django.db import migrations
SQL=r"""
CREATE FUNCTION psl_finance_followup_successor_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE p finance_financefollowupsuccessor; r finance_financereceiptfollowup;
 o finance_invoicejob; s finance_invoicejob;
BEGIN
 IF TG_OP<>'INSERT' THEN RAISE EXCEPTION 'Finance successor lineage history is immutable'; END IF;
 IF TG_TABLE_NAME='finance_financefollowupsuccessorreview' THEN
   SELECT * INTO p FROM finance_financefollowupsuccessor WHERE id=NEW.proposal_id;
   SELECT * INTO r FROM finance_financereceiptfollowup WHERE id=p.followup_id;
   IF NEW.actor_id=p.actor_id OR NEW.verdict NOT IN ('approve','hold') OR
      NEW.pin->'subject' IS DISTINCT FROM p.pin OR
      NOT EXISTS(SELECT 1 FROM policy_configuration WHERE id::text=NEW.pin->>'policy' AND case_id=r.case_id AND component='OPS.finance_followup_successors') THEN
     RAISE EXCEPTION 'Independent same-scope lineage review required'; END IF;
 ELSE
   SELECT * INTO r FROM finance_financereceiptfollowup WHERE id=NEW.followup_id;
   SELECT * INTO o FROM finance_invoicejob WHERE id=NEW.original_id;
   SELECT * INTO s FROM finance_invoicejob WHERE id=NEW.successor_id;
   IF o.id=s.id OR o.invoice_id<>s.invoice_id OR
      o.invoice_id::text IS DISTINCT FROM r.projection->>'source_invoice_id' OR
      o.kind IS DISTINCT FROM r.projection->>'variant' OR
      o.intent->'correction' IS DISTINCT FROM nullif(r.projection->'source_correction_id','null'::jsonb) OR
      NOT EXISTS(SELECT 1 FROM finance_invoice WHERE id=o.invoice_id AND case_id=r.case_id) OR
      NEW.pin->>'request_sha256' IS DISTINCT FROM r.sha256 OR
      coalesce(NEW.pin->>'original_intent_sha256','') !~ '^[a-f0-9]{64}$' OR
      coalesce(NEW.pin->>'successor_intent_sha256','') !~ '^[a-f0-9]{64}$' OR
      coalesce(NEW.relation,'') NOT IN ('intent_generation','legal_correction') OR
      (NEW.relation='intent_generation' AND (s.kind<>o.kind OR s.generation<=o.generation OR s.intent->'correction' IS DISTINCT FROM o.intent->'correction')) OR
      (NEW.relation='legal_correction' AND (s.kind NOT IN ('adjust','adjust_deliver') OR
        NOT EXISTS(SELECT 1 FROM finance_invoicecorrection c JOIN finance_invoiceissue i ON i.id=c.issue_id
          WHERE c.id::text=s.intent->>'correction' AND c.case_id=r.case_id AND i.invoice_id=o.invoice_id AND
          c.id::text IS DISTINCT FROM r.projection->>'source_correction_id'))) THEN
     RAISE EXCEPTION 'Exact original and same-obligation successor lineage required'; END IF;
 END IF;
 IF length(trim(NEW.note))=0 OR
    NEW.pin->'execution_authorized' IS DISTINCT FROM 'false'::jsonb OR
    NEW.pin->'financial_effect_verified' IS DISTINCT FROM 'false'::jsonb OR
    NEW.pin->'debt_waived' IS DISTINCT FROM 'false'::jsonb OR
    NOT EXISTS(SELECT 1 FROM core_evidence WHERE id=NEW.evidence_id AND case_id=r.case_id AND kind IN ('integration_contract','financial_correction_review')) THEN
   RAISE EXCEPTION 'Inert same-case evidence and rationale required'; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER finance_followup_successor_guard BEFORE INSERT OR UPDATE OR DELETE ON finance_financefollowupsuccessor FOR EACH ROW EXECUTE FUNCTION psl_finance_followup_successor_guard();
CREATE TRIGGER finance_followup_successor_review_guard BEFORE INSERT OR UPDATE OR DELETE ON finance_financefollowupsuccessorreview FOR EACH ROW EXECUTE FUNCTION psl_finance_followup_successor_guard();
"""
class Migration(migrations.Migration):
    dependencies=[('finance','0056_followup_successors')]
    operations=[migrations.RunSQL(SQL,reverse_sql=migrations.RunSQL.noop)]

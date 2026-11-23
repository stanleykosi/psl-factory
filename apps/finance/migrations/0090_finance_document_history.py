from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [('finance', '0089_finance_document_review')]
    operations = [migrations.RunSQL("""
        CREATE FUNCTION psl_finance_file_history() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          IF TG_OP = 'DELETE' OR
             ROW(NEW.case_id, NEW.key, NEW.sha256, NEW.size, NEW.name, NEW.uploader_id)
             IS DISTINCT FROM ROW(OLD.case_id, OLD.key, OLD.sha256, OLD.size, OLD.name, OLD.uploader_id)
          THEN RAISE EXCEPTION 'Finance original is immutable'; END IF;
          IF OLD.status IN ('approved','returned') AND
             (to_jsonb(NEW) - 'receipt_id' - 'updated_at') IS DISTINCT FROM
             (to_jsonb(OLD) - 'receipt_id' - 'updated_at')
          THEN RAISE EXCEPTION 'Finance decision is immutable'; END IF;
          IF OLD.receipt_id IS NOT NULL AND NEW.receipt_id IS DISTINCT FROM OLD.receipt_id
          THEN RAISE EXCEPTION 'Finance receipt is immutable'; END IF;
          RETURN NEW;
        END $$;
        CREATE TRIGGER finance_file_history BEFORE UPDATE OR DELETE ON finance_financedocument
        FOR EACH ROW EXECUTE FUNCTION psl_finance_file_history();
        CREATE FUNCTION psl_reviewed_figure_history() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          IF TG_OP <> 'INSERT' THEN RAISE EXCEPTION 'Approved Finance figures are immutable'; END IF;
          IF NOT EXISTS (SELECT FROM finance_financedocument d, jsonb_array_elements(d.approved->'rows') r
              WHERE d.id=NEW.document_id AND d.status='approved' AND d.reviewer_id IS NOT NULL
              AND d.approved->>'currency'=NEW.currency AND d.approved->>'period'=NEW.period
              AND r->>'account'=NEW.account AND (r->>'full_amount')::numeric=NEW.amount AND r->>'citation'=NEW.citation)
          THEN RAISE EXCEPTION 'Figure must match the approved document'; END IF;
          RETURN NEW;
        END $$;
        CREATE TRIGGER reviewed_figure_history BEFORE INSERT OR UPDATE OR DELETE ON finance_reviewedfinancefigure
        FOR EACH ROW EXECUTE FUNCTION psl_reviewed_figure_history();
    """, """
        DROP TRIGGER reviewed_figure_history ON finance_reviewedfinancefigure;
        DROP FUNCTION psl_reviewed_figure_history();
        DROP TRIGGER finance_file_history ON finance_financedocument;
        DROP FUNCTION psl_finance_file_history();
    """)]

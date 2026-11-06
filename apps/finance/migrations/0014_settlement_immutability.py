from django.db import migrations

class Migration(migrations.Migration):
    dependencies=[('finance','0013_cashallocation_cashreceipt_cashassignment_and_more')]
    operations=[migrations.RunSQL(
        f'CREATE TRIGGER psl_immutable BEFORE UPDATE OR DELETE ON finance_{name} FOR EACH ROW EXECUTE FUNCTION psl_append_only()',
        f'DROP TRIGGER psl_immutable ON finance_{name}') for name in ['invoice','invoicereview','invoiceissue','invoicedelivery','cashreceipt','cashverification','cashassignment','cashallocation','cashreversal','receivablesnapshot']]+[migrations.RunSQL("""
CREATE FUNCTION psl_invoice_job_intent_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF TG_OP='DELETE' OR (NEW.invoice_id,NEW.kind,NEW.generation,NEW.intent,NEW.operation_key,NEW.actor_id,NEW.created_at) IS DISTINCT FROM (OLD.invoice_id,OLD.kind,OLD.generation,OLD.intent,OLD.operation_key,OLD.actor_id,OLD.created_at) THEN
  RAISE EXCEPTION 'Invoice reservation intent is immutable';
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER psl_intent BEFORE UPDATE OR DELETE ON finance_invoicejob FOR EACH ROW EXECUTE FUNCTION psl_invoice_job_intent_guard();
""","DROP TRIGGER psl_intent ON finance_invoicejob; DROP FUNCTION psl_invoice_job_intent_guard();")]

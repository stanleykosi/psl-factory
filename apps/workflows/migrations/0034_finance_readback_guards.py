from django.db import migrations
SQL=r"""
CREATE FUNCTION psl_finance_readback_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE o workflows_financefollowupreadback; p workflows_nativefinancepacket; m workflows_nativefinancemapping;
BEGIN
 IF TG_OP<>'INSERT' THEN RAISE EXCEPTION 'native Finance readback history is immutable'; END IF;
 IF TG_TABLE_NAME='workflows_financefollowupreadbackreview' THEN
   SELECT * INTO o FROM workflows_financefollowupreadback WHERE id=NEW.observation_id;
   IF NEW.actor_id=o.actor_id OR NEW.verdict NOT IN ('approve','hold') OR length(trim(NEW.rationale))=0 OR
      NEW.pin - 'result_sha256' IS DISTINCT FROM o.pin OR coalesce(NEW.pin->>'result_sha256','') !~ '^[a-f0-9]{64}$' THEN
      RAISE EXCEPTION 'independent exact readback evidence review required'; END IF;
   RETURN NEW;
 END IF;
 SELECT * INTO p FROM workflows_nativefinancepacket WHERE id=NEW.packet_id;
 SELECT * INTO m FROM workflows_nativefinancemapping WHERE id=p.mapping_id;
 IF m.payload->>'contract_version' IS DISTINCT FROM 'psl.internal-finance-invoice/v1' OR
    NEW.pin->>'packet_sha256' IS DISTINCT FROM p.sha256 OR NEW.projection->>'packet_sha256' IS DISTINCT FROM p.sha256 OR
    NEW.projection->>'mapping_sha256' IS DISTINCT FROM m.sha256 OR
    NEW.projection->>'source_case_id' IS DISTINCT FROM m.payload->>'source_case_id' OR
    NEW.projection->>'source_invoice_id' IS DISTINCT FROM m.payload->>'source_invoice_id' OR
    NEW.projection->'source_correction_id' IS DISTINCT FROM m.payload->'source_correction_id' OR
    NEW.projection->>'variant' IS DISTINCT FROM m.payload->>'variant' OR
    NEW.pin->'native'->>'mapping_sha256' IS DISTINCT FROM m.sha256 OR
    NOT EXISTS(SELECT 1 FROM policy_configuration c JOIN workflows_reconstitutionplan r ON r.id=m.plan_id
       WHERE c.id::text=NEW.pin->>'policy' AND c.case_id=r.case_id AND c.component='OPS.native_finance_readback') OR
    NOT EXISTS(SELECT 1 FROM workflows_nativefinancepublicationjob j WHERE j.packet_id=p.id AND j.status='confirmed' AND j.receipt IS NOT NULL
       AND j.operation_key=NEW.projection->>'publication_operation') OR
    NEW.result->>'format' IS DISTINCT FROM 'psl.native-finance-followup-readback/v1' OR
    NEW.result->>'classification' IS DISTINCT FROM 'native_postgres_finance_followup' OR
    coalesce(NEW.result->>'outcome','') NOT IN ('unknown','conflict','acknowledged') OR
    coalesce(NEW.result->>'disposition','') NOT IN ('absent','current','revoked','stale','unavailable') OR
    NEW.result->>'request_sha256' IS DISTINCT FROM NEW.pin->>'request_sha256' OR
    NEW.result->'direct_native_verification' IS DISTINCT FROM 'true'::jsonb OR NEW.result->'direct_vendor_verification' IS DISTINCT FROM 'false'::jsonb OR
    NEW.result->'execution_authorized' IS DISTINCT FROM 'false'::jsonb OR NEW.result->'financial_effect_verified' IS DISTINCT FROM 'false'::jsonb OR
    NEW.result->'business_jobs_reenacted' IS DISTINCT FROM 'false'::jsonb OR NEW.result->'debt_waived' IS DISTINCT FROM 'false'::jsonb OR
    ((NEW.result->>'outcome'='acknowledged') IS DISTINCT FROM (jsonb_typeof(NEW.result->'request_ref')='string' AND coalesce(NEW.result->>'request_row_sha256','') ~ '^[a-f0-9]{64}$')) OR
    NEW.result->'current_authority_verified' IS DISTINCT FROM to_jsonb(NEW.result->>'outcome'='acknowledged' AND NEW.result->>'disposition'='current' AND jsonb_typeof(NEW.result->'decision_ref')='string') THEN
    RAISE EXCEPTION 'typed exact published non-executing Finance readback required'; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER finance_followup_readback_guard BEFORE INSERT OR UPDATE OR DELETE ON workflows_financefollowupreadback FOR EACH ROW EXECUTE FUNCTION psl_finance_readback_guard();
CREATE TRIGGER finance_followup_readback_review_guard BEFORE INSERT OR UPDATE OR DELETE ON workflows_financefollowupreadbackreview FOR EACH ROW EXECUTE FUNCTION psl_finance_readback_guard();
"""
class Migration(migrations.Migration):
    dependencies=[('workflows','0033_finance_followup_readback')]
    operations=[migrations.RunSQL(SQL,reverse_sql=migrations.RunSQL.noop)]

from django.db import migrations
SQL=r"""
CREATE FUNCTION psl_authenticated_finance_intake_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE r finance_financereceiptfollowup;
BEGIN
 IF TG_OP<>'INSERT' THEN RAISE EXCEPTION 'Authenticated intake history is immutable'; END IF;
 SELECT * INTO r FROM finance_financereceiptfollowup WHERE id=NEW.followup_id;
 IF NEW.sha256 !~ '^[a-f0-9]{64}$' OR NEW.operation_key !~ '^[a-f0-9]{64}$' OR
    NEW.envelope->>'format' IS DISTINCT FROM 'psl.finance-followup-delivery/v1' OR
    NEW.envelope->>'sender_ref' IS DISTINCT FROM NEW.sender_ref OR NEW.envelope->>'destination_ref' IS DISTINCT FROM NEW.destination_ref OR
    NEW.envelope->>'operation_key' IS DISTINCT FROM NEW.operation_key OR NEW.envelope->'projection' IS DISTINCT FROM r.projection OR
    NEW.pin->'authenticated_transport' IS DISTINCT FROM 'true'::jsonb OR NEW.pin->'execution_authorized' IS DISTINCT FROM 'false'::jsonb OR
    NEW.pin->'financial_effect_verified' IS DISTINCT FROM 'false'::jsonb OR NEW.pin->'debt_waived' IS DISTINCT FROM 'false'::jsonb OR
    NOT EXISTS(SELECT 1 FROM policy_configuration WHERE id::text=NEW.pin->>'policy' AND case_id=r.case_id AND component='OPS.finance_followup_intake') THEN
    RAISE EXCEPTION 'Exact inert authenticated same-case intake required'; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER authenticated_finance_intake_guard BEFORE INSERT OR UPDATE OR DELETE ON finance_financeauthenticatedintake FOR EACH ROW EXECUTE FUNCTION psl_authenticated_finance_intake_guard();
"""
class Migration(migrations.Migration):
    dependencies=[('finance','0060_followup_transport')]
    operations=[migrations.RunSQL(SQL,reverse_sql=migrations.RunSQL.noop)]

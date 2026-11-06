from django.db import migrations
SQL=r"""
CREATE FUNCTION psl_finance_followup_dispatch_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE p workflows_nativefinancepacket; m workflows_nativefinancemapping; plan workflows_reconstitutionplan; e jsonb;
BEGIN
 IF TG_OP='DELETE' THEN RAISE EXCEPTION 'Finance intake dispatch history is immutable'; END IF;
 IF TG_OP='UPDATE' AND ((NEW.packet_id,NEW.operation_key,NEW.intent,NEW.actor_id,NEW.created_at) IS DISTINCT FROM (OLD.packet_id,OLD.operation_key,OLD.intent,OLD.actor_id,OLD.created_at) OR
    NEW.attempts<OLD.attempts OR NEW.fence<OLD.fence OR (OLD.receipt IS NOT NULL AND (NEW.receipt IS DISTINCT FROM OLD.receipt OR NEW.status<>'confirmed'))) THEN
    RAISE EXCEPTION 'Original dispatch intent/fence/receipt required'; END IF;
 SELECT * INTO p FROM workflows_nativefinancepacket WHERE id=NEW.packet_id;
 SELECT * INTO m FROM workflows_nativefinancemapping WHERE id=p.mapping_id;
 SELECT * INTO plan FROM workflows_reconstitutionplan WHERE id=m.plan_id;
 e=NEW.intent->'envelope';
 IF NEW.operation_key !~ '^[a-f0-9]{64}$' OR NEW.status NOT IN ('pending','leased','unknown','held','confirmed') OR
    NEW.intent->>'format' IS DISTINCT FROM 'psl.finance-followup-delivery/v1' OR e->>'format' IS DISTINCT FROM 'psl.finance-followup-delivery/v1' OR
    e->>'operation_key' IS DISTINCT FROM NEW.operation_key OR e->'projection'->>'packet_sha256' IS DISTINCT FROM p.sha256 OR
    e->'projection'->>'mapping_sha256' IS DISTINCT FROM m.sha256 OR e->'projection'->>'source_case_id' IS DISTINCT FROM m.payload->>'source_case_id' OR
    e->'projection'->'source_invoice_id' IS DISTINCT FROM m.payload->'source_invoice_id' OR e->'projection'->'source_correction_id' IS DISTINCT FROM m.payload->'source_correction_id' OR
    e->'projection'->>'variant' IS DISTINCT FROM m.payload->>'variant' OR e->'projection'->'business_jobs_reenacted' IS DISTINCT FROM 'false'::jsonb OR
    e->'projection'->'debt_waived' IS DISTINCT FROM 'false'::jsonb OR e->'projection'->'activation_enabled' IS DISTINCT FROM 'false'::jsonb OR
    e->>'sender_ref' IS DISTINCT FROM NEW.intent->'rules'->>'sender_ref' OR e->>'destination_ref' IS DISTINCT FROM NEW.intent->'rules'->>'destination_ref' OR
    NOT EXISTS(SELECT 1 FROM policy_configuration WHERE id::text=NEW.intent->'pin'->>'transport_policy' AND case_id=plan.case_id AND component='OPS.finance_followup_transport') OR
    NOT EXISTS(SELECT 1 FROM workflows_nativefinancepublicationjob j WHERE j.packet_id=p.id AND j.status='confirmed' AND j.operation_key=e->'projection'->>'publication_operation') THEN
    RAISE EXCEPTION 'Exact published inert Finance request and transport criteria required'; END IF;
 IF NEW.status='confirmed' AND NEW.receipt IS NULL THEN RAISE EXCEPTION 'Confirmed source intake needs a receipt'; END IF;
 IF NEW.receipt IS NOT NULL AND (NEW.receipt->>'format' IS DISTINCT FROM 'psl.finance-followup-intake/v1' OR NEW.receipt->>'operation_key' IS DISTINCT FROM NEW.operation_key OR
    NEW.receipt->>'outcome' IS DISTINCT FROM 'acknowledged' OR NEW.receipt->>'sender_ref' IS DISTINCT FROM e->>'sender_ref' OR NEW.receipt->>'destination_ref' IS DISTINCT FROM e->>'destination_ref' OR
    NEW.receipt->'authenticated_transport' IS DISTINCT FROM 'true'::jsonb OR NEW.receipt->'execution_authorized' IS DISTINCT FROM 'false'::jsonb OR
    NEW.receipt->'financial_effect_verified' IS DISTINCT FROM 'false'::jsonb OR NEW.receipt->'debt_waived' IS DISTINCT FROM 'false'::jsonb) THEN
    RAISE EXCEPTION 'Authenticated inert source acknowledgement required'; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER finance_followup_dispatch_guard BEFORE INSERT OR UPDATE OR DELETE ON workflows_financefollowupdispatch FOR EACH ROW EXECUTE FUNCTION psl_finance_followup_dispatch_guard();
"""
class Migration(migrations.Migration):
    dependencies=[('workflows','0035_followup_transport')]
    operations=[migrations.RunSQL(SQL,reverse_sql=migrations.RunSQL.noop)]

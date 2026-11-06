from django.db import migrations

SQL = r"""
CREATE FUNCTION psl_cold_recovery_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE p workflows_coldrecoveryplan;
BEGIN
 IF TG_OP='DELETE' OR (TG_OP='UPDATE' AND TG_TABLE_NAME<>'workflows_coldrecoveryjob') THEN
   RAISE EXCEPTION 'cold recovery history is immutable'; END IF;
 IF TG_TABLE_NAME='workflows_coldcontrolidentity' THEN
   IF NEW.secret_sha256 !~ '^[a-f0-9]{64}$' OR length(NEW.reference)=0 THEN RAISE EXCEPTION 'independent control identity required'; END IF;
   RETURN NEW;
 END IF;
 IF TG_TABLE_NAME='workflows_coldrecoveryplan' THEN
   IF jsonb_typeof(NEW.payload) IS DISTINCT FROM 'object' OR
      NOT NEW.payload ?& ARRAY['archive_ref','target_ref','key_ref','archive_sha256','manifest_sha256','runtime_sha256'] OR
      NEW.payload - ARRAY['archive_ref','target_ref','key_ref','archive_sha256','manifest_sha256','runtime_sha256'] <> '{}' OR
      NEW.version<1 OR NEW.sha256 !~ '^[a-f0-9]{64}$' OR
      coalesce(NEW.payload->>'archive_sha256','') !~ '^[a-f0-9]{64}$' OR
      coalesce(NEW.payload->>'manifest_sha256','') !~ '^[a-f0-9]{64}$' OR
      coalesce(NEW.payload->>'runtime_sha256','') !~ '^[a-f0-9]{64}$' THEN RAISE EXCEPTION 'closed exact cold request required'; END IF;
   RETURN NEW;
 END IF;
 SELECT * INTO p FROM workflows_coldrecoveryplan WHERE id=NEW.plan_id;
 IF TG_TABLE_NAME='workflows_coldrecoveryreview' THEN
   IF NEW.actor_id=p.actor_id OR NEW.phase NOT IN ('authorize','recovered') OR NEW.decision NOT IN ('approve','hold') OR
      length(trim(NEW.rationale))=0 OR length(NEW.operation_key)=0 OR
      NEW.pin->>'plan_sha256' IS DISTINCT FROM p.sha256 OR NEW.pin->>'runtime_sha256' IS DISTINCT FROM p.payload->>'runtime_sha256' OR
      NOT NEW.pin ?& ARRAY['plan_sha256','policy','role_policy','runtime_sha256'] OR
      NEW.pin - ARRAY['plan_sha256','policy','role_policy','runtime_sha256','receipt_sha256'] <> '{}' OR
      EXISTS(SELECT 1 FROM workflows_coldrecoveryjob WHERE plan_id=p.id AND actor_id=NEW.actor_id) OR
      NOT EXISTS(SELECT 1 FROM policy_configuration WHERE id::text=NEW.pin->>'policy' AND case_id=p.case_id AND component='OPS.cold_recovery') OR
      NOT EXISTS(SELECT 1 FROM policy_configuration WHERE id::text=NEW.pin->>'role_policy' AND case_id=p.case_id AND component='D05.role_principal_assignments') THEN
      RAISE EXCEPTION 'independent same-scope cold human review required'; END IF;
   IF (NEW.phase='authorize' AND NEW.pin ? 'receipt_sha256') OR
      (NEW.phase='recovered' AND (coalesce(NEW.pin->>'receipt_sha256','') !~ '^[a-f0-9]{64}$' OR NOT EXISTS(SELECT 1 FROM workflows_coldrecoveryjob WHERE plan_id=p.id AND status='confirmed'))) THEN
      RAISE EXCEPTION 'recovered review requires actual cold receipt'; END IF;
   RETURN NEW;
 END IF;
 IF TG_OP='UPDATE' AND (NEW.plan_id,NEW.operation_key,NEW.intent,NEW.actor_id,NEW.created_at) IS DISTINCT FROM
      (OLD.plan_id,OLD.operation_key,OLD.intent,OLD.actor_id,OLD.created_at) THEN RAISE EXCEPTION 'cold intent is immutable'; END IF;
 IF TG_OP='UPDATE' AND (NEW.attempts<OLD.attempts OR NEW.fence<OLD.fence OR
      (OLD.receipt IS NOT NULL AND (NEW.receipt IS DISTINCT FROM OLD.receipt OR NEW.status<>'confirmed'))) THEN
      RAISE EXCEPTION 'cold receipt/fence history cannot be replaced'; END IF;
 IF NEW.status NOT IN ('pending','leased','held','unknown','confirmed') OR
    NEW.intent->>'format' IS DISTINCT FROM 'psl.postgres-attachments.aesgcm.v1' OR
    NEW.intent->>'operation_key' IS DISTINCT FROM NEW.operation_key OR NEW.operation_key !~ '^[a-f0-9]{64}$' OR
    NEW.intent->>'plan' IS DISTINCT FROM p.id::text OR NEW.intent->>'plan_sha256' IS DISTINCT FROM p.sha256 OR
    NEW.intent->'payload' IS DISTINCT FROM p.payload OR
    NEW.intent->>'runtime_sha256' IS DISTINCT FROM p.payload->>'runtime_sha256' OR
    NOT NEW.intent ?& ARRAY['format','operation_key','plan','plan_sha256','payload','rules','pin','runtime_sha256'] OR
    NEW.intent - ARRAY['format','operation_key','plan','plan_sha256','payload','rules','pin','runtime_sha256'] <> '{}' OR
    (NEW.status='confirmed') IS DISTINCT FROM (NEW.receipt IS NOT NULL) THEN RAISE EXCEPTION 'closed exact cold job required'; END IF;
 IF NOT EXISTS(SELECT 1 FROM workflows_coldrecoveryreview r WHERE r.id::text=NEW.intent->'pin'->>'authorization_review' AND
    r.plan_id=p.id AND r.phase='authorize' AND r.decision='approve' AND r.actor_id<>NEW.actor_id AND r.pin=(NEW.intent->'pin'-'authorization_review')) THEN
    RAISE EXCEPTION 'exact fresh independent cold authorization required'; END IF;
 IF NEW.receipt IS NOT NULL AND (
    NEW.receipt->>'format' IS DISTINCT FROM 'psl.postgres-attachments.aesgcm.v1' OR
    NEW.receipt->>'archive_sha256' IS DISTINCT FROM p.payload->>'archive_sha256' OR
    NEW.receipt->>'manifest_sha256' IS DISTINCT FROM p.payload->>'manifest_sha256' OR
    NEW.receipt->>'runtime_sha256' IS DISTINCT FROM p.payload->>'runtime_sha256' OR
    NEW.receipt->'schema_and_rows_verified' IS DISTINCT FROM 'true'::jsonb OR NEW.receipt->'attachment_bytes_verified' IS DISTINCT FROM 'true'::jsonb OR
    NEW.receipt->'authentication_disabled' IS DISTINCT FROM 'true'::jsonb OR NEW.receipt->'outbound_disabled' IS DISTINCT FROM 'true'::jsonb OR
    NEW.receipt->'live_authority_restored' IS DISTINCT FROM 'false'::jsonb OR NEW.receipt->'operational_acceptance' IS DISTINCT FROM 'false'::jsonb OR
    NEW.receipt - ARRAY['format','archive_sha256','manifest_sha256','runtime_sha256','schema_and_rows_verified','attachment_bytes_verified','authentication_disabled','outbound_disabled','live_authority_restored','operational_acceptance'] <> '{}') THEN
    RAISE EXCEPTION 'closed inert target-only receipt required'; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER cold_identity_guard BEFORE INSERT OR UPDATE OR DELETE ON workflows_coldcontrolidentity FOR EACH ROW EXECUTE FUNCTION psl_cold_recovery_guard();
CREATE TRIGGER cold_plan_guard BEFORE INSERT OR UPDATE OR DELETE ON workflows_coldrecoveryplan FOR EACH ROW EXECUTE FUNCTION psl_cold_recovery_guard();
CREATE TRIGGER cold_review_guard BEFORE INSERT OR UPDATE OR DELETE ON workflows_coldrecoveryreview FOR EACH ROW EXECUTE FUNCTION psl_cold_recovery_guard();
CREATE TRIGGER cold_job_guard BEFORE INSERT OR UPDATE OR DELETE ON workflows_coldrecoveryjob FOR EACH ROW EXECUTE FUNCTION psl_cold_recovery_guard();
"""


class Migration(migrations.Migration):
    dependencies = [('workflows','0023_cold_recovery')]
    operations = [migrations.RunSQL(SQL, reverse_sql=migrations.RunSQL.noop)]

from django.db import migrations

SQL = r"""
CREATE FUNCTION psl_application_recovery_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'native application recovery history is immutable'; END $$;
CREATE TRIGGER app_recovery_plan_immutable BEFORE UPDATE OR DELETE ON workflows_applicationrecoveryplan FOR EACH ROW EXECUTE FUNCTION psl_application_recovery_immutable();
CREATE TRIGGER app_recovery_review_immutable BEFORE UPDATE OR DELETE ON workflows_applicationrecoveryreview FOR EACH ROW EXECUTE FUNCTION psl_application_recovery_immutable();
CREATE TRIGGER app_recovery_attachment_immutable BEFORE UPDATE OR DELETE ON workflows_recoveryattachment FOR EACH ROW EXECUTE FUNCTION psl_application_recovery_immutable();

CREATE FUNCTION psl_application_recovery_lineage() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE p workflows_applicationrecoveryplan; b workflows_applicationrecoveryjob;
BEGIN
 IF TG_TABLE_NAME='workflows_applicationrecoveryplan' THEN
   IF jsonb_typeof(NEW.payload) IS DISTINCT FROM 'object' OR NOT NEW.payload ?& ARRAY['source_ref','target_ref','key_ref'] OR
      NEW.payload - ARRAY['source_ref','target_ref','key_ref'] <> '{}' OR NEW.sha256 !~ '^[a-f0-9]{64}$' OR NEW.version<1 THEN
      RAISE EXCEPTION 'closed native recovery plan required'; END IF;
   RETURN NEW;
 END IF;
 SELECT * INTO p FROM workflows_applicationrecoveryplan WHERE id=NEW.plan_id;
 IF TG_TABLE_NAME='workflows_applicationrecoveryreview' THEN
   IF NEW.actor_id=p.actor_id OR NEW.phase NOT IN ('authorize','recovered') OR NEW.decision NOT IN ('approve','hold') OR
      NEW.pin->>'plan_sha256' IS DISTINCT FROM p.sha256 OR NOT NEW.pin ?& ARRAY['policy','role_policy','runtime_sha256'] OR
      NEW.pin - ARRAY['plan_sha256','policy','role_policy','runtime_sha256','recovery_receipt_sha256'] <> '{}' OR
      coalesce(NEW.pin->>'runtime_sha256','') !~ '^[a-f0-9]{64}$' OR
      EXISTS(SELECT 1 FROM workflows_applicationrecoveryjob WHERE plan_id=p.id AND actor_id=NEW.actor_id) THEN
      RAISE EXCEPTION 'independent native human review lineage required'; END IF;
   IF NEW.phase='recovered' AND (NOT NEW.pin ? 'recovery_receipt_sha256' OR NOT EXISTS(SELECT 1 FROM workflows_applicationrecoveryjob WHERE plan_id=p.id AND kind='restore' AND status='confirmed')) THEN
      RAISE EXCEPTION 'actual recovered receipt required'; END IF;
   RETURN NEW;
 END IF;
 IF TG_OP='DELETE' THEN RAISE EXCEPTION 'native job history cannot be deleted'; END IF;
 IF TG_OP='UPDATE' AND (NEW.plan_id,NEW.kind,NEW.operation_key,NEW.intent,NEW.actor_id,NEW.created_at) IS DISTINCT FROM
      (OLD.plan_id,OLD.kind,OLD.operation_key,OLD.intent,OLD.actor_id,OLD.created_at) THEN
   RAISE EXCEPTION 'native job intent is immutable'; END IF;
 IF TG_OP='UPDATE' AND OLD.receipt IS NOT NULL AND (NEW.receipt IS DISTINCT FROM OLD.receipt OR NEW.status<>'confirmed') THEN
   RAISE EXCEPTION 'confirmed native receipt cannot be replaced'; END IF;
 IF NEW.kind NOT IN ('archive','restore') OR NEW.status NOT IN ('pending','leased','held','unknown','confirmed') OR
    NEW.intent->>'format' IS DISTINCT FROM 'psl.postgres-attachments.aesgcm.v1' OR
    NEW.intent->>'operation_key' IS DISTINCT FROM NEW.operation_key OR NEW.intent->>'kind' IS DISTINCT FROM NEW.kind OR
    NEW.intent->>'plan' IS DISTINCT FROM p.id::text OR NEW.intent->>'plan_sha256' IS DISTINCT FROM p.sha256 OR
    NEW.intent->'pin'->>'plan_sha256' IS DISTINCT FROM p.sha256 OR
    NEW.intent->>'runtime_sha256' IS DISTINCT FROM NEW.intent->'pin'->>'runtime_sha256' OR
    coalesce(NEW.intent->>'runtime_sha256','') !~ '^[a-f0-9]{64}$' OR
    jsonb_typeof(NEW.intent->'case_ids') IS DISTINCT FROM 'array' OR NOT (NEW.intent->'case_ids' ? p.case_id::text) OR
    NOT NEW.intent ?& ARRAY['format','operation_key','kind','plan','plan_sha256','rules','pin','case_ids','runtime_sha256','archive_job'] OR
    NEW.intent - ARRAY['format','operation_key','kind','plan','plan_sha256','rules','pin','case_ids','runtime_sha256','archive_job'] <> '{}' OR
    NEW.intent->'rules'->>'source_ref' IS DISTINCT FROM p.payload->>'source_ref' OR
    NEW.intent->'rules'->>'target_ref' IS DISTINCT FROM p.payload->>'target_ref' OR
    NEW.intent->'rules'->>'key_ref' IS DISTINCT FROM p.payload->>'key_ref' OR
    (NEW.status='confirmed') IS DISTINCT FROM (NEW.receipt IS NOT NULL) THEN
   RAISE EXCEPTION 'native job closed exact-intent/receipt lineage required'; END IF;
 IF NOT EXISTS(SELECT 1 FROM workflows_applicationrecoveryreview r WHERE r.id::text=NEW.intent->'pin'->>'authorization_review' AND r.plan_id=p.id AND r.phase='authorize' AND r.decision='approve' AND r.actor_id<>NEW.actor_id AND r.pin=((NEW.intent->'pin')-'authorization_review')) THEN
   RAISE EXCEPTION 'exact independent native authorization required'; END IF;
 IF NEW.kind='archive' AND NEW.intent->'archive_job' IS DISTINCT FROM 'null'::jsonb THEN RAISE EXCEPTION 'archive cannot borrow a metadata input'; END IF;
 IF NEW.kind='restore' THEN
   SELECT * INTO b FROM workflows_applicationrecoveryjob WHERE id::text=NEW.intent->>'archive_job' AND plan_id=p.id AND kind='archive' AND status='confirmed';
   IF b.id IS NULL THEN RAISE EXCEPTION 'same-plan confirmed native archive required'; END IF;
 END IF;
 IF NEW.receipt IS NOT NULL THEN
   IF NEW.receipt->>'format' IS DISTINCT FROM 'psl.postgres-attachments.aesgcm.v1' OR
      NEW.receipt->'live_authority_restored' IS DISTINCT FROM 'false'::jsonb OR
      NEW.receipt->'operational_acceptance' IS DISTINCT FROM 'false'::jsonb OR
      coalesce(NEW.receipt->>'archive_sha256','') !~ '^[a-f0-9]{64}$' OR
      coalesce(NEW.receipt->>'manifest_sha256','') !~ '^[a-f0-9]{64}$' THEN RAISE EXCEPTION 'bounded native receipt flags required'; END IF;
   IF NEW.kind='archive' AND (NOT NEW.receipt ?& ARRAY['managed_attachment_count','table_count'] OR
      NEW.receipt - ARRAY['format','archive_sha256','manifest_sha256','managed_attachment_count','table_count','live_authority_restored','operational_acceptance'] <> '{}') THEN
      RAISE EXCEPTION 'closed native archive receipt required'; END IF;
   IF NEW.kind='restore' AND (NEW.receipt->>'archive_sha256' IS DISTINCT FROM b.receipt->>'archive_sha256' OR
      NEW.receipt->>'runtime_sha256' IS DISTINCT FROM NEW.intent->>'runtime_sha256' OR
      NEW.receipt->'schema_and_rows_verified' IS DISTINCT FROM 'true'::jsonb OR
      NEW.receipt->'attachment_bytes_verified' IS DISTINCT FROM 'true'::jsonb OR
      NEW.receipt->'authentication_disabled' IS DISTINCT FROM 'true'::jsonb OR
      NEW.receipt->'outbound_disabled' IS DISTINCT FROM 'true'::jsonb OR
      NEW.receipt - ARRAY['format','archive_sha256','manifest_sha256','runtime_sha256','schema_and_rows_verified','attachment_bytes_verified','authentication_disabled','outbound_disabled','live_authority_restored','operational_acceptance'] <> '{}') THEN
      RAISE EXCEPTION 'closed isolated recovery receipt required'; END IF;
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER app_recovery_plan_lineage BEFORE INSERT ON workflows_applicationrecoveryplan FOR EACH ROW EXECUTE FUNCTION psl_application_recovery_lineage();
CREATE TRIGGER app_recovery_review_lineage BEFORE INSERT ON workflows_applicationrecoveryreview FOR EACH ROW EXECUTE FUNCTION psl_application_recovery_lineage();
CREATE TRIGGER app_recovery_job_lineage BEFORE INSERT OR UPDATE OR DELETE ON workflows_applicationrecoveryjob FOR EACH ROW EXECUTE FUNCTION psl_application_recovery_lineage();
"""


class Migration(migrations.Migration):
    dependencies = [('workflows', '0021_application_recovery')]
    operations = [migrations.RunSQL(SQL, reverse_sql=migrations.RunSQL.noop)]

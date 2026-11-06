from django.db import migrations

SQL=r"""
CREATE FUNCTION psl_reconstitution_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE p workflows_reconstitutionplan; r workflows_reconstitutionreview; b workflows_reconstitutionjob;
BEGIN
 IF TG_OP='DELETE' OR (TG_OP='UPDATE' AND TG_TABLE_NAME<>'workflows_reconstitutionjob') THEN RAISE EXCEPTION 'reconstitution history is immutable'; END IF;
 IF TG_TABLE_NAME='workflows_reconstitutionplan' THEN
   IF NEW.version<1 OR NEW.sha256 !~ '^[a-f0-9]{64}$' OR NOT NEW.payload ?& ARRAY['profile_ref','destination_ref','inventory'] OR
      NEW.payload - ARRAY['profile_ref','destination_ref','inventory']<>'{}' OR
      NEW.payload->'inventory'->>'format' IS DISTINCT FROM 'psl.reconstitution.v1' OR
      NEW.payload->'inventory'->'activation_enabled' IS DISTINCT FROM 'false'::jsonb OR NEW.payload->'inventory'->'archived_authority_accepted' IS DISTINCT FROM 'false'::jsonb OR
      jsonb_typeof(NEW.payload->'inventory'->'effects') IS DISTINCT FROM 'array' OR
      NOT EXISTS(SELECT 1 FROM workflows_coldrecoveryjob j JOIN workflows_coldrecoveryplan c ON c.id=j.plan_id WHERE j.id=NEW.recovery_id AND c.case_id=NEW.case_id AND j.status='confirmed') THEN
      RAISE EXCEPTION 'closed same-scope confirmed recovery inventory required'; END IF;
   RETURN NEW;
 END IF;
 SELECT * INTO p FROM workflows_reconstitutionplan WHERE id=NEW.plan_id;
 IF TG_TABLE_NAME IN ('workflows_reconstitutiondisposition','workflows_reconstitutionreview') THEN
   IF NEW.actor_id=p.actor_id OR EXISTS(SELECT 1 FROM workflows_reconstitutionjob WHERE plan_id=p.id AND actor_id=NEW.actor_id) OR
      length(trim(NEW.rationale))=0 OR length(NEW.operation_key)=0 OR NEW.pin->>'plan_sha256' IS DISTINCT FROM p.sha256 OR
      NEW.pin->>'runtime_sha256' IS DISTINCT FROM p.payload->'inventory'->>'runtime_sha256' OR
      NOT NEW.pin ?& ARRAY['plan_sha256','runtime_sha256','policy','role_policy'] OR
      NOT EXISTS(SELECT 1 FROM policy_configuration WHERE id::text=NEW.pin->>'policy' AND case_id=p.case_id AND component='OPS.reconstitution') OR
      NOT EXISTS(SELECT 1 FROM policy_configuration WHERE id::text=NEW.pin->>'role_policy' AND case_id=p.case_id AND component='D05.role_principal_assignments') THEN
      RAISE EXCEPTION 'independent fresh same-scope reconstitution decision required'; END IF;
   IF TG_TABLE_NAME='workflows_reconstitutiondisposition' THEN
      IF NEW.version<1 OR NEW.verdict NOT IN ('unresolved','retain_quarantine','receipt_confirmed','replacement_required') OR
         NOT EXISTS(SELECT 1 FROM jsonb_array_elements(p.payload->'inventory'->'effects') e WHERE e->>'effect_key'=NEW.effect_key) OR
         NEW.pin - ARRAY['plan_sha256','runtime_sha256','policy','role_policy','probe_receipt_sha256']<>'{}' THEN RAISE EXCEPTION 'exact versioned human effect disposition required'; END IF;
      IF NEW.verdict='receipt_confirmed' THEN
         SELECT * INTO b FROM workflows_reconstitutionjob WHERE id=NEW.probe_id AND plan_id=p.id AND kind='receipt' AND effect_key=NEW.effect_key AND status='confirmed';
         IF b.id IS NULL OR b.receipt->'payload'->>'outcome' IS DISTINCT FROM 'present' OR coalesce(NEW.pin->>'probe_receipt_sha256','') !~ '^[a-f0-9]{64}$' THEN
            RAISE EXCEPTION 'absence is unknown; current exact receipt evidence required'; END IF;
      ELSIF NEW.probe_id IS NOT NULL OR NEW.pin ? 'probe_receipt_sha256' THEN RAISE EXCEPTION 'only receipt confirmation binds a probe'; END IF;
   ELSE
      IF NEW.verdict NOT IN ('approve','hold') OR coalesce(NEW.pin->>'manifest_sha256','') !~ '^[a-f0-9]{64}$' OR
         NEW.pin - ARRAY['plan_sha256','runtime_sha256','policy','role_policy','manifest_sha256']<>'{}' THEN RAISE EXCEPTION 'closed exact packet review required'; END IF;
      IF NEW.verdict='approve' AND EXISTS(SELECT 1 FROM jsonb_array_elements(p.payload->'inventory'->'effects') e WHERE NOT EXISTS(SELECT 1 FROM workflows_reconstitutiondisposition d WHERE d.plan_id=p.id AND d.effect_key=e->>'effect_key')) THEN
         RAISE EXCEPTION 'every effect requires an explicit human disposition'; END IF;
   END IF;
   RETURN NEW;
 END IF;
 IF TG_OP='UPDATE' AND (NEW.plan_id,NEW.kind,NEW.effect_key,NEW.operation_key,NEW.intent,NEW.actor_id,NEW.created_at) IS DISTINCT FROM
      (OLD.plan_id,OLD.kind,OLD.effect_key,OLD.operation_key,OLD.intent,OLD.actor_id,OLD.created_at) THEN RAISE EXCEPTION 'reconstitution job intent is immutable'; END IF;
 IF TG_OP='UPDATE' AND (NEW.fence<OLD.fence OR NEW.attempts<OLD.attempts OR (OLD.receipt IS NOT NULL AND (NEW.receipt IS DISTINCT FROM OLD.receipt OR NEW.status<>'confirmed'))) THEN
      RAISE EXCEPTION 'reconstitution receipt/fence history cannot be replaced'; END IF;
 IF NEW.kind NOT IN ('receipt','publish') OR NEW.status NOT IN ('pending','leased','unknown','held','confirmed') OR
    NEW.intent->>'format' IS DISTINCT FROM 'psl.reconstitution.v1' OR NEW.intent->>'operation_key' IS DISTINCT FROM NEW.operation_key OR NEW.operation_key !~ '^[a-f0-9]{64}$' OR
    NEW.intent->>'plan' IS DISTINCT FROM p.id::text OR NEW.intent->>'plan_sha256' IS DISTINCT FROM p.sha256 OR NEW.intent->'pin'->>'plan_sha256' IS DISTINCT FROM p.sha256 OR
    NEW.intent->'pin'->>'runtime_sha256' IS DISTINCT FROM p.payload->'inventory'->>'runtime_sha256' OR NEW.intent->>'profile_ref' IS DISTINCT FROM p.payload->>'profile_ref' OR
    NEW.intent->'rules'->>'profile_ref' IS DISTINCT FROM p.payload->>'profile_ref' OR NEW.intent->'rules'->>'destination_ref' IS DISTINCT FROM p.payload->>'destination_ref' OR
    NOT NEW.intent ?& ARRAY['format','operation_key','plan','plan_sha256','kind','profile_ref','rules','pin','effect','manifest','authorization'] OR
    NEW.intent - ARRAY['format','operation_key','plan','plan_sha256','kind','profile_ref','rules','pin','effect','manifest','authorization']<>'{}' OR
    (NEW.status='confirmed') IS DISTINCT FROM (NEW.receipt IS NOT NULL) THEN RAISE EXCEPTION 'closed exact inert reconstitution job required'; END IF;
 IF NEW.kind='receipt' THEN
    IF NEW.intent->'manifest' IS DISTINCT FROM 'null'::jsonb OR NEW.intent->'authorization' IS DISTINCT FROM 'null'::jsonb OR
       NOT EXISTS(SELECT 1 FROM jsonb_array_elements(p.payload->'inventory'->'effects') e WHERE e=NEW.intent->'effect' AND e->>'effect_key'=NEW.effect_key) THEN RAISE EXCEPTION 'exact captured receipt lookup required'; END IF;
 ELSE
    SELECT * INTO r FROM workflows_reconstitutionreview WHERE id::text=NEW.intent->>'authorization' AND plan_id=p.id AND verdict='approve' AND actor_id<>NEW.actor_id;
    IF NEW.effect_key<>'all' OR NEW.intent->'effect' IS DISTINCT FROM 'null'::jsonb OR r.id IS NULL OR
       r.pin IS DISTINCT FROM ((NEW.intent->'pin') || jsonb_build_object('manifest_sha256',r.pin->>'manifest_sha256')) OR
       NEW.intent->'manifest'->'activation_enabled' IS DISTINCT FROM 'false'::jsonb OR
       NEW.intent->'manifest'->'business_jobs_reenacted' IS DISTINCT FROM 'false'::jsonb OR
       NEW.intent->'manifest'->'debt_waived' IS DISTINCT FROM 'false'::jsonb OR NEW.intent->'manifest'->'archived_authority_accepted' IS DISTINCT FROM 'false'::jsonb THEN
       RAISE EXCEPTION 'complete independently reviewed inert publication required'; END IF;
 END IF;
 IF NEW.receipt IS NOT NULL THEN
    IF NEW.receipt->>'format' IS DISTINCT FROM 'psl.reconstitution.v1' OR NEW.receipt->>'kind' IS DISTINCT FROM NEW.kind OR
       NEW.receipt->>'runtime_sha256' IS DISTINCT FROM NEW.intent->'pin'->>'runtime_sha256' OR
       NEW.receipt->'activation_enabled' IS DISTINCT FROM 'false'::jsonb OR NEW.receipt->'business_jobs_reenacted' IS DISTINCT FROM 'false'::jsonb OR
       coalesce(NEW.receipt->>'payload_sha256','') !~ '^[a-f0-9]{64}$' OR NOT NEW.receipt ? 'payload' OR
       NEW.receipt - ARRAY['format','kind','runtime_sha256','payload','payload_sha256','activation_enabled','business_jobs_reenacted']<>'{}' THEN RAISE EXCEPTION 'closed non-activating artifact receipt required'; END IF;
    IF NEW.kind='publish' AND NEW.receipt->'payload' IS DISTINCT FROM NEW.intent->'manifest' THEN RAISE EXCEPTION 'exact reviewed packet receipt required'; END IF;
    IF NEW.kind='receipt' AND (NEW.receipt->'payload'->>'effect_key' IS DISTINCT FROM NEW.effect_key OR
       coalesce(NEW.receipt->'payload'->>'outcome','') NOT IN ('present','unknown') OR NEW.receipt->'payload'->'direct_vendor_verification' IS DISTINCT FROM 'false'::jsonb) THEN
       RAISE EXCEPTION 'typed gateway attestation; no direct vendor inference'; END IF;
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER reconstitution_plan_guard BEFORE INSERT OR UPDATE OR DELETE ON workflows_reconstitutionplan FOR EACH ROW EXECUTE FUNCTION psl_reconstitution_guard();
CREATE TRIGGER reconstitution_job_guard BEFORE INSERT OR UPDATE OR DELETE ON workflows_reconstitutionjob FOR EACH ROW EXECUTE FUNCTION psl_reconstitution_guard();
CREATE TRIGGER reconstitution_disposition_guard BEFORE INSERT OR UPDATE OR DELETE ON workflows_reconstitutiondisposition FOR EACH ROW EXECUTE FUNCTION psl_reconstitution_guard();
CREATE TRIGGER reconstitution_review_guard BEFORE INSERT OR UPDATE OR DELETE ON workflows_reconstitutionreview FOR EACH ROW EXECUTE FUNCTION psl_reconstitution_guard();
"""


class Migration(migrations.Migration):
    dependencies=[('workflows','0026_reconstitution')]
    operations=[migrations.RunSQL(SQL,reverse_sql=migrations.RunSQL.noop)]

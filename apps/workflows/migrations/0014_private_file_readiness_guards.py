from django.db import migrations

SQL="""
CREATE TRIGGER psl_immutable BEFORE UPDATE OR DELETE ON workflows_privatefilereadiness FOR EACH ROW EXECUTE FUNCTION psl_append_only();
CREATE FUNCTION psl_private_file_binding() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
PERFORM 1 FROM workflows_integrationcontract WHERE id=NEW.contract_id FOR UPDATE;
IF NOT EXISTS(SELECT 1 FROM workflows_integrationcontract c JOIN workflows_recoveryjob j ON j.id=NEW.job_id JOIN workflows_recoveryplan p ON p.id=j.plan_id
 WHERE c.id=NEW.contract_id AND c.case_id=p.case_id AND c.actor_id=NEW.actor_id AND c.payload->>'kind'='adapter' AND c.payload->>'family'='protection' AND c.payload->>'implementation'='internal_postgres_session_v1' AND c.payload->>'target_key'='internal:protection' AND (c.payload->'capabilities') @> '["health","receipt_lookup"]'::jsonb AND jsonb_array_length(c.payload->'capabilities')=2
 AND j.kind IN ('export','backup') AND p.payload ? 'private_readiness_packet_ids'
 AND NEW.snapshot->>'job'=j.id::text AND NEW.snapshot->>'job_kind'=j.kind AND NEW.snapshot->>'plan'=p.id::text AND NEW.snapshot->>'case'=p.case_id::text AND NEW.snapshot->>'plan_sha256'=p.sha256 AND NEW.snapshot->'packets'=p.payload->'private_readiness_packet_ids' AND NEW.snapshot->'storage_identity'=j.intent->'storage_identity'
 AND NEW.snapshot->>'manifest_sha256' ~ '^[a-f0-9]{64}$' AND NEW.snapshot->>'intent_sha256' ~ '^[a-f0-9]{64}$' AND NEW.snapshot->'current_authority_restored'='false'::jsonb
 AND NEW.snapshot - ARRAY['job','job_kind','plan','case','plan_sha256','manifest_sha256','intent_sha256','packets','storage_identity','current_authority_restored']='{}'::jsonb
 AND (j.kind='export' AND j.intent->>'input_artifact' IS NULL OR j.kind='backup' AND EXISTS(SELECT 1 FROM workflows_recoveryartifact a JOIN workflows_recoveryjob src ON src.id=a.job_id WHERE a.id::text=j.intent->>'input_artifact' AND src.plan_id=p.id AND src.kind='export' AND a.manifest=j.intent->'manifest' AND a.sha256=NEW.snapshot->>'manifest_sha256'))
 AND NOT EXISTS(SELECT 1 FROM workflows_recoveryartifact a WHERE a.job_id=j.id AND a.sha256<>NEW.snapshot->>'manifest_sha256')
) OR EXISTS(SELECT 1 FROM workflows_privateprotectionreadiness WHERE contract_id=NEW.contract_id) OR EXISTS(SELECT 1 FROM finance_financepublicationreadiness WHERE contract_id=NEW.contract_id) THEN RAISE EXCEPTION 'Exact exclusive private export/file backup lineage required'; END IF;
IF EXISTS(SELECT 1 FROM workflows_integrationprobe WHERE contract_id=NEW.contract_id) OR EXISTS(SELECT 1 FROM workflows_integrationobservation WHERE contract_id=NEW.contract_id) OR EXISTS(SELECT 1 FROM workflows_integrationassessment WHERE contract_id=NEW.contract_id) OR EXISTS(SELECT 1 FROM workflows_integrationselection WHERE contract_id=NEW.contract_id) THEN RAISE EXCEPTION 'Private file binding must precede all readiness history'; END IF;
RETURN NEW; END $$;
CREATE TRIGGER psl_lineage BEFORE INSERT ON workflows_privatefilereadiness FOR EACH ROW EXECUTE FUNCTION psl_private_file_binding();
CREATE FUNCTION psl_private_file_other_binding() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
PERFORM 1 FROM workflows_integrationcontract WHERE id=NEW.contract_id FOR UPDATE;
IF EXISTS(SELECT 1 FROM workflows_privatefilereadiness WHERE contract_id=NEW.contract_id) THEN RAISE EXCEPTION 'File and restore bindings are exclusive'; END IF;
RETURN NEW; END $$;
CREATE TRIGGER psl_no_file_binding BEFORE INSERT ON workflows_privateprotectionreadiness FOR EACH ROW EXECUTE FUNCTION psl_private_file_other_binding();
CREATE FUNCTION psl_private_file_probe() RETURNS trigger LANGUAGE plpgsql AS $$ DECLARE b workflows_privatefilereadiness%ROWTYPE; BEGIN
PERFORM 1 FROM workflows_integrationcontract WHERE id=NEW.contract_id FOR UPDATE;
SELECT * INTO b FROM workflows_privatefilereadiness WHERE contract_id=NEW.contract_id;
IF FOUND THEN
 IF NEW.intent->'native_file' IS DISTINCT FROM jsonb_build_object('binding',b.id,'sha256',b.sha256,'source',b.snapshot) OR NEW.intent->>'kind' NOT IN ('health','receipt') OR (NEW.intent->>'kind'='receipt' AND NEW.intent->>'source_job' IS DISTINCT FROM b.job_id::text) OR (NEW.intent->>'kind'='health' AND NEW.intent->'source_job' IS DISTINCT FROM 'null'::jsonb) THEN RAISE EXCEPTION 'Exact native file probe required'; END IF;
ELSIF NEW.intent ? 'native_file' THEN RAISE EXCEPTION 'Unbound private file probe'; END IF;
RETURN NEW; END $$;
CREATE TRIGGER psl_file_lineage BEFORE INSERT ON workflows_integrationprobe FOR EACH ROW EXECUTE FUNCTION psl_private_file_probe();
CREATE FUNCTION psl_private_file_observation() RETURNS trigger LANGUAGE plpgsql AS $$ DECLARE b workflows_privatefilereadiness%ROWTYPE; j workflows_integrationprobe%ROWTYPE; v jsonb; BEGIN
PERFORM 1 FROM workflows_integrationcontract WHERE id=NEW.contract_id FOR UPDATE;
SELECT * INTO b FROM workflows_privatefilereadiness WHERE contract_id=NEW.contract_id;
IF FOUND AND NEW.job_id IS NOT NULL THEN
 SELECT * INTO j FROM workflows_integrationprobe WHERE id=NEW.job_id;
 IF j.contract_id IS DISTINCT FROM NEW.contract_id OR j.actor_id IS DISTINCT FROM NEW.actor_id OR NEW.payload->'native_file' IS DISTINCT FROM j.intent->'native_file' OR NEW.payload->'kind' IS DISTINCT FROM j.intent->'kind' OR NEW.payload->'password_authentication_proven' IS DISTINCT FROM 'false'::jsonb OR NEW.payload->'storage_write_proven' IS DISTINCT FROM 'false'::jsonb OR NEW.payload->'authenticated_transport' IS DISTINCT FROM 'true'::jsonb OR NEW.payload - ARRAY['kind','classification','authenticated_transport','outcome','identity_match','capabilities_verified','password_authentication_proven','storage_probe','storage_write_proven','lookup_verified','native_file','file_receipt_provenance','observed_at']<>'{}'::jsonb THEN RAISE EXCEPTION 'Closed exact native file observation required'; END IF;
 IF NEW.payload->>'kind'='receipt' THEN
  v=NEW.payload->'file_receipt_provenance';
  IF NOT (v ?& ARRAY['state','job_kind','operation_key_sha256','manifest_sha256','storage_identity','artifact','file_verified','payload_bodies_included','current_authority_restored','full_database_backup','full_database_export']) OR v - ARRAY['state','job_kind','operation_key_sha256','manifest_sha256','storage_identity','artifact','file_verified','payload_bodies_included','current_authority_restored','full_database_backup','full_database_export']<>'{}'::jsonb OR v->>'state' NOT IN ('found','not_found') OR v->'job_kind' IS DISTINCT FROM b.snapshot->'job_kind' OR v->'manifest_sha256' IS DISTINCT FROM b.snapshot->'manifest_sha256' OR v->'storage_identity' IS DISTINCT FROM b.snapshot->'storage_identity' OR v->'current_authority_restored' IS DISTINCT FROM 'false'::jsonb OR v->'payload_bodies_included' IS DISTINCT FROM 'false'::jsonb OR v->'full_database_export' IS DISTINCT FROM 'false'::jsonb OR v->'full_database_backup' IS DISTINCT FROM 'false'::jsonb OR v->'file_verified' IS DISTINCT FROM to_jsonb(b.snapshot->>'job_kind'='backup' AND v->>'state'='found') THEN RAISE EXCEPTION 'Closed file receipt provenance required'; END IF;
  IF v->>'artifact' IS NOT NULL AND NOT EXISTS(SELECT 1 FROM workflows_recoveryartifact a WHERE a.id::text=v->>'artifact' AND a.job_id=b.job_id AND a.sha256=b.snapshot->>'manifest_sha256') OR b.snapshot->>'job_kind'='export' AND v->>'state'='found' AND v->>'artifact' IS NULL THEN RAISE EXCEPTION 'Exact native file/export artifact required'; END IF;
 END IF;
ELSIF NEW.payload ? 'native_file' OR NEW.payload ? 'file_receipt_provenance' THEN RAISE EXCEPTION 'Unbound private file observation'; END IF;
RETURN NEW; END $$;
CREATE TRIGGER psl_file_lineage BEFORE INSERT ON workflows_integrationobservation FOR EACH ROW EXECUTE FUNCTION psl_private_file_observation();
CREATE FUNCTION psl_private_file_history_lock() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
PERFORM 1 FROM workflows_integrationcontract WHERE id=NEW.contract_id FOR UPDATE; RETURN NEW; END $$;
CREATE TRIGGER psl_file_history BEFORE INSERT ON workflows_integrationassessment FOR EACH ROW EXECUTE FUNCTION psl_private_file_history_lock();
CREATE TRIGGER psl_file_history BEFORE INSERT ON workflows_integrationselection FOR EACH ROW EXECUTE FUNCTION psl_private_file_history_lock();
CREATE OR REPLACE FUNCTION psl_private_protection_source() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
IF EXISTS(SELECT 1 FROM workflows_integrationcontract c JOIN workflows_recoveryjob j ON j.id::text=NEW.intent->>'source_job' JOIN workflows_recoveryplan p ON p.id=j.plan_id WHERE c.id=NEW.contract_id AND c.payload->>'family'='protection' AND p.payload ? 'private_readiness_packet_ids') AND NOT EXISTS(SELECT 1 FROM workflows_privateprotectionreadiness b JOIN workflows_recoveryjob j ON j.id=b.job_id WHERE b.contract_id=NEW.contract_id AND j.kind='restore' AND b.job_id::text=NEW.intent->>'source_job') AND NOT EXISTS(SELECT 1 FROM workflows_privatefilereadiness b WHERE b.contract_id=NEW.contract_id AND b.job_id::text=NEW.intent->>'source_job') THEN RAISE EXCEPTION 'Private metadata receipt source requires exact native binding'; END IF;
RETURN NEW; END $$;
"""

REVERSE="""
CREATE OR REPLACE FUNCTION psl_private_protection_source() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
IF EXISTS(SELECT 1 FROM workflows_integrationcontract c JOIN workflows_recoveryjob j ON j.id::text=NEW.intent->>'source_job' JOIN workflows_recoveryplan p ON p.id=j.plan_id WHERE c.id=NEW.contract_id AND c.payload->>'family'='protection' AND p.payload ? 'private_readiness_packet_ids') AND NOT EXISTS(SELECT 1 FROM workflows_privateprotectionreadiness b WHERE b.contract_id=NEW.contract_id AND b.job_id::text=NEW.intent->>'source_job') THEN RAISE EXCEPTION 'Private restore receipt source requires exact native binding'; END IF;
RETURN NEW; END $$;
DROP TRIGGER psl_file_history ON workflows_integrationselection; DROP TRIGGER psl_file_history ON workflows_integrationassessment; DROP FUNCTION psl_private_file_history_lock();
DROP TRIGGER psl_file_lineage ON workflows_integrationobservation; DROP FUNCTION psl_private_file_observation();
DROP TRIGGER psl_file_lineage ON workflows_integrationprobe; DROP FUNCTION psl_private_file_probe();
DROP TRIGGER psl_no_file_binding ON workflows_privateprotectionreadiness; DROP FUNCTION psl_private_file_other_binding();
DROP TRIGGER psl_lineage ON workflows_privatefilereadiness; DROP FUNCTION psl_private_file_binding(); DROP TRIGGER psl_immutable ON workflows_privatefilereadiness;
"""
class Migration(migrations.Migration):
 dependencies=[('workflows','0013_private_file_readiness'),('finance','0053_private_readiness_guards')]
 operations=[migrations.RunSQL(SQL,REVERSE)]

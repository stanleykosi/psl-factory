from django.db import migrations

class Migration(migrations.Migration):
 dependencies=[('workflows','0010_private_protection_readiness'),('finance','0053_private_readiness_guards')]
 operations=[migrations.RunSQL('CREATE TRIGGER psl_immutable BEFORE UPDATE OR DELETE ON workflows_privateprotectionreadiness FOR EACH ROW EXECUTE FUNCTION psl_append_only()','DROP TRIGGER psl_immutable ON workflows_privateprotectionreadiness'),migrations.RunSQL("""
 CREATE FUNCTION psl_private_protection_binding() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
 IF NOT EXISTS(SELECT 1 FROM workflows_integrationcontract c JOIN workflows_recoveryjob j ON j.id=NEW.job_id JOIN workflows_recoveryplan p ON p.id=j.plan_id JOIN workflows_recoveryartifact a ON a.id::text=j.intent->>'input_artifact'
 WHERE c.id=NEW.contract_id AND c.case_id=p.case_id AND c.actor_id=NEW.actor_id AND c.payload->>'kind'='adapter' AND c.payload->>'family'='protection' AND c.payload->>'implementation'='internal_postgres_session_v1' AND c.payload->>'target_key'='internal:protection' AND j.kind='restore' AND p.payload ? 'private_readiness_packet_ids'
 AND NEW.snapshot->>'job'=j.id::text AND NEW.snapshot->>'plan'=p.id::text AND NEW.snapshot->>'case'=p.case_id::text AND NEW.snapshot->>'plan_sha256'=p.sha256 AND NEW.snapshot->>'manifest_sha256'=a.sha256 AND j.intent->'manifest'=a.manifest AND NEW.snapshot->'packets'=p.payload->'private_readiness_packet_ids' AND NEW.snapshot->'target_identity'=j.intent->'target_identity'
 AND NEW.snapshot->'current_authority_restored'='false'::jsonb
 AND NEW.snapshot - ARRAY['job','plan','case','plan_sha256','manifest_sha256','intent_sha256','packets','target_identity','current_authority_restored']='{}'::jsonb AND NEW.snapshot->>'intent_sha256' ~ '^[a-f0-9]{64}$') THEN RAISE EXCEPTION 'Exact private restore readiness lineage required'; END IF;
 IF EXISTS(SELECT 1 FROM workflows_integrationprobe WHERE contract_id=NEW.contract_id) OR EXISTS(SELECT 1 FROM workflows_integrationobservation WHERE contract_id=NEW.contract_id) OR EXISTS(SELECT 1 FROM workflows_integrationselection WHERE contract_id=NEW.contract_id) THEN RAISE EXCEPTION 'Native binding must precede probe and enrollment history'; END IF;
 RETURN NEW; END $$;
 CREATE TRIGGER psl_lineage BEFORE INSERT ON workflows_privateprotectionreadiness FOR EACH ROW EXECUTE FUNCTION psl_private_protection_binding();
 CREATE FUNCTION psl_private_protection_probe() RETURNS trigger LANGUAGE plpgsql AS $$ DECLARE b workflows_privateprotectionreadiness%ROWTYPE; BEGIN
 SELECT * INTO b FROM workflows_privateprotectionreadiness WHERE contract_id=NEW.contract_id;
 IF FOUND THEN
 IF NEW.intent->'native_protection' IS DISTINCT FROM jsonb_build_object('binding',b.id,'sha256',b.sha256,'source',b.snapshot) OR NEW.intent->>'kind' NOT IN ('health','receipt') OR (NEW.intent->>'kind'='receipt' AND NEW.intent->>'source_job' IS DISTINCT FROM b.job_id::text) OR (NEW.intent->>'kind'='health' AND NEW.intent->'source_job' IS DISTINCT FROM 'null'::jsonb) THEN RAISE EXCEPTION 'Exact private protection probe source required'; END IF;
 ELSIF NEW.intent ? 'native_protection' THEN RAISE EXCEPTION 'Unbound private protection probe'; END IF;
 RETURN NEW; END $$;
 CREATE TRIGGER psl_private_lineage BEFORE INSERT ON workflows_integrationprobe FOR EACH ROW EXECUTE FUNCTION psl_private_protection_probe();
 CREATE FUNCTION psl_private_protection_observation() RETURNS trigger LANGUAGE plpgsql AS $$ DECLARE b workflows_privateprotectionreadiness%ROWTYPE; j workflows_integrationprobe%ROWTYPE; BEGIN
 SELECT * INTO b FROM workflows_privateprotectionreadiness WHERE contract_id=NEW.contract_id;
 IF FOUND AND NEW.job_id IS NOT NULL THEN
 SELECT * INTO j FROM workflows_integrationprobe WHERE id=NEW.job_id;
 IF j.contract_id IS DISTINCT FROM NEW.contract_id OR j.actor_id IS DISTINCT FROM NEW.actor_id OR NEW.payload->'native_protection' IS DISTINCT FROM j.intent->'native_protection' OR NEW.payload->'kind' IS DISTINCT FROM j.intent->'kind' THEN RAISE EXCEPTION 'Exact private protection observation provenance required'; END IF;
 IF NEW.payload->>'kind'='receipt' AND (NEW.payload->'receipt_provenance'->'current_authority_restored' IS DISTINCT FROM 'false'::jsonb OR NEW.payload->'receipt_provenance'->'payload_bodies_included' IS DISTINCT FROM 'false'::jsonb OR (NEW.payload->'receipt_provenance') - ARRAY['state','operation_key_sha256','manifest_sha256','payload_bodies_included','current_authority_restored','full_database_restore'] IS DISTINCT FROM '{}'::jsonb) THEN RAISE EXCEPTION 'Closed private protection receipt metadata required'; END IF;
 ELSIF NEW.payload ? 'native_protection' THEN RAISE EXCEPTION 'Unbound private protection observation'; END IF;
 RETURN NEW; END $$;
 CREATE TRIGGER psl_private_lineage BEFORE INSERT ON workflows_integrationobservation FOR EACH ROW EXECUTE FUNCTION psl_private_protection_observation();
 ""","DROP TRIGGER psl_private_lineage ON workflows_integrationobservation; DROP FUNCTION psl_private_protection_observation(); DROP TRIGGER psl_private_lineage ON workflows_integrationprobe; DROP FUNCTION psl_private_protection_probe(); DROP TRIGGER psl_lineage ON workflows_privateprotectionreadiness; DROP FUNCTION psl_private_protection_binding();")]

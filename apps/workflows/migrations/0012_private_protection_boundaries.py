from django.db import migrations

class Migration(migrations.Migration):
 dependencies=[('workflows','0011_private_protection_guards')]
 operations=[migrations.RunSQL("""
 CREATE FUNCTION psl_private_protection_prior_history() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
 IF EXISTS(SELECT 1 FROM workflows_integrationassessment WHERE contract_id=NEW.contract_id) THEN RAISE EXCEPTION 'No retroactive private binding of existing assessments'; END IF;
 RETURN NEW; END $$;
 CREATE TRIGGER psl_prior_history BEFORE INSERT ON workflows_privateprotectionreadiness FOR EACH ROW EXECUTE FUNCTION psl_private_protection_prior_history();
 CREATE FUNCTION psl_private_protection_source() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
 IF EXISTS(SELECT 1 FROM workflows_integrationcontract c JOIN workflows_recoveryjob j ON j.id::text=NEW.intent->>'source_job' JOIN workflows_recoveryplan p ON p.id=j.plan_id WHERE c.id=NEW.contract_id AND c.payload->>'family'='protection' AND p.payload ? 'private_readiness_packet_ids') AND NOT EXISTS(SELECT 1 FROM workflows_privateprotectionreadiness b WHERE b.contract_id=NEW.contract_id AND b.job_id::text=NEW.intent->>'source_job') THEN RAISE EXCEPTION 'Private restore receipt source requires exact native binding'; END IF;
 RETURN NEW; END $$;
 CREATE TRIGGER psl_private_source BEFORE INSERT ON workflows_integrationprobe FOR EACH ROW EXECUTE FUNCTION psl_private_protection_source();
 ""","DROP TRIGGER psl_private_source ON workflows_integrationprobe; DROP FUNCTION psl_private_protection_source(); DROP TRIGGER psl_prior_history ON workflows_privateprotectionreadiness; DROP FUNCTION psl_private_protection_prior_history();")]

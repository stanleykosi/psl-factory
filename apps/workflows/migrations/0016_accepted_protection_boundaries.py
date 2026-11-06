from django.db import migrations

SQL="""
CREATE FUNCTION psl_accepted_protection_native_boundary() RETURNS trigger LANGUAGE plpgsql AS $$ DECLARE source_id text; BEGIN
 IF TG_TABLE_NAME='workflows_integrationprobe' THEN
  IF (SELECT payload->>'family' FROM workflows_integrationcontract WHERE id=NEW.contract_id) IS DISTINCT FROM 'protection' THEN RETURN NEW; END IF;
  source_id=NEW.intent->>'source_job';
 ELSE source_id=NEW.job_id::text;
 END IF;
 IF source_id IS NULL THEN RETURN NEW; END IF;
 IF source_id !~ '^[0-9]+$' THEN RAISE EXCEPTION 'Exact positive protection source identity required'; END IF;
 IF source_id::numeric<1 THEN RAISE EXCEPTION 'Exact positive protection source identity required'; END IF;
 IF EXISTS(SELECT 1 FROM workflows_recoveryjob j JOIN workflows_recoveryplan p ON p.id=j.plan_id WHERE j.id=source_id::bigint AND p.payload ? 'private_protection_packet_ids') THEN RAISE EXCEPTION 'AF13 protection inventory requires an explicit native readiness contract'; END IF;
 RETURN NEW; END $$;
CREATE TRIGGER psl_accepted_protection_boundary BEFORE INSERT ON workflows_integrationprobe FOR EACH ROW EXECUTE FUNCTION psl_accepted_protection_native_boundary();
CREATE TRIGGER psl_accepted_protection_boundary BEFORE INSERT ON workflows_privatefilereadiness FOR EACH ROW EXECUTE FUNCTION psl_accepted_protection_native_boundary();
CREATE TRIGGER psl_accepted_protection_boundary BEFORE INSERT ON workflows_privateprotectionreadiness FOR EACH ROW EXECUTE FUNCTION psl_accepted_protection_native_boundary();
"""

class Migration(migrations.Migration):
 dependencies=[('workflows','0015_accepted_protection_operations')]
 operations=[migrations.RunSQL(SQL,"DROP TRIGGER psl_accepted_protection_boundary ON workflows_integrationprobe; DROP TRIGGER psl_accepted_protection_boundary ON workflows_privatefilereadiness; DROP TRIGGER psl_accepted_protection_boundary ON workflows_privateprotectionreadiness; DROP FUNCTION psl_accepted_protection_native_boundary();")]

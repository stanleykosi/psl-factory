from django.db import migrations

class Migration(migrations.Migration):
    dependencies=[('policy','0008_impact_correction_effects'),('documents','0012_native_validation_guards')]
    operations=[migrations.RunSQL("""
CREATE OR REPLACE FUNCTION psl_pilot_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE selected policy_pilotcontract%ROWTYPE;
BEGIN
 IF TG_TABLE_NAME='policy_pilotcontract' THEN
  IF (NEW.payload->>'format' IS NULL OR NEW.payload->>'format' NOT IN ('psl.pilot-contract/v1','psl.pilot-contract/v2'))
   OR (NEW.payload->>'format'='psl.pilot-contract/v2' AND (
    jsonb_typeof(NEW.payload->'acceptance_reviews') IS DISTINCT FROM 'array'
    OR jsonb_array_length(NEW.payload->'acceptance_reviews') NOT BETWEEN 1 AND 20
    OR EXISTS (SELECT 1 FROM jsonb_array_elements_text(NEW.payload->'acceptance_reviews') AS a(value) LEFT JOIN documents_validationreview r ON r.id=value::bigint LEFT JOIN documents_validationpackage p ON p.id=r.package_id WHERE r.kind IS DISTINCT FROM 'acceptance' OR p.case_id IS DISTINCT FROM NEW.case_id)
    OR (SELECT count(DISTINCT value) FROM jsonb_array_elements_text(NEW.payload->'acceptance_reviews') AS a(value))<>jsonb_array_length(NEW.payload->'acceptance_reviews')))
   OR NEW.payload->>'case_id' IS DISTINCT FROM NEW.case_id::text
   OR NEW.payload->'read_only' IS DISTINCT FROM 'true'::jsonb
   OR NEW.version<1 OR NEW.sha256 !~ '^[0-9a-f]{64}$'
  THEN RAISE EXCEPTION 'PSL invalid read-only pilot contract'; END IF;
 ELSE
  SELECT * INTO selected FROM policy_pilotcontract WHERE id=NEW.contract_id;
  IF NEW.snapshot->>'format' IS DISTINCT FROM 'psl.pilot-observation/v1'
   OR NEW.snapshot->>'case_id' IS DISTINCT FROM selected.case_id::text
   OR NEW.snapshot->>'contract' IS DISTINCT FROM selected.sha256
   OR NEW.snapshot->'boundaries'->'read_only' IS DISTINCT FROM 'true'::jsonb
   OR NEW.snapshot->'boundaries'->'effect_tools' IS DISTINCT FROM '[]'::jsonb
   OR NEW.snapshot->'boundaries'->'effects_scheduled' IS DISTINCT FROM 'false'::jsonb
   OR NEW.snapshot->'boundaries'->'operational_acceptance' IS DISTINCT FROM 'false'::jsonb
   OR NEW.sha256 !~ '^[0-9a-f]{64}$' OR NEW.operation_key !~ '^[0-9a-f]{64}$'
  THEN RAISE EXCEPTION 'PSL invalid pilot observation identity'; END IF;
 END IF;
 RETURN NEW;
END; $$;
""", """
CREATE OR REPLACE FUNCTION psl_pilot_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE selected policy_pilotcontract%ROWTYPE;
BEGIN
 IF TG_TABLE_NAME='policy_pilotcontract' THEN
  IF NEW.payload->>'format' IS DISTINCT FROM 'psl.pilot-contract/v1'
   OR NEW.payload->>'case_id' IS DISTINCT FROM NEW.case_id::text
   OR NEW.payload->'read_only' IS DISTINCT FROM 'true'::jsonb
   OR NEW.version<1 OR NEW.sha256 !~ '^[0-9a-f]{64}$'
  THEN RAISE EXCEPTION 'PSL invalid read-only pilot contract'; END IF;
 ELSE
  SELECT * INTO selected FROM policy_pilotcontract WHERE id=NEW.contract_id;
  IF NEW.snapshot->>'format' IS DISTINCT FROM 'psl.pilot-observation/v1'
   OR NEW.snapshot->>'case_id' IS DISTINCT FROM selected.case_id::text
   OR NEW.snapshot->>'contract' IS DISTINCT FROM selected.sha256
   OR NEW.snapshot->'boundaries'->'read_only' IS DISTINCT FROM 'true'::jsonb
   OR NEW.snapshot->'boundaries'->'effect_tools' IS DISTINCT FROM '[]'::jsonb
   OR NEW.snapshot->'boundaries'->'effects_scheduled' IS DISTINCT FROM 'false'::jsonb
   OR NEW.snapshot->'boundaries'->'operational_acceptance' IS DISTINCT FROM 'false'::jsonb
   OR NEW.sha256 !~ '^[0-9a-f]{64}$' OR NEW.operation_key !~ '^[0-9a-f]{64}$'
  THEN RAISE EXCEPTION 'PSL invalid pilot observation identity'; END IF;
 END IF;
 RETURN NEW;
END; $$;
""")]

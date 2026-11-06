from django.db import migrations

SQL="""
CREATE TRIGGER psl_immutable BEFORE UPDATE OR DELETE ON workflows_acceptedprotectionreadiness FOR EACH ROW EXECUTE FUNCTION psl_append_only();
CREATE FUNCTION psl_af13_native_binding() RETURNS trigger LANGUAGE plpgsql AS $$ DECLARE j workflows_recoveryjob; p workflows_recoveryplan; c workflows_integrationcontract; inv jsonb; fin jsonb; BEGIN
 SELECT * INTO c FROM workflows_integrationcontract WHERE id=NEW.contract_id FOR UPDATE;
 SELECT * INTO j FROM workflows_recoveryjob WHERE id=NEW.job_id;
 SELECT * INTO p FROM workflows_recoveryplan WHERE id=j.plan_id;
 SELECT coalesce(jsonb_agg(jsonb_build_object('packet',value->'packet','packet_sha256',value->'packet_sha256','metadata_sha256',value->'metadata_sha256') ORDER BY ord),'[]') INTO inv FROM jsonb_array_elements(j.intent->'manifest'->'accepted_private_protection') WITH ORDINALITY x(value,ord);
 SELECT coalesce(jsonb_agg(jsonb_build_object('packet',value->'packet','packet_sha256',value->'packet_sha256','metadata_sha256',value->'metadata_sha256') ORDER BY ord),'[]') INTO fin FROM jsonb_array_elements(coalesce(j.intent->'manifest'->'accepted_private_readiness','[]')) WITH ORDINALITY x(value,ord);
 IF c.case_id IS DISTINCT FROM p.case_id OR c.actor_id IS DISTINCT FROM NEW.actor_id OR c.payload->>'kind' IS DISTINCT FROM 'adapter' OR c.payload->>'family' IS DISTINCT FROM 'protection' OR c.payload->>'implementation' IS DISTINCT FROM 'internal_postgres_session_v1' OR c.payload->>'target_key' IS DISTINCT FROM 'internal:protection' OR c.payload->'capabilities' IS NULL OR NOT (c.payload->'capabilities' @> '["health","receipt_lookup"]') OR jsonb_array_length(c.payload->'capabilities')<>2 OR j.kind NOT IN ('export','backup','restore') OR NOT (p.payload ? 'private_protection_packet_ids') OR inv='[]' THEN RAISE EXCEPTION 'Exact AF13 native source required'; END IF;
 IF NEW.snapshot->>'schema_ref' IS DISTINCT FROM 'schema:psl/accepted-protection-native-source/v1' OR NEW.snapshot->>'job' IS DISTINCT FROM j.id::text OR NEW.snapshot->>'job_kind' IS DISTINCT FROM j.kind OR NEW.snapshot->>'plan' IS DISTINCT FROM p.id::text OR NEW.snapshot->>'case' IS DISTINCT FROM p.case_id::text OR NEW.snapshot->>'plan_sha256' IS DISTINCT FROM p.sha256 OR NEW.snapshot->'storage_identity' IS DISTINCT FROM j.intent->'storage_identity' OR NEW.snapshot->'target_identity' IS DISTINCT FROM j.intent->'target_identity' OR NEW.snapshot->'protection_inventory' IS DISTINCT FROM inv OR NEW.snapshot->'finance_inventory' IS DISTINCT FROM fin OR coalesce(NEW.snapshot->>'manifest_sha256','')!~'^[a-f0-9]{64}$' OR coalesce(NEW.snapshot->>'intent_sha256','')!~'^[a-f0-9]{64}$' OR NEW.snapshot->'current_authority_restored' IS DISTINCT FROM 'false'::jsonb OR NEW.snapshot - ARRAY['schema_ref','job','job_kind','plan','case','plan_sha256','manifest_sha256','intent_sha256','protection_inventory','finance_inventory','storage_identity','target_identity','current_authority_restored']<>'{}' OR (SELECT count(*) FROM jsonb_object_keys(NEW.snapshot))<>13 THEN RAISE EXCEPTION 'Exact closed AF13 native inventory required'; END IF;
 IF EXISTS(SELECT 1 FROM workflows_privatefilereadiness WHERE contract_id=c.id) OR EXISTS(SELECT 1 FROM workflows_privateprotectionreadiness WHERE contract_id=c.id) OR EXISTS(SELECT 1 FROM finance_financepublicationreadiness WHERE contract_id=c.id) THEN RAISE EXCEPTION 'Exclusive native inventory type required'; END IF;
 IF EXISTS(SELECT 1 FROM workflows_integrationprobe WHERE contract_id=c.id) OR EXISTS(SELECT 1 FROM workflows_integrationobservation WHERE contract_id=c.id) OR EXISTS(SELECT 1 FROM workflows_integrationassessment WHERE contract_id=c.id) OR EXISTS(SELECT 1 FROM workflows_integrationselection WHERE contract_id=c.id) THEN RAISE EXCEPTION 'AF13 binding must precede readiness history'; END IF;
 RETURN NEW; END $$;
CREATE TRIGGER psl_af13_lineage BEFORE INSERT ON workflows_acceptedprotectionreadiness FOR EACH ROW EXECUTE FUNCTION psl_af13_native_binding();
CREATE FUNCTION psl_af13_native_exclusive() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
 PERFORM 1 FROM workflows_integrationcontract WHERE id=NEW.contract_id FOR UPDATE;
 IF EXISTS(SELECT 1 FROM workflows_acceptedprotectionreadiness WHERE contract_id=NEW.contract_id) THEN RAISE EXCEPTION 'Exclusive AF13 native inventory type required'; END IF;
 RETURN NEW; END $$;
CREATE TRIGGER psl_af13_exclusive BEFORE INSERT ON workflows_privatefilereadiness FOR EACH ROW EXECUTE FUNCTION psl_af13_native_exclusive();
CREATE TRIGGER psl_af13_exclusive BEFORE INSERT ON workflows_privateprotectionreadiness FOR EACH ROW EXECUTE FUNCTION psl_af13_native_exclusive();
CREATE TRIGGER psl_af13_exclusive BEFORE INSERT ON finance_financepublicationreadiness FOR EACH ROW EXECUTE FUNCTION psl_af13_native_exclusive();
CREATE FUNCTION psl_af13_native_probe() RETURNS trigger LANGUAGE plpgsql AS $$ DECLARE b workflows_acceptedprotectionreadiness; BEGIN
 PERFORM 1 FROM workflows_integrationcontract WHERE id=NEW.contract_id FOR UPDATE;
 SELECT * INTO b FROM workflows_acceptedprotectionreadiness WHERE contract_id=NEW.contract_id;
 IF FOUND THEN
  IF NEW.intent->'native_accepted_protection' IS DISTINCT FROM jsonb_build_object('binding',b.id,'sha256',b.sha256,'source',b.snapshot) OR NEW.intent->>'kind' NOT IN ('health','receipt') OR NEW.intent ?| ARRAY['native_file','native_protection','native_publication'] OR (NEW.intent->>'kind'='receipt' AND NEW.intent->'source_job' IS DISTINCT FROM to_jsonb(b.job_id)) OR (NEW.intent->>'kind'='health' AND NEW.intent->'source_job' IS DISTINCT FROM 'null'::jsonb) THEN RAISE EXCEPTION 'Exact AF13 native probe provenance required'; END IF;
 ELSIF NEW.intent ? 'native_accepted_protection' OR EXISTS(SELECT 1 FROM workflows_integrationcontract c JOIN workflows_integrationcontract old ON old.case_id=c.case_id AND old.reference=c.reference JOIN workflows_acceptedprotectionreadiness previous ON previous.contract_id=old.id WHERE c.id=NEW.contract_id) THEN RAISE EXCEPTION 'Unbound AF13 native probe or private history downgrade';
 END IF;
 RETURN NEW; END $$;
CREATE TRIGGER psl_af13_lineage BEFORE INSERT ON workflows_integrationprobe FOR EACH ROW EXECUTE FUNCTION psl_af13_native_probe();
CREATE FUNCTION psl_af13_native_observation() RETURNS trigger LANGUAGE plpgsql AS $$ DECLARE b workflows_acceptedprotectionreadiness; j workflows_integrationprobe; v jsonb; inner_v jsonb; fields text[]; BEGIN
 PERFORM 1 FROM workflows_integrationcontract WHERE id=NEW.contract_id FOR UPDATE;
 SELECT * INTO b FROM workflows_acceptedprotectionreadiness WHERE contract_id=NEW.contract_id;
 IF FOUND AND NEW.job_id IS NOT NULL THEN
  SELECT * INTO j FROM workflows_integrationprobe WHERE id=NEW.job_id;
  IF j.contract_id IS DISTINCT FROM NEW.contract_id OR j.actor_id IS DISTINCT FROM NEW.actor_id OR NEW.payload->'native_accepted_protection' IS DISTINCT FROM j.intent->'native_accepted_protection' OR NEW.payload->'kind' IS DISTINCT FROM j.intent->'kind' OR NEW.payload->'password_authentication_proven' IS DISTINCT FROM 'false'::jsonb OR NEW.payload->'storage_write_proven' IS DISTINCT FROM 'false'::jsonb OR NEW.payload->'authenticated_transport' IS DISTINCT FROM 'true'::jsonb OR NEW.payload - ARRAY['kind','classification','authenticated_transport','outcome','identity_match','capabilities_verified','password_authentication_proven','storage_probe','storage_write_proven','lookup_verified','native_accepted_protection','accepted_protection_receipt','observed_at']<>'{}' THEN RAISE EXCEPTION 'Closed AF13 native observation required'; END IF;
  IF NEW.payload->>'kind'='receipt' THEN
   v=NEW.payload->'accepted_protection_receipt';inner_v=v->'receipt';
   IF v->>'schema_ref' IS DISTINCT FROM 'schema:psl/accepted-protection-native-receipt/v1' OR v->'job_kind' IS DISTINCT FROM b.snapshot->'job_kind' OR v - ARRAY['schema_ref','job_kind','receipt']<>'{}' OR NOT (v ?& ARRAY['schema_ref','job_kind','receipt']) THEN RAISE EXCEPTION 'Closed AF13 receipt discriminator required'; END IF;
   fields=CASE WHEN b.snapshot->>'job_kind'='restore' THEN ARRAY['state','operation_key_sha256','manifest_sha256','payload_bodies_included','current_authority_restored','full_database_restore'] ELSE ARRAY['state','job_kind','operation_key_sha256','manifest_sha256','storage_identity','artifact','file_verified','payload_bodies_included','current_authority_restored','full_database_backup','full_database_export'] END;
   IF inner_v IS NULL OR NOT (inner_v ?& fields) OR inner_v-fields<>'{}' OR inner_v->'manifest_sha256' IS DISTINCT FROM b.snapshot->'manifest_sha256' OR inner_v->>'state' NOT IN ('found','not_found') OR inner_v->'payload_bodies_included' IS DISTINCT FROM 'false'::jsonb OR inner_v->'current_authority_restored' IS DISTINCT FROM 'false'::jsonb OR EXISTS(SELECT 1 FROM jsonb_each(inner_v) x WHERE x.key LIKE 'full_database_%' AND x.value<>'false') THEN RAISE EXCEPTION 'Closed AF13 receipt provenance required'; END IF;
   IF b.snapshot->>'job_kind'<>'restore' AND (inner_v->'job_kind' IS DISTINCT FROM b.snapshot->'job_kind' OR inner_v->'storage_identity' IS DISTINCT FROM b.snapshot->'storage_identity' OR inner_v->'file_verified' IS DISTINCT FROM to_jsonb(b.snapshot->>'job_kind'='backup' AND inner_v->>'state'='found') OR (inner_v->>'artifact' IS NOT NULL AND NOT EXISTS(SELECT 1 FROM workflows_recoveryartifact a WHERE a.id::text=inner_v->>'artifact' AND a.job_id=b.job_id AND a.sha256=b.snapshot->>'manifest_sha256')) OR (b.snapshot->>'job_kind'='export' AND inner_v->>'state'='found' AND inner_v->>'artifact' IS NULL)) THEN RAISE EXCEPTION 'Exact AF13 artifact receipt required'; END IF;
  END IF;
 ELSIF NEW.payload ?| ARRAY['native_accepted_protection','accepted_protection_receipt'] THEN RAISE EXCEPTION 'Unbound AF13 native observation'; END IF;
 RETURN NEW; END $$;
CREATE TRIGGER psl_af13_lineage BEFORE INSERT ON workflows_integrationobservation FOR EACH ROW EXECUTE FUNCTION psl_af13_native_observation();
CREATE FUNCTION psl_af13_no_readiness_cycle() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
 IF EXISTS(SELECT 1 FROM jsonb_array_elements_text(NEW.payload->'private_protection_packet_ids') x JOIN documents_privateprotectionpacket b ON b.id::text=x.value JOIN documents_validationpackage p ON p.id=b.package_id WHERE p.payload->'policy_components' ? 'INT.accepted_protection_readiness') THEN RAISE EXCEPTION 'AF13 source cannot depend on downstream native readiness'; END IF;
 RETURN NEW; END $$;
CREATE TRIGGER psl_af13_no_cycle BEFORE INSERT ON workflows_recoveryplan FOR EACH ROW EXECUTE FUNCTION psl_af13_no_readiness_cycle();
CREATE OR REPLACE FUNCTION psl_accepted_protection_native_boundary() RETURNS trigger LANGUAGE plpgsql AS $$ DECLARE source_id text; BEGIN
 IF TG_TABLE_NAME='workflows_integrationprobe' THEN
  IF (SELECT payload->>'family' FROM workflows_integrationcontract WHERE id=NEW.contract_id) IS DISTINCT FROM 'protection' THEN RETURN NEW; END IF;
  source_id=NEW.intent->>'source_job';
 ELSE source_id=NEW.job_id::text;
 END IF;
 IF source_id IS NULL THEN RETURN NEW; END IF;
 IF source_id !~ '^[0-9]+$' THEN RAISE EXCEPTION 'Exact positive protection source identity required'; END IF;
 IF source_id::numeric<1 THEN RAISE EXCEPTION 'Exact positive protection source identity required'; END IF;
 IF EXISTS(SELECT 1 FROM workflows_recoveryjob j JOIN workflows_recoveryplan p ON p.id=j.plan_id WHERE j.id=source_id::bigint AND p.payload ? 'private_protection_packet_ids') THEN
  IF TG_TABLE_NAME='workflows_integrationprobe' THEN
   IF EXISTS(SELECT 1 FROM workflows_acceptedprotectionreadiness b WHERE b.contract_id=NEW.contract_id AND b.job_id=source_id::bigint AND NEW.intent->'native_accepted_protection'=jsonb_build_object('binding',b.id,'sha256',b.sha256,'source',b.snapshot)) THEN RETURN NEW; END IF;
  END IF;
  RAISE EXCEPTION 'AF13 protection inventory requires an explicit native readiness contract'; END IF;
 RETURN NEW; END $$;CREATE OR REPLACE FUNCTION psl_private_protection_source()RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
IF EXISTS(SELECT 1 FROM workflows_integrationcontract c JOIN workflows_recoveryjob j ON j.id::text=NEW.intent->>'source_job' JOIN workflows_recoveryplan p ON p.id=j.plan_id WHERE c.id=NEW.contract_id AND c.payload->>'family'='protection' AND p.payload ? 'private_readiness_packet_ids') AND NOT EXISTS(SELECT 1 FROM workflows_privateprotectionreadiness b JOIN workflows_recoveryjob j ON j.id=b.job_id WHERE b.contract_id=NEW.contract_id AND j.kind='restore' AND b.job_id::text=NEW.intent->>'source_job') AND NOT EXISTS(SELECT 1 FROM workflows_privatefilereadiness b WHERE b.contract_id=NEW.contract_id AND b.job_id::text=NEW.intent->>'source_job') AND NOT EXISTS(SELECT 1 FROM workflows_acceptedprotectionreadiness b WHERE b.contract_id=NEW.contract_id AND b.job_id::text=NEW.intent->>'source_job') THEN RAISE EXCEPTION 'Private metadata receipt source requires exact native binding'; END IF;
RETURN NEW; END $$;"""

REVERSE="""
DROP TRIGGER psl_af13_no_cycle ON workflows_recoveryplan; DROP FUNCTION psl_af13_no_readiness_cycle();
DROP TRIGGER psl_af13_lineage ON workflows_integrationobservation; DROP FUNCTION psl_af13_native_observation();
DROP TRIGGER psl_af13_lineage ON workflows_integrationprobe; DROP FUNCTION psl_af13_native_probe();
DROP TRIGGER psl_af13_exclusive ON finance_financepublicationreadiness;
DROP TRIGGER psl_af13_exclusive ON workflows_privateprotectionreadiness;
DROP TRIGGER psl_af13_exclusive ON workflows_privatefilereadiness; DROP FUNCTION psl_af13_native_exclusive();
DROP TRIGGER psl_af13_lineage ON workflows_acceptedprotectionreadiness; DROP FUNCTION psl_af13_native_binding();
DROP TRIGGER psl_immutable ON workflows_acceptedprotectionreadiness;
CREATE OR REPLACE FUNCTION psl_accepted_protection_native_boundary() RETURNS trigger LANGUAGE plpgsql AS $$ DECLARE source_id text; BEGIN
 IF TG_TABLE_NAME='workflows_integrationprobe' THEN
  IF (SELECT payload->>'family' FROM workflows_integrationcontract WHERE id=NEW.contract_id) IS DISTINCT FROM 'protection' THEN RETURN NEW; END IF;
  source_id=NEW.intent->>'source_job';
 ELSE source_id=NEW.job_id::text;
 END IF;
 IF source_id IS NULL THEN RETURN NEW; END IF;
 IF source_id !~ '^[0-9]+$' THEN RAISE EXCEPTION 'Exact positive protection source identity required'; END IF;
 IF source_id::numeric<1 THEN RAISE EXCEPTION 'Exact positive protection source identity required'; END IF;
 IF EXISTS(SELECT 1 FROM workflows_recoveryjob j JOIN workflows_recoveryplan p ON p.id=j.plan_id WHERE j.id=source_id::bigint AND p.payload ? 'private_protection_packet_ids') THEN RAISE EXCEPTION 'AF13 protection inventory requires an explicit native readiness contract'; END IF;
 RETURN NEW; END $$;CREATE OR REPLACE FUNCTION psl_private_protection_source()RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
IF EXISTS(SELECT 1 FROM workflows_integrationcontract c JOIN workflows_recoveryjob j ON j.id::text=NEW.intent->>'source_job' JOIN workflows_recoveryplan p ON p.id=j.plan_id WHERE c.id=NEW.contract_id AND c.payload->>'family'='protection' AND p.payload ? 'private_readiness_packet_ids') AND NOT EXISTS(SELECT 1 FROM workflows_privateprotectionreadiness b JOIN workflows_recoveryjob j ON j.id=b.job_id WHERE b.contract_id=NEW.contract_id AND j.kind='restore' AND b.job_id::text=NEW.intent->>'source_job') AND NOT EXISTS(SELECT 1 FROM workflows_privatefilereadiness b WHERE b.contract_id=NEW.contract_id AND b.job_id::text=NEW.intent->>'source_job') THEN RAISE EXCEPTION 'Private metadata receipt source requires exact native binding'; END IF;
RETURN NEW; END $$;"""

class Migration(migrations.Migration):
 dependencies=[('workflows','0017_acceptedprotectionreadiness')]
 operations=[migrations.RunSQL(SQL,REVERSE)]

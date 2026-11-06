from django.db import migrations

SQL="""
CREATE FUNCTION psl_accepted_protection_sources(selected jsonb) RETURNS SETOF bigint LANGUAGE sql STABLE AS $$
 WITH RECURSIVE sources(plan_id) AS (
  SELECT (b.snapshot->'evidence'->>'plan')::bigint FROM documents_privateprotectionpacket b WHERE selected @> jsonb_build_array(b.id)
  UNION
  SELECT (b.snapshot->'evidence'->>'plan')::bigint FROM sources s JOIN workflows_recoveryplan p ON p.id=s.plan_id
  JOIN documents_privateprotectionpacket b ON coalesce(p.payload->'private_protection_packet_ids','[]'::jsonb) @> jsonb_build_array(b.id)
 ) SELECT plan_id FROM sources;
$$;
CREATE FUNCTION psl_accepted_protection_plan() RETURNS trigger LANGUAGE plpgsql AS $$ DECLARE item jsonb; BEGIN
 PERFORM 1 FROM core_case WHERE id=NEW.case_id FOR UPDATE;
 IF EXISTS(SELECT 1 FROM workflows_recoveryplan p WHERE p.case_id=NEW.case_id AND p.reference=NEW.reference AND p.payload ? 'private_protection_packet_ids') AND NOT (NEW.payload ? 'private_protection_packet_ids') THEN RAISE EXCEPTION 'Protection plan history cannot become public'; END IF;
 IF NEW.payload ? 'private_protection_packet_ids' THEN
  IF NEW.payload->>'scope' IS DISTINCT FROM 'portable_case_metadata_v1' OR jsonb_typeof(NEW.payload->'private_protection_packet_ids') IS DISTINCT FROM 'array' THEN RAISE EXCEPTION 'Explicit AF13 protection plan inventory required'; END IF;
  IF jsonb_array_length(NEW.payload->'private_protection_packet_ids') NOT BETWEEN 1 AND 100 OR (SELECT count(DISTINCT value) FROM jsonb_array_elements(NEW.payload->'private_protection_packet_ids'))<>jsonb_array_length(NEW.payload->'private_protection_packet_ids') THEN RAISE EXCEPTION 'Distinct bounded AF13 protection inventory required'; END IF;
  FOR item IN SELECT value FROM jsonb_array_elements(NEW.payload->'private_protection_packet_ids') LOOP
   IF jsonb_typeof(item)<>'number' OR NOT EXISTS(SELECT 1 FROM documents_privateprotectionpacket b JOIN documents_validationpackage p ON p.id=b.package_id WHERE b.id::text=item::text AND b.case_id=NEW.case_id AND (p.payload->'process_ids') <@ (NEW.payload->'process_ids') AND NOT (p.payload->'policy_components' ? 'OPS.accepted_protection_rules')) THEN RAISE EXCEPTION 'Exact AF13 protection plan case/process scope required'; END IF;
  END LOOP;
  IF EXISTS(SELECT 1 FROM workflows_recoveryplan p WHERE p.id IN (SELECT psl_accepted_protection_sources(NEW.payload->'private_protection_packet_ids')) AND p.case_id=NEW.case_id AND p.reference=NEW.reference) THEN RAISE EXCEPTION 'Protection metadata plan cannot supersede its own source closure'; END IF;
 END IF;
 RETURN NEW; END $$;
CREATE TRIGGER psl_accepted_protection BEFORE INSERT ON workflows_recoveryplan FOR EACH ROW EXECUTE FUNCTION psl_accepted_protection_plan();

CREATE FUNCTION psl_accepted_protection_effect() RETURNS trigger LANGUAGE plpgsql AS $$ DECLARE p workflows_recoveryplan; m jsonb; item jsonb; actual jsonb; am jsonb; v jsonb; BEGIN
 IF TG_TABLE_NAME='workflows_recoveryjob' THEN SELECT * INTO p FROM workflows_recoveryplan WHERE id=NEW.plan_id; m=NEW.intent->'manifest';
 ELSE SELECT r.* INTO p FROM workflows_recoveryplan r JOIN workflows_recoveryjob j ON j.plan_id=r.id WHERE j.id=NEW.job_id; SELECT intent->'manifest' INTO m FROM workflows_recoveryjob WHERE id=NEW.job_id; am=NEW.manifest;
 END IF;
 IF (p.payload ? 'private_protection_packet_ids') OR (m ? 'accepted_private_protection') OR (am ? 'accepted_private_protection') THEN
  IF am IS NOT NULL AND am IS DISTINCT FROM m THEN RAISE EXCEPTION 'Exact sealed AF13 protection artifact required'; END IF;
  IF m - ARRAY['schema','case_id','evidence','jobs','source_grants','omitted_families','evidence_bodies_included','credentials_included','business_jobs_reenacted','private_metadata_schema','accepted_private_readiness','protection_metadata_schema','accepted_private_protection','current_authority_restored']<>'{}'::jsonb OR EXISTS(SELECT 1 FROM unnest(ARRAY['evidence_bodies_included','credentials_included','business_jobs_reenacted']) flag WHERE m->flag IS DISTINCT FROM 'false'::jsonb) THEN RAISE EXCEPTION 'Closed portable protection metadata manifest required'; END IF;
  IF NOT (p.payload ? 'private_protection_packet_ids') OR (m->>'protection_metadata_schema') IS DISTINCT FROM 'accepted_private_protection_v1' OR (m->'current_authority_restored') IS DISTINCT FROM 'false'::jsonb OR jsonb_typeof(m->'accepted_private_protection') IS DISTINCT FROM 'array' THEN RAISE EXCEPTION 'Explicit AF13 protection effect binding required'; END IF;
  SELECT jsonb_agg(value->'packet') INTO actual FROM jsonb_array_elements(m->'accepted_private_protection');
  IF actual IS DISTINCT FROM p.payload->'private_protection_packet_ids' THEN RAISE EXCEPTION 'Exact selected AF13 protection effect inventory required'; END IF;
  FOR item IN SELECT value FROM jsonb_array_elements(m->'accepted_private_protection') LOOP
   v=item->'metadata';
   IF jsonb_typeof(item) IS DISTINCT FROM 'object' OR item - ARRAY['packet','packet_sha256','metadata','metadata_sha256','accepted_at_capture','current_authority_restored']<>'{}'::jsonb OR (SELECT count(*) FROM jsonb_object_keys(item))<>6 OR item->'accepted_at_capture' IS DISTINCT FROM 'true'::jsonb OR item->'current_authority_restored' IS DISTINCT FROM 'false'::jsonb OR coalesce(item->>'metadata_sha256','')!~'^[a-f0-9]{64}$' THEN RAISE EXCEPTION 'Closed AF13 protection metadata row required'; END IF;
   IF jsonb_typeof(v) IS DISTINCT FROM 'object' OR v - ARRAY['packet','sha256','package','process_ids','level','acceptance_review','acceptor','pins','evidence','scope','full_database_backup','full_database_export','payload_bodies_included','current_authority_restored','full_database_restore','native_quickbooks_verified','operational_acceptance','whole_product_accepted','deployment_authorized']<>'{}'::jsonb OR (SELECT count(*) FROM jsonb_object_keys(v))<>19 THEN RAISE EXCEPTION 'Closed AF13 protection metadata fields required'; END IF;
   IF EXISTS(SELECT 1 FROM unnest(ARRAY['full_database_backup','full_database_export','payload_bodies_included','current_authority_restored','full_database_restore','native_quickbooks_verified','operational_acceptance','whole_product_accepted','deployment_authorized']) flag WHERE (v->flag) IS DISTINCT FROM 'false'::jsonb) THEN RAISE EXCEPTION 'Protection metadata cannot restore authority or acceptance'; END IF;
   IF NOT EXISTS(SELECT 1 FROM documents_privateprotectionpacket b JOIN documents_validationpackage vp ON vp.id=b.package_id JOIN documents_validationreview r ON r.package_id=b.package_id
    WHERE b.id::text=item->>'packet' AND b.case_id=p.case_id AND b.sha256=item->>'packet_sha256' AND v->'packet'=item->'packet' AND v->>'sha256'=b.sha256 AND v->>'package'=b.package_id::text AND v->'process_ids'=vp.payload->'process_ids' AND v->'level'=vp.payload->'level' AND v->'evidence'=b.snapshot->'evidence' AND v->>'scope'='selected AF13 evidence only' AND r.id::text=v->>'acceptance_review' AND r.kind='acceptance' AND r.verdict='approve' AND r.actor_id::text=v->>'acceptor' AND r.snapshot->'private_protection'=v->'pins') THEN RAISE EXCEPTION 'Exact accepted AF13 protection effect lineage required'; END IF;
  END LOOP;
 END IF;
 RETURN NEW; END $$;
CREATE TRIGGER psl_accepted_protection BEFORE INSERT ON workflows_recoveryjob FOR EACH ROW EXECUTE FUNCTION psl_accepted_protection_effect();
CREATE TRIGGER psl_accepted_protection BEFORE INSERT ON workflows_recoveryartifact FOR EACH ROW EXECUTE FUNCTION psl_accepted_protection_effect();
"""

class Migration(migrations.Migration):
 dependencies=[('workflows','0014_private_file_readiness_guards'),('documents','0011_native_file_acceptance')]
 operations=[migrations.RunSQL(SQL,"DROP TRIGGER psl_accepted_protection ON workflows_recoveryartifact; DROP TRIGGER psl_accepted_protection ON workflows_recoveryjob; DROP FUNCTION psl_accepted_protection_effect(); DROP TRIGGER psl_accepted_protection ON workflows_recoveryplan; DROP FUNCTION psl_accepted_protection_plan(); DROP FUNCTION psl_accepted_protection_sources(jsonb);")]

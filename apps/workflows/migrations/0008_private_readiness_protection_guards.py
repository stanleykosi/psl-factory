from django.db import migrations

class Migration(migrations.Migration):
 dependencies=[('workflows','0007_integration_guards'),('finance','0053_private_readiness_guards')]
 operations=[migrations.RunSQL("""
 CREATE FUNCTION psl_private_readiness_plan() RETURNS trigger LANGUAGE plpgsql AS $$ DECLARE item jsonb; BEGIN
 IF NEW.payload ? 'private_readiness_packet_ids' THEN
  IF NEW.payload->>'scope'<>'portable_case_metadata_v1' OR jsonb_typeof(NEW.payload->'private_readiness_packet_ids')<>'array' OR jsonb_array_length(NEW.payload->'private_readiness_packet_ids')=0 THEN RAISE EXCEPTION 'Explicit private metadata plan inventory required'; END IF;
  FOR item IN SELECT value FROM jsonb_array_elements(NEW.payload->'private_readiness_packet_ids') LOOP
   IF NOT EXISTS(SELECT 1 FROM finance_privatereadinesspacket b JOIN documents_validationpackage p ON p.id=b.package_id WHERE b.id::text=item::text AND b.case_id=NEW.case_id AND p.payload->'process_ids' <@ NEW.payload->'process_ids') THEN RAISE EXCEPTION 'Exact private metadata plan case/source scope required'; END IF;
  END LOOP;
 END IF;
 RETURN NEW; END $$;
 CREATE TRIGGER psl_private_lineage BEFORE INSERT ON workflows_recoveryplan FOR EACH ROW EXECUTE FUNCTION psl_private_readiness_plan();
 CREATE FUNCTION psl_private_readiness_effect() RETURNS trigger LANGUAGE plpgsql AS $$ DECLARE p workflows_recoveryplan; m jsonb; item jsonb; actual jsonb; artifact_manifest jsonb; BEGIN
 IF TG_TABLE_NAME='workflows_recoveryjob' THEN SELECT * INTO p FROM workflows_recoveryplan WHERE id=NEW.plan_id; m=NEW.intent->'manifest';
 ELSE SELECT r.* INTO p FROM workflows_recoveryplan r JOIN workflows_recoveryjob j ON j.plan_id=r.id WHERE j.id=NEW.job_id; SELECT intent->'manifest' INTO m FROM workflows_recoveryjob WHERE id=NEW.job_id;
  artifact_manifest=NEW.manifest;
 END IF;
 IF (p.payload ? 'private_readiness_packet_ids') OR (m ? 'accepted_private_readiness') OR (artifact_manifest ? 'accepted_private_readiness') THEN
  IF artifact_manifest IS NOT NULL AND artifact_manifest IS DISTINCT FROM m THEN RAISE EXCEPTION 'Exact sealed protection artifact required'; END IF;
  IF NOT (p.payload ? 'private_readiness_packet_ids') OR m->>'private_metadata_schema'<>'accepted_private_readiness_v1' OR m->>'current_authority_restored'<>'false' OR jsonb_typeof(m->'accepted_private_readiness') IS DISTINCT FROM 'array' THEN RAISE EXCEPTION 'Explicit private metadata effect binding required'; END IF;
  SELECT jsonb_agg(value->'packet') INTO actual FROM jsonb_array_elements(m->'accepted_private_readiness');
  IF actual IS DISTINCT FROM p.payload->'private_readiness_packet_ids' THEN RAISE EXCEPTION 'Exact selected private metadata effect inventory required'; END IF;
  FOR item IN SELECT value FROM jsonb_array_elements(m->'accepted_private_readiness') LOOP
   IF NOT EXISTS(SELECT 1 FROM finance_privatereadinesspacket b JOIN documents_validationreview r ON r.package_id=b.package_id WHERE b.id::text=item->>'packet' AND b.case_id=p.case_id AND b.sha256=item->>'packet_sha256' AND r.id::text=item->'metadata'->>'acceptance_review' AND r.kind='acceptance' AND r.verdict='approve' AND r.snapshot->'private_readiness'=item->'metadata'->'pins') THEN RAISE EXCEPTION 'Exact accepted private metadata effect lineage required'; END IF;
  END LOOP;
 END IF;
 RETURN NEW; END $$;
 CREATE TRIGGER psl_private_lineage BEFORE INSERT ON workflows_recoveryjob FOR EACH ROW EXECUTE FUNCTION psl_private_readiness_effect();
 CREATE TRIGGER psl_private_lineage BEFORE INSERT ON workflows_recoveryartifact FOR EACH ROW EXECUTE FUNCTION psl_private_readiness_effect();
 """,'DROP TRIGGER psl_private_lineage ON workflows_recoveryartifact; DROP TRIGGER psl_private_lineage ON workflows_recoveryjob; DROP FUNCTION psl_private_readiness_effect(); DROP TRIGGER psl_private_lineage ON workflows_recoveryplan; DROP FUNCTION psl_private_readiness_plan();')]

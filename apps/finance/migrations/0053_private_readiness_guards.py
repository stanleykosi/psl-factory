from django.db import migrations

class Migration(migrations.Migration):
 dependencies=[('finance','0052_private_readiness_packet')]
 operations=[migrations.RunSQL('CREATE TRIGGER psl_immutable BEFORE UPDATE OR DELETE ON finance_privatereadinesspacket FOR EACH ROW EXECUTE FUNCTION psl_append_only()','DROP TRIGGER psl_immutable ON finance_privatereadinesspacket'),migrations.RunSQL("""
 CREATE FUNCTION psl_private_readiness_packet() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
 IF NOT EXISTS(SELECT 1 FROM documents_validationpackage p JOIN workflows_integrationassessment a ON a.id=NEW.assessment_id JOIN workflows_integrationcontract c ON c.id=a.contract_id JOIN finance_financepublicationreadiness b ON b.contract_id=c.id WHERE p.id=NEW.package_id AND p.case_id=NEW.case_id AND c.case_id=NEW.case_id AND NEW.snapshot->>'package'=p.id::text AND NEW.snapshot->>'package_sha256'=p.sha256 AND NEW.snapshot->'evidence'->>'assessment'=a.id::text AND NEW.snapshot->'evidence'->>'contract'=c.id::text AND NEW.snapshot->'evidence'->>'binding'=b.id::text AND NEW.snapshot->'evidence'->>'binding_sha256'=b.sha256 AND NEW.snapshot->'evidence'->>'publication_job'=b.job_id::text AND p.payload->'process_ids' ? 'F01' AND p.payload->>'level'<>'operational') OR EXISTS(SELECT 1 FROM finance_financehandoff h WHERE h.package_id=NEW.package_id) OR EXISTS(SELECT 1 FROM documents_validationreview r WHERE r.package_id=NEW.package_id) THEN RAISE EXCEPTION 'Exact fresh private readiness package/source lineage required'; END IF;
 IF NEW.parent_id IS NULL THEN
  IF NEW.version<>1 OR EXISTS(SELECT 1 FROM finance_privatereadinesspacket x WHERE x.case_id=NEW.case_id AND x.reference=NEW.reference) THEN RAISE EXCEPTION 'Initial private packet version required'; END IF;
 ELSE
  IF NOT EXISTS(SELECT 1 FROM finance_privatereadinesspacket x WHERE x.id=NEW.parent_id AND x.case_id=NEW.case_id AND x.reference=NEW.reference AND x.version+1=NEW.version) THEN RAISE EXCEPTION 'Exact private packet predecessor required'; END IF;
 END IF;
 RETURN NEW; END $$;
 CREATE TRIGGER psl_lineage BEFORE INSERT ON finance_privatereadinesspacket FOR EACH ROW EXECUTE FUNCTION psl_private_readiness_packet();
 CREATE FUNCTION psl_no_private_readiness_cycle() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
 IF EXISTS(SELECT 1 FROM finance_privatereadinesspacket b WHERE b.package_id=NEW.package_id) THEN RAISE EXCEPTION 'Readiness evidence cannot recursively become a Finance source handoff'; END IF;
 RETURN NEW; END $$;
 CREATE TRIGGER psl_no_readiness_cycle BEFORE INSERT ON finance_financehandoff FOR EACH ROW EXECUTE FUNCTION psl_no_private_readiness_cycle();
 """,'DROP TRIGGER psl_no_readiness_cycle ON finance_financehandoff; DROP FUNCTION psl_no_private_readiness_cycle(); DROP TRIGGER psl_lineage ON finance_privatereadinesspacket; DROP FUNCTION psl_private_readiness_packet();')]

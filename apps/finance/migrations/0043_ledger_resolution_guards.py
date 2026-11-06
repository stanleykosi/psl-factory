from django.db import migrations

class Migration(migrations.Migration):
 dependencies=[('finance','0042_ledgerresolution_ledgerresolutionmember_and_more')]
 operations=[migrations.RunSQL(f'CREATE TRIGGER psl_immutable BEFORE UPDATE OR DELETE ON finance_{name} FOR EACH ROW EXECUTE FUNCTION psl_append_only()',f'DROP TRIGGER psl_immutable ON finance_{name}') for name in ['ledgerresolution','ledgerresolutionmember','ledgerresolutionreview']]+[migrations.RunSQL("""
 CREATE FUNCTION psl_ledger_resolution_lineage() RETURNS trigger LANGUAGE plpgsql AS $$
 DECLARE p finance_ledgerresolution%ROWTYPE;
 BEGIN
 IF NEW.predecessor_id IS NULL THEN
 IF NEW.version<>1 THEN RAISE EXCEPTION 'First resolution version required'; END IF;
 ELSE
 SELECT * INTO p FROM finance_ledgerresolution WHERE id=NEW.predecessor_id;
 IF p.id IS NULL OR (NEW.case_id,NEW.reference,NEW.version) IS DISTINCT FROM (p.case_id,p.reference,p.version+1) THEN RAISE EXCEPTION 'Exact resolution predecessor required'; END IF;
 END IF;
 IF NEW.mode NOT IN ('duplicate_alias','reference_correction') OR NOT EXISTS(SELECT 1 FROM finance_ledgerlineage WHERE id=NEW.selected_id AND case_id=NEW.case_id) OR NEW.snapshot->>'selected' IS DISTINCT FROM NEW.selected_id::text OR NEW.snapshot->>'mode' IS DISTINCT FROM NEW.mode THEN RAISE EXCEPTION 'Typed selected resolution scope required'; END IF;
 RETURN NEW; END $$;
 CREATE TRIGGER psl_lineage BEFORE INSERT ON finance_ledgerresolution FOR EACH ROW EXECUTE FUNCTION psl_ledger_resolution_lineage();
 CREATE FUNCTION psl_ledger_resolution_member() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
 IF NOT EXISTS(SELECT 1 FROM finance_ledgercheck WHERE id=NEW.verification_id AND lineage_id=NEW.lineage_id) OR NOT EXISTS(SELECT 1 FROM finance_ledgerresolution r, jsonb_array_elements(r.snapshot->'members') m WHERE r.id=NEW.resolution_id AND m->>'lineage'=NEW.lineage_id::text AND m->'proof'->>'check'=NEW.verification_id::text AND m->>'disposition'=NEW.disposition) THEN RAISE EXCEPTION 'Exact resolution member and read evidence required'; END IF;
 RETURN NEW; END $$;
 CREATE TRIGGER psl_member BEFORE INSERT ON finance_ledgerresolutionmember FOR EACH ROW EXECUTE FUNCTION psl_ledger_resolution_member();
 ""","""
 DROP TRIGGER psl_member ON finance_ledgerresolutionmember;
 DROP FUNCTION psl_ledger_resolution_member();
 DROP TRIGGER psl_lineage ON finance_ledgerresolution;
 DROP FUNCTION psl_ledger_resolution_lineage();
 """)]

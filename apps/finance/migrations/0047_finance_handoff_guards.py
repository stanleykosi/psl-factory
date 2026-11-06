from django.db import migrations

class Migration(migrations.Migration):
 dependencies=[('finance','0046_finance_validation_handoff')]
 operations=[migrations.RunSQL(f'CREATE TRIGGER psl_immutable BEFORE UPDATE OR DELETE ON finance_{name} FOR EACH ROW EXECUTE FUNCTION psl_append_only()',f'DROP TRIGGER psl_immutable ON finance_{name}') for name in ['financehandoff','financehandoffdecision']]+[migrations.RunSQL("""
 CREATE FUNCTION psl_finance_handoff_lineage() RETURNS trigger LANGUAGE plpgsql AS $$ DECLARE p finance_financehandoff%ROWTYPE; BEGIN
 IF NOT EXISTS(SELECT 1 FROM finance_ledgeragentdraft d JOIN documents_validationpackage v ON v.id=NEW.package_id JOIN policy_configuration c ON c.id=NEW.policy_id WHERE d.id=NEW.draft_id AND d.case_id=NEW.case_id AND v.case_id=NEW.case_id AND c.case_id=NEW.case_id AND c.component='F01.validation_handoff' AND d.owner_id=NEW.actor_id AND v.payload->'process_ids' ? 'F01') OR NEW.snapshot->>'package' IS DISTINCT FROM NEW.package_id::text OR NEW.snapshot->>'policy' IS DISTINCT FROM NEW.policy_id::text OR NEW.snapshot->>'recipient' IS DISTINCT FROM NEW.recipient_id::text OR NEW.snapshot->>'acceptor' IS DISTINCT FROM NEW.acceptor_id::text OR NEW.snapshot->'finance'->>'draft' IS DISTINCT FROM NEW.draft_id::text OR NEW.recipient_id IN (NEW.actor_id,NEW.acceptor_id) OR NEW.acceptor_id=NEW.actor_id THEN RAISE EXCEPTION 'Exact independent Finance/package handoff binding required'; END IF;
 IF EXISTS(SELECT 1 FROM finance_financehandoff WHERE package_id=NEW.package_id AND reference<>NEW.reference) THEN RAISE EXCEPTION 'Package has another native handoff reference'; END IF;
 IF NEW.parent_id IS NULL THEN IF NEW.version<>1 THEN RAISE EXCEPTION 'First handoff version required'; END IF;
 ELSE SELECT * INTO p FROM finance_financehandoff WHERE id=NEW.parent_id;
 IF p.id IS NULL OR (NEW.case_id,NEW.reference,NEW.version) IS DISTINCT FROM (p.case_id,p.reference,p.version+1) THEN RAISE EXCEPTION 'Exact immutable handoff predecessor required'; END IF; END IF;
 RETURN NEW; END $$;
 CREATE TRIGGER psl_lineage BEFORE INSERT ON finance_financehandoff FOR EACH ROW EXECUTE FUNCTION psl_finance_handoff_lineage();
 CREATE FUNCTION psl_finance_handoff_decision() RETURNS trigger LANGUAGE plpgsql AS $$ DECLARE h finance_financehandoff%ROWTYPE; BEGIN
 SELECT * INTO h FROM finance_financehandoff WHERE id=NEW.handoff_id;
 IF h.id IS NULL OR NEW.snapshot->>'handoff' IS DISTINCT FROM NEW.handoff_id::text OR NEW.snapshot->>'sha256' IS DISTINCT FROM h.sha256 OR NEW.actor_id IS DISTINCT FROM (CASE WHEN NEW.phase='accept' THEN h.acceptor_id ELSE h.recipient_id END) THEN RAISE EXCEPTION 'Exact handoff decision principal/lineage required'; END IF;
 RETURN NEW; END $$;
 CREATE TRIGGER psl_lineage BEFORE INSERT ON finance_financehandoffdecision FOR EACH ROW EXECUTE FUNCTION psl_finance_handoff_decision();
 ""","""
 DROP TRIGGER psl_lineage ON finance_financehandoffdecision; DROP FUNCTION psl_finance_handoff_decision();
 DROP TRIGGER psl_lineage ON finance_financehandoff; DROP FUNCTION psl_finance_handoff_lineage();
 """)]

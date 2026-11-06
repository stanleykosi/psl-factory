from django.db import migrations
class Migration(migrations.Migration):
 dependencies=[('finance','0044_ledgeragentdraft_ledgeragentdraftreview_and_more')]
 operations=[migrations.RunSQL(f'CREATE TRIGGER psl_immutable BEFORE UPDATE OR DELETE ON finance_{name} FOR EACH ROW EXECUTE FUNCTION psl_append_only()',f'DROP TRIGGER psl_immutable ON finance_{name}') for name in ['ledgerprojection','ledgeragentdraft','ledgeragentdraftreview']]+[migrations.RunSQL("""
 CREATE FUNCTION psl_ledger_projection_binding() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
 IF NOT EXISTS(SELECT 1 FROM agents_evidenceprojection p JOIN core_evidence e ON e.id=p.evidence_id JOIN finance_ledgerlineage w ON w.id=NEW.lineage_id JOIN policy_configuration c ON c.id=NEW.policy_id WHERE p.id=NEW.projection_id AND p.case_id=NEW.case_id AND w.case_id=NEW.case_id AND e.case_id=NEW.case_id AND e.kind='agent_private_ledger' AND p.process_id='F01' AND c.case_id=NEW.case_id AND c.component='F01.agent_projection') OR NEW.snapshot->>'lineage' IS DISTINCT FROM NEW.lineage_id::text OR NEW.snapshot->>'policy' IS DISTINCT FROM NEW.policy_id::text THEN RAISE EXCEPTION 'Exact Finance projection binding required'; END IF;
 RETURN NEW; END $$;
 CREATE TRIGGER psl_binding BEFORE INSERT ON finance_ledgerprojection FOR EACH ROW EXECUTE FUNCTION psl_ledger_projection_binding();
 CREATE FUNCTION psl_ledger_draft_lineage() RETURNS trigger LANGUAGE plpgsql AS $$ DECLARE p finance_ledgeragentdraft%ROWTYPE; BEGIN
 IF NOT EXISTS(SELECT 1 FROM finance_ledgerprojection s JOIN agents_evidenceextraction j ON j.projection_id=s.projection_id JOIN agents_evidenceextractionreceipt r ON r.job_id=j.id JOIN agents_evidenceextractionreview rr ON rr.receipt_id=r.id WHERE s.id=NEW.source_id AND s.case_id=NEW.case_id AND rr.id=NEW.result_review_id) OR NEW.snapshot->>'source' IS DISTINCT FROM NEW.source_id::text OR NEW.snapshot->>'result_review' IS DISTINCT FROM NEW.result_review_id::text THEN RAISE EXCEPTION 'Exact Finance source/result review required'; END IF;
 IF NEW.parent_id IS NULL THEN IF NEW.version<>1 THEN RAISE EXCEPTION 'First draft version required'; END IF;
 ELSE
 SELECT * INTO p FROM finance_ledgeragentdraft WHERE id=NEW.parent_id;
 IF p.id IS NULL OR (NEW.case_id,NEW.reference,NEW.version,NEW.source_id,NEW.result_review_id,NEW.owner_id,NEW.snapshot) IS DISTINCT FROM (p.case_id,p.reference,p.version+1,p.source_id,p.result_review_id,p.owner_id,p.snapshot) THEN RAISE EXCEPTION 'Exact immutable draft predecessor required'; END IF;
 END IF; RETURN NEW; END $$;
 CREATE TRIGGER psl_lineage BEFORE INSERT ON finance_ledgeragentdraft FOR EACH ROW EXECUTE FUNCTION psl_ledger_draft_lineage();
 ""","""
 DROP TRIGGER psl_lineage ON finance_ledgeragentdraft; DROP FUNCTION psl_ledger_draft_lineage();
 DROP TRIGGER psl_binding ON finance_ledgerprojection; DROP FUNCTION psl_ledger_projection_binding();
 """)]

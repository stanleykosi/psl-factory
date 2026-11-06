from django.db import migrations

class Migration(migrations.Migration):
 dependencies=[('finance','0048_accepted_finance_document')]
 operations=[migrations.RunSQL('CREATE TRIGGER psl_immutable BEFORE UPDATE OR DELETE ON finance_acceptedfinancedocument FOR EACH ROW EXECUTE FUNCTION psl_append_only()','DROP TRIGGER psl_immutable ON finance_acceptedfinancedocument'),migrations.RunSQL("""
 CREATE FUNCTION psl_accepted_finance_document() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
 IF NOT EXISTS(SELECT 1 FROM documents_version v JOIN documents_document d ON d.id=v.document_id JOIN documents_template t ON t.id=v.template_id JOIN finance_financehandoff h ON h.id=NEW.handoff_id JOIN policy_configuration p ON p.id=NEW.policy_id WHERE v.id=NEW.version_id AND d.case_id=h.case_id AND t.case_id=h.case_id AND p.case_id=h.case_id AND p.component='F01.accepted_publication' AND t.definition->>'document_type'='accepted_finance_metadata' AND v.created_by_id=h.actor_id AND d.owner_id=h.actor_id AND NEW.snapshot->>'handoff'=h.id::text AND NEW.snapshot->>'handoff_sha256'=h.sha256 AND NEW.snapshot->>'policy'=p.id::text AND NEW.snapshot->>'template'=t.id::text AND NEW.snapshot->>'audience'=v.audience) THEN RAISE EXCEPTION 'Exact accepted Finance metadata lineage required'; END IF;
 RETURN NEW; END $$;
 CREATE TRIGGER psl_lineage BEFORE INSERT ON finance_acceptedfinancedocument FOR EACH ROW EXECUTE FUNCTION psl_accepted_finance_document();
 """,'DROP TRIGGER psl_lineage ON finance_acceptedfinancedocument; DROP FUNCTION psl_accepted_finance_document();')]

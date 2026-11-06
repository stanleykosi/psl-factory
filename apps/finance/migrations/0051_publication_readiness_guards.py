from django.db import migrations

class Migration(migrations.Migration):
 dependencies=[('finance','0050_publication_readiness')]
 operations=[migrations.RunSQL('CREATE TRIGGER psl_immutable BEFORE UPDATE OR DELETE ON finance_financepublicationreadiness FOR EACH ROW EXECUTE FUNCTION psl_append_only()','DROP TRIGGER psl_immutable ON finance_financepublicationreadiness'),migrations.RunSQL("""
 CREATE FUNCTION psl_finance_publication_readiness() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
 IF NOT EXISTS(SELECT 1 FROM workflows_integrationcontract c JOIN documents_publicationjob j ON j.id=NEW.job_id JOIN documents_publication p ON p.id=j.publication_id JOIN documents_version v ON v.id=p.version_id JOIN documents_document d ON d.id=v.document_id JOIN finance_acceptedfinancedocument b ON b.version_id=v.id WHERE c.id=NEW.contract_id AND c.case_id=d.case_id AND c.actor_id=NEW.actor_id AND c.payload->>'kind'='adapter' AND c.payload->>'family'='publication' AND c.payload->>'implementation'='internal_postgres_session_v1' AND NEW.snapshot->>'job'=j.id::text AND NEW.snapshot->>'publication'=p.id::text AND NEW.snapshot->>'version'=v.id::text AND NEW.snapshot->>'native_binding'=b.id::text AND NEW.snapshot->>'native_binding_sha256'=b.sha256 AND NEW.snapshot->>'payload_sha256'=v.payload_sha256 AND NEW.snapshot->>'case'=d.case_id::text) THEN RAISE EXCEPTION 'Exact native Finance publication readiness binding required'; END IF;
 RETURN NEW; END $$;
 CREATE TRIGGER psl_lineage BEFORE INSERT ON finance_financepublicationreadiness FOR EACH ROW EXECUTE FUNCTION psl_finance_publication_readiness();
 """,'DROP TRIGGER psl_lineage ON finance_financepublicationreadiness; DROP FUNCTION psl_finance_publication_readiness();')]

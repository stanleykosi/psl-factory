from django.db import migrations

def protect(apps,schema_editor):
    for table in ['pmo_issuestate','pmo_issueclosureentry']:
        schema_editor.execute(f'CREATE TRIGGER psl_immutable BEFORE UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION psl_append_only()')
    schema_editor.execute("""CREATE FUNCTION psl_issue_root() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
      IF NEW.case_id IS DISTINCT FROM OLD.case_id OR NEW.tenant IS DISTINCT FROM OLD.tenant OR NEW.reference IS DISTINCT FROM OLD.reference THEN RAISE EXCEPTION 'Immutable authoritative issue identity'; END IF;
      IF NEW.current_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM pmo_issuestate WHERE id=NEW.current_id AND issue_id=NEW.id) THEN RAISE EXCEPTION 'Issue state belongs to another issue'; END IF;
      RETURN NEW; END; $$;
      CREATE TRIGGER psl_root_identity BEFORE UPDATE ON pmo_issue FOR EACH ROW EXECUTE FUNCTION psl_issue_root();""")

def unprotect(apps,schema_editor):
    for table in ['pmo_issuestate','pmo_issueclosureentry']:schema_editor.execute(f'DROP TRIGGER psl_immutable ON {table}')
    schema_editor.execute('DROP TRIGGER psl_root_identity ON pmo_issue; DROP FUNCTION psl_issue_root();')

class Migration(migrations.Migration):
    dependencies=[('pmo','0014_issue_issuestate_issueclosureentry_issue_current_and_more')]
    operations=[migrations.RunPython(protect,unprotect)]

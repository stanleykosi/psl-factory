from django.db import migrations

TABLES = ['core_evidence', 'core_audit', 'pmo_decision', 'documents_review', 'agents_agentrun', 'policy_configuration', 'policy_policystate', 'policy_registeredreference']

def protect(apps, schema_editor):
    schema_editor.execute("CREATE FUNCTION psl_append_only() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'PSL immutable history'; END; $$")
    for table in TABLES:
        schema_editor.execute(f'CREATE TRIGGER psl_immutable BEFORE UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION psl_append_only()')

def unprotect(apps, schema_editor):
    for table in TABLES:
        schema_editor.execute(f'DROP TRIGGER psl_immutable ON {table}')
    schema_editor.execute('DROP FUNCTION psl_append_only()')

class Migration(migrations.Migration):
    dependencies = [('core', '0001_initial'), ('pmo', '0001_initial'), ('documents', '0001_initial'), ('agents', '0001_initial'), ('policy', '0001_initial')]
    operations = [migrations.RunPython(protect, unprotect)]

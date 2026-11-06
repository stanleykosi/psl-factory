from django.db import migrations

TABLES=['documents_template','documents_version','documents_controlledreview','documents_publication','documents_publicationreceipt','workflows_taskevent']

def protect(apps,schema_editor):
    for table in TABLES:
        schema_editor.execute(f'CREATE TRIGGER psl_immutable BEFORE UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION psl_append_only()')
    schema_editor.execute("""CREATE FUNCTION psl_publication_job_identity() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
    IF NEW.publication_id IS DISTINCT FROM OLD.publication_id THEN RAISE EXCEPTION 'PSL publication identity is immutable'; END IF;
    RETURN NEW; END; $$;
    CREATE TRIGGER psl_job_identity BEFORE UPDATE ON documents_publicationjob FOR EACH ROW EXECUTE FUNCTION psl_publication_job_identity();
    CREATE FUNCTION psl_review_task_identity() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
    IF NEW.case_id IS DISTINCT FROM OLD.case_id OR NEW.version_id IS DISTINCT FROM OLD.version_id OR NEW.required_role IS DISTINCT FROM OLD.required_role OR NEW.created_by_id IS DISTINCT FROM OLD.created_by_id THEN RAISE EXCEPTION 'PSL human wait identity is immutable'; END IF;
    RETURN NEW; END; $$;
    CREATE TRIGGER psl_task_identity BEFORE UPDATE ON workflows_humantask FOR EACH ROW EXECUTE FUNCTION psl_review_task_identity();""")

def unprotect(apps,schema_editor):
    for table in TABLES:
        schema_editor.execute(f'DROP TRIGGER psl_immutable ON {table}')
    schema_editor.execute('DROP TRIGGER psl_job_identity ON documents_publicationjob; DROP FUNCTION psl_publication_job_identity(); DROP TRIGGER psl_task_identity ON workflows_humantask; DROP FUNCTION psl_review_task_identity();')

class Migration(migrations.Migration):
    dependencies=[('documents','0002_controlledreview_document_publication_publicationjob_and_more'),('workflows','0003_humantask_taskevent'),('core','0002_append_only_history')]
    operations=[migrations.RunPython(protect,unprotect)]

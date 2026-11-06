from django.db import migrations
TABLES=['pmo_escalationprofile','pmo_escalationrequest','pmo_escalationdecision','pmo_escalationdocumentbinding','pmo_escalationsignal']
def protect(apps,schema_editor):
    for table in TABLES:schema_editor.execute(f'CREATE TRIGGER psl_immutable BEFORE UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION psl_append_only()')
def unprotect(apps,schema_editor):
    for table in TABLES:schema_editor.execute(f'DROP TRIGGER psl_immutable ON {table}')
class Migration(migrations.Migration):
    dependencies=[('pmo','0016_escalationscancursor_escalationdecision_and_more')]
    operations=[migrations.RunPython(protect,unprotect)]

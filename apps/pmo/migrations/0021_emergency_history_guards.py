from django.db import migrations

TABLES=['pmo_emergencyprofile','pmo_emergencydecision','pmo_emergencyauthorization','pmo_emergencyoutcome',
    'pmo_emergencyreview','pmo_emergencyretrospectivedecision','pmo_emergencyretrospectiverecord','pmo_emergencydocumentbinding']


def protect(apps,schema_editor):
    for table in TABLES:
        schema_editor.execute(f'CREATE TRIGGER psl_immutable BEFORE UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION psl_append_only()')


def unprotect(apps,schema_editor):
    for table in TABLES:schema_editor.execute(f'DROP TRIGGER psl_immutable ON {table}')


class Migration(migrations.Migration):
    dependencies=[('pmo','0020_emergencyauthorization_emergencyoutcome_and_more')]
    operations=[migrations.RunPython(protect,unprotect)]

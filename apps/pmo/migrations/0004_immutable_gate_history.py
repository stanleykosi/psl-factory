from django.db import migrations

TABLES=['pmo_deliverycandidate','pmo_gaterecord','pmo_gateverification','pmo_gatedocumentbinding']
def protect(apps,schema_editor):
    for table in TABLES:
        schema_editor.execute(f'CREATE TRIGGER psl_immutable BEFORE UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION psl_append_only()')
def unprotect(apps,schema_editor):
    for table in TABLES:
        schema_editor.execute(f'DROP TRIGGER psl_immutable ON {table}')
class Migration(migrations.Migration):
    dependencies=[('pmo','0003_deliverycandidate_gatedocumentbinding_gaterecord_and_more'),('documents','0003_immutable_controlled_documents')]
    operations=[migrations.RunPython(protect,unprotect)]

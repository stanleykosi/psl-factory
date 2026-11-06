from django.db import migrations


class Migration(migrations.Migration):
    dependencies=[('pmo','0028_deliverydossier_deliverydocumentbinding_and_more')]
    operations=[migrations.RunSQL(
        f'CREATE TRIGGER psl_immutable BEFORE UPDATE OR DELETE ON pmo_{table} FOR EACH ROW EXECUTE FUNCTION psl_append_only()',
        f'DROP TRIGGER psl_immutable ON pmo_{table}') for table in
        ['deliverydossier','deliverysource','deliverysourceverification','deliveryrecord','deliverydocumentbinding']]

from django.db import migrations

class Migration(migrations.Migration):
    dependencies=[('documents','0005_validationexample_validationpackage_and_more')]
    operations=[migrations.RunSQL(f'CREATE TRIGGER psl_immutable BEFORE UPDATE OR DELETE ON documents_{name} FOR EACH ROW EXECUTE FUNCTION psl_append_only()',f'DROP TRIGGER psl_immutable ON documents_{name}') for name in ['discoverysource','validationexample','validationpackage','validationreview','validationreplay','validationfollowup']]

from django.db import migrations


class Migration(migrations.Migration):
    dependencies=[('pmo','0032_rfpcase_rfpintake_rfpcontribution_and_more')]
    operations=[migrations.RunSQL(f'CREATE TRIGGER psl_immutable BEFORE UPDATE OR DELETE ON pmo_{name} FOR EACH ROW EXECUTE FUNCTION psl_append_only()',f'DROP TRIGGER psl_immutable ON pmo_{name}') for name in ['rfpintake', 'rfpassignment', 'rfpcontribution', 'rfpresponse', 'rfpreview', 'rfpdocumentbinding', 'rfpsubmission', 'rfpoutcome', 'rfpdisposition']]

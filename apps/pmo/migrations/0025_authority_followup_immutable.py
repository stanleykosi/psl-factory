from django.db import migrations

TABLES=['authorityrecoveryrequest','authorityrecoverydecision','authorityrecoveryrecord','emergencyfollowup','emergencyfollowupcompletion']


class Migration(migrations.Migration):
    dependencies=[('pmo','0024_authorityrecoveryrequest_authorityrecoveryrecord_and_more')]
    operations=[migrations.RunSQL(
        f'CREATE TRIGGER psl_immutable BEFORE UPDATE OR DELETE ON pmo_{table} FOR EACH ROW EXECUTE FUNCTION psl_append_only()',
        f'DROP TRIGGER psl_immutable ON pmo_{table}') for table in TABLES]

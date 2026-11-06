from django.db import migrations


class Migration(migrations.Migration):
    dependencies=[('pmo','0030_deliveryscancursor_deliverysignal')]
    operations=[migrations.RunSQL('CREATE TRIGGER psl_immutable BEFORE UPDATE OR DELETE ON pmo_deliverysignal FOR EACH ROW EXECUTE FUNCTION psl_append_only()',
        'DROP TRIGGER psl_immutable ON pmo_deliverysignal')]

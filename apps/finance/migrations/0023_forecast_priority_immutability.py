from django.db import migrations

class Migration(migrations.Migration):
    dependencies=[('finance','0022_forecastpriority')]
    operations=[migrations.RunSQL('CREATE TRIGGER psl_immutable BEFORE UPDATE OR DELETE ON finance_forecastpriority FOR EACH ROW EXECUTE FUNCTION psl_append_only()','DROP TRIGGER psl_immutable ON finance_forecastpriority')]

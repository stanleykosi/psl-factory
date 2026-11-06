from django.db import migrations

class Migration(migrations.Migration):
    dependencies=[('finance','0020_forecastmatchreversal_and_more')]
    operations=[migrations.RunSQL('CREATE TRIGGER psl_immutable BEFORE UPDATE OR DELETE ON finance_forecastmatchreversal FOR EACH ROW EXECUTE FUNCTION psl_append_only()','DROP TRIGGER psl_immutable ON finance_forecastmatchreversal')]

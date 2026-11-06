from django.db import migrations

class Migration(migrations.Migration):
    dependencies = [('finance','0002_financialimport_importvalidation_invoicepreparation_and_more'),('core','0002_append_only_history')]
    operations = [migrations.RunSQL(
        'CREATE TRIGGER psl_immutable BEFORE UPDATE OR DELETE ON finance_financialimport FOR EACH ROW EXECUTE FUNCTION psl_append_only(); CREATE TRIGGER psl_immutable BEFORE UPDATE OR DELETE ON finance_importvalidation FOR EACH ROW EXECUTE FUNCTION psl_append_only();',
        'DROP TRIGGER psl_immutable ON finance_financialimport; DROP TRIGGER psl_immutable ON finance_importvalidation;')]

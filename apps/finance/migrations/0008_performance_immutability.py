from django.db import migrations


class Migration(migrations.Migration):
    dependencies=[('finance','0007_financebudget_financeperformance_and_more')]
    operations=[migrations.RunSQL(
        f'CREATE TRIGGER psl_immutable BEFORE UPDATE OR DELETE ON finance_{name} FOR EACH ROW EXECUTE FUNCTION psl_append_only()',
        f'DROP TRIGGER psl_immutable ON finance_{name}') for name in
        ['financebudget','financeperiod','financerestatement','financeperformance','financeperformancedecision','financeperformancebinding']]

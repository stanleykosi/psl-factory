from django.db import migrations
class Migration(migrations.Migration):
 dependencies=[('pmo','0036_costingoracle_costingrule_costingreview_and_more')]
 operations=[migrations.RunSQL(f'CREATE TRIGGER psl_immutable BEFORE UPDATE OR DELETE ON pmo_{name} FOR EACH ROW EXECUTE FUNCTION psl_append_only()',f'DROP TRIGGER psl_immutable ON pmo_{name}') for name in ['costingrule','costingoracle','costingreview','costingrun','costingbinding','costingaf13binding']]

from django.db import migrations
class Migration(migrations.Migration):
 dependencies=[('baas','0006_supportevent_supportintake_supportlink_supportmerge_and_more')]
 operations=[migrations.RunSQL(f'CREATE TRIGGER psl_immutable BEFORE UPDATE OR DELETE ON baas_{name} FOR EACH ROW EXECUTE FUNCTION psl_append_only()',f'DROP TRIGGER psl_immutable ON baas_{name}') for name in ['supportintake','supportlink','supportevent','supportresult','supportreport','supportreview','supportmerge']]

from django.db import migrations
class Migration(migrations.Migration):
 dependencies=[('baas','0008_supportagentdraft_supportagentdraftreview_and_more')]
 operations=[migrations.RunSQL(f'CREATE TRIGGER psl_immutable BEFORE UPDATE OR DELETE ON baas_{name} FOR EACH ROW EXECUTE FUNCTION psl_append_only()',f'DROP TRIGGER psl_immutable ON baas_{name}') for name in ['supportprojection','supportagentdraft','supportagentdraftreview']]

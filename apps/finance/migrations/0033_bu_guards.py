from django.db import migrations
class Migration(migrations.Migration):
 dependencies=[('finance','0032_buwork_bureview_bureport_bueventclaim_bureceipt_and_more')]
 operations=[migrations.RunSQL(f'CREATE TRIGGER psl_immutable BEFORE UPDATE OR DELETE ON finance_{name} FOR EACH ROW EXECUTE FUNCTION psl_append_only()',f'DROP TRIGGER psl_immutable ON finance_{name}') for name in ['buwork','bureview','bureport','bureceipt','bueventclaim']]

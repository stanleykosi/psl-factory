from django.db import migrations
class Migration(migrations.Migration):
 dependencies=[('documents','0007_migrationplan_migrationobservation_and_more')]
 operations=[migrations.RunSQL(f'CREATE TRIGGER psl_immutable BEFORE UPDATE OR DELETE ON documents_{name} FOR EACH ROW EXECUTE FUNCTION psl_append_only()',f'DROP TRIGGER psl_immutable ON documents_{name}') for name in ['migrationplan','migrationproof','migrationobservation','migrationassessment','migrationreadinessreview','migrationaf13binding']]

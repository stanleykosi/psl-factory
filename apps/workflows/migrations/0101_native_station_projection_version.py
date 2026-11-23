from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("workflows", "0100_native_station_provenance")]
    operations = [
        migrations.AddField(
            model_name="nativestation", name="projection_version", field=models.PositiveSmallIntegerField(default=1),
        ),
        migrations.AddConstraint(
            model_name="nativestation",
            constraint=models.CheckConstraint(
                condition=models.Q(projection_version=1) | models.Q(process="F02", projection_version=2),
                name="native_station_projection_version",
            ),
        ),
        migrations.RunSQL("""
            CREATE FUNCTION psl_native_station_pinned_projection() RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN
              IF OLD.work_id IS NOT NULL AND NEW.projection_version <> OLD.projection_version THEN
                RAISE EXCEPTION 'The enrolled source projection version is immutable';
              END IF;
              RETURN NEW;
            END $$;
            CREATE TRIGGER station_pinned_projection BEFORE UPDATE OF projection_version ON workflows_nativestation
              FOR EACH ROW EXECUTE FUNCTION psl_native_station_pinned_projection();
        """, """
            DROP TRIGGER station_pinned_projection ON workflows_nativestation;
            DROP FUNCTION psl_native_station_pinned_projection();
        """),
    ]

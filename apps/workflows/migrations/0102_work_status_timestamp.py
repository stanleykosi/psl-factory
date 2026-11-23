from django.db import migrations, models


TRACK_STATUS = """
CREATE FUNCTION psl_factory_status_timestamp() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        NEW.status_changed_at := clock_timestamp();
    ELSIF OLD.status IS DISTINCT FROM NEW.status THEN
        NEW.status_changed_at := clock_timestamp();
    ELSE
        NEW.status_changed_at := OLD.status_changed_at;
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER psl_factory_status_timestamp
BEFORE INSERT OR UPDATE ON workflows_factorywork
FOR EACH ROW EXECUTE FUNCTION psl_factory_status_timestamp();
"""


class Migration(migrations.Migration):
    dependencies = [('workflows', '0101_native_station_projection_version')]

    operations = [
        migrations.AddField(model_name='factorywork', name='status_changed_at',
                            field=models.DateTimeField(null=True, editable=False)),
        migrations.RunSQL(TRACK_STATUS, reverse_sql='''
            DROP TRIGGER psl_factory_status_timestamp ON workflows_factorywork;
            DROP FUNCTION psl_factory_status_timestamp();
        '''),
    ]

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('identity', '0010_staff_reactivation'), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]

    operations = [
        migrations.CreateModel(
            name='WorkAccessRequest',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('work_reference', models.PositiveBigIntegerField(db_index=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('requester', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
            ],
            options={'constraints': [models.UniqueConstraint(fields=('requester', 'work_reference'), name='identity_work_access_reference')]},
        ),
        migrations.RunSQL(
            'CREATE TRIGGER work_access_requests_append_only BEFORE UPDATE OR DELETE ON identity_workaccessrequest '
            'FOR EACH ROW EXECUTE FUNCTION psl_append_only()',
            'DROP TRIGGER work_access_requests_append_only ON identity_workaccessrequest',
        ),
    ]

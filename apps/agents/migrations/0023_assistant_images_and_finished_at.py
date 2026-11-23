from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('agents', '0022_specialistcoordination_attempts')]

    operations = [
        migrations.AddField('assistantturn', 'image_upload_ids', models.JSONField(blank=True, default=list)),
        migrations.AddField('assistantturn', 'finished_at', models.DateTimeField(null=True)),
    ]

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('agents', '0009_file_draft_review')]

    operations = [migrations.AddField(
        model_name='assistantturn', name='selected_sources',
        field=models.JSONField(default=list, blank=True),
    )]

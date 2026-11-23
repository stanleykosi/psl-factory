from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('agents', '0013_upload_current_claim_guard')]
    operations = [migrations.AddField('assistantconversation', 'scope', models.CharField(
        max_length=12, choices=[('project', 'Project'), ('department', 'Department')], default='project'))]

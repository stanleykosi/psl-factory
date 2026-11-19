from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('pmo', '0072_client_uat_literal_check_v2')]

    operations = [
        migrations.AddField(
            model_name='archivecopyjob',
            name='lease_operation',
            field=models.CharField(choices=[('copy', 'Copy'), ('lookup', 'Lookup')], max_length=6, null=True),
        ),
    ]

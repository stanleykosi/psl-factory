from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [('pmo', '0042_go_live_reaffirmation')]
    operations = [
        migrations.AddField(model_name='changeassessment', name='impact_details', field=models.JSONField(default=dict)),
        migrations.AddField(model_name='changeexecutionevent', name='impact_details', field=models.JSONField(default=dict)),
    ]

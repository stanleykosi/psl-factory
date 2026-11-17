from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('pmo', '0054_rfp_followup_delivery')]
    operations = [migrations.CreateModel(name='RFPFollowupCursor', fields=[
        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
        ('name', models.CharField(max_length=40, unique=True)),
        ('last_dispatch_id', models.BigIntegerField(default=0)),
    ])]

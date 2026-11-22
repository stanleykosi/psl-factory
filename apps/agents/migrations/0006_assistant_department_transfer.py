import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('agents', '0005_department_assistant')]
    operations = [
        migrations.AddField(
            model_name='assistantturn',
            name='transferred_to',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT,
                                    related_name='+', to='agents.assistantconversation'),
        ),
    ]

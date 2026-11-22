import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('agents', '0008_focused_chat_alerts')]

    operations = [
        migrations.CreateModel(
            name='FileDraftReview',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('draft_sha256', models.CharField(max_length=64)),
                ('summary', models.TextField()),
                ('gaps', models.JSONField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('evidence', models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, to='core.evidence')),
                ('job', models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name='file_review', to='agents.agentjob')),
            ],
        ),
        migrations.RunSQL(
            'CREATE TRIGGER psl_immutable BEFORE UPDATE OR DELETE ON agents_filedraftreview '
            'FOR EACH ROW EXECUTE FUNCTION psl_append_only()',
            'DROP TRIGGER psl_immutable ON agents_filedraftreview',
        ),
    ]

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('agents', '0010_assistant_selected_sources'),
        ('workflows', '0089_handover_reply_provenance'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='RFPAnswerSuggestion',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('key', models.CharField(max_length=100)),
                ('row', models.JSONField()),
                ('context', models.JSONField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('source_head', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='core.evidence')),
                ('turn', models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name='rfp_answer', to='agents.assistantturn')),
                ('work', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='workflows.factorywork')),
            ],
        ),
        migrations.CreateModel(
            name='RFPAnswerReview',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('verdict', models.CharField(max_length=12)),
                ('row', models.JSONField()),
                ('note', models.TextField(blank=True, max_length=2000)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('actor', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
                ('predecessor', models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT, to='agents.rfpanswerreview')),
                ('source_head', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='core.evidence')),
                ('suggestion', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='reviews', to='agents.rfpanswersuggestion')),
            ],
        ),
        migrations.RunSQL(
            'CREATE TRIGGER psl_immutable BEFORE UPDATE OR DELETE ON agents_rfpanswersuggestion '
            'FOR EACH ROW EXECUTE FUNCTION psl_append_only(); '
            'CREATE TRIGGER psl_immutable BEFORE UPDATE OR DELETE ON agents_rfpanswerreview '
            'FOR EACH ROW EXECUTE FUNCTION psl_append_only()',
            'DROP TRIGGER psl_immutable ON agents_rfpanswerreview; '
            'DROP TRIGGER psl_immutable ON agents_rfpanswersuggestion',
        ),
    ]

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('workflows', '0092_leadership_project_scope'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='WeeklyReportDraftVersion',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('values', models.JSONField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('author', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
                ('case', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='core.case')),
                ('return_review', models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT, to='documents.controlledreview')),
                ('source_head', models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT, to='core.evidence')),
                ('submitted_work', models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT,
                                                     related_name='weekly_submitted_drafts', to='workflows.factorywork')),
                ('work', models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT,
                                           related_name='weekly_edit_drafts', to='workflows.factorywork')),
            ],
            options={
                'indexes': [models.Index(fields=['case', 'author', 'work', '-id'], name='weekly_draft_head')],
                'constraints': [models.CheckConstraint(
                    condition=(models.Q(work__isnull=True, source_head__isnull=True, return_review__isnull=True)
                               | models.Q(work__isnull=False, source_head__isnull=False, return_review__isnull=False)),
                    name='weekly_draft_exact_basis',
                )],
            },
        ),
    ]

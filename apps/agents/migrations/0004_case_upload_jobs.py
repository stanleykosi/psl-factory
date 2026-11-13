import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('agents', '0003_boundary_guards'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]
    operations = [
        migrations.CreateModel(
            name='CaseUpload',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=160)),
                ('key', models.CharField(max_length=100, unique=True)),
                ('sha256', models.CharField(max_length=64)),
                ('size', models.PositiveIntegerField()),
                ('actor', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
                ('case', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='core.case')),
            ],
        ),
        migrations.CreateModel(
            name='AgentJob',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('role', models.CharField(max_length=3)),
                ('status', models.CharField(db_index=True, default='queued', max_length=12)),
                ('result', models.JSONField(default=dict)),
                ('started_at', models.DateTimeField(null=True)),
                ('actor', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
                ('upload', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='agents.caseupload')),
            ],
            options={'constraints': [models.UniqueConstraint(
                fields=('upload', 'actor', 'role'), name='unique_upload_agent_job',
            )]},
        ),
    ]

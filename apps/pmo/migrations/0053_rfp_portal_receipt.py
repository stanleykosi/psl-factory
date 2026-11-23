import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('pmo', '0052_rfp_award_amount'),
        ('documents', '0032_contacts_template_files'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(name='RFPPortalReceipt', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('reference', models.CharField(max_length=160)),
            ('note', models.TextField()),
            ('created_at', models.DateTimeField(auto_now_add=True)),
            ('actor', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
            ('evidence', models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, to='core.evidence')),
            ('review', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='documents.controlledreview')),
            ('submission', models.OneToOneField(on_delete=django.db.models.deletion.PROTECT,
                                               related_name='portal_receipt', to='pmo.rfpsubmission')),
        ]),
        migrations.RunSQL('CREATE TRIGGER psl_immutable BEFORE UPDATE OR DELETE ON pmo_rfpportalreceipt '
                          'FOR EACH ROW EXECUTE FUNCTION psl_append_only()',
                          'DROP TRIGGER psl_immutable ON pmo_rfpportalreceipt'),
    ]

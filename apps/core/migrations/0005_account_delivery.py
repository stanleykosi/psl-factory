import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('core', '0004_contacts_template_files'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='AccountDelivery',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('purpose', models.CharField(choices=[('alert', 'Alert'), ('recovery', 'Password recovery')], max_length=10)),
                ('channel', models.CharField(choices=[('email', 'Email'), ('whatsapp', 'WhatsApp')], max_length=10)),
                ('source', models.CharField(max_length=64)),
                ('route_pin', models.CharField(max_length=64)),
                ('relay_pin', models.CharField(blank=True, max_length=64)),
                ('state', models.CharField(choices=[('queued', 'Waiting to send'), ('uncertain', 'Checking the original send'),
                                                   ('delivered', 'Delivery verified'), ('held', 'Delivery on hold')],
                                           default='queued', max_length=10)),
                ('fingerprint', models.CharField(blank=True, max_length=64)),
                ('receipt', models.CharField(blank=True, max_length=128)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('next_check', models.DateTimeField(db_index=True)),
                ('delivered_at', models.DateTimeField(null=True)),
                ('consumed_at', models.DateTimeField(null=True)),
                ('actor', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'indexes': [models.Index(fields=['state', 'next_check'], name='factory_account_delivery_due')],
                'constraints': [models.UniqueConstraint(fields=('actor', 'purpose', 'channel', 'source'),
                                                        name='factory_account_delivery_once')],
            },
        ),
        migrations.CreateModel(
            name='RecoveryAttempt',
            fields=[('key', models.CharField(max_length=64, primary_key=True, serialize=False)),
                    ('until', models.DateTimeField(db_index=True))],
        ),
        migrations.CreateModel(
            name='SampleAccountInbox',
            fields=[('delivery', models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, primary_key=True,
                                                     serialize=False, to='core.accountdelivery')),
                    ('fingerprint', models.CharField(max_length=64)),
                    ('received_at', models.DateTimeField(auto_now_add=True))],
        ),
    ]

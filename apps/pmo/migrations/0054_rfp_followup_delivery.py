import django.db.models.deletion
import uuid

from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('pmo','0053_rfp_portal_receipt'),('core','0005_account_delivery'),migrations.swappable_dependency(settings.AUTH_USER_MODEL)]

    operations = [
        migrations.CreateModel(name='RFPFollowupDispatch',fields=[
            ('id',models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name='ID')),
            ('operation',models.UUIDField(default=uuid.uuid4,unique=True)),
            ('payload',models.JSONField()),('sha256',models.CharField(max_length=64)),('route',models.JSONField()),
            ('created_at',models.DateTimeField(auto_now_add=True)),
            ('review',models.OneToOneField(on_delete=django.db.models.deletion.PROTECT,related_name='+',to='core.audit')),
            ('outcome',models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,related_name='followup_deliveries',to='pmo.rfpoutcome')),
            ('configuration',models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,to='policy.configuration')),
            ('contact',models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,to='core.clientcontactrevision')),
            ('source',models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,to='core.evidence')),
            ('actor',models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,to=settings.AUTH_USER_MODEL)),
        ]),
        migrations.CreateModel(name='RFPFollowupAttempt',fields=[
            ('id',models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name='ID')),
            ('created_at',models.DateTimeField(auto_now_add=True)),
            ('dispatch',models.OneToOneField(on_delete=django.db.models.deletion.PROTECT,related_name='attempt',to='pmo.rfpfollowupdispatch')),
        ]),
        migrations.CreateModel(name='RFPFollowupMailbox',fields=[
            ('id',models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name='ID')),
            ('reference',models.CharField(max_length=160)),('payload',models.JSONField()),('sha256',models.CharField(max_length=64)),
            ('created_at',models.DateTimeField(auto_now_add=True)),
            ('dispatch',models.OneToOneField(on_delete=django.db.models.deletion.PROTECT,related_name='mailbox',to='pmo.rfpfollowupdispatch')),
        ]),
        migrations.CreateModel(name='RFPFollowupReceipt',fields=[
            ('id',models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name='ID')),
            ('reference',models.CharField(max_length=160)),('delivered',models.BooleanField()),
            ('created_at',models.DateTimeField(auto_now_add=True)),
            ('dispatch',models.OneToOneField(on_delete=django.db.models.deletion.PROTECT,related_name='receipt',to='pmo.rfpfollowupdispatch')),
            ('evidence',models.ForeignKey(null=True,on_delete=django.db.models.deletion.PROTECT,to='core.evidence')),
            ('actor',models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,to=settings.AUTH_USER_MODEL)),
        ]),
        *[migrations.RunSQL(f'CREATE TRIGGER psl_immutable BEFORE UPDATE OR DELETE ON pmo_{name} FOR EACH ROW EXECUTE FUNCTION psl_append_only()',
                           f'DROP TRIGGER psl_immutable ON pmo_{name}') for name in
          ['rfpfollowupdispatch','rfpfollowupattempt','rfpfollowupmailbox','rfpfollowupreceipt']],
    ]

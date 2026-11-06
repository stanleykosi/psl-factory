from django.db import migrations,models

class Migration(migrations.Migration):
    dependencies=[('finance','0014_settlement_immutability')]
    operations=[
        migrations.AddField(model_name='cashreceipt',name='tenant',field=models.CharField(max_length=100,null=True)),
        # Populate only the new identity namespace from the existing exact Case relation.
        # This transactional schema migration does not change financial payload/evidence/history.
        migrations.RunSQL("""
ALTER TABLE finance_cashreceipt DISABLE TRIGGER psl_immutable;
UPDATE finance_cashreceipt r SET tenant=c.tenant FROM core_case c WHERE c.id=r.case_id;
ALTER TABLE finance_cashreceipt ENABLE TRIGGER psl_immutable;
""",migrations.RunSQL.noop),
        migrations.AlterField(model_name='cashreceipt',name='tenant',field=models.CharField(max_length=100)),
        migrations.RemoveConstraint(model_name='cashreceipt',name='cash_transaction_identity'),
        migrations.AddConstraint(model_name='cashreceipt',constraint=models.UniqueConstraint(fields=['tenant','source','transaction_ref'],name='cash_tenant_transaction_identity')),
    ]

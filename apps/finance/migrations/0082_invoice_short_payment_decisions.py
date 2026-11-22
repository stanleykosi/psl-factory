import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


FORWARD = """
CREATE FUNCTION psl_short_payment_allocation_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM finance_cashallocation WHERE id = NEW.allocation_id AND issue_id = NEW.issue_id)
    THEN RAISE EXCEPTION 'Short-payment evidence must be allocated to the exact issued invoice';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER psl_short_payment_allocation BEFORE INSERT ON finance_invoiceshortpaymentdecision
FOR EACH ROW EXECUTE FUNCTION psl_short_payment_allocation_guard();
CREATE TRIGGER psl_immutable BEFORE UPDATE OR DELETE ON finance_invoiceshortpaymentdecision
FOR EACH ROW EXECUTE FUNCTION psl_append_only();
"""

REVERSE = """
DROP TRIGGER psl_immutable ON finance_invoiceshortpaymentdecision;
DROP TRIGGER psl_short_payment_allocation ON finance_invoiceshortpaymentdecision;
DROP FUNCTION psl_short_payment_allocation_guard();
"""


class Migration(migrations.Migration):
    dependencies = [
        ('finance', '0081_payroll_question_guards'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='InvoiceShortPaymentDecision',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('position', models.JSONField()),
                ('position_sha256', models.CharField(max_length=64)),
                ('treatment', models.CharField(max_length=24)),
                ('reason', models.TextField()),
                ('authority', models.JSONField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('actor', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
                ('allocation', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='finance.cashallocation')),
                ('issue', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,
                                            related_name='short_payment_decisions', to='finance.invoiceissue')),
            ],
            options={'constraints': [models.CheckConstraint(
                condition=models.Q(treatment__in=['request_proof', 'record_exception', 'reject_exception']),
                name='invoice_short_payment_treatment')]},
        ),
        migrations.RunSQL(FORWARD, REVERSE),
    ]

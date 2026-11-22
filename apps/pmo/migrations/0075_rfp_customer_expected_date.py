from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('pmo', '0074_rfp_estimate_requests')]

    operations = [
        migrations.AddField(
            model_name='rfpoutcome', name='customer_expected_on',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddConstraint(
            model_name='rfpoutcome',
            constraint=models.CheckConstraint(
                condition=models.Q(customer_expected_on__isnull=True) |
                models.Q(result='pending', evidence__isnull=False),
                name='rfp_customer_date_for_evidenced_pending',
            ),
        ),
    ]

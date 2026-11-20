from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('pmo', '0075_rfp_customer_expected_date')]

    operations = [
        migrations.AddField(
            model_name='rfpoutcome', name='remind_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddConstraint(
            model_name='rfpoutcome',
            constraint=models.CheckConstraint(
                condition=models.Q(remind_at__isnull=True) |
                models.Q(result__in=['pending', 'unknown'], followup_on__isnull=True,
                         remind_at__gte=models.F('observed_at')),
                name='rfp_exact_reminder_open_outcome',
            ),
        ),
    ]

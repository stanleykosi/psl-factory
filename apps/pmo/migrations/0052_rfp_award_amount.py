from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('pmo', '0051_rfp_outcome_followup')]

    operations = [
        migrations.AddField(model_name='rfpoutcome', name='award_amount', field=models.DecimalField(
            blank=True, decimal_places=8, max_digits=32, null=True)),
        migrations.AddField(model_name='rfpoutcome', name='award_currency', field=models.CharField(
            blank=True, max_length=3, null=True)),
        migrations.AddConstraint(model_name='rfpoutcome', constraint=models.CheckConstraint(condition=(
            models.Q(award_amount__isnull=True, award_currency__isnull=True) |
            models.Q(result='won', award_amount__isnull=False, award_amount__gte=0, award_amount__lt=10**24,
                     award_currency__isnull=False, award_currency__regex=r'^[A-Z]{3}$')),
            name='rfp_award_complete_won_pair')),
    ]

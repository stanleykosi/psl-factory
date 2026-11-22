from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [('pmo', '0050_change_client_applicability')]

    operations = [
        migrations.AddField(model_name='rfpoutcome', name='followup_on', field=models.DateField(blank=True, null=True)),
        migrations.AlterField(model_name='rfpoutcome', name='evidence', field=models.ForeignKey(
            blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, to='core.evidence')),
        migrations.AddConstraint(model_name='rfpoutcome', constraint=models.CheckConstraint(
            condition=models.Q(result='unknown') | models.Q(evidence__isnull=False), name='rfp_asserted_outcome_has_evidence')),
    ]

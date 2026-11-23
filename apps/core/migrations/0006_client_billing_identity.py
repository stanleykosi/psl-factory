from django.conf import settings
from django.db import migrations, models
from django.db.models.deletion import PROTECT


GUARD = """
CREATE FUNCTION psl_client_billing_identity_insert() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE earlier core_clientbillingidentityrevision;
BEGIN
  PERFORM 1 FROM core_case WHERE id=NEW.case_id FOR UPDATE;
  SELECT * INTO earlier FROM core_clientbillingidentityrevision
  WHERE case_id=NEW.case_id AND customer_ref=NEW.customer_ref ORDER BY number DESC LIMIT 1;
  IF NEW.previous_id IS DISTINCT FROM earlier.id OR NEW.number<>COALESCE(earlier.number,0)+1
    OR NOT EXISTS (
      SELECT 1 FROM finance_billingcoverage c JOIN core_evidence e ON e.id=NEW.evidence_id AND e.case_id=c.case_id
      WHERE c.id=NEW.coverage_id AND c.case_id=NEW.case_id AND c.customer=NEW.customer_ref
        AND (e.kind='policy_decision' OR (e.kind='billing_coverage' AND e.id=c.evidence_id))
        AND NOT EXISTS (SELECT 1 FROM finance_billingcoverage newer WHERE newer.case_id=c.case_id
          AND newer.reference=c.reference AND newer.version>c.version)
    ) OR 3<>(
      SELECT COUNT(DISTINCT action) FROM identity_grant
      WHERE case_id=NEW.case_id AND user_id=NEW.actor_id AND active
        AND action IN ('case.read','finance.read','finance.billing.register')
    ) THEN
    RAISE EXCEPTION 'Current case billing coverage, evidence, author and exact predecessor are required';
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER psl_billing_identity_insert BEFORE INSERT ON core_clientbillingidentityrevision
FOR EACH ROW EXECUTE FUNCTION psl_client_billing_identity_insert();
CREATE TRIGGER psl_immutable BEFORE UPDATE OR DELETE ON core_clientbillingidentityrevision
FOR EACH ROW EXECUTE FUNCTION psl_append_only();
"""

REVERSE = """
DROP TRIGGER psl_immutable ON core_clientbillingidentityrevision;
DROP TRIGGER psl_billing_identity_insert ON core_clientbillingidentityrevision;
DROP FUNCTION psl_client_billing_identity_insert();
"""


class Migration(migrations.Migration):
    dependencies = [
        ('core', '0005_account_delivery'),
        ('finance', '0010_billingcoverage_billingusage_billingpreparation_and_more'),
        ('identity', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='ClientBillingIdentityRevision',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('customer_ref', models.CharField(max_length=100)),
                ('number', models.PositiveIntegerField()),
                ('legal_name', models.CharField(max_length=160, null=True)),
                ('billing_address', models.CharField(max_length=600, null=True)),
                ('tax_reference', models.CharField(max_length=100, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('actor', models.ForeignKey(on_delete=PROTECT, to=settings.AUTH_USER_MODEL)),
                ('case', models.ForeignKey(on_delete=PROTECT, to='core.case')),
                ('coverage', models.ForeignKey(on_delete=PROTECT, to='finance.billingcoverage')),
                ('evidence', models.ForeignKey(on_delete=PROTECT, to='core.evidence')),
                ('previous', models.OneToOneField(null=True, on_delete=PROTECT, to='core.clientbillingidentityrevision')),
            ],
            options={
                'constraints': [models.UniqueConstraint(fields=('case', 'customer_ref', 'number'),
                                                        name='client_billing_identity_version')],
            },
        ),
        migrations.RunSQL(GUARD, REVERSE),
    ]

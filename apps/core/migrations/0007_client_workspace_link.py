from django.conf import settings
from django.db import migrations, models
from django.db.models.deletion import PROTECT


GUARD = """
CREATE FUNCTION psl_client_workspace_link_insert() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
  earlier core_clientworkspacelink;
  origin core_evidence;
  facts jsonb;
BEGIN
  PERFORM 1 FROM core_case WHERE id=NEW.case_id AND tenant=NEW.tenant AND kind='project' FOR UPDATE;
  IF NOT FOUND THEN RAISE EXCEPTION 'Same-tenant project required for client link'; END IF;
  SELECT * INTO earlier FROM core_clientworkspacelink
  WHERE case_id=NEW.case_id ORDER BY number DESC LIMIT 1;
  SELECT * INTO origin FROM core_evidence WHERE id=NEW.evidence_id AND case_id=NEW.case_id
    AND kind='client_workspace_link' AND octet_length(body)<=16384 AND sha256=encode(sha256(convert_to(body,'UTF8')),'hex');
  IF NOT FOUND THEN RAISE EXCEPTION 'Exact original client link evidence required'; END IF;
  facts := origin.body::jsonb;
  IF jsonb_typeof(facts) IS DISTINCT FROM 'object' OR facts->>'schema' IS DISTINCT FROM 'psl/client-workspace-link/v1'
    OR facts->>'case' IS DISTINCT FROM NEW.case_id::text
    OR facts->'previous' IS DISTINCT FROM COALESCE(to_jsonb(earlier.id),'null'::jsonb)
    OR NEW.previous_id IS DISTINCT FROM earlier.id OR NEW.number<>COALESCE(earlier.number,0)+1
    OR NEW.reviewer_id=origin.created_by_id
    OR 3<>(SELECT COUNT(DISTINCT g.action) FROM identity_grant g JOIN auth_user u ON u.id=g.user_id AND u.is_active
           WHERE g.case_id=NEW.case_id AND g.user_id=origin.created_by_id AND g.active
             AND g.action IN ('case.read','finance.read','finance.billing.register'))
    OR 3<>(SELECT COUNT(DISTINCT g.action) FROM identity_grant g JOIN auth_user u ON u.id=g.user_id AND u.is_active
           WHERE g.case_id=NEW.case_id AND g.user_id=NEW.reviewer_id AND g.active
             AND g.action IN ('case.read','finance.read','policy.activate'))
  THEN RAISE EXCEPTION 'Exact client link predecessor and independent current authority required'; END IF;
  IF facts->>'action'='unlink' THEN
    IF earlier.coverage_id IS NULL OR NEW.coverage_id IS NOT NULL OR NEW.group_key<>'' OR NEW.client_label<>''
      OR facts-ARRAY['schema','case','previous','action']<>'{}'::jsonb
    THEN RAISE EXCEPTION 'Exact reviewed withdrawal of the current client link required'; END IF;
  ELSIF facts->>'action'='link' THEN
    IF facts-ARRAY['schema','case','previous','action','coverage','customer','issuer','reference','name']<>'{}'::jsonb
      OR COALESCE(facts->>'issuer','') !~ '^[A-Za-z0-9][A-Za-z0-9._:/-]{0,99}$'
      OR COALESCE(facts->>'reference','') !~ '^[A-Za-z0-9][A-Za-z0-9._:/-]{0,99}$'
      OR to_jsonb(NEW.client_label) IS DISTINCT FROM facts->'name' OR btrim(NEW.client_label)=''
      OR NEW.group_key IS DISTINCT FROM encode(sha256(convert_to(
          NEW.tenant||chr(31)||(facts->>'issuer')||chr(31)||(facts->>'reference'),'UTF8')),'hex')
      OR NOT EXISTS (SELECT 1 FROM finance_billingcoverage c WHERE c.id=NEW.coverage_id AND c.case_id=NEW.case_id
        AND facts->'coverage'=to_jsonb(c.id) AND facts->'customer'=to_jsonb(c.customer)
        AND NOT EXISTS (SELECT 1 FROM finance_billingcoverage n WHERE n.case_id=c.case_id AND n.reference=c.reference
          AND n.version>c.version))
    THEN RAISE EXCEPTION 'Exact current billing coverage and declared stable client identity required'; END IF;
  ELSE
    RAISE EXCEPTION 'Typed reviewed client link required';
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER psl_client_workspace_link_insert BEFORE INSERT ON core_clientworkspacelink
FOR EACH ROW EXECUTE FUNCTION psl_client_workspace_link_insert();
CREATE TRIGGER psl_immutable BEFORE UPDATE OR DELETE ON core_clientworkspacelink
FOR EACH ROW EXECUTE FUNCTION psl_append_only();
"""

REVERSE = """
DROP TRIGGER psl_immutable ON core_clientworkspacelink;
DROP TRIGGER psl_client_workspace_link_insert ON core_clientworkspacelink;
DROP FUNCTION psl_client_workspace_link_insert();
"""


class Migration(migrations.Migration):
    dependencies = [
        ('core', '0006_client_billing_identity'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='ClientWorkspaceLink',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('number', models.PositiveIntegerField()),
                ('tenant', models.CharField(max_length=100)),
                ('group_key', models.CharField(blank=True, db_index=True, max_length=64)),
                ('client_label', models.CharField(blank=True, max_length=160)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('case', models.ForeignKey(on_delete=PROTECT, to='core.case')),
                ('coverage', models.ForeignKey(null=True, on_delete=PROTECT, to='finance.billingcoverage')),
                ('evidence', models.OneToOneField(on_delete=PROTECT, to='core.evidence')),
                ('previous', models.OneToOneField(null=True, on_delete=PROTECT, to='core.clientworkspacelink')),
                ('reviewer', models.ForeignKey(on_delete=PROTECT, to=settings.AUTH_USER_MODEL)),
            ],
            options={'constraints': [models.UniqueConstraint(fields=('case', 'number'), name='client_workspace_link_version')]},
        ),
        migrations.RunSQL(GUARD, REVERSE),
    ]

from django.db import migrations, models


GUARD = """
ALTER TABLE pmo_rfpcontribution ADD CONSTRAINT rfp_team_fact_shape CHECK (
 (received_at IS NULL AND person_days IS NULL AND source_party IS NULL AND summary IS NULL) OR
 (received_at IS NOT NULL AND received_at<=created_at AND source_party IS NOT NULL AND summary IS NOT NULL
  AND btrim(source_party)<>'' AND btrim(summary)<>''
  AND (person_days IS NULL OR (person_days>='0'::numeric AND person_days<>'NaN'::numeric)))
);
CREATE FUNCTION psl_rfp_team_fact_source() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF NEW.received_at IS NOT NULL AND NOT EXISTS (
  SELECT 1 FROM pmo_rfpintake i JOIN pmo_rfpcase r ON r.current_intake_id=i.id AND i.rfp_id=r.id
  JOIN core_evidence e ON e.id=NEW.evidence_id AND e.case_id=r.case_id
  JOIN auth_user u ON u.id=NEW.actor_id AND u.is_active
  WHERE i.id=NEW.intake_id AND e.kind=CASE NEW.team WHEN 'Engineering' THEN 'engineering_estimate'
    WHEN 'QA' THEN 'qa_estimate' WHEN 'Security' THEN 'security_estimate' WHEN 'Product' THEN 'product_input' END
   AND NOT EXISTS(SELECT 1 FROM unnest(ARRAY['case.read','rfp.read','rfp.contribute:'||NEW.team]) AS needed(action)
    WHERE NOT EXISTS(SELECT 1 FROM identity_grant g WHERE g.user_id=u.id AND g.case_id=r.case_id
     AND g.active AND g.action=needed.action))) THEN
  RAISE EXCEPTION 'Exact current team input, evidence and recorder required';
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER psl_rfp_team_facts_provenance BEFORE INSERT ON pmo_rfpcontribution
 FOR EACH ROW EXECUTE FUNCTION psl_rfp_team_fact_source();
"""

REVERSE = """
DROP TRIGGER psl_rfp_team_facts_provenance ON pmo_rfpcontribution;
DROP FUNCTION psl_rfp_team_fact_source();
ALTER TABLE pmo_rfpcontribution DROP CONSTRAINT rfp_team_fact_shape;
"""


class Migration(migrations.Migration):
    dependencies = [('pmo', '0077_rfp_loss_reason_provenance')]

    operations = [
        migrations.AddField('rfpcontribution', 'received_at', models.DateTimeField(null=True, blank=True)),
        migrations.AddField('rfpcontribution', 'source_party', models.CharField(max_length=160, blank=True, null=True)),
        migrations.AddField('rfpcontribution', 'summary', models.CharField(max_length=4000, blank=True, null=True)),
        migrations.AddField('rfpcontribution', 'person_days', models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True)),
        migrations.RunSQL(GUARD, REVERSE),
    ]

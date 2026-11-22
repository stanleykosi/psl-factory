from django.db import migrations, models
import django.db.models.deletion


GUARD = """
ALTER TABLE pmo_rfpintakesourcecontext ADD CONSTRAINT rfp_intake_source_context_shape CHECK (
 (prospect_name IS NOT NULL OR submission_method IS NOT NULL OR submission_target IS NOT NULL)
 AND (prospect_name IS NULL OR (btrim(prospect_name)<>'' AND prospect_name !~ '[[:cntrl:]]'))
 AND (submission_method IS NULL OR submission_method IN ('email','portal','by_hand','not_stated'))
 AND (submission_target IS NULL OR (submission_method IS NOT NULL
  AND submission_method IN ('email','portal','by_hand') AND btrim(submission_target)<>''
  AND submission_target !~ '[[:cntrl:]]'))
);
CREATE FUNCTION psl_rfp_intake_source_context() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF NOT EXISTS (
   SELECT 1 FROM pmo_rfpintake i JOIN pmo_rfpcase r ON r.id=i.rfp_id AND r.current_intake_id=i.id
   JOIN core_evidence e ON e.id=i.evidence_id AND e.case_id=r.case_id
   JOIN auth_user recorder ON recorder.id=i.actor_id AND recorder.is_active
   JOIN auth_user source_owner ON source_owner.id=e.created_by_id AND source_owner.is_active
   WHERE i.id=NEW.intake_id AND e.kind='rfp_intake' AND e.source<>'psl:p56-confirmed-request/v1'
    AND NOT EXISTS(SELECT 1 FROM unnest(ARRAY['case.read','rfp.read','document.read','rfp.intake','evidence.add']) AS needed(action)
     WHERE NOT EXISTS(SELECT 1 FROM identity_grant g WHERE g.user_id=recorder.id AND g.case_id=r.case_id
      AND g.active AND g.action=needed.action))
    AND NOT EXISTS(SELECT 1 FROM unnest(ARRAY['case.read','evidence.add']) AS needed(action)
     WHERE NOT EXISTS(SELECT 1 FROM identity_grant g WHERE g.user_id=source_owner.id AND g.case_id=r.case_id
      AND g.active AND g.action=needed.action))) THEN
  RAISE EXCEPTION 'Exact granted intake source and recorder required for customer instructions';
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER psl_rfp_intake_source_context_provenance BEFORE INSERT ON pmo_rfpintakesourcecontext
 FOR EACH ROW EXECUTE FUNCTION psl_rfp_intake_source_context();
CREATE TRIGGER psl_rfp_intake_source_context_immutable BEFORE UPDATE OR DELETE ON pmo_rfpintakesourcecontext
 FOR EACH ROW EXECUTE FUNCTION psl_append_only();
"""

REVERSE = """
DROP TRIGGER psl_rfp_intake_source_context_provenance ON pmo_rfpintakesourcecontext;
DROP TRIGGER psl_rfp_intake_source_context_immutable ON pmo_rfpintakesourcecontext;
DROP FUNCTION psl_rfp_intake_source_context();
ALTER TABLE pmo_rfpintakesourcecontext DROP CONSTRAINT rfp_intake_source_context_shape;
"""


class Migration(migrations.Migration):
    dependencies = [('pmo', '0078_rfp_team_input_facts')]

    operations = [
        migrations.CreateModel(name='RFPIntakeSourceContext', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('prospect_name', models.CharField(max_length=160, null=True, blank=True)),
            ('submission_method', models.CharField(max_length=20, null=True, blank=True)),
            ('submission_target', models.CharField(max_length=320, null=True, blank=True)),
            ('intake', models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name='observed_context', to='pmo.rfpintake')),
        ]),
        migrations.RunSQL(GUARD, REVERSE),
    ]

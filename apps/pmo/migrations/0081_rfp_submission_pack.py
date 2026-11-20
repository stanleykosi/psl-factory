import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


GUARDS = """
ALTER TABLE pmo_rfpsubmissionpack ADD CONSTRAINT rfp_submission_pack_shape CHECK (
  number > 0 AND (file_extension='' OR file_extension ~ '^[a-z0-9]{1,16}$')
  AND (file_count IS NULL OR file_count > 0)
  AND ((file_size_bytes IS NULL AND file_size_rule='') OR
       (file_size_bytes IS NOT NULL AND file_size_bytes > 0 AND file_size_rule IN ('less_than','at_most')))
);
CREATE FUNCTION psl_rfp_submission_pack_scope() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pmo_rfpresponse r JOIN pmo_rfpcase root ON root.id=r.rfp_id
    JOIN pmo_rfpintake i ON i.id=r.intake_id AND i.rfp_id=root.id
    JOIN core_evidence e ON e.id=i.evidence_id AND e.case_id=root.case_id AND e.kind='rfp_intake'
    WHERE r.id=NEW.response_id AND root.current_response_id=r.id AND root.current_intake_id=i.id
      AND r.actor_id=NEW.actor_id AND e.id=NEW.source_id
  ) OR NEW.number<>1+COALESCE((SELECT max(number) FROM pmo_rfpsubmissionpack WHERE response_id=NEW.response_id),0)
    OR NEW.supersedes_id IS DISTINCT FROM (
      SELECT id FROM pmo_rfpsubmissionpack WHERE response_id=NEW.response_id ORDER BY number DESC LIMIT 1
    ) THEN RAISE EXCEPTION 'Exact current response, intake proof and submission pack predecessor required'; END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER psl_rfp_submission_pack_scope BEFORE INSERT ON pmo_rfpsubmissionpack
FOR EACH ROW EXECUTE FUNCTION psl_rfp_submission_pack_scope();
CREATE TRIGGER psl_immutable BEFORE UPDATE OR DELETE ON pmo_rfpsubmissionpack
FOR EACH ROW EXECUTE FUNCTION psl_append_only();
CREATE FUNCTION psl_rfp_submission_pack_binding() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.snapshot ? 'submission_pack' AND (
      jsonb_typeof(NEW.snapshot->'submission_pack') IS DISTINCT FROM 'number'
      OR NOT EXISTS (
        SELECT 1 FROM pmo_rfpsubmissionpack p
        WHERE p.response_id=NEW.response_id AND to_jsonb(p.id)=NEW.snapshot->'submission_pack'
          AND p.number=(SELECT max(number) FROM pmo_rfpsubmissionpack WHERE response_id=NEW.response_id)
      )
  ) THEN RAISE EXCEPTION 'The document must bind the exact current submission pack'; END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER psl_rfp_submission_pack_binding BEFORE INSERT ON pmo_rfpdocumentbinding
FOR EACH ROW EXECUTE FUNCTION psl_rfp_submission_pack_binding();
"""

REVERSE = """
DROP TRIGGER psl_rfp_submission_pack_binding ON pmo_rfpdocumentbinding;
DROP FUNCTION psl_rfp_submission_pack_binding();
DROP TRIGGER psl_immutable ON pmo_rfpsubmissionpack;
DROP TRIGGER psl_rfp_submission_pack_scope ON pmo_rfpsubmissionpack;
DROP FUNCTION psl_rfp_submission_pack_scope();
ALTER TABLE pmo_rfpsubmissionpack DROP CONSTRAINT rfp_submission_pack_shape;
"""


class Migration(migrations.Migration):
    dependencies = [
        ('pmo', '0080_rfp_staged_upload'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]
    operations = [
        migrations.CreateModel(
            name='RFPSubmissionPack',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('number', models.PositiveIntegerField()),
                ('cover_note', models.CharField(blank=True, max_length=4000)),
                ('file_extension', models.CharField(blank=True, max_length=16)),
                ('file_count', models.PositiveIntegerField(blank=True, null=True)),
                ('file_size_rule', models.CharField(blank=True, max_length=12)),
                ('file_size_bytes', models.PositiveBigIntegerField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('actor', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
                ('response', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='pmo.rfpresponse')),
                ('source', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='core.evidence')),
                ('supersedes', models.OneToOneField(null=True, on_delete=django.db.models.deletion.PROTECT,
                                                  to='pmo.rfpsubmissionpack')),
            ],
            options={'constraints': [models.UniqueConstraint(fields=['response', 'number'],
                                                             name='rfp_submission_pack_revision')]},
        ),
        migrations.RunSQL(GUARDS, REVERSE),
    ]

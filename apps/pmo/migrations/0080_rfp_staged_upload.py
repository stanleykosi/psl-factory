import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


GUARD = """
ALTER TABLE pmo_rfpstagedupload ADD CONSTRAINT rfp_staged_upload_metadata_shape CHECK (
  operation ~ '^[0-9a-f]{64}$' AND payload_sha256 ~ '^[0-9a-f]{64}$'
  AND storage_identity ~ '^[0-9a-f]{64}$' AND key ~ '^rfp-intake-[0-9a-f]{64}$'
  AND sha256 ~ '^[0-9a-f]{64}$' AND size BETWEEN 1 AND 5242880
);
CREATE FUNCTION psl_rfp_staged_upload_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP='DELETE' THEN RAISE EXCEPTION 'Private bid upload history is retained'; END IF;
  IF TG_OP='INSERT' THEN
    IF NEW.upload_id IS NOT NULL OR NEW.intake_id IS NOT NULL THEN
      RAISE EXCEPTION 'Reserve the private bid object before attaching it';
    END IF;
    RETURN NEW;
  END IF;
  IF OLD.upload_id IS NOT NULL OR NEW.upload_id IS NULL OR NEW.intake_id IS NULL
     OR (to_jsonb(NEW)-ARRAY['upload_id','intake_id']) IS DISTINCT FROM
        (to_jsonb(OLD)-ARRAY['upload_id','intake_id']) THEN
    RAISE EXCEPTION 'Only the original bid reservation may be bound, once';
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM pmo_rfpintake i JOIN pmo_rfpcase r ON r.id=i.rfp_id
    JOIN agents_caseupload f ON f.id=NEW.upload_id AND f.case_id=r.case_id
    JOIN core_evidence e ON e.id=i.evidence_id AND e.case_id=r.case_id
    JOIN core_audit a ON a.case_id=r.case_id AND a.actor_id=i.actor_id
    JOIN auth_user recorder ON recorder.id=NEW.actor_id AND recorder.is_active
    WHERE i.id=NEW.intake_id AND r.current_intake_id=i.id AND i.actor_id=NEW.actor_id
      AND f.actor_id=NEW.actor_id AND f.key=NEW.key AND f.sha256=NEW.sha256 AND f.size=NEW.size
      AND e.created_by_id=NEW.actor_id AND e.kind='rfp_intake'
      AND e.source='psl:rfp-intake-private-attachment' AND a.action='rfp.intake_attachment_admitted'
      AND a.data @> jsonb_build_object('intent', NEW.id::text, 'intake', i.id, 'upload', f.id,
           'evidence', e.id, 'evidence_sha256', e.sha256, 'file_sha256', f.sha256)
      AND NOT EXISTS (SELECT 1 FROM unnest(ARRAY['case.read','rfp.read','document.read','rfp.intake','evidence.add']) AS needed(action)
        WHERE NOT EXISTS (SELECT 1 FROM identity_grant g WHERE g.case_id=r.case_id AND g.user_id=NEW.actor_id
          AND g.active AND g.action=needed.action))
      AND (r.case_id=NEW.case_id OR (NEW.case_id IS NULL AND i.number=1 AND EXISTS (
        SELECT 1 FROM identity_caseintake origin WHERE origin.case_id=r.case_id
          AND origin.actor_id=NEW.actor_id AND origin.authority_id=NEW.authority_id)))
  ) THEN RAISE EXCEPTION 'Exact private bid scope, source and object must bind together'; END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER psl_rfp_staged_upload_guard BEFORE INSERT OR UPDATE OR DELETE ON pmo_rfpstagedupload
FOR EACH ROW EXECUTE FUNCTION psl_rfp_staged_upload_guard();
"""

REVERSE = """
DROP TRIGGER psl_rfp_staged_upload_guard ON pmo_rfpstagedupload;
DROP FUNCTION psl_rfp_staged_upload_guard();
ALTER TABLE pmo_rfpstagedupload DROP CONSTRAINT rfp_staged_upload_metadata_shape;
"""


class Migration(migrations.Migration):
    dependencies = [
        ('agents', '0013_upload_current_claim_guard'),
        ('identity', '0002_product_intake'),
        ('pmo', '0079_rfp_intake_source_context'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='RFPStagedUpload',
            fields=[
                ('id', models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ('case_revision', models.PositiveBigIntegerField(null=True)),
                ('operation', models.CharField(max_length=64, unique=True)),
                ('payload_sha256', models.CharField(max_length=64)),
                ('storage_identity', models.CharField(max_length=64)),
                ('key', models.CharField(max_length=100, unique=True)),
                ('sha256', models.CharField(max_length=64)),
                ('size', models.PositiveIntegerField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('actor', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
                ('authority', models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT, to='identity.tenantauthority')),
                ('case', models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT, to='core.case')),
                ('intake', models.OneToOneField(null=True, on_delete=django.db.models.deletion.PROTECT, to='pmo.rfpintake')),
                ('upload', models.OneToOneField(null=True, on_delete=django.db.models.deletion.PROTECT, to='agents.caseupload')),
            ],
            options={
                'indexes': [models.Index(fields=['actor', '-created_at', '-id'], name='rfp_upload_actor_recent')],
                'constraints': [
                    models.CheckConstraint(condition=(models.Q(case__isnull=False, case_revision__isnull=False,
                                                               case_revision__gte=1, authority__isnull=True)
                                                      | models.Q(case__isnull=True, case_revision__isnull=True, authority__isnull=False)),
                                           name='rfp_staged_upload_one_scope'),
                    models.CheckConstraint(condition=(models.Q(intake__isnull=True, upload__isnull=True)
                                                      | models.Q(intake__isnull=False, upload__isnull=False)),
                                           name='rfp_staged_upload_one_binding'),
                ],
            },
        ),
        migrations.RunSQL(GUARD, REVERSE),
    ]

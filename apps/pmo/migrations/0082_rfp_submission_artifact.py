import django.db.models.deletion
from django.db import migrations, models


GUARDS = """
ALTER TABLE pmo_rfpsubmissionartifact ADD CONSTRAINT psl_rfp_pack_pdf_integrity CHECK (
  size BETWEEN 1 AND 1048576 AND size=octet_length(content)
  AND substring(content from 1 for 5)=decode('255044462d','hex')
  AND sha256=encode(sha256(content),'hex')
);
CREATE FUNCTION psl_rfp_submission_artifact_scope() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pmo_rfpdocumentbinding b
    JOIN documents_version v ON v.id=b.version_id
    JOIN documents_document d ON d.id=v.document_id
    JOIN pmo_rfpresponse r ON r.id=b.response_id
    JOIN pmo_rfpcase root ON root.id=r.rfp_id AND root.case_id=d.case_id
    JOIN pmo_rfpsubmissionpack pack ON pack.response_id=r.id AND to_jsonb(pack.id)=b.snapshot->'submission_pack'
    WHERE b.id=NEW.binding_id AND v.audience='client' AND v.payload_sha256=NEW.payload_sha256
      AND d.current_id=v.id AND root.current_response_id=r.id AND NOT EXISTS (
        SELECT 1 FROM pmo_rfpsubmissionpack newer WHERE newer.response_id=r.id AND newer.number>pack.number
      )
      AND NOT EXISTS (SELECT 1 FROM workflows_humantask t WHERE t.version_id=v.id)
      AND NOT EXISTS (SELECT 1 FROM documents_controlledreview review WHERE review.version_id=v.id)
      AND NOT EXISTS (SELECT 1 FROM documents_publication publication WHERE publication.version_id=v.id)
  ) THEN RAISE EXCEPTION 'PDF requires the exact current undelivered bid pack before final review'; END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER psl_rfp_submission_artifact_scope BEFORE INSERT ON pmo_rfpsubmissionartifact
FOR EACH ROW EXECUTE FUNCTION psl_rfp_submission_artifact_scope();
CREATE TRIGGER psl_immutable BEFORE UPDATE OR DELETE ON pmo_rfpsubmissionartifact
FOR EACH ROW EXECUTE FUNCTION psl_append_only();
"""

REVERSE = """
DROP TRIGGER psl_immutable ON pmo_rfpsubmissionartifact;
DROP TRIGGER psl_rfp_submission_artifact_scope ON pmo_rfpsubmissionartifact;
DROP FUNCTION psl_rfp_submission_artifact_scope();
ALTER TABLE pmo_rfpsubmissionartifact DROP CONSTRAINT psl_rfp_pack_pdf_integrity;
"""


class Migration(migrations.Migration):
    dependencies = [
        ('pmo', '0081_rfp_submission_pack'),
        ('workflows', '0003_humantask_taskevent'),
    ]
    operations = [
        migrations.CreateModel(
            name='RFPSubmissionArtifact',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('payload_sha256', models.CharField(max_length=64)),
                ('sha256', models.CharField(max_length=64)),
                ('size', models.PositiveIntegerField()),
                ('content', models.BinaryField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('binding', models.OneToOneField(on_delete=django.db.models.deletion.PROTECT,
                                                 to='pmo.rfpdocumentbinding')),
            ],
        ),
        migrations.RunSQL(GUARDS, REVERSE),
    ]

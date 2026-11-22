import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


GUARDS = """
CREATE FUNCTION psl_client_project_person_scope() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  PERFORM id FROM core_case WHERE id=NEW.case_id AND kind='project' FOR UPDATE;
  IF NOT FOUND OR btrim(NEW.name)='' OR btrim(NEW.role)='' OR NOT EXISTS (
    SELECT 1 FROM core_evidence e WHERE e.id=NEW.evidence_id AND e.case_id=NEW.case_id
      AND e.kind IN ('engagement_source','policy_decision')
  ) THEN RAISE EXCEPTION 'Project contact needs an exact same-project source and named role'; END IF;
  IF (NEW.previous_id IS NULL AND NEW.number<>1) OR (NEW.previous_id IS NOT NULL AND NOT EXISTS (
      SELECT 1 FROM core_clientprojectpersonrevision prior WHERE prior.id=NEW.previous_id AND prior.case_id=NEW.case_id
        AND prior.person_key=NEW.person_key AND prior.number+1=NEW.number
        AND NOT EXISTS (
          SELECT 1 FROM core_clientprojectpersonrevision successor WHERE successor.previous_id=prior.id
        )
  )) THEN RAISE EXCEPTION 'Project contact must extend its exact current identity'; END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER psl_client_project_person_scope BEFORE INSERT ON core_clientprojectpersonrevision
FOR EACH ROW EXECUTE FUNCTION psl_client_project_person_scope();
CREATE TRIGGER psl_immutable BEFORE UPDATE OR DELETE ON core_clientprojectpersonrevision
FOR EACH ROW EXECUTE FUNCTION psl_append_only();
"""

REVERSE = """
DROP TRIGGER psl_immutable ON core_clientprojectpersonrevision;
DROP TRIGGER psl_client_project_person_scope ON core_clientprojectpersonrevision;
DROP FUNCTION psl_client_project_person_scope();
"""


class Migration(migrations.Migration):
    dependencies = [
        ('core', '0007_client_workspace_link'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]
    operations = [
        migrations.CreateModel(
            name='ClientProjectPersonRevision',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('person_key', models.UUIDField(default=uuid.uuid4, editable=False)),
                ('number', models.PositiveIntegerField()),
                ('name', models.CharField(max_length=160)),
                ('role', models.CharField(max_length=100)),
                ('email', models.EmailField(blank=True, max_length=254)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('case', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='core.case')),
                ('previous', models.OneToOneField(null=True, on_delete=django.db.models.deletion.PROTECT, to='core.clientprojectpersonrevision')),
                ('evidence', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='core.evidence')),
                ('actor', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
            ],
            options={'constraints': [models.UniqueConstraint(fields=['case', 'person_key', 'number'], name='client_project_person_version')]},
        ),
        migrations.RunSQL(GUARDS, REVERSE),
    ]

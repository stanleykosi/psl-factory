"""Add exact workspace profile snapshots to one-use staff invitations."""

from importlib import import_module

from django.db import migrations, models
from django.db.models import PROTECT


LEGACY = import_module('apps.identity.migrations.0009_staff_profile_json_operators').SQL

SCOPE_GUARD = r"""
CREATE FUNCTION psl_staff_invitation_workspace_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE s jsonb; p jsonb; base core_case; target core_case; cfg identity_tenantauthority; effect_count int;
BEGIN
 IF jsonb_typeof(NEW.workspace_profiles) IS DISTINCT FROM 'array'
    OR jsonb_array_length(NEW.workspace_profiles)>49 THEN
  RAISE EXCEPTION 'A bounded selection of extra workspaces is required';
 END IF;
 IF NEW.workspace_profiles='[]'::jsonb THEN RETURN NEW; END IF;
 SELECT * INTO base FROM core_case WHERE id=NEW.case_id;
 SELECT * INTO cfg FROM identity_tenantauthority WHERE id=NEW.authority_id;
 IF NEW.profile_key='' OR jsonb_typeof(NEW.actions) IS DISTINCT FROM 'array'
    OR cfg.user_id IS DISTINCT FROM NEW.actor_id OR cfg.tenant IS DISTINCT FROM base.tenant
    OR cfg.value->'staff_lifecycle'->'allow_invite' IS DISTINCT FROM 'true'::jsonb
    OR NOT cfg.enabled OR cfg.expires_at<=NEW.created_at OR NEW.expires_at>cfg.expires_at
    OR EXISTS(SELECT 1 FROM identity_tenantauthority WHERE tenant=cfg.tenant AND user_id=cfg.user_id AND version>cfg.version)
    OR (SELECT count(*)<>count(DISTINCT x->>'case') FROM jsonb_array_elements(NEW.workspace_profiles) AS x) THEN
  RAISE EXCEPTION 'A named profile and current invitation authority are required';
 END IF;
 effect_count := jsonb_array_length(NEW.actions);
 FOR s IN SELECT * FROM jsonb_array_elements(NEW.workspace_profiles) LOOP
  IF jsonb_typeof(s) IS DISTINCT FROM 'object' OR NOT(s ?& ARRAY['case','profile_key','profile_label','profile_sha256','actions'])
     OR s-ARRAY['case','profile_key','profile_label','profile_sha256','actions']<>'{}'::jsonb
     OR COALESCE(s->>'case','') !~ '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$' THEN
   RAISE EXCEPTION 'Each extra workspace needs one exact profile';
  END IF;
  SELECT * INTO target FROM core_case WHERE id=(s->>'case')::uuid;
  SELECT x INTO p FROM jsonb_array_elements(cfg.value->'staff_lifecycle'->'profiles') AS x WHERE x->>'key'=s->>'profile_key';
  IF target.id IS NULL OR target.id=base.id OR target.kind<>'project' OR target.tenant<>base.tenant
     OR target.synthetic IS DISTINCT FROM base.synthetic OR target.synthetic IS DISTINCT FROM (cfg.value->>'classification'='synthetic')
     OR NOT((cfg.value->'kinds') ? target.kind) OR p IS NULL
     OR s->>'profile_label' IS DISTINCT FROM p->>'label' OR COALESCE(s->>'profile_sha256', '') !~ '^[a-f0-9]{64}$'
     OR jsonb_typeof(s->'actions') IS DISTINCT FROM 'array'
     OR NOT((p->'actions') @> (s->'actions') AND (s->'actions') @> (p->'actions'))
     OR jsonb_array_length(s->'actions')<>jsonb_array_length(p->'actions')
     OR NOT EXISTS(SELECT 1 FROM identity_grant WHERE case_id=target.id AND user_id=NEW.actor_id AND action='case.read' AND active) THEN
   RAISE EXCEPTION 'Extra workspace access must match a current delegated named profile';
  END IF;
  effect_count := effect_count + jsonb_array_length(s->'actions');
  IF effect_count>150 THEN
   RAISE EXCEPTION 'Combined invitations may grant up to 150 workspace access functions';
  END IF;
 END LOOP;
 RETURN NEW;
END $$;
CREATE TRIGGER psl_invitation_workspace_guard BEFORE INSERT ON identity_staffinvitation
 FOR EACH ROW EXECUTE FUNCTION psl_staff_invitation_workspace_guard();
"""

PRIMARY_MATCH = "AND s.user_id=NEW.user_id AND i.profile_key=NEW.profile_key AND i.profile_label=NEW.profile_label\n     AND i.profile_sha256=NEW.profile_sha256 AND i.actions=NEW.after_actions"
SCOPED_MATCH = r"""AND s.user_id=NEW.user_id AND (
      (i.case_id=c.id AND i.profile_key=NEW.profile_key AND i.profile_label=NEW.profile_label
       AND i.profile_sha256=NEW.profile_sha256 AND i.actions=NEW.after_actions)
      OR EXISTS(SELECT 1 FROM jsonb_array_elements(i.workspace_profiles) AS w
         WHERE w->>'case'=c.id::text AND w->>'profile_key'=NEW.profile_key AND w->>'profile_label'=NEW.profile_label
           AND w->>'profile_sha256'=NEW.profile_sha256 AND w->'actions'=NEW.after_actions))"""

PROFILE_GUARD = LEGACY.replace('i.id=NEW.invitation_id AND i.case_id=c.id', 'i.id=NEW.invitation_id').replace(PRIMARY_MATCH, SCOPED_MATCH)


class Migration(migrations.Migration):
    dependencies = [('identity', '0011_work_access_request')]
    operations = [
        migrations.AddField('staffinvitation', 'workspace_profiles', models.JSONField(blank=True, default=list)),
        migrations.AlterField('staffprofilechange', 'invitation', models.ForeignKey(null=True, on_delete=PROTECT, to='identity.staffinvitation')),
        migrations.AddConstraint('staffprofilechange', models.UniqueConstraint(fields=['invitation', 'case'], name='staff_invite_workspace_profile')),
        migrations.RunSQL(SCOPE_GUARD, 'DROP TRIGGER psl_invitation_workspace_guard ON identity_staffinvitation; DROP FUNCTION psl_staff_invitation_workspace_guard();'),
        migrations.RunSQL(PROFILE_GUARD, LEGACY),
    ]

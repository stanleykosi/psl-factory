from django.db import migrations

# Forward-only: preserve every existing guard predicate, extending only supported format.
SQL=r"""
CREATE OR REPLACE FUNCTION psl_technical_intake_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE a identity_tenantauthority; c core_case;
BEGIN
 IF TG_OP<>'INSERT' THEN RAISE EXCEPTION 'Technical intake history is immutable'; END IF;
 IF TG_TABLE_NAME='identity_tenantauthority' THEN
  IF NOT EXISTS(SELECT 1 FROM auth_user WHERE id=NEW.actor_id AND is_active AND is_superuser)
     OR COALESCE(NEW.value->>'format','') NOT IN ('psl.tenant-access/v1','psl.tenant-access/v2')
     OR NEW.expires_at<=NEW.created_at
     OR NEW.version<>1+COALESCE((SELECT max(version) FROM identity_tenantauthority WHERE tenant=NEW.tenant AND user_id=NEW.user_id),0) THEN
   RAISE EXCEPTION 'Versioned explicit technical bootstrap required'; END IF;
 ELSE
  SELECT * INTO a FROM identity_tenantauthority WHERE id=NEW.authority_id;
  SELECT * INTO c FROM core_case WHERE id=NEW.case_id;
  IF a.user_id IS DISTINCT FROM NEW.actor_id OR a.tenant IS DISTINCT FROM c.tenant OR NOT a.enabled
     OR a.expires_at<=NEW.created_at OR EXISTS(SELECT 1 FROM identity_tenantauthority WHERE tenant=a.tenant AND user_id=a.user_id AND version>a.version)
     OR c.synthetic IS DISTINCT FROM (a.value->>'classification'='synthetic') THEN
   RAISE EXCEPTION 'Current same-tenant technical authority required'; END IF;
  IF TG_TABLE_NAME='identity_caseintake' THEN
   IF a.value->'create_cases' IS DISTINCT FROM 'true'::jsonb OR NEW.tenant IS DISTINCT FROM c.tenant
      OR NEW.payload->>'title' IS DISTINCT FROM c.title OR NEW.payload->>'kind' IS DISTINCT FROM c.kind
      OR NEW.payload->'synthetic' IS DISTINCT FROM to_jsonb(c.synthetic) OR NOT (a.value->'kinds' ? c.kind) THEN
    RAISE EXCEPTION 'Exact delegated case intake required'; END IF;
  ELSE
   IF NOT (a.value->'allowed_actions' ? NEW.action) OR NOT EXISTS(SELECT 1 FROM identity_grant WHERE case_id=c.id AND user_id=NEW.subject_id AND action=NEW.action AND active=NEW.enabled)
      OR (a.value->'manage_access' IS DISTINCT FROM 'true'::jsonb AND NOT(NEW.subject_id=NEW.actor_id AND a.value->'initial_actions' ? NEW.action)) THEN
    RAISE EXCEPTION 'Exact delegated record access change required'; END IF;
  END IF;
 END IF;
 RETURN NEW;
END $$;
"""

class Migration(migrations.Migration):
    dependencies=[('identity','0003_intake_guard')]
    operations=[migrations.RunSQL(SQL)]

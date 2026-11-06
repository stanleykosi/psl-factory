from django.db import migrations
SQL=r"""
CREATE FUNCTION psl_identity_resolution_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE c core_case; other core_case;
BEGIN
 IF TG_OP<>'INSERT' THEN RAISE EXCEPTION 'Human identity finding history is immutable'; END IF;
 SELECT * INTO c FROM core_case WHERE id=NEW.case_id;
 SELECT * INTO other FROM core_case WHERE id=NEW.other_case_id;
 IF c.id=other.id OR c.tenant IS DISTINCT FROM other.tenant OR c.kind IS DISTINCT FROM 'project' OR other.kind IS DISTINCT FROM 'project' OR c.synthetic IS DISTINCT FROM other.synthetic
    OR NOT EXISTS(SELECT 1 FROM core_evidence WHERE id=NEW.evidence_id AND case_id=c.id)
    OR NOT EXISTS(SELECT 1 FROM core_evidence WHERE id=NEW.other_evidence_id AND case_id=other.id)
    OR NOT EXISTS(SELECT 1 FROM policy_configuration WHERE id::text=NEW.data->>'source_policy' AND case_id=c.id AND component='D11.engagement_identity_resolution')
    OR NOT EXISTS(SELECT 1 FROM policy_configuration WHERE id::text=NEW.data->>'target_policy' AND case_id=other.id AND component='D11.engagement_identity_resolution')
    OR NEW.data->'access_transferred' IS DISTINCT FROM 'false'::jsonb OR NEW.data->'business_records_transferred' IS DISTINCT FROM 'false'::jsonb OR NEW.data->'financial_authority' IS DISTINCT FROM 'false'::jsonb THEN
  RAISE EXCEPTION 'Exact human same-tenant identity evidence with no authority transfer required'; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER identity_resolution_guard BEFORE INSERT OR UPDATE OR DELETE ON pmo_projectidentitydecision FOR EACH ROW EXECUTE FUNCTION psl_identity_resolution_guard();
"""
class Migration(migrations.Migration):
    dependencies=[('pmo','0040_identity_resolution')]
    operations=[migrations.RunSQL(SQL,'DROP TRIGGER identity_resolution_guard ON pmo_projectidentitydecision; DROP FUNCTION psl_identity_resolution_guard();')]

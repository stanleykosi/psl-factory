from django.db import migrations
SQL=r"""
CREATE FUNCTION psl_engagement_history_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE c core_case; r pmo_engagementrecord;
BEGIN
 IF TG_OP<>'INSERT' THEN RAISE EXCEPTION 'Engagement identity history is immutable'; END IF;
 SELECT * INTO c FROM core_case WHERE id=NEW.case_id;
 IF c.kind IS DISTINCT FROM 'project' THEN RAISE EXCEPTION 'Project engagement required'; END IF;
 IF TG_TABLE_NAME='pmo_engagementrecord' THEN
  IF NOT EXISTS(SELECT 1 FROM core_evidence WHERE id=NEW.evidence_id AND case_id=c.id)
     OR NEW.kind NOT IN ('capture','assignment','registration','export','delivery_link') THEN RAISE EXCEPTION 'Same-case typed engagement source evidence required'; END IF;
  IF NEW.kind='capture' AND (NEW.data->>'route' NOT IN ('A','B','C') OR NEW.data->>'route' IS NULL) THEN RAISE EXCEPTION 'Explicit route required'; END IF;
  IF NEW.kind IN ('assignment','registration') AND NOT EXISTS(SELECT 1 FROM policy_configuration WHERE id::text=NEW.data->>'policy' AND case_id=c.id AND component=CASE WHEN NEW.kind='assignment' THEN 'D11.engagement_assignment' ELSE 'D11.project_identifiers' END) THEN RAISE EXCEPTION 'Exact project configuration history required'; END IF;
 ELSE
  SELECT * INTO r FROM pmo_engagementrecord WHERE id=NEW.record_id;
  IF NEW.tenant IS DISTINCT FROM c.tenant OR r.case_id IS DISTINCT FROM c.id OR r.kind IS DISTINCT FROM 'registration'
     OR r.data->>'namespace' IS DISTINCT FROM NEW.namespace OR r.data->>'value' IS DISTINCT FROM NEW.value OR r.data->>'normalized' IS DISTINCT FROM NEW.normalized THEN
   RAISE EXCEPTION 'Exact project identifier lineage required'; END IF;
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER engagement_history_guard BEFORE INSERT OR UPDATE OR DELETE ON pmo_engagementrecord FOR EACH ROW EXECUTE FUNCTION psl_engagement_history_guard();
CREATE TRIGGER engagement_history_guard BEFORE INSERT OR UPDATE OR DELETE ON pmo_projectidentifier FOR EACH ROW EXECUTE FUNCTION psl_engagement_history_guard();
"""
class Migration(migrations.Migration):
    dependencies=[('pmo','0038_engagement_intake')]
    operations=[migrations.RunSQL(SQL,'DROP TRIGGER engagement_history_guard ON pmo_projectidentifier; DROP TRIGGER engagement_history_guard ON pmo_engagementrecord; DROP FUNCTION psl_engagement_history_guard();')]

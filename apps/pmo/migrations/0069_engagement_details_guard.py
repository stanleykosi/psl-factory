from django.db import migrations

SQL=r"""
CREATE FUNCTION psl_engagement_details_current(did bigint) RETURNS boolean LANGUAGE sql STABLE AS $$
 SELECT EXISTS(SELECT 1 FROM pmo_engagementdetails d JOIN pmo_engagementrecord c ON c.id=d.capture_id
 WHERE d.id=did AND d.schema_version=1 AND c.case_id=d.case_id AND c.kind='capture'
 AND c.id=(SELECT max(id) FROM pmo_engagementrecord WHERE case_id=d.case_id AND kind='capture')
 AND psl_schedules_grants(d.case_id,d.actor_id,ARRAY['case.read','engagement.read','engagement.capture'])
 AND psl_schedules_grants(d.case_id,c.actor_id,ARRAY['case.read','engagement.read','engagement.capture'])
 AND psl_engagement_public_source(d.case_id,c.evidence_id)
 AND psl_engagement_public_source(d.case_id,d.evidence_id)
 AND psl_engagement_public_source(d.case_id,d.plan_id)
 AND EXISTS(SELECT 1 FROM core_evidence e WHERE e.id=d.plan_id AND e.kind='plan')
 AND (d.contact_id IS NULL OR EXISTS(SELECT 1 FROM core_clientcontactrevision x
  WHERE x.id=d.contact_id AND x.case_id=d.case_id AND x.purpose='project' AND x.customer=''
  AND NOT EXISTS(SELECT 1 FROM core_clientcontactrevision newer WHERE newer.case_id=x.case_id AND newer.purpose='project' AND newer.customer='' AND newer.number>x.number)
  AND psl_schedules_grants(d.case_id,x.actor_id,ARRAY['case.read','engagement.read','engagement.capture'])
  AND psl_engagement_public_source(d.case_id,x.evidence_id)
  AND EXISTS(SELECT 1 FROM core_evidence e WHERE e.id=x.evidence_id AND e.kind IN ('engagement_source','policy_decision')))));
$$;
CREATE FUNCTION psl_engagement_registration_details_current(rid bigint) RETURNS boolean LANGUAGE plpgsql STABLE AS $$
DECLARE r pmo_engagementrecord; d pmo_engagementdetails; required jsonb; has_binding boolean;
BEGIN
 SELECT * INTO r FROM pmo_engagementrecord WHERE id=rid AND kind='registration';
 IF NOT FOUND THEN RETURN false; END IF;
 SELECT v->'required_details' INTO required FROM jsonb_array_elements(psl_schedules_values((r.data->>'policy')::bigint)) v LIMIT 1;
 SELECT x.* INTO d FROM pmo_engagementdetails x JOIN pmo_engagementdetailsbinding b ON b.details_id=x.id WHERE b.registration_id=r.id;
 has_binding:=FOUND;
 IF required IS NOT NULL THEN
  IF required->'planned_start' IS NULL OR required->'client_contact' IS NULL
   OR required->'planned_start'='null'::jsonb OR required->'client_contact'='null'::jsonb
   OR NOT has_binding THEN RETURN false; END IF;
  IF required->'planned_start'='true'::jsonb AND d.planned_start IS NULL
   OR required->'client_contact'='true'::jsonb AND d.contact_id IS NULL THEN RETURN false; END IF;
 END IF;
 IF NOT has_binding THEN RETURN true; END IF;
 RETURN d.case_id=r.case_id AND d.capture_id::text=r.data->>'capture'
  AND d.reference=r.data->>'value' AND d.plan_id::text=r.data->>'plan'
  AND d.evidence_id=r.evidence_id AND psl_engagement_details_current(d.id);
EXCEPTION WHEN OTHERS THEN RETURN false;
END $$;
CREATE FUNCTION psl_engagement_details_history_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF TG_OP<>'INSERT' THEN RAISE EXCEPTION 'Project details history is immutable'; END IF;
 IF TG_TABLE_NAME='pmo_engagementdetails' THEN
  IF NOT EXISTS(SELECT 1 FROM core_case WHERE id=NEW.case_id AND kind='project')
   OR NEW.schema_version<>1 OR NEW.reference='' OR NEW.reference<>btrim(NEW.reference)
   OR NOT EXISTS(SELECT 1 FROM pmo_engagementrecord WHERE id=NEW.capture_id AND case_id=NEW.case_id AND kind='capture')
   OR NOT EXISTS(SELECT 1 FROM core_evidence WHERE id=NEW.plan_id AND case_id=NEW.case_id AND kind='plan')
   OR NOT psl_engagement_public_source(NEW.case_id,NEW.evidence_id)
   OR NEW.contact_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM core_clientcontactrevision WHERE id=NEW.contact_id AND case_id=NEW.case_id AND purpose='project' AND customer='')
   THEN RAISE EXCEPTION 'Exact project detail sources and contact required'; END IF;
 ELSE
  IF NOT psl_engagement_registration_details_current(NEW.registration_id) THEN RAISE EXCEPTION 'Exact current registration details required'; END IF;
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER psl_engagement_details_history BEFORE INSERT OR UPDATE OR DELETE ON pmo_engagementdetails
 FOR EACH ROW EXECUTE FUNCTION psl_engagement_details_history_guard();
CREATE TRIGGER psl_engagement_details_binding_history AFTER INSERT OR UPDATE OR DELETE ON pmo_engagementdetailsbinding
 FOR EACH ROW EXECUTE FUNCTION psl_engagement_details_history_guard();
CREATE FUNCTION psl_engagement_details_registration_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF NEW.kind='registration' AND NOT psl_engagement_registration_details_current(NEW.id)
 THEN RAISE EXCEPTION 'Configured project details required for formal registration'; END IF;
 RETURN NEW;
END $$;
CREATE CONSTRAINT TRIGGER psl_engagement_details_registration AFTER INSERT ON pmo_engagementrecord
 DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION psl_engagement_details_registration_guard();
CREATE FUNCTION psl_engagement_details_work_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF NEW.definition='engagement/v1' AND NEW.status='verified' AND NOT psl_engagement_registration_details_current(
  (SELECT max(id) FROM pmo_engagementrecord WHERE case_id=NEW.case_id AND kind='registration'))
 THEN RAISE EXCEPTION 'Current exact project details required before verification'; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER psl_engagement_details_work BEFORE INSERT OR UPDATE ON workflows_factorywork
 FOR EACH ROW EXECUTE FUNCTION psl_engagement_details_work_guard();
"""

REVERSE="""
DROP TRIGGER psl_engagement_details_work ON workflows_factorywork;
DROP FUNCTION psl_engagement_details_work_guard();
DROP TRIGGER psl_engagement_details_registration ON pmo_engagementrecord;
DROP FUNCTION psl_engagement_details_registration_guard();
DROP TRIGGER psl_engagement_details_binding_history ON pmo_engagementdetailsbinding;
DROP TRIGGER psl_engagement_details_history ON pmo_engagementdetails;
DROP FUNCTION psl_engagement_details_history_guard();
DROP FUNCTION psl_engagement_registration_details_current(bigint);
DROP FUNCTION psl_engagement_details_current(bigint);
"""

class Migration(migrations.Migration):
    dependencies=[('pmo','0068_engagement_details'),('workflows','0075_factory_engagement')]
    operations=[migrations.RunSQL(SQL,REVERSE)]

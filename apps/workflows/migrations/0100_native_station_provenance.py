"""Keep station identity, source joins and receipt-use history consistent in PostgreSQL."""
from django.db import migrations


FORWARD = """
CREATE FUNCTION psl_native_station_subject() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF TG_OP='DELETE' OR (TG_OP='UPDATE' AND
  (NEW.process,NEW.subject_model,NEW.subject_pk) IS DISTINCT FROM (OLD.process,OLD.subject_model,OLD.subject_pk))
 THEN RAISE EXCEPTION 'Department source identity is immutable'; END IF;
 IF TG_OP='UPDATE' AND OLD.work_id IS NOT NULL AND NEW.work_id IS DISTINCT FROM OLD.work_id
 THEN RAISE EXCEPTION 'The coordinator work identity is immutable'; END IF;
 IF NEW.work_id IS NOT NULL AND NOT EXISTS (
  SELECT 1 FROM workflows_factorywork w WHERE w.id=NEW.work_id AND w.definition='process-handoff/v1'
   AND w.request=jsonb_build_object('station',NEW.id,'process',NEW.process))
 THEN RAISE EXCEPTION 'Current exact coordinator work required'; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER station_original_subject BEFORE UPDATE OR DELETE ON workflows_nativestation
 FOR EACH ROW EXECUTE FUNCTION psl_native_station_subject();
CREATE FUNCTION psl_native_station_handoff() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF NEW.projection_sha256 !~ '^[a-f0-9]{64}$' OR NEW.packet_sha256 !~ '^[a-f0-9]{64}$'
 OR NOT EXISTS (SELECT 1 FROM workflows_nativestation s JOIN agents_specialistpacket p
   ON p.work_id=s.work_id AND p.process=s.process
   WHERE s.id=NEW.station_id AND p.id=NEW.packet_id AND p.superseded_by_id IS NULL)
 THEN RAISE EXCEPTION 'Exact department work and specialist evidence required'; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER station_handoff_origin BEFORE INSERT ON workflows_nativestationadvice
 FOR EACH ROW EXECUTE FUNCTION psl_native_station_handoff();
CREATE TRIGGER station_use_history BEFORE UPDATE OR DELETE ON workflows_nativestationuse
 FOR EACH ROW EXECUTE FUNCTION psl_append_only();
CREATE FUNCTION psl_native_station_consumed() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF NOT EXISTS (
  SELECT 1 FROM workflows_nativestation s JOIN workflows_nativestationadvice h ON h.station_id=s.id
   JOIN workflows_nativestationreceipt r ON r.handoff_id=h.id
   JOIN workflows_factoryactivity c ON c.work_id=s.work_id AND c.kind='ACT13'
   JOIN workflows_factoryattempt a ON a.activity_id=c.id AND a.phase='observed'
   WHERE s.work_id=NEW.id AND a.result->'station_receipt'=to_jsonb(r.id)
    AND (s.process IN ('P05','P19') OR EXISTS(SELECT 1 FROM workflows_nativestationuse u WHERE u.handoff_id=h.id))
 ) THEN RAISE EXCEPTION 'The receiving department has not consumed the reviewed specialist findings'; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER station_verified_consumption BEFORE INSERT OR UPDATE ON workflows_factorywork
 FOR EACH ROW WHEN (NEW.definition='process-handoff/v1' AND NEW.status='verified')
 EXECUTE FUNCTION psl_native_station_consumed();
"""


class Migration(migrations.Migration):
    dependencies = [("workflows", "0099_nativestationuse")]
    operations = [migrations.RunSQL(FORWARD, """
      DROP TRIGGER station_verified_consumption ON workflows_factorywork;
      DROP FUNCTION psl_native_station_consumed();
      DROP TRIGGER station_use_history ON workflows_nativestationuse;
      DROP TRIGGER station_handoff_origin ON workflows_nativestationadvice;
      DROP FUNCTION psl_native_station_handoff();
      DROP TRIGGER station_original_subject ON workflows_nativestation;
      DROP FUNCTION psl_native_station_subject();
    """)]

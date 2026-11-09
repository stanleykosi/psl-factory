"""Additive P22 typed UI artifact/owner-receipt defenses. No history backfill."""
from django.db import migrations

PREVIOUS_PLAN = r"""CREATE OR REPLACE FUNCTION psl_progress_plan(pid bigint) RETURNS boolean LANGUAGE sql STABLE AS $$
 SELECT EXISTS(SELECT 1 FROM pmo_deliveryrecord p JOIN pmo_deliverydossier d ON d.id=p.dossier_id
 JOIN pmo_baseline b ON b.case_id=d.case_id JOIN pmo_deliverycandidate dc ON dc.id=d.candidate_id
 WHERE p.id=pid AND p.kind='planning_decision' AND p.data->>'verdict'='approve'
 AND p.id=(SELECT max(id) FROM pmo_deliveryrecord WHERE dossier_id=d.id AND kind='planning_decision')
 AND d.baseline=jsonb_build_object('plan_id',b.plan_id,'costing_id',b.costing_id,'sow_id',b.sow_id)
 AND p.snapshot-ARRAY['baseline','requirements_id','sources']='{}'::jsonb
 AND EXISTS(SELECT 1 FROM pmo_deliverysource ui WHERE ui.id=(p.snapshot->'sources'->'ui_applicability'->>0)::bigint
 AND jsonb_typeof(ui.payload->'requires_ui')='boolean' AND jsonb_typeof(ui.payload->'client_signoff_required')='boolean'
 AND (ui.payload->'requires_ui'<>'true'::jsonb OR p.snapshot->'sources' ? 'ui_design')
 AND (ui.payload->'requires_ui'<>'true'::jsonb OR ui.payload->'client_signoff_required'<>'true'::jsonb OR p.snapshot->'sources' ? 'ui_client')
 AND (p.snapshot->'sources')-ARRAY['registration','scope_baseline','technical_design','test_strategy','uat_approach','ui_applicability']
 -CASE WHEN ui.payload->'requires_ui'='true'::jsonb THEN ARRAY['ui_design'] ELSE ARRAY[]::text[] END
 -CASE WHEN ui.payload->'requires_ui'='true'::jsonb AND ui.payload->'client_signoff_required'='true'::jsonb THEN ARRAY['ui_client'] ELSE ARRAY[]::text[] END='{}'::jsonb)
 AND p.snapshot->'baseline'=d.baseline AND p.snapshot->>'requirements_id'=dc.requirements_id::text
 AND psl_schedules_grants(d.case_id,p.actor_id,ARRAY['delivery.planning_decide'])
 AND psl_escalation_authority(d.case_id,p.actor_id,'PMO Lead',false,p.data->'authority')
 AND p.snapshot->'sources' ?& ARRAY['registration','scope_baseline','technical_design','test_strategy','uat_approach','ui_applicability']
 AND NOT EXISTS(SELECT 1 FROM jsonb_each(p.snapshot->'sources') pin WHERE NOT EXISTS(
 SELECT 1 FROM pmo_deliverysource s JOIN pmo_deliverysourceverification v ON v.source_id=s.id
 WHERE s.id=(pin.value->>0)::bigint AND v.id=(pin.value->>1)::bigint AND s.dossier_id=d.id AND s.kind=pin.key
 AND s.id=(SELECT max(id) FROM pmo_deliverysource WHERE dossier_id=d.id AND kind=pin.key)
 AND v.id=(SELECT max(id) FROM pmo_deliverysourceverification WHERE source_id=s.id) AND v.result->>'decision'='accepted'
 AND (s.kind<>'scope_baseline' OR NOT EXISTS(SELECT 1 FROM core_evidence pe WHERE pe.id=s.evidence_id AND pe.kind='planning_readiness') OR (psl_progress_readiness(s.evidence_id) AND EXISTS(SELECT 1 FROM core_evidence pe WHERE pe.id=s.evidence_id AND psl_escalation_json(pe.body)->'inputs'->>'candidate_id'=d.candidate_id::text)))
 AND psl_schedules_grants(d.case_id,v.actor_id,ARRAY['delivery.verify']))));
$$;"""

CURRENT_PLAN = r"""CREATE OR REPLACE FUNCTION psl_progress_plan(pid bigint) RETURNS boolean LANGUAGE sql STABLE AS $$
 SELECT EXISTS(SELECT 1 FROM pmo_deliveryrecord p JOIN pmo_deliverydossier d ON d.id=p.dossier_id
 JOIN pmo_baseline b ON b.case_id=d.case_id JOIN pmo_deliverycandidate dc ON dc.id=d.candidate_id
 WHERE p.id=pid AND p.kind='planning_decision' AND p.data->>'verdict'='approve'
 AND p.id=(SELECT max(id) FROM pmo_deliveryrecord WHERE dossier_id=d.id AND kind='planning_decision')
 AND d.baseline=jsonb_build_object('plan_id',b.plan_id,'costing_id',b.costing_id,'sow_id',b.sow_id)
 AND p.snapshot-ARRAY['baseline','requirements_id','sources','ui_target']='{}'::jsonb
 AND psl_delivery_ui_current(d.id,p.snapshot)
 AND EXISTS(SELECT 1 FROM pmo_deliverysource ui WHERE ui.id=(p.snapshot->'sources'->'ui_applicability'->>0)::bigint
 AND jsonb_typeof(ui.payload->'requires_ui')='boolean' AND jsonb_typeof(ui.payload->'client_signoff_required')='boolean'
 AND (ui.payload->'requires_ui'<>'true'::jsonb OR p.snapshot->'sources' ? 'ui_design')
 AND (ui.payload->'requires_ui'<>'true'::jsonb OR ui.payload->'client_signoff_required'<>'true'::jsonb OR p.snapshot->'sources' ? 'ui_client')
 AND (p.snapshot->'sources')-ARRAY['registration','scope_baseline','technical_design','test_strategy','uat_approach','ui_applicability']
 -CASE WHEN ui.payload->'requires_ui'='true'::jsonb THEN ARRAY['ui_target','ui_design'] ELSE ARRAY[]::text[] END
 -CASE WHEN ui.payload->'requires_ui'='true'::jsonb AND ui.payload->'client_signoff_required'='true'::jsonb THEN ARRAY['ui_client'] ELSE ARRAY[]::text[] END='{}'::jsonb)
 AND p.snapshot->'baseline'=d.baseline AND p.snapshot->>'requirements_id'=dc.requirements_id::text
 AND psl_schedules_grants(d.case_id,p.actor_id,ARRAY['delivery.planning_decide'])
 AND psl_escalation_authority(d.case_id,p.actor_id,'PMO Lead',false,p.data->'authority')
 AND p.snapshot->'sources' ?& ARRAY['registration','scope_baseline','technical_design','test_strategy','uat_approach','ui_applicability']
 AND NOT EXISTS(SELECT 1 FROM jsonb_each(p.snapshot->'sources') pin WHERE NOT EXISTS(
 SELECT 1 FROM pmo_deliverysource s JOIN pmo_deliverysourceverification v ON v.source_id=s.id
 WHERE s.id=(pin.value->>0)::bigint AND v.id=(pin.value->>1)::bigint AND s.dossier_id=d.id AND s.kind=pin.key
 AND s.id=(SELECT max(id) FROM pmo_deliverysource WHERE dossier_id=d.id AND kind=pin.key)
 AND v.id=(SELECT max(id) FROM pmo_deliverysourceverification WHERE source_id=s.id) AND v.result->>'decision'='accepted'
 AND (s.kind<>'scope_baseline' OR NOT EXISTS(SELECT 1 FROM core_evidence pe WHERE pe.id=s.evidence_id AND pe.kind='planning_readiness') OR (psl_progress_readiness(s.evidence_id) AND EXISTS(SELECT 1 FROM core_evidence pe WHERE pe.id=s.evidence_id AND psl_escalation_json(pe.body)->'inputs'->>'candidate_id'=d.candidate_id::text)))
 AND psl_schedules_grants(d.case_id,v.actor_id,ARRAY['delivery.verify']))));
$$;"""

SQL = r"""-- Additive P22 protocol defense. Requires accepted pmo0046 helpers.
CREATE FUNCTION psl_delivery_ui_identity(value jsonb) RETURNS boolean LANGUAGE sql IMMUTABLE AS $$
 SELECT COALESCE(jsonb_typeof(value)='object' AND value ?& ARRAY['artifact_ref','artifact_version','artifact_sha256']
 AND value-ARRAY['artifact_ref','artifact_version','artifact_sha256']='{}'::jsonb
 AND jsonb_typeof(value->'artifact_ref')='string' AND length(value->>'artifact_ref') BETWEEN 1 AND 240 AND value->>'artifact_ref' ~ '[^[:space:]]'
 AND jsonb_typeof(value->'artifact_version')='string' AND length(value->>'artifact_version') BETWEEN 1 AND 240 AND value->>'artifact_version' ~ '[^[:space:]]'
 AND jsonb_typeof(value->'artifact_sha256')='string' AND value->>'artifact_sha256' ~ '^[a-f0-9]{64}$',false);
$$;
CREATE FUNCTION psl_delivery_ui_payload(did bigint, skind text, value jsonb, eid bigint, complete boolean DEFAULT false) RETURNS boolean LANGUAGE plpgsql STABLE AS $$
DECLARE cid uuid; artifact core_evidence; target jsonb;
BEGIN
 SELECT case_id INTO cid FROM pmo_deliverydossier WHERE id=did;
 IF cid IS NULL OR psl_progress_public(cid,eid) IS DISTINCT FROM TRUE OR jsonb_typeof(value) IS DISTINCT FROM 'object'
 OR NOT EXISTS(SELECT 1 FROM core_evidence WHERE id=eid AND encode(sha256(convert_to(body,'UTF8')),'hex')=sha256) THEN RETURN false; END IF;
 IF skind='ui_target' THEN
  IF value->>'protocol' IS DISTINCT FROM 'ui-target/v1' OR NOT(value ?& ARRAY['protocol','artifact_ref','artifact_version','artifact_sha256','artifact_evidence'])
  OR value-ARRAY['protocol','artifact_ref','artifact_version','artifact_sha256','artifact_evidence']<>'{}'::jsonb
  OR (value->'artifact_ref'<>'null'::jsonb AND (jsonb_typeof(value->'artifact_ref') IS DISTINCT FROM 'string' OR length(value->>'artifact_ref') NOT BETWEEN 1 AND 240 OR value->>'artifact_ref' !~ '[^[:space:]]'))
  OR (value->'artifact_version'<>'null'::jsonb AND (jsonb_typeof(value->'artifact_version') IS DISTINCT FROM 'string' OR length(value->>'artifact_version') NOT BETWEEN 1 AND 240 OR value->>'artifact_version' !~ '[^[:space:]]'))
  OR (value->'artifact_sha256'<>'null'::jsonb AND (jsonb_typeof(value->'artifact_sha256') IS DISTINCT FROM 'string' OR value->>'artifact_sha256' !~ '^[a-f0-9]{64}$'))
  OR (complete AND (value->'artifact_evidence'='null'::jsonb OR psl_delivery_ui_identity(value-ARRAY['protocol','artifact_evidence']) IS DISTINCT FROM TRUE)) THEN RETURN false; END IF;
  IF value->'artifact_evidence'='null'::jsonb THEN RETURN NOT complete; END IF;
  SELECT * INTO artifact FROM core_evidence WHERE id::text=value->'artifact_evidence'->>'id' AND case_id=cid;
  RETURN artifact.id IS NOT NULL AND psl_progress_public(cid,artifact.id)
   AND value->'artifact_evidence'=jsonb_build_object('id',artifact.id,'version',artifact.version,'sha256',artifact.sha256)
   AND (value->'artifact_sha256'='null'::jsonb OR value->>'artifact_sha256'=artifact.sha256)
   AND encode(sha256(convert_to(artifact.body,'UTF8')),'hex')=artifact.sha256;
 ELSIF skind IN ('ui_design','ui_client') THEN
  IF value->>'protocol' IS DISTINCT FROM 'ui-approval/v1' OR NOT(value ?& ARRAY['protocol','source_version','signatory_ref','decided_at','approved_ui_target'])
  OR value-ARRAY['protocol','source_version','signatory_ref','decided_at','approved_ui_target']<>'{}'::jsonb
  OR psl_delivery_ui_identity(value->'approved_ui_target') IS DISTINCT FROM TRUE
  OR jsonb_typeof(value->'source_version') IS DISTINCT FROM 'string' OR length(value->>'source_version') NOT BETWEEN 1 AND 240 OR value->>'source_version' !~ '[^[:space:]]'
  OR jsonb_typeof(value->'signatory_ref') IS DISTINCT FROM 'string' OR length(value->>'signatory_ref') NOT BETWEEN 1 AND 240 OR value->>'signatory_ref' !~ '[^[:space:]]'
  OR jsonb_typeof(value->'decided_at') IS DISTINCT FROM 'string' OR length(value->>'decided_at') NOT BETWEEN 1 AND 64
  OR value->>'decided_at' !~ 'T.*(Z|[+-][0-9]{2}(:?[0-9]{2})?(:[0-9]{2})?)$' THEN RETURN false; END IF;
  RETURN (value->>'decided_at')::timestamptz<=statement_timestamp();
 END IF;
 RETURN false;
EXCEPTION WHEN invalid_text_representation OR invalid_datetime_format OR datetime_field_overflow THEN RETURN false;
END $$;
CREATE FUNCTION psl_delivery_ui_source(sid bigint) RETURNS boolean LANGUAGE sql STABLE AS $$
 SELECT EXISTS(SELECT 1 FROM pmo_deliverysource s JOIN pmo_deliverydossier d ON d.id=s.dossier_id
 WHERE s.id=sid AND length(btrim(s.external_ref)) BETWEEN 1 AND 240
 AND psl_delivery_ui_payload(s.dossier_id,s.kind,s.payload,s.evidence_id,true)
 AND psl_schedules_grants(d.case_id,s.actor_id,ARRAY['delivery.source']));
$$;
CREATE FUNCTION psl_delivery_ui_verified(sid bigint, vid bigint) RETURNS boolean LANGUAGE sql STABLE AS $$
 SELECT EXISTS(SELECT 1 FROM pmo_deliverysource s JOIN pmo_deliverydossier d ON d.id=s.dossier_id
 JOIN pmo_deliverycandidate candidate ON candidate.id=d.candidate_id JOIN core_evidence e ON e.id=s.evidence_id
 JOIN pmo_deliverysourceverification v ON v.source_id=s.id
 WHERE s.id=sid AND v.id=vid AND psl_delivery_ui_source(s.id)
 AND EXISTS(SELECT 1 FROM core_case WHERE id=d.case_id AND synthetic)
 AND s.id=(SELECT max(id) FROM pmo_deliverysource WHERE dossier_id=d.id AND kind=s.kind)
 AND v.id=(SELECT max(id) FROM pmo_deliverysourceverification WHERE source_id=s.id)
 AND psl_schedules_grants(d.case_id,v.actor_id,ARRAY['delivery.verify'])
 AND jsonb_typeof(v.result->'source_receipt')='string' AND length(btrim(v.result->>'source_receipt')) BETWEEN 1 AND 240
 AND v.result=jsonb_build_object('source_id',s.id,'candidate_ref',candidate.reference,'external_ref',s.external_ref,
 'owner',CASE s.kind WHEN 'ui_target' THEN 'Product/Design' WHEN 'ui_design' THEN 'Design Lead' ELSE 'Client' END,
 'evidence_sha256',e.sha256,'payload_sha256',encode(sha256(convert_to(psl_progress_canonical(s.payload),'UTF8')),'hex'),
 'decision','accepted','source_receipt',v.result->>'source_receipt','ui_binding',s.payload));
$$;
CREATE FUNCTION psl_delivery_ui_current(did bigint, snapshot jsonb) RETURNS boolean LANGUAGE plpgsql STABLE AS $$
DECLARE app pmo_deliverysource; av pmo_deliverysourceverification; target pmo_deliverysource; tv bigint; source pmo_deliverysource; vid bigint; k text; kinds text[]; cid uuid;
BEGIN
 SELECT case_id INTO cid FROM pmo_deliverydossier WHERE id=did;
 IF cid IS NULL OR jsonb_typeof(snapshot->'sources') IS DISTINCT FROM 'object' THEN RETURN false; END IF;
 SELECT * INTO app FROM pmo_deliverysource WHERE dossier_id=did AND kind='ui_applicability' ORDER BY id DESC LIMIT 1;
 SELECT * INTO av FROM pmo_deliverysourceverification WHERE source_id=app.id ORDER BY id DESC LIMIT 1;
 IF app.id IS NULL OR av.id IS NULL OR app.payload-ARRAY['requires_ui','client_signoff_required']<>'{}'::jsonb
 OR jsonb_typeof(app.payload->'requires_ui') IS DISTINCT FROM 'boolean' OR jsonb_typeof(app.payload->'client_signoff_required') IS DISTINCT FROM 'boolean'
 OR av.result->>'decision' IS DISTINCT FROM 'accepted' OR NOT psl_schedules_grants(cid,av.actor_id,ARRAY['delivery.verify'])
 OR snapshot->'sources'->'ui_applicability' IS DISTINCT FROM jsonb_build_array(app.id,av.id) THEN RETURN false; END IF;
 IF app.payload->'requires_ui'='false'::jsonb THEN
  RETURN NOT(snapshot ? 'ui_target') AND NOT(snapshot->'sources' ?| ARRAY['ui_target','ui_design','ui_client']);
 END IF;
 SELECT * INTO target FROM pmo_deliverysource WHERE dossier_id=did AND kind='ui_target' ORDER BY id DESC LIMIT 1;
 SELECT id INTO tv FROM pmo_deliverysourceverification WHERE source_id=target.id ORDER BY id DESC LIMIT 1;
 IF target.id IS NULL OR tv IS NULL OR NOT psl_delivery_ui_verified(target.id,tv)
 OR snapshot->'sources'->'ui_target' IS DISTINCT FROM jsonb_build_array(target.id,tv)
 OR snapshot->'ui_target' IS DISTINCT FROM (target.payload-'protocol')||jsonb_build_object('source_id',target.id,'verification_id',tv) THEN RETURN false; END IF;
 kinds:=ARRAY['ui_design'];
 IF app.payload->'client_signoff_required'='true'::jsonb THEN kinds:=array_append(kinds,'ui_client');
 ELSIF snapshot->'sources' ? 'ui_client' THEN RETURN false; END IF;
 FOREACH k IN ARRAY kinds LOOP
  SELECT * INTO source FROM pmo_deliverysource WHERE dossier_id=did AND kind=k ORDER BY id DESC LIMIT 1;
  SELECT id INTO vid FROM pmo_deliverysourceverification WHERE source_id=source.id ORDER BY id DESC LIMIT 1;
  IF source.id IS NULL OR vid IS NULL OR NOT psl_delivery_ui_verified(source.id,vid)
  OR snapshot->'sources'->k IS DISTINCT FROM jsonb_build_array(source.id,vid)
  OR source.payload->'approved_ui_target' IS DISTINCT FROM target.payload-ARRAY['protocol','artifact_evidence'] THEN RETURN false; END IF;
 END LOOP;
 RETURN true;
END $$;
CREATE FUNCTION psl_delivery_ui_source_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE cid uuid;
BEGIN
 IF NEW.kind NOT IN ('ui_target','ui_design','ui_client') THEN RETURN NEW; END IF;
 SELECT case_id INTO cid FROM pmo_deliverydossier WHERE id=NEW.dossier_id;
 PERFORM 1 FROM core_case WHERE id=cid FOR UPDATE;
 IF psl_delivery_ui_payload(NEW.dossier_id,NEW.kind,NEW.payload,NEW.evidence_id) IS DISTINCT FROM TRUE
 OR psl_schedules_grants(cid,NEW.actor_id,ARRAY['delivery.source']) IS DISTINCT FROM TRUE
 OR length(btrim(NEW.external_ref)) NOT BETWEEN 1 AND 240
 OR EXISTS(SELECT 1 FROM pmo_deliveryrecord WHERE dossier_id=NEW.dossier_id AND kind='closure')
 THEN RAISE EXCEPTION 'Typed authorized same-case UI artifact/owner source required'; END IF;
 IF NEW.kind='ui_target' AND NEW.payload->'artifact_sha256'<>'null'::jsonb AND EXISTS(SELECT 1 FROM pmo_deliverysource s WHERE s.dossier_id=NEW.dossier_id AND s.kind=NEW.kind
  AND s.payload->>'artifact_ref'=NEW.payload->>'artifact_ref' AND s.payload->>'artifact_version'=NEW.payload->>'artifact_version'
  AND s.payload->'artifact_sha256'<>'null'::jsonb AND s.payload->>'artifact_sha256' IS DISTINCT FROM NEW.payload->>'artifact_sha256')
 THEN RAISE EXCEPTION 'UI artifact reference/version content cannot be rebound'; END IF;
 IF NEW.kind IN ('ui_design','ui_client') AND EXISTS(SELECT 1 FROM pmo_deliverysource s WHERE s.dossier_id=NEW.dossier_id AND s.kind=NEW.kind AND s.external_ref=NEW.external_ref
  AND s.payload->>'source_version'=NEW.payload->>'source_version' AND (s.payload IS DISTINCT FROM NEW.payload OR s.evidence_id<>NEW.evidence_id))
 THEN RAISE EXCEPTION 'UI source receipt version cannot be rebound'; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER psl_delivery_ui_source_guard BEFORE INSERT ON pmo_deliverysource FOR EACH ROW EXECUTE FUNCTION psl_delivery_ui_source_guard();
CREATE FUNCTION psl_delivery_ui_verification_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE source pmo_deliverysource; d pmo_deliverydossier; e core_evidence; candidate pmo_deliverycandidate; target pmo_deliverysource; tv bigint;
BEGIN
 SELECT * INTO source FROM pmo_deliverysource WHERE id=NEW.source_id;
 IF source.kind NOT IN ('ui_target','ui_design','ui_client') THEN RETURN NEW; END IF;
 SELECT * INTO d FROM pmo_deliverydossier WHERE id=source.dossier_id;
 PERFORM 1 FROM core_case WHERE id=d.case_id FOR UPDATE;
 SELECT * INTO e FROM core_evidence WHERE id=source.evidence_id;
 SELECT * INTO candidate FROM pmo_deliverycandidate WHERE id=d.candidate_id;
 IF psl_delivery_ui_source(source.id) IS DISTINCT FROM TRUE
 OR source.id IS DISTINCT FROM (SELECT max(id) FROM pmo_deliverysource WHERE dossier_id=d.id AND kind=source.kind)
 OR psl_schedules_grants(d.case_id,NEW.actor_id,ARRAY['delivery.verify']) IS DISTINCT FROM TRUE
 OR NOT EXISTS(SELECT 1 FROM core_case WHERE id=d.case_id AND synthetic)
 OR EXISTS(SELECT 1 FROM pmo_deliveryrecord WHERE dossier_id=d.id AND kind='closure')
 OR jsonb_typeof(NEW.result->'source_receipt') IS DISTINCT FROM 'string' OR length(btrim(NEW.result->>'source_receipt')) NOT BETWEEN 1 AND 240
 OR NEW.result->>'decision' NOT IN ('accepted','rejected','unknown') OR NEW.result->>'decision' IS NULL
 OR NEW.result IS DISTINCT FROM jsonb_build_object('source_id',source.id,'candidate_ref',candidate.reference,'external_ref',source.external_ref,
 'owner',CASE source.kind WHEN 'ui_target' THEN 'Product/Design' WHEN 'ui_design' THEN 'Design Lead' ELSE 'Client' END,
 'evidence_sha256',e.sha256,'payload_sha256',encode(sha256(convert_to(psl_progress_canonical(source.payload),'UTF8')),'hex'),
 'decision',NEW.result->>'decision','source_receipt',NEW.result->>'source_receipt','ui_binding',source.payload)
 THEN RAISE EXCEPTION 'Current explicit UI source verification binding required'; END IF;
 IF source.kind<>'ui_target' AND NEW.result->>'decision'='accepted' THEN
  SELECT * INTO target FROM pmo_deliverysource WHERE dossier_id=d.id AND kind='ui_target' ORDER BY id DESC LIMIT 1;
  SELECT id INTO tv FROM pmo_deliverysourceverification WHERE source_id=target.id ORDER BY id DESC LIMIT 1;
  IF target.id IS NULL OR tv IS NULL OR psl_delivery_ui_verified(target.id,tv) IS DISTINCT FROM TRUE
  OR source.payload->'approved_ui_target' IS DISTINCT FROM target.payload-ARRAY['protocol','artifact_evidence']
  THEN RAISE EXCEPTION 'UI artifact target mismatch or current target verification missing'; END IF;
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER psl_delivery_ui_verification_guard BEFORE INSERT ON pmo_deliverysourceverification FOR EACH ROW EXECUTE FUNCTION psl_delivery_ui_verification_guard();
CREATE FUNCTION psl_delivery_ui_record_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE cid uuid; plan pmo_deliveryrecord;
BEGIN
 IF NEW.kind NOT IN ('planning_decision','kickoff','progress','glpi_request','release_ready') THEN RETURN NEW; END IF;
 SELECT case_id INTO cid FROM pmo_deliverydossier WHERE id=NEW.dossier_id;
 PERFORM 1 FROM core_case WHERE id=cid FOR UPDATE;
 IF NEW.kind='planning_decision' THEN
  IF psl_delivery_ui_current(NEW.dossier_id,NEW.snapshot) IS DISTINCT FROM TRUE THEN RAISE EXCEPTION 'Current exact UI artifact prerequisite snapshot required'; END IF;
 ELSE
  SELECT * INTO plan FROM pmo_deliveryrecord WHERE dossier_id=NEW.dossier_id AND kind='planning_decision' ORDER BY id DESC LIMIT 1;
  IF plan.id IS NULL OR psl_progress_plan(plan.id) IS DISTINCT FROM TRUE
  OR (CASE WHEN NEW.kind='release_ready' THEN NEW.snapshot->'upstream'->>'planning_id' ELSE NEW.snapshot->>'planning_id' END) IS DISTINCT FROM plan.id::text
  THEN RAISE EXCEPTION 'Current exact UI artifact planning prerequisite required'; END IF;
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER psl_delivery_ui_record_guard BEFORE INSERT ON pmo_deliveryrecord FOR EACH ROW EXECUTE FUNCTION psl_delivery_ui_record_guard();
"""

REVERSE = r"""DROP TRIGGER psl_delivery_ui_record_guard ON pmo_deliveryrecord;
DROP TRIGGER psl_delivery_ui_verification_guard ON pmo_deliverysourceverification;
DROP TRIGGER psl_delivery_ui_source_guard ON pmo_deliverysource;
DROP FUNCTION psl_delivery_ui_record_guard();
DROP FUNCTION psl_delivery_ui_verification_guard();
DROP FUNCTION psl_delivery_ui_source_guard();
DROP FUNCTION psl_delivery_ui_current(bigint,jsonb);
DROP FUNCTION psl_delivery_ui_verified(bigint,bigint);
DROP FUNCTION psl_delivery_ui_source(bigint);
DROP FUNCTION psl_delivery_ui_payload(bigint,text,jsonb,bigint,boolean);
DROP FUNCTION psl_delivery_ui_identity(jsonb);
"""

class Migration(migrations.Migration):
    dependencies = [('pmo','0046_delivery_progress_correlation')]
    operations = [migrations.RunSQL(SQL + CURRENT_PLAN, PREVIOUS_PLAN + REVERSE)]

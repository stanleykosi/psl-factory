from django.db import migrations

# Bounded structural defence in depth. Native services additionally validate
# private file bytes, current agent results, clocks, and all release conditions.
SQL=r"""
CREATE UNIQUE INDEX psl_client_uat_operation ON pmo_deliverysource ((payload->>'operation_key'))
 WHERE kind IN ('uat_client_target','uat_client_response');
CREATE UNIQUE INDEX psl_client_uat_revision ON pmo_deliverysource
 (dossier_id,kind,(coalesce(payload->>'target_id','')),(payload->>'number'))
 WHERE kind IN ('uat_client_target','uat_client_response');
CREATE FUNCTION psl_client_uat_source_current(sid bigint) RETURNS boolean LANGUAGE plpgsql STABLE AS $$
DECLARE s pmo_deliverysource; d pmo_deliverydossier; t pmo_deliverysource; pin jsonb;
BEGIN
 SELECT * INTO STRICT s FROM pmo_deliverysource WHERE id=sid;
 SELECT * INTO STRICT d FROM pmo_deliverydossier WHERE id=s.dossier_id;
 IF NOT psl_schedules_grants(d.case_id,s.actor_id,ARRAY['case.read','delivery.read','engagement.read','client_uat.record'])
  OR NOT psl_schedules_role_current(d.case_id,s.actor_id,s.payload->'recording_authority','PM') THEN RETURN false; END IF;
 IF s.kind='uat_client_target' THEN
  RETURN s.id=(SELECT max(id) FROM pmo_deliverysource WHERE dossier_id=d.id AND kind=s.kind)
   AND s.payload->'baseline'=d.baseline
   AND EXISTS(SELECT 1 FROM pmo_deliverycandidate c JOIN core_evidence e ON e.id=c.requirements_id
    WHERE c.id=d.candidate_id AND s.payload->'candidate'=jsonb_build_object('id',c.id,'reference',c.reference,'requirements_id',e.id,'requirements_sha256',e.sha256))
   AND EXISTS(SELECT 1 FROM core_clientcontactrevision c JOIN core_evidence e ON e.id=c.evidence_id
    WHERE c.id=(s.payload->'contact'->>'id')::bigint AND c.case_id=d.case_id AND c.purpose='project' AND c.customer=''
    AND c.number=(SELECT max(number) FROM core_clientcontactrevision WHERE case_id=d.case_id AND purpose='project' AND customer='')
    AND s.payload->'contact'=jsonb_build_object('id',c.id,'number',c.number,'evidence_id',e.id,'evidence_sha256',e.sha256)
    AND psl_schedules_grants(d.case_id,c.actor_id,ARRAY['case.read','engagement.read','engagement.capture'])
    AND psl_engagement_public_source(d.case_id,e.id));
 ELSIF s.kind='uat_client_response' THEN
  SELECT * INTO STRICT t FROM pmo_deliverysource WHERE id=(s.payload->>'target_id')::bigint AND dossier_id=d.id AND kind='uat_client_target';
  IF s.id<>(SELECT max(id) FROM pmo_deliverysource WHERE dossier_id=d.id AND kind=s.kind AND payload->>'target_id'=t.id::text)
   OR NOT psl_client_uat_source_current(t.id)
   OR s.payload->>'target_sha256'<>encode(sha256(convert_to(psl_fixed_json(t.payload),'UTF8')),'hex') THEN RETURN false; END IF;
  FOR pin IN SELECT value FROM jsonb_array_elements(s.payload->'proofs') LOOP
   IF NOT EXISTS(SELECT 1 FROM agents_caseupload u WHERE u.id=(pin->>'id')::bigint AND u.case_id=d.case_id AND u.actor_id=s.actor_id
     AND u.actor_id::text=pin->>'actor_id' AND u.sha256=pin->>'sha256' AND u.size::text=pin->>'size') THEN RETURN false; END IF;
  END LOOP;
  RETURN true;
 END IF;
 RETURN false;
EXCEPTION WHEN OTHERS THEN RETURN false;
END $$;
CREATE FUNCTION psl_client_uat_source_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE d pmo_deliverydossier; previous pmo_deliverysource; t pmo_deliverysource; expected_format text;
BEGIN
 IF NEW.kind NOT IN ('uat_client_target','uat_client_response') THEN RETURN NEW; END IF;
 SELECT * INTO STRICT d FROM pmo_deliverydossier WHERE id=NEW.dossier_id;
 PERFORM 1 FROM core_case WHERE id=d.case_id FOR UPDATE;
 IF NOT psl_schedules_grants(d.case_id,NEW.actor_id,ARRAY['case.read','delivery.read','engagement.read','client_uat.record','evidence.add'])
  OR NOT psl_schedules_role_current(d.case_id,NEW.actor_id,NEW.payload->'recording_authority','PM')
  OR NOT EXISTS(SELECT 1 FROM core_evidence WHERE id=NEW.evidence_id AND case_id=d.case_id AND kind='client_uat_metadata')
  OR NEW.external_ref IS DISTINCT FROM 'psl:client-uat:'||(NEW.payload->>'operation_key')
  OR (NEW.payload->>'operation_key') !~ '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
  OR (NEW.payload->>'command_sha256') !~ '^[0-9a-f]{64}$'
  THEN RAISE EXCEPTION 'Exact current human witness and source identity required'; END IF;
 SELECT * INTO previous FROM pmo_deliverysource WHERE dossier_id=d.id AND kind=NEW.kind
  AND (NEW.kind='uat_client_target' OR payload->'target_id'=NEW.payload->'target_id') ORDER BY id DESC LIMIT 1;
 IF NEW.payload->'predecessor_id' IS DISTINCT FROM coalesce(to_jsonb(previous.id),'null'::jsonb)
  OR (NEW.payload->>'number')::bigint IS DISTINCT FROM coalesce((previous.payload->>'number')::bigint,0)+1
  THEN RAISE EXCEPTION 'Exact predecessor and consecutive response revision required'; END IF;
 IF NEW.kind='uat_client_target' THEN
  expected_format:='psl.client-uat-target/v1';
  IF (NEW.payload->>'sent_at')::timestamptz>clock_timestamp() OR NEW.payload->'baseline'<>d.baseline
   THEN RAISE EXCEPTION 'Actual test request and exact baseline required'; END IF;
 ELSE
  expected_format:='psl.client-uat-response/v1';
  SELECT * INTO STRICT t FROM pmo_deliverysource WHERE id=(NEW.payload->>'target_id')::bigint AND dossier_id=d.id AND kind='uat_client_target';
  IF NOT psl_client_uat_source_current(t.id) OR NEW.payload->>'target_sha256'<>encode(sha256(convert_to(psl_fixed_json(t.payload),'UTF8')),'hex')
   OR NEW.payload->'genuine' IS DISTINCT FROM 'true'::jsonb
   OR NEW.payload->>'outcome' NOT IN ('approved','changes_requested','rejected','approved_with_workaround')
   OR jsonb_typeof(NEW.payload->'proofs')<>'array' OR jsonb_array_length(NEW.payload->'proofs') NOT BETWEEN 1 AND 4
   OR (NEW.payload->>'responded_at')::timestamptz NOT BETWEEN (t.payload->>'sent_at')::timestamptz AND clock_timestamp()
   THEN RAISE EXCEPTION 'Genuine exact client response with bounded proof and actual time required'; END IF;
 END IF;
 IF NEW.payload->>'format' IS DISTINCT FROM expected_format THEN RAISE EXCEPTION 'Typed client response format required'; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER psl_client_uat_source BEFORE INSERT ON pmo_deliverysource FOR EACH ROW EXECUTE FUNCTION psl_client_uat_source_guard();
CREATE FUNCTION psl_client_uat_insert_current() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF NEW.kind IN ('uat_client_target','uat_client_response') AND NOT psl_client_uat_source_current(NEW.id)
  THEN RAISE EXCEPTION 'Exact current client version, contact and original file pins required'; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER psl_client_uat_insert_current AFTER INSERT ON pmo_deliverysource FOR EACH ROW EXECUTE FUNCTION psl_client_uat_insert_current();
CREATE FUNCTION psl_client_uat_verification_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE s pmo_deliverysource; d pmo_deliverydossier; t pmo_deliverysource; cfg policy_configuration; rules jsonb; checkrow pmo_deliverysourceverification;
BEGIN
 SELECT * INTO s FROM pmo_deliverysource WHERE id=NEW.source_id;
 IF s.kind NOT IN ('uat_client_target','uat_client_response') THEN RETURN NEW; END IF;
 SELECT * INTO STRICT d FROM pmo_deliverydossier WHERE id=s.dossier_id;
 PERFORM 1 FROM core_case WHERE id=d.case_id FOR UPDATE;
 IF s.kind<>'uat_client_response' OR NEW.adapter NOT IN ('client-uat-evidence-check/v1','human-client-uat-proof/v1','client-uat-recording-withdrawal/v1')
  OR NOT (NEW.result ?& ARRAY['source_id','candidate_ref','external_ref','owner','evidence_sha256','payload_sha256','decision','source_receipt','purpose','external_authenticity_verified','go_live_accepted','payment_authorized','record_type'])
  OR NEW.result->>'decision' NOT IN ('accepted','rejected','unknown')
  OR NEW.result->>'source_id' IS DISTINCT FROM s.id::text
  OR NEW.result->>'purpose' IS DISTINCT FROM 'ordinary_client_uat'
  OR NEW.result->'external_authenticity_verified' IS DISTINCT FROM 'false'::jsonb
  OR NEW.result->'go_live_accepted' IS DISTINCT FROM 'false'::jsonb
  OR NEW.result->'payment_authorized' IS DISTINCT FROM 'false'::jsonb
  OR NEW.result->>'payload_sha256' IS DISTINCT FROM encode(sha256(convert_to(psl_fixed_json(s.payload),'UTF8')),'hex')
  THEN RAISE EXCEPTION 'Human proof cannot impersonate an external signature, go-live or payment decision'; END IF;
 IF NEW.adapter='client-uat-recording-withdrawal/v1' THEN
  IF NEW.actor_id<>s.actor_id OR NOT psl_schedules_grants(d.case_id,NEW.actor_id,ARRAY['case.read','delivery.read','engagement.read','client_uat.record'])
   OR NEW.result->>'decision'<>'unknown' THEN RAISE EXCEPTION 'Only the current original witness can retract their recording'; END IF;
  RETURN NEW;
 END IF;
 IF NOT psl_client_uat_source_current(s.id) OR NOT psl_schedules_grants(d.case_id,NEW.actor_id,ARRAY['case.read','delivery.read','engagement.read','client_uat.proof.read'])
  THEN RAISE EXCEPTION 'Current source and private proof authority required'; END IF;
 IF NEW.adapter='client-uat-evidence-check/v1' THEN
  IF NOT (NEW.result ? 'checks') OR NOT psl_schedules_grants(d.case_id,NEW.actor_id,ARRAY['client_uat.inspect']) OR NEW.result->>'decision'<>'unknown'
   THEN RAISE EXCEPTION 'File inspection cannot grant client approval'; END IF;
 ELSE
  IF NOT (NEW.result ?& ARRAY['policy_id','inspection_id','inspection_sha256','authority','reviewer_role','verdict','proof_confirmed','operation_key','note'])
   THEN RAISE EXCEPTION 'Typed human review identity required'; END IF;
  SELECT * INTO STRICT cfg FROM policy_configuration WHERE id=(NEW.result->>'policy_id')::bigint AND case_id=d.case_id AND component='P02.client_response_rules';
  SELECT value INTO rules FROM jsonb_array_elements(psl_schedules_values(cfg.id)) LIMIT 1;
  SELECT * INTO STRICT checkrow FROM pmo_deliverysourceverification WHERE id=(NEW.result->>'inspection_id')::bigint AND source_id=s.id AND adapter='client-uat-evidence-check/v1';
  IF NOT psl_schedules_policy_current(d.case_id,cfg.id) OR NOT (rules->'reviewer_ids' @> to_jsonb(ARRAY[NEW.actor_id]))
   OR NOT psl_schedules_role_current(d.case_id,NEW.actor_id,NEW.result->'authority',rules->>'reviewer_role')
   OR NOT psl_schedules_grants(d.case_id,NEW.actor_id,ARRAY['client_uat.review'])
   OR checkrow.id<>(SELECT max(id) FROM pmo_deliverysourceverification WHERE source_id=s.id AND adapter=checkrow.adapter)
   OR NEW.result->>'inspection_sha256'<>encode(sha256(convert_to(psl_fixed_json(checkrow.result),'UTF8')),'hex')
   THEN RAISE EXCEPTION 'Exact current nominated human proof review required'; END IF;
  SELECT * INTO STRICT t FROM pmo_deliverysource WHERE id=(s.payload->>'target_id')::bigint;
  IF rules->'independent_review'='true'::jsonb AND NEW.actor_id IN (s.actor_id,t.actor_id)
   THEN RAISE EXCEPTION 'Independent reviewer cannot be the original witness'; END IF;
  IF NEW.result->>'decision'='accepted' AND (NEW.result->>'verdict' IS DISTINCT FROM 'confirm' OR NEW.result->'proof_confirmed' IS DISTINCT FROM 'true'::jsonb
   OR s.payload->>'outcome' NOT IN ('approved','approved_with_workaround')) THEN RAISE EXCEPTION 'Only actual client approval can qualify acceptance'; END IF;
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER psl_client_uat_verification BEFORE INSERT ON pmo_deliverysourceverification FOR EACH ROW EXECUTE FUNCTION psl_client_uat_verification_guard();
CREATE FUNCTION psl_client_uat_binding_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE review pmo_deliverysourceverification; s pmo_deliverysource; d pmo_deliverydossier; gate pmo_gaterecord; verification pmo_gateverification;
BEGIN
 IF TG_OP<>'INSERT' THEN RAISE EXCEPTION 'Client proof binding history is immutable'; END IF;
 SELECT * INTO STRICT review FROM pmo_deliverysourceverification WHERE id=NEW.review_id AND adapter='human-client-uat-proof/v1';
 SELECT * INTO STRICT s FROM pmo_deliverysource WHERE id=review.source_id AND kind='uat_client_response';
 SELECT * INTO STRICT d FROM pmo_deliverydossier WHERE id=s.dossier_id;
 PERFORM 1 FROM core_case WHERE id=d.case_id FOR UPDATE;
 SELECT * INTO STRICT verification FROM pmo_gateverification WHERE id=NEW.verification_id;
 SELECT * INTO STRICT gate FROM pmo_gaterecord WHERE id=verification.record_id;
 IF NOT psl_client_uat_source_current(s.id) OR review.result->>'decision' IS DISTINCT FROM 'accepted' OR review.result->>'verdict' IS DISTINCT FROM 'confirm'
  OR review.id<>(SELECT max(id) FROM pmo_deliverysourceverification WHERE source_id=s.id AND adapter IN ('human-client-uat-proof/v1','client-uat-recording-withdrawal/v1'))
  OR NOT psl_schedules_policy_current(d.case_id,(review.result->>'policy_id')::bigint)
  OR NOT psl_schedules_grants(d.case_id,review.actor_id,ARRAY['case.read','delivery.read','engagement.read','client_uat.review','client_uat.proof.read'])
  OR NOT psl_schedules_role_current(d.case_id,review.actor_id,review.result->'authority',review.result->>'reviewer_role')
  OR gate.candidate_id<>d.candidate_id OR gate.kind<>'uat_client' OR verification.result->>'decision'<>'accepted'
  OR gate.id<>(SELECT max(id) FROM pmo_gaterecord WHERE candidate_id=d.candidate_id AND kind='uat_client')
  OR verification.id<>(SELECT max(id) FROM pmo_gateverification WHERE record_id=gate.id)
  OR NOT psl_schedules_grants(d.case_id,NEW.actor_id,ARRAY['case.read','delivery.read','engagement.read','client_uat.export','pmo.gate_record','pmo.gate_verify'])
  OR NEW.snapshot IS DISTINCT FROM jsonb_build_object('purpose','ordinary_client_uat','source_id',s.id,
   'payload_sha256',encode(sha256(convert_to(psl_fixed_json(s.payload),'UTF8')),'hex'),'target_id',s.payload->'target_id',
   'review_id',review.id,'review_sha256',encode(sha256(convert_to(psl_fixed_json(review.result),'UTF8')),'hex'),
   'export_actor_id',NEW.actor_id,'external_authenticity_verified',false,'go_live_accepted',false,'payment_authorized',false)
  THEN RAISE EXCEPTION 'Exact current reviewed client proof and delivery gate required'; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER psl_client_uat_binding BEFORE INSERT OR UPDATE OR DELETE ON pmo_clientuatgatebinding FOR EACH ROW EXECUTE FUNCTION psl_client_uat_binding_guard();
"""
REVERSE=r"""
DROP TRIGGER psl_client_uat_binding ON pmo_clientuatgatebinding;
DROP FUNCTION psl_client_uat_binding_guard();
DROP TRIGGER psl_client_uat_verification ON pmo_deliverysourceverification;
DROP FUNCTION psl_client_uat_verification_guard();
DROP TRIGGER psl_client_uat_source ON pmo_deliverysource;
DROP FUNCTION psl_client_uat_source_guard();
DROP TRIGGER psl_client_uat_insert_current ON pmo_deliverysource;
DROP FUNCTION psl_client_uat_insert_current();
DROP FUNCTION psl_client_uat_source_current(bigint);
DROP INDEX psl_client_uat_revision;
DROP INDEX psl_client_uat_operation;
"""


class Migration(migrations.Migration):
    dependencies=[('pmo','0070_client_uat_gate_binding'),('finance','0081_payroll_question_guards')]
    operations=[migrations.RunSQL(SQL,REVERSE)]

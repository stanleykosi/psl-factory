-- Provisional isolated schema guard. Final workflows0070 must embed this literal SQL
-- after actual accepted0069; this file does not claim an applied migration.
CREATE FUNCTION psl_change_intake_confirmation() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE cid uuid;
BEGIN
 SELECT case_id INTO cid FROM core_audit WHERE id=NEW.receipt_id;
 PERFORM 1 FROM core_case WHERE id=cid FOR UPDATE;
 IF NOT EXISTS(
  SELECT 1 FROM core_audit a
  JOIN core_evidence raw ON raw.id::text=a.data->>'source' AND raw.case_id=a.case_id
  JOIN pmo_changeversion v ON v.id=NEW.version_id
  JOIN pmo_changerequest cr ON cr.id=v.change_id AND cr.case_id=a.case_id
  JOIN core_evidence e ON e.id=v.evidence_id AND e.case_id=a.case_id
  JOIN auth_user u ON u.id=NEW.actor_id AND u.is_active
  WHERE a.id=NEW.receipt_id AND a.action='factory.change_request_received'
   AND a.data->>'schema'='p56-change-intake/v1'
   AND raw.kind='agent_private_change_request' AND raw.sha256=a.data->>'sha256' AND raw.created_by_id=a.actor_id
   AND encode(sha256(convert_to(raw.body,'UTF8')),'hex')=raw.sha256
   AND v.actor_id=NEW.actor_id AND cr.current_id=v.id
   AND e.kind='change_request' AND e.source='psl:p56-confirmed-request/v1' AND e.created_by_id=NEW.actor_id
   AND (CASE WHEN e.body IS JSON OBJECT THEN e.body::jsonb ELSE '{}'::jsonb END)->>'schema'='p56-confirmed-request/v1'
   AND (CASE WHEN e.body IS JSON OBJECT THEN e.body::jsonb ELSE '{}'::jsonb END)->>'intake'=a.id::text
   AND (CASE WHEN e.body IS JSON OBJECT THEN e.body::jsonb ELSE '{}'::jsonb END)->>'source_id'=raw.id::text AND (CASE WHEN e.body IS JSON OBJECT THEN e.body::jsonb ELSE '{}'::jsonb END)->>'source_sha256'=raw.sha256
   AND (CASE WHEN e.body IS JSON OBJECT THEN e.body::jsonb ELSE '{}'::jsonb END)->'fields'=NEW.payload->'fields'
   AND (CASE WHEN e.body IS JSON OBJECT THEN e.body::jsonb ELSE '{}'::jsonb END)->'confirmation'=NEW.payload AND (CASE WHEN e.body IS JSON OBJECT THEN e.body::jsonb ELSE '{}'::jsonb END)->>'confirmation_sha256'=NEW.sha256
   AND cr.reference=NEW.payload->'fields'->>'reference'
   AND (v.number=1 AND NEW.payload->'fields'->'predecessor_version_id'='null'::jsonb OR EXISTS(SELECT 1 FROM pmo_changeversion predecessor
     WHERE predecessor.id::text=NEW.payload->'fields'->>'predecessor_version_id' AND predecessor.change_id=v.change_id AND predecessor.number+1=v.number))
   AND v.category=NEW.payload->'fields'->>'category'
   AND v.module=NEW.payload->'fields'->>'module'
   AND v.description=NEW.payload->'fields'->>'description'
   AND v.reason=NEW.payload->'fields'->>'reason'
   AND to_jsonb(v.incident_id) IS NOT DISTINCT FROM NULLIF(NEW.payload->'fields'->'incident_id','null'::jsonb)
   AND jsonb_typeof(NEW.payload->'fields'->'requestor')='string'
   AND length(trim(NEW.payload->'fields'->>'requestor')) BETWEEN 1 AND 160
   AND NEW.payload->'fields'->>'date_raised' ~ '^\d{4}-\d{2}-\d{2}$'
   AND to_char((NEW.payload->'fields'->>'date_raised')::date,'YYYY-MM-DD')=NEW.payload->'fields'->>'date_raised'
   AND (NEW.payload->'fields'->>'date_raised')::date <= (CURRENT_TIMESTAMP AT TIME ZONE 'Africa/Lagos')::date
   AND length(trim(NEW.payload->'fields'->>'category_basis')) BETWEEN 1 AND 2000
   AND NEW.payload - ARRAY['fields','note','extraction_id']='{}'::jsonb
   AND (NEW.payload->'fields') - ARRAY['reference','requestor','date_raised','module','description','reason','category','category_basis','incident_id','template_id','predecessor_version_id']='{}'::jsonb
   AND (NEW.extraction_id IS NULL AND NEW.payload->'extraction_id'='null'::jsonb AND NOT EXISTS(SELECT 1 FROM core_audit er WHERE er.case_id=a.case_id AND er.action='factory.change_request_extracted' AND er.data->>'receipt'=a.id::text) OR EXISTS(
      SELECT 1 FROM agents_agentrun r JOIN core_audit x ON x.case_id=a.case_id
       AND x.action='factory.change_request_extracted' AND x.data->>'receipt'=a.id::text AND x.data->>'run'=r.id::text
      WHERE r.id=NEW.extraction_id AND r.case_id=a.case_id AND r.evidence_id=raw.id AND r.process_id='P56'
       AND NEW.payload->>'extraction_id'=r.id::text AND r.result->>'schema'='p56-extraction/v1'))
   AND NOT EXISTS(SELECT 1 FROM core_audit later WHERE later.case_id=a.case_id AND
      (later.action='factory.change_request_received' AND later.data->>'predecessor'=a.id::text OR
       later.action='factory.change_request_cancelled' AND later.data->>'receipt'=a.id::text))
   AND NOT EXISTS(SELECT 1 FROM unnest(ARRAY['case.read','change.read','factory.read','factory.start','evidence.add','change.manage']) permission
     WHERE NOT EXISTS(SELECT 1 FROM identity_grant g WHERE g.case_id=a.case_id AND g.user_id=NEW.actor_id AND g.action=permission AND g.active))
   AND (v.category='Emergency' AND NEW.work_id IS NULL OR v.category IN ('Normal','Standard') AND
      (NEW.work_id IS NULL AND NEW.payload->'fields'->'predecessor_version_id'<>'null'::jsonb AND EXISTS(SELECT 1 FROM workflows_factorywork existing
       WHERE existing.case_id=a.case_id AND existing.definition='pmo-change/v1' AND existing.request->>'change'=cr.id::text) OR EXISTS(
       SELECT 1 FROM workflows_factorywork w JOIN core_evidence we ON we.id=w.source_head_id
       WHERE w.id=NEW.work_id AND w.case_id=a.case_id AND w.definition='pmo-change/v1'
        AND we.kind='agent_private_change_intake' AND we.source='psl:factory-change-intake/v1'
        AND w.request->>'change'=cr.id::text AND (CASE WHEN we.body IS JSON OBJECT THEN we.body::jsonb ELSE '{}'::jsonb END)->>'change_version_id'=v.id::text
        AND (CASE WHEN we.body IS JSON OBJECT THEN we.body::jsonb ELSE '{}'::jsonb END)->'inputs'->'template_id'=NEW.payload->'fields'->'template_id'
        AND (CASE WHEN we.body IS JSON OBJECT THEN we.body::jsonb ELSE '{}'::jsonb END)->'inputs'->'authorization_id'='null'::jsonb)))
 ) THEN RAISE EXCEPTION 'Exact current P56 source, PM classification and native handoff binding required'; END IF;
 IF NOT EXISTS(
   SELECT 1 FROM policy_configuration p JOIN core_case c ON c.id=p.case_id
   JOIN policy_registeredreference r ON r.case_id=p.case_id AND r.version=1
   WHERE NEW.authority - ARRAY['D05.role_principal_assignments']='{}'::jsonb AND p.id::text=NEW.authority->>'D05.role_principal_assignments' AND p.case_id=cid
    AND p.component='D05.role_principal_assignments'
    AND (c.synthetic OR (SELECT count(*) FROM policy_registeredreference own WHERE own.case_id=p.case_id AND own.version=1 AND p.envelope->'value' @> to_jsonb(ARRAY[own.ref]) AND own.content->>'user_id'=NEW.actor_id::text)=1 OR
      NOT EXISTS(SELECT 1 FROM policy_registeredreference own WHERE own.case_id=p.case_id AND own.version=1 AND p.envelope->'value' @> to_jsonb(ARRAY[own.ref]) AND own.content->>'user_id'=NEW.actor_id::text
        AND (NOT own.content ? 'eligibility' OR NOT (own.content->'eligibility'->'roles' ? (own.content->>'role'))
          OR (own.content->'eligibility'->>'valid_from')::timestamptz>CURRENT_TIMESTAMP
          OR (own.content->'eligibility'->>'valid_until')::timestamptz<=CURRENT_TIMESTAMP)))
    AND (SELECT state FROM policy_policystate WHERE configuration_id=p.id ORDER BY id DESC LIMIT 1)='active'
    AND p.envelope->'value' @> to_jsonb(ARRAY[r.ref])
    AND r.content->>'role'='PM' AND r.content->>'user_id'=NEW.actor_id::text
    AND (p.envelope->>'effective_from')::timestamptz<=CURRENT_TIMESTAMP
    AND (p.envelope->>'effective_until' IS NULL OR (p.envelope->>'effective_until')::timestamptz>CURRENT_TIMESTAMP)
 ) THEN RAISE EXCEPTION 'Current assigned PM required, not a classification approval'; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER psl_change_intake_binding BEFORE INSERT ON workflows_changeintakeconfirmation FOR EACH ROW EXECUTE FUNCTION psl_change_intake_confirmation();
CREATE TRIGGER psl_immutable BEFORE UPDATE OR DELETE ON workflows_changeintakeconfirmation FOR EACH ROW EXECUTE FUNCTION psl_append_only();

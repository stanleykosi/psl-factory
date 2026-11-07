"""F01 supplied-incumbent reference envelope; frozen exact actual0076 extension.

No native ledger, document or prior migration changes. Literal SQL only.
"""
from django.db import migrations

PREVIOUS = r"""-- Structural defense in depth. Python native services retain full business validation.
CREATE OR REPLACE FUNCTION psl_bu_private(wid bigint,uid bigint) RETURNS boolean LANGUAGE plpgsql STABLE AS $$
DECLARE w record; p record; cfg record; v jsonb;
BEGIN
 SELECT * INTO w FROM finance_buwork WHERE id=wid;
 IF NOT FOUND OR NOT psl_schedules_grants(w.case_id,uid,ARRAY['case.read','bu.read','bu.private.read']) THEN RETURN false; END IF;
 IF w.payroll_id IS NOT NULL THEN
  SELECT r.*,q.metadata AS scope,q.case_id INTO p FROM finance_payrollrun r JOIN finance_payrollrequest q ON q.id=r.request_id WHERE r.id=w.payroll_id AND q.case_id=w.case_id;
  IF NOT FOUND OR NOT psl_schedules_grants(w.case_id,uid,ARRAY['payroll.read','payroll.private.read']) THEN RETURN false; END IF;
  SELECT c.* INTO cfg FROM policy_configuration c WHERE c.case_id=w.case_id AND c.component='F16.input_access_rules' AND psl_schedules_policy_current(w.case_id,c.id);
  IF NOT FOUND THEN RETURN false; END IF;
  v=psl_schedules_values(cfg.id)->0;
  RETURN COALESCE(v->'reader_ids' @> to_jsonb(ARRAY[uid]) AND v->'entity'=p.scope->'entity' AND v->'currency'=p.scope->'currency'
   AND v->>'from_period'<=p.scope->>'period' AND v->>'to_period'>=p.scope->>'period',false);
 END IF;
 SELECT c.* INTO cfg FROM policy_configuration c WHERE c.case_id=w.case_id AND c.component='F44.source_rules' AND psl_schedules_policy_current(w.case_id,c.id);
 IF NOT FOUND THEN RETURN false; END IF;
 v=psl_schedules_values(cfg.id)->0;
 RETURN COALESCE(v->'reader_ids' @> to_jsonb(ARRAY[uid]) AND v->'entity'=w.metadata->'scope'->'entity'
  AND v->>'from_period'<=w.metadata->'scope'->>'period' AND v->>'to_period'>=w.metadata->'scope'->>'period',false);
END $$;

CREATE OR REPLACE FUNCTION psl_bu_authority(wid bigint,uid bigint,purpose text,pins jsonb) RETURNS boolean LANGUAGE sql STABLE AS $$
 SELECT EXISTS(SELECT 1 FROM finance_buwork w JOIN policy_configuration c ON c.id=(pins->>'BU.review_authority')::bigint
 WHERE w.id=wid AND c.component='BU.review_authority' AND psl_schedules_policy_current(w.case_id,c.id)
 AND psl_schedules_role_current(w.case_id,uid,pins,'Finance')
 AND EXISTS(SELECT 1 FROM jsonb_array_elements(psl_schedules_values(c.id)->0->'assignments') a
  WHERE a->>'user_id'=uid::text AND a->'purposes' ? purpose)
 AND (purpose='publish' OR psl_schedules_values(c.id)->0->'independent_reviewer'='false'::jsonb OR w.actor_id<>uid));
$$;

CREATE OR REPLACE FUNCTION psl_bu_current(wid bigint,depth integer DEFAULT 0) RETURNS boolean LANGUAGE plpgsql STABLE AS $$
DECLARE w record; p record; v jsonb; rid bigint; inventory jsonb; cmp record;
BEGIN
 IF depth>4 THEN RETURN false; END IF;
 SELECT * INTO w FROM finance_buwork WHERE id=wid;
 IF NOT FOUND OR w.metadata->'accepted' IS DISTINCT FROM 'true'::jsonb OR (w.metadata->>'retain_until')::timestamptz<=statement_timestamp()
  OR NOT psl_schedules_grants(w.case_id,w.actor_id,ARRAY['case.read','bu.read',CASE WHEN w.kind='source' THEN 'bu.capture' ELSE 'bu.'||w.kind END])
  OR EXISTS(SELECT 1 FROM finance_buwork n WHERE n.case_id=w.case_id AND n.reference=w.reference AND n.kind=w.kind AND n.version>w.version AND n.metadata->'accepted'='true'::jsonb)
  OR EXISTS(SELECT 1 FROM jsonb_each(w.metadata->'policy_ids') pin WHERE NOT psl_schedules_policy_current(w.case_id,(pin.value#>>'{}')::bigint))
 THEN RETURN false; END IF;
 IF w.kind<>'source' AND NOT psl_bu_private(wid,w.actor_id) THEN RETURN false; END IF;
 IF w.kind='source' THEN
  v=psl_schedules_values((w.metadata->'policy_ids'->>'F44.source_rules')::bigint)->0;
  IF v->>'owner_id' IS DISTINCT FROM w.actor_id::text OR NOT psl_schedules_role_current(w.case_id,w.actor_id,w.metadata->'owner_authority','Finance')
   OR extract(epoch FROM statement_timestamp()-(w.metadata->>'extracted_at')::timestamptz)>(v->>'max_age_seconds')::numeric THEN RETURN false; END IF;
 END IF;
 IF w.payroll_id IS NOT NULL THEN
  SELECT r.*,q.case_id,q.reference AS request_reference,q.version AS request_version,q.metadata AS request_scope INTO p FROM finance_payrollrun r JOIN finance_payrollrequest q ON q.id=r.request_id WHERE r.id=w.payroll_id AND q.case_id=w.case_id;
  IF NOT FOUND OR p.kind<>'match' OR p.sha256 IS DISTINCT FROM w.metadata->>'payroll_sha256' OR p.retain_until<=statement_timestamp()
   OR EXISTS(SELECT 1 FROM finance_payrollrequest n WHERE n.case_id=w.case_id AND n.reference=p.request_reference AND n.version>p.request_version)
   OR EXISTS(SELECT 1 FROM jsonb_each(p.metadata->'policy_ids') pin WHERE NOT psl_schedules_policy_current(w.case_id,(pin.value#>>'{}')::bigint))
  THEN RETURN false; END IF;
  IF w.kind='staff' THEN
   v=psl_schedules_values((w.metadata->'policy_ids'->>'F21.allocation_rules')::bigint)->0;
   SELECT COALESCE(jsonb_agg(jsonb_build_object('rule_id',r.id,'review_id',rv.id,'verdict',COALESCE(rv.verdict,'pending')) ORDER BY r.id),'[]'::jsonb) INTO inventory
   FROM (SELECT DISTINCT ON (reference) * FROM finance_buwork WHERE case_id=w.case_id AND payroll_id=w.payroll_id AND kind='rule'
    AND metadata->'accepted'='true'::jsonb AND v->'components' ? (payload->>'component') ORDER BY reference,version DESC) r
   LEFT JOIN LATERAL (SELECT id,verdict FROM finance_bureview WHERE work_id=r.id AND purpose='rule' ORDER BY id DESC LIMIT 1) rv ON true;
   IF inventory IS DISTINCT FROM w.metadata->'exception_inventory'
    OR EXISTS(SELECT 1 FROM jsonb_array_elements(inventory) i WHERE i->>'verdict'<>'revoke' AND NOT(w.metadata->'rule_ids' @> jsonb_build_array(i->'rule_id'))) THEN RETURN false; END IF;
  END IF;
 END IF;
 IF w.parent_id IS NOT NULL AND NOT psl_bu_current(w.parent_id,depth+1) THEN RETURN false; END IF;
 FOR rid IN SELECT value::bigint FROM jsonb_array_elements_text(COALESCE(w.metadata->'rule_ids','[]'::jsonb)) LOOP
  IF NOT psl_bu_current(rid,depth+1) THEN RETURN false; END IF;
 END LOOP;
 IF w.metadata->'comparison' IS NOT NULL AND w.metadata->'comparison'<>'null'::jsonb THEN
  SELECT * INTO cmp FROM finance_financerun WHERE id=(w.metadata->'comparison'->>'run_id')::bigint AND case_id=w.case_id AND kind='allocation';
  IF NOT FOUND OR NOT psl_schedules_grants(w.case_id,w.actor_id,ARRAY['finance.calculate']) OR NOT psl_schedules_mapping_current(cmp.parent_id)
   OR cmp.result->>'status'<>'complete' OR cmp.result->'conservation'->(w.metadata->'comparison'->>'metric')->'conserved' IS DISTINCT FROM 'true'::jsonb
   OR EXISTS(SELECT 1 FROM jsonb_each(cmp.snapshot->'policies') pin WHERE NOT psl_schedules_policy_pin_current(w.case_id,pin.key,pin.value))
   OR NOT psl_schedules_finance_review_current((cmp.snapshot->'source_review'->>'id')::bigint)
  THEN RETURN false; END IF;
 END IF;
 RETURN true;
END $$;

CREATE OR REPLACE FUNCTION psl_bu_review(rid bigint,depth integer DEFAULT 0) RETURNS boolean LANGUAGE plpgsql STABLE AS $$
DECLARE r record; w record; parent_review bigint; rule_id bigint;
BEGIN
 IF depth>4 THEN RETURN false; END IF;
 SELECT * INTO r FROM finance_bureview WHERE id=rid;
 IF NOT FOUND THEN RETURN false; END IF;
 SELECT * INTO w FROM finance_buwork WHERE id=r.work_id;
 IF r.verdict<>'approve' OR r.subject_sha256<>w.sha256 OR r.id<>(SELECT max(id) FROM finance_bureview WHERE work_id=w.id AND purpose=r.purpose)
  OR NOT psl_bu_current(w.id) OR NOT psl_bu_private(w.id,r.actor_id)
  OR NOT psl_schedules_grants(w.case_id,r.actor_id,ARRAY['bu.review']) OR NOT psl_bu_authority(w.id,r.actor_id,r.purpose,r.authority) THEN RETURN false; END IF;
 IF w.payroll_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM finance_payrollreview pr JOIN finance_payrollrun p ON p.id=pr.run_id
  WHERE p.id=w.payroll_id AND pr.verdict='approve' AND pr.subject_sha256=p.sha256
   AND pr.id=(SELECT max(id) FROM finance_payrollreview WHERE run_id=p.id)
   AND psl_schedules_grants(w.case_id,pr.actor_id,ARRAY['case.read','payroll.read','payroll.private.read','payroll.review'])
   AND psl_schedules_authority_current(w.case_id,pr.authority)) THEN RETURN false; END IF;
 IF w.parent_id IS NOT NULL THEN
  SELECT rv.id INTO parent_review FROM finance_bureview rv JOIN finance_buwork p ON p.id=rv.work_id WHERE p.id=w.parent_id AND rv.purpose=p.kind ORDER BY rv.id DESC LIMIT 1;
  IF parent_review IS NULL OR NOT psl_bu_review(parent_review,depth+1) THEN RETURN false; END IF;
 END IF;
 FOR rule_id IN SELECT value::bigint FROM jsonb_array_elements_text(COALESCE(w.metadata->'rule_ids','[]'::jsonb)) LOOP
  SELECT id INTO parent_review FROM finance_bureview WHERE work_id=rule_id AND purpose='rule' ORDER BY id DESC LIMIT 1;
  IF parent_review IS NULL OR NOT psl_bu_review(parent_review,depth+1) THEN RETURN false; END IF;
 END LOOP;
 RETURN true;
END $$;

CREATE OR REPLACE FUNCTION psl_minutes_current(wid bigint, head bigint, vid bigint) RETURNS boolean LANGUAGE sql STABLE AS $$
 SELECT EXISTS(
  SELECT 1 FROM workflows_factorywork w JOIN core_evidence e ON e.id=head AND e.case_id=w.case_id
  JOIN core_audit c ON c.case_id=w.case_id AND c.action='factory.minutes_confirmed' AND c.data->>'work'=w.id::text AND c.data->>'head'=e.id::text
  JOIN pmo_meetingversion mv ON mv.id=(c.data->>'meeting_version')::bigint AND mv.created_by_id=c.actor_id
  JOIN pmo_meeting m ON m.id=mv.meeting_id AND m.current_id=mv.id AND m.case_id=w.case_id AND m.reference=w.request->>'reference'
  JOIN pmo_minutesreportbinding b ON b.meeting_id=m.id AND b.version_id=vid
  JOIN documents_version v ON v.id=b.version_id
  JOIN documents_document d ON d.id=v.document_id AND d.current_id=v.id AND d.case_id=w.case_id
  WHERE w.id=wid AND w.definition='pmo-minutes/v1' AND w.source_head_id=head
   AND mv.evidence_id=(e.body::jsonb->>'evidence_id')::bigint
   AND (e.body::jsonb->'meeting_version_id'='null'::jsonb AND mv.number=1 OR EXISTS(
    SELECT 1 FROM pmo_meetingversion predecessor WHERE predecessor.id=(e.body::jsonb->>'meeting_version_id')::bigint
     AND predecessor.meeting_id=m.id AND predecessor.number+1=mv.number))
   AND mv.purpose=c.data->'fields'->>'purpose' AND mv.summary=c.data->'fields'->>'summary'
   AND mv.decisions=c.data->'fields'->'decisions' AND mv.participant_ids=c.data->'fields'->'participant_ids'
   AND v.template_id=(e.body::jsonb->>'template_id')::bigint AND v.audience=e.body::jsonb->>'audience'
   AND psl_schedules_grants(w.case_id,c.actor_id,ARRAY['case.read','meeting.read','meeting.record'])
   AND EXISTS(SELECT 1 FROM core_audit intake WHERE intake.case_id=w.case_id AND intake.actor_id=e.created_by_id
    AND intake.data=jsonb_build_object('evidence_id',e.id,'sha256',e.sha256)
    AND (intake.action='factory.minutes_intake' AND psl_schedules_grants(w.case_id,e.created_by_id,ARRAY['case.read','meeting.read','factory.start'])
      OR intake.action='factory.minutes_source' AND psl_schedules_grants(w.case_id,e.created_by_id,ARRAY['case.read','meeting.read','factory.manage'])))
   AND b.manifest=jsonb_build_object('meeting_version',m.current_id,'actions',COALESCE((SELECT jsonb_agg(jsonb_build_array(ai.id,ai.current_id) ORDER BY ai.id) FROM pmo_meetingactionlink link JOIN pmo_actionitem ai ON ai.id=link.item_id WHERE link.meeting_id=m.id),'[]'::jsonb))
   AND EXISTS(SELECT 1 FROM workflows_factoryactivity fa JOIN workflows_factoryattempt a ON a.activity_id=fa.id
    WHERE fa.work_id=w.id AND fa.kind='ACT09' AND a.phase='observed' AND a.result->>'head'=e.id::text AND a.result->>'document_version'=v.id::text)
 );
$$;

CREATE OR REPLACE FUNCTION psl_escalation_json(body text) RETURNS jsonb LANGUAGE plpgsql IMMUTABLE AS $$
BEGIN RETURN body::jsonb; EXCEPTION WHEN invalid_text_representation THEN RETURN NULL; END $$;
CREATE OR REPLACE FUNCTION psl_escalation_intake(eid bigint) RETURNS jsonb LANGUAGE plpgsql STABLE AS $$
DECLARE body jsonb; raw_body text; source_kind text; key text;
BEGIN
 SELECT e.kind,e.body INTO source_kind,raw_body FROM core_evidence e WHERE e.id=eid;
 IF source_kind IS DISTINCT FROM 'agent_private_escalation_intake' THEN RETURN NULL; END IF;
 body:=psl_escalation_json(raw_body);
 IF jsonb_typeof(body) IS DISTINCT FROM 'object' THEN RETURN NULL; END IF;
 IF body->>'protocol' IS DISTINCT FROM 'factory-escalation-intake/v1' OR (body-ARRAY['protocol','request_id','profile_id','template_id'])<>'{}'::jsonb OR NOT body ?& ARRAY['protocol','request_id','profile_id','template_id'] THEN RETURN NULL; END IF;
 FOREACH key IN ARRAY ARRAY['request_id','profile_id','template_id'] LOOP
  IF key='template_id' AND body->key='null'::jsonb THEN CONTINUE; END IF;
  IF jsonb_typeof(body->key) IS DISTINCT FROM 'number' OR (body->>key)!~'^[1-9][0-9]{0,18}$' THEN RETURN NULL; END IF;
  IF (body->>key)::numeric>9223372036854775807 THEN RETURN NULL; END IF;
 END LOOP;
 RETURN body;
END $$;
CREATE OR REPLACE FUNCTION psl_escalation_bundle(c uuid,p bigint,u bigint) RETURNS boolean LANGUAGE sql STABLE AS $$
 WITH roles AS (SELECT rr.content v FROM policy_configuration cfg JOIN policy_registeredreference rr
 ON rr.case_id=cfg.case_id AND (cfg.envelope->'value') ? rr.ref AND rr.version=1
 WHERE cfg.id=p AND cfg.case_id=c AND rr.content->>'user_id'=u::text)
 SELECT CASE WHEN (SELECT count(*) FROM roles)<=1 THEN true
 WHEN NOT EXISTS(SELECT 1 FROM roles WHERE NOT v ? 'eligibility') THEN
 NOT EXISTS(SELECT 1 FROM roles WHERE (v->'eligibility'->>'valid_from')::timestamptz>statement_timestamp() OR (v->'eligibility'->>'valid_until')::timestamptz<=statement_timestamp())
 ELSE (SELECT synthetic FROM core_case WHERE id=c) END;
$$;

CREATE OR REPLACE FUNCTION psl_escalation_grants(c uuid,u bigint,actions text[]) RETURNS boolean LANGUAGE sql STABLE AS $$
 SELECT EXISTS(SELECT 1 FROM auth_user WHERE id=u AND is_active) AND NOT EXISTS(
 SELECT 1 FROM unnest(actions) a WHERE NOT EXISTS(SELECT 1 FROM identity_grant g WHERE g.case_id=c AND g.user_id=u AND g.action=a AND g.active));
$$;
CREATE OR REPLACE FUNCTION psl_escalation_policy(c uuid,p bigint,component_arg text) RETURNS boolean LANGUAGE sql STABLE AS $$
 SELECT EXISTS(SELECT 1 FROM policy_configuration cfg WHERE cfg.id=p AND cfg.case_id=c AND cfg.component=component_arg
 AND (SELECT state FROM policy_policystate WHERE configuration_id=cfg.id ORDER BY id DESC LIMIT 1)='active'
 AND (cfg.envelope->>'effective_from')::timestamptz<=statement_timestamp()
 AND (cfg.envelope->>'effective_until' IS NULL OR (cfg.envelope->>'effective_until')::timestamptz>statement_timestamp()));
$$;
CREATE OR REPLACE FUNCTION psl_escalation_authority(c uuid,u bigint,role_name text,delegated boolean,pins jsonb) RETURNS boolean LANGUAGE sql STABLE AS $$
 SELECT psl_escalation_grants(c,u,ARRAY[]::text[]) AND EXISTS(
 SELECT 1 FROM policy_configuration pc WHERE pc.id=(pins->>'D05.role_principal_assignments')::bigint
 AND psl_escalation_policy(c,pc.id,'D05.role_principal_assignments')
 AND pins=jsonb_build_object('D05.role_principal_assignments',pc.id) || CASE WHEN delegated THEN jsonb_build_object('D05.delegation_rules',(pins->>'D05.delegation_rules')::bigint) ELSE '{}'::jsonb END AND (
 (NOT delegated AND psl_escalation_bundle(c,pc.id,u) AND EXISTS(SELECT 1 FROM policy_registeredreference rr WHERE rr.case_id=c AND (pc.envelope->'value') ? rr.ref AND rr.version=1
  AND rr.content->>'role'=role_name AND rr.content->>'user_id'=u::text))
 OR (delegated AND EXISTS(SELECT 1 FROM policy_configuration dc JOIN policy_registeredreference dr ON dr.case_id=c AND (dc.envelope->'value') ? dr.ref AND dr.version=1
  JOIN policy_registeredreference rr ON rr.case_id=c AND (pc.envelope->'value') ? rr.ref AND rr.version=1
  WHERE dc.id=(pins->>'D05.delegation_rules')::bigint AND psl_escalation_policy(c,dc.id,'D05.delegation_rules')
  AND dr.content->>'role'=role_name AND dr.content->>'delegate_id'=u::text AND NOT dr.content ? 'decision_scope'
  AND rr.content->>'role'=role_name AND rr.content->>'user_id'=dr.content->>'principal_id'
  AND psl_escalation_grants(c,(dr.content->>'principal_id')::bigint,ARRAY[]::text[])
  AND psl_escalation_bundle(c,pc.id,(dr.content->>'principal_id')::bigint) AND psl_escalation_bundle(c,pc.id,u)
  AND (CASE WHEN dr.content ? 'delegate_eligibility' THEN
    (dr.content->'delegate_eligibility'->>'valid_from')::timestamptz<=statement_timestamp() AND (dr.content->'delegate_eligibility'->>'valid_until')::timestamptz>statement_timestamp()
    AND (SELECT array_agg(x ORDER BY x) FROM jsonb_array_elements_text(dr.content->'delegate_eligibility'->'roles') x)=
     (SELECT array_agg(x ORDER BY x) FROM (SELECT role_name x UNION SELECT ar.content->>'role' FROM policy_registeredreference ar WHERE ar.case_id=c AND ar.version=1 AND (pc.envelope->'value') ? ar.ref AND ar.content->>'user_id'=u::text) bundle)
   ELSE (SELECT synthetic FROM core_case WHERE id=c) OR NOT EXISTS(SELECT 1 FROM policy_registeredreference ar WHERE ar.case_id=c AND ar.version=1 AND (pc.envelope->'value') ? ar.ref AND ar.content->>'user_id'=u::text AND ar.content->>'role'<>role_name) END)
  AND (dr.content->>'valid_from')::timestamptz<=statement_timestamp() AND (dr.content->>'valid_until')::timestamptz>statement_timestamp()))));
$$;
CREATE OR REPLACE FUNCTION psl_escalation_document(wid bigint,vid bigint,rid bigint,publisher_id_arg bigint,policy_id_arg bigint,source_id_arg bigint,recipient_ids_arg jsonb,pins jsonb) RETURNS boolean LANGUAGE sql STABLE AS $$
 SELECT EXISTS(
 SELECT 1 FROM workflows_factorywork w JOIN core_evidence e ON e.id=source_id_arg
 JOIN pmo_escalationrequest r ON r.id=(psl_escalation_intake(e.id)->>'request_id')::bigint
 JOIN pmo_escalationprofile ep ON ep.id=r.profile_id JOIN pmo_issuestate ist ON ist.id=ep.state_id JOIN pmo_issue i ON i.id=ist.issue_id
 JOIN pmo_escalationdocumentbinding b ON b.request_id=r.id AND b.version_id=vid
 JOIN documents_version v ON v.id=b.version_id JOIN documents_document doc ON doc.id=v.document_id JOIN documents_template t ON t.id=v.template_id
 JOIN policy_configuration pc ON pc.id=policy_id_arg JOIN policy_registeredreference cfg ON cfg.case_id=pc.case_id
  AND cfg.ref=pc.envelope->'value'->>'artifact_ref' AND cfg.version=(pc.envelope->'value'->>'artifact_version')::integer AND cfg.sha256=pc.envelope->'value'->>'sha256'
 JOIN policy_configuration rc ON rc.id=(pins->>'D11.recipient_grant_refs')::bigint
 JOIN policy_configuration sc ON sc.id=(pins->>'D11.template_storage_retention_rules')::bigint
 JOIN policy_registeredreference store ON store.case_id=sc.case_id AND store.ref=sc.envelope->'value'->>'artifact_ref'
  AND store.version=(sc.envelope->'value'->>'artifact_version')::integer AND store.sha256=sc.envelope->'value'->>'sha256'
 WHERE w.id=wid AND w.definition='pmo-escalation/v1' AND w.policy_id=policy_id_arg AND w.source_head_id=e.id
 AND e.case_id=w.case_id AND i.case_id=w.case_id AND doc.case_id=w.case_id AND t.case_id=w.case_id
 AND i.id=(w.request->>'issue')::bigint AND i.current_id=ist.id AND ep.id=(psl_escalation_intake(e.id)->>'profile_id')::bigint
 AND ep.id=(SELECT max(p.id) FROM pmo_escalationprofile p JOIN pmo_issuestate s ON s.id=p.state_id WHERE s.issue_id=i.id)
 AND r.direction=w.request->>'direction' AND r.target=w.request->>'target'
 AND v.template_id=(psl_escalation_intake(e.id)->>'template_id')::bigint AND doc.current_id=v.id
 AND v.audience=CASE WHEN r.target='Client' THEN 'client' ELSE 'internal' END
 AND psl_escalation_policy(w.case_id,policy_id_arg,'OPS.factory_escalation_execution') AND cfg.content->'enabled'='true'::jsonb
 AND cfg.content->>'definition'=w.definition AND cfg.content->>'executor_id'=publisher_id_arg::text
 AND psl_escalation_grants(w.case_id,publisher_id_arg,ARRAY['case.read','issue.read','factory.execute','document.publish'])
 AND psl_escalation_grants(w.case_id,(cfg.content->>'preparer_id')::bigint,ARRAY['case.read','issue.read','factory.execute','issue.escalate','document.draft'])
 AND psl_escalation_grants(w.case_id,e.created_by_id,ARRAY['case.read','issue.read','evidence.add'])
 AND EXISTS(SELECT 1 FROM core_audit ia WHERE ia.case_id=w.case_id AND ia.actor_id=e.created_by_id AND ia.data=jsonb_build_object('evidence_id',e.id,'sha256',e.sha256)
  AND ((ia.action='factory.escalation_intake' AND psl_escalation_grants(w.case_id,e.created_by_id,ARRAY['factory.start'])) OR (ia.action='factory.escalation_source' AND psl_escalation_grants(w.case_id,e.created_by_id,ARRAY['factory.manage']))))
 AND ((r.target<>'Client' AND b.decision_id IS NULL) OR EXISTS(SELECT 1 FROM pmo_escalationdecision d WHERE d.id=b.decision_id AND d.request_id=r.id
  AND d.id=(SELECT max(id) FROM pmo_escalationdecision WHERE request_id=r.id) AND d.verdict='approve' AND d.role IN ('PMO Lead','Head of PMO')
  AND psl_escalation_grants(w.case_id,d.actor_id,ARRAY['issue.escalation_decide']) AND psl_escalation_authority(w.case_id,d.actor_id,d.role,d.delegated,d.authority)))
 AND ((rid IS NULL AND v.audience<>'client' AND t.definition->'internal_review_required'='false'::jsonb AND NOT EXISTS(SELECT 1 FROM documents_controlledreview WHERE version_id=v.id))
 OR EXISTS(SELECT 1 FROM documents_controlledreview rv WHERE rv.id=rid AND rv.version_id=v.id AND rv.id=(SELECT max(id) FROM documents_controlledreview WHERE version_id=v.id)
  AND rv.verdict='approve' AND rv.payload_sha256=v.payload_sha256 AND psl_escalation_grants(w.case_id,rv.actor_id,ARRAY['document.review_controlled'])
  AND psl_escalation_authority(w.case_id,rv.actor_id,'PMO Lead',rv.delegated,rv.authority)))
 AND psl_escalation_policy(w.case_id,rc.id,'D11.recipient_grant_refs') AND psl_escalation_policy(w.case_id,sc.id,'D11.template_storage_retention_rules')
 AND store.content->'template_ids' @> jsonb_build_array(t.id) AND jsonb_array_length(recipient_ids_arg)>0
 AND recipient_ids_arg=(SELECT jsonb_agg(u ORDER BY u) FROM (SELECT DISTINCT (rr.content->>'user_id')::bigint u FROM policy_registeredreference rr
  WHERE rr.case_id=w.case_id AND (rc.envelope->'value') ? rr.ref AND rr.version=1 AND rr.content->>'audience'=v.audience) selected)
 AND NOT EXISTS(SELECT 1 FROM jsonb_array_elements_text(recipient_ids_arg) recipient WHERE NOT psl_escalation_grants(w.case_id,recipient::bigint,ARRAY['document.receive:'||v.audience]))
 AND (r.target='Client' OR EXISTS(SELECT 1 FROM policy_configuration ap JOIN policy_registeredreference ar ON ar.case_id=ap.case_id AND (ap.envelope->'value') ? ar.ref AND ar.version=1
  WHERE ap.id=(pins->>'D05.role_principal_assignments')::bigint AND psl_escalation_policy(w.case_id,ap.id,'D05.role_principal_assignments')
  AND ar.content->>'role'=r.target AND recipient_ids_arg @> jsonb_build_array((ar.content->>'user_id')::bigint)))
 AND EXISTS(SELECT 1 FROM workflows_factoryactivity fa JOIN workflows_factoryattempt a ON a.activity_id=fa.id
  WHERE fa.work_id=w.id AND fa.kind='ACT09' AND a.phase='observed' AND a.result->>'head'=e.id::text AND a.result->>'document_version'=v.id::text AND a.result->>'request'=r.id::text));
$$;

CREATE OR REPLACE FUNCTION psl_reporting_grants(cid uuid, uid bigint, actions text[]) RETURNS boolean LANGUAGE sql STABLE AS $$
 SELECT EXISTS(SELECT 1 FROM auth_user WHERE id=uid AND is_active)
 AND NOT EXISTS(SELECT 1 FROM unnest(actions) required(action) WHERE NOT EXISTS(
  SELECT 1 FROM identity_grant g WHERE g.case_id=cid AND g.user_id=uid AND g.action=required.action AND g.active));
$$;
CREATE OR REPLACE FUNCTION psl_reporting_policy(cid uuid,pid bigint) RETURNS boolean LANGUAGE sql STABLE AS $$
 SELECT EXISTS(SELECT 1 FROM policy_configuration p WHERE p.id=pid AND p.case_id=cid
 AND (SELECT state FROM policy_policystate WHERE configuration_id=p.id ORDER BY id DESC LIMIT 1)='active'
 AND NOT EXISTS(SELECT 1 FROM policy_configuration n WHERE n.case_id=cid AND n.component=p.component AND n.revision>p.revision
  AND (SELECT state FROM policy_policystate WHERE configuration_id=n.id ORDER BY id DESC LIMIT 1) IN ('active','revoked','superseded'))
 AND (p.envelope->>'effective_from')::timestamptz<=statement_timestamp()
 AND (p.envelope->>'effective_until' IS NULL OR (p.envelope->>'effective_until')::timestamptz>statement_timestamp())
 AND NOT EXISTS(SELECT 1 FROM policy_scopeapplication app JOIN policy_scopeversion src ON src.id=app.source_id
  JOIN policy_configuration origin ON origin.id=src.configuration_id WHERE app.configuration_id=p.id
  AND ((SELECT state FROM policy_scopestate WHERE source_id=src.id ORDER BY id DESC LIMIT 1) IS DISTINCT FROM 'active'
   OR (SELECT state FROM policy_policystate WHERE configuration_id=origin.id ORDER BY id DESC LIMIT 1) IS DISTINCT FROM 'validated'
   OR (origin.envelope->>'effective_from')::timestamptz>statement_timestamp()
   OR (origin.envelope->>'effective_until' IS NOT NULL AND (origin.envelope->>'effective_until')::timestamptz<=statement_timestamp())
   OR NOT psl_reporting_grants(origin.case_id,(SELECT actor_id FROM policy_scopestate WHERE source_id=src.id AND state='active' ORDER BY id DESC LIMIT 1),ARRAY['case.read','policy.activate'])
   OR EXISTS(SELECT 1 FROM policy_scopeversion n JOIN policy_configuration nc ON nc.id=n.configuration_id
    WHERE nc.case_id=origin.case_id AND nc.component=origin.component AND n.kind=src.kind AND n.ref=src.ref AND n.revision>src.revision
     AND EXISTS(SELECT 1 FROM policy_scopestate ns WHERE ns.source_id=n.id AND ns.state IN ('active','revoked'))))));
$$;
CREATE OR REPLACE FUNCTION psl_reporting_refs(pid bigint) RETURNS SETOF jsonb LANGUAGE sql STABLE AS $$
 SELECT r.content FROM policy_configuration p JOIN policy_registeredreference r ON r.case_id=p.case_id
 WHERE p.id=pid AND CASE jsonb_typeof(p.envelope->'value')
  WHEN 'object' THEN r.ref=p.envelope->'value'->>'artifact_ref' AND r.version=(p.envelope->'value'->>'artifact_version')::integer AND r.sha256=p.envelope->'value'->>'sha256'
  WHEN 'array' THEN p.envelope->'value'?r.ref AND r.version=1
  WHEN 'string' THEN to_jsonb(r.ref)=p.envelope->'value' AND r.version=1 ELSE false END;
$$;
CREATE OR REPLACE FUNCTION psl_reporting_role(cid uuid,uid bigint,pid bigint,role_name text) RETURNS boolean LANGUAGE sql STABLE AS $$
 WITH records AS (SELECT value FROM psl_reporting_refs(pid) value WHERE value->>'user_id'=uid::text),
 roles AS (SELECT COALESCE(jsonb_agg(DISTINCT value->>'role'),'[]'::jsonb) names FROM records)
 SELECT psl_reporting_policy(cid,pid) AND EXISTS(SELECT 1 FROM auth_user WHERE id=uid AND is_active)
 AND EXISTS(SELECT 1 FROM records WHERE value->>'role'=role_name)
 AND ((SELECT jsonb_array_length(names) FROM roles)=1 OR (EXISTS(SELECT 1 FROM core_case WHERE id=cid AND synthetic) AND EXISTS(SELECT 1 FROM records WHERE NOT(value?'eligibility')))
 OR NOT EXISTS(SELECT 1 FROM records,roles WHERE NOT(value?'eligibility')
  OR (value->'eligibility'->'roles') IS NULL OR NOT(value->'eligibility'->'roles' @> roles.names AND value->'eligibility'->'roles' <@ roles.names)
  OR NOT((value->'eligibility'->>'valid_from')::timestamptz<=statement_timestamp() AND (value->'eligibility'->>'valid_until')::timestamptz>statement_timestamp())));
$$;
CREATE OR REPLACE FUNCTION psl_reporting_review(cid uuid,rid bigint) RETURNS boolean LANGUAGE sql STABLE AS $$
 SELECT EXISTS(SELECT 1 FROM documents_controlledreview rv JOIN documents_version v ON v.id=rv.version_id
 JOIN documents_document d ON d.id=v.document_id
 JOIN policy_configuration assignment ON assignment.id=(rv.authority->>'D05.role_principal_assignments')::bigint
 WHERE rv.id=rid AND d.case_id=cid AND d.current_id=v.id AND rv.verdict='approve'
 AND rv.payload_sha256=v.payload_sha256
 AND rv.id=(SELECT max(id) FROM documents_controlledreview WHERE version_id=v.id)
 AND assignment.component='D05.role_principal_assignments' AND psl_reporting_policy(cid,assignment.id)
 AND psl_reporting_grants(cid,rv.actor_id,ARRAY['document.review_controlled'])
 AND ((NOT rv.delegated AND rv.authority=jsonb_build_object('D05.role_principal_assignments',assignment.id)
  AND psl_reporting_role(cid,rv.actor_id,assignment.id,'PMO Lead'))
 OR (rv.delegated AND EXISTS(SELECT 1 FROM policy_configuration delegation, LATERAL psl_reporting_refs(delegation.id) entry
  WHERE delegation.id=(rv.authority->>'D05.delegation_rules')::bigint AND delegation.component='D05.delegation_rules'
   AND psl_reporting_policy(cid,delegation.id)
   AND rv.authority=jsonb_build_object('D05.role_principal_assignments',assignment.id,'D05.delegation_rules',delegation.id)
   AND entry->>'role'='PMO Lead' AND entry->>'delegate_id'=rv.actor_id::text AND NOT(entry?'decision_scope')
   AND (entry->>'valid_from')::timestamptz<=statement_timestamp() AND (entry->>'valid_until')::timestamptz>statement_timestamp()
   AND psl_reporting_role(cid,(entry->>'principal_id')::bigint,assignment.id,'PMO Lead')
   AND (NOT EXISTS(SELECT 1 FROM psl_reporting_refs(assignment.id) own WHERE own->>'user_id'=rv.actor_id::text)
    OR EXISTS(SELECT 1 FROM psl_reporting_refs(assignment.id) own WHERE own->>'user_id'=rv.actor_id::text AND psl_reporting_role(cid,rv.actor_id,assignment.id,own->>'role')))
   AND (CASE WHEN entry?'delegate_eligibility' THEN
     (entry->'delegate_eligibility'->>'valid_from')::timestamptz<=statement_timestamp()
     AND (entry->'delegate_eligibility'->>'valid_until')::timestamptz>statement_timestamp()
     AND (SELECT COALESCE(jsonb_agg(DISTINCT role_name),'[]'::jsonb) FROM
       (SELECT 'PMO Lead' role_name UNION SELECT own->>'role' FROM psl_reporting_refs(assignment.id) own WHERE own->>'user_id'=rv.actor_id::text) roles)
       @> (entry->'delegate_eligibility'->'roles')
     AND entry->'delegate_eligibility'->'roles' @> (SELECT COALESCE(jsonb_agg(DISTINCT role_name),'[]'::jsonb) FROM
       (SELECT 'PMO Lead' role_name UNION SELECT own->>'role' FROM psl_reporting_refs(assignment.id) own WHERE own->>'user_id'=rv.actor_id::text) roles)
    ELSE EXISTS(SELECT 1 FROM core_case WHERE id=cid AND synthetic)
     OR NOT EXISTS(SELECT 1 FROM psl_reporting_refs(assignment.id) own WHERE own->>'user_id'=rv.actor_id::text AND own->>'role'<>'PMO Lead') END)))));
$$;
CREATE OR REPLACE FUNCTION psl_reporting_principals(wid bigint,vid bigint,publisher bigint) RETURNS boolean LANGUAGE sql STABLE AS $$
 SELECT EXISTS(SELECT 1 FROM workflows_factorywork w JOIN documents_version v ON v.id=vid
 JOIN policy_configuration p ON p.id=w.policy_id, LATERAL psl_reporting_refs(p.id) cfg
 WHERE w.id=wid AND p.component='OPS.factory_reporting_execution' AND psl_reporting_policy(w.case_id,p.id)
 AND cfg->>'executor_id'=publisher::text AND cfg->>'preparer_id'=v.created_by_id::text
 AND psl_reporting_grants(w.case_id,publisher,ARRAY['case.read','report.read','factory.execute','document.publish'])
 AND psl_reporting_grants(w.case_id,v.created_by_id,ARRAY['case.read','report.read','factory.execute','report.draft','document.draft','document.request_review']));
$$;
CREATE OR REPLACE FUNCTION psl_reporting_distribution(cid uuid,vid bigint,policies jsonb,recipients jsonb,retention integer) RETURNS boolean LANGUAGE sql STABLE AS $$
 SELECT jsonb_array_length(recipients)>0
 AND policies ?& ARRAY['D11.template_storage_retention_rules','D11.recipient_grant_refs']
 AND policies-ARRAY['D11.template_storage_retention_rules','D11.recipient_grant_refs']='{}'::jsonb
 AND NOT EXISTS(SELECT 1 FROM jsonb_each_text(policies) pin WHERE NOT EXISTS(
  SELECT 1 FROM policy_configuration p WHERE p.id=pin.value::bigint AND p.component=pin.key AND psl_reporting_policy(cid,p.id)))
 AND recipients=COALESCE((SELECT jsonb_agg(DISTINCT (r->>'user_id')::bigint ORDER BY (r->>'user_id')::bigint)
 FROM psl_reporting_refs((policies->>'D11.recipient_grant_refs')::bigint) r WHERE r->>'audience'='client'),'[]'::jsonb)
 AND NOT EXISTS(SELECT 1 FROM jsonb_array_elements_text(recipients) r WHERE NOT psl_reporting_grants(cid,r::bigint,ARRAY['document.receive:client']))
 AND EXISTS(SELECT 1 FROM psl_reporting_refs((policies->>'D11.template_storage_retention_rules')::bigint) storage
  JOIN documents_version v ON v.id=vid WHERE storage->>'retention_days'=retention::text AND storage->'template_ids' @> jsonb_build_array(v.template_id));
$$;
CREATE OR REPLACE FUNCTION psl_reporting_heads(cid uuid,m jsonb,s timestamptz,t timestamptz) RETURNS boolean LANGUAGE sql STABLE AS $$
 SELECT m->>'source_mode'='weekly_client_facts/v1'
 AND m-ARRAY['source_mode','meetings','actions','milestones','issues','changes','client_content']='{}'::jsonb
 AND m->'meetings'=COALESCE((SELECT jsonb_agg(jsonb_build_array(x.id,x.current_id) ORDER BY x.id) FROM pmo_meeting x JOIN pmo_meetingversion v ON v.id=x.current_id WHERE x.case_id=cid AND v.occurred_at>=s AND v.occurred_at<t),'[]'::jsonb)
 AND m->'actions'=COALESCE((SELECT jsonb_agg(jsonb_build_array(id,current_id) ORDER BY id) FROM pmo_actionitem WHERE case_id=cid),'[]'::jsonb)
 AND m->'milestones'=COALESCE((SELECT jsonb_agg(id ORDER BY id) FROM pmo_milestone WHERE case_id=cid AND completed_at>=s AND completed_at<t),'[]'::jsonb)
 AND m->'issues'=COALESCE((SELECT jsonb_agg(jsonb_build_array(id,current_id) ORDER BY id) FROM pmo_issue WHERE case_id=cid),'[]'::jsonb)
 AND m->'changes'=COALESCE((SELECT jsonb_agg(jsonb_build_array(id,current_id) ORDER BY id) FROM pmo_changerequest WHERE case_id=cid),'[]'::jsonb);
$$;
CREATE OR REPLACE FUNCTION psl_reporting_document(wid bigint,eid bigint,vid bigint) RETURNS boolean LANGUAGE sql STABLE AS $$
 SELECT EXISTS(SELECT 1 FROM workflows_factorywork w JOIN core_evidence e ON e.id=eid AND e.case_id=w.case_id
 JOIN documents_version v ON v.id=vid JOIN documents_template template ON template.id=v.template_id JOIN documents_document d ON d.id=v.document_id AND d.case_id=w.case_id AND d.current_id=v.id
 JOIN pmo_minutesreportbinding b ON b.version_id=v.id JOIN pmo_periodreport r ON r.id=b.report_id AND r.case_id=w.case_id
 JOIN core_evidence projection ON projection.id=(v.source_manifest->0->>'id')::bigint AND projection.case_id=w.case_id
 JOIN core_evidence content ON content.id=(e.body::jsonb->'inputs'->>'content_id')::bigint AND content.case_id=w.case_id AND content.kind='agent_private_report_content'
 WHERE w.id=wid AND w.definition='pmo-weekly-report/v1' AND e.kind='agent_private_reporting_intake'
 AND psl_reporting_grants(w.case_id,e.created_by_id,ARRAY['case.read','report.read','evidence.add'])
 AND EXISTS(SELECT 1 FROM core_audit provenance WHERE provenance.case_id=w.case_id AND provenance.actor_id=e.created_by_id
  AND provenance.data=jsonb_build_object('evidence_id',e.id,'sha256',e.sha256)
  AND ((provenance.action='factory.reporting_intake' AND psl_reporting_grants(w.case_id,e.created_by_id,ARRAY['factory.start']))
   OR (provenance.action='factory.reporting_source' AND psl_reporting_grants(w.case_id,e.created_by_id,ARRAY['factory.manage']))))
 AND v.baseline_manifest=COALESCE((SELECT jsonb_build_object('plan_id',plan_id,'costing_id',costing_id,'sow_id',sow_id,'signed_id',signed_id) FROM pmo_baseline WHERE case_id=w.case_id),'{}'::jsonb)
 AND e.id=w.source_head_id AND v.audience='client' AND r.kind='weekly_client' AND r.audience='client' AND r.document_id=d.id
 AND r.start_at=(w.request->>'start_at')::timestamptz AND r.end_at=(w.request->>'end_at')::timestamptz
 AND v.template_id=(e.body::jsonb->'inputs'->>'template_id')::bigint AND b.manifest=e.body::jsonb->'manifest'
 AND psl_reporting_heads(w.case_id,b.manifest,r.start_at,r.end_at)
 AND b.manifest->'client_content'=jsonb_build_object('id',content.id,'sha256',content.sha256)
 AND v.source_manifest=jsonb_build_array(jsonb_build_object('id',projection.id,'version',projection.version,'sha256',projection.sha256))
 AND jsonb_array_length(v.source_manifest)=1 AND projection.kind='ops_client_report_projection'
 AND projection.source='psl:weekly-client-projection:'||r.id::text AND projection.created_by_id=v.created_by_id
 AND NOT EXISTS(SELECT 1 FROM jsonb_each(v.fields) field WHERE field.value->'evidence_ids' IS DISTINCT FROM jsonb_build_array(projection.id))
 AND template.definition->>'document_type'='status_report'
 AND template.definition->'required_fields' @> '["executive_summary","status","risks","timeline","next_steps"]'::jsonb
 AND template.definition->'audience_fields'->'client' @> '["executive_summary","status","risks","timeline","next_steps"]'::jsonb
 AND jsonb_array_length(template.definition->'audience_fields'->'client')=5
 AND v.payload->>'type'='status_report' AND jsonb_array_length(v.payload->'sections')=5
 AND (SELECT jsonb_agg(section->>'heading' ORDER BY section->>'heading') FROM jsonb_array_elements(v.payload->'sections') section)='["executive_summary","next_steps","risks","status","timeline"]'::jsonb
 AND content.body::jsonb->>'protocol'='pmo-weekly-client-content/v1'
 AND (content.body::jsonb->'sections')-ARRAY['status','risks','timeline','next_steps']='{}'::jsonb
 AND NOT EXISTS(SELECT 1 FROM unnest(ARRAY['status','risks','timeline','next_steps']) theme(k)
  WHERE NOT(content.body::jsonb->'sections'?theme.k) OR length(trim(content.body::jsonb->'sections'->theme.k->>'text')) NOT BETWEEN 1 AND 10000
   OR jsonb_array_length(content.body::jsonb->'sections'->theme.k->'evidence_ids') NOT BETWEEN 1 AND 18
   OR EXISTS(SELECT 1 FROM jsonb_array_elements_text(content.body::jsonb->'sections'->theme.k->'evidence_ids') citation
    WHERE NOT EXISTS(SELECT 1 FROM core_evidence ce WHERE ce.id=citation::bigint AND ce.case_id=w.case_id
     AND ce.kind NOT IN ('ledger_source','quickbooks_verification','ledger_resolution','ledger_resolution_review','approval_source','approval_observation','migration_proof','d03_source','planning_packet','planning_prd_alignment','planning_scope_alignment','planning_contract_comparison','planning_readiness','finance_group_snapshot')
     AND ce.kind NOT LIKE 'forecast_%' AND ce.kind NOT LIKE 'd03_control_%' AND ce.kind NOT LIKE 'p14_%'
     AND NOT(ce.kind='finance_report_snapshot' AND ce.source LIKE 'derived:forecast:%')
     AND NOT EXISTS(SELECT 1 FROM finance_forecastscenario fs WHERE fs.case_id=w.case_id AND (fs.evidence_id=ce.id OR fs.payload->'items' @> jsonb_build_array(jsonb_build_object('evidence_id',ce.id)) OR fs.payload->'openings' @> jsonb_build_array(jsonb_build_object('evidence_id',ce.id))))
     AND (ce.source<>'psl:p56-confirmed-request/v1' OR EXISTS(SELECT 1 FROM pmo_changerequest cr JOIN pmo_changeversion cv ON cv.id=cr.current_id WHERE cr.case_id=w.case_id AND cv.evidence_id=ce.id))
     AND ce.kind NOT LIKE 'agent_private_%' AND ce.kind NOT LIKE 'ops_%' AND ce.kind NOT LIKE 'integration_%'
     AND (EXISTS(SELECT 1 FROM pmo_meeting m JOIN pmo_meetingversion mv ON mv.id=m.current_id WHERE m.case_id=w.case_id AND mv.evidence_id=ce.id AND mv.occurred_at>=r.start_at AND mv.occurred_at<r.end_at)
      OR EXISTS(SELECT 1 FROM pmo_actionitem ai JOIN pmo_actionstate state ON state.id=ai.current_id WHERE ai.case_id=w.case_id AND state.evidence_id=ce.id)
      OR EXISTS(SELECT 1 FROM pmo_milestone m WHERE m.case_id=w.case_id AND m.evidence_id=ce.id AND m.completed_at>=r.start_at AND m.completed_at<r.end_at)
      OR EXISTS(SELECT 1 FROM pmo_issue i JOIN pmo_issuestate state ON state.id=i.current_id WHERE i.case_id=w.case_id AND state.evidence_id=ce.id)
      OR EXISTS(SELECT 1 FROM pmo_changerequest cr JOIN pmo_changeversion cv ON cv.id=cr.current_id WHERE cr.case_id=w.case_id AND cv.evidence_id=ce.id))))
   OR NOT EXISTS(SELECT 1 FROM jsonb_array_elements(v.payload->'sections') section WHERE section->>'heading'=theme.k AND section->>'text'=content.body::jsonb->'sections'->theme.k->>'text')
   OR v.fields->theme.k->>'text' IS DISTINCT FROM content.body::jsonb->'sections'->theme.k->>'text')
 AND EXISTS(SELECT 1 FROM workflows_factoryactivity fa JOIN workflows_factoryattempt a ON a.activity_id=fa.id
  WHERE fa.work_id=w.id AND fa.kind='ACT09' AND a.phase='observed' AND a.result->>'document_version'=v.id::text AND a.result->>'head'=e.id::text));
$$;

CREATE OR REPLACE FUNCTION psl_schedules_grants(cid uuid, uid bigint, actions text[]) RETURNS boolean LANGUAGE sql STABLE AS $$
 SELECT EXISTS(SELECT 1 FROM auth_user WHERE id=uid AND is_active)
  AND NOT EXISTS(SELECT 1 FROM unnest(actions) required(action_name) WHERE NOT EXISTS(
   SELECT 1 FROM identity_grant g WHERE g.case_id=cid AND g.user_id=uid AND g.action=required.action_name AND g.active));
$$;
-- Structural checks are bounded mirrors, not execution of Python domain validators.
CREATE OR REPLACE FUNCTION psl_schedules_values(pid bigint) RETURNS jsonb LANGUAGE sql STABLE AS $$
 SELECT CASE WHEN c.component='D04.iana_timezone' THEN jsonb_build_array(c.envelope->'value') ELSE
 (SELECT jsonb_agg(r.content ORDER BY item.ordinality) FROM jsonb_array_elements(CASE WHEN jsonb_typeof(c.envelope->'value')='array' THEN c.envelope->'value' ELSE jsonb_build_array(c.envelope->'value') END) WITH ORDINALITY item(value,ordinality)
 JOIN policy_registeredreference r ON r.case_id=c.case_id AND r.ref=CASE WHEN jsonb_typeof(item.value)='object' THEN item.value->>'artifact_ref' ELSE item.value#>>'{}' END
 AND r.version=CASE WHEN jsonb_typeof(item.value)='object' THEN (item.value->>'artifact_version')::integer ELSE 1 END) END
 FROM policy_configuration c WHERE c.id=pid;
$$;
CREATE OR REPLACE FUNCTION psl_schedules_binding_current(pid bigint) RETURNS boolean LANGUAGE plpgsql STABLE AS $$
DECLARE ap record; bound jsonb; item jsonb; path text[];
BEGIN
 SELECT a.*,s.binding_paths,s.configuration_id AS origin_id,c.case_id AS origin_case,t.case_id AS target_case INTO ap
 FROM policy_scopeapplication a JOIN policy_scopeversion s ON s.id=a.source_id JOIN policy_configuration c ON c.id=s.configuration_id
 JOIN policy_configuration t ON t.id=a.configuration_id WHERE a.configuration_id=pid;
 IF NOT FOUND THEN RETURN true; END IF;
 bound:=psl_schedules_values(ap.origin_id);
 FOR item IN SELECT value FROM jsonb_array_elements(ap.bindings) LOOP
  IF NOT ap.binding_paths ? (item->>'path') THEN RETURN false; END IF;
  SELECT array_agg(replace(replace(part,'~1','/'),'~0','~') ORDER BY ordinality) INTO path FROM unnest(string_to_array(substr(item->>'path',2),'/')) WITH ORDINALITY p(part,ordinality);
  IF bound#>path IS NULL OR jsonb_typeof(bound#>path) IN ('object','array') THEN RETURN false; END IF;
  bound:=jsonb_set(bound,path,item->'value',false);
 END LOOP;
 IF ap.origin_case<>ap.target_case AND jsonb_array_length(ap.bindings)<>jsonb_array_length(ap.binding_paths) THEN RETURN false; END IF;
 RETURN bound IS NOT DISTINCT FROM psl_schedules_values(pid);
END;
$$;
CREATE OR REPLACE FUNCTION psl_schedules_envelope_current(pid bigint) RETURNS boolean LANGUAGE sql STABLE AS $$
 SELECT EXISTS(SELECT 1 FROM policy_configuration c JOIN core_case k ON k.id=c.case_id WHERE c.id=pid
 AND c.envelope->'subject_scope'=jsonb_build_object('kind',CASE WHEN k.kind='project' THEN 'project' ELSE 'service' END,'ref',k.id::text)
 AND (c.envelope->>'fixture_scope'='synthetic_test')=k.synthetic
 AND (c.component NOT IN ('SCHEDULES.review_authority','AF13.owner_validation_rules') OR NOT EXISTS(
 SELECT 1 FROM jsonb_array_elements(psl_schedules_values(c.id)) v CROSS JOIN LATERAL jsonb_array_elements(v->'assignments') a
 WHERE NOT EXISTS(SELECT 1 FROM auth_user WHERE id=(a->>'user_id')::bigint AND is_active)))
 AND (c.component<>'D05.role_principal_assignments' OR NOT EXISTS(
 SELECT 1 FROM jsonb_array_elements(psl_schedules_values(c.id)) v WHERE NOT EXISTS(SELECT 1 FROM auth_user WHERE id=(v->>'user_id')::bigint AND is_active))));
$$;
CREATE OR REPLACE FUNCTION psl_schedules_policy_status(cid uuid, component_name text) RETURNS text LANGUAGE plpgsql STABLE AS $$
DECLARE c record; ap record; life text; source_life text;
BEGIN
 SELECT cfg.*,(SELECT state FROM policy_policystate WHERE configuration_id=cfg.id ORDER BY id DESC LIMIT 1) AS lifecycle INTO c
 FROM policy_configuration cfg WHERE cfg.case_id=cid AND cfg.component=component_name
 AND (SELECT state FROM policy_policystate WHERE configuration_id=cfg.id ORDER BY id DESC LIMIT 1) IN ('active','revoked','superseded') ORDER BY cfg.revision DESC LIMIT 1;
 IF NOT FOUND THEN RETURN 'MISSING'; END IF;
 IF c.lifecycle='revoked' THEN RETURN 'REVOKED'; END IF;
 SELECT a.*,s.kind,s.ref,s.revision,s.configuration_id AS origin_id,o.case_id AS origin_case,o.component AS origin_component,o.envelope AS origin_envelope,
 (SELECT state FROM policy_scopestate WHERE source_id=s.id ORDER BY id DESC LIMIT 1) AS lifecycle INTO ap
 FROM policy_scopeapplication a JOIN policy_scopeversion s ON s.id=a.source_id JOIN policy_configuration o ON o.id=s.configuration_id WHERE a.configuration_id=c.id;
 IF FOUND THEN
  IF NOT psl_schedules_grants(c.case_id,ap.actor_id,ARRAY['case.read','policy.configure'])
   OR NOT psl_schedules_grants(ap.origin_case,ap.actor_id,ARRAY['case.read','policy.read'])
   OR NOT EXISTS(SELECT 1 FROM core_case t JOIN core_case o ON o.id=ap.origin_case WHERE t.id=c.case_id AND t.tenant=o.tenant AND t.synthetic=o.synthetic)
   OR c.component<>ap.origin_component OR (ap.kind<>'organization' AND c.case_id<>ap.origin_case)
   OR NOT psl_schedules_binding_current(c.id)
   OR EXISTS(SELECT 1 FROM unnest(ARRAY['effective_from','effective_until','implementation_id','implementation_version','reviewed_implementation_ref','component_schema_ref','schema_version','fixture_scope']) f WHERE c.envelope->f IS DISTINCT FROM ap.origin_envelope->f)
  THEN RETURN 'INVALID'; END IF;
  IF ap.lifecycle='revoked' THEN RETURN 'REVOKED'; END IF;
  IF ap.lifecycle<>'active' OR EXISTS(SELECT 1 FROM policy_scopeversion n JOIN policy_configuration nc ON nc.id=n.configuration_id WHERE nc.case_id=ap.origin_case AND nc.component=ap.origin_component AND n.kind=ap.kind AND n.ref=ap.ref AND n.revision>ap.revision AND EXISTS(SELECT 1 FROM policy_scopestate WHERE source_id=n.id AND state IN ('active','revoked')))
   OR NOT EXISTS(SELECT 1 FROM policy_scopestate s WHERE s.id=(SELECT max(id) FROM policy_scopestate WHERE source_id=ap.source_id AND state='active') AND psl_schedules_grants(ap.origin_case,s.actor_id,ARRAY['case.read','policy.activate']))
   OR NOT EXISTS(SELECT 1 FROM core_case k WHERE k.id=ap.origin_case AND ((ap.kind='organization' AND ap.ref=k.tenant) OR (ap.kind='project' AND k.kind='project' AND ap.ref=k.id::text) OR (ap.kind='service' AND k.kind='support' AND ap.ref=k.id::text) OR (ap.kind='contract' AND EXISTS(SELECT 1 FROM core_evidence e WHERE e.case_id=k.id AND e.kind='sow' AND ap.ref='evidence:'||e.id::text))))
   OR (SELECT state FROM policy_policystate WHERE configuration_id=ap.origin_id ORDER BY id DESC LIMIT 1)<>'validated'
   OR NOT psl_schedules_envelope_current(ap.origin_id)
  THEN RETURN 'INVALID'; END IF;
  IF (ap.origin_envelope->>'effective_from')::timestamptz>clock_timestamp() THEN RETURN 'MISSING'; END IF;
  IF (ap.origin_envelope->>'effective_until')::timestamptz<=clock_timestamp() THEN RETURN 'EXPIRED'; END IF;
 END IF;
 IF NOT psl_schedules_envelope_current(c.id) THEN RETURN 'INVALID'; END IF;
 IF (c.envelope->>'effective_from')::timestamptz>clock_timestamp() THEN RETURN 'MISSING'; END IF;
 IF (c.envelope->>'effective_until')::timestamptz<=clock_timestamp() THEN RETURN 'EXPIRED'; END IF;
 RETURN 'ACTIVE';
END;
$$;
CREATE OR REPLACE FUNCTION psl_schedules_policy_current(cid uuid, pid bigint) RETURNS boolean LANGUAGE sql STABLE AS $$
 SELECT EXISTS(SELECT 1 FROM policy_configuration c WHERE c.id=pid AND c.case_id=cid
 AND c.id=(SELECT cc.id FROM policy_configuration cc WHERE cc.case_id=cid AND cc.component=c.component AND (SELECT state FROM policy_policystate WHERE configuration_id=cc.id ORDER BY id DESC LIMIT 1) IN ('active','revoked','superseded') ORDER BY cc.revision DESC LIMIT 1)
 AND psl_schedules_policy_status(cid,c.component)='ACTIVE');
$$;
CREATE OR REPLACE FUNCTION psl_schedules_authority_current(cid uuid, authority jsonb) RETURNS boolean LANGUAGE sql STABLE AS $$
 SELECT NOT EXISTS(SELECT 1 FROM jsonb_each(authority) pin WHERE jsonb_typeof(pin.value)='number'
  AND pin.key<>'D05.decision_action_matrix' AND NOT psl_schedules_policy_current(cid,(pin.value::text)::bigint));
$$;
CREATE OR REPLACE FUNCTION psl_schedules_role_current(cid uuid, uid bigint, authority jsonb, required_role text DEFAULT 'Finance') RETURNS boolean LANGUAGE sql STABLE AS $$
 WITH assignments AS (SELECT ref.content FROM policy_configuration c
  CROSS JOIN LATERAL jsonb_array_elements_text(c.envelope->'value') selection(ref)
  JOIN policy_registeredreference ref ON ref.case_id=c.case_id AND ref.ref=selection.ref AND ref.version=1
  WHERE c.id=(authority->>'D05.role_principal_assignments')::bigint AND psl_schedules_policy_current(cid,c.id)
   AND ref.content->>'user_id'=uid::text)
 SELECT EXISTS(SELECT 1 FROM assignments WHERE content->>'role'=required_role)
  AND ((SELECT count(DISTINCT content->>'role') FROM assignments)=1
   OR ((SELECT bool_and(content ? 'eligibility') FROM assignments)
    AND (SELECT bool_and((content->'eligibility'->>'valid_from')::timestamptz<=clock_timestamp()
     AND (content->'eligibility'->>'valid_until')::timestamptz>clock_timestamp()) FROM assignments))
   OR ((SELECT synthetic FROM core_case WHERE id=cid) AND NOT (SELECT bool_and(content ? 'eligibility') FROM assignments)));
$$;
CREATE OR REPLACE FUNCTION psl_schedules_finance_review_current(rid bigint) RETURNS boolean LANGUAGE sql STABLE AS $$
 SELECT EXISTS(SELECT 1 FROM finance_financereview r WHERE r.id=rid AND r.verdict='approve'
  AND psl_schedules_grants(r.case_id,r.actor_id,ARRAY['finance.review'])
  AND psl_schedules_authority_current(r.case_id,r.authority)
  AND psl_schedules_role_current(r.case_id,r.actor_id,r.authority)
  AND EXISTS(SELECT 1 FROM policy_configuration c JOIN policy_registeredreference ref
   ON ref.case_id=c.case_id AND ref.ref=c.envelope->'value'->>'artifact_ref'
    AND ref.version=(c.envelope->'value'->>'artifact_version')::integer AND ref.sha256=c.envelope->'value'->>'sha256'
   WHERE c.case_id=r.case_id AND c.component='D05.decision_action_matrix' AND psl_schedules_policy_current(r.case_id,c.id)
    AND ref.content->'finance' @> jsonb_build_array(r.authority->'finance_review_rule'))
  AND r.id=(SELECT max(x.id) FROM finance_financereview x WHERE x.case_id=r.case_id AND x.purpose=r.purpose
   AND x.source_id IS NOT DISTINCT FROM r.source_id AND x.configuration_id IS NOT DISTINCT FROM r.configuration_id
   AND x.adjustment_id IS NOT DISTINCT FROM r.adjustment_id AND x.run_id IS NOT DISTINCT FROM r.run_id));
$$;
CREATE OR REPLACE FUNCTION psl_schedules_mapping_current(nid bigint) RETURNS boolean LANGUAGE sql STABLE AS $$
 SELECT EXISTS(SELECT 1 FROM finance_financerun n JOIN finance_financesource src ON src.id=n.source_id
  WHERE n.id=nid AND src.id=(SELECT max(id) FROM finance_financesource WHERE batch_id=src.batch_id) AND n.kind='mapping' AND n.result->>'status'='complete' AND src.completeness='complete'
   AND psl_schedules_grants(n.case_id,n.actor_id,ARRAY['case.read','finance.read','finance.calculate'])
   AND psl_schedules_finance_review_current((n.snapshot->'source_review'->>'id')::bigint)
   AND NOT EXISTS(SELECT 1 FROM jsonb_each(n.snapshot->'policies') pin
    WHERE pin.value->>'status'<>'ACTIVE' OR NOT psl_schedules_policy_current(n.case_id,(pin.value->>'id')::bigint))
   AND NOT EXISTS(SELECT 1 FROM jsonb_each(n.snapshot->'reviews') pin
    WHERE pin.value->'valid'<>'true'::jsonb OR NOT psl_schedules_finance_review_current((pin.value->>'id')::bigint))
   AND NOT EXISTS(SELECT 1 FROM jsonb_array_elements(n.snapshot->'adjustments') pin
    WHERE NOT psl_schedules_finance_review_current((pin->'review'->>'id')::bigint)
     OR EXISTS(SELECT 1 FROM finance_financeadjustment old JOIN finance_financeadjustment newer
      ON newer.source_id=old.source_id AND newer.reference=old.reference AND newer.number>old.number
      WHERE old.id=(pin->>'id')::bigint)));
$$;
CREATE OR REPLACE FUNCTION psl_schedules_policy_pin_current(cid uuid, component_name text, pin jsonb) RETURNS boolean LANGUAGE sql STABLE AS $$
 SELECT COALESCE((pin->>'status'='ACTIVE' AND psl_schedules_policy_current(cid,(pin->>'id')::bigint))
  OR (pin->'id'='null'::jsonb AND pin->>'status'<>'ACTIVE' AND pin->>'status'=psl_schedules_policy_status(cid,component_name)),false);
$$;
CREATE OR REPLACE FUNCTION psl_schedules_package_current(pid bigint) RETURNS boolean LANGUAGE sql STABLE AS $$
 SELECT EXISTS(SELECT 1 FROM documents_validationpackage p WHERE p.id=pid
  AND NOT EXISTS(SELECT 1 FROM documents_validationpackage n WHERE n.case_id=p.case_id AND n.reference=p.reference AND n.version>p.version)
  AND NOT EXISTS(SELECT 1 FROM jsonb_array_elements(p.manifest->'sources') pin WHERE NOT EXISTS(
   SELECT 1 FROM documents_discoverysource d WHERE d.id=(pin->>0)::bigint AND d.case_id=p.case_id AND d.sha256=pin->>1
    AND NOT EXISTS(SELECT 1 FROM documents_discoverysource n WHERE n.case_id=d.case_id AND n.reference=d.reference AND n.version>d.version)))
  AND NOT EXISTS(SELECT 1 FROM jsonb_array_elements(p.manifest->'examples') pin WHERE NOT EXISTS(
   SELECT 1 FROM documents_validationexample e JOIN core_evidence ce ON ce.id=e.evidence_id WHERE e.id=(pin->>0)::bigint AND e.case_id=p.case_id AND ce.sha256=pin->>2
    AND NOT EXISTS(SELECT 1 FROM documents_validationexample n WHERE n.case_id=e.case_id AND n.reference=e.reference AND n.version>e.version)))
  AND NOT EXISTS(SELECT 1 FROM jsonb_each(p.manifest->'policies') pin WHERE NOT psl_schedules_policy_pin_current(p.case_id,pin.key,pin.value)));
$$;
CREATE OR REPLACE FUNCTION psl_schedules_validation_review_current(rid bigint) RETURNS boolean LANGUAGE sql STABLE AS $$
 SELECT EXISTS(SELECT 1 FROM documents_validationreview r JOIN documents_validationpackage p ON p.id=r.package_id
 WHERE r.id=rid AND r.verdict='approve' AND psl_schedules_package_current(p.id)
  AND r.snapshot->>'package'=p.sha256
  AND r.id=(SELECT max(id) FROM documents_validationreview WHERE package_id=p.id AND kind=r.kind)
  AND psl_schedules_grants(p.case_id,r.actor_id,ARRAY[CASE WHEN r.kind='acceptance' THEN 'validation.accept' ELSE 'validation.review' END])
  AND psl_schedules_authority_current(p.case_id,r.authority)
  AND EXISTS(SELECT 1 FROM policy_configuration owner JOIN policy_registeredreference ref ON ref.case_id=owner.case_id
   AND ref.ref=owner.envelope->'value'->>'artifact_ref' AND ref.version=(owner.envelope->'value'->>'artifact_version')::integer
   CROSS JOIN LATERAL jsonb_array_elements(ref.content->'assignments') assignment
   WHERE owner.id=(r.authority->>'AF13.owner_validation_rules')::bigint
    AND assignment->>'user_id'=r.actor_id::text AND assignment->'purposes' ? r.kind
    AND psl_schedules_role_current(p.case_id,r.actor_id,r.authority,assignment->>'role'))
  AND (r.kind='meaning' OR (r.snapshot->>'meaning'=(SELECT max(id)::text FROM documents_validationreview WHERE package_id=p.id AND kind='meaning')
   AND psl_schedules_validation_review_current((r.snapshot->>'meaning')::bigint)))
  AND (r.kind<>'acceptance' OR (psl_schedules_policy_current(p.case_id,(r.snapshot->>'criteria')::bigint)
   AND r.snapshot->>'expectations'=(SELECT max(id)::text FROM documents_validationreview WHERE package_id=p.id AND kind='expectations')
   AND psl_schedules_validation_review_current((r.snapshot->>'expectations')::bigint)
   AND NOT EXISTS(SELECT 1 FROM jsonb_array_elements_text(r.snapshot->'replays') replay WHERE NOT EXISTS(
    SELECT 1 FROM documents_validationreplay vr WHERE vr.id=replay::bigint AND vr.package_id=p.id
     AND vr.expectation_review_id=(r.snapshot->>'expectations')::bigint AND vr.result->'matches'='true'::jsonb
     AND psl_schedules_grants(p.case_id,vr.actor_id,ARRAY['validation.replay.record'])
     AND vr.id=(SELECT max(id) FROM documents_validationreplay WHERE package_id=p.id AND example_id=vr.example_id))))));
$$;
CREATE OR REPLACE FUNCTION psl_schedules_current(sid bigint) RETURNS boolean LANGUAGE sql STABLE AS $$
 SELECT EXISTS(SELECT 1 FROM finance_schedulework s WHERE s.id=sid AND s.kind IN ('income','inventory')
  AND psl_schedules_grants(s.case_id,s.actor_id,ARRAY['case.read','finance.read','schedules.read','schedules.prepare'])
  AND NOT EXISTS(SELECT 1 FROM finance_schedulework n WHERE n.case_id=s.case_id AND n.kind=s.kind AND n.reference=s.reference AND n.version>s.version)
  AND s.snapshot->'policy'->>'status'='ACTIVE' AND psl_schedules_policy_current(s.case_id,(s.snapshot->'policy'->>'id')::bigint)
  AND (s.parent_id IS NULL OR (psl_schedules_grants(s.case_id,s.actor_id,ARRAY['finance.calculate']) AND psl_schedules_mapping_current(s.parent_id)))
  AND NOT EXISTS(SELECT 1 FROM jsonb_array_elements(s.snapshot->'packages') pin WHERE NOT EXISTS(
   SELECT 1 FROM documents_validationpackage p WHERE p.id=(pin->>'id')::bigint AND p.case_id=s.case_id AND p.sha256=pin->>'sha256' AND p.reference=pin->>'schedule'
    AND psl_schedules_package_current(p.id)
    AND NOT EXISTS(SELECT 1 FROM jsonb_array_elements(pin->'reviews') rp WHERE
     (rp->>'id')::bigint IS DISTINCT FROM (SELECT max(id) FROM documents_validationreview WHERE package_id=p.id AND kind=rp->>'purpose')
     OR (rp->>'valid')::boolean IS DISTINCT FROM psl_schedules_validation_review_current((rp->>'id')::bigint)))))
$$;
CREATE OR REPLACE FUNCTION psl_schedules_review_current(rid bigint) RETURNS boolean LANGUAGE sql STABLE AS $$
 SELECT EXISTS(SELECT 1 FROM finance_schedulereview r JOIN finance_schedulework w ON w.id=r.work_id
  WHERE r.id=rid AND r.verdict='approve' AND r.snapshot=w.snapshot AND psl_schedules_current(w.id)
   AND psl_schedules_grants(w.case_id,r.actor_id,ARRAY['case.read','finance.read','schedules.read','schedules.review'])
   AND psl_schedules_authority_current(w.case_id,r.authority) AND psl_schedules_role_current(w.case_id,r.actor_id,r.authority)
   AND r.id=(SELECT max(id) FROM finance_schedulereview WHERE work_id=w.id));
$$;

CREATE OR REPLACE FUNCTION psl_ppe_policy_people_current(pid bigint) RETURNS boolean LANGUAGE sql STABLE AS $$
 SELECT EXISTS(SELECT 1 FROM policy_configuration c WHERE c.id=pid AND
  CASE WHEN c.component IN ('F07.review_authority','AF13.owner_validation_rules') THEN
   EXISTS(SELECT 1 FROM policy_registeredreference r WHERE r.case_id=c.case_id
    AND r.ref=c.envelope->'value'->>'artifact_ref' AND r.version=(c.envelope->'value'->>'artifact_version')::integer
    AND r.sha256=c.envelope->'value'->>'sha256'
    AND NOT EXISTS(SELECT 1 FROM jsonb_array_elements(r.content->'assignments') assignment
     WHERE NOT EXISTS(SELECT 1 FROM auth_user u WHERE u.id=(assignment->>'user_id')::bigint AND u.is_active)))
  WHEN c.component='D05.role_principal_assignments' THEN
   NOT EXISTS(SELECT 1 FROM jsonb_array_elements_text(c.envelope->'value') selection(ref)
    LEFT JOIN policy_registeredreference r ON r.case_id=c.case_id AND r.ref=selection.ref AND r.version=1
    LEFT JOIN auth_user u ON u.id=(r.content->>'user_id')::bigint
    WHERE r.id IS NULL OR u.id IS NULL OR NOT u.is_active)
  ELSE true END);
$$;
CREATE OR REPLACE FUNCTION psl_ppe_policy_current(cid uuid, pid bigint) RETURNS boolean LANGUAGE sql STABLE AS $$
 SELECT EXISTS(SELECT 1 FROM policy_configuration c JOIN core_case target_case ON target_case.id=c.case_id
  WHERE c.id=pid AND c.case_id=cid AND psl_ppe_policy_people_current(c.id)
  AND c.envelope->'subject_scope'=jsonb_build_object('kind',CASE WHEN target_case.kind='project' THEN 'project' ELSE 'service' END,'ref',c.case_id::text)
  AND (c.envelope->>'fixture_scope'='synthetic_test')=target_case.synthetic
  AND (SELECT state FROM policy_policystate WHERE configuration_id=c.id ORDER BY id DESC LIMIT 1)='active'
  AND (c.envelope->>'effective_from')::timestamptz<=clock_timestamp()
  AND (c.envelope->>'effective_until' IS NULL OR (c.envelope->>'effective_until')::timestamptz>clock_timestamp())
  AND NOT EXISTS(SELECT 1 FROM policy_scopeapplication ap
   JOIN policy_scopeversion sv ON sv.id=ap.source_id JOIN policy_configuration origin ON origin.id=sv.configuration_id
   JOIN core_case origin_case ON origin_case.id=origin.case_id
   WHERE ap.configuration_id=c.id AND (
    NOT psl_ppe_policy_people_current(origin.id) OR target_case.tenant<>origin_case.tenant OR target_case.synthetic<>origin_case.synthetic
    OR c.component<>origin.component OR (sv.kind<>'organization' AND c.case_id<>origin.case_id)
    OR NOT ((sv.kind='organization' AND sv.ref=origin_case.tenant)
     OR (sv.kind='project' AND origin_case.kind='project' AND sv.ref=origin.case_id::text)
     OR (sv.kind='service' AND origin_case.kind='support' AND sv.ref=origin.case_id::text)
     OR (sv.kind='contract' AND EXISTS(SELECT 1 FROM core_evidence e WHERE e.case_id=origin.case_id AND e.kind='sow' AND sv.ref='evidence:'||e.id::text)))
    OR sv.id IS DISTINCT FROM (SELECT family.id FROM policy_scopeversion family
     JOIN policy_configuration fc ON fc.id=family.configuration_id
     WHERE fc.case_id=origin.case_id AND fc.component=origin.component AND family.kind=sv.kind AND family.ref=sv.ref
      AND EXISTS(SELECT 1 FROM policy_scopestate fs WHERE fs.source_id=family.id AND fs.state IN ('active','revoked'))
     ORDER BY family.revision DESC LIMIT 1)
    OR EXISTS(SELECT 1 FROM unnest(ARRAY['effective_from','effective_until','implementation_id','implementation_version','reviewed_implementation_ref','component_schema_ref','schema_version','fixture_scope']) k
     WHERE c.envelope->k IS DISTINCT FROM origin.envelope->k)
    OR origin.envelope->'subject_scope'<>jsonb_build_object('kind',CASE WHEN origin_case.kind='project' THEN 'project' ELSE 'service' END,'ref',origin.case_id::text)
    OR (origin.envelope->>'fixture_scope'='synthetic_test')<>origin_case.synthetic
    OR (SELECT state FROM policy_scopestate WHERE source_id=sv.id ORDER BY id DESC LIMIT 1)<>'active'
    OR (SELECT state FROM policy_policystate WHERE configuration_id=origin.id ORDER BY id DESC LIMIT 1)<>'validated'
    OR NOT EXISTS(SELECT 1 FROM auth_user u WHERE u.id=ap.actor_id AND u.is_active)
    OR NOT EXISTS(SELECT 1 FROM identity_grant WHERE user_id=ap.actor_id AND case_id=c.case_id AND action='case.read' AND active)
    OR NOT EXISTS(SELECT 1 FROM identity_grant WHERE user_id=ap.actor_id AND case_id=c.case_id AND action='policy.configure' AND active)
    OR NOT EXISTS(SELECT 1 FROM identity_grant WHERE user_id=ap.actor_id AND case_id=origin.case_id AND action='case.read' AND active)
    OR NOT EXISTS(SELECT 1 FROM identity_grant WHERE user_id=ap.actor_id AND case_id=origin.case_id AND action='policy.read' AND active)
    OR NOT EXISTS(SELECT 1 FROM policy_scopestate activation JOIN auth_user u ON u.id=activation.actor_id
     WHERE activation.id=(SELECT max(id) FROM policy_scopestate WHERE source_id=sv.id AND state='active')
      AND u.is_active AND EXISTS(SELECT 1 FROM identity_grant WHERE user_id=u.id AND case_id=origin.case_id AND action='case.read' AND active)
      AND EXISTS(SELECT 1 FROM identity_grant WHERE user_id=u.id AND case_id=origin.case_id AND action='policy.activate' AND active)))));

$$;
CREATE OR REPLACE FUNCTION psl_ppe_grants(cid uuid, uid bigint, actions text[]) RETURNS boolean LANGUAGE sql STABLE AS $$
 SELECT EXISTS(SELECT 1 FROM auth_user WHERE id=uid AND is_active)
  AND NOT EXISTS(SELECT 1 FROM unnest(actions) required(action_name) WHERE NOT EXISTS(
   SELECT 1 FROM identity_grant g WHERE g.case_id=cid AND g.user_id=uid AND g.action=required.action_name AND g.active));
$$;
CREATE OR REPLACE FUNCTION psl_ppe_authority_current(cid uuid, authority jsonb) RETURNS boolean LANGUAGE sql STABLE AS $$
 SELECT NOT EXISTS(SELECT 1 FROM jsonb_each(authority) pin WHERE jsonb_typeof(pin.value)='number'
  AND pin.key<>'D05.decision_action_matrix' AND NOT psl_ppe_policy_current(cid,(pin.value::text)::bigint));
$$;
CREATE OR REPLACE FUNCTION psl_ppe_role_current(cid uuid, uid bigint, authority jsonb) RETURNS boolean LANGUAGE sql STABLE AS $$
 SELECT EXISTS(SELECT 1 FROM policy_configuration c
  CROSS JOIN LATERAL jsonb_array_elements_text(c.envelope->'value') selection(ref)
  JOIN policy_registeredreference r ON r.case_id=c.case_id AND r.ref=selection.ref AND r.version=1
  WHERE c.id=(authority->>'D05.role_principal_assignments')::bigint AND psl_ppe_policy_current(cid,c.id)
   AND r.content->>'user_id'=uid::text AND r.content->>'role'='Finance'
   AND (NOT r.content ? 'eligibility' OR
    ((r.content->'eligibility'->>'valid_from')::timestamptz<=clock_timestamp()
     AND (r.content->'eligibility'->>'valid_until')::timestamptz>clock_timestamp())));
$$;
CREATE OR REPLACE FUNCTION psl_ppe_finance_review_current(rid bigint) RETURNS boolean LANGUAGE sql STABLE AS $$
 SELECT EXISTS(SELECT 1 FROM finance_financereview r WHERE r.id=rid AND r.verdict='approve'
  AND psl_ppe_grants(r.case_id,r.actor_id,ARRAY['finance.review'])
  AND psl_ppe_authority_current(r.case_id,r.authority)
  AND psl_ppe_role_current(r.case_id,r.actor_id,r.authority)
  AND EXISTS(SELECT 1 FROM policy_configuration c JOIN policy_registeredreference ref
   ON ref.case_id=c.case_id AND ref.ref=c.envelope->'value'->>'artifact_ref'
    AND ref.version=(c.envelope->'value'->>'artifact_version')::integer AND ref.sha256=c.envelope->'value'->>'sha256'
   WHERE c.case_id=r.case_id AND c.component='D05.decision_action_matrix' AND psl_ppe_policy_current(r.case_id,c.id)
    AND ref.content->'finance' @> jsonb_build_array(r.authority->'finance_review_rule'))
  AND r.id=(SELECT max(x.id) FROM finance_financereview x WHERE x.case_id=r.case_id AND x.purpose=r.purpose
   AND x.source_id IS NOT DISTINCT FROM r.source_id AND x.configuration_id IS NOT DISTINCT FROM r.configuration_id
   AND x.adjustment_id IS NOT DISTINCT FROM r.adjustment_id AND x.run_id IS NOT DISTINCT FROM r.run_id));
$$;
CREATE OR REPLACE FUNCTION psl_ppe_mapping_current(nid bigint) RETURNS boolean LANGUAGE sql STABLE AS $$
 SELECT EXISTS(SELECT 1 FROM finance_financerun n JOIN finance_financesource src ON src.id=n.source_id
  WHERE n.id=nid AND n.kind='mapping' AND n.result->>'status'='complete' AND src.completeness='complete'
   AND psl_ppe_grants(n.case_id,n.actor_id,ARRAY['case.read','finance.read','finance.calculate'])
   AND psl_ppe_finance_review_current((n.snapshot->'source_review'->>'id')::bigint)
   AND NOT EXISTS(SELECT 1 FROM jsonb_each(n.snapshot->'policies') pin
    WHERE pin.value->>'status'<>'ACTIVE' OR NOT psl_ppe_policy_current(n.case_id,(pin.value->>'id')::bigint))
   AND NOT EXISTS(SELECT 1 FROM jsonb_each(n.snapshot->'reviews') pin
    WHERE pin.value->'valid'<>'true'::jsonb OR NOT psl_ppe_finance_review_current((pin.value->>'id')::bigint))
   AND NOT EXISTS(SELECT 1 FROM jsonb_array_elements(n.snapshot->'adjustments') pin
    WHERE NOT psl_ppe_finance_review_current((pin->'review'->>'id')::bigint)
     OR EXISTS(SELECT 1 FROM finance_financeadjustment old JOIN finance_financeadjustment newer
      ON newer.source_id=old.source_id AND newer.reference=old.reference AND newer.number>old.number
      WHERE old.id=(pin->>'id')::bigint)));
$$;
CREATE OR REPLACE FUNCTION psl_ppe_review_current(rid bigint) RETURNS boolean LANGUAGE sql STABLE AS $$
 SELECT EXISTS(SELECT 1 FROM finance_schedulereview r JOIN finance_schedulework w ON w.id=r.work_id
  WHERE r.id=rid AND r.verdict='approve' AND r.snapshot=w.snapshot
   AND psl_ppe_grants(w.case_id,r.actor_id,ARRAY['case.read','finance.read','ppe.read','ppe.review'])
   AND psl_ppe_authority_current(w.case_id,r.authority)
   AND psl_ppe_role_current(w.case_id,r.actor_id,r.authority)
   AND r.id=(SELECT max(x.id) FROM finance_schedulereview x WHERE x.work_id=w.id AND x.authority->>'purpose'=r.authority->>'purpose'));
$$;
CREATE OR REPLACE FUNCTION psl_ppe_schedule_current(sid bigint, depth integer DEFAULT 0) RETURNS boolean LANGUAGE plpgsql STABLE AS $$
DECLARE s finance_schedulework; r finance_schedulework; basis bigint; prior_id bigint; pin jsonb;
BEGIN
 IF depth>36 THEN RETURN false; END IF;
 SELECT * INTO s FROM finance_schedulework WHERE id=sid AND kind='ppe_schedule';
 IF NOT FOUND OR s.result->>'status'<>'ready' THEN RETURN false; END IF;
 SELECT * INTO r FROM finance_schedulework WHERE id=(s.payload->>'register_id')::bigint AND case_id=s.case_id AND kind='ppe_register';
 IF NOT FOUND THEN RETURN false; END IF;
 IF NOT psl_ppe_grants(s.case_id,s.actor_id,ARRAY['case.read','finance.read','ppe.read','ppe.prepare'])
  OR NOT psl_ppe_grants(r.case_id,r.actor_id,ARRAY['case.read','finance.read','ppe.read','ppe.capture'])
  OR NOT psl_ppe_review_current((s.snapshot->>'register_review')::bigint)
  OR s.snapshot->'register'<>jsonb_build_array(r.id,r.sha256)
  OR EXISTS(SELECT 1 FROM finance_schedulework newer WHERE newer.case_id=s.case_id
   AND ((newer.kind=s.kind AND newer.reference=s.reference AND newer.version>s.version)
    OR (newer.kind=r.kind AND newer.reference=r.reference AND newer.version>r.version))) THEN RETURN false; END IF;
 SELECT max(id) INTO basis FROM finance_schedulereview WHERE work_id=r.id AND authority->>'purpose'='basis';
 IF basis IS DISTINCT FROM (s.snapshot->>'basis_review')::bigint
  OR (s.snapshot->>'basis_approved')::boolean IS DISTINCT FROM psl_ppe_review_current(basis)
  OR (r.result->'date_basis_ambiguous'='true'::jsonb AND NOT psl_ppe_review_current(basis)) THEN RETURN false; END IF;
 IF EXISTS(SELECT 1 FROM jsonb_each(s.snapshot->'policies') p WHERE p.value->>'status'<>'ACTIVE'
   OR NOT psl_ppe_policy_current(s.case_id,(p.value->>'id')::bigint)) THEN RETURN false; END IF;
 IF s.parent_id IS NOT NULL AND NOT psl_ppe_mapping_current(s.parent_id) THEN RETURN false; END IF;
 IF NOT EXISTS(SELECT 1 FROM policy_configuration c JOIN policy_registeredreference ref
   ON ref.case_id=c.case_id AND ref.ref=c.envelope->'value'->>'artifact_ref'
    AND ref.version=(c.envelope->'value'->>'artifact_version')::integer AND ref.sha256=c.envelope->'value'->>'sha256'
   WHERE c.id=(s.snapshot->'policies'->'F07.source_rules'->>'id')::bigint
    AND EXTRACT(EPOCH FROM (clock_timestamp()-(r.payload->>'extracted_at')::timestamptz))<=(ref.content->>'max_age_seconds')::numeric)
 THEN RETURN false; END IF;
 prior_id=(s.payload->>'prior_id')::bigint;
 IF prior_id IS NOT NULL AND (NOT psl_ppe_schedule_current(prior_id,depth+1)
  OR NOT psl_ppe_review_current((s.snapshot->'prior'->>2)::bigint)) THEN RETURN false; END IF;
 IF s.snapshot->'owner_validation'->'valid'='true'::jsonb THEN
  FOR pin IN SELECT value FROM jsonb_array_elements(s.snapshot->'owner_validation'->'reviews') LOOP
   IF NOT EXISTS(SELECT 1 FROM documents_validationreview vr JOIN documents_validationpackage vp ON vp.id=vr.package_id
    WHERE vr.id=(pin::text)::bigint AND vr.package_id=(s.snapshot->'owner_validation'->>'id')::bigint
     AND vr.verdict='approve' AND psl_ppe_authority_current(s.case_id,vr.authority)
     AND psl_ppe_grants(s.case_id,vr.actor_id,ARRAY['case.read','validation.read',CASE WHEN vr.kind='acceptance' THEN 'validation.accept' ELSE 'validation.review' END])
     AND vr.id=(SELECT max(id) FROM documents_validationreview WHERE package_id=vr.package_id AND kind=vr.kind)) THEN RETURN false; END IF;
  END LOOP;
 END IF;
 RETURN true;
END $$;

CREATE OR REPLACE FUNCTION psl_factory_identity() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
 IF TG_OP='DELETE' THEN RAISE EXCEPTION 'Factory history cannot be deleted'; END IF;
 IF TG_OP='UPDATE' THEN
  IF (NEW.case_id,NEW.actor_id,NEW.key,NEW.definition,NEW.request,NEW.request_hash,NEW.created_at)
    IS DISTINCT FROM (OLD.case_id,OLD.actor_id,OLD.key,OLD.definition,OLD.request,OLD.request_hash,OLD.created_at)
    OR NEW.budget_used<OLD.budget_used OR NEW.fence<OLD.fence OR NEW.revision<OLD.revision
    OR (OLD.budget_used>0 AND NEW.budget_limit<>OLD.budget_limit)
  THEN RAISE EXCEPTION 'Immutable factory identity and monotonic shared budget required'; END IF;
  IF OLD.source_head_id IS NOT NULL AND NEW.source_head_id IS DISTINCT FROM OLD.source_head_id
   AND (NEW.source_head_id IS NULL OR NOT EXISTS(SELECT 1 FROM core_evidence n JOIN core_evidence o ON o.id=OLD.source_head_id WHERE n.id=NEW.source_head_id AND n.version>o.version))
  THEN RAISE EXCEPTION 'Forward native source successor required'; END IF;
 END IF;
 IF NEW.definition NOT IN ('engagement/v1','pmo-minutes/v1','pmo-finance/v1','planning/v1','commercial/v1','delivery-release/v1','delivery-hypercare/v1','delivery-archive/v1','delivery-handover/v1','delivery-closure/v1','delivery-go-live/v1','finance-accounts/v1','rfp-response/v1','finance-schedules/v1','finance-ppe/v1','pmo-change/v1','finance-forecast/v1','finance-payroll/v1','pmo-emergency/v1','finance-bu/v1','pmo-weekly-report/v1','pmo-escalation/v1') THEN RAISE EXCEPTION 'Closed factory definition required'; END IF;
 IF (NEW.invoice_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM finance_invoice i WHERE i.id=NEW.invoice_id AND i.case_id=NEW.case_id))
  OR (NEW.preparation_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM finance_billingpreparation p WHERE p.id=NEW.preparation_id AND p.case_id=NEW.case_id))
  OR (NEW.policy_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM policy_configuration p WHERE p.id=NEW.policy_id AND p.case_id=NEW.case_id
    AND p.component=CASE NEW.definition WHEN 'engagement/v1' THEN 'OPS.factory_engagement_execution' WHEN 'pmo-minutes/v1' THEN 'OPS.factory_minutes_execution' WHEN 'planning/v1' THEN 'OPS.factory_planning_execution' WHEN 'commercial/v1' THEN 'OPS.factory_commercial_execution' WHEN 'delivery-release/v1' THEN 'OPS.factory_delivery_execution' WHEN 'delivery-hypercare/v1' THEN 'OPS.factory_hypercare_execution' WHEN 'delivery-archive/v1' THEN 'OPS.factory_archive_execution' WHEN 'delivery-handover/v1' THEN 'OPS.factory_handover_execution' WHEN 'delivery-closure/v1' THEN 'OPS.factory_closure_execution' WHEN 'delivery-go-live/v1' THEN 'OPS.factory_go_live_execution' WHEN 'finance-schedules/v1' THEN 'OPS.factory_schedules_execution' WHEN 'pmo-escalation/v1' THEN 'OPS.factory_escalation_execution' WHEN 'finance-ppe/v1' THEN 'OPS.factory_ppe_execution' WHEN 'pmo-change/v1' THEN 'OPS.factory_change_execution' WHEN 'finance-bu/v1' THEN 'OPS.factory_bu_execution' WHEN 'finance-forecast/v1' THEN 'OPS.factory_forecast_execution' WHEN 'finance-payroll/v1' THEN 'OPS.factory_payroll_execution' WHEN 'pmo-emergency/v1' THEN 'OPS.factory_emergency_execution' WHEN 'pmo-weekly-report/v1' THEN 'OPS.factory_reporting_execution' WHEN 'finance-accounts/v1' THEN 'OPS.factory_accounting_execution' WHEN 'rfp-response/v1' THEN 'OPS.factory_rfp_execution' ELSE 'OPS.factory_execution' END))
 THEN RAISE EXCEPTION 'Same-case native factory references required'; END IF;
 IF NEW.definition='pmo-finance/v1' AND NEW.source_head_id IS NOT NULL THEN RAISE EXCEPTION 'Invoice work cannot carry a domain source head'; END IF;
 IF NEW.definition='planning/v1' THEN
  IF NEW.invoice_id IS NOT NULL OR NEW.preparation_id IS NOT NULL OR NOT EXISTS(
    SELECT 1 FROM core_evidence e JOIN core_audit a ON a.case_id=e.case_id AND a.actor_id=e.created_by_id
    WHERE e.id=NEW.source_head_id AND e.case_id=NEW.case_id AND e.kind='planning_packet' AND a.action='planning.recorded'
    AND a.data=jsonb_build_object('kind','packet','evidence_id',e.id,'sha256',e.sha256) AND e.body::jsonb->'engagement_id'=NEW.request->'engagement')
  THEN RAISE EXCEPTION 'Native same-engagement planning packet required'; END IF;
 END IF;
 IF NEW.definition='commercial/v1' THEN
  IF NEW.invoice_id IS NOT NULL OR NEW.preparation_id IS NOT NULL OR NOT EXISTS(
    SELECT 1 FROM core_evidence e JOIN core_audit a ON a.case_id=e.case_id AND a.actor_id=e.created_by_id
    WHERE e.id=NEW.source_head_id AND e.case_id=NEW.case_id AND e.kind='agent_private_commercial_intake'
    AND e.body::jsonb->>'protocol'='factory-commercial-intake/v1' AND a.action='factory.commercial_intake'
    AND a.data=jsonb_build_object('evidence_id',e.id,'sha256',e.sha256))
  THEN RAISE EXCEPTION 'Native private commercial intake required'; END IF;
 END IF;

 IF NEW.definition='delivery-release/v1' THEN
  IF NEW.invoice_id IS NOT NULL OR NEW.preparation_id IS NOT NULL OR NOT EXISTS(
   SELECT 1 FROM core_evidence e JOIN core_audit a ON a.case_id=e.case_id AND a.actor_id=e.created_by_id
   JOIN pmo_deliverydossier d ON d.id=(NEW.request->>'dossier')::bigint
   WHERE e.id=NEW.source_head_id AND e.case_id=NEW.case_id AND e.kind='agent_private_delivery_intake'
    AND d.case_id=NEW.case_id AND e.body::jsonb->>'protocol'='factory-delivery-intake/v1'
    AND e.body::jsonb->>'dossier_id'=d.id::text AND a.action='factory.delivery_intake'
    AND a.data=jsonb_build_object('evidence_id',e.id,'sha256',e.sha256))
  THEN RAISE EXCEPTION 'Native same-case delivery intake and dossier required'; END IF;
 END IF;

 IF NEW.definition='delivery-hypercare/v1' THEN
  IF NEW.invoice_id IS NOT NULL OR NEW.preparation_id IS NOT NULL OR NOT EXISTS(
   SELECT 1 FROM core_evidence e JOIN core_audit a ON a.case_id=e.case_id AND a.actor_id=e.created_by_id
   JOIN pmo_deliverydossier d ON d.id=(NEW.request->>'dossier')::bigint
   WHERE e.id=NEW.source_head_id AND e.case_id=NEW.case_id AND e.kind='agent_private_delivery_intake'
    AND d.case_id=NEW.case_id AND e.body::jsonb->>'protocol'='factory-delivery-intake/v1'
    AND e.body::jsonb->>'dossier_id'=d.id::text AND a.action='factory.delivery_intake'
    AND a.data=jsonb_build_object('evidence_id',e.id,'sha256',e.sha256))
  THEN RAISE EXCEPTION 'Native same-case delivery intake and dossier required'; END IF;
 END IF;

 IF NEW.definition='delivery-archive/v1' THEN
  IF NEW.invoice_id IS NOT NULL OR NEW.preparation_id IS NOT NULL OR NOT EXISTS(
   SELECT 1 FROM core_evidence e JOIN core_audit a ON a.case_id=e.case_id AND a.actor_id=e.created_by_id
   JOIN pmo_deliverydossier d ON d.id=(NEW.request->>'dossier')::bigint
   WHERE e.id=NEW.source_head_id AND e.case_id=NEW.case_id AND e.kind='agent_private_archive_intake'
    AND e.body::jsonb->>'protocol'='factory-archive-intake/v1' AND e.body::jsonb->>'dossier_id'=d.id::text
    AND e.body::jsonb-ARRAY['protocol','dossier_id','inventory']='{}'::jsonb
    AND jsonb_typeof(e.body::jsonb->'inventory')='object' AND d.case_id=NEW.case_id
    AND a.action IN ('factory.archive_intake','factory.archive_source')
    AND a.data=jsonb_build_object('evidence_id',e.id,'sha256',e.sha256))
  THEN RAISE EXCEPTION 'Native same-case declared archive intake and dossier required'; END IF;
 END IF;

 IF NEW.definition='delivery-handover/v1' THEN
  IF NEW.invoice_id IS NOT NULL OR NEW.preparation_id IS NOT NULL OR NOT EXISTS(
   SELECT 1 FROM core_evidence e JOIN core_audit a ON a.case_id=e.case_id AND a.actor_id=e.created_by_id
   JOIN pmo_deliverydossier d ON d.id=(NEW.request->>'dossier')::bigint
   WHERE e.id=NEW.source_head_id AND e.case_id=NEW.case_id AND e.kind='agent_private_handover_intake'
    AND e.body::jsonb->>'protocol'='factory-handover-intake/v1' AND e.body::jsonb->>'dossier_id'=d.id::text
    AND e.body::jsonb-ARRAY['protocol','dossier_id','inputs']='{}'::jsonb
    AND jsonb_typeof(e.body::jsonb->'inputs')='object' AND d.case_id=NEW.case_id
    AND a.action IN ('factory.handover_intake','factory.handover_source')
    AND a.data=jsonb_build_object('evidence_id',e.id,'sha256',e.sha256))
  THEN RAISE EXCEPTION 'Native same-case handover input provenance and dossier required'; END IF;
 END IF;

 IF NEW.definition='delivery-closure/v1' THEN
  IF NEW.invoice_id IS NOT NULL OR NEW.preparation_id IS NOT NULL OR NOT EXISTS(
   SELECT 1 FROM core_evidence e JOIN core_audit a ON a.case_id=e.case_id AND a.actor_id=e.created_by_id
   JOIN pmo_deliverydossier d ON d.id=(NEW.request->>'dossier')::bigint
   WHERE e.id=NEW.source_head_id AND e.case_id=NEW.case_id AND e.kind='agent_private_closure_intake'
    AND e.body::jsonb->>'protocol'='factory-closure-intake/v1' AND e.body::jsonb->>'dossier_id'=d.id::text
    AND e.body::jsonb-ARRAY['protocol','dossier_id','inputs']='{}'::jsonb
    AND jsonb_typeof(e.body::jsonb->'inputs')='object' AND d.case_id=NEW.case_id
    AND a.action IN ('factory.closure_intake','factory.closure_source')
    AND a.data=jsonb_build_object('evidence_id',e.id,'sha256',e.sha256))
  THEN RAISE EXCEPTION 'Native same-case closure input provenance and dossier required'; END IF;
 END IF;

 IF NEW.definition='delivery-go-live/v1' THEN
  IF NEW.invoice_id IS NOT NULL OR NEW.preparation_id IS NOT NULL OR NOT EXISTS(
   SELECT 1 FROM core_evidence e JOIN core_audit a ON a.case_id=e.case_id AND a.actor_id=e.created_by_id
   JOIN pmo_deliverydossier d ON d.id=(NEW.request->>'dossier')::bigint
   WHERE e.id=NEW.source_head_id AND e.case_id=NEW.case_id AND e.kind='agent_private_go_live_intake'
    AND e.body::jsonb->>'protocol'='factory-go-live-intake/v1' AND e.body::jsonb->>'dossier_id'=d.id::text
    AND e.body::jsonb-ARRAY['protocol','dossier_id','inputs']='{}'::jsonb
    AND jsonb_typeof(e.body::jsonb->'inputs')='object' AND d.case_id=NEW.case_id
    AND a.action IN ('factory.go_live_intake','factory.go_live_source')
    AND a.data=jsonb_build_object('evidence_id',e.id,'sha256',e.sha256))
  THEN RAISE EXCEPTION 'Native same-case go_live input provenance and dossier required'; END IF;
 END IF;

 IF NEW.definition='finance-accounts/v1' THEN
  IF NEW.invoice_id IS NOT NULL OR NEW.preparation_id IS NOT NULL OR NOT EXISTS(
   SELECT 1 FROM core_evidence e JOIN finance_financesource s ON s.id=(e.body::jsonb->>'source')::bigint
   JOIN core_audit a ON a.case_id=e.case_id AND a.actor_id=e.created_by_id
   WHERE e.id=NEW.source_head_id AND e.case_id=NEW.case_id AND e.kind='agent_private_accounting_intake'
    AND e.body::jsonb->>'schema'='factory-accounting-intake/v1' AND s.case_id=NEW.case_id
    AND s.batch_id=(NEW.request->>'batch')::bigint AND s.entity=NEW.request->>'entity'
    AND e.body::jsonb->'batch'=NEW.request->'batch' AND e.body::jsonb->'entity'=NEW.request->'entity'
    AND e.body::jsonb->'reference'=NEW.request->'reference'
    AND a.action='factory.accounting_inputs_recorded'
    AND a.data=jsonb_build_object('evidence_id',e.id,'sha256',e.sha256))
  THEN RAISE EXCEPTION 'Native exact accounting intake/source references required'; END IF;
 END IF;

 IF NEW.definition='pmo-change/v1' THEN
  IF NEW.invoice_id IS NOT NULL OR NEW.preparation_id IS NOT NULL OR NOT EXISTS(
   SELECT 1 FROM core_evidence e JOIN core_audit a ON a.case_id=e.case_id AND a.actor_id=e.created_by_id
   JOIN pmo_changeversion v ON v.id=(e.body::jsonb->>'change_version_id')::bigint
   JOIN pmo_changerequest c ON c.id=v.change_id
   WHERE e.id=NEW.source_head_id AND e.case_id=NEW.case_id AND e.kind='agent_private_change_intake'
    AND c.case_id=NEW.case_id AND c.id=(NEW.request->>'change')::bigint
    AND e.body::jsonb->>'protocol'='factory-change-intake/v1'
    AND e.body::jsonb-ARRAY['protocol','change_version_id','inputs']='{}'::jsonb
    AND jsonb_typeof(e.body::jsonb->'inputs')='object'
    AND a.action IN ('factory.change_intake','factory.change_source')
    AND a.data=jsonb_build_object('evidence_id',e.id,'sha256',e.sha256))
  THEN RAISE EXCEPTION 'Exact same-project native change intake provenance required'; END IF;
 END IF;

 IF NEW.definition='pmo-emergency/v1' THEN
  IF NEW.invoice_id IS NOT NULL OR NEW.preparation_id IS NOT NULL OR NOT EXISTS(
   SELECT 1 FROM core_evidence e JOIN core_audit a ON a.case_id=e.case_id AND a.actor_id=e.created_by_id
   JOIN pmo_emergencyprofile ep ON ep.id=(e.body::jsonb->>'profile_id')::bigint
   JOIN pmo_changeversion cv ON cv.id=ep.version_id JOIN pmo_changerequest cr ON cr.id=cv.change_id
   WHERE e.id=NEW.source_head_id AND e.case_id=NEW.case_id AND e.kind='agent_private_emergency_intake'
    AND cr.case_id=NEW.case_id AND cr.id=(NEW.request->>'change')::bigint AND cv.category='Emergency' AND cv.incident_id IS NOT NULL
    AND e.body::jsonb->>'protocol'='factory-emergency-intake/v1'
    AND e.body::jsonb-ARRAY['protocol','profile_id','inputs']='{}'::jsonb
    AND jsonb_typeof(e.body::jsonb->'inputs')='object'
    AND a.action IN ('factory.emergency_intake','factory.emergency_source')
    AND a.data=jsonb_build_object('evidence_id',e.id,'sha256',e.sha256))
  THEN RAISE EXCEPTION 'Exact same-project incident-linked native Emergency source required'; END IF;
 END IF;

 IF NEW.definition='finance-payroll/v1' THEN
  IF NEW.invoice_id IS NOT NULL OR NEW.preparation_id IS NOT NULL OR NOT EXISTS(
   SELECT 1 FROM core_evidence e JOIN core_audit a ON a.case_id=e.case_id AND a.actor_id=e.created_by_id
   JOIN finance_payrollrequest q ON q.id=(e.body::jsonb->>'request_id')::bigint
   WHERE e.id=NEW.source_head_id AND e.case_id=NEW.case_id AND e.kind='agent_private_payroll_intake'
    AND q.case_id=NEW.case_id AND q.reference=NEW.request->>'payroll_reference'
    AND e.body::jsonb->>'protocol'='factory-payroll-intake/v1'
    AND e.body::jsonb-ARRAY['protocol','request_id','inputs']='{}'::jsonb
    AND (e.body::jsonb->'inputs')-ARRAY['input_ids','hr_snapshot_id']='{}'::jsonb
    AND jsonb_array_length(e.body::jsonb->'inputs'->'input_ids')=2
    AND (SELECT count(DISTINCT i.provider) FROM finance_payrollinput i
      WHERE i.id IN (SELECT value::bigint FROM jsonb_array_elements_text(e.body::jsonb->'inputs'->'input_ids'))
       AND i.request_id=q.id AND i.metadata->'accepted'='true'::jsonb)=2
    AND a.action IN ('factory.payroll_intake','factory.payroll_source')
    AND a.data=jsonb_build_object('evidence_id',e.id,'sha256',e.sha256))
  THEN RAISE EXCEPTION 'Exact same-workspace restricted payroll provenance required'; END IF;
 END IF;

 IF NEW.definition='finance-ppe/v1' THEN
  IF NEW.invoice_id IS NOT NULL OR NEW.preparation_id IS NOT NULL OR NOT EXISTS(
   SELECT 1 FROM core_evidence e JOIN core_audit a ON a.case_id=e.case_id AND a.actor_id=e.created_by_id
   JOIN finance_schedulework r ON r.id=(e.body::jsonb->>'register_id')::bigint
   WHERE e.id=NEW.source_head_id AND e.case_id=NEW.case_id AND e.kind='agent_private_ppe_intake'
    AND r.case_id=NEW.case_id AND r.kind='ppe_register' AND r.reference=NEW.request->>'register_reference'
    AND e.body::jsonb->>'protocol'='factory-ppe-intake/v1'
    AND e.body::jsonb-ARRAY['protocol','register_id','prior_id','ledger_id']='{}'::jsonb
    AND a.action IN ('factory.ppe_intake','factory.ppe_source')
    AND a.data=jsonb_build_object('evidence_id',e.id,'sha256',e.sha256))
  THEN RAISE EXCEPTION 'Exact same-case native PPE register provenance required'; END IF;
 END IF;

 IF NEW.definition='finance-schedules/v1' THEN
  IF NEW.invoice_id IS NOT NULL OR NEW.preparation_id IS NOT NULL OR NOT EXISTS(
   SELECT 1 FROM core_evidence e JOIN core_audit a ON a.case_id=e.case_id AND a.actor_id=e.created_by_id
   JOIN core_evidence supplied ON supplied.id=(e.body::jsonb->>'evidence_id')::bigint AND supplied.case_id=e.case_id
   WHERE e.id=NEW.source_head_id AND e.case_id=NEW.case_id AND e.kind='agent_private_schedules_intake'
    AND e.body::jsonb->>'protocol'='factory-schedules-intake/v1' AND e.body::jsonb->>'kind'=NEW.request->>'kind'
    AND e.body::jsonb-ARRAY['protocol','kind','parent_id','evidence_id','payload']='{}'::jsonb
    AND ((NEW.request->>'kind'='inventory' AND supplied.kind='schedule_inventory' AND e.body::jsonb->'payload'='null'::jsonb AND e.body::jsonb->'parent_id'='null'::jsonb)
     OR (NEW.request->>'kind'='income' AND supplied.kind='income_detail' AND EXISTS(SELECT 1 FROM finance_financerun n WHERE n.id=(e.body::jsonb->>'parent_id')::bigint AND n.case_id=NEW.case_id AND n.kind='mapping')))
    AND a.action IN ('factory.schedules_intake','factory.schedules_source') AND a.data=jsonb_build_object('evidence_id',e.id,'sha256',e.sha256))
  THEN RAISE EXCEPTION 'Exact native schedule source provenance required'; END IF;
 END IF;

 IF NEW.definition='pmo-weekly-report/v1' THEN
  IF NEW.invoice_id IS NOT NULL OR NEW.preparation_id IS NOT NULL OR NOT EXISTS(
   SELECT 1 FROM core_evidence e JOIN core_audit a ON a.case_id=e.case_id AND a.actor_id=e.created_by_id
   WHERE e.id=NEW.source_head_id AND e.case_id=NEW.case_id AND e.kind='agent_private_reporting_intake'
    AND e.body::jsonb->>'protocol'='factory-weekly-report-intake/v1'
    AND e.body::jsonb-ARRAY['protocol','inputs','manifest','captured_at']='{}'::jsonb
    AND (e.body::jsonb->'inputs')-ARRAY['template_id','content_id','start_at','end_at']='{}'::jsonb
    AND jsonb_typeof(e.body::jsonb->'manifest')='object'
    AND e.body::jsonb->'inputs'->>'start_at'=NEW.request->>'start_at' AND e.body::jsonb->'inputs'->>'end_at'=NEW.request->>'end_at'
    AND NEW.request->>'kind'='weekly_client' AND NEW.request->>'audience'='client'
    AND a.action IN ('factory.reporting_intake','factory.reporting_source') AND a.data=jsonb_build_object('evidence_id',e.id,'sha256',e.sha256))
  THEN RAISE EXCEPTION 'Exact private selected-period weekly report source required'; END IF;
 END IF;

 IF NEW.definition='pmo-escalation/v1' AND (NEW.invoice_id IS NOT NULL OR NEW.preparation_id IS NOT NULL OR NOT EXISTS(
 SELECT 1 FROM core_evidence e JOIN core_audit a ON a.case_id=e.case_id AND a.actor_id=e.created_by_id
 JOIN pmo_escalationrequest r ON r.id=(psl_escalation_intake(e.id)->>'request_id')::bigint JOIN pmo_escalationprofile ep ON ep.id=r.profile_id
 JOIN pmo_issuestate s ON s.id=ep.state_id JOIN pmo_issue i ON i.id=s.issue_id
 WHERE e.id=NEW.source_head_id AND e.case_id=NEW.case_id AND i.case_id=NEW.case_id AND i.id=(NEW.request->>'issue')::bigint
 AND e.kind='agent_private_escalation_intake' AND psl_escalation_intake(e.id)->>'protocol'='factory-escalation-intake/v1'
 AND (psl_escalation_intake(e.id)-ARRAY['protocol','request_id','profile_id','template_id'])='{}'::jsonb AND psl_escalation_intake(e.id)->>'profile_id'=ep.id::text
 AND r.direction=NEW.request->>'direction' AND r.target=NEW.request->>'target'
 AND a.action IN ('factory.escalation_intake','factory.escalation_source') AND a.data=jsonb_build_object('evidence_id',e.id,'sha256',e.sha256)))
 THEN RAISE EXCEPTION 'Exact same-case source-bound escalation request required'; END IF;

 IF NEW.definition='finance-bu/v1' THEN
  IF NEW.invoice_id IS NOT NULL OR NEW.preparation_id IS NOT NULL OR NOT EXISTS(
   SELECT 1 FROM core_evidence e JOIN core_audit a ON a.case_id=e.case_id AND a.actor_id=e.created_by_id
   WHERE e.id=NEW.source_head_id AND e.case_id=NEW.case_id AND e.kind='agent_private_bu_intake'
    AND e.sha256=encode(sha256(convert_to(e.body,'UTF8')),'hex')
    AND e.body::jsonb->>'protocol'='factory-bu-intake/v1'
    AND e.body::jsonb-ARRAY['protocol','inputs']='{}'::jsonb
    AND (e.body::jsonb->'inputs')-ARRAY['mode','payroll_id','source_id','rule_ids','comparison']='{}'::jsonb
    AND e.body::jsonb->'inputs'->>'mode'=NEW.request->>'mode'
    AND jsonb_array_length(e.body::jsonb->'inputs'->'rule_ids')<=100
    AND a.action IN ('factory.bu_intake','factory.bu_source')
    AND a.data=jsonb_build_object('evidence_id',e.id,'sha256',e.sha256)
    AND ((NEW.request->>'mode'='staff' AND EXISTS(SELECT 1 FROM finance_payrollrun r JOIN finance_payrollrequest q ON q.id=r.request_id
      WHERE r.id=(e.body::jsonb->'inputs'->>'payroll_id')::bigint AND r.kind='match' AND q.case_id=NEW.case_id
       AND q.reference=NEW.request->>'source_reference' AND NEW.request->'scope'=jsonb_build_object('entity',q.metadata->'entity','period',q.metadata->'period','currency',q.metadata->'currency')
       AND e.body::jsonb->'inputs'->'source_id'='null'::jsonb AND e.body::jsonb->'inputs'->'comparison'='null'::jsonb
       AND NOT EXISTS(SELECT 1 FROM jsonb_array_elements_text(e.body::jsonb->'inputs'->'rule_ids') ri WHERE NOT EXISTS(
        SELECT 1 FROM finance_buwork rule WHERE rule.id=ri::bigint AND rule.case_id=NEW.case_id AND rule.kind='rule' AND rule.payroll_id=r.id))))
     OR (NEW.request->>'mode'='event' AND EXISTS(SELECT 1 FROM finance_buwork s
      WHERE s.id=(e.body::jsonb->'inputs'->>'source_id')::bigint AND s.case_id=NEW.case_id AND s.kind='source'
       AND s.reference=NEW.request->>'source_reference' AND s.metadata->'accepted'='true'::jsonb AND s.metadata->'scope'=NEW.request->'scope'
       AND e.body::jsonb->'inputs'->'payroll_id'='null'::jsonb AND e.body::jsonb->'inputs'->'rule_ids'='[]'::jsonb
       AND (e.body::jsonb->'inputs'->'comparison'='null'::jsonb OR EXISTS(SELECT 1 FROM finance_financerun fr
        WHERE fr.id=(e.body::jsonb->'inputs'->'comparison'->>'run_id')::bigint AND fr.case_id=NEW.case_id AND fr.kind='allocation'))))))
  THEN RAISE EXCEPTION 'Exact scoped native BU intake required'; END IF;
 END IF;
 IF NEW.status='verified' THEN
  IF NEW.definition='pmo-finance/v1' AND NOT EXISTS(
    SELECT 1 FROM finance_invoiceissue i JOIN finance_invoicedelivery d ON d.invoice_id=i.invoice_id JOIN finance_invoice n ON n.id=i.invoice_id
    WHERE n.id=NEW.invoice_id AND n.case_id=NEW.case_id AND i.sha256=n.sha256 AND i.payload=n.payload)
  THEN RAISE EXCEPTION 'Native invoice receipts required; agent completion is not verification'; END IF;
  IF NEW.definition='planning/v1' AND NOT EXISTS(
    SELECT 1 FROM pmo_deliverysource s JOIN pmo_deliverydossier d ON d.id=s.dossier_id JOIN core_evidence e ON e.id=s.evidence_id
    JOIN core_audit a ON a.case_id=e.case_id AND a.actor_id=e.created_by_id
    WHERE d.case_id=NEW.case_id AND e.case_id=NEW.case_id AND e.kind='planning_readiness' AND s.kind='scope_baseline'
    AND e.body::jsonb->>'packet_id'=NEW.source_head_id::text AND e.body::jsonb->'inputs'->>'candidate_id'=d.candidate_id::text
    AND s.external_ref='psl:planning-readiness:'||e.id::text AND a.action='planning.recorded'
    AND a.data=jsonb_build_object('kind','ready','evidence_id',e.id,'sha256',e.sha256))
  THEN RAISE EXCEPTION 'Native planning readiness and delivery source required'; END IF;
  IF NEW.definition='commercial/v1' AND NOT EXISTS(
    SELECT 1 FROM pmo_commercialdocumentbinding b JOIN documents_version v ON v.id=b.version_id JOIN documents_document doc ON doc.id=v.document_id
    JOIN documents_publication p ON p.version_id=v.id JOIN pmo_commercialrevision r ON r.id=b.revision_id
    JOIN pmo_commercialcase c ON c.id=r.dossier_id JOIN pmo_costingbinding cb ON cb.costing_id=(r.sources->>'costing')::bigint
    JOIN pmo_costingrun cr ON cr.id=cb.run_id JOIN core_evidence e ON e.id=NEW.source_head_id
    WHERE c.case_id=NEW.case_id AND doc.case_id=NEW.case_id AND cr.case_id=NEW.case_id AND c.current_id=r.id AND cr.result->>'status'='known'
    AND r.sources->'requirements'=e.body::jsonb->'sources'->'requirements' AND r.sources->'plan'=e.body::jsonb->'sources'->'plan'
    AND r.sources->'engineering_estimate'=e.body::jsonb->'sources'->'engineering_estimate' AND r.sources->'security_estimate'=e.body::jsonb->'sources'->'security_estimate'
    AND r.sources->'sow'=e.body::jsonb->'sources'->'sow' AND cr.evidence_id::text=e.body::jsonb->'sources'->>'inputs'
    AND jsonb_array_length(p.recipient_ids)>0 AND NOT EXISTS(
      SELECT 1 FROM jsonb_array_elements_text(p.recipient_ids) AS destinations(recipient) WHERE NOT EXISTS(
       SELECT 1 FROM documents_publicationreceipt pr WHERE pr.publication_id=p.id AND pr.recipient_id::text=destinations.recipient
       AND pr.payload_sha256=v.payload_sha256 AND pr.payload=v.payload)))
  THEN RAISE EXCEPTION 'Exact native costing, commercial document and all recipient receipts required'; END IF;
 END IF;

 IF NEW.definition='delivery-release/v1' AND NEW.status='verified' AND NOT EXISTS(
  SELECT 1 FROM pmo_deliveryrecord r JOIN pmo_deliverydossier d ON d.id=r.dossier_id
  JOIN workflows_factoryactivity fa ON fa.work_id=NEW.id JOIN workflows_factoryattempt a ON a.activity_id=fa.id
  WHERE d.id=(NEW.request->>'dossier')::bigint AND d.case_id=NEW.case_id AND r.kind='release_ready'
   AND r.snapshot->'deployment_authorized'='false'::jsonb AND r.snapshot->>'financial_controls'='independent'
   AND a.phase='observed' AND a.result->>'release_ready'=r.id::text AND a.result->>'head'=NEW.source_head_id::text)
 THEN RAISE EXCEPTION 'Native source-bound release evidence required; no deployment authority is granted'; END IF;

 IF NEW.definition='delivery-hypercare/v1' AND NEW.status='verified' AND NOT EXISTS(
  SELECT 1 FROM pmo_deliveryrecord r JOIN pmo_deliverydossier d ON d.id=r.dossier_id
  JOIN workflows_factoryactivity fa ON fa.work_id=NEW.id JOIN workflows_factoryattempt a ON a.activity_id=fa.id
  WHERE d.id=(NEW.request->>'dossier')::bigint AND d.case_id=NEW.case_id AND r.kind='hypercare'
   AND r.snapshot->'qualified'='true'::jsonb
   AND a.phase='observed' AND a.result->>'hypercare'=r.id::text AND a.result->>'head'=NEW.source_head_id::text)
 THEN RAISE EXCEPTION 'Native source-bound qualified hypercare required; no closure or release authority is granted'; END IF;

 IF NEW.definition='delivery-archive/v1' AND NEW.status='verified' AND NOT EXISTS(
  SELECT 1 FROM pmo_deliveryrecord r JOIN pmo_deliverydossier d ON d.id=r.dossier_id
  JOIN core_evidence e ON e.id=NEW.source_head_id
  JOIN workflows_factoryactivity fa ON fa.work_id=NEW.id JOIN workflows_factoryattempt a ON a.activity_id=fa.id
  WHERE d.id=(NEW.request->>'dossier')::bigint AND d.case_id=NEW.case_id AND r.kind='archive'
   AND r.data->'inventory'=e.body::jsonb->'inventory'
   AND r.snapshot->'physical_purge_performed'='false'::jsonb
   AND r.snapshot->>'repository'='internal-versioned'
   AND a.phase='observed' AND a.result->>'archive'=r.id::text AND a.result->>'head'=NEW.source_head_id::text)
 THEN RAISE EXCEPTION 'Exact observed native archive index required; no physical purge or closure authority'; END IF;

 IF NEW.definition='delivery-handover/v1' AND NEW.status='verified' AND NOT EXISTS(
  SELECT 1 FROM documents_publication p JOIN documents_publicationreceipt r ON r.publication_id=p.id
  JOIN pmo_deliverydocumentbinding b ON b.version_id=p.version_id
  JOIN pmo_deliveryrecord h ON h.dossier_id=b.dossier_id AND h.kind='handover'
  JOIN workflows_factoryactivity fa ON fa.work_id=NEW.id JOIN workflows_factoryattempt a ON a.activity_id=fa.id
  WHERE p.factory_work_id=NEW.id AND p.factory_source_id=NEW.source_head_id AND b.purpose='handover'
   AND b.dossier_id=(NEW.request->>'dossier')::bigint AND h.data->>'receipt_id'=r.id::text
   AND h.data->>'status'='received' AND h.actor_id=r.recipient_id
   AND a.phase='observed' AND fa.kind='ACT13' AND a.result->'verified'='true'::jsonb
   AND a.result->>'publication'=p.id::text AND a.result->>'head'=NEW.source_head_id::text)
 THEN RAISE EXCEPTION 'Observed exact native handover and actual recipient acknowledgement required'; END IF;

 IF NEW.definition='delivery-closure/v1' AND NEW.status='verified' AND NOT EXISTS(
  SELECT 1 FROM pmo_deliveryrecord c JOIN pmo_deliverydocumentbinding b ON b.version_id=(c.data->>'version_id')::bigint
  JOIN documents_version v ON v.id=b.version_id
  JOIN pmo_deliveryrecord decision ON decision.id=(c.data->>'decision_id')::bigint
  JOIN core_evidence head ON head.id=NEW.source_head_id
  JOIN workflows_factoryactivity fa ON fa.work_id=NEW.id AND fa.kind='ACT13'
  JOIN workflows_factoryattempt a ON a.activity_id=fa.id AND a.phase='observed'
  WHERE c.dossier_id=(NEW.request->>'dossier')::bigint AND c.kind='closure' AND b.dossier_id=c.dossier_id AND b.purpose='closure'
   AND decision.dossier_id=c.dossier_id AND decision.kind='closure_decision' AND decision.data->>'verdict'='approve'
   AND decision.data->>'version_id'=v.id::text AND decision.snapshot=b.snapshot AND c.snapshot=b.snapshot
   AND b.data=(head.body::jsonb->'inputs')-'template_id' AND v.template_id=(head.body::jsonb->'inputs'->>'template_id')::bigint
   AND a.result->'verified'='true'::jsonb AND a.result->>'closure'=c.id::text
   AND a.result->>'document_version'=v.id::text AND a.result->>'head'=NEW.source_head_id::text)
 THEN RAISE EXCEPTION 'Observed exact native closure, prescribed decision and current source binding required'; END IF;

 IF NEW.definition='delivery-go-live/v1' AND NEW.status='verified' AND NOT EXISTS(
  SELECT 1 FROM documents_publication p JOIN documents_publicationreceipt r ON r.publication_id=p.id
  JOIN documents_version v ON v.id=p.version_id JOIN pmo_deliverydocumentbinding b ON b.version_id=v.id
  JOIN pmo_deliveryrecord g ON g.dossier_id=b.dossier_id AND g.kind IN ('go_live','go_live_reaffirmation')
  JOIN core_evidence pm ON pm.id=(g.data->>'pm_signature_id')::bigint
  JOIN core_evidence client ON client.id=(g.data->>'client_signature_id')::bigint
  JOIN core_evidence head ON head.id=NEW.source_head_id
  JOIN workflows_factoryactivity fa ON fa.work_id=NEW.id AND fa.kind='ACT13'
  JOIN workflows_factoryattempt a ON a.activity_id=fa.id AND a.phase='observed'
  WHERE p.factory_work_id=NEW.id AND p.factory_source_id=NEW.source_head_id AND b.purpose='go_live' AND v.audience='client'
   AND b.dossier_id=(NEW.request->>'dossier')::bigint AND g.data->>'receipt_id'=r.id::text AND g.snapshot=b.snapshot
   AND b.data=(head.body::jsonb->'inputs')-'template_id' AND v.template_id=(head.body::jsonb->'inputs'->>'template_id')::bigint
   AND pm.case_id=NEW.case_id AND client.case_id=NEW.case_id AND pm.kind='signature' AND client.kind='signature' AND pm.id<>client.id
   AND a.result->'verified'='true'::jsonb AND a.result->>'acceptance'=g.id::text
   AND a.result->>'document_version'=v.id::text AND a.result->>'head'=NEW.source_head_id::text)
 THEN RAISE EXCEPTION 'Observed exact native go-live acceptance, distinct actual signature evidence and source-bound client receipt required'; END IF;

 IF NEW.definition='finance-accounts/v1' AND NEW.status='verified' AND NOT EXISTS(
  SELECT 1 FROM finance_financerun r JOIN finance_financesource s ON s.id=r.source_id
  JOIN finance_financedocumentbinding b ON b.run_id=r.id
  JOIN documents_version v ON v.id=b.version_id JOIN documents_document d ON d.id=v.document_id
  JOIN documents_publication p ON p.version_id=v.id JOIN documents_publicationjob j ON j.publication_id=p.id
  JOIN core_evidence h ON h.id=NEW.source_head_id
  JOIN workflows_factoryactivity fa ON fa.work_id=NEW.id AND fa.kind='ACT13'
  JOIN workflows_factoryattempt a ON a.activity_id=fa.id AND a.phase='observed'
  WHERE r.case_id=NEW.case_id AND s.case_id=NEW.case_id AND d.case_id=NEW.case_id AND r.kind='formula'
   AND s.id=(h.body::jsonb->>'source')::bigint AND s.batch_id=(NEW.request->>'batch')::bigint
   AND (p.factory_work_id=NEW.id AND p.factory_source_id=NEW.source_head_id OR p.factory_work_id IS NULL)
   AND d.current_id=v.id AND j.status='confirmed' AND jsonb_array_length(p.recipient_ids)>0
   AND NOT EXISTS(SELECT 1 FROM jsonb_array_elements_text(p.recipient_ids) x WHERE NOT EXISTS(
    SELECT 1 FROM documents_publicationreceipt pr WHERE pr.publication_id=p.id AND pr.recipient_id=x.value::bigint))
   AND (SELECT count(*) FROM documents_publicationreceipt pr WHERE pr.publication_id=p.id)=jsonb_array_length(p.recipient_ids)
   AND EXISTS(SELECT 1 FROM finance_financereview fr WHERE fr.run_id=r.id AND fr.purpose='output' AND fr.verdict='approve'
    AND fr.id=(SELECT max(last.id) FROM finance_financereview last WHERE last.run_id=r.id AND last.purpose='output'))
   AND a.result->'verified'='true'::jsonb AND a.result->>'run'=r.id::text AND a.result->>'source'=s.id::text
   AND a.result->>'binding'=b.id::text AND a.result->>'publication'=p.id::text AND a.result->>'document_version'=v.id::text
   AND a.result->'receipt_ids'=(SELECT jsonb_agg(pr.id ORDER BY pr.id) FROM documents_publicationreceipt pr WHERE pr.publication_id=p.id)) AND NOT EXISTS(
  SELECT 1 FROM finance_financerun r JOIN finance_financesource s ON s.id=r.source_id
  JOIN finance_financedocumentbinding b ON b.run_id=r.id
  JOIN documents_version v ON v.id=b.version_id JOIN documents_document d ON d.id=v.document_id
  JOIN documents_publication p ON p.version_id=v.id JOIN documents_publicationjob j ON j.publication_id=p.id
  JOIN core_evidence h ON h.id=NEW.source_head_id
  JOIN workflows_factoryactivity fa ON fa.work_id=NEW.id AND fa.kind='ACT13'
  JOIN workflows_factoryattempt a ON a.activity_id=fa.id AND a.phase='observed'
  WHERE r.case_id=NEW.case_id AND s.case_id=NEW.case_id AND d.case_id=NEW.case_id AND r.kind='statement'
   AND s.id=(h.body::jsonb->>'source')::bigint AND s.batch_id=(NEW.request->>'batch')::bigint
   AND (p.factory_work_id=NEW.id AND p.factory_source_id=NEW.source_head_id OR p.factory_work_id IS NULL)
   AND d.current_id=v.id AND j.status='confirmed' AND jsonb_array_length(p.recipient_ids)>0
   AND NOT EXISTS(SELECT 1 FROM jsonb_array_elements_text(p.recipient_ids) x WHERE NOT EXISTS(
    SELECT 1 FROM documents_publicationreceipt pr WHERE pr.publication_id=p.id AND pr.recipient_id=x.value::bigint))
   AND (SELECT count(*) FROM documents_publicationreceipt pr WHERE pr.publication_id=p.id)=jsonb_array_length(p.recipient_ids)
   AND EXISTS(SELECT 1 FROM finance_financereview fr WHERE fr.run_id=r.id AND fr.purpose='output' AND fr.verdict='approve'
    AND fr.id=(SELECT max(last.id) FROM finance_financereview last WHERE last.run_id=r.id AND last.purpose='output'))
   AND a.result->'verified'='true'::jsonb AND a.result->>'run'=r.id::text AND a.result->>'source'=s.id::text
   AND a.result->>'binding'=b.id::text AND a.result->>'publication'=p.id::text AND a.result->>'document_version'=v.id::text
   AND a.result->'receipt_ids'=(SELECT jsonb_agg(pr.id ORDER BY pr.id) FROM documents_publicationreceipt pr WHERE pr.publication_id=p.id)
   AND EXISTS(SELECT 1 FROM policy_configuration pc JOIN policy_registeredreference pr ON pr.case_id=pc.case_id
    AND pr.ref=pc.envelope->'value'->>'artifact_ref' AND pr.version=(pc.envelope->'value'->>'artifact_version')::integer
    AND pr.sha256=pc.envelope->'value'->>'sha256'
    WHERE pc.id=NEW.policy_id AND pc.component='OPS.factory_accounting_execution'
     AND pr.schema_ref='schema:psl/factory-accounting-execution/v3' AND pr.content->>'statement_contract_id'=r.request->>'contract_id')
   AND r.result->>'status'='complete' AND r.result->>'scope'='selected_statement_lines'
   AND r.result->'whole_statement_certified'='false'::jsonb
   AND EXISTS(SELECT 1 FROM finance_financereview cr JOIN policy_configuration cc ON cc.id=cr.configuration_id
    WHERE cc.id=(r.request->>'contract_id')::bigint AND cc.case_id=r.case_id AND cc.component='D06.statement_contract'
     AND cr.purpose='formula' AND cr.verdict='approve'
     AND cr.id=(SELECT max(id) FROM finance_financereview WHERE configuration_id=cc.id AND purpose='formula')
     AND cr.id::text=r.snapshot->'reviews'->'D06.statement_contract'->>'id'
     AND (SELECT state FROM policy_policystate WHERE configuration_id=cc.id ORDER BY id DESC LIMIT 1)='active')
   AND jsonb_array_length(r.snapshot->'inputs')>0
   AND (SELECT count(*) FROM finance_financestatementinput si WHERE si.statement_id=r.id)=jsonb_array_length(r.snapshot->'inputs')
   AND NOT EXISTS(SELECT 1 FROM finance_financestatementinput si
    JOIN finance_financerun sr ON sr.id=si.source_run_id
    JOIN finance_financereview rv ON rv.id=si.source_review_id
    JOIN finance_financesource ss ON ss.id=sr.source_id
    WHERE si.statement_id=r.id AND (sr.case_id<>r.case_id OR rv.run_id<>sr.id OR rv.verdict<>'approve'
     OR rv.id<>(SELECT max(id) FROM finance_financereview WHERE run_id=sr.id AND purpose='output')
     OR sr.result->>'period'<>r.result->>'period' OR sr.result->>'entity'<>r.result->>'entity'
     OR sr.result->>'currency'<>r.result->>'currency' OR ss.accounting_basis IS DISTINCT FROM r.result->>'accounting_basis'
     OR si.declaration->>'source_sign' IS NULL OR si.declaration->>'source_sign' IS DISTINCT FROM si.declaration->>'destination_sign'
     OR sr.result->'company'->si.metric->'value' IS DISTINCT FROM r.result->'company'->si.destination->'value'
     OR sr.result->'company'->si.metric->>'unit' IS DISTINCT FROM si.declaration->>'unit'))
)
 THEN RAISE EXCEPTION 'Current native accounting binding/output review and all exact recipient receipts required'; END IF;

 IF TG_OP='UPDATE' AND NEW.definition IN ('delivery-release/v1','delivery-hypercare/v1')
 AND NEW.source_head_id IS DISTINCT FROM OLD.source_head_id THEN
  IF NEW.cancel_requested OR OLD.status IN ('cancelled','followup_needed') OR NEW.status<>'ready'
   OR (OLD.lease_until IS NOT NULL AND OLD.lease_until>statement_timestamp())
   OR NOT EXISTS(SELECT 1 FROM core_evidence n JOIN core_evidence o ON o.id=OLD.source_head_id
     JOIN core_audit a ON a.case_id=n.case_id AND a.actor_id=n.created_by_id
     JOIN core_evidence e ON e.case_id=n.case_id AND a.data->'evidence'=to_jsonb(e.id)
     WHERE n.id=NEW.source_head_id AND n.body=o.body AND n.version>o.version
      AND a.action='factory.delivery_intake_reaffirmed' AND a.data->>'work'=NEW.id::text
      AND a.data->>'previous'=OLD.source_head_id::text AND a.data->>'current'=n.id::text
      AND length(btrim(a.data->>'reason')) BETWEEN 1 AND 2000
      AND coalesce(a.data->>'packet','') ~ '^[a-f0-9]{64}$')
   OR EXISTS(SELECT 1 FROM workflows_factoryattempt a JOIN workflows_factoryactivity t ON t.id=a.activity_id
     WHERE t.work_id=NEW.id AND t.kind='ACT03' AND a.phase='started' AND a.result->>'schema'='factory-provider-request/v1'
      AND NOT EXISTS(SELECT 1 FROM workflows_factoryattempt done WHERE done.activity_id=a.activity_id AND done.number=a.number AND done.phase IN ('observed','failed'))
      AND NOT EXISTS(SELECT 1 FROM workflows_factoryplanningreceipt WHERE attempt_id=a.id))
  THEN RAISE EXCEPTION 'Exact fresh human source instruction and reconciled original effects required'; END IF;
 END IF;

 IF NEW.definition='rfp-response/v1' THEN
  IF NEW.invoice_id IS NOT NULL OR NEW.preparation_id IS NOT NULL OR NOT EXISTS(
   SELECT 1 FROM core_evidence e JOIN core_audit a ON a.case_id=e.case_id AND a.actor_id=e.created_by_id
   JOIN pmo_rfpcase r ON r.id=(NEW.request->>'rfp')::bigint AND r.case_id=NEW.case_id
   JOIN pmo_rfpintake i ON i.id=(e.body::jsonb->>'intake')::bigint AND i.rfp_id=r.id
   WHERE e.id=NEW.source_head_id AND e.case_id=NEW.case_id AND e.kind='agent_private_rfp_intake'
    AND e.body::jsonb->>'schema'='factory-rfp-intake/v1' AND e.body::jsonb->'rfp'=NEW.request->'rfp'
    AND NEW.request-ARRAY['rfp','reference']='{}'::jsonb
    AND e.body::jsonb-ARRAY['schema','rfp','intake','response_evidence','public_terms','sources','matrix','lessons']='{}'::jsonb
    AND jsonb_typeof(e.body::jsonb->'sources')='object' AND jsonb_typeof(e.body::jsonb->'matrix')='array'
    AND a.action='factory.rfp_inputs_recorded' AND a.data=jsonb_build_object('evidence_id',e.id,'sha256',e.sha256))
  THEN RAISE EXCEPTION 'Exact native same-case RFP instruction provenance required'; END IF;
  IF TG_OP='UPDATE' AND NEW.source_head_id IS DISTINCT FROM OLD.source_head_id THEN
   IF OLD.status IN ('verified','cancelled','followup_needed') OR NEW.cancel_requested OR NEW.status<>'ready'
    OR (OLD.lease_until IS NOT NULL AND OLD.lease_until>statement_timestamp())
    OR NOT EXISTS(SELECT 1 FROM core_audit a JOIN core_evidence e ON e.id=NEW.source_head_id AND e.created_by_id=a.actor_id
      WHERE a.case_id=NEW.case_id AND a.action='factory.rfp_instruction_changed'
       AND a.data->>'work'=NEW.id::text AND a.data->>'previous'=OLD.source_head_id::text
       AND a.data->>'current'=NEW.source_head_id::text AND length(btrim(a.data->>'reason')) BETWEEN 1 AND 4000)
    OR EXISTS(SELECT 1 FROM documents_publication p JOIN documents_publicationjob j ON j.publication_id=p.id
      WHERE p.factory_work_id=NEW.id AND (j.status IN ('pending','unknown','leased','held') OR
       j.status='confirmed' AND NOT EXISTS(SELECT 1 FROM pmo_rfpsubmission s WHERE s.version_id=p.version_id)))
    OR EXISTS(SELECT 1 FROM workflows_factoryattempt a JOIN workflows_factoryactivity t ON t.id=a.activity_id
      WHERE t.work_id=NEW.id AND t.kind='ACT03' AND a.phase='started' AND a.result->>'schema'='factory-provider-request/v1'
       AND NOT EXISTS(SELECT 1 FROM workflows_factoryattempt done WHERE done.activity_id=a.activity_id AND done.number=a.number AND done.phase IN ('observed','failed'))
       AND NOT EXISTS(SELECT 1 FROM workflows_factoryplanningreceipt pr WHERE pr.attempt_id=a.id))
   THEN RAISE EXCEPTION 'Fresh human RFP instruction and reconciled original effects required'; END IF;
  END IF;

  IF NEW.status='verified' AND NOT EXISTS(
   SELECT 1 FROM pmo_rfpdisposition d JOIN pmo_rfpoutcome o ON o.id=d.outcome_id
   JOIN pmo_rfpsubmission s ON s.id=o.submission_id JOIN pmo_rfpresponse r ON r.id=s.response_id
   JOIN pmo_rfpcase root ON root.id=r.rfp_id JOIN core_evidence h ON h.id=NEW.source_head_id
   JOIN pmo_commercialrevision cr ON cr.id=r.commercial_id
   JOIN pmo_rfpdocumentbinding b ON b.response_id=r.id AND b.version_id=s.version_id
   JOIN documents_version v ON v.id=s.version_id JOIN documents_document doc ON doc.id=v.document_id
   JOIN documents_publication p ON p.version_id=v.id JOIN documents_publicationjob j ON j.publication_id=p.id
   JOIN documents_controlledreview review ON review.id=p.review_id AND review.version_id=v.id
   JOIN workflows_factoryactivity t ON t.work_id=NEW.id AND t.kind='ACT13'
   JOIN workflows_factoryattempt a ON a.activity_id=t.id AND a.phase='observed'
   WHERE root.case_id=NEW.case_id AND root.id=(NEW.request->>'rfp')::bigint AND d.rfp_id=root.id
    AND doc.case_id=NEW.case_id AND s.snapshot=b.snapshot AND s.snapshot->>'response'=r.id::text
    AND s.snapshot->'sources'=r.snapshot AND d.snapshot->'sources'=r.snapshot AND d.snapshot->'commercial_sources'=cr.sources
    AND jsonb_array_length(s.snapshot->'reviews')=2 AND NOT EXISTS(
     SELECT 1 FROM jsonb_array_elements_text(s.snapshot->'reviews') WITH ORDINALITY item(id,nth)
     WHERE NOT EXISTS(SELECT 1 FROM pmo_rfpreview rr WHERE rr.id=item.id::bigint AND rr.response_id=r.id AND rr.verdict='approve'
      AND rr.role=CASE item.nth WHEN 1 THEN 'PMO Lead' WHEN 2 THEN 'Engineering Lead' END AND rr.created_at<=p.created_at))
    AND jsonb_array_length(s.snapshot->'costing_decisions')=3 AND NOT EXISTS(
     SELECT 1 FROM jsonb_array_elements_text(s.snapshot->'costing_decisions') WITH ORDINALITY item(id,nth)
     WHERE NOT EXISTS(SELECT 1 FROM pmo_commercialdecision cd WHERE cd.id=item.id::bigint AND cd.revision_id=cr.id AND cd.verdict='approve'
      AND cd.role=CASE item.nth WHEN 1 THEN 'PM' WHEN 2 THEN 'Head of PMO' WHEN 3 THEN 'CEO' END AND cd.created_at<=p.created_at))
    AND review.verdict='approve' AND review.payload_sha256=v.payload_sha256 AND review.created_at<=p.created_at
    AND j.status='confirmed' AND jsonb_array_length(p.recipient_ids)>0
    AND (p.factory_work_id=NEW.id OR p.factory_work_id IS NULL)
    AND (p.factory_work_id IS NULL OR EXISTS(SELECT 1 FROM core_evidence origin WHERE origin.id=p.factory_source_id
     AND origin.case_id=NEW.case_id AND origin.kind='agent_private_rfp_intake' AND origin.body::jsonb->'rfp'=NEW.request->'rfp'))
    AND d.snapshot->>'response'=r.id::text AND d.snapshot->>'submission'=s.id::text AND d.snapshot->>'outcome'=o.id::text
    AND d.snapshot->>'case'=NEW.case_id::text AND d.snapshot->'baseline_imported'='false'::jsonb
    AND (d.kind='route_a' AND o.result='won' AND d.snapshot->>'route'='A' OR
     d.kind='loss_archive' AND o.result='lost' AND d.lessons_id=(h.body::jsonb->>'lessons')::bigint)
    AND NOT EXISTS(SELECT 1 FROM jsonb_array_elements_text(p.recipient_ids) x WHERE NOT EXISTS(
     SELECT 1 FROM documents_publicationreceipt pr WHERE pr.publication_id=p.id AND pr.recipient_id=x.value::bigint AND pr.payload=v.payload AND pr.payload_sha256=v.payload_sha256))
    AND s.receipt_ids=(SELECT jsonb_agg(pr.id ORDER BY pr.id) FROM documents_publicationreceipt pr WHERE pr.publication_id=p.id)
    AND (SELECT count(*) FROM documents_publicationreceipt pr WHERE pr.publication_id=p.id)=jsonb_array_length(p.recipient_ids)
    AND a.result->'verified'='true'::jsonb AND a.result->>'head'=NEW.source_head_id::text
    AND a.result->>'response'=r.id::text AND a.result->>'disposition'=d.id::text AND a.result->>'submission'=s.id::text
    AND a.result->>'outcome'=o.id::text AND a.result->>'document_version'=v.id::text
    AND a.result->>'publication'=p.id::text AND a.result->'receipt_ids'=s.receipt_ids)
  THEN RAISE EXCEPTION 'Historical approved RFP submission, actual customer outcome and all exact receipts required'; END IF;

 END IF;

 IF NEW.definition='pmo-change/v1' AND NEW.status='verified' AND NOT EXISTS(
  SELECT 1 FROM core_evidence e JOIN pmo_changeauthorization ca ON ca.id=(e.body::jsonb->'inputs'->>'authorization_id')::bigint
  JOIN pmo_changeversion cv ON cv.id=ca.version_id JOIN pmo_changerequest cr ON cr.id=cv.change_id
  JOIN pmo_changeclosure cc ON cc.authorization_id=ca.id
  JOIN documents_publicationreceipt r ON r.id=cc.receipt_id JOIN documents_publication p ON p.id=r.publication_id
  JOIN pmo_changedocumentbinding b ON b.version_id=p.version_id AND b.authorization_id=ca.id AND b.purpose='go_live'
  JOIN workflows_factoryactivity fa ON fa.work_id=NEW.id AND fa.kind='ACT13'
  JOIN workflows_factoryattempt a ON a.activity_id=fa.id AND a.phase='observed'
  WHERE e.id=NEW.source_head_id AND cv.id=(e.body::jsonb->>'change_version_id')::bigint
   AND cr.case_id=NEW.case_id AND cr.current_id=cv.id AND cr.id=(NEW.request->>'change')::bigint
   AND p.factory_work_id=NEW.id AND p.factory_source_id=e.id
   AND cc.execution_ids=b.execution_ids AND cc.pm_signature_id<>cc.client_signature_id
   AND a.result->'verified'='true'::jsonb AND a.result->>'head'=e.id::text AND a.result->>'closure'=cc.id::text
   AND a.result->>'document_version'=p.version_id::text
   AND EXISTS(SELECT 1 FROM documents_publication np JOIN pmo_changedocumentbinding nb ON nb.version_id=np.version_id
    JOIN documents_publicationreceipt nr ON nr.publication_id=np.id
    WHERE np.factory_work_id=NEW.id AND np.factory_source_id=e.id AND nb.authorization_id=ca.id AND nb.purpose='notice')
   AND NOT EXISTS(SELECT 1 FROM jsonb_array_elements_text(p.recipient_ids) recipient
    WHERE NOT EXISTS(SELECT 1 FROM documents_publicationreceipt pr WHERE pr.publication_id=p.id AND pr.recipient_id=recipient::bigint)))
 THEN RAISE EXCEPTION 'Observed exact native change closure and controlled recipient receipts required'; END IF;

 IF NEW.definition='pmo-emergency/v1' AND NEW.status='verified' AND NOT EXISTS(
  SELECT 1 FROM core_evidence e JOIN pmo_emergencyprofile ep ON ep.id=(e.body::jsonb->>'profile_id')::bigint
  JOIN pmo_emergencyoutcome o ON o.id=(e.body::jsonb->'inputs'->>'outcome_id')::bigint AND o.profile_id=ep.id
  JOIN pmo_emergencyauthorization ea ON ea.id=o.authorization_id AND ea.profile_id=ep.id
  JOIN pmo_emergencyretrospectiverecord rr ON rr.outcome_id=o.id
  JOIN pmo_changeversion cv ON cv.id=ep.version_id JOIN pmo_changerequest cr ON cr.id=cv.change_id
  JOIN pmo_emergencydocumentbinding b ON b.outcome_id=o.id
  JOIN documents_version v ON v.id=b.version_id JOIN documents_publication p ON p.version_id=v.id
  JOIN workflows_factoryactivity fa ON fa.work_id=NEW.id AND fa.kind='ACT13'
  JOIN workflows_factoryattempt a ON a.activity_id=fa.id AND a.phase='observed'
  WHERE e.id=NEW.source_head_id AND cr.case_id=NEW.case_id AND cr.id=(NEW.request->>'change')::bigint AND cr.current_id=cv.id
   AND ea.id=(e.body::jsonb->'inputs'->>'authorization_id')::bigint AND ea.created_at<=o.implemented_at
   AND rr.snapshot->>'authorization_id'=ea.id::text AND rr.snapshot->>'status' IN ('evidenced_on_time','completed_with_lateness_exception')
   AND b.manifest->>'reconciliation_id'=rr.id::text AND b.manifest->>'outcome_id'=o.id::text
   AND p.factory_work_id=NEW.id AND p.factory_source_id=e.id AND v.template_id=(e.body::jsonb->'inputs'->>'template_id')::bigint
   AND v.audience=e.body::jsonb->'inputs'->>'audience'
   AND a.result->'verified'='true'::jsonb AND a.result->>'head'=e.id::text AND a.result->>'retrospective_record'=rr.id::text
   AND a.result->>'document_version'=v.id::text AND a.result->>'retrospective_status'=rr.snapshot->>'status'
   AND EXISTS(SELECT 1 FROM documents_publicationreceipt pr WHERE pr.publication_id=p.id)
   AND NOT EXISTS(SELECT 1 FROM jsonb_array_elements_text(p.recipient_ids) recipient
    WHERE NOT EXISTS(SELECT 1 FROM documents_publicationreceipt pr WHERE pr.publication_id=p.id AND pr.recipient_id=recipient::bigint)))
 THEN RAISE EXCEPTION 'Observed exact native Emergency retrospective and every report receipt required; deployment and ordinary closure are not granted'; END IF;

 IF NEW.definition='finance-payroll/v1' AND NEW.status='verified' AND NOT EXISTS(
  SELECT 1 FROM core_evidence e JOIN finance_payrollrequest q ON q.id=(e.body::jsonb->>'request_id')::bigint
   JOIN finance_payrollrun ar ON ar.request_id=q.id AND ar.kind='aggregate'
   JOIN finance_payrollrun mr ON mr.id=ar.parent_id AND mr.kind='match'
   JOIN finance_payrollrun cr ON cr.id=mr.parent_id AND cr.kind='combine'
   JOIN finance_payrollpublication p ON p.run_id=ar.id AND p.request_id=q.id
   JOIN finance_payrollreview rv ON rv.id=p.review_id AND rv.run_id=ar.id
   JOIN workflows_factoryactivity fa ON fa.work_id=NEW.id AND fa.kind='ACT13'
   JOIN workflows_factoryattempt a ON a.activity_id=fa.id AND a.phase='observed'
   JOIN policy_configuration pc ON pc.id=(p.policy_ids->>'F18.reporting_rules')::bigint
   JOIN policy_registeredreference pr ON pr.case_id=pc.case_id AND pr.ref=pc.envelope->'value'->>'artifact_ref'
    AND pr.version=(pc.envelope->'value'->>'artifact_version')::integer AND pr.sha256=pc.envelope->'value'->>'sha256'
  WHERE e.id=NEW.source_head_id AND q.case_id=NEW.case_id AND q.reference=NEW.request->>'payroll_reference'
   AND cr.request_id=q.id AND mr.request_id=q.id
   AND (cr.metadata->'input_ids') @> (e.body::jsonb->'inputs'->'input_ids')
   AND (cr.metadata->'input_ids') <@ (e.body::jsonb->'inputs'->'input_ids')
   AND mr.hr_snapshot_id=(e.body::jsonb->'inputs'->>'hr_snapshot_id')::bigint
   AND ar.metadata->>'status'='complete' AND mr.metadata->>'status'='complete' AND cr.metadata->>'status'='complete'
   AND rv.verdict='approve' AND rv.subject_sha256=ar.sha256
   AND rv.id=(SELECT max(id) FROM finance_payrollreview WHERE run_id=ar.id)
   AND p.payload->'by_bu'=ar.result->'by_bu' AND p.payload->'eligible_total'=ar.result->'eligible_total'
   AND p.payload->>'source_run'=ar.id::text AND p.payload->>'disclosure'='aggregate_only'
   AND NOT (p.payload ? 'rows') AND p.payload->'hr_written'='false'::jsonb AND p.payload->'ledger_posted'='false'::jsonb
   AND NOT EXISTS(SELECT 1 FROM finance_payrollpublication newer WHERE newer.request_id=q.id AND newer.version>p.version)
   AND NOT EXISTS(SELECT 1 FROM finance_payrollrequest newer WHERE newer.case_id=q.case_id AND newer.reference=q.reference AND newer.version>q.version)
   AND a.result->'verified'='true'::jsonb AND a.result->>'head'=e.id::text AND a.result->>'publication'=p.id::text
   AND a.result->>'run'=ar.id::text AND a.result->>'request'=q.id::text
   AND jsonb_array_length(pr.content->'recipient_ids')>0
   AND NOT EXISTS(SELECT 1 FROM jsonb_array_elements_text(pr.content->'recipient_ids') recipient
     WHERE NOT EXISTS(SELECT 1 FROM finance_payrollreportreceipt rr WHERE rr.publication_id=p.id AND rr.actor_id=recipient::bigint
       AND a.result->'receipt_ids' @> to_jsonb(ARRAY[rr.id]))))
 THEN RAISE EXCEPTION 'Observed exact payroll aggregate and actual recipient-owned receipts required'; END IF;

 IF NEW.definition='finance-forecast/v1' AND NOT EXISTS(
  SELECT 1 FROM core_evidence e JOIN core_audit a ON a.case_id=e.case_id AND a.actor_id=e.created_by_id
  JOIN finance_forecastscenario s ON s.id=(e.body::jsonb->>'scenario_id')::bigint
  WHERE e.id=NEW.source_head_id AND e.case_id=NEW.case_id AND s.case_id=NEW.case_id
   AND e.kind='agent_private_forecast_intake' AND e.body::jsonb->>'protocol'='factory-forecast-selection/v1'
   AND s.reference=NEW.request->>'scenario_reference'
   AND e.body::jsonb-ARRAY['protocol','scenario_id','as_of','months','source_ids','template_id','audience']='{}'::jsonb
   AND e.body::jsonb->>'audience' IN ('internal','management','group')
   AND jsonb_typeof(e.body::jsonb->'source_ids')='array'
   AND jsonb_array_length(e.body::jsonb->'source_ids')=(SELECT count(*) FROM (
    SELECT s.evidence_id AS id UNION SELECT (item->>'evidence_id')::bigint FROM jsonb_array_elements(s.payload->'openings') item
    UNION SELECT (item->>'evidence_id')::bigint FROM jsonb_array_elements(s.payload->'items') item) exact_sources)
   AND NOT EXISTS(SELECT id FROM (
    SELECT s.evidence_id AS id UNION SELECT (item->>'evidence_id')::bigint FROM jsonb_array_elements(s.payload->'openings') item
    UNION SELECT (item->>'evidence_id')::bigint FROM jsonb_array_elements(s.payload->'items') item) exact_sources
    WHERE NOT e.body::jsonb->'source_ids' @> jsonb_build_array(id))
   AND (e.body::jsonb->'template_id'='null'::jsonb OR EXISTS(SELECT 1 FROM documents_template t
    WHERE t.id=(e.body::jsonb->>'template_id')::bigint AND t.case_id=NEW.case_id AND t.definition->>'document_type'=CASE WHEN e.body::jsonb->>'audience'='group' THEN 'finance_group_report' ELSE 'finance_report' END))
   AND e.body::jsonb->>'as_of'=s.payload->>'as_of' AND e.body::jsonb->'months'=s.payload->'months'
   AND a.action IN ('factory.forecast_intake','factory.forecast_source')
   AND a.data=jsonb_build_object('evidence_id',e.id,'sha256',e.sha256)
   AND NEW.invoice_id IS NULL AND NEW.preparation_id IS NULL)
 THEN RAISE EXCEPTION 'Exact native forecast intake provenance required'; END IF;
 IF NEW.definition='finance-forecast/v1' AND NEW.status='verified' AND NOT EXISTS(
  SELECT 1 FROM core_evidence e JOIN finance_forecastscenario s ON s.id=(e.body::jsonb->>'scenario_id')::bigint
  JOIN finance_forecastrun r ON r.scenario_id=s.id JOIN finance_forecastreview rv ON rv.run_id=r.id
  JOIN finance_forecastbinding b ON b.run_id=r.id JOIN documents_version v ON v.id=b.version_id
  JOIN documents_publication p ON p.version_id=v.id
  JOIN workflows_factoryactivity fa ON fa.work_id=NEW.id AND fa.kind='ACT13'
  JOIN workflows_factoryattempt a ON a.activity_id=fa.id AND a.phase='observed'
  WHERE e.id=NEW.source_head_id AND r.case_id=NEW.case_id AND s.case_id=NEW.case_id
   AND rv.verdict='approve' AND rv.id=(SELECT max(id) FROM finance_forecastreview WHERE run_id=r.id)
   AND NOT EXISTS(SELECT 1 FROM finance_forecastscenario newer WHERE newer.case_id=s.case_id AND newer.reference=s.reference AND newer.number>s.number)
   AND p.factory_work_id=NEW.id AND p.factory_source_id=e.id AND p.factory_policy_id=NEW.policy_id
   AND v.template_id=(e.body::jsonb->>'template_id')::bigint AND v.audience=e.body::jsonb->>'audience'
   AND b.snapshot->>'run_hash'=r.sha256 AND b.snapshot->>'output_review'=rv.id::text
   AND a.result->'verified'='true'::jsonb AND a.result->>'head'=e.id::text
   AND a.result->>'forecast_run'=r.id::text AND a.result->>'forecast_review'=rv.id::text
   AND a.result->>'document_version'=v.id::text AND a.result->>'publication'=p.id::text
   AND jsonb_array_length(p.recipient_ids)>0
   AND NOT EXISTS(SELECT 1 FROM jsonb_array_elements_text(p.recipient_ids) recipient WHERE NOT EXISTS(
    SELECT 1 FROM documents_publicationreceipt pr WHERE pr.publication_id=p.id AND pr.recipient_id=recipient::bigint
     AND pr.payload_sha256=v.payload_sha256 AND pr.payload=v.payload)))
 THEN RAISE EXCEPTION 'Observed exact native forecast approval and aggregate receipts required'; END IF;

 IF NEW.definition='finance-ppe/v1' AND NEW.status='verified' AND NOT EXISTS(
  SELECT 1 FROM core_evidence e
  JOIN finance_schedulework r ON r.id=(e.body::jsonb->>'register_id')::bigint
  JOIN finance_schedulework s ON s.case_id=NEW.case_id AND s.kind='ppe_schedule'
  JOIN finance_schedulereview sr ON sr.work_id=s.id AND sr.authority->>'purpose'='schedule'
  JOIN finance_schedulereview rr ON rr.work_id=r.id AND rr.authority->>'purpose'='register'
  JOIN workflows_factoryactivity fa ON fa.work_id=NEW.id AND fa.kind='ACT13'
  JOIN workflows_factoryattempt a ON a.activity_id=fa.id AND a.phase='observed'
  WHERE e.id=NEW.source_head_id AND s.payload->>'register_id'=r.id::text
   AND s.payload->'prior_id'=e.body::jsonb->'prior_id'
   AND s.parent_id IS NOT DISTINCT FROM (e.body::jsonb->>'ledger_id')::bigint
   AND s.reference=NEW.request->>'reference' AND s.result->>'status'='ready'
   AND psl_ppe_schedule_current(s.id) AND psl_ppe_review_current(sr.id)
   AND psl_ppe_policy_current(NEW.case_id,NEW.policy_id)
   AND psl_ppe_grants(NEW.case_id,e.created_by_id,ARRAY['case.read','finance.read','ppe.read','evidence.add'])
   AND EXISTS(SELECT 1 FROM core_audit intake WHERE intake.case_id=NEW.case_id AND intake.actor_id=e.created_by_id
    AND intake.data=jsonb_build_object('evidence_id',e.id,'sha256',e.sha256)
    AND ((intake.action='factory.ppe_intake' AND psl_ppe_grants(NEW.case_id,e.created_by_id,ARRAY['factory.start']))
     OR (intake.action='factory.ppe_source' AND psl_ppe_grants(NEW.case_id,e.created_by_id,ARRAY['factory.manage']))))
   AND sr.verdict='approve' AND rr.verdict='approve' AND sr.snapshot=s.snapshot AND rr.snapshot=r.snapshot
   AND sr.id=(SELECT max(id) FROM finance_schedulereview WHERE work_id=s.id AND authority->>'purpose'='schedule')
   AND rr.id=(SELECT max(id) FROM finance_schedulereview WHERE work_id=r.id AND authority->>'purpose'='register')
   AND NOT EXISTS(SELECT 1 FROM finance_schedulework newer WHERE newer.case_id=NEW.case_id AND
     ((newer.kind=r.kind AND newer.reference=r.reference AND newer.version>r.version) OR
      (newer.kind=s.kind AND newer.reference=s.reference AND newer.version>s.version)))
   AND a.result->'verified'='true'::jsonb AND a.result->>'head'=e.id::text
   AND a.result->>'schedule'=s.id::text AND a.result->>'schedule_sha256'=s.sha256
   AND a.result->>'schedule_review'=sr.id::text AND a.result->>'register_review'=rr.id::text
   AND a.result->'ledger'=COALESCE(to_jsonb(s.parent_id),'null'::jsonb)
   AND a.result->'ledger_posted'='false'::jsonb
   AND a.result->>'full_owner_oracle_acceptance'='unresolved'
   AND (s.parent_id IS NULL OR EXISTS(SELECT 1 FROM finance_financerun note
     JOIN finance_financereview source_review ON source_review.source_id=note.source_id AND source_review.purpose='source'
     WHERE note.id=s.parent_id AND note.case_id=NEW.case_id AND note.kind='mapping'
      AND source_review.verdict='approve'
      AND source_review.id=(SELECT max(id) FROM finance_financereview WHERE source_id=note.source_id AND purpose='source')
      AND note.snapshot->'source_review'->>'id'=source_review.id::text
      AND a.result->'ledger_reviews'=jsonb_build_object('source',note.snapshot->'source_review','rules',note.snapshot->'reviews')))
   AND s.snapshot->>'register_review'=rr.id::text
   AND NOT EXISTS(SELECT 1 FROM jsonb_each(s.snapshot->'policies') pin
     WHERE pin.value->>'status'<>'ACTIVE' OR NOT EXISTS(SELECT 1 FROM policy_configuration pc
      WHERE pc.id=(pin.value->>'id')::bigint AND pc.case_id=NEW.case_id AND pc.component=pin.key
       AND (SELECT state FROM policy_policystate WHERE configuration_id=pc.id ORDER BY id DESC LIMIT 1)='active'))
   AND NOT EXISTS(SELECT 1 FROM (VALUES(sr.actor_id),(rr.actor_id)) reviewer(id)
     WHERE NOT EXISTS(SELECT 1 FROM auth_user u JOIN identity_grant g ON g.user_id=u.id
      WHERE u.id=reviewer.id AND u.is_active AND g.case_id=NEW.case_id AND g.action='ppe.review' AND g.active)))
 THEN RAISE EXCEPTION 'Observed exact current human-reviewed PPE schedule and accounting note required'; END IF;

 IF NEW.definition='finance-schedules/v1' AND NEW.status='verified' AND NOT EXISTS(
  SELECT 1 FROM core_evidence e JOIN core_evidence supplied ON supplied.id=(e.body::jsonb->>'evidence_id')::bigint
  JOIN finance_schedulework s ON s.evidence_id=supplied.id AND s.case_id=NEW.case_id AND s.kind=NEW.request->>'kind' AND s.reference=NEW.request->>'reference'
  JOIN finance_schedulereview r ON r.work_id=s.id
  JOIN workflows_factoryactivity fa ON fa.work_id=NEW.id AND fa.kind='ACT13'
  JOIN workflows_factoryattempt a ON a.activity_id=fa.id AND a.phase='observed'
  WHERE e.id=NEW.source_head_id AND s.parent_id IS NOT DISTINCT FROM (e.body::jsonb->>'parent_id')::bigint
   AND s.payload=CASE WHEN s.kind='income' THEN e.body::jsonb->'payload' ELSE supplied.body::jsonb END
   AND s.result->>'status'='ready' AND psl_schedules_review_current(r.id)
   AND psl_schedules_policy_current(NEW.case_id,NEW.policy_id)
   AND psl_schedules_grants(NEW.case_id,e.created_by_id,ARRAY['case.read','finance.read','schedules.read','evidence.add'])
   AND EXISTS(SELECT 1 FROM core_audit intake WHERE intake.case_id=NEW.case_id AND intake.actor_id=e.created_by_id
    AND intake.data=jsonb_build_object('evidence_id',e.id,'sha256',e.sha256)
    AND ((intake.action='factory.schedules_intake' AND psl_schedules_grants(NEW.case_id,e.created_by_id,ARRAY['factory.start']))
     OR (intake.action='factory.schedules_source' AND psl_schedules_grants(NEW.case_id,e.created_by_id,ARRAY['factory.manage']))))
   AND a.result->'verified'='true'::jsonb AND a.result->>'head'=e.id::text
   AND a.result->>'schedule'=s.id::text AND a.result->>'schedule_sha256'=s.sha256
   AND a.result->>'schedule_review'=r.id::text AND a.result->>'source_evidence'=supplied.id::text
   AND a.result->'parent'=COALESCE(to_jsonb(s.parent_id),'null'::jsonb)
   AND a.result->'ledger_posted'='false'::jsonb AND a.result->'native_workbook_verified'='false'::jsonb)
 THEN RAISE EXCEPTION 'Observed exact current human-reviewed selected schedule required'; END IF;

 IF TG_OP='UPDATE' AND NEW.definition='finance-forecast/v1' AND NEW.source_head_id IS DISTINCT FROM OLD.source_head_id
 AND ((SELECT body::jsonb->>'audience'='group' FROM core_evidence WHERE id=NEW.source_head_id)
 IS DISTINCT FROM (SELECT body::jsonb->>'audience'='group' FROM core_evidence WHERE id=OLD.source_head_id))
 THEN RAISE EXCEPTION 'Separate group audience work identity is immutable'; END IF;

 IF NEW.definition='pmo-weekly-report/v1' AND NEW.status='verified' AND NOT EXISTS(
  SELECT 1 FROM documents_publication p JOIN documents_version v ON v.id=p.version_id
  JOIN documents_controlledreview rv ON rv.id=p.review_id
  JOIN workflows_factoryactivity fa ON fa.work_id=NEW.id AND fa.kind='ACT13'
  JOIN workflows_factoryattempt a ON a.activity_id=fa.id AND a.phase='observed'
  WHERE p.factory_work_id=NEW.id AND p.factory_source_id=NEW.source_head_id AND p.factory_policy_id=NEW.policy_id
   AND psl_reporting_document(NEW.id,NEW.source_head_id,v.id)
   AND rv.version_id=v.id AND rv.verdict='approve' AND rv.payload_sha256=v.payload_sha256
   AND rv.id=(SELECT max(id) FROM documents_controlledreview WHERE version_id=v.id)
   AND psl_reporting_review(NEW.case_id,rv.id)
   AND psl_reporting_principals(NEW.id,v.id,p.actor_id)
   AND psl_reporting_distribution(NEW.case_id,v.id,p.policies,p.recipient_ids,p.retention_days)
   AND psl_reporting_grants(NEW.case_id,p.actor_id,ARRAY['case.read','report.read','factory.execute','document.publish'])
   AND a.result->'verified'='true'::jsonb AND a.result->>'head'=NEW.source_head_id::text AND a.result->>'document_version'=v.id::text
   AND a.result->>'publication'=p.id::text AND a.result->'complete_project_coverage'='false'::jsonb AND a.result->'external_delivery_verified'='false'::jsonb AND a.result->'business_approval_granted'='false'::jsonb
   AND jsonb_array_length(p.recipient_ids)>0
   AND (SELECT count(*) FROM documents_publicationreceipt WHERE publication_id=p.id)=jsonb_array_length(p.recipient_ids)
   AND NOT EXISTS(SELECT 1 FROM jsonb_array_elements_text(p.recipient_ids) recipient WHERE NOT EXISTS(
    SELECT 1 FROM documents_publicationreceipt pr WHERE pr.publication_id=p.id AND pr.recipient_id=recipient::bigint
     AND pr.payload=v.payload AND pr.payload_sha256=v.payload_sha256 AND psl_reporting_grants(NEW.case_id,pr.recipient_id,ARRAY['document.receive:client']))))
 THEN RAISE EXCEPTION 'Observed exact current weekly client report, native PMO Lead review and every recipient receipt required'; END IF;

 IF NEW.definition='pmo-escalation/v1' AND NEW.status='verified' AND NOT EXISTS(
 SELECT 1 FROM documents_publication p JOIN documents_version v ON v.id=p.version_id JOIN documents_publicationjob j ON j.publication_id=p.id
 JOIN pmo_escalationdocumentbinding b ON b.version_id=v.id JOIN pmo_escalationrequest r ON r.id=b.request_id JOIN pmo_escalationprofile ep ON ep.id=r.profile_id
 JOIN workflows_factoryactivity fa ON fa.work_id=NEW.id AND fa.kind='ACT13' JOIN workflows_factoryattempt a ON a.activity_id=fa.id AND a.phase='observed'
 WHERE p.factory_work_id=NEW.id AND p.factory_source_id=NEW.source_head_id AND p.factory_policy_id=NEW.policy_id AND j.status='confirmed'
 AND psl_escalation_document(NEW.id,v.id,p.review_id,p.actor_id,p.factory_policy_id,p.factory_source_id,p.recipient_ids,p.policies)
 AND a.result->'verified'='true'::jsonb AND a.result->'issue_resolution_verified'='false'::jsonb AND a.result->>'head'=NEW.source_head_id::text
 AND a.result->>'verification_scope'='reviewed_escalation_communication' AND a.result->>'request'=r.id::text AND a.result->>'profile'=ep.id::text AND a.result->>'issue_state'=ep.state_id::text
 AND a.result->'decision'=COALESCE(to_jsonb(b.decision_id),'null'::jsonb) AND a.result->>'direction'=r.direction AND a.result->>'target'=r.target
 AND a.result->>'document_version'=v.id::text AND a.result->>'publication'=p.id::text
 AND a.result->'receipt_ids'=(SELECT jsonb_agg(pr.id ORDER BY pr.id) FROM documents_publicationreceipt pr WHERE pr.publication_id=p.id)
 AND (SELECT count(*) FROM documents_publicationreceipt WHERE publication_id=p.id)=jsonb_array_length(p.recipient_ids)
 AND NOT EXISTS(SELECT 1 FROM jsonb_array_elements_text(p.recipient_ids) recipient WHERE NOT EXISTS(SELECT 1 FROM documents_publicationreceipt pr WHERE pr.publication_id=p.id AND pr.recipient_id=recipient::bigint AND pr.payload=v.payload AND pr.payload_sha256=v.payload_sha256)))
 THEN RAISE EXCEPTION 'Observed exact current communication and every receipt required; issue resolution is not verified'; END IF;

 IF NEW.definition='pmo-minutes/v1' THEN
  IF NEW.invoice_id IS NOT NULL OR NEW.preparation_id IS NOT NULL OR NOT EXISTS(
   SELECT 1 FROM core_evidence e JOIN core_audit a ON a.case_id=e.case_id AND a.actor_id=e.created_by_id
   JOIN core_evidence note ON note.id=(e.body::jsonb->>'evidence_id')::bigint AND note.case_id=e.case_id
   JOIN documents_template t ON t.id=(e.body::jsonb->>'template_id')::bigint AND t.case_id=e.case_id
   WHERE e.id=NEW.source_head_id AND e.case_id=NEW.case_id AND e.kind='agent_private_minutes_intake'
    AND e.body::jsonb->>'protocol'='factory-minutes-intake/v1' AND note.kind='meeting_notes'
    AND t.definition->>'document_type'='minutes' AND t.definition->'audience_fields' ? (e.body::jsonb->>'audience')
    AND (e.body::jsonb->>'audience'='internal' AND e.body::jsonb->'publish'='false'::jsonb OR e.body::jsonb->>'audience'='client' AND e.body::jsonb->'publish'='true'::jsonb)
    AND e.body::jsonb - ARRAY['protocol','meeting_version_id','evidence_id','template_id','audience','publish']='{}'::jsonb
    AND a.action IN ('factory.minutes_intake','factory.minutes_source')
    AND a.data=jsonb_build_object('evidence_id',e.id,'sha256',e.sha256)
    AND encode(sha256(convert_to(e.body,'UTF8')),'hex')=e.sha256)
   THEN RAISE EXCEPTION 'Exact authorized typed formal-minutes intake required'; END IF;
  IF NEW.status='verified' AND NOT EXISTS(
   SELECT 1 FROM workflows_factoryactivity fa JOIN workflows_factoryattempt a ON a.activity_id=fa.id
   WHERE fa.work_id=NEW.id AND fa.kind='ACT13' AND a.phase='observed'
    AND a.result->'verified'='true'::jsonb AND a.result->>'head'=NEW.source_head_id::text
    AND a.result->'actions_completed'='false'::jsonb AND a.result->'scope_changed'='false'::jsonb
    AND psl_minutes_current(NEW.id,NEW.source_head_id,(a.result->>'document_version')::bigint)
    AND psl_schedules_policy_current(NEW.case_id,NEW.policy_id)
    AND a.result->'manifest'=(SELECT manifest FROM pmo_minutesreportbinding WHERE version_id=(a.result->>'document_version')::bigint)
    AND ((SELECT body::jsonb->'publish' FROM core_evidence WHERE id=NEW.source_head_id)='false'::jsonb OR EXISTS(
     SELECT 1 FROM documents_publication p JOIN documents_controlledreview r ON r.id=p.review_id JOIN documents_version v ON v.id=p.version_id
     WHERE p.id=(a.result->>'publication')::bigint AND p.version_id=(a.result->>'document_version')::bigint
      AND p.factory_work_id=NEW.id AND p.factory_source_id=NEW.source_head_id AND p.factory_policy_id=NEW.policy_id
      AND r.version_id=v.id AND r.verdict='approve' AND r.payload_sha256=v.payload_sha256
      AND r.id=(SELECT max(id) FROM documents_controlledreview WHERE version_id=v.id)
      AND psl_schedules_authority_current(NEW.case_id,r.authority)
      AND psl_schedules_grants(NEW.case_id,r.actor_id,ARRAY['document.review_controlled'])
      AND psl_schedules_authority_current(NEW.case_id,p.policies)
      AND p.actor_id=(psl_schedules_values(NEW.policy_id)->0->>'executor_id')::bigint
      AND psl_schedules_grants(NEW.case_id,p.actor_id,ARRAY['case.read','meeting.read','factory.execute','document.publish'])
      AND p.recipient_ids=(SELECT jsonb_agg(DISTINCT (recipient->>'user_id')::bigint ORDER BY (recipient->>'user_id')::bigint)
       FROM jsonb_array_elements(psl_schedules_values((p.policies->>'D11.recipient_grant_refs')::bigint)) recipient WHERE recipient->>'audience'=v.audience)
      AND p.retention_days=(psl_schedules_values((p.policies->>'D11.template_storage_retention_rules')::bigint)->0->>'retention_days')::integer
      AND NOT EXISTS(SELECT 1 FROM jsonb_array_elements_text(p.recipient_ids) recipient WHERE NOT psl_schedules_grants(NEW.case_id,recipient::bigint,ARRAY['document.receive:'||v.audience]))
      AND jsonb_array_length(p.recipient_ids)>0
      AND NOT EXISTS(SELECT 1 FROM jsonb_array_elements_text(p.recipient_ids) recipient WHERE NOT EXISTS(
       SELECT 1 FROM documents_publicationreceipt pr WHERE pr.publication_id=p.id AND pr.recipient_id=recipient::bigint
        AND pr.payload=v.payload AND pr.payload_sha256=v.payload_sha256)))))
   THEN RAISE EXCEPTION 'Observed current human-confirmed minutes and exact requested recipient receipts required'; END IF;
 END IF;

 IF NEW.definition='finance-bu/v1' AND NEW.status='verified' AND NOT EXISTS(
  SELECT 1 FROM core_evidence e JOIN finance_buwork w ON w.case_id=NEW.case_id AND w.kind=NEW.request->>'mode'
  JOIN finance_bureport p ON p.work_id=w.id JOIN finance_bureview rv ON rv.id=p.review_id
  JOIN workflows_factoryactivity fa ON fa.work_id=NEW.id AND fa.kind='ACT13'
  JOIN workflows_factoryattempt a ON a.activity_id=fa.id AND a.phase='observed'
  JOIN policy_configuration pc ON pc.id=(p.policy_ids->>'BU.disclosure_rules')::bigint
  WHERE e.id=NEW.source_head_id AND w.reference='factory-bu-'||NEW.id::text
   AND psl_schedules_grants(NEW.case_id,e.created_by_id,ARRAY['case.read','bu.read','bu.private.read','evidence.add'])
   AND EXISTS(SELECT 1 FROM core_audit origin WHERE origin.case_id=NEW.case_id AND origin.actor_id=e.created_by_id
    AND origin.data=jsonb_build_object('evidence_id',e.id,'sha256',e.sha256)
    AND ((origin.action='factory.bu_intake' AND psl_schedules_grants(NEW.case_id,e.created_by_id,ARRAY['factory.start']))
     OR (origin.action='factory.bu_source' AND psl_schedules_grants(NEW.case_id,e.created_by_id,ARRAY['factory.manage']))))
   AND w.metadata->>'status'='complete' AND w.payload->'conserved'='true'::jsonb
   AND psl_bu_current(w.id) AND psl_bu_review(rv.id) AND psl_bu_private(w.id,p.actor_id) AND psl_bu_authority(w.id,p.actor_id,'publish',p.policy_ids)
   AND (COALESCE(w.metadata->'historical','false'::jsonb)='false'::jsonb OR EXISTS(SELECT 1 FROM finance_bureview history WHERE history.work_id=w.id AND history.purpose='historical' AND psl_bu_review(history.id)))
   AND rv.work_id=w.id AND rv.purpose=w.kind AND rv.verdict='approve' AND rv.subject_sha256=w.sha256
   AND rv.id=(SELECT max(id) FROM finance_bureview WHERE work_id=w.id AND purpose=w.kind)
   AND NOT EXISTS(SELECT 1 FROM finance_buwork newer WHERE newer.case_id=w.case_id AND newer.kind=w.kind AND newer.reference=w.reference AND newer.version>w.version AND newer.metadata->'accepted'='true'::jsonb)
   AND NOT EXISTS(SELECT 1 FROM finance_bureport newer JOIN finance_buwork nw ON nw.id=newer.work_id WHERE nw.case_id=w.case_id AND nw.kind=w.kind AND nw.metadata->'scope'=w.metadata->'scope' AND newer.id>p.id)
   AND ((w.kind='staff' AND w.payroll_id=(e.body::jsonb->'inputs'->>'payroll_id')::bigint AND w.metadata->'rule_ids'=e.body::jsonb->'inputs'->'rule_ids')
    OR (w.kind='event' AND w.parent_id=(e.body::jsonb->'inputs'->>'source_id')::bigint AND w.metadata->'comparison'=e.body::jsonb->'inputs'->'comparison'))
   AND psl_schedules_policy_current(NEW.case_id,pc.id)
   AND psl_schedules_grants(NEW.case_id,p.actor_id,ARRAY['case.read','bu.read','bu.private.read','bu.publish'])
   AND psl_schedules_grants(NEW.case_id,rv.actor_id,ARRAY['case.read','bu.read','bu.private.read','bu.review'])
   AND NOT EXISTS(SELECT 1 FROM jsonb_each(w.metadata->'policy_ids') pin WHERE NOT psl_schedules_policy_current(NEW.case_id,(pin.value#>>'{}')::bigint))
   AND p.payload-ARRAY['entity','period','currency','unit','by_bu','company_source_total','allocated_total','company_only','residual','conserved','source_work','coverage','native_authenticity_verified','destination','ledger_posted','source_written','disclosure']='{}'::jsonb
   AND p.payload->>'disclosure'='aggregate_only' AND NOT (p.payload ? 'rows') AND p.payload->'ledger_posted'='false'::jsonb AND p.payload->'source_written'='false'::jsonb
   AND p.payload->>'source_work'=w.id::text AND p.payload->'by_bu'=w.payload->'by_bu'
   AND p.payload->'company_source_total'=w.payload->'source_total' AND p.payload->'allocated_total'=w.payload->'allocated_total' AND p.payload->'residual'=w.payload->'residual'
   AND a.result->'verified'='true'::jsonb AND a.result->>'head'=e.id::text AND a.result->>'work'=w.id::text AND a.result->>'publication'=p.id::text
   AND a.result->'private_payloads_in_result'='false'::jsonb AND a.result->'source_written'='false'::jsonb AND a.result->'ledger_posted'='false'::jsonb
   AND jsonb_array_length(psl_schedules_values(pc.id)->0->'recipient_ids')>0
   AND (SELECT count(*) FROM finance_bureceipt WHERE report_id=p.id)=jsonb_array_length(psl_schedules_values(pc.id)->0->'recipient_ids')
   AND NOT EXISTS(SELECT 1 FROM jsonb_array_elements_text(psl_schedules_values(pc.id)->0->'recipient_ids') recipient WHERE NOT EXISTS(
    SELECT 1 FROM finance_bureceipt rr WHERE rr.report_id=p.id AND rr.actor_id=recipient::bigint
     AND a.result->'receipt_ids' @> to_jsonb(ARRAY[rr.id])
     AND psl_schedules_grants(NEW.case_id,rr.actor_id,ARRAY['case.read','bu.read','bu.report.read','bu.receive']))))
 THEN RAISE EXCEPTION 'Observed exact reviewed BU aggregate and actual recipient-owned receipts required'; END IF;
 RETURN NEW;
END $$;

CREATE OR REPLACE FUNCTION psl_engagement_factory_source(w workflows_factorywork) RETURNS boolean LANGUAGE sql STABLE AS $$
 SELECT EXISTS(SELECT 1 FROM core_evidence e JOIN pmo_engagementrecord r ON r.id::text=e.body::jsonb->>'capture'
 WHERE e.id=w.source_head_id AND e.case_id=w.case_id AND e.kind='agent_private_engagement_intake'
  AND e.source='psl:engagement-intake/v1' AND e.body::jsonb->>'protocol'='engagement-intake/v1'
  AND e.body::jsonb - ARRAY['protocol','capture','capture_hash','source','sha256']='{}'::jsonb
  AND encode(sha256(convert_to(e.body,'UTF8')),'hex')=e.sha256
  AND EXISTS(SELECT 1 FROM core_audit a WHERE a.case_id=w.case_id AND a.actor_id=e.created_by_id AND a.action='factory.engagement_intake'
    AND a.data=jsonb_build_object('head',e.id,'sha256',e.sha256))
  AND r.case_id=w.case_id AND r.kind='capture' AND r.evidence_id::text=e.body::jsonb->>'source'
  AND EXISTS(SELECT 1 FROM core_evidence original WHERE original.id=r.evidence_id AND original.case_id=w.case_id AND original.sha256=e.body::jsonb->>'sha256')
  AND w.invoice_id IS NULL AND w.preparation_id IS NULL);
$$;
CREATE OR REPLACE FUNCTION psl_engagement_factory_identity_clear(cid uuid, uid bigint) RETURNS boolean LANGUAGE sql STABLE AS $$
 SELECT NOT EXISTS(SELECT 1 FROM (SELECT * FROM pmo_projectidentitydecision WHERE case_id=cid ORDER BY id DESC LIMIT 100) d
 WHERE NOT psl_schedules_grants(d.other_case_id,uid,ARRAY['case.read','engagement.read'])
 OR (d.relation IN ('alias','unresolved')
  AND d.id=(SELECT max(id) FROM pmo_projectidentitydecision WHERE case_id=cid AND other_case_id=d.other_case_id)
  AND d.data->>'source_capture'=(SELECT max(id)::text FROM pmo_engagementrecord WHERE case_id=cid AND kind='capture')
  AND d.data->>'target_capture'=(SELECT max(id)::text FROM pmo_engagementrecord WHERE case_id=d.other_case_id AND kind='capture')
  AND psl_schedules_policy_current(cid,(d.data->>'source_policy')::bigint)
  AND psl_schedules_policy_current(d.other_case_id,(d.data->>'target_policy')::bigint)
  AND psl_schedules_grants(cid,d.actor_id,ARRAY['case.read','engagement.read','engagement.resolve_identity'])
  AND psl_schedules_grants(d.other_case_id,d.actor_id,ARRAY['case.read','engagement.read','engagement.resolve_identity'])
  AND psl_schedules_role_current(cid,d.actor_id,d.data->'source_authority',d.data->>'role')
  AND psl_schedules_role_current(d.other_case_id,d.actor_id,d.data->'target_authority',d.data->>'role')
  AND EXISTS(SELECT 1 FROM jsonb_array_elements(psl_schedules_values((d.data->>'source_policy')::bigint)) v WHERE v->'resolution_roles' ? (d.data->>'role'))
  AND EXISTS(SELECT 1 FROM jsonb_array_elements(psl_schedules_values((d.data->>'target_policy')::bigint)) v WHERE v->'resolution_roles' ? (d.data->>'role'))
  AND d.data->'access_transferred'='false'::jsonb AND d.data->'business_records_transferred'='false'::jsonb AND d.data->'financial_authority'='false'::jsonb));
$$;
CREATE OR REPLACE FUNCTION psl_engagement_public_source(cid uuid, eid bigint) RETURNS boolean LANGUAGE sql STABLE AS $$
 SELECT EXISTS(SELECT 1 FROM core_evidence e WHERE e.id=eid AND e.case_id=cid
  AND e.kind NOT IN ('ledger_source','quickbooks_verification','ledger_resolution','ledger_resolution_review','approval_source','approval_observation','migration_proof','d03_source','planning_packet','planning_prd_alignment','planning_scope_alignment','planning_contract_comparison','planning_readiness','finance_group_snapshot')
  AND e.kind !~ '^(d03_control_|p14_|ops_|integration_|agent_private_|forecast_)'
  AND e.source<>'psl:p56-confirmed-request/v1'
  AND NOT(e.kind='finance_report_snapshot' AND e.source LIKE 'derived:forecast:%')
  AND NOT EXISTS(SELECT 1 FROM finance_forecastscenario f WHERE f.case_id=cid AND
   (f.evidence_id=eid OR EXISTS(SELECT 1 FROM jsonb_array_elements(f.payload->'items') item WHERE item->>'evidence_id'=eid::text)
    OR EXISTS(SELECT 1 FROM jsonb_array_elements(f.payload->'openings') opening WHERE opening->>'evidence_id'=eid::text))));
$$;
CREATE OR REPLACE FUNCTION psl_engagement_planning_inputs_current(eid bigint) RETURNS boolean LANGUAGE sql STABLE AS $$
 SELECT EXISTS(SELECT 1 FROM core_evidence e WHERE e.id=eid AND e.kind='planning_packet'
  AND encode(sha256(convert_to(e.body,'UTF8')),'hex')=e.sha256
  AND NOT EXISTS(SELECT 1 FROM jsonb_array_elements(e.body::jsonb->'payload'->'stakeholders') s
    WHERE (s->'contact_id'<>'null'::jsonb AND NOT psl_schedules_grants(e.case_id,(s->>'contact_id')::bigint,ARRAY['planning.participate']))
     OR (s->'evidence_id'<>'null'::jsonb AND NOT psl_engagement_public_source(e.case_id,(s->>'evidence_id')::bigint)))
  AND NOT EXISTS(SELECT 1 FROM jsonb_array_elements(e.body::jsonb->'payload'->'questions') q
    WHERE (q->'evidence_id'<>'null'::jsonb AND NOT psl_engagement_public_source(e.case_id,(q->>'evidence_id')::bigint))
     OR (q->'action_id'<>'null'::jsonb AND NOT EXISTS(SELECT 1 FROM pmo_actionitem a WHERE a.id::text=q->>'action_id' AND a.case_id=e.case_id
      AND a.current_id::text=e.body::jsonb->'action_heads'->>(q->>'action_id'))))
  AND NOT EXISTS(SELECT 1 FROM jsonb_each(e.body::jsonb->'action_heads') h
    WHERE NOT EXISTS(SELECT 1 FROM pmo_actionitem a WHERE a.id::text=h.key AND a.case_id=e.case_id AND to_jsonb(a.current_id)=h.value))
  AND NOT EXISTS(SELECT 1 FROM unnest(ARRAY['prd_id','scope_id','engineering_estimate_id','security_estimate_id']) k
    WHERE e.body::jsonb->'payload'->k<>'null'::jsonb AND NOT psl_engagement_public_source(e.case_id,(e.body::jsonb->'payload'->>k)::bigint)));
$$;
CREATE OR REPLACE FUNCTION psl_engagement_worker_current(w workflows_factorywork) RETURNS boolean LANGUAGE sql STABLE AS $$
 SELECT w.execution_binding_id IS NULL OR EXISTS(
  SELECT 1 FROM workflows_factoryexecutionbinding b WHERE b.id=w.execution_binding_id AND b.work_id=w.id
   AND psl_schedules_policy_current(w.case_id,b.configuration_id)
   AND EXISTS(SELECT 1 FROM policy_configuration p WHERE p.id=b.configuration_id AND p.case_id=w.case_id AND p.component='OPS.factory_recovery_authority')
   AND EXISTS(SELECT 1 FROM jsonb_array_elements(psl_schedules_values(b.configuration_id)) value
    WHERE value->'rules' @> jsonb_build_array(b.rule)
     AND (SELECT count(*) FROM jsonb_array_elements(value->'rules') rule WHERE rule->>'definition'=w.definition)=1)
   AND b.rule->>'definition'=w.definition AND b.rule->>'method'='reviewed_execution_principal_v1'
   AND b.rule->>'principal_id'=b.principal_id::text AND b.rule->>'reviewer_id'=b.reviewer_id::text
   AND b.rule->'independent_of_worker' IN ('true'::jsonb,'false'::jsonb)
   AND (b.rule->'independent_of_worker'='false'::jsonb OR b.principal_id<>b.reviewer_id)
   AND (b.rule->>'valid_from')::timestamptz<=statement_timestamp() AND statement_timestamp()<(b.rule->>'valid_until')::timestamptz
   AND psl_schedules_grants(w.case_id,b.principal_id,ARRAY['case.read','factory.read','engagement.read','factory.execute'])
   AND psl_schedules_grants(w.case_id,b.reviewer_id,ARRAY['case.read','factory.read','engagement.read','factory.manage'])
   AND EXISTS(SELECT 1 FROM policy_configuration roles WHERE roles.case_id=w.case_id AND roles.component='D05.role_principal_assignments'
    AND psl_schedules_policy_current(w.case_id,roles.id)
    AND psl_schedules_role_current(w.case_id,b.reviewer_id,jsonb_build_object('D05.role_principal_assignments',roles.id),b.rule->>'review_role'))
   AND NOT EXISTS(SELECT 1 FROM policy_scopeapplication app JOIN policy_scopeversion scope ON scope.id=app.source_id
    JOIN policy_configuration origin ON origin.id=scope.configuration_id WHERE app.configuration_id=b.configuration_id
     AND (NOT psl_schedules_grants(origin.case_id,b.principal_id,ARRAY['case.read','policy.read'])
      OR NOT psl_schedules_grants(origin.case_id,b.reviewer_id,ARRAY['case.read','policy.read'])))
 );
$$;
CREATE OR REPLACE FUNCTION psl_engagement_factory_current(w workflows_factorywork, result jsonb) RETURNS boolean LANGUAGE sql STABLE AS $$
 SELECT psl_engagement_factory_source(w) AND psl_engagement_worker_current(w)
 AND psl_engagement_factory_identity_clear(w.case_id,COALESCE((SELECT principal_id FROM workflows_factoryexecutionbinding WHERE id=w.execution_binding_id),w.actor_id))
 AND psl_schedules_grants(w.case_id,COALESCE((SELECT principal_id FROM workflows_factoryexecutionbinding WHERE id=w.execution_binding_id),w.actor_id),ARRAY['case.read','engagement.read','planning.read','factory.execute'])
 AND EXISTS(
 SELECT 1 FROM pmo_engagementrecord c
 JOIN pmo_engagementrecord a ON a.id::text=result->>'assignment' AND a.case_id=w.case_id AND a.kind='assignment'
 JOIN pmo_engagementrecord r ON r.id::text=result->>'registration' AND r.case_id=w.case_id AND r.kind='registration'
 JOIN core_evidence source ON source.id=c.evidence_id AND source.case_id=w.case_id
 JOIN core_evidence plan ON plan.id::text=r.data->>'plan' AND plan.case_id=w.case_id AND plan.kind='plan' AND plan.sha256=r.data->>'plan_sha256'
 JOIN core_evidence packet ON packet.id::text=result->>'planning_packet' AND packet.case_id=w.case_id AND packet.kind='planning_packet'
 JOIN workflows_factorywork child ON child.id::text=result->>'planning_work' AND child.case_id=w.case_id AND child.definition='planning/v1'
 JOIN core_audit receipt ON receipt.id::text=result->>'receipt' AND receipt.case_id=w.case_id AND receipt.action='factory.engagement_planning_linked'
 WHERE c.id::text=result->>'capture' AND c.case_id=w.case_id AND c.kind='capture'
  AND c.id=(SELECT max(id) FROM pmo_engagementrecord WHERE case_id=w.case_id AND kind='capture')
  AND a.id=(SELECT max(id) FROM pmo_engagementrecord WHERE case_id=w.case_id AND kind='assignment')
  AND r.id=(SELECT max(id) FROM pmo_engagementrecord WHERE case_id=w.case_id AND kind='registration')
  AND a.data->>'capture'=c.id::text AND r.data->>'capture'=c.id::text AND r.data->>'assignment'=a.id::text
  AND result->'verified'='true'::jsonb AND result->>'verification_scope'='current_engagement_identity_and_internal_planning_handoff'
  AND result->>'head'=w.source_head_id::text
  AND result->'planning_complete'='false'::jsonb AND result->'external_master_verified'='false'::jsonb AND result->'signature_required'='false'::jsonb
  AND (SELECT body::jsonb->>'capture' FROM core_evidence WHERE id=w.source_head_id)=c.id::text
  AND encode(sha256(convert_to(source.body,'UTF8')),'hex')=source.sha256
  AND psl_engagement_public_source(w.case_id,source.id)
  AND psl_engagement_public_source(w.case_id,plan.id)
  AND (c.data->>'route' IN ('B','C') OR EXISTS(SELECT 1 FROM pmo_rfpdisposition d JOIN pmo_rfpcase rf ON rf.id=d.rfp_id
    JOIN pmo_rfpoutcome o ON o.id=d.outcome_id WHERE d.id::text=c.data->>'rfp_disposition' AND rf.case_id=w.case_id AND d.kind='route_a' AND o.result='won'))
  AND (c.data->>'route'<>'C' OR source.kind='product_input')
  AND psl_schedules_grants(w.case_id,c.actor_id,ARRAY['case.read','engagement.read','engagement.capture'])
  AND psl_schedules_grants(w.case_id,a.actor_id,ARRAY['engagement.assign'])
  AND psl_schedules_grants(w.case_id,(a.data->>'pm_id')::bigint,ARRAY['engagement.read'])
  AND psl_schedules_grants(w.case_id,r.actor_id,ARRAY['engagement.register'])
  AND psl_schedules_policy_current(w.case_id,(a.data->>'policy')::bigint)
  AND psl_schedules_policy_current(w.case_id,(r.data->>'policy')::bigint)
  AND psl_schedules_role_current(w.case_id,a.actor_id,a.data->'authority',a.data->>'role')
  AND psl_schedules_role_current(w.case_id,(a.data->>'pm_id')::bigint,a.data->'pm_authority','PM')
  AND psl_schedules_role_current(w.case_id,r.actor_id,r.data->'authority',r.data->>'role')
  AND EXISTS(SELECT 1 FROM jsonb_array_elements(psl_schedules_values((a.data->>'policy')::bigint)) v WHERE v->'assignment_roles' ? (a.data->>'role'))
  AND EXISTS(SELECT 1 FROM jsonb_array_elements(psl_schedules_values((r.data->>'policy')::bigint)) v WHERE v->'registration_roles' ? (r.data->>'role'))
  AND EXISTS(SELECT 1 FROM pmo_projectidentifier i JOIN core_case k ON k.id=w.case_id WHERE i.case_id=w.case_id AND i.tenant=k.tenant
    AND i.namespace=r.data->>'namespace' AND i.normalized=r.data->>'normalized')
  AND psl_engagement_planning_inputs_current(packet.id)
  AND packet.id=child.source_head_id AND packet.id=(SELECT id FROM core_evidence WHERE case_id=w.case_id AND kind='planning_packet' ORDER BY version DESC LIMIT 1)
  AND packet.body::jsonb->>'engagement_id'=c.id::text AND child.request->>'engagement'=c.id::text
  AND NOT child.cancel_requested AND child.status NOT IN ('cancelled','followup_needed')
  AND psl_schedules_grants(w.case_id,packet.created_by_id,ARRAY['case.read','planning.read','planning.coordinate'])
  AND EXISTS(SELECT 1 FROM core_audit pa WHERE pa.case_id=w.case_id AND pa.actor_id=packet.created_by_id AND pa.action='planning.recorded'
     AND pa.data=jsonb_build_object('kind','packet','evidence_id',packet.id,'sha256',packet.sha256))
  AND receipt.data->>'work'=w.id::text AND receipt.data->>'capture'=c.id::text AND receipt.data->>'planning_work'=child.id::text
 );
$$;
CREATE OR REPLACE FUNCTION psl_engagement_factory_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF NEW.definition<>'engagement/v1' THEN RETURN NEW; END IF;
 IF NOT psl_engagement_factory_source(NEW) THEN RAISE EXCEPTION 'Exact native engagement intake pointer required'; END IF;
 IF NEW.status='verified' AND NOT EXISTS(SELECT 1 FROM workflows_factoryattempt a JOIN workflows_factoryactivity act ON act.id=a.activity_id
  WHERE act.work_id=NEW.id AND act.kind='ACT13' AND a.phase='observed' AND a.id=(SELECT max(x.id) FROM workflows_factoryattempt x JOIN workflows_factoryactivity y ON y.id=x.activity_id WHERE y.work_id=NEW.id AND y.kind='ACT13' AND x.phase='observed')
  AND psl_engagement_factory_current(NEW,a.result))
 THEN RAISE EXCEPTION 'Observed current engagement identity and native planning handoff required'; END IF;
 RETURN NEW;
END $$;
DROP TRIGGER IF EXISTS psl_engagement_factory_guard ON workflows_factorywork;
CREATE TRIGGER psl_engagement_factory_guard BEFORE INSERT OR UPDATE ON workflows_factorywork FOR EACH ROW EXECUTE FUNCTION psl_engagement_factory_guard();
"""

SQL = r"""-- Structural defense in depth. Python native services retain full business validation.
CREATE OR REPLACE FUNCTION psl_bu_private(wid bigint,uid bigint) RETURNS boolean LANGUAGE plpgsql STABLE AS $$
DECLARE w record; p record; cfg record; v jsonb;
BEGIN
 SELECT * INTO w FROM finance_buwork WHERE id=wid;
 IF NOT FOUND OR NOT psl_schedules_grants(w.case_id,uid,ARRAY['case.read','bu.read','bu.private.read']) THEN RETURN false; END IF;
 IF w.payroll_id IS NOT NULL THEN
  SELECT r.*,q.metadata AS scope,q.case_id INTO p FROM finance_payrollrun r JOIN finance_payrollrequest q ON q.id=r.request_id WHERE r.id=w.payroll_id AND q.case_id=w.case_id;
  IF NOT FOUND OR NOT psl_schedules_grants(w.case_id,uid,ARRAY['payroll.read','payroll.private.read']) THEN RETURN false; END IF;
  SELECT c.* INTO cfg FROM policy_configuration c WHERE c.case_id=w.case_id AND c.component='F16.input_access_rules' AND psl_schedules_policy_current(w.case_id,c.id);
  IF NOT FOUND THEN RETURN false; END IF;
  v=psl_schedules_values(cfg.id)->0;
  RETURN COALESCE(v->'reader_ids' @> to_jsonb(ARRAY[uid]) AND v->'entity'=p.scope->'entity' AND v->'currency'=p.scope->'currency'
   AND v->>'from_period'<=p.scope->>'period' AND v->>'to_period'>=p.scope->>'period',false);
 END IF;
 SELECT c.* INTO cfg FROM policy_configuration c WHERE c.case_id=w.case_id AND c.component='F44.source_rules' AND psl_schedules_policy_current(w.case_id,c.id);
 IF NOT FOUND THEN RETURN false; END IF;
 v=psl_schedules_values(cfg.id)->0;
 RETURN COALESCE(v->'reader_ids' @> to_jsonb(ARRAY[uid]) AND v->'entity'=w.metadata->'scope'->'entity'
  AND v->>'from_period'<=w.metadata->'scope'->>'period' AND v->>'to_period'>=w.metadata->'scope'->>'period',false);
END $$;

CREATE OR REPLACE FUNCTION psl_bu_authority(wid bigint,uid bigint,purpose text,pins jsonb) RETURNS boolean LANGUAGE sql STABLE AS $$
 SELECT EXISTS(SELECT 1 FROM finance_buwork w JOIN policy_configuration c ON c.id=(pins->>'BU.review_authority')::bigint
 WHERE w.id=wid AND c.component='BU.review_authority' AND psl_schedules_policy_current(w.case_id,c.id)
 AND psl_schedules_role_current(w.case_id,uid,pins,'Finance')
 AND EXISTS(SELECT 1 FROM jsonb_array_elements(psl_schedules_values(c.id)->0->'assignments') a
  WHERE a->>'user_id'=uid::text AND a->'purposes' ? purpose)
 AND (purpose='publish' OR psl_schedules_values(c.id)->0->'independent_reviewer'='false'::jsonb OR w.actor_id<>uid));
$$;

CREATE OR REPLACE FUNCTION psl_bu_current(wid bigint,depth integer DEFAULT 0) RETURNS boolean LANGUAGE plpgsql STABLE AS $$
DECLARE w record; p record; v jsonb; rid bigint; inventory jsonb; cmp record;
BEGIN
 IF depth>4 THEN RETURN false; END IF;
 SELECT * INTO w FROM finance_buwork WHERE id=wid;
 IF NOT FOUND OR w.metadata->'accepted' IS DISTINCT FROM 'true'::jsonb OR (w.metadata->>'retain_until')::timestamptz<=statement_timestamp()
  OR NOT psl_schedules_grants(w.case_id,w.actor_id,ARRAY['case.read','bu.read',CASE WHEN w.kind='source' THEN 'bu.capture' ELSE 'bu.'||w.kind END])
  OR EXISTS(SELECT 1 FROM finance_buwork n WHERE n.case_id=w.case_id AND n.reference=w.reference AND n.kind=w.kind AND n.version>w.version AND n.metadata->'accepted'='true'::jsonb)
  OR EXISTS(SELECT 1 FROM jsonb_each(w.metadata->'policy_ids') pin WHERE NOT psl_schedules_policy_current(w.case_id,(pin.value#>>'{}')::bigint))
 THEN RETURN false; END IF;
 IF w.kind<>'source' AND NOT psl_bu_private(wid,w.actor_id) THEN RETURN false; END IF;
 IF w.kind='source' THEN
  v=psl_schedules_values((w.metadata->'policy_ids'->>'F44.source_rules')::bigint)->0;
  IF v->>'owner_id' IS DISTINCT FROM w.actor_id::text OR NOT psl_schedules_role_current(w.case_id,w.actor_id,w.metadata->'owner_authority','Finance')
   OR extract(epoch FROM statement_timestamp()-(w.metadata->>'extracted_at')::timestamptz)>(v->>'max_age_seconds')::numeric THEN RETURN false; END IF;
 END IF;
 IF w.payroll_id IS NOT NULL THEN
  SELECT r.*,q.case_id,q.reference AS request_reference,q.version AS request_version,q.metadata AS request_scope INTO p FROM finance_payrollrun r JOIN finance_payrollrequest q ON q.id=r.request_id WHERE r.id=w.payroll_id AND q.case_id=w.case_id;
  IF NOT FOUND OR p.kind<>'match' OR p.sha256 IS DISTINCT FROM w.metadata->>'payroll_sha256' OR p.retain_until<=statement_timestamp()
   OR EXISTS(SELECT 1 FROM finance_payrollrequest n WHERE n.case_id=w.case_id AND n.reference=p.request_reference AND n.version>p.request_version)
   OR EXISTS(SELECT 1 FROM jsonb_each(p.metadata->'policy_ids') pin WHERE NOT psl_schedules_policy_current(w.case_id,(pin.value#>>'{}')::bigint))
  THEN RETURN false; END IF;
  IF w.kind='staff' THEN
   v=psl_schedules_values((w.metadata->'policy_ids'->>'F21.allocation_rules')::bigint)->0;
   SELECT COALESCE(jsonb_agg(jsonb_build_object('rule_id',r.id,'review_id',rv.id,'verdict',COALESCE(rv.verdict,'pending')) ORDER BY r.id),'[]'::jsonb) INTO inventory
   FROM (SELECT DISTINCT ON (reference) * FROM finance_buwork WHERE case_id=w.case_id AND payroll_id=w.payroll_id AND kind='rule'
    AND metadata->'accepted'='true'::jsonb AND v->'components' ? (payload->>'component') ORDER BY reference,version DESC) r
   LEFT JOIN LATERAL (SELECT id,verdict FROM finance_bureview WHERE work_id=r.id AND purpose='rule' ORDER BY id DESC LIMIT 1) rv ON true;
   IF inventory IS DISTINCT FROM w.metadata->'exception_inventory'
    OR EXISTS(SELECT 1 FROM jsonb_array_elements(inventory) i WHERE i->>'verdict'<>'revoke' AND NOT(w.metadata->'rule_ids' @> jsonb_build_array(i->'rule_id'))) THEN RETURN false; END IF;
  END IF;
 END IF;
 IF w.parent_id IS NOT NULL AND NOT psl_bu_current(w.parent_id,depth+1) THEN RETURN false; END IF;
 FOR rid IN SELECT value::bigint FROM jsonb_array_elements_text(COALESCE(w.metadata->'rule_ids','[]'::jsonb)) LOOP
  IF NOT psl_bu_current(rid,depth+1) THEN RETURN false; END IF;
 END LOOP;
 IF w.metadata->'comparison' IS NOT NULL AND w.metadata->'comparison'<>'null'::jsonb THEN
  SELECT * INTO cmp FROM finance_financerun WHERE id=(w.metadata->'comparison'->>'run_id')::bigint AND case_id=w.case_id AND kind='allocation';
  IF NOT FOUND OR NOT psl_schedules_grants(w.case_id,w.actor_id,ARRAY['finance.calculate']) OR NOT psl_schedules_mapping_current(cmp.parent_id)
   OR cmp.result->>'status'<>'complete' OR cmp.result->'conservation'->(w.metadata->'comparison'->>'metric')->'conserved' IS DISTINCT FROM 'true'::jsonb
   OR EXISTS(SELECT 1 FROM jsonb_each(cmp.snapshot->'policies') pin WHERE NOT psl_schedules_policy_pin_current(w.case_id,pin.key,pin.value))
   OR NOT psl_schedules_finance_review_current((cmp.snapshot->'source_review'->>'id')::bigint)
  THEN RETURN false; END IF;
 END IF;
 RETURN true;
END $$;

CREATE OR REPLACE FUNCTION psl_bu_review(rid bigint,depth integer DEFAULT 0) RETURNS boolean LANGUAGE plpgsql STABLE AS $$
DECLARE r record; w record; parent_review bigint; rule_id bigint;
BEGIN
 IF depth>4 THEN RETURN false; END IF;
 SELECT * INTO r FROM finance_bureview WHERE id=rid;
 IF NOT FOUND THEN RETURN false; END IF;
 SELECT * INTO w FROM finance_buwork WHERE id=r.work_id;
 IF r.verdict<>'approve' OR r.subject_sha256<>w.sha256 OR r.id<>(SELECT max(id) FROM finance_bureview WHERE work_id=w.id AND purpose=r.purpose)
  OR NOT psl_bu_current(w.id) OR NOT psl_bu_private(w.id,r.actor_id)
  OR NOT psl_schedules_grants(w.case_id,r.actor_id,ARRAY['bu.review']) OR NOT psl_bu_authority(w.id,r.actor_id,r.purpose,r.authority) THEN RETURN false; END IF;
 IF w.payroll_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM finance_payrollreview pr JOIN finance_payrollrun p ON p.id=pr.run_id
  WHERE p.id=w.payroll_id AND pr.verdict='approve' AND pr.subject_sha256=p.sha256
   AND pr.id=(SELECT max(id) FROM finance_payrollreview WHERE run_id=p.id)
   AND psl_schedules_grants(w.case_id,pr.actor_id,ARRAY['case.read','payroll.read','payroll.private.read','payroll.review'])
   AND psl_schedules_authority_current(w.case_id,pr.authority)) THEN RETURN false; END IF;
 IF w.parent_id IS NOT NULL THEN
  SELECT rv.id INTO parent_review FROM finance_bureview rv JOIN finance_buwork p ON p.id=rv.work_id WHERE p.id=w.parent_id AND rv.purpose=p.kind ORDER BY rv.id DESC LIMIT 1;
  IF parent_review IS NULL OR NOT psl_bu_review(parent_review,depth+1) THEN RETURN false; END IF;
 END IF;
 FOR rule_id IN SELECT value::bigint FROM jsonb_array_elements_text(COALESCE(w.metadata->'rule_ids','[]'::jsonb)) LOOP
  SELECT id INTO parent_review FROM finance_bureview WHERE work_id=rule_id AND purpose='rule' ORDER BY id DESC LIMIT 1;
  IF parent_review IS NULL OR NOT psl_bu_review(parent_review,depth+1) THEN RETURN false; END IF;
 END LOOP;
 RETURN true;
END $$;

CREATE OR REPLACE FUNCTION psl_minutes_current(wid bigint, head bigint, vid bigint) RETURNS boolean LANGUAGE sql STABLE AS $$
 SELECT EXISTS(
  SELECT 1 FROM workflows_factorywork w JOIN core_evidence e ON e.id=head AND e.case_id=w.case_id
  JOIN core_audit c ON c.case_id=w.case_id AND c.action='factory.minutes_confirmed' AND c.data->>'work'=w.id::text AND c.data->>'head'=e.id::text
  JOIN pmo_meetingversion mv ON mv.id=(c.data->>'meeting_version')::bigint AND mv.created_by_id=c.actor_id
  JOIN pmo_meeting m ON m.id=mv.meeting_id AND m.current_id=mv.id AND m.case_id=w.case_id AND m.reference=w.request->>'reference'
  JOIN pmo_minutesreportbinding b ON b.meeting_id=m.id AND b.version_id=vid
  JOIN documents_version v ON v.id=b.version_id
  JOIN documents_document d ON d.id=v.document_id AND d.current_id=v.id AND d.case_id=w.case_id
  WHERE w.id=wid AND w.definition='pmo-minutes/v1' AND w.source_head_id=head
   AND mv.evidence_id=(e.body::jsonb->>'evidence_id')::bigint
   AND (e.body::jsonb->'meeting_version_id'='null'::jsonb AND mv.number=1 OR EXISTS(
    SELECT 1 FROM pmo_meetingversion predecessor WHERE predecessor.id=(e.body::jsonb->>'meeting_version_id')::bigint
     AND predecessor.meeting_id=m.id AND predecessor.number+1=mv.number))
   AND mv.purpose=c.data->'fields'->>'purpose' AND mv.summary=c.data->'fields'->>'summary'
   AND mv.decisions=c.data->'fields'->'decisions' AND mv.participant_ids=c.data->'fields'->'participant_ids'
   AND v.template_id=(e.body::jsonb->>'template_id')::bigint AND v.audience=e.body::jsonb->>'audience'
   AND psl_schedules_grants(w.case_id,c.actor_id,ARRAY['case.read','meeting.read','meeting.record'])
   AND EXISTS(SELECT 1 FROM core_audit intake WHERE intake.case_id=w.case_id AND intake.actor_id=e.created_by_id
    AND intake.data=jsonb_build_object('evidence_id',e.id,'sha256',e.sha256)
    AND (intake.action='factory.minutes_intake' AND psl_schedules_grants(w.case_id,e.created_by_id,ARRAY['case.read','meeting.read','factory.start'])
      OR intake.action='factory.minutes_source' AND psl_schedules_grants(w.case_id,e.created_by_id,ARRAY['case.read','meeting.read','factory.manage'])))
   AND b.manifest=jsonb_build_object('meeting_version',m.current_id,'actions',COALESCE((SELECT jsonb_agg(jsonb_build_array(ai.id,ai.current_id) ORDER BY ai.id) FROM pmo_meetingactionlink link JOIN pmo_actionitem ai ON ai.id=link.item_id WHERE link.meeting_id=m.id),'[]'::jsonb))
   AND EXISTS(SELECT 1 FROM workflows_factoryactivity fa JOIN workflows_factoryattempt a ON a.activity_id=fa.id
    WHERE fa.work_id=w.id AND fa.kind='ACT09' AND a.phase='observed' AND a.result->>'head'=e.id::text AND a.result->>'document_version'=v.id::text)
 );
$$;

CREATE OR REPLACE FUNCTION psl_escalation_json(body text) RETURNS jsonb LANGUAGE plpgsql IMMUTABLE AS $$
BEGIN RETURN body::jsonb; EXCEPTION WHEN invalid_text_representation THEN RETURN NULL; END $$;
CREATE OR REPLACE FUNCTION psl_escalation_intake(eid bigint) RETURNS jsonb LANGUAGE plpgsql STABLE AS $$
DECLARE body jsonb; raw_body text; source_kind text; key text;
BEGIN
 SELECT e.kind,e.body INTO source_kind,raw_body FROM core_evidence e WHERE e.id=eid;
 IF source_kind IS DISTINCT FROM 'agent_private_escalation_intake' THEN RETURN NULL; END IF;
 body:=psl_escalation_json(raw_body);
 IF jsonb_typeof(body) IS DISTINCT FROM 'object' THEN RETURN NULL; END IF;
 IF body->>'protocol' IS DISTINCT FROM 'factory-escalation-intake/v1' OR (body-ARRAY['protocol','request_id','profile_id','template_id'])<>'{}'::jsonb OR NOT body ?& ARRAY['protocol','request_id','profile_id','template_id'] THEN RETURN NULL; END IF;
 FOREACH key IN ARRAY ARRAY['request_id','profile_id','template_id'] LOOP
  IF key='template_id' AND body->key='null'::jsonb THEN CONTINUE; END IF;
  IF jsonb_typeof(body->key) IS DISTINCT FROM 'number' OR (body->>key)!~'^[1-9][0-9]{0,18}$' THEN RETURN NULL; END IF;
  IF (body->>key)::numeric>9223372036854775807 THEN RETURN NULL; END IF;
 END LOOP;
 RETURN body;
END $$;
CREATE OR REPLACE FUNCTION psl_escalation_bundle(c uuid,p bigint,u bigint) RETURNS boolean LANGUAGE sql STABLE AS $$
 WITH roles AS (SELECT rr.content v FROM policy_configuration cfg JOIN policy_registeredreference rr
 ON rr.case_id=cfg.case_id AND (cfg.envelope->'value') ? rr.ref AND rr.version=1
 WHERE cfg.id=p AND cfg.case_id=c AND rr.content->>'user_id'=u::text)
 SELECT CASE WHEN (SELECT count(*) FROM roles)<=1 THEN true
 WHEN NOT EXISTS(SELECT 1 FROM roles WHERE NOT v ? 'eligibility') THEN
 NOT EXISTS(SELECT 1 FROM roles WHERE (v->'eligibility'->>'valid_from')::timestamptz>statement_timestamp() OR (v->'eligibility'->>'valid_until')::timestamptz<=statement_timestamp())
 ELSE (SELECT synthetic FROM core_case WHERE id=c) END;
$$;

CREATE OR REPLACE FUNCTION psl_escalation_grants(c uuid,u bigint,actions text[]) RETURNS boolean LANGUAGE sql STABLE AS $$
 SELECT EXISTS(SELECT 1 FROM auth_user WHERE id=u AND is_active) AND NOT EXISTS(
 SELECT 1 FROM unnest(actions) a WHERE NOT EXISTS(SELECT 1 FROM identity_grant g WHERE g.case_id=c AND g.user_id=u AND g.action=a AND g.active));
$$;
CREATE OR REPLACE FUNCTION psl_escalation_policy(c uuid,p bigint,component_arg text) RETURNS boolean LANGUAGE sql STABLE AS $$
 SELECT EXISTS(SELECT 1 FROM policy_configuration cfg WHERE cfg.id=p AND cfg.case_id=c AND cfg.component=component_arg
 AND (SELECT state FROM policy_policystate WHERE configuration_id=cfg.id ORDER BY id DESC LIMIT 1)='active'
 AND (cfg.envelope->>'effective_from')::timestamptz<=statement_timestamp()
 AND (cfg.envelope->>'effective_until' IS NULL OR (cfg.envelope->>'effective_until')::timestamptz>statement_timestamp()));
$$;
CREATE OR REPLACE FUNCTION psl_escalation_authority(c uuid,u bigint,role_name text,delegated boolean,pins jsonb) RETURNS boolean LANGUAGE sql STABLE AS $$
 SELECT psl_escalation_grants(c,u,ARRAY[]::text[]) AND EXISTS(
 SELECT 1 FROM policy_configuration pc WHERE pc.id=(pins->>'D05.role_principal_assignments')::bigint
 AND psl_escalation_policy(c,pc.id,'D05.role_principal_assignments')
 AND pins=jsonb_build_object('D05.role_principal_assignments',pc.id) || CASE WHEN delegated THEN jsonb_build_object('D05.delegation_rules',(pins->>'D05.delegation_rules')::bigint) ELSE '{}'::jsonb END AND (
 (NOT delegated AND psl_escalation_bundle(c,pc.id,u) AND EXISTS(SELECT 1 FROM policy_registeredreference rr WHERE rr.case_id=c AND (pc.envelope->'value') ? rr.ref AND rr.version=1
  AND rr.content->>'role'=role_name AND rr.content->>'user_id'=u::text))
 OR (delegated AND EXISTS(SELECT 1 FROM policy_configuration dc JOIN policy_registeredreference dr ON dr.case_id=c AND (dc.envelope->'value') ? dr.ref AND dr.version=1
  JOIN policy_registeredreference rr ON rr.case_id=c AND (pc.envelope->'value') ? rr.ref AND rr.version=1
  WHERE dc.id=(pins->>'D05.delegation_rules')::bigint AND psl_escalation_policy(c,dc.id,'D05.delegation_rules')
  AND dr.content->>'role'=role_name AND dr.content->>'delegate_id'=u::text AND NOT dr.content ? 'decision_scope'
  AND rr.content->>'role'=role_name AND rr.content->>'user_id'=dr.content->>'principal_id'
  AND psl_escalation_grants(c,(dr.content->>'principal_id')::bigint,ARRAY[]::text[])
  AND psl_escalation_bundle(c,pc.id,(dr.content->>'principal_id')::bigint) AND psl_escalation_bundle(c,pc.id,u)
  AND (CASE WHEN dr.content ? 'delegate_eligibility' THEN
    (dr.content->'delegate_eligibility'->>'valid_from')::timestamptz<=statement_timestamp() AND (dr.content->'delegate_eligibility'->>'valid_until')::timestamptz>statement_timestamp()
    AND (SELECT array_agg(x ORDER BY x) FROM jsonb_array_elements_text(dr.content->'delegate_eligibility'->'roles') x)=
     (SELECT array_agg(x ORDER BY x) FROM (SELECT role_name x UNION SELECT ar.content->>'role' FROM policy_registeredreference ar WHERE ar.case_id=c AND ar.version=1 AND (pc.envelope->'value') ? ar.ref AND ar.content->>'user_id'=u::text) bundle)
   ELSE (SELECT synthetic FROM core_case WHERE id=c) OR NOT EXISTS(SELECT 1 FROM policy_registeredreference ar WHERE ar.case_id=c AND ar.version=1 AND (pc.envelope->'value') ? ar.ref AND ar.content->>'user_id'=u::text AND ar.content->>'role'<>role_name) END)
  AND (dr.content->>'valid_from')::timestamptz<=statement_timestamp() AND (dr.content->>'valid_until')::timestamptz>statement_timestamp()))));
$$;
CREATE OR REPLACE FUNCTION psl_escalation_document(wid bigint,vid bigint,rid bigint,publisher_id_arg bigint,policy_id_arg bigint,source_id_arg bigint,recipient_ids_arg jsonb,pins jsonb) RETURNS boolean LANGUAGE sql STABLE AS $$
 SELECT EXISTS(
 SELECT 1 FROM workflows_factorywork w JOIN core_evidence e ON e.id=source_id_arg
 JOIN pmo_escalationrequest r ON r.id=(psl_escalation_intake(e.id)->>'request_id')::bigint
 JOIN pmo_escalationprofile ep ON ep.id=r.profile_id JOIN pmo_issuestate ist ON ist.id=ep.state_id JOIN pmo_issue i ON i.id=ist.issue_id
 JOIN pmo_escalationdocumentbinding b ON b.request_id=r.id AND b.version_id=vid
 JOIN documents_version v ON v.id=b.version_id JOIN documents_document doc ON doc.id=v.document_id JOIN documents_template t ON t.id=v.template_id
 JOIN policy_configuration pc ON pc.id=policy_id_arg JOIN policy_registeredreference cfg ON cfg.case_id=pc.case_id
  AND cfg.ref=pc.envelope->'value'->>'artifact_ref' AND cfg.version=(pc.envelope->'value'->>'artifact_version')::integer AND cfg.sha256=pc.envelope->'value'->>'sha256'
 JOIN policy_configuration rc ON rc.id=(pins->>'D11.recipient_grant_refs')::bigint
 JOIN policy_configuration sc ON sc.id=(pins->>'D11.template_storage_retention_rules')::bigint
 JOIN policy_registeredreference store ON store.case_id=sc.case_id AND store.ref=sc.envelope->'value'->>'artifact_ref'
  AND store.version=(sc.envelope->'value'->>'artifact_version')::integer AND store.sha256=sc.envelope->'value'->>'sha256'
 WHERE w.id=wid AND w.definition='pmo-escalation/v1' AND w.policy_id=policy_id_arg AND w.source_head_id=e.id
 AND e.case_id=w.case_id AND i.case_id=w.case_id AND doc.case_id=w.case_id AND t.case_id=w.case_id
 AND i.id=(w.request->>'issue')::bigint AND i.current_id=ist.id AND ep.id=(psl_escalation_intake(e.id)->>'profile_id')::bigint
 AND ep.id=(SELECT max(p.id) FROM pmo_escalationprofile p JOIN pmo_issuestate s ON s.id=p.state_id WHERE s.issue_id=i.id)
 AND r.direction=w.request->>'direction' AND r.target=w.request->>'target'
 AND v.template_id=(psl_escalation_intake(e.id)->>'template_id')::bigint AND doc.current_id=v.id
 AND v.audience=CASE WHEN r.target='Client' THEN 'client' ELSE 'internal' END
 AND psl_escalation_policy(w.case_id,policy_id_arg,'OPS.factory_escalation_execution') AND cfg.content->'enabled'='true'::jsonb
 AND cfg.content->>'definition'=w.definition AND cfg.content->>'executor_id'=publisher_id_arg::text
 AND psl_escalation_grants(w.case_id,publisher_id_arg,ARRAY['case.read','issue.read','factory.execute','document.publish'])
 AND psl_escalation_grants(w.case_id,(cfg.content->>'preparer_id')::bigint,ARRAY['case.read','issue.read','factory.execute','issue.escalate','document.draft'])
 AND psl_escalation_grants(w.case_id,e.created_by_id,ARRAY['case.read','issue.read','evidence.add'])
 AND EXISTS(SELECT 1 FROM core_audit ia WHERE ia.case_id=w.case_id AND ia.actor_id=e.created_by_id AND ia.data=jsonb_build_object('evidence_id',e.id,'sha256',e.sha256)
  AND ((ia.action='factory.escalation_intake' AND psl_escalation_grants(w.case_id,e.created_by_id,ARRAY['factory.start'])) OR (ia.action='factory.escalation_source' AND psl_escalation_grants(w.case_id,e.created_by_id,ARRAY['factory.manage']))))
 AND ((r.target<>'Client' AND b.decision_id IS NULL) OR EXISTS(SELECT 1 FROM pmo_escalationdecision d WHERE d.id=b.decision_id AND d.request_id=r.id
  AND d.id=(SELECT max(id) FROM pmo_escalationdecision WHERE request_id=r.id) AND d.verdict='approve' AND d.role IN ('PMO Lead','Head of PMO')
  AND psl_escalation_grants(w.case_id,d.actor_id,ARRAY['issue.escalation_decide']) AND psl_escalation_authority(w.case_id,d.actor_id,d.role,d.delegated,d.authority)))
 AND ((rid IS NULL AND v.audience<>'client' AND t.definition->'internal_review_required'='false'::jsonb AND NOT EXISTS(SELECT 1 FROM documents_controlledreview WHERE version_id=v.id))
 OR EXISTS(SELECT 1 FROM documents_controlledreview rv WHERE rv.id=rid AND rv.version_id=v.id AND rv.id=(SELECT max(id) FROM documents_controlledreview WHERE version_id=v.id)
  AND rv.verdict='approve' AND rv.payload_sha256=v.payload_sha256 AND psl_escalation_grants(w.case_id,rv.actor_id,ARRAY['document.review_controlled'])
  AND psl_escalation_authority(w.case_id,rv.actor_id,'PMO Lead',rv.delegated,rv.authority)))
 AND psl_escalation_policy(w.case_id,rc.id,'D11.recipient_grant_refs') AND psl_escalation_policy(w.case_id,sc.id,'D11.template_storage_retention_rules')
 AND store.content->'template_ids' @> jsonb_build_array(t.id) AND jsonb_array_length(recipient_ids_arg)>0
 AND recipient_ids_arg=(SELECT jsonb_agg(u ORDER BY u) FROM (SELECT DISTINCT (rr.content->>'user_id')::bigint u FROM policy_registeredreference rr
  WHERE rr.case_id=w.case_id AND (rc.envelope->'value') ? rr.ref AND rr.version=1 AND rr.content->>'audience'=v.audience) selected)
 AND NOT EXISTS(SELECT 1 FROM jsonb_array_elements_text(recipient_ids_arg) recipient WHERE NOT psl_escalation_grants(w.case_id,recipient::bigint,ARRAY['document.receive:'||v.audience]))
 AND (r.target='Client' OR EXISTS(SELECT 1 FROM policy_configuration ap JOIN policy_registeredreference ar ON ar.case_id=ap.case_id AND (ap.envelope->'value') ? ar.ref AND ar.version=1
  WHERE ap.id=(pins->>'D05.role_principal_assignments')::bigint AND psl_escalation_policy(w.case_id,ap.id,'D05.role_principal_assignments')
  AND ar.content->>'role'=r.target AND recipient_ids_arg @> jsonb_build_array((ar.content->>'user_id')::bigint)))
 AND EXISTS(SELECT 1 FROM workflows_factoryactivity fa JOIN workflows_factoryattempt a ON a.activity_id=fa.id
  WHERE fa.work_id=w.id AND fa.kind='ACT09' AND a.phase='observed' AND a.result->>'head'=e.id::text AND a.result->>'document_version'=v.id::text AND a.result->>'request'=r.id::text));
$$;

CREATE OR REPLACE FUNCTION psl_reporting_grants(cid uuid, uid bigint, actions text[]) RETURNS boolean LANGUAGE sql STABLE AS $$
 SELECT EXISTS(SELECT 1 FROM auth_user WHERE id=uid AND is_active)
 AND NOT EXISTS(SELECT 1 FROM unnest(actions) required(action) WHERE NOT EXISTS(
  SELECT 1 FROM identity_grant g WHERE g.case_id=cid AND g.user_id=uid AND g.action=required.action AND g.active));
$$;
CREATE OR REPLACE FUNCTION psl_reporting_policy(cid uuid,pid bigint) RETURNS boolean LANGUAGE sql STABLE AS $$
 SELECT EXISTS(SELECT 1 FROM policy_configuration p WHERE p.id=pid AND p.case_id=cid
 AND (SELECT state FROM policy_policystate WHERE configuration_id=p.id ORDER BY id DESC LIMIT 1)='active'
 AND NOT EXISTS(SELECT 1 FROM policy_configuration n WHERE n.case_id=cid AND n.component=p.component AND n.revision>p.revision
  AND (SELECT state FROM policy_policystate WHERE configuration_id=n.id ORDER BY id DESC LIMIT 1) IN ('active','revoked','superseded'))
 AND (p.envelope->>'effective_from')::timestamptz<=statement_timestamp()
 AND (p.envelope->>'effective_until' IS NULL OR (p.envelope->>'effective_until')::timestamptz>statement_timestamp())
 AND NOT EXISTS(SELECT 1 FROM policy_scopeapplication app JOIN policy_scopeversion src ON src.id=app.source_id
  JOIN policy_configuration origin ON origin.id=src.configuration_id WHERE app.configuration_id=p.id
  AND ((SELECT state FROM policy_scopestate WHERE source_id=src.id ORDER BY id DESC LIMIT 1) IS DISTINCT FROM 'active'
   OR (SELECT state FROM policy_policystate WHERE configuration_id=origin.id ORDER BY id DESC LIMIT 1) IS DISTINCT FROM 'validated'
   OR (origin.envelope->>'effective_from')::timestamptz>statement_timestamp()
   OR (origin.envelope->>'effective_until' IS NOT NULL AND (origin.envelope->>'effective_until')::timestamptz<=statement_timestamp())
   OR NOT psl_reporting_grants(origin.case_id,(SELECT actor_id FROM policy_scopestate WHERE source_id=src.id AND state='active' ORDER BY id DESC LIMIT 1),ARRAY['case.read','policy.activate'])
   OR EXISTS(SELECT 1 FROM policy_scopeversion n JOIN policy_configuration nc ON nc.id=n.configuration_id
    WHERE nc.case_id=origin.case_id AND nc.component=origin.component AND n.kind=src.kind AND n.ref=src.ref AND n.revision>src.revision
     AND EXISTS(SELECT 1 FROM policy_scopestate ns WHERE ns.source_id=n.id AND ns.state IN ('active','revoked'))))));
$$;
CREATE OR REPLACE FUNCTION psl_reporting_refs(pid bigint) RETURNS SETOF jsonb LANGUAGE sql STABLE AS $$
 SELECT r.content FROM policy_configuration p JOIN policy_registeredreference r ON r.case_id=p.case_id
 WHERE p.id=pid AND CASE jsonb_typeof(p.envelope->'value')
  WHEN 'object' THEN r.ref=p.envelope->'value'->>'artifact_ref' AND r.version=(p.envelope->'value'->>'artifact_version')::integer AND r.sha256=p.envelope->'value'->>'sha256'
  WHEN 'array' THEN p.envelope->'value'?r.ref AND r.version=1
  WHEN 'string' THEN to_jsonb(r.ref)=p.envelope->'value' AND r.version=1 ELSE false END;
$$;
CREATE OR REPLACE FUNCTION psl_reporting_role(cid uuid,uid bigint,pid bigint,role_name text) RETURNS boolean LANGUAGE sql STABLE AS $$
 WITH records AS (SELECT value FROM psl_reporting_refs(pid) value WHERE value->>'user_id'=uid::text),
 roles AS (SELECT COALESCE(jsonb_agg(DISTINCT value->>'role'),'[]'::jsonb) names FROM records)
 SELECT psl_reporting_policy(cid,pid) AND EXISTS(SELECT 1 FROM auth_user WHERE id=uid AND is_active)
 AND EXISTS(SELECT 1 FROM records WHERE value->>'role'=role_name)
 AND ((SELECT jsonb_array_length(names) FROM roles)=1 OR (EXISTS(SELECT 1 FROM core_case WHERE id=cid AND synthetic) AND EXISTS(SELECT 1 FROM records WHERE NOT(value?'eligibility')))
 OR NOT EXISTS(SELECT 1 FROM records,roles WHERE NOT(value?'eligibility')
  OR (value->'eligibility'->'roles') IS NULL OR NOT(value->'eligibility'->'roles' @> roles.names AND value->'eligibility'->'roles' <@ roles.names)
  OR NOT((value->'eligibility'->>'valid_from')::timestamptz<=statement_timestamp() AND (value->'eligibility'->>'valid_until')::timestamptz>statement_timestamp())));
$$;
CREATE OR REPLACE FUNCTION psl_reporting_review(cid uuid,rid bigint) RETURNS boolean LANGUAGE sql STABLE AS $$
 SELECT EXISTS(SELECT 1 FROM documents_controlledreview rv JOIN documents_version v ON v.id=rv.version_id
 JOIN documents_document d ON d.id=v.document_id
 JOIN policy_configuration assignment ON assignment.id=(rv.authority->>'D05.role_principal_assignments')::bigint
 WHERE rv.id=rid AND d.case_id=cid AND d.current_id=v.id AND rv.verdict='approve'
 AND rv.payload_sha256=v.payload_sha256
 AND rv.id=(SELECT max(id) FROM documents_controlledreview WHERE version_id=v.id)
 AND assignment.component='D05.role_principal_assignments' AND psl_reporting_policy(cid,assignment.id)
 AND psl_reporting_grants(cid,rv.actor_id,ARRAY['document.review_controlled'])
 AND ((NOT rv.delegated AND rv.authority=jsonb_build_object('D05.role_principal_assignments',assignment.id)
  AND psl_reporting_role(cid,rv.actor_id,assignment.id,'PMO Lead'))
 OR (rv.delegated AND EXISTS(SELECT 1 FROM policy_configuration delegation, LATERAL psl_reporting_refs(delegation.id) entry
  WHERE delegation.id=(rv.authority->>'D05.delegation_rules')::bigint AND delegation.component='D05.delegation_rules'
   AND psl_reporting_policy(cid,delegation.id)
   AND rv.authority=jsonb_build_object('D05.role_principal_assignments',assignment.id,'D05.delegation_rules',delegation.id)
   AND entry->>'role'='PMO Lead' AND entry->>'delegate_id'=rv.actor_id::text AND NOT(entry?'decision_scope')
   AND (entry->>'valid_from')::timestamptz<=statement_timestamp() AND (entry->>'valid_until')::timestamptz>statement_timestamp()
   AND psl_reporting_role(cid,(entry->>'principal_id')::bigint,assignment.id,'PMO Lead')
   AND (NOT EXISTS(SELECT 1 FROM psl_reporting_refs(assignment.id) own WHERE own->>'user_id'=rv.actor_id::text)
    OR EXISTS(SELECT 1 FROM psl_reporting_refs(assignment.id) own WHERE own->>'user_id'=rv.actor_id::text AND psl_reporting_role(cid,rv.actor_id,assignment.id,own->>'role')))
   AND (CASE WHEN entry?'delegate_eligibility' THEN
     (entry->'delegate_eligibility'->>'valid_from')::timestamptz<=statement_timestamp()
     AND (entry->'delegate_eligibility'->>'valid_until')::timestamptz>statement_timestamp()
     AND (SELECT COALESCE(jsonb_agg(DISTINCT role_name),'[]'::jsonb) FROM
       (SELECT 'PMO Lead' role_name UNION SELECT own->>'role' FROM psl_reporting_refs(assignment.id) own WHERE own->>'user_id'=rv.actor_id::text) roles)
       @> (entry->'delegate_eligibility'->'roles')
     AND entry->'delegate_eligibility'->'roles' @> (SELECT COALESCE(jsonb_agg(DISTINCT role_name),'[]'::jsonb) FROM
       (SELECT 'PMO Lead' role_name UNION SELECT own->>'role' FROM psl_reporting_refs(assignment.id) own WHERE own->>'user_id'=rv.actor_id::text) roles)
    ELSE EXISTS(SELECT 1 FROM core_case WHERE id=cid AND synthetic)
     OR NOT EXISTS(SELECT 1 FROM psl_reporting_refs(assignment.id) own WHERE own->>'user_id'=rv.actor_id::text AND own->>'role'<>'PMO Lead') END)))));
$$;
CREATE OR REPLACE FUNCTION psl_reporting_principals(wid bigint,vid bigint,publisher bigint) RETURNS boolean LANGUAGE sql STABLE AS $$
 SELECT EXISTS(SELECT 1 FROM workflows_factorywork w JOIN documents_version v ON v.id=vid
 JOIN policy_configuration p ON p.id=w.policy_id, LATERAL psl_reporting_refs(p.id) cfg
 WHERE w.id=wid AND p.component='OPS.factory_reporting_execution' AND psl_reporting_policy(w.case_id,p.id)
 AND cfg->>'executor_id'=publisher::text AND cfg->>'preparer_id'=v.created_by_id::text
 AND psl_reporting_grants(w.case_id,publisher,ARRAY['case.read','report.read','factory.execute','document.publish'])
 AND psl_reporting_grants(w.case_id,v.created_by_id,ARRAY['case.read','report.read','factory.execute','report.draft','document.draft','document.request_review']));
$$;
CREATE OR REPLACE FUNCTION psl_reporting_distribution(cid uuid,vid bigint,policies jsonb,recipients jsonb,retention integer) RETURNS boolean LANGUAGE sql STABLE AS $$
 SELECT jsonb_array_length(recipients)>0
 AND policies ?& ARRAY['D11.template_storage_retention_rules','D11.recipient_grant_refs']
 AND policies-ARRAY['D11.template_storage_retention_rules','D11.recipient_grant_refs']='{}'::jsonb
 AND NOT EXISTS(SELECT 1 FROM jsonb_each_text(policies) pin WHERE NOT EXISTS(
  SELECT 1 FROM policy_configuration p WHERE p.id=pin.value::bigint AND p.component=pin.key AND psl_reporting_policy(cid,p.id)))
 AND recipients=COALESCE((SELECT jsonb_agg(DISTINCT (r->>'user_id')::bigint ORDER BY (r->>'user_id')::bigint)
 FROM psl_reporting_refs((policies->>'D11.recipient_grant_refs')::bigint) r WHERE r->>'audience'='client'),'[]'::jsonb)
 AND NOT EXISTS(SELECT 1 FROM jsonb_array_elements_text(recipients) r WHERE NOT psl_reporting_grants(cid,r::bigint,ARRAY['document.receive:client']))
 AND EXISTS(SELECT 1 FROM psl_reporting_refs((policies->>'D11.template_storage_retention_rules')::bigint) storage
  JOIN documents_version v ON v.id=vid WHERE storage->>'retention_days'=retention::text AND storage->'template_ids' @> jsonb_build_array(v.template_id));
$$;
CREATE OR REPLACE FUNCTION psl_reporting_heads(cid uuid,m jsonb,s timestamptz,t timestamptz) RETURNS boolean LANGUAGE sql STABLE AS $$
 SELECT m->>'source_mode'='weekly_client_facts/v1'
 AND m-ARRAY['source_mode','meetings','actions','milestones','issues','changes','client_content']='{}'::jsonb
 AND m->'meetings'=COALESCE((SELECT jsonb_agg(jsonb_build_array(x.id,x.current_id) ORDER BY x.id) FROM pmo_meeting x JOIN pmo_meetingversion v ON v.id=x.current_id WHERE x.case_id=cid AND v.occurred_at>=s AND v.occurred_at<t),'[]'::jsonb)
 AND m->'actions'=COALESCE((SELECT jsonb_agg(jsonb_build_array(id,current_id) ORDER BY id) FROM pmo_actionitem WHERE case_id=cid),'[]'::jsonb)
 AND m->'milestones'=COALESCE((SELECT jsonb_agg(id ORDER BY id) FROM pmo_milestone WHERE case_id=cid AND completed_at>=s AND completed_at<t),'[]'::jsonb)
 AND m->'issues'=COALESCE((SELECT jsonb_agg(jsonb_build_array(id,current_id) ORDER BY id) FROM pmo_issue WHERE case_id=cid),'[]'::jsonb)
 AND m->'changes'=COALESCE((SELECT jsonb_agg(jsonb_build_array(id,current_id) ORDER BY id) FROM pmo_changerequest WHERE case_id=cid),'[]'::jsonb);
$$;
CREATE OR REPLACE FUNCTION psl_reporting_document(wid bigint,eid bigint,vid bigint) RETURNS boolean LANGUAGE sql STABLE AS $$
 SELECT EXISTS(SELECT 1 FROM workflows_factorywork w JOIN core_evidence e ON e.id=eid AND e.case_id=w.case_id
 JOIN documents_version v ON v.id=vid JOIN documents_template template ON template.id=v.template_id JOIN documents_document d ON d.id=v.document_id AND d.case_id=w.case_id AND d.current_id=v.id
 JOIN pmo_minutesreportbinding b ON b.version_id=v.id JOIN pmo_periodreport r ON r.id=b.report_id AND r.case_id=w.case_id
 JOIN core_evidence projection ON projection.id=(v.source_manifest->0->>'id')::bigint AND projection.case_id=w.case_id
 JOIN core_evidence content ON content.id=(e.body::jsonb->'inputs'->>'content_id')::bigint AND content.case_id=w.case_id AND content.kind='agent_private_report_content'
 WHERE w.id=wid AND w.definition='pmo-weekly-report/v1' AND e.kind='agent_private_reporting_intake'
 AND psl_reporting_grants(w.case_id,e.created_by_id,ARRAY['case.read','report.read','evidence.add'])
 AND EXISTS(SELECT 1 FROM core_audit provenance WHERE provenance.case_id=w.case_id AND provenance.actor_id=e.created_by_id
  AND provenance.data=jsonb_build_object('evidence_id',e.id,'sha256',e.sha256)
  AND ((provenance.action='factory.reporting_intake' AND psl_reporting_grants(w.case_id,e.created_by_id,ARRAY['factory.start']))
   OR (provenance.action='factory.reporting_source' AND psl_reporting_grants(w.case_id,e.created_by_id,ARRAY['factory.manage']))))
 AND v.baseline_manifest=COALESCE((SELECT jsonb_build_object('plan_id',plan_id,'costing_id',costing_id,'sow_id',sow_id,'signed_id',signed_id) FROM pmo_baseline WHERE case_id=w.case_id),'{}'::jsonb)
 AND e.id=w.source_head_id AND v.audience='client' AND r.kind='weekly_client' AND r.audience='client' AND r.document_id=d.id
 AND r.start_at=(w.request->>'start_at')::timestamptz AND r.end_at=(w.request->>'end_at')::timestamptz
 AND v.template_id=(e.body::jsonb->'inputs'->>'template_id')::bigint AND b.manifest=e.body::jsonb->'manifest'
 AND psl_reporting_heads(w.case_id,b.manifest,r.start_at,r.end_at)
 AND b.manifest->'client_content'=jsonb_build_object('id',content.id,'sha256',content.sha256)
 AND v.source_manifest=jsonb_build_array(jsonb_build_object('id',projection.id,'version',projection.version,'sha256',projection.sha256))
 AND jsonb_array_length(v.source_manifest)=1 AND projection.kind='ops_client_report_projection'
 AND projection.source='psl:weekly-client-projection:'||r.id::text AND projection.created_by_id=v.created_by_id
 AND NOT EXISTS(SELECT 1 FROM jsonb_each(v.fields) field WHERE field.value->'evidence_ids' IS DISTINCT FROM jsonb_build_array(projection.id))
 AND template.definition->>'document_type'='status_report'
 AND template.definition->'required_fields' @> '["executive_summary","status","risks","timeline","next_steps"]'::jsonb
 AND template.definition->'audience_fields'->'client' @> '["executive_summary","status","risks","timeline","next_steps"]'::jsonb
 AND jsonb_array_length(template.definition->'audience_fields'->'client')=5
 AND v.payload->>'type'='status_report' AND jsonb_array_length(v.payload->'sections')=5
 AND (SELECT jsonb_agg(section->>'heading' ORDER BY section->>'heading') FROM jsonb_array_elements(v.payload->'sections') section)='["executive_summary","next_steps","risks","status","timeline"]'::jsonb
 AND content.body::jsonb->>'protocol'='pmo-weekly-client-content/v1'
 AND (content.body::jsonb->'sections')-ARRAY['status','risks','timeline','next_steps']='{}'::jsonb
 AND NOT EXISTS(SELECT 1 FROM unnest(ARRAY['status','risks','timeline','next_steps']) theme(k)
  WHERE NOT(content.body::jsonb->'sections'?theme.k) OR length(trim(content.body::jsonb->'sections'->theme.k->>'text')) NOT BETWEEN 1 AND 10000
   OR jsonb_array_length(content.body::jsonb->'sections'->theme.k->'evidence_ids') NOT BETWEEN 1 AND 18
   OR EXISTS(SELECT 1 FROM jsonb_array_elements_text(content.body::jsonb->'sections'->theme.k->'evidence_ids') citation
    WHERE NOT EXISTS(SELECT 1 FROM core_evidence ce WHERE ce.id=citation::bigint AND ce.case_id=w.case_id
     AND ce.kind NOT IN ('ledger_source','quickbooks_verification','ledger_resolution','ledger_resolution_review','approval_source','approval_observation','migration_proof','d03_source','planning_packet','planning_prd_alignment','planning_scope_alignment','planning_contract_comparison','planning_readiness','finance_group_snapshot')
     AND ce.kind NOT LIKE 'forecast_%' AND ce.kind NOT LIKE 'd03_control_%' AND ce.kind NOT LIKE 'p14_%'
     AND NOT(ce.kind='finance_report_snapshot' AND ce.source LIKE 'derived:forecast:%')
     AND NOT EXISTS(SELECT 1 FROM finance_forecastscenario fs WHERE fs.case_id=w.case_id AND (fs.evidence_id=ce.id OR fs.payload->'items' @> jsonb_build_array(jsonb_build_object('evidence_id',ce.id)) OR fs.payload->'openings' @> jsonb_build_array(jsonb_build_object('evidence_id',ce.id))))
     AND (ce.source<>'psl:p56-confirmed-request/v1' OR EXISTS(SELECT 1 FROM pmo_changerequest cr JOIN pmo_changeversion cv ON cv.id=cr.current_id WHERE cr.case_id=w.case_id AND cv.evidence_id=ce.id))
     AND ce.kind NOT LIKE 'agent_private_%' AND ce.kind NOT LIKE 'ops_%' AND ce.kind NOT LIKE 'integration_%'
     AND (EXISTS(SELECT 1 FROM pmo_meeting m JOIN pmo_meetingversion mv ON mv.id=m.current_id WHERE m.case_id=w.case_id AND mv.evidence_id=ce.id AND mv.occurred_at>=r.start_at AND mv.occurred_at<r.end_at)
      OR EXISTS(SELECT 1 FROM pmo_actionitem ai JOIN pmo_actionstate state ON state.id=ai.current_id WHERE ai.case_id=w.case_id AND state.evidence_id=ce.id)
      OR EXISTS(SELECT 1 FROM pmo_milestone m WHERE m.case_id=w.case_id AND m.evidence_id=ce.id AND m.completed_at>=r.start_at AND m.completed_at<r.end_at)
      OR EXISTS(SELECT 1 FROM pmo_issue i JOIN pmo_issuestate state ON state.id=i.current_id WHERE i.case_id=w.case_id AND state.evidence_id=ce.id)
      OR EXISTS(SELECT 1 FROM pmo_changerequest cr JOIN pmo_changeversion cv ON cv.id=cr.current_id WHERE cr.case_id=w.case_id AND cv.evidence_id=ce.id))))
   OR NOT EXISTS(SELECT 1 FROM jsonb_array_elements(v.payload->'sections') section WHERE section->>'heading'=theme.k AND section->>'text'=content.body::jsonb->'sections'->theme.k->>'text')
   OR v.fields->theme.k->>'text' IS DISTINCT FROM content.body::jsonb->'sections'->theme.k->>'text')
 AND EXISTS(SELECT 1 FROM workflows_factoryactivity fa JOIN workflows_factoryattempt a ON a.activity_id=fa.id
  WHERE fa.work_id=w.id AND fa.kind='ACT09' AND a.phase='observed' AND a.result->>'document_version'=v.id::text AND a.result->>'head'=e.id::text));
$$;

CREATE OR REPLACE FUNCTION psl_schedules_grants(cid uuid, uid bigint, actions text[]) RETURNS boolean LANGUAGE sql STABLE AS $$
 SELECT EXISTS(SELECT 1 FROM auth_user WHERE id=uid AND is_active)
  AND NOT EXISTS(SELECT 1 FROM unnest(actions) required(action_name) WHERE NOT EXISTS(
   SELECT 1 FROM identity_grant g WHERE g.case_id=cid AND g.user_id=uid AND g.action=required.action_name AND g.active));
$$;
-- Structural checks are bounded mirrors, not execution of Python domain validators.
CREATE OR REPLACE FUNCTION psl_schedules_values(pid bigint) RETURNS jsonb LANGUAGE sql STABLE AS $$
 SELECT CASE WHEN c.component='D04.iana_timezone' THEN jsonb_build_array(c.envelope->'value') ELSE
 (SELECT jsonb_agg(r.content ORDER BY item.ordinality) FROM jsonb_array_elements(CASE WHEN jsonb_typeof(c.envelope->'value')='array' THEN c.envelope->'value' ELSE jsonb_build_array(c.envelope->'value') END) WITH ORDINALITY item(value,ordinality)
 JOIN policy_registeredreference r ON r.case_id=c.case_id AND r.ref=CASE WHEN jsonb_typeof(item.value)='object' THEN item.value->>'artifact_ref' ELSE item.value#>>'{}' END
 AND r.version=CASE WHEN jsonb_typeof(item.value)='object' THEN (item.value->>'artifact_version')::integer ELSE 1 END) END
 FROM policy_configuration c WHERE c.id=pid;
$$;
CREATE OR REPLACE FUNCTION psl_schedules_binding_current(pid bigint) RETURNS boolean LANGUAGE plpgsql STABLE AS $$
DECLARE ap record; bound jsonb; item jsonb; path text[];
BEGIN
 SELECT a.*,s.binding_paths,s.configuration_id AS origin_id,c.case_id AS origin_case,t.case_id AS target_case INTO ap
 FROM policy_scopeapplication a JOIN policy_scopeversion s ON s.id=a.source_id JOIN policy_configuration c ON c.id=s.configuration_id
 JOIN policy_configuration t ON t.id=a.configuration_id WHERE a.configuration_id=pid;
 IF NOT FOUND THEN RETURN true; END IF;
 bound:=psl_schedules_values(ap.origin_id);
 FOR item IN SELECT value FROM jsonb_array_elements(ap.bindings) LOOP
  IF NOT ap.binding_paths ? (item->>'path') THEN RETURN false; END IF;
  SELECT array_agg(replace(replace(part,'~1','/'),'~0','~') ORDER BY ordinality) INTO path FROM unnest(string_to_array(substr(item->>'path',2),'/')) WITH ORDINALITY p(part,ordinality);
  IF bound#>path IS NULL OR jsonb_typeof(bound#>path) IN ('object','array') THEN RETURN false; END IF;
  bound:=jsonb_set(bound,path,item->'value',false);
 END LOOP;
 IF ap.origin_case<>ap.target_case AND jsonb_array_length(ap.bindings)<>jsonb_array_length(ap.binding_paths) THEN RETURN false; END IF;
 RETURN bound IS NOT DISTINCT FROM psl_schedules_values(pid);
END;
$$;
CREATE OR REPLACE FUNCTION psl_schedules_envelope_current(pid bigint) RETURNS boolean LANGUAGE sql STABLE AS $$
 SELECT EXISTS(SELECT 1 FROM policy_configuration c JOIN core_case k ON k.id=c.case_id WHERE c.id=pid
 AND c.envelope->'subject_scope'=jsonb_build_object('kind',CASE WHEN k.kind='project' THEN 'project' ELSE 'service' END,'ref',k.id::text)
 AND (c.envelope->>'fixture_scope'='synthetic_test')=k.synthetic
 AND (c.component NOT IN ('SCHEDULES.review_authority','AF13.owner_validation_rules') OR NOT EXISTS(
 SELECT 1 FROM jsonb_array_elements(psl_schedules_values(c.id)) v CROSS JOIN LATERAL jsonb_array_elements(v->'assignments') a
 WHERE NOT EXISTS(SELECT 1 FROM auth_user WHERE id=(a->>'user_id')::bigint AND is_active)))
 AND (c.component<>'D05.role_principal_assignments' OR NOT EXISTS(
 SELECT 1 FROM jsonb_array_elements(psl_schedules_values(c.id)) v WHERE NOT EXISTS(SELECT 1 FROM auth_user WHERE id=(v->>'user_id')::bigint AND is_active))));
$$;
CREATE OR REPLACE FUNCTION psl_schedules_policy_status(cid uuid, component_name text) RETURNS text LANGUAGE plpgsql STABLE AS $$
DECLARE c record; ap record; life text; source_life text;
BEGIN
 SELECT cfg.*,(SELECT state FROM policy_policystate WHERE configuration_id=cfg.id ORDER BY id DESC LIMIT 1) AS lifecycle INTO c
 FROM policy_configuration cfg WHERE cfg.case_id=cid AND cfg.component=component_name
 AND (SELECT state FROM policy_policystate WHERE configuration_id=cfg.id ORDER BY id DESC LIMIT 1) IN ('active','revoked','superseded') ORDER BY cfg.revision DESC LIMIT 1;
 IF NOT FOUND THEN RETURN 'MISSING'; END IF;
 IF c.lifecycle='revoked' THEN RETURN 'REVOKED'; END IF;
 SELECT a.*,s.kind,s.ref,s.revision,s.configuration_id AS origin_id,o.case_id AS origin_case,o.component AS origin_component,o.envelope AS origin_envelope,
 (SELECT state FROM policy_scopestate WHERE source_id=s.id ORDER BY id DESC LIMIT 1) AS lifecycle INTO ap
 FROM policy_scopeapplication a JOIN policy_scopeversion s ON s.id=a.source_id JOIN policy_configuration o ON o.id=s.configuration_id WHERE a.configuration_id=c.id;
 IF FOUND THEN
  IF NOT psl_schedules_grants(c.case_id,ap.actor_id,ARRAY['case.read','policy.configure'])
   OR NOT psl_schedules_grants(ap.origin_case,ap.actor_id,ARRAY['case.read','policy.read'])
   OR NOT EXISTS(SELECT 1 FROM core_case t JOIN core_case o ON o.id=ap.origin_case WHERE t.id=c.case_id AND t.tenant=o.tenant AND t.synthetic=o.synthetic)
   OR c.component<>ap.origin_component OR (ap.kind<>'organization' AND c.case_id<>ap.origin_case)
   OR NOT psl_schedules_binding_current(c.id)
   OR EXISTS(SELECT 1 FROM unnest(ARRAY['effective_from','effective_until','implementation_id','implementation_version','reviewed_implementation_ref','component_schema_ref','schema_version','fixture_scope']) f WHERE c.envelope->f IS DISTINCT FROM ap.origin_envelope->f)
  THEN RETURN 'INVALID'; END IF;
  IF ap.lifecycle='revoked' THEN RETURN 'REVOKED'; END IF;
  IF ap.lifecycle<>'active' OR EXISTS(SELECT 1 FROM policy_scopeversion n JOIN policy_configuration nc ON nc.id=n.configuration_id WHERE nc.case_id=ap.origin_case AND nc.component=ap.origin_component AND n.kind=ap.kind AND n.ref=ap.ref AND n.revision>ap.revision AND EXISTS(SELECT 1 FROM policy_scopestate WHERE source_id=n.id AND state IN ('active','revoked')))
   OR NOT EXISTS(SELECT 1 FROM policy_scopestate s WHERE s.id=(SELECT max(id) FROM policy_scopestate WHERE source_id=ap.source_id AND state='active') AND psl_schedules_grants(ap.origin_case,s.actor_id,ARRAY['case.read','policy.activate']))
   OR NOT EXISTS(SELECT 1 FROM core_case k WHERE k.id=ap.origin_case AND ((ap.kind='organization' AND ap.ref=k.tenant) OR (ap.kind='project' AND k.kind='project' AND ap.ref=k.id::text) OR (ap.kind='service' AND k.kind='support' AND ap.ref=k.id::text) OR (ap.kind='contract' AND EXISTS(SELECT 1 FROM core_evidence e WHERE e.case_id=k.id AND e.kind='sow' AND ap.ref='evidence:'||e.id::text))))
   OR (SELECT state FROM policy_policystate WHERE configuration_id=ap.origin_id ORDER BY id DESC LIMIT 1)<>'validated'
   OR NOT psl_schedules_envelope_current(ap.origin_id)
  THEN RETURN 'INVALID'; END IF;
  IF (ap.origin_envelope->>'effective_from')::timestamptz>clock_timestamp() THEN RETURN 'MISSING'; END IF;
  IF (ap.origin_envelope->>'effective_until')::timestamptz<=clock_timestamp() THEN RETURN 'EXPIRED'; END IF;
 END IF;
 IF NOT psl_schedules_envelope_current(c.id) THEN RETURN 'INVALID'; END IF;
 IF (c.envelope->>'effective_from')::timestamptz>clock_timestamp() THEN RETURN 'MISSING'; END IF;
 IF (c.envelope->>'effective_until')::timestamptz<=clock_timestamp() THEN RETURN 'EXPIRED'; END IF;
 RETURN 'ACTIVE';
END;
$$;
CREATE OR REPLACE FUNCTION psl_schedules_policy_current(cid uuid, pid bigint) RETURNS boolean LANGUAGE sql STABLE AS $$
 SELECT EXISTS(SELECT 1 FROM policy_configuration c WHERE c.id=pid AND c.case_id=cid
 AND c.id=(SELECT cc.id FROM policy_configuration cc WHERE cc.case_id=cid AND cc.component=c.component AND (SELECT state FROM policy_policystate WHERE configuration_id=cc.id ORDER BY id DESC LIMIT 1) IN ('active','revoked','superseded') ORDER BY cc.revision DESC LIMIT 1)
 AND psl_schedules_policy_status(cid,c.component)='ACTIVE');
$$;
CREATE OR REPLACE FUNCTION psl_schedules_authority_current(cid uuid, authority jsonb) RETURNS boolean LANGUAGE sql STABLE AS $$
 SELECT NOT EXISTS(SELECT 1 FROM jsonb_each(authority) pin WHERE jsonb_typeof(pin.value)='number'
  AND pin.key<>'D05.decision_action_matrix' AND NOT psl_schedules_policy_current(cid,(pin.value::text)::bigint));
$$;
CREATE OR REPLACE FUNCTION psl_schedules_role_current(cid uuid, uid bigint, authority jsonb, required_role text DEFAULT 'Finance') RETURNS boolean LANGUAGE sql STABLE AS $$
 WITH assignments AS (SELECT ref.content FROM policy_configuration c
  CROSS JOIN LATERAL jsonb_array_elements_text(c.envelope->'value') selection(ref)
  JOIN policy_registeredreference ref ON ref.case_id=c.case_id AND ref.ref=selection.ref AND ref.version=1
  WHERE c.id=(authority->>'D05.role_principal_assignments')::bigint AND psl_schedules_policy_current(cid,c.id)
   AND ref.content->>'user_id'=uid::text)
 SELECT EXISTS(SELECT 1 FROM assignments WHERE content->>'role'=required_role)
  AND ((SELECT count(DISTINCT content->>'role') FROM assignments)=1
   OR ((SELECT bool_and(content ? 'eligibility') FROM assignments)
    AND (SELECT bool_and((content->'eligibility'->>'valid_from')::timestamptz<=clock_timestamp()
     AND (content->'eligibility'->>'valid_until')::timestamptz>clock_timestamp()) FROM assignments))
   OR ((SELECT synthetic FROM core_case WHERE id=cid) AND NOT (SELECT bool_and(content ? 'eligibility') FROM assignments)));
$$;
CREATE OR REPLACE FUNCTION psl_schedules_finance_review_current(rid bigint) RETURNS boolean LANGUAGE sql STABLE AS $$
 SELECT EXISTS(SELECT 1 FROM finance_financereview r WHERE r.id=rid AND r.verdict='approve'
  AND psl_schedules_grants(r.case_id,r.actor_id,ARRAY['finance.review'])
  AND psl_schedules_authority_current(r.case_id,r.authority)
  AND psl_schedules_role_current(r.case_id,r.actor_id,r.authority)
  AND EXISTS(SELECT 1 FROM policy_configuration c JOIN policy_registeredreference ref
   ON ref.case_id=c.case_id AND ref.ref=c.envelope->'value'->>'artifact_ref'
    AND ref.version=(c.envelope->'value'->>'artifact_version')::integer AND ref.sha256=c.envelope->'value'->>'sha256'
   WHERE c.case_id=r.case_id AND c.component='D05.decision_action_matrix' AND psl_schedules_policy_current(r.case_id,c.id)
    AND ref.content->'finance' @> jsonb_build_array(r.authority->'finance_review_rule'))
  AND r.id=(SELECT max(x.id) FROM finance_financereview x WHERE x.case_id=r.case_id AND x.purpose=r.purpose
   AND x.source_id IS NOT DISTINCT FROM r.source_id AND x.configuration_id IS NOT DISTINCT FROM r.configuration_id
   AND x.adjustment_id IS NOT DISTINCT FROM r.adjustment_id AND x.run_id IS NOT DISTINCT FROM r.run_id));
$$;
CREATE OR REPLACE FUNCTION psl_schedules_mapping_current(nid bigint) RETURNS boolean LANGUAGE sql STABLE AS $$
 SELECT EXISTS(SELECT 1 FROM finance_financerun n JOIN finance_financesource src ON src.id=n.source_id
  WHERE n.id=nid AND src.id=(SELECT max(id) FROM finance_financesource WHERE batch_id=src.batch_id) AND n.kind='mapping' AND n.result->>'status'='complete' AND src.completeness='complete'
   AND psl_schedules_grants(n.case_id,n.actor_id,ARRAY['case.read','finance.read','finance.calculate'])
   AND psl_schedules_finance_review_current((n.snapshot->'source_review'->>'id')::bigint)
   AND NOT EXISTS(SELECT 1 FROM jsonb_each(n.snapshot->'policies') pin
    WHERE pin.value->>'status'<>'ACTIVE' OR NOT psl_schedules_policy_current(n.case_id,(pin.value->>'id')::bigint))
   AND NOT EXISTS(SELECT 1 FROM jsonb_each(n.snapshot->'reviews') pin
    WHERE pin.value->'valid'<>'true'::jsonb OR NOT psl_schedules_finance_review_current((pin.value->>'id')::bigint))
   AND NOT EXISTS(SELECT 1 FROM jsonb_array_elements(n.snapshot->'adjustments') pin
    WHERE NOT psl_schedules_finance_review_current((pin->'review'->>'id')::bigint)
     OR EXISTS(SELECT 1 FROM finance_financeadjustment old JOIN finance_financeadjustment newer
      ON newer.source_id=old.source_id AND newer.reference=old.reference AND newer.number>old.number
      WHERE old.id=(pin->>'id')::bigint)));
$$;
CREATE OR REPLACE FUNCTION psl_schedules_policy_pin_current(cid uuid, component_name text, pin jsonb) RETURNS boolean LANGUAGE sql STABLE AS $$
 SELECT COALESCE((pin->>'status'='ACTIVE' AND psl_schedules_policy_current(cid,(pin->>'id')::bigint))
  OR (pin->'id'='null'::jsonb AND pin->>'status'<>'ACTIVE' AND pin->>'status'=psl_schedules_policy_status(cid,component_name)),false);
$$;
CREATE OR REPLACE FUNCTION psl_schedules_package_current(pid bigint) RETURNS boolean LANGUAGE sql STABLE AS $$
 SELECT EXISTS(SELECT 1 FROM documents_validationpackage p WHERE p.id=pid
  AND NOT EXISTS(SELECT 1 FROM documents_validationpackage n WHERE n.case_id=p.case_id AND n.reference=p.reference AND n.version>p.version)
  AND NOT EXISTS(SELECT 1 FROM jsonb_array_elements(p.manifest->'sources') pin WHERE NOT EXISTS(
   SELECT 1 FROM documents_discoverysource d WHERE d.id=(pin->>0)::bigint AND d.case_id=p.case_id AND d.sha256=pin->>1
    AND NOT EXISTS(SELECT 1 FROM documents_discoverysource n WHERE n.case_id=d.case_id AND n.reference=d.reference AND n.version>d.version)))
  AND NOT EXISTS(SELECT 1 FROM jsonb_array_elements(p.manifest->'examples') pin WHERE NOT EXISTS(
   SELECT 1 FROM documents_validationexample e JOIN core_evidence ce ON ce.id=e.evidence_id WHERE e.id=(pin->>0)::bigint AND e.case_id=p.case_id AND ce.sha256=pin->>2
    AND NOT EXISTS(SELECT 1 FROM documents_validationexample n WHERE n.case_id=e.case_id AND n.reference=e.reference AND n.version>e.version)))
  AND NOT EXISTS(SELECT 1 FROM jsonb_each(p.manifest->'policies') pin WHERE NOT psl_schedules_policy_pin_current(p.case_id,pin.key,pin.value)));
$$;
CREATE OR REPLACE FUNCTION psl_schedules_validation_review_current(rid bigint) RETURNS boolean LANGUAGE sql STABLE AS $$
 SELECT EXISTS(SELECT 1 FROM documents_validationreview r JOIN documents_validationpackage p ON p.id=r.package_id
 WHERE r.id=rid AND r.verdict='approve' AND psl_schedules_package_current(p.id)
  AND r.snapshot->>'package'=p.sha256
  AND r.id=(SELECT max(id) FROM documents_validationreview WHERE package_id=p.id AND kind=r.kind)
  AND psl_schedules_grants(p.case_id,r.actor_id,ARRAY[CASE WHEN r.kind='acceptance' THEN 'validation.accept' ELSE 'validation.review' END])
  AND psl_schedules_authority_current(p.case_id,r.authority)
  AND EXISTS(SELECT 1 FROM policy_configuration owner JOIN policy_registeredreference ref ON ref.case_id=owner.case_id
   AND ref.ref=owner.envelope->'value'->>'artifact_ref' AND ref.version=(owner.envelope->'value'->>'artifact_version')::integer
   CROSS JOIN LATERAL jsonb_array_elements(ref.content->'assignments') assignment
   WHERE owner.id=(r.authority->>'AF13.owner_validation_rules')::bigint
    AND assignment->>'user_id'=r.actor_id::text AND assignment->'purposes' ? r.kind
    AND psl_schedules_role_current(p.case_id,r.actor_id,r.authority,assignment->>'role'))
  AND (r.kind='meaning' OR (r.snapshot->>'meaning'=(SELECT max(id)::text FROM documents_validationreview WHERE package_id=p.id AND kind='meaning')
   AND psl_schedules_validation_review_current((r.snapshot->>'meaning')::bigint)))
  AND (r.kind<>'acceptance' OR (psl_schedules_policy_current(p.case_id,(r.snapshot->>'criteria')::bigint)
   AND r.snapshot->>'expectations'=(SELECT max(id)::text FROM documents_validationreview WHERE package_id=p.id AND kind='expectations')
   AND psl_schedules_validation_review_current((r.snapshot->>'expectations')::bigint)
   AND NOT EXISTS(SELECT 1 FROM jsonb_array_elements_text(r.snapshot->'replays') replay WHERE NOT EXISTS(
    SELECT 1 FROM documents_validationreplay vr WHERE vr.id=replay::bigint AND vr.package_id=p.id
     AND vr.expectation_review_id=(r.snapshot->>'expectations')::bigint AND vr.result->'matches'='true'::jsonb
     AND psl_schedules_grants(p.case_id,vr.actor_id,ARRAY['validation.replay.record'])
     AND vr.id=(SELECT max(id) FROM documents_validationreplay WHERE package_id=p.id AND example_id=vr.example_id))))));
$$;
CREATE OR REPLACE FUNCTION psl_schedules_current(sid bigint) RETURNS boolean LANGUAGE sql STABLE AS $$
 SELECT EXISTS(SELECT 1 FROM finance_schedulework s WHERE s.id=sid AND s.kind IN ('income','inventory')
  AND psl_schedules_grants(s.case_id,s.actor_id,ARRAY['case.read','finance.read','schedules.read','schedules.prepare'])
  AND NOT EXISTS(SELECT 1 FROM finance_schedulework n WHERE n.case_id=s.case_id AND n.kind=s.kind AND n.reference=s.reference AND n.version>s.version)
  AND s.snapshot->'policy'->>'status'='ACTIVE' AND psl_schedules_policy_current(s.case_id,(s.snapshot->'policy'->>'id')::bigint)
  AND (s.parent_id IS NULL OR (psl_schedules_grants(s.case_id,s.actor_id,ARRAY['finance.calculate']) AND psl_schedules_mapping_current(s.parent_id)))
  AND NOT EXISTS(SELECT 1 FROM jsonb_array_elements(s.snapshot->'packages') pin WHERE NOT EXISTS(
   SELECT 1 FROM documents_validationpackage p WHERE p.id=(pin->>'id')::bigint AND p.case_id=s.case_id AND p.sha256=pin->>'sha256' AND p.reference=pin->>'schedule'
    AND psl_schedules_package_current(p.id)
    AND NOT EXISTS(SELECT 1 FROM jsonb_array_elements(pin->'reviews') rp WHERE
     (rp->>'id')::bigint IS DISTINCT FROM (SELECT max(id) FROM documents_validationreview WHERE package_id=p.id AND kind=rp->>'purpose')
     OR (rp->>'valid')::boolean IS DISTINCT FROM psl_schedules_validation_review_current((rp->>'id')::bigint)))))
$$;
CREATE OR REPLACE FUNCTION psl_schedules_review_current(rid bigint) RETURNS boolean LANGUAGE sql STABLE AS $$
 SELECT EXISTS(SELECT 1 FROM finance_schedulereview r JOIN finance_schedulework w ON w.id=r.work_id
  WHERE r.id=rid AND r.verdict='approve' AND r.snapshot=w.snapshot AND psl_schedules_current(w.id)
   AND psl_schedules_grants(w.case_id,r.actor_id,ARRAY['case.read','finance.read','schedules.read','schedules.review'])
   AND psl_schedules_authority_current(w.case_id,r.authority) AND psl_schedules_role_current(w.case_id,r.actor_id,r.authority)
   AND r.id=(SELECT max(id) FROM finance_schedulereview WHERE work_id=w.id));
$$;

CREATE OR REPLACE FUNCTION psl_ppe_policy_people_current(pid bigint) RETURNS boolean LANGUAGE sql STABLE AS $$
 SELECT EXISTS(SELECT 1 FROM policy_configuration c WHERE c.id=pid AND
  CASE WHEN c.component IN ('F07.review_authority','AF13.owner_validation_rules') THEN
   EXISTS(SELECT 1 FROM policy_registeredreference r WHERE r.case_id=c.case_id
    AND r.ref=c.envelope->'value'->>'artifact_ref' AND r.version=(c.envelope->'value'->>'artifact_version')::integer
    AND r.sha256=c.envelope->'value'->>'sha256'
    AND NOT EXISTS(SELECT 1 FROM jsonb_array_elements(r.content->'assignments') assignment
     WHERE NOT EXISTS(SELECT 1 FROM auth_user u WHERE u.id=(assignment->>'user_id')::bigint AND u.is_active)))
  WHEN c.component='D05.role_principal_assignments' THEN
   NOT EXISTS(SELECT 1 FROM jsonb_array_elements_text(c.envelope->'value') selection(ref)
    LEFT JOIN policy_registeredreference r ON r.case_id=c.case_id AND r.ref=selection.ref AND r.version=1
    LEFT JOIN auth_user u ON u.id=(r.content->>'user_id')::bigint
    WHERE r.id IS NULL OR u.id IS NULL OR NOT u.is_active)
  ELSE true END);
$$;
CREATE OR REPLACE FUNCTION psl_ppe_policy_current(cid uuid, pid bigint) RETURNS boolean LANGUAGE sql STABLE AS $$
 SELECT EXISTS(SELECT 1 FROM policy_configuration c JOIN core_case target_case ON target_case.id=c.case_id
  WHERE c.id=pid AND c.case_id=cid AND psl_ppe_policy_people_current(c.id)
  AND c.envelope->'subject_scope'=jsonb_build_object('kind',CASE WHEN target_case.kind='project' THEN 'project' ELSE 'service' END,'ref',c.case_id::text)
  AND (c.envelope->>'fixture_scope'='synthetic_test')=target_case.synthetic
  AND (SELECT state FROM policy_policystate WHERE configuration_id=c.id ORDER BY id DESC LIMIT 1)='active'
  AND (c.envelope->>'effective_from')::timestamptz<=clock_timestamp()
  AND (c.envelope->>'effective_until' IS NULL OR (c.envelope->>'effective_until')::timestamptz>clock_timestamp())
  AND NOT EXISTS(SELECT 1 FROM policy_scopeapplication ap
   JOIN policy_scopeversion sv ON sv.id=ap.source_id JOIN policy_configuration origin ON origin.id=sv.configuration_id
   JOIN core_case origin_case ON origin_case.id=origin.case_id
   WHERE ap.configuration_id=c.id AND (
    NOT psl_ppe_policy_people_current(origin.id) OR target_case.tenant<>origin_case.tenant OR target_case.synthetic<>origin_case.synthetic
    OR c.component<>origin.component OR (sv.kind<>'organization' AND c.case_id<>origin.case_id)
    OR NOT ((sv.kind='organization' AND sv.ref=origin_case.tenant)
     OR (sv.kind='project' AND origin_case.kind='project' AND sv.ref=origin.case_id::text)
     OR (sv.kind='service' AND origin_case.kind='support' AND sv.ref=origin.case_id::text)
     OR (sv.kind='contract' AND EXISTS(SELECT 1 FROM core_evidence e WHERE e.case_id=origin.case_id AND e.kind='sow' AND sv.ref='evidence:'||e.id::text)))
    OR sv.id IS DISTINCT FROM (SELECT family.id FROM policy_scopeversion family
     JOIN policy_configuration fc ON fc.id=family.configuration_id
     WHERE fc.case_id=origin.case_id AND fc.component=origin.component AND family.kind=sv.kind AND family.ref=sv.ref
      AND EXISTS(SELECT 1 FROM policy_scopestate fs WHERE fs.source_id=family.id AND fs.state IN ('active','revoked'))
     ORDER BY family.revision DESC LIMIT 1)
    OR EXISTS(SELECT 1 FROM unnest(ARRAY['effective_from','effective_until','implementation_id','implementation_version','reviewed_implementation_ref','component_schema_ref','schema_version','fixture_scope']) k
     WHERE c.envelope->k IS DISTINCT FROM origin.envelope->k)
    OR origin.envelope->'subject_scope'<>jsonb_build_object('kind',CASE WHEN origin_case.kind='project' THEN 'project' ELSE 'service' END,'ref',origin.case_id::text)
    OR (origin.envelope->>'fixture_scope'='synthetic_test')<>origin_case.synthetic
    OR (SELECT state FROM policy_scopestate WHERE source_id=sv.id ORDER BY id DESC LIMIT 1)<>'active'
    OR (SELECT state FROM policy_policystate WHERE configuration_id=origin.id ORDER BY id DESC LIMIT 1)<>'validated'
    OR NOT EXISTS(SELECT 1 FROM auth_user u WHERE u.id=ap.actor_id AND u.is_active)
    OR NOT EXISTS(SELECT 1 FROM identity_grant WHERE user_id=ap.actor_id AND case_id=c.case_id AND action='case.read' AND active)
    OR NOT EXISTS(SELECT 1 FROM identity_grant WHERE user_id=ap.actor_id AND case_id=c.case_id AND action='policy.configure' AND active)
    OR NOT EXISTS(SELECT 1 FROM identity_grant WHERE user_id=ap.actor_id AND case_id=origin.case_id AND action='case.read' AND active)
    OR NOT EXISTS(SELECT 1 FROM identity_grant WHERE user_id=ap.actor_id AND case_id=origin.case_id AND action='policy.read' AND active)
    OR NOT EXISTS(SELECT 1 FROM policy_scopestate activation JOIN auth_user u ON u.id=activation.actor_id
     WHERE activation.id=(SELECT max(id) FROM policy_scopestate WHERE source_id=sv.id AND state='active')
      AND u.is_active AND EXISTS(SELECT 1 FROM identity_grant WHERE user_id=u.id AND case_id=origin.case_id AND action='case.read' AND active)
      AND EXISTS(SELECT 1 FROM identity_grant WHERE user_id=u.id AND case_id=origin.case_id AND action='policy.activate' AND active)))));

$$;
CREATE OR REPLACE FUNCTION psl_ppe_grants(cid uuid, uid bigint, actions text[]) RETURNS boolean LANGUAGE sql STABLE AS $$
 SELECT EXISTS(SELECT 1 FROM auth_user WHERE id=uid AND is_active)
  AND NOT EXISTS(SELECT 1 FROM unnest(actions) required(action_name) WHERE NOT EXISTS(
   SELECT 1 FROM identity_grant g WHERE g.case_id=cid AND g.user_id=uid AND g.action=required.action_name AND g.active));
$$;
CREATE OR REPLACE FUNCTION psl_ppe_authority_current(cid uuid, authority jsonb) RETURNS boolean LANGUAGE sql STABLE AS $$
 SELECT NOT EXISTS(SELECT 1 FROM jsonb_each(authority) pin WHERE jsonb_typeof(pin.value)='number'
  AND pin.key<>'D05.decision_action_matrix' AND NOT psl_ppe_policy_current(cid,(pin.value::text)::bigint));
$$;
CREATE OR REPLACE FUNCTION psl_ppe_role_current(cid uuid, uid bigint, authority jsonb) RETURNS boolean LANGUAGE sql STABLE AS $$
 SELECT EXISTS(SELECT 1 FROM policy_configuration c
  CROSS JOIN LATERAL jsonb_array_elements_text(c.envelope->'value') selection(ref)
  JOIN policy_registeredreference r ON r.case_id=c.case_id AND r.ref=selection.ref AND r.version=1
  WHERE c.id=(authority->>'D05.role_principal_assignments')::bigint AND psl_ppe_policy_current(cid,c.id)
   AND r.content->>'user_id'=uid::text AND r.content->>'role'='Finance'
   AND (NOT r.content ? 'eligibility' OR
    ((r.content->'eligibility'->>'valid_from')::timestamptz<=clock_timestamp()
     AND (r.content->'eligibility'->>'valid_until')::timestamptz>clock_timestamp())));
$$;
CREATE OR REPLACE FUNCTION psl_ppe_finance_review_current(rid bigint) RETURNS boolean LANGUAGE sql STABLE AS $$
 SELECT EXISTS(SELECT 1 FROM finance_financereview r WHERE r.id=rid AND r.verdict='approve'
  AND psl_ppe_grants(r.case_id,r.actor_id,ARRAY['finance.review'])
  AND psl_ppe_authority_current(r.case_id,r.authority)
  AND psl_ppe_role_current(r.case_id,r.actor_id,r.authority)
  AND EXISTS(SELECT 1 FROM policy_configuration c JOIN policy_registeredreference ref
   ON ref.case_id=c.case_id AND ref.ref=c.envelope->'value'->>'artifact_ref'
    AND ref.version=(c.envelope->'value'->>'artifact_version')::integer AND ref.sha256=c.envelope->'value'->>'sha256'
   WHERE c.case_id=r.case_id AND c.component='D05.decision_action_matrix' AND psl_ppe_policy_current(r.case_id,c.id)
    AND ref.content->'finance' @> jsonb_build_array(r.authority->'finance_review_rule'))
  AND r.id=(SELECT max(x.id) FROM finance_financereview x WHERE x.case_id=r.case_id AND x.purpose=r.purpose
   AND x.source_id IS NOT DISTINCT FROM r.source_id AND x.configuration_id IS NOT DISTINCT FROM r.configuration_id
   AND x.adjustment_id IS NOT DISTINCT FROM r.adjustment_id AND x.run_id IS NOT DISTINCT FROM r.run_id));
$$;
CREATE OR REPLACE FUNCTION psl_ppe_mapping_current(nid bigint) RETURNS boolean LANGUAGE sql STABLE AS $$
 SELECT EXISTS(SELECT 1 FROM finance_financerun n JOIN finance_financesource src ON src.id=n.source_id
  WHERE n.id=nid AND n.kind='mapping' AND n.result->>'status'='complete' AND src.completeness='complete'
   AND psl_ppe_grants(n.case_id,n.actor_id,ARRAY['case.read','finance.read','finance.calculate'])
   AND psl_ppe_finance_review_current((n.snapshot->'source_review'->>'id')::bigint)
   AND NOT EXISTS(SELECT 1 FROM jsonb_each(n.snapshot->'policies') pin
    WHERE pin.value->>'status'<>'ACTIVE' OR NOT psl_ppe_policy_current(n.case_id,(pin.value->>'id')::bigint))
   AND NOT EXISTS(SELECT 1 FROM jsonb_each(n.snapshot->'reviews') pin
    WHERE pin.value->'valid'<>'true'::jsonb OR NOT psl_ppe_finance_review_current((pin.value->>'id')::bigint))
   AND NOT EXISTS(SELECT 1 FROM jsonb_array_elements(n.snapshot->'adjustments') pin
    WHERE NOT psl_ppe_finance_review_current((pin->'review'->>'id')::bigint)
     OR EXISTS(SELECT 1 FROM finance_financeadjustment old JOIN finance_financeadjustment newer
      ON newer.source_id=old.source_id AND newer.reference=old.reference AND newer.number>old.number
      WHERE old.id=(pin->>'id')::bigint)));
$$;
CREATE OR REPLACE FUNCTION psl_ppe_review_current(rid bigint) RETURNS boolean LANGUAGE sql STABLE AS $$
 SELECT EXISTS(SELECT 1 FROM finance_schedulereview r JOIN finance_schedulework w ON w.id=r.work_id
  WHERE r.id=rid AND r.verdict='approve' AND r.snapshot=w.snapshot
   AND psl_ppe_grants(w.case_id,r.actor_id,ARRAY['case.read','finance.read','ppe.read','ppe.review'])
   AND psl_ppe_authority_current(w.case_id,r.authority)
   AND psl_ppe_role_current(w.case_id,r.actor_id,r.authority)
   AND r.id=(SELECT max(x.id) FROM finance_schedulereview x WHERE x.work_id=w.id AND x.authority->>'purpose'=r.authority->>'purpose'));
$$;
CREATE OR REPLACE FUNCTION psl_ppe_schedule_current(sid bigint, depth integer DEFAULT 0) RETURNS boolean LANGUAGE plpgsql STABLE AS $$
DECLARE s finance_schedulework; r finance_schedulework; basis bigint; prior_id bigint; pin jsonb;
BEGIN
 IF depth>36 THEN RETURN false; END IF;
 SELECT * INTO s FROM finance_schedulework WHERE id=sid AND kind='ppe_schedule';
 IF NOT FOUND OR s.result->>'status'<>'ready' THEN RETURN false; END IF;
 SELECT * INTO r FROM finance_schedulework WHERE id=(s.payload->>'register_id')::bigint AND case_id=s.case_id AND kind='ppe_register';
 IF NOT FOUND THEN RETURN false; END IF;
 IF NOT psl_ppe_grants(s.case_id,s.actor_id,ARRAY['case.read','finance.read','ppe.read','ppe.prepare'])
  OR NOT psl_ppe_grants(r.case_id,r.actor_id,ARRAY['case.read','finance.read','ppe.read','ppe.capture'])
  OR NOT psl_ppe_review_current((s.snapshot->>'register_review')::bigint)
  OR s.snapshot->'register'<>jsonb_build_array(r.id,r.sha256)
  OR EXISTS(SELECT 1 FROM finance_schedulework newer WHERE newer.case_id=s.case_id
   AND ((newer.kind=s.kind AND newer.reference=s.reference AND newer.version>s.version)
    OR (newer.kind=r.kind AND newer.reference=r.reference AND newer.version>r.version))) THEN RETURN false; END IF;
 SELECT max(id) INTO basis FROM finance_schedulereview WHERE work_id=r.id AND authority->>'purpose'='basis';
 IF basis IS DISTINCT FROM (s.snapshot->>'basis_review')::bigint
  OR (s.snapshot->>'basis_approved')::boolean IS DISTINCT FROM psl_ppe_review_current(basis)
  OR (r.result->'date_basis_ambiguous'='true'::jsonb AND NOT psl_ppe_review_current(basis)) THEN RETURN false; END IF;
 IF EXISTS(SELECT 1 FROM jsonb_each(s.snapshot->'policies') p WHERE p.value->>'status'<>'ACTIVE'
   OR NOT psl_ppe_policy_current(s.case_id,(p.value->>'id')::bigint)) THEN RETURN false; END IF;
 IF s.parent_id IS NOT NULL AND NOT psl_ppe_mapping_current(s.parent_id) THEN RETURN false; END IF;
 IF NOT EXISTS(SELECT 1 FROM policy_configuration c JOIN policy_registeredreference ref
   ON ref.case_id=c.case_id AND ref.ref=c.envelope->'value'->>'artifact_ref'
    AND ref.version=(c.envelope->'value'->>'artifact_version')::integer AND ref.sha256=c.envelope->'value'->>'sha256'
   WHERE c.id=(s.snapshot->'policies'->'F07.source_rules'->>'id')::bigint
    AND EXTRACT(EPOCH FROM (clock_timestamp()-(r.payload->>'extracted_at')::timestamptz))<=(ref.content->>'max_age_seconds')::numeric)
 THEN RETURN false; END IF;
 prior_id=(s.payload->>'prior_id')::bigint;
 IF prior_id IS NOT NULL AND (NOT psl_ppe_schedule_current(prior_id,depth+1)
  OR NOT psl_ppe_review_current((s.snapshot->'prior'->>2)::bigint)) THEN RETURN false; END IF;
 IF s.snapshot->'owner_validation'->'valid'='true'::jsonb THEN
  FOR pin IN SELECT value FROM jsonb_array_elements(s.snapshot->'owner_validation'->'reviews') LOOP
   IF NOT EXISTS(SELECT 1 FROM documents_validationreview vr JOIN documents_validationpackage vp ON vp.id=vr.package_id
    WHERE vr.id=(pin::text)::bigint AND vr.package_id=(s.snapshot->'owner_validation'->>'id')::bigint
     AND vr.verdict='approve' AND psl_ppe_authority_current(s.case_id,vr.authority)
     AND psl_ppe_grants(s.case_id,vr.actor_id,ARRAY['case.read','validation.read',CASE WHEN vr.kind='acceptance' THEN 'validation.accept' ELSE 'validation.review' END])
     AND vr.id=(SELECT max(id) FROM documents_validationreview WHERE package_id=vr.package_id AND kind=vr.kind)) THEN RETURN false; END IF;
  END LOOP;
 END IF;
 RETURN true;
END $$;

CREATE OR REPLACE FUNCTION psl_factory_identity() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
 IF TG_OP='DELETE' THEN RAISE EXCEPTION 'Factory history cannot be deleted'; END IF;
 IF TG_OP='UPDATE' THEN
  IF (NEW.case_id,NEW.actor_id,NEW.key,NEW.definition,NEW.request,NEW.request_hash,NEW.created_at)
    IS DISTINCT FROM (OLD.case_id,OLD.actor_id,OLD.key,OLD.definition,OLD.request,OLD.request_hash,OLD.created_at)
    OR NEW.budget_used<OLD.budget_used OR NEW.fence<OLD.fence OR NEW.revision<OLD.revision
    OR (OLD.budget_used>0 AND NEW.budget_limit<>OLD.budget_limit)
  THEN RAISE EXCEPTION 'Immutable factory identity and monotonic shared budget required'; END IF;
  IF OLD.source_head_id IS NOT NULL AND NEW.source_head_id IS DISTINCT FROM OLD.source_head_id
   AND (NEW.source_head_id IS NULL OR NOT EXISTS(SELECT 1 FROM core_evidence n JOIN core_evidence o ON o.id=OLD.source_head_id WHERE n.id=NEW.source_head_id AND n.version>o.version))
  THEN RAISE EXCEPTION 'Forward native source successor required'; END IF;
 END IF;
 IF NEW.definition NOT IN ('finance-ledger/v1','engagement/v1','pmo-minutes/v1','pmo-finance/v1','planning/v1','commercial/v1','delivery-release/v1','delivery-hypercare/v1','delivery-archive/v1','delivery-handover/v1','delivery-closure/v1','delivery-go-live/v1','finance-accounts/v1','rfp-response/v1','finance-schedules/v1','finance-ppe/v1','pmo-change/v1','finance-forecast/v1','finance-payroll/v1','pmo-emergency/v1','finance-bu/v1','pmo-weekly-report/v1','pmo-escalation/v1') THEN RAISE EXCEPTION 'Closed factory definition required'; END IF;
 IF (NEW.invoice_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM finance_invoice i WHERE i.id=NEW.invoice_id AND i.case_id=NEW.case_id))
  OR (NEW.preparation_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM finance_billingpreparation p WHERE p.id=NEW.preparation_id AND p.case_id=NEW.case_id))
  OR (NEW.policy_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM policy_configuration p WHERE p.id=NEW.policy_id AND p.case_id=NEW.case_id
    AND p.component=CASE NEW.definition WHEN 'finance-ledger/v1' THEN 'OPS.factory_ledger_execution' WHEN 'engagement/v1' THEN 'OPS.factory_engagement_execution' WHEN 'pmo-minutes/v1' THEN 'OPS.factory_minutes_execution' WHEN 'planning/v1' THEN 'OPS.factory_planning_execution' WHEN 'commercial/v1' THEN 'OPS.factory_commercial_execution' WHEN 'delivery-release/v1' THEN 'OPS.factory_delivery_execution' WHEN 'delivery-hypercare/v1' THEN 'OPS.factory_hypercare_execution' WHEN 'delivery-archive/v1' THEN 'OPS.factory_archive_execution' WHEN 'delivery-handover/v1' THEN 'OPS.factory_handover_execution' WHEN 'delivery-closure/v1' THEN 'OPS.factory_closure_execution' WHEN 'delivery-go-live/v1' THEN 'OPS.factory_go_live_execution' WHEN 'finance-schedules/v1' THEN 'OPS.factory_schedules_execution' WHEN 'pmo-escalation/v1' THEN 'OPS.factory_escalation_execution' WHEN 'finance-ppe/v1' THEN 'OPS.factory_ppe_execution' WHEN 'pmo-change/v1' THEN 'OPS.factory_change_execution' WHEN 'finance-bu/v1' THEN 'OPS.factory_bu_execution' WHEN 'finance-forecast/v1' THEN 'OPS.factory_forecast_execution' WHEN 'finance-payroll/v1' THEN 'OPS.factory_payroll_execution' WHEN 'pmo-emergency/v1' THEN 'OPS.factory_emergency_execution' WHEN 'pmo-weekly-report/v1' THEN 'OPS.factory_reporting_execution' WHEN 'finance-accounts/v1' THEN 'OPS.factory_accounting_execution' WHEN 'rfp-response/v1' THEN 'OPS.factory_rfp_execution' ELSE 'OPS.factory_execution' END))
 THEN RAISE EXCEPTION 'Same-case native factory references required'; END IF;
 IF NEW.definition='pmo-finance/v1' AND NEW.source_head_id IS NOT NULL THEN RAISE EXCEPTION 'Invoice work cannot carry a domain source head'; END IF;
 IF NEW.definition='planning/v1' THEN
  IF NEW.invoice_id IS NOT NULL OR NEW.preparation_id IS NOT NULL OR NOT EXISTS(
    SELECT 1 FROM core_evidence e JOIN core_audit a ON a.case_id=e.case_id AND a.actor_id=e.created_by_id
    WHERE e.id=NEW.source_head_id AND e.case_id=NEW.case_id AND e.kind='planning_packet' AND a.action='planning.recorded'
    AND a.data=jsonb_build_object('kind','packet','evidence_id',e.id,'sha256',e.sha256) AND e.body::jsonb->'engagement_id'=NEW.request->'engagement')
  THEN RAISE EXCEPTION 'Native same-engagement planning packet required'; END IF;
 END IF;
 IF NEW.definition='commercial/v1' THEN
  IF NEW.invoice_id IS NOT NULL OR NEW.preparation_id IS NOT NULL OR NOT EXISTS(
    SELECT 1 FROM core_evidence e JOIN core_audit a ON a.case_id=e.case_id AND a.actor_id=e.created_by_id
    WHERE e.id=NEW.source_head_id AND e.case_id=NEW.case_id AND e.kind='agent_private_commercial_intake'
    AND e.body::jsonb->>'protocol'='factory-commercial-intake/v1' AND a.action='factory.commercial_intake'
    AND a.data=jsonb_build_object('evidence_id',e.id,'sha256',e.sha256))
  THEN RAISE EXCEPTION 'Native private commercial intake required'; END IF;
 END IF;

 IF NEW.definition='delivery-release/v1' THEN
  IF NEW.invoice_id IS NOT NULL OR NEW.preparation_id IS NOT NULL OR NOT EXISTS(
   SELECT 1 FROM core_evidence e JOIN core_audit a ON a.case_id=e.case_id AND a.actor_id=e.created_by_id
   JOIN pmo_deliverydossier d ON d.id=(NEW.request->>'dossier')::bigint
   WHERE e.id=NEW.source_head_id AND e.case_id=NEW.case_id AND e.kind='agent_private_delivery_intake'
    AND d.case_id=NEW.case_id AND e.body::jsonb->>'protocol'='factory-delivery-intake/v1'
    AND e.body::jsonb->>'dossier_id'=d.id::text AND a.action='factory.delivery_intake'
    AND a.data=jsonb_build_object('evidence_id',e.id,'sha256',e.sha256))
  THEN RAISE EXCEPTION 'Native same-case delivery intake and dossier required'; END IF;
 END IF;

 IF NEW.definition='delivery-hypercare/v1' THEN
  IF NEW.invoice_id IS NOT NULL OR NEW.preparation_id IS NOT NULL OR NOT EXISTS(
   SELECT 1 FROM core_evidence e JOIN core_audit a ON a.case_id=e.case_id AND a.actor_id=e.created_by_id
   JOIN pmo_deliverydossier d ON d.id=(NEW.request->>'dossier')::bigint
   WHERE e.id=NEW.source_head_id AND e.case_id=NEW.case_id AND e.kind='agent_private_delivery_intake'
    AND d.case_id=NEW.case_id AND e.body::jsonb->>'protocol'='factory-delivery-intake/v1'
    AND e.body::jsonb->>'dossier_id'=d.id::text AND a.action='factory.delivery_intake'
    AND a.data=jsonb_build_object('evidence_id',e.id,'sha256',e.sha256))
  THEN RAISE EXCEPTION 'Native same-case delivery intake and dossier required'; END IF;
 END IF;

 IF NEW.definition='delivery-archive/v1' THEN
  IF NEW.invoice_id IS NOT NULL OR NEW.preparation_id IS NOT NULL OR NOT EXISTS(
   SELECT 1 FROM core_evidence e JOIN core_audit a ON a.case_id=e.case_id AND a.actor_id=e.created_by_id
   JOIN pmo_deliverydossier d ON d.id=(NEW.request->>'dossier')::bigint
   WHERE e.id=NEW.source_head_id AND e.case_id=NEW.case_id AND e.kind='agent_private_archive_intake'
    AND e.body::jsonb->>'protocol'='factory-archive-intake/v1' AND e.body::jsonb->>'dossier_id'=d.id::text
    AND e.body::jsonb-ARRAY['protocol','dossier_id','inventory']='{}'::jsonb
    AND jsonb_typeof(e.body::jsonb->'inventory')='object' AND d.case_id=NEW.case_id
    AND a.action IN ('factory.archive_intake','factory.archive_source')
    AND a.data=jsonb_build_object('evidence_id',e.id,'sha256',e.sha256))
  THEN RAISE EXCEPTION 'Native same-case declared archive intake and dossier required'; END IF;
 END IF;

 IF NEW.definition='delivery-handover/v1' THEN
  IF NEW.invoice_id IS NOT NULL OR NEW.preparation_id IS NOT NULL OR NOT EXISTS(
   SELECT 1 FROM core_evidence e JOIN core_audit a ON a.case_id=e.case_id AND a.actor_id=e.created_by_id
   JOIN pmo_deliverydossier d ON d.id=(NEW.request->>'dossier')::bigint
   WHERE e.id=NEW.source_head_id AND e.case_id=NEW.case_id AND e.kind='agent_private_handover_intake'
    AND e.body::jsonb->>'protocol'='factory-handover-intake/v1' AND e.body::jsonb->>'dossier_id'=d.id::text
    AND e.body::jsonb-ARRAY['protocol','dossier_id','inputs']='{}'::jsonb
    AND jsonb_typeof(e.body::jsonb->'inputs')='object' AND d.case_id=NEW.case_id
    AND a.action IN ('factory.handover_intake','factory.handover_source')
    AND a.data=jsonb_build_object('evidence_id',e.id,'sha256',e.sha256))
  THEN RAISE EXCEPTION 'Native same-case handover input provenance and dossier required'; END IF;
 END IF;

 IF NEW.definition='delivery-closure/v1' THEN
  IF NEW.invoice_id IS NOT NULL OR NEW.preparation_id IS NOT NULL OR NOT EXISTS(
   SELECT 1 FROM core_evidence e JOIN core_audit a ON a.case_id=e.case_id AND a.actor_id=e.created_by_id
   JOIN pmo_deliverydossier d ON d.id=(NEW.request->>'dossier')::bigint
   WHERE e.id=NEW.source_head_id AND e.case_id=NEW.case_id AND e.kind='agent_private_closure_intake'
    AND e.body::jsonb->>'protocol'='factory-closure-intake/v1' AND e.body::jsonb->>'dossier_id'=d.id::text
    AND e.body::jsonb-ARRAY['protocol','dossier_id','inputs']='{}'::jsonb
    AND jsonb_typeof(e.body::jsonb->'inputs')='object' AND d.case_id=NEW.case_id
    AND a.action IN ('factory.closure_intake','factory.closure_source')
    AND a.data=jsonb_build_object('evidence_id',e.id,'sha256',e.sha256))
  THEN RAISE EXCEPTION 'Native same-case closure input provenance and dossier required'; END IF;
 END IF;

 IF NEW.definition='delivery-go-live/v1' THEN
  IF NEW.invoice_id IS NOT NULL OR NEW.preparation_id IS NOT NULL OR NOT EXISTS(
   SELECT 1 FROM core_evidence e JOIN core_audit a ON a.case_id=e.case_id AND a.actor_id=e.created_by_id
   JOIN pmo_deliverydossier d ON d.id=(NEW.request->>'dossier')::bigint
   WHERE e.id=NEW.source_head_id AND e.case_id=NEW.case_id AND e.kind='agent_private_go_live_intake'
    AND e.body::jsonb->>'protocol'='factory-go-live-intake/v1' AND e.body::jsonb->>'dossier_id'=d.id::text
    AND e.body::jsonb-ARRAY['protocol','dossier_id','inputs']='{}'::jsonb
    AND jsonb_typeof(e.body::jsonb->'inputs')='object' AND d.case_id=NEW.case_id
    AND a.action IN ('factory.go_live_intake','factory.go_live_source')
    AND a.data=jsonb_build_object('evidence_id',e.id,'sha256',e.sha256))
  THEN RAISE EXCEPTION 'Native same-case go_live input provenance and dossier required'; END IF;
 END IF;

 IF NEW.definition='finance-accounts/v1' THEN
  IF NEW.invoice_id IS NOT NULL OR NEW.preparation_id IS NOT NULL OR NOT EXISTS(
   SELECT 1 FROM core_evidence e JOIN finance_financesource s ON s.id=(e.body::jsonb->>'source')::bigint
   JOIN core_audit a ON a.case_id=e.case_id AND a.actor_id=e.created_by_id
   WHERE e.id=NEW.source_head_id AND e.case_id=NEW.case_id AND e.kind='agent_private_accounting_intake'
    AND e.body::jsonb->>'schema'='factory-accounting-intake/v1' AND s.case_id=NEW.case_id
    AND s.batch_id=(NEW.request->>'batch')::bigint AND s.entity=NEW.request->>'entity'
    AND e.body::jsonb->'batch'=NEW.request->'batch' AND e.body::jsonb->'entity'=NEW.request->'entity'
    AND e.body::jsonb->'reference'=NEW.request->'reference'
    AND a.action='factory.accounting_inputs_recorded'
    AND a.data=jsonb_build_object('evidence_id',e.id,'sha256',e.sha256))
  THEN RAISE EXCEPTION 'Native exact accounting intake/source references required'; END IF;
 END IF;

 IF NEW.definition='pmo-change/v1' THEN
  IF NEW.invoice_id IS NOT NULL OR NEW.preparation_id IS NOT NULL OR NOT EXISTS(
   SELECT 1 FROM core_evidence e JOIN core_audit a ON a.case_id=e.case_id AND a.actor_id=e.created_by_id
   JOIN pmo_changeversion v ON v.id=(e.body::jsonb->>'change_version_id')::bigint
   JOIN pmo_changerequest c ON c.id=v.change_id
   WHERE e.id=NEW.source_head_id AND e.case_id=NEW.case_id AND e.kind='agent_private_change_intake'
    AND c.case_id=NEW.case_id AND c.id=(NEW.request->>'change')::bigint
    AND e.body::jsonb->>'protocol'='factory-change-intake/v1'
    AND e.body::jsonb-ARRAY['protocol','change_version_id','inputs']='{}'::jsonb
    AND jsonb_typeof(e.body::jsonb->'inputs')='object'
    AND a.action IN ('factory.change_intake','factory.change_source')
    AND a.data=jsonb_build_object('evidence_id',e.id,'sha256',e.sha256))
  THEN RAISE EXCEPTION 'Exact same-project native change intake provenance required'; END IF;
 END IF;

 IF NEW.definition='pmo-emergency/v1' THEN
  IF NEW.invoice_id IS NOT NULL OR NEW.preparation_id IS NOT NULL OR NOT EXISTS(
   SELECT 1 FROM core_evidence e JOIN core_audit a ON a.case_id=e.case_id AND a.actor_id=e.created_by_id
   JOIN pmo_emergencyprofile ep ON ep.id=(e.body::jsonb->>'profile_id')::bigint
   JOIN pmo_changeversion cv ON cv.id=ep.version_id JOIN pmo_changerequest cr ON cr.id=cv.change_id
   WHERE e.id=NEW.source_head_id AND e.case_id=NEW.case_id AND e.kind='agent_private_emergency_intake'
    AND cr.case_id=NEW.case_id AND cr.id=(NEW.request->>'change')::bigint AND cv.category='Emergency' AND cv.incident_id IS NOT NULL
    AND e.body::jsonb->>'protocol'='factory-emergency-intake/v1'
    AND e.body::jsonb-ARRAY['protocol','profile_id','inputs']='{}'::jsonb
    AND jsonb_typeof(e.body::jsonb->'inputs')='object'
    AND a.action IN ('factory.emergency_intake','factory.emergency_source')
    AND a.data=jsonb_build_object('evidence_id',e.id,'sha256',e.sha256))
  THEN RAISE EXCEPTION 'Exact same-project incident-linked native Emergency source required'; END IF;
 END IF;

 IF NEW.definition='finance-payroll/v1' THEN
  IF NEW.invoice_id IS NOT NULL OR NEW.preparation_id IS NOT NULL OR NOT EXISTS(
   SELECT 1 FROM core_evidence e JOIN core_audit a ON a.case_id=e.case_id AND a.actor_id=e.created_by_id
   JOIN finance_payrollrequest q ON q.id=(e.body::jsonb->>'request_id')::bigint
   WHERE e.id=NEW.source_head_id AND e.case_id=NEW.case_id AND e.kind='agent_private_payroll_intake'
    AND q.case_id=NEW.case_id AND q.reference=NEW.request->>'payroll_reference'
    AND e.body::jsonb->>'protocol'='factory-payroll-intake/v1'
    AND e.body::jsonb-ARRAY['protocol','request_id','inputs']='{}'::jsonb
    AND (e.body::jsonb->'inputs')-ARRAY['input_ids','hr_snapshot_id']='{}'::jsonb
    AND jsonb_array_length(e.body::jsonb->'inputs'->'input_ids')=2
    AND (SELECT count(DISTINCT i.provider) FROM finance_payrollinput i
      WHERE i.id IN (SELECT value::bigint FROM jsonb_array_elements_text(e.body::jsonb->'inputs'->'input_ids'))
       AND i.request_id=q.id AND i.metadata->'accepted'='true'::jsonb)=2
    AND a.action IN ('factory.payroll_intake','factory.payroll_source')
    AND a.data=jsonb_build_object('evidence_id',e.id,'sha256',e.sha256))
  THEN RAISE EXCEPTION 'Exact same-workspace restricted payroll provenance required'; END IF;
 END IF;

 IF NEW.definition='finance-ppe/v1' THEN
  IF NEW.invoice_id IS NOT NULL OR NEW.preparation_id IS NOT NULL OR NOT EXISTS(
   SELECT 1 FROM core_evidence e JOIN core_audit a ON a.case_id=e.case_id AND a.actor_id=e.created_by_id
   JOIN finance_schedulework r ON r.id=(e.body::jsonb->>'register_id')::bigint
   WHERE e.id=NEW.source_head_id AND e.case_id=NEW.case_id AND e.kind='agent_private_ppe_intake'
    AND r.case_id=NEW.case_id AND r.kind='ppe_register' AND r.reference=NEW.request->>'register_reference'
    AND e.body::jsonb->>'protocol'='factory-ppe-intake/v1'
    AND e.body::jsonb-ARRAY['protocol','register_id','prior_id','ledger_id']='{}'::jsonb
    AND a.action IN ('factory.ppe_intake','factory.ppe_source')
    AND a.data=jsonb_build_object('evidence_id',e.id,'sha256',e.sha256))
  THEN RAISE EXCEPTION 'Exact same-case native PPE register provenance required'; END IF;
 END IF;

 IF NEW.definition='finance-schedules/v1' THEN
  IF NEW.invoice_id IS NOT NULL OR NEW.preparation_id IS NOT NULL OR NOT EXISTS(
   SELECT 1 FROM core_evidence e JOIN core_audit a ON a.case_id=e.case_id AND a.actor_id=e.created_by_id
   JOIN core_evidence supplied ON supplied.id=(e.body::jsonb->>'evidence_id')::bigint AND supplied.case_id=e.case_id
   WHERE e.id=NEW.source_head_id AND e.case_id=NEW.case_id AND e.kind='agent_private_schedules_intake'
    AND e.body::jsonb->>'protocol'='factory-schedules-intake/v1' AND e.body::jsonb->>'kind'=NEW.request->>'kind'
    AND e.body::jsonb-ARRAY['protocol','kind','parent_id','evidence_id','payload']='{}'::jsonb
    AND ((NEW.request->>'kind'='inventory' AND supplied.kind='schedule_inventory' AND e.body::jsonb->'payload'='null'::jsonb AND e.body::jsonb->'parent_id'='null'::jsonb)
     OR (NEW.request->>'kind'='income' AND supplied.kind='income_detail' AND EXISTS(SELECT 1 FROM finance_financerun n WHERE n.id=(e.body::jsonb->>'parent_id')::bigint AND n.case_id=NEW.case_id AND n.kind='mapping')))
    AND a.action IN ('factory.schedules_intake','factory.schedules_source') AND a.data=jsonb_build_object('evidence_id',e.id,'sha256',e.sha256))
  THEN RAISE EXCEPTION 'Exact native schedule source provenance required'; END IF;
 END IF;

 IF NEW.definition='pmo-weekly-report/v1' THEN
  IF NEW.invoice_id IS NOT NULL OR NEW.preparation_id IS NOT NULL OR NOT EXISTS(
   SELECT 1 FROM core_evidence e JOIN core_audit a ON a.case_id=e.case_id AND a.actor_id=e.created_by_id
   WHERE e.id=NEW.source_head_id AND e.case_id=NEW.case_id AND e.kind='agent_private_reporting_intake'
    AND e.body::jsonb->>'protocol'='factory-weekly-report-intake/v1'
    AND e.body::jsonb-ARRAY['protocol','inputs','manifest','captured_at']='{}'::jsonb
    AND (e.body::jsonb->'inputs')-ARRAY['template_id','content_id','start_at','end_at']='{}'::jsonb
    AND jsonb_typeof(e.body::jsonb->'manifest')='object'
    AND e.body::jsonb->'inputs'->>'start_at'=NEW.request->>'start_at' AND e.body::jsonb->'inputs'->>'end_at'=NEW.request->>'end_at'
    AND NEW.request->>'kind'='weekly_client' AND NEW.request->>'audience'='client'
    AND a.action IN ('factory.reporting_intake','factory.reporting_source') AND a.data=jsonb_build_object('evidence_id',e.id,'sha256',e.sha256))
  THEN RAISE EXCEPTION 'Exact private selected-period weekly report source required'; END IF;
 END IF;

 IF NEW.definition='pmo-escalation/v1' AND (NEW.invoice_id IS NOT NULL OR NEW.preparation_id IS NOT NULL OR NOT EXISTS(
 SELECT 1 FROM core_evidence e JOIN core_audit a ON a.case_id=e.case_id AND a.actor_id=e.created_by_id
 JOIN pmo_escalationrequest r ON r.id=(psl_escalation_intake(e.id)->>'request_id')::bigint JOIN pmo_escalationprofile ep ON ep.id=r.profile_id
 JOIN pmo_issuestate s ON s.id=ep.state_id JOIN pmo_issue i ON i.id=s.issue_id
 WHERE e.id=NEW.source_head_id AND e.case_id=NEW.case_id AND i.case_id=NEW.case_id AND i.id=(NEW.request->>'issue')::bigint
 AND e.kind='agent_private_escalation_intake' AND psl_escalation_intake(e.id)->>'protocol'='factory-escalation-intake/v1'
 AND (psl_escalation_intake(e.id)-ARRAY['protocol','request_id','profile_id','template_id'])='{}'::jsonb AND psl_escalation_intake(e.id)->>'profile_id'=ep.id::text
 AND r.direction=NEW.request->>'direction' AND r.target=NEW.request->>'target'
 AND a.action IN ('factory.escalation_intake','factory.escalation_source') AND a.data=jsonb_build_object('evidence_id',e.id,'sha256',e.sha256)))
 THEN RAISE EXCEPTION 'Exact same-case source-bound escalation request required'; END IF;

 IF NEW.definition='finance-bu/v1' THEN
  IF NEW.invoice_id IS NOT NULL OR NEW.preparation_id IS NOT NULL OR NOT EXISTS(
   SELECT 1 FROM core_evidence e JOIN core_audit a ON a.case_id=e.case_id AND a.actor_id=e.created_by_id
   WHERE e.id=NEW.source_head_id AND e.case_id=NEW.case_id AND e.kind='agent_private_bu_intake'
    AND e.sha256=encode(sha256(convert_to(e.body,'UTF8')),'hex')
    AND e.body::jsonb->>'protocol'='factory-bu-intake/v1'
    AND e.body::jsonb-ARRAY['protocol','inputs']='{}'::jsonb
    AND (e.body::jsonb->'inputs')-ARRAY['mode','payroll_id','source_id','rule_ids','comparison']='{}'::jsonb
    AND e.body::jsonb->'inputs'->>'mode'=NEW.request->>'mode'
    AND jsonb_array_length(e.body::jsonb->'inputs'->'rule_ids')<=100
    AND a.action IN ('factory.bu_intake','factory.bu_source')
    AND a.data=jsonb_build_object('evidence_id',e.id,'sha256',e.sha256)
    AND ((NEW.request->>'mode'='staff' AND EXISTS(SELECT 1 FROM finance_payrollrun r JOIN finance_payrollrequest q ON q.id=r.request_id
      WHERE r.id=(e.body::jsonb->'inputs'->>'payroll_id')::bigint AND r.kind='match' AND q.case_id=NEW.case_id
       AND q.reference=NEW.request->>'source_reference' AND NEW.request->'scope'=jsonb_build_object('entity',q.metadata->'entity','period',q.metadata->'period','currency',q.metadata->'currency')
       AND e.body::jsonb->'inputs'->'source_id'='null'::jsonb AND e.body::jsonb->'inputs'->'comparison'='null'::jsonb
       AND NOT EXISTS(SELECT 1 FROM jsonb_array_elements_text(e.body::jsonb->'inputs'->'rule_ids') ri WHERE NOT EXISTS(
        SELECT 1 FROM finance_buwork rule WHERE rule.id=ri::bigint AND rule.case_id=NEW.case_id AND rule.kind='rule' AND rule.payroll_id=r.id))))
     OR (NEW.request->>'mode'='event' AND EXISTS(SELECT 1 FROM finance_buwork s
      WHERE s.id=(e.body::jsonb->'inputs'->>'source_id')::bigint AND s.case_id=NEW.case_id AND s.kind='source'
       AND s.reference=NEW.request->>'source_reference' AND s.metadata->'accepted'='true'::jsonb AND s.metadata->'scope'=NEW.request->'scope'
       AND e.body::jsonb->'inputs'->'payroll_id'='null'::jsonb AND e.body::jsonb->'inputs'->'rule_ids'='[]'::jsonb
       AND (e.body::jsonb->'inputs'->'comparison'='null'::jsonb OR EXISTS(SELECT 1 FROM finance_financerun fr
        WHERE fr.id=(e.body::jsonb->'inputs'->'comparison'->>'run_id')::bigint AND fr.case_id=NEW.case_id AND fr.kind='allocation'))))))
  THEN RAISE EXCEPTION 'Exact scoped native BU intake required'; END IF;
 END IF;
 IF NEW.status='verified' THEN
  IF NEW.definition='pmo-finance/v1' AND NOT EXISTS(
    SELECT 1 FROM finance_invoiceissue i JOIN finance_invoicedelivery d ON d.invoice_id=i.invoice_id JOIN finance_invoice n ON n.id=i.invoice_id
    WHERE n.id=NEW.invoice_id AND n.case_id=NEW.case_id AND i.sha256=n.sha256 AND i.payload=n.payload)
  THEN RAISE EXCEPTION 'Native invoice receipts required; agent completion is not verification'; END IF;
  IF NEW.definition='planning/v1' AND NOT EXISTS(
    SELECT 1 FROM pmo_deliverysource s JOIN pmo_deliverydossier d ON d.id=s.dossier_id JOIN core_evidence e ON e.id=s.evidence_id
    JOIN core_audit a ON a.case_id=e.case_id AND a.actor_id=e.created_by_id
    WHERE d.case_id=NEW.case_id AND e.case_id=NEW.case_id AND e.kind='planning_readiness' AND s.kind='scope_baseline'
    AND e.body::jsonb->>'packet_id'=NEW.source_head_id::text AND e.body::jsonb->'inputs'->>'candidate_id'=d.candidate_id::text
    AND s.external_ref='psl:planning-readiness:'||e.id::text AND a.action='planning.recorded'
    AND a.data=jsonb_build_object('kind','ready','evidence_id',e.id,'sha256',e.sha256))
  THEN RAISE EXCEPTION 'Native planning readiness and delivery source required'; END IF;
  IF NEW.definition='commercial/v1' AND NOT EXISTS(
    SELECT 1 FROM pmo_commercialdocumentbinding b JOIN documents_version v ON v.id=b.version_id JOIN documents_document doc ON doc.id=v.document_id
    JOIN documents_publication p ON p.version_id=v.id JOIN pmo_commercialrevision r ON r.id=b.revision_id
    JOIN pmo_commercialcase c ON c.id=r.dossier_id JOIN pmo_costingbinding cb ON cb.costing_id=(r.sources->>'costing')::bigint
    JOIN pmo_costingrun cr ON cr.id=cb.run_id JOIN core_evidence e ON e.id=NEW.source_head_id
    WHERE c.case_id=NEW.case_id AND doc.case_id=NEW.case_id AND cr.case_id=NEW.case_id AND c.current_id=r.id AND cr.result->>'status'='known'
    AND r.sources->'requirements'=e.body::jsonb->'sources'->'requirements' AND r.sources->'plan'=e.body::jsonb->'sources'->'plan'
    AND r.sources->'engineering_estimate'=e.body::jsonb->'sources'->'engineering_estimate' AND r.sources->'security_estimate'=e.body::jsonb->'sources'->'security_estimate'
    AND r.sources->'sow'=e.body::jsonb->'sources'->'sow' AND cr.evidence_id::text=e.body::jsonb->'sources'->>'inputs'
    AND jsonb_array_length(p.recipient_ids)>0 AND NOT EXISTS(
      SELECT 1 FROM jsonb_array_elements_text(p.recipient_ids) AS destinations(recipient) WHERE NOT EXISTS(
       SELECT 1 FROM documents_publicationreceipt pr WHERE pr.publication_id=p.id AND pr.recipient_id::text=destinations.recipient
       AND pr.payload_sha256=v.payload_sha256 AND pr.payload=v.payload)))
  THEN RAISE EXCEPTION 'Exact native costing, commercial document and all recipient receipts required'; END IF;
 END IF;

 IF NEW.definition='delivery-release/v1' AND NEW.status='verified' AND NOT EXISTS(
  SELECT 1 FROM pmo_deliveryrecord r JOIN pmo_deliverydossier d ON d.id=r.dossier_id
  JOIN workflows_factoryactivity fa ON fa.work_id=NEW.id JOIN workflows_factoryattempt a ON a.activity_id=fa.id
  WHERE d.id=(NEW.request->>'dossier')::bigint AND d.case_id=NEW.case_id AND r.kind='release_ready'
   AND r.snapshot->'deployment_authorized'='false'::jsonb AND r.snapshot->>'financial_controls'='independent'
   AND a.phase='observed' AND a.result->>'release_ready'=r.id::text AND a.result->>'head'=NEW.source_head_id::text)
 THEN RAISE EXCEPTION 'Native source-bound release evidence required; no deployment authority is granted'; END IF;

 IF NEW.definition='delivery-hypercare/v1' AND NEW.status='verified' AND NOT EXISTS(
  SELECT 1 FROM pmo_deliveryrecord r JOIN pmo_deliverydossier d ON d.id=r.dossier_id
  JOIN workflows_factoryactivity fa ON fa.work_id=NEW.id JOIN workflows_factoryattempt a ON a.activity_id=fa.id
  WHERE d.id=(NEW.request->>'dossier')::bigint AND d.case_id=NEW.case_id AND r.kind='hypercare'
   AND r.snapshot->'qualified'='true'::jsonb
   AND a.phase='observed' AND a.result->>'hypercare'=r.id::text AND a.result->>'head'=NEW.source_head_id::text)
 THEN RAISE EXCEPTION 'Native source-bound qualified hypercare required; no closure or release authority is granted'; END IF;

 IF NEW.definition='delivery-archive/v1' AND NEW.status='verified' AND NOT EXISTS(
  SELECT 1 FROM pmo_deliveryrecord r JOIN pmo_deliverydossier d ON d.id=r.dossier_id
  JOIN core_evidence e ON e.id=NEW.source_head_id
  JOIN workflows_factoryactivity fa ON fa.work_id=NEW.id JOIN workflows_factoryattempt a ON a.activity_id=fa.id
  WHERE d.id=(NEW.request->>'dossier')::bigint AND d.case_id=NEW.case_id AND r.kind='archive'
   AND r.data->'inventory'=e.body::jsonb->'inventory'
   AND r.snapshot->'physical_purge_performed'='false'::jsonb
   AND r.snapshot->>'repository'='internal-versioned'
   AND a.phase='observed' AND a.result->>'archive'=r.id::text AND a.result->>'head'=NEW.source_head_id::text)
 THEN RAISE EXCEPTION 'Exact observed native archive index required; no physical purge or closure authority'; END IF;

 IF NEW.definition='delivery-handover/v1' AND NEW.status='verified' AND NOT EXISTS(
  SELECT 1 FROM documents_publication p JOIN documents_publicationreceipt r ON r.publication_id=p.id
  JOIN pmo_deliverydocumentbinding b ON b.version_id=p.version_id
  JOIN pmo_deliveryrecord h ON h.dossier_id=b.dossier_id AND h.kind='handover'
  JOIN workflows_factoryactivity fa ON fa.work_id=NEW.id JOIN workflows_factoryattempt a ON a.activity_id=fa.id
  WHERE p.factory_work_id=NEW.id AND p.factory_source_id=NEW.source_head_id AND b.purpose='handover'
   AND b.dossier_id=(NEW.request->>'dossier')::bigint AND h.data->>'receipt_id'=r.id::text
   AND h.data->>'status'='received' AND h.actor_id=r.recipient_id
   AND a.phase='observed' AND fa.kind='ACT13' AND a.result->'verified'='true'::jsonb
   AND a.result->>'publication'=p.id::text AND a.result->>'head'=NEW.source_head_id::text)
 THEN RAISE EXCEPTION 'Observed exact native handover and actual recipient acknowledgement required'; END IF;

 IF NEW.definition='delivery-closure/v1' AND NEW.status='verified' AND NOT EXISTS(
  SELECT 1 FROM pmo_deliveryrecord c JOIN pmo_deliverydocumentbinding b ON b.version_id=(c.data->>'version_id')::bigint
  JOIN documents_version v ON v.id=b.version_id
  JOIN pmo_deliveryrecord decision ON decision.id=(c.data->>'decision_id')::bigint
  JOIN core_evidence head ON head.id=NEW.source_head_id
  JOIN workflows_factoryactivity fa ON fa.work_id=NEW.id AND fa.kind='ACT13'
  JOIN workflows_factoryattempt a ON a.activity_id=fa.id AND a.phase='observed'
  WHERE c.dossier_id=(NEW.request->>'dossier')::bigint AND c.kind='closure' AND b.dossier_id=c.dossier_id AND b.purpose='closure'
   AND decision.dossier_id=c.dossier_id AND decision.kind='closure_decision' AND decision.data->>'verdict'='approve'
   AND decision.data->>'version_id'=v.id::text AND decision.snapshot=b.snapshot AND c.snapshot=b.snapshot
   AND b.data=(head.body::jsonb->'inputs')-'template_id' AND v.template_id=(head.body::jsonb->'inputs'->>'template_id')::bigint
   AND a.result->'verified'='true'::jsonb AND a.result->>'closure'=c.id::text
   AND a.result->>'document_version'=v.id::text AND a.result->>'head'=NEW.source_head_id::text)
 THEN RAISE EXCEPTION 'Observed exact native closure, prescribed decision and current source binding required'; END IF;

 IF NEW.definition='delivery-go-live/v1' AND NEW.status='verified' AND NOT EXISTS(
  SELECT 1 FROM documents_publication p JOIN documents_publicationreceipt r ON r.publication_id=p.id
  JOIN documents_version v ON v.id=p.version_id JOIN pmo_deliverydocumentbinding b ON b.version_id=v.id
  JOIN pmo_deliveryrecord g ON g.dossier_id=b.dossier_id AND g.kind IN ('go_live','go_live_reaffirmation')
  JOIN core_evidence pm ON pm.id=(g.data->>'pm_signature_id')::bigint
  JOIN core_evidence client ON client.id=(g.data->>'client_signature_id')::bigint
  JOIN core_evidence head ON head.id=NEW.source_head_id
  JOIN workflows_factoryactivity fa ON fa.work_id=NEW.id AND fa.kind='ACT13'
  JOIN workflows_factoryattempt a ON a.activity_id=fa.id AND a.phase='observed'
  WHERE p.factory_work_id=NEW.id AND p.factory_source_id=NEW.source_head_id AND b.purpose='go_live' AND v.audience='client'
   AND b.dossier_id=(NEW.request->>'dossier')::bigint AND g.data->>'receipt_id'=r.id::text AND g.snapshot=b.snapshot
   AND b.data=(head.body::jsonb->'inputs')-'template_id' AND v.template_id=(head.body::jsonb->'inputs'->>'template_id')::bigint
   AND pm.case_id=NEW.case_id AND client.case_id=NEW.case_id AND pm.kind='signature' AND client.kind='signature' AND pm.id<>client.id
   AND a.result->'verified'='true'::jsonb AND a.result->>'acceptance'=g.id::text
   AND a.result->>'document_version'=v.id::text AND a.result->>'head'=NEW.source_head_id::text)
 THEN RAISE EXCEPTION 'Observed exact native go-live acceptance, distinct actual signature evidence and source-bound client receipt required'; END IF;

 IF NEW.definition='finance-accounts/v1' AND NEW.status='verified' AND NOT EXISTS(
  SELECT 1 FROM finance_financerun r JOIN finance_financesource s ON s.id=r.source_id
  JOIN finance_financedocumentbinding b ON b.run_id=r.id
  JOIN documents_version v ON v.id=b.version_id JOIN documents_document d ON d.id=v.document_id
  JOIN documents_publication p ON p.version_id=v.id JOIN documents_publicationjob j ON j.publication_id=p.id
  JOIN core_evidence h ON h.id=NEW.source_head_id
  JOIN workflows_factoryactivity fa ON fa.work_id=NEW.id AND fa.kind='ACT13'
  JOIN workflows_factoryattempt a ON a.activity_id=fa.id AND a.phase='observed'
  WHERE r.case_id=NEW.case_id AND s.case_id=NEW.case_id AND d.case_id=NEW.case_id AND r.kind='formula'
   AND s.id=(h.body::jsonb->>'source')::bigint AND s.batch_id=(NEW.request->>'batch')::bigint
   AND (p.factory_work_id=NEW.id AND p.factory_source_id=NEW.source_head_id OR p.factory_work_id IS NULL)
   AND d.current_id=v.id AND j.status='confirmed' AND jsonb_array_length(p.recipient_ids)>0
   AND NOT EXISTS(SELECT 1 FROM jsonb_array_elements_text(p.recipient_ids) x WHERE NOT EXISTS(
    SELECT 1 FROM documents_publicationreceipt pr WHERE pr.publication_id=p.id AND pr.recipient_id=x.value::bigint))
   AND (SELECT count(*) FROM documents_publicationreceipt pr WHERE pr.publication_id=p.id)=jsonb_array_length(p.recipient_ids)
   AND EXISTS(SELECT 1 FROM finance_financereview fr WHERE fr.run_id=r.id AND fr.purpose='output' AND fr.verdict='approve'
    AND fr.id=(SELECT max(last.id) FROM finance_financereview last WHERE last.run_id=r.id AND last.purpose='output'))
   AND a.result->'verified'='true'::jsonb AND a.result->>'run'=r.id::text AND a.result->>'source'=s.id::text
   AND a.result->>'binding'=b.id::text AND a.result->>'publication'=p.id::text AND a.result->>'document_version'=v.id::text
   AND a.result->'receipt_ids'=(SELECT jsonb_agg(pr.id ORDER BY pr.id) FROM documents_publicationreceipt pr WHERE pr.publication_id=p.id)) AND NOT EXISTS(
  SELECT 1 FROM finance_financerun r JOIN finance_financesource s ON s.id=r.source_id
  JOIN finance_financedocumentbinding b ON b.run_id=r.id
  JOIN documents_version v ON v.id=b.version_id JOIN documents_document d ON d.id=v.document_id
  JOIN documents_publication p ON p.version_id=v.id JOIN documents_publicationjob j ON j.publication_id=p.id
  JOIN core_evidence h ON h.id=NEW.source_head_id
  JOIN workflows_factoryactivity fa ON fa.work_id=NEW.id AND fa.kind='ACT13'
  JOIN workflows_factoryattempt a ON a.activity_id=fa.id AND a.phase='observed'
  WHERE r.case_id=NEW.case_id AND s.case_id=NEW.case_id AND d.case_id=NEW.case_id AND r.kind='statement'
   AND s.id=(h.body::jsonb->>'source')::bigint AND s.batch_id=(NEW.request->>'batch')::bigint
   AND (p.factory_work_id=NEW.id AND p.factory_source_id=NEW.source_head_id OR p.factory_work_id IS NULL)
   AND d.current_id=v.id AND j.status='confirmed' AND jsonb_array_length(p.recipient_ids)>0
   AND NOT EXISTS(SELECT 1 FROM jsonb_array_elements_text(p.recipient_ids) x WHERE NOT EXISTS(
    SELECT 1 FROM documents_publicationreceipt pr WHERE pr.publication_id=p.id AND pr.recipient_id=x.value::bigint))
   AND (SELECT count(*) FROM documents_publicationreceipt pr WHERE pr.publication_id=p.id)=jsonb_array_length(p.recipient_ids)
   AND EXISTS(SELECT 1 FROM finance_financereview fr WHERE fr.run_id=r.id AND fr.purpose='output' AND fr.verdict='approve'
    AND fr.id=(SELECT max(last.id) FROM finance_financereview last WHERE last.run_id=r.id AND last.purpose='output'))
   AND a.result->'verified'='true'::jsonb AND a.result->>'run'=r.id::text AND a.result->>'source'=s.id::text
   AND a.result->>'binding'=b.id::text AND a.result->>'publication'=p.id::text AND a.result->>'document_version'=v.id::text
   AND a.result->'receipt_ids'=(SELECT jsonb_agg(pr.id ORDER BY pr.id) FROM documents_publicationreceipt pr WHERE pr.publication_id=p.id)
   AND EXISTS(SELECT 1 FROM policy_configuration pc JOIN policy_registeredreference pr ON pr.case_id=pc.case_id
    AND pr.ref=pc.envelope->'value'->>'artifact_ref' AND pr.version=(pc.envelope->'value'->>'artifact_version')::integer
    AND pr.sha256=pc.envelope->'value'->>'sha256'
    WHERE pc.id=NEW.policy_id AND pc.component='OPS.factory_accounting_execution'
     AND pr.schema_ref='schema:psl/factory-accounting-execution/v3' AND pr.content->>'statement_contract_id'=r.request->>'contract_id')
   AND r.result->>'status'='complete' AND r.result->>'scope'='selected_statement_lines'
   AND r.result->'whole_statement_certified'='false'::jsonb
   AND EXISTS(SELECT 1 FROM finance_financereview cr JOIN policy_configuration cc ON cc.id=cr.configuration_id
    WHERE cc.id=(r.request->>'contract_id')::bigint AND cc.case_id=r.case_id AND cc.component='D06.statement_contract'
     AND cr.purpose='formula' AND cr.verdict='approve'
     AND cr.id=(SELECT max(id) FROM finance_financereview WHERE configuration_id=cc.id AND purpose='formula')
     AND cr.id::text=r.snapshot->'reviews'->'D06.statement_contract'->>'id'
     AND (SELECT state FROM policy_policystate WHERE configuration_id=cc.id ORDER BY id DESC LIMIT 1)='active')
   AND jsonb_array_length(r.snapshot->'inputs')>0
   AND (SELECT count(*) FROM finance_financestatementinput si WHERE si.statement_id=r.id)=jsonb_array_length(r.snapshot->'inputs')
   AND NOT EXISTS(SELECT 1 FROM finance_financestatementinput si
    JOIN finance_financerun sr ON sr.id=si.source_run_id
    JOIN finance_financereview rv ON rv.id=si.source_review_id
    JOIN finance_financesource ss ON ss.id=sr.source_id
    WHERE si.statement_id=r.id AND (sr.case_id<>r.case_id OR rv.run_id<>sr.id OR rv.verdict<>'approve'
     OR rv.id<>(SELECT max(id) FROM finance_financereview WHERE run_id=sr.id AND purpose='output')
     OR sr.result->>'period'<>r.result->>'period' OR sr.result->>'entity'<>r.result->>'entity'
     OR sr.result->>'currency'<>r.result->>'currency' OR ss.accounting_basis IS DISTINCT FROM r.result->>'accounting_basis'
     OR si.declaration->>'source_sign' IS NULL OR si.declaration->>'source_sign' IS DISTINCT FROM si.declaration->>'destination_sign'
     OR sr.result->'company'->si.metric->'value' IS DISTINCT FROM r.result->'company'->si.destination->'value'
     OR sr.result->'company'->si.metric->>'unit' IS DISTINCT FROM si.declaration->>'unit'))
)
 THEN RAISE EXCEPTION 'Current native accounting binding/output review and all exact recipient receipts required'; END IF;

 IF TG_OP='UPDATE' AND NEW.definition IN ('delivery-release/v1','delivery-hypercare/v1')
 AND NEW.source_head_id IS DISTINCT FROM OLD.source_head_id THEN
  IF NEW.cancel_requested OR OLD.status IN ('cancelled','followup_needed') OR NEW.status<>'ready'
   OR (OLD.lease_until IS NOT NULL AND OLD.lease_until>statement_timestamp())
   OR NOT EXISTS(SELECT 1 FROM core_evidence n JOIN core_evidence o ON o.id=OLD.source_head_id
     JOIN core_audit a ON a.case_id=n.case_id AND a.actor_id=n.created_by_id
     JOIN core_evidence e ON e.case_id=n.case_id AND a.data->'evidence'=to_jsonb(e.id)
     WHERE n.id=NEW.source_head_id AND n.body=o.body AND n.version>o.version
      AND a.action='factory.delivery_intake_reaffirmed' AND a.data->>'work'=NEW.id::text
      AND a.data->>'previous'=OLD.source_head_id::text AND a.data->>'current'=n.id::text
      AND length(btrim(a.data->>'reason')) BETWEEN 1 AND 2000
      AND coalesce(a.data->>'packet','') ~ '^[a-f0-9]{64}$')
   OR EXISTS(SELECT 1 FROM workflows_factoryattempt a JOIN workflows_factoryactivity t ON t.id=a.activity_id
     WHERE t.work_id=NEW.id AND t.kind='ACT03' AND a.phase='started' AND a.result->>'schema'='factory-provider-request/v1'
      AND NOT EXISTS(SELECT 1 FROM workflows_factoryattempt done WHERE done.activity_id=a.activity_id AND done.number=a.number AND done.phase IN ('observed','failed'))
      AND NOT EXISTS(SELECT 1 FROM workflows_factoryplanningreceipt WHERE attempt_id=a.id))
  THEN RAISE EXCEPTION 'Exact fresh human source instruction and reconciled original effects required'; END IF;
 END IF;

 IF NEW.definition='rfp-response/v1' THEN
  IF NEW.invoice_id IS NOT NULL OR NEW.preparation_id IS NOT NULL OR NOT EXISTS(
   SELECT 1 FROM core_evidence e JOIN core_audit a ON a.case_id=e.case_id AND a.actor_id=e.created_by_id
   JOIN pmo_rfpcase r ON r.id=(NEW.request->>'rfp')::bigint AND r.case_id=NEW.case_id
   JOIN pmo_rfpintake i ON i.id=(e.body::jsonb->>'intake')::bigint AND i.rfp_id=r.id
   WHERE e.id=NEW.source_head_id AND e.case_id=NEW.case_id AND e.kind='agent_private_rfp_intake'
    AND e.body::jsonb->>'schema'='factory-rfp-intake/v1' AND e.body::jsonb->'rfp'=NEW.request->'rfp'
    AND NEW.request-ARRAY['rfp','reference']='{}'::jsonb
    AND e.body::jsonb-ARRAY['schema','rfp','intake','response_evidence','public_terms','sources','matrix','lessons']='{}'::jsonb
    AND jsonb_typeof(e.body::jsonb->'sources')='object' AND jsonb_typeof(e.body::jsonb->'matrix')='array'
    AND a.action='factory.rfp_inputs_recorded' AND a.data=jsonb_build_object('evidence_id',e.id,'sha256',e.sha256))
  THEN RAISE EXCEPTION 'Exact native same-case RFP instruction provenance required'; END IF;
  IF TG_OP='UPDATE' AND NEW.source_head_id IS DISTINCT FROM OLD.source_head_id THEN
   IF OLD.status IN ('verified','cancelled','followup_needed') OR NEW.cancel_requested OR NEW.status<>'ready'
    OR (OLD.lease_until IS NOT NULL AND OLD.lease_until>statement_timestamp())
    OR NOT EXISTS(SELECT 1 FROM core_audit a JOIN core_evidence e ON e.id=NEW.source_head_id AND e.created_by_id=a.actor_id
      WHERE a.case_id=NEW.case_id AND a.action='factory.rfp_instruction_changed'
       AND a.data->>'work'=NEW.id::text AND a.data->>'previous'=OLD.source_head_id::text
       AND a.data->>'current'=NEW.source_head_id::text AND length(btrim(a.data->>'reason')) BETWEEN 1 AND 4000)
    OR EXISTS(SELECT 1 FROM documents_publication p JOIN documents_publicationjob j ON j.publication_id=p.id
      WHERE p.factory_work_id=NEW.id AND (j.status IN ('pending','unknown','leased','held') OR
       j.status='confirmed' AND NOT EXISTS(SELECT 1 FROM pmo_rfpsubmission s WHERE s.version_id=p.version_id)))
    OR EXISTS(SELECT 1 FROM workflows_factoryattempt a JOIN workflows_factoryactivity t ON t.id=a.activity_id
      WHERE t.work_id=NEW.id AND t.kind='ACT03' AND a.phase='started' AND a.result->>'schema'='factory-provider-request/v1'
       AND NOT EXISTS(SELECT 1 FROM workflows_factoryattempt done WHERE done.activity_id=a.activity_id AND done.number=a.number AND done.phase IN ('observed','failed'))
       AND NOT EXISTS(SELECT 1 FROM workflows_factoryplanningreceipt pr WHERE pr.attempt_id=a.id))
   THEN RAISE EXCEPTION 'Fresh human RFP instruction and reconciled original effects required'; END IF;
  END IF;

  IF NEW.status='verified' AND NOT EXISTS(
   SELECT 1 FROM pmo_rfpdisposition d JOIN pmo_rfpoutcome o ON o.id=d.outcome_id
   JOIN pmo_rfpsubmission s ON s.id=o.submission_id JOIN pmo_rfpresponse r ON r.id=s.response_id
   JOIN pmo_rfpcase root ON root.id=r.rfp_id JOIN core_evidence h ON h.id=NEW.source_head_id
   JOIN pmo_commercialrevision cr ON cr.id=r.commercial_id
   JOIN pmo_rfpdocumentbinding b ON b.response_id=r.id AND b.version_id=s.version_id
   JOIN documents_version v ON v.id=s.version_id JOIN documents_document doc ON doc.id=v.document_id
   JOIN documents_publication p ON p.version_id=v.id JOIN documents_publicationjob j ON j.publication_id=p.id
   JOIN documents_controlledreview review ON review.id=p.review_id AND review.version_id=v.id
   JOIN workflows_factoryactivity t ON t.work_id=NEW.id AND t.kind='ACT13'
   JOIN workflows_factoryattempt a ON a.activity_id=t.id AND a.phase='observed'
   WHERE root.case_id=NEW.case_id AND root.id=(NEW.request->>'rfp')::bigint AND d.rfp_id=root.id
    AND doc.case_id=NEW.case_id AND s.snapshot=b.snapshot AND s.snapshot->>'response'=r.id::text
    AND s.snapshot->'sources'=r.snapshot AND d.snapshot->'sources'=r.snapshot AND d.snapshot->'commercial_sources'=cr.sources
    AND jsonb_array_length(s.snapshot->'reviews')=2 AND NOT EXISTS(
     SELECT 1 FROM jsonb_array_elements_text(s.snapshot->'reviews') WITH ORDINALITY item(id,nth)
     WHERE NOT EXISTS(SELECT 1 FROM pmo_rfpreview rr WHERE rr.id=item.id::bigint AND rr.response_id=r.id AND rr.verdict='approve'
      AND rr.role=CASE item.nth WHEN 1 THEN 'PMO Lead' WHEN 2 THEN 'Engineering Lead' END AND rr.created_at<=p.created_at))
    AND jsonb_array_length(s.snapshot->'costing_decisions')=3 AND NOT EXISTS(
     SELECT 1 FROM jsonb_array_elements_text(s.snapshot->'costing_decisions') WITH ORDINALITY item(id,nth)
     WHERE NOT EXISTS(SELECT 1 FROM pmo_commercialdecision cd WHERE cd.id=item.id::bigint AND cd.revision_id=cr.id AND cd.verdict='approve'
      AND cd.role=CASE item.nth WHEN 1 THEN 'PM' WHEN 2 THEN 'Head of PMO' WHEN 3 THEN 'CEO' END AND cd.created_at<=p.created_at))
    AND review.verdict='approve' AND review.payload_sha256=v.payload_sha256 AND review.created_at<=p.created_at
    AND j.status='confirmed' AND jsonb_array_length(p.recipient_ids)>0
    AND (p.factory_work_id=NEW.id OR p.factory_work_id IS NULL)
    AND (p.factory_work_id IS NULL OR EXISTS(SELECT 1 FROM core_evidence origin WHERE origin.id=p.factory_source_id
     AND origin.case_id=NEW.case_id AND origin.kind='agent_private_rfp_intake' AND origin.body::jsonb->'rfp'=NEW.request->'rfp'))
    AND d.snapshot->>'response'=r.id::text AND d.snapshot->>'submission'=s.id::text AND d.snapshot->>'outcome'=o.id::text
    AND d.snapshot->>'case'=NEW.case_id::text AND d.snapshot->'baseline_imported'='false'::jsonb
    AND (d.kind='route_a' AND o.result='won' AND d.snapshot->>'route'='A' OR
     d.kind='loss_archive' AND o.result='lost' AND d.lessons_id=(h.body::jsonb->>'lessons')::bigint)
    AND NOT EXISTS(SELECT 1 FROM jsonb_array_elements_text(p.recipient_ids) x WHERE NOT EXISTS(
     SELECT 1 FROM documents_publicationreceipt pr WHERE pr.publication_id=p.id AND pr.recipient_id=x.value::bigint AND pr.payload=v.payload AND pr.payload_sha256=v.payload_sha256))
    AND s.receipt_ids=(SELECT jsonb_agg(pr.id ORDER BY pr.id) FROM documents_publicationreceipt pr WHERE pr.publication_id=p.id)
    AND (SELECT count(*) FROM documents_publicationreceipt pr WHERE pr.publication_id=p.id)=jsonb_array_length(p.recipient_ids)
    AND a.result->'verified'='true'::jsonb AND a.result->>'head'=NEW.source_head_id::text
    AND a.result->>'response'=r.id::text AND a.result->>'disposition'=d.id::text AND a.result->>'submission'=s.id::text
    AND a.result->>'outcome'=o.id::text AND a.result->>'document_version'=v.id::text
    AND a.result->>'publication'=p.id::text AND a.result->'receipt_ids'=s.receipt_ids)
  THEN RAISE EXCEPTION 'Historical approved RFP submission, actual customer outcome and all exact receipts required'; END IF;

 END IF;

 IF NEW.definition='pmo-change/v1' AND NEW.status='verified' AND NOT EXISTS(
  SELECT 1 FROM core_evidence e JOIN pmo_changeauthorization ca ON ca.id=(e.body::jsonb->'inputs'->>'authorization_id')::bigint
  JOIN pmo_changeversion cv ON cv.id=ca.version_id JOIN pmo_changerequest cr ON cr.id=cv.change_id
  JOIN pmo_changeclosure cc ON cc.authorization_id=ca.id
  JOIN documents_publicationreceipt r ON r.id=cc.receipt_id JOIN documents_publication p ON p.id=r.publication_id
  JOIN pmo_changedocumentbinding b ON b.version_id=p.version_id AND b.authorization_id=ca.id AND b.purpose='go_live'
  JOIN workflows_factoryactivity fa ON fa.work_id=NEW.id AND fa.kind='ACT13'
  JOIN workflows_factoryattempt a ON a.activity_id=fa.id AND a.phase='observed'
  WHERE e.id=NEW.source_head_id AND cv.id=(e.body::jsonb->>'change_version_id')::bigint
   AND cr.case_id=NEW.case_id AND cr.current_id=cv.id AND cr.id=(NEW.request->>'change')::bigint
   AND p.factory_work_id=NEW.id AND p.factory_source_id=e.id
   AND cc.execution_ids=b.execution_ids AND cc.pm_signature_id<>cc.client_signature_id
   AND a.result->'verified'='true'::jsonb AND a.result->>'head'=e.id::text AND a.result->>'closure'=cc.id::text
   AND a.result->>'document_version'=p.version_id::text
   AND EXISTS(SELECT 1 FROM documents_publication np JOIN pmo_changedocumentbinding nb ON nb.version_id=np.version_id
    JOIN documents_publicationreceipt nr ON nr.publication_id=np.id
    WHERE np.factory_work_id=NEW.id AND np.factory_source_id=e.id AND nb.authorization_id=ca.id AND nb.purpose='notice')
   AND NOT EXISTS(SELECT 1 FROM jsonb_array_elements_text(p.recipient_ids) recipient
    WHERE NOT EXISTS(SELECT 1 FROM documents_publicationreceipt pr WHERE pr.publication_id=p.id AND pr.recipient_id=recipient::bigint)))
 THEN RAISE EXCEPTION 'Observed exact native change closure and controlled recipient receipts required'; END IF;

 IF NEW.definition='pmo-emergency/v1' AND NEW.status='verified' AND NOT EXISTS(
  SELECT 1 FROM core_evidence e JOIN pmo_emergencyprofile ep ON ep.id=(e.body::jsonb->>'profile_id')::bigint
  JOIN pmo_emergencyoutcome o ON o.id=(e.body::jsonb->'inputs'->>'outcome_id')::bigint AND o.profile_id=ep.id
  JOIN pmo_emergencyauthorization ea ON ea.id=o.authorization_id AND ea.profile_id=ep.id
  JOIN pmo_emergencyretrospectiverecord rr ON rr.outcome_id=o.id
  JOIN pmo_changeversion cv ON cv.id=ep.version_id JOIN pmo_changerequest cr ON cr.id=cv.change_id
  JOIN pmo_emergencydocumentbinding b ON b.outcome_id=o.id
  JOIN documents_version v ON v.id=b.version_id JOIN documents_publication p ON p.version_id=v.id
  JOIN workflows_factoryactivity fa ON fa.work_id=NEW.id AND fa.kind='ACT13'
  JOIN workflows_factoryattempt a ON a.activity_id=fa.id AND a.phase='observed'
  WHERE e.id=NEW.source_head_id AND cr.case_id=NEW.case_id AND cr.id=(NEW.request->>'change')::bigint AND cr.current_id=cv.id
   AND ea.id=(e.body::jsonb->'inputs'->>'authorization_id')::bigint AND ea.created_at<=o.implemented_at
   AND rr.snapshot->>'authorization_id'=ea.id::text AND rr.snapshot->>'status' IN ('evidenced_on_time','completed_with_lateness_exception')
   AND b.manifest->>'reconciliation_id'=rr.id::text AND b.manifest->>'outcome_id'=o.id::text
   AND p.factory_work_id=NEW.id AND p.factory_source_id=e.id AND v.template_id=(e.body::jsonb->'inputs'->>'template_id')::bigint
   AND v.audience=e.body::jsonb->'inputs'->>'audience'
   AND a.result->'verified'='true'::jsonb AND a.result->>'head'=e.id::text AND a.result->>'retrospective_record'=rr.id::text
   AND a.result->>'document_version'=v.id::text AND a.result->>'retrospective_status'=rr.snapshot->>'status'
   AND EXISTS(SELECT 1 FROM documents_publicationreceipt pr WHERE pr.publication_id=p.id)
   AND NOT EXISTS(SELECT 1 FROM jsonb_array_elements_text(p.recipient_ids) recipient
    WHERE NOT EXISTS(SELECT 1 FROM documents_publicationreceipt pr WHERE pr.publication_id=p.id AND pr.recipient_id=recipient::bigint)))
 THEN RAISE EXCEPTION 'Observed exact native Emergency retrospective and every report receipt required; deployment and ordinary closure are not granted'; END IF;

 IF NEW.definition='finance-payroll/v1' AND NEW.status='verified' AND NOT EXISTS(
  SELECT 1 FROM core_evidence e JOIN finance_payrollrequest q ON q.id=(e.body::jsonb->>'request_id')::bigint
   JOIN finance_payrollrun ar ON ar.request_id=q.id AND ar.kind='aggregate'
   JOIN finance_payrollrun mr ON mr.id=ar.parent_id AND mr.kind='match'
   JOIN finance_payrollrun cr ON cr.id=mr.parent_id AND cr.kind='combine'
   JOIN finance_payrollpublication p ON p.run_id=ar.id AND p.request_id=q.id
   JOIN finance_payrollreview rv ON rv.id=p.review_id AND rv.run_id=ar.id
   JOIN workflows_factoryactivity fa ON fa.work_id=NEW.id AND fa.kind='ACT13'
   JOIN workflows_factoryattempt a ON a.activity_id=fa.id AND a.phase='observed'
   JOIN policy_configuration pc ON pc.id=(p.policy_ids->>'F18.reporting_rules')::bigint
   JOIN policy_registeredreference pr ON pr.case_id=pc.case_id AND pr.ref=pc.envelope->'value'->>'artifact_ref'
    AND pr.version=(pc.envelope->'value'->>'artifact_version')::integer AND pr.sha256=pc.envelope->'value'->>'sha256'
  WHERE e.id=NEW.source_head_id AND q.case_id=NEW.case_id AND q.reference=NEW.request->>'payroll_reference'
   AND cr.request_id=q.id AND mr.request_id=q.id
   AND (cr.metadata->'input_ids') @> (e.body::jsonb->'inputs'->'input_ids')
   AND (cr.metadata->'input_ids') <@ (e.body::jsonb->'inputs'->'input_ids')
   AND mr.hr_snapshot_id=(e.body::jsonb->'inputs'->>'hr_snapshot_id')::bigint
   AND ar.metadata->>'status'='complete' AND mr.metadata->>'status'='complete' AND cr.metadata->>'status'='complete'
   AND rv.verdict='approve' AND rv.subject_sha256=ar.sha256
   AND rv.id=(SELECT max(id) FROM finance_payrollreview WHERE run_id=ar.id)
   AND p.payload->'by_bu'=ar.result->'by_bu' AND p.payload->'eligible_total'=ar.result->'eligible_total'
   AND p.payload->>'source_run'=ar.id::text AND p.payload->>'disclosure'='aggregate_only'
   AND NOT (p.payload ? 'rows') AND p.payload->'hr_written'='false'::jsonb AND p.payload->'ledger_posted'='false'::jsonb
   AND NOT EXISTS(SELECT 1 FROM finance_payrollpublication newer WHERE newer.request_id=q.id AND newer.version>p.version)
   AND NOT EXISTS(SELECT 1 FROM finance_payrollrequest newer WHERE newer.case_id=q.case_id AND newer.reference=q.reference AND newer.version>q.version)
   AND a.result->'verified'='true'::jsonb AND a.result->>'head'=e.id::text AND a.result->>'publication'=p.id::text
   AND a.result->>'run'=ar.id::text AND a.result->>'request'=q.id::text
   AND jsonb_array_length(pr.content->'recipient_ids')>0
   AND NOT EXISTS(SELECT 1 FROM jsonb_array_elements_text(pr.content->'recipient_ids') recipient
     WHERE NOT EXISTS(SELECT 1 FROM finance_payrollreportreceipt rr WHERE rr.publication_id=p.id AND rr.actor_id=recipient::bigint
       AND a.result->'receipt_ids' @> to_jsonb(ARRAY[rr.id]))))
 THEN RAISE EXCEPTION 'Observed exact payroll aggregate and actual recipient-owned receipts required'; END IF;

 IF NEW.definition='finance-forecast/v1' AND NOT EXISTS(
  SELECT 1 FROM core_evidence e JOIN core_audit a ON a.case_id=e.case_id AND a.actor_id=e.created_by_id
  JOIN finance_forecastscenario s ON s.id=(e.body::jsonb->>'scenario_id')::bigint
  WHERE e.id=NEW.source_head_id AND e.case_id=NEW.case_id AND s.case_id=NEW.case_id
   AND e.kind='agent_private_forecast_intake' AND e.body::jsonb->>'protocol'='factory-forecast-selection/v1'
   AND s.reference=NEW.request->>'scenario_reference'
   AND e.body::jsonb-ARRAY['protocol','scenario_id','as_of','months','source_ids','template_id','audience']='{}'::jsonb
   AND e.body::jsonb->>'audience' IN ('internal','management','group')
   AND jsonb_typeof(e.body::jsonb->'source_ids')='array'
   AND jsonb_array_length(e.body::jsonb->'source_ids')=(SELECT count(*) FROM (
    SELECT s.evidence_id AS id UNION SELECT (item->>'evidence_id')::bigint FROM jsonb_array_elements(s.payload->'openings') item
    UNION SELECT (item->>'evidence_id')::bigint FROM jsonb_array_elements(s.payload->'items') item) exact_sources)
   AND NOT EXISTS(SELECT id FROM (
    SELECT s.evidence_id AS id UNION SELECT (item->>'evidence_id')::bigint FROM jsonb_array_elements(s.payload->'openings') item
    UNION SELECT (item->>'evidence_id')::bigint FROM jsonb_array_elements(s.payload->'items') item) exact_sources
    WHERE NOT e.body::jsonb->'source_ids' @> jsonb_build_array(id))
   AND (e.body::jsonb->'template_id'='null'::jsonb OR EXISTS(SELECT 1 FROM documents_template t
    WHERE t.id=(e.body::jsonb->>'template_id')::bigint AND t.case_id=NEW.case_id AND t.definition->>'document_type'=CASE WHEN e.body::jsonb->>'audience'='group' THEN 'finance_group_report' ELSE 'finance_report' END))
   AND e.body::jsonb->>'as_of'=s.payload->>'as_of' AND e.body::jsonb->'months'=s.payload->'months'
   AND a.action IN ('factory.forecast_intake','factory.forecast_source')
   AND a.data=jsonb_build_object('evidence_id',e.id,'sha256',e.sha256)
   AND NEW.invoice_id IS NULL AND NEW.preparation_id IS NULL)
 THEN RAISE EXCEPTION 'Exact native forecast intake provenance required'; END IF;
 IF NEW.definition='finance-forecast/v1' AND NEW.status='verified' AND NOT EXISTS(
  SELECT 1 FROM core_evidence e JOIN finance_forecastscenario s ON s.id=(e.body::jsonb->>'scenario_id')::bigint
  JOIN finance_forecastrun r ON r.scenario_id=s.id JOIN finance_forecastreview rv ON rv.run_id=r.id
  JOIN finance_forecastbinding b ON b.run_id=r.id JOIN documents_version v ON v.id=b.version_id
  JOIN documents_publication p ON p.version_id=v.id
  JOIN workflows_factoryactivity fa ON fa.work_id=NEW.id AND fa.kind='ACT13'
  JOIN workflows_factoryattempt a ON a.activity_id=fa.id AND a.phase='observed'
  WHERE e.id=NEW.source_head_id AND r.case_id=NEW.case_id AND s.case_id=NEW.case_id
   AND rv.verdict='approve' AND rv.id=(SELECT max(id) FROM finance_forecastreview WHERE run_id=r.id)
   AND NOT EXISTS(SELECT 1 FROM finance_forecastscenario newer WHERE newer.case_id=s.case_id AND newer.reference=s.reference AND newer.number>s.number)
   AND p.factory_work_id=NEW.id AND p.factory_source_id=e.id AND p.factory_policy_id=NEW.policy_id
   AND v.template_id=(e.body::jsonb->>'template_id')::bigint AND v.audience=e.body::jsonb->>'audience'
   AND b.snapshot->>'run_hash'=r.sha256 AND b.snapshot->>'output_review'=rv.id::text
   AND a.result->'verified'='true'::jsonb AND a.result->>'head'=e.id::text
   AND a.result->>'forecast_run'=r.id::text AND a.result->>'forecast_review'=rv.id::text
   AND a.result->>'document_version'=v.id::text AND a.result->>'publication'=p.id::text
   AND jsonb_array_length(p.recipient_ids)>0
   AND NOT EXISTS(SELECT 1 FROM jsonb_array_elements_text(p.recipient_ids) recipient WHERE NOT EXISTS(
    SELECT 1 FROM documents_publicationreceipt pr WHERE pr.publication_id=p.id AND pr.recipient_id=recipient::bigint
     AND pr.payload_sha256=v.payload_sha256 AND pr.payload=v.payload)))
 THEN RAISE EXCEPTION 'Observed exact native forecast approval and aggregate receipts required'; END IF;

 IF NEW.definition='finance-ppe/v1' AND NEW.status='verified' AND NOT EXISTS(
  SELECT 1 FROM core_evidence e
  JOIN finance_schedulework r ON r.id=(e.body::jsonb->>'register_id')::bigint
  JOIN finance_schedulework s ON s.case_id=NEW.case_id AND s.kind='ppe_schedule'
  JOIN finance_schedulereview sr ON sr.work_id=s.id AND sr.authority->>'purpose'='schedule'
  JOIN finance_schedulereview rr ON rr.work_id=r.id AND rr.authority->>'purpose'='register'
  JOIN workflows_factoryactivity fa ON fa.work_id=NEW.id AND fa.kind='ACT13'
  JOIN workflows_factoryattempt a ON a.activity_id=fa.id AND a.phase='observed'
  WHERE e.id=NEW.source_head_id AND s.payload->>'register_id'=r.id::text
   AND s.payload->'prior_id'=e.body::jsonb->'prior_id'
   AND s.parent_id IS NOT DISTINCT FROM (e.body::jsonb->>'ledger_id')::bigint
   AND s.reference=NEW.request->>'reference' AND s.result->>'status'='ready'
   AND psl_ppe_schedule_current(s.id) AND psl_ppe_review_current(sr.id)
   AND psl_ppe_policy_current(NEW.case_id,NEW.policy_id)
   AND psl_ppe_grants(NEW.case_id,e.created_by_id,ARRAY['case.read','finance.read','ppe.read','evidence.add'])
   AND EXISTS(SELECT 1 FROM core_audit intake WHERE intake.case_id=NEW.case_id AND intake.actor_id=e.created_by_id
    AND intake.data=jsonb_build_object('evidence_id',e.id,'sha256',e.sha256)
    AND ((intake.action='factory.ppe_intake' AND psl_ppe_grants(NEW.case_id,e.created_by_id,ARRAY['factory.start']))
     OR (intake.action='factory.ppe_source' AND psl_ppe_grants(NEW.case_id,e.created_by_id,ARRAY['factory.manage']))))
   AND sr.verdict='approve' AND rr.verdict='approve' AND sr.snapshot=s.snapshot AND rr.snapshot=r.snapshot
   AND sr.id=(SELECT max(id) FROM finance_schedulereview WHERE work_id=s.id AND authority->>'purpose'='schedule')
   AND rr.id=(SELECT max(id) FROM finance_schedulereview WHERE work_id=r.id AND authority->>'purpose'='register')
   AND NOT EXISTS(SELECT 1 FROM finance_schedulework newer WHERE newer.case_id=NEW.case_id AND
     ((newer.kind=r.kind AND newer.reference=r.reference AND newer.version>r.version) OR
      (newer.kind=s.kind AND newer.reference=s.reference AND newer.version>s.version)))
   AND a.result->'verified'='true'::jsonb AND a.result->>'head'=e.id::text
   AND a.result->>'schedule'=s.id::text AND a.result->>'schedule_sha256'=s.sha256
   AND a.result->>'schedule_review'=sr.id::text AND a.result->>'register_review'=rr.id::text
   AND a.result->'ledger'=COALESCE(to_jsonb(s.parent_id),'null'::jsonb)
   AND a.result->'ledger_posted'='false'::jsonb
   AND a.result->>'full_owner_oracle_acceptance'='unresolved'
   AND (s.parent_id IS NULL OR EXISTS(SELECT 1 FROM finance_financerun note
     JOIN finance_financereview source_review ON source_review.source_id=note.source_id AND source_review.purpose='source'
     WHERE note.id=s.parent_id AND note.case_id=NEW.case_id AND note.kind='mapping'
      AND source_review.verdict='approve'
      AND source_review.id=(SELECT max(id) FROM finance_financereview WHERE source_id=note.source_id AND purpose='source')
      AND note.snapshot->'source_review'->>'id'=source_review.id::text
      AND a.result->'ledger_reviews'=jsonb_build_object('source',note.snapshot->'source_review','rules',note.snapshot->'reviews')))
   AND s.snapshot->>'register_review'=rr.id::text
   AND NOT EXISTS(SELECT 1 FROM jsonb_each(s.snapshot->'policies') pin
     WHERE pin.value->>'status'<>'ACTIVE' OR NOT EXISTS(SELECT 1 FROM policy_configuration pc
      WHERE pc.id=(pin.value->>'id')::bigint AND pc.case_id=NEW.case_id AND pc.component=pin.key
       AND (SELECT state FROM policy_policystate WHERE configuration_id=pc.id ORDER BY id DESC LIMIT 1)='active'))
   AND NOT EXISTS(SELECT 1 FROM (VALUES(sr.actor_id),(rr.actor_id)) reviewer(id)
     WHERE NOT EXISTS(SELECT 1 FROM auth_user u JOIN identity_grant g ON g.user_id=u.id
      WHERE u.id=reviewer.id AND u.is_active AND g.case_id=NEW.case_id AND g.action='ppe.review' AND g.active)))
 THEN RAISE EXCEPTION 'Observed exact current human-reviewed PPE schedule and accounting note required'; END IF;

 IF NEW.definition='finance-schedules/v1' AND NEW.status='verified' AND NOT EXISTS(
  SELECT 1 FROM core_evidence e JOIN core_evidence supplied ON supplied.id=(e.body::jsonb->>'evidence_id')::bigint
  JOIN finance_schedulework s ON s.evidence_id=supplied.id AND s.case_id=NEW.case_id AND s.kind=NEW.request->>'kind' AND s.reference=NEW.request->>'reference'
  JOIN finance_schedulereview r ON r.work_id=s.id
  JOIN workflows_factoryactivity fa ON fa.work_id=NEW.id AND fa.kind='ACT13'
  JOIN workflows_factoryattempt a ON a.activity_id=fa.id AND a.phase='observed'
  WHERE e.id=NEW.source_head_id AND s.parent_id IS NOT DISTINCT FROM (e.body::jsonb->>'parent_id')::bigint
   AND s.payload=CASE WHEN s.kind='income' THEN e.body::jsonb->'payload' ELSE supplied.body::jsonb END
   AND s.result->>'status'='ready' AND psl_schedules_review_current(r.id)
   AND psl_schedules_policy_current(NEW.case_id,NEW.policy_id)
   AND psl_schedules_grants(NEW.case_id,e.created_by_id,ARRAY['case.read','finance.read','schedules.read','evidence.add'])
   AND EXISTS(SELECT 1 FROM core_audit intake WHERE intake.case_id=NEW.case_id AND intake.actor_id=e.created_by_id
    AND intake.data=jsonb_build_object('evidence_id',e.id,'sha256',e.sha256)
    AND ((intake.action='factory.schedules_intake' AND psl_schedules_grants(NEW.case_id,e.created_by_id,ARRAY['factory.start']))
     OR (intake.action='factory.schedules_source' AND psl_schedules_grants(NEW.case_id,e.created_by_id,ARRAY['factory.manage']))))
   AND a.result->'verified'='true'::jsonb AND a.result->>'head'=e.id::text
   AND a.result->>'schedule'=s.id::text AND a.result->>'schedule_sha256'=s.sha256
   AND a.result->>'schedule_review'=r.id::text AND a.result->>'source_evidence'=supplied.id::text
   AND a.result->'parent'=COALESCE(to_jsonb(s.parent_id),'null'::jsonb)
   AND a.result->'ledger_posted'='false'::jsonb AND a.result->'native_workbook_verified'='false'::jsonb)
 THEN RAISE EXCEPTION 'Observed exact current human-reviewed selected schedule required'; END IF;

 IF TG_OP='UPDATE' AND NEW.definition='finance-forecast/v1' AND NEW.source_head_id IS DISTINCT FROM OLD.source_head_id
 AND ((SELECT body::jsonb->>'audience'='group' FROM core_evidence WHERE id=NEW.source_head_id)
 IS DISTINCT FROM (SELECT body::jsonb->>'audience'='group' FROM core_evidence WHERE id=OLD.source_head_id))
 THEN RAISE EXCEPTION 'Separate group audience work identity is immutable'; END IF;

 IF NEW.definition='pmo-weekly-report/v1' AND NEW.status='verified' AND NOT EXISTS(
  SELECT 1 FROM documents_publication p JOIN documents_version v ON v.id=p.version_id
  JOIN documents_controlledreview rv ON rv.id=p.review_id
  JOIN workflows_factoryactivity fa ON fa.work_id=NEW.id AND fa.kind='ACT13'
  JOIN workflows_factoryattempt a ON a.activity_id=fa.id AND a.phase='observed'
  WHERE p.factory_work_id=NEW.id AND p.factory_source_id=NEW.source_head_id AND p.factory_policy_id=NEW.policy_id
   AND psl_reporting_document(NEW.id,NEW.source_head_id,v.id)
   AND rv.version_id=v.id AND rv.verdict='approve' AND rv.payload_sha256=v.payload_sha256
   AND rv.id=(SELECT max(id) FROM documents_controlledreview WHERE version_id=v.id)
   AND psl_reporting_review(NEW.case_id,rv.id)
   AND psl_reporting_principals(NEW.id,v.id,p.actor_id)
   AND psl_reporting_distribution(NEW.case_id,v.id,p.policies,p.recipient_ids,p.retention_days)
   AND psl_reporting_grants(NEW.case_id,p.actor_id,ARRAY['case.read','report.read','factory.execute','document.publish'])
   AND a.result->'verified'='true'::jsonb AND a.result->>'head'=NEW.source_head_id::text AND a.result->>'document_version'=v.id::text
   AND a.result->>'publication'=p.id::text AND a.result->'complete_project_coverage'='false'::jsonb AND a.result->'external_delivery_verified'='false'::jsonb AND a.result->'business_approval_granted'='false'::jsonb
   AND jsonb_array_length(p.recipient_ids)>0
   AND (SELECT count(*) FROM documents_publicationreceipt WHERE publication_id=p.id)=jsonb_array_length(p.recipient_ids)
   AND NOT EXISTS(SELECT 1 FROM jsonb_array_elements_text(p.recipient_ids) recipient WHERE NOT EXISTS(
    SELECT 1 FROM documents_publicationreceipt pr WHERE pr.publication_id=p.id AND pr.recipient_id=recipient::bigint
     AND pr.payload=v.payload AND pr.payload_sha256=v.payload_sha256 AND psl_reporting_grants(NEW.case_id,pr.recipient_id,ARRAY['document.receive:client']))))
 THEN RAISE EXCEPTION 'Observed exact current weekly client report, native PMO Lead review and every recipient receipt required'; END IF;

 IF NEW.definition='pmo-escalation/v1' AND NEW.status='verified' AND NOT EXISTS(
 SELECT 1 FROM documents_publication p JOIN documents_version v ON v.id=p.version_id JOIN documents_publicationjob j ON j.publication_id=p.id
 JOIN pmo_escalationdocumentbinding b ON b.version_id=v.id JOIN pmo_escalationrequest r ON r.id=b.request_id JOIN pmo_escalationprofile ep ON ep.id=r.profile_id
 JOIN workflows_factoryactivity fa ON fa.work_id=NEW.id AND fa.kind='ACT13' JOIN workflows_factoryattempt a ON a.activity_id=fa.id AND a.phase='observed'
 WHERE p.factory_work_id=NEW.id AND p.factory_source_id=NEW.source_head_id AND p.factory_policy_id=NEW.policy_id AND j.status='confirmed'
 AND psl_escalation_document(NEW.id,v.id,p.review_id,p.actor_id,p.factory_policy_id,p.factory_source_id,p.recipient_ids,p.policies)
 AND a.result->'verified'='true'::jsonb AND a.result->'issue_resolution_verified'='false'::jsonb AND a.result->>'head'=NEW.source_head_id::text
 AND a.result->>'verification_scope'='reviewed_escalation_communication' AND a.result->>'request'=r.id::text AND a.result->>'profile'=ep.id::text AND a.result->>'issue_state'=ep.state_id::text
 AND a.result->'decision'=COALESCE(to_jsonb(b.decision_id),'null'::jsonb) AND a.result->>'direction'=r.direction AND a.result->>'target'=r.target
 AND a.result->>'document_version'=v.id::text AND a.result->>'publication'=p.id::text
 AND a.result->'receipt_ids'=(SELECT jsonb_agg(pr.id ORDER BY pr.id) FROM documents_publicationreceipt pr WHERE pr.publication_id=p.id)
 AND (SELECT count(*) FROM documents_publicationreceipt WHERE publication_id=p.id)=jsonb_array_length(p.recipient_ids)
 AND NOT EXISTS(SELECT 1 FROM jsonb_array_elements_text(p.recipient_ids) recipient WHERE NOT EXISTS(SELECT 1 FROM documents_publicationreceipt pr WHERE pr.publication_id=p.id AND pr.recipient_id=recipient::bigint AND pr.payload=v.payload AND pr.payload_sha256=v.payload_sha256)))
 THEN RAISE EXCEPTION 'Observed exact current communication and every receipt required; issue resolution is not verified'; END IF;

 IF NEW.definition='pmo-minutes/v1' THEN
  IF NEW.invoice_id IS NOT NULL OR NEW.preparation_id IS NOT NULL OR NOT EXISTS(
   SELECT 1 FROM core_evidence e JOIN core_audit a ON a.case_id=e.case_id AND a.actor_id=e.created_by_id
   JOIN core_evidence note ON note.id=(e.body::jsonb->>'evidence_id')::bigint AND note.case_id=e.case_id
   JOIN documents_template t ON t.id=(e.body::jsonb->>'template_id')::bigint AND t.case_id=e.case_id
   WHERE e.id=NEW.source_head_id AND e.case_id=NEW.case_id AND e.kind='agent_private_minutes_intake'
    AND e.body::jsonb->>'protocol'='factory-minutes-intake/v1' AND note.kind='meeting_notes'
    AND t.definition->>'document_type'='minutes' AND t.definition->'audience_fields' ? (e.body::jsonb->>'audience')
    AND (e.body::jsonb->>'audience'='internal' AND e.body::jsonb->'publish'='false'::jsonb OR e.body::jsonb->>'audience'='client' AND e.body::jsonb->'publish'='true'::jsonb)
    AND e.body::jsonb - ARRAY['protocol','meeting_version_id','evidence_id','template_id','audience','publish']='{}'::jsonb
    AND a.action IN ('factory.minutes_intake','factory.minutes_source')
    AND a.data=jsonb_build_object('evidence_id',e.id,'sha256',e.sha256)
    AND encode(sha256(convert_to(e.body,'UTF8')),'hex')=e.sha256)
   THEN RAISE EXCEPTION 'Exact authorized typed formal-minutes intake required'; END IF;
  IF NEW.status='verified' AND NOT EXISTS(
   SELECT 1 FROM workflows_factoryactivity fa JOIN workflows_factoryattempt a ON a.activity_id=fa.id
   WHERE fa.work_id=NEW.id AND fa.kind='ACT13' AND a.phase='observed'
    AND a.result->'verified'='true'::jsonb AND a.result->>'head'=NEW.source_head_id::text
    AND a.result->'actions_completed'='false'::jsonb AND a.result->'scope_changed'='false'::jsonb
    AND psl_minutes_current(NEW.id,NEW.source_head_id,(a.result->>'document_version')::bigint)
    AND psl_schedules_policy_current(NEW.case_id,NEW.policy_id)
    AND a.result->'manifest'=(SELECT manifest FROM pmo_minutesreportbinding WHERE version_id=(a.result->>'document_version')::bigint)
    AND ((SELECT body::jsonb->'publish' FROM core_evidence WHERE id=NEW.source_head_id)='false'::jsonb OR EXISTS(
     SELECT 1 FROM documents_publication p JOIN documents_controlledreview r ON r.id=p.review_id JOIN documents_version v ON v.id=p.version_id
     WHERE p.id=(a.result->>'publication')::bigint AND p.version_id=(a.result->>'document_version')::bigint
      AND p.factory_work_id=NEW.id AND p.factory_source_id=NEW.source_head_id AND p.factory_policy_id=NEW.policy_id
      AND r.version_id=v.id AND r.verdict='approve' AND r.payload_sha256=v.payload_sha256
      AND r.id=(SELECT max(id) FROM documents_controlledreview WHERE version_id=v.id)
      AND psl_schedules_authority_current(NEW.case_id,r.authority)
      AND psl_schedules_grants(NEW.case_id,r.actor_id,ARRAY['document.review_controlled'])
      AND psl_schedules_authority_current(NEW.case_id,p.policies)
      AND p.actor_id=(psl_schedules_values(NEW.policy_id)->0->>'executor_id')::bigint
      AND psl_schedules_grants(NEW.case_id,p.actor_id,ARRAY['case.read','meeting.read','factory.execute','document.publish'])
      AND p.recipient_ids=(SELECT jsonb_agg(DISTINCT (recipient->>'user_id')::bigint ORDER BY (recipient->>'user_id')::bigint)
       FROM jsonb_array_elements(psl_schedules_values((p.policies->>'D11.recipient_grant_refs')::bigint)) recipient WHERE recipient->>'audience'=v.audience)
      AND p.retention_days=(psl_schedules_values((p.policies->>'D11.template_storage_retention_rules')::bigint)->0->>'retention_days')::integer
      AND NOT EXISTS(SELECT 1 FROM jsonb_array_elements_text(p.recipient_ids) recipient WHERE NOT psl_schedules_grants(NEW.case_id,recipient::bigint,ARRAY['document.receive:'||v.audience]))
      AND jsonb_array_length(p.recipient_ids)>0
      AND NOT EXISTS(SELECT 1 FROM jsonb_array_elements_text(p.recipient_ids) recipient WHERE NOT EXISTS(
       SELECT 1 FROM documents_publicationreceipt pr WHERE pr.publication_id=p.id AND pr.recipient_id=recipient::bigint
        AND pr.payload=v.payload AND pr.payload_sha256=v.payload_sha256)))))
   THEN RAISE EXCEPTION 'Observed current human-confirmed minutes and exact requested recipient receipts required'; END IF;
 END IF;

 IF NEW.definition='finance-bu/v1' AND NEW.status='verified' AND NOT EXISTS(
  SELECT 1 FROM core_evidence e JOIN finance_buwork w ON w.case_id=NEW.case_id AND w.kind=NEW.request->>'mode'
  JOIN finance_bureport p ON p.work_id=w.id JOIN finance_bureview rv ON rv.id=p.review_id
  JOIN workflows_factoryactivity fa ON fa.work_id=NEW.id AND fa.kind='ACT13'
  JOIN workflows_factoryattempt a ON a.activity_id=fa.id AND a.phase='observed'
  JOIN policy_configuration pc ON pc.id=(p.policy_ids->>'BU.disclosure_rules')::bigint
  WHERE e.id=NEW.source_head_id AND w.reference='factory-bu-'||NEW.id::text
   AND psl_schedules_grants(NEW.case_id,e.created_by_id,ARRAY['case.read','bu.read','bu.private.read','evidence.add'])
   AND EXISTS(SELECT 1 FROM core_audit origin WHERE origin.case_id=NEW.case_id AND origin.actor_id=e.created_by_id
    AND origin.data=jsonb_build_object('evidence_id',e.id,'sha256',e.sha256)
    AND ((origin.action='factory.bu_intake' AND psl_schedules_grants(NEW.case_id,e.created_by_id,ARRAY['factory.start']))
     OR (origin.action='factory.bu_source' AND psl_schedules_grants(NEW.case_id,e.created_by_id,ARRAY['factory.manage']))))
   AND w.metadata->>'status'='complete' AND w.payload->'conserved'='true'::jsonb
   AND psl_bu_current(w.id) AND psl_bu_review(rv.id) AND psl_bu_private(w.id,p.actor_id) AND psl_bu_authority(w.id,p.actor_id,'publish',p.policy_ids)
   AND (COALESCE(w.metadata->'historical','false'::jsonb)='false'::jsonb OR EXISTS(SELECT 1 FROM finance_bureview history WHERE history.work_id=w.id AND history.purpose='historical' AND psl_bu_review(history.id)))
   AND rv.work_id=w.id AND rv.purpose=w.kind AND rv.verdict='approve' AND rv.subject_sha256=w.sha256
   AND rv.id=(SELECT max(id) FROM finance_bureview WHERE work_id=w.id AND purpose=w.kind)
   AND NOT EXISTS(SELECT 1 FROM finance_buwork newer WHERE newer.case_id=w.case_id AND newer.kind=w.kind AND newer.reference=w.reference AND newer.version>w.version AND newer.metadata->'accepted'='true'::jsonb)
   AND NOT EXISTS(SELECT 1 FROM finance_bureport newer JOIN finance_buwork nw ON nw.id=newer.work_id WHERE nw.case_id=w.case_id AND nw.kind=w.kind AND nw.metadata->'scope'=w.metadata->'scope' AND newer.id>p.id)
   AND ((w.kind='staff' AND w.payroll_id=(e.body::jsonb->'inputs'->>'payroll_id')::bigint AND w.metadata->'rule_ids'=e.body::jsonb->'inputs'->'rule_ids')
    OR (w.kind='event' AND w.parent_id=(e.body::jsonb->'inputs'->>'source_id')::bigint AND w.metadata->'comparison'=e.body::jsonb->'inputs'->'comparison'))
   AND psl_schedules_policy_current(NEW.case_id,pc.id)
   AND psl_schedules_grants(NEW.case_id,p.actor_id,ARRAY['case.read','bu.read','bu.private.read','bu.publish'])
   AND psl_schedules_grants(NEW.case_id,rv.actor_id,ARRAY['case.read','bu.read','bu.private.read','bu.review'])
   AND NOT EXISTS(SELECT 1 FROM jsonb_each(w.metadata->'policy_ids') pin WHERE NOT psl_schedules_policy_current(NEW.case_id,(pin.value#>>'{}')::bigint))
   AND p.payload-ARRAY['entity','period','currency','unit','by_bu','company_source_total','allocated_total','company_only','residual','conserved','source_work','coverage','native_authenticity_verified','destination','ledger_posted','source_written','disclosure']='{}'::jsonb
   AND p.payload->>'disclosure'='aggregate_only' AND NOT (p.payload ? 'rows') AND p.payload->'ledger_posted'='false'::jsonb AND p.payload->'source_written'='false'::jsonb
   AND p.payload->>'source_work'=w.id::text AND p.payload->'by_bu'=w.payload->'by_bu'
   AND p.payload->'company_source_total'=w.payload->'source_total' AND p.payload->'allocated_total'=w.payload->'allocated_total' AND p.payload->'residual'=w.payload->'residual'
   AND a.result->'verified'='true'::jsonb AND a.result->>'head'=e.id::text AND a.result->>'work'=w.id::text AND a.result->>'publication'=p.id::text
   AND a.result->'private_payloads_in_result'='false'::jsonb AND a.result->'source_written'='false'::jsonb AND a.result->'ledger_posted'='false'::jsonb
   AND jsonb_array_length(psl_schedules_values(pc.id)->0->'recipient_ids')>0
   AND (SELECT count(*) FROM finance_bureceipt WHERE report_id=p.id)=jsonb_array_length(psl_schedules_values(pc.id)->0->'recipient_ids')
   AND NOT EXISTS(SELECT 1 FROM jsonb_array_elements_text(psl_schedules_values(pc.id)->0->'recipient_ids') recipient WHERE NOT EXISTS(
    SELECT 1 FROM finance_bureceipt rr WHERE rr.report_id=p.id AND rr.actor_id=recipient::bigint
     AND a.result->'receipt_ids' @> to_jsonb(ARRAY[rr.id])
     AND psl_schedules_grants(NEW.case_id,rr.actor_id,ARRAY['case.read','bu.read','bu.report.read','bu.receive']))))
 THEN RAISE EXCEPTION 'Observed exact reviewed BU aggregate and actual recipient-owned receipts required'; END IF;
 RETURN NEW;
END $$;

CREATE OR REPLACE FUNCTION psl_engagement_factory_source(w workflows_factorywork) RETURNS boolean LANGUAGE sql STABLE AS $$
 SELECT EXISTS(SELECT 1 FROM core_evidence e JOIN pmo_engagementrecord r ON r.id::text=e.body::jsonb->>'capture'
 WHERE e.id=w.source_head_id AND e.case_id=w.case_id AND e.kind='agent_private_engagement_intake'
  AND e.source='psl:engagement-intake/v1' AND e.body::jsonb->>'protocol'='engagement-intake/v1'
  AND e.body::jsonb - ARRAY['protocol','capture','capture_hash','source','sha256']='{}'::jsonb
  AND encode(sha256(convert_to(e.body,'UTF8')),'hex')=e.sha256
  AND EXISTS(SELECT 1 FROM core_audit a WHERE a.case_id=w.case_id AND a.actor_id=e.created_by_id AND a.action='factory.engagement_intake'
    AND a.data=jsonb_build_object('head',e.id,'sha256',e.sha256))
  AND r.case_id=w.case_id AND r.kind='capture' AND r.evidence_id::text=e.body::jsonb->>'source'
  AND EXISTS(SELECT 1 FROM core_evidence original WHERE original.id=r.evidence_id AND original.case_id=w.case_id AND original.sha256=e.body::jsonb->>'sha256')
  AND w.invoice_id IS NULL AND w.preparation_id IS NULL);
$$;
CREATE OR REPLACE FUNCTION psl_engagement_factory_identity_clear(cid uuid, uid bigint) RETURNS boolean LANGUAGE sql STABLE AS $$
 SELECT NOT EXISTS(SELECT 1 FROM (SELECT * FROM pmo_projectidentitydecision WHERE case_id=cid ORDER BY id DESC LIMIT 100) d
 WHERE NOT psl_schedules_grants(d.other_case_id,uid,ARRAY['case.read','engagement.read'])
 OR (d.relation IN ('alias','unresolved')
  AND d.id=(SELECT max(id) FROM pmo_projectidentitydecision WHERE case_id=cid AND other_case_id=d.other_case_id)
  AND d.data->>'source_capture'=(SELECT max(id)::text FROM pmo_engagementrecord WHERE case_id=cid AND kind='capture')
  AND d.data->>'target_capture'=(SELECT max(id)::text FROM pmo_engagementrecord WHERE case_id=d.other_case_id AND kind='capture')
  AND psl_schedules_policy_current(cid,(d.data->>'source_policy')::bigint)
  AND psl_schedules_policy_current(d.other_case_id,(d.data->>'target_policy')::bigint)
  AND psl_schedules_grants(cid,d.actor_id,ARRAY['case.read','engagement.read','engagement.resolve_identity'])
  AND psl_schedules_grants(d.other_case_id,d.actor_id,ARRAY['case.read','engagement.read','engagement.resolve_identity'])
  AND psl_schedules_role_current(cid,d.actor_id,d.data->'source_authority',d.data->>'role')
  AND psl_schedules_role_current(d.other_case_id,d.actor_id,d.data->'target_authority',d.data->>'role')
  AND EXISTS(SELECT 1 FROM jsonb_array_elements(psl_schedules_values((d.data->>'source_policy')::bigint)) v WHERE v->'resolution_roles' ? (d.data->>'role'))
  AND EXISTS(SELECT 1 FROM jsonb_array_elements(psl_schedules_values((d.data->>'target_policy')::bigint)) v WHERE v->'resolution_roles' ? (d.data->>'role'))
  AND d.data->'access_transferred'='false'::jsonb AND d.data->'business_records_transferred'='false'::jsonb AND d.data->'financial_authority'='false'::jsonb));
$$;
CREATE OR REPLACE FUNCTION psl_engagement_public_source(cid uuid, eid bigint) RETURNS boolean LANGUAGE sql STABLE AS $$
 SELECT EXISTS(SELECT 1 FROM core_evidence e WHERE e.id=eid AND e.case_id=cid
  AND e.kind NOT IN ('ledger_source','quickbooks_verification','ledger_resolution','ledger_resolution_review','approval_source','approval_observation','migration_proof','d03_source','planning_packet','planning_prd_alignment','planning_scope_alignment','planning_contract_comparison','planning_readiness','finance_group_snapshot')
  AND e.kind !~ '^(d03_control_|p14_|ops_|integration_|agent_private_|forecast_)'
  AND e.source<>'psl:p56-confirmed-request/v1'
  AND NOT(e.kind='finance_report_snapshot' AND e.source LIKE 'derived:forecast:%')
  AND NOT EXISTS(SELECT 1 FROM finance_forecastscenario f WHERE f.case_id=cid AND
   (f.evidence_id=eid OR EXISTS(SELECT 1 FROM jsonb_array_elements(f.payload->'items') item WHERE item->>'evidence_id'=eid::text)
    OR EXISTS(SELECT 1 FROM jsonb_array_elements(f.payload->'openings') opening WHERE opening->>'evidence_id'=eid::text))));
$$;
CREATE OR REPLACE FUNCTION psl_engagement_planning_inputs_current(eid bigint) RETURNS boolean LANGUAGE sql STABLE AS $$
 SELECT EXISTS(SELECT 1 FROM core_evidence e WHERE e.id=eid AND e.kind='planning_packet'
  AND encode(sha256(convert_to(e.body,'UTF8')),'hex')=e.sha256
  AND NOT EXISTS(SELECT 1 FROM jsonb_array_elements(e.body::jsonb->'payload'->'stakeholders') s
    WHERE (s->'contact_id'<>'null'::jsonb AND NOT psl_schedules_grants(e.case_id,(s->>'contact_id')::bigint,ARRAY['planning.participate']))
     OR (s->'evidence_id'<>'null'::jsonb AND NOT psl_engagement_public_source(e.case_id,(s->>'evidence_id')::bigint)))
  AND NOT EXISTS(SELECT 1 FROM jsonb_array_elements(e.body::jsonb->'payload'->'questions') q
    WHERE (q->'evidence_id'<>'null'::jsonb AND NOT psl_engagement_public_source(e.case_id,(q->>'evidence_id')::bigint))
     OR (q->'action_id'<>'null'::jsonb AND NOT EXISTS(SELECT 1 FROM pmo_actionitem a WHERE a.id::text=q->>'action_id' AND a.case_id=e.case_id
      AND a.current_id::text=e.body::jsonb->'action_heads'->>(q->>'action_id'))))
  AND NOT EXISTS(SELECT 1 FROM jsonb_each(e.body::jsonb->'action_heads') h
    WHERE NOT EXISTS(SELECT 1 FROM pmo_actionitem a WHERE a.id::text=h.key AND a.case_id=e.case_id AND to_jsonb(a.current_id)=h.value))
  AND NOT EXISTS(SELECT 1 FROM unnest(ARRAY['prd_id','scope_id','engineering_estimate_id','security_estimate_id']) k
    WHERE e.body::jsonb->'payload'->k<>'null'::jsonb AND NOT psl_engagement_public_source(e.case_id,(e.body::jsonb->'payload'->>k)::bigint)));
$$;
CREATE OR REPLACE FUNCTION psl_engagement_worker_current(w workflows_factorywork) RETURNS boolean LANGUAGE sql STABLE AS $$
 SELECT w.execution_binding_id IS NULL OR EXISTS(
  SELECT 1 FROM workflows_factoryexecutionbinding b WHERE b.id=w.execution_binding_id AND b.work_id=w.id
   AND psl_schedules_policy_current(w.case_id,b.configuration_id)
   AND EXISTS(SELECT 1 FROM policy_configuration p WHERE p.id=b.configuration_id AND p.case_id=w.case_id AND p.component='OPS.factory_recovery_authority')
   AND EXISTS(SELECT 1 FROM jsonb_array_elements(psl_schedules_values(b.configuration_id)) value
    WHERE value->'rules' @> jsonb_build_array(b.rule)
     AND (SELECT count(*) FROM jsonb_array_elements(value->'rules') rule WHERE rule->>'definition'=w.definition)=1)
   AND b.rule->>'definition'=w.definition AND b.rule->>'method'='reviewed_execution_principal_v1'
   AND b.rule->>'principal_id'=b.principal_id::text AND b.rule->>'reviewer_id'=b.reviewer_id::text
   AND b.rule->'independent_of_worker' IN ('true'::jsonb,'false'::jsonb)
   AND (b.rule->'independent_of_worker'='false'::jsonb OR b.principal_id<>b.reviewer_id)
   AND (b.rule->>'valid_from')::timestamptz<=statement_timestamp() AND statement_timestamp()<(b.rule->>'valid_until')::timestamptz
   AND psl_schedules_grants(w.case_id,b.principal_id,ARRAY['case.read','factory.read','engagement.read','factory.execute'])
   AND psl_schedules_grants(w.case_id,b.reviewer_id,ARRAY['case.read','factory.read','engagement.read','factory.manage'])
   AND EXISTS(SELECT 1 FROM policy_configuration roles WHERE roles.case_id=w.case_id AND roles.component='D05.role_principal_assignments'
    AND psl_schedules_policy_current(w.case_id,roles.id)
    AND psl_schedules_role_current(w.case_id,b.reviewer_id,jsonb_build_object('D05.role_principal_assignments',roles.id),b.rule->>'review_role'))
   AND NOT EXISTS(SELECT 1 FROM policy_scopeapplication app JOIN policy_scopeversion scope ON scope.id=app.source_id
    JOIN policy_configuration origin ON origin.id=scope.configuration_id WHERE app.configuration_id=b.configuration_id
     AND (NOT psl_schedules_grants(origin.case_id,b.principal_id,ARRAY['case.read','policy.read'])
      OR NOT psl_schedules_grants(origin.case_id,b.reviewer_id,ARRAY['case.read','policy.read'])))
 );
$$;
CREATE OR REPLACE FUNCTION psl_engagement_factory_current(w workflows_factorywork, result jsonb) RETURNS boolean LANGUAGE sql STABLE AS $$
 SELECT psl_engagement_factory_source(w) AND psl_engagement_worker_current(w)
 AND psl_engagement_factory_identity_clear(w.case_id,COALESCE((SELECT principal_id FROM workflows_factoryexecutionbinding WHERE id=w.execution_binding_id),w.actor_id))
 AND psl_schedules_grants(w.case_id,COALESCE((SELECT principal_id FROM workflows_factoryexecutionbinding WHERE id=w.execution_binding_id),w.actor_id),ARRAY['case.read','engagement.read','planning.read','factory.execute'])
 AND EXISTS(
 SELECT 1 FROM pmo_engagementrecord c
 JOIN pmo_engagementrecord a ON a.id::text=result->>'assignment' AND a.case_id=w.case_id AND a.kind='assignment'
 JOIN pmo_engagementrecord r ON r.id::text=result->>'registration' AND r.case_id=w.case_id AND r.kind='registration'
 JOIN core_evidence source ON source.id=c.evidence_id AND source.case_id=w.case_id
 JOIN core_evidence plan ON plan.id::text=r.data->>'plan' AND plan.case_id=w.case_id AND plan.kind='plan' AND plan.sha256=r.data->>'plan_sha256'
 JOIN core_evidence packet ON packet.id::text=result->>'planning_packet' AND packet.case_id=w.case_id AND packet.kind='planning_packet'
 JOIN workflows_factorywork child ON child.id::text=result->>'planning_work' AND child.case_id=w.case_id AND child.definition='planning/v1'
 JOIN core_audit receipt ON receipt.id::text=result->>'receipt' AND receipt.case_id=w.case_id AND receipt.action='factory.engagement_planning_linked'
 WHERE c.id::text=result->>'capture' AND c.case_id=w.case_id AND c.kind='capture'
  AND c.id=(SELECT max(id) FROM pmo_engagementrecord WHERE case_id=w.case_id AND kind='capture')
  AND a.id=(SELECT max(id) FROM pmo_engagementrecord WHERE case_id=w.case_id AND kind='assignment')
  AND r.id=(SELECT max(id) FROM pmo_engagementrecord WHERE case_id=w.case_id AND kind='registration')
  AND a.data->>'capture'=c.id::text AND r.data->>'capture'=c.id::text AND r.data->>'assignment'=a.id::text
  AND result->'verified'='true'::jsonb AND result->>'verification_scope'='current_engagement_identity_and_internal_planning_handoff'
  AND result->>'head'=w.source_head_id::text
  AND result->'planning_complete'='false'::jsonb AND result->'external_master_verified'='false'::jsonb AND result->'signature_required'='false'::jsonb
  AND (SELECT body::jsonb->>'capture' FROM core_evidence WHERE id=w.source_head_id)=c.id::text
  AND encode(sha256(convert_to(source.body,'UTF8')),'hex')=source.sha256
  AND psl_engagement_public_source(w.case_id,source.id)
  AND psl_engagement_public_source(w.case_id,plan.id)
  AND (c.data->>'route' IN ('B','C') OR EXISTS(SELECT 1 FROM pmo_rfpdisposition d JOIN pmo_rfpcase rf ON rf.id=d.rfp_id
    JOIN pmo_rfpoutcome o ON o.id=d.outcome_id WHERE d.id::text=c.data->>'rfp_disposition' AND rf.case_id=w.case_id AND d.kind='route_a' AND o.result='won'))
  AND (c.data->>'route'<>'C' OR source.kind='product_input')
  AND psl_schedules_grants(w.case_id,c.actor_id,ARRAY['case.read','engagement.read','engagement.capture'])
  AND psl_schedules_grants(w.case_id,a.actor_id,ARRAY['engagement.assign'])
  AND psl_schedules_grants(w.case_id,(a.data->>'pm_id')::bigint,ARRAY['engagement.read'])
  AND psl_schedules_grants(w.case_id,r.actor_id,ARRAY['engagement.register'])
  AND psl_schedules_policy_current(w.case_id,(a.data->>'policy')::bigint)
  AND psl_schedules_policy_current(w.case_id,(r.data->>'policy')::bigint)
  AND psl_schedules_role_current(w.case_id,a.actor_id,a.data->'authority',a.data->>'role')
  AND psl_schedules_role_current(w.case_id,(a.data->>'pm_id')::bigint,a.data->'pm_authority','PM')
  AND psl_schedules_role_current(w.case_id,r.actor_id,r.data->'authority',r.data->>'role')
  AND EXISTS(SELECT 1 FROM jsonb_array_elements(psl_schedules_values((a.data->>'policy')::bigint)) v WHERE v->'assignment_roles' ? (a.data->>'role'))
  AND EXISTS(SELECT 1 FROM jsonb_array_elements(psl_schedules_values((r.data->>'policy')::bigint)) v WHERE v->'registration_roles' ? (r.data->>'role'))
  AND EXISTS(SELECT 1 FROM pmo_projectidentifier i JOIN core_case k ON k.id=w.case_id WHERE i.case_id=w.case_id AND i.tenant=k.tenant
    AND i.namespace=r.data->>'namespace' AND i.normalized=r.data->>'normalized')
  AND psl_engagement_planning_inputs_current(packet.id)
  AND packet.id=child.source_head_id AND packet.id=(SELECT id FROM core_evidence WHERE case_id=w.case_id AND kind='planning_packet' ORDER BY version DESC LIMIT 1)
  AND packet.body::jsonb->>'engagement_id'=c.id::text AND child.request->>'engagement'=c.id::text
  AND NOT child.cancel_requested AND child.status NOT IN ('cancelled','followup_needed')
  AND psl_schedules_grants(w.case_id,packet.created_by_id,ARRAY['case.read','planning.read','planning.coordinate'])
  AND EXISTS(SELECT 1 FROM core_audit pa WHERE pa.case_id=w.case_id AND pa.actor_id=packet.created_by_id AND pa.action='planning.recorded'
     AND pa.data=jsonb_build_object('kind','packet','evidence_id',packet.id,'sha256',packet.sha256))
  AND receipt.data->>'work'=w.id::text AND receipt.data->>'capture'=c.id::text AND receipt.data->>'planning_work'=child.id::text
 );
$$;
CREATE OR REPLACE FUNCTION psl_engagement_factory_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF NEW.definition<>'engagement/v1' THEN RETURN NEW; END IF;
 IF NOT psl_engagement_factory_source(NEW) THEN RAISE EXCEPTION 'Exact native engagement intake pointer required'; END IF;
 IF NEW.status='verified' AND NOT EXISTS(SELECT 1 FROM workflows_factoryattempt a JOIN workflows_factoryactivity act ON act.id=a.activity_id
  WHERE act.work_id=NEW.id AND act.kind='ACT13' AND a.phase='observed' AND a.id=(SELECT max(x.id) FROM workflows_factoryattempt x JOIN workflows_factoryactivity y ON y.id=x.activity_id WHERE y.work_id=NEW.id AND y.kind='ACT13' AND x.phase='observed')
  AND psl_engagement_factory_current(NEW,a.result))
 THEN RAISE EXCEPTION 'Observed current engagement identity and native planning handoff required'; END IF;
 RETURN NEW;
END $$;
DROP TRIGGER IF EXISTS psl_engagement_factory_guard ON workflows_factorywork;
CREATE TRIGGER psl_engagement_factory_guard BEFORE INSERT OR UPDATE ON workflows_factorywork FOR EACH ROW EXECUTE FUNCTION psl_engagement_factory_guard();


-- Factory-side currentness mirrors. Native Finance remains the decision owner.
CREATE OR REPLACE FUNCTION psl_factory_ledger_read_current(check_id bigint) RETURNS boolean LANGUAGE plpgsql STABLE AS $$
DECLARE x finance_ledgercheck; l finance_ledgerlineage; rules jsonb; cfg bigint; supplied jsonb;
BEGIN
 SELECT * INTO x FROM finance_ledgercheck WHERE id=check_id;
 SELECT * INTO l FROM finance_ledgerlineage WHERE id=x.lineage_id;
 SELECT id INTO cfg FROM policy_configuration WHERE case_id=l.case_id AND component='F01.verification_rules' AND psl_schedules_policy_current(l.case_id,id);
 IF l.id IS NULL OR NOT psl_schedules_policy_current(l.case_id,cfg)
 OR NOT psl_schedules_grants(l.case_id,l.actor_id,ARRAY['case.read','finance.read','ledger.read','ledger.capture'])
 OR NOT psl_schedules_grants(l.case_id,x.actor_id,ARRAY['case.read','finance.read','ledger.read','ledger.verify']) THEN RETURN false; END IF;
 rules:=psl_schedules_values(cfg)->0;
 IF NOT EXISTS(SELECT 1 FROM policy_configuration WHERE id=cfg AND component='F01.verification_rules') THEN RETURN false; END IF;
 SELECT body::jsonb INTO supplied FROM core_evidence WHERE id=x.evidence_id AND case_id=l.case_id AND kind='quickbooks_verification';
 IF supplied IS DISTINCT FROM x.payload OR rules->>'entity' IS DISTINCT FROM l.payload->>'entity' OR rules->>'realm' IS DISTINCT FROM l.payload->>'realm'
 OR rules->>'provider' IS DISTINCT FROM l.payload->>'provider' OR NOT rules->'treatment_evidence_ids' @> jsonb_build_array(l.payload->'treatment_evidence_id')
 OR NOT rules->'incumbent_user_references' @> jsonb_build_array(l.payload->'incumbent_user_reference')
 OR x.payload->>'state' IS DISTINCT FROM 'found' OR x.payload->>'target_reference' IS NULL OR x.payload->>'incumbent_version' IS NULL
 OR x.payload-ARRAY['state','observed_at','incumbent_version','target_reference'] IS DISTINCT FROM jsonb_build_object('provider',l.payload->'provider','realm',l.payload->'realm','entity',l.payload->'entity','source_reference',l.payload->'source_reference','transaction_date',l.payload->'transaction_date','accounting_period',l.payload->'accounting_period','treatment_evidence_id',l.payload->'treatment_evidence_id')
 OR (x.payload->>'observed_at')::timestamptz>statement_timestamp()
 OR (x.payload->>'observed_at')::timestamptz<statement_timestamp()-make_interval(secs=>(rules->>'max_age_seconds')::integer) THEN RETURN false; END IF;
 RETURN true;
END $$;
CREATE OR REPLACE FUNCTION psl_factory_ledger_resolution_current(rid bigint) RETURNS boolean LANGUAGE plpgsql STABLE AS $$
DECLARE r finance_ledgerresolution; rr finance_ledgerresolutionreview; selected finance_ledgerlineage; m record; x finance_ledgercheck; newest finance_ledgercheck;
 rules jsonb; proposer jsonb; reviewer jsonb; count_members integer; count_cases integer; population bigint[]; actual bigint[]; selected_check finance_ledgercheck;
BEGIN
 SELECT * INTO r FROM finance_ledgerresolution WHERE id=rid;
 SELECT * INTO rr FROM finance_ledgerresolutionreview WHERE resolution_id=rid ORDER BY id DESC LIMIT 1;
 SELECT * INTO selected FROM finance_ledgerlineage WHERE id=r.selected_id;
 SELECT count(*),count(DISTINCT l.case_id),array_agg(mm.lineage_id ORDER BY mm.lineage_id) INTO count_members,count_cases,actual
 FROM finance_ledgerresolutionmember mm JOIN finance_ledgerlineage l ON l.id=mm.lineage_id WHERE mm.resolution_id=rid;
 IF r.id IS NULL OR rr.verdict IS DISTINCT FROM 'confirm' OR count_members<2 OR rr.actor_id=r.actor_id
 OR jsonb_array_length(r.snapshot->'members') IS DISTINCT FROM count_members
 OR EXISTS(SELECT 1 FROM finance_ledgerresolutionmember mm WHERE mm.resolution_id>rid AND mm.lineage_id=ANY(actual)) THEN RETURN false; END IF;
 SELECT array_agg(l.id ORDER BY l.id) INTO population FROM finance_ledgerlineage l JOIN core_case c ON c.id=l.case_id JOIN core_case sc ON sc.id=selected.case_id
 WHERE c.tenant=sc.tenant AND (l.identity=selected.identity OR (l.payload->>'provider'=selected.payload->>'provider' AND l.payload->>'realm'=selected.payload->>'realm'
 AND l.payload->>'target_reference' IN (SELECT selected.payload->>'target_reference' UNION SELECT retired.payload->>'target_reference' FROM finance_ledgerresolutionmember mem JOIN finance_ledgerlineage retired ON retired.id=mem.lineage_id WHERE mem.resolution_id=rid AND mem.disposition='retired')));
 IF population IS DISTINCT FROM actual OR EXISTS(SELECT 1 FROM finance_ledgerlineage WHERE predecessor_id=selected.id) THEN RETURN false; END IF;
 SELECT ck.* INTO selected_check FROM finance_ledgercheck ck JOIN finance_ledgerresolutionmember mem ON mem.verification_id=ck.id WHERE mem.resolution_id=rid AND mem.lineage_id=selected.id AND mem.disposition='selected';
 IF selected_check.id IS NULL OR selected_check.payload->>'target_reference' IS DISTINCT FROM selected.payload->>'target_reference' THEN RETURN false; END IF;
 FOR m IN SELECT mem.*,l.case_id,l.actor_id,l.identity,l.payload,l.predecessor_id FROM finance_ledgerresolutionmember mem JOIN finance_ledgerlineage l ON l.id=mem.lineage_id WHERE mem.resolution_id=rid LOOP
  proposer:=r.snapshot->'authority'->m.case_id::text;reviewer:=rr.authority->m.case_id::text;
  IF proposer IS NULL OR reviewer IS NULL OR proposer->'policy' IS DISTINCT FROM reviewer->'policy'
  OR NOT psl_schedules_policy_current(m.case_id,(proposer->>'policy')::bigint)
  OR NOT EXISTS(SELECT 1 FROM policy_configuration WHERE id=(proposer->>'policy')::bigint AND component='F01.conflict_rules')
  OR NOT psl_schedules_role_current(m.case_id,r.actor_id,proposer->'role')
  OR NOT psl_schedules_role_current(m.case_id,rr.actor_id,reviewer->'role')
  OR NOT psl_schedules_authority_current(m.case_id,proposer->'role') OR NOT psl_schedules_authority_current(m.case_id,reviewer->'role')
  OR NOT psl_schedules_grants(m.case_id,r.actor_id,ARRAY['case.read','finance.read','ledger.read','ledger.resolve'])
  OR NOT psl_schedules_grants(m.case_id,rr.actor_id,ARRAY['case.read','finance.read','ledger.read','ledger.resolve_review']) THEN RETURN false; END IF;
  rules:=psl_schedules_values((proposer->>'policy')::bigint)->0;
  IF rules->>'proposer_id' IS DISTINCT FROM r.actor_id::text OR rules->>'reviewer_id' IS DISTINCT FROM rr.actor_id::text
  OR (count_cases>1 AND rules->'allow_cross_case' IS DISTINCT FROM 'true'::jsonb) OR count_members>(rules->>'max_members')::integer
  OR NOT rules->'allowed_modes' @> jsonb_build_array(r.mode)
  OR rr.created_at<statement_timestamp()-make_interval(secs=>(rules->>'decision_ttl_seconds')::integer) THEN RETURN false; END IF;
  SELECT * INTO x FROM finance_ledgercheck WHERE id=m.verification_id;
  SELECT * INTO newest FROM finance_ledgercheck WHERE lineage_id=m.lineage_id ORDER BY id DESC LIMIT 1;
  IF rr.actor_id IN (m.actor_id,x.actor_id) OR NOT psl_factory_ledger_read_current(x.id) THEN RETURN false; END IF;
  IF newest.id<>x.id AND (m.disposition='retired' OR NOT psl_factory_ledger_read_current(newest.id) OR newest.payload-'observed_at' IS DISTINCT FROM x.payload-'observed_at') THEN RETURN false; END IF;
  IF NOT EXISTS(SELECT 1 FROM jsonb_array_elements(r.snapshot->'members') pin JOIN core_evidence e ON e.id=(SELECT evidence_id FROM finance_ledgerlineage WHERE id=m.lineage_id)
   WHERE pin->>'lineage'=m.lineage_id::text AND pin->>'disposition'=m.disposition AND pin->'proof'->>'check'=x.id::text
   AND EXISTS(SELECT 1 FROM policy_configuration pc WHERE pc.id=(pin->'proof'->>'rule')::bigint AND pc.component='F01.verification_rules' AND psl_schedules_policy_current(m.case_id,pc.id)) AND pin->'proof'->>'evidence'=e.sha256) THEN RETURN false; END IF;
  IF m.payload->>'provider' IS DISTINCT FROM selected.payload->>'provider' OR m.payload->>'realm' IS DISTINCT FROM selected.payload->>'realm' OR m.payload->>'entity' IS DISTINCT FROM selected.payload->>'entity' THEN RETURN false; END IF;
  IF m.disposition='retired' THEN
   IF m.identity<>selected.identity OR m.payload->>'transaction_date' IS DISTINCT FROM selected.payload->>'transaction_date' OR m.payload->>'accounting_period' IS DISTINCT FROM selected.payload->>'accounting_period'
   OR (SELECT sha256 FROM core_evidence WHERE id=(m.payload->>'treatment_evidence_id')::bigint) IS DISTINCT FROM (SELECT sha256 FROM core_evidence WHERE id=(selected.payload->>'treatment_evidence_id')::bigint)
   OR x.payload->>'target_reference' IS DISTINCT FROM selected_check.payload->>'target_reference' OR x.payload->>'incumbent_version' IS DISTINCT FROM selected_check.payload->>'incumbent_version' THEN RETURN false; END IF;
  ELSIF m.lineage_id<>selected.id AND (m.disposition<>'retained' OR m.identity=selected.identity OR x.payload->>'target_reference' IS DISTINCT FROM m.payload->>'target_reference' OR m.payload->>'target_reference'=selected.payload->>'target_reference') THEN RETURN false; END IF;
 END LOOP;
 RETURN true;
END $$;
CREATE OR REPLACE FUNCTION psl_factory_ledger_resolution(lineage_id bigint) RETURNS bigint LANGUAGE plpgsql STABLE AS $$
DECLARE l finance_ledgerlineage; rid bigint;
BEGIN
 SELECT * INTO l FROM finance_ledgerlineage WHERE id=lineage_id;
 SELECT max(mem.resolution_id) INTO rid FROM finance_ledgerresolutionmember mem JOIN finance_ledgerlineage other ON other.id=mem.lineage_id JOIN core_case oc ON oc.id=other.case_id JOIN core_case lc ON lc.id=l.case_id
 WHERE oc.tenant=lc.tenant AND (other.identity=l.identity OR (other.payload->>'provider'=l.payload->>'provider' AND other.payload->>'realm'=l.payload->>'realm' AND other.payload->>'target_reference' IS NOT DISTINCT FROM l.payload->>'target_reference'));
 IF rid IS NOT NULL AND psl_factory_ledger_resolution_current(rid) THEN RETURN rid; END IF;
 RETURN NULL;
END $$;
CREATE OR REPLACE FUNCTION psl_factory_ledger_current(check_id bigint) RETURNS boolean LANGUAGE plpgsql STABLE AS $$
DECLARE x finance_ledgercheck; l finance_ledgerlineage; rid bigint; retired bigint[]; ancestors bigint[]; reviewed_at timestamptz; selected bigint;
BEGIN
 SELECT * INTO x FROM finance_ledgercheck WHERE id=check_id;SELECT * INTO l FROM finance_ledgerlineage WHERE id=x.lineage_id;
 IF l.id IS NULL OR NOT psl_factory_ledger_read_current(x.id) OR x.status<>'candidate'
 OR x.id<>(SELECT max(id) FROM finance_ledgercheck WHERE lineage_id=l.id) OR x.payload->>'target_reference' IS DISTINCT FROM l.payload->>'target_reference' THEN RETURN false; END IF;
 rid:=psl_factory_ledger_resolution(l.id);retired:=ARRAY[]::bigint[];
 IF rid IS NOT NULL THEN
  SELECT array_agg(lineage_id) INTO retired FROM finance_ledgerresolutionmember WHERE resolution_id=rid AND disposition='retired';retired:=coalesce(retired,ARRAY[]::bigint[]);
  SELECT r.selected_id,rr.created_at INTO selected,reviewed_at FROM finance_ledgerresolution r JOIN finance_ledgerresolutionreview rr ON rr.resolution_id=r.id WHERE r.id=rid ORDER BY rr.id DESC LIMIT 1;
  IF x.snapshot->'resolution'->>'resolution' IS DISTINCT FROM rid::text OR x.snapshot->'resolution'->>'review' IS DISTINCT FROM (SELECT max(id)::text FROM finance_ledgerresolutionreview WHERE resolution_id=rid)
  OR x.snapshot->'resolution'->>'selected' IS DISTINCT FROM selected::text OR (x.snapshot->'resolution'->>'reviewed_at')::timestamptz IS DISTINCT FROM reviewed_at
  OR x.snapshot-ARRAY['F01.verification_rules','resolution']<>'{}'::jsonb OR (x.snapshot->'resolution')-ARRAY['resolution','review','selected','reviewed_at']<>'{}'::jsonb
  OR x.created_at<=reviewed_at OR (x.payload->>'observed_at')::timestamptz<=reviewed_at THEN RETURN false; END IF;
 ELSIF x.snapshot-ARRAY['F01.verification_rules']<>'{}'::jsonb THEN RETURN false; END IF;
 IF l.predecessor_id IS NOT NULL AND EXISTS(SELECT 1 FROM policy_configuration p JOIN policy_policystate s ON s.configuration_id=p.id WHERE p.case_id=l.case_id AND p.component='F01.conflict_rules' AND s.state='active') AND (rid IS NULL OR selected<>l.id) THEN RETURN false; END IF;
 IF l.id=ANY(retired) OR EXISTS(SELECT 1 FROM finance_ledgerlineage newer WHERE newer.identity=l.identity AND newer.id>l.id AND NOT newer.id=ANY(retired)) THEN RETURN false; END IF;
 WITH RECURSIVE chain AS (SELECT id,predecessor_id,1 depth FROM finance_ledgerlineage WHERE id=l.predecessor_id UNION ALL SELECT p.id,p.predecessor_id,c.depth+1 FROM finance_ledgerlineage p JOIN chain c ON p.id=c.predecessor_id WHERE c.depth<100) SELECT array_agg(id) INTO ancestors FROM chain;
 IF EXISTS(SELECT 1 FROM finance_ledgerlineage dup WHERE dup.identity=l.identity AND dup.id<>l.id AND NOT dup.id=ANY(coalesce(ancestors,ARRAY[]::bigint[])||retired)) THEN RETURN false; END IF;
 IF EXISTS(SELECT 1 FROM finance_ledgerlineage other JOIN core_case oc ON oc.id=other.case_id JOIN core_case lc ON lc.id=l.case_id WHERE oc.tenant=lc.tenant AND other.identity<>l.identity AND other.payload->>'provider'=l.payload->>'provider' AND other.payload->>'realm'=l.payload->>'realm' AND other.payload->>'target_reference'=l.payload->>'target_reference' AND NOT other.id=ANY(retired)) THEN RETURN false; END IF;
 RETURN true;
END $$;

CREATE OR REPLACE FUNCTION psl_factory_ledger_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE intake_body jsonb; supplied jsonb;
BEGIN
 IF NEW.definition<>'finance-ledger/v1' THEN RETURN NEW; END IF;
 SELECT e.body::jsonb INTO intake_body FROM core_evidence e JOIN core_audit a ON a.case_id=e.case_id AND a.actor_id=e.created_by_id
 WHERE e.id=NEW.source_head_id AND e.case_id=NEW.case_id AND e.kind='agent_private_ledger_intake'
 AND a.action IN ('factory.ledger_intake','factory.ledger_source') AND a.data=jsonb_build_object('evidence_id',e.id,'sha256',e.sha256);
 IF intake_body IS NULL OR intake_body->>'protocol'<>'factory-ledger-intake/v1' OR NOT intake_body ?& ARRAY['protocol','evidence_id','predecessor_id']
 OR intake_body-ARRAY['protocol','evidence_id','predecessor_id']<>'{}'::jsonb OR NEW.invoice_id IS NOT NULL OR NEW.preparation_id IS NOT NULL
 THEN RAISE EXCEPTION 'Exact private supplied incumbent intake required'; END IF;
 SELECT e.body::jsonb INTO supplied FROM core_evidence e WHERE e.id=(intake_body->>'evidence_id')::bigint AND e.case_id=NEW.case_id AND e.kind='ledger_source';
 IF supplied IS NULL THEN RAISE EXCEPTION 'Exact private incumbent source required'; END IF;
 IF NEW.status='verified' AND NOT EXISTS(
 SELECT 1 FROM finance_ledgerlineage l JOIN finance_ledgercheck x ON x.lineage_id=l.id JOIN finance_ledgerdecision r ON r.verification_id=x.id
 JOIN workflows_factoryactivity a ON a.work_id=NEW.id AND a.kind='ACT13'
 JOIN workflows_factoryattempt t ON t.activity_id=a.id AND t.phase='observed'
 JOIN policy_configuration rules ON rules.id=(x.snapshot->>'F01.verification_rules')::bigint
 JOIN policy_registeredreference rv ON rv.case_id=rules.case_id AND rv.ref=rules.envelope->'value'->>'artifact_ref' AND rv.version=(rules.envelope->'value'->>'artifact_version')::integer
 WHERE l.case_id=NEW.case_id AND l.identity=NEW.request->>'identity' AND l.evidence_id=(intake_body->>'evidence_id')::bigint
 AND l.predecessor_id IS NOT DISTINCT FROM (intake_body->>'predecessor_id')::bigint AND l.payload=supplied
 AND x.status='candidate' AND x.id=(SELECT max(id) FROM finance_ledgercheck WHERE lineage_id=l.id)
 AND r.verdict='approve' AND r.id=(SELECT max(id) FROM finance_ledgerdecision WHERE verification_id=x.id)
 AND r.actor_id NOT IN (l.actor_id,x.actor_id)
 AND r.authority-ARRAY['F01.review_authority','D05.role_principal_assignments']='{}'::jsonb
 AND psl_factory_ledger_current(x.id)
 AND EXISTS(SELECT 1 FROM policy_configuration ac JOIN policy_registeredreference av ON av.case_id=ac.case_id AND av.ref=ac.envelope->'value'->>'artifact_ref' AND av.version=(ac.envelope->'value'->>'artifact_version')::integer
 WHERE ac.id=(r.authority->>'F01.review_authority')::bigint AND psl_schedules_policy_current(NEW.case_id,ac.id) AND av.content->'user_ids' @> jsonb_build_array(r.actor_id))
 AND EXISTS(SELECT 1 FROM core_evidence e JOIN core_audit a ON a.case_id=e.case_id AND a.actor_id=e.created_by_id
 WHERE e.id=NEW.source_head_id AND a.data=jsonb_build_object('evidence_id',e.id,'sha256',e.sha256)
 AND psl_schedules_grants(NEW.case_id,e.created_by_id,ARRAY['case.read','finance.read','ledger.read','ledger.private.read','evidence.add'])
 AND ((a.action='factory.ledger_intake' AND psl_schedules_grants(NEW.case_id,e.created_by_id,ARRAY['factory.start'])) OR (a.action='factory.ledger_source' AND psl_schedules_grants(NEW.case_id,e.created_by_id,ARRAY['factory.manage'])))
 )
 AND psl_schedules_policy_current(NEW.case_id,NEW.policy_id)
 AND psl_schedules_policy_current(NEW.case_id,rules.id)
 AND psl_schedules_authority_current(NEW.case_id,r.authority)
 AND psl_schedules_role_current(NEW.case_id,r.actor_id,r.authority)
 AND psl_schedules_grants(NEW.case_id,l.actor_id,ARRAY['case.read','finance.read','ledger.read','ledger.capture'])
 AND psl_schedules_grants(NEW.case_id,x.actor_id,ARRAY['case.read','finance.read','ledger.read','ledger.verify'])
 AND psl_schedules_grants(NEW.case_id,r.actor_id,ARRAY['case.read','finance.read','ledger.read','ledger.review'])
 AND (x.payload->>'observed_at')::timestamptz<=statement_timestamp()
 AND (x.payload->>'observed_at')::timestamptz>=statement_timestamp()-make_interval(secs=>(rv.content->>'max_age_seconds')::integer)
 AND t.result->'verified'='true'::jsonb AND t.result->>'head'=NEW.source_head_id::text
 AND t.result->>'lineage'=l.id::text AND t.result->>'check'=x.id::text AND t.result->>'review'=r.id::text
 AND t.result->'posting_performed'='false'::jsonb AND t.result->'native_authenticity_verified'='false'::jsonb
 AND t.result->'financial_completeness_verified'='false'::jsonb
 ) THEN RAISE EXCEPTION 'Observed exact current independently reviewed incumbent reference required'; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER psl_factory_ledger BEFORE INSERT OR UPDATE ON workflows_factorywork FOR EACH ROW EXECUTE FUNCTION psl_factory_ledger_guard();
"""

REVERSE = r"""-- Structural defense in depth. Python native services retain full business validation.
CREATE OR REPLACE FUNCTION psl_bu_private(wid bigint,uid bigint) RETURNS boolean LANGUAGE plpgsql STABLE AS $$
DECLARE w record; p record; cfg record; v jsonb;
BEGIN
 SELECT * INTO w FROM finance_buwork WHERE id=wid;
 IF NOT FOUND OR NOT psl_schedules_grants(w.case_id,uid,ARRAY['case.read','bu.read','bu.private.read']) THEN RETURN false; END IF;
 IF w.payroll_id IS NOT NULL THEN
  SELECT r.*,q.metadata AS scope,q.case_id INTO p FROM finance_payrollrun r JOIN finance_payrollrequest q ON q.id=r.request_id WHERE r.id=w.payroll_id AND q.case_id=w.case_id;
  IF NOT FOUND OR NOT psl_schedules_grants(w.case_id,uid,ARRAY['payroll.read','payroll.private.read']) THEN RETURN false; END IF;
  SELECT c.* INTO cfg FROM policy_configuration c WHERE c.case_id=w.case_id AND c.component='F16.input_access_rules' AND psl_schedules_policy_current(w.case_id,c.id);
  IF NOT FOUND THEN RETURN false; END IF;
  v=psl_schedules_values(cfg.id)->0;
  RETURN COALESCE(v->'reader_ids' @> to_jsonb(ARRAY[uid]) AND v->'entity'=p.scope->'entity' AND v->'currency'=p.scope->'currency'
   AND v->>'from_period'<=p.scope->>'period' AND v->>'to_period'>=p.scope->>'period',false);
 END IF;
 SELECT c.* INTO cfg FROM policy_configuration c WHERE c.case_id=w.case_id AND c.component='F44.source_rules' AND psl_schedules_policy_current(w.case_id,c.id);
 IF NOT FOUND THEN RETURN false; END IF;
 v=psl_schedules_values(cfg.id)->0;
 RETURN COALESCE(v->'reader_ids' @> to_jsonb(ARRAY[uid]) AND v->'entity'=w.metadata->'scope'->'entity'
  AND v->>'from_period'<=w.metadata->'scope'->>'period' AND v->>'to_period'>=w.metadata->'scope'->>'period',false);
END $$;

CREATE OR REPLACE FUNCTION psl_bu_authority(wid bigint,uid bigint,purpose text,pins jsonb) RETURNS boolean LANGUAGE sql STABLE AS $$
 SELECT EXISTS(SELECT 1 FROM finance_buwork w JOIN policy_configuration c ON c.id=(pins->>'BU.review_authority')::bigint
 WHERE w.id=wid AND c.component='BU.review_authority' AND psl_schedules_policy_current(w.case_id,c.id)
 AND psl_schedules_role_current(w.case_id,uid,pins,'Finance')
 AND EXISTS(SELECT 1 FROM jsonb_array_elements(psl_schedules_values(c.id)->0->'assignments') a
  WHERE a->>'user_id'=uid::text AND a->'purposes' ? purpose)
 AND (purpose='publish' OR psl_schedules_values(c.id)->0->'independent_reviewer'='false'::jsonb OR w.actor_id<>uid));
$$;

CREATE OR REPLACE FUNCTION psl_bu_current(wid bigint,depth integer DEFAULT 0) RETURNS boolean LANGUAGE plpgsql STABLE AS $$
DECLARE w record; p record; v jsonb; rid bigint; inventory jsonb; cmp record;
BEGIN
 IF depth>4 THEN RETURN false; END IF;
 SELECT * INTO w FROM finance_buwork WHERE id=wid;
 IF NOT FOUND OR w.metadata->'accepted' IS DISTINCT FROM 'true'::jsonb OR (w.metadata->>'retain_until')::timestamptz<=statement_timestamp()
  OR NOT psl_schedules_grants(w.case_id,w.actor_id,ARRAY['case.read','bu.read',CASE WHEN w.kind='source' THEN 'bu.capture' ELSE 'bu.'||w.kind END])
  OR EXISTS(SELECT 1 FROM finance_buwork n WHERE n.case_id=w.case_id AND n.reference=w.reference AND n.kind=w.kind AND n.version>w.version AND n.metadata->'accepted'='true'::jsonb)
  OR EXISTS(SELECT 1 FROM jsonb_each(w.metadata->'policy_ids') pin WHERE NOT psl_schedules_policy_current(w.case_id,(pin.value#>>'{}')::bigint))
 THEN RETURN false; END IF;
 IF w.kind<>'source' AND NOT psl_bu_private(wid,w.actor_id) THEN RETURN false; END IF;
 IF w.kind='source' THEN
  v=psl_schedules_values((w.metadata->'policy_ids'->>'F44.source_rules')::bigint)->0;
  IF v->>'owner_id' IS DISTINCT FROM w.actor_id::text OR NOT psl_schedules_role_current(w.case_id,w.actor_id,w.metadata->'owner_authority','Finance')
   OR extract(epoch FROM statement_timestamp()-(w.metadata->>'extracted_at')::timestamptz)>(v->>'max_age_seconds')::numeric THEN RETURN false; END IF;
 END IF;
 IF w.payroll_id IS NOT NULL THEN
  SELECT r.*,q.case_id,q.reference AS request_reference,q.version AS request_version,q.metadata AS request_scope INTO p FROM finance_payrollrun r JOIN finance_payrollrequest q ON q.id=r.request_id WHERE r.id=w.payroll_id AND q.case_id=w.case_id;
  IF NOT FOUND OR p.kind<>'match' OR p.sha256 IS DISTINCT FROM w.metadata->>'payroll_sha256' OR p.retain_until<=statement_timestamp()
   OR EXISTS(SELECT 1 FROM finance_payrollrequest n WHERE n.case_id=w.case_id AND n.reference=p.request_reference AND n.version>p.request_version)
   OR EXISTS(SELECT 1 FROM jsonb_each(p.metadata->'policy_ids') pin WHERE NOT psl_schedules_policy_current(w.case_id,(pin.value#>>'{}')::bigint))
  THEN RETURN false; END IF;
  IF w.kind='staff' THEN
   v=psl_schedules_values((w.metadata->'policy_ids'->>'F21.allocation_rules')::bigint)->0;
   SELECT COALESCE(jsonb_agg(jsonb_build_object('rule_id',r.id,'review_id',rv.id,'verdict',COALESCE(rv.verdict,'pending')) ORDER BY r.id),'[]'::jsonb) INTO inventory
   FROM (SELECT DISTINCT ON (reference) * FROM finance_buwork WHERE case_id=w.case_id AND payroll_id=w.payroll_id AND kind='rule'
    AND metadata->'accepted'='true'::jsonb AND v->'components' ? (payload->>'component') ORDER BY reference,version DESC) r
   LEFT JOIN LATERAL (SELECT id,verdict FROM finance_bureview WHERE work_id=r.id AND purpose='rule' ORDER BY id DESC LIMIT 1) rv ON true;
   IF inventory IS DISTINCT FROM w.metadata->'exception_inventory'
    OR EXISTS(SELECT 1 FROM jsonb_array_elements(inventory) i WHERE i->>'verdict'<>'revoke' AND NOT(w.metadata->'rule_ids' @> jsonb_build_array(i->'rule_id'))) THEN RETURN false; END IF;
  END IF;
 END IF;
 IF w.parent_id IS NOT NULL AND NOT psl_bu_current(w.parent_id,depth+1) THEN RETURN false; END IF;
 FOR rid IN SELECT value::bigint FROM jsonb_array_elements_text(COALESCE(w.metadata->'rule_ids','[]'::jsonb)) LOOP
  IF NOT psl_bu_current(rid,depth+1) THEN RETURN false; END IF;
 END LOOP;
 IF w.metadata->'comparison' IS NOT NULL AND w.metadata->'comparison'<>'null'::jsonb THEN
  SELECT * INTO cmp FROM finance_financerun WHERE id=(w.metadata->'comparison'->>'run_id')::bigint AND case_id=w.case_id AND kind='allocation';
  IF NOT FOUND OR NOT psl_schedules_grants(w.case_id,w.actor_id,ARRAY['finance.calculate']) OR NOT psl_schedules_mapping_current(cmp.parent_id)
   OR cmp.result->>'status'<>'complete' OR cmp.result->'conservation'->(w.metadata->'comparison'->>'metric')->'conserved' IS DISTINCT FROM 'true'::jsonb
   OR EXISTS(SELECT 1 FROM jsonb_each(cmp.snapshot->'policies') pin WHERE NOT psl_schedules_policy_pin_current(w.case_id,pin.key,pin.value))
   OR NOT psl_schedules_finance_review_current((cmp.snapshot->'source_review'->>'id')::bigint)
  THEN RETURN false; END IF;
 END IF;
 RETURN true;
END $$;

CREATE OR REPLACE FUNCTION psl_bu_review(rid bigint,depth integer DEFAULT 0) RETURNS boolean LANGUAGE plpgsql STABLE AS $$
DECLARE r record; w record; parent_review bigint; rule_id bigint;
BEGIN
 IF depth>4 THEN RETURN false; END IF;
 SELECT * INTO r FROM finance_bureview WHERE id=rid;
 IF NOT FOUND THEN RETURN false; END IF;
 SELECT * INTO w FROM finance_buwork WHERE id=r.work_id;
 IF r.verdict<>'approve' OR r.subject_sha256<>w.sha256 OR r.id<>(SELECT max(id) FROM finance_bureview WHERE work_id=w.id AND purpose=r.purpose)
  OR NOT psl_bu_current(w.id) OR NOT psl_bu_private(w.id,r.actor_id)
  OR NOT psl_schedules_grants(w.case_id,r.actor_id,ARRAY['bu.review']) OR NOT psl_bu_authority(w.id,r.actor_id,r.purpose,r.authority) THEN RETURN false; END IF;
 IF w.payroll_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM finance_payrollreview pr JOIN finance_payrollrun p ON p.id=pr.run_id
  WHERE p.id=w.payroll_id AND pr.verdict='approve' AND pr.subject_sha256=p.sha256
   AND pr.id=(SELECT max(id) FROM finance_payrollreview WHERE run_id=p.id)
   AND psl_schedules_grants(w.case_id,pr.actor_id,ARRAY['case.read','payroll.read','payroll.private.read','payroll.review'])
   AND psl_schedules_authority_current(w.case_id,pr.authority)) THEN RETURN false; END IF;
 IF w.parent_id IS NOT NULL THEN
  SELECT rv.id INTO parent_review FROM finance_bureview rv JOIN finance_buwork p ON p.id=rv.work_id WHERE p.id=w.parent_id AND rv.purpose=p.kind ORDER BY rv.id DESC LIMIT 1;
  IF parent_review IS NULL OR NOT psl_bu_review(parent_review,depth+1) THEN RETURN false; END IF;
 END IF;
 FOR rule_id IN SELECT value::bigint FROM jsonb_array_elements_text(COALESCE(w.metadata->'rule_ids','[]'::jsonb)) LOOP
  SELECT id INTO parent_review FROM finance_bureview WHERE work_id=rule_id AND purpose='rule' ORDER BY id DESC LIMIT 1;
  IF parent_review IS NULL OR NOT psl_bu_review(parent_review,depth+1) THEN RETURN false; END IF;
 END LOOP;
 RETURN true;
END $$;

CREATE OR REPLACE FUNCTION psl_minutes_current(wid bigint, head bigint, vid bigint) RETURNS boolean LANGUAGE sql STABLE AS $$
 SELECT EXISTS(
  SELECT 1 FROM workflows_factorywork w JOIN core_evidence e ON e.id=head AND e.case_id=w.case_id
  JOIN core_audit c ON c.case_id=w.case_id AND c.action='factory.minutes_confirmed' AND c.data->>'work'=w.id::text AND c.data->>'head'=e.id::text
  JOIN pmo_meetingversion mv ON mv.id=(c.data->>'meeting_version')::bigint AND mv.created_by_id=c.actor_id
  JOIN pmo_meeting m ON m.id=mv.meeting_id AND m.current_id=mv.id AND m.case_id=w.case_id AND m.reference=w.request->>'reference'
  JOIN pmo_minutesreportbinding b ON b.meeting_id=m.id AND b.version_id=vid
  JOIN documents_version v ON v.id=b.version_id
  JOIN documents_document d ON d.id=v.document_id AND d.current_id=v.id AND d.case_id=w.case_id
  WHERE w.id=wid AND w.definition='pmo-minutes/v1' AND w.source_head_id=head
   AND mv.evidence_id=(e.body::jsonb->>'evidence_id')::bigint
   AND (e.body::jsonb->'meeting_version_id'='null'::jsonb AND mv.number=1 OR EXISTS(
    SELECT 1 FROM pmo_meetingversion predecessor WHERE predecessor.id=(e.body::jsonb->>'meeting_version_id')::bigint
     AND predecessor.meeting_id=m.id AND predecessor.number+1=mv.number))
   AND mv.purpose=c.data->'fields'->>'purpose' AND mv.summary=c.data->'fields'->>'summary'
   AND mv.decisions=c.data->'fields'->'decisions' AND mv.participant_ids=c.data->'fields'->'participant_ids'
   AND v.template_id=(e.body::jsonb->>'template_id')::bigint AND v.audience=e.body::jsonb->>'audience'
   AND psl_schedules_grants(w.case_id,c.actor_id,ARRAY['case.read','meeting.read','meeting.record'])
   AND EXISTS(SELECT 1 FROM core_audit intake WHERE intake.case_id=w.case_id AND intake.actor_id=e.created_by_id
    AND intake.data=jsonb_build_object('evidence_id',e.id,'sha256',e.sha256)
    AND (intake.action='factory.minutes_intake' AND psl_schedules_grants(w.case_id,e.created_by_id,ARRAY['case.read','meeting.read','factory.start'])
      OR intake.action='factory.minutes_source' AND psl_schedules_grants(w.case_id,e.created_by_id,ARRAY['case.read','meeting.read','factory.manage'])))
   AND b.manifest=jsonb_build_object('meeting_version',m.current_id,'actions',COALESCE((SELECT jsonb_agg(jsonb_build_array(ai.id,ai.current_id) ORDER BY ai.id) FROM pmo_meetingactionlink link JOIN pmo_actionitem ai ON ai.id=link.item_id WHERE link.meeting_id=m.id),'[]'::jsonb))
   AND EXISTS(SELECT 1 FROM workflows_factoryactivity fa JOIN workflows_factoryattempt a ON a.activity_id=fa.id
    WHERE fa.work_id=w.id AND fa.kind='ACT09' AND a.phase='observed' AND a.result->>'head'=e.id::text AND a.result->>'document_version'=v.id::text)
 );
$$;

CREATE OR REPLACE FUNCTION psl_escalation_json(body text) RETURNS jsonb LANGUAGE plpgsql IMMUTABLE AS $$
BEGIN RETURN body::jsonb; EXCEPTION WHEN invalid_text_representation THEN RETURN NULL; END $$;
CREATE OR REPLACE FUNCTION psl_escalation_intake(eid bigint) RETURNS jsonb LANGUAGE plpgsql STABLE AS $$
DECLARE body jsonb; raw_body text; source_kind text; key text;
BEGIN
 SELECT e.kind,e.body INTO source_kind,raw_body FROM core_evidence e WHERE e.id=eid;
 IF source_kind IS DISTINCT FROM 'agent_private_escalation_intake' THEN RETURN NULL; END IF;
 body:=psl_escalation_json(raw_body);
 IF jsonb_typeof(body) IS DISTINCT FROM 'object' THEN RETURN NULL; END IF;
 IF body->>'protocol' IS DISTINCT FROM 'factory-escalation-intake/v1' OR (body-ARRAY['protocol','request_id','profile_id','template_id'])<>'{}'::jsonb OR NOT body ?& ARRAY['protocol','request_id','profile_id','template_id'] THEN RETURN NULL; END IF;
 FOREACH key IN ARRAY ARRAY['request_id','profile_id','template_id'] LOOP
  IF key='template_id' AND body->key='null'::jsonb THEN CONTINUE; END IF;
  IF jsonb_typeof(body->key) IS DISTINCT FROM 'number' OR (body->>key)!~'^[1-9][0-9]{0,18}$' THEN RETURN NULL; END IF;
  IF (body->>key)::numeric>9223372036854775807 THEN RETURN NULL; END IF;
 END LOOP;
 RETURN body;
END $$;
CREATE OR REPLACE FUNCTION psl_escalation_bundle(c uuid,p bigint,u bigint) RETURNS boolean LANGUAGE sql STABLE AS $$
 WITH roles AS (SELECT rr.content v FROM policy_configuration cfg JOIN policy_registeredreference rr
 ON rr.case_id=cfg.case_id AND (cfg.envelope->'value') ? rr.ref AND rr.version=1
 WHERE cfg.id=p AND cfg.case_id=c AND rr.content->>'user_id'=u::text)
 SELECT CASE WHEN (SELECT count(*) FROM roles)<=1 THEN true
 WHEN NOT EXISTS(SELECT 1 FROM roles WHERE NOT v ? 'eligibility') THEN
 NOT EXISTS(SELECT 1 FROM roles WHERE (v->'eligibility'->>'valid_from')::timestamptz>statement_timestamp() OR (v->'eligibility'->>'valid_until')::timestamptz<=statement_timestamp())
 ELSE (SELECT synthetic FROM core_case WHERE id=c) END;
$$;

CREATE OR REPLACE FUNCTION psl_escalation_grants(c uuid,u bigint,actions text[]) RETURNS boolean LANGUAGE sql STABLE AS $$
 SELECT EXISTS(SELECT 1 FROM auth_user WHERE id=u AND is_active) AND NOT EXISTS(
 SELECT 1 FROM unnest(actions) a WHERE NOT EXISTS(SELECT 1 FROM identity_grant g WHERE g.case_id=c AND g.user_id=u AND g.action=a AND g.active));
$$;
CREATE OR REPLACE FUNCTION psl_escalation_policy(c uuid,p bigint,component_arg text) RETURNS boolean LANGUAGE sql STABLE AS $$
 SELECT EXISTS(SELECT 1 FROM policy_configuration cfg WHERE cfg.id=p AND cfg.case_id=c AND cfg.component=component_arg
 AND (SELECT state FROM policy_policystate WHERE configuration_id=cfg.id ORDER BY id DESC LIMIT 1)='active'
 AND (cfg.envelope->>'effective_from')::timestamptz<=statement_timestamp()
 AND (cfg.envelope->>'effective_until' IS NULL OR (cfg.envelope->>'effective_until')::timestamptz>statement_timestamp()));
$$;
CREATE OR REPLACE FUNCTION psl_escalation_authority(c uuid,u bigint,role_name text,delegated boolean,pins jsonb) RETURNS boolean LANGUAGE sql STABLE AS $$
 SELECT psl_escalation_grants(c,u,ARRAY[]::text[]) AND EXISTS(
 SELECT 1 FROM policy_configuration pc WHERE pc.id=(pins->>'D05.role_principal_assignments')::bigint
 AND psl_escalation_policy(c,pc.id,'D05.role_principal_assignments')
 AND pins=jsonb_build_object('D05.role_principal_assignments',pc.id) || CASE WHEN delegated THEN jsonb_build_object('D05.delegation_rules',(pins->>'D05.delegation_rules')::bigint) ELSE '{}'::jsonb END AND (
 (NOT delegated AND psl_escalation_bundle(c,pc.id,u) AND EXISTS(SELECT 1 FROM policy_registeredreference rr WHERE rr.case_id=c AND (pc.envelope->'value') ? rr.ref AND rr.version=1
  AND rr.content->>'role'=role_name AND rr.content->>'user_id'=u::text))
 OR (delegated AND EXISTS(SELECT 1 FROM policy_configuration dc JOIN policy_registeredreference dr ON dr.case_id=c AND (dc.envelope->'value') ? dr.ref AND dr.version=1
  JOIN policy_registeredreference rr ON rr.case_id=c AND (pc.envelope->'value') ? rr.ref AND rr.version=1
  WHERE dc.id=(pins->>'D05.delegation_rules')::bigint AND psl_escalation_policy(c,dc.id,'D05.delegation_rules')
  AND dr.content->>'role'=role_name AND dr.content->>'delegate_id'=u::text AND NOT dr.content ? 'decision_scope'
  AND rr.content->>'role'=role_name AND rr.content->>'user_id'=dr.content->>'principal_id'
  AND psl_escalation_grants(c,(dr.content->>'principal_id')::bigint,ARRAY[]::text[])
  AND psl_escalation_bundle(c,pc.id,(dr.content->>'principal_id')::bigint) AND psl_escalation_bundle(c,pc.id,u)
  AND (CASE WHEN dr.content ? 'delegate_eligibility' THEN
    (dr.content->'delegate_eligibility'->>'valid_from')::timestamptz<=statement_timestamp() AND (dr.content->'delegate_eligibility'->>'valid_until')::timestamptz>statement_timestamp()
    AND (SELECT array_agg(x ORDER BY x) FROM jsonb_array_elements_text(dr.content->'delegate_eligibility'->'roles') x)=
     (SELECT array_agg(x ORDER BY x) FROM (SELECT role_name x UNION SELECT ar.content->>'role' FROM policy_registeredreference ar WHERE ar.case_id=c AND ar.version=1 AND (pc.envelope->'value') ? ar.ref AND ar.content->>'user_id'=u::text) bundle)
   ELSE (SELECT synthetic FROM core_case WHERE id=c) OR NOT EXISTS(SELECT 1 FROM policy_registeredreference ar WHERE ar.case_id=c AND ar.version=1 AND (pc.envelope->'value') ? ar.ref AND ar.content->>'user_id'=u::text AND ar.content->>'role'<>role_name) END)
  AND (dr.content->>'valid_from')::timestamptz<=statement_timestamp() AND (dr.content->>'valid_until')::timestamptz>statement_timestamp()))));
$$;
CREATE OR REPLACE FUNCTION psl_escalation_document(wid bigint,vid bigint,rid bigint,publisher_id_arg bigint,policy_id_arg bigint,source_id_arg bigint,recipient_ids_arg jsonb,pins jsonb) RETURNS boolean LANGUAGE sql STABLE AS $$
 SELECT EXISTS(
 SELECT 1 FROM workflows_factorywork w JOIN core_evidence e ON e.id=source_id_arg
 JOIN pmo_escalationrequest r ON r.id=(psl_escalation_intake(e.id)->>'request_id')::bigint
 JOIN pmo_escalationprofile ep ON ep.id=r.profile_id JOIN pmo_issuestate ist ON ist.id=ep.state_id JOIN pmo_issue i ON i.id=ist.issue_id
 JOIN pmo_escalationdocumentbinding b ON b.request_id=r.id AND b.version_id=vid
 JOIN documents_version v ON v.id=b.version_id JOIN documents_document doc ON doc.id=v.document_id JOIN documents_template t ON t.id=v.template_id
 JOIN policy_configuration pc ON pc.id=policy_id_arg JOIN policy_registeredreference cfg ON cfg.case_id=pc.case_id
  AND cfg.ref=pc.envelope->'value'->>'artifact_ref' AND cfg.version=(pc.envelope->'value'->>'artifact_version')::integer AND cfg.sha256=pc.envelope->'value'->>'sha256'
 JOIN policy_configuration rc ON rc.id=(pins->>'D11.recipient_grant_refs')::bigint
 JOIN policy_configuration sc ON sc.id=(pins->>'D11.template_storage_retention_rules')::bigint
 JOIN policy_registeredreference store ON store.case_id=sc.case_id AND store.ref=sc.envelope->'value'->>'artifact_ref'
  AND store.version=(sc.envelope->'value'->>'artifact_version')::integer AND store.sha256=sc.envelope->'value'->>'sha256'
 WHERE w.id=wid AND w.definition='pmo-escalation/v1' AND w.policy_id=policy_id_arg AND w.source_head_id=e.id
 AND e.case_id=w.case_id AND i.case_id=w.case_id AND doc.case_id=w.case_id AND t.case_id=w.case_id
 AND i.id=(w.request->>'issue')::bigint AND i.current_id=ist.id AND ep.id=(psl_escalation_intake(e.id)->>'profile_id')::bigint
 AND ep.id=(SELECT max(p.id) FROM pmo_escalationprofile p JOIN pmo_issuestate s ON s.id=p.state_id WHERE s.issue_id=i.id)
 AND r.direction=w.request->>'direction' AND r.target=w.request->>'target'
 AND v.template_id=(psl_escalation_intake(e.id)->>'template_id')::bigint AND doc.current_id=v.id
 AND v.audience=CASE WHEN r.target='Client' THEN 'client' ELSE 'internal' END
 AND psl_escalation_policy(w.case_id,policy_id_arg,'OPS.factory_escalation_execution') AND cfg.content->'enabled'='true'::jsonb
 AND cfg.content->>'definition'=w.definition AND cfg.content->>'executor_id'=publisher_id_arg::text
 AND psl_escalation_grants(w.case_id,publisher_id_arg,ARRAY['case.read','issue.read','factory.execute','document.publish'])
 AND psl_escalation_grants(w.case_id,(cfg.content->>'preparer_id')::bigint,ARRAY['case.read','issue.read','factory.execute','issue.escalate','document.draft'])
 AND psl_escalation_grants(w.case_id,e.created_by_id,ARRAY['case.read','issue.read','evidence.add'])
 AND EXISTS(SELECT 1 FROM core_audit ia WHERE ia.case_id=w.case_id AND ia.actor_id=e.created_by_id AND ia.data=jsonb_build_object('evidence_id',e.id,'sha256',e.sha256)
  AND ((ia.action='factory.escalation_intake' AND psl_escalation_grants(w.case_id,e.created_by_id,ARRAY['factory.start'])) OR (ia.action='factory.escalation_source' AND psl_escalation_grants(w.case_id,e.created_by_id,ARRAY['factory.manage']))))
 AND ((r.target<>'Client' AND b.decision_id IS NULL) OR EXISTS(SELECT 1 FROM pmo_escalationdecision d WHERE d.id=b.decision_id AND d.request_id=r.id
  AND d.id=(SELECT max(id) FROM pmo_escalationdecision WHERE request_id=r.id) AND d.verdict='approve' AND d.role IN ('PMO Lead','Head of PMO')
  AND psl_escalation_grants(w.case_id,d.actor_id,ARRAY['issue.escalation_decide']) AND psl_escalation_authority(w.case_id,d.actor_id,d.role,d.delegated,d.authority)))
 AND ((rid IS NULL AND v.audience<>'client' AND t.definition->'internal_review_required'='false'::jsonb AND NOT EXISTS(SELECT 1 FROM documents_controlledreview WHERE version_id=v.id))
 OR EXISTS(SELECT 1 FROM documents_controlledreview rv WHERE rv.id=rid AND rv.version_id=v.id AND rv.id=(SELECT max(id) FROM documents_controlledreview WHERE version_id=v.id)
  AND rv.verdict='approve' AND rv.payload_sha256=v.payload_sha256 AND psl_escalation_grants(w.case_id,rv.actor_id,ARRAY['document.review_controlled'])
  AND psl_escalation_authority(w.case_id,rv.actor_id,'PMO Lead',rv.delegated,rv.authority)))
 AND psl_escalation_policy(w.case_id,rc.id,'D11.recipient_grant_refs') AND psl_escalation_policy(w.case_id,sc.id,'D11.template_storage_retention_rules')
 AND store.content->'template_ids' @> jsonb_build_array(t.id) AND jsonb_array_length(recipient_ids_arg)>0
 AND recipient_ids_arg=(SELECT jsonb_agg(u ORDER BY u) FROM (SELECT DISTINCT (rr.content->>'user_id')::bigint u FROM policy_registeredreference rr
  WHERE rr.case_id=w.case_id AND (rc.envelope->'value') ? rr.ref AND rr.version=1 AND rr.content->>'audience'=v.audience) selected)
 AND NOT EXISTS(SELECT 1 FROM jsonb_array_elements_text(recipient_ids_arg) recipient WHERE NOT psl_escalation_grants(w.case_id,recipient::bigint,ARRAY['document.receive:'||v.audience]))
 AND (r.target='Client' OR EXISTS(SELECT 1 FROM policy_configuration ap JOIN policy_registeredreference ar ON ar.case_id=ap.case_id AND (ap.envelope->'value') ? ar.ref AND ar.version=1
  WHERE ap.id=(pins->>'D05.role_principal_assignments')::bigint AND psl_escalation_policy(w.case_id,ap.id,'D05.role_principal_assignments')
  AND ar.content->>'role'=r.target AND recipient_ids_arg @> jsonb_build_array((ar.content->>'user_id')::bigint)))
 AND EXISTS(SELECT 1 FROM workflows_factoryactivity fa JOIN workflows_factoryattempt a ON a.activity_id=fa.id
  WHERE fa.work_id=w.id AND fa.kind='ACT09' AND a.phase='observed' AND a.result->>'head'=e.id::text AND a.result->>'document_version'=v.id::text AND a.result->>'request'=r.id::text));
$$;

CREATE OR REPLACE FUNCTION psl_reporting_grants(cid uuid, uid bigint, actions text[]) RETURNS boolean LANGUAGE sql STABLE AS $$
 SELECT EXISTS(SELECT 1 FROM auth_user WHERE id=uid AND is_active)
 AND NOT EXISTS(SELECT 1 FROM unnest(actions) required(action) WHERE NOT EXISTS(
  SELECT 1 FROM identity_grant g WHERE g.case_id=cid AND g.user_id=uid AND g.action=required.action AND g.active));
$$;
CREATE OR REPLACE FUNCTION psl_reporting_policy(cid uuid,pid bigint) RETURNS boolean LANGUAGE sql STABLE AS $$
 SELECT EXISTS(SELECT 1 FROM policy_configuration p WHERE p.id=pid AND p.case_id=cid
 AND (SELECT state FROM policy_policystate WHERE configuration_id=p.id ORDER BY id DESC LIMIT 1)='active'
 AND NOT EXISTS(SELECT 1 FROM policy_configuration n WHERE n.case_id=cid AND n.component=p.component AND n.revision>p.revision
  AND (SELECT state FROM policy_policystate WHERE configuration_id=n.id ORDER BY id DESC LIMIT 1) IN ('active','revoked','superseded'))
 AND (p.envelope->>'effective_from')::timestamptz<=statement_timestamp()
 AND (p.envelope->>'effective_until' IS NULL OR (p.envelope->>'effective_until')::timestamptz>statement_timestamp())
 AND NOT EXISTS(SELECT 1 FROM policy_scopeapplication app JOIN policy_scopeversion src ON src.id=app.source_id
  JOIN policy_configuration origin ON origin.id=src.configuration_id WHERE app.configuration_id=p.id
  AND ((SELECT state FROM policy_scopestate WHERE source_id=src.id ORDER BY id DESC LIMIT 1) IS DISTINCT FROM 'active'
   OR (SELECT state FROM policy_policystate WHERE configuration_id=origin.id ORDER BY id DESC LIMIT 1) IS DISTINCT FROM 'validated'
   OR (origin.envelope->>'effective_from')::timestamptz>statement_timestamp()
   OR (origin.envelope->>'effective_until' IS NOT NULL AND (origin.envelope->>'effective_until')::timestamptz<=statement_timestamp())
   OR NOT psl_reporting_grants(origin.case_id,(SELECT actor_id FROM policy_scopestate WHERE source_id=src.id AND state='active' ORDER BY id DESC LIMIT 1),ARRAY['case.read','policy.activate'])
   OR EXISTS(SELECT 1 FROM policy_scopeversion n JOIN policy_configuration nc ON nc.id=n.configuration_id
    WHERE nc.case_id=origin.case_id AND nc.component=origin.component AND n.kind=src.kind AND n.ref=src.ref AND n.revision>src.revision
     AND EXISTS(SELECT 1 FROM policy_scopestate ns WHERE ns.source_id=n.id AND ns.state IN ('active','revoked'))))));
$$;
CREATE OR REPLACE FUNCTION psl_reporting_refs(pid bigint) RETURNS SETOF jsonb LANGUAGE sql STABLE AS $$
 SELECT r.content FROM policy_configuration p JOIN policy_registeredreference r ON r.case_id=p.case_id
 WHERE p.id=pid AND CASE jsonb_typeof(p.envelope->'value')
  WHEN 'object' THEN r.ref=p.envelope->'value'->>'artifact_ref' AND r.version=(p.envelope->'value'->>'artifact_version')::integer AND r.sha256=p.envelope->'value'->>'sha256'
  WHEN 'array' THEN p.envelope->'value'?r.ref AND r.version=1
  WHEN 'string' THEN to_jsonb(r.ref)=p.envelope->'value' AND r.version=1 ELSE false END;
$$;
CREATE OR REPLACE FUNCTION psl_reporting_role(cid uuid,uid bigint,pid bigint,role_name text) RETURNS boolean LANGUAGE sql STABLE AS $$
 WITH records AS (SELECT value FROM psl_reporting_refs(pid) value WHERE value->>'user_id'=uid::text),
 roles AS (SELECT COALESCE(jsonb_agg(DISTINCT value->>'role'),'[]'::jsonb) names FROM records)
 SELECT psl_reporting_policy(cid,pid) AND EXISTS(SELECT 1 FROM auth_user WHERE id=uid AND is_active)
 AND EXISTS(SELECT 1 FROM records WHERE value->>'role'=role_name)
 AND ((SELECT jsonb_array_length(names) FROM roles)=1 OR (EXISTS(SELECT 1 FROM core_case WHERE id=cid AND synthetic) AND EXISTS(SELECT 1 FROM records WHERE NOT(value?'eligibility')))
 OR NOT EXISTS(SELECT 1 FROM records,roles WHERE NOT(value?'eligibility')
  OR (value->'eligibility'->'roles') IS NULL OR NOT(value->'eligibility'->'roles' @> roles.names AND value->'eligibility'->'roles' <@ roles.names)
  OR NOT((value->'eligibility'->>'valid_from')::timestamptz<=statement_timestamp() AND (value->'eligibility'->>'valid_until')::timestamptz>statement_timestamp())));
$$;
CREATE OR REPLACE FUNCTION psl_reporting_review(cid uuid,rid bigint) RETURNS boolean LANGUAGE sql STABLE AS $$
 SELECT EXISTS(SELECT 1 FROM documents_controlledreview rv JOIN documents_version v ON v.id=rv.version_id
 JOIN documents_document d ON d.id=v.document_id
 JOIN policy_configuration assignment ON assignment.id=(rv.authority->>'D05.role_principal_assignments')::bigint
 WHERE rv.id=rid AND d.case_id=cid AND d.current_id=v.id AND rv.verdict='approve'
 AND rv.payload_sha256=v.payload_sha256
 AND rv.id=(SELECT max(id) FROM documents_controlledreview WHERE version_id=v.id)
 AND assignment.component='D05.role_principal_assignments' AND psl_reporting_policy(cid,assignment.id)
 AND psl_reporting_grants(cid,rv.actor_id,ARRAY['document.review_controlled'])
 AND ((NOT rv.delegated AND rv.authority=jsonb_build_object('D05.role_principal_assignments',assignment.id)
  AND psl_reporting_role(cid,rv.actor_id,assignment.id,'PMO Lead'))
 OR (rv.delegated AND EXISTS(SELECT 1 FROM policy_configuration delegation, LATERAL psl_reporting_refs(delegation.id) entry
  WHERE delegation.id=(rv.authority->>'D05.delegation_rules')::bigint AND delegation.component='D05.delegation_rules'
   AND psl_reporting_policy(cid,delegation.id)
   AND rv.authority=jsonb_build_object('D05.role_principal_assignments',assignment.id,'D05.delegation_rules',delegation.id)
   AND entry->>'role'='PMO Lead' AND entry->>'delegate_id'=rv.actor_id::text AND NOT(entry?'decision_scope')
   AND (entry->>'valid_from')::timestamptz<=statement_timestamp() AND (entry->>'valid_until')::timestamptz>statement_timestamp()
   AND psl_reporting_role(cid,(entry->>'principal_id')::bigint,assignment.id,'PMO Lead')
   AND (NOT EXISTS(SELECT 1 FROM psl_reporting_refs(assignment.id) own WHERE own->>'user_id'=rv.actor_id::text)
    OR EXISTS(SELECT 1 FROM psl_reporting_refs(assignment.id) own WHERE own->>'user_id'=rv.actor_id::text AND psl_reporting_role(cid,rv.actor_id,assignment.id,own->>'role')))
   AND (CASE WHEN entry?'delegate_eligibility' THEN
     (entry->'delegate_eligibility'->>'valid_from')::timestamptz<=statement_timestamp()
     AND (entry->'delegate_eligibility'->>'valid_until')::timestamptz>statement_timestamp()
     AND (SELECT COALESCE(jsonb_agg(DISTINCT role_name),'[]'::jsonb) FROM
       (SELECT 'PMO Lead' role_name UNION SELECT own->>'role' FROM psl_reporting_refs(assignment.id) own WHERE own->>'user_id'=rv.actor_id::text) roles)
       @> (entry->'delegate_eligibility'->'roles')
     AND entry->'delegate_eligibility'->'roles' @> (SELECT COALESCE(jsonb_agg(DISTINCT role_name),'[]'::jsonb) FROM
       (SELECT 'PMO Lead' role_name UNION SELECT own->>'role' FROM psl_reporting_refs(assignment.id) own WHERE own->>'user_id'=rv.actor_id::text) roles)
    ELSE EXISTS(SELECT 1 FROM core_case WHERE id=cid AND synthetic)
     OR NOT EXISTS(SELECT 1 FROM psl_reporting_refs(assignment.id) own WHERE own->>'user_id'=rv.actor_id::text AND own->>'role'<>'PMO Lead') END)))));
$$;
CREATE OR REPLACE FUNCTION psl_reporting_principals(wid bigint,vid bigint,publisher bigint) RETURNS boolean LANGUAGE sql STABLE AS $$
 SELECT EXISTS(SELECT 1 FROM workflows_factorywork w JOIN documents_version v ON v.id=vid
 JOIN policy_configuration p ON p.id=w.policy_id, LATERAL psl_reporting_refs(p.id) cfg
 WHERE w.id=wid AND p.component='OPS.factory_reporting_execution' AND psl_reporting_policy(w.case_id,p.id)
 AND cfg->>'executor_id'=publisher::text AND cfg->>'preparer_id'=v.created_by_id::text
 AND psl_reporting_grants(w.case_id,publisher,ARRAY['case.read','report.read','factory.execute','document.publish'])
 AND psl_reporting_grants(w.case_id,v.created_by_id,ARRAY['case.read','report.read','factory.execute','report.draft','document.draft','document.request_review']));
$$;
CREATE OR REPLACE FUNCTION psl_reporting_distribution(cid uuid,vid bigint,policies jsonb,recipients jsonb,retention integer) RETURNS boolean LANGUAGE sql STABLE AS $$
 SELECT jsonb_array_length(recipients)>0
 AND policies ?& ARRAY['D11.template_storage_retention_rules','D11.recipient_grant_refs']
 AND policies-ARRAY['D11.template_storage_retention_rules','D11.recipient_grant_refs']='{}'::jsonb
 AND NOT EXISTS(SELECT 1 FROM jsonb_each_text(policies) pin WHERE NOT EXISTS(
  SELECT 1 FROM policy_configuration p WHERE p.id=pin.value::bigint AND p.component=pin.key AND psl_reporting_policy(cid,p.id)))
 AND recipients=COALESCE((SELECT jsonb_agg(DISTINCT (r->>'user_id')::bigint ORDER BY (r->>'user_id')::bigint)
 FROM psl_reporting_refs((policies->>'D11.recipient_grant_refs')::bigint) r WHERE r->>'audience'='client'),'[]'::jsonb)
 AND NOT EXISTS(SELECT 1 FROM jsonb_array_elements_text(recipients) r WHERE NOT psl_reporting_grants(cid,r::bigint,ARRAY['document.receive:client']))
 AND EXISTS(SELECT 1 FROM psl_reporting_refs((policies->>'D11.template_storage_retention_rules')::bigint) storage
  JOIN documents_version v ON v.id=vid WHERE storage->>'retention_days'=retention::text AND storage->'template_ids' @> jsonb_build_array(v.template_id));
$$;
CREATE OR REPLACE FUNCTION psl_reporting_heads(cid uuid,m jsonb,s timestamptz,t timestamptz) RETURNS boolean LANGUAGE sql STABLE AS $$
 SELECT m->>'source_mode'='weekly_client_facts/v1'
 AND m-ARRAY['source_mode','meetings','actions','milestones','issues','changes','client_content']='{}'::jsonb
 AND m->'meetings'=COALESCE((SELECT jsonb_agg(jsonb_build_array(x.id,x.current_id) ORDER BY x.id) FROM pmo_meeting x JOIN pmo_meetingversion v ON v.id=x.current_id WHERE x.case_id=cid AND v.occurred_at>=s AND v.occurred_at<t),'[]'::jsonb)
 AND m->'actions'=COALESCE((SELECT jsonb_agg(jsonb_build_array(id,current_id) ORDER BY id) FROM pmo_actionitem WHERE case_id=cid),'[]'::jsonb)
 AND m->'milestones'=COALESCE((SELECT jsonb_agg(id ORDER BY id) FROM pmo_milestone WHERE case_id=cid AND completed_at>=s AND completed_at<t),'[]'::jsonb)
 AND m->'issues'=COALESCE((SELECT jsonb_agg(jsonb_build_array(id,current_id) ORDER BY id) FROM pmo_issue WHERE case_id=cid),'[]'::jsonb)
 AND m->'changes'=COALESCE((SELECT jsonb_agg(jsonb_build_array(id,current_id) ORDER BY id) FROM pmo_changerequest WHERE case_id=cid),'[]'::jsonb);
$$;
CREATE OR REPLACE FUNCTION psl_reporting_document(wid bigint,eid bigint,vid bigint) RETURNS boolean LANGUAGE sql STABLE AS $$
 SELECT EXISTS(SELECT 1 FROM workflows_factorywork w JOIN core_evidence e ON e.id=eid AND e.case_id=w.case_id
 JOIN documents_version v ON v.id=vid JOIN documents_template template ON template.id=v.template_id JOIN documents_document d ON d.id=v.document_id AND d.case_id=w.case_id AND d.current_id=v.id
 JOIN pmo_minutesreportbinding b ON b.version_id=v.id JOIN pmo_periodreport r ON r.id=b.report_id AND r.case_id=w.case_id
 JOIN core_evidence projection ON projection.id=(v.source_manifest->0->>'id')::bigint AND projection.case_id=w.case_id
 JOIN core_evidence content ON content.id=(e.body::jsonb->'inputs'->>'content_id')::bigint AND content.case_id=w.case_id AND content.kind='agent_private_report_content'
 WHERE w.id=wid AND w.definition='pmo-weekly-report/v1' AND e.kind='agent_private_reporting_intake'
 AND psl_reporting_grants(w.case_id,e.created_by_id,ARRAY['case.read','report.read','evidence.add'])
 AND EXISTS(SELECT 1 FROM core_audit provenance WHERE provenance.case_id=w.case_id AND provenance.actor_id=e.created_by_id
  AND provenance.data=jsonb_build_object('evidence_id',e.id,'sha256',e.sha256)
  AND ((provenance.action='factory.reporting_intake' AND psl_reporting_grants(w.case_id,e.created_by_id,ARRAY['factory.start']))
   OR (provenance.action='factory.reporting_source' AND psl_reporting_grants(w.case_id,e.created_by_id,ARRAY['factory.manage']))))
 AND v.baseline_manifest=COALESCE((SELECT jsonb_build_object('plan_id',plan_id,'costing_id',costing_id,'sow_id',sow_id,'signed_id',signed_id) FROM pmo_baseline WHERE case_id=w.case_id),'{}'::jsonb)
 AND e.id=w.source_head_id AND v.audience='client' AND r.kind='weekly_client' AND r.audience='client' AND r.document_id=d.id
 AND r.start_at=(w.request->>'start_at')::timestamptz AND r.end_at=(w.request->>'end_at')::timestamptz
 AND v.template_id=(e.body::jsonb->'inputs'->>'template_id')::bigint AND b.manifest=e.body::jsonb->'manifest'
 AND psl_reporting_heads(w.case_id,b.manifest,r.start_at,r.end_at)
 AND b.manifest->'client_content'=jsonb_build_object('id',content.id,'sha256',content.sha256)
 AND v.source_manifest=jsonb_build_array(jsonb_build_object('id',projection.id,'version',projection.version,'sha256',projection.sha256))
 AND jsonb_array_length(v.source_manifest)=1 AND projection.kind='ops_client_report_projection'
 AND projection.source='psl:weekly-client-projection:'||r.id::text AND projection.created_by_id=v.created_by_id
 AND NOT EXISTS(SELECT 1 FROM jsonb_each(v.fields) field WHERE field.value->'evidence_ids' IS DISTINCT FROM jsonb_build_array(projection.id))
 AND template.definition->>'document_type'='status_report'
 AND template.definition->'required_fields' @> '["executive_summary","status","risks","timeline","next_steps"]'::jsonb
 AND template.definition->'audience_fields'->'client' @> '["executive_summary","status","risks","timeline","next_steps"]'::jsonb
 AND jsonb_array_length(template.definition->'audience_fields'->'client')=5
 AND v.payload->>'type'='status_report' AND jsonb_array_length(v.payload->'sections')=5
 AND (SELECT jsonb_agg(section->>'heading' ORDER BY section->>'heading') FROM jsonb_array_elements(v.payload->'sections') section)='["executive_summary","next_steps","risks","status","timeline"]'::jsonb
 AND content.body::jsonb->>'protocol'='pmo-weekly-client-content/v1'
 AND (content.body::jsonb->'sections')-ARRAY['status','risks','timeline','next_steps']='{}'::jsonb
 AND NOT EXISTS(SELECT 1 FROM unnest(ARRAY['status','risks','timeline','next_steps']) theme(k)
  WHERE NOT(content.body::jsonb->'sections'?theme.k) OR length(trim(content.body::jsonb->'sections'->theme.k->>'text')) NOT BETWEEN 1 AND 10000
   OR jsonb_array_length(content.body::jsonb->'sections'->theme.k->'evidence_ids') NOT BETWEEN 1 AND 18
   OR EXISTS(SELECT 1 FROM jsonb_array_elements_text(content.body::jsonb->'sections'->theme.k->'evidence_ids') citation
    WHERE NOT EXISTS(SELECT 1 FROM core_evidence ce WHERE ce.id=citation::bigint AND ce.case_id=w.case_id
     AND ce.kind NOT IN ('ledger_source','quickbooks_verification','ledger_resolution','ledger_resolution_review','approval_source','approval_observation','migration_proof','d03_source','planning_packet','planning_prd_alignment','planning_scope_alignment','planning_contract_comparison','planning_readiness','finance_group_snapshot')
     AND ce.kind NOT LIKE 'forecast_%' AND ce.kind NOT LIKE 'd03_control_%' AND ce.kind NOT LIKE 'p14_%'
     AND NOT(ce.kind='finance_report_snapshot' AND ce.source LIKE 'derived:forecast:%')
     AND NOT EXISTS(SELECT 1 FROM finance_forecastscenario fs WHERE fs.case_id=w.case_id AND (fs.evidence_id=ce.id OR fs.payload->'items' @> jsonb_build_array(jsonb_build_object('evidence_id',ce.id)) OR fs.payload->'openings' @> jsonb_build_array(jsonb_build_object('evidence_id',ce.id))))
     AND (ce.source<>'psl:p56-confirmed-request/v1' OR EXISTS(SELECT 1 FROM pmo_changerequest cr JOIN pmo_changeversion cv ON cv.id=cr.current_id WHERE cr.case_id=w.case_id AND cv.evidence_id=ce.id))
     AND ce.kind NOT LIKE 'agent_private_%' AND ce.kind NOT LIKE 'ops_%' AND ce.kind NOT LIKE 'integration_%'
     AND (EXISTS(SELECT 1 FROM pmo_meeting m JOIN pmo_meetingversion mv ON mv.id=m.current_id WHERE m.case_id=w.case_id AND mv.evidence_id=ce.id AND mv.occurred_at>=r.start_at AND mv.occurred_at<r.end_at)
      OR EXISTS(SELECT 1 FROM pmo_actionitem ai JOIN pmo_actionstate state ON state.id=ai.current_id WHERE ai.case_id=w.case_id AND state.evidence_id=ce.id)
      OR EXISTS(SELECT 1 FROM pmo_milestone m WHERE m.case_id=w.case_id AND m.evidence_id=ce.id AND m.completed_at>=r.start_at AND m.completed_at<r.end_at)
      OR EXISTS(SELECT 1 FROM pmo_issue i JOIN pmo_issuestate state ON state.id=i.current_id WHERE i.case_id=w.case_id AND state.evidence_id=ce.id)
      OR EXISTS(SELECT 1 FROM pmo_changerequest cr JOIN pmo_changeversion cv ON cv.id=cr.current_id WHERE cr.case_id=w.case_id AND cv.evidence_id=ce.id))))
   OR NOT EXISTS(SELECT 1 FROM jsonb_array_elements(v.payload->'sections') section WHERE section->>'heading'=theme.k AND section->>'text'=content.body::jsonb->'sections'->theme.k->>'text')
   OR v.fields->theme.k->>'text' IS DISTINCT FROM content.body::jsonb->'sections'->theme.k->>'text')
 AND EXISTS(SELECT 1 FROM workflows_factoryactivity fa JOIN workflows_factoryattempt a ON a.activity_id=fa.id
  WHERE fa.work_id=w.id AND fa.kind='ACT09' AND a.phase='observed' AND a.result->>'document_version'=v.id::text AND a.result->>'head'=e.id::text));
$$;

CREATE OR REPLACE FUNCTION psl_schedules_grants(cid uuid, uid bigint, actions text[]) RETURNS boolean LANGUAGE sql STABLE AS $$
 SELECT EXISTS(SELECT 1 FROM auth_user WHERE id=uid AND is_active)
  AND NOT EXISTS(SELECT 1 FROM unnest(actions) required(action_name) WHERE NOT EXISTS(
   SELECT 1 FROM identity_grant g WHERE g.case_id=cid AND g.user_id=uid AND g.action=required.action_name AND g.active));
$$;
-- Structural checks are bounded mirrors, not execution of Python domain validators.
CREATE OR REPLACE FUNCTION psl_schedules_values(pid bigint) RETURNS jsonb LANGUAGE sql STABLE AS $$
 SELECT CASE WHEN c.component='D04.iana_timezone' THEN jsonb_build_array(c.envelope->'value') ELSE
 (SELECT jsonb_agg(r.content ORDER BY item.ordinality) FROM jsonb_array_elements(CASE WHEN jsonb_typeof(c.envelope->'value')='array' THEN c.envelope->'value' ELSE jsonb_build_array(c.envelope->'value') END) WITH ORDINALITY item(value,ordinality)
 JOIN policy_registeredreference r ON r.case_id=c.case_id AND r.ref=CASE WHEN jsonb_typeof(item.value)='object' THEN item.value->>'artifact_ref' ELSE item.value#>>'{}' END
 AND r.version=CASE WHEN jsonb_typeof(item.value)='object' THEN (item.value->>'artifact_version')::integer ELSE 1 END) END
 FROM policy_configuration c WHERE c.id=pid;
$$;
CREATE OR REPLACE FUNCTION psl_schedules_binding_current(pid bigint) RETURNS boolean LANGUAGE plpgsql STABLE AS $$
DECLARE ap record; bound jsonb; item jsonb; path text[];
BEGIN
 SELECT a.*,s.binding_paths,s.configuration_id AS origin_id,c.case_id AS origin_case,t.case_id AS target_case INTO ap
 FROM policy_scopeapplication a JOIN policy_scopeversion s ON s.id=a.source_id JOIN policy_configuration c ON c.id=s.configuration_id
 JOIN policy_configuration t ON t.id=a.configuration_id WHERE a.configuration_id=pid;
 IF NOT FOUND THEN RETURN true; END IF;
 bound:=psl_schedules_values(ap.origin_id);
 FOR item IN SELECT value FROM jsonb_array_elements(ap.bindings) LOOP
  IF NOT ap.binding_paths ? (item->>'path') THEN RETURN false; END IF;
  SELECT array_agg(replace(replace(part,'~1','/'),'~0','~') ORDER BY ordinality) INTO path FROM unnest(string_to_array(substr(item->>'path',2),'/')) WITH ORDINALITY p(part,ordinality);
  IF bound#>path IS NULL OR jsonb_typeof(bound#>path) IN ('object','array') THEN RETURN false; END IF;
  bound:=jsonb_set(bound,path,item->'value',false);
 END LOOP;
 IF ap.origin_case<>ap.target_case AND jsonb_array_length(ap.bindings)<>jsonb_array_length(ap.binding_paths) THEN RETURN false; END IF;
 RETURN bound IS NOT DISTINCT FROM psl_schedules_values(pid);
END;
$$;
CREATE OR REPLACE FUNCTION psl_schedules_envelope_current(pid bigint) RETURNS boolean LANGUAGE sql STABLE AS $$
 SELECT EXISTS(SELECT 1 FROM policy_configuration c JOIN core_case k ON k.id=c.case_id WHERE c.id=pid
 AND c.envelope->'subject_scope'=jsonb_build_object('kind',CASE WHEN k.kind='project' THEN 'project' ELSE 'service' END,'ref',k.id::text)
 AND (c.envelope->>'fixture_scope'='synthetic_test')=k.synthetic
 AND (c.component NOT IN ('SCHEDULES.review_authority','AF13.owner_validation_rules') OR NOT EXISTS(
 SELECT 1 FROM jsonb_array_elements(psl_schedules_values(c.id)) v CROSS JOIN LATERAL jsonb_array_elements(v->'assignments') a
 WHERE NOT EXISTS(SELECT 1 FROM auth_user WHERE id=(a->>'user_id')::bigint AND is_active)))
 AND (c.component<>'D05.role_principal_assignments' OR NOT EXISTS(
 SELECT 1 FROM jsonb_array_elements(psl_schedules_values(c.id)) v WHERE NOT EXISTS(SELECT 1 FROM auth_user WHERE id=(v->>'user_id')::bigint AND is_active))));
$$;
CREATE OR REPLACE FUNCTION psl_schedules_policy_status(cid uuid, component_name text) RETURNS text LANGUAGE plpgsql STABLE AS $$
DECLARE c record; ap record; life text; source_life text;
BEGIN
 SELECT cfg.*,(SELECT state FROM policy_policystate WHERE configuration_id=cfg.id ORDER BY id DESC LIMIT 1) AS lifecycle INTO c
 FROM policy_configuration cfg WHERE cfg.case_id=cid AND cfg.component=component_name
 AND (SELECT state FROM policy_policystate WHERE configuration_id=cfg.id ORDER BY id DESC LIMIT 1) IN ('active','revoked','superseded') ORDER BY cfg.revision DESC LIMIT 1;
 IF NOT FOUND THEN RETURN 'MISSING'; END IF;
 IF c.lifecycle='revoked' THEN RETURN 'REVOKED'; END IF;
 SELECT a.*,s.kind,s.ref,s.revision,s.configuration_id AS origin_id,o.case_id AS origin_case,o.component AS origin_component,o.envelope AS origin_envelope,
 (SELECT state FROM policy_scopestate WHERE source_id=s.id ORDER BY id DESC LIMIT 1) AS lifecycle INTO ap
 FROM policy_scopeapplication a JOIN policy_scopeversion s ON s.id=a.source_id JOIN policy_configuration o ON o.id=s.configuration_id WHERE a.configuration_id=c.id;
 IF FOUND THEN
  IF NOT psl_schedules_grants(c.case_id,ap.actor_id,ARRAY['case.read','policy.configure'])
   OR NOT psl_schedules_grants(ap.origin_case,ap.actor_id,ARRAY['case.read','policy.read'])
   OR NOT EXISTS(SELECT 1 FROM core_case t JOIN core_case o ON o.id=ap.origin_case WHERE t.id=c.case_id AND t.tenant=o.tenant AND t.synthetic=o.synthetic)
   OR c.component<>ap.origin_component OR (ap.kind<>'organization' AND c.case_id<>ap.origin_case)
   OR NOT psl_schedules_binding_current(c.id)
   OR EXISTS(SELECT 1 FROM unnest(ARRAY['effective_from','effective_until','implementation_id','implementation_version','reviewed_implementation_ref','component_schema_ref','schema_version','fixture_scope']) f WHERE c.envelope->f IS DISTINCT FROM ap.origin_envelope->f)
  THEN RETURN 'INVALID'; END IF;
  IF ap.lifecycle='revoked' THEN RETURN 'REVOKED'; END IF;
  IF ap.lifecycle<>'active' OR EXISTS(SELECT 1 FROM policy_scopeversion n JOIN policy_configuration nc ON nc.id=n.configuration_id WHERE nc.case_id=ap.origin_case AND nc.component=ap.origin_component AND n.kind=ap.kind AND n.ref=ap.ref AND n.revision>ap.revision AND EXISTS(SELECT 1 FROM policy_scopestate WHERE source_id=n.id AND state IN ('active','revoked')))
   OR NOT EXISTS(SELECT 1 FROM policy_scopestate s WHERE s.id=(SELECT max(id) FROM policy_scopestate WHERE source_id=ap.source_id AND state='active') AND psl_schedules_grants(ap.origin_case,s.actor_id,ARRAY['case.read','policy.activate']))
   OR NOT EXISTS(SELECT 1 FROM core_case k WHERE k.id=ap.origin_case AND ((ap.kind='organization' AND ap.ref=k.tenant) OR (ap.kind='project' AND k.kind='project' AND ap.ref=k.id::text) OR (ap.kind='service' AND k.kind='support' AND ap.ref=k.id::text) OR (ap.kind='contract' AND EXISTS(SELECT 1 FROM core_evidence e WHERE e.case_id=k.id AND e.kind='sow' AND ap.ref='evidence:'||e.id::text))))
   OR (SELECT state FROM policy_policystate WHERE configuration_id=ap.origin_id ORDER BY id DESC LIMIT 1)<>'validated'
   OR NOT psl_schedules_envelope_current(ap.origin_id)
  THEN RETURN 'INVALID'; END IF;
  IF (ap.origin_envelope->>'effective_from')::timestamptz>clock_timestamp() THEN RETURN 'MISSING'; END IF;
  IF (ap.origin_envelope->>'effective_until')::timestamptz<=clock_timestamp() THEN RETURN 'EXPIRED'; END IF;
 END IF;
 IF NOT psl_schedules_envelope_current(c.id) THEN RETURN 'INVALID'; END IF;
 IF (c.envelope->>'effective_from')::timestamptz>clock_timestamp() THEN RETURN 'MISSING'; END IF;
 IF (c.envelope->>'effective_until')::timestamptz<=clock_timestamp() THEN RETURN 'EXPIRED'; END IF;
 RETURN 'ACTIVE';
END;
$$;
CREATE OR REPLACE FUNCTION psl_schedules_policy_current(cid uuid, pid bigint) RETURNS boolean LANGUAGE sql STABLE AS $$
 SELECT EXISTS(SELECT 1 FROM policy_configuration c WHERE c.id=pid AND c.case_id=cid
 AND c.id=(SELECT cc.id FROM policy_configuration cc WHERE cc.case_id=cid AND cc.component=c.component AND (SELECT state FROM policy_policystate WHERE configuration_id=cc.id ORDER BY id DESC LIMIT 1) IN ('active','revoked','superseded') ORDER BY cc.revision DESC LIMIT 1)
 AND psl_schedules_policy_status(cid,c.component)='ACTIVE');
$$;
CREATE OR REPLACE FUNCTION psl_schedules_authority_current(cid uuid, authority jsonb) RETURNS boolean LANGUAGE sql STABLE AS $$
 SELECT NOT EXISTS(SELECT 1 FROM jsonb_each(authority) pin WHERE jsonb_typeof(pin.value)='number'
  AND pin.key<>'D05.decision_action_matrix' AND NOT psl_schedules_policy_current(cid,(pin.value::text)::bigint));
$$;
CREATE OR REPLACE FUNCTION psl_schedules_role_current(cid uuid, uid bigint, authority jsonb, required_role text DEFAULT 'Finance') RETURNS boolean LANGUAGE sql STABLE AS $$
 WITH assignments AS (SELECT ref.content FROM policy_configuration c
  CROSS JOIN LATERAL jsonb_array_elements_text(c.envelope->'value') selection(ref)
  JOIN policy_registeredreference ref ON ref.case_id=c.case_id AND ref.ref=selection.ref AND ref.version=1
  WHERE c.id=(authority->>'D05.role_principal_assignments')::bigint AND psl_schedules_policy_current(cid,c.id)
   AND ref.content->>'user_id'=uid::text)
 SELECT EXISTS(SELECT 1 FROM assignments WHERE content->>'role'=required_role)
  AND ((SELECT count(DISTINCT content->>'role') FROM assignments)=1
   OR ((SELECT bool_and(content ? 'eligibility') FROM assignments)
    AND (SELECT bool_and((content->'eligibility'->>'valid_from')::timestamptz<=clock_timestamp()
     AND (content->'eligibility'->>'valid_until')::timestamptz>clock_timestamp()) FROM assignments))
   OR ((SELECT synthetic FROM core_case WHERE id=cid) AND NOT (SELECT bool_and(content ? 'eligibility') FROM assignments)));
$$;
CREATE OR REPLACE FUNCTION psl_schedules_finance_review_current(rid bigint) RETURNS boolean LANGUAGE sql STABLE AS $$
 SELECT EXISTS(SELECT 1 FROM finance_financereview r WHERE r.id=rid AND r.verdict='approve'
  AND psl_schedules_grants(r.case_id,r.actor_id,ARRAY['finance.review'])
  AND psl_schedules_authority_current(r.case_id,r.authority)
  AND psl_schedules_role_current(r.case_id,r.actor_id,r.authority)
  AND EXISTS(SELECT 1 FROM policy_configuration c JOIN policy_registeredreference ref
   ON ref.case_id=c.case_id AND ref.ref=c.envelope->'value'->>'artifact_ref'
    AND ref.version=(c.envelope->'value'->>'artifact_version')::integer AND ref.sha256=c.envelope->'value'->>'sha256'
   WHERE c.case_id=r.case_id AND c.component='D05.decision_action_matrix' AND psl_schedules_policy_current(r.case_id,c.id)
    AND ref.content->'finance' @> jsonb_build_array(r.authority->'finance_review_rule'))
  AND r.id=(SELECT max(x.id) FROM finance_financereview x WHERE x.case_id=r.case_id AND x.purpose=r.purpose
   AND x.source_id IS NOT DISTINCT FROM r.source_id AND x.configuration_id IS NOT DISTINCT FROM r.configuration_id
   AND x.adjustment_id IS NOT DISTINCT FROM r.adjustment_id AND x.run_id IS NOT DISTINCT FROM r.run_id));
$$;
CREATE OR REPLACE FUNCTION psl_schedules_mapping_current(nid bigint) RETURNS boolean LANGUAGE sql STABLE AS $$
 SELECT EXISTS(SELECT 1 FROM finance_financerun n JOIN finance_financesource src ON src.id=n.source_id
  WHERE n.id=nid AND src.id=(SELECT max(id) FROM finance_financesource WHERE batch_id=src.batch_id) AND n.kind='mapping' AND n.result->>'status'='complete' AND src.completeness='complete'
   AND psl_schedules_grants(n.case_id,n.actor_id,ARRAY['case.read','finance.read','finance.calculate'])
   AND psl_schedules_finance_review_current((n.snapshot->'source_review'->>'id')::bigint)
   AND NOT EXISTS(SELECT 1 FROM jsonb_each(n.snapshot->'policies') pin
    WHERE pin.value->>'status'<>'ACTIVE' OR NOT psl_schedules_policy_current(n.case_id,(pin.value->>'id')::bigint))
   AND NOT EXISTS(SELECT 1 FROM jsonb_each(n.snapshot->'reviews') pin
    WHERE pin.value->'valid'<>'true'::jsonb OR NOT psl_schedules_finance_review_current((pin.value->>'id')::bigint))
   AND NOT EXISTS(SELECT 1 FROM jsonb_array_elements(n.snapshot->'adjustments') pin
    WHERE NOT psl_schedules_finance_review_current((pin->'review'->>'id')::bigint)
     OR EXISTS(SELECT 1 FROM finance_financeadjustment old JOIN finance_financeadjustment newer
      ON newer.source_id=old.source_id AND newer.reference=old.reference AND newer.number>old.number
      WHERE old.id=(pin->>'id')::bigint)));
$$;
CREATE OR REPLACE FUNCTION psl_schedules_policy_pin_current(cid uuid, component_name text, pin jsonb) RETURNS boolean LANGUAGE sql STABLE AS $$
 SELECT COALESCE((pin->>'status'='ACTIVE' AND psl_schedules_policy_current(cid,(pin->>'id')::bigint))
  OR (pin->'id'='null'::jsonb AND pin->>'status'<>'ACTIVE' AND pin->>'status'=psl_schedules_policy_status(cid,component_name)),false);
$$;
CREATE OR REPLACE FUNCTION psl_schedules_package_current(pid bigint) RETURNS boolean LANGUAGE sql STABLE AS $$
 SELECT EXISTS(SELECT 1 FROM documents_validationpackage p WHERE p.id=pid
  AND NOT EXISTS(SELECT 1 FROM documents_validationpackage n WHERE n.case_id=p.case_id AND n.reference=p.reference AND n.version>p.version)
  AND NOT EXISTS(SELECT 1 FROM jsonb_array_elements(p.manifest->'sources') pin WHERE NOT EXISTS(
   SELECT 1 FROM documents_discoverysource d WHERE d.id=(pin->>0)::bigint AND d.case_id=p.case_id AND d.sha256=pin->>1
    AND NOT EXISTS(SELECT 1 FROM documents_discoverysource n WHERE n.case_id=d.case_id AND n.reference=d.reference AND n.version>d.version)))
  AND NOT EXISTS(SELECT 1 FROM jsonb_array_elements(p.manifest->'examples') pin WHERE NOT EXISTS(
   SELECT 1 FROM documents_validationexample e JOIN core_evidence ce ON ce.id=e.evidence_id WHERE e.id=(pin->>0)::bigint AND e.case_id=p.case_id AND ce.sha256=pin->>2
    AND NOT EXISTS(SELECT 1 FROM documents_validationexample n WHERE n.case_id=e.case_id AND n.reference=e.reference AND n.version>e.version)))
  AND NOT EXISTS(SELECT 1 FROM jsonb_each(p.manifest->'policies') pin WHERE NOT psl_schedules_policy_pin_current(p.case_id,pin.key,pin.value)));
$$;
CREATE OR REPLACE FUNCTION psl_schedules_validation_review_current(rid bigint) RETURNS boolean LANGUAGE sql STABLE AS $$
 SELECT EXISTS(SELECT 1 FROM documents_validationreview r JOIN documents_validationpackage p ON p.id=r.package_id
 WHERE r.id=rid AND r.verdict='approve' AND psl_schedules_package_current(p.id)
  AND r.snapshot->>'package'=p.sha256
  AND r.id=(SELECT max(id) FROM documents_validationreview WHERE package_id=p.id AND kind=r.kind)
  AND psl_schedules_grants(p.case_id,r.actor_id,ARRAY[CASE WHEN r.kind='acceptance' THEN 'validation.accept' ELSE 'validation.review' END])
  AND psl_schedules_authority_current(p.case_id,r.authority)
  AND EXISTS(SELECT 1 FROM policy_configuration owner JOIN policy_registeredreference ref ON ref.case_id=owner.case_id
   AND ref.ref=owner.envelope->'value'->>'artifact_ref' AND ref.version=(owner.envelope->'value'->>'artifact_version')::integer
   CROSS JOIN LATERAL jsonb_array_elements(ref.content->'assignments') assignment
   WHERE owner.id=(r.authority->>'AF13.owner_validation_rules')::bigint
    AND assignment->>'user_id'=r.actor_id::text AND assignment->'purposes' ? r.kind
    AND psl_schedules_role_current(p.case_id,r.actor_id,r.authority,assignment->>'role'))
  AND (r.kind='meaning' OR (r.snapshot->>'meaning'=(SELECT max(id)::text FROM documents_validationreview WHERE package_id=p.id AND kind='meaning')
   AND psl_schedules_validation_review_current((r.snapshot->>'meaning')::bigint)))
  AND (r.kind<>'acceptance' OR (psl_schedules_policy_current(p.case_id,(r.snapshot->>'criteria')::bigint)
   AND r.snapshot->>'expectations'=(SELECT max(id)::text FROM documents_validationreview WHERE package_id=p.id AND kind='expectations')
   AND psl_schedules_validation_review_current((r.snapshot->>'expectations')::bigint)
   AND NOT EXISTS(SELECT 1 FROM jsonb_array_elements_text(r.snapshot->'replays') replay WHERE NOT EXISTS(
    SELECT 1 FROM documents_validationreplay vr WHERE vr.id=replay::bigint AND vr.package_id=p.id
     AND vr.expectation_review_id=(r.snapshot->>'expectations')::bigint AND vr.result->'matches'='true'::jsonb
     AND psl_schedules_grants(p.case_id,vr.actor_id,ARRAY['validation.replay.record'])
     AND vr.id=(SELECT max(id) FROM documents_validationreplay WHERE package_id=p.id AND example_id=vr.example_id))))));
$$;
CREATE OR REPLACE FUNCTION psl_schedules_current(sid bigint) RETURNS boolean LANGUAGE sql STABLE AS $$
 SELECT EXISTS(SELECT 1 FROM finance_schedulework s WHERE s.id=sid AND s.kind IN ('income','inventory')
  AND psl_schedules_grants(s.case_id,s.actor_id,ARRAY['case.read','finance.read','schedules.read','schedules.prepare'])
  AND NOT EXISTS(SELECT 1 FROM finance_schedulework n WHERE n.case_id=s.case_id AND n.kind=s.kind AND n.reference=s.reference AND n.version>s.version)
  AND s.snapshot->'policy'->>'status'='ACTIVE' AND psl_schedules_policy_current(s.case_id,(s.snapshot->'policy'->>'id')::bigint)
  AND (s.parent_id IS NULL OR (psl_schedules_grants(s.case_id,s.actor_id,ARRAY['finance.calculate']) AND psl_schedules_mapping_current(s.parent_id)))
  AND NOT EXISTS(SELECT 1 FROM jsonb_array_elements(s.snapshot->'packages') pin WHERE NOT EXISTS(
   SELECT 1 FROM documents_validationpackage p WHERE p.id=(pin->>'id')::bigint AND p.case_id=s.case_id AND p.sha256=pin->>'sha256' AND p.reference=pin->>'schedule'
    AND psl_schedules_package_current(p.id)
    AND NOT EXISTS(SELECT 1 FROM jsonb_array_elements(pin->'reviews') rp WHERE
     (rp->>'id')::bigint IS DISTINCT FROM (SELECT max(id) FROM documents_validationreview WHERE package_id=p.id AND kind=rp->>'purpose')
     OR (rp->>'valid')::boolean IS DISTINCT FROM psl_schedules_validation_review_current((rp->>'id')::bigint)))))
$$;
CREATE OR REPLACE FUNCTION psl_schedules_review_current(rid bigint) RETURNS boolean LANGUAGE sql STABLE AS $$
 SELECT EXISTS(SELECT 1 FROM finance_schedulereview r JOIN finance_schedulework w ON w.id=r.work_id
  WHERE r.id=rid AND r.verdict='approve' AND r.snapshot=w.snapshot AND psl_schedules_current(w.id)
   AND psl_schedules_grants(w.case_id,r.actor_id,ARRAY['case.read','finance.read','schedules.read','schedules.review'])
   AND psl_schedules_authority_current(w.case_id,r.authority) AND psl_schedules_role_current(w.case_id,r.actor_id,r.authority)
   AND r.id=(SELECT max(id) FROM finance_schedulereview WHERE work_id=w.id));
$$;

CREATE OR REPLACE FUNCTION psl_ppe_policy_people_current(pid bigint) RETURNS boolean LANGUAGE sql STABLE AS $$
 SELECT EXISTS(SELECT 1 FROM policy_configuration c WHERE c.id=pid AND
  CASE WHEN c.component IN ('F07.review_authority','AF13.owner_validation_rules') THEN
   EXISTS(SELECT 1 FROM policy_registeredreference r WHERE r.case_id=c.case_id
    AND r.ref=c.envelope->'value'->>'artifact_ref' AND r.version=(c.envelope->'value'->>'artifact_version')::integer
    AND r.sha256=c.envelope->'value'->>'sha256'
    AND NOT EXISTS(SELECT 1 FROM jsonb_array_elements(r.content->'assignments') assignment
     WHERE NOT EXISTS(SELECT 1 FROM auth_user u WHERE u.id=(assignment->>'user_id')::bigint AND u.is_active)))
  WHEN c.component='D05.role_principal_assignments' THEN
   NOT EXISTS(SELECT 1 FROM jsonb_array_elements_text(c.envelope->'value') selection(ref)
    LEFT JOIN policy_registeredreference r ON r.case_id=c.case_id AND r.ref=selection.ref AND r.version=1
    LEFT JOIN auth_user u ON u.id=(r.content->>'user_id')::bigint
    WHERE r.id IS NULL OR u.id IS NULL OR NOT u.is_active)
  ELSE true END);
$$;
CREATE OR REPLACE FUNCTION psl_ppe_policy_current(cid uuid, pid bigint) RETURNS boolean LANGUAGE sql STABLE AS $$
 SELECT EXISTS(SELECT 1 FROM policy_configuration c JOIN core_case target_case ON target_case.id=c.case_id
  WHERE c.id=pid AND c.case_id=cid AND psl_ppe_policy_people_current(c.id)
  AND c.envelope->'subject_scope'=jsonb_build_object('kind',CASE WHEN target_case.kind='project' THEN 'project' ELSE 'service' END,'ref',c.case_id::text)
  AND (c.envelope->>'fixture_scope'='synthetic_test')=target_case.synthetic
  AND (SELECT state FROM policy_policystate WHERE configuration_id=c.id ORDER BY id DESC LIMIT 1)='active'
  AND (c.envelope->>'effective_from')::timestamptz<=clock_timestamp()
  AND (c.envelope->>'effective_until' IS NULL OR (c.envelope->>'effective_until')::timestamptz>clock_timestamp())
  AND NOT EXISTS(SELECT 1 FROM policy_scopeapplication ap
   JOIN policy_scopeversion sv ON sv.id=ap.source_id JOIN policy_configuration origin ON origin.id=sv.configuration_id
   JOIN core_case origin_case ON origin_case.id=origin.case_id
   WHERE ap.configuration_id=c.id AND (
    NOT psl_ppe_policy_people_current(origin.id) OR target_case.tenant<>origin_case.tenant OR target_case.synthetic<>origin_case.synthetic
    OR c.component<>origin.component OR (sv.kind<>'organization' AND c.case_id<>origin.case_id)
    OR NOT ((sv.kind='organization' AND sv.ref=origin_case.tenant)
     OR (sv.kind='project' AND origin_case.kind='project' AND sv.ref=origin.case_id::text)
     OR (sv.kind='service' AND origin_case.kind='support' AND sv.ref=origin.case_id::text)
     OR (sv.kind='contract' AND EXISTS(SELECT 1 FROM core_evidence e WHERE e.case_id=origin.case_id AND e.kind='sow' AND sv.ref='evidence:'||e.id::text)))
    OR sv.id IS DISTINCT FROM (SELECT family.id FROM policy_scopeversion family
     JOIN policy_configuration fc ON fc.id=family.configuration_id
     WHERE fc.case_id=origin.case_id AND fc.component=origin.component AND family.kind=sv.kind AND family.ref=sv.ref
      AND EXISTS(SELECT 1 FROM policy_scopestate fs WHERE fs.source_id=family.id AND fs.state IN ('active','revoked'))
     ORDER BY family.revision DESC LIMIT 1)
    OR EXISTS(SELECT 1 FROM unnest(ARRAY['effective_from','effective_until','implementation_id','implementation_version','reviewed_implementation_ref','component_schema_ref','schema_version','fixture_scope']) k
     WHERE c.envelope->k IS DISTINCT FROM origin.envelope->k)
    OR origin.envelope->'subject_scope'<>jsonb_build_object('kind',CASE WHEN origin_case.kind='project' THEN 'project' ELSE 'service' END,'ref',origin.case_id::text)
    OR (origin.envelope->>'fixture_scope'='synthetic_test')<>origin_case.synthetic
    OR (SELECT state FROM policy_scopestate WHERE source_id=sv.id ORDER BY id DESC LIMIT 1)<>'active'
    OR (SELECT state FROM policy_policystate WHERE configuration_id=origin.id ORDER BY id DESC LIMIT 1)<>'validated'
    OR NOT EXISTS(SELECT 1 FROM auth_user u WHERE u.id=ap.actor_id AND u.is_active)
    OR NOT EXISTS(SELECT 1 FROM identity_grant WHERE user_id=ap.actor_id AND case_id=c.case_id AND action='case.read' AND active)
    OR NOT EXISTS(SELECT 1 FROM identity_grant WHERE user_id=ap.actor_id AND case_id=c.case_id AND action='policy.configure' AND active)
    OR NOT EXISTS(SELECT 1 FROM identity_grant WHERE user_id=ap.actor_id AND case_id=origin.case_id AND action='case.read' AND active)
    OR NOT EXISTS(SELECT 1 FROM identity_grant WHERE user_id=ap.actor_id AND case_id=origin.case_id AND action='policy.read' AND active)
    OR NOT EXISTS(SELECT 1 FROM policy_scopestate activation JOIN auth_user u ON u.id=activation.actor_id
     WHERE activation.id=(SELECT max(id) FROM policy_scopestate WHERE source_id=sv.id AND state='active')
      AND u.is_active AND EXISTS(SELECT 1 FROM identity_grant WHERE user_id=u.id AND case_id=origin.case_id AND action='case.read' AND active)
      AND EXISTS(SELECT 1 FROM identity_grant WHERE user_id=u.id AND case_id=origin.case_id AND action='policy.activate' AND active)))));

$$;
CREATE OR REPLACE FUNCTION psl_ppe_grants(cid uuid, uid bigint, actions text[]) RETURNS boolean LANGUAGE sql STABLE AS $$
 SELECT EXISTS(SELECT 1 FROM auth_user WHERE id=uid AND is_active)
  AND NOT EXISTS(SELECT 1 FROM unnest(actions) required(action_name) WHERE NOT EXISTS(
   SELECT 1 FROM identity_grant g WHERE g.case_id=cid AND g.user_id=uid AND g.action=required.action_name AND g.active));
$$;
CREATE OR REPLACE FUNCTION psl_ppe_authority_current(cid uuid, authority jsonb) RETURNS boolean LANGUAGE sql STABLE AS $$
 SELECT NOT EXISTS(SELECT 1 FROM jsonb_each(authority) pin WHERE jsonb_typeof(pin.value)='number'
  AND pin.key<>'D05.decision_action_matrix' AND NOT psl_ppe_policy_current(cid,(pin.value::text)::bigint));
$$;
CREATE OR REPLACE FUNCTION psl_ppe_role_current(cid uuid, uid bigint, authority jsonb) RETURNS boolean LANGUAGE sql STABLE AS $$
 SELECT EXISTS(SELECT 1 FROM policy_configuration c
  CROSS JOIN LATERAL jsonb_array_elements_text(c.envelope->'value') selection(ref)
  JOIN policy_registeredreference r ON r.case_id=c.case_id AND r.ref=selection.ref AND r.version=1
  WHERE c.id=(authority->>'D05.role_principal_assignments')::bigint AND psl_ppe_policy_current(cid,c.id)
   AND r.content->>'user_id'=uid::text AND r.content->>'role'='Finance'
   AND (NOT r.content ? 'eligibility' OR
    ((r.content->'eligibility'->>'valid_from')::timestamptz<=clock_timestamp()
     AND (r.content->'eligibility'->>'valid_until')::timestamptz>clock_timestamp())));
$$;
CREATE OR REPLACE FUNCTION psl_ppe_finance_review_current(rid bigint) RETURNS boolean LANGUAGE sql STABLE AS $$
 SELECT EXISTS(SELECT 1 FROM finance_financereview r WHERE r.id=rid AND r.verdict='approve'
  AND psl_ppe_grants(r.case_id,r.actor_id,ARRAY['finance.review'])
  AND psl_ppe_authority_current(r.case_id,r.authority)
  AND psl_ppe_role_current(r.case_id,r.actor_id,r.authority)
  AND EXISTS(SELECT 1 FROM policy_configuration c JOIN policy_registeredreference ref
   ON ref.case_id=c.case_id AND ref.ref=c.envelope->'value'->>'artifact_ref'
    AND ref.version=(c.envelope->'value'->>'artifact_version')::integer AND ref.sha256=c.envelope->'value'->>'sha256'
   WHERE c.case_id=r.case_id AND c.component='D05.decision_action_matrix' AND psl_ppe_policy_current(r.case_id,c.id)
    AND ref.content->'finance' @> jsonb_build_array(r.authority->'finance_review_rule'))
  AND r.id=(SELECT max(x.id) FROM finance_financereview x WHERE x.case_id=r.case_id AND x.purpose=r.purpose
   AND x.source_id IS NOT DISTINCT FROM r.source_id AND x.configuration_id IS NOT DISTINCT FROM r.configuration_id
   AND x.adjustment_id IS NOT DISTINCT FROM r.adjustment_id AND x.run_id IS NOT DISTINCT FROM r.run_id));
$$;
CREATE OR REPLACE FUNCTION psl_ppe_mapping_current(nid bigint) RETURNS boolean LANGUAGE sql STABLE AS $$
 SELECT EXISTS(SELECT 1 FROM finance_financerun n JOIN finance_financesource src ON src.id=n.source_id
  WHERE n.id=nid AND n.kind='mapping' AND n.result->>'status'='complete' AND src.completeness='complete'
   AND psl_ppe_grants(n.case_id,n.actor_id,ARRAY['case.read','finance.read','finance.calculate'])
   AND psl_ppe_finance_review_current((n.snapshot->'source_review'->>'id')::bigint)
   AND NOT EXISTS(SELECT 1 FROM jsonb_each(n.snapshot->'policies') pin
    WHERE pin.value->>'status'<>'ACTIVE' OR NOT psl_ppe_policy_current(n.case_id,(pin.value->>'id')::bigint))
   AND NOT EXISTS(SELECT 1 FROM jsonb_each(n.snapshot->'reviews') pin
    WHERE pin.value->'valid'<>'true'::jsonb OR NOT psl_ppe_finance_review_current((pin.value->>'id')::bigint))
   AND NOT EXISTS(SELECT 1 FROM jsonb_array_elements(n.snapshot->'adjustments') pin
    WHERE NOT psl_ppe_finance_review_current((pin->'review'->>'id')::bigint)
     OR EXISTS(SELECT 1 FROM finance_financeadjustment old JOIN finance_financeadjustment newer
      ON newer.source_id=old.source_id AND newer.reference=old.reference AND newer.number>old.number
      WHERE old.id=(pin->>'id')::bigint)));
$$;
CREATE OR REPLACE FUNCTION psl_ppe_review_current(rid bigint) RETURNS boolean LANGUAGE sql STABLE AS $$
 SELECT EXISTS(SELECT 1 FROM finance_schedulereview r JOIN finance_schedulework w ON w.id=r.work_id
  WHERE r.id=rid AND r.verdict='approve' AND r.snapshot=w.snapshot
   AND psl_ppe_grants(w.case_id,r.actor_id,ARRAY['case.read','finance.read','ppe.read','ppe.review'])
   AND psl_ppe_authority_current(w.case_id,r.authority)
   AND psl_ppe_role_current(w.case_id,r.actor_id,r.authority)
   AND r.id=(SELECT max(x.id) FROM finance_schedulereview x WHERE x.work_id=w.id AND x.authority->>'purpose'=r.authority->>'purpose'));
$$;
CREATE OR REPLACE FUNCTION psl_ppe_schedule_current(sid bigint, depth integer DEFAULT 0) RETURNS boolean LANGUAGE plpgsql STABLE AS $$
DECLARE s finance_schedulework; r finance_schedulework; basis bigint; prior_id bigint; pin jsonb;
BEGIN
 IF depth>36 THEN RETURN false; END IF;
 SELECT * INTO s FROM finance_schedulework WHERE id=sid AND kind='ppe_schedule';
 IF NOT FOUND OR s.result->>'status'<>'ready' THEN RETURN false; END IF;
 SELECT * INTO r FROM finance_schedulework WHERE id=(s.payload->>'register_id')::bigint AND case_id=s.case_id AND kind='ppe_register';
 IF NOT FOUND THEN RETURN false; END IF;
 IF NOT psl_ppe_grants(s.case_id,s.actor_id,ARRAY['case.read','finance.read','ppe.read','ppe.prepare'])
  OR NOT psl_ppe_grants(r.case_id,r.actor_id,ARRAY['case.read','finance.read','ppe.read','ppe.capture'])
  OR NOT psl_ppe_review_current((s.snapshot->>'register_review')::bigint)
  OR s.snapshot->'register'<>jsonb_build_array(r.id,r.sha256)
  OR EXISTS(SELECT 1 FROM finance_schedulework newer WHERE newer.case_id=s.case_id
   AND ((newer.kind=s.kind AND newer.reference=s.reference AND newer.version>s.version)
    OR (newer.kind=r.kind AND newer.reference=r.reference AND newer.version>r.version))) THEN RETURN false; END IF;
 SELECT max(id) INTO basis FROM finance_schedulereview WHERE work_id=r.id AND authority->>'purpose'='basis';
 IF basis IS DISTINCT FROM (s.snapshot->>'basis_review')::bigint
  OR (s.snapshot->>'basis_approved')::boolean IS DISTINCT FROM psl_ppe_review_current(basis)
  OR (r.result->'date_basis_ambiguous'='true'::jsonb AND NOT psl_ppe_review_current(basis)) THEN RETURN false; END IF;
 IF EXISTS(SELECT 1 FROM jsonb_each(s.snapshot->'policies') p WHERE p.value->>'status'<>'ACTIVE'
   OR NOT psl_ppe_policy_current(s.case_id,(p.value->>'id')::bigint)) THEN RETURN false; END IF;
 IF s.parent_id IS NOT NULL AND NOT psl_ppe_mapping_current(s.parent_id) THEN RETURN false; END IF;
 IF NOT EXISTS(SELECT 1 FROM policy_configuration c JOIN policy_registeredreference ref
   ON ref.case_id=c.case_id AND ref.ref=c.envelope->'value'->>'artifact_ref'
    AND ref.version=(c.envelope->'value'->>'artifact_version')::integer AND ref.sha256=c.envelope->'value'->>'sha256'
   WHERE c.id=(s.snapshot->'policies'->'F07.source_rules'->>'id')::bigint
    AND EXTRACT(EPOCH FROM (clock_timestamp()-(r.payload->>'extracted_at')::timestamptz))<=(ref.content->>'max_age_seconds')::numeric)
 THEN RETURN false; END IF;
 prior_id=(s.payload->>'prior_id')::bigint;
 IF prior_id IS NOT NULL AND (NOT psl_ppe_schedule_current(prior_id,depth+1)
  OR NOT psl_ppe_review_current((s.snapshot->'prior'->>2)::bigint)) THEN RETURN false; END IF;
 IF s.snapshot->'owner_validation'->'valid'='true'::jsonb THEN
  FOR pin IN SELECT value FROM jsonb_array_elements(s.snapshot->'owner_validation'->'reviews') LOOP
   IF NOT EXISTS(SELECT 1 FROM documents_validationreview vr JOIN documents_validationpackage vp ON vp.id=vr.package_id
    WHERE vr.id=(pin::text)::bigint AND vr.package_id=(s.snapshot->'owner_validation'->>'id')::bigint
     AND vr.verdict='approve' AND psl_ppe_authority_current(s.case_id,vr.authority)
     AND psl_ppe_grants(s.case_id,vr.actor_id,ARRAY['case.read','validation.read',CASE WHEN vr.kind='acceptance' THEN 'validation.accept' ELSE 'validation.review' END])
     AND vr.id=(SELECT max(id) FROM documents_validationreview WHERE package_id=vr.package_id AND kind=vr.kind)) THEN RETURN false; END IF;
  END LOOP;
 END IF;
 RETURN true;
END $$;

CREATE OR REPLACE FUNCTION psl_factory_identity() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
 IF TG_OP='DELETE' THEN RAISE EXCEPTION 'Factory history cannot be deleted'; END IF;
 IF TG_OP='UPDATE' THEN
  IF (NEW.case_id,NEW.actor_id,NEW.key,NEW.definition,NEW.request,NEW.request_hash,NEW.created_at)
    IS DISTINCT FROM (OLD.case_id,OLD.actor_id,OLD.key,OLD.definition,OLD.request,OLD.request_hash,OLD.created_at)
    OR NEW.budget_used<OLD.budget_used OR NEW.fence<OLD.fence OR NEW.revision<OLD.revision
    OR (OLD.budget_used>0 AND NEW.budget_limit<>OLD.budget_limit)
  THEN RAISE EXCEPTION 'Immutable factory identity and monotonic shared budget required'; END IF;
  IF OLD.source_head_id IS NOT NULL AND NEW.source_head_id IS DISTINCT FROM OLD.source_head_id
   AND (NEW.source_head_id IS NULL OR NOT EXISTS(SELECT 1 FROM core_evidence n JOIN core_evidence o ON o.id=OLD.source_head_id WHERE n.id=NEW.source_head_id AND n.version>o.version))
  THEN RAISE EXCEPTION 'Forward native source successor required'; END IF;
 END IF;
 IF NEW.definition NOT IN ('engagement/v1','pmo-minutes/v1','pmo-finance/v1','planning/v1','commercial/v1','delivery-release/v1','delivery-hypercare/v1','delivery-archive/v1','delivery-handover/v1','delivery-closure/v1','delivery-go-live/v1','finance-accounts/v1','rfp-response/v1','finance-schedules/v1','finance-ppe/v1','pmo-change/v1','finance-forecast/v1','finance-payroll/v1','pmo-emergency/v1','finance-bu/v1','pmo-weekly-report/v1','pmo-escalation/v1') THEN RAISE EXCEPTION 'Closed factory definition required'; END IF;
 IF (NEW.invoice_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM finance_invoice i WHERE i.id=NEW.invoice_id AND i.case_id=NEW.case_id))
  OR (NEW.preparation_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM finance_billingpreparation p WHERE p.id=NEW.preparation_id AND p.case_id=NEW.case_id))
  OR (NEW.policy_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM policy_configuration p WHERE p.id=NEW.policy_id AND p.case_id=NEW.case_id
    AND p.component=CASE NEW.definition WHEN 'engagement/v1' THEN 'OPS.factory_engagement_execution' WHEN 'pmo-minutes/v1' THEN 'OPS.factory_minutes_execution' WHEN 'planning/v1' THEN 'OPS.factory_planning_execution' WHEN 'commercial/v1' THEN 'OPS.factory_commercial_execution' WHEN 'delivery-release/v1' THEN 'OPS.factory_delivery_execution' WHEN 'delivery-hypercare/v1' THEN 'OPS.factory_hypercare_execution' WHEN 'delivery-archive/v1' THEN 'OPS.factory_archive_execution' WHEN 'delivery-handover/v1' THEN 'OPS.factory_handover_execution' WHEN 'delivery-closure/v1' THEN 'OPS.factory_closure_execution' WHEN 'delivery-go-live/v1' THEN 'OPS.factory_go_live_execution' WHEN 'finance-schedules/v1' THEN 'OPS.factory_schedules_execution' WHEN 'pmo-escalation/v1' THEN 'OPS.factory_escalation_execution' WHEN 'finance-ppe/v1' THEN 'OPS.factory_ppe_execution' WHEN 'pmo-change/v1' THEN 'OPS.factory_change_execution' WHEN 'finance-bu/v1' THEN 'OPS.factory_bu_execution' WHEN 'finance-forecast/v1' THEN 'OPS.factory_forecast_execution' WHEN 'finance-payroll/v1' THEN 'OPS.factory_payroll_execution' WHEN 'pmo-emergency/v1' THEN 'OPS.factory_emergency_execution' WHEN 'pmo-weekly-report/v1' THEN 'OPS.factory_reporting_execution' WHEN 'finance-accounts/v1' THEN 'OPS.factory_accounting_execution' WHEN 'rfp-response/v1' THEN 'OPS.factory_rfp_execution' ELSE 'OPS.factory_execution' END))
 THEN RAISE EXCEPTION 'Same-case native factory references required'; END IF;
 IF NEW.definition='pmo-finance/v1' AND NEW.source_head_id IS NOT NULL THEN RAISE EXCEPTION 'Invoice work cannot carry a domain source head'; END IF;
 IF NEW.definition='planning/v1' THEN
  IF NEW.invoice_id IS NOT NULL OR NEW.preparation_id IS NOT NULL OR NOT EXISTS(
    SELECT 1 FROM core_evidence e JOIN core_audit a ON a.case_id=e.case_id AND a.actor_id=e.created_by_id
    WHERE e.id=NEW.source_head_id AND e.case_id=NEW.case_id AND e.kind='planning_packet' AND a.action='planning.recorded'
    AND a.data=jsonb_build_object('kind','packet','evidence_id',e.id,'sha256',e.sha256) AND e.body::jsonb->'engagement_id'=NEW.request->'engagement')
  THEN RAISE EXCEPTION 'Native same-engagement planning packet required'; END IF;
 END IF;
 IF NEW.definition='commercial/v1' THEN
  IF NEW.invoice_id IS NOT NULL OR NEW.preparation_id IS NOT NULL OR NOT EXISTS(
    SELECT 1 FROM core_evidence e JOIN core_audit a ON a.case_id=e.case_id AND a.actor_id=e.created_by_id
    WHERE e.id=NEW.source_head_id AND e.case_id=NEW.case_id AND e.kind='agent_private_commercial_intake'
    AND e.body::jsonb->>'protocol'='factory-commercial-intake/v1' AND a.action='factory.commercial_intake'
    AND a.data=jsonb_build_object('evidence_id',e.id,'sha256',e.sha256))
  THEN RAISE EXCEPTION 'Native private commercial intake required'; END IF;
 END IF;

 IF NEW.definition='delivery-release/v1' THEN
  IF NEW.invoice_id IS NOT NULL OR NEW.preparation_id IS NOT NULL OR NOT EXISTS(
   SELECT 1 FROM core_evidence e JOIN core_audit a ON a.case_id=e.case_id AND a.actor_id=e.created_by_id
   JOIN pmo_deliverydossier d ON d.id=(NEW.request->>'dossier')::bigint
   WHERE e.id=NEW.source_head_id AND e.case_id=NEW.case_id AND e.kind='agent_private_delivery_intake'
    AND d.case_id=NEW.case_id AND e.body::jsonb->>'protocol'='factory-delivery-intake/v1'
    AND e.body::jsonb->>'dossier_id'=d.id::text AND a.action='factory.delivery_intake'
    AND a.data=jsonb_build_object('evidence_id',e.id,'sha256',e.sha256))
  THEN RAISE EXCEPTION 'Native same-case delivery intake and dossier required'; END IF;
 END IF;

 IF NEW.definition='delivery-hypercare/v1' THEN
  IF NEW.invoice_id IS NOT NULL OR NEW.preparation_id IS NOT NULL OR NOT EXISTS(
   SELECT 1 FROM core_evidence e JOIN core_audit a ON a.case_id=e.case_id AND a.actor_id=e.created_by_id
   JOIN pmo_deliverydossier d ON d.id=(NEW.request->>'dossier')::bigint
   WHERE e.id=NEW.source_head_id AND e.case_id=NEW.case_id AND e.kind='agent_private_delivery_intake'
    AND d.case_id=NEW.case_id AND e.body::jsonb->>'protocol'='factory-delivery-intake/v1'
    AND e.body::jsonb->>'dossier_id'=d.id::text AND a.action='factory.delivery_intake'
    AND a.data=jsonb_build_object('evidence_id',e.id,'sha256',e.sha256))
  THEN RAISE EXCEPTION 'Native same-case delivery intake and dossier required'; END IF;
 END IF;

 IF NEW.definition='delivery-archive/v1' THEN
  IF NEW.invoice_id IS NOT NULL OR NEW.preparation_id IS NOT NULL OR NOT EXISTS(
   SELECT 1 FROM core_evidence e JOIN core_audit a ON a.case_id=e.case_id AND a.actor_id=e.created_by_id
   JOIN pmo_deliverydossier d ON d.id=(NEW.request->>'dossier')::bigint
   WHERE e.id=NEW.source_head_id AND e.case_id=NEW.case_id AND e.kind='agent_private_archive_intake'
    AND e.body::jsonb->>'protocol'='factory-archive-intake/v1' AND e.body::jsonb->>'dossier_id'=d.id::text
    AND e.body::jsonb-ARRAY['protocol','dossier_id','inventory']='{}'::jsonb
    AND jsonb_typeof(e.body::jsonb->'inventory')='object' AND d.case_id=NEW.case_id
    AND a.action IN ('factory.archive_intake','factory.archive_source')
    AND a.data=jsonb_build_object('evidence_id',e.id,'sha256',e.sha256))
  THEN RAISE EXCEPTION 'Native same-case declared archive intake and dossier required'; END IF;
 END IF;

 IF NEW.definition='delivery-handover/v1' THEN
  IF NEW.invoice_id IS NOT NULL OR NEW.preparation_id IS NOT NULL OR NOT EXISTS(
   SELECT 1 FROM core_evidence e JOIN core_audit a ON a.case_id=e.case_id AND a.actor_id=e.created_by_id
   JOIN pmo_deliverydossier d ON d.id=(NEW.request->>'dossier')::bigint
   WHERE e.id=NEW.source_head_id AND e.case_id=NEW.case_id AND e.kind='agent_private_handover_intake'
    AND e.body::jsonb->>'protocol'='factory-handover-intake/v1' AND e.body::jsonb->>'dossier_id'=d.id::text
    AND e.body::jsonb-ARRAY['protocol','dossier_id','inputs']='{}'::jsonb
    AND jsonb_typeof(e.body::jsonb->'inputs')='object' AND d.case_id=NEW.case_id
    AND a.action IN ('factory.handover_intake','factory.handover_source')
    AND a.data=jsonb_build_object('evidence_id',e.id,'sha256',e.sha256))
  THEN RAISE EXCEPTION 'Native same-case handover input provenance and dossier required'; END IF;
 END IF;

 IF NEW.definition='delivery-closure/v1' THEN
  IF NEW.invoice_id IS NOT NULL OR NEW.preparation_id IS NOT NULL OR NOT EXISTS(
   SELECT 1 FROM core_evidence e JOIN core_audit a ON a.case_id=e.case_id AND a.actor_id=e.created_by_id
   JOIN pmo_deliverydossier d ON d.id=(NEW.request->>'dossier')::bigint
   WHERE e.id=NEW.source_head_id AND e.case_id=NEW.case_id AND e.kind='agent_private_closure_intake'
    AND e.body::jsonb->>'protocol'='factory-closure-intake/v1' AND e.body::jsonb->>'dossier_id'=d.id::text
    AND e.body::jsonb-ARRAY['protocol','dossier_id','inputs']='{}'::jsonb
    AND jsonb_typeof(e.body::jsonb->'inputs')='object' AND d.case_id=NEW.case_id
    AND a.action IN ('factory.closure_intake','factory.closure_source')
    AND a.data=jsonb_build_object('evidence_id',e.id,'sha256',e.sha256))
  THEN RAISE EXCEPTION 'Native same-case closure input provenance and dossier required'; END IF;
 END IF;

 IF NEW.definition='delivery-go-live/v1' THEN
  IF NEW.invoice_id IS NOT NULL OR NEW.preparation_id IS NOT NULL OR NOT EXISTS(
   SELECT 1 FROM core_evidence e JOIN core_audit a ON a.case_id=e.case_id AND a.actor_id=e.created_by_id
   JOIN pmo_deliverydossier d ON d.id=(NEW.request->>'dossier')::bigint
   WHERE e.id=NEW.source_head_id AND e.case_id=NEW.case_id AND e.kind='agent_private_go_live_intake'
    AND e.body::jsonb->>'protocol'='factory-go-live-intake/v1' AND e.body::jsonb->>'dossier_id'=d.id::text
    AND e.body::jsonb-ARRAY['protocol','dossier_id','inputs']='{}'::jsonb
    AND jsonb_typeof(e.body::jsonb->'inputs')='object' AND d.case_id=NEW.case_id
    AND a.action IN ('factory.go_live_intake','factory.go_live_source')
    AND a.data=jsonb_build_object('evidence_id',e.id,'sha256',e.sha256))
  THEN RAISE EXCEPTION 'Native same-case go_live input provenance and dossier required'; END IF;
 END IF;

 IF NEW.definition='finance-accounts/v1' THEN
  IF NEW.invoice_id IS NOT NULL OR NEW.preparation_id IS NOT NULL OR NOT EXISTS(
   SELECT 1 FROM core_evidence e JOIN finance_financesource s ON s.id=(e.body::jsonb->>'source')::bigint
   JOIN core_audit a ON a.case_id=e.case_id AND a.actor_id=e.created_by_id
   WHERE e.id=NEW.source_head_id AND e.case_id=NEW.case_id AND e.kind='agent_private_accounting_intake'
    AND e.body::jsonb->>'schema'='factory-accounting-intake/v1' AND s.case_id=NEW.case_id
    AND s.batch_id=(NEW.request->>'batch')::bigint AND s.entity=NEW.request->>'entity'
    AND e.body::jsonb->'batch'=NEW.request->'batch' AND e.body::jsonb->'entity'=NEW.request->'entity'
    AND e.body::jsonb->'reference'=NEW.request->'reference'
    AND a.action='factory.accounting_inputs_recorded'
    AND a.data=jsonb_build_object('evidence_id',e.id,'sha256',e.sha256))
  THEN RAISE EXCEPTION 'Native exact accounting intake/source references required'; END IF;
 END IF;

 IF NEW.definition='pmo-change/v1' THEN
  IF NEW.invoice_id IS NOT NULL OR NEW.preparation_id IS NOT NULL OR NOT EXISTS(
   SELECT 1 FROM core_evidence e JOIN core_audit a ON a.case_id=e.case_id AND a.actor_id=e.created_by_id
   JOIN pmo_changeversion v ON v.id=(e.body::jsonb->>'change_version_id')::bigint
   JOIN pmo_changerequest c ON c.id=v.change_id
   WHERE e.id=NEW.source_head_id AND e.case_id=NEW.case_id AND e.kind='agent_private_change_intake'
    AND c.case_id=NEW.case_id AND c.id=(NEW.request->>'change')::bigint
    AND e.body::jsonb->>'protocol'='factory-change-intake/v1'
    AND e.body::jsonb-ARRAY['protocol','change_version_id','inputs']='{}'::jsonb
    AND jsonb_typeof(e.body::jsonb->'inputs')='object'
    AND a.action IN ('factory.change_intake','factory.change_source')
    AND a.data=jsonb_build_object('evidence_id',e.id,'sha256',e.sha256))
  THEN RAISE EXCEPTION 'Exact same-project native change intake provenance required'; END IF;
 END IF;

 IF NEW.definition='pmo-emergency/v1' THEN
  IF NEW.invoice_id IS NOT NULL OR NEW.preparation_id IS NOT NULL OR NOT EXISTS(
   SELECT 1 FROM core_evidence e JOIN core_audit a ON a.case_id=e.case_id AND a.actor_id=e.created_by_id
   JOIN pmo_emergencyprofile ep ON ep.id=(e.body::jsonb->>'profile_id')::bigint
   JOIN pmo_changeversion cv ON cv.id=ep.version_id JOIN pmo_changerequest cr ON cr.id=cv.change_id
   WHERE e.id=NEW.source_head_id AND e.case_id=NEW.case_id AND e.kind='agent_private_emergency_intake'
    AND cr.case_id=NEW.case_id AND cr.id=(NEW.request->>'change')::bigint AND cv.category='Emergency' AND cv.incident_id IS NOT NULL
    AND e.body::jsonb->>'protocol'='factory-emergency-intake/v1'
    AND e.body::jsonb-ARRAY['protocol','profile_id','inputs']='{}'::jsonb
    AND jsonb_typeof(e.body::jsonb->'inputs')='object'
    AND a.action IN ('factory.emergency_intake','factory.emergency_source')
    AND a.data=jsonb_build_object('evidence_id',e.id,'sha256',e.sha256))
  THEN RAISE EXCEPTION 'Exact same-project incident-linked native Emergency source required'; END IF;
 END IF;

 IF NEW.definition='finance-payroll/v1' THEN
  IF NEW.invoice_id IS NOT NULL OR NEW.preparation_id IS NOT NULL OR NOT EXISTS(
   SELECT 1 FROM core_evidence e JOIN core_audit a ON a.case_id=e.case_id AND a.actor_id=e.created_by_id
   JOIN finance_payrollrequest q ON q.id=(e.body::jsonb->>'request_id')::bigint
   WHERE e.id=NEW.source_head_id AND e.case_id=NEW.case_id AND e.kind='agent_private_payroll_intake'
    AND q.case_id=NEW.case_id AND q.reference=NEW.request->>'payroll_reference'
    AND e.body::jsonb->>'protocol'='factory-payroll-intake/v1'
    AND e.body::jsonb-ARRAY['protocol','request_id','inputs']='{}'::jsonb
    AND (e.body::jsonb->'inputs')-ARRAY['input_ids','hr_snapshot_id']='{}'::jsonb
    AND jsonb_array_length(e.body::jsonb->'inputs'->'input_ids')=2
    AND (SELECT count(DISTINCT i.provider) FROM finance_payrollinput i
      WHERE i.id IN (SELECT value::bigint FROM jsonb_array_elements_text(e.body::jsonb->'inputs'->'input_ids'))
       AND i.request_id=q.id AND i.metadata->'accepted'='true'::jsonb)=2
    AND a.action IN ('factory.payroll_intake','factory.payroll_source')
    AND a.data=jsonb_build_object('evidence_id',e.id,'sha256',e.sha256))
  THEN RAISE EXCEPTION 'Exact same-workspace restricted payroll provenance required'; END IF;
 END IF;

 IF NEW.definition='finance-ppe/v1' THEN
  IF NEW.invoice_id IS NOT NULL OR NEW.preparation_id IS NOT NULL OR NOT EXISTS(
   SELECT 1 FROM core_evidence e JOIN core_audit a ON a.case_id=e.case_id AND a.actor_id=e.created_by_id
   JOIN finance_schedulework r ON r.id=(e.body::jsonb->>'register_id')::bigint
   WHERE e.id=NEW.source_head_id AND e.case_id=NEW.case_id AND e.kind='agent_private_ppe_intake'
    AND r.case_id=NEW.case_id AND r.kind='ppe_register' AND r.reference=NEW.request->>'register_reference'
    AND e.body::jsonb->>'protocol'='factory-ppe-intake/v1'
    AND e.body::jsonb-ARRAY['protocol','register_id','prior_id','ledger_id']='{}'::jsonb
    AND a.action IN ('factory.ppe_intake','factory.ppe_source')
    AND a.data=jsonb_build_object('evidence_id',e.id,'sha256',e.sha256))
  THEN RAISE EXCEPTION 'Exact same-case native PPE register provenance required'; END IF;
 END IF;

 IF NEW.definition='finance-schedules/v1' THEN
  IF NEW.invoice_id IS NOT NULL OR NEW.preparation_id IS NOT NULL OR NOT EXISTS(
   SELECT 1 FROM core_evidence e JOIN core_audit a ON a.case_id=e.case_id AND a.actor_id=e.created_by_id
   JOIN core_evidence supplied ON supplied.id=(e.body::jsonb->>'evidence_id')::bigint AND supplied.case_id=e.case_id
   WHERE e.id=NEW.source_head_id AND e.case_id=NEW.case_id AND e.kind='agent_private_schedules_intake'
    AND e.body::jsonb->>'protocol'='factory-schedules-intake/v1' AND e.body::jsonb->>'kind'=NEW.request->>'kind'
    AND e.body::jsonb-ARRAY['protocol','kind','parent_id','evidence_id','payload']='{}'::jsonb
    AND ((NEW.request->>'kind'='inventory' AND supplied.kind='schedule_inventory' AND e.body::jsonb->'payload'='null'::jsonb AND e.body::jsonb->'parent_id'='null'::jsonb)
     OR (NEW.request->>'kind'='income' AND supplied.kind='income_detail' AND EXISTS(SELECT 1 FROM finance_financerun n WHERE n.id=(e.body::jsonb->>'parent_id')::bigint AND n.case_id=NEW.case_id AND n.kind='mapping')))
    AND a.action IN ('factory.schedules_intake','factory.schedules_source') AND a.data=jsonb_build_object('evidence_id',e.id,'sha256',e.sha256))
  THEN RAISE EXCEPTION 'Exact native schedule source provenance required'; END IF;
 END IF;

 IF NEW.definition='pmo-weekly-report/v1' THEN
  IF NEW.invoice_id IS NOT NULL OR NEW.preparation_id IS NOT NULL OR NOT EXISTS(
   SELECT 1 FROM core_evidence e JOIN core_audit a ON a.case_id=e.case_id AND a.actor_id=e.created_by_id
   WHERE e.id=NEW.source_head_id AND e.case_id=NEW.case_id AND e.kind='agent_private_reporting_intake'
    AND e.body::jsonb->>'protocol'='factory-weekly-report-intake/v1'
    AND e.body::jsonb-ARRAY['protocol','inputs','manifest','captured_at']='{}'::jsonb
    AND (e.body::jsonb->'inputs')-ARRAY['template_id','content_id','start_at','end_at']='{}'::jsonb
    AND jsonb_typeof(e.body::jsonb->'manifest')='object'
    AND e.body::jsonb->'inputs'->>'start_at'=NEW.request->>'start_at' AND e.body::jsonb->'inputs'->>'end_at'=NEW.request->>'end_at'
    AND NEW.request->>'kind'='weekly_client' AND NEW.request->>'audience'='client'
    AND a.action IN ('factory.reporting_intake','factory.reporting_source') AND a.data=jsonb_build_object('evidence_id',e.id,'sha256',e.sha256))
  THEN RAISE EXCEPTION 'Exact private selected-period weekly report source required'; END IF;
 END IF;

 IF NEW.definition='pmo-escalation/v1' AND (NEW.invoice_id IS NOT NULL OR NEW.preparation_id IS NOT NULL OR NOT EXISTS(
 SELECT 1 FROM core_evidence e JOIN core_audit a ON a.case_id=e.case_id AND a.actor_id=e.created_by_id
 JOIN pmo_escalationrequest r ON r.id=(psl_escalation_intake(e.id)->>'request_id')::bigint JOIN pmo_escalationprofile ep ON ep.id=r.profile_id
 JOIN pmo_issuestate s ON s.id=ep.state_id JOIN pmo_issue i ON i.id=s.issue_id
 WHERE e.id=NEW.source_head_id AND e.case_id=NEW.case_id AND i.case_id=NEW.case_id AND i.id=(NEW.request->>'issue')::bigint
 AND e.kind='agent_private_escalation_intake' AND psl_escalation_intake(e.id)->>'protocol'='factory-escalation-intake/v1'
 AND (psl_escalation_intake(e.id)-ARRAY['protocol','request_id','profile_id','template_id'])='{}'::jsonb AND psl_escalation_intake(e.id)->>'profile_id'=ep.id::text
 AND r.direction=NEW.request->>'direction' AND r.target=NEW.request->>'target'
 AND a.action IN ('factory.escalation_intake','factory.escalation_source') AND a.data=jsonb_build_object('evidence_id',e.id,'sha256',e.sha256)))
 THEN RAISE EXCEPTION 'Exact same-case source-bound escalation request required'; END IF;

 IF NEW.definition='finance-bu/v1' THEN
  IF NEW.invoice_id IS NOT NULL OR NEW.preparation_id IS NOT NULL OR NOT EXISTS(
   SELECT 1 FROM core_evidence e JOIN core_audit a ON a.case_id=e.case_id AND a.actor_id=e.created_by_id
   WHERE e.id=NEW.source_head_id AND e.case_id=NEW.case_id AND e.kind='agent_private_bu_intake'
    AND e.sha256=encode(sha256(convert_to(e.body,'UTF8')),'hex')
    AND e.body::jsonb->>'protocol'='factory-bu-intake/v1'
    AND e.body::jsonb-ARRAY['protocol','inputs']='{}'::jsonb
    AND (e.body::jsonb->'inputs')-ARRAY['mode','payroll_id','source_id','rule_ids','comparison']='{}'::jsonb
    AND e.body::jsonb->'inputs'->>'mode'=NEW.request->>'mode'
    AND jsonb_array_length(e.body::jsonb->'inputs'->'rule_ids')<=100
    AND a.action IN ('factory.bu_intake','factory.bu_source')
    AND a.data=jsonb_build_object('evidence_id',e.id,'sha256',e.sha256)
    AND ((NEW.request->>'mode'='staff' AND EXISTS(SELECT 1 FROM finance_payrollrun r JOIN finance_payrollrequest q ON q.id=r.request_id
      WHERE r.id=(e.body::jsonb->'inputs'->>'payroll_id')::bigint AND r.kind='match' AND q.case_id=NEW.case_id
       AND q.reference=NEW.request->>'source_reference' AND NEW.request->'scope'=jsonb_build_object('entity',q.metadata->'entity','period',q.metadata->'period','currency',q.metadata->'currency')
       AND e.body::jsonb->'inputs'->'source_id'='null'::jsonb AND e.body::jsonb->'inputs'->'comparison'='null'::jsonb
       AND NOT EXISTS(SELECT 1 FROM jsonb_array_elements_text(e.body::jsonb->'inputs'->'rule_ids') ri WHERE NOT EXISTS(
        SELECT 1 FROM finance_buwork rule WHERE rule.id=ri::bigint AND rule.case_id=NEW.case_id AND rule.kind='rule' AND rule.payroll_id=r.id))))
     OR (NEW.request->>'mode'='event' AND EXISTS(SELECT 1 FROM finance_buwork s
      WHERE s.id=(e.body::jsonb->'inputs'->>'source_id')::bigint AND s.case_id=NEW.case_id AND s.kind='source'
       AND s.reference=NEW.request->>'source_reference' AND s.metadata->'accepted'='true'::jsonb AND s.metadata->'scope'=NEW.request->'scope'
       AND e.body::jsonb->'inputs'->'payroll_id'='null'::jsonb AND e.body::jsonb->'inputs'->'rule_ids'='[]'::jsonb
       AND (e.body::jsonb->'inputs'->'comparison'='null'::jsonb OR EXISTS(SELECT 1 FROM finance_financerun fr
        WHERE fr.id=(e.body::jsonb->'inputs'->'comparison'->>'run_id')::bigint AND fr.case_id=NEW.case_id AND fr.kind='allocation'))))))
  THEN RAISE EXCEPTION 'Exact scoped native BU intake required'; END IF;
 END IF;
 IF NEW.status='verified' THEN
  IF NEW.definition='pmo-finance/v1' AND NOT EXISTS(
    SELECT 1 FROM finance_invoiceissue i JOIN finance_invoicedelivery d ON d.invoice_id=i.invoice_id JOIN finance_invoice n ON n.id=i.invoice_id
    WHERE n.id=NEW.invoice_id AND n.case_id=NEW.case_id AND i.sha256=n.sha256 AND i.payload=n.payload)
  THEN RAISE EXCEPTION 'Native invoice receipts required; agent completion is not verification'; END IF;
  IF NEW.definition='planning/v1' AND NOT EXISTS(
    SELECT 1 FROM pmo_deliverysource s JOIN pmo_deliverydossier d ON d.id=s.dossier_id JOIN core_evidence e ON e.id=s.evidence_id
    JOIN core_audit a ON a.case_id=e.case_id AND a.actor_id=e.created_by_id
    WHERE d.case_id=NEW.case_id AND e.case_id=NEW.case_id AND e.kind='planning_readiness' AND s.kind='scope_baseline'
    AND e.body::jsonb->>'packet_id'=NEW.source_head_id::text AND e.body::jsonb->'inputs'->>'candidate_id'=d.candidate_id::text
    AND s.external_ref='psl:planning-readiness:'||e.id::text AND a.action='planning.recorded'
    AND a.data=jsonb_build_object('kind','ready','evidence_id',e.id,'sha256',e.sha256))
  THEN RAISE EXCEPTION 'Native planning readiness and delivery source required'; END IF;
  IF NEW.definition='commercial/v1' AND NOT EXISTS(
    SELECT 1 FROM pmo_commercialdocumentbinding b JOIN documents_version v ON v.id=b.version_id JOIN documents_document doc ON doc.id=v.document_id
    JOIN documents_publication p ON p.version_id=v.id JOIN pmo_commercialrevision r ON r.id=b.revision_id
    JOIN pmo_commercialcase c ON c.id=r.dossier_id JOIN pmo_costingbinding cb ON cb.costing_id=(r.sources->>'costing')::bigint
    JOIN pmo_costingrun cr ON cr.id=cb.run_id JOIN core_evidence e ON e.id=NEW.source_head_id
    WHERE c.case_id=NEW.case_id AND doc.case_id=NEW.case_id AND cr.case_id=NEW.case_id AND c.current_id=r.id AND cr.result->>'status'='known'
    AND r.sources->'requirements'=e.body::jsonb->'sources'->'requirements' AND r.sources->'plan'=e.body::jsonb->'sources'->'plan'
    AND r.sources->'engineering_estimate'=e.body::jsonb->'sources'->'engineering_estimate' AND r.sources->'security_estimate'=e.body::jsonb->'sources'->'security_estimate'
    AND r.sources->'sow'=e.body::jsonb->'sources'->'sow' AND cr.evidence_id::text=e.body::jsonb->'sources'->>'inputs'
    AND jsonb_array_length(p.recipient_ids)>0 AND NOT EXISTS(
      SELECT 1 FROM jsonb_array_elements_text(p.recipient_ids) AS destinations(recipient) WHERE NOT EXISTS(
       SELECT 1 FROM documents_publicationreceipt pr WHERE pr.publication_id=p.id AND pr.recipient_id::text=destinations.recipient
       AND pr.payload_sha256=v.payload_sha256 AND pr.payload=v.payload)))
  THEN RAISE EXCEPTION 'Exact native costing, commercial document and all recipient receipts required'; END IF;
 END IF;

 IF NEW.definition='delivery-release/v1' AND NEW.status='verified' AND NOT EXISTS(
  SELECT 1 FROM pmo_deliveryrecord r JOIN pmo_deliverydossier d ON d.id=r.dossier_id
  JOIN workflows_factoryactivity fa ON fa.work_id=NEW.id JOIN workflows_factoryattempt a ON a.activity_id=fa.id
  WHERE d.id=(NEW.request->>'dossier')::bigint AND d.case_id=NEW.case_id AND r.kind='release_ready'
   AND r.snapshot->'deployment_authorized'='false'::jsonb AND r.snapshot->>'financial_controls'='independent'
   AND a.phase='observed' AND a.result->>'release_ready'=r.id::text AND a.result->>'head'=NEW.source_head_id::text)
 THEN RAISE EXCEPTION 'Native source-bound release evidence required; no deployment authority is granted'; END IF;

 IF NEW.definition='delivery-hypercare/v1' AND NEW.status='verified' AND NOT EXISTS(
  SELECT 1 FROM pmo_deliveryrecord r JOIN pmo_deliverydossier d ON d.id=r.dossier_id
  JOIN workflows_factoryactivity fa ON fa.work_id=NEW.id JOIN workflows_factoryattempt a ON a.activity_id=fa.id
  WHERE d.id=(NEW.request->>'dossier')::bigint AND d.case_id=NEW.case_id AND r.kind='hypercare'
   AND r.snapshot->'qualified'='true'::jsonb
   AND a.phase='observed' AND a.result->>'hypercare'=r.id::text AND a.result->>'head'=NEW.source_head_id::text)
 THEN RAISE EXCEPTION 'Native source-bound qualified hypercare required; no closure or release authority is granted'; END IF;

 IF NEW.definition='delivery-archive/v1' AND NEW.status='verified' AND NOT EXISTS(
  SELECT 1 FROM pmo_deliveryrecord r JOIN pmo_deliverydossier d ON d.id=r.dossier_id
  JOIN core_evidence e ON e.id=NEW.source_head_id
  JOIN workflows_factoryactivity fa ON fa.work_id=NEW.id JOIN workflows_factoryattempt a ON a.activity_id=fa.id
  WHERE d.id=(NEW.request->>'dossier')::bigint AND d.case_id=NEW.case_id AND r.kind='archive'
   AND r.data->'inventory'=e.body::jsonb->'inventory'
   AND r.snapshot->'physical_purge_performed'='false'::jsonb
   AND r.snapshot->>'repository'='internal-versioned'
   AND a.phase='observed' AND a.result->>'archive'=r.id::text AND a.result->>'head'=NEW.source_head_id::text)
 THEN RAISE EXCEPTION 'Exact observed native archive index required; no physical purge or closure authority'; END IF;

 IF NEW.definition='delivery-handover/v1' AND NEW.status='verified' AND NOT EXISTS(
  SELECT 1 FROM documents_publication p JOIN documents_publicationreceipt r ON r.publication_id=p.id
  JOIN pmo_deliverydocumentbinding b ON b.version_id=p.version_id
  JOIN pmo_deliveryrecord h ON h.dossier_id=b.dossier_id AND h.kind='handover'
  JOIN workflows_factoryactivity fa ON fa.work_id=NEW.id JOIN workflows_factoryattempt a ON a.activity_id=fa.id
  WHERE p.factory_work_id=NEW.id AND p.factory_source_id=NEW.source_head_id AND b.purpose='handover'
   AND b.dossier_id=(NEW.request->>'dossier')::bigint AND h.data->>'receipt_id'=r.id::text
   AND h.data->>'status'='received' AND h.actor_id=r.recipient_id
   AND a.phase='observed' AND fa.kind='ACT13' AND a.result->'verified'='true'::jsonb
   AND a.result->>'publication'=p.id::text AND a.result->>'head'=NEW.source_head_id::text)
 THEN RAISE EXCEPTION 'Observed exact native handover and actual recipient acknowledgement required'; END IF;

 IF NEW.definition='delivery-closure/v1' AND NEW.status='verified' AND NOT EXISTS(
  SELECT 1 FROM pmo_deliveryrecord c JOIN pmo_deliverydocumentbinding b ON b.version_id=(c.data->>'version_id')::bigint
  JOIN documents_version v ON v.id=b.version_id
  JOIN pmo_deliveryrecord decision ON decision.id=(c.data->>'decision_id')::bigint
  JOIN core_evidence head ON head.id=NEW.source_head_id
  JOIN workflows_factoryactivity fa ON fa.work_id=NEW.id AND fa.kind='ACT13'
  JOIN workflows_factoryattempt a ON a.activity_id=fa.id AND a.phase='observed'
  WHERE c.dossier_id=(NEW.request->>'dossier')::bigint AND c.kind='closure' AND b.dossier_id=c.dossier_id AND b.purpose='closure'
   AND decision.dossier_id=c.dossier_id AND decision.kind='closure_decision' AND decision.data->>'verdict'='approve'
   AND decision.data->>'version_id'=v.id::text AND decision.snapshot=b.snapshot AND c.snapshot=b.snapshot
   AND b.data=(head.body::jsonb->'inputs')-'template_id' AND v.template_id=(head.body::jsonb->'inputs'->>'template_id')::bigint
   AND a.result->'verified'='true'::jsonb AND a.result->>'closure'=c.id::text
   AND a.result->>'document_version'=v.id::text AND a.result->>'head'=NEW.source_head_id::text)
 THEN RAISE EXCEPTION 'Observed exact native closure, prescribed decision and current source binding required'; END IF;

 IF NEW.definition='delivery-go-live/v1' AND NEW.status='verified' AND NOT EXISTS(
  SELECT 1 FROM documents_publication p JOIN documents_publicationreceipt r ON r.publication_id=p.id
  JOIN documents_version v ON v.id=p.version_id JOIN pmo_deliverydocumentbinding b ON b.version_id=v.id
  JOIN pmo_deliveryrecord g ON g.dossier_id=b.dossier_id AND g.kind IN ('go_live','go_live_reaffirmation')
  JOIN core_evidence pm ON pm.id=(g.data->>'pm_signature_id')::bigint
  JOIN core_evidence client ON client.id=(g.data->>'client_signature_id')::bigint
  JOIN core_evidence head ON head.id=NEW.source_head_id
  JOIN workflows_factoryactivity fa ON fa.work_id=NEW.id AND fa.kind='ACT13'
  JOIN workflows_factoryattempt a ON a.activity_id=fa.id AND a.phase='observed'
  WHERE p.factory_work_id=NEW.id AND p.factory_source_id=NEW.source_head_id AND b.purpose='go_live' AND v.audience='client'
   AND b.dossier_id=(NEW.request->>'dossier')::bigint AND g.data->>'receipt_id'=r.id::text AND g.snapshot=b.snapshot
   AND b.data=(head.body::jsonb->'inputs')-'template_id' AND v.template_id=(head.body::jsonb->'inputs'->>'template_id')::bigint
   AND pm.case_id=NEW.case_id AND client.case_id=NEW.case_id AND pm.kind='signature' AND client.kind='signature' AND pm.id<>client.id
   AND a.result->'verified'='true'::jsonb AND a.result->>'acceptance'=g.id::text
   AND a.result->>'document_version'=v.id::text AND a.result->>'head'=NEW.source_head_id::text)
 THEN RAISE EXCEPTION 'Observed exact native go-live acceptance, distinct actual signature evidence and source-bound client receipt required'; END IF;

 IF NEW.definition='finance-accounts/v1' AND NEW.status='verified' AND NOT EXISTS(
  SELECT 1 FROM finance_financerun r JOIN finance_financesource s ON s.id=r.source_id
  JOIN finance_financedocumentbinding b ON b.run_id=r.id
  JOIN documents_version v ON v.id=b.version_id JOIN documents_document d ON d.id=v.document_id
  JOIN documents_publication p ON p.version_id=v.id JOIN documents_publicationjob j ON j.publication_id=p.id
  JOIN core_evidence h ON h.id=NEW.source_head_id
  JOIN workflows_factoryactivity fa ON fa.work_id=NEW.id AND fa.kind='ACT13'
  JOIN workflows_factoryattempt a ON a.activity_id=fa.id AND a.phase='observed'
  WHERE r.case_id=NEW.case_id AND s.case_id=NEW.case_id AND d.case_id=NEW.case_id AND r.kind='formula'
   AND s.id=(h.body::jsonb->>'source')::bigint AND s.batch_id=(NEW.request->>'batch')::bigint
   AND (p.factory_work_id=NEW.id AND p.factory_source_id=NEW.source_head_id OR p.factory_work_id IS NULL)
   AND d.current_id=v.id AND j.status='confirmed' AND jsonb_array_length(p.recipient_ids)>0
   AND NOT EXISTS(SELECT 1 FROM jsonb_array_elements_text(p.recipient_ids) x WHERE NOT EXISTS(
    SELECT 1 FROM documents_publicationreceipt pr WHERE pr.publication_id=p.id AND pr.recipient_id=x.value::bigint))
   AND (SELECT count(*) FROM documents_publicationreceipt pr WHERE pr.publication_id=p.id)=jsonb_array_length(p.recipient_ids)
   AND EXISTS(SELECT 1 FROM finance_financereview fr WHERE fr.run_id=r.id AND fr.purpose='output' AND fr.verdict='approve'
    AND fr.id=(SELECT max(last.id) FROM finance_financereview last WHERE last.run_id=r.id AND last.purpose='output'))
   AND a.result->'verified'='true'::jsonb AND a.result->>'run'=r.id::text AND a.result->>'source'=s.id::text
   AND a.result->>'binding'=b.id::text AND a.result->>'publication'=p.id::text AND a.result->>'document_version'=v.id::text
   AND a.result->'receipt_ids'=(SELECT jsonb_agg(pr.id ORDER BY pr.id) FROM documents_publicationreceipt pr WHERE pr.publication_id=p.id)) AND NOT EXISTS(
  SELECT 1 FROM finance_financerun r JOIN finance_financesource s ON s.id=r.source_id
  JOIN finance_financedocumentbinding b ON b.run_id=r.id
  JOIN documents_version v ON v.id=b.version_id JOIN documents_document d ON d.id=v.document_id
  JOIN documents_publication p ON p.version_id=v.id JOIN documents_publicationjob j ON j.publication_id=p.id
  JOIN core_evidence h ON h.id=NEW.source_head_id
  JOIN workflows_factoryactivity fa ON fa.work_id=NEW.id AND fa.kind='ACT13'
  JOIN workflows_factoryattempt a ON a.activity_id=fa.id AND a.phase='observed'
  WHERE r.case_id=NEW.case_id AND s.case_id=NEW.case_id AND d.case_id=NEW.case_id AND r.kind='statement'
   AND s.id=(h.body::jsonb->>'source')::bigint AND s.batch_id=(NEW.request->>'batch')::bigint
   AND (p.factory_work_id=NEW.id AND p.factory_source_id=NEW.source_head_id OR p.factory_work_id IS NULL)
   AND d.current_id=v.id AND j.status='confirmed' AND jsonb_array_length(p.recipient_ids)>0
   AND NOT EXISTS(SELECT 1 FROM jsonb_array_elements_text(p.recipient_ids) x WHERE NOT EXISTS(
    SELECT 1 FROM documents_publicationreceipt pr WHERE pr.publication_id=p.id AND pr.recipient_id=x.value::bigint))
   AND (SELECT count(*) FROM documents_publicationreceipt pr WHERE pr.publication_id=p.id)=jsonb_array_length(p.recipient_ids)
   AND EXISTS(SELECT 1 FROM finance_financereview fr WHERE fr.run_id=r.id AND fr.purpose='output' AND fr.verdict='approve'
    AND fr.id=(SELECT max(last.id) FROM finance_financereview last WHERE last.run_id=r.id AND last.purpose='output'))
   AND a.result->'verified'='true'::jsonb AND a.result->>'run'=r.id::text AND a.result->>'source'=s.id::text
   AND a.result->>'binding'=b.id::text AND a.result->>'publication'=p.id::text AND a.result->>'document_version'=v.id::text
   AND a.result->'receipt_ids'=(SELECT jsonb_agg(pr.id ORDER BY pr.id) FROM documents_publicationreceipt pr WHERE pr.publication_id=p.id)
   AND EXISTS(SELECT 1 FROM policy_configuration pc JOIN policy_registeredreference pr ON pr.case_id=pc.case_id
    AND pr.ref=pc.envelope->'value'->>'artifact_ref' AND pr.version=(pc.envelope->'value'->>'artifact_version')::integer
    AND pr.sha256=pc.envelope->'value'->>'sha256'
    WHERE pc.id=NEW.policy_id AND pc.component='OPS.factory_accounting_execution'
     AND pr.schema_ref='schema:psl/factory-accounting-execution/v3' AND pr.content->>'statement_contract_id'=r.request->>'contract_id')
   AND r.result->>'status'='complete' AND r.result->>'scope'='selected_statement_lines'
   AND r.result->'whole_statement_certified'='false'::jsonb
   AND EXISTS(SELECT 1 FROM finance_financereview cr JOIN policy_configuration cc ON cc.id=cr.configuration_id
    WHERE cc.id=(r.request->>'contract_id')::bigint AND cc.case_id=r.case_id AND cc.component='D06.statement_contract'
     AND cr.purpose='formula' AND cr.verdict='approve'
     AND cr.id=(SELECT max(id) FROM finance_financereview WHERE configuration_id=cc.id AND purpose='formula')
     AND cr.id::text=r.snapshot->'reviews'->'D06.statement_contract'->>'id'
     AND (SELECT state FROM policy_policystate WHERE configuration_id=cc.id ORDER BY id DESC LIMIT 1)='active')
   AND jsonb_array_length(r.snapshot->'inputs')>0
   AND (SELECT count(*) FROM finance_financestatementinput si WHERE si.statement_id=r.id)=jsonb_array_length(r.snapshot->'inputs')
   AND NOT EXISTS(SELECT 1 FROM finance_financestatementinput si
    JOIN finance_financerun sr ON sr.id=si.source_run_id
    JOIN finance_financereview rv ON rv.id=si.source_review_id
    JOIN finance_financesource ss ON ss.id=sr.source_id
    WHERE si.statement_id=r.id AND (sr.case_id<>r.case_id OR rv.run_id<>sr.id OR rv.verdict<>'approve'
     OR rv.id<>(SELECT max(id) FROM finance_financereview WHERE run_id=sr.id AND purpose='output')
     OR sr.result->>'period'<>r.result->>'period' OR sr.result->>'entity'<>r.result->>'entity'
     OR sr.result->>'currency'<>r.result->>'currency' OR ss.accounting_basis IS DISTINCT FROM r.result->>'accounting_basis'
     OR si.declaration->>'source_sign' IS NULL OR si.declaration->>'source_sign' IS DISTINCT FROM si.declaration->>'destination_sign'
     OR sr.result->'company'->si.metric->'value' IS DISTINCT FROM r.result->'company'->si.destination->'value'
     OR sr.result->'company'->si.metric->>'unit' IS DISTINCT FROM si.declaration->>'unit'))
)
 THEN RAISE EXCEPTION 'Current native accounting binding/output review and all exact recipient receipts required'; END IF;

 IF TG_OP='UPDATE' AND NEW.definition IN ('delivery-release/v1','delivery-hypercare/v1')
 AND NEW.source_head_id IS DISTINCT FROM OLD.source_head_id THEN
  IF NEW.cancel_requested OR OLD.status IN ('cancelled','followup_needed') OR NEW.status<>'ready'
   OR (OLD.lease_until IS NOT NULL AND OLD.lease_until>statement_timestamp())
   OR NOT EXISTS(SELECT 1 FROM core_evidence n JOIN core_evidence o ON o.id=OLD.source_head_id
     JOIN core_audit a ON a.case_id=n.case_id AND a.actor_id=n.created_by_id
     JOIN core_evidence e ON e.case_id=n.case_id AND a.data->'evidence'=to_jsonb(e.id)
     WHERE n.id=NEW.source_head_id AND n.body=o.body AND n.version>o.version
      AND a.action='factory.delivery_intake_reaffirmed' AND a.data->>'work'=NEW.id::text
      AND a.data->>'previous'=OLD.source_head_id::text AND a.data->>'current'=n.id::text
      AND length(btrim(a.data->>'reason')) BETWEEN 1 AND 2000
      AND coalesce(a.data->>'packet','') ~ '^[a-f0-9]{64}$')
   OR EXISTS(SELECT 1 FROM workflows_factoryattempt a JOIN workflows_factoryactivity t ON t.id=a.activity_id
     WHERE t.work_id=NEW.id AND t.kind='ACT03' AND a.phase='started' AND a.result->>'schema'='factory-provider-request/v1'
      AND NOT EXISTS(SELECT 1 FROM workflows_factoryattempt done WHERE done.activity_id=a.activity_id AND done.number=a.number AND done.phase IN ('observed','failed'))
      AND NOT EXISTS(SELECT 1 FROM workflows_factoryplanningreceipt WHERE attempt_id=a.id))
  THEN RAISE EXCEPTION 'Exact fresh human source instruction and reconciled original effects required'; END IF;
 END IF;

 IF NEW.definition='rfp-response/v1' THEN
  IF NEW.invoice_id IS NOT NULL OR NEW.preparation_id IS NOT NULL OR NOT EXISTS(
   SELECT 1 FROM core_evidence e JOIN core_audit a ON a.case_id=e.case_id AND a.actor_id=e.created_by_id
   JOIN pmo_rfpcase r ON r.id=(NEW.request->>'rfp')::bigint AND r.case_id=NEW.case_id
   JOIN pmo_rfpintake i ON i.id=(e.body::jsonb->>'intake')::bigint AND i.rfp_id=r.id
   WHERE e.id=NEW.source_head_id AND e.case_id=NEW.case_id AND e.kind='agent_private_rfp_intake'
    AND e.body::jsonb->>'schema'='factory-rfp-intake/v1' AND e.body::jsonb->'rfp'=NEW.request->'rfp'
    AND NEW.request-ARRAY['rfp','reference']='{}'::jsonb
    AND e.body::jsonb-ARRAY['schema','rfp','intake','response_evidence','public_terms','sources','matrix','lessons']='{}'::jsonb
    AND jsonb_typeof(e.body::jsonb->'sources')='object' AND jsonb_typeof(e.body::jsonb->'matrix')='array'
    AND a.action='factory.rfp_inputs_recorded' AND a.data=jsonb_build_object('evidence_id',e.id,'sha256',e.sha256))
  THEN RAISE EXCEPTION 'Exact native same-case RFP instruction provenance required'; END IF;
  IF TG_OP='UPDATE' AND NEW.source_head_id IS DISTINCT FROM OLD.source_head_id THEN
   IF OLD.status IN ('verified','cancelled','followup_needed') OR NEW.cancel_requested OR NEW.status<>'ready'
    OR (OLD.lease_until IS NOT NULL AND OLD.lease_until>statement_timestamp())
    OR NOT EXISTS(SELECT 1 FROM core_audit a JOIN core_evidence e ON e.id=NEW.source_head_id AND e.created_by_id=a.actor_id
      WHERE a.case_id=NEW.case_id AND a.action='factory.rfp_instruction_changed'
       AND a.data->>'work'=NEW.id::text AND a.data->>'previous'=OLD.source_head_id::text
       AND a.data->>'current'=NEW.source_head_id::text AND length(btrim(a.data->>'reason')) BETWEEN 1 AND 4000)
    OR EXISTS(SELECT 1 FROM documents_publication p JOIN documents_publicationjob j ON j.publication_id=p.id
      WHERE p.factory_work_id=NEW.id AND (j.status IN ('pending','unknown','leased','held') OR
       j.status='confirmed' AND NOT EXISTS(SELECT 1 FROM pmo_rfpsubmission s WHERE s.version_id=p.version_id)))
    OR EXISTS(SELECT 1 FROM workflows_factoryattempt a JOIN workflows_factoryactivity t ON t.id=a.activity_id
      WHERE t.work_id=NEW.id AND t.kind='ACT03' AND a.phase='started' AND a.result->>'schema'='factory-provider-request/v1'
       AND NOT EXISTS(SELECT 1 FROM workflows_factoryattempt done WHERE done.activity_id=a.activity_id AND done.number=a.number AND done.phase IN ('observed','failed'))
       AND NOT EXISTS(SELECT 1 FROM workflows_factoryplanningreceipt pr WHERE pr.attempt_id=a.id))
   THEN RAISE EXCEPTION 'Fresh human RFP instruction and reconciled original effects required'; END IF;
  END IF;

  IF NEW.status='verified' AND NOT EXISTS(
   SELECT 1 FROM pmo_rfpdisposition d JOIN pmo_rfpoutcome o ON o.id=d.outcome_id
   JOIN pmo_rfpsubmission s ON s.id=o.submission_id JOIN pmo_rfpresponse r ON r.id=s.response_id
   JOIN pmo_rfpcase root ON root.id=r.rfp_id JOIN core_evidence h ON h.id=NEW.source_head_id
   JOIN pmo_commercialrevision cr ON cr.id=r.commercial_id
   JOIN pmo_rfpdocumentbinding b ON b.response_id=r.id AND b.version_id=s.version_id
   JOIN documents_version v ON v.id=s.version_id JOIN documents_document doc ON doc.id=v.document_id
   JOIN documents_publication p ON p.version_id=v.id JOIN documents_publicationjob j ON j.publication_id=p.id
   JOIN documents_controlledreview review ON review.id=p.review_id AND review.version_id=v.id
   JOIN workflows_factoryactivity t ON t.work_id=NEW.id AND t.kind='ACT13'
   JOIN workflows_factoryattempt a ON a.activity_id=t.id AND a.phase='observed'
   WHERE root.case_id=NEW.case_id AND root.id=(NEW.request->>'rfp')::bigint AND d.rfp_id=root.id
    AND doc.case_id=NEW.case_id AND s.snapshot=b.snapshot AND s.snapshot->>'response'=r.id::text
    AND s.snapshot->'sources'=r.snapshot AND d.snapshot->'sources'=r.snapshot AND d.snapshot->'commercial_sources'=cr.sources
    AND jsonb_array_length(s.snapshot->'reviews')=2 AND NOT EXISTS(
     SELECT 1 FROM jsonb_array_elements_text(s.snapshot->'reviews') WITH ORDINALITY item(id,nth)
     WHERE NOT EXISTS(SELECT 1 FROM pmo_rfpreview rr WHERE rr.id=item.id::bigint AND rr.response_id=r.id AND rr.verdict='approve'
      AND rr.role=CASE item.nth WHEN 1 THEN 'PMO Lead' WHEN 2 THEN 'Engineering Lead' END AND rr.created_at<=p.created_at))
    AND jsonb_array_length(s.snapshot->'costing_decisions')=3 AND NOT EXISTS(
     SELECT 1 FROM jsonb_array_elements_text(s.snapshot->'costing_decisions') WITH ORDINALITY item(id,nth)
     WHERE NOT EXISTS(SELECT 1 FROM pmo_commercialdecision cd WHERE cd.id=item.id::bigint AND cd.revision_id=cr.id AND cd.verdict='approve'
      AND cd.role=CASE item.nth WHEN 1 THEN 'PM' WHEN 2 THEN 'Head of PMO' WHEN 3 THEN 'CEO' END AND cd.created_at<=p.created_at))
    AND review.verdict='approve' AND review.payload_sha256=v.payload_sha256 AND review.created_at<=p.created_at
    AND j.status='confirmed' AND jsonb_array_length(p.recipient_ids)>0
    AND (p.factory_work_id=NEW.id OR p.factory_work_id IS NULL)
    AND (p.factory_work_id IS NULL OR EXISTS(SELECT 1 FROM core_evidence origin WHERE origin.id=p.factory_source_id
     AND origin.case_id=NEW.case_id AND origin.kind='agent_private_rfp_intake' AND origin.body::jsonb->'rfp'=NEW.request->'rfp'))
    AND d.snapshot->>'response'=r.id::text AND d.snapshot->>'submission'=s.id::text AND d.snapshot->>'outcome'=o.id::text
    AND d.snapshot->>'case'=NEW.case_id::text AND d.snapshot->'baseline_imported'='false'::jsonb
    AND (d.kind='route_a' AND o.result='won' AND d.snapshot->>'route'='A' OR
     d.kind='loss_archive' AND o.result='lost' AND d.lessons_id=(h.body::jsonb->>'lessons')::bigint)
    AND NOT EXISTS(SELECT 1 FROM jsonb_array_elements_text(p.recipient_ids) x WHERE NOT EXISTS(
     SELECT 1 FROM documents_publicationreceipt pr WHERE pr.publication_id=p.id AND pr.recipient_id=x.value::bigint AND pr.payload=v.payload AND pr.payload_sha256=v.payload_sha256))
    AND s.receipt_ids=(SELECT jsonb_agg(pr.id ORDER BY pr.id) FROM documents_publicationreceipt pr WHERE pr.publication_id=p.id)
    AND (SELECT count(*) FROM documents_publicationreceipt pr WHERE pr.publication_id=p.id)=jsonb_array_length(p.recipient_ids)
    AND a.result->'verified'='true'::jsonb AND a.result->>'head'=NEW.source_head_id::text
    AND a.result->>'response'=r.id::text AND a.result->>'disposition'=d.id::text AND a.result->>'submission'=s.id::text
    AND a.result->>'outcome'=o.id::text AND a.result->>'document_version'=v.id::text
    AND a.result->>'publication'=p.id::text AND a.result->'receipt_ids'=s.receipt_ids)
  THEN RAISE EXCEPTION 'Historical approved RFP submission, actual customer outcome and all exact receipts required'; END IF;

 END IF;

 IF NEW.definition='pmo-change/v1' AND NEW.status='verified' AND NOT EXISTS(
  SELECT 1 FROM core_evidence e JOIN pmo_changeauthorization ca ON ca.id=(e.body::jsonb->'inputs'->>'authorization_id')::bigint
  JOIN pmo_changeversion cv ON cv.id=ca.version_id JOIN pmo_changerequest cr ON cr.id=cv.change_id
  JOIN pmo_changeclosure cc ON cc.authorization_id=ca.id
  JOIN documents_publicationreceipt r ON r.id=cc.receipt_id JOIN documents_publication p ON p.id=r.publication_id
  JOIN pmo_changedocumentbinding b ON b.version_id=p.version_id AND b.authorization_id=ca.id AND b.purpose='go_live'
  JOIN workflows_factoryactivity fa ON fa.work_id=NEW.id AND fa.kind='ACT13'
  JOIN workflows_factoryattempt a ON a.activity_id=fa.id AND a.phase='observed'
  WHERE e.id=NEW.source_head_id AND cv.id=(e.body::jsonb->>'change_version_id')::bigint
   AND cr.case_id=NEW.case_id AND cr.current_id=cv.id AND cr.id=(NEW.request->>'change')::bigint
   AND p.factory_work_id=NEW.id AND p.factory_source_id=e.id
   AND cc.execution_ids=b.execution_ids AND cc.pm_signature_id<>cc.client_signature_id
   AND a.result->'verified'='true'::jsonb AND a.result->>'head'=e.id::text AND a.result->>'closure'=cc.id::text
   AND a.result->>'document_version'=p.version_id::text
   AND EXISTS(SELECT 1 FROM documents_publication np JOIN pmo_changedocumentbinding nb ON nb.version_id=np.version_id
    JOIN documents_publicationreceipt nr ON nr.publication_id=np.id
    WHERE np.factory_work_id=NEW.id AND np.factory_source_id=e.id AND nb.authorization_id=ca.id AND nb.purpose='notice')
   AND NOT EXISTS(SELECT 1 FROM jsonb_array_elements_text(p.recipient_ids) recipient
    WHERE NOT EXISTS(SELECT 1 FROM documents_publicationreceipt pr WHERE pr.publication_id=p.id AND pr.recipient_id=recipient::bigint)))
 THEN RAISE EXCEPTION 'Observed exact native change closure and controlled recipient receipts required'; END IF;

 IF NEW.definition='pmo-emergency/v1' AND NEW.status='verified' AND NOT EXISTS(
  SELECT 1 FROM core_evidence e JOIN pmo_emergencyprofile ep ON ep.id=(e.body::jsonb->>'profile_id')::bigint
  JOIN pmo_emergencyoutcome o ON o.id=(e.body::jsonb->'inputs'->>'outcome_id')::bigint AND o.profile_id=ep.id
  JOIN pmo_emergencyauthorization ea ON ea.id=o.authorization_id AND ea.profile_id=ep.id
  JOIN pmo_emergencyretrospectiverecord rr ON rr.outcome_id=o.id
  JOIN pmo_changeversion cv ON cv.id=ep.version_id JOIN pmo_changerequest cr ON cr.id=cv.change_id
  JOIN pmo_emergencydocumentbinding b ON b.outcome_id=o.id
  JOIN documents_version v ON v.id=b.version_id JOIN documents_publication p ON p.version_id=v.id
  JOIN workflows_factoryactivity fa ON fa.work_id=NEW.id AND fa.kind='ACT13'
  JOIN workflows_factoryattempt a ON a.activity_id=fa.id AND a.phase='observed'
  WHERE e.id=NEW.source_head_id AND cr.case_id=NEW.case_id AND cr.id=(NEW.request->>'change')::bigint AND cr.current_id=cv.id
   AND ea.id=(e.body::jsonb->'inputs'->>'authorization_id')::bigint AND ea.created_at<=o.implemented_at
   AND rr.snapshot->>'authorization_id'=ea.id::text AND rr.snapshot->>'status' IN ('evidenced_on_time','completed_with_lateness_exception')
   AND b.manifest->>'reconciliation_id'=rr.id::text AND b.manifest->>'outcome_id'=o.id::text
   AND p.factory_work_id=NEW.id AND p.factory_source_id=e.id AND v.template_id=(e.body::jsonb->'inputs'->>'template_id')::bigint
   AND v.audience=e.body::jsonb->'inputs'->>'audience'
   AND a.result->'verified'='true'::jsonb AND a.result->>'head'=e.id::text AND a.result->>'retrospective_record'=rr.id::text
   AND a.result->>'document_version'=v.id::text AND a.result->>'retrospective_status'=rr.snapshot->>'status'
   AND EXISTS(SELECT 1 FROM documents_publicationreceipt pr WHERE pr.publication_id=p.id)
   AND NOT EXISTS(SELECT 1 FROM jsonb_array_elements_text(p.recipient_ids) recipient
    WHERE NOT EXISTS(SELECT 1 FROM documents_publicationreceipt pr WHERE pr.publication_id=p.id AND pr.recipient_id=recipient::bigint)))
 THEN RAISE EXCEPTION 'Observed exact native Emergency retrospective and every report receipt required; deployment and ordinary closure are not granted'; END IF;

 IF NEW.definition='finance-payroll/v1' AND NEW.status='verified' AND NOT EXISTS(
  SELECT 1 FROM core_evidence e JOIN finance_payrollrequest q ON q.id=(e.body::jsonb->>'request_id')::bigint
   JOIN finance_payrollrun ar ON ar.request_id=q.id AND ar.kind='aggregate'
   JOIN finance_payrollrun mr ON mr.id=ar.parent_id AND mr.kind='match'
   JOIN finance_payrollrun cr ON cr.id=mr.parent_id AND cr.kind='combine'
   JOIN finance_payrollpublication p ON p.run_id=ar.id AND p.request_id=q.id
   JOIN finance_payrollreview rv ON rv.id=p.review_id AND rv.run_id=ar.id
   JOIN workflows_factoryactivity fa ON fa.work_id=NEW.id AND fa.kind='ACT13'
   JOIN workflows_factoryattempt a ON a.activity_id=fa.id AND a.phase='observed'
   JOIN policy_configuration pc ON pc.id=(p.policy_ids->>'F18.reporting_rules')::bigint
   JOIN policy_registeredreference pr ON pr.case_id=pc.case_id AND pr.ref=pc.envelope->'value'->>'artifact_ref'
    AND pr.version=(pc.envelope->'value'->>'artifact_version')::integer AND pr.sha256=pc.envelope->'value'->>'sha256'
  WHERE e.id=NEW.source_head_id AND q.case_id=NEW.case_id AND q.reference=NEW.request->>'payroll_reference'
   AND cr.request_id=q.id AND mr.request_id=q.id
   AND (cr.metadata->'input_ids') @> (e.body::jsonb->'inputs'->'input_ids')
   AND (cr.metadata->'input_ids') <@ (e.body::jsonb->'inputs'->'input_ids')
   AND mr.hr_snapshot_id=(e.body::jsonb->'inputs'->>'hr_snapshot_id')::bigint
   AND ar.metadata->>'status'='complete' AND mr.metadata->>'status'='complete' AND cr.metadata->>'status'='complete'
   AND rv.verdict='approve' AND rv.subject_sha256=ar.sha256
   AND rv.id=(SELECT max(id) FROM finance_payrollreview WHERE run_id=ar.id)
   AND p.payload->'by_bu'=ar.result->'by_bu' AND p.payload->'eligible_total'=ar.result->'eligible_total'
   AND p.payload->>'source_run'=ar.id::text AND p.payload->>'disclosure'='aggregate_only'
   AND NOT (p.payload ? 'rows') AND p.payload->'hr_written'='false'::jsonb AND p.payload->'ledger_posted'='false'::jsonb
   AND NOT EXISTS(SELECT 1 FROM finance_payrollpublication newer WHERE newer.request_id=q.id AND newer.version>p.version)
   AND NOT EXISTS(SELECT 1 FROM finance_payrollrequest newer WHERE newer.case_id=q.case_id AND newer.reference=q.reference AND newer.version>q.version)
   AND a.result->'verified'='true'::jsonb AND a.result->>'head'=e.id::text AND a.result->>'publication'=p.id::text
   AND a.result->>'run'=ar.id::text AND a.result->>'request'=q.id::text
   AND jsonb_array_length(pr.content->'recipient_ids')>0
   AND NOT EXISTS(SELECT 1 FROM jsonb_array_elements_text(pr.content->'recipient_ids') recipient
     WHERE NOT EXISTS(SELECT 1 FROM finance_payrollreportreceipt rr WHERE rr.publication_id=p.id AND rr.actor_id=recipient::bigint
       AND a.result->'receipt_ids' @> to_jsonb(ARRAY[rr.id]))))
 THEN RAISE EXCEPTION 'Observed exact payroll aggregate and actual recipient-owned receipts required'; END IF;

 IF NEW.definition='finance-forecast/v1' AND NOT EXISTS(
  SELECT 1 FROM core_evidence e JOIN core_audit a ON a.case_id=e.case_id AND a.actor_id=e.created_by_id
  JOIN finance_forecastscenario s ON s.id=(e.body::jsonb->>'scenario_id')::bigint
  WHERE e.id=NEW.source_head_id AND e.case_id=NEW.case_id AND s.case_id=NEW.case_id
   AND e.kind='agent_private_forecast_intake' AND e.body::jsonb->>'protocol'='factory-forecast-selection/v1'
   AND s.reference=NEW.request->>'scenario_reference'
   AND e.body::jsonb-ARRAY['protocol','scenario_id','as_of','months','source_ids','template_id','audience']='{}'::jsonb
   AND e.body::jsonb->>'audience' IN ('internal','management','group')
   AND jsonb_typeof(e.body::jsonb->'source_ids')='array'
   AND jsonb_array_length(e.body::jsonb->'source_ids')=(SELECT count(*) FROM (
    SELECT s.evidence_id AS id UNION SELECT (item->>'evidence_id')::bigint FROM jsonb_array_elements(s.payload->'openings') item
    UNION SELECT (item->>'evidence_id')::bigint FROM jsonb_array_elements(s.payload->'items') item) exact_sources)
   AND NOT EXISTS(SELECT id FROM (
    SELECT s.evidence_id AS id UNION SELECT (item->>'evidence_id')::bigint FROM jsonb_array_elements(s.payload->'openings') item
    UNION SELECT (item->>'evidence_id')::bigint FROM jsonb_array_elements(s.payload->'items') item) exact_sources
    WHERE NOT e.body::jsonb->'source_ids' @> jsonb_build_array(id))
   AND (e.body::jsonb->'template_id'='null'::jsonb OR EXISTS(SELECT 1 FROM documents_template t
    WHERE t.id=(e.body::jsonb->>'template_id')::bigint AND t.case_id=NEW.case_id AND t.definition->>'document_type'=CASE WHEN e.body::jsonb->>'audience'='group' THEN 'finance_group_report' ELSE 'finance_report' END))
   AND e.body::jsonb->>'as_of'=s.payload->>'as_of' AND e.body::jsonb->'months'=s.payload->'months'
   AND a.action IN ('factory.forecast_intake','factory.forecast_source')
   AND a.data=jsonb_build_object('evidence_id',e.id,'sha256',e.sha256)
   AND NEW.invoice_id IS NULL AND NEW.preparation_id IS NULL)
 THEN RAISE EXCEPTION 'Exact native forecast intake provenance required'; END IF;
 IF NEW.definition='finance-forecast/v1' AND NEW.status='verified' AND NOT EXISTS(
  SELECT 1 FROM core_evidence e JOIN finance_forecastscenario s ON s.id=(e.body::jsonb->>'scenario_id')::bigint
  JOIN finance_forecastrun r ON r.scenario_id=s.id JOIN finance_forecastreview rv ON rv.run_id=r.id
  JOIN finance_forecastbinding b ON b.run_id=r.id JOIN documents_version v ON v.id=b.version_id
  JOIN documents_publication p ON p.version_id=v.id
  JOIN workflows_factoryactivity fa ON fa.work_id=NEW.id AND fa.kind='ACT13'
  JOIN workflows_factoryattempt a ON a.activity_id=fa.id AND a.phase='observed'
  WHERE e.id=NEW.source_head_id AND r.case_id=NEW.case_id AND s.case_id=NEW.case_id
   AND rv.verdict='approve' AND rv.id=(SELECT max(id) FROM finance_forecastreview WHERE run_id=r.id)
   AND NOT EXISTS(SELECT 1 FROM finance_forecastscenario newer WHERE newer.case_id=s.case_id AND newer.reference=s.reference AND newer.number>s.number)
   AND p.factory_work_id=NEW.id AND p.factory_source_id=e.id AND p.factory_policy_id=NEW.policy_id
   AND v.template_id=(e.body::jsonb->>'template_id')::bigint AND v.audience=e.body::jsonb->>'audience'
   AND b.snapshot->>'run_hash'=r.sha256 AND b.snapshot->>'output_review'=rv.id::text
   AND a.result->'verified'='true'::jsonb AND a.result->>'head'=e.id::text
   AND a.result->>'forecast_run'=r.id::text AND a.result->>'forecast_review'=rv.id::text
   AND a.result->>'document_version'=v.id::text AND a.result->>'publication'=p.id::text
   AND jsonb_array_length(p.recipient_ids)>0
   AND NOT EXISTS(SELECT 1 FROM jsonb_array_elements_text(p.recipient_ids) recipient WHERE NOT EXISTS(
    SELECT 1 FROM documents_publicationreceipt pr WHERE pr.publication_id=p.id AND pr.recipient_id=recipient::bigint
     AND pr.payload_sha256=v.payload_sha256 AND pr.payload=v.payload)))
 THEN RAISE EXCEPTION 'Observed exact native forecast approval and aggregate receipts required'; END IF;

 IF NEW.definition='finance-ppe/v1' AND NEW.status='verified' AND NOT EXISTS(
  SELECT 1 FROM core_evidence e
  JOIN finance_schedulework r ON r.id=(e.body::jsonb->>'register_id')::bigint
  JOIN finance_schedulework s ON s.case_id=NEW.case_id AND s.kind='ppe_schedule'
  JOIN finance_schedulereview sr ON sr.work_id=s.id AND sr.authority->>'purpose'='schedule'
  JOIN finance_schedulereview rr ON rr.work_id=r.id AND rr.authority->>'purpose'='register'
  JOIN workflows_factoryactivity fa ON fa.work_id=NEW.id AND fa.kind='ACT13'
  JOIN workflows_factoryattempt a ON a.activity_id=fa.id AND a.phase='observed'
  WHERE e.id=NEW.source_head_id AND s.payload->>'register_id'=r.id::text
   AND s.payload->'prior_id'=e.body::jsonb->'prior_id'
   AND s.parent_id IS NOT DISTINCT FROM (e.body::jsonb->>'ledger_id')::bigint
   AND s.reference=NEW.request->>'reference' AND s.result->>'status'='ready'
   AND psl_ppe_schedule_current(s.id) AND psl_ppe_review_current(sr.id)
   AND psl_ppe_policy_current(NEW.case_id,NEW.policy_id)
   AND psl_ppe_grants(NEW.case_id,e.created_by_id,ARRAY['case.read','finance.read','ppe.read','evidence.add'])
   AND EXISTS(SELECT 1 FROM core_audit intake WHERE intake.case_id=NEW.case_id AND intake.actor_id=e.created_by_id
    AND intake.data=jsonb_build_object('evidence_id',e.id,'sha256',e.sha256)
    AND ((intake.action='factory.ppe_intake' AND psl_ppe_grants(NEW.case_id,e.created_by_id,ARRAY['factory.start']))
     OR (intake.action='factory.ppe_source' AND psl_ppe_grants(NEW.case_id,e.created_by_id,ARRAY['factory.manage']))))
   AND sr.verdict='approve' AND rr.verdict='approve' AND sr.snapshot=s.snapshot AND rr.snapshot=r.snapshot
   AND sr.id=(SELECT max(id) FROM finance_schedulereview WHERE work_id=s.id AND authority->>'purpose'='schedule')
   AND rr.id=(SELECT max(id) FROM finance_schedulereview WHERE work_id=r.id AND authority->>'purpose'='register')
   AND NOT EXISTS(SELECT 1 FROM finance_schedulework newer WHERE newer.case_id=NEW.case_id AND
     ((newer.kind=r.kind AND newer.reference=r.reference AND newer.version>r.version) OR
      (newer.kind=s.kind AND newer.reference=s.reference AND newer.version>s.version)))
   AND a.result->'verified'='true'::jsonb AND a.result->>'head'=e.id::text
   AND a.result->>'schedule'=s.id::text AND a.result->>'schedule_sha256'=s.sha256
   AND a.result->>'schedule_review'=sr.id::text AND a.result->>'register_review'=rr.id::text
   AND a.result->'ledger'=COALESCE(to_jsonb(s.parent_id),'null'::jsonb)
   AND a.result->'ledger_posted'='false'::jsonb
   AND a.result->>'full_owner_oracle_acceptance'='unresolved'
   AND (s.parent_id IS NULL OR EXISTS(SELECT 1 FROM finance_financerun note
     JOIN finance_financereview source_review ON source_review.source_id=note.source_id AND source_review.purpose='source'
     WHERE note.id=s.parent_id AND note.case_id=NEW.case_id AND note.kind='mapping'
      AND source_review.verdict='approve'
      AND source_review.id=(SELECT max(id) FROM finance_financereview WHERE source_id=note.source_id AND purpose='source')
      AND note.snapshot->'source_review'->>'id'=source_review.id::text
      AND a.result->'ledger_reviews'=jsonb_build_object('source',note.snapshot->'source_review','rules',note.snapshot->'reviews')))
   AND s.snapshot->>'register_review'=rr.id::text
   AND NOT EXISTS(SELECT 1 FROM jsonb_each(s.snapshot->'policies') pin
     WHERE pin.value->>'status'<>'ACTIVE' OR NOT EXISTS(SELECT 1 FROM policy_configuration pc
      WHERE pc.id=(pin.value->>'id')::bigint AND pc.case_id=NEW.case_id AND pc.component=pin.key
       AND (SELECT state FROM policy_policystate WHERE configuration_id=pc.id ORDER BY id DESC LIMIT 1)='active'))
   AND NOT EXISTS(SELECT 1 FROM (VALUES(sr.actor_id),(rr.actor_id)) reviewer(id)
     WHERE NOT EXISTS(SELECT 1 FROM auth_user u JOIN identity_grant g ON g.user_id=u.id
      WHERE u.id=reviewer.id AND u.is_active AND g.case_id=NEW.case_id AND g.action='ppe.review' AND g.active)))
 THEN RAISE EXCEPTION 'Observed exact current human-reviewed PPE schedule and accounting note required'; END IF;

 IF NEW.definition='finance-schedules/v1' AND NEW.status='verified' AND NOT EXISTS(
  SELECT 1 FROM core_evidence e JOIN core_evidence supplied ON supplied.id=(e.body::jsonb->>'evidence_id')::bigint
  JOIN finance_schedulework s ON s.evidence_id=supplied.id AND s.case_id=NEW.case_id AND s.kind=NEW.request->>'kind' AND s.reference=NEW.request->>'reference'
  JOIN finance_schedulereview r ON r.work_id=s.id
  JOIN workflows_factoryactivity fa ON fa.work_id=NEW.id AND fa.kind='ACT13'
  JOIN workflows_factoryattempt a ON a.activity_id=fa.id AND a.phase='observed'
  WHERE e.id=NEW.source_head_id AND s.parent_id IS NOT DISTINCT FROM (e.body::jsonb->>'parent_id')::bigint
   AND s.payload=CASE WHEN s.kind='income' THEN e.body::jsonb->'payload' ELSE supplied.body::jsonb END
   AND s.result->>'status'='ready' AND psl_schedules_review_current(r.id)
   AND psl_schedules_policy_current(NEW.case_id,NEW.policy_id)
   AND psl_schedules_grants(NEW.case_id,e.created_by_id,ARRAY['case.read','finance.read','schedules.read','evidence.add'])
   AND EXISTS(SELECT 1 FROM core_audit intake WHERE intake.case_id=NEW.case_id AND intake.actor_id=e.created_by_id
    AND intake.data=jsonb_build_object('evidence_id',e.id,'sha256',e.sha256)
    AND ((intake.action='factory.schedules_intake' AND psl_schedules_grants(NEW.case_id,e.created_by_id,ARRAY['factory.start']))
     OR (intake.action='factory.schedules_source' AND psl_schedules_grants(NEW.case_id,e.created_by_id,ARRAY['factory.manage']))))
   AND a.result->'verified'='true'::jsonb AND a.result->>'head'=e.id::text
   AND a.result->>'schedule'=s.id::text AND a.result->>'schedule_sha256'=s.sha256
   AND a.result->>'schedule_review'=r.id::text AND a.result->>'source_evidence'=supplied.id::text
   AND a.result->'parent'=COALESCE(to_jsonb(s.parent_id),'null'::jsonb)
   AND a.result->'ledger_posted'='false'::jsonb AND a.result->'native_workbook_verified'='false'::jsonb)
 THEN RAISE EXCEPTION 'Observed exact current human-reviewed selected schedule required'; END IF;

 IF TG_OP='UPDATE' AND NEW.definition='finance-forecast/v1' AND NEW.source_head_id IS DISTINCT FROM OLD.source_head_id
 AND ((SELECT body::jsonb->>'audience'='group' FROM core_evidence WHERE id=NEW.source_head_id)
 IS DISTINCT FROM (SELECT body::jsonb->>'audience'='group' FROM core_evidence WHERE id=OLD.source_head_id))
 THEN RAISE EXCEPTION 'Separate group audience work identity is immutable'; END IF;

 IF NEW.definition='pmo-weekly-report/v1' AND NEW.status='verified' AND NOT EXISTS(
  SELECT 1 FROM documents_publication p JOIN documents_version v ON v.id=p.version_id
  JOIN documents_controlledreview rv ON rv.id=p.review_id
  JOIN workflows_factoryactivity fa ON fa.work_id=NEW.id AND fa.kind='ACT13'
  JOIN workflows_factoryattempt a ON a.activity_id=fa.id AND a.phase='observed'
  WHERE p.factory_work_id=NEW.id AND p.factory_source_id=NEW.source_head_id AND p.factory_policy_id=NEW.policy_id
   AND psl_reporting_document(NEW.id,NEW.source_head_id,v.id)
   AND rv.version_id=v.id AND rv.verdict='approve' AND rv.payload_sha256=v.payload_sha256
   AND rv.id=(SELECT max(id) FROM documents_controlledreview WHERE version_id=v.id)
   AND psl_reporting_review(NEW.case_id,rv.id)
   AND psl_reporting_principals(NEW.id,v.id,p.actor_id)
   AND psl_reporting_distribution(NEW.case_id,v.id,p.policies,p.recipient_ids,p.retention_days)
   AND psl_reporting_grants(NEW.case_id,p.actor_id,ARRAY['case.read','report.read','factory.execute','document.publish'])
   AND a.result->'verified'='true'::jsonb AND a.result->>'head'=NEW.source_head_id::text AND a.result->>'document_version'=v.id::text
   AND a.result->>'publication'=p.id::text AND a.result->'complete_project_coverage'='false'::jsonb AND a.result->'external_delivery_verified'='false'::jsonb AND a.result->'business_approval_granted'='false'::jsonb
   AND jsonb_array_length(p.recipient_ids)>0
   AND (SELECT count(*) FROM documents_publicationreceipt WHERE publication_id=p.id)=jsonb_array_length(p.recipient_ids)
   AND NOT EXISTS(SELECT 1 FROM jsonb_array_elements_text(p.recipient_ids) recipient WHERE NOT EXISTS(
    SELECT 1 FROM documents_publicationreceipt pr WHERE pr.publication_id=p.id AND pr.recipient_id=recipient::bigint
     AND pr.payload=v.payload AND pr.payload_sha256=v.payload_sha256 AND psl_reporting_grants(NEW.case_id,pr.recipient_id,ARRAY['document.receive:client']))))
 THEN RAISE EXCEPTION 'Observed exact current weekly client report, native PMO Lead review and every recipient receipt required'; END IF;

 IF NEW.definition='pmo-escalation/v1' AND NEW.status='verified' AND NOT EXISTS(
 SELECT 1 FROM documents_publication p JOIN documents_version v ON v.id=p.version_id JOIN documents_publicationjob j ON j.publication_id=p.id
 JOIN pmo_escalationdocumentbinding b ON b.version_id=v.id JOIN pmo_escalationrequest r ON r.id=b.request_id JOIN pmo_escalationprofile ep ON ep.id=r.profile_id
 JOIN workflows_factoryactivity fa ON fa.work_id=NEW.id AND fa.kind='ACT13' JOIN workflows_factoryattempt a ON a.activity_id=fa.id AND a.phase='observed'
 WHERE p.factory_work_id=NEW.id AND p.factory_source_id=NEW.source_head_id AND p.factory_policy_id=NEW.policy_id AND j.status='confirmed'
 AND psl_escalation_document(NEW.id,v.id,p.review_id,p.actor_id,p.factory_policy_id,p.factory_source_id,p.recipient_ids,p.policies)
 AND a.result->'verified'='true'::jsonb AND a.result->'issue_resolution_verified'='false'::jsonb AND a.result->>'head'=NEW.source_head_id::text
 AND a.result->>'verification_scope'='reviewed_escalation_communication' AND a.result->>'request'=r.id::text AND a.result->>'profile'=ep.id::text AND a.result->>'issue_state'=ep.state_id::text
 AND a.result->'decision'=COALESCE(to_jsonb(b.decision_id),'null'::jsonb) AND a.result->>'direction'=r.direction AND a.result->>'target'=r.target
 AND a.result->>'document_version'=v.id::text AND a.result->>'publication'=p.id::text
 AND a.result->'receipt_ids'=(SELECT jsonb_agg(pr.id ORDER BY pr.id) FROM documents_publicationreceipt pr WHERE pr.publication_id=p.id)
 AND (SELECT count(*) FROM documents_publicationreceipt WHERE publication_id=p.id)=jsonb_array_length(p.recipient_ids)
 AND NOT EXISTS(SELECT 1 FROM jsonb_array_elements_text(p.recipient_ids) recipient WHERE NOT EXISTS(SELECT 1 FROM documents_publicationreceipt pr WHERE pr.publication_id=p.id AND pr.recipient_id=recipient::bigint AND pr.payload=v.payload AND pr.payload_sha256=v.payload_sha256)))
 THEN RAISE EXCEPTION 'Observed exact current communication and every receipt required; issue resolution is not verified'; END IF;

 IF NEW.definition='pmo-minutes/v1' THEN
  IF NEW.invoice_id IS NOT NULL OR NEW.preparation_id IS NOT NULL OR NOT EXISTS(
   SELECT 1 FROM core_evidence e JOIN core_audit a ON a.case_id=e.case_id AND a.actor_id=e.created_by_id
   JOIN core_evidence note ON note.id=(e.body::jsonb->>'evidence_id')::bigint AND note.case_id=e.case_id
   JOIN documents_template t ON t.id=(e.body::jsonb->>'template_id')::bigint AND t.case_id=e.case_id
   WHERE e.id=NEW.source_head_id AND e.case_id=NEW.case_id AND e.kind='agent_private_minutes_intake'
    AND e.body::jsonb->>'protocol'='factory-minutes-intake/v1' AND note.kind='meeting_notes'
    AND t.definition->>'document_type'='minutes' AND t.definition->'audience_fields' ? (e.body::jsonb->>'audience')
    AND (e.body::jsonb->>'audience'='internal' AND e.body::jsonb->'publish'='false'::jsonb OR e.body::jsonb->>'audience'='client' AND e.body::jsonb->'publish'='true'::jsonb)
    AND e.body::jsonb - ARRAY['protocol','meeting_version_id','evidence_id','template_id','audience','publish']='{}'::jsonb
    AND a.action IN ('factory.minutes_intake','factory.minutes_source')
    AND a.data=jsonb_build_object('evidence_id',e.id,'sha256',e.sha256)
    AND encode(sha256(convert_to(e.body,'UTF8')),'hex')=e.sha256)
   THEN RAISE EXCEPTION 'Exact authorized typed formal-minutes intake required'; END IF;
  IF NEW.status='verified' AND NOT EXISTS(
   SELECT 1 FROM workflows_factoryactivity fa JOIN workflows_factoryattempt a ON a.activity_id=fa.id
   WHERE fa.work_id=NEW.id AND fa.kind='ACT13' AND a.phase='observed'
    AND a.result->'verified'='true'::jsonb AND a.result->>'head'=NEW.source_head_id::text
    AND a.result->'actions_completed'='false'::jsonb AND a.result->'scope_changed'='false'::jsonb
    AND psl_minutes_current(NEW.id,NEW.source_head_id,(a.result->>'document_version')::bigint)
    AND psl_schedules_policy_current(NEW.case_id,NEW.policy_id)
    AND a.result->'manifest'=(SELECT manifest FROM pmo_minutesreportbinding WHERE version_id=(a.result->>'document_version')::bigint)
    AND ((SELECT body::jsonb->'publish' FROM core_evidence WHERE id=NEW.source_head_id)='false'::jsonb OR EXISTS(
     SELECT 1 FROM documents_publication p JOIN documents_controlledreview r ON r.id=p.review_id JOIN documents_version v ON v.id=p.version_id
     WHERE p.id=(a.result->>'publication')::bigint AND p.version_id=(a.result->>'document_version')::bigint
      AND p.factory_work_id=NEW.id AND p.factory_source_id=NEW.source_head_id AND p.factory_policy_id=NEW.policy_id
      AND r.version_id=v.id AND r.verdict='approve' AND r.payload_sha256=v.payload_sha256
      AND r.id=(SELECT max(id) FROM documents_controlledreview WHERE version_id=v.id)
      AND psl_schedules_authority_current(NEW.case_id,r.authority)
      AND psl_schedules_grants(NEW.case_id,r.actor_id,ARRAY['document.review_controlled'])
      AND psl_schedules_authority_current(NEW.case_id,p.policies)
      AND p.actor_id=(psl_schedules_values(NEW.policy_id)->0->>'executor_id')::bigint
      AND psl_schedules_grants(NEW.case_id,p.actor_id,ARRAY['case.read','meeting.read','factory.execute','document.publish'])
      AND p.recipient_ids=(SELECT jsonb_agg(DISTINCT (recipient->>'user_id')::bigint ORDER BY (recipient->>'user_id')::bigint)
       FROM jsonb_array_elements(psl_schedules_values((p.policies->>'D11.recipient_grant_refs')::bigint)) recipient WHERE recipient->>'audience'=v.audience)
      AND p.retention_days=(psl_schedules_values((p.policies->>'D11.template_storage_retention_rules')::bigint)->0->>'retention_days')::integer
      AND NOT EXISTS(SELECT 1 FROM jsonb_array_elements_text(p.recipient_ids) recipient WHERE NOT psl_schedules_grants(NEW.case_id,recipient::bigint,ARRAY['document.receive:'||v.audience]))
      AND jsonb_array_length(p.recipient_ids)>0
      AND NOT EXISTS(SELECT 1 FROM jsonb_array_elements_text(p.recipient_ids) recipient WHERE NOT EXISTS(
       SELECT 1 FROM documents_publicationreceipt pr WHERE pr.publication_id=p.id AND pr.recipient_id=recipient::bigint
        AND pr.payload=v.payload AND pr.payload_sha256=v.payload_sha256)))))
   THEN RAISE EXCEPTION 'Observed current human-confirmed minutes and exact requested recipient receipts required'; END IF;
 END IF;

 IF NEW.definition='finance-bu/v1' AND NEW.status='verified' AND NOT EXISTS(
  SELECT 1 FROM core_evidence e JOIN finance_buwork w ON w.case_id=NEW.case_id AND w.kind=NEW.request->>'mode'
  JOIN finance_bureport p ON p.work_id=w.id JOIN finance_bureview rv ON rv.id=p.review_id
  JOIN workflows_factoryactivity fa ON fa.work_id=NEW.id AND fa.kind='ACT13'
  JOIN workflows_factoryattempt a ON a.activity_id=fa.id AND a.phase='observed'
  JOIN policy_configuration pc ON pc.id=(p.policy_ids->>'BU.disclosure_rules')::bigint
  WHERE e.id=NEW.source_head_id AND w.reference='factory-bu-'||NEW.id::text
   AND psl_schedules_grants(NEW.case_id,e.created_by_id,ARRAY['case.read','bu.read','bu.private.read','evidence.add'])
   AND EXISTS(SELECT 1 FROM core_audit origin WHERE origin.case_id=NEW.case_id AND origin.actor_id=e.created_by_id
    AND origin.data=jsonb_build_object('evidence_id',e.id,'sha256',e.sha256)
    AND ((origin.action='factory.bu_intake' AND psl_schedules_grants(NEW.case_id,e.created_by_id,ARRAY['factory.start']))
     OR (origin.action='factory.bu_source' AND psl_schedules_grants(NEW.case_id,e.created_by_id,ARRAY['factory.manage']))))
   AND w.metadata->>'status'='complete' AND w.payload->'conserved'='true'::jsonb
   AND psl_bu_current(w.id) AND psl_bu_review(rv.id) AND psl_bu_private(w.id,p.actor_id) AND psl_bu_authority(w.id,p.actor_id,'publish',p.policy_ids)
   AND (COALESCE(w.metadata->'historical','false'::jsonb)='false'::jsonb OR EXISTS(SELECT 1 FROM finance_bureview history WHERE history.work_id=w.id AND history.purpose='historical' AND psl_bu_review(history.id)))
   AND rv.work_id=w.id AND rv.purpose=w.kind AND rv.verdict='approve' AND rv.subject_sha256=w.sha256
   AND rv.id=(SELECT max(id) FROM finance_bureview WHERE work_id=w.id AND purpose=w.kind)
   AND NOT EXISTS(SELECT 1 FROM finance_buwork newer WHERE newer.case_id=w.case_id AND newer.kind=w.kind AND newer.reference=w.reference AND newer.version>w.version AND newer.metadata->'accepted'='true'::jsonb)
   AND NOT EXISTS(SELECT 1 FROM finance_bureport newer JOIN finance_buwork nw ON nw.id=newer.work_id WHERE nw.case_id=w.case_id AND nw.kind=w.kind AND nw.metadata->'scope'=w.metadata->'scope' AND newer.id>p.id)
   AND ((w.kind='staff' AND w.payroll_id=(e.body::jsonb->'inputs'->>'payroll_id')::bigint AND w.metadata->'rule_ids'=e.body::jsonb->'inputs'->'rule_ids')
    OR (w.kind='event' AND w.parent_id=(e.body::jsonb->'inputs'->>'source_id')::bigint AND w.metadata->'comparison'=e.body::jsonb->'inputs'->'comparison'))
   AND psl_schedules_policy_current(NEW.case_id,pc.id)
   AND psl_schedules_grants(NEW.case_id,p.actor_id,ARRAY['case.read','bu.read','bu.private.read','bu.publish'])
   AND psl_schedules_grants(NEW.case_id,rv.actor_id,ARRAY['case.read','bu.read','bu.private.read','bu.review'])
   AND NOT EXISTS(SELECT 1 FROM jsonb_each(w.metadata->'policy_ids') pin WHERE NOT psl_schedules_policy_current(NEW.case_id,(pin.value#>>'{}')::bigint))
   AND p.payload-ARRAY['entity','period','currency','unit','by_bu','company_source_total','allocated_total','company_only','residual','conserved','source_work','coverage','native_authenticity_verified','destination','ledger_posted','source_written','disclosure']='{}'::jsonb
   AND p.payload->>'disclosure'='aggregate_only' AND NOT (p.payload ? 'rows') AND p.payload->'ledger_posted'='false'::jsonb AND p.payload->'source_written'='false'::jsonb
   AND p.payload->>'source_work'=w.id::text AND p.payload->'by_bu'=w.payload->'by_bu'
   AND p.payload->'company_source_total'=w.payload->'source_total' AND p.payload->'allocated_total'=w.payload->'allocated_total' AND p.payload->'residual'=w.payload->'residual'
   AND a.result->'verified'='true'::jsonb AND a.result->>'head'=e.id::text AND a.result->>'work'=w.id::text AND a.result->>'publication'=p.id::text
   AND a.result->'private_payloads_in_result'='false'::jsonb AND a.result->'source_written'='false'::jsonb AND a.result->'ledger_posted'='false'::jsonb
   AND jsonb_array_length(psl_schedules_values(pc.id)->0->'recipient_ids')>0
   AND (SELECT count(*) FROM finance_bureceipt WHERE report_id=p.id)=jsonb_array_length(psl_schedules_values(pc.id)->0->'recipient_ids')
   AND NOT EXISTS(SELECT 1 FROM jsonb_array_elements_text(psl_schedules_values(pc.id)->0->'recipient_ids') recipient WHERE NOT EXISTS(
    SELECT 1 FROM finance_bureceipt rr WHERE rr.report_id=p.id AND rr.actor_id=recipient::bigint
     AND a.result->'receipt_ids' @> to_jsonb(ARRAY[rr.id])
     AND psl_schedules_grants(NEW.case_id,rr.actor_id,ARRAY['case.read','bu.read','bu.report.read','bu.receive']))))
 THEN RAISE EXCEPTION 'Observed exact reviewed BU aggregate and actual recipient-owned receipts required'; END IF;
 RETURN NEW;
END $$;

CREATE OR REPLACE FUNCTION psl_engagement_factory_source(w workflows_factorywork) RETURNS boolean LANGUAGE sql STABLE AS $$
 SELECT EXISTS(SELECT 1 FROM core_evidence e JOIN pmo_engagementrecord r ON r.id::text=e.body::jsonb->>'capture'
 WHERE e.id=w.source_head_id AND e.case_id=w.case_id AND e.kind='agent_private_engagement_intake'
  AND e.source='psl:engagement-intake/v1' AND e.body::jsonb->>'protocol'='engagement-intake/v1'
  AND e.body::jsonb - ARRAY['protocol','capture','capture_hash','source','sha256']='{}'::jsonb
  AND encode(sha256(convert_to(e.body,'UTF8')),'hex')=e.sha256
  AND EXISTS(SELECT 1 FROM core_audit a WHERE a.case_id=w.case_id AND a.actor_id=e.created_by_id AND a.action='factory.engagement_intake'
    AND a.data=jsonb_build_object('head',e.id,'sha256',e.sha256))
  AND r.case_id=w.case_id AND r.kind='capture' AND r.evidence_id::text=e.body::jsonb->>'source'
  AND EXISTS(SELECT 1 FROM core_evidence original WHERE original.id=r.evidence_id AND original.case_id=w.case_id AND original.sha256=e.body::jsonb->>'sha256')
  AND w.invoice_id IS NULL AND w.preparation_id IS NULL);
$$;
CREATE OR REPLACE FUNCTION psl_engagement_factory_identity_clear(cid uuid, uid bigint) RETURNS boolean LANGUAGE sql STABLE AS $$
 SELECT NOT EXISTS(SELECT 1 FROM (SELECT * FROM pmo_projectidentitydecision WHERE case_id=cid ORDER BY id DESC LIMIT 100) d
 WHERE NOT psl_schedules_grants(d.other_case_id,uid,ARRAY['case.read','engagement.read'])
 OR (d.relation IN ('alias','unresolved')
  AND d.id=(SELECT max(id) FROM pmo_projectidentitydecision WHERE case_id=cid AND other_case_id=d.other_case_id)
  AND d.data->>'source_capture'=(SELECT max(id)::text FROM pmo_engagementrecord WHERE case_id=cid AND kind='capture')
  AND d.data->>'target_capture'=(SELECT max(id)::text FROM pmo_engagementrecord WHERE case_id=d.other_case_id AND kind='capture')
  AND psl_schedules_policy_current(cid,(d.data->>'source_policy')::bigint)
  AND psl_schedules_policy_current(d.other_case_id,(d.data->>'target_policy')::bigint)
  AND psl_schedules_grants(cid,d.actor_id,ARRAY['case.read','engagement.read','engagement.resolve_identity'])
  AND psl_schedules_grants(d.other_case_id,d.actor_id,ARRAY['case.read','engagement.read','engagement.resolve_identity'])
  AND psl_schedules_role_current(cid,d.actor_id,d.data->'source_authority',d.data->>'role')
  AND psl_schedules_role_current(d.other_case_id,d.actor_id,d.data->'target_authority',d.data->>'role')
  AND EXISTS(SELECT 1 FROM jsonb_array_elements(psl_schedules_values((d.data->>'source_policy')::bigint)) v WHERE v->'resolution_roles' ? (d.data->>'role'))
  AND EXISTS(SELECT 1 FROM jsonb_array_elements(psl_schedules_values((d.data->>'target_policy')::bigint)) v WHERE v->'resolution_roles' ? (d.data->>'role'))
  AND d.data->'access_transferred'='false'::jsonb AND d.data->'business_records_transferred'='false'::jsonb AND d.data->'financial_authority'='false'::jsonb));
$$;
CREATE OR REPLACE FUNCTION psl_engagement_public_source(cid uuid, eid bigint) RETURNS boolean LANGUAGE sql STABLE AS $$
 SELECT EXISTS(SELECT 1 FROM core_evidence e WHERE e.id=eid AND e.case_id=cid
  AND e.kind NOT IN ('ledger_source','quickbooks_verification','ledger_resolution','ledger_resolution_review','approval_source','approval_observation','migration_proof','d03_source','planning_packet','planning_prd_alignment','planning_scope_alignment','planning_contract_comparison','planning_readiness','finance_group_snapshot')
  AND e.kind !~ '^(d03_control_|p14_|ops_|integration_|agent_private_|forecast_)'
  AND e.source<>'psl:p56-confirmed-request/v1'
  AND NOT(e.kind='finance_report_snapshot' AND e.source LIKE 'derived:forecast:%')
  AND NOT EXISTS(SELECT 1 FROM finance_forecastscenario f WHERE f.case_id=cid AND
   (f.evidence_id=eid OR EXISTS(SELECT 1 FROM jsonb_array_elements(f.payload->'items') item WHERE item->>'evidence_id'=eid::text)
    OR EXISTS(SELECT 1 FROM jsonb_array_elements(f.payload->'openings') opening WHERE opening->>'evidence_id'=eid::text))));
$$;
CREATE OR REPLACE FUNCTION psl_engagement_planning_inputs_current(eid bigint) RETURNS boolean LANGUAGE sql STABLE AS $$
 SELECT EXISTS(SELECT 1 FROM core_evidence e WHERE e.id=eid AND e.kind='planning_packet'
  AND encode(sha256(convert_to(e.body,'UTF8')),'hex')=e.sha256
  AND NOT EXISTS(SELECT 1 FROM jsonb_array_elements(e.body::jsonb->'payload'->'stakeholders') s
    WHERE (s->'contact_id'<>'null'::jsonb AND NOT psl_schedules_grants(e.case_id,(s->>'contact_id')::bigint,ARRAY['planning.participate']))
     OR (s->'evidence_id'<>'null'::jsonb AND NOT psl_engagement_public_source(e.case_id,(s->>'evidence_id')::bigint)))
  AND NOT EXISTS(SELECT 1 FROM jsonb_array_elements(e.body::jsonb->'payload'->'questions') q
    WHERE (q->'evidence_id'<>'null'::jsonb AND NOT psl_engagement_public_source(e.case_id,(q->>'evidence_id')::bigint))
     OR (q->'action_id'<>'null'::jsonb AND NOT EXISTS(SELECT 1 FROM pmo_actionitem a WHERE a.id::text=q->>'action_id' AND a.case_id=e.case_id
      AND a.current_id::text=e.body::jsonb->'action_heads'->>(q->>'action_id'))))
  AND NOT EXISTS(SELECT 1 FROM jsonb_each(e.body::jsonb->'action_heads') h
    WHERE NOT EXISTS(SELECT 1 FROM pmo_actionitem a WHERE a.id::text=h.key AND a.case_id=e.case_id AND to_jsonb(a.current_id)=h.value))
  AND NOT EXISTS(SELECT 1 FROM unnest(ARRAY['prd_id','scope_id','engineering_estimate_id','security_estimate_id']) k
    WHERE e.body::jsonb->'payload'->k<>'null'::jsonb AND NOT psl_engagement_public_source(e.case_id,(e.body::jsonb->'payload'->>k)::bigint)));
$$;
CREATE OR REPLACE FUNCTION psl_engagement_worker_current(w workflows_factorywork) RETURNS boolean LANGUAGE sql STABLE AS $$
 SELECT w.execution_binding_id IS NULL OR EXISTS(
  SELECT 1 FROM workflows_factoryexecutionbinding b WHERE b.id=w.execution_binding_id AND b.work_id=w.id
   AND psl_schedules_policy_current(w.case_id,b.configuration_id)
   AND EXISTS(SELECT 1 FROM policy_configuration p WHERE p.id=b.configuration_id AND p.case_id=w.case_id AND p.component='OPS.factory_recovery_authority')
   AND EXISTS(SELECT 1 FROM jsonb_array_elements(psl_schedules_values(b.configuration_id)) value
    WHERE value->'rules' @> jsonb_build_array(b.rule)
     AND (SELECT count(*) FROM jsonb_array_elements(value->'rules') rule WHERE rule->>'definition'=w.definition)=1)
   AND b.rule->>'definition'=w.definition AND b.rule->>'method'='reviewed_execution_principal_v1'
   AND b.rule->>'principal_id'=b.principal_id::text AND b.rule->>'reviewer_id'=b.reviewer_id::text
   AND b.rule->'independent_of_worker' IN ('true'::jsonb,'false'::jsonb)
   AND (b.rule->'independent_of_worker'='false'::jsonb OR b.principal_id<>b.reviewer_id)
   AND (b.rule->>'valid_from')::timestamptz<=statement_timestamp() AND statement_timestamp()<(b.rule->>'valid_until')::timestamptz
   AND psl_schedules_grants(w.case_id,b.principal_id,ARRAY['case.read','factory.read','engagement.read','factory.execute'])
   AND psl_schedules_grants(w.case_id,b.reviewer_id,ARRAY['case.read','factory.read','engagement.read','factory.manage'])
   AND EXISTS(SELECT 1 FROM policy_configuration roles WHERE roles.case_id=w.case_id AND roles.component='D05.role_principal_assignments'
    AND psl_schedules_policy_current(w.case_id,roles.id)
    AND psl_schedules_role_current(w.case_id,b.reviewer_id,jsonb_build_object('D05.role_principal_assignments',roles.id),b.rule->>'review_role'))
   AND NOT EXISTS(SELECT 1 FROM policy_scopeapplication app JOIN policy_scopeversion scope ON scope.id=app.source_id
    JOIN policy_configuration origin ON origin.id=scope.configuration_id WHERE app.configuration_id=b.configuration_id
     AND (NOT psl_schedules_grants(origin.case_id,b.principal_id,ARRAY['case.read','policy.read'])
      OR NOT psl_schedules_grants(origin.case_id,b.reviewer_id,ARRAY['case.read','policy.read'])))
 );
$$;
CREATE OR REPLACE FUNCTION psl_engagement_factory_current(w workflows_factorywork, result jsonb) RETURNS boolean LANGUAGE sql STABLE AS $$
 SELECT psl_engagement_factory_source(w) AND psl_engagement_worker_current(w)
 AND psl_engagement_factory_identity_clear(w.case_id,COALESCE((SELECT principal_id FROM workflows_factoryexecutionbinding WHERE id=w.execution_binding_id),w.actor_id))
 AND psl_schedules_grants(w.case_id,COALESCE((SELECT principal_id FROM workflows_factoryexecutionbinding WHERE id=w.execution_binding_id),w.actor_id),ARRAY['case.read','engagement.read','planning.read','factory.execute'])
 AND EXISTS(
 SELECT 1 FROM pmo_engagementrecord c
 JOIN pmo_engagementrecord a ON a.id::text=result->>'assignment' AND a.case_id=w.case_id AND a.kind='assignment'
 JOIN pmo_engagementrecord r ON r.id::text=result->>'registration' AND r.case_id=w.case_id AND r.kind='registration'
 JOIN core_evidence source ON source.id=c.evidence_id AND source.case_id=w.case_id
 JOIN core_evidence plan ON plan.id::text=r.data->>'plan' AND plan.case_id=w.case_id AND plan.kind='plan' AND plan.sha256=r.data->>'plan_sha256'
 JOIN core_evidence packet ON packet.id::text=result->>'planning_packet' AND packet.case_id=w.case_id AND packet.kind='planning_packet'
 JOIN workflows_factorywork child ON child.id::text=result->>'planning_work' AND child.case_id=w.case_id AND child.definition='planning/v1'
 JOIN core_audit receipt ON receipt.id::text=result->>'receipt' AND receipt.case_id=w.case_id AND receipt.action='factory.engagement_planning_linked'
 WHERE c.id::text=result->>'capture' AND c.case_id=w.case_id AND c.kind='capture'
  AND c.id=(SELECT max(id) FROM pmo_engagementrecord WHERE case_id=w.case_id AND kind='capture')
  AND a.id=(SELECT max(id) FROM pmo_engagementrecord WHERE case_id=w.case_id AND kind='assignment')
  AND r.id=(SELECT max(id) FROM pmo_engagementrecord WHERE case_id=w.case_id AND kind='registration')
  AND a.data->>'capture'=c.id::text AND r.data->>'capture'=c.id::text AND r.data->>'assignment'=a.id::text
  AND result->'verified'='true'::jsonb AND result->>'verification_scope'='current_engagement_identity_and_internal_planning_handoff'
  AND result->>'head'=w.source_head_id::text
  AND result->'planning_complete'='false'::jsonb AND result->'external_master_verified'='false'::jsonb AND result->'signature_required'='false'::jsonb
  AND (SELECT body::jsonb->>'capture' FROM core_evidence WHERE id=w.source_head_id)=c.id::text
  AND encode(sha256(convert_to(source.body,'UTF8')),'hex')=source.sha256
  AND psl_engagement_public_source(w.case_id,source.id)
  AND psl_engagement_public_source(w.case_id,plan.id)
  AND (c.data->>'route' IN ('B','C') OR EXISTS(SELECT 1 FROM pmo_rfpdisposition d JOIN pmo_rfpcase rf ON rf.id=d.rfp_id
    JOIN pmo_rfpoutcome o ON o.id=d.outcome_id WHERE d.id::text=c.data->>'rfp_disposition' AND rf.case_id=w.case_id AND d.kind='route_a' AND o.result='won'))
  AND (c.data->>'route'<>'C' OR source.kind='product_input')
  AND psl_schedules_grants(w.case_id,c.actor_id,ARRAY['case.read','engagement.read','engagement.capture'])
  AND psl_schedules_grants(w.case_id,a.actor_id,ARRAY['engagement.assign'])
  AND psl_schedules_grants(w.case_id,(a.data->>'pm_id')::bigint,ARRAY['engagement.read'])
  AND psl_schedules_grants(w.case_id,r.actor_id,ARRAY['engagement.register'])
  AND psl_schedules_policy_current(w.case_id,(a.data->>'policy')::bigint)
  AND psl_schedules_policy_current(w.case_id,(r.data->>'policy')::bigint)
  AND psl_schedules_role_current(w.case_id,a.actor_id,a.data->'authority',a.data->>'role')
  AND psl_schedules_role_current(w.case_id,(a.data->>'pm_id')::bigint,a.data->'pm_authority','PM')
  AND psl_schedules_role_current(w.case_id,r.actor_id,r.data->'authority',r.data->>'role')
  AND EXISTS(SELECT 1 FROM jsonb_array_elements(psl_schedules_values((a.data->>'policy')::bigint)) v WHERE v->'assignment_roles' ? (a.data->>'role'))
  AND EXISTS(SELECT 1 FROM jsonb_array_elements(psl_schedules_values((r.data->>'policy')::bigint)) v WHERE v->'registration_roles' ? (r.data->>'role'))
  AND EXISTS(SELECT 1 FROM pmo_projectidentifier i JOIN core_case k ON k.id=w.case_id WHERE i.case_id=w.case_id AND i.tenant=k.tenant
    AND i.namespace=r.data->>'namespace' AND i.normalized=r.data->>'normalized')
  AND psl_engagement_planning_inputs_current(packet.id)
  AND packet.id=child.source_head_id AND packet.id=(SELECT id FROM core_evidence WHERE case_id=w.case_id AND kind='planning_packet' ORDER BY version DESC LIMIT 1)
  AND packet.body::jsonb->>'engagement_id'=c.id::text AND child.request->>'engagement'=c.id::text
  AND NOT child.cancel_requested AND child.status NOT IN ('cancelled','followup_needed')
  AND psl_schedules_grants(w.case_id,packet.created_by_id,ARRAY['case.read','planning.read','planning.coordinate'])
  AND EXISTS(SELECT 1 FROM core_audit pa WHERE pa.case_id=w.case_id AND pa.actor_id=packet.created_by_id AND pa.action='planning.recorded'
     AND pa.data=jsonb_build_object('kind','packet','evidence_id',packet.id,'sha256',packet.sha256))
  AND receipt.data->>'work'=w.id::text AND receipt.data->>'capture'=c.id::text AND receipt.data->>'planning_work'=child.id::text
 );
$$;
CREATE OR REPLACE FUNCTION psl_engagement_factory_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF NEW.definition<>'engagement/v1' THEN RETURN NEW; END IF;
 IF NOT psl_engagement_factory_source(NEW) THEN RAISE EXCEPTION 'Exact native engagement intake pointer required'; END IF;
 IF NEW.status='verified' AND NOT EXISTS(SELECT 1 FROM workflows_factoryattempt a JOIN workflows_factoryactivity act ON act.id=a.activity_id
  WHERE act.work_id=NEW.id AND act.kind='ACT13' AND a.phase='observed' AND a.id=(SELECT max(x.id) FROM workflows_factoryattempt x JOIN workflows_factoryactivity y ON y.id=x.activity_id WHERE y.work_id=NEW.id AND y.kind='ACT13' AND x.phase='observed')
  AND psl_engagement_factory_current(NEW,a.result))
 THEN RAISE EXCEPTION 'Observed current engagement identity and native planning handoff required'; END IF;
 RETURN NEW;
END $$;
DROP TRIGGER IF EXISTS psl_engagement_factory_guard ON workflows_factorywork;
CREATE TRIGGER psl_engagement_factory_guard BEFORE INSERT OR UPDATE ON workflows_factorywork FOR EACH ROW EXECUTE FUNCTION psl_engagement_factory_guard();

DROP TRIGGER psl_factory_ledger ON workflows_factorywork; DROP FUNCTION psl_factory_ledger_guard(); DROP FUNCTION psl_factory_ledger_current(bigint); DROP FUNCTION psl_factory_ledger_resolution(bigint); DROP FUNCTION psl_factory_ledger_resolution_current(bigint); DROP FUNCTION psl_factory_ledger_read_current(bigint);"""

class Migration(migrations.Migration):
    dependencies = [("workflows", "0076_factory_bu")]
    operations = [migrations.RunSQL(SQL, REVERSE)]

"""P44 SQL composition source. Final migrations freeze these bytes, never import this helper."""
FUNCTIONS=r"""
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
"""
SOURCE=r"""
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
"""
VERIFIED=r"""
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
"""
BRANCH=r"""
    OR
    (w.definition='pmo-escalation/v1' AND NOT w.cancel_requested AND w.status NOT IN ('verified','cancelled','followup_needed')
     AND psl_escalation_document(w.id,v.id,NEW.review_id,NEW.actor_id,p.id,e.id,NEW.recipient_ids,NEW.policies))
"""
UNBOUND=r"""
 IF NEW.factory_work_id IS NULL AND EXISTS(SELECT 1 FROM workflows_factoryactivity fa JOIN workflows_factorywork w ON w.id=fa.work_id
 JOIN workflows_factoryattempt a ON a.activity_id=fa.id WHERE w.definition='pmo-escalation/v1' AND fa.kind='ACT09' AND a.phase='observed'
 AND a.result->>'document_version'=NEW.version_id::text)
 THEN RAISE EXCEPTION 'Observed escalation communication requires its exact factory scope'; END IF;
"""
def work_sql(previous):
    marker="'finance-schedules/v1'";assert previous.count(marker)>=1
    # Only the closed definition list, not the independent native verification branch.
    start=previous.index('NEW.definition NOT IN');end=previous.index(')',start)
    head=previous[start:end];result=previous[:start]+head+",'pmo-escalation/v1'"+previous[end:]
    marker="WHEN 'finance-schedules/v1' THEN 'OPS.factory_schedules_execution'";assert result.count(marker)==1
    result=result.replace(marker,marker+" WHEN 'pmo-escalation/v1' THEN 'OPS.factory_escalation_execution'")
    marker=" IF NEW.status='verified' THEN";assert result.count(marker)==1
    result=result.replace(marker,SOURCE+marker);assert result.count(' RETURN NEW;')==1
    return result.replace(' RETURN NEW;',VERIFIED+' RETURN NEW;')
def document_sql(previous):
    marker='\n   ))';assert previous.count(marker)==1
    result=previous.replace(marker,BRANCH+marker);assert result.count(' RETURN NEW;')==1
    return result.replace(' RETURN NEW;',UNBOUND+' RETURN NEW;')

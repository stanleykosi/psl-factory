"""PROVISIONAL diagnostic guards against accepted actual0071 plus retained0023 factory scope; not a migration or final717 proof."""
from importlib import import_module
PREVIOUS=import_module('apps.workflows.migrations.0071_factory_group_forecast').SQL
PREVIOUS_DOCUMENT=import_module('apps.documents.migrations.0023_factory_forecast').SQL
HELPERS=r'''
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
'''
SOURCE=r'''
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
'''
VERIFIED=r'''
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
'''
SQL=PREVIOUS
marker="'finance-payroll/v1','pmo-emergency/v1'"
assert SQL.count(marker)==1
SQL=SQL.replace(marker,marker+",'pmo-weekly-report/v1'")
marker="WHEN 'pmo-emergency/v1' THEN 'OPS.factory_emergency_execution'"
assert SQL.count(marker)==1
SQL=SQL.replace(marker,marker+" WHEN 'pmo-weekly-report/v1' THEN 'OPS.factory_reporting_execution'")
marker=" IF NEW.status='verified' THEN"
assert SQL.count(marker)==1
SQL=HELPERS+SQL.replace(marker,SOURCE+marker)
assert SQL.count(' RETURN NEW;')==1
SQL=SQL.replace(' RETURN NEW;',VERIFIED+' RETURN NEW;')
BRANCH=r'''
    OR
    (w.definition='pmo-weekly-report/v1' AND p.component='OPS.factory_reporting_execution'
     AND w.policy_id=p.id AND w.source_head_id=e.id AND NOT w.cancel_requested
     AND w.status NOT IN ('verified','cancelled','followup_needed')
     AND psl_reporting_document(w.id,e.id,v.id)
     AND EXISTS(SELECT 1 FROM documents_controlledreview rv WHERE rv.id=NEW.review_id AND rv.version_id=v.id
      AND rv.verdict='approve' AND rv.payload_sha256=v.payload_sha256
      AND rv.id=(SELECT max(id) FROM documents_controlledreview WHERE version_id=v.id)
      AND psl_reporting_review(w.case_id,rv.id))
     AND psl_reporting_principals(w.id,v.id,NEW.actor_id)
     AND psl_reporting_distribution(w.case_id,v.id,NEW.policies,NEW.recipient_ids,NEW.retention_days)
     AND psl_reporting_grants(w.case_id,NEW.actor_id,ARRAY['case.read','report.read','factory.execute','document.publish']))
'''
assert PREVIOUS_DOCUMENT.count('\n   ))')==1
DOCUMENT_SQL=PREVIOUS_DOCUMENT.replace('\n   ))',BRANCH+'\n   ))')

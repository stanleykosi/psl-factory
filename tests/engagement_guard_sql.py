"""Provisional SQL diagnostic only. Final migration freezes these exact statements."""
from importlib import import_module
PREVIOUS=import_module('apps.workflows.migrations.0071_factory_group_forecast').SQL

SOURCE=r"""
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

def extend(previous):
    whitelist=" IF NEW.definition NOT IN ("
    case="p.component=CASE NEW.definition "
    assert previous.count(whitelist)==1 and previous.count(case)==1
    result=previous.replace(whitelist,whitelist+"'engagement/v1',",1).replace(case,case+"WHEN 'engagement/v1' THEN 'OPS.factory_engagement_execution' ",1)
    return result+SOURCE
SQL=extend(PREVIOUS)

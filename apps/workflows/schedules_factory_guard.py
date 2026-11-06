"""Scoped schedule envelope guard; no native Finance semantics are changed."""
FUNCTIONS=r"""
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
"""
SOURCE=r"""
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
"""
VERIFIED=r"""
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
"""
def extend(previous):
    marker="'delivery-go-live/v1','finance-accounts/v1','rfp-response/v1'"
    assert previous.count(marker)==1
    sql=previous.replace(marker,marker+",'finance-schedules/v1'")
    marker="WHEN 'delivery-go-live/v1' THEN 'OPS.factory_go_live_execution'"
    assert sql.count(marker)==1
    sql=sql.replace(marker,marker+" WHEN 'finance-schedules/v1' THEN 'OPS.factory_schedules_execution'")
    marker=" IF NEW.status='verified' THEN"
    assert sql.count(marker)==1 and sql.count(' RETURN NEW;')==1
    return FUNCTIONS+sql.replace(marker,SOURCE+marker).replace(' RETURN NEW;',VERIFIED+' RETURN NEW;')

"""F01 additive guard proposal; frozen into the real migration after predecessors land."""
SQL=r"""
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
REVERSE='DROP TRIGGER psl_factory_ledger ON workflows_factorywork; DROP FUNCTION psl_factory_ledger_guard(); DROP FUNCTION psl_factory_ledger_current(bigint); DROP FUNCTION psl_factory_ledger_resolution(bigint); DROP FUNCTION psl_factory_ledger_resolution_current(bigint); DROP FUNCTION psl_factory_ledger_read_current(bigint);'

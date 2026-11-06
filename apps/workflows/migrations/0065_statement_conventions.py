"""Finite reviewed sign conversion; earlier factory guards remain composed intact."""
from importlib import import_module
from django.db import migrations

CURRENT=r"""
CREATE FUNCTION psl_finance_policy_current(selected_config_id bigint) RETURNS boolean LANGUAGE plpgsql STABLE AS $$
DECLARE cfg policy_configuration;
BEGIN
 SELECT * INTO cfg FROM policy_configuration WHERE id=selected_config_id;
 IF NOT FOUND OR (SELECT state FROM policy_policystate WHERE configuration_id=cfg.id ORDER BY id DESC LIMIT 1) IS DISTINCT FROM 'active'
  OR cfg.id IS DISTINCT FROM (SELECT candidate.id FROM policy_configuration candidate WHERE candidate.case_id=cfg.case_id AND candidate.component=cfg.component
    AND (SELECT state FROM policy_policystate WHERE configuration_id=candidate.id ORDER BY id DESC LIMIT 1) IN ('active','revoked','superseded') ORDER BY candidate.revision DESC LIMIT 1)
  OR (cfg.envelope->>'effective_from')::timestamptz>statement_timestamp()
  OR ((cfg.envelope->>'effective_until') IS NOT NULL AND (cfg.envelope->>'effective_until')::timestamptz<=statement_timestamp()) THEN RETURN false; END IF;
 -- Applied scope bytes are immutable. Recheck the mutable origin lifecycle and actor grants.
 IF EXISTS(SELECT 1 FROM policy_scopeapplication WHERE configuration_id=cfg.id) AND NOT EXISTS(
  SELECT 1 FROM policy_scopeapplication app JOIN policy_scopeversion source ON source.id=app.source_id
   JOIN policy_configuration origin ON origin.id=source.configuration_id
   JOIN core_case local_case ON local_case.id=cfg.case_id JOIN core_case origin_case ON origin_case.id=origin.case_id
   JOIN auth_user applicant ON applicant.id=app.actor_id AND applicant.is_active
   JOIN policy_scopestate activated ON activated.id=(SELECT max(id) FROM policy_scopestate WHERE source_id=source.id AND state='active')
   JOIN auth_user activator ON activator.id=activated.actor_id AND activator.is_active
  WHERE app.configuration_id=cfg.id AND local_case.tenant=origin_case.tenant AND local_case.synthetic=origin_case.synthetic
   AND cfg.component=origin.component AND (source.kind='organization' OR origin.case_id=cfg.case_id)
   AND ((source.kind='organization' AND source.ref=origin_case.tenant)
    OR (source.kind='project' AND origin_case.kind='project' AND source.ref=origin.case_id::text)
    OR (source.kind='service' AND origin_case.kind='support' AND source.ref=origin.case_id::text)
    OR (source.kind='contract' AND source.ref LIKE 'evidence:%' AND EXISTS(SELECT 1 FROM core_evidence WHERE case_id=origin.case_id AND kind='sow' AND id::text=substring(source.ref FROM 10))))
   AND (SELECT state FROM policy_scopestate WHERE source_id=source.id ORDER BY id DESC LIMIT 1)='active'
   AND (SELECT state FROM policy_policystate WHERE configuration_id=origin.id ORDER BY id DESC LIMIT 1)='validated'
   AND NOT EXISTS(SELECT 1 FROM policy_scopeversion newer JOIN policy_configuration nc ON nc.id=newer.configuration_id
    WHERE nc.case_id=origin.case_id AND nc.component=origin.component AND newer.kind=source.kind AND newer.ref=source.ref AND newer.revision>source.revision
     AND EXISTS(SELECT 1 FROM policy_scopestate WHERE source_id=newer.id AND state IN ('active','revoked')))
   AND (origin.envelope->>'effective_from')::timestamptz<=statement_timestamp()
   AND ((origin.envelope->>'effective_until') IS NULL OR (origin.envelope->>'effective_until')::timestamptz>statement_timestamp())
   AND EXISTS(SELECT 1 FROM identity_grant WHERE user_id=app.actor_id AND case_id=cfg.case_id AND action='case.read' AND active)
   AND EXISTS(SELECT 1 FROM identity_grant WHERE user_id=app.actor_id AND case_id=cfg.case_id AND action='policy.configure' AND active)
   AND EXISTS(SELECT 1 FROM identity_grant WHERE user_id=app.actor_id AND case_id=origin.case_id AND action='case.read' AND active)
   AND EXISTS(SELECT 1 FROM identity_grant WHERE user_id=app.actor_id AND case_id=origin.case_id AND action='policy.read' AND active)
   AND EXISTS(SELECT 1 FROM identity_grant WHERE user_id=activated.actor_id AND case_id=origin.case_id AND action='case.read' AND active)
   AND EXISTS(SELECT 1 FROM identity_grant WHERE user_id=activated.actor_id AND case_id=origin.case_id AND action='policy.activate' AND active)
 ) THEN RETURN false; END IF;
 RETURN true;
END $$;

CREATE FUNCTION psl_finance_review_authority_current(selected_review_id bigint) RETURNS boolean LANGUAGE plpgsql STABLE AS $$
DECLARE rv finance_financereview; assignments policy_configuration; matrix policy_configuration;
 assignment_rows jsonb; rule jsonb; matches integer; preparer bigint; subject_case uuid; role_count integer;
BEGIN
 SELECT * INTO rv FROM finance_financereview WHERE id=selected_review_id;
 -- Statement boundaries use only native formula-configuration and output reviews.
 IF NOT FOUND OR rv.purpose NOT IN ('formula','output') OR rv.verdict<>'approve'
  OR NOT EXISTS(SELECT 1 FROM auth_user WHERE id=rv.actor_id AND is_active)
  OR NOT EXISTS(SELECT 1 FROM identity_grant WHERE user_id=rv.actor_id AND case_id=rv.case_id AND action='finance.review' AND active)
 THEN RETURN false; END IF;
 SELECT coalesce(c.created_by_id,s.actor_id,a.actor_id,r.actor_id),coalesce(c.case_id,s.case_id,adjustment_source.case_id,r.case_id) INTO preparer,subject_case FROM finance_financereview fr
  LEFT JOIN policy_configuration c ON c.id=fr.configuration_id LEFT JOIN finance_financesource s ON s.id=fr.source_id
  LEFT JOIN finance_financeadjustment a ON a.id=fr.adjustment_id LEFT JOIN finance_financesource adjustment_source ON adjustment_source.id=a.source_id LEFT JOIN finance_financerun r ON r.id=fr.run_id WHERE fr.id=rv.id;
 IF preparer IS NULL OR subject_case IS DISTINCT FROM rv.case_id THEN RETURN false; END IF;
 SELECT * INTO assignments FROM policy_configuration WHERE case_id=rv.case_id AND component='D05.role_principal_assignments'
  AND id=(rv.authority->>'D05.role_principal_assignments')::bigint;
 IF NOT FOUND OR NOT psl_finance_policy_current(assignments.id) THEN RETURN false; END IF;
 SELECT jsonb_agg(pr.content) INTO assignment_rows FROM jsonb_array_elements_text(assignments.envelope->'value') named
  JOIN policy_registeredreference pr ON pr.case_id=rv.case_id AND pr.ref=named.value AND pr.version=1;
 IF assignment_rows IS NULL OR NOT EXISTS(SELECT 1 FROM jsonb_array_elements(assignment_rows) x WHERE x->>'user_id'=rv.actor_id::text AND x->>'role'=rv.role)
  OR EXISTS(SELECT 1 FROM jsonb_array_elements(assignment_rows) x WHERE NOT EXISTS(SELECT 1 FROM auth_user WHERE id=(x->>'user_id')::bigint AND is_active)) THEN RETURN false; END IF;
 SELECT count(DISTINCT x->>'role') INTO role_count FROM jsonb_array_elements(assignment_rows) x WHERE x->>'user_id'=rv.actor_id::text;
 IF role_count>1 THEN
  IF NOT EXISTS(SELECT 1 FROM jsonb_array_elements(assignment_rows) x WHERE x->>'user_id'=rv.actor_id::text AND NOT x ? 'eligibility') THEN
   IF EXISTS(SELECT 1 FROM jsonb_array_elements(assignment_rows) x WHERE x->>'user_id'=rv.actor_id::text
     AND NOT ((x->'eligibility'->>'valid_from')::timestamptz<=statement_timestamp() AND (x->'eligibility'->>'valid_until')::timestamptz>statement_timestamp())) THEN RETURN false; END IF;
  ELSIF NOT (SELECT synthetic FROM core_case WHERE id=rv.case_id) THEN RETURN false; END IF;
 END IF;
 SELECT * INTO matrix FROM policy_configuration WHERE case_id=rv.case_id AND component='D05.decision_action_matrix'
  AND (SELECT state FROM policy_policystate WHERE configuration_id=policy_configuration.id ORDER BY id DESC LIMIT 1) IN ('active','revoked','superseded') ORDER BY revision DESC LIMIT 1;
 IF NOT FOUND OR NOT psl_finance_policy_current(matrix.id) THEN RETURN false; END IF;
 SELECT count(*),jsonb_agg(x.value)->0 INTO matches,rule FROM policy_registeredreference pr,
  LATERAL jsonb_array_elements(pr.content->'finance') x WHERE pr.case_id=rv.case_id
   AND pr.ref=matrix.envelope->'value'->>'artifact_ref' AND pr.version=(matrix.envelope->'value'->>'artifact_version')::integer
   AND pr.sha256=matrix.envelope->'value'->>'sha256' AND x.value->>'purpose'=rv.purpose AND x.value->>'role'=rv.role AND x.value->'actions' ? rv.verdict;
 IF matches<>1 OR rule IS DISTINCT FROM rv.authority->'finance_review_rule'
  OR (preparer=rv.actor_id AND rule->'allow_preparer_review' IS DISTINCT FROM 'true'::jsonb) THEN RETURN false; END IF;
 RETURN true;
END $$;

CREATE FUNCTION psl_statement_reviews_current(selected_run_id bigint) RETURNS boolean LANGUAGE plpgsql STABLE AS $$
DECLARE r finance_financerun; contract policy_configuration; contract_value jsonb; registered_schema text; decision finance_financereview; i jsonb; source finance_financerun;
BEGIN
 SELECT * INTO r FROM finance_financerun WHERE id=selected_run_id AND kind='statement';
 IF NOT FOUND OR r.snapshot->>'implementation' IS NULL OR r.snapshot->>'implementation' NOT IN ('finance-statement-inputs/v1','finance-statement-inputs/v2')
  OR r.result->>'status' IS DISTINCT FROM 'complete'
  OR r.result->>'scope' IS DISTINCT FROM 'selected_statement_lines' OR r.result->'whole_statement_certified' IS DISTINCT FROM 'false'::jsonb
  OR jsonb_array_length(r.snapshot->'inputs')<1 THEN RETURN false; END IF;
 SELECT * INTO contract FROM policy_configuration WHERE id=(r.request->>'contract_id')::bigint AND case_id=r.case_id AND component='D06.statement_contract';
 IF NOT FOUND OR NOT psl_finance_policy_current(contract.id) THEN RETURN false; END IF;
 SELECT pr.content,pr.schema_ref INTO contract_value,registered_schema FROM policy_registeredreference pr WHERE pr.case_id=r.case_id
  AND pr.ref=contract.envelope->'value'->>'artifact_ref' AND pr.version=(contract.envelope->'value'->>'artifact_version')::integer
  AND pr.sha256=contract.envelope->'value'->>'sha256';
 IF NOT FOUND OR (r.snapshot->>'implementation'='finance-statement-inputs/v1' AND (registered_schema IS DISTINCT FROM 'schema:psl/finance-statement/v1' OR contract_value ? 'convention_mode'))
  OR (r.snapshot->>'implementation'='finance-statement-inputs/v2' AND (registered_schema IS DISTINCT FROM 'schema:psl/finance-statement/v2' OR contract_value->>'convention_mode' IS DISTINCT FROM 'producer_verified'))
  OR r.snapshot->'policies'->'D06.statement_contract'->>'id' IS DISTINCT FROM contract.id::text
  OR r.snapshot->'policies'->'D06.statement_contract'->>'revision' IS DISTINCT FROM contract.revision::text
  OR jsonb_array_length(contract_value->'inputs') IS DISTINCT FROM jsonb_array_length(r.snapshot->'inputs') THEN RETURN false; END IF;
 SELECT * INTO decision FROM finance_financereview WHERE configuration_id=contract.id AND purpose='formula' ORDER BY id DESC LIMIT 1;
 IF NOT FOUND OR decision.id::text IS DISTINCT FROM r.snapshot->'reviews'->'D06.statement_contract'->>'id'
  OR NOT psl_finance_review_authority_current(decision.id) THEN RETURN false; END IF;
 SELECT * INTO decision FROM finance_financereview WHERE run_id=r.id AND purpose='output' ORDER BY id DESC LIMIT 1;
 IF NOT FOUND OR NOT psl_finance_review_authority_current(decision.id) THEN RETURN false; END IF;
 IF (SELECT count(*) FROM finance_financestatementinput WHERE statement_id=r.id)<>jsonb_array_length(r.snapshot->'inputs') THEN RETURN false; END IF;
 FOR i IN SELECT value FROM jsonb_array_elements(r.snapshot->'inputs') LOOP
  IF NOT EXISTS(SELECT 1 FROM jsonb_array_elements(contract_value->'inputs') declared WHERE declared=i->'declaration')
   OR NOT EXISTS(SELECT 1 FROM finance_financestatementinput si WHERE si.statement_id=r.id AND si.declaration=i->'declaration'
    AND si.source_run_id::text=i->'declaration'->>'source_run' AND si.source_review_id::text=i->'declaration'->>'source_review'
    AND si.metric=i->'declaration'->>'metric' AND si.destination=i->'declaration'->>'destination' AND si.contract_id=contract.id)
   THEN RETURN false; END IF;
  SELECT * INTO source FROM finance_financerun WHERE id=(i->'declaration'->>'source_run')::bigint AND case_id=r.case_id AND kind='formula';
  IF NOT FOUND OR source.operation_key IS DISTINCT FROM i->>'operation_key'
   OR source.result->>'entity' IS DISTINCT FROM r.result->>'entity' OR source.result->>'period' IS DISTINCT FROM r.result->>'period'
   OR source.result->>'currency' IS DISTINCT FROM r.result->>'currency'
   OR (SELECT accounting_basis FROM finance_financesource WHERE id=source.source_id) IS DISTINCT FROM r.result->>'accounting_basis'
   OR source.result->'company'->(i->'declaration'->>'metric')->>'unit' IS DISTINCT FROM i->'declaration'->>'unit'
   OR r.result->'company'->(i->'declaration'->>'destination')->>'unit' IS DISTINCT FROM i->'declaration'->>'unit'
   THEN RETURN false; END IF;
  SELECT * INTO decision FROM finance_financereview WHERE run_id=source.id AND purpose='output' ORDER BY id DESC LIMIT 1;
  IF NOT FOUND OR decision.id::text IS DISTINCT FROM i->'declaration'->>'source_review'
   OR NOT psl_finance_review_authority_current(decision.id) THEN RETURN false; END IF;
  IF r.snapshot->>'implementation'='finance-statement-inputs/v1' AND
   (i->'declaration'->>'transfer' IS DISTINCT FROM 'identity' OR i->'declaration'->>'source_sign' IS NULL
    OR i->'declaration'->>'source_sign' IS DISTINCT FROM i->'declaration'->>'destination_sign'
    OR source.result->'company'->(i->'declaration'->>'metric')->'value' IS DISTINCT FROM r.result->'company'->(i->'declaration'->>'destination')->'value')
   THEN RETURN false; END IF;
 END LOOP;
 RETURN true;
END $$;

CREATE FUNCTION psl_statement_conventions_current(selected_run_id bigint) RETURNS boolean LANGUAGE plpgsql STABLE AS $$
DECLARE r finance_financerun; i jsonb; pin jsonb; role_name text; config policy_configuration; ref policy_registeredreference;
 declaration jsonb; rv finance_financereview; source finance_financerun; conversion jsonb; producer jsonb; amount numeric;
BEGIN
 SELECT * INTO r FROM finance_financerun WHERE id=selected_run_id;
 IF NOT FOUND THEN RETURN false; END IF;
 IF NOT psl_statement_reviews_current(r.id) THEN RETURN false; END IF;
 IF r.snapshot->>'implementation'='finance-statement-inputs/v1' THEN RETURN true; END IF;
 IF r.snapshot->>'implementation' IS DISTINCT FROM 'finance-statement-inputs/v2' THEN RETURN false; END IF;
 IF r.kind<>'statement' OR r.result->>'status' IS DISTINCT FROM 'complete' OR jsonb_array_length(r.snapshot->'inputs')<1 THEN RETURN false; END IF;
 FOR i IN SELECT value FROM jsonb_array_elements(r.snapshot->'inputs') LOOP
  pin=i->'convention_transfer';
  IF pin IS NULL OR pin='null'::jsonb OR pin->>'applications' IS DISTINCT FROM '1' THEN RETURN false; END IF;
  FOREACH role_name IN ARRAY ARRAY['producer','conversion'] LOOP
   SELECT * INTO config FROM policy_configuration WHERE id=(pin->role_name->>'id')::bigint AND case_id=r.case_id
    AND component=CASE role_name WHEN 'producer' THEN 'D06.producer_conventions' ELSE 'D06.statement_conversions' END;
   IF NOT FOUND OR NOT psl_finance_policy_current(config.id) OR config.revision::text IS DISTINCT FROM pin->role_name->>'revision'
    OR (SELECT state FROM policy_policystate WHERE configuration_id=config.id ORDER BY id DESC LIMIT 1) IS DISTINCT FROM 'active'
    OR (config.envelope->>'effective_from')::timestamptz>statement_timestamp()
    OR ((config.envelope->>'effective_until') IS NOT NULL AND (config.envelope->>'effective_until')::timestamptz<=statement_timestamp())
    THEN RETURN false; END IF;
   SELECT pr.* INTO ref FROM policy_registeredreference pr WHERE pr.case_id=r.case_id AND pr.ref=config.envelope->'value'->>'artifact_ref'
    AND pr.version=(config.envelope->'value'->>'artifact_version')::integer AND pr.sha256=config.envelope->'value'->>'sha256';
   IF NOT FOUND THEN RETURN false; END IF;
   SELECT value INTO declaration FROM jsonb_array_elements(ref.content->'declarations')
    WHERE value->>'key'=i->'declaration'->>(role_name||'_key');
   IF declaration IS DISTINCT FROM pin->role_name->'declaration'
    OR config.id::text IS DISTINCT FROM i->'declaration'->>(role_name||'_contract_id') THEN RETURN false; END IF;
   SELECT * INTO rv FROM finance_financereview WHERE configuration_id=config.id AND purpose='formula' ORDER BY id DESC LIMIT 1;
   IF NOT FOUND OR NOT psl_finance_review_authority_current(rv.id) OR rv.verdict<>'approve' OR rv.case_id<>r.case_id OR rv.id::text IS DISTINCT FROM pin->role_name->'review'->>'id' THEN RETURN false; END IF;
  END LOOP;
  producer=pin->'producer'->'declaration';conversion=pin->'conversion'->'declaration';
  SELECT * INTO source FROM finance_financerun WHERE id=(producer->>'source_run')::bigint AND case_id=r.case_id AND kind='formula';
  IF NOT FOUND OR source.operation_key IS DISTINCT FROM producer->>'operation_key'
   OR source.operation_key IS DISTINCT FROM i->>'operation_key'
   OR producer->>'source_run' IS DISTINCT FROM i->'declaration'->>'source_run'
   OR producer->>'source_review' IS DISTINCT FROM i->'declaration'->>'source_review'
   OR producer->>'source_review' IS DISTINCT FROM (SELECT id::text FROM finance_financereview WHERE run_id=source.id AND purpose='output' ORDER BY finance_financereview.id DESC LIMIT 1)
   OR NOT EXISTS(SELECT 1 FROM finance_financereview WHERE id=(producer->>'source_review')::bigint AND verdict='approve' AND purpose='output' AND run_id=source.id)
   OR producer->>'metric' IS DISTINCT FROM i->'declaration'->>'metric'
   OR producer->>'unit' IS DISTINCT FROM source.result->'company'->(producer->>'metric')->>'unit'
   OR producer->>'unit' IS DISTINCT FROM i->'declaration'->>'unit'
   OR producer->>'convention' IS DISTINCT FROM i->'declaration'->>'source_sign'
   OR conversion->>'from_convention' IS DISTINCT FROM producer->>'convention'
   OR conversion->>'to_convention' IS DISTINCT FROM i->'declaration'->>'destination_sign'
   OR conversion->>'unit' IS DISTINCT FROM producer->>'unit'
   OR conversion->>'operation' IS DISTINCT FROM i->'declaration'->>'transfer'
   OR (conversion->>'operation',conversion->>'factor') NOT IN (('identity','1'),('reverse_sign','-1'))
   OR pin->'source_value' IS DISTINCT FROM source.result->'company'->(producer->>'metric')->'value'
   OR pin->'destination_value' IS DISTINCT FROM r.result->'company'->(i->'declaration'->>'destination')->'value'
   OR r.result->'company'->(i->'declaration'->>'destination')->>'unit' IS DISTINCT FROM producer->>'unit'
   THEN RETURN false; END IF;
  IF pin->'source_value'='null'::jsonb THEN RETURN false; END IF;
  amount=(pin->>'source_value')::numeric*(conversion->>'factor')::numeric;
  IF amount IS DISTINCT FROM (pin->>'destination_value')::numeric THEN RETURN false; END IF;
 END LOOP;
 RETURN true;
END $$;
"""
PREVIOUS=import_module('apps.workflows.migrations.0064_factory_performance').SQL
ORIGINAL="""OR si.declaration->>'source_sign' IS NULL OR si.declaration->>'source_sign' IS DISTINCT FROM si.declaration->>'destination_sign'
     OR sr.result->'company'->si.metric->'value' IS DISTINCT FROM r.result->'company'->si.destination->'value'"""
# The legacy identity condition stays literal. Only the explicitly versioned v2 branch can convert.
REPLACEMENT="""OR (r.snapshot->>'implementation' IS DISTINCT FROM 'finance-statement-inputs/v2' AND (false """+ORIGINAL+"""))
     OR NOT psl_statement_conventions_current(r.id)"""
assert PREVIOUS.count(ORIGINAL)==1
SQL=PREVIOUS.replace(ORIGINAL,REPLACEMENT)
assert SQL.replace(REPLACEMENT,ORIGINAL)==PREVIOUS

class Migration(migrations.Migration):
    dependencies=[('workflows','0064_factory_performance'),('documents','0021_factory_performance_scope')]
    operations=[migrations.RunSQL(CURRENT),migrations.RunSQL(SQL)]

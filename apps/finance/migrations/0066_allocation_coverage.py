"""Explicit v2 allocation insertion guard; legacy and other kinds unchanged.

No staff factory replacement: that remains reserved for workflows0082.
"""
from django.db import migrations

SQL = r'''
-- Additive v2-only allocation coverage predicates. No arithmetic engine or v1 reinterpretation.
CREATE FUNCTION psl_allocation_v2_contract_current(cid uuid,v jsonb,staff boolean) RETURNS boolean LANGUAGE plpgsql STABLE AS $$
DECLARE cov jsonb; weights jsonb; method text; n integer; population_count integer; total numeric; denominator numeric;
 e record; newer record; candidate jsonb; expected jsonb; entry jsonb; amount numeric;
BEGIN
 cov=v->'weight_contract';method=v->>CASE WHEN staff THEN 'standard_method' ELSE 'method' END;
 IF method IS NULL THEN RETURN false; END IF;
 IF method<> 'fixed_weights' THEN RETURN coalesce(method=CASE WHEN staff THEN 'matched_bu' ELSE 'headcount_weighted' END AND cov='null'::jsonb,false); END IF;
 weights=v->CASE WHEN staff THEN 'standard_weights' ELSE 'weights' END;
 IF jsonb_typeof(cov) IS DISTINCT FROM 'object' OR NOT(cov ?& ARRAY['version','mode','population','completeness','denominator','basis','evidence_id'])
  OR (SELECT count(*) FROM jsonb_object_keys(cov))<>7 OR jsonb_typeof(cov->'evidence_id') IS DISTINCT FROM 'number' OR cov->>'version' IS DISTINCT FROM 'allocation-coverage/v1'
  OR jsonb_typeof(cov->'mode') IS DISTINCT FROM 'string' OR cov->>'mode' NOT IN ('relative_weights','declared_shares') OR cov->>'completeness' IS DISTINCT FROM 'complete'
  OR jsonb_typeof(cov->'basis') IS DISTINCT FROM 'string' OR (cov->>'basis')!~'^[A-Za-z0-9][A-Za-z0-9_.:-]{0,99}$'
  OR jsonb_typeof(cov->'population') IS DISTINCT FROM 'array' OR jsonb_typeof(weights) IS DISTINCT FROM 'array'
  OR (cov->>'evidence_id')!~'^[1-9][0-9]*([.]0+)?$' THEN RETURN false; END IF;
 n=jsonb_array_length(weights);population_count=jsonb_array_length(cov->'population');
 IF n<1 OR n>100 OR n<>population_count OR population_count<>(SELECT count(DISTINCT value) FROM jsonb_array_elements(cov->'population'))
  OR n<>(SELECT count(DISTINCT value->>'bu') FROM jsonb_array_elements(weights)) THEN RETURN false; END IF;
 total=0;
 FOR entry IN SELECT value FROM jsonb_array_elements(weights) LOOP
  IF jsonb_typeof(entry->'bu') IS DISTINCT FROM 'string' OR (entry->>'bu')!~'^[A-Za-z0-9][A-Za-z0-9_.:-]{0,99}$'
   OR NOT(cov->'population' ? (entry->>'bu')) OR jsonb_typeof(entry->'weight') IS DISTINCT FROM 'string' OR (entry->>'weight')!~'^-?(0|[1-9][0-9]{0,23})([.][0-9]{1,8})?$' THEN RETURN false; END IF;
  amount=(entry->>'weight')::numeric;
  IF amount<0 OR amount>=1e24::numeric OR scale(amount)>8 THEN RETURN false; END IF;
  total=total+amount;
 END LOOP;
 IF total<=0 THEN RETURN false; END IF;
 IF cov->>'mode'='relative_weights' THEN
  IF cov->'denominator' IS DISTINCT FROM 'null'::jsonb THEN RETURN false; END IF;
 ELSE
  IF jsonb_typeof(cov->'denominator') IS DISTINCT FROM 'string' OR (cov->>'denominator')!~'^-?(0|[1-9][0-9]{0,23})([.][0-9]{1,8})?$' THEN RETURN false; END IF;
  denominator=(cov->>'denominator')::numeric;
  IF denominator<=0 OR denominator>=1e24::numeric OR scale(denominator)>8 OR denominator<>total THEN RETURN false; END IF;
 END IF;
 IF staff AND (jsonb_typeof(v->'pool_contract_evidence_id') IS DISTINCT FROM 'number' OR (cov->>'evidence_id')::numeric IS DISTINCT FROM (v->>'pool_contract_evidence_id')::numeric) THEN RETURN false; END IF;
 IF NOT staff AND EXISTS(SELECT 1 FROM jsonb_array_elements_text(v->'excluded_bu_keys') b WHERE cov->'population' ? b.value) THEN RETURN false; END IF;
 SELECT * INTO e FROM core_evidence WHERE id=(cov->>'evidence_id')::numeric::bigint AND case_id=cid
  AND kind=CASE WHEN staff THEN 'bu_pool_contract' ELSE 'finance_pool_contract' END;
 IF NOT FOUND THEN RETURN false; END IF;
 expected=jsonb_build_object('entity',v->'entity','from_period',v->'from_period','to_period',v->'to_period',
  'pool',v->CASE WHEN staff THEN 'standard_pool_ref' ELSE 'pool' END,'weights',weights,
  'excluded_bu_keys',CASE WHEN staff THEN '[]'::jsonb ELSE v->'excluded_bu_keys' END,'coverage',cov-'evidence_id');
 IF e.body::jsonb IS DISTINCT FROM expected THEN RETURN false; END IF;
 FOR newer IN SELECT body FROM core_evidence WHERE case_id=cid AND kind=e.kind AND version>e.version LOOP
  BEGIN candidate=newer.body::jsonb; EXCEPTION WHEN OTHERS THEN CONTINUE; END;
  IF candidate->>'entity'=expected->>'entity' AND candidate->>'pool'=expected->>'pool'
   AND candidate->>'from_period' ~ '^[0-9]{4}-(0[1-9]|1[0-2])$' AND candidate->>'to_period' ~ '^[0-9]{4}-(0[1-9]|1[0-2])$'
   AND greatest(candidate->>'from_period',expected->>'from_period')<=least(candidate->>'to_period',expected->>'to_period') THEN RETURN false; END IF;
 END LOOP;
 RETURN true;
EXCEPTION WHEN OTHERS THEN RETURN false;
END $$;

CREATE FUNCTION psl_allocation_v2_policy_current(cid uuid,pid bigint) RETURNS boolean LANGUAGE plpgsql STABLE AS $$
DECLARE cfg record; r record; found_v2 boolean:=false; staff boolean;
BEGIN
 SELECT * INTO cfg FROM policy_configuration WHERE id=pid AND case_id=cid;
 IF NOT FOUND THEN RETURN false; END IF;
 staff=cfg.component='F21.allocation_rules';
 IF NOT staff AND cfg.component<>'D07.allocation_pool_rules' THEN RETURN true; END IF;
 FOR r IN SELECT rr.* FROM policy_registeredreference rr WHERE rr.case_id=cid AND
  ((staff AND rr.ref=cfg.envelope->'value'->>'artifact_ref' AND rr.version=(cfg.envelope->'value'->>'artifact_version')::integer)
   OR (NOT staff AND cfg.envelope->'value' ? rr.ref AND rr.version=1)) LOOP
  IF r.schema_ref=(CASE WHEN staff THEN 'schema:psl/bu-staff/v2' ELSE 'schema:psl/finance-pool/v2' END) THEN
   found_v2=true;
   IF staff AND (cfg.envelope->'value'->>'sha256' IS DISTINCT FROM r.sha256 OR cfg.envelope->'value'->>'schema_ref' IS DISTINCT FROM r.schema_ref) THEN RETURN false; END IF;
   IF psl_allocation_v2_contract_current(cid,r.content,staff) IS DISTINCT FROM true THEN RETURN false; END IF;
  END IF;
 END LOOP;
 IF NOT found_v2 THEN RETURN coalesce(NOT(staff AND cfg.envelope->'value'->>'schema_ref'='schema:psl/bu-staff/v2'),true); END IF;
 RETURN coalesce(psl_schedules_policy_current(cid,pid),false);
EXCEPTION WHEN OTHERS THEN RETURN false;
END $$;

CREATE FUNCTION psl_allocation_v2_result_current(cid uuid,pid bigint,result jsonb) RETURNS boolean LANGUAGE plpgsql STABLE AS $$
DECLARE cfg record; row_data jsonb; candidates jsonb; v jsonb; weights jsonb; total numeric; entry jsonb; has_v2 boolean; claimed_v2 boolean:=false;
BEGIN
 IF jsonb_typeof(result->'rows')='array' THEN
  SELECT EXISTS(SELECT 1 FROM jsonb_array_elements(result->'rows') x WHERE x.value->'basis'->>'weight_semantics'='explicit_contract'
   OR jsonb_typeof(x.value->'weight_contract')='object' OR jsonb_typeof(x.value->'basis'->'weight_contract')='object') INTO claimed_v2;
 END IF;
 SELECT * INTO cfg FROM policy_configuration WHERE id=pid AND case_id=cid AND component='D07.allocation_pool_rules';
 IF NOT FOUND THEN RETURN NOT claimed_v2; END IF;
 SELECT EXISTS(SELECT 1 FROM policy_registeredreference rr WHERE rr.case_id=cid AND cfg.envelope->'value' ? rr.ref AND rr.version=1 AND rr.schema_ref='schema:psl/finance-pool/v2') INTO has_v2;
 IF NOT has_v2 THEN RETURN NOT claimed_v2; END IF;
 IF psl_allocation_v2_policy_current(cid,pid) IS DISTINCT FROM true OR jsonb_typeof(result->'rows') IS DISTINCT FROM 'array' THEN RETURN false; END IF;
 IF result->>'status'='complete' AND jsonb_array_length(result->'rows')=0 THEN RETURN false; END IF;
 FOR row_data IN SELECT value FROM jsonb_array_elements(result->'rows') LOOP
  IF row_data->>'treatment'<>'pool' OR row_data->>'status' NOT IN ('allocated','residual_held') THEN CONTINUE; END IF;
  SELECT jsonb_agg(rr.content) INTO candidates FROM policy_registeredreference rr WHERE rr.case_id=cid AND cfg.envelope->'value' ? rr.ref AND rr.version=1
   AND rr.schema_ref='schema:psl/finance-pool/v2' AND rr.content->>'pool'=row_data->>'pool' AND rr.content->>'metric'=row_data->>'metric';
  IF candidates IS NULL THEN
   IF row_data->'basis'->>'weight_semantics'='explicit_contract' OR jsonb_typeof(row_data->'weight_contract')='object'
    OR jsonb_typeof(row_data->'basis'->'weight_contract')='object' THEN RETURN false; END IF;
   CONTINUE;
  END IF;
  SELECT jsonb_agg(value) INTO candidates FROM jsonb_array_elements(candidates) WHERE value->>'entity'=result->>'entity'
   AND value->>'from_period'<=result->>'period' AND value->>'to_period'>=result->>'period';
  IF candidates IS NULL OR jsonb_array_length(candidates)<>1 THEN RETURN false; END IF;
  v=candidates->0;
  IF v->>'method'<>'fixed_weights' THEN CONTINUE; END IF;
  IF row_data->>'pool_rule' IS DISTINCT FROM v->>'key' OR row_data->'weight_contract' IS DISTINCT FROM v->'weight_contract'
   OR row_data->'basis'->'weight_contract' IS DISTINCT FROM v->'weight_contract'
   OR row_data->'basis'->>'method' IS DISTINCT FROM 'explicit_fixed_weights' THEN RETURN false; END IF;
  weights=v->'weights';total=0;
  IF jsonb_typeof(row_data->'basis'->'weights') IS DISTINCT FROM 'object'
   OR (SELECT count(*) FROM jsonb_object_keys(row_data->'basis'->'weights'))<>jsonb_array_length(weights) THEN RETURN false; END IF;
  FOR entry IN SELECT value FROM jsonb_array_elements(weights) LOOP
   IF (row_data->'basis'->'weights'->>(entry->>'bu'))::numeric IS DISTINCT FROM (entry->>'weight')::numeric THEN RETURN false; END IF;
   total=total+(entry->>'weight')::numeric;
  END LOOP;
  IF (row_data->>'denominator')::numeric IS DISTINCT FROM total THEN RETURN false; END IF;
 END LOOP;
 RETURN true;
EXCEPTION WHEN OTHERS THEN RETURN false;
END $$;

CREATE FUNCTION psl_allocation_v2_insert_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE pid bigint;
BEGIN
 IF NEW.kind<>'allocation' THEN RETURN NEW; END IF;
 pid=(NEW.snapshot->'policies'->'D07.allocation_pool_rules'->>'id')::bigint;
 IF psl_allocation_v2_result_current(NEW.case_id,pid,NEW.result) IS DISTINCT FROM true THEN
  RAISE EXCEPTION 'Explicit v2 allocation coverage, evidence or result pins are not current';
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER psl_allocation_v2_insert_guard BEFORE INSERT ON finance_financerun FOR EACH ROW EXECUTE FUNCTION psl_allocation_v2_insert_guard();
'''

REVERSE = r'''
DROP TRIGGER psl_allocation_v2_insert_guard ON finance_financerun;
DROP FUNCTION psl_allocation_v2_insert_guard();
DROP FUNCTION psl_allocation_v2_result_current(uuid,bigint,jsonb);
DROP FUNCTION psl_allocation_v2_policy_current(uuid,bigint);
DROP FUNCTION psl_allocation_v2_contract_current(uuid,jsonb,boolean);
'''

class Migration(migrations.Migration):
    dependencies = [('finance','0065_contract_coverage'), ('workflows','0076_factory_bu')]
    operations = [migrations.RunSQL(SQL, REVERSE)]

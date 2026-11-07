"""Add only explicit-v2 allocation currentness to the native BU predicate."""
from django.db import migrations

PARENT_SHA256 = '3d80719b805e15df332b9db0b6dd93460b2ed436bd4a1dcdcc87e744a7fc7c30'
PARENT_SQL = r'''CREATE OR REPLACE FUNCTION psl_bu_current(wid bigint,depth integer DEFAULT 0) RETURNS boolean LANGUAGE plpgsql STABLE AS $$
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
'''
SQL = r'''CREATE OR REPLACE FUNCTION psl_bu_current(wid bigint,depth integer DEFAULT 0) RETURNS boolean LANGUAGE plpgsql STABLE AS $$
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
   IF psl_allocation_v2_policy_current(w.case_id,(w.metadata->'policy_ids'->>'F21.allocation_rules')::bigint) IS DISTINCT FROM true THEN RETURN false; END IF;
   IF (w.payload->>'weight_semantics'='explicit_contract' OR jsonb_typeof(w.payload->'weight_contract')='object')
    AND NOT EXISTS(SELECT 1 FROM policy_configuration cfg JOIN policy_registeredreference rr ON rr.case_id=cfg.case_id
     AND rr.ref=cfg.envelope->'value'->>'artifact_ref' AND rr.version=(cfg.envelope->'value'->>'artifact_version')::integer
     WHERE cfg.id=(w.metadata->'policy_ids'->>'F21.allocation_rules')::bigint AND rr.schema_ref='schema:psl/bu-staff/v2') THEN RETURN false; END IF;
   IF EXISTS(SELECT 1 FROM policy_configuration cfg JOIN policy_registeredreference rr ON rr.case_id=cfg.case_id
    AND rr.ref=cfg.envelope->'value'->>'artifact_ref' AND rr.version=(cfg.envelope->'value'->>'artifact_version')::integer
    WHERE cfg.id=(w.metadata->'policy_ids'->>'F21.allocation_rules')::bigint AND rr.schema_ref='schema:psl/bu-staff/v2')
    AND w.payload->'weight_contract' IS DISTINCT FROM v->'weight_contract' THEN RETURN false; END IF;
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
   OR psl_allocation_v2_result_current(w.case_id,(cmp.snapshot->'policies'->'D07.allocation_pool_rules'->>'id')::bigint,cmp.result) IS DISTINCT FROM true
  THEN RETURN false; END IF;
 END IF;
 RETURN true;
END $$;
'''

def require_exact_parent(apps, schema_editor):
    import hashlib
    assert hashlib.sha256(PARENT_SQL.encode()).hexdigest() == PARENT_SHA256
    expected = PARENT_SQL.split('AS $$', 1)[1].rsplit('$$;', 1)[0]
    with schema_editor.connection.cursor() as cursor:
        cursor.execute("SELECT prosrc FROM pg_proc WHERE oid='psl_bu_current(bigint,integer)'::regprocedure")
        if cursor.fetchone()[0] != expected:
            raise RuntimeError('BU currentness predecessor differs from the frozen native function; reconcile before upgrading')

class Migration(migrations.Migration):
    dependencies = [('workflows', '0081_pmo_client_sections'), ('finance', '0066_allocation_coverage')]
    operations = [migrations.RunPython(require_exact_parent, migrations.RunPython.noop), migrations.RunSQL(SQL, PARENT_SQL)]

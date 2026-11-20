"""Require review and exact configured date fractions in native schedule verification."""

from django.db import migrations


GUARD_SQL = """
CREATE FUNCTION psl_ppe_asset_dates_current(sid bigint, rid bigint, basis bigint) RETURNS boolean
LANGUAGE plpgsql STABLE AS $$
DECLARE
 s finance_schedulework;
 r finance_schedulework;
 asset jsonb;
 facts jsonb;
 rule_ref jsonb;
 fraction numeric;
 count_matches integer;
 service text;
BEGIN
 SELECT * INTO s FROM finance_schedulework WHERE id=sid AND kind='ppe_schedule';
 SELECT * INTO r FROM finance_schedulework WHERE id=rid AND case_id=s.case_id AND kind='ppe_register';
 IF NOT FOUND OR (s.payload->>'register_id')::bigint IS DISTINCT FROM r.id THEN RETURN false; END IF;
 IF EXISTS(SELECT 1 FROM core_evidence e WHERE e.id=r.evidence_id AND e.case_id=r.case_id
   AND e.source='psl:ppe-private-asset-dates/v1'
   AND NOT psl_ppe_grants(r.case_id,e.created_by_id,ARRAY['case.read','finance.read','ppe.read','ppe.capture','evidence.add']))
 THEN RETURN false; END IF;
 FOR asset IN SELECT value FROM jsonb_array_elements(r.payload->'assets') WHERE value ? 'dates' LOOP
  facts := asset->'dates';
  IF NOT psl_ppe_review_current(basis) OR NOT EXISTS(
    SELECT 1 FROM finance_schedulereview rv WHERE rv.id=basis AND rv.work_id=r.id AND rv.authority->>'purpose'='basis')
   OR facts->>'contract' IS DISTINCT FROM 'psl/ppe-asset-dates/v1'
   OR COALESCE(facts->>'fraction_basis','') NOT IN ('explicit_supplied_fraction','reviewed_in_service_date')
   OR NOT EXISTS(SELECT 1 FROM core_evidence e WHERE e.case_id=r.case_id
     AND e.id=(facts->>'support_evidence_id')::bigint AND e.kind IN ('ppe_event','ppe_basis_explanation'))
   OR NOT EXISTS(SELECT 1 FROM core_evidence e WHERE e.case_id=r.case_id
     AND e.id=(facts->>'evidence_id')::bigint AND e.kind='ppe_asset_date_fact'
     AND e.source='psl:ppe-private-asset-dates/v1'
     AND e.body::jsonb=((facts-'evidence_id') || jsonb_build_object('asset_id',asset->>'asset_id'))
     AND psl_ppe_grants(r.case_id,e.created_by_id,ARRAY['case.read','finance.read','ppe.read','ppe.capture','evidence.add']))
  THEN RETURN false; END IF;
  IF facts->>'fraction_basis'='explicit_supplied_fraction' THEN CONTINUE; END IF;

  service := facts->>'in_service_date';
  IF service IS NULL OR NOT (s.snapshot->'policies' ? 'F07.in_service_fraction_rules') THEN RETURN false; END IF;
  IF rule_ref IS NULL THEN
   SELECT ref.content INTO rule_ref FROM policy_configuration c JOIN policy_registeredreference ref
    ON ref.case_id=c.case_id AND ref.ref=c.envelope->'value'->>'artifact_ref'
    AND ref.version=(c.envelope->'value'->>'artifact_version')::integer AND ref.sha256=c.envelope->'value'->>'sha256'
    WHERE c.id=(s.snapshot->'policies'->'F07.in_service_fraction_rules'->>'id')::bigint
    AND c.component='F07.in_service_fraction_rules' AND psl_ppe_policy_current(s.case_id,c.id);
   IF NOT FOUND THEN RETURN false; END IF;
  END IF;
  SELECT count(*), min((value->>'fraction')::numeric) INTO count_matches,fraction
   FROM jsonb_array_elements(rule_ref->'rules')
   WHERE value->>'category'=asset->>'category' AND value->>'period_start'=r.payload->>'period_start'
     AND value->>'period_end'=r.payload->>'period_end'
     AND service::date BETWEEN (value->>'in_service_from')::date AND (value->>'in_service_through')::date;
  IF count_matches<>1 OR fraction IS NULL OR NOT EXISTS(
   SELECT 1 FROM jsonb_array_elements(s.result->'rows') AS result_rows(result_row)
   WHERE result_row->>'asset_id'=asset->>'asset_id' AND result_row->>'fraction_basis'='reviewed_in_service_date'
     AND (result_row->>'used_fraction')::numeric=fraction)
  THEN RETURN false; END IF;
 END LOOP;
 RETURN true;
EXCEPTION WHEN data_exception THEN RETURN false;
END $$;
"""

PREVIOUS = "IF EXISTS(SELECT 1 FROM jsonb_each(s.snapshot->'policies') p"
CHECKED = "IF NOT psl_ppe_asset_dates_current(s.id,r.id,basis) THEN RETURN false; END IF;\n " + PREVIOUS


def replace_guard(schema_editor, previous, checked):
    with schema_editor.connection.cursor() as cursor:
        cursor.execute("SELECT pg_get_functiondef('psl_ppe_schedule_current(bigint,integer)'::regprocedure)")
        definition = cursor.fetchone()[0]
    if definition.count(previous) != 1 or 'psl_ppe_opening_owner_current(r.id)' not in definition:
        raise RuntimeError('Unexpected current native PPE schedule guard')
    schema_editor.execute(definition.replace(previous, checked), params=None)


def forwards(apps, schema_editor):
    schema_editor.execute(GUARD_SQL, params=None)
    replace_guard(schema_editor, PREVIOUS, CHECKED)


def backwards(apps, schema_editor):
    replace_guard(schema_editor, CHECKED, PREVIOUS)
    schema_editor.execute('DROP FUNCTION psl_ppe_asset_dates_current(bigint,bigint,bigint)', params=None)


class Migration(migrations.Migration):
    dependencies = [('workflows', '0094_invoice_milestone_proof')]
    operations = [migrations.RunPython(forwards, backwards)]

"""Permit scaled source runs only with an active, source-matched conversion rule."""
from django.db import migrations


ANCHOR = "status=psl_source_units(s.case_id,s.batch_id,s.unit_declaration);"
SCALED = """
 IF status='unsupported' THEN
   DECLARE cfg policy_configuration; rule jsonb; unit text; factor integer; pin jsonb;
   BEGIN
     pin := NEW.snapshot->'source_units';
     SELECT * INTO cfg FROM policy_configuration WHERE case_id=s.case_id
       AND component='D06.import_unit_conversion' AND id=(pin->>'policy')::bigint;
     IF NOT FOUND OR (SELECT state FROM policy_policystate WHERE configuration_id=cfg.id ORDER BY id DESC LIMIT 1)
         IS DISTINCT FROM 'active' OR (cfg.envelope->>'effective_from')::timestamptz > statement_timestamp()
         OR (cfg.envelope->>'effective_until')::timestamptz <= statement_timestamp()
       THEN RAISE EXCEPTION 'Current reviewed conversion is required'; END IF;
     rule := cfg.envelope->'value';
     unit := s.unit_declaration->'declarations'->0->>'unit';
     factor := CASE unit WHEN 'thousands_currency' THEN 1000 WHEN 'millions_currency' THEN 1000000 END;
     IF factor IS NULL OR rule->>'entity' IS DISTINCT FROM s.entity OR NOT (rule->'units' ? unit)
       OR rule->>'adjustment_unit' IS DISTINCT FROM 'major_currency'
       OR rule->>'control_total_unit' IS DISTINCT FROM 'as_declared_in_file'
       OR EXISTS (SELECT FROM jsonb_array_elements(s.unit_declaration->'declarations') d
                  WHERE d->>'feed' IS DISTINCT FROM rule->>'feed' OR d->>'unit' IS DISTINCT FROM unit)
       OR EXISTS (SELECT FROM finance_financialimport b, jsonb_array_elements(b.rows) r WHERE b.id=s.batch_id
                  AND (r->>'period' IS DISTINCT FROM rule->>'period' OR r->>'currency' IS DISTINCT FROM rule->>'currency'))
       OR pin IS DISTINCT FROM jsonb_build_object('status','converted_major_currency','declaration',s.unit_declaration,
                                                   'findings','[]'::jsonb,'factor',factor,'policy',cfg.id)
       THEN RAISE EXCEPTION 'Conversion does not match the evidenced source, rule and units'; END IF;
     RETURN NEW;
   END;
 END IF;
"""


def update_function(editor, before, after):
    with editor.connection.cursor() as cursor:
        cursor.execute("SELECT pg_get_functiondef('psl_source_units_run_insert()'::regprocedure)")
        definition = cursor.fetchone()[0]
        if definition.count(before) != 1:
            raise RuntimeError('Unexpected PostgreSQL source-unit guard.')
        cursor.execute(definition.replace(before, after))


def forwards(apps, editor):
    update_function(editor, ANCHOR, ANCHOR + SCALED)


def backwards(apps, editor):
    update_function(editor, ANCHOR + SCALED, ANCHOR)


class Migration(migrations.Migration):
    dependencies = [('finance', '0087_cash_reported_amount')]
    operations = [migrations.RunPython(forwards, backwards)]

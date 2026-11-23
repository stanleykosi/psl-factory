"""Require the current private opening proof owner in the native PPE SQL guard."""

from django.db import migrations


OWNER_SQL = """
CREATE FUNCTION psl_ppe_opening_owner_current(register_id bigint) RETURNS boolean
LANGUAGE sql STABLE AS $$
 SELECT NOT EXISTS(
   SELECT 1 FROM finance_schedulework r
   JOIN core_evidence e ON e.id=(r.payload->>'opening_evidence_id')::bigint AND e.case_id=r.case_id
   WHERE r.id=register_id AND r.kind='ppe_register' AND e.kind='ppe_opening'
    AND e.source='psl:ppe-private-opening-proof/v1'
    AND NOT psl_ppe_grants(r.case_id,e.created_by_id,
        ARRAY['case.read','finance.read','ppe.read','ppe.capture','ppe.report','evidence.add','factory.manage'])
 );
$$;
"""

ORIGINAL = "OR NOT psl_ppe_grants(r.case_id,r.actor_id,ARRAY['case.read','finance.read','ppe.read','ppe.capture'])"
PROTECTED = ORIGINAL + "\n  OR NOT psl_ppe_opening_owner_current(r.id)"


def replace_guard(schema_editor, old, new):
    with schema_editor.connection.cursor() as cursor:
        cursor.execute("SELECT pg_get_functiondef('psl_ppe_schedule_current(bigint,integer)'::regprocedure)")
        definition = cursor.fetchone()[0]
    if definition.count(old) != 1 or 'RETURN false;' not in definition or 'register_review' not in definition:
        raise RuntimeError('Unexpected native PPE verification predecessor')
    schema_editor.execute(definition.replace(old, new), params=None)


def forwards(apps, schema_editor):
    schema_editor.execute(OWNER_SQL, params=None)
    replace_guard(schema_editor, ORIGINAL, PROTECTED)


def backwards(apps, schema_editor):
    replace_guard(schema_editor, PROTECTED, ORIGINAL)
    schema_editor.execute('DROP FUNCTION psl_ppe_opening_owner_current(bigint)', params=None)


class Migration(migrations.Migration):
    dependencies = [('workflows', '0090_schedule_supplied_evidence')]
    operations = [migrations.RunPython(forwards, backwards)]

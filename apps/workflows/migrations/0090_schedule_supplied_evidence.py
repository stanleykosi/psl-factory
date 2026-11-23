"""Match the verified schedule's effective input when no override was supplied."""

from django.db import migrations


ORIGINAL = "s.payload=CASE WHEN s.kind='income' THEN e.body::jsonb->'payload' ELSE supplied.body::jsonb END"
EFFECTIVE = ("s.payload=CASE WHEN s.kind='income' THEN COALESCE(NULLIF(e.body::jsonb->'payload','null'::jsonb),"
             "supplied.body::jsonb) ELSE supplied.body::jsonb END")


def replace_guard(schema_editor, old, new):
    with schema_editor.connection.cursor() as cursor:
        cursor.execute("SELECT pg_get_functiondef('psl_factory_identity()'::regprocedure)")
        definition = cursor.fetchone()[0]
    if definition.count(old) != 1:
        raise RuntimeError('Unexpected selected schedule verification predecessor')
    schema_editor.execute(definition.replace(old, new), params=None)


def forwards(apps, schema_editor):
    replace_guard(schema_editor, ORIGINAL, EFFECTIVE)


def backwards(apps, schema_editor):
    replace_guard(schema_editor, EFFECTIVE, ORIGINAL)


class Migration(migrations.Migration):
    dependencies = [('workflows', '0089_handover_reply_provenance')]
    operations = [migrations.RunPython(forwards, backwards)]

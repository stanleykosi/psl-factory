"""Record supplied Millions alongside the other immutable source-unit labels."""

from django.db import migrations


PREVIOUS = (
    "NOT IN ('major_currency','thousands_currency','unknown')",
    "IF 'major_currency'=ANY(units) AND 'thousands_currency'=ANY(units) THEN RETURN 'conflict'; END IF;",
    "IF 'thousands_currency'=ANY(units) THEN RETURN 'unsupported'; END IF;",
)
CURRENT = (
    "NOT IN ('major_currency','thousands_currency','millions_currency','unknown')",
    "IF (SELECT count(DISTINCT unit) FROM unnest(units) AS supplied(unit) WHERE unit<>'unknown')>1 "
    "THEN RETURN 'conflict'; END IF;",
    "IF units && ARRAY['thousands_currency','millions_currency'] THEN RETURN 'unsupported'; END IF;",
)


def replace_checks(schema_editor, previous, current):
    with schema_editor.connection.cursor() as cursor:
        cursor.execute("SELECT pg_get_functiondef('psl_source_units(uuid,bigint,jsonb)'::regprocedure)")
        definition = cursor.fetchone()[0]
    for old, new in zip(previous, current, strict=True):
        if definition.count(old) != 1 or new in definition:
            raise RuntimeError('Unexpected exact PostgreSQL source-unit verifier')
        definition = definition.replace(old, new)
    schema_editor.execute(definition, params=None)


def forwards(apps, schema_editor):
    replace_checks(schema_editor, PREVIOUS, CURRENT)


def backwards(apps, schema_editor):
    with schema_editor.connection.cursor() as cursor:
        cursor.execute('LOCK TABLE finance_financesource IN SHARE ROW EXCLUSIVE MODE')
        cursor.execute("""
            SELECT EXISTS (
                SELECT 1 FROM finance_financesource
                WHERE unit_declaration->'declarations' @> '[{"unit":"millions_currency"}]'::jsonb
            )
        """)
        if cursor.fetchone()[0]:
            raise RuntimeError('Millions declarations already in source history require this validator')
    replace_checks(schema_editor, CURRENT, PREVIOUS)


class Migration(migrations.Migration):
    dependencies = [('finance', '0082_invoice_short_payment_decisions')]
    operations = [migrations.RunPython(forwards, backwards)]
